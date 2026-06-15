"""Factory helpers for assembling ingestion services from configuration."""

from __future__ import annotations

from customer360.config import Customer360Config
from customer360.infrastructure.snowflake import SnowflakeBronzeLoader, SnowflakeWatermarkStore
from customer360.ingestion.retry import RetryPolicy
from customer360.ingestion.service import IngestionService
from customer360.ingestion.sources import build_source_extractor


def build_ingestion_service(settings: Customer360Config) -> IngestionService:
    """Build a production ingestion service from validated application settings."""
    sources = {
        name: build_source_extractor(name, source_config)
        for name, source_config in settings.ingestion.sources.items()
        if source_config.enabled
    }
    loader = SnowflakeBronzeLoader(settings.snowflake.connection_parameters())
    watermarks = SnowflakeWatermarkStore(settings.snowflake.connection_parameters())
    return IngestionService(
        source_configs=settings.ingestion.sources,
        sources=sources,
        loader=loader,
        watermarks=watermarks,
        retry_policy=RetryPolicy.from_config(settings.ingestion.retry),
        default_batch_size=settings.ingestion.default_batch_size,
    )
