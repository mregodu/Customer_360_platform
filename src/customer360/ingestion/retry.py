"""Retry helpers for transient ingestion failures."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import TypeVar

from customer360.config import RetryConfig

T = TypeVar("T")


@dataclass(frozen=True)
class RetryPolicy:
    """Runtime retry policy with exponential backoff."""

    max_attempts: int = 3
    initial_delay_seconds: float = 1
    max_delay_seconds: float = 30
    backoff_multiplier: float = 2

    @classmethod
    def from_config(cls, config: RetryConfig) -> RetryPolicy:
        """Build a retry policy from validated configuration."""
        return cls(
            max_attempts=config.max_attempts,
            initial_delay_seconds=config.initial_delay_seconds,
            max_delay_seconds=config.max_delay_seconds,
            backoff_multiplier=config.backoff_multiplier,
        )


def retry_call(
    operation: Callable[[], T],
    *,
    policy: RetryPolicy,
    operation_name: str,
    logger: logging.Logger,
    sleep: Callable[[float], None] = time.sleep,
) -> T:
    """Run an operation with bounded exponential backoff."""
    attempt = 1
    delay = policy.initial_delay_seconds
    while True:
        try:
            return operation()
        except Exception:
            if attempt >= policy.max_attempts:
                logger.exception(
                    "ingestion_operation_failed",
                    extra={"operation_name": operation_name, "attempt": attempt},
                )
                raise
            logger.warning(
                "ingestion_operation_retrying",
                extra={
                    "operation_name": operation_name,
                    "attempt": attempt,
                    "next_delay_seconds": delay,
                },
                exc_info=True,
            )
            if delay > 0:
                sleep(delay)
            delay = min(delay * policy.backoff_multiplier, policy.max_delay_seconds)
            attempt += 1
