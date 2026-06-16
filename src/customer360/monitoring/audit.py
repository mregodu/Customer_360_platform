"""Enterprise audit logging for Customer 360 pipeline runs and ETL steps."""

from __future__ import annotations

import hashlib
import logging
import traceback
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from types import TracebackType
from typing import Literal, Protocol
from uuid import uuid4

AuditStatus = str


def _utc_now() -> datetime:
    return datetime.now(tz=UTC)


class AuditLogWriter(Protocol):
    """Persistence contract for enterprise audit logs."""

    def write_pipeline_execution_log(self, records: Iterable[Mapping[str, object]]) -> int:
        """Persist rows into `ANALYTICS.pipeline_execution_log`."""

    def write_etl_audit_log(self, records: Iterable[Mapping[str, object]]) -> int:
        """Persist rows into `ANALYTICS.etl_audit_log`."""


@dataclass(frozen=True)
class RowCounts:
    """Common row counters tracked across Customer 360 pipelines."""

    rows_read: int = 0
    rows_inserted: int = 0
    rows_updated: int = 0
    rows_deleted: int = 0

    @property
    def rows_processed(self) -> int:
        """Return total rows touched by the pipeline."""
        return self.rows_read + self.rows_inserted + self.rows_updated + self.rows_deleted

    def add(
        self,
        *,
        rows_read: int = 0,
        rows_inserted: int = 0,
        rows_updated: int = 0,
        rows_deleted: int = 0,
    ) -> RowCounts:
        """Return a new counter with increments applied."""
        return RowCounts(
            rows_read=self.rows_read + rows_read,
            rows_inserted=self.rows_inserted + rows_inserted,
            rows_updated=self.rows_updated + rows_updated,
            rows_deleted=self.rows_deleted + rows_deleted,
        )


@dataclass(frozen=True)
class PipelineExecutionLog:
    """Pipeline-level audit record."""

    pipeline_name: str
    run_id: str
    start_time: datetime
    status: AuditStatus
    pipeline_execution_id: str = field(default_factory=lambda: str(uuid4()))
    environment: str | None = None
    source_system: str | None = None
    target_table: str | None = None
    end_time: datetime | None = None
    row_counts: RowCounts = field(default_factory=RowCounts)
    error_message: str | None = None
    error_details: Mapping[str, object] | None = None
    metadata: Mapping[str, object] = field(default_factory=dict)
    created_at: datetime = field(default_factory=_utc_now)

    @property
    def duration_seconds(self) -> float | None:
        """Return run duration in seconds when the pipeline has ended."""
        if self.end_time is None:
            return None
        return round((self.end_time - self.start_time).total_seconds(), 6)

    def to_row(self) -> dict[str, object]:
        """Return a Snowflake-ready row for `ANALYTICS.pipeline_execution_log`."""
        return {
            "pipeline_execution_id": self.pipeline_execution_id,
            "pipeline_name": self.pipeline_name,
            "run_id": self.run_id,
            "environment": self.environment,
            "source_system": self.source_system,
            "target_table": self.target_table,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration_seconds": self.duration_seconds,
            "status": self.status,
            "rows_read": self.row_counts.rows_read,
            "rows_inserted": self.row_counts.rows_inserted,
            "rows_updated": self.row_counts.rows_updated,
            "rows_deleted": self.row_counts.rows_deleted,
            "rows_processed": self.row_counts.rows_processed,
            "error_message": self.error_message,
            "error_details": dict(self.error_details) if self.error_details else None,
            "metadata": dict(self.metadata),
            "created_at": self.created_at.isoformat(),
        }


