"""Application service for customer entity resolution."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from customer360.application.ports import EntityResolutionEngine
from customer360.domain.customer import SourceCustomerRecord


class MatchingService:
    """Coordinates customer matching without depending directly on Splink."""

    def __init__(self, engine: EntityResolutionEngine) -> None:
        self.engine = engine

    def match_customers(self, records: Sequence[SourceCustomerRecord]) -> Sequence[Mapping[str, object]]:
        """Generate customer clusters, match probabilities, and confidence scores."""
        return self.engine.predict_clusters(records)
