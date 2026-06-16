"""Snowflake repository adapter.

The adapter centralizes warehouse IO so application services never need to know
about connection details, SQLAlchemy sessions, or Snowflake-specific APIs.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping, Sequence
from contextlib import contextmanager
from typing import Any
from uuid import uuid4


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


class SnowflakeBronzeReader:
    """Reads incremental records from Snowflake bronze tables."""

    def __init__(
        self,
        connection_parameters: Mapping[str, str | int],
        connection_factory: SnowflakeConnectionFactory | None = None,
    ) -> None:
        self._connection_factory = connection_factory or SnowflakeConnectionFactory(connection_parameters)

    def fetch_incremental(
        self,
        table_name: str,
        watermark_column: str,
        since_watermark: str | None,
    ) -> Sequence[Mapping[str, object]]:
        """Fetch bronze rows changed after a watermark."""
        quoted_table = _qualified_name(table_name)
        quoted_watermark = _quote_identifier(watermark_column)
        sql = f"select * from {quoted_table}"
        params: tuple[object, ...] = tuple()
        if since_watermark is not None:
            sql += f" where {quoted_watermark} > %s"
            params = (since_watermark,)
        sql += f" order by {quoted_watermark}"

        with self._connection_factory.connect() as connection:
            cursor = connection.cursor()
            try:
                cursor.execute(sql, params)
                columns = [column[0].lower() for column in cursor.description]
                rows = cursor.fetchall()
            finally:
                cursor.close()
        return [dict(zip(columns, row, strict=False)) for row in rows]


class SnowflakeSilverWriter:
    """Merges transformed Silver records into Snowflake targets."""

    def __init__(
        self,
        connection_parameters: Mapping[str, str | int],
        database_name: str = "CUSTOMER360_DB",
        connection_factory: SnowflakeConnectionFactory | None = None,
    ) -> None:
        self._database_name = database_name
        self._connection_factory = connection_factory or SnowflakeConnectionFactory(connection_parameters)

    def merge_customers(self, records: Iterable[Mapping[str, object]]) -> int:
        """Merge records into `SILVER.silver_customer`."""
        return self._merge_records(
            f"{self._database_name}.SILVER.silver_customer",
            records,
            key_columns=("source_system", "source_customer_id"),
        )

    def merge_metrics(self, records: Iterable[Mapping[str, object]]) -> int:
        """Merge records into `SILVER.silver_customer_metric_daily`."""
        return self._merge_records(
            f"{self._database_name}.SILVER.silver_customer_metric_daily",
            records,
            key_columns=("source_system", "source_customer_id", "metric_date"),
        )

    def merge_partners(self, records: Iterable[Mapping[str, object]]) -> int:
        """Merge records into `SILVER.silver_partner_profile`."""
        return self._merge_records(
            f"{self._database_name}.SILVER.silver_partner_profile",
            records,
            key_columns=("source_system", "partner_id"),
        )

    def write_quality_metrics(self, records: Iterable[Mapping[str, object]]) -> int:
        """Merge records into `ANALYTICS.data_quality_metrics`."""
        return self._merge_records(
            f"{self._database_name}.ANALYTICS.data_quality_metrics",
            records,
            key_columns=("metric_id",),
        )

    def _merge_records(
        self,
        target_table: str,
        records: Iterable[Mapping[str, object]],
        *,
        key_columns: Sequence[str],
    ) -> int:
        rows = [dict(record) for record in records]
        if not rows:
            return 0

        columns = _ordered_columns(rows)
        temp_table = f"TEMP_SILVER_MERGE_{uuid4().hex}"
        create_temp_sql = (
            f"create temporary table {_quote_identifier(temp_table)} "
            f"like {_qualified_name(target_table)}"
        )
        merge_sql = _merge_sql(target_table, temp_table, columns, key_columns)

        with self._connection_factory.connect() as connection:
            cursor = connection.cursor()
            try:
                cursor.execute(create_temp_sql)
                cursor.executemany(
                    _insert_sql(temp_table, columns),
                    [
                        tuple(_serialize_snowflake_value(row.get(column)) for column in columns)
                        for row in rows
                    ],
                )
                cursor.execute(merge_sql)
                connection.commit()
            except Exception:
                connection.rollback()
                raise
            finally:
                cursor.close()
        return len(rows)


class SnowflakeGoldMatchingWriter:
    """Persists matching predictions and gold customer clusters."""

    def __init__(
        self,
        connection_parameters: Mapping[str, str | int],
        database_name: str = "CUSTOMER360_DB",
        connection_factory: SnowflakeConnectionFactory | None = None,
    ) -> None:
        self._database_name = database_name
        self._connection_factory = connection_factory or SnowflakeConnectionFactory(connection_parameters)

    def write_predictions(self, records: Iterable[Any]) -> int:
        """Merge pairwise predictions into `GOLD.customer_match_predictions`."""
        rows = [
            record.to_row() if hasattr(record, "to_row") else dict(record)
            for record in records
        ]
        return self._merge_records(
            f"{self._database_name}.GOLD.customer_match_predictions",
            rows,
            key_columns=("match_id",),
        )

    def write_clusters(self, records: Iterable[Mapping[str, object]]) -> int:
        """Merge clusters into `GOLD.gold_customer_clusters`."""
        return self._merge_records(
            f"{self._database_name}.GOLD.gold_customer_clusters",
            records,
            key_columns=("cluster_id",),
        )

    def _merge_records(
        self,
        target_table: str,
        records: Iterable[Mapping[str, object]],
        *,
        key_columns: Sequence[str],
    ) -> int:
        rows = [dict(record) for record in records]
        if not rows:
            return 0

        columns = _ordered_columns(rows)
        temp_table = f"TEMP_GOLD_MATCHING_MERGE_{uuid4().hex}"
        create_temp_sql = (
            f"create temporary table {_quote_identifier(temp_table)} "
            f"like {_qualified_name(target_table)}"
        )
        merge_sql = _merge_sql(target_table, temp_table, columns, key_columns)

        with self._connection_factory.connect() as connection:
            cursor = connection.cursor()
            try:
                cursor.execute(create_temp_sql)
                cursor.executemany(
                    _insert_sql(temp_table, columns),
                    [
                        tuple(_serialize_snowflake_value(row.get(column)) for column in columns)
                        for row in rows
                    ],
                )
                cursor.execute(merge_sql)
                connection.commit()
            except Exception:
                connection.rollback()
                raise
            finally:
                cursor.close()
        return len(rows)


class SnowflakeSqlScriptRunner:
    """Executes checked-in Snowflake SQL scripts."""

    def __init__(
        self,
        connection_parameters: Mapping[str, str | int],
        connection_factory: SnowflakeConnectionFactory | None = None,
    ) -> None:
        self._connection_factory = connection_factory or SnowflakeConnectionFactory(connection_parameters)

    def execute_sql(self, sql_text: str) -> None:
        """Execute one SQL script containing semicolon-delimited statements."""
        statements = [statement.strip() for statement in sql_text.split(";") if statement.strip()]
        with self._connection_factory.connect() as connection:
            cursor = connection.cursor()
            try:
                for statement in statements:
                    cursor.execute(statement)
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


def _merge_sql(
    target_table: str,
    source_table: str,
    columns: Sequence[str],
    key_columns: Sequence[str],
) -> str:
    join_clause = " and ".join(
        f"target.{_quote_identifier(column)} = source.{_quote_identifier(column)}"
        for column in key_columns
    )
    update_columns = [column for column in columns if column.lower() not in {key.lower() for key in key_columns}]
    update_clause = ", ".join(
        f"target.{_quote_identifier(column)} = source.{_quote_identifier(column)}"
        for column in update_columns
    )
    insert_columns = ", ".join(_quote_identifier(column) for column in columns)
    insert_values = ", ".join(f"source.{_quote_identifier(column)}" for column in columns)
    return f"""
        merge into {_qualified_name(target_table)} target
        using {_qualified_name(source_table)} source
        on {join_clause}
        when matched then update set {update_clause}
        when not matched then insert ({insert_columns})
        values ({insert_values})
    """


def _qualified_name(name: str) -> str:
    return ".".join(_quote_identifier(part) for part in name.split("."))


def _quote_identifier(identifier: str) -> str:
    escaped = identifier.replace('"', '""')
    return f'"{escaped.upper()}"'


def _serialize_snowflake_value(value: object) -> object:
    if isinstance(value, dict | list):
        return json.dumps(value, sort_keys=True, default=str)
    return value
