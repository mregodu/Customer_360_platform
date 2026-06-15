"""Reusable standardization functions for silver-layer transformations."""

from __future__ import annotations

import re

_ADDRESS_ABBREVIATIONS = {
    "STREET": "ST",
    "ROAD": "RD",
    "AVENUE": "AVE",
}


def standardize_company_name(value: str | None) -> str | None:
    """Normalize company names for deterministic matching and reporting."""
    return " ".join(value.upper().split()) if value else None


def standardize_email(value: str | None) -> str | None:
    """Normalize email values by trimming whitespace and lowercasing."""
    return value.strip().lower() if value else None


def normalize_phone(value: str | None) -> str | None:
    """Normalize phone numbers to digits only for matching."""
    if not value:
        return None
    digits = re.sub(r"\D", "", value)
    return digits or None


def standardize_address(value: str | None) -> str | None:
    """Uppercase addresses and standardize common suffix abbreviations."""
    if not value:
        return None
    tokens = " ".join(value.upper().split()).split(" ")
    return " ".join(_ADDRESS_ABBREVIATIONS.get(token, token) for token in tokens)
