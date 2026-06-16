"""Survivorship rules for Customer 360 golden customer records."""

from __future__ import annotations

import json
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from customer360.cleansing.standardizers import (
    combine_address,
    normalize_phone,
    normalize_website_domain,
    standardize_email,
)

IDENTITY_FIELDS = ("company_name", "email", "phone", "address")
PROFILE_FIELDS = ("website_domain", "industry", "customer_status")
SURVIVORSHIP_RULE_NAME = "source_priority_quality_recency"


@dataclass(frozen=True)
class SurvivorshipDecision:
    """Selected winner for one golden-record field."""

    field_name: str
    value: object | None
    source_system: str | None
    source_customer_id: str | None
    rule_name: str
    confidence_score: float

    def to_dict(self) -> dict[str, object | None]:
        """Return a JSON-serializable decision payload."""
        return {
            "field_name": self.field_name,
            "value": self.value,
            "source_system": self.source_system,
            "source_customer_id": self.source_customer_id,
            "rule_name": self.rule_name,
            "confidence_score": self.confidence_score,
        }


class GoldenRecordGenerator:
    """Builds golden customer records from resolved clusters and Silver rows."""

    def __init__(self, *, record_version: str = "v1") -> None:
        self._record_version = record_version

    def generate(
        self,
        clusters: Sequence[Mapping[str, object]],
        silver_records: Sequence[Mapping[str, object]],
        *,
        load_batch_id: str | None = None,
    ) -> tuple[dict[str, object], ...]:
        """Generate one golden customer master row for every customer cluster."""
        silver_index = {_record_key(record): dict(record) for record in silver_records}
        rows: list[dict[str, object]] = []
        now = datetime.now(tz=UTC).isoformat()

        for cluster in clusters:
            member_records = self._member_records(cluster, silver_index)
            if not member_records:
                continue

            decisions = {
                field_name: self._choose_field(field_name, member_records)
                for field_name in (*IDENTITY_FIELDS, *PROFILE_FIELDS)
            }
            primary_record = self._choose_primary_record(cluster, member_records)
            address_record = self._decision_record(decisions["address"], member_records)
            member_keys = [_record_key(record) for record in member_records]
            source_systems = sorted({source_system for source_system, _ in member_keys})
            source_customer_ids = sorted({source_customer_id for _, source_customer_id in member_keys})

            first_seen_at = _earliest_timestamp(
                record.get("created_date") or record.get("last_modified_timestamp")
                for record in member_records
            )
            last_seen_at = _latest_timestamp(
                record.get("last_modified_timestamp") or record.get("created_date")
                for record in member_records
            )
            selected_values = {
                field_name: decisions[field_name].value for field_name in IDENTITY_FIELDS
            }

            rows.append(
                {
                    "golden_customer_id": str(cluster["golden_customer_id"]),
                    "cluster_id": str(cluster["cluster_id"]),
                    "source_customer_ids": source_customer_ids,
                    "source_systems": source_systems,
                    "company_name": decisions["company_name"].value,
                    "email": decisions["email"].value,
                    "phone": decisions["phone"].value,
                    "address_line_1": _clean(address_record.get("address_line_1"))
                    if address_record
                    else None,
                    "address_line_2": _clean(address_record.get("address_line_2"))
                    if address_record
                    else None,
                    "city": _clean(address_record.get("city")) if address_record else None,
                    "state_region": _clean(address_record.get("state_region"))
                    if address_record
                    else None,
                    "postal_code": _clean(address_record.get("postal_code"))
                    if address_record
                    else None,
                    "country": _clean(address_record.get("country")) if address_record else None,
                    "address": decisions["address"].value,
                    "website_domain": decisions["website_domain"].value,
                    "industry": decisions["industry"].value,
                    "customer_status": decisions["customer_status"].value,
                    "primary_source_system": _clean(primary_record.get("source_system")),
                    "primary_source_customer_id": _clean(
                        primary_record.get("source_customer_id")
                    ),
                    "first_seen_at": first_seen_at,
                    "last_seen_at": last_seen_at,
                    "confidence_score": _bounded_float(cluster.get("confidence_score"), 1.0),
                    "completeness_score": _completeness_score(selected_values),
                    "data_quality_score": _member_data_quality_score(member_records),
                    "survivorship_rules": {
                        field_name: decision.to_dict()
                        for field_name, decision in decisions.items()
                    },
                    "golden_record_version": self._record_version,
                    "is_active": True,
                    "created_at": now,
                    "updated_at": now,
                    "load_batch_id": load_batch_id,
                }
            )

        return tuple(sorted(rows, key=lambda row: str(row["golden_customer_id"])))

    def _member_records(
        self,
        cluster: Mapping[str, object],
        silver_index: Mapping[tuple[str, str], dict[str, object]],
    ) -> list[dict[str, object]]:
        member_keys = _cluster_member_keys(cluster)
        if member_keys:
            return [silver_index[key] for key in member_keys if key in silver_index]

        source_customer_ids = set(_coerce_string_sequence(cluster.get("source_customer_ids")))
        source_systems = set(_coerce_string_sequence(cluster.get("source_systems")))
        return [
            record
            for (source_system, source_customer_id), record in silver_index.items()
            if source_customer_id in source_customer_ids and source_system in source_systems
        ]

    def _choose_field(
        self,
        field_name: str,
        records: Sequence[Mapping[str, object]],
    ) -> SurvivorshipDecision:
        candidates: list[tuple[Mapping[str, object], str]] = []
        for record in records:
            value = _field_value(record, field_name)
            if value is not None:
                candidates.append((record, value))
        if not candidates:
            return SurvivorshipDecision(
                field_name=field_name,
                value=None,
                source_system=None,
                source_customer_id=None,
                rule_name=SURVIVORSHIP_RULE_NAME,
                confidence_score=0.0,
            )

        winner, value = min(
            candidates,
            key=lambda candidate: _candidate_sort_key(
                candidate[0],
                candidate[1],
                field_name,
            ),
        )
        return SurvivorshipDecision(
            field_name=field_name,
            value=value,
            source_system=_clean(winner.get("source_system")),
            source_customer_id=_clean(winner.get("source_customer_id")),
            rule_name=SURVIVORSHIP_RULE_NAME,
            confidence_score=_candidate_confidence(winner, field_name, value),
        )

    def _choose_primary_record(
        self,
        cluster: Mapping[str, object],
        records: Sequence[Mapping[str, object]],
    ) -> Mapping[str, object]:
        representative_key = (
            _clean(cluster.get("representative_source_system")),
            _clean(cluster.get("representative_source_customer_id")),
        )
        for record in records:
            if _record_key(record) == representative_key:
                return record
        return min(records, key=_record_sort_key)

    def _decision_record(
        self,
        decision: SurvivorshipDecision,
        records: Sequence[Mapping[str, object]],
    ) -> Mapping[str, object] | None:
        if decision.source_system is None or decision.source_customer_id is None:
            return None
        for record in records:
            if _record_key(record) == (decision.source_system, decision.source_customer_id):
                return record
        return None


