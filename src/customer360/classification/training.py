"""Training and evaluation pipeline for customer health scoring models."""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from customer360.classification.features import (
    HEALTH_FEATURE_COLUMNS,
    CustomerHealthFeatureEngineer,
    HealthFeatureRow,
)
from customer360.classification.models import (
    HealthModelAlgorithm,
    create_health_classifier,
)
from customer360.domain.customer import CustomerHealthClass

CLASS_LABELS = (
    CustomerHealthClass.HEALTHY.value,
    CustomerHealthClass.AT_RISK.value,
    CustomerHealthClass.CHURN_RISK.value,
)


@dataclass(frozen=True)
class HealthModelEvaluation:
    """Evaluation metrics for one trained health scoring model."""

    algorithm: str
    model_version: str
    trained_at: str
    training_rows: int
    validation_rows: int
    accuracy: float
    macro_f1: float
    confusion_matrix: list[list[int]]
    classification_report: Mapping[str, object]
    label_distribution: Mapping[str, int]

    def to_row(self, *, load_batch_id: str | None = None) -> dict[str, object]:
        """Return a Snowflake-ready model evaluation row."""
        return {
            "model_version": self.model_version,
            "algorithm": self.algorithm,
            "trained_at": self.trained_at,
            "training_rows": self.training_rows,
            "validation_rows": self.validation_rows,
            "accuracy": self.accuracy,
            "macro_f1": self.macro_f1,
            "metrics": {
                "confusion_matrix": self.confusion_matrix,
                "classification_report": dict(self.classification_report),
                "label_distribution": dict(self.label_distribution),
            },
            "load_batch_id": load_batch_id,
        }


@dataclass(frozen=True)
class TrainedHealthModel:
    """A fitted customer health model plus preprocessing metadata."""

    algorithm: str
    estimator: Any
    label_encoder: Any
    feature_columns: tuple[str, ...]
    model_version: str
    trained_at: str
    evaluation: HealthModelEvaluation

    def predict_labels(self, feature_rows: Sequence[HealthFeatureRow]) -> tuple[str, ...]:
        """Predict health class labels for feature rows."""
        encoded = self.estimator.predict(_matrix(feature_rows))
        return tuple(str(label) for label in self.label_encoder.inverse_transform(encoded))

    def predict_probabilities(
        self,
        feature_rows: Sequence[HealthFeatureRow],
    ) -> tuple[dict[str, float], ...]:
        """Predict class probabilities aligned to all supported health classes."""
        if not hasattr(self.estimator, "predict_proba"):
            labels = self.predict_labels(feature_rows)
            return tuple(
                {
                    label: 1.0 if label == predicted_label else 0.0
                    for label in CLASS_LABELS
                }
                for predicted_label in labels
            )

        raw_probabilities = self.estimator.predict_proba(_matrix(feature_rows))
        model_classes = [
            str(self.label_encoder.inverse_transform([int(encoded_class)])[0])
            for encoded_class in self.estimator.classes_
        ]
        aligned: list[dict[str, float]] = []
        for row_probabilities in raw_probabilities:
            class_probabilities = {label: 0.0 for label in CLASS_LABELS}
            for label, probability in zip(model_classes, row_probabilities, strict=False):
                class_probabilities[label] = round(float(probability), 8)
            aligned.append(class_probabilities)
        return tuple(aligned)


@dataclass(frozen=True)
class HealthTrainingResult:
    """Result from fitting and evaluating one health model."""

    trained_model: TrainedHealthModel
    evaluation: HealthModelEvaluation


