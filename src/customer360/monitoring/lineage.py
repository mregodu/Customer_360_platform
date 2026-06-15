"""Lineage event models for ETL audit logging."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass(frozen=True)
class LineageEvent:
    """Records source-to-target movement for auditability and troubleshooting."""

    source_table: str
    transformation_step: str
    destination_table: str
    execution_timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
