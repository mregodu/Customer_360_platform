"""Logging helpers for consistent structured logs across jobs and DAGs."""

from __future__ import annotations

import logging
import os

import structlog


def configure_logging() -> None:
    """Configure standard and structured logging once per process."""
    level = os.getenv("LOG_LEVEL", "INFO").upper()
    logging.basicConfig(level=level, format="%(message)s")
    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.add_log_level,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(getattr(logging, level, logging.INFO)),
    )
