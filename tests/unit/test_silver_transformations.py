from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence

from customer360.cleansing.pipeline import (
    SilverSourceMapping,
    SilverTransformationPipeline,
)
from customer360.cleansing.transformations import (
    BronzeToSilverTransformer,
    quality_metrics_to_rows,
    transform_customer_identity,
    transform_customer_metric,
    transform_partner_profile,
)
from customer360.cleansing.validation import SilverRecordValidator


class FakeBronzeReader:
    def __init__(self, records: Sequence[Mapping[str, object]]) -> None:
        self.records = records

    def fetch_incremental(
        self,
        table_name: str,
        watermark_column: str,
        since_watermark: str | None,
    ) -> Sequence[Mapping[str, object]]:
        assert table_name == "bronze.salesforce"
        assert watermark_column == "last_modified_timestamp"
        assert since_watermark == "2024-01-01T00:00:00"
        return self.records


class FakeSilverWriter:
    def __init__(self) -> None:
        self.customers: list[dict[str, object]] = []
        self.metrics: list[dict[str, object]] = []
        self.partners: list[dict[str, object]] = []
        self.quality: list[dict[str, object]] = []

    def merge_customers(self, records: Iterable[Mapping[str, object]]) -> int:
        rows = [dict(record) for record in records]
        self.customers.extend(rows)
        return len(rows)

    def merge_metrics(self, records: Iterable[Mapping[str, object]]) -> int:
        rows = [dict(record) for record in records]
        self.metrics.extend(rows)
        return len(rows)

    def merge_partners(self, records: Iterable[Mapping[str, object]]) -> int:
        rows = [dict(record) for record in records]
        self.partners.extend(rows)
        return len(rows)

    def write_quality_metrics(self, records: Iterable[Mapping[str, object]]) -> int:
        rows = [dict(record) for record in records]
        self.quality.extend(rows)
        return len(rows)


def test_transform_customer_identity_standardizes_salesforce_record() -> None:
    record = {
        "source_record_id": "sf-1",
        "customer_id": "001",
        "company_name": "  Acme, Inc. ",
        "email": " USER@Example.COM ",
        "phone": "+1 (312) 555-0101",
        "billing_street": "12 main street",
        "billing_city": "Chicago",
        "billing_state": "Illinois",
        "billing_postal_code": "60601",
        "billing_country": "United States",
        "website": "https://www.acme.com/home",
        "industry": " software ",
        "last_modified_timestamp": "2024-01-02T00:00:00",
        "load_batch_id": "batch-1",
    }

    transformed = transform_customer_identity("SALESFORCE", record)

    assert transformed is not None
    assert transformed["company_name"] == "ACME INC"
    assert transformed["company_name_normalized"] == "ACME"
    assert transformed["email"] == "user@example.com"
    assert transformed["email_domain"] == "example.com"
    assert transformed["phone"] == "3125550101"
    assert transformed["address"] == "12 MAIN ST CHICAGO IL 60601 US"
    assert transformed["website_domain"] == "acme.com"
    assert transformed["record_hash"]


def test_transform_customer_metric_scores_product_usage() -> None:
    metric = transform_customer_metric(
        "PRODUCT_USAGE",
        {
            "customer_id": "001",
            "event_date": "2024-01-02",
            "login_count": "100",
            "active_days": "30",
            "active_users": "50",
        },
    )

    assert metric is not None
    assert metric["product_usage_score"] == 1.0
    assert metric["metric_date"] == "2024-01-02"


def test_transform_partner_profile_standardizes_impartner_record() -> None:
    partner = transform_partner_profile(
        {
            "partner_id": "p-1",
            "company_name": " Northwind LLC ",
            "email": "Partner@Example.com",
            "phone": "312.555.0101",
            "partner_tier": " gold ",
            "partner_region": " north america ",
            "certifications": '["implementation", "support"]',
        }
    )

    assert partner["company_name"] == "NORTHWIND LLC"
    assert partner["company_name_normalized"] == "NORTHWIND"
    assert partner["certification_count"] == 2
    assert partner["partner_region"] == "NORTH AMERICA"


def test_validator_builds_quality_report_for_invalid_email() -> None:
    validator = SilverRecordValidator()
    result = validator.validate_customer(
        {
            "source_system": "SALESFORCE",
            "source_customer_id": "001",
            "company_name": "ACME",
            "email": "not-an-email",
        }
    )
    report = validator.build_report([result])

    assert not result.is_valid
    assert report.invalid_records == 1
    assert any(metric.rule_name == "valid_email" for metric in report.metrics)


def test_quality_metrics_to_rows_are_analytics_ready() -> None:
    transformer = BronzeToSilverTransformer()
    transformed = transformer.transform_batch(
        "SALESFORCE",
        [
            {
                "customer_id": "001",
                "company_name": "Acme",
                "email": "user@example.com",
                "last_modified_timestamp": "2024-01-02T00:00:00",
            }
        ],
    )
    assert transformed.quality_report is not None

    rows = quality_metrics_to_rows(
        transformed.quality_report,
        run_id="run-1",
        source_system="SALESFORCE",
        table_name="silver_customer",
    )

    assert rows
    assert rows[0]["schema_name"] == "SILVER"
    assert rows[0]["source_system"] == "SALESFORCE"


def test_silver_pipeline_reads_transforms_merges_and_writes_quality_metrics() -> None:
    reader = FakeBronzeReader(
        [
            {
                "customer_id": "001",
                "company_name": "Acme",
                "email": "user@example.com",
                "last_modified_timestamp": "2024-01-02T00:00:00",
            }
        ]
    )
    writer = FakeSilverWriter()
    pipeline = SilverTransformationPipeline(
        mappings={
            "salesforce": SilverSourceMapping(
                "salesforce",
                "SALESFORCE",
                "bronze.salesforce",
            )
        },
        reader=reader,
        writer=writer,
    )

    result = pipeline.run_source("salesforce", since_watermark="2024-01-01T00:00:00")

    assert result.bronze_rows_read == 1
    assert result.customers_merged == 1
    assert result.quality_metrics_written >= 1
    assert writer.customers[0]["source_customer_id"] == "001"
    assert writer.quality
