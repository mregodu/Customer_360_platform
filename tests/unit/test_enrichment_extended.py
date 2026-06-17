from __future__ import annotations

from datetime import date

from customer360.enrichment.pipeline import CustomerEnrichmentPipeline
from customer360.enrichment.scoring import (
    customer_lifetime_value,
    engagement_score,
    product_adoption_score,
    renewal_probability,
    support_health_score,
)


def test_product_adoption_score_ignores_missing_components_and_clamps_high_values() -> None:
    assert (
        product_adoption_score(
            product_usage_score=2.0,
            active_users=None,
            active_days=60,
            feature_utilization_score=None,
        )
        == 1.0
    )


def test_engagement_score_returns_zero_without_available_components() -> None:
    assert engagement_score(product_usage_score=None, marketing_engagement_score=None, support_activity_score=None) == 0.0


def test_support_health_score_penalizes_high_ticket_volume_and_slow_response() -> None:
    score = support_health_score(
        ticket_count=100,
        satisfaction_score=1,
        response_time_minutes=5000,
        support_activity_score=0.2,
    )

    assert score == 0.1


def test_renewal_probability_handles_unknown_and_expired_statuses() -> None:
    unknown = renewal_probability(
        engagement_score_value=0.5,
        product_adoption_score_value=0.5,
        support_health_score_value=0.5,
        renewal_status="waiting",
        license_expiration_date=date(2024, 1, 1),
        as_of_date=date(2024, 2, 1),
    )
    churned = renewal_probability(
        engagement_score_value=0.5,
        product_adoption_score_value=0.5,
        support_health_score_value=0.5,
        renewal_status="cancelled",
        license_expiration_date=None,
        as_of_date=date(2024, 2, 1),
    )

    assert unknown == 0.5
    assert churned == 0.3737


def test_customer_lifetime_value_clamps_negative_inputs() -> None:
    assert (
        customer_lifetime_value(
            contract_value=-100,
            renewal_probability_value=2.0,
            engagement_score_value=-1.0,
            product_adoption_score_value=1.5,
        )
        == 0.0
    )


def test_enrichment_pipeline_rolls_up_multiple_metric_dates_separately() -> None:
    rows = CustomerEnrichmentPipeline().generate_metrics(
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
                "product_usage_score": 0.4,
                "contract_value": 1000,
            },
            {
                "source_system": "PRODUCT_USAGE",
                "source_customer_id": "001",
                "metric_date": "2024-04-02",
                "product_usage_score": 0.8,
                "contract_value": 2000,
            },
        ],
    )

    assert [row["metric_date"] for row in rows] == ["2024-04-01", "2024-04-02"]
    assert rows[0]["product_usage_score"] == 0.4
    assert rows[1]["product_usage_score"] == 0.8


def test_enrichment_pipeline_supports_legacy_single_source_cluster_shape() -> None:
    rows = CustomerEnrichmentPipeline().generate_metrics(
        [
            {
                "golden_customer_id": "gold-legacy",
                "source_systems": ["PRODUCT_USAGE"],
                "source_customer_ids": ["001"],
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

    assert len(rows) == 1
    assert rows[0]["golden_customer_id"] == "gold-legacy"
