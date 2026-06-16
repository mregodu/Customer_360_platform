"""Customer enrichment pipeline orchestration."""

from __future__ import annotations

import json
import logging
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any, Protocol

from customer360.enrichment.scoring import (
    ENRICHMENT_MODEL_VERSION,
    EnrichmentScoreCalculator,
)


class CustomerEnrichmentWriter(Protocol):
    """Persistence contract for generated customer enrichment metrics."""

    def write_customer_enrichment_metrics(self, records: Iterable[Mapping[str, object]]) -> int:
        """Persist rows into `GOLD.customer_enrichment_metrics`."""


@dataclass(frozen=True)
class CustomerEnrichmentPipelineResult:
    """Summary from one enrichment pipeline run."""

    clusters_read: int
    metric_rows_read: int
    enrichment_rows_generated: int
    enrichment_rows_written: int


class CustomerEnrichmentPipeline:
    """Generates enrichment metrics from golden clusters and Silver daily metrics."""

    def __init__(
        self,
        *,
        score_calculator: EnrichmentScoreCalculator | None = None,
        writer: CustomerEnrichmentWriter | None = None,
        model_version: str = ENRICHMENT_MODEL_VERSION,
        logger: logging.Logger | None = None,
    ) -> None:
        self._score_calculator = score_calculator or EnrichmentScoreCalculator()
        self._writer = writer
        self._model_version = model_version
        self._logger = logger or logging.getLogger(__name__)

    def generate_metrics(
        self,
        clusters: Sequence[Mapping[str, object]],
        silver_metric_records: Sequence[Mapping[str, object]],
        *,
        load_batch_id: str | None = None,
    ) -> tuple[dict[str, object], ...]:
        """Generate customer enrichment metric rows for every clustered metric date."""
        cluster_index = _cluster_member_index(clusters)
        grouped: dict[tuple[str, str], list[Mapping[str, object]]] = {}
        for metric_record in silver_metric_records:
            member_key = _record_key(metric_record)
            golden_customer_id = cluster_index.get(member_key)
            metric_date = _metric_date(metric_record.get("metric_date"))
            if golden_customer_id is None or metric_date is None:
                continue
            grouped.setdefault((golden_customer_id, metric_date), []).append(metric_record)

        rows = [
            self._build_row(
                golden_customer_id,
                metric_date,
                records,
                load_batch_id=load_batch_id,
            )
            for (golden_customer_id, metric_date), records in grouped.items()
        ]
        return tuple(sorted(rows, key=lambda row: (str(row["metric_date"]), str(row["golden_customer_id"]))))

    def generate_and_write(
        self,
        clusters: Sequence[Mapping[str, object]],
        silver_metric_records: Sequence[Mapping[str, object]],
        *,
        load_batch_id: str | None = None,
    ) -> CustomerEnrichmentPipelineResult:
        """Generate enrichment metrics and persist them with the configured writer."""
        if self._writer is None:
            raise RuntimeError("CustomerEnrichmentPipeline requires a writer for persistence.")

        rows = self.generate_metrics(
            clusters,
            silver_metric_records,
            load_batch_id=load_batch_id,
        )
        written = self._writer.write_customer_enrichment_metrics(rows)
        result = CustomerEnrichmentPipelineResult(
            clusters_read=len(clusters),
            metric_rows_read=len(silver_metric_records),
            enrichment_rows_generated=len(rows),
            enrichment_rows_written=written,
        )
        self._logger.info("customer_enrichment_completed", extra=result.__dict__)
        return result

    def _build_row(
        self,
        golden_customer_id: str,
        metric_date: str,
        records: Sequence[Mapping[str, object]],
        *,
        load_batch_id: str | None,
    ) -> dict[str, object]:
        signals = _aggregate_metric_signals(records)
        signals["metric_date"] = metric_date
        scores = self._score_calculator.score(signals)
        now = datetime.now(tz=UTC).isoformat()
        return {
            "golden_customer_id": golden_customer_id,
            "metric_date": metric_date,
            "lifetime_value": scores.lifetime_value,
            "product_adoption_score": scores.product_adoption_score,
            "engagement_score": scores.engagement_score,
            "support_health_score": scores.support_health_score,
            "renewal_probability": scores.renewal_probability,
            "product_usage_score": signals["product_usage_score"],
            "marketing_engagement_score": signals["marketing_engagement_score"],
            "support_activity_score": signals["support_activity_score"],
            "support_ticket_count": signals["support_ticket_count"],
            "satisfaction_score": signals["satisfaction_score"],
            "response_time_minutes": signals["response_time_minutes"],
            "active_users": signals["active_users"],
            "active_days": signals["active_days"],
            "feature_utilization_score": signals["feature_utilization_score"],
            "renewal_status": signals["renewal_status"],
            "license_expiration_date": signals["license_expiration_date"],
            "contract_value": signals["contract_value"],
            "seat_count": signals["seat_count"],
            "metric_components": {
                "source_systems": sorted(
                    {
                        source_system
                        for source_system in (_clean(record.get("source_system")) for record in records)
                        if source_system is not None
                    }
                ),
                "source_metric_count": len(records),
                "formula_version": self._model_version,
            },
            "model_version": self._model_version,
            "calculated_at": now,
            "load_batch_id": load_batch_id or _latest_text(records, "load_batch_id"),
        }


