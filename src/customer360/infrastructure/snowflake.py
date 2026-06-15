"""Snowflake repository adapter.

The adapter centralizes warehouse IO so application services never need to know
about connection details, SQLAlchemy sessions, or Snowflake-specific APIs.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping, Sequence
from contextlib import contextmanager
from typing import Any


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


class SnowflakeConnectionFactory:
    """Creates Snowflake connector connections from validated parameters."""

    def __init__(self, connection_parameters: Mapping[str, str | int]) -> None:
        self._connection_parameters = dict(connection_parameters)

    @contextmanager
    def connect(self) -> Any:
        """Yield a Snowflake connection and close it after use."""
        try:
            import snowflake.connector
        except ModuleNotFoundError as exc:  # pragma: no cover - depends on runtime extras
            raise RuntimeError("snowflake-connector-python is required for Snowflake IO.") from exc

        connection = snowflake.connector.connect(**self._connection_parameters)
        try:
            yield connection
        finally:
            connection.close()


class SnowflakeBronzeLoader:
    """Loads generic ingestion records into Snowflake bronze tables."""

    def __init__(
        self,
        connection_parameters: Mapping[str, str | int],
        connection_factory: SnowflakeConnectionFactory | None = None,
    ) -> None:
        self._connection_factory = connection_factory or SnowflakeConnectionFactory(connection_parameters)

    def write_records(self, table_name: str, records: Iterable[Mapping[str, object]]) -> int:
        """Insert records into a bronze table and return the loaded row count."""
        rows = [dict(record) for record in records]
        if not rows:
            return 0

        columns = _ordered_columns(rows)
        sql = _insert_sql(table_name, columns)
        values = [
            tuple(_serialize_snowflake_value(row.get(column)) for column in columns)
            for row in rows
        ]

        with self._connection_factory.connect() as connection:
            cursor = connection.cursor()
            try:
                cursor.executemany(sql, values)
                connection.commit()
            except Exception:
                connection.rollback()
                raise
            finally:
                cursor.close()
        return len(rows)


class SnowflakeWatermarkStore:
    """Reads and writes incremental watermarks in LANDING.source_extract_watermarks."""

    def __init__(
        self,
        connection_parameters: Mapping[str, str | int],
        table_name: str = "CUSTOMER360_DB.LANDING.source_extract_watermarks",
        connection_factory: SnowflakeConnectionFactory | None = None,
    ) -> None:
        self._table_name = table_name
        self._connection_factory = connection_factory or SnowflakeConnectionFactory(connection_parameters)

    def get_watermark(self, source_system: str, source_object: str) -> str | None:
        """Return the last successful high-watermark value for a source."""
        sql = f"""
            select high_watermark_value
            from {_qualified_name(self._table_name)}
            where source_system = %s
              and source_object = %s
              and is_active = true
            qualify row_number() over (
                partition by source_system, source_object
                order by updated_at desc
            ) = 1
        """
        with self._connection_factory.connect() as connection:
            cursor = connection.cursor()
            try:
                cursor.execute(sql, (source_system, source_object))
                row = cursor.fetchone()
            finally:
                cursor.close()
        if row is None:
            return None
        return str(row[0]) if row[0] is not None else None

    def update_watermark(
        self,
        source_system: str,
        source_object: str,
        watermark_column: str,
        watermark_value: str,
        run_id: str,
    ) -> None:
        """Merge a successful high-watermark value into Snowflake."""
        sql = f"""
            merge into {_qualified_name(self._table_name)} target
            using (
                select
                    %s as source_system,
                    %s as source_object,
                    %s as watermark_column,
                    %s as high_watermark_value,
                    %s as last_successful_run_id
            ) source
            on target.source_system = source.source_system
               and target.source_object = source.source_object
            when matched then update set
                watermark_column = source.watermark_column,
                high_watermark_value = source.high_watermark_value,
                high_watermark_timestamp = current_timestamp(),
                last_successful_run_id = source.last_successful_run_id,
                last_successful_load_at = current_timestamp(),
                is_active = true,
                updated_at = current_timestamp()
            when not matched then insert (
                source_system,
                source_object,
                watermark_column,
                high_watermark_value,
                high_watermark_timestamp,
                last_successful_run_id,
                last_successful_load_at,
                is_active,
                created_at,
                updated_at
            ) values (
                source.source_system,
                source.source_object,
                source.watermark_column,
                source.high_watermark_value,
                current_timestamp(),
                source.last_successful_run_id,
                current_timestamp(),
                true,
                current_timestamp(),
                current_timestamp()
            )
        """
        params = (source_system, source_object, watermark_column, watermark_value, run_id)
        with self._connection_factory.connect() as connection:
            cursor = connection.cursor()
            try:
                cursor.execute(sql, params)
                connection.commit()
            except Exception:
                connection.rollback()
                raise
            finally:
                cursor.close()


def _ordered_columns(rows: Sequence[Mapping[str, object]]) -> list[str]:
    columns: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for column in row:
            normalized = column.lower()
            if normalized not in seen:
                seen.add(normalized)
                columns.append(column)
    return columns


def _insert_sql(table_name: str, columns: Sequence[str]) -> str:
    column_list = ", ".join(_quote_identifier(column) for column in columns)
    placeholders = ", ".join(["%s"] * len(columns))
    return f"insert into {_qualified_name(table_name)} ({column_list}) values ({placeholders})"


def _qualified_name(name: str) -> str:
    return ".".join(_quote_identifier(part) for part in name.split("."))


def _quote_identifier(identifier: str) -> str:
    escaped = identifier.replace('"', '""')
    return f'"{escaped.upper()}"'


def _serialize_snowflake_value(value: object) -> object:
    if isinstance(value, dict | list):
        return json.dumps(value, sort_keys=True, default=str)
    return value
