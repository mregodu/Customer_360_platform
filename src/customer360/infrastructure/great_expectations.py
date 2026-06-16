"""Great Expectations validation, alerting, and metric publishing adapters."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Protocol, cast

DEFAULT_EXPECTATIONS_DIR = Path("great_expectations/expectations")


class TableDataProvider(Protocol):
    """Reads table records for validation."""

    def fetch_table(self, table_name: str) -> Sequence[Mapping[str, object]]:
        """Return records for a fully qualified table name."""


class DataQualityResultWriter(Protocol):
    """Persists Great Expectations validation outputs."""

    def write_quality_metrics(self, records: Iterable[Mapping[str, object]]) -> int:
        """Persist expectation-level quality metrics."""

    def write_quality_validation_runs(self, records: Iterable[Mapping[str, object]]) -> int:
        """Persist run-level validation summaries."""

    def write_quality_alerts(self, records: Iterable[Mapping[str, object]]) -> int:
        """Persist alert events produced by failed quality checks."""


class AlertNotifier(Protocol):
    """Sends data-quality alerts to an external system."""

    def send_alert(self, alert: DataQualityAlert) -> None:
        """Send one alert event."""


@dataclass(frozen=True)
class ExpectationSuite:
    """A loaded Great Expectations suite."""

    name: str
    table_name: str
    expectations: tuple[Mapping[str, object], ...]
    meta: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class ExpectationMetric:
    """One expectation-level validation result."""

    suite_name: str
    table_name: str
    expectation_type: str
    rule_name: str
    rule_type: str
    severity: str
    success: bool
    passed_count: int
    failed_count: int
    total_count: int
    quality_score: float
    threshold: float
    details: Mapping[str, object]

    @property
    def status(self) -> str:
        """Return dashboard status for the metric."""
        if self.success:
            return "PASS"
        return "FAIL" if self.severity.upper() in {"ERROR", "CRITICAL"} else "WARN"

    def to_row(
        self,
        *,
        run_id: str,
        measured_at: str,
        source_system: str | None = None,
    ) -> dict[str, object]:
        """Return an analytics-ready data-quality metric row."""
        schema_name, table_name = _schema_and_table(self.table_name)
        return {
            "metric_id": _stable_id(run_id, self.table_name, self.rule_name),
            "run_id": run_id,
            "source_system": source_system,
            "schema_name": schema_name,
            "table_name": table_name,
            "expectation_suite_name": self.suite_name,
            "rule_name": self.rule_name,
            "rule_type": self.rule_type,
            "dimension": self.rule_type,
            "severity": self.severity.upper(),
            "measured_at": measured_at,
            "passed_count": self.passed_count,
            "failed_count": self.failed_count,
            "total_count": self.total_count,
            "quality_score": self.quality_score,
            "threshold": self.threshold,
            "status": self.status,
            "details": dict(self.details),
        }


@dataclass(frozen=True)
class DataQualityAlert:
    """Alert event generated from a failed or warning quality metric."""

    alert_id: str
    run_id: str
    suite_name: str
    table_name: str
    rule_name: str
    severity: str
    status: str
    message: str
    created_at: str
    details: Mapping[str, object]

    def to_row(self) -> dict[str, object]:
        """Return an analytics-ready alert row."""
        schema_name, table_name = _schema_and_table(self.table_name)
        return {
            "alert_id": self.alert_id,
            "run_id": self.run_id,
            "schema_name": schema_name,
            "table_name": table_name,
            "expectation_suite_name": self.suite_name,
            "rule_name": self.rule_name,
            "severity": self.severity,
            "status": self.status,
            "message": self.message,
            "created_at": self.created_at,
            "details": dict(self.details),
        }


@dataclass(frozen=True)
class ValidationRunResult:
    """Complete result from validating one table against one suite."""

    run_id: str
    suite_name: str
    table_name: str
    success: bool
    started_at: str
    completed_at: str
    row_count: int
    metrics: tuple[ExpectationMetric, ...]
    alerts: tuple[DataQualityAlert, ...] = field(default_factory=tuple)

    @property
    def quality_score(self) -> float:
        """Return average metric quality score."""
        if not self.metrics:
            return 1.0
        return round(sum(metric.quality_score for metric in self.metrics) / len(self.metrics), 4)

    def metric_rows(self, *, source_system: str | None = None) -> tuple[dict[str, object], ...]:
        """Return metric rows for persistence."""
        return tuple(
            metric.to_row(
                run_id=self.run_id,
                measured_at=self.completed_at,
                source_system=source_system,
            )
            for metric in self.metrics
        )

    def run_summary_row(self) -> dict[str, object]:
        """Return run-level validation summary row."""
        schema_name, table_name = _schema_and_table(self.table_name)
        failed_metrics = sum(1 for metric in self.metrics if not metric.success)
        warning_metrics = sum(1 for metric in self.metrics if metric.status == "WARN")
        return {
            "run_id": self.run_id,
            "expectation_suite_name": self.suite_name,
            "schema_name": schema_name,
            "table_name": table_name,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "status": "PASS" if self.success else "FAIL",
            "row_count": self.row_count,
            "metrics_total": len(self.metrics),
            "metrics_failed": failed_metrics,
            "metrics_warned": warning_metrics,
            "quality_score": self.quality_score,
            "details": {
                "failed_rules": [
                    metric.rule_name for metric in self.metrics if not metric.success
                ],
            },
        }


@dataclass(frozen=True)
class TableValidationConfig:
    """Configuration for one validation pipeline target."""

    table_name: str
    suite_name: str
    source_system: str | None = None


@dataclass(frozen=True)
class ValidationPipelineResult:
    """Aggregated result from one validation pipeline run."""

    run_id: str
    table_results: tuple[ValidationRunResult, ...]
    metrics_written: int
    run_summaries_written: int
    alerts_written: int

    @property
    def success(self) -> bool:
        """Return whether all tables passed validation."""
        return all(result.success for result in self.table_results)


class ExpectationSuiteLoader:
    """Loads checked-in Great Expectations JSON suites."""

    def __init__(self, expectations_dir: Path | str = DEFAULT_EXPECTATIONS_DIR) -> None:
        self._expectations_dir = Path(expectations_dir)

    def load(self, suite_name: str) -> ExpectationSuite:
        """Load one expectation suite by name."""
        path = self._expectations_dir / f"{suite_name}.json"
        if not path.exists():
            raise FileNotFoundError(f"Expectation suite not found: {path}")
        payload = json.loads(path.read_text(encoding="utf-8"))
        meta = payload.get("meta") or {}
        return ExpectationSuite(
            name=str(payload["expectation_suite_name"]),
            table_name=str(meta.get("table_name") or suite_name.replace("_suite", "")),
            expectations=tuple(payload.get("expectations", ())),
            meta=meta,
        )


class GreatExpectationsAlertManager:
    """Creates and optionally dispatches alert events from validation metrics."""

    def __init__(self, notifiers: Sequence[AlertNotifier] | None = None) -> None:
        self._notifiers = tuple(notifiers or ())

    def build_alerts(
        self,
        *,
        run_id: str,
        suite_name: str,
        table_name: str,
        metrics: Sequence[ExpectationMetric],
        created_at: str,
    ) -> tuple[DataQualityAlert, ...]:
        """Build alerts for warning and failed expectation metrics."""
        alerts: list[DataQualityAlert] = []
        for metric in metrics:
            if metric.status == "PASS":
                continue
            severity = "CRITICAL" if metric.status == "FAIL" else "WARNING"
            alert = DataQualityAlert(
                alert_id=_stable_id(run_id, table_name, metric.rule_name, severity),
                run_id=run_id,
                suite_name=suite_name,
                table_name=table_name,
                rule_name=metric.rule_name,
                severity=severity,
                status="OPEN",
                message=(
                    f"{table_name}.{metric.rule_name} {metric.status}: "
                    f"quality_score={metric.quality_score:.4f}, threshold={metric.threshold:.4f}"
                ),
                created_at=created_at,
                details={
                    "rule_type": metric.rule_type,
                    "expectation_type": metric.expectation_type,
                    "failed_count": metric.failed_count,
                    "total_count": metric.total_count,
                    "details": dict(metric.details),
                },
            )
            alerts.append(alert)
            for notifier in self._notifiers:
                notifier.send_alert(alert)
        return tuple(alerts)


class GreatExpectationsRunner:
    """Runs table-level quality checks using checked-in expectation suites."""

    def __init__(
        self,
        *,
        data_provider: TableDataProvider | None = None,
        suite_loader: ExpectationSuiteLoader | None = None,
        alert_manager: GreatExpectationsAlertManager | None = None,
        current_time: datetime | None = None,
    ) -> None:
        self._data_provider = data_provider
        self._suite_loader = suite_loader or ExpectationSuiteLoader()
        self._alert_manager = alert_manager or GreatExpectationsAlertManager()
        self._current_time = current_time

    def validate_table(self, table_name: str, suite_name: str | None = None) -> bool:
        """Validate a table against its configured expectation suite."""
        result = self.run_validation(table_name, suite_name=suite_name)
        return result.success

    def run_validation(
        self,
        table_name: str,
        *,
        suite_name: str | None = None,
        rows: Sequence[Mapping[str, object]] | None = None,
        run_id: str | None = None,
    ) -> ValidationRunResult:
        """Run one expectation suite against table rows."""
        if rows is None:
            if self._data_provider is None:
                raise RuntimeError("GreatExpectationsRunner requires rows or a data_provider.")
            rows = self._data_provider.fetch_table(table_name)

        suite = self._suite_loader.load(suite_name or _default_suite_name(table_name))
        started_at = _now_iso(self._current_time)
        metrics = tuple(
            _evaluate_expectation(
                expectation,
                rows,
                suite_name=suite.name,
                table_name=table_name,
                current_time=self._current_time or datetime.now(tz=UTC),
            )
            for expectation in suite.expectations
        )
        completed_at = _now_iso(self._current_time)
        resolved_run_id = run_id or _stable_id(table_name, suite.name, completed_at)
        alerts = self._alert_manager.build_alerts(
            run_id=resolved_run_id,
            suite_name=suite.name,
            table_name=table_name,
            metrics=metrics,
            created_at=completed_at,
        )
        return ValidationRunResult(
            run_id=resolved_run_id,
            suite_name=suite.name,
            table_name=table_name,
            success=all(metric.success for metric in metrics),
            started_at=started_at,
            completed_at=completed_at,
            row_count=len(rows),
            metrics=metrics,
            alerts=alerts,
        )


class GreatExpectationsValidationPipeline:
    """Runs configured validations and publishes metrics, summaries, and alerts."""

    def __init__(
        self,
        *,
        runner: GreatExpectationsRunner,
        writer: DataQualityResultWriter | None = None,
    ) -> None:
        self._runner = runner
        self._writer = writer

    def run(
        self,
        configs: Sequence[TableValidationConfig],
        *,
        run_id: str | None = None,
    ) -> ValidationPipelineResult:
        """Run validation for all configured tables."""
        resolved_run_id = run_id or _stable_id("quality", _now_iso())
        table_results = tuple(
            self._runner.run_validation(
                config.table_name,
                suite_name=config.suite_name,
                run_id=resolved_run_id,
            )
            for config in configs
        )

        metrics = [
            metric_row
            for config, result in zip(configs, table_results, strict=False)
            for metric_row in result.metric_rows(source_system=config.source_system)
        ]
        summaries = [result.run_summary_row() for result in table_results]
        alerts = [alert.to_row() for result in table_results for alert in result.alerts]

        metrics_written = 0
        summaries_written = 0
        alerts_written = 0
        if self._writer is not None:
            metrics_written = self._writer.write_quality_metrics(metrics)
            summaries_written = self._writer.write_quality_validation_runs(summaries)
            alerts_written = self._writer.write_quality_alerts(alerts)

        return ValidationPipelineResult(
            run_id=resolved_run_id,
            table_results=table_results,
            metrics_written=metrics_written,
            run_summaries_written=summaries_written,
            alerts_written=alerts_written,
        )


def _evaluate_expectation(
    expectation: Mapping[str, object],
    rows: Sequence[Mapping[str, object]],
    *,
    suite_name: str,
    table_name: str,
    current_time: datetime,
) -> ExpectationMetric:
    expectation_type = str(expectation["expectation_type"])
    kwargs = _mapping(expectation.get("kwargs"))
    meta = _mapping(expectation.get("meta"))
    rule_name = str(meta.get("rule_name") or expectation_type)
    rule_type = str(meta.get("rule_type") or _rule_type(expectation_type))
    severity = str(meta.get("severity") or "ERROR")
    threshold = _required_float(kwargs.get("mostly", meta.get("threshold", 1.0)))

    if expectation_type == "expect_table_row_count_to_be_between":
        result = _expect_table_row_count_to_be_between(rows, kwargs)
    elif expectation_type == "expect_column_values_to_not_be_null":
        result = _expect_column_values_to_not_be_null(rows, kwargs)
    elif expectation_type == "expect_column_values_to_be_unique":
        result = _expect_column_values_to_be_unique(rows, kwargs)
    elif expectation_type == "expect_compound_columns_to_be_unique":
        result = _expect_compound_columns_to_be_unique(rows, kwargs)
    elif expectation_type == "expect_column_values_to_match_regex":
        result = _expect_column_values_to_match_regex(rows, kwargs)
    elif expectation_type == "expect_column_values_to_be_in_set":
        result = _expect_column_values_to_be_in_set(rows, kwargs)
    elif expectation_type == "expect_column_values_to_be_between":
        result = _expect_column_values_to_be_between(rows, kwargs)
    elif expectation_type == "expect_column_pair_values_a_to_be_greater_than_or_equal_to_b":
        result = _expect_column_pair_values_a_to_be_greater_than_or_equal_to_b(rows, kwargs)
    elif expectation_type == "expect_column_max_to_be_recent":
        result = _expect_column_max_to_be_recent(rows, kwargs, current_time=current_time)
    else:
        raise ValueError(f"Unsupported expectation_type={expectation_type}")

    passed_count = _required_int(result["passed_count"])
    failed_count = _required_int(result["failed_count"])
    total_count = _required_int(result["total_count"])
    details = _mapping(result.get("details"))
    quality_score = _quality_score(passed_count, total_count)
    success = quality_score >= threshold
    return ExpectationMetric(
        suite_name=suite_name,
        table_name=table_name,
        expectation_type=expectation_type,
        rule_name=rule_name,
        rule_type=rule_type,
        severity=severity,
        success=success,
        passed_count=passed_count,
        failed_count=failed_count,
        total_count=total_count,
        quality_score=quality_score,
        threshold=threshold,
        details=details,
    )


def _expect_table_row_count_to_be_between(
    rows: Sequence[Mapping[str, object]],
    kwargs: Mapping[str, object],
) -> dict[str, object]:
    row_count = len(rows)
    min_value = _optional_int(kwargs.get("min_value"))
    max_value = _optional_int(kwargs.get("max_value"))
    passed = (min_value is None or row_count >= min_value) and (
        max_value is None or row_count <= max_value
    )
    return {
        "passed_count": 1 if passed else 0,
        "failed_count": 0 if passed else 1,
        "total_count": 1,
        "details": {"row_count": row_count, "min_value": min_value, "max_value": max_value},
    }


def _expect_column_values_to_not_be_null(
    rows: Sequence[Mapping[str, object]],
    kwargs: Mapping[str, object],
) -> dict[str, object]:
    column = str(kwargs["column"])
    passed = sum(1 for row in rows if _present(row.get(column)))
    return _row_metric(rows, passed, {"column": column})


def _expect_column_values_to_be_unique(
    rows: Sequence[Mapping[str, object]],
    kwargs: Mapping[str, object],
) -> dict[str, object]:
    column = str(kwargs["column"])
    return _uniqueness_metric(rows, lambda row: (_normalized(row.get(column)),), {"column": column})


def _expect_compound_columns_to_be_unique(
    rows: Sequence[Mapping[str, object]],
    kwargs: Mapping[str, object],
) -> dict[str, object]:
    columns = tuple(str(column) for column in _sequence(kwargs["column_list"]))
    return _uniqueness_metric(
        rows,
        lambda row: tuple(_normalized(row.get(column)) for column in columns),
        {"column_list": list(columns)},
    )


def _expect_column_values_to_match_regex(
    rows: Sequence[Mapping[str, object]],
    kwargs: Mapping[str, object],
) -> dict[str, object]:
    column = str(kwargs["column"])
    pattern = re.compile(str(kwargs["regex"]))
    allow_null = bool(kwargs.get("allow_null", True))
    passed = 0
    examples: list[object] = []
    for row in rows:
        value = row.get(column)
        if not _present(value) and allow_null:
            passed += 1
            continue
        if _present(value) and pattern.match(str(value)):
            passed += 1
        elif len(examples) < 5:
            examples.append(value)
    return _row_metric(rows, passed, {"column": column, "regex": pattern.pattern, "examples": examples})


def _expect_column_values_to_be_in_set(
    rows: Sequence[Mapping[str, object]],
    kwargs: Mapping[str, object],
) -> dict[str, object]:
    column = str(kwargs["column"])
    allowed_values = {str(value) for value in _sequence(kwargs["value_set"])}
    allow_null = bool(kwargs.get("allow_null", False))
    passed = 0
    examples: list[object] = []
    for row in rows:
        value = row.get(column)
        if not _present(value) and allow_null:
            passed += 1
            continue
        if _present(value) and str(value) in allowed_values:
            passed += 1
        elif len(examples) < 5:
            examples.append(value)
    return _row_metric(rows, passed, {"column": column, "allowed_values": sorted(allowed_values), "examples": examples})


def _expect_column_values_to_be_between(
    rows: Sequence[Mapping[str, object]],
    kwargs: Mapping[str, object],
) -> dict[str, object]:
    column = str(kwargs["column"])
    min_value = _optional_float(kwargs.get("min_value"))
    max_value = _optional_float(kwargs.get("max_value"))
    allow_null = bool(kwargs.get("allow_null", False))
    passed = 0
    examples: list[object] = []
    for row in rows:
        raw_value = row.get(column)
        value = _optional_float(raw_value)
        if value is None and allow_null:
            passed += 1
            continue
        if value is not None and (min_value is None or value >= min_value) and (
            max_value is None or value <= max_value
        ):
            passed += 1
        elif len(examples) < 5:
            examples.append(raw_value)
    return _row_metric(
        rows,
        passed,
        {"column": column, "min_value": min_value, "max_value": max_value, "examples": examples},
    )


def _expect_column_pair_values_a_to_be_greater_than_or_equal_to_b(
    rows: Sequence[Mapping[str, object]],
    kwargs: Mapping[str, object],
) -> dict[str, object]:
    column_a = str(kwargs["column_A"])
    column_b = str(kwargs["column_B"])
    allow_null = bool(kwargs.get("allow_null", True))
    passed = 0
    examples: list[dict[str, object]] = []
    for row in rows:
        raw_a = row.get(column_a)
        raw_b = row.get(column_b)
        value_a = _parse_comparable(raw_a)
        value_b = _parse_comparable(raw_b)
        if (value_a is None or value_b is None) and allow_null:
            passed += 1
            continue
        if value_a is not None and value_b is not None and value_a >= value_b:
            passed += 1
        elif len(examples) < 5:
            examples.append({column_a: raw_a, column_b: raw_b})
    return _row_metric(rows, passed, {"column_A": column_a, "column_B": column_b, "examples": examples})


def _expect_column_max_to_be_recent(
    rows: Sequence[Mapping[str, object]],
    kwargs: Mapping[str, object],
    *,
    current_time: datetime,
) -> dict[str, object]:
    column = str(kwargs["column"])
    max_age_hours = _required_float(kwargs["max_age_hours"])
    parsed_values = [_parse_datetime(row.get(column)) for row in rows]
    present_values = [value for value in parsed_values if value is not None]
    max_value = max(present_values) if present_values else None
    min_allowed = current_time - timedelta(hours=max_age_hours)
    passed = max_value is not None and max_value >= min_allowed
    return {
        "passed_count": 1 if passed else 0,
        "failed_count": 0 if passed else 1,
        "total_count": 1,
        "details": {
            "column": column,
            "max_value": max_value.isoformat() if max_value else None,
            "max_age_hours": max_age_hours,
            "min_allowed": min_allowed.isoformat(),
        },
    }


def _uniqueness_metric(
    rows: Sequence[Mapping[str, object]],
    key_fn: Any,
    details: Mapping[str, object],
) -> dict[str, object]:
    counts: dict[tuple[object, ...], int] = {}
    for row in rows:
        key = key_fn(row)
        counts[key] = counts.get(key, 0) + 1
    duplicate_keys = {key for key, count in counts.items() if count > 1}
    failed = sum(1 for row in rows if key_fn(row) in duplicate_keys)
    result_details = dict(details)
    result_details["duplicate_count"] = failed
    result_details["duplicate_examples"] = [list(key) for key in sorted(duplicate_keys)[:5]]
    return _row_metric(rows, len(rows) - failed, result_details)


def _row_metric(
    rows: Sequence[Mapping[str, object]],
    passed_count: int,
    details: Mapping[str, object],
) -> dict[str, object]:
    total = len(rows)
    failed = max(total - passed_count, 0)
    return {
        "passed_count": passed_count,
        "failed_count": failed,
        "total_count": total,
        "details": dict(details),
    }


def _rule_type(expectation_type: str) -> str:
    if "not_be_null" in expectation_type:
        return "completeness"
    if "unique" in expectation_type:
        return "uniqueness"
    if "regex" in expectation_type or "in_set" in expectation_type or "between" in expectation_type:
        return "validity"
    if "pair_values" in expectation_type:
        return "consistency"
    if "recent" in expectation_type:
        return "freshness"
    return "quality"


def _quality_score(passed_count: int, total_count: int) -> float:
    if total_count == 0:
        return 1.0
    return round(passed_count / total_count, 4)


def _mapping(value: object) -> dict[str, object]:
    if isinstance(value, Mapping):
        return dict(cast(Mapping[str, object], value))
    return {}


def _sequence(value: object) -> Sequence[object]:
    if isinstance(value, Sequence) and not isinstance(value, str | bytes):
        return value
    raise TypeError(f"Expected a sequence value, received {type(value).__name__}.")


def _schema_and_table(table_name: str) -> tuple[str, str]:
    parts = table_name.split(".")
    if len(parts) >= 2:
        return parts[-2].upper(), parts[-1].upper()
    return "UNKNOWN", table_name.upper()


def _default_suite_name(table_name: str) -> str:
    return f"{table_name.split('.')[-1].lower()}_suite"


def _stable_id(*parts: object) -> str:
    payload = "|".join(str(part) for part in parts)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:32]


def _now_iso(current_time: datetime | None = None) -> str:
    return (current_time or datetime.now(tz=UTC)).isoformat()


def _present(value: object) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    return True


def _normalized(value: object) -> object:
    if isinstance(value, str):
        return value.strip().upper()
    return value


def _optional_int(value: object) -> int | None:
    parsed = _optional_float(value)
    return int(parsed) if parsed is not None else None


def _required_int(value: object) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float | str):
        return int(value)
    raise TypeError(f"Expected an integer-compatible value, received {type(value).__name__}.")


def _required_float(value: object) -> float:
    if isinstance(value, int | float | str):
        return float(value)
    raise TypeError(f"Expected a float-compatible value, received {type(value).__name__}.")


def _optional_float(value: object) -> float | None:
    if value is None:
        return None
    if not isinstance(value, int | float | str):
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _parse_comparable(value: object) -> float | None:
    timestamp = _parse_datetime(value)
    if timestamp is not None:
        return timestamp.timestamp()
    return _optional_float(value)


def _parse_datetime(value: object) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    text = str(value).strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
