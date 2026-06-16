from customer360.cleansing.standardizers import (
    combine_address,
    extract_email_domain,
    normalize_phone,
    normalize_website_domain,
    standardize_address,
    standardize_city,
    standardize_company_name,
    standardize_country,
    standardize_email,
    standardize_name,
    standardize_postal_code,
    standardize_state,
)


def test_standardize_company_name() -> None:
    assert standardize_company_name("  Acme   Corp ") == "ACME CORP"


def test_standardize_email() -> None:
    assert standardize_email("  USER@Example.COM ") == "user@example.com"


def test_normalize_phone() -> None:
    assert normalize_phone("(312) 555-0101") == "3125550101"


def test_standardize_address() -> None:
    assert standardize_address("12 main street") == "12 MAIN ST"


def test_standardize_name() -> None:
    assert standardize_name("  Jane   O'Neil, Jr. ") == "JANE O'NEIL JR"


def test_extract_email_domain() -> None:
    assert extract_email_domain("  person@Example.COM ") == "example.com"


def test_normalize_phone_removes_us_country_code() -> None:
    assert normalize_phone("+1 (312) 555-0101") == "3125550101"


def test_standardize_address_components() -> None:
    assert standardize_city("  chicago ") == "CHICAGO"
    assert standardize_state("Illinois") == "IL"
    assert standardize_postal_code("60601-1234") == "606011234"
    assert standardize_country("United States") == "US"


def test_normalize_website_domain() -> None:
    assert normalize_website_domain("https://www.Example.com/path") == "example.com"


def test_combine_address() -> None:
    assert combine_address("12 main street", "Chicago", "Illinois", "60601", "USA") == (
        "12 MAIN ST CHICAGO IL 60601 US"
    )
