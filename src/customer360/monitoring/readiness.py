"""Production readiness checks for deployment hardening."""

from __future__ import annotations

import os
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Literal

from customer360.config import Customer360Config

ReadinessSeverity = Literal["PASS", "WARN", "FAIL"]

REQUIRED_SOURCE_NAMES = frozenset(
    {
        "salesforce",
        "marketo",
        "zendesk",
        "product_usage",
        "licensing",
        "impartner",
    }
)

REQUIRED_DAG_IDS = frozenset(
    {
        "customer_ingestion_dag",
        "customer_standardization_dag",
        "customer_matching_dag",
        "customer_enrichment_dag",
        "customer_scoring_dag",
        "dashboard_refresh_dag",
    }
)

_DEV_SECRET_VALUES = frozenset(
    {
        "local-dev",
        "local_password",
        "customer360_dev",
        "CUSTOMER360_DEV_ROLE",
        "CUSTOMER360_DEV_WH",
        "dev_domo_client_id",
        "dev_domo_client_secret",
        "test_domo_client_id",
        "test_domo_client_secret",
    }
)


@dataclass(frozen=True)
class ReadinessFinding:
    """One production-readiness result."""

    category: str
    severity: ReadinessSeverity
    check_name: str
    message: str
    remediation: str | None = None

    def to_dict(self) -> dict[str, str | None]:
        """Serialize the finding for JSON output."""
        return {
            "category": self.category,
            "severity": self.severity,
            "check_name": self.check_name,
            "message": self.message,
            "remediation": self.remediation,
        }


@dataclass(frozen=True)
class ReadinessReport:
    """Aggregated readiness status."""

    environment: str
    findings: tuple[ReadinessFinding, ...]

    @property
    def failed(self) -> bool:
        """Return whether any finding blocks deployment."""
        return any(finding.severity == "FAIL" for finding in self.findings)

    @property
    def warning_count(self) -> int:
        """Return the number of warning findings."""
        return sum(1 for finding in self.findings if finding.severity == "WARN")

    @property
    def failure_count(self) -> int:
        """Return the number of failing findings."""
        return sum(1 for finding in self.findings if finding.severity == "FAIL")

    def to_dict(self) -> dict[str, object]:
        """Serialize the report for JSON output."""
        return {
            "environment": self.environment,
            "failed": self.failed,
            "warning_count": self.warning_count,
            "failure_count": self.failure_count,
            "findings": [finding.to_dict() for finding in self.findings],
        }


