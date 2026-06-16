"""Model factories for customer health scoring algorithms."""

from __future__ import annotations

from enum import StrEnum
from typing import Any


class HealthModelAlgorithm(StrEnum):
    """Supported supervised customer health model algorithms."""

    LOGISTIC_REGRESSION = "logistic_regression"
    RANDOM_FOREST = "random_forest"
    XGBOOST = "xgboost"


def create_health_classifier(
    algorithm: HealthModelAlgorithm | str,
    *,
    random_state: int = 42,
    class_count: int = 3,
) -> Any:
    """Create an unfitted classifier for the requested algorithm."""
    parsed_algorithm = HealthModelAlgorithm(algorithm)
    if parsed_algorithm is HealthModelAlgorithm.LOGISTIC_REGRESSION:
        from sklearn.linear_model import LogisticRegression

        return LogisticRegression(
            class_weight="balanced",
            max_iter=1000,
            random_state=random_state,
        )
    if parsed_algorithm is HealthModelAlgorithm.RANDOM_FOREST:
        from sklearn.ensemble import RandomForestClassifier

        return RandomForestClassifier(
            n_estimators=200,
            min_samples_leaf=2,
            class_weight="balanced",
            random_state=random_state,
        )

    try:
        from xgboost import XGBClassifier
    except ModuleNotFoundError as exc:  # pragma: no cover - depends on runtime extras
        raise RuntimeError(
            "xgboost is required for HealthModelAlgorithm.XGBOOST. "
            "Install project dependencies from requirements.txt."
        ) from exc

    return XGBClassifier(
        objective="multi:softprob",
        num_class=class_count,
        eval_metric="mlogloss",
        n_estimators=200,
        max_depth=4,
        learning_rate=0.08,
        subsample=0.9,
        colsample_bytree=0.9,
        random_state=random_state,
    )
