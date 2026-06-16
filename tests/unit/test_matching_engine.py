from __future__ import annotations

from customer360.domain.customer import SourceCustomerRecord
from customer360.infrastructure.splink_engine import SplinkEntityResolutionEngine
from customer360.matching.clustering import MatchPrediction
from customer360.matching.scoring import MatchScoreCalculator
from customer360.matching.settings import SplinkSettingsBuilder


def test_splink_settings_include_required_blocking_and_comparison_rules() -> None:
    settings = SplinkSettingsBuilder().to_settings_dict()

    assert "l.email = r.email" in settings["blocking_rules_to_generate_predictions"]
    assert "l.phone = r.phone" in settings["blocking_rules_to_generate_predictions"]
    assert (
        "l.website_domain = r.website_domain"
        in settings["blocking_rules_to_generate_predictions"]
    )

    comparison_columns = {
        comparison["output_column_name"]
        for comparison in settings["comparisons"]
    }
    assert {"company_name", "email", "phone", "website_domain", "address"} <= comparison_columns


def test_match_score_calculates_probability_and_confidence() -> None:
    left = _record("SALESFORCE", "001", email="hello@example.com", company_name="ACME INC")
    right = _record("MARKETO", "m-1", email="hello@example.com", company_name="ACME INC")

    score = MatchScoreCalculator().score_pair(left, right)

    assert score.match_probability == 1.0
    assert score.confidence_score >= 0.95
    assert score.comparison_vector["email"] == 1.0
    assert score.blocking_rule == "l.email = r.email"


def test_engine_generates_gold_customer_clusters() -> None:
    records = [
        _record(
            "SALESFORCE",
            "001",
            email="hello@example.com",
            company_name="ACME INC",
            phone="3125550101",
            website_domain="acme.com",
            address="12 MAIN ST CHICAGO IL",
        ),
        _record(
            "MARKETO",
            "m-1",
            email="hello@example.com",
            company_name="ACME INC",
            phone="3125550101",
            website_domain="acme.com",
            address="12 MAIN ST CHICAGO IL",
        ),
        _record("SALESFORCE", "002", email="other@example.com", company_name="OTHER CO"),
    ]

    engine = SplinkEntityResolutionEngine()
    predictions = engine.predict_matches(records)
    clusters = engine.generate_clusters(records, predictions, load_batch_id="batch-1")

    assert len(predictions) == 1
    assert predictions[0].match_probability == 1.0
    assert len(clusters) == 2
    matched_cluster = next(cluster for cluster in clusters if cluster["cluster_size"] == 2)
    source_customer_ids = matched_cluster["source_customer_ids"]
    confidence_score = matched_cluster["confidence_score"]
    golden_customer_id = matched_cluster["golden_customer_id"]
    assert isinstance(source_customer_ids, list)
    assert isinstance(confidence_score, float)
    assert isinstance(golden_customer_id, str)
    assert set(source_customer_ids) == {"001", "m-1"}
    assert confidence_score >= 0.95
    assert matched_cluster["load_batch_id"] == "batch-1"
    assert golden_customer_id.startswith("gold_")


def test_prediction_serializes_to_gold_prediction_row() -> None:
    prediction = MatchPrediction(
        left_source_system="SALESFORCE",
        left_source_customer_id="001",
        right_source_system="MARKETO",
        right_source_customer_id="m-1",
        match_probability=0.99,
        confidence_score=0.98,
        comparison_vector={"email": 1.0},
        blocking_rule="l.email = r.email",
        model_version="splink_customer_matching_v1",
    )

    row = prediction.to_row(load_batch_id="batch-1")

    assert row["match_id"]
    assert row["comparison_vector"] == {"email": 1.0}
    assert row["load_batch_id"] == "batch-1"
    assert row["model_version"] == "splink_customer_matching_v1"


def _record(
    source_system: str,
    source_customer_id: str,
    *,
    company_name: str | None = None,
    email: str | None = None,
    phone: str | None = None,
    website_domain: str | None = None,
    address: str | None = None,
) -> SourceCustomerRecord:
    return SourceCustomerRecord(
        source_system=source_system,
        source_customer_id=source_customer_id,
        company_name=company_name,
        email=email,
        phone=phone,
        website_domain=website_domain,
        address=address,
    )