class ProductionReadinessChecker:
    """Validate production hardening controls across config and runtime environment."""

    def __init__(
        self,
        settings: Customer360Config,
        *,
        environment_variables: Mapping[str, str] | None = None,
    ) -> None:
        self._settings = settings
        self._environment_variables = dict(environment_variables or os.environ)

    def run(self) -> ReadinessReport:
        """Return all production readiness findings."""
        findings: list[ReadinessFinding] = []
        findings.extend(self._security_findings())
        findings.extend(self._scalability_findings())
        findings.extend(self._performance_findings())
        findings.extend(self._maintainability_findings())
        findings.extend(self._observability_findings())
        return ReadinessReport(
            environment=self._settings.environment,
            findings=tuple(findings),
        )

    @property
    def _is_prod(self) -> bool:
        return self._settings.environment == "prod"

    def _security_findings(self) -> tuple[ReadinessFinding, ...]:
        findings = [
            _finding(
                "security",
                "PASS",
                "snowflake_authentication_configured",
                "Snowflake authentication material is configured.",
            )
            if self._settings.snowflake.password is not None
            or self._settings.snowflake.private_key_path is not None
            else _finding(
                "security",
                "FAIL",
                "snowflake_authentication_configured",
                "Snowflake authentication material is missing.",
                "Set SNOWFLAKE_PASSWORD or configure private_key_path for the service user.",
            )
        ]

        if self._is_prod:
            findings.extend(self._prod_secret_findings())
            findings.extend(self._source_api_security_findings())
            dry_run = self._environment_variables.get("CUSTOMER360_DOMO_DRY_RUN", "").lower()
            findings.append(
                _finding(
                    "security",
                    "FAIL" if dry_run in {"1", "true", "yes", "y"} else "PASS",
                    "domo_not_in_dry_run",
                    "Domo publishing is configured for production execution.",
                    "Set CUSTOMER360_DOMO_DRY_RUN=false for production dashboard publishing.",
                )
            )
        else:
            findings.append(
                _finding(
                    "security",
                    "WARN",
                    "non_prod_defaults",
                    "Non-production environments may use placeholder credentials.",
                    "Use production readiness with CUSTOMER360_ENV=prod before release.",
                )
            )

        return tuple(findings)

    def _prod_secret_findings(self) -> list[ReadinessFinding]:
        checks = {
            "snowflake_account_not_default": self._settings.snowflake.account,
            "snowflake_user_not_default": self._settings.snowflake.user,
            "snowflake_role_not_default": self._settings.snowflake.role,
            "snowflake_warehouse_not_default": self._settings.snowflake.warehouse,
            "domo_client_id_not_default": self._settings.domo.client_id,
            "domo_client_secret_not_default": self._settings.domo.client_secret.get_secret_value(),
        }
        if self._settings.snowflake.password is not None:
            checks["snowflake_password_not_default"] = self._settings.snowflake.password.get_secret_value()

        findings: list[ReadinessFinding] = []
        for check_name, value in checks.items():
            findings.append(
                _finding(
                    "security",
                    "FAIL" if value in _DEV_SECRET_VALUES else "PASS",
                    check_name,
                    f"{check_name.replace('_', ' ').capitalize()} passed.",
                    "Replace development defaults with production secret-manager values.",
                )
            )
        return findings

    def _source_api_security_findings(self) -> list[ReadinessFinding]:
        findings: list[ReadinessFinding] = []
        for name, source in sorted(self._settings.ingestion.sources.items()):
            if not source.enabled or source.source_type != "api" or source.api is None:
                continue
            is_https = str(source.api.base_url).lower().startswith("https://")
            has_token = source.api.auth_token is not None and bool(source.api.auth_token.get_secret_value())
            findings.append(
                _finding(
                    "security",
                    "PASS" if is_https else "FAIL",
                    f"{name}_api_uses_https",
                    f"{source.source_system} API base URL uses HTTPS.",
                    "Use HTTPS endpoints for all production API sources.",
                )
            )
            findings.append(
                _finding(
                    "security",
                    "PASS" if has_token else "FAIL",
                    f"{name}_api_token_configured",
                    f"{source.source_system} API authentication token is configured.",
                    "Provide API tokens through the deployment secret store.",
                )
            )
        return findings

    def _scalability_findings(self) -> tuple[ReadinessFinding, ...]:
        retry_attempts = self._settings.ingestion.retry.max_attempts
        return (
            _threshold_finding(
                category="scalability",
                check_name="batch_size_at_least_10000",
                value=self._settings.pipeline.batch_size,
                minimum=10000,
                message="Pipeline batch size supports high-volume ingestion.",
                remediation="Set pipeline.batch_size to at least 10000 for production workloads.",
            ),
            _threshold_finding(
                category="scalability",
                check_name="ingestion_retry_attempts_at_least_3",
                value=retry_attempts,
                minimum=3,
                message="Ingestion retry policy can absorb transient source and warehouse failures.",
                remediation="Set ingestion.retry.max_attempts to at least 3.",
            ),
            _threshold_finding(
                category="scalability",
                check_name="splink_match_threshold_at_least_090",
                value=self._settings.splink.match_threshold,
                minimum=0.90,
                message="Matching threshold is high enough for production entity resolution.",
                remediation="Tune splink.match_threshold to at least 0.90 after validation.",
            ),
            _finding(
                "scalability",
                "PASS" if self._settings.airflow.max_active_runs <= 2 else "WARN",
                "airflow_max_active_runs_bounded",
                "Airflow max_active_runs is bounded to protect Snowflake capacity.",
                "Keep max_active_runs at 1 or 2 unless warehouses are scaled accordingly.",
            ),
        )

    def _performance_findings(self) -> tuple[ReadinessFinding, ...]:
        return (
            _threshold_finding(
                category="performance",
                check_name="snowflake_query_timeout_at_least_300",
                value=self._settings.snowflake.query_timeout_seconds,
                minimum=300,
                message="Snowflake query timeout supports long-running transformations.",
                remediation="Set snowflake.query_timeout_seconds to at least 300.",
            ),
            _finding(
                "performance",
                "PASS" if self._settings.snowflake.login_timeout_seconds <= 60 else "WARN",
                "snowflake_login_timeout_bounded",
                "Snowflake login timeout is bounded for fast failure detection.",
                "Keep snowflake.login_timeout_seconds at or below 60.",
            ),
            _threshold_finding(
                category="performance",
                check_name="splink_max_iterations_at_least_10",
                value=self._settings.splink.max_iterations,
                minimum=10,
                message="Splink model iteration budget supports stable matching.",
                remediation="Set splink.max_iterations to at least 10 for production matching.",
            ),
        )

    def _maintainability_findings(self) -> tuple[ReadinessFinding, ...]:
        configured_sources = set(self._settings.ingestion.sources)
        configured_dags = set(self._settings.airflow.dags)
        enabled_dags = {
            dag_id for dag_id, dag_config in self._settings.airflow.dags.items() if dag_config.enabled
        }
        missing_sources = sorted(REQUIRED_SOURCE_NAMES - configured_sources)
        missing_dags = sorted(REQUIRED_DAG_IDS - configured_dags)
        disabled_required_dags = sorted(REQUIRED_DAG_IDS - enabled_dags)
        return (
            _finding(
                "maintainability",
                "PASS" if not missing_sources else "FAIL",
                "required_sources_configured",
                "All required source systems are configured.",
                f"Add missing source configs: {', '.join(missing_sources)}" if missing_sources else None,
            ),
            _finding(
                "maintainability",
                "PASS" if not missing_dags else "FAIL",
                "required_dags_configured",
                "All required Airflow DAGs are configured.",
                f"Add missing DAG configs: {', '.join(missing_dags)}" if missing_dags else None,
            ),
            _finding(
                "maintainability",
                "PASS" if not disabled_required_dags else "FAIL",
                "required_dags_enabled",
                "All required Airflow DAGs are enabled.",
                f"Enable required DAG configs: {', '.join(disabled_required_dags)}"
                if disabled_required_dags
                else None,
            ),
        )

    def _observability_findings(self) -> tuple[ReadinessFinding, ...]:
        alert_emails = [
            email.strip()
            for email in self._environment_variables.get("CUSTOMER360_ALERT_EMAILS", "").split(",")
            if email.strip()
        ]
        prod_alerting_ok = not self._is_prod or (self._settings.airflow.email_on_failure and alert_emails)
        return (
            _finding(
                "observability",
                "PASS"
                if self._settings.logging.enable_structured_logging
                else ("FAIL" if self._is_prod else "WARN"),
                "structured_logging_enabled",
                "Structured logging is enabled.",
                "Set logging.enable_structured_logging=true.",
            ),
            _finding(
                "observability",
                "PASS" if self._settings.logging.renderer == "json" else "WARN",
                "json_logs_enabled",
                "JSON logs are enabled for aggregation.",
                "Set logging.renderer=json in production.",
            ),
            _finding(
                "observability",
                "PASS" if self._settings.pipeline.audit_history_enabled else "FAIL",
                "audit_history_enabled",
                "Pipeline audit history is enabled.",
                "Set pipeline.audit_history_enabled=true.",
            ),
            _finding(
                "observability",
                "PASS" if prod_alerting_ok else "WARN",
                "production_failure_alerting_configured",
                "Production Airflow failure alerting is configured.",
                "Set airflow.email_on_failure=true and CUSTOMER360_ALERT_EMAILS.",
            ),
            _finding(
                "observability",
                "PASS"
                if _all_tables_in_analytics(
                    (
                        self._settings.logging.pipeline_execution_log_table,
                        self._settings.logging.etl_audit_log_table,
                    )
                )
                else "FAIL",
                "audit_tables_in_analytics_schema",
                "Audit log tables are stored in the Analytics schema.",
                "Point logging tables to CUSTOMER360_DB.ANALYTICS.",
            ),
        )


def _all_tables_in_analytics(table_names: Sequence[str]) -> bool:
    return all(".ANALYTICS." in table_name.upper() for table_name in table_names)


def _threshold_finding(
    *,
    category: str,
    check_name: str,
    value: float,
    minimum: float,
    message: str,
    remediation: str,
) -> ReadinessFinding:
    return _finding(
        category,
        "PASS" if value >= minimum else "WARN",
        check_name,
        message,
        remediation if value < minimum else None,
    )


def _finding(
    category: str,
    severity: ReadinessSeverity,
    check_name: str,
    message: str,
    remediation: str | None = None,
) -> ReadinessFinding:
    return ReadinessFinding(
        category=category,
        severity=severity,
        check_name=check_name,
        message=message,
        remediation=remediation if severity != "PASS" else None,
    )
