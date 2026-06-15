"""Logging helpers for consistent structured logs across jobs and DAGs."""

from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from customer360.config import LoggingConfig

try:
    import structlog
except ModuleNotFoundError:  # pragma: no cover - exercised only in minimal local environments
    structlog = None  # type: ignore[assignment]


def configure_logging(config: LoggingConfig | None = None) -> None:
    """Configure standard and structured logging once per process."""
    level = (config.level if config is not None else os.getenv("LOG_LEVEL", "INFO")).upper()
    logging.basicConfig(level=level, format="%(message)s")
    if structlog is None:
        return
    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.add_log_level,
            structlog.processors.JSONRenderer()
            if config is None or config.renderer == "json"
            else structlog.dev.ConsoleRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(getattr(logging, level, logging.INFO)),
    )
