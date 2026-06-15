"""Domain models for customer identity and enrichment.

This module intentionally avoids Snowflake, Airflow, dbt, Splink, and Domo imports.
Keeping domain objects dependency-free makes them easy to test and reuse.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum


class CustomerHealthClass(StrEnum):
    """Allowed customer health classes for downstream reporting."""

    HEALTHY = "Healthy"
    AT_RISK = "At Risk"
    CHURN_RISK = "Churn Risk"


@dataclass(frozen=True)
class SourceCustomerRecord:
    """Customer-like record received from a source business system."""

    source_system: str
    source_customer_id: str
    company_name: str | None = None
    email: str | None = None
    phone: str | None = None
    address: str | None = None
    website_domain: str | None = None
    last_modified_timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(frozen=True)
class GoldenCustomerRecord:
    """Resolved trusted customer profile used as the Customer 360 golden record."""

    golden_customer_id: str
    source_customer_ids: tuple[str, ...]
    company_name: str
    email: str | None
    phone: str | None
    address: str | None
    confidence_score: float

    def is_high_confidence(self, threshold: float = 0.95) -> bool:
        """Return whether this record meets the enterprise matching threshold."""
        return self.confidence_score >= threshold


@dataclass(frozen=True)
class CustomerHealthScore:
    """Derived customer health metrics consumed by analytics and Domo."""

    golden_customer_id: str
    lifetime_value: float
    engagement_score: float
    adoption_score: float
    renewal_probability: float
    health_class: CustomerHealthClass
