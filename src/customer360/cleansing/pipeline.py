"""Silver-layer transformation pipeline orchestration."""

from __future__ import annotations

import logging
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Protocol
from uuid import uuid4

from customer360.cleansing.transformations import (
    BronzeToSilverTransformer,
    quality_metrics_to_rows,
)


class BronzeRecordReader(Protocol):
    """Reads incremental bronze records for Silver transformation."""

    def fetch_incremental(
        self,
        table_name: str,
        watermark_column: str,
        since_watermark: str | None,
    ) -> Sequence[Mapping[str, object]]:
        """Fetch bronze records changed after the supplied watermark."""


class SilverRecordWriter(Protocol):
    """Merges transformed records into Silver and analytics targets."""

    def merge_customers(self, records: Iterable[Mapping[str, object]]) -> int:
        """Merge records into `SILVER.silver_customer`."""

    def merge_metrics(self, records: Iterable[Mapping[str, object]]) -> int:
        """Merge records into `SILVER.silver_customer_metric_daily`."""

    def merge_partners(self, records: Iterable[Mapping[str, object]]) -> int:
        """Merge records into `SILVER.silver_partner_profile`."""

    def write_quality_metrics(self, records: Iterable[Mapping[str, object]]) -> int:
        """Write records into `ANALYTICS.data_quality_metrics`."""


@dataclass(frozen=True)
class SilverSourceMapping:
    """Mapping from one bronze source table to its Silver output."""

    source_name: str
    source_system: str
    bronze_table: str
    watermark_column: str = "last_modified_timestamp"
    silver_quality_table: str = "silver_customer"


@dataclass(frozen=True)
class SilverPipelineResult:
    """Outcome from one Silver transformation source run."""

    run_id: str
    source_name: str
    source_system: str
    bronze_rows_read: int
    customers_merged: int
    metrics_merged: int
    partners_merged: int
    quality_metrics_written: int


class SilverTransformationPipeline:
    """Coordinates bronze reads, Python transformations, and Silver merges."""

    def __init__(
        self,
        *,
        mappings: Mapping[str, SilverSourceMapping],
        reader: BronzeRecordReader,
        writer: SilverRecordWriter,
        transformer: BronzeToSilverTransformer | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self._mappings = dict(mappings)
        self._reader = reader
        self._writer = writer
        self._transformer = transformer or BronzeToSilverTransformer()
        self._logger = logger or logging.getLogger(__name__)

    def run_source(
        self,
        source_name: str,
        *,
        since_watermark: str | None = None,
    ) -> SilverPipelineResult:
        """Run Silver transformation for one configured source."""
        run_id = str(uuid4())
        mapping = self._mappings[source_name]
        self._logger.info(
            "silver_transformation_started",
            extra={
                "run_id": run_id,
                "source_name": source_name,
                "bronze_table": mapping.bronze_table,
                "since_watermark": since_watermark,
            },
        )
        bronze_records = self._reader.fetch_incremental(
            mapping.bronze_table,
            mapping.watermark_column,
            since_watermark,
        )
        transformed = self._transformer.transform_batch(mapping.source_system, bronze_records)

        customers_merged = self._writer.merge_customers(transformed.customers)
        metrics_merged = self._writer.merge_metrics(transformed.metrics)
        partners_merged = self._writer.merge_partners(transformed.partners)
        quality_rows = (
            quality_metrics_to_rows(
                transformed.quality_report,
                run_id=run_id,
                source_system=mapping.source_system,
                table_name=mapping.silver_quality_table,
            )
            if transformed.quality_report is not None
            else tuple()
        )
        quality_metrics_written = self._writer.write_quality_metrics(quality_rows)

        result = SilverPipelineResult(
            run_id=run_id,
            source_name=source_name,
            source_system=mapping.source_system,
            bronze_rows_read=len(bronze_records),
            customers_merged=customers_merged,
            metrics_merged=metrics_merged,
            partners_merged=partners_merged,
            quality_metrics_written=quality_metrics_written,
        )
        self._logger.info("silver_transformation_completed", extra=result.__dict__)
        return result

    def run_all(self, *, since_watermark: str | None = None) -> tuple[SilverPipelineResult, ...]:
        """Run Silver transformation for all configured mappings."""
        return tuple(
            self.run_source(source_name, since_watermark=since_watermark)
            for source_name in self._mappings
        )


def default_silver_source_mappings(
    database_name: str = "CUSTOMER360_DB",
) -> dict[str, SilverSourceMapping]:
    """Return default bronze-to-silver mappings for all Customer 360 sources."""
    prefix = f"{database_name}.BRONZE"
    return {
        "salesforce": SilverSourceMapping(
            "salesforce",
            "SALESFORCE",
            f"{prefix}.salesforce_customer_bronze",
            "last_modified_timestamp",
        ),
        "marketo": SilverSourceMapping(
            "marketo",
            "MARKETO",
            f"{prefix}.marketo_lead_bronze",
            "last_modified_timestamp",
        ),
        "zendesk": SilverSourceMapping(
            "zendesk",
            "ZENDESK",
            f"{prefix}.zendesk_support_bronze",
            "last_modified_timestamp",
        ),
        "product_usage": SilverSourceMapping(
            "product_usage",
            "PRODUCT_USAGE",
            f"{prefix}.product_usage_bronze",
            "last_modified_timestamp",
        ),
        "licensing": SilverSourceMapping(
            "licensing",
            "LICENSING",
            f"{prefix}.licensing_customer_bronze",
            "last_modified_timestamp",
        ),
        "impartner": SilverSourceMapping(
            "impartner",
            "IMPARTNER",
            f"{prefix}.impartner_partner_bronze",
            "last_modified_timestamp",
            "silver_partner_profile",
        ),
    }
