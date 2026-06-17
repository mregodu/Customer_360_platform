from __future__ import annotations

import json

import pytest

from customer360.infrastructure.snowflake import (
    SnowflakeBronzeLoader,
    SnowflakeBronzeReader,
    SnowflakeCustomerHealthScoringWriter,
    SnowflakeSilverWriter,
    SnowflakeSqlScriptRunner,
    SnowflakeTableDataProvider,
    SnowflakeWatermarkStore,
)

pytestmark = [pytest.mark.integration, pytest.mark.snowflake]


def test_bronze_loader_inserts_ordered_columns_and_serializes_variant_values(
    fake_snowflake_factory_builder,
) -> None:
    factory, connection, cursor = fake_snowflake_factory_builder()
    loader = SnowflakeBronzeLoader({}, connection_factory=factory)

    loaded = loader.write_records(
        "CUSTOMER360_DB.BRONZE.salesforce_customer_bronze",
        [
            {"source_record_id": "1", "raw_payload": {"company": "Acme"}, "tags": ["new"]},
            {"source_record_id": "2", "raw_payload": {"company": "Beta"}, "tags": ["old"]},
        ],
    )

    assert loaded == 2
    assert connection.commit_count == 1
    assert connection.rollback_count == 0
    sql, rows = cursor.executemany_calls[0]
    assert '"CUSTOMER360_DB"."BRONZE"."SALESFORCE_CUSTOMER_BRONZE"' in sql
    assert '"SOURCE_RECORD_ID", "RAW_PAYLOAD", "TAGS"' in sql
    assert json.loads(rows[0][1]) == {"company": "Acme"}
    assert json.loads(rows[0][2]) == ["new"]
    assert cursor.closed


def test_bronze_loader_rolls_back_on_insert_failure(fake_snowflake_factory_builder) -> None:
    factory, connection, cursor = fake_snowflake_factory_builder(fail_on_executemany=True)
    loader = SnowflakeBronzeLoader({}, connection_factory=factory)

    with pytest.raises(RuntimeError, match="planned executemany failure"):
        loader.write_records("db.schema.table", [{"id": "1"}])

    assert connection.commit_count == 0
    assert connection.rollback_count == 1
    assert cursor.closed


def test_bronze_reader_fetches_incremental_rows_with_lowercase_columns(
    fake_snowflake_factory_builder,
) -> None:
    factory, _, cursor = fake_snowflake_factory_builder(
        description=[("SOURCE_SYSTEM",), ("SOURCE_CUSTOMER_ID",)],
        rows=[("SALESFORCE", "001")],
    )
    reader = SnowflakeBronzeReader({}, connection_factory=factory)

    rows = reader.fetch_incremental(
        "CUSTOMER360_DB.BRONZE.salesforce_customer_bronze",
        "last_modified_timestamp",
        "2024-01-01",
    )

    assert rows == [{"source_system": "SALESFORCE", "source_customer_id": "001"}]
    sql, params = cursor.execute_calls[0]
    assert 'where "LAST_MODIFIED_TIMESTAMP" > %s' in sql
    assert params == ("2024-01-01",)


def test_table_data_provider_applies_limit_and_query_params(fake_snowflake_factory_builder) -> None:
    factory, _, cursor = fake_snowflake_factory_builder(
        description=[("ID",), ("STATUS",)],
        rows=[("1", "ACTIVE")],
    )
    provider = SnowflakeTableDataProvider({}, connection_factory=factory, default_limit=10)

    rows = provider.fetch_table(
        "CUSTOMER360_DB.GOLD.gold_customer_master",
        where_clause='"IS_ACTIVE" = %s',
        params=(True,),
    )

    assert rows == [{"id": "1", "status": "ACTIVE"}]
    sql, params = cursor.execute_calls[0]
    assert 'from "CUSTOMER360_DB"."GOLD"."GOLD_CUSTOMER_MASTER"' in sql
    assert 'where "IS_ACTIVE" = %s limit 10' in sql
    assert params == (True,)


