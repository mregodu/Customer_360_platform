"""Customer enrichment scoring formulas."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime

ENRICHMENT_MODEL_VERSION = "customer_enrichment_v1"


@dataclass(frozen=True)
class EnrichmentScores:
    """Calculated customer enrichment metrics."""

    lifetime_value: float
    product_adoption_score: float
    engagement_score: float
    support_health_score: float
    renewal_probability: float


class EnrichmentScoreCalculator:
    """Calculates explainable enrichment metrics from aggregated customer signals."""

    def score(self, signals: Mapping[str, object]) -> EnrichmentScores:
        """Calculate all enrichment scores for one customer/date aggregate."""
        product_adoption = product_adoption_score(
            product_usage_score=_optional_float(signals.get("product_usage_score")),
            active_users=_optional_float(signals.get("active_users")),
            active_days=_optional_float(signals.get("active_days")),
            feature_utilization_score=_optional_float(signals.get("feature_utilization_score")),
        )
        support_health = support_health_score(
            ticket_count=_optional_float(signals.get("support_ticket_count")),
            satisfaction_score=_optional_float(signals.get("satisfaction_score")),
            response_time_minutes=_optional_float(signals.get("response_time_minutes")),
            support_activity_score=_optional_float(signals.get("support_activity_score")),
        )
        engagement = engagement_score(
            product_usage_score=_optional_float(signals.get("product_usage_score")),
            marketing_engagement_score=_optional_float(signals.get("marketing_engagement_score")),
            support_activity_score=_optional_float(signals.get("support_activity_score")),
        )
        renewal = renewal_probability(
            engagement_score_value=engagement,
            product_adoption_score_value=product_adoption,
            support_health_score_value=support_health,
            renewal_status=_optional_text(signals.get("renewal_status")),
            license_expiration_date=_parse_date(signals.get("license_expiration_date")),
            as_of_date=_parse_date(signals.get("metric_date")),
        )
        lifetime = customer_lifetime_value(
            contract_value=_optional_float(signals.get("contract_value")),
            renewal_probability_value=renewal,
            engagement_score_value=engagement,
            product_adoption_score_value=product_adoption,
        )
        return EnrichmentScores(
            lifetime_value=lifetime,
            product_adoption_score=product_adoption,
            engagement_score=engagement,
            support_health_score=support_health,
            renewal_probability=renewal,
        )


def customer_lifetime_value(
    *,
    contract_value: float | None,
    renewal_probability_value: float,
    engagement_score_value: float,
    product_adoption_score_value: float,
) -> float:
    """Estimate CLV from contract value, retention likelihood, and expansion signals."""
    base_value = max(contract_value or 0.0, 0.0)
    if base_value == 0.0:
        return 0.0
    retention_multiplier = 1.0 + _required_score(renewal_probability_value)
    expansion_multiplier = 1.0 + (
        (_required_score(engagement_score_value) + _required_score(product_adoption_score_value)) / 4
    )
    return round(base_value * retention_multiplier * expansion_multiplier, 2)


def product_adoption_score(
    *,
    product_usage_score: float | None,
    active_users: float | None,
    active_days: float | None,
    feature_utilization_score: float | None,
) -> float:
    """Calculate normalized product adoption from usage, users, days, and features."""
    return _weighted_score(
        (
            (_clamp_score(product_usage_score), 0.45),
            (_normalize_count(active_users, target=50.0), 0.15),
            (_normalize_count(active_days, target=30.0), 0.15),
            (_clamp_score(feature_utilization_score), 0.25),
        )
    )


def engagement_score(
    *,
    product_usage_score: float | None,
    marketing_engagement_score: float | None,
    support_activity_score: float | None,
) -> float:
    """Calculate weighted engagement from product, marketing, and support activity."""
    return _weighted_score(
        (
            (_clamp_score(product_usage_score), 0.40),
            (_clamp_score(marketing_engagement_score), 0.35),
            (_clamp_score(support_activity_score), 0.25),
        )
    )


def support_health_score(
    *,
    ticket_count: float | None,
    satisfaction_score: float | None,
    response_time_minutes: float | None,
    support_activity_score: float | None,
) -> float:
    """Calculate support health where higher means fewer unresolved support concerns."""
    normalized_ticket_count = _normalize_count(ticket_count, target=25.0)
    normalized_response_time = _normalize_count(response_time_minutes, target=1440.0)
    ticket_component = (
        1.0 - normalized_ticket_count
        if normalized_ticket_count is not None
        else None
    )
    satisfaction_component = (
        _normalize_count(satisfaction_score, target=5.0)
        if satisfaction_score is not None
        else None
    )
    response_component = (
        1.0 - normalized_response_time
        if normalized_response_time is not None
        else None
    )
    if (
        ticket_component is None
        and satisfaction_component is None
        and response_component is None
        and support_activity_score is None
    ):
        return 1.0
    return _weighted_score(
        (
            (ticket_component, 0.30),
            (satisfaction_component, 0.35),
            (response_component, 0.20),
            (_clamp_score(support_activity_score), 0.15),
        )
    )


def renewal_probability(
    *,
    engagement_score_value: float,
    product_adoption_score_value: float,
    support_health_score_value: float,
    renewal_status: str | None,
    license_expiration_date: date | None,
    as_of_date: date | None = None,
) -> float:
    """Estimate renewal probability from behavior, support health, status, and timing."""
    timing_score = _expiration_timing_score(license_expiration_date, as_of_date)
    return _weighted_score(
        (
            (_status_probability(renewal_status), 0.30),
            (_clamp_score(engagement_score_value), 0.25),
            (_clamp_score(product_adoption_score_value), 0.20),
            (_clamp_score(support_health_score_value), 0.20),
            (timing_score, 0.05),
        )
    )


def _weighted_score(components: Sequence[tuple[float | None, float]]) -> float:
    available: list[tuple[float, float]] = []
    for value, weight in components:
        if value is not None and weight > 0:
            available.append((value, weight))
    if not available:
        return 0.0
    numerator = sum(_required_score(value) * weight for value, weight in available)
    denominator = sum(weight for _, weight in available)
    return round(numerator / denominator, 4)


def _status_probability(status: str | None) -> float | None:
    if status is None:
        return None
    normalized = status.strip().upper().replace("-", "_").replace(" ", "_")
    if normalized in {"RENEWED", "ACTIVE", "AUTO_RENEW", "AUTO_RENEWAL"}:
        return 0.95
    if normalized in {"OPEN", "PENDING", "IN_PROGRESS"}:
        return 0.65
    if normalized in {"AT_RISK", "RISK", "DOWNGRADE_RISK"}:
        return 0.35
    if normalized in {"CANCELLED", "CANCELED", "CHURNED", "EXPIRED", "LOST"}:
        return 0.10
    return 0.55


def _expiration_timing_score(
    license_expiration_date: date | None,
    as_of_date: date | None,
) -> float | None:
    if license_expiration_date is None:
        return None
    comparison_date = as_of_date or datetime.now(tz=UTC).date()
    days_until_expiration = (license_expiration_date - comparison_date).days
    if days_until_expiration < 0:
        return 0.20
    if days_until_expiration <= 30:
        return 0.45
    if days_until_expiration <= 90:
        return 0.65
    return 0.85


def _normalize_count(value: float | None, *, target: float) -> float | None:
    if value is None:
        return None
    if target <= 0:
        return 0.0
    return _clamp_score(max(value, 0.0) / target)


def _clamp_score(value: float | None) -> float | None:
    if value is None:
        return None
    return max(0.0, min(1.0, float(value)))


def _required_score(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _optional_float(value: object) -> float | None:
    if value is None:
        return None
    if not isinstance(value, int | float | str):
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _parse_date(value: object) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = _optional_text(value)
    if text is None:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
    except ValueError:
        try:
            return date.fromisoformat(text[:10])
        except ValueError:
            return None