def _cluster_member_keys(cluster: Mapping[str, object]) -> list[tuple[str, str]]:
    keys: list[tuple[str, str]] = []
    for member in _coerce_sequence(cluster.get("source_members")):
        if not isinstance(member, Mapping):
            continue
        source_system = _clean(member.get("source_system"))
        source_customer_id = _clean(member.get("source_customer_id"))
        if source_system and source_customer_id:
            keys.append((source_system, source_customer_id))
    return sorted(set(keys))


def _field_value(record: Mapping[str, object], field_name: str) -> str | None:
    if field_name == "email":
        return standardize_email(record.get("email"))
    if field_name == "phone":
        return normalize_phone(record.get("phone"))
    if field_name == "address":
        return _clean(record.get("address")) or combine_address(
            record.get("address_line_1"),
            record.get("city"),
            record.get("state_region"),
            record.get("postal_code"),
            record.get("country"),
        )
    if field_name == "website_domain":
        return normalize_website_domain(record.get("website_domain"))
    return _clean(record.get(field_name))


def _candidate_sort_key(
    record: Mapping[str, object],
    value: str,
    field_name: str,
) -> tuple[float, float, float, float, float, float, float, str, str]:
    return (
        0.0 if _passes_field_validation(field_name, value) else 1.0,
        _source_priority(record),
        -_bounded_float(record.get("data_quality_score"), 0.0),
        -_bounded_float(record.get("completeness_score"), 0.0),
        -_timestamp_sort_value(record.get("last_modified_timestamp")),
        -_timestamp_sort_value(record.get("created_date")),
        -float(len(value)),
        _clean(record.get("source_system")) or "",
        _clean(record.get("source_customer_id")) or "",
    )


