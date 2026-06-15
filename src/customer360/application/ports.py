"""Ports define infrastructure contracts used by application services.

Adapters in `customer360.infrastructure` implement these protocols. This keeps
business workflows testable without live Snowflake, Domo, or filesystem access.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from typing import Protocol

from customer360.domain.customer import SourceCustomerRecord


class CustomerRepository(Protocol):
    """Persistence contract for customer records across warehouse layers."""

    def fetch_incremental(self, source_system: str, since_watermark: str) -> Sequence[Mapping[str, object]]:
        """Fetch records changed since the previous successful watermark."""

    def write_records(self, table_name: str, records: Iterable[Mapping[str, object]]) -> int:
        """Write records to a target table and return the number of rows written."""


class DataQualityRunner(Protocol):
    """Validation contract for Great Expectations or compatible quality engines."""

    def validate_table(self, table_name: str) -> bool:
        """Return whether the table satisfies its quality expectations."""


class DashboardPublisher(Protocol):
    """Dashboard publishing contract for Domo datasets and cards."""

    def publish_dataset(self, dataset_name: str, rows: Sequence[Mapping[str, object]]) -> str:
        """Publish rows and return the downstream dataset identifier."""


class EntityResolutionEngine(Protocol):
    """Entity-resolution contract implemented by Splink infrastructure."""

    def predict_clusters(self, records: Sequence[SourceCustomerRecord]) -> Sequence[Mapping[str, object]]:
        """Return cluster predictions and confidence scores."""
