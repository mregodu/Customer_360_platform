"""Match scoring and confidence calculation for customer entity resolution."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from difflib import SequenceMatcher

from customer360.domain.customer import SourceCustomerRecord
from customer360.matching.settings import DEFAULT_MATCHING_FIELDS, MatchingField


@dataclass(frozen=True)
class FieldComparison:
    """Score for one matched field."""

    field_name: str
    method: str
    score: float | None
    weight: float
    matched: bool


@dataclass(frozen=True)
class MatchScore:
    """Pairwise match score and explainability payload."""

    match_probability: float
    confidence_score: float
    comparison_vector: dict[str, float | None]
    matched_fields: tuple[str, ...]
    blocking_rule: str | None


class MatchScoreCalculator:
    """Calculates pairwise match probability and confidence score."""

    def __init__(
        self,
        fields: tuple[MatchingField, ...] = DEFAULT_MATCHING_FIELDS,
        match_threshold: float = 0.95,
    ) -> None:
        self._fields = fields
        self._match_threshold = match_threshold

    def score_pair(self, left: SourceCustomerRecord, right: SourceCustomerRecord) -> MatchScore:
        """Score a pair of customer records using configured fields."""
        comparisons = tuple(self._compare_field(field, left, right) for field in self._fields)
        available_weight = sum(item.weight for item in comparisons if item.score is not None)
        weighted_score = sum(
            (item.score or 0.0) * item.weight
            for item in comparisons
            if item.score is not None
        )
        match_probability = round(weighted_score / available_weight, 8) if available_weight else 0.0
        matched_fields = tuple(item.field_name for item in comparisons if item.matched)
        confidence_score = self._confidence_score(match_probability, comparisons)
        return MatchScore(
            match_probability=match_probability,
            confidence_score=confidence_score,
            comparison_vector={item.field_name: item.score for item in comparisons},
            matched_fields=matched_fields,
            blocking_rule=_blocking_rule(left, right),
        )

    def is_match(self, score: MatchScore) -> bool:
        """Return whether a score meets the configured threshold."""
        return score.match_probability >= self._match_threshold

    def _compare_field(
        self,
        field: MatchingField,
        left: SourceCustomerRecord,
        right: SourceCustomerRecord,
    ) -> FieldComparison:
        left_value = _record_value(left, field.column)
        right_value = _record_value(right, field.column)
        if left_value is None or right_value is None:
            return FieldComparison(field.column, field.method, None, field.weight, False)

        if field.method == "exact":
            score = 1.0 if left_value == right_value else 0.0
        elif field.method == "levenshtein":
            score = _levenshtein_similarity(left_value, right_value)
        else:
            score = SequenceMatcher(None, left_value, right_value).ratio()

        threshold = field.threshold if field.threshold is not None else 1.0
        return FieldComparison(
            field_name=field.column,
            method=field.method,
            score=round(score, 8),
            weight=field.weight,
            matched=score >= threshold,
        )

    def _confidence_score(
        self,
        match_probability: float,
        comparisons: tuple[FieldComparison, ...],
    ) -> float:
        available_weight = sum(item.weight for item in comparisons if item.score is not None)
        total_weight = sum(item.weight for item in comparisons)
        signal_coverage = available_weight / total_weight if total_weight else 0.0
        strong_signal_bonus = 0.05 if _has_strong_signal(comparisons) else 0.0
        confidence = (match_probability * 0.85) + (signal_coverage * 0.10) + strong_signal_bonus
        return round(min(confidence, 1.0), 8)


def _record_value(record: SourceCustomerRecord, field_name: str) -> str | None:
    value = getattr(record, "website_domain" if field_name == "website" else field_name, None)
    if value is None:
        return None
    normalized = str(value).strip().lower()
    return normalized or None


def _blocking_rule(left: SourceCustomerRecord, right: SourceCustomerRecord) -> str | None:
    values: Mapping[str, tuple[str | None, str | None]] = {
        "email": (_record_value(left, "email"), _record_value(right, "email")),
        "phone": (_record_value(left, "phone"), _record_value(right, "phone")),
        "website_domain": (
            _record_value(left, "website_domain"),
            _record_value(right, "website_domain"),
        ),
        "company_name": (
            _record_value(left, "company_name"),
            _record_value(right, "company_name"),
        ),
        "address": (_record_value(left, "address"), _record_value(right, "address")),
    }
    for field_name, (left_value, right_value) in values.items():
        if left_value and left_value == right_value:
            return f"l.{field_name} = r.{field_name}"
    return None


def _has_strong_signal(comparisons: tuple[FieldComparison, ...]) -> bool:
    exact_strong_fields = {"email", "phone"}
    matched = {item.field_name for item in comparisons if item.matched}
    return bool(matched & exact_strong_fields) or {"company_name", "website_domain"} <= matched


def _levenshtein_similarity(left: str, right: str) -> float:
    if left == right:
        return 1.0
    if not left or not right:
        return 0.0
    previous = list(range(len(right) + 1))
    for i, left_char in enumerate(left, start=1):
        current = [i]
        for j, right_char in enumerate(right, start=1):
            insert_cost = current[j - 1] + 1
            delete_cost = previous[j] + 1
            replace_cost = previous[j - 1] + (left_char != right_char)
            current.append(min(insert_cost, delete_cost, replace_cost))
        previous = current
    distance = previous[-1]
    return max(0.0, 1 - distance / max(len(left), len(right)))
