from customer360.cleansing.standardizers import (
    normalize_phone,
    standardize_address,
    standardize_company_name,
    standardize_email,
)


def test_standardize_company_name() -> None:
    assert standardize_company_name("  Acme   Corp ") == "ACME CORP"


def test_standardize_email() -> None:
    assert standardize_email("  USER@Example.COM ") == "user@example.com"


def test_normalize_phone() -> None:
    assert normalize_phone("(312) 555-0101") == "3125550101"


def test_standardize_address() -> None:
    assert standardize_address("12 main street") == "12 MAIN ST"
