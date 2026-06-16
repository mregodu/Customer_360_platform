from __future__ import annotations

from collections.abc import Iterable, Mapping

from customer360.golden.service import GoldenRecordService
from customer360.golden.survivorship import GoldenRecordGenerator


class FakeGoldenRecordWriter:
    def __init__(self) -> None:
        self.records: list[dict[str, object]] = []

    def write_golden_records(self, records: Iterable[Mapping[str, object]]) -> int:
        rows = [dict(record) for record in records]
        self.records.extend(rows)
        return len(rows)


def test_golden_record_generator_applies_survivorship_rules() -> None:
    generator = GoldenRecordGenerator()

    records = generator.generate(
        [
            {
                "cluster_id": "cluster-1",
                "golden_customer_id": "gold-1",
                "source_members": [
                    {"source_system": "SALESFORCE", "source_customer_id": "001"},
                    {"source_system": "MARKETO", "source_customer_id": "m-1"},
                ],
                "source_customer_ids": ["001", "m-1"],
                "source_systems": ["MARKETO", "SALESFORCE"],
                "representative_source_system": "SALESFORCE",
                "representative_source_customer_id": "001",
                "confidence_score": 0.98,
            }
        ],
        [
            {
                "source_system": "SALESFORCE",
                "source_customer_id": "001",
                "company_name": "ACME INC",
                "email": "",
                "phone": "123",
                "address_line_1": "12 MAIN ST",
                "city": "CHICAGO",
                "state_region": "IL",
                "postal_code": "60601",
                "country": "US",
                "address": "12 MAIN ST CHICAGO IL 60601 US",
                "website_domain": "www.acme.com",
                "industry": "SOFTWARE",
                "customer_status": "ACTIVE",
                "created_date": "2024-01-01T00:00:00+00:00",
                "last_modified_timestamp": "2024-01-02T00:00:00+00:00",
                "source_priority": 10,
                "completeness_score": 0.75,
                "data_quality_score": 0.80,
            },
            {
                "source_system": "MARKETO",
                "source_customer_id": "m-1",
                "company_name": "ACME CORPORATION",
                "email": "hello@example.com",
                "phone": "+1 (312) 555-0101",
                "address": "",
                "website_domain": "https://acme.com/products",
                "created_date": "2024-01-03T00:00:00+00:00",
                "last_modified_timestamp": "2024-02-01T00:00:00+00:00",
                "source_priority": 20,
                "completeness_score": 1.0,
                "data_quality_score": 1.0,
            },
        ],
        load_batch_id="batch-1",
    )

    assert len(records) == 1
    record = records[0]
    survivorship_rules = record["survivorship_rules"]

    assert record["golden_customer_id"] == "gold-1"
    assert record["company_name"] == "ACME INC"
    assert record["email"] == "hello@example.com"
    assert record["phone"] == "3125550101"
    assert record["address"] == "12 MAIN ST CHICAGO IL 60601 US"
    assert record["website_domain"] == "acme.com"
    assert record["primary_source_system"] == "SALESFORCE"
    assert record["primary_source_customer_id"] == "001"
    assert record["confidence_score"] == 0.98
    assert record["completeness_score"] == 1.0
    assert record["load_batch_id"] == "batch-1"
    assert isinstance(survivorship_rules, dict)
    assert survivorship_rules["email"]["source_system"] == "MARKETO"
    assert survivorship_rules["address"]["source_system"] == "SALESFORCE"


def test_golden_record_service_generates_and_writes_records() -> None:
    writer = FakeGoldenRecordWriter()
    service = GoldenRecordService(writer=writer)

    written = service.generate_and_write(
        [
            {
                "cluster_id": "cluster-1",
                "golden_customer_id": "gold-1",
                "source_members": [
                    {"source_system": "SALESFORCE", "source_customer_id": "001"}
                ],
                "source_customer_ids": ["001"],
                "source_systems": ["SALESFORCE"],
                "confidence_score": 1.0,
            }
        ],
        [
            {
                "source_system": "SALESFORCE",
                "source_customer_id": "001",
                "company_name": "ACME",
                "email": "hello@example.com",
                "phone": "3125550101",
                "address": "12 MAIN ST CHICAGO IL 60601 US",
                "source_priority": 10,
                "completeness_score": 1.0,
                "data_quality_score": 1.0,
            }
        ],
    )

    assert written == 1
    assert writer.records[0]["golden_customer_id"] == "gold-1"
