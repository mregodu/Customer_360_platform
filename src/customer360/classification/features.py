"""Feature engineering for customer health scoring."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime

from customer360.classification.rules import classify_customer
from customer360.domain.customer import CustomerHealthClass

HEALTH_FEATURE_COLUMNS = (
    "product_usage_score",
    "product_adoption_score",
    "marketing_engagement_score",
    "engagement_score",
    "support_health_score",
    "support_ticket_count_norm",
    "satisfaction_score_norm",
    "response_time_risk",
    "active_users_norm",
    "active_days_norm",
    "renewal_probability",
    "renewal_status_risk",
    "renewal_timing_risk",
    "lifetime_value_norm",
    "contract_value_norm",
)

LABEL_CANDIDATES = (
    "health_class",
    "derived_health_class",
    "target_health_class",
    "customer_health_class",
    "label",
)


@dataclass(frozen=True)
class HealthFeatureRow:
    """One engineered customer health feature row."""

    golden_customer_id: str
    score_date: str
    features: tuple[float, ...]
    feature_map: Mapping[str, float]
    source_record: Mapping[str, object]
    label: CustomerHealthClass | None = None


class CustomerHealthFeatureEngineer:
    """Builds model-ready features from customer enrichment metrics."""

    def __init__(
        self,
        *,
        feature_columns: Sequence[str] = HEALTH_FEATURE_COLUMNS,
        derive_labels: bool = True,
    ) -> None:
        self.feature_columns = tuple(feature_columns)
        self.derive_labels = derive_labels

    def build_feature_rows(
        self,
        records: Sequence[Mapping[str, object]],
        *,
        require_label: bool = False,
    ) -> tuple[HealthFeatureRow, ...]:
        """Convert enrichment records into typed feature rows."""
        feature_rows: list[HealthFeatureRow] = []
        for record in records:
            golden_customer_id = _clean(record.get("golden_customer_id"))
            score_date = _score_date(record.get("score_date") or record.get("metric_date"))
            if golden_customer_id is None or score_date is None:
                continue

            feature_map = _feature_map(record)
            label = _explicit_label(record)
            if label is None and self.derive_labels:
                label = _derive_label(record, feature_map)
            if require_label and label is None:
                continue

            feature_rows.append(
                HealthFeatureRow(
                    golden_customer_id=golden_customer_id,
                    score_date=score_date,
                    features=tuple(feature_map[column] for column in self.feature_columns),
                    feature_map={column: feature_map[column] for column in self.feature_columns},
                    source_record=record,
                    label=label,
                )
            )
        return tuple(feature_rows)


def _feature_map(record: Mapping[str, object]) -> dict[str, float]:
    product_usage_score = _score(record.get("product_usage_score"))
    product_adoption_score = _score(
        record.get("product_adoption_score") or record.get("adoption_score")
    )
    marketing_engagement_score = _score(record.get("marketing_engagement_score"))
    engagement = _score(record.get("engagement_score"))
    support_health = _score(record.get("support_health_score"), default=1.0)
    renewal_probability = _score(record.get("renewal_probability"))

    return {
        "product_usage_score": product_usage_score,
        "product_adoption_score": product_adoption_score,
        "marketing_engagement_score": marketing_engagement_score,
        "engagement_score": engagement,
        "support_health_score": support_health,
        "support_ticket_count_norm": _normalize_count(record.get("support_ticket_count"), 25.0),
        "satisfaction_score_norm": _normalize_count(record.get("satisfaction_score"), 5.0),
        "response_time_risk": _normalize_count(record.get("response_time_minutes"), 1440.0),
        "active_users_norm": _normalize_count(record.get("active_users"), 50.0),
        "active_days_norm": _normalize_count(record.get("active_days"), 30.0),
        "renewal_probability": renewal_probability,
        "renewal_status_risk": _renewal_status_risk(record.get("renewal_status")),
        "renewal_timing_risk": _renewal_timing_risk(
            record.get("license_expiration_date"),
            record.get("score_date") or record.get("metric_date"),
        ),
        "lifetime_value_norm": _money_norm(record.get("lifetime_value")),
        "contract_value_norm": _money_norm(record.get("contract_value")),
    }


def _derive_label(
    record: Mapping[str, object],
    feature_map: Mapping[str, float],
) -> CustomerHealthClass:
    renewal_status_risk = feature_map["renewal_status_risk"]
    renewal_probability = feature_map["renewal_probability"]
    support_risk = 1.0 - feature_map["support_health_score"]

    if renewal_status_risk >= 0.90 or renewal_probability <= 0.20:
        return CustomerHealthClass.CHURN_RISK
    if renewal_probability < 0.35 or support_risk >= 0.75:
        return CustomerHealthClass.CHURN_RISK

    health_class = classify_customer(
        feature_map["engagement_score"],
        feature_map["product_adoption_score"],
        support_risk,
    )
    if health_class == CustomerHealthClass.HEALTHY and _score(record.get("renewal_probability")) < 0.55:
        return CustomerHealthClass.AT_RISK
    return health_class


def _explicit_label(record: Mapping[str, object]) -> CustomerHealthClass | None:
    for field_name in LABEL_CANDIDATES:
        parsed = parse_health_class(record.get(field_name))
        if parsed is not None:
            return parsed
    return None


def parse_health_class(value: object) -> CustomerHealthClass | None:
    """Parse a health class label from source data."""
    text = _clean(value)
    if text is None:
        return None
    normalized = text.strip().upper().replace("_", " ").replace("-", " ")
    if normalized == "HEALTHY":
        return CustomerHealthClass.HEALTHY
    if normalized == "AT RISK":
        return CustomerHealthClass.AT_RISK
    if normalized == "CHURN RISK":
        return CustomerHealthClass.CHURN_RISK
    return None


def _renewal_status_risk(value: object) -> float:
    status = _clean(value)
    if status is None:
        return 0.50
    normalized = status.upper().replace("-", "_").replace(" ", "_")
    if normalized in {"RENEWED", "ACTIVE", "AUTO_RENEW", "AUTO_RENEWAL"}:
        return 0.05
    if normalized in {"OPEN", "PENDING", "IN_PROGRESS"}:
        return 0.40
    if normalized in {"AT_RISK", "RISK", "DOWNGRADE_RISK"}:
        return 0.75
    if normalized in {"CANCELLED", "CANCELED", "CHURNED", "EXPIRED", "LOST"}:
        return 1.00
    return 0.50


def _renewal_timing_risk(expiration_value: object, score_date_value: object) -> float:
    expiration_date = _parse_date(expiration_value)
    score_date = _parse_date(score_date_value)
    if expiration_date is None or score_date is None:
        return 0.50
    days_until_expiration = (expiration_date - score_date).days
    if days_until_expiration < 0:
        return 1.00
    if days_until_expiration <= 30:
        return 0.75
    if days_until_expiration <= 90:
        return 0.45
    return 0.15


def _money_norm(value: object) -> float:
    amount = _float_or_default(value, 0.0)
    if amount <= 0:
        return 0.0
    return round(min(math.log1p(amount) / math.log1p(100_000.0), 1.0), 6)


def _normalize_count(value: object, target: float) -> float:
    if target <= 0:
        return 0.0
    return _clamp(_float_or_default(value, 0.0) / target)


def _score(value: object, default: float = 0.0) -> float:
    return _clamp(_float_or_default(value, default))


def _clamp(value: float) -> float:
    return round(max(0.0, min(1.0, value)), 6)


def _float_or_default(value: object, default: float) -> float:
    if value is None:
        return default
    if not isinstance(value, int | float | str):
        return default
    try:
        return float(value)
    except ValueError:
        return default


def _score_date(value: object) -> str | None:
    parsed = _parse_date(value)
    return parsed.isoformat() if parsed is not None else None


def _parse_date(value: object) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = _clean(value)
    if text is None:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
    except ValueError:
        try:
            return date.fromisoformat(text[:10])
        except ValueError:
            return None


def _clean(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.upper() in {"NULL", "NONE", "N/A", "NA"}:
        return None
    return text
