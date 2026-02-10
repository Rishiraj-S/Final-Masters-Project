"""General utility functions for Barcelona Post-Match Analysis App."""
from __future__ import annotations

import math
from typing import Optional

import numpy as np
import pandas as pd

from barcelona_postmatch_app.config import (
    BARCELONA_CODES,
    BARCELONA_NAMES,
    OPTA_X_MAX,
    OPTA_Y_MAX,
    PITCH_LENGTH,
    PITCH_WIDTH,
)


def is_barcelona(team_name: str | None, team_code: str | None = None) -> bool:
    """Check if a team identifier refers to Barcelona."""
    if team_name and team_name in BARCELONA_NAMES:
        return True
    if team_code and team_code in BARCELONA_CODES:
        return True
    return False


def opta_to_meters(x: float, y: float) -> tuple[float, float]:
    """Convert Opta 0-100 coordinates to meters on a standard pitch."""
    x_m = (x / OPTA_X_MAX) * PITCH_LENGTH
    y_m = (y / OPTA_Y_MAX) * PITCH_WIDTH
    return x_m, y_m


def meters_to_opta(x_m: float, y_m: float) -> tuple[float, float]:
    """Convert meters to Opta 0-100 coordinates."""
    x = (x_m / PITCH_LENGTH) * OPTA_X_MAX
    y = (y_m / PITCH_WIDTH) * OPTA_Y_MAX
    return x, y


def distance_opta(x1: float, y1: float, x2: float, y2: float) -> float:
    """Calculate Euclidean distance between two Opta coordinate points (in Opta units)."""
    return math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)


def distance_meters(x1: float, y1: float, x2: float, y2: float) -> float:
    """Calculate Euclidean distance in meters between two Opta coordinate points."""
    x1m, y1m = opta_to_meters(x1, y1)
    x2m, y2m = opta_to_meters(x2, y2)
    return math.sqrt((x2m - x1m) ** 2 + (y2m - y1m) ** 2)


def safe_float(val, default: float = np.nan) -> float:
    """Safely convert a value to float, handling 'N/A' and None."""
    if val is None or (isinstance(val, str) and val.strip() in ("N/A", "", "None")):
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


def safe_int(val, default: int = 0) -> int:
    """Safely convert a value to int."""
    if val is None or (isinstance(val, str) and val.strip() in ("N/A", "", "None")):
        return default
    try:
        return int(float(val))
    except (ValueError, TypeError):
        return default


def qualifier_is_set(val) -> bool:
    """Check if an Opta qualifier column value is set (not N/A)."""
    if val is None:
        return False
    if isinstance(val, str):
        return val.strip() not in ("N/A", "", "None")
    if isinstance(val, float) and np.isnan(val):
        return False
    return True


def event_minute_str(minute: int, second: int = 0) -> str:
    """Format event time as MM:SS string."""
    return f"{minute}:{second:02d}"


def timestamp_to_seconds(ts: str) -> Optional[float]:
    """Convert ISO timestamp to seconds since midnight for relative time calculations."""
    if not ts or ts == "N/A":
        return None
    try:
        dt = pd.Timestamp(ts)
        return dt.hour * 3600 + dt.minute * 60 + dt.second + dt.microsecond / 1e6
    except (ValueError, TypeError):
        return None


def get_match_minute(time_min: int, period_id: int) -> int:
    """Calculate the absolute match minute accounting for periods."""
    if period_id == 1:
        return time_min
    elif period_id == 2:
        return time_min + 45
    elif period_id == 3:
        return time_min + 90
    elif period_id == 4:
        return time_min + 105
    return time_min


def flip_coordinates(x: float, y: float) -> tuple[float, float]:
    """Flip coordinates to represent attacking from left to right."""
    return OPTA_X_MAX - x, OPTA_Y_MAX - y


def compute_xg_simple(x: float, y: float, is_header: bool = False) -> float:
    """Compute a simplified xG based on shot location.

    Uses distance and angle to goal center as primary factors.
    x,y in Opta coordinates (0-100), attacking left to right.
    """
    # Goal center at (100, 50) in Opta coords
    goal_x, goal_y = 100.0, 50.0

    dist = distance_opta(x, y, goal_x, goal_y)

    # Angle to goal posts (goal is ~7.32m wide = ~10.76 Opta units on y-axis)
    goal_width_opta = (7.32 / PITCH_WIDTH) * OPTA_Y_MAX
    half_goal = goal_width_opta / 2

    left_post_y = goal_y - half_goal
    right_post_y = goal_y + half_goal

    # Angle subtended by goal from shot position
    dx = goal_x - x
    if dx <= 0:
        return 0.0

    angle_left = math.atan2(left_post_y - y, dx)
    angle_right = math.atan2(right_post_y - y, dx)
    angle = abs(angle_right - angle_left)

    # Base xG from distance (exponential decay)
    base_xg = max(0, 0.9 * math.exp(-0.05 * dist))

    # Adjust for angle
    angle_factor = min(1.0, angle / (math.pi / 4))
    xg = base_xg * angle_factor

    # Header penalty
    if is_header:
        xg *= 0.7

    return min(1.0, max(0.0, xg))
