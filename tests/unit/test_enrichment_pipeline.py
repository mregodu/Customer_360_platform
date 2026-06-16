from __future__ import annotations

from collections.abc import Iterable, Mapping

from customer360.enrichment.pipeline import CustomerEnrichmentPipeline
from customer360.enrichment.scoring import (
    EnrichmentScoreCalculator,
    customer_lifetime_value,
    support_health_score,
)


class FakeCustomerEnrichmentWriter:
    def __init__(self) -> None:
        self.records: list[dict[str, object]] = []

    def write_customer_enrichment_metrics(self, records: Iterable[Mapping[str, object]]) -> int:
        rows = [dict(record) for record in records]
        self.records.extend(rows)
        return len(rows)


def test_enrichment_score_calculator_generates_required_metrics() -> None:
    scores = EnrichmentScoreCalculator().score(
        {
            "metric_date": "2024-04-01",
            "product_usage_score": 0.8,
            "marketing_engagement_score": 0.6,
            "support_activity_score": 0.7,
            "support_ticket_count": 5,
            "satisfaction_score": 4,
            "response_time_minutes": 120,
            "active_users": 25,
            "active_days": 20,
            "feature_utilization_score": 0.6667,
            "renewal_status": "ACTIVE",
            "license_expiration_date": "2024-10-01",
            "contract_value": 1000,
        }
    )

    assert scores.product_adoption_score == 0.7017
    assert scores.engagement_score == 0.705
    assert scores.support_health_score == 0.8083
    assert scores.renewal_probability == 0.8057
    assert scores.lifetime_value > 2400


def test_customer_enrichment_pipeline_rolls_up_clustered_metrics() -> None:
    pipeline = CustomerEnrichmentPipeline()

    rows = pipeline.generate_metrics(
        [
            {
                "golden_customer_id": "gold-1",
                "source_members": [
                    {"source_system": "PRODUCT_USAGE", "source_customer_id": "001"},
                    {"source_system": "MARKETO", "source_customer_id": "m-1"},
                    {"source_system": "ZENDESK", "source_customer_id": "z-1"},
                    {"source_system": "LICENSING", "source_customer_id": "l-1"},
                ],
            }
        ],
        [
            {
                "source_system": "PRODUCT_USAGE",
                "source_customer_id": "001",
                "metric_date": "2024-04-01",
                "product_usage_score": 0.8,
                "active_users": 25,
                "active_days": 20,
                "feature_usage": {"exports": True, "dashboards": False, "api": True},
            },
            {
                "source_system": "MARKETO",
                "source_customer_id": "m-1",
                "metric_date": "2024-04-01",
                "marketing_engagement_score": 0.6,
            },
            {
                "source_system": "ZENDESK",
                "source_customer_id": "z-1",
                "metric_date": "2024-04-01",
                "support_activity_score": 0.7,
                "ticket_count": 5,
                "satisfaction_score": 4,
                "response_time_minutes": 120,
            },
            {
                "source_system": "LICENSING",
                "source_customer_id": "l-1",
                "metric_date": "2024-04-01",
                "renewal_status": "ACTIVE",
                "license_expiration_date": "2024-10-01",
                "contract_value": 1000,
                "seat_count": 50,
                "load_batch_id": "batch-source",
            },
            {
                "source_system": "PRODUCT_USAGE",
                "source_customer_id": "unmatched",
                "metric_date": "2024-04-01",
                "product_usage_score": 1.0,
            },
        ],
        load_batch_id="batch-1",
    )

    assert len(rows) == 1
    row = rows[0]
    lifetime_value = row["lifetime_value"]
    metric_components = row["metric_components"]
    assert isinstance(lifetime_value, int | float)
    assert isinstance(metric_components, Mapping)
    assert row["golden_customer_id"] == "gold-1"
    assert row["metric_date"] == "2024-04-01"
    assert lifetime_value > 2400
    assert row["product_adoption_score"] == 0.7017
    assert row["engagement_score"] == 0.705
    assert row["support_health_score"] == 0.8083
    assert row["renewal_probability"] == 0.8057
    assert row["support_ticket_count"] == 5.0
    assert row["seat_count"] == 50.0
    assert row["load_batch_id"] == "batch-1"
    assert row["model_version"] == "customer_enrichment_v1"
    assert metric_components["source_metric_count"] == 4


def test_customer_enrichment_pipeline_writes_generated_rows() -> None:
    writer = FakeCustomerEnrichmentWriter()
    pipeline = CustomerEnrichmentPipeline(writer=writer)

    result = pipeline.generate_and_write(
        [
            {
                "golden_customer_id": "gold-1",
                "source_members": [{"source_system": "PRODUCT_USAGE", "source_customer_id": "001"}],
            }
        ],
        [
            {
                "source_system": "PRODUCT_USAGE",
                "source_customer_id": "001",
                "metric_date": "2024-04-01",
                "product_usage_score": 0.8,
            }
        ],
    )

    assert result.enrichment_rows_generated == 1
    assert result.enrichment_rows_written == 1
    assert writer.records[0]["golden_customer_id"] == "gold-1"


def test_support_health_defaults_to_healthy_when_support_signals_are_absent() -> None:
    assert support_health_score(
        ticket_count=None,
        satisfaction_score=None,
        response_time_minutes=None,
        support_activity_score=None,
    ) == 1.0


def test_customer_lifetime_value_returns_zero_without_contract_value() -> None:
    assert (
        customer_lifetime_value(
            contract_value=None,
            renewal_probability_value=0.9,
            engagement_score_value=0.8,
            product_adoption_score_value=0.7,
        )
        == 0.0
    )
