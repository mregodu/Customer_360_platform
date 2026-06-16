"""Application service for customer entity resolution."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Protocol

from customer360.application.ports import EntityResolutionEngine
from customer360.domain.customer import SourceCustomerRecord
from customer360.matching.clustering import MatchPrediction


class MatchingService:
    """Coordinates customer matching without depending directly on Splink."""

    def __init__(self, engine: EntityResolutionEngine) -> None:
        self.engine = engine

    def match_customers(
        self,
        records: Sequence[SourceCustomerRecord],
    ) -> Sequence[Mapping[str, object]]:
        """Generate customer clusters, match probabilities, and confidence scores."""
        return self.engine.predict_clusters(records)

    def match_to_gold_clusters(
        self,
        records: Sequence[SourceCustomerRecord],
    ) -> Sequence[Mapping[str, object]]:
        """Generate rows for `GOLD.gold_customer_clusters`."""
        return self.engine.predict_clusters(records)


class SplinkMatchResultWriter(Protocol):
    """Utility adapter contract for persistence-oriented matching jobs."""

    def write_predictions(self, predictions: Sequence[MatchPrediction]) -> int:
        """Persist pairwise match predictions."""

    def write_clusters(self, clusters: Sequence[Mapping[str, object]]) -> int:
        """Persist generated cluster rows."""
