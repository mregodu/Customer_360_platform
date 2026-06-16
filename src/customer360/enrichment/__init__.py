"""Enrichment module for CLV, engagement, adoption, support, and renewal metrics."""

from customer360.enrichment.pipeline import (
    CustomerEnrichmentPipeline,
    CustomerEnrichmentPipelineResult,
    CustomerEnrichmentWriter,
)
from customer360.enrichment.scoring import (
    ENRICHMENT_MODEL_VERSION,
    EnrichmentScoreCalculator,
    EnrichmentScores,
    customer_lifetime_value,
    engagement_score,
    product_adoption_score,
    renewal_probability,
    support_health_score,
)

__all__ = [
    "ENRICHMENT_MODEL_VERSION",
    "CustomerEnrichmentPipeline",
    "CustomerEnrichmentPipelineResult",
    "CustomerEnrichmentWriter",
    "EnrichmentScoreCalculator",
    "EnrichmentScores",
    "customer_lifetime_value",
    "engagement_score",
    "product_adoption_score",
    "renewal_probability",
    "support_health_score",
]
