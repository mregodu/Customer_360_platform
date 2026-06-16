from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from datetime import UTC, datetime

from customer360.infrastructure.great_expectations import (
    DataQualityAlert,
    ExpectationSuiteLoader,
    GreatExpectationsAlertManager,
    GreatExpectationsRunner,
    GreatExpectationsValidationPipeline,
    TableValidationConfig,
)


class FakeTableDataProvider:
    def __init__(self, tables: Mapping[str, Sequence[Mapping[str, object]]]) -> None:
        self.tables = tables

    def fetch_table(self, table_name: str) -> Sequence[Mapping[str, object]]:
        return self.tables[table_name]


class FakeDataQualityWriter:
    def __init__(self) -> None:
        self.metrics: list[dict[str, object]] = []
        self.runs: list[dict[str, object]] = []
        self.alerts: list[dict[str, object]] = []

    def write_quality_metrics(self, records: Iterable[Mapping[str, object]]) -> int:
        rows = [dict(record) for record in records]
        self.metrics.extend(rows)
        return len(rows)

    def write_quality_validation_runs(self, records: Iterable[Mapping[str, object]]) -> int:
        rows = [dict(record) for record in records]
        self.runs.extend(rows)
        return len(rows)

    def write_quality_alerts(self, records: Iterable[Mapping[str, object]]) -> int:
        rows = [dict(record) for record in records]
        self.alerts.extend(rows)
        return len(rows)


class FakeNotifier:
    def __init__(self) -> None:
        self.alerts: list[DataQualityAlert] = []

    def send_alert(self, alert: DataQualityAlert) -> None:
        self.alerts.append(alert)


def test_suite_loader_reads_checked_in_expectation_suite() -> None:
    suite = ExpectationSuiteLoader().load("customer_silver_suite")

    assert suite.name == "customer_silver_suite"
    assert suite.table_name == "CUSTOMER360_DB.SILVER.silver_customer"
    assert {
        expectation["expectation_type"]
        for expectation in suite.expectations
    } >= {
        "expect_column_values_to_not_be_null",
        "expect_compound_columns_to_be_unique",
        "expect_column_values_to_match_regex",
        "expect_column_max_to_be_recent",
    }


def test_runner_validates_completeness_uniqueness_validity_consistency_and_freshness() -> None:
    current_time = datetime(2026, 6, 16, 12, 0, tzinfo=UTC)
    runner = GreatExpectationsRunner(current_time=current_time)

    result = runner.run_validation(
        "CUSTOMER360_DB.SILVER.silver_customer",
        suite_name="customer_silver_suite",
        rows=[
            _silver_customer("001", "hello@example.com", current_time.isoformat()),
            _silver_customer("002", "team@example.com", current_time.isoformat()),
        ],
        run_id="run-1",
    )

    assert result.success
    assert result.row_count == 2
    assert not result.alerts
    rule_types = {metric.rule_type for metric in result.metrics}
    assert {"completeness", "uniqueness", "validity", "consistency", "freshness"} <= rule_types
    assert all(metric.status == "PASS" for metric in result.metrics)
    assert result.metric_rows()[0]["expectation_suite_name"] == "customer_silver_suite"
    assert result.run_summary_row()["quality_score"] == 1.0


def test_runner_generates_alerts_for_failed_expectations() -> None:
    current_time = datetime(2026, 6, 16, 12, 0, tzinfo=UTC)
    notifier = FakeNotifier()
    runner = GreatExpectationsRunner(
        alert_manager=GreatExpectationsAlertManager(notifiers=[notifier]),
        current_time=current_time,
    )

    result = runner.run_validation(
        "CUSTOMER360_DB.SILVER.silver_customer",
        suite_name="customer_silver_suite",
        rows=[
            _silver_customer("001", "bad-email", "2026-06-14T00:00:00+00:00"),
            _silver_customer("001", "also-bad", "2026-06-14T00:00:00+00:00"),
        ],
        run_id="run-2",
    )

    assert not result.success
    assert result.alerts
    assert notifier.alerts
    failed_rules = {alert.rule_name for alert in result.alerts}
    assert "source_customer_unique" in failed_rules
    assert "email_valid_format" in failed_rules
    assert "silver_customer_freshness_24h" in failed_rules
    assert all(alert.status == "OPEN" for alert in result.alerts)


def test_validation_pipeline_writes_metrics_runs_and_alerts() -> None:
    current_time = datetime(2026, 6, 16, 12, 0, tzinfo=UTC)
    table_name = "CUSTOMER360_DB.SILVER.silver_customer"
    provider = FakeTableDataProvider(
        {
            table_name: [
                _silver_customer("001", "hello@example.com", current_time.isoformat()),
                _silver_customer("002", "team@example.com", current_time.isoformat()),
            ]
        }
    )
    writer = FakeDataQualityWriter()
    runner = GreatExpectationsRunner(data_provider=provider, current_time=current_time)
    pipeline = GreatExpectationsValidationPipeline(runner=runner, writer=writer)

    result = pipeline.run(
        [TableValidationConfig(table_name, "customer_silver_suite", source_system="SILVER")],
        run_id="quality-run-1",
    )

    assert result.success
    assert result.metrics_written == len(writer.metrics)
    assert result.run_summaries_written == 1
    assert result.alerts_written == 0
    assert writer.metrics
    assert writer.runs[0]["status"] == "PASS"
    assert writer.metrics[0]["source_system"] == "SILVER"


def _silver_customer(
    source_customer_id: str,
    email: str,
    standardized_at: str,
) -> dict[str, object]:
    return {
        "source_system": "SALESFORCE",
        "source_customer_id": source_customer_id,
        "email": email,
        "is_deleted": False,
        "completeness_score": 1.0,
        "data_quality_score": 1.0,
        "created_date": "2026-06-15T12:00:00+00:00",
        "last_modified_timestamp": "2026-06-15T13:00:00+00:00",
        "standardized_at": standardized_at,
    }
