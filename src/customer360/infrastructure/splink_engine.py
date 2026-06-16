"""Splink entity-resolution adapter."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from itertools import combinations

from customer360.config import SplinkConfig
from customer360.domain.customer import SourceCustomerRecord
from customer360.matching.clustering import CustomerClusterGenerator, MatchPrediction
from customer360.matching.scoring import MatchScoreCalculator
from customer360.matching.settings import (
    DEFAULT_MODEL_VERSION,
    SplinkSettingsBuilder,
)


class SplinkEntityResolutionEngine:
    """Runs probabilistic customer matching with Splink-compatible settings."""

    def __init__(
        self,
        *,
        splink_config: SplinkConfig | None = None,
        settings_builder: SplinkSettingsBuilder | None = None,
        score_calculator: MatchScoreCalculator | None = None,
        match_threshold: float | None = None,
        include_singletons: bool = True,
        model_version: str = DEFAULT_MODEL_VERSION,
    ) -> None:
        self.settings_builder = (
            settings_builder
            or (
                SplinkSettingsBuilder.from_config(splink_config)
                if splink_config is not None
                else SplinkSettingsBuilder()
            )
        )
        threshold = match_threshold or (splink_config.match_threshold if splink_config else 0.95)
        self.score_calculator = score_calculator or MatchScoreCalculator(
            fields=self.settings_builder.matching_fields,
            match_threshold=threshold,
        )
        self.cluster_generator = CustomerClusterGenerator(
            threshold=threshold,
            include_singletons=include_singletons,
        )
        self.model_version = model_version

    def splink_settings(self) -> Mapping[str, object]:
        """Return the production Splink settings dictionary."""
        return self.settings_builder.to_settings_dict()

    def predict_matches(
        self,
        records: Sequence[SourceCustomerRecord],
    ) -> tuple[MatchPrediction, ...]:
        """Return pairwise customer match predictions."""
        predictions: list[MatchPrediction] = []
        for left, right in _candidate_pairs(records):
            score = self.score_calculator.score_pair(left, right)
            predictions.append(
                MatchPrediction(
                    left_source_system=left.source_system,
                    left_source_customer_id=left.source_customer_id,
                    right_source_system=right.source_system,
                    right_source_customer_id=right.source_customer_id,
                    match_probability=score.match_probability,
                    confidence_score=score.confidence_score,
                    comparison_vector=score.comparison_vector,
                    blocking_rule=score.blocking_rule,
                    model_version=self.model_version,
                )
            )
        return tuple(predictions)

    def generate_clusters(
        self,
        records: Sequence[SourceCustomerRecord],
        predictions: Sequence[MatchPrediction] | None = None,
        *,
        load_batch_id: str | None = None,
    ) -> tuple[dict[str, object], ...]:
        """Generate `gold_customer_clusters` rows."""
        return self.cluster_generator.generate(
            records,
            predictions if predictions is not None else self.predict_matches(records),
            load_batch_id=load_batch_id,
        )

    def predict_clusters(
        self,
        records: Sequence[SourceCustomerRecord],
    ) -> Sequence[Mapping[str, object]]:
        """Return cluster rows for the Customer 360 gold layer."""
        return self.generate_clusters(records)


def _candidate_pairs(
    records: Sequence[SourceCustomerRecord],
) -> tuple[tuple[SourceCustomerRecord, SourceCustomerRecord], ...]:
    """Generate candidate pairs using configured blocking field semantics."""
    blocked_pairs: set[tuple[int, int]] = set()
    blocking_fields = ("email", "phone", "website_domain", "company_name", "address")
    for field_name in blocking_fields:
        buckets: dict[str, list[int]] = {}
        for index, record in enumerate(records):
            value = getattr(record, field_name)
            if value:
                buckets.setdefault(str(value).strip().lower(), []).append(index)
        for indexes in buckets.values():
            for left_index, right_index in combinations(indexes, 2):
                blocked_pairs.add((left_index, right_index))

    return tuple((records[left], records[right]) for left, right in sorted(blocked_pairs))
