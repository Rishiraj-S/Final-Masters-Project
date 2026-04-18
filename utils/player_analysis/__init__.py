"""
Player analysis utilities for CuléVision.

Provides metric computation and percentile/rating logic — adapted from the
standalone PlayerAnalysisEngine to work with the project's Opta event-parquet
data format.
"""

from .metrics import (
    compute_player_stats,
    compute_5d_scores,
    get_player_percentiles,
    get_player_ratings,
    POSITION_PIZZA_ATT,
    POSITION_PIZZA_DEF,
)

__all__ = [
    "compute_player_stats",
    "compute_5d_scores",
    "get_player_percentiles",
    "get_player_ratings",
    "POSITION_PIZZA_ATT",
    "POSITION_PIZZA_DEF",
]
