"""Golden customer record generation and survivorship."""

from customer360.golden.service import GoldenRecordService, GoldenRecordWriter
from customer360.golden.survivorship import (
    GoldenRecordGenerator,
    SurvivorshipDecision,
)

__all__ = [
    "GoldenRecordGenerator",
    "GoldenRecordService",
    "GoldenRecordWriter",
    "SurvivorshipDecision",
]
