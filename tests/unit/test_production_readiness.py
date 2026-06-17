from __future__ import annotations

from collections.abc import Mapping

import pytest

from customer360.config import ConfigManager, load_settings
from customer360.interfaces.cli.main import readiness
from customer360.monitoring.readiness import ProductionReadinessChecker


def test_dev_readiness_passes_with_non_prod_warning() -> None:
    report = ProductionReadinessChecker(load_settings("configs/dev.yaml")).run()

    assert not report.failed
    assert report.warning_count >= 1
    assert any(finding.check_name == "non_prod_defaults" for finding in report.findings)


def test_prod_readiness_passes_with_secret_backed_configuration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_prod_env(monkeypatch)

    report = ProductionReadinessChecker(
        ConfigManager(environment="prod", config_path="configs/prod.yaml").load(),
        environment_variables={"CUSTOMER360_ALERT_EMAILS": "data-alerts@example.com"},
    ).run()

    assert not report.failed
    assert report.failure_count == 0
    assert _finding(report.to_dict(), "security", "domo_not_in_dry_run")["severity"] == "PASS"
    assert _finding(report.to_dict(), "observability", "production_failure_alerting_configured")[
        "severity"
    ] == "PASS"


def test_prod_readiness_fails_on_dry_run_and_default_secrets(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_prod_env(
        monkeypatch,
        SNOWFLAKE_ACCOUNT="local-dev",
        SNOWFLAKE_USER="customer360_dev",
        SNOWFLAKE_PASSWORD="local_password",
        SNOWFLAKE_ROLE="CUSTOMER360_DEV_ROLE",
        SNOWFLAKE_WAREHOUSE="CUSTOMER360_DEV_WH",
        DOMO_CLIENT_ID="dev_domo_client_id",
        DOMO_CLIENT_SECRET="dev_domo_client_secret",
    )

    report = ProductionReadinessChecker(
        ConfigManager(environment="prod", config_path="configs/prod.yaml").load(),
        environment_variables={"CUSTOMER360_DOMO_DRY_RUN": "true"},
    ).run()

    failing_checks = {finding.check_name for finding in report.findings if finding.severity == "FAIL"}
    assert report.failed
    assert "snowflake_password_not_default" in failing_checks
    assert "domo_client_secret_not_default" in failing_checks
    assert "domo_not_in_dry_run" in failing_checks


def test_readiness_cli_returns_success_for_dev_config(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = readiness(config_path=None, environment="dev", strict=False, json_output=False)

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Customer 360 readiness environment=dev" in captured.out


def test_readiness_cli_strict_mode_fails_on_warnings(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = readiness(config_path=None, environment="dev", strict=True, json_output=True)

    captured = capsys.readouterr()
    assert exit_code == 1
    assert '"environment": "dev"' in captured.out


def _set_prod_env(monkeypatch: pytest.MonkeyPatch, **overrides: str) -> None:
    values = {
        "SNOWFLAKE_ACCOUNT": "prod-acct",
        "SNOWFLAKE_USER": "customer360_prod_svc",
        "SNOWFLAKE_PASSWORD": "prod-secret",
        "SNOWFLAKE_ROLE": "CUSTOMER360_TRANSFORMER",
        "SNOWFLAKE_WAREHOUSE": "WH_CUSTOMER360_PROD",
        "DOMO_CLIENT_ID": "domo-prod-client",
        "DOMO_CLIENT_SECRET": "domo-prod-secret",
        "SALESFORCE_API_BASE_URL": "https://salesforce.example.com",
        "SALESFORCE_API_TOKEN": "salesforce-token",
        "MARKETO_API_BASE_URL": "https://marketo.example.com",
        "MARKETO_API_TOKEN": "marketo-token",
        "ZENDESK_API_BASE_URL": "https://zendesk.example.com",
        "ZENDESK_API_TOKEN": "zendesk-token",
        "PRODUCT_USAGE_API_BASE_URL": "https://usage.example.com",
        "PRODUCT_USAGE_API_TOKEN": "usage-token",
        "LICENSING_API_BASE_URL": "https://licensing.example.com",
        "LICENSING_API_TOKEN": "licensing-token",
        "IMPARTNER_API_BASE_URL": "https://impartner.example.com",
        "IMPARTNER_API_TOKEN": "impartner-token",
    }
    values.update(overrides)
    for key, value in values.items():
        monkeypatch.setenv(key, value)


def _finding(report: Mapping[str, object], category: str, check_name: str) -> Mapping[str, object]:
    findings = report["findings"]
    assert isinstance(findings, list)
    for finding in findings:
        assert isinstance(finding, dict)
        if finding["category"] == category and finding["check_name"] == check_name:
            return finding
    raise AssertionError(f"Finding not found: {category}.{check_name}")
