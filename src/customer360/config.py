"""Centralized configuration management for the Customer 360 platform."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Annotated, Any, Literal

import yaml
from pydantic import (
    AnyHttpUrl,
    BaseModel,
    ConfigDict,
    Field,
    NonNegativeInt,
    PositiveInt,
    SecretStr,
    StringConstraints,
    ValidationError,
    field_validator,
)

EnvironmentName = Literal["dev", "test", "prod"]
LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
LogRenderer = Literal["json", "console"]
SplinkComparisonMethod = Literal["exact", "jaro_winkler", "levenshtein"]
SplinkLinkType = Literal["dedupe_only", "link_only", "link_and_dedupe"]
NonEmptyStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]

_DEFAULT_CONFIG_DIR = Path(__file__).resolve().parents[2] / "configs"
_ENV_PATTERN = re.compile(r"\$\{(?P<name>[A-Za-z_][A-Za-z0-9_]*)(?::-(?P<default>[^}]*))?\}")


class ConfigurationError(RuntimeError):
    """Raised when configuration cannot be loaded or validated."""


class StrictConfigModel(BaseModel):
    """Base model for all validated configuration sections."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        populate_by_name=True,
        str_strip_whitespace=True,
    )


class SnowflakeConfig(StrictConfigModel):
    """Snowflake connection and warehouse target settings."""

    account: NonEmptyStr
    user: NonEmptyStr
    password: SecretStr | None = Field(default=None, repr=False)
    private_key_path: Path | None = None
    role: NonEmptyStr
    warehouse: NonEmptyStr
    database: NonEmptyStr
    schema_name: NonEmptyStr = Field(alias="schema")
    authenticator: NonEmptyStr = "snowflake"
    login_timeout_seconds: PositiveInt = 30
    query_timeout_seconds: PositiveInt = 300

    @field_validator("password", mode="before")
    @classmethod
    def _empty_password_to_none(cls, value: object) -> object:
        if value == "":
            return None
        return value

    @field_validator("private_key_path", mode="before")
    @classmethod
    def _empty_private_key_to_none(cls, value: object) -> object:
        if value == "":
            return None
        return value

    def connection_parameters(self) -> dict[str, str | int]:
        """Return Snowflake connector keyword arguments with secrets materialized."""
        params: dict[str, str | int] = {
            "account": self.account,
            "user": self.user,
            "role": self.role,
            "warehouse": self.warehouse,
            "database": self.database,
            "schema": self.schema_name,
            "authenticator": self.authenticator,
            "login_timeout": self.login_timeout_seconds,
            "network_timeout": self.query_timeout_seconds,
        }
        if self.password is not None:
            params["password"] = self.password.get_secret_value()
        if self.private_key_path is not None:
            params["private_key_file"] = str(self.private_key_path)
        return params


class AirflowDagConfig(StrictConfigModel):
    """Schedule and enablement controls for one Airflow DAG."""

    schedule: NonEmptyStr
    enabled: bool = True


class AirflowConfig(StrictConfigModel):
    """Airflow runtime settings shared by generated DAGs."""

    airflow_home: Path
    dag_owner: NonEmptyStr
    schedule_timezone: NonEmptyStr = "UTC"
    max_active_runs: PositiveInt = 1
    catchup: bool = False
    email_on_failure: bool = False
    retries: NonNegativeInt = 1
    retry_delay_minutes: PositiveInt = 5
    default_pool: NonEmptyStr = "default_pool"
    dags: dict[NonEmptyStr, AirflowDagConfig]


class SplinkComparisonConfig(StrictConfigModel):
    """One column comparison used by the Splink matching engine."""

    column: NonEmptyStr
    method: SplinkComparisonMethod
    threshold: float | None = Field(default=None, ge=0, le=1)


class SplinkConfig(StrictConfigModel):
    """Probabilistic matching settings for Splink."""

    sql_dialect: NonEmptyStr = "snowflake"
    link_type: SplinkLinkType = "link_and_dedupe"
    unique_id_column: NonEmptyStr
    source_dataset_column: NonEmptyStr
    match_threshold: float = Field(ge=0, le=1)
    deterministic_rules: list[NonEmptyStr] = Field(default_factory=list)
    blocking_rules: list[NonEmptyStr] = Field(min_length=1)
    comparisons: list[SplinkComparisonConfig] = Field(min_length=1)
    retain_matching_columns: bool = True
    max_iterations: PositiveInt = 20
    output_table: NonEmptyStr
    cluster_table: NonEmptyStr


class LoggingConfig(StrictConfigModel):
    """Logging and audit metadata table settings."""

    level: LogLevel = "INFO"
    renderer: LogRenderer = "json"
    enable_structured_logging: bool = True
    pipeline_execution_log_table: NonEmptyStr
    etl_audit_log_table: NonEmptyStr
    retention_days: PositiveInt = 90

    @field_validator("level", mode="before")
    @classmethod
    def _normalize_level(cls, value: object) -> object:
        if isinstance(value, str):
            return value.upper()
        return value


class PipelineConfig(StrictConfigModel):
    """Runtime knobs shared across ingestion, matching, and validation."""

    batch_size: PositiveInt = 10000
    freshness_hours: PositiveInt = 24
    matching_threshold: float = Field(default=0.95, ge=0, le=1)
    cdc_column: NonEmptyStr = "last_modified_timestamp"
    audit_history_enabled: bool = True