def _record_sort_key(record: Mapping[str, object]) -> tuple[float, float, float, float, str, str]:
    return (
        _source_priority(record),
        -_bounded_float(record.get("data_quality_score"), 0.0),
        -_bounded_float(record.get("completeness_score"), 0.0),
        -_timestamp_sort_value(record.get("last_modified_timestamp")),
        _clean(record.get("source_system")) or "",
        _clean(record.get("source_customer_id")) or "",
    )


def _candidate_confidence(
    record: Mapping[str, object],
    field_name: str,
    value: str,
) -> float:
    quality = _bounded_float(record.get("data_quality_score"), 0.0)
    completeness = _bounded_float(record.get("completeness_score"), 0.0)
    validation_bonus = 1.0 if _passes_field_validation(field_name, value) else 0.5
    return round(min(1.0, (quality * 0.5) + (completeness * 0.3) + (validation_bonus * 0.2)), 4)


def _passes_field_validation(field_name: str, value: str) -> bool:
    if field_name == "email":
        return bool(re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", value))
    if field_name == "phone":
        return len(re.sub(r"\D", "", value)) >= 7
    if field_name == "address":
        return len(value) >= 8
    return bool(value)


def _member_data_quality_score(records: Sequence[Mapping[str, object]]) -> float:
    quality_scores = [
        _bounded_float(record.get("data_quality_score"), 0.0)
        for record in records
        if record.get("data_quality_score") is not None
    ]
    if not quality_scores:
        return 0.0
    return round(sum(quality_scores) / len(quality_scores), 4)


def _completeness_score(values: Mapping[str, object | None]) -> float:
    return round(
        sum(1 for value in values.values() if _clean(value) is not None) / len(values),
        4,
    )


def _record_key(record: Mapping[str, object]) -> tuple[str, str]:
    return (
        _clean(record.get("source_system")) or "",
        _clean(record.get("source_customer_id")) or "",
    )


def _source_priority(record: Mapping[str, object]) -> float:
    return _float_or_default(record.get("source_priority"), 100.0)


def _bounded_float(value: object, default: float) -> float:
    parsed = _float_or_default(value, default)
    return max(0.0, min(1.0, parsed))


def _float_or_default(value: object, default: float) -> float:
    if value is None:
        return default
    if not isinstance(value, int | float | str):
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _earliest_timestamp(values: Iterable[object]) -> str | None:
    timestamps = [_parse_timestamp(value) for value in values if value is not None]
    parsed = [value for value in timestamps if value is not None]
    return min(parsed).isoformat() if parsed else None


def _latest_timestamp(values: Iterable[object]) -> str | None:
    timestamps = [_parse_timestamp(value) for value in values if value is not None]
    parsed = [value for value in timestamps if value is not None]
    return max(parsed).isoformat() if parsed else None


def _timestamp_sort_value(value: object) -> float:
    parsed = _parse_timestamp(value)
    return parsed.timestamp() if parsed is not None else 0.0


def _parse_timestamp(value: object) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo is not None else value.replace(tzinfo=UTC)
    text = _clean(value)
    if text is None:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)


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
