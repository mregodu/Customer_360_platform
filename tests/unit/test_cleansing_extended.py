from __future__ import annotations

from customer360.cleansing.transformations import (
    BronzeToSilverTransformer,
    stable_record_hash,
    transform_customer_identity,
    transform_customer_metric,
    transform_partner_profile,
)
from customer360.cleansing.validation import SilverRecordValidator, completeness_score


def test_transform_customer_identity_returns_none_without_source_customer_id() -> None:
    assert transform_customer_identity("PRODUCT_USAGE", {"company_name": "No Id Co"}) is None


def test_transform_marketo_customer_uses_email_as_identity_and_lead_status() -> None:
    customer = transform_customer_identity(
        "MARKETO",
        {
            "email": " Lead@Example.com ",
            "company_name": " Example LLC ",
            "lead_status": " open ",
            "last_modified_timestamp": "2024-02-01T00:00:00",
        },
    )

    assert customer is not None
    assert customer["source_customer_id"] == "Lead@Example.com"
    assert customer["email"] == "lead@example.com"
    assert customer["customer_status"] == "OPEN"
    assert customer["source_priority"] == 50


def test_transform_zendesk_metric_calculates_support_activity_score() -> None:
    metric = transform_customer_metric(
        "ZENDESK",
        {
            "support_account_id": "z-1",
            "last_ticket_created_at": "2024-04-15T10:30:00",
            "ticket_count": "5",
            "satisfaction_score": "4",
            "response_time_minutes": "120",
        },
    )

    assert metric is not None
    assert metric["metric_date"] == "2024-04-15"
    assert metric["support_activity_score"] == 0.5833


def test_transform_licensing_metric_uses_expiration_as_metric_date() -> None:
    metric = transform_customer_metric(
        "LICENSING",
        {
            "license_id": "lic-1",
            "customer_id": "cust-1",
            "expiration_date": "2024-12-31",
            "renewal_status": "auto renew",
            "contract_value": "25000.50",
            "seat_count": "100",
        },
    )

    assert metric is not None
    assert metric["metric_date"] == "2024-12-31"
    assert metric["renewal_status"] == "AUTO RENEW"
    assert metric["contract_value"] == 25000.5
    assert metric["seat_count"] == 100


def test_partner_validation_marks_required_field_failures_and_phone_warning() -> None:
    result = SilverRecordValidator().validate_partner(
        {
            "source_system": "IMPARTNER",
            "partner_id": "",
            "company_name": "",
            "email": "partner@example.com",
            "phone": "12",
        }
    )

    issue_names = {issue.rule_name for issue in result.issues}
    assert not result.is_valid
    assert {"partner_id_required", "company_name_required", "valid_phone"} <= issue_names
    assert result.quality_score < result.completeness_score


def test_build_report_handles_empty_batches_as_perfect_quality() -> None:
    report = SilverRecordValidator().build_report([])

    assert report.total_records == 0
    assert report.valid_records == 0
    assert report.average_quality_score == 1.0
    assert report.metrics[0].status == "PASS"


def test_completeness_score_returns_one_when_no_fields_are_requested() -> None:
    assert completeness_score({}, ()) == 1.0


def test_stable_record_hash_is_order_independent_and_can_exclude_fields() -> None:
    first = stable_record_hash({"id": "1", "name": "Acme", "updated_at": "now"}, exclude=("updated_at",))
    second = stable_record_hash({"updated_at": "later", "name": "Acme", "id": "1"}, exclude=("updated_at",))

    assert first == second


def test_transformer_routes_impartner_records_to_partner_outputs() -> None:
    result = BronzeToSilverTransformer().transform_batch(
        "IMPARTNER",
        [
            {
                "partner_id": "p-1",
                "company_name": "Partner Co",
                "email": "partner@example.com",
                "partner_tier": "gold",
                "partner_region": "north america",
            }
        ],
    )

    assert not result.customers
    assert not result.metrics
    assert len(result.partners) == 1
    assert result.partners[0]["partner_tier"] == "GOLD"
    assert result.quality_report is not None
    assert result.quality_report.total_records == 1


def test_transform_partner_profile_handles_comma_separated_certifications() -> None:
    partner = transform_partner_profile(
        {
            "partner_id": "p-1",
            "company_name": "Partner Co",
            "certifications": "implementation, support, implementation",
        }
    )

    assert partner["certifications"] == ("IMPLEMENTATION", "SUPPORT", "IMPLEMENTATION")
    assert partner["certification_count"] == 3