@dataclass(frozen=True)
class EtlAuditLog:
    """Step-level ETL audit record."""

    run_id: str
    pipeline_name: str
    transformation_step: str
    status: AuditStatus
    audit_id: str = field(default_factory=lambda: str(uuid4()))
    source_table: str | None = None
    destination_table: str | None = None
    execution_timestamp: datetime = field(default_factory=_utc_now)
    row_count: int = 0
    rows_processed: int = 0
    checksum: str | None = None
    error_details: Mapping[str, object] | None = None
    details: Mapping[str, object] = field(default_factory=dict)

    def to_row(self) -> dict[str, object]:
        """Return a Snowflake-ready row for `ANALYTICS.etl_audit_log`."""
        return {
            "audit_id": self.audit_id,
            "run_id": self.run_id,
            "pipeline_name": self.pipeline_name,
            "source_table": self.source_table,
            "transformation_step": self.transformation_step,
            "destination_table": self.destination_table,
            "execution_timestamp": self.execution_timestamp.isoformat(),
            "row_count": self.row_count,
            "rows_processed": self.rows_processed,
            "checksum": self.checksum,
            "status": self.status,
            "error_details": dict(self.error_details) if self.error_details else None,
            "details": dict(self.details),
        }


class AuditLogger:
    """Reusable audit logger for pipeline and ETL step execution."""

    def __init__(
        self,
        *,
        writer: AuditLogWriter | None = None,
        environment: str | None = None,
        clock: Callable[[], datetime] = _utc_now,
        logger: logging.Logger | None = None,
    ) -> None:
        self._writer = writer
        self._environment = environment
        self._clock = clock
        self._logger = logger or logging.getLogger(__name__)

    def start_pipeline(
        self,
        pipeline_name: str,
        *,
        run_id: str | None = None,
        environment: str | None = None,
        source_system: str | None = None,
        target_table: str | None = None,
        metadata: Mapping[str, object] | None = None,
    ) -> PipelineAuditContext:
        """Start a context-managed pipeline audit run."""
        resolved_run_id = run_id or str(uuid4())
        return PipelineAuditContext(
            audit_logger=self,
            pipeline_name=pipeline_name,
            run_id=resolved_run_id,
            environment=environment or self._environment,
            source_system=source_system,
            target_table=target_table,
            metadata=metadata or {},
        )

    def record_pipeline_execution(self, record: PipelineExecutionLog) -> int:
        """Persist and log one pipeline execution record."""
        self._logger.info(
            "pipeline_execution_audited",
            extra={
                "pipeline_name": record.pipeline_name,
                "run_id": record.run_id,
                "status": record.status,
                "rows_processed": record.row_counts.rows_processed,
                "error_message": record.error_message,
            },
        )
        if self._writer is None:
            return 0
        return self._writer.write_pipeline_execution_log([record.to_row()])

    def record_etl_step(
        self,
        *,
        run_id: str,
        pipeline_name: str,
        transformation_step: str,
        status: AuditStatus,
        source_table: str | None = None,
        destination_table: str | None = None,
        row_count: int = 0,
        rows_processed: int | None = None,
        checksum: str | None = None,
        error_details: Mapping[str, object] | None = None,
        details: Mapping[str, object] | None = None,
    ) -> EtlAuditLog:
        """Create, persist, and return one ETL step audit record."""
        record = EtlAuditLog(
            run_id=run_id,
            pipeline_name=pipeline_name,
            source_table=source_table,
            transformation_step=transformation_step,
            destination_table=destination_table,
            execution_timestamp=self._clock(),
            row_count=row_count,
            rows_processed=row_count if rows_processed is None else rows_processed,
            checksum=checksum,
            status=status,
            error_details=error_details,
            details=details or {},
        )
        self._logger.info(
            "etl_step_audited",
            extra={
                "pipeline_name": pipeline_name,
                "run_id": run_id,
                "transformation_step": transformation_step,
                "status": status,
                "rows_processed": record.rows_processed,
            },
        )
        if self._writer is not None:
            self._writer.write_etl_audit_log([record.to_row()])
        return record


