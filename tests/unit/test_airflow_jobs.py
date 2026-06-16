from __future__ import annotations

from customer360.domain.customer import SourceCustomerRecord
from customer360.infrastructure.domo import DomoPublisher
from customer360.interfaces.airflow.jobs import (
    DOMO_DATASET_TABLES,
    INGESTION_SOURCES,
    _source_customer_record,
)


def test_airflow_jobs_cover_required_sources_and_domo_outputs() -> None:
    assert INGESTION_SOURCES == (
        "salesforce",
        "marketo",
        "zendesk",
        "product_usage",
        "licensing",
        "impartner",
    )
    assert {
        "customer_health_scores",
        "executive_customer_kpis_daily",
        "executive_segment_health_daily",
        "customer_success_account_daily",
        "customer_health_drilldown",
        "partner_performance_daily",
        "data_quality_dashboard_daily",
    } <= set(DOMO_DATASET_TABLES)


def test_source_customer_record_mapping_cleans_snowflake_rows() -> None:
    record = _source_customer_record(
        {
            "source_system": "SALESFORCE",
            "source_customer_id": "001",
            "company_name": "  ACME INC  ",
            "email": "hello@example.com",
            "phone": "3125550101",
            "address": "  ",
            "website_domain": "acme.com",
        }
    )

    assert isinstance(record, SourceCustomerRecord)
    assert record.source_system == "SALESFORCE"
    assert record.source_customer_id == "001"
    assert record.company_name == "ACME INC"
    assert record.address is None
    assert record.website_domain == "acme.com"


def test_domo_publisher_dry_run_returns_stable_dataset_reference() -> None:
    publisher = DomoPublisher(dry_run=True)

    dataset_id = publisher.publish_dataset(
        "customer360_dev_customer_health_scores",
        [{"golden_customer_id": "gold-1", "health_class": "Healthy"}],
    )

    assert dataset_id == "dry-run:customer360_dev_customer_health_scores"