class CustomerHealthTrainingPipeline:
    """Fits Logistic Regression, Random Forest, or XGBoost health classifiers."""

    def __init__(
        self,
        *,
        feature_engineer: CustomerHealthFeatureEngineer | None = None,
        model_version: str = "customer_health_v1",
        random_state: int = 42,
    ) -> None:
        self._feature_engineer = feature_engineer or CustomerHealthFeatureEngineer()
        self._model_version = model_version
        self._random_state = random_state

    def train(
        self,
        records: Sequence[Mapping[str, object]],
        *,
        algorithm: HealthModelAlgorithm | str = HealthModelAlgorithm.LOGISTIC_REGRESSION,
        test_size: float = 0.25,
    ) -> HealthTrainingResult:
        """Train and evaluate one customer health classifier."""
        feature_rows = self._feature_engineer.build_feature_rows(records, require_label=True)
        if len(feature_rows) < 3:
            raise ValueError("At least three labeled records are required to train health scoring.")

        labels = [row.label.value for row in feature_rows if row.label is not None]
        if len(set(labels)) < 2:
            raise ValueError("At least two health classes are required to train health scoring.")

        parsed_algorithm = HealthModelAlgorithm(algorithm)
        classifier = create_health_classifier(
            parsed_algorithm,
            random_state=self._random_state,
            class_count=len(CLASS_LABELS),
        )
        label_encoder = _label_encoder()
        y_all = label_encoder.transform(labels)
        split = _train_validation_split(
            feature_rows,
            y_all,
            test_size=test_size,
            random_state=self._random_state,
        )
        classifier.fit(split["x_train"], split["y_train"])
        y_pred = classifier.predict(split["x_validation"])

        trained_at = datetime.now(tz=UTC).isoformat()
        evaluation = _evaluate(
            algorithm=parsed_algorithm.value,
            model_version=self._model_version,
            trained_at=trained_at,
            y_true=split["y_validation"],
            y_pred=y_pred,
            label_encoder=label_encoder,
            training_rows=len(split["y_train"]),
            validation_rows=len(split["y_validation"]),
            label_distribution=Counter(labels),
        )
        trained_model = TrainedHealthModel(
            algorithm=parsed_algorithm.value,
            estimator=classifier,
            label_encoder=label_encoder,
            feature_columns=HEALTH_FEATURE_COLUMNS,
            model_version=self._model_version,
            trained_at=trained_at,
            evaluation=evaluation,
        )
        return HealthTrainingResult(trained_model=trained_model, evaluation=evaluation)

    def train_candidate_models(
        self,
        records: Sequence[Mapping[str, object]],
        *,
        algorithms: Sequence[HealthModelAlgorithm | str] = (
            HealthModelAlgorithm.LOGISTIC_REGRESSION,
            HealthModelAlgorithm.RANDOM_FOREST,
            HealthModelAlgorithm.XGBOOST,
        ),
        skip_unavailable: bool = True,
    ) -> tuple[HealthTrainingResult, ...]:
        """Train multiple candidate models and optionally skip unavailable extras."""
        results: list[HealthTrainingResult] = []
        for algorithm in algorithms:
            try:
                results.append(self.train(records, algorithm=algorithm))
            except RuntimeError:
                if not skip_unavailable:
                    raise
        return tuple(results)


def _matrix(feature_rows: Sequence[HealthFeatureRow]) -> list[list[float]]:
    return [list(row.features) for row in feature_rows]


def _label_encoder() -> Any:
    from sklearn.preprocessing import LabelEncoder

    encoder = LabelEncoder()
    encoder.fit(CLASS_LABELS)
    return encoder


def _train_validation_split(
    feature_rows: Sequence[HealthFeatureRow],
    y_all: Sequence[int],
    *,
    test_size: float,
    random_state: int,
) -> dict[str, Any]:
    x_all = _matrix(feature_rows)
    class_counts = Counter(y_all)
    can_stratify = len(feature_rows) >= 6 and all(count >= 2 for count in class_counts.values())
    if not can_stratify:
        return {
            "x_train": x_all,
            "x_validation": x_all,
            "y_train": list(y_all),
            "y_validation": list(y_all),
        }

    from sklearn.model_selection import train_test_split

    x_train, x_validation, y_train, y_validation = train_test_split(
        x_all,
        list(y_all),
        test_size=test_size,
        random_state=random_state,
        stratify=list(y_all),
    )
    return {
        "x_train": x_train,
        "x_validation": x_validation,
        "y_train": y_train,
        "y_validation": y_validation,
    }


def _evaluate(
    *,
    algorithm: str,
    model_version: str,
    trained_at: str,
    y_true: Sequence[int],
    y_pred: Sequence[int],
    label_encoder: Any,
    training_rows: int,
    validation_rows: int,
    label_distribution: Mapping[str, int],
) -> HealthModelEvaluation:
    from sklearn.metrics import (
        accuracy_score,
        classification_report,
        confusion_matrix,
        f1_score,
    )

    encoded_labels = label_encoder.transform(CLASS_LABELS)
    report = classification_report(
        y_true,
        y_pred,
        labels=encoded_labels,
        target_names=CLASS_LABELS,
        output_dict=True,
        zero_division=0,
    )
    return HealthModelEvaluation(
        algorithm=algorithm,
        model_version=model_version,
        trained_at=trained_at,
        training_rows=training_rows,
        validation_rows=validation_rows,
        accuracy=round(float(accuracy_score(y_true, y_pred)), 6),
        macro_f1=round(float(f1_score(y_true, y_pred, labels=encoded_labels, average="macro", zero_division=0)), 6),
        confusion_matrix=confusion_matrix(y_true, y_pred, labels=encoded_labels).tolist(),
        classification_report=report,
        label_distribution=dict(label_distribution),
    )
