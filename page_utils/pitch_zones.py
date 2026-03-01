"""
pitch_zones.py
==============
Pitch zone detection and spatial utilities.

Coordinate conventions (Opta 0-100 scale):
    x : own goal = 0  →  opponent goal = 100  (always from the performing team's
        perspective, i.e. the ball carrier / event team attacks toward high x).
    y : top touchline = 0  →  bottom touchline = 100.

The pitch is divided into three equal thirds along the x-axis by default,
but all boundaries are configurable via ``ZoneBoundaries``.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional

import pandas as pd


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class PitchZone(Enum):
    """Longitudinal zone of the pitch."""

    DEFENSIVE_THIRD = "defensive_third"
    MIDDLE_THIRD = "middle_third"
    FINAL_THIRD = "final_third"
    UNKNOWN = "unknown"


class PitchHalf(Enum):
    """Which half of the pitch an event occurred in."""

    OWN_HALF = "own_half"
    OPPONENT_HALF = "opponent_half"


# ---------------------------------------------------------------------------
# Configurable boundaries
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ZoneBoundaries:
    """Pitch zone boundary thresholds on the 0-100 x-axis.

    Attributes:
        defensive_end : Upper x limit of the defensive third (exclusive).
        middle_end    : Upper x limit of the middle third (exclusive).
                        Everything above this is the final / attacking third.
    """

    defensive_end: float = 33.3
    middle_end: float = 66.7


_DEFAULT_BOUNDARIES: ZoneBoundaries = ZoneBoundaries()

# ---------------------------------------------------------------------------
# Penalty-box constants (standard Opta 100x100 layout)
# ---------------------------------------------------------------------------

BOX_X_MIN: float = 83.0   # attacking penalty box starts at x ≈ 83
BOX_Y_MIN: float = 21.1   # top post (y decreases from bottom)
BOX_Y_MAX: float = 78.9   # bottom post


# ---------------------------------------------------------------------------
# Core zone functions
# ---------------------------------------------------------------------------


def get_zone(
    x: float,
    boundaries: ZoneBoundaries = _DEFAULT_BOUNDARIES,
) -> PitchZone:
    """Return the pitch zone for a single x-coordinate.

    Args:
        x          : Ball x-position (0–100).
        boundaries : Custom zone thresholds (optional).

    Returns:
        PitchZone enum value, or ``PitchZone.UNKNOWN`` if x is out of range.
    """
    if not (0.0 <= x <= 100.0):
        return PitchZone.UNKNOWN
    if x <= boundaries.defensive_end:
        return PitchZone.DEFENSIVE_THIRD
    if x <= boundaries.middle_end:
        return PitchZone.MIDDLE_THIRD
    return PitchZone.FINAL_THIRD


def get_half(x: float) -> PitchHalf:
    """Return which half of the pitch an event occurred in.

    Args:
        x : Ball x-position (0–100).

    Returns:
        ``PitchHalf.OWN_HALF`` if x ≤ 50, else ``PitchHalf.OPPONENT_HALF``.
    """
    return PitchHalf.OWN_HALF if x <= 50.0 else PitchHalf.OPPONENT_HALF


def is_in_penalty_box(x: float, y: float) -> bool:
    """Return True if the coordinate falls inside the attacking penalty box.

    Uses the standard Opta 100×100 scale.  The penalty box occupies
    x > 83, y in [21.1, 78.9].

    Args:
        x : Event x-position (0–100).
        y : Event y-position (0–100).

    Returns:
        bool
    """
    return x >= BOX_X_MIN and BOX_Y_MIN <= y <= BOX_Y_MAX


def zone_from_series(
    x_series: pd.Series,
    boundaries: ZoneBoundaries = _DEFAULT_BOUNDARIES,
) -> PitchZone:
    """Classify the dominant zone for a sequence of x-coordinates.

    Uses the mean x-value to represent the whole sequence.

    Args:
        x_series   : Series of x-coordinates (may contain NaN, which are dropped).
        boundaries : Custom zone thresholds (optional).

    Returns:
        PitchZone enum value for the mean position.
    """
    valid = x_series.dropna()
    if valid.empty:
        return PitchZone.UNKNOWN
    return get_zone(float(valid.mean()), boundaries)


def pitch_third_label(zone: PitchZone) -> str:
    """Human-readable label for a PitchZone."""
    return {
        PitchZone.DEFENSIVE_THIRD: "Defensive Third",
        PitchZone.MIDDLE_THIRD:    "Middle Third",
        PitchZone.FINAL_THIRD:     "Final Third",
        PitchZone.UNKNOWN:         "Unknown",
    }[zone]
