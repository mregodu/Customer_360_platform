"""Prediction pipeline for customer health scoring."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol

from customer360.classification.features import (
    CustomerHealthFeatureEngineer,
    HealthFeatureRow,
)
from customer360.classification.training import CLASS_LABELS, TrainedHealthModel
from customer360.domain.customer import CustomerHealthClass


class CustomerHealthScoreWriter(Protocol):
    """Persistence contract for predicted customer health scores."""

    def write_customer_health_scores(self, records: Iterable[Mapping[str, object]]) -> int:
        """Persist rows into `ANALYTICS.customer_health_scores`."""


@dataclass(frozen=True)
class CustomerHealthPredictionResult:
    """Summary from one health scoring prediction run."""

    rows_scored: int
    rows_written: int


class CustomerHealthPredictionPipeline:
    """Generates Snowflake-ready health score rows from a trained model."""

    def __init__(
        self,
        *,
        feature_engineer: CustomerHealthFeatureEngineer | None = None,
        writer: CustomerHealthScoreWriter | None = None,
    ) -> None:
        self._feature_engineer = feature_engineer or CustomerHealthFeatureEngineer(derive_labels=False)
        self._writer = writer

    def predict(
        self,
        records: Sequence[Mapping[str, object]],
        *,
        trained_model: TrainedHealthModel,
        load_batch_id: str | None = None,
    ) -> tuple[dict[str, object], ...]:
        """Predict customer health and return rows for `ANALYTICS.customer_health_scores`."""
        feature_rows = self._feature_engineer.build_feature_rows(records)
        labels = trained_model.predict_labels(feature_rows)
        probabilities = trained_model.predict_probabilities(feature_rows)
        scored_at = datetime.now(tz=UTC).isoformat()
        rows = [
            _prediction_row(
                feature_row,
                health_class=label,
                class_probabilities=probability,
                trained_model=trained_model,
                scored_at=scored_at,
                load_batch_id=load_batch_id,
            )
            for feature_row, label, probability in zip(feature_rows, labels, probabilities, strict=False)
        ]
        return tuple(rows)

    def predict_and_write(
        self,
        records: Sequence[Mapping[str, object]],
        *,
        trained_model: TrainedHealthModel,
        load_batch_id: str | None = None,
    ) -> CustomerHealthPredictionResult:
        """Predict health scores and persist them with the configured writer."""
        if self._writer is None:
            raise RuntimeError("CustomerHealthPredictionPipeline requires a writer for persistence.")
        rows = self.predict(records, trained_model=trained_model, load_batch_id=load_batch_id)
        written = self._writer.write_customer_health_scores(rows)
        return CustomerHealthPredictionResult(rows_scored=len(rows), rows_written=written)


def _prediction_row(
    feature_row: HealthFeatureRow,
    *,
    health_class: str,
    class_probabilities: Mapping[str, float],
    trained_model: TrainedHealthModel,
    scored_at: str,
    load_batch_id: str | None,
) -> dict[str, object]:
    record = feature_row.source_record
    churn_risk_score = round(float(class_probabilities.get(CustomerHealthClass.CHURN_RISK.value, 0.0)), 8)
    return {
        "golden_customer_id": feature_row.golden_customer_id,
        "score_date": feature_row.score_date,
        "company_name": _clean(record.get("company_name")),
        "email": _clean(record.get("email")),
        "industry": _clean(record.get("industry")),
        "lifetime_value": _float_or_none(record.get("lifetime_value")),
        "engagement_score": _float_or_none(record.get("engagement_score")),
        "adoption_score": _float_or_none(record.get("product_adoption_score") or record.get("adoption_score")),
        "renewal_probability": _float_or_none(record.get("renewal_probability")),
        "support_activity_score": _float_or_none(record.get("support_activity_score")),
        "satisfaction_score": _float_or_none(record.get("satisfaction_score")),
        "support_ticket_count": _float_or_none(record.get("support_ticket_count")),
        "active_users": _float_or_none(record.get("active_users")),
        "churn_risk_score": churn_risk_score,
        "health_class": health_class,
        "classification_reason": _classification_reason(health_class, class_probabilities),
        "model_version": trained_model.model_version,
        "model_algorithm": trained_model.algorithm,
        "class_probabilities": {label: class_probabilities.get(label, 0.0) for label in CLASS_LABELS},
        "feature_snapshot": dict(feature_row.feature_map),
        "scored_at": scored_at,
        "load_batch_id": load_batch_id or _clean(record.get("load_batch_id")),
    }


def _classification_reason(health_class: str, probabilities: Mapping[str, float]) -> str:
    churn_probability = probabilities.get(CustomerHealthClass.CHURN_RISK.value, 0.0)
    at_risk_probability = probabilities.get(CustomerHealthClass.AT_RISK.value, 0.0)
    healthy_probability = probabilities.get(CustomerHealthClass.HEALTHY.value, 0.0)
    return (
        f"Predicted {health_class} from product usage, support history, marketing engagement, "
        f"and renewal history. Probabilities: Healthy={healthy_probability:.4f}, "
        f"At Risk={at_risk_probability:.4f}, Churn Risk={churn_probability:.4f}."
    )


def _float_or_none(value: object) -> float | None:
    if value is None:
        return None
    if not isinstance(value, int | float | str):
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _clean(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.upper() in {"NULL", "NONE", "N/A", "NA"}:
        return None
    return text
