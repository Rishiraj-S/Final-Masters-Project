"""
time_utils.py
=============
Match-time arithmetic, window operations, and duration utilities.

All times are represented in seconds (integers) measured from kick-off.
"""

from __future__ import annotations

from typing import List

import pandas as pd


# ---------------------------------------------------------------------------
# Basic time conversions
# ---------------------------------------------------------------------------


def to_seconds(time_min: int, time_sec: int) -> int:
    """Convert minute + second within a period to total seconds.

    Args:
        time_min : Minute value (0-based or 1-based, as stored in the data).
        time_sec : Second within that minute (0–59).

    Returns:
        Total seconds as an integer.
    """
    return int(time_min) * 60 + int(time_sec)


def format_seconds(total_seconds: int) -> str:
    """Format an absolute second count as ``"MM:SS"`` for display.

    Args:
        total_seconds : Non-negative integer second count.

    Returns:
        Zero-padded ``"MM:SS"`` string.
    """
    minutes, seconds = divmod(abs(int(total_seconds)), 60)
    return f"{minutes:02d}:{seconds:02d}"


def time_diff_seconds(row_a: pd.Series, row_b: pd.Series) -> float:
    """Compute the signed time gap (seconds) between two event rows.

    Requires both rows to have an ``abs_time_sec`` column
    (added by :func:`page_utils.possession_utils.annotate_possession`).

    Args:
        row_a : Earlier event row.
        row_b : Later event row.

    Returns:
        ``row_b.abs_time_sec - row_a.abs_time_sec`` as a float.
    """
    return float(row_b["abs_time_sec"] - row_a["abs_time_sec"])


# ---------------------------------------------------------------------------
# Window-based filtering
# ---------------------------------------------------------------------------


def events_within_window(
    events_df: pd.DataFrame,
    anchor_time: int,
    window_seconds: int,
    direction: str = "forward",
) -> pd.DataFrame:
    """Filter events that fall within a time window from an anchor.

    Args:
        events_df      : DataFrame with ``abs_time_sec`` column.
        anchor_time    : Reference time in seconds.
        window_seconds : Width of the window.
        direction      : ``"forward"`` (events *after* anchor) or
                         ``"backward"`` (events *before* anchor).

    Returns:
        Filtered DataFrame (may be empty).

    Raises:
        ValueError: If ``direction`` is not ``"forward"`` or ``"backward"``.
    """
    if direction == "forward":
        mask = (events_df["abs_time_sec"] >= anchor_time) & (
            events_df["abs_time_sec"] <= anchor_time + window_seconds
        )
    elif direction == "backward":
        mask = (events_df["abs_time_sec"] >= anchor_time - window_seconds) & (
            events_df["abs_time_sec"] <= anchor_time
        )
    else:
        raise ValueError(f"direction must be 'forward' or 'backward', got {direction!r}")

    return events_df[mask].reset_index(drop=True)


def rolling_event_windows(
    events_df: pd.DataFrame,
    window_size: int,
    step: int = 1,
) -> List[pd.DataFrame]:
    """Generate sliding windows of consecutive events by row index.

    Args:
        events_df   : Sorted event DataFrame.
        window_size : Number of rows per window.
        step        : Slide increment between windows (default 1).

    Returns:
        List of DataFrame slices, each of length ``window_size``
        (the last window may be shorter if ``len(events_df) % step != 0``).
    """
    n = len(events_df)
    windows: List[pd.DataFrame] = []
    for start in range(0, max(0, n - window_size + 1), step):
        windows.append(events_df.iloc[start : start + window_size].reset_index(drop=True))
    return windows


def compute_match_duration(events_df: pd.DataFrame) -> int:
    """Return the total match duration in seconds from the events data.

    Uses the maximum ``abs_time_sec`` value.

    Args:
        events_df : Annotated events DataFrame with ``abs_time_sec``.

    Returns:
        Duration in seconds (0 if the DataFrame is empty or column missing).
    """
    if events_df.empty or "abs_time_sec" not in events_df.columns:
        return 0
    return int(events_df["abs_time_sec"].max())
