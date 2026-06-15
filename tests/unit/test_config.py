from pathlib import Path

import pytest

from customer360.config import ConfigManager, ConfigurationError, load_settings


def test_loads_dev_configuration_with_defaults() -> None:
    settings = load_settings("configs/dev.yaml")

    assert settings.environment == "dev"
    assert settings.snowflake.database == "CUSTOMER360_DB"
    assert settings.airflow.dags["customer_ingestion_dag"].schedule == "@hourly"
    assert settings.splink.match_threshold == 0.95
    assert settings.logging.level == "INFO"
    assert settings.domo.dataset_prefix == "customer360_dev"


def test_config_manager_expands_environment_values(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SNOWFLAKE_ACCOUNT", "acct")
    monkeypatch.setenv("SNOWFLAKE_USER", "svc_user")
    monkeypatch.setenv("SNOWFLAKE_PASSWORD", "secret")
    monkeypatch.setenv("SNOWFLAKE_ROLE", "svc_role")
    monkeypatch.setenv("DOMO_CLIENT_ID", "domo_id")
    monkeypatch.setenv("DOMO_CLIENT_SECRET", "domo_secret")

    manager = ConfigManager(environment="prod")

    snowflake_params = manager.snowflake_connection_parameters()
    domo_payload = manager.domo_credential_payload()

    assert snowflake_params["account"] == "acct"
    assert snowflake_params["password"] == "secret"
    assert domo_payload["client_id"] == "domo_id"
    assert domo_payload["client_secret"] == "domo_secret"


def test_missing_required_environment_variable_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for name in (
        "SNOWFLAKE_ACCOUNT",
        "SNOWFLAKE_USER",
        "SNOWFLAKE_PASSWORD",
        "SNOWFLAKE_ROLE",
        "DOMO_CLIENT_ID",
        "DOMO_CLIENT_SECRET",
    ):
        monkeypatch.delenv(name, raising=False)

    with pytest.raises(ConfigurationError, match="SNOWFLAKE_ACCOUNT"):
        ConfigManager(environment="prod").load()


def test_invalid_splink_threshold_is_rejected(tmp_path: Path) -> None:
    config_path = tmp_path / "invalid.yaml"
    config_path.write_text(
        """
environment: dev
snowflake:
  account: local
  user: user
  password: pass
  role: role
  warehouse: wh
  database: CUSTOMER360_DB
  schema: LANDING
airflow:
  airflow_home: ./airflow
  dag_owner: owner
  dags:
    customer_ingestion_dag:
      schedule: "@hourly"
splink:
  unique_id_column: source_customer_id
  source_dataset_column: source_system
  match_threshold: 1.2
  blocking_rules:
    - "l.email = r.email"
  comparisons:
    - column: email
      method: exact
  output_table: CUSTOMER360_DB.GOLD.customer_match_predictions
  cluster_table: CUSTOMER360_DB.GOLD.customer_clusters
logging:
  pipeline_execution_log_table: CUSTOMER360_DB.ANALYTICS.pipeline_execution_log
  etl_audit_log_table: CUSTOMER360_DB.ANALYTICS.etl_audit_log
domo:
  api_host: https://api.domo.com
  client_id: id
  client_secret: secret
""",
        encoding="utf-8",
    )

    with pytest.raises(ConfigurationError, match="match_threshold"):
        ConfigManager(config_path=config_path).load()
