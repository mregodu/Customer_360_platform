from __future__ import annotations

from collections.abc import Callable

from customer360.domain.customer import SourceCustomerRecord
from customer360.infrastructure.splink_engine import SplinkEntityResolutionEngine
from customer360.matching.clustering import CustomerClusterGenerator, MatchPrediction
from customer360.matching.scoring import MatchScoreCalculator


def test_match_score_does_not_match_when_only_weak_company_similarity_exists(
    source_customer_factory: Callable[..., SourceCustomerRecord],
) -> None:
    left = source_customer_factory(company_name="ACME SOFTWARE", email=None, phone=None, website_domain=None)
    right = source_customer_factory(
        "MARKETO",
        "m-1",
        company_name="ACME HARDWARE",
        email=None,
        phone=None,
        website_domain=None,
        address=None,
    )

    score = MatchScoreCalculator(match_threshold=0.95).score_pair(left, right)

    assert score.match_probability < 0.95
    assert not MatchScoreCalculator(match_threshold=0.95).is_match(score)
    assert score.blocking_rule is None


def test_match_score_uses_levenshtein_similarity_for_address(
    source_customer_factory: Callable[..., SourceCustomerRecord],
) -> None:
    left = source_customer_factory(email=None, phone=None, company_name=None, website_domain=None, address="12 MAIN STREET")
    right = source_customer_factory(
        "ZENDESK",
        "z-1",
        email=None,
        phone=None,
        company_name=None,
        website_domain=None,
        address="12 MAIN ST",
    )

    score = MatchScoreCalculator().score_pair(left, right)

    address_score = score.comparison_vector["address"]
    assert address_score is not None
    assert 0.65 < address_score < 1.0
    assert score.matched_fields == ()


def test_splink_engine_only_generates_candidate_pairs_for_blocked_records(
    source_customer_factory: Callable[..., SourceCustomerRecord],
) -> None:
    records = [
        source_customer_factory(
            "SALESFORCE",
            "001",
            company_name=None,
            email="same@example.com",
            phone=None,
            website_domain=None,
            address=None,
        ),
        source_customer_factory(
            "MARKETO",
            "m-1",
            company_name=None,
            email="same@example.com",
            phone=None,
            website_domain=None,
            address=None,
        ),
        source_customer_factory(
            "ZENDESK",
            "z-1",
            company_name=None,
            email="unique@example.com",
            phone="9999999999",
            website_domain=None,
            address=None,
        ),
    ]

    predictions = SplinkEntityResolutionEngine().predict_matches(records)

    assert len(predictions) == 1
    assert predictions[0].left_source_customer_id == "001"
    assert predictions[0].right_source_customer_id == "m-1"


def test_cluster_generator_can_exclude_singletons(
    source_customer_factory: Callable[..., SourceCustomerRecord],
) -> None:
    records = [
        source_customer_factory("SALESFORCE", "001"),
        source_customer_factory("MARKETO", "m-1"),
        source_customer_factory("ZENDESK", "z-1", email="other@example.com"),
    ]
    prediction = MatchPrediction(
        left_source_system="SALESFORCE",
        left_source_customer_id="001",
        right_source_system="MARKETO",
        right_source_customer_id="m-1",
        match_probability=0.99,
        confidence_score=0.98,
        comparison_vector={"email": 1.0},
        blocking_rule="l.email = r.email",
        model_version="test",
    )

    clusters = CustomerClusterGenerator(threshold=0.95, include_singletons=False).generate(
        records,
        [prediction],
        load_batch_id="batch-1",
    )

    assert len(clusters) == 1
    assert clusters[0]["cluster_size"] == 2
    assert clusters[0]["load_batch_id"] == "batch-1"


def test_predictions_below_cluster_threshold_do_not_merge_records(
    source_customer_factory: Callable[..., SourceCustomerRecord],
) -> None:
    records = [
        source_customer_factory("SALESFORCE", "001"),
        source_customer_factory("MARKETO", "m-1"),
    ]
    prediction = MatchPrediction(
        left_source_system="SALESFORCE",
        left_source_customer_id="001",
        right_source_system="MARKETO",
        right_source_customer_id="m-1",
        match_probability=0.80,
        confidence_score=0.80,
        comparison_vector={"email": 1.0},
        blocking_rule="l.email = r.email",
        model_version="test",
    )

    clusters = CustomerClusterGenerator(threshold=0.95, include_singletons=True).generate(records, [prediction])

    assert len(clusters) == 2
    assert all(cluster["cluster_size"] == 1 for cluster in clusters)
