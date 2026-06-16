from __future__ import annotations

from collections.abc import Iterable, Mapping

from customer360.classification.features import (
    CustomerHealthFeatureEngineer,
    parse_health_class,
)
from customer360.classification.models import (
    HealthModelAlgorithm,
    create_health_classifier,
)
from customer360.classification.prediction import CustomerHealthPredictionPipeline
from customer360.classification.training import CustomerHealthTrainingPipeline
from customer360.domain.customer import CustomerHealthClass


class FakeHealthScoreWriter:
    def __init__(self) -> None:
        self.records: list[dict[str, object]] = []

    def write_customer_health_scores(self, records: Iterable[Mapping[str, object]]) -> int:
        rows = [dict(record) for record in records]
        self.records.extend(rows)
        return len(rows)


def test_feature_engineer_builds_product_support_marketing_and_renewal_features() -> None:
    rows = CustomerHealthFeatureEngineer().build_feature_rows(
        [
            {
                "golden_customer_id": "gold-1",
                "metric_date": "2024-04-01",
                "product_usage_score": 0.9,
                "product_adoption_score": 0.8,
                "marketing_engagement_score": 0.7,
                "engagement_score": 0.8,
                "support_health_score": 0.9,
                "support_ticket_count": 2,
                "satisfaction_score": 4.5,
                "response_time_minutes": 60,
                "active_users": 20,
                "active_days": 22,
                "renewal_probability": 0.9,
                "renewal_status": "ACTIVE",
                "license_expiration_date": "2024-12-01",
                "lifetime_value": 25000,
                "contract_value": 10000,
            }
        ]
    )

    assert len(rows) == 1
    row = rows[0]
    assert row.golden_customer_id == "gold-1"
    assert row.score_date == "2024-04-01"
    assert row.label == CustomerHealthClass.HEALTHY
    assert row.feature_map["product_usage_score"] == 0.9
    assert row.feature_map["support_ticket_count_norm"] == 0.08
    assert row.feature_map["renewal_status_risk"] == 0.05


def test_training_pipeline_trains_and_evaluates_logistic_regression() -> None:
    result = CustomerHealthTrainingPipeline(model_version="customer_health_test_v1").train(
        _training_records(),
        algorithm=HealthModelAlgorithm.LOGISTIC_REGRESSION,
        test_size=0.34,
    )

    assert result.trained_model.algorithm == "logistic_regression"
    assert result.evaluation.model_version == "customer_health_test_v1"
    assert result.evaluation.training_rows > 0
    assert result.evaluation.validation_rows > 0
    assert 0.0 <= result.evaluation.accuracy <= 1.0
    assert result.evaluation.confusion_matrix


def test_prediction_pipeline_generates_snowflake_ready_rows() -> None:
    trained = CustomerHealthTrainingPipeline(model_version="customer_health_test_v1").train(
        _training_records(),
        algorithm=HealthModelAlgorithm.LOGISTIC_REGRESSION,
        test_size=0.34,
    ).trained_model

    rows = CustomerHealthPredictionPipeline().predict(
        [
            {
                "golden_customer_id": "gold-new",
                "metric_date": "2024-04-02",
                "company_name": "ACME INC",
                "email": "hello@example.com",
                "industry": "SOFTWARE",
                "lifetime_value": 5000,
                "product_usage_score": 0.2,
                "product_adoption_score": 0.2,
                "marketing_engagement_score": 0.1,
                "engagement_score": 0.2,
                "support_health_score": 0.2,
                "support_activity_score": 0.2,
                "support_ticket_count": 20,
                "satisfaction_score": 1.5,
                "response_time_minutes": 1200,
                "active_users": 3,
                "active_days": 5,
                "renewal_probability": 0.15,
                "renewal_status": "AT_RISK",
                "license_expiration_date": "2024-04-15",
                "contract_value": 3000,
            }
        ],
        trained_model=trained,
        load_batch_id="batch-1",
    )

    assert len(rows) == 1
    row = rows[0]
    assert row["golden_customer_id"] == "gold-new"
    assert row["model_algorithm"] == "logistic_regression"
    assert row["model_version"] == "customer_health_test_v1"
    assert row["health_class"] in {
        CustomerHealthClass.HEALTHY.value,
        CustomerHealthClass.AT_RISK.value,
        CustomerHealthClass.CHURN_RISK.value,
    }
    assert isinstance(row["class_probabilities"], dict)
    assert isinstance(row["feature_snapshot"], dict)
    assert "Churn Risk" in row["class_probabilities"]
    assert row["load_batch_id"] == "batch-1"


