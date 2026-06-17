from __future__ import annotations

from collections.abc import Sequence
from dataclasses import replace
from typing import Any

import pytest

from customer360.classification.features import CustomerHealthFeatureEngineer
from customer360.classification.models import HealthModelAlgorithm
from customer360.classification.prediction import CustomerHealthPredictionPipeline
from customer360.classification.training import CustomerHealthTrainingPipeline
from customer360.domain.customer import CustomerHealthClass


def test_feature_engineer_skips_rows_without_customer_id_or_metric_date() -> None:
    rows = CustomerHealthFeatureEngineer().build_feature_rows(
        [
            {"metric_date": "2024-04-01", "product_usage_score": 0.9},
            {"golden_customer_id": "gold-1", "product_usage_score": 0.9},
            {"golden_customer_id": "gold-2", "metric_date": "2024-04-01", "product_usage_score": 0.9},
        ]
    )

    assert len(rows) == 1
    assert rows[0].golden_customer_id == "gold-2"


def test_feature_engineer_can_require_explicit_or_derived_labels() -> None:
    rows = CustomerHealthFeatureEngineer(derive_labels=False).build_feature_rows(
        [
            {
                "golden_customer_id": "gold-1",
                "metric_date": "2024-04-01",
                "product_usage_score": 0.9,
            }
        ],
        require_label=True,
    )

    assert rows == ()


def test_feature_engineer_derives_churn_risk_from_bad_renewal_signals() -> None:
    rows = CustomerHealthFeatureEngineer().build_feature_rows(
        [
            {
                "golden_customer_id": "gold-1",
                "metric_date": "2024-04-01",
                "engagement_score": 0.7,
                "product_adoption_score": 0.7,
                "support_health_score": 0.8,
                "renewal_probability": 0.1,
                "renewal_status": "CANCELLED",
            }
        ]
    )

    assert rows[0].label == CustomerHealthClass.CHURN_RISK
    assert rows[0].feature_map["renewal_status_risk"] == 1.0


def test_training_pipeline_rejects_too_few_labeled_records(
    health_training_records: list[dict[str, object]],
) -> None:
    with pytest.raises(ValueError, match="At least three"):
        CustomerHealthTrainingPipeline().train(health_training_records[:2])


def test_training_pipeline_rejects_single_class_training_set(
    health_training_records: list[dict[str, object]],
) -> None:
    healthy_only = [
        {**record, "health_class": "Healthy"}
        for record in health_training_records[:3]
    ]

    with pytest.raises(ValueError, match="At least two health classes"):
        CustomerHealthTrainingPipeline().train(healthy_only)


def test_train_candidate_models_can_raise_unavailable_runtime_errors(
    monkeypatch: pytest.MonkeyPatch,
    health_training_records: list[dict[str, object]],
) -> None:
    from customer360.classification import training

    def raise_runtime_error(*args: object, **kwargs: object) -> Any:
        raise RuntimeError("model unavailable")

    monkeypatch.setattr(training, "create_health_classifier", raise_runtime_error)

    with pytest.raises(RuntimeError, match="model unavailable"):
        CustomerHealthTrainingPipeline().train_candidate_models(
            health_training_records,
            algorithms=(HealthModelAlgorithm.LOGISTIC_REGRESSION,),
            skip_unavailable=False,
        )


def test_prediction_pipeline_requires_writer_for_predict_and_write(
    health_training_records: list[dict[str, object]],
) -> None:
    trained = CustomerHealthTrainingPipeline().train(health_training_records).trained_model

    with pytest.raises(RuntimeError, match="requires a writer"):
        CustomerHealthPredictionPipeline().predict_and_write(
            [health_training_records[0]],
            trained_model=trained,
        )


def test_trained_model_probability_fallback_for_estimators_without_predict_proba(
    health_training_records: list[dict[str, object]],
) -> None:
    trained = CustomerHealthTrainingPipeline().train(health_training_records).trained_model

    class LabelOnlyEstimator:
        classes_ = trained.estimator.classes_

        def predict(self, matrix: Sequence[Sequence[float]]) -> Any:
            return trained.estimator.predict(matrix)

    label_only = replace(trained, estimator=LabelOnlyEstimator())
    feature_rows = CustomerHealthFeatureEngineer().build_feature_rows([health_training_records[0]])

    probabilities = label_only.predict_probabilities(feature_rows)

    assert len(probabilities) == 1
    assert sum(probabilities[0].values()) == 1.0
    assert set(probabilities[0]) == {
        CustomerHealthClass.HEALTHY.value,
        CustomerHealthClass.AT_RISK.value,
        CustomerHealthClass.CHURN_RISK.value,
    }
