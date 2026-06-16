"""Classification module for customer health classes and churn-risk labels."""

from customer360.classification.features import (
    HEALTH_FEATURE_COLUMNS,
    CustomerHealthFeatureEngineer,
    HealthFeatureRow,
    parse_health_class,
)
from customer360.classification.models import (
    HealthModelAlgorithm,
    create_health_classifier,
)
from customer360.classification.prediction import (
    CustomerHealthPredictionPipeline,
    CustomerHealthPredictionResult,
    CustomerHealthScoreWriter,
)
from customer360.classification.rules import classify_customer
from customer360.classification.training import (
    CLASS_LABELS,
    CustomerHealthTrainingPipeline,
    HealthModelEvaluation,
    HealthTrainingResult,
    TrainedHealthModel,
)

__all__ = [
    "CLASS_LABELS",
    "HEALTH_FEATURE_COLUMNS",
    "CustomerHealthFeatureEngineer",
    "CustomerHealthPredictionPipeline",
    "CustomerHealthPredictionResult",
    "CustomerHealthScoreWriter",
    "CustomerHealthTrainingPipeline",
    "HealthFeatureRow",
    "HealthModelAlgorithm",
    "HealthModelEvaluation",
    "HealthTrainingResult",
    "TrainedHealthModel",
    "classify_customer",
    "create_health_classifier",
    "parse_health_class",
]