def test_prediction_pipeline_writes_generated_rows() -> None:
    trained = CustomerHealthTrainingPipeline(model_version="customer_health_test_v1").train(
        _training_records(),
        algorithm=HealthModelAlgorithm.RANDOM_FOREST,
        test_size=0.34,
    ).trained_model
    writer = FakeHealthScoreWriter()
    pipeline = CustomerHealthPredictionPipeline(writer=writer)

    result = pipeline.predict_and_write(
        [_training_records()[0]],
        trained_model=trained,
    )

    assert result.rows_scored == 1
    assert result.rows_written == 1
    assert writer.records[0]["golden_customer_id"] == "gold-healthy-1"


def test_training_pipeline_skips_unavailable_xgboost_candidates() -> None:
    results = CustomerHealthTrainingPipeline(model_version="customer_health_test_v1").train_candidate_models(
        _training_records(),
        algorithms=(
            HealthModelAlgorithm.LOGISTIC_REGRESSION,
            HealthModelAlgorithm.RANDOM_FOREST,
            HealthModelAlgorithm.XGBOOST,
        ),
    )

    trained_algorithms = {result.trained_model.algorithm for result in results}
    assert {"logistic_regression", "random_forest"} <= trained_algorithms


def test_xgboost_factory_is_available_or_reports_clear_runtime_error() -> None:
    try:
        classifier = create_health_classifier(HealthModelAlgorithm.XGBOOST)
    except RuntimeError as exc:
        assert "xgboost" in str(exc).lower()
    else:
        assert hasattr(classifier, "fit")


def test_parse_health_class_accepts_expected_labels() -> None:
    assert parse_health_class("Healthy") == CustomerHealthClass.HEALTHY
    assert parse_health_class("at_risk") == CustomerHealthClass.AT_RISK
    assert parse_health_class("churn-risk") == CustomerHealthClass.CHURN_RISK


def _training_records() -> list[dict[str, object]]:
    return [
        _record("gold-healthy-1", "Healthy", 0.92, 0.88, 0.85, 0.90, 0.95, "ACTIVE"),
        _record("gold-healthy-2", "Healthy", 0.86, 0.82, 0.78, 0.84, 0.90, "RENEWED"),
        _record("gold-healthy-3", "Healthy", 0.95, 0.90, 0.88, 0.91, 0.96, "AUTO_RENEW"),
        _record("gold-risk-1", "At Risk", 0.55, 0.50, 0.45, 0.52, 0.58, "PENDING"),
        _record("gold-risk-2", "At Risk", 0.48, 0.44, 0.50, 0.47, 0.50, "OPEN"),
        _record("gold-risk-3", "At Risk", 0.62, 0.58, 0.40, 0.56, 0.52, "IN_PROGRESS"),
        _record("gold-churn-1", "Churn Risk", 0.20, 0.18, 0.10, 0.20, 0.15, "AT_RISK"),
        _record("gold-churn-2", "Churn Risk", 0.15, 0.20, 0.15, 0.18, 0.10, "CANCELLED"),
        _record("gold-churn-3", "Churn Risk", 0.28, 0.24, 0.20, 0.25, 0.22, "EXPIRED"),
    ]


def _record(
    customer_id: str,
    health_class: str,
    product_usage: float,
    adoption: float,
    marketing: float,
    engagement: float,
    renewal_probability: float,
    renewal_status: str,
) -> dict[str, object]:
    support_health = max(0.1, min(1.0, (engagement + renewal_probability) / 2))
    return {
        "golden_customer_id": customer_id,
        "metric_date": "2024-04-01",
        "health_class": health_class,
        "company_name": customer_id.upper(),
        "lifetime_value": 10000 * renewal_probability,
        "product_usage_score": product_usage,
        "product_adoption_score": adoption,
        "marketing_engagement_score": marketing,
        "engagement_score": engagement,
        "support_health_score": support_health,
        "support_activity_score": support_health,
        "support_ticket_count": int((1 - support_health) * 25),
        "satisfaction_score": support_health * 5,
        "response_time_minutes": (1 - support_health) * 1440,
        "active_users": int(product_usage * 50),
        "active_days": int(product_usage * 30),
        "renewal_probability": renewal_probability,
        "renewal_status": renewal_status,
        "license_expiration_date": "2024-12-01",
        "contract_value": 10000 * renewal_probability,
    }
