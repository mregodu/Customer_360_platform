"""Ingestion use cases for source-to-bronze processing."""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal, Protocol
from uuid import uuid4

from customer360.config import IngestionSourceConfig
from customer360.ingestion.exceptions import FailedIngestionResult, IngestionRunError
from customer360.ingestion.retry import RetryPolicy, retry_call
from customer360.ingestion.sources import IngestionRecord, SourceExtractor
from customer360.ingestion.watermarks import WatermarkStore

RunStatus = Literal["SUCCESS", "FAILED", "SKIPPED"]


class BronzeLoader(Protocol):
    """Writes records into a bronze target table."""

    def write_records(self, table_name: str, records: Iterable[Mapping[str, object]]) -> int:
        """Write records to a target table and return the number of rows written."""


@dataclass(frozen=True)
class IngestionResult:
    """Result metadata emitted after a source ingestion run."""

    source_name: str
    source_system: str
    source_object: str
    target_table: str
    run_id: str
    status: RunStatus
    started_at: datetime
    ended_at: datetime
    rows_extracted: int = 0
    rows_loaded: int = 0
    previous_watermark: str | None = None
    new_watermark: str | None = None
    error_message: str | None = None


class IngestionService:
    """Coordinates incremental extraction and bronze-layer loading."""

    def __init__(
        self,
        *,
        source_configs: Mapping[str, IngestionSourceConfig],
        sources: Mapping[str, SourceExtractor],
        loader: BronzeLoader,
        watermarks: WatermarkStore,
        retry_policy: RetryPolicy | None = None,
        default_batch_size: int = 10000,
        logger: logging.Logger | None = None,
        sleep: Callable[[float], None] | None = None,
    ) -> None:
        self._source_configs = dict(source_configs)
        self._sources = dict(sources)
        self._loader = loader
        self._watermarks = watermarks
        self._retry_policy = retry_policy or RetryPolicy()
        self._default_batch_size = default_batch_size
        self._logger = logger or logging.getLogger(__name__)
        self._sleep = sleep

    def ingest_source(self, source_name: str, *, raise_on_error: bool = True) -> IngestionResult:
        """Extract changed records for one source and load them into its bronze table."""
        run_id = str(uuid4())
        started_at = _utc_now()
        rows_extracted = 0
        rows_loaded = 0
        new_watermark: str | None = None

        try:
            source_config = self._source_configs[source_name]
            if not source_config.enabled:
                return IngestionResult(
                    source_name=source_name,
                    source_system=source_config.source_system,
                    source_object=source_config.source_object,
                    target_table=source_config.target_table,
                    run_id=run_id,
                    status="SKIPPED",
                    started_at=started_at,
                    ended_at=_utc_now(),
                )

            source = self._sources[source_name]
            previous_watermark = self._watermarks.get_watermark(
                source_config.source_system,
                source_config.source_object,
            )
            batch_size = source_config.batch_size or self._default_batch_size

            self._logger.info(
                "ingestion_started",
                extra={
                    "source_name": source_name,
                    "source_system": source_config.source_system,
                    "target_table": source_config.target_table,
                    "run_id": run_id,
                    "previous_watermark": previous_watermark,
                },
            )

            batches = iter(source.extract(previous_watermark, batch_size))

            while True:
                batch = retry_call(
                    lambda: _next_batch(batches),
                    policy=self._retry_policy,
                    operation_name=f"extract:{source_name}",
                    logger=self._logger,
                    sleep=self._sleep or _noop_sleep,
                )
                if batch is None:
                    break
                rows_extracted += len(batch)
                prepared_batch = [
                    _prepare_bronze_record(record, source_config, run_id)
                    for record in batch
                ]
                batch_watermark = _max_watermark(prepared_batch, source_config.watermark_column)
                if batch_watermark is not None:
                    new_watermark = max(new_watermark, batch_watermark) if new_watermark else batch_watermark

                def load_prepared_batch(
                    batch_to_load: list[IngestionRecord] = prepared_batch,
                ) -> int:
                    return self._loader.write_records(
                        source_config.target_table,
                        batch_to_load,
                    )

                rows_loaded += retry_call(
                    load_prepared_batch,
                    policy=self._retry_policy,
                    operation_name=f"load:{source_name}",
                    logger=self._logger,
                    sleep=self._sleep or _noop_sleep,
                )

            if new_watermark is not None:
                self._watermarks.update_watermark(
                    source_config.source_system,
                    source_config.source_object,
                    source_config.watermark_column,
                    new_watermark,
                    run_id,
                )

            result = IngestionResult(
                source_name=source_name,
                source_system=source_config.source_system,
                source_object=source_config.source_object,
                target_table=source_config.target_table,
                run_id=run_id,
                status="SUCCESS",
                started_at=started_at,
                ended_at=_utc_now(),
                rows_extracted=rows_extracted,
                rows_loaded=rows_loaded,
                previous_watermark=previous_watermark,
                new_watermark=new_watermark,
            )
            self._logger.info(
                "ingestion_completed",
                extra={
                    "source_name": source_name,
                    "target_table": source_config.target_table,
                    "run_id": run_id,
                    "rows_extracted": rows_extracted,
                    "rows_loaded": rows_loaded,
                    "new_watermark": new_watermark,
                },
            )
            return result
        except Exception as exc:
            ended_at = _utc_now()
            failed_source_config = self._source_configs.get(source_name)
            failed = FailedIngestionResult(
                source_name=source_name,
                source_system=(
                    failed_source_config.source_system
                    if failed_source_config is not None
                    else "UNKNOWN"
                ),
                target_table=(
                    failed_source_config.target_table
                    if failed_source_config is not None
                    else "UNKNOWN"
                ),
                rows_extracted=rows_extracted,
                rows_loaded=rows_loaded,
                error_message=str(exc),
            )
            self._logger.exception(
                "ingestion_failed",
                extra={
                    "source_name": source_name,
                    "run_id": run_id,
                    "rows_extracted": rows_extracted,
                    "rows_loaded": rows_loaded,
                    "error_message": str(exc),
                },
            )
            if raise_on_error:
                raise IngestionRunError(failed) from exc
            return IngestionResult(
                source_name=source_name,
                source_system=failed.source_system,
                source_object=(
                    failed_source_config.source_object
                    if failed_source_config is not None
                    else "UNKNOWN"
                ),
                target_table=failed.target_table,
                run_id=run_id,
                status="FAILED",
                started_at=started_at,
                ended_at=ended_at,
                rows_extracted=rows_extracted,
                rows_loaded=rows_loaded,
                error_message=str(exc),
            )

    def ingest_all(self, *, raise_on_error: bool = True) -> list[IngestionResult]:
        """Run ingestion for every configured enabled source."""
        results: list[IngestionResult] = []
        for source_name in self._source_configs:
            results.append(self.ingest_source(source_name, raise_on_error=raise_on_error))
        return results


def _prepare_bronze_record(
    record: Mapping[str, object],
    source_config: IngestionSourceConfig,
    run_id: str,
) -> IngestionRecord:
    prepared = dict(record)
    primary_key_value = prepared.get(source_config.primary_key)
    if primary_key_value is not None and "source_record_id" not in prepared:
        prepared["source_record_id"] = str(primary_key_value)
    prepared.setdefault("source_system", source_config.source_system)
    prepared.setdefault("source_object", source_config.source_object)
    prepared.setdefault("load_batch_id", run_id)
    prepared.setdefault("load_timestamp", _utc_now().isoformat())
    prepared.setdefault("raw_payload", dict(record))
    return prepared


def _max_watermark(
    records: Iterable[Mapping[str, object]],
    watermark_column: str,
) -> str | None:
    values = [str(record[watermark_column]) for record in records if record.get(watermark_column)]
    if not values:
        return None
    return max(values)


def _utc_now() -> datetime:
    return datetime.now(tz=UTC)


def _next_batch(batches: Iterable[list[IngestionRecord]]) -> list[IngestionRecord] | None:
    iterator = iter(batches)
    try:
        return next(iterator)
    except StopIteration:
        return None


def _noop_sleep(_: float) -> None:
    return None
