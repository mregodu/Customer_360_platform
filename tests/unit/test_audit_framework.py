from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import UTC, datetime, timedelta

import pytest

from customer360.monitoring.audit import AuditLogger, RowCounts, checksum_records


class FakeAuditWriter:
    def __init__(self) -> None:
        self.pipeline_records: list[dict[str, object]] = []
        self.etl_records: list[dict[str, object]] = []

    def write_pipeline_execution_log(self, records: Iterable[Mapping[str, object]]) -> int:
        rows = [dict(record) for record in records]
        self.pipeline_records.extend(rows)
        return len(rows)

    def write_etl_audit_log(self, records: Iterable[Mapping[str, object]]) -> int:
        rows = [dict(record) for record in records]
        self.etl_records.extend(rows)
        return len(rows)


class FakeClock:
    def __init__(self) -> None:
        self.current = datetime(2026, 6, 16, 12, 0, tzinfo=UTC)

    def __call__(self) -> datetime:
        value = self.current
        self.current = self.current + timedelta(seconds=5)
        return value


def test_audit_logger_records_successful_pipeline_and_etl_step() -> None:
    writer = FakeAuditWriter()
    audit_logger = AuditLogger(writer=writer, environment="dev", clock=FakeClock())

    with audit_logger.start_pipeline(
        "customer_ingestion",
        run_id="run-1",
        source_system="SALESFORCE",
        target_table="CUSTOMER360_DB.BRONZE.salesforce_customer_bronze",
        metadata={"source_object": "ACCOUNT"},
    ) as audit:
        audit.add_rows(rows_read=100, rows_inserted=95, rows_updated=5)
        audit.record_step(
            "extract_and_load",
            source_table="SALESFORCE.ACCOUNT",
            destination_table="CUSTOMER360_DB.BRONZE.salesforce_customer_bronze",
            row_count=100,
            checksum="abc123",
        )

    assert len(writer.pipeline_records) == 1
    assert len(writer.etl_records) == 1

    pipeline_row = writer.pipeline_records[0]
    assert pipeline_row["pipeline_name"] == "customer_ingestion"
    assert pipeline_row["run_id"] == "run-1"
    assert pipeline_row["environment"] == "dev"
    assert pipeline_row["status"] == "SUCCESS"
    assert pipeline_row["rows_read"] == 100
    assert pipeline_row["rows_inserted"] == 95
    assert pipeline_row["rows_updated"] == 5
    assert pipeline_row["rows_processed"] == 200
    assert pipeline_row["error_message"] is None
    assert pipeline_row["duration_seconds"] == 10.0
    assert pipeline_row["metadata"] == {"source_object": "ACCOUNT"}

    etl_row = writer.etl_records[0]
    assert etl_row["pipeline_name"] == "customer_ingestion"
    assert etl_row["run_id"] == "run-1"
    assert etl_row["transformation_step"] == "extract_and_load"
    assert etl_row["row_count"] == 100
    assert etl_row["rows_processed"] == 100
    assert etl_row["checksum"] == "abc123"
    assert etl_row["status"] == "SUCCESS"


def test_audit_logger_records_failure_with_error_details() -> None:
    writer = FakeAuditWriter()
    audit_logger = AuditLogger(writer=writer, environment="test", clock=FakeClock())

    with (
        pytest.raises(RuntimeError, match="warehouse timeout"),
        audit_logger.start_pipeline("silver_transform", run_id="run-2") as audit,
    ):
        audit.add_rows(rows_read=10)
        raise RuntimeError("warehouse timeout")

    assert len(writer.pipeline_records) == 1
    row = writer.pipeline_records[0]
    assert row["pipeline_name"] == "silver_transform"
    assert row["status"] == "FAILED"
    assert row["rows_processed"] == 10
    assert row["error_message"] == "warehouse timeout"
    assert isinstance(row["error_details"], dict)
    assert row["error_details"]["exception_type"] == "RuntimeError"


def test_record_etl_step_supports_failed_status_and_structured_details() -> None:
    writer = FakeAuditWriter()
    audit_logger = AuditLogger(writer=writer, clock=FakeClock())

    record = audit_logger.record_etl_step(
        run_id="run-3",
        pipeline_name="gold_generation",
        transformation_step="merge_gold_customer_master",
        status="FAILED",
        source_table="CUSTOMER360_DB.GOLD.gold_customer_clusters",
        destination_table="CUSTOMER360_DB.GOLD.gold_customer_master",
        row_count=25,
        error_details={"message": "duplicate key"},
        details={"warehouse": "WH_CUSTOMER360_TRANSFORM"},
    )

    assert record.status == "FAILED"
    assert len(writer.etl_records) == 1
    row = writer.etl_records[0]
    assert row["rows_processed"] == 25
    assert row["error_details"] == {"message": "duplicate key"}
    assert row["details"] == {"warehouse": "WH_CUSTOMER360_TRANSFORM"}


def test_row_counts_and_checksum_are_deterministic() -> None:
    counts = RowCounts(rows_read=10).add(rows_inserted=5, rows_updated=3, rows_deleted=2)

    assert counts.rows_processed == 20
    assert checksum_records([{"id": 2}, {"id": 1}]) == checksum_records(
        [{"id": 1}, {"id": 2}]
    )
