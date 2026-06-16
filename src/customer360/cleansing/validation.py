"""Validation and data-quality metrics for silver-layer transformations."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

_EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


@dataclass(frozen=True)
class ValidationIssue:
    """One validation issue found on a transformed record."""

    rule_name: str
    field_name: str
    severity: str
    message: str


@dataclass(frozen=True)
class RecordValidationResult:
    """Validation outcome for one transformed record."""

    is_valid: bool
    quality_score: float
    completeness_score: float
    issues: tuple[ValidationIssue, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class DataQualityMetric:
    """Aggregated quality metric ready for analytics persistence."""

    rule_name: str
    rule_type: str
    passed_count: int
    failed_count: int
    total_count: int
    quality_score: float
    status: str


@dataclass(frozen=True)
class DataQualityReport:
    """Aggregated validation results for a transformation batch."""

    total_records: int
    valid_records: int
    invalid_records: int
    average_quality_score: float
    metrics: tuple[DataQualityMetric, ...]


class SilverRecordValidator:
    """Validates standardized records before they are merged into Silver."""

    def validate_customer(self, record: Mapping[str, object]) -> RecordValidationResult:
        """Validate a standardized customer identity record."""
        issues: list[ValidationIssue] = []
        _require(record, "source_system", issues)
        _require(record, "source_customer_id", issues)

        email = _text(record.get("email"))
        phone = _text(record.get("phone"))
        company_name = _text(record.get("company_name"))

        if not any([email, phone, company_name]):
            issues.append(
                ValidationIssue(
                    "identity_signal_present",
                    "company_name,email,phone",
                    "ERROR",
                    "At least one identity signal is required.",
                )
            )
        if email and not _EMAIL_PATTERN.match(email):
            issues.append(
                ValidationIssue("valid_email", "email", "ERROR", "Email format is invalid.")
            )
        if phone and not 7 <= len(phone) <= 15:
            issues.append(
                ValidationIssue("valid_phone", "phone", "WARNING", "Phone length is outside range.")
            )

        completeness = completeness_score(
            record,
            (
                "company_name",
                "email",
                "phone",
                "address",
                "industry",
                "last_modified_timestamp",
            ),
        )
        quality_score = _quality_score(completeness, issues)
        return RecordValidationResult(
            is_valid=not any(issue.severity == "ERROR" for issue in issues),
            quality_score=quality_score,
            completeness_score=completeness,
            issues=tuple(issues),
        )

    def validate_partner(self, record: Mapping[str, object]) -> RecordValidationResult:
        """Validate a standardized partner profile record."""
        issues: list[ValidationIssue] = []
        _require(record, "source_system", issues)
        _require(record, "partner_id", issues)
        _require(record, "company_name", issues)

        email = _text(record.get("email"))
        phone = _text(record.get("phone"))
        if email and not _EMAIL_PATTERN.match(email):
            issues.append(
                ValidationIssue("valid_email", "email", "ERROR", "Email format is invalid.")
            )
        if phone and not 7 <= len(phone) <= 15:
            issues.append(
                ValidationIssue("valid_phone", "phone", "WARNING", "Phone length is outside range.")
            )

        completeness = completeness_score(
            record,
            ("company_name", "email", "phone", "partner_tier", "partner_region"),
        )
        quality_score = _quality_score(completeness, issues)
        return RecordValidationResult(
            is_valid=not any(issue.severity == "ERROR" for issue in issues),
            quality_score=quality_score,
            completeness_score=completeness,
            issues=tuple(issues),
        )

    def build_report(self, results: Sequence[RecordValidationResult]) -> DataQualityReport:
        """Build aggregate data-quality metrics for a batch."""
        total = len(results)
        valid = sum(1 for result in results if result.is_valid)
        invalid = total - valid
        average_quality = (
            round(sum(result.quality_score for result in results) / total, 4) if total else 1.0
        )

        rule_counts: dict[str, int] = {}
        for result in results:
            for issue in result.issues:
                rule_counts[issue.rule_name] = rule_counts.get(issue.rule_name, 0) + 1

        metrics = [
            DataQualityMetric(
                rule_name="record_validity",
                rule_type="validity",
                passed_count=valid,
                failed_count=invalid,
                total_count=total,
                quality_score=round(valid / total, 4) if total else 1.0,
                status="PASS" if invalid == 0 else "FAIL",
            ),
            DataQualityMetric(
                rule_name="average_record_quality",
                rule_type="quality_score",
                passed_count=valid,
                failed_count=invalid,
                total_count=total,
                quality_score=average_quality,
                status="PASS" if average_quality >= 0.95 else "WARN",
            ),
        ]
        for rule_name, failed_count in sorted(rule_counts.items()):
            passed_count = total - failed_count
            score = round(passed_count / total, 4) if total else 1.0
            metrics.append(
                DataQualityMetric(
                    rule_name=rule_name,
                    rule_type="rule",
                    passed_count=passed_count,
                    failed_count=failed_count,
                    total_count=total,
                    quality_score=score,
                    status="PASS" if failed_count == 0 else "FAIL",
                )
            )
        return DataQualityReport(
            total_records=total,
            valid_records=valid,
            invalid_records=invalid,
            average_quality_score=average_quality,
            metrics=tuple(metrics),
        )


def completeness_score(record: Mapping[str, object], fields: Sequence[str]) -> float:
    """Calculate field completeness for a selected set of fields."""
    if not fields:
        return 1.0
    populated = sum(1 for field_name in fields if _text(record.get(field_name)))
    return round(populated / len(fields), 4)


def _require(
    record: Mapping[str, object],
    field_name: str,
    issues: list[ValidationIssue],
) -> None:
    if not _text(record.get(field_name)):
        issues.append(
            ValidationIssue(
                f"{field_name}_required",
                field_name,
                "ERROR",
                f"{field_name} is required.",
            )
        )


def _quality_score(completeness: float, issues: Sequence[ValidationIssue]) -> float:
    penalty = 0.0
    for issue in issues:
        penalty += 0.25 if issue.severity == "ERROR" else 0.1
    return round(max(0.0, completeness - penalty), 4)


def _text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
