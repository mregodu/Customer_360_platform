from customer360.classification.rules import classify_customer
from customer360.domain.customer import CustomerHealthClass


def test_classifies_healthy_customer() -> None:
    assert classify_customer(0.9, 0.8, 0.1) == CustomerHealthClass.HEALTHY


def test_classifies_churn_risk_customer() -> None:
    assert classify_customer(0.2, 0.8, 0.2) == CustomerHealthClass.CHURN_RISK


def test_classifies_at_risk_customer() -> None:
    assert classify_customer(0.6, 0.5, 0.4) == CustomerHealthClass.AT_RISK