class PipelineAuditContext:
    """Context manager that records pipeline completion or failure."""

    def __init__(
        self,
        *,
        audit_logger: AuditLogger,
        pipeline_name: str,
        run_id: str,
        environment: str | None,
        source_system: str | None,
        target_table: str | None,
        metadata: Mapping[str, object],
    ) -> None:
        self._audit_logger = audit_logger
        self.pipeline_name = pipeline_name
        self.run_id = run_id
        self.environment = environment
        self.source_system = source_system
        self.target_table = target_table
        self.metadata = dict(metadata)
        self.start_time = audit_logger._clock()
        self.row_counts = RowCounts()
        self.status: AuditStatus = "RUNNING"
        self.pipeline_record: PipelineExecutionLog | None = None

    def __enter__(self) -> PipelineAuditContext:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> Literal[False]:
        if exc is None:
            self.complete(status="SUCCESS")
        else:
            self.fail(exc, tb)
        return False

    def add_rows(
        self,
        *,
        rows_read: int = 0,
        rows_inserted: int = 0,
        rows_updated: int = 0,
        rows_deleted: int = 0,
    ) -> None:
        """Increment row counters for the pipeline."""
        self.row_counts = self.row_counts.add(
            rows_read=rows_read,
            rows_inserted=rows_inserted,
            rows_updated=rows_updated,
            rows_deleted=rows_deleted,
        )

    def record_step(
        self,
        transformation_step: str,
        *,
        status: AuditStatus = "SUCCESS",
        source_table: str | None = None,
        destination_table: str | None = None,
        row_count: int = 0,
        rows_processed: int | None = None,
        checksum: str | None = None,
        error_details: Mapping[str, object] | None = None,
        details: Mapping[str, object] | None = None,
    ) -> EtlAuditLog:
        """Record a step-level ETL audit event for this pipeline run."""
        return self._audit_logger.record_etl_step(
            run_id=self.run_id,
            pipeline_name=self.pipeline_name,
            transformation_step=transformation_step,
            status=status,
            source_table=source_table,
            destination_table=destination_table,
            row_count=row_count,
            rows_processed=rows_processed,
            checksum=checksum,
            error_details=error_details,
            details=details,
        )

    def complete(self, *, status: AuditStatus = "SUCCESS") -> PipelineExecutionLog:
        """Complete and persist the pipeline audit record."""
        self.status = status
        self.pipeline_record = PipelineExecutionLog(
            pipeline_name=self.pipeline_name,
            run_id=self.run_id,
            environment=self.environment,
            source_system=self.source_system,
            target_table=self.target_table,
            start_time=self.start_time,
            end_time=self._audit_logger._clock(),
            status=status,
            row_counts=self.row_counts,
            metadata=self.metadata,
        )
        self._audit_logger.record_pipeline_execution(self.pipeline_record)
        return self.pipeline_record

    def fail(
        self,
        exc: BaseException,
        tb: TracebackType | None = None,
    ) -> PipelineExecutionLog:
        """Mark the pipeline failed and persist error details."""
        self.status = "FAILED"
        error_details = error_details_from_exception(exc, tb)
        self.pipeline_record = PipelineExecutionLog(
            pipeline_name=self.pipeline_name,
            run_id=self.run_id,
            environment=self.environment,
            source_system=self.source_system,
            target_table=self.target_table,
            start_time=self.start_time,
            end_time=self._audit_logger._clock(),
            status="FAILED",
            row_counts=self.row_counts,
            error_message=str(exc),
            error_details=error_details,
            metadata=self.metadata,
        )
        self._audit_logger.record_pipeline_execution(self.pipeline_record)
        return self.pipeline_record


def checksum_records(records: Iterable[Mapping[str, object]]) -> str:
    """Create a stable checksum for a collection of row-like mappings."""
    digest = hashlib.sha256()
    normalized_records = sorted(
        (dict(record) for record in records),
        key=lambda row: repr(sorted(row.items())),
    )
    for record in normalized_records:
        digest.update(repr(sorted(record.items())).encode("utf-8"))
    return digest.hexdigest()


def error_details_from_exception(
    exc: BaseException,
    tb: TracebackType | None = None,
) -> dict[str, object]:
    """Return structured error details for audit storage."""
    traceback_lines = traceback.format_exception(type(exc), exc, tb or exc.__traceback__)
    return {
        "exception_type": type(exc).__name__,
        "message": str(exc),
        "traceback": traceback_lines,
    }
