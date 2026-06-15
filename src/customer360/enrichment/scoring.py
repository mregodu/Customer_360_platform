"""Customer enrichment scoring formulas."""

from __future__ import annotations


def engagement_score(product_usage: float, marketing_engagement: float, support_activity: float) -> float:
    """Calculate weighted engagement score from product, marketing, and support signals."""
    return (0.4 * product_usage) + (0.3 * marketing_engagement) + (0.3 * support_activity)


def adoption_score(feature_utilization: float, active_users: float, login_frequency: float) -> float:
    """Calculate simple normalized adoption score from usage behavior."""
    return (feature_utilization + active_users + login_frequency) / 3