def test_table_data_provider_rejects_non_positive_limits(fake_snowflake_factory_builder) -> None:
    factory, _, _ = fake_snowflake_factory_builder()
    provider = SnowflakeTableDataProvider({}, connection_factory=factory)

    with pytest.raises(ValueError, match="greater than zero"):
        provider.fetch_table("db.schema.table", limit=0)


def test_silver_writer_generates_merge_sql_and_temp_table(fake_snowflake_factory_builder) -> None:
    factory, connection, cursor = fake_snowflake_factory_builder()
    writer = SnowflakeSilverWriter({}, database_name="CUSTOMER360_TEST_DB", connection_factory=factory)

    merged = writer.merge_customers(
        [
            {
                "source_system": "SALESFORCE",
                "source_customer_id": "001",
                "company_name": "ACME INC",
            }
        ]
    )

    assert merged == 1
    assert connection.commit_count == 1
    create_sql = cursor.execute_calls[0][0]
    merge_sql = cursor.execute_calls[1][0]
    assert "create temporary table" in create_sql.lower()
    assert '"CUSTOMER360_TEST_DB"."SILVER"."SILVER_CUSTOMER"' in create_sql
    assert 'merge into "CUSTOMER360_TEST_DB"."SILVER"."SILVER_CUSTOMER" target' in merge_sql
    assert 'target."SOURCE_SYSTEM" = source."SOURCE_SYSTEM"' in merge_sql
    assert 'target."SOURCE_CUSTOMER_ID" = source."SOURCE_CUSTOMER_ID"' in merge_sql


def test_health_scoring_writer_accepts_model_evaluation_objects(fake_snowflake_factory_builder) -> None:
    class Evaluation:
        def to_row(self) -> dict[str, object]:
            return {
                "model_version": "v1",
                "algorithm": "logistic_regression",
                "trained_at": "2024-01-01T00:00:00",
                "accuracy": 1.0,
            }

    factory, _, cursor = fake_snowflake_factory_builder()
    writer = SnowflakeCustomerHealthScoringWriter({}, connection_factory=factory)

    merged = writer.write_model_evaluations([Evaluation()])

    assert merged == 1
    merge_sql = cursor.execute_calls[1][0]
    assert '"CUSTOMER_HEALTH_MODEL_EVALUATIONS"' in merge_sql
    assert 'target."MODEL_VERSION" = source."MODEL_VERSION"' in merge_sql
    assert 'target."ALGORITHM" = source."ALGORITHM"' in merge_sql
    assert 'target."TRAINED_AT" = source."TRAINED_AT"' in merge_sql


def test_watermark_store_reads_and_merges_watermarks(fake_snowflake_factory_builder) -> None:
    factory, connection, cursor = fake_snowflake_factory_builder(
        rows=[("2024-01-02T00:00:00",)],
    )
    store = SnowflakeWatermarkStore({}, connection_factory=factory)

    assert store.get_watermark("SALESFORCE", "ACCOUNT") == "2024-01-02T00:00:00"
    store.update_watermark(
        "SALESFORCE",
        "ACCOUNT",
        "last_modified_timestamp",
        "2024-01-03T00:00:00",
        "run-1",
    )

    assert connection.commit_count == 1
    assert cursor.execute_calls[0][1] == ("SALESFORCE", "ACCOUNT")
    assert cursor.execute_calls[1][1] == (
        "SALESFORCE",
        "ACCOUNT",
        "last_modified_timestamp",
        "2024-01-03T00:00:00",
        "run-1",
    )


def test_sql_script_runner_executes_statements_and_rolls_back_on_failure(
    fake_snowflake_factory_builder,
) -> None:
    factory, connection, cursor = fake_snowflake_factory_builder(fail_on_execute_index=1)
    runner = SnowflakeSqlScriptRunner({}, connection_factory=factory)

    with pytest.raises(RuntimeError, match="planned execute failure"):
        runner.execute_sql("select 1; select 2;")

    assert [call[0] for call in cursor.execute_calls] == ["select 1", "select 2"]
    assert connection.commit_count == 0
    assert connection.rollback_count == 1
