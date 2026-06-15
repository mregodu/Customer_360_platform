"""Configuration loading for the Customer 360 platform."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


class SnowflakeConfig(BaseModel):
    """Snowflake connection and warehouse target settings."""

    account: str
    user: str
    role: str
    warehouse: str
    database: str
    schema_name: str = Field(alias="schema")


class PipelineConfig(BaseModel):
    """Runtime knobs shared across ingestion, matching, and validation."""

    batch_size: int = 10000
    freshness_hours: int = 24
    matching_threshold: float = 0.95


class DomoConfig(BaseModel):
    """Domo API settings without credentials."""

    api_host: str


class Settings(BaseModel):
    """Top-level application settings loaded from YAML and environment variables."""

    environment: str
    snowflake: SnowflakeConfig
    pipeline: PipelineConfig
    domo: DomoConfig


def _expand_env(value: Any) -> Any:
    """Recursively expand `${VAR}` placeholders in YAML values."""
    if isinstance(value, str):
        return os.path.expandvars(value)
    if isinstance(value, dict):
        return {key: _expand_env(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_expand_env(item) for item in value]
    return value


def load_settings(path: str | Path | None = None) -> Settings:
    """Load platform settings from YAML.

    The default path can be supplied by `CUSTOMER360_CONFIG_PATH`. Keeping this
    function small makes it safe for Airflow DAG import time.
    """
    config_path = Path(path or os.getenv("CUSTOMER360_CONFIG_PATH", "configs/dev.yaml"))
    with config_path.open("r", encoding="utf-8") as handle:
        raw = yaml.safe_load(handle) or {}
    return Settings.model_validate(_expand_env(raw))
