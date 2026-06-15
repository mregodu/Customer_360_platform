"""Baseline explainable customer health classification rules.

Machine-learning models can replace or augment these rules later, but this gives
analytics a deterministic first production contract.
"""

from __future__ import annotations

from customer360.domain.customer import CustomerHealthClass


def classify_customer(engagement: float, adoption: float, support_risk: float) -> CustomerHealthClass:
    """Classify a customer using normalized scores from 0 to 1.

    `support_risk` is higher when support trends are negative.
    """
    if engagement >= 0.75 and adoption >= 0.75 and support_risk <= 0.25:
        return CustomerHealthClass.HEALTHY
    if engagement < 0.35 or adoption < 0.35 or support_risk >= 0.75:
        return CustomerHealthClass.CHURN_RISK
    return CustomerHealthClass.AT_RISK
