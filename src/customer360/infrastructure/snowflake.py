"""Snowflake repository adapter.

The adapter centralizes warehouse IO so application services never need to know
about connection details, SQLAlchemy sessions, or Snowflake-specific APIs.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence


class SnowflakeCustomerRepository:
    """Repository placeholder for production Snowflake reads and writes."""

    def __init__(self, connection_name: str = "snowflake_default") -> None:
        self.connection_name = connection_name

    def fetch_incremental(self, source_system: str, since_watermark: str) -> Sequence[Mapping[str, object]]:
        """Fetch changed records for a source system.

        In Airflow, this adapter should resolve `connection_name` to an Airflow
        connection. In local jobs, it can resolve environment variables instead.
        """
        raise NotImplementedError(
            f"Snowflake incremental fetch is not wired yet for {source_system=} {since_watermark=}."
        )

    def write_records(self, table_name: str, records: Iterable[Mapping[str, object]]) -> int:
        """Write records to Snowflake and return row count."""
        rows = list(records)
        raise NotImplementedError(f"Snowflake write is not wired yet for {table_name=} rows={len(rows)}.")
