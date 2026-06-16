"""Application service for golden customer record generation."""

from __future__ import annotations

import logging
from collections.abc import Iterable, Mapping, Sequence
from typing import Protocol

from customer360.golden.survivorship import GoldenRecordGenerator


class GoldenRecordWriter(Protocol):
    """Persistence contract for generated golden customer records."""

    def write_golden_records(self, records: Iterable[Mapping[str, object]]) -> int:
        """Persist generated records into `GOLD.gold_customer_master`."""


class GoldenRecordService:
    """Coordinates survivorship and persistence for customer master records."""

    def __init__(
        self,
        *,
        generator: GoldenRecordGenerator | None = None,
        writer: GoldenRecordWriter | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self._generator = generator or GoldenRecordGenerator()
        self._writer = writer
        self._logger = logger or logging.getLogger(__name__)

    def generate_records(
        self,
        clusters: Sequence[Mapping[str, object]],
        silver_records: Sequence[Mapping[str, object]],
        *,
        load_batch_id: str | None = None,
    ) -> tuple[dict[str, object], ...]:
        """Generate `GOLD.gold_customer_master` rows from clusters and Silver records."""
        return self._generator.generate(
            clusters,
            silver_records,
            load_batch_id=load_batch_id,
        )

    def generate_and_write(
        self,
        clusters: Sequence[Mapping[str, object]],
        silver_records: Sequence[Mapping[str, object]],
        *,
        load_batch_id: str | None = None,
    ) -> int:
        """Generate golden records and persist them with the configured writer."""
        if self._writer is None:
            raise RuntimeError("GoldenRecordService requires a writer for persistence.")

        records = self.generate_records(
            clusters,
            silver_records,
            load_batch_id=load_batch_id,
        )
        written = self._writer.write_golden_records(records)
        self._logger.info(
            "golden_records_generated",
            extra={
                "clusters_read": len(clusters),
                "silver_records_read": len(silver_records),
                "golden_records_written": written,
                "load_batch_id": load_batch_id,
            },
        )
        return written