class DomoConfig(StrictConfigModel):
    """Domo API endpoint and credential settings."""

    api_host: AnyHttpUrl
    client_id: NonEmptyStr
    client_secret: SecretStr = Field(repr=False)
    access_token: SecretStr | None = Field(default=None, repr=False)
    dataset_prefix: NonEmptyStr = "customer360"
    timeout_seconds: PositiveInt = 30
    retry_attempts: NonNegativeInt = 3

    @field_validator("access_token", mode="before")
    @classmethod
    def _empty_access_token_to_none(cls, value: object) -> object:
        if value == "":
            return None
        return value

    def credential_payload(self) -> dict[str, str]:
        """Return Domo credentials for OAuth or client construction."""
        payload = {
            "client_id": self.client_id,
            "client_secret": self.client_secret.get_secret_value(),
        }
        if self.access_token is not None:
            payload["access_token"] = self.access_token.get_secret_value()
        return payload


class Customer360Config(StrictConfigModel):
    """Top-level application settings loaded from YAML and environment variables."""

    environment: EnvironmentName
    snowflake: SnowflakeConfig
    airflow: AirflowConfig
    splink: SplinkConfig
    logging: LoggingConfig
    pipeline: PipelineConfig = Field(default_factory=PipelineConfig)
    domo: DomoConfig


Settings = Customer360Config


class ConfigManager:
    """Load, validate, cache, and expose Customer 360 configuration."""

    def __init__(
        self,
        environment: str | None = None,
        config_dir: str | Path | None = None,
        config_path: str | Path | None = None,
    ) -> None:
        self._expected_environment = environment or os.getenv("CUSTOMER360_ENV")
        env_config_path = os.getenv("CUSTOMER360_CONFIG_PATH")
        env_config_dir = os.getenv("CUSTOMER360_CONFIG_DIR")
        self._config_path = (
            Path(config_path or env_config_path) if config_path or env_config_path else None
        )
        self._config_dir = (
            Path(config_dir or env_config_dir)
            if config_dir or env_config_dir
            else _DEFAULT_CONFIG_DIR
        )
        self._settings: Customer360Config | None = None

    @property
    def environment(self) -> str:
        """Return the selected environment name, defaulting to dev."""
        return self._expected_environment or "dev"

    @property
    def config_path(self) -> Path:
        """Return the YAML file path that will be loaded."""
        if self._config_path is not None:
            return self._config_path
        return self._config_dir / f"{self.environment}.yaml"

    @property
    def settings(self) -> Customer360Config:
        """Return cached settings, loading them on first access."""
        if self._settings is None:
            self._settings = self.load()
        return self._settings

    def load(self) -> Customer360Config:
        """Read and validate configuration from YAML."""
        path = self.config_path
        if not path.exists():
            raise ConfigurationError(f"Configuration file not found: {path}")

        try:
            with path.open("r", encoding="utf-8") as handle:
                raw = yaml.safe_load(handle) or {}
        except yaml.YAMLError as exc:
            raise ConfigurationError(f"Configuration file is not valid YAML: {path}") from exc

        try:
            expanded = _expand_env(raw)
            settings = Customer360Config.model_validate(expanded)
        except ValidationError as exc:
            raise ConfigurationError(f"Configuration validation failed for {path}: {exc}") from exc

        if (
            self._expected_environment is not None
            and self._config_path is None
            and settings.environment != self._expected_environment
        ):
            raise ConfigurationError(
                f"Configuration environment mismatch: expected "
                f"{self._expected_environment!r}, found {settings.environment!r}."
            )

        self._settings = settings
        return settings

    def reload(self) -> Customer360Config:
        """Clear cached settings and reload from disk."""
        self._settings = None
        return self.load()

    def snowflake_connection_parameters(self) -> dict[str, str | int]:
        """Expose validated Snowflake connector parameters."""
        return self.settings.snowflake.connection_parameters()

    def domo_credential_payload(self) -> dict[str, str]:
        """Expose validated Domo credentials with secrets materialized."""
        return self.settings.domo.credential_payload()


def _expand_env(value: Any) -> Any:
    """Recursively expand `${VAR}` and `${VAR:-default}` placeholders."""
    if isinstance(value, str):
        return _expand_env_string(value)
    if isinstance(value, dict):
        return {key: _expand_env(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_expand_env(item) for item in value]
    return value


def _expand_env_string(value: str) -> str:
    """Expand environment placeholders inside a single string."""

    def replace(match: re.Match[str]) -> str:
        name = match.group("name")
        default = match.group("default")
        env_value = os.getenv(name)
        if env_value is not None:
            return env_value
        if default is not None:
            return default
        raise ConfigurationError(f"Missing required environment variable: {name}")

    return _ENV_PATTERN.sub(replace, value)


def load_settings(
    path: str | Path | None = None,
    environment: str | None = None,
) -> Settings:
    """Load platform settings from YAML.

    The default path can be supplied by `CUSTOMER360_CONFIG_PATH`, or selected
    with `CUSTOMER360_ENV`. Keeping this wrapper small makes it safe for Airflow
    DAG import time while preserving the original public API.
    """
    return ConfigManager(environment=environment, config_path=path).settings
