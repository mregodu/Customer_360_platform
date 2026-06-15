"""Ingestion use cases for source-to-bronze processing."""

from __future__ import annotations

from dataclasses import dataclass

from customer360.application.ports import CustomerRepository


@dataclass(frozen=True)
class IngestionResult:
    """Result metadata emitted after a source ingestion run."""

    source_system: str
    target_table: str
    rows_loaded: int


class IngestionService:
    """Coordinates incremental extraction and bronze-layer loading."""

    def __init__(self, repository: CustomerRepository) -> None:
        self.repository = repository

    def ingest_source(self, source_system: str, target_table: str, since_watermark: str) -> IngestionResult:
        """Extract changed records and load them into the bronze table unchanged."""
        records = self.repository.fetch_incremental(source_system, since_watermark)
        rows_loaded = self.repository.write_records(target_table, records)
        return IngestionResult(source_system=source_system, target_table=target_table, rows_loaded=rows_loaded)
