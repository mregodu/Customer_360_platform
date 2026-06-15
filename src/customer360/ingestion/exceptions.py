"""Exception types for source-to-bronze ingestion."""

from __future__ import annotations

from dataclasses import dataclass


class IngestionError(RuntimeError):
    """Base exception for ingestion framework failures."""


class SourceExtractionError(IngestionError):
    """Raised when a source cannot be extracted successfully."""


class BronzeLoadError(IngestionError):
    """Raised when bronze-layer loading fails."""


class WatermarkError(IngestionError):
    """Raised when incremental watermark state cannot be read or written."""


@dataclass(frozen=True)
class FailedIngestionResult:
    """Failure metadata captured before re-raising an ingestion exception."""

    source_name: str
    source_system: str
    target_table: str
    error_message: str
    rows_extracted: int = 0
    rows_loaded: int = 0


class IngestionRunError(IngestionError):
    """Raised when a full source ingestion run fails."""

    def __init__(self, result: FailedIngestionResult) -> None:
        super().__init__(
            f"Ingestion failed for {result.source_name} into {result.target_table}: "
            f"{result.error_message}"
        )
        self.result = result
