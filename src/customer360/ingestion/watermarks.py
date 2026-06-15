"""Incremental watermark storage contracts and in-memory implementation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from customer360.ingestion.exceptions import WatermarkError


class WatermarkStore(Protocol):
    """Stores high-watermarks for incremental ingestion sources."""

    def get_watermark(self, source_system: str, source_object: str) -> str | None:
        """Return the last successful high-watermark value for a source."""

    def update_watermark(
        self,
        source_system: str,
        source_object: str,
        watermark_column: str,
        watermark_value: str,
        run_id: str,
    ) -> None:
        """Persist a source high-watermark after a successful load."""


@dataclass
class InMemoryWatermarkStore:
    """Simple watermark store for local development and unit tests."""

    _values: dict[tuple[str, str], str] = field(default_factory=dict)

    def get_watermark(self, source_system: str, source_object: str) -> str | None:
        """Return a stored high-watermark value."""
        return self._values.get((source_system, source_object))

    def update_watermark(
        self,
        source_system: str,
        source_object: str,
        watermark_column: str,
        watermark_value: str,
        run_id: str,
    ) -> None:
        """Store a high-watermark value."""
        if not watermark_value:
            raise WatermarkError(
                f"Cannot store empty watermark for {source_system}.{source_object} "
                f"column={watermark_column} run_id={run_id}."
            )
        self._values[(source_system, source_object)] = watermark_value