def _cluster_member_index(clusters: Sequence[Mapping[str, object]]) -> dict[tuple[str, str], str]:
    index: dict[tuple[str, str], str] = {}
    for cluster in clusters:
        golden_customer_id = _clean(cluster.get("golden_customer_id"))
        if golden_customer_id is None:
            continue
        member_keys = _cluster_member_keys(cluster)
        for member_key in member_keys:
            index[member_key] = golden_customer_id
    return index


def _cluster_member_keys(cluster: Mapping[str, object]) -> tuple[tuple[str, str], ...]:
    keys: list[tuple[str, str]] = []
    for member in _coerce_sequence(cluster.get("source_members")):
        if not isinstance(member, Mapping):
            continue
        source_system = _clean(member.get("source_system"))
        source_customer_id = _clean(member.get("source_customer_id"))
        if source_system is not None and source_customer_id is not None:
            keys.append((source_system, source_customer_id))
    if keys:
        return tuple(sorted(set(keys)))

    source_systems = _coerce_string_sequence(cluster.get("source_systems"))
    source_customer_ids = _coerce_string_sequence(cluster.get("source_customer_ids"))
    if len(source_systems) == 1:
        return tuple(sorted((source_systems[0], source_customer_id) for source_customer_id in source_customer_ids))
    return tuple()


def _aggregate_metric_signals(records: Sequence[Mapping[str, object]]) -> dict[str, object]:
    return {
        "product_usage_score": _average(records, "product_usage_score"),
        "marketing_engagement_score": _average(records, "marketing_engagement_score"),
        "support_activity_score": _average(records, "support_activity_score"),
        "support_ticket_count": _sum(records, "ticket_count"),
        "satisfaction_score": _average(records, "satisfaction_score"),
        "response_time_minutes": _average(records, "response_time_minutes"),
        "active_users": _sum(records, "active_users"),
        "active_days": _max(records, "active_days"),
        "feature_utilization_score": _feature_utilization_score(records),
        "renewal_status": _conservative_renewal_status(records),
        "license_expiration_date": _earliest_date(records, "license_expiration_date"),
        "contract_value": _sum(records, "contract_value"),
        "seat_count": _sum(records, "seat_count"),
    }


def _feature_utilization_score(records: Sequence[Mapping[str, object]]) -> float | None:
    explicit = _average(records, "feature_utilization_score")
    if explicit is not None:
        return explicit
    derived = [_feature_usage_ratio(record.get("feature_usage")) for record in records]
    values = [value for value in derived if value is not None]
    if values:
        return round(sum(values) / len(values), 4)
    return _average(records, "product_usage_score")


