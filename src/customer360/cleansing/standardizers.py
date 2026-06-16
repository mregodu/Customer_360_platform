"""Reusable standardization functions for silver-layer transformations."""

from __future__ import annotations

import re
from urllib.parse import urlparse

_ADDRESS_ABBREVIATIONS = {
    "STREET": "ST",
    "ST.": "ST",
    "ROAD": "RD",
    "RD.": "RD",
    "AVENUE": "AVE",
    "AVE.": "AVE",
    "BOULEVARD": "BLVD",
    "BLVD.": "BLVD",
    "DRIVE": "DR",
    "DR.": "DR",
    "LANE": "LN",
    "LN.": "LN",
    "COURT": "CT",
    "CT.": "CT",
    "SUITE": "STE",
    "STE.": "STE",
    "APARTMENT": "APT",
    "APT.": "APT",
}

_STATE_ABBREVIATIONS = {
    "ALABAMA": "AL",
    "ALASKA": "AK",
    "ARIZONA": "AZ",
    "ARKANSAS": "AR",
    "CALIFORNIA": "CA",
    "COLORADO": "CO",
    "CONNECTICUT": "CT",
    "DELAWARE": "DE",
    "FLORIDA": "FL",
    "GEORGIA": "GA",
    "HAWAII": "HI",
    "IDAHO": "ID",
    "ILLINOIS": "IL",
    "INDIANA": "IN",
    "IOWA": "IA",
    "KANSAS": "KS",
    "KENTUCKY": "KY",
    "LOUISIANA": "LA",
    "MAINE": "ME",
    "MARYLAND": "MD",
    "MASSACHUSETTS": "MA",
    "MICHIGAN": "MI",
    "MINNESOTA": "MN",
    "MISSISSIPPI": "MS",
    "MISSOURI": "MO",
    "MONTANA": "MT",
    "NEBRASKA": "NE",
    "NEVADA": "NV",
    "NEW HAMPSHIRE": "NH",
    "NEW JERSEY": "NJ",
    "NEW MEXICO": "NM",
    "NEW YORK": "NY",
    "NORTH CAROLINA": "NC",
    "NORTH DAKOTA": "ND",
    "OHIO": "OH",
    "OKLAHOMA": "OK",
    "OREGON": "OR",
    "PENNSYLVANIA": "PA",
    "RHODE ISLAND": "RI",
    "SOUTH CAROLINA": "SC",
    "SOUTH DAKOTA": "SD",
    "TENNESSEE": "TN",
    "TEXAS": "TX",
    "UTAH": "UT",
    "VERMONT": "VT",
    "VIRGINIA": "VA",
    "WASHINGTON": "WA",
    "WEST VIRGINIA": "WV",
    "WISCONSIN": "WI",
    "WYOMING": "WY",
}

_LEGAL_SUFFIXES = {
    "CO",
    "COMPANY",
    "CORP",
    "CORPORATION",
    "INC",
    "INCORPORATED",
    "LLC",
    "LTD",
    "LIMITED",
    "PLC",
}


def null_if_blank(value: object) -> str | None:
    """Return a stripped string or None for blank-like values."""
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if text.upper() in {"NULL", "NONE", "N/A", "NA"}:
        return None
    return text


def normalize_whitespace(value: object) -> str | None:
    """Collapse repeated whitespace in string-like values."""
    text = null_if_blank(value)
    return " ".join(text.split()) if text is not None else None


def standardize_name(value: object) -> str | None:
    """Normalize person names for deterministic comparisons."""
    text = normalize_whitespace(value)
    if text is None:
        return None
    return re.sub(r"[^A-Z0-9 '\-]", "", text.upper())


def standardize_company_name(value: object) -> str | None:
    """Normalize company names for deterministic matching and reporting."""
    text = normalize_whitespace(value)
    if text is None:
        return None
    cleaned = re.sub(r"[^\w& ]", " ", text.upper())
    return " ".join(cleaned.split())


def normalize_company_name(value: object) -> str | None:
    """Create a legal-suffix-free company key for fuzzy matching."""
    company_name = standardize_company_name(value)
    if company_name is None:
        return None
    tokens = [token for token in company_name.split() if token not in _LEGAL_SUFFIXES]
    return " ".join(tokens) or company_name


def standardize_email(value: object) -> str | None:
    """Normalize email values by trimming whitespace and lowercasing."""
    text = null_if_blank(value)
    if text is None:
        return None
    return text.lower()


def extract_email_domain(value: object) -> str | None:
    """Return the domain component of a standardized email value."""
    email = standardize_email(value)
    if email is None or "@" not in email:
        return None
    return email.rsplit("@", 1)[1]


def normalize_phone(value: object) -> str | None:
    """Normalize phone numbers to digits only for matching."""
    text = null_if_blank(value)
    if text is None:
        return None
    digits = re.sub(r"\D", "", text)
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    return digits or None


def standardize_address(value: object) -> str | None:
    """Uppercase addresses and standardize common suffix abbreviations."""
    text = normalize_whitespace(value)
    if text is None:
        return None
    cleaned = re.sub(r"[#,]", " ", text.upper())
    tokens = " ".join(cleaned.split()).split(" ")
    return " ".join(_ADDRESS_ABBREVIATIONS.get(token, token) for token in tokens)


def standardize_city(value: object) -> str | None:
    """Normalize city values for reporting and matching."""
    return standardize_name(value)


def standardize_state(value: object) -> str | None:
    """Normalize US state names to two-letter abbreviations when possible."""
    text = standardize_name(value)
    if text is None:
        return None
    if len(text) == 2:
        return text
    return _STATE_ABBREVIATIONS.get(text, text)


def standardize_postal_code(value: object) -> str | None:
    """Normalize postal codes while preserving non-US alphanumeric formats."""
    text = null_if_blank(value)
    if text is None:
        return None
    return re.sub(r"[^A-Z0-9]", "", text.upper())


def standardize_country(value: object) -> str | None:
    """Normalize country names and common aliases."""
    text = standardize_name(value)
    if text is None:
        return None
    if text in {"US", "USA", "UNITED STATES", "UNITED STATES OF AMERICA"}:
        return "US"
    if text in {"UK", "UNITED KINGDOM", "GREAT BRITAIN"}:
        return "GB"
    return text


def normalize_website_domain(value: object) -> str | None:
    """Extract a lowercased website domain from a URL or raw domain."""
    text = null_if_blank(value)
    if text is None:
        return None
    candidate = text.lower()
    parsed = urlparse(candidate if "://" in candidate else f"https://{candidate}")
    domain = parsed.netloc or parsed.path
    domain = domain.split("/", 1)[0].split(":", 1)[0]
    if domain.startswith("www."):
        domain = domain[4:]
    return domain or None


def combine_address(
    address_line_1: object,
    city: object = None,
    state_region: object = None,
    postal_code: object = None,
    country: object = None,
) -> str | None:
    """Build a standardized single-line address from address components."""
    parts = [
        standardize_address(address_line_1),
        standardize_city(city),
        standardize_state(state_region),
        standardize_postal_code(postal_code),
        standardize_country(country),
    ]
    present = [part for part in parts if part]
    return " ".join(present) if present else None
