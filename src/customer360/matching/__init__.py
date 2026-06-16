"""Matching module for Splink-driven entity resolution and golden cluster generation."""

from customer360.matching.clustering import CustomerClusterGenerator, MatchPrediction
from customer360.matching.scoring import MatchScore, MatchScoreCalculator
from customer360.matching.service import MatchingService
from customer360.matching.settings import SplinkSettingsBuilder

__all__ = [
    "CustomerClusterGenerator",
    "MatchPrediction",
    "MatchScore",
    "MatchScoreCalculator",
    "MatchingService",
    "SplinkSettingsBuilder",
]
