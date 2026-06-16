"""Cluster generation for pairwise customer match predictions."""

from __future__ import annotations

import hashlib
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime

from customer360.domain.customer import SourceCustomerRecord


@dataclass(frozen=True)
class MatchPrediction:
    """Pairwise match prediction emitted by the matching engine."""

    left_source_system: str
    left_source_customer_id: str
    right_source_system: str
    right_source_customer_id: str
    match_probability: float
    confidence_score: float
    comparison_vector: Mapping[str, float | None]
    blocking_rule: str | None
    model_version: str

    def to_row(self, *, load_batch_id: str | None = None) -> dict[str, object]:
        """Return a Snowflake-ready row for `GOLD.customer_match_predictions`."""
        return {
            "match_id": _stable_id(
                "match",
                (
                    (self.left_source_system, self.left_source_customer_id),
                    (self.right_source_system, self.right_source_customer_id),
                ),
            ),
            "left_source_system": self.left_source_system,
            "left_source_customer_id": self.left_source_customer_id,
            "right_source_system": self.right_source_system,
            "right_source_customer_id": self.right_source_customer_id,
            "match_probability": self.match_probability,
            "confidence_score": self.confidence_score,
            "comparison_vector": dict(self.comparison_vector),
            "blocking_rule": self.blocking_rule,
            "model_version": self.model_version,
            "predicted_at": datetime.now(tz=UTC).isoformat(),
            "load_batch_id": load_batch_id,
        }


class CustomerClusterGenerator:
    """Converts pairwise match predictions into resolved customer clusters."""

    def __init__(self, threshold: float = 0.95, include_singletons: bool = True) -> None:
        self._threshold = threshold
        self._include_singletons = include_singletons

    def generate(
        self,
        records: Sequence[SourceCustomerRecord],
        predictions: Iterable[MatchPrediction],
        *,
        load_batch_id: str | None = None,
    ) -> tuple[dict[str, object], ...]:
        """Generate `gold_customer_clusters` rows from pairwise predictions."""
        union_find = _UnionFind(_record_key(record) for record in records)
        retained_predictions = [
            prediction
            for prediction in predictions
            if prediction.match_probability >= self._threshold
        ]
        for prediction in retained_predictions:
            union_find.union(
                (prediction.left_source_system, prediction.left_source_customer_id),
                (prediction.right_source_system, prediction.right_source_customer_id),
            )

        groups = union_find.groups()
        rows: list[dict[str, object]] = []
        now = datetime.now(tz=UTC).isoformat()
        for members in groups:
            if len(members) == 1 and not self._include_singletons:
                continue
            member_predictions = [
                prediction
                for prediction in retained_predictions
                if _prediction_members(prediction) <= set(members)
            ]
            probabilities = [prediction.match_probability for prediction in member_predictions]
            confidence_scores = [prediction.confidence_score for prediction in member_predictions]
            cluster_id = _stable_id("cluster", members)
            representative = sorted(members)[0]
            rows.append(
                {
                    "cluster_id": cluster_id,
                    "golden_customer_id": _stable_id("gold", members),
                    "cluster_size": len(members),
                    "source_members": [
                        {
                            "source_system": member[0],
                            "source_customer_id": member[1],
                        }
                        for member in sorted(members)
                    ],
                    "source_customer_ids": [member[1] for member in sorted(members)],
                    "source_systems": sorted({member[0] for member in members}),
                    "representative_source_system": representative[0],
                    "representative_source_customer_id": representative[1],
                    "max_match_probability": round(max(probabilities), 8) if probabilities else 1.0,
                    "avg_match_probability": (
                        round(sum(probabilities) / len(probabilities), 8) if probabilities else 1.0
                    ),
                    "confidence_score": (
                        round(sum(confidence_scores) / len(confidence_scores), 8)
                        if confidence_scores
                        else 1.0
                    ),
                    "cluster_rules": sorted(
                        {
                            prediction.blocking_rule
                            for prediction in member_predictions
                            if prediction.blocking_rule
                        }
                    ),
                    "model_version": (
                        member_predictions[0].model_version
                        if member_predictions
                        else "splink_customer_matching_v1"
                    ),
                    "created_at": now,
                    "updated_at": now,
                    "load_batch_id": load_batch_id,
                }
            )
        return tuple(sorted(rows, key=lambda row: str(row["cluster_id"])))


class _UnionFind:
    def __init__(self, keys: Iterable[tuple[str, str]]) -> None:
        self._parent = {key: key for key in keys}

    def find(self, key: tuple[str, str]) -> tuple[str, str]:
        parent = self._parent.setdefault(key, key)
        if parent != key:
            self._parent[key] = self.find(parent)
        return self._parent[key]

    def union(self, left: tuple[str, str], right: tuple[str, str]) -> None:
        left_root = self.find(left)
        right_root = self.find(right)
        if left_root != right_root:
            self._parent[right_root] = left_root

    def groups(self) -> tuple[tuple[tuple[str, str], ...], ...]:
        grouped: dict[tuple[str, str], list[tuple[str, str]]] = {}
        for key in self._parent:
            grouped.setdefault(self.find(key), []).append(key)
        return tuple(tuple(sorted(members)) for members in grouped.values())


def _record_key(record: SourceCustomerRecord) -> tuple[str, str]:
    return (record.source_system, record.source_customer_id)


def _prediction_members(prediction: MatchPrediction) -> set[tuple[str, str]]:
    return {
        (prediction.left_source_system, prediction.left_source_customer_id),
        (prediction.right_source_system, prediction.right_source_customer_id),
    }


def _stable_id(prefix: str, members: Sequence[tuple[str, str]]) -> str:
    payload = "|".join(f"{source}:{customer_id}" for source, customer_id in sorted(members))
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:24]
    return f"{prefix}_{digest}"
