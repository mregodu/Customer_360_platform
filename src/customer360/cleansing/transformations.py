"""Bronze-to-silver transformation functions."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, date, datetime

from customer360.cleansing.standardizers import (
    combine_address,
    extract_email_domain,
    normalize_company_name,
    normalize_phone,
    normalize_website_domain,
    standardize_address,
    standardize_city,
    standardize_company_name,
    standardize_country,
    standardize_email,
    standardize_name,
    standardize_postal_code,
    standardize_state,
)
from customer360.cleansing.validation import (
    DataQualityReport,
    RecordValidationResult,
    SilverRecordValidator,
)

SILVER_STANDARDIZATION_VERSION = "v1"

_SOURCE_PRIORITIES = {
    "SALESFORCE": 10,
    "LICENSING": 20,
    "PRODUCT_USAGE": 30,
    "ZENDESK": 40,
    "MARKETO": 50,
    "IMPARTNER": 60,
}


@dataclass(frozen=True)
class SilverTransformationResult:
    """Result of transforming a bronze record batch into silver-ready records."""

    customers: tuple[dict[str, object], ...] = field(default_factory=tuple)
    metrics: tuple[dict[str, object], ...] = field(default_factory=tuple)
    partners: tuple[dict[str, object], ...] = field(default_factory=tuple)
    validation_results: tuple[RecordValidationResult, ...] = field(default_factory=tuple)
    quality_report: DataQualityReport | None = None


class BronzeToSilverTransformer:
    """Transforms source-shaped bronze records into Silver-layer records."""

    def __init__(self, validator: SilverRecordValidator | None = None) -> None:
        self._validator = validator or SilverRecordValidator()

    def transform_batch(
        self,
        source_system: str,
        records: Iterable[Mapping[str, object]],
    ) -> SilverTransformationResult:
        """Transform a batch of bronze records for one source system."""
        source = source_system.upper()
        customers: list[dict[str, object]] = []
        metrics: list[dict[str, object]] = []
        partners: list[dict[str, object]] = []
        validations: list[RecordValidationResult] = []

        for record in records:
            if source == "IMPARTNER":
                partner = transform_partner_profile(record)
                partners.append(partner)
                validations.append(self._validator.validate_partner(partner))
                continue

            customer = transform_customer_identity(source, record)
            if customer is not None:
                validation = self._validator.validate_customer(customer)
                customer["completeness_score"] = validation.completeness_score
                customer["data_quality_score"] = validation.quality_score
                customers.append(customer)
                validations.append(validation)

            metric = transform_customer_metric(source, record)
            if metric is not None:
                metrics.append(metric)

        return SilverTransformationResult(
            customers=tuple(customers),
            metrics=tuple(metrics),
            partners=tuple(partners),
            validation_results=tuple(validations),
            quality_report=self._validator.build_report(validations),
        )


def transform_customer_identity(
    source_system: str,
    record: Mapping[str, object],
) -> dict[str, object] | None:
    """Transform one bronze customer-like record into `SILVER.silver_customer` shape."""
    source = source_system.upper()
    source_customer_id = _source_customer_id(source, record)
    if source_customer_id is None:
        return None

    company_name = standardize_company_name(record.get("company_name"))
    email = standardize_email(record.get("email"))
    phone = normalize_phone(record.get("phone"))
    address_line_1 = _address_line_1(source, record)
    city = standardize_city(record.get("billing_city"))
    state_region = standardize_state(record.get("billing_state"))
    postal_code = standardize_postal_code(record.get("billing_postal_code"))
    country = standardize_country(record.get("billing_country"))

    if source != "SALESFORCE":
        city = city or standardize_city(record.get("city"))
        state_region = state_region or standardize_state(record.get("state_region"))
        postal_code = postal_code or standardize_postal_code(record.get("postal_code"))
        country = country or standardize_country(record.get("country"))

    standardized: dict[str, object] = {
        "source_system": source,
        "source_customer_id": source_customer_id,
        "source_record_id": _text(record.get("source_record_id")),
        "company_name": company_name,
        "company_name_normalized": normalize_company_name(company_name),
        "email": email,
        "email_domain": extract_email_domain(email),
        "phone": phone,
        "address_line_1": address_line_1,
        "address_line_2": standardize_address(record.get("billing_address_line_2")),
        "city": city,
        "state_region": state_region,
        "postal_code": postal_code,
        "country": country,
        "address": combine_address(address_line_1, city, state_region, postal_code, country),
        "website_domain": normalize_website_domain(record.get("website")),
        "industry": standardize_name(record.get("industry")),
        "customer_status": standardize_name(_customer_status(source, record)),
        "created_date": _text(record.get("created_date")),
        "last_modified_timestamp": _last_modified(record),
        "is_deleted": bool(record.get("is_deleted", False)),
        "source_priority": _SOURCE_PRIORITIES.get(source, 100),
        "completeness_score": 0.0,
        "data_quality_score": 0.0,
        "standardization_version": SILVER_STANDARDIZATION_VERSION,
        "load_batch_id": _text(record.get("load_batch_id")),
        "standardized_at": _utc_now(),
    }
    standardized["record_hash"] = stable_record_hash(standardized, exclude=("standardized_at",))
    return standardized


def transform_customer_metric(
    source_system: str,
    record: Mapping[str, object],
) -> dict[str, object] | None:
    """Transform one bronze record into `SILVER.silver_customer_metric_daily` shape."""
    source = source_system.upper()
    source_customer_id = _source_customer_id(source, record)
    if source_customer_id is None:
        return None

    metric_date = _metric_date(source, record)
    if metric_date is None:
        return None

    return {
        "source_system": source,
        "source_customer_id": source_customer_id,
        "metric_date": metric_date,
        "product_usage_score": _product_usage_score(source, record),
        "marketing_engagement_score": _number(record.get("engagement_score")),
        "support_activity_score": _support_activity_score(source, record),
        "login_count": _integer(record.get("login_count")),
        "active_days": _integer(record.get("active_days")),
        "active_users": _integer(record.get("active_users")),
        "feature_usage": record.get("feature_usage"),
        "campaign_count": 1 if source == "MARKETO" and record.get("campaign") else None,
        "ticket_count": _integer(record.get("ticket_count")),
        "satisfaction_score": _number(record.get("satisfaction_score")),
        "response_time_minutes": _number(record.get("response_time_minutes")),
        "license_type": standardize_name(record.get("license_type")),
        "renewal_status": standardize_name(record.get("renewal_status")),
        "license_expiration_date": _text(record.get("expiration_date")),
        "contract_value": _number(record.get("contract_value")),
        "seat_count": _integer(record.get("seat_count")),
        "load_batch_id": _text(record.get("load_batch_id")),
        "updated_at": _utc_now(),
    }


def transform_partner_profile(record: Mapping[str, object]) -> dict[str, object]:
    """Transform one Impartner bronze record into `SILVER.silver_partner_profile` shape."""
    company_name = standardize_company_name(record.get("company_name"))
    certifications = _certifications(record.get("certifications"))
    partner: dict[str, object] = {
        "source_system": "IMPARTNER",
        "partner_id": _text(record.get("partner_id")) or _text(record.get("source_record_id")),
        "company_name": company_name,
        "company_name_normalized": normalize_company_name(company_name),
        "email": standardize_email(record.get("email")),
        "phone": normalize_phone(record.get("phone")),
        "partner_tier": standardize_name(record.get("partner_tier")),
        "certifications": certifications,
        "certification_count": len(certifications),
        "partner_region": standardize_name(record.get("partner_region")),
        "partner_status": standardize_name(record.get("partner_status")),
        "last_modified_timestamp": _last_modified(record),
        "is_deleted": bool(record.get("is_deleted", False)),
        "data_quality_score": 0.0,
        "load_batch_id": _text(record.get("load_batch_id")),
        "standardized_at": _utc_now(),
    }
    validation = SilverRecordValidator().validate_partner(partner)
    partner["data_quality_score"] = validation.quality_score
    return partner


def quality_metrics_to_rows(
    report: DataQualityReport,
    *,
    run_id: str,
    source_system: str,
    table_name: str,
) -> tuple[dict[str, object], ...]:
    """Convert a quality report into analytics metric rows."""
    measured_at = _utc_now()
    rows = []
    for metric in report.metrics:
        rows.append(
            {
                "metric_id": stable_record_hash(
                    {
                        "run_id": run_id,
                        "source_system": source_system,
                        "table_name": table_name,
                        "rule_name": metric.rule_name,
                    }
                ),
                "run_id": run_id,
                "source_system": source_system,
                "schema_name": "SILVER",
                "table_name": table_name,
                "rule_name": metric.rule_name,
                "rule_type": metric.rule_type,
                "measured_at": measured_at,
                "passed_count": metric.passed_count,
                "failed_count": metric.failed_count,
                "total_count": metric.total_count,
                "quality_score": metric.quality_score,
                "threshold": 0.95,
                "status": metric.status,
                "details": {
                    "average_quality_score": report.average_quality_score,
                    "valid_records": report.valid_records,
                    "invalid_records": report.invalid_records,
                },
            }
        )
    return tuple(rows)


def stable_record_hash(record: Mapping[str, object], exclude: Sequence[str] = ()) -> str:
    """Generate a deterministic hash for change detection."""
    excluded = set(exclude)
    payload = {
        key: _json_safe(value)
        for key, value in sorted(record.items())
        if key not in excluded
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _source_customer_id(source_system: str, record: Mapping[str, object]) -> str | None:
    candidates = {
        "SALESFORCE": ("customer_id", "source_record_id"),
        "MARKETO": ("lead_id", "email", "source_record_id"),
        "ZENDESK": ("customer_id", "support_account_id", "email", "source_record_id"),
        "PRODUCT_USAGE": ("customer_id", "source_record_id"),
        "LICENSING": ("customer_id", "license_id", "source_record_id"),
    }
    for field_name in candidates.get(source_system, ("source_record_id",)):
        value = _text(record.get(field_name))
        if value:
            return value
    return None


def _address_line_1(source_system: str, record: Mapping[str, object]) -> str | None:
    if source_system == "SALESFORCE":
        return standardize_address(record.get("billing_street"))
    return standardize_address(record.get("address_line_1") or record.get("address"))


def _customer_status(source_system: str, record: Mapping[str, object]) -> object:
    if source_system == "MARKETO":
        return record.get("lead_status")
    if source_system == "LICENSING":
        return record.get("renewal_status")
    if source_system == "ZENDESK":
        return record.get("ticket_status")
    return record.get("customer_status")


def _metric_date(source_system: str, record: Mapping[str, object]) -> str | None:
    if source_system == "PRODUCT_USAGE":
        return _text(record.get("event_date"))
    if source_system == "LICENSING":
        return _text(record.get("expiration_date"))
    if source_system == "ZENDESK":
        return _date_from_timestamp(record.get("last_ticket_created_at") or _last_modified(record))
    return _date_from_timestamp(record.get("last_modified_timestamp") or record.get("created_date"))


def _last_modified(record: Mapping[str, object]) -> str | None:
    return _text(record.get("last_modified_timestamp") or record.get("load_timestamp"))


def _date_from_timestamp(value: object) -> str | None:
    text = _text(value)
    if text is None:
        return None
    return text[:10]


def _product_usage_score(source_system: str, record: Mapping[str, object]) -> float | None:
    if source_system != "PRODUCT_USAGE":
        return None
    login_count = _number(record.get("login_count")) or 0.0
    active_days = _number(record.get("active_days")) or 0.0
    active_users = _number(record.get("active_users")) or 0.0
    score = min(
        1.0,
        (login_count / 100 * 0.4) + (active_days / 30 * 0.3) + (active_users / 50 * 0.3),
    )
    return round(score, 4)


def _support_activity_score(source_system: str, record: Mapping[str, object]) -> float | None:
    if source_system != "ZENDESK":
        return None
    ticket_count = _number(record.get("ticket_count")) or 0.0
    satisfaction = _number(record.get("satisfaction_score")) or 0.0
    response_time = _number(record.get("response_time_minutes")) or 0.0
    volume_component = min(ticket_count / 25, 1.0) * 0.4
    satisfaction_component = min(satisfaction / 5, 1.0) * 0.4
    response_component = max(0.0, 1.0 - min(response_time / 1440, 1.0)) * 0.2
    return round(volume_component + satisfaction_component + response_component, 4)


def _certifications(value: object) -> tuple[str, ...]:
    if value is None:
        return tuple()
    if isinstance(value, list | tuple):
        return tuple(str(item).strip().upper() for item in value if str(item).strip())
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return tuple()
        try:
            parsed = json.loads(stripped)
        except json.JSONDecodeError:
            parsed = [part.strip() for part in stripped.split(",")]
        if isinstance(parsed, list):
            return tuple(str(item).strip().upper() for item in parsed if str(item).strip())
    return tuple()


def _number(value: object) -> float | None:
    text = _text(value)
    if text is None:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _integer(value: object) -> int | None:
    number = _number(value)
    return int(number) if number is not None else None


def _text(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    text = str(value).strip()
    return text or None


def _utc_now() -> str:
    return datetime.now(tz=UTC).isoformat()


def _json_safe(value: object) -> object:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, datetime | date):
        return value.isoformat()
    return value