def _feature_usage_ratio(value: object) -> float | None:
    if value is None:
        return None
    parsed: object = value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return None
    if isinstance(parsed, Mapping):
        if not parsed:
            return None
        enabled = sum(1 for item in parsed.values() if bool(item))
        return round(enabled / len(parsed), 4)
    if isinstance(parsed, Sequence) and not isinstance(parsed, bytes | str):
        if not parsed:
            return None
        enabled = sum(1 for item in parsed if bool(item))
        return round(enabled / len(parsed), 4)
    return None


def _conservative_renewal_status(records: Sequence[Mapping[str, object]]) -> str | None:
    statuses = [_clean(record.get("renewal_status")) for record in records]
    ranked = [(status, _status_risk_rank(status)) for status in statuses if status is not None]
    if not ranked:
        return None
    return min(ranked, key=lambda item: (item[1], item[0]))[0]


def _status_risk_rank(status: str) -> int:
    normalized = status.upper().replace("-", "_").replace(" ", "_")
    if normalized in {"CANCELLED", "CANCELED", "CHURNED", "EXPIRED", "LOST"}:
        return 0
    if normalized in {"AT_RISK", "RISK", "DOWNGRADE_RISK"}:
        return 1
    if normalized in {"OPEN", "PENDING", "IN_PROGRESS"}:
        return 2
    if normalized in {"RENEWED", "ACTIVE", "AUTO_RENEW", "AUTO_RENEWAL"}:
        return 3
    return 2


def _average(records: Sequence[Mapping[str, object]], field_name: str) -> float | None:
    values = [_optional_float(record.get(field_name)) for record in records]
    present = [value for value in values if value is not None]
    if not present:
        return None
    return round(sum(present) / len(present), 4)


def _sum(records: Sequence[Mapping[str, object]], field_name: str) -> float | None:
    values = [_optional_float(record.get(field_name)) for record in records]
    present = [value for value in values if value is not None]
    if not present:
        return None
    return round(sum(present), 4)


def _max(records: Sequence[Mapping[str, object]], field_name: str) -> float | None:
    values = [_optional_float(record.get(field_name)) for record in records]
    present = [value for value in values if value is not None]
    return round(max(present), 4) if present else None


def _earliest_date(records: Sequence[Mapping[str, object]], field_name: str) -> str | None:
    values = [_parse_date(record.get(field_name)) for record in records]
    present = [value for value in values if value is not None]
    return min(present).isoformat() if present else None


def _latest_text(records: Sequence[Mapping[str, object]], field_name: str) -> str | None:
    values = [_clean(record.get(field_name)) for record in records]
    present = [value for value in values if value is not None]
    return present[-1] if present else None


def _record_key(record: Mapping[str, object]) -> tuple[str, str]:
    return (
        _clean(record.get("source_system")) or "",
        _clean(record.get("source_customer_id")) or "",
    )


def _metric_date(value: object) -> str | None:
    parsed = _parse_date(value)
    return parsed.isoformat() if parsed is not None else None


def _parse_date(value: object) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = _clean(value)
    if text is None:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
    except ValueError:
        try:
            return date.fromisoformat(text[:10])
        except ValueError:
            return None


def _optional_float(value: object) -> float | None:
    if value is None:
        return None
    if not isinstance(value, int | float | str):
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _coerce_string_sequence(value: object) -> list[str]:
    values: list[str] = []
    for item in _coerce_sequence(value):
        cleaned = _clean(item)
        if cleaned is not None:
            values.append(cleaned)
    return values


def _coerce_sequence(value: object) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return [value]
        return parsed if isinstance(parsed, list) else [parsed]
    if isinstance(value, Sequence) and not isinstance(value, bytes):
        return list(value)
    return [value]


def _clean(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.upper() in {"NULL", "NONE", "N/A", "NA"}:
        return None
    return text
