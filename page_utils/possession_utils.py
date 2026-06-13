"""
possession_utils.py
===================
Utilities for tracking possession ownership, detecting possession changes,
and computing ball-progression metrics from Opta event DataFrames.

Possession Model
----------------
Each event's ``team_name`` is used as the primary possession indicator.
Neutral / administrative events (fouls, offsides, cards, etc.) are skipped
by forward-filling from the last known possessing team.  Contested events
(aerials, 50/50 challenges) are flagged separately and do NOT clear the
possession state.

Coordinate Assumptions
----------------------
``x`` runs 0 (own goal) → 100 (opponent goal) from the performing team's
perspective.  Vertical speed is therefore a positive number for forward
progression.
"""

from __future__ import annotations

from typing import Set

import pandas as pd


# ---------------------------------------------------------------------------
# Event-type classification sets
# ---------------------------------------------------------------------------

# Events that always hand possession to the performing team.
POSSESSION_TAKING_EVENT_TYPES: Set[str] = {
    "Ball recovery",
    "Interception",
    "Goal kick",
    "Keeper pick-up",
    "Cross not claimed",
}

# Events where a *successful* outcome (outcome == 1) means possession is taken.
CONDITIONAL_POSSESSION_TAKING: Set[str] = {
    "Tackle",
    "Clearance",
}

# Events representing an active contest — no clear possessor.
CONTESTED_EVENT_TYPES: Set[str] = {
    "Aerial",
    "Challenge",
    "50/50",
}

# Administrative / neutral events that do NOT change or establish possession.
# Possession is forward-filled through these rows.
NEUTRAL_EVENT_TYPES: Set[str] = {
    "Foul",
    "Offside",
    "Card",
    "Team set up",
    "Team setp up",   # Opta typo — kept intentionally to match data
    "Period",
    "Start",
    "End",
    "Deleted event",
    "Referee ball drop",
    "Blocked shot",   # The blocker doesn't necessarily have possession
}

# Period IDs that are NOT regular match play.
IGNORE_PERIOD_IDS: Set[int] = {16, 5, 6}   # 16 = team setup; 5/6 = shootout


# ---------------------------------------------------------------------------
# Time helpers
# ---------------------------------------------------------------------------


def compute_absolute_time(row: pd.Series) -> int:
    """Convert a single event row to absolute match time in seconds.

    Period 1 events start at 0 s; period 2 events start at 45 * 60 = 2700 s.
    Extra-time periods (3, 4) are offset by 90 and 105 minutes respectively.

    Args:
        row : A row from the events DataFrame (must have ``period_id``,
              ``time_min``, ``time_sec``).

    Returns:
        Absolute time in seconds (int).
    """
    period_offsets = {1: 0, 2: 45 * 60, 3: 90 * 60, 4: 105 * 60}
    offset = period_offsets.get(int(row["period_id"]), 0)
    return offset + int(row["time_min"]) * 60 + int(row["time_sec"])


# ---------------------------------------------------------------------------
# Possession annotation
# ---------------------------------------------------------------------------


def annotate_possession(events_df: pd.DataFrame) -> pd.DataFrame:
    """Annotate events with possession owner, absolute time, and contested flag.

    Adds the following columns to a copy of the input DataFrame:
        abs_time_sec    (int)  : Absolute match time in seconds.
        possession_team (str)  : Team currently in possession (forward-filled
                                 through neutral events; empty string if unknown).
        is_contested    (bool) : True when the event is an aerial / 50-50.

    The returned DataFrame:
      * Excludes non-play periods (team-setup, shootout).
      * Is sorted chronologically by (period_id, abs_time_sec, event_id).

    Args:
        events_df : Raw match events from ``get_match_events()``.

    Returns:
        Annotated copy of the DataFrame.
    """
    df = events_df.copy()
    df = df[~df["period_id"].isin(IGNORE_PERIOD_IDS)].reset_index(drop=True)
    df["abs_time_sec"] = df.apply(compute_absolute_time, axis=1)
    df = df.sort_values(
        ["period_id", "abs_time_sec", "event_id"]
    ).reset_index(drop=True)

    # Mark contested events before touching possession_team
    df["is_contested"] = df["event_type"].isin(CONTESTED_EVENT_TYPES)

    # Raw possession: use team_name except for neutral events (set to NaN)
    df["possession_team"] = df["team_name"].where(
        ~df["event_type"].isin(NEUTRAL_EVENT_TYPES), other=pd.NA
    )

    # Forward-fill so neutral events inherit the previous possessor
    df["possession_team"] = df["possession_team"].ffill().fillna("")

    return df


# ---------------------------------------------------------------------------
# Possession-sequence helpers
# ---------------------------------------------------------------------------


def compute_vertical_speed(events_subset: pd.DataFrame) -> float:
    """Compute the mean rate of forward progression (Δx per second).

    A positive value indicates net forward movement toward the opponent goal.
    Returns 0.0 if the subset has fewer than 2 events or no time elapsed.

    Args:
        events_subset : Subset of the annotated events DataFrame for a
                        single possession sequence.  Must contain ``x`` and
                        ``abs_time_sec`` columns.

    Returns:
        Vertical speed as a float (x-units per second).
    """
    valid = events_subset.dropna(subset=["x", "abs_time_sec"])
    if len(valid) < 2:
        return 0.0

    dx = float(valid["x"].max() - valid["x"].min())
    dt = float(valid["abs_time_sec"].max() - valid["abs_time_sec"].min())
    return dx / dt if dt > 0.0 else 0.0


def is_stable_possession(
    events_subset: pd.DataFrame,
    min_events: int = 3,
) -> bool:
    """Return True if the subset represents a stable possession sequence.

    A sequence is considered *stable* if it contains at least ``min_events``
    non-neutral, non-contested events by the same team.

    Args:
        events_subset : Subset of the annotated events DataFrame.
        min_events    : Minimum number of qualifying events (default: 3).

    Returns:
        bool
    """
    if events_subset.empty:
        return False

    exclude = NEUTRAL_EVENT_TYPES | CONTESTED_EVENT_TYPES
    qualifying = events_subset[~events_subset["event_type"].isin(exclude)]
    return len(qualifying) >= min_events


def detect_turnovers(
    events_df: pd.DataFrame,
    focus_team: str,
) -> pd.DataFrame:
    """Return rows where the focus team loses possession.

    A turnover is defined as:
      * A failed pass (``event_type == "Pass"`` and ``outcome == 0``) by the
        focus team.
      * A successful tackle against the focus team (``event_type == "Tackle"``
        and ``outcome == 1`` by the *opponent*).
      * Any possession_team transition from focus_team → opponent.

    Args:
        events_df  : Annotated events (output of ``annotate_possession``).
        focus_team : The team whose turnovers are counted.

    Returns:
        DataFrame rows representing turnover events.
    """
    df = events_df.copy()

    # Criterion 1: failed passes by the focus team
    failed_passes = (
        (df["team_name"] == focus_team)
        & (df["event_type"] == "Pass")
        & (df["outcome"] == 0)
    )

    # Criterion 2: successful tackles against the focus team
    opponent_tackles = (
        (df["team_name"] != focus_team)
        & (df["event_type"] == "Tackle")
        & (df["outcome"] == 1)
        & (df["possession_team"] == focus_team)
    )

    return df[failed_passes | opponent_tackles].reset_index(drop=True)
