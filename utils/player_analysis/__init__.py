"""
Player analysis utilities for CuléVision.

Provides metric computation, percentile/rating logic, and pizza plot
generation — adapted from the standalone PlayerAnalysisEngine to work
with the project's Opta event-parquet data format.
"""

from .metrics import (
    compute_player_stats,
    compute_5d_scores,
    get_player_percentiles,
    get_player_ratings,
    POSITION_PIZZA_ATT,
    POSITION_PIZZA_DEF,
)
from .pizza import render_pizza_plot

__all__ = [
    "compute_player_stats",
    "compute_5d_scores",
    "get_player_percentiles",
    "get_player_ratings",
    "render_pizza_plot",
    "POSITION_PIZZA_ATT",
    "POSITION_PIZZA_DEF",
]
