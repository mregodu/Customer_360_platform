"""Splink settings builder for Customer 360 entity resolution."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from customer360.config import SplinkComparisonConfig, SplinkConfig

DEFAULT_MODEL_VERSION = "splink_customer_matching_v1"


@dataclass(frozen=True)
class MatchingField:
    """One matching field and its scoring behavior."""

    column: str
    method: str
    weight: float
    threshold: float | None = None


DEFAULT_MATCHING_FIELDS = (
    MatchingField("company_name", "jaro_winkler", 0.20, 0.92),
    MatchingField("email", "exact", 0.35),
    MatchingField("phone", "exact", 0.25),
    MatchingField("website_domain", "exact", 0.10),
    MatchingField("address", "levenshtein", 0.10, 0.88),
)

DEFAULT_BLOCKING_RULES = (
    "l.email = r.email",
    "l.phone = r.phone",
    "l.website_domain = r.website_domain",
    "l.company_name = r.company_name",
    "l.address = r.address",
)


class SplinkSettingsBuilder:
    """Builds production Splink settings for customer matching."""

    def __init__(
        self,
        *,
        link_type: str = "link_and_dedupe",
        unique_id_column: str = "source_customer_id",
        source_dataset_column: str = "source_system",
        blocking_rules: tuple[str, ...] = DEFAULT_BLOCKING_RULES,
        matching_fields: tuple[MatchingField, ...] = DEFAULT_MATCHING_FIELDS,
        retain_matching_columns: bool = True,
        retain_intermediate_calculation_columns: bool = True,
        model_version: str = DEFAULT_MODEL_VERSION,
    ) -> None:
        self.link_type = link_type
        self.unique_id_column = unique_id_column
        self.source_dataset_column = source_dataset_column
        self.blocking_rules = blocking_rules
        self.matching_fields = matching_fields
        self.retain_matching_columns = retain_matching_columns
        self.retain_intermediate_calculation_columns = retain_intermediate_calculation_columns
        self.model_version = model_version

    @classmethod
    def from_config(cls, config: SplinkConfig) -> SplinkSettingsBuilder:
        """Build a settings builder from validated platform configuration."""
        configured_fields = tuple(_field_from_config(item) for item in config.comparisons)
        return cls(
            link_type=config.link_type,
            unique_id_column=config.unique_id_column,
            source_dataset_column=config.source_dataset_column,
            blocking_rules=tuple(config.blocking_rules),
            matching_fields=configured_fields or DEFAULT_MATCHING_FIELDS,
            retain_matching_columns=config.retain_matching_columns,
            model_version=DEFAULT_MODEL_VERSION,
        )

    def to_settings_dict(self) -> dict[str, Any]:
        """Return a Splink settings dictionary suitable for `Linker` construction."""
        return {
            "link_type": self.link_type,
            "unique_id_column_name": self.unique_id_column,
            "source_dataset_column_name": self.source_dataset_column,
            "blocking_rules_to_generate_predictions": list(self.blocking_rules),
            "comparisons": [_comparison_dict(field) for field in self.matching_fields],
            "retain_matching_columns": self.retain_matching_columns,
            "retain_intermediate_calculation_columns": (
                self.retain_intermediate_calculation_columns
            ),
            "em_convergence": 0.001,
            "max_iterations": 20,
            "sql_dialect": "snowflake",
        }


def _field_from_config(config: SplinkComparisonConfig) -> MatchingField:
    weights = {
        "email": 0.35,
        "phone": 0.25,
        "company_name": 0.20,
        "website_domain": 0.10,
        "website": 0.10,
        "address": 0.10,
    }
    column = "website_domain" if config.column == "website" else config.column
    return MatchingField(
        column=column,
        method=config.method,
        threshold=config.threshold,
        weight=weights.get(column, 0.10),
    )


def _comparison_dict(field: MatchingField) -> dict[str, Any]:
    if field.method == "exact":
        levels = [
            {
                "sql_condition": f"{field.column}_l is null or {field.column}_r is null",
                "label_for_charts": f"{field.column} missing",
                "is_null_level": True,
            },
            {
                "sql_condition": f"{field.column}_l = {field.column}_r",
                "label_for_charts": f"Exact {field.column}",
                "m_probability": 0.95,
                "u_probability": 0.01,
            },
            {"sql_condition": "else", "label_for_charts": f"Different {field.column}"},
        ]
    elif field.method == "levenshtein":
        threshold = field.threshold or 0.88
        levels = [
            {
                "sql_condition": f"{field.column}_l is null or {field.column}_r is null",
                "label_for_charts": f"{field.column} missing",
                "is_null_level": True,
            },
            {
                "sql_condition": (
                    f"1 - editdistance({field.column}_l, {field.column}_r) / "
                    f"greatest(length({field.column}_l), length({field.column}_r)) >= {threshold}"
                ),
                "label_for_charts": f"Levenshtein {field.column} >= {threshold}",
                "m_probability": 0.90,
                "u_probability": 0.05,
            },
            {"sql_condition": "else", "label_for_charts": f"Different {field.column}"},
        ]
    else:
        threshold = field.threshold or 0.92
        levels = [
            {
                "sql_condition": f"{field.column}_l is null or {field.column}_r is null",
                "label_for_charts": f"{field.column} missing",
                "is_null_level": True,
            },
            {
                "sql_condition": (
                    f"jaro_winkler_similarity({field.column}_l, {field.column}_r) "
                    f">= {threshold}"
                ),
                "label_for_charts": f"Jaro-Winkler {field.column} >= {threshold}",
                "m_probability": 0.90,
                "u_probability": 0.05,
            },
            {"sql_condition": "else", "label_for_charts": f"Different {field.column}"},
        ]

    return {
        "output_column_name": field.column,
        "comparison_description": f"{field.method} comparison for {field.column}",
        "comparison_levels": levels,
    }
