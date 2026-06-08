"""
page_utils.event_filters
========================
Shared event-type constants and filtering helpers used across match, team,
opposition, and player analysis tabs.

Previously each tab module defined its own copies of _SHOT_TYPES,
_DEF_ACTION_TYPES, _DEF_COLORS, and its own period-filtering inline logic.
All of those should now import the canonical versions from here.
"""

from __future__ import annotations

import pandas as pd

# ---------------------------------------------------------------------------
# Shot event types
# ---------------------------------------------------------------------------

#: All Opta event_type values that represent a shot.
SHOT_TYPES: frozenset[str] = frozenset({
    'Miss', 'Saved Shot', 'Goal', 'Post',
})

#: Plotly marker colour per shot outcome (attacker's perspective).
SHOT_OUTCOME_COLOR: dict[str, str] = {
    'Goal':       '#51cf66',
    'Saved Shot': '#339af0',
    'Miss':       '#ff6b6b',
    'Post':       '#ffd43b',
}

#: Plotly marker symbol per shot outcome.
SHOT_OUTCOME_SYMBOL: dict[str, str] = {
    'Goal':       'star',
    'Saved Shot': 'circle',
    'Miss':       'x',
    'Post':       'diamond',
}

# ---------------------------------------------------------------------------
# Defensive action event types
# ---------------------------------------------------------------------------

#: Opta event_type values that represent a defensive action.
DEF_ACTION_TYPES: frozenset[str] = frozenset({
    'Tackle', 'Interception', 'Ball recovery', 'Clearance',
})

#: Plotly marker colour per defensive action type.
DEF_COLORS: dict[str, str] = {
    'Tackle':        '#4dabf7',
    'Interception':  '#51cf66',
    'Ball recovery': '#ffd43b',
    'Clearance':     '#ff922b',
}

# ---------------------------------------------------------------------------
# Period filtering helpers
# ---------------------------------------------------------------------------

def filter_by_period(
    events: pd.DataFrame,
    period: int | None,
) -> pd.DataFrame:
    """
    Return events filtered to a specific period_id, or the full DataFrame.

    Args:
        events: Events DataFrame that may contain a 'period_id' column.
        period: 1 (first half), 2 (second half), or None (all periods).

    Returns:
        Filtered (or unchanged) DataFrame.  Never raises — if 'period_id'
        is absent and period is not None, an empty frame is returned.
    """
    if period is None:
        return events
    if 'period_id' not in events.columns:
        return events.iloc[:0]
    return events[events['period_id'] == period]


def split_by_halves(
    events: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Split an events DataFrame into full-match, first-half, and second-half.

    Returns:
        (full, h1, h2) — all three are views/slices of the original frame.
        If 'period_id' is absent, h1 and h2 are empty frames.
    """
    if 'period_id' not in events.columns:
        empty = events.iloc[:0]
        return events, empty, empty

    h1 = events[events['period_id'] == 1]
    h2 = events[events['period_id'] == 2]
    return events, h1, h2
