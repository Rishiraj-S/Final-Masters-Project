"""
xg_utils.py
===========
Bridge between Opta event data and the trained XGBoost xG model.

The Opta event parquets store qualifier values as human-readable column names
(e.g. 'Head', 'Right footed', 'Regular play') derived from opta_qualifier_types.csv.
This module maps those columns to the feature format XGPredictor expects, then
runs batch inference.

Public API
----------
    add_xg_column(shots_df) -> pd.DataFrame
        Accepts any Opta shot event DataFrame and returns a copy with an 'xg'
        column added.  Penalties and direct free kicks get NaN (excluded from
        training).  Errors per-row are caught silently and also produce NaN.

The predictor is loaded once (lazy singleton) so the model weights are only
read from disk on the first call, not on every page load.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from pathlib import Path

# ── Singleton predictor ───────────────────────────────────────────────────────
# Loaded lazily on the first call to add_xg_column().
# This avoids importing XGPredictor (and therefore xgboost) at module import
# time, which would slow down the Dash app startup.
_predictor = None


def _get_predictor():
    global _predictor
    if _predictor is None:
        from xg_model.predictor import XGPredictor
        model_dir = Path(__file__).parent.parent / 'xg_model'
        _predictor = XGPredictor(model_dir)
    return _predictor


# ── Goal geometry (Opta 0-100 pitch) ─────────────────────────────────────────
# Goal is at x = 100.  Pitch width ≈ 68 m → goal width 7.32 m = 10.76 Opta units.
# Posts sit at y = 50 ± 5.38 = 44.62 and 55.38.
_GOAL_X      = 100.0
_GOAL_Y_LOW  = 44.62   # near post (y < 50)
_GOAL_Y_HIGH = 55.38   # far  post (y > 50)

# Period id → period name string (matches training)
_PERIOD_MAP = {
    1: 'First Half',
    2: 'Second Half',
    3: 'Extra Time First Half',
    4: 'Extra Time Second Half',
}

# Qualifier values that mean "not present" in Opta data
_ABSENT = {'N/A', '', 'nan', 'None', 'none'}


def _present(val) -> bool:
    """Return True if a qualifier column value means the qualifier is present."""
    return val is not None and str(val).strip() not in _ABSENT


def _flag(row, *cols: str) -> int:
    """Return 1 if any of the named qualifier columns is present, else 0."""
    return 1 if any(_present(row.get(c)) for c in cols) else 0


# ── Core row mapper ───────────────────────────────────────────────────────────

def _row_to_shot_dict(row) -> dict | None:
    """
    Map a single Opta shot event row to the dict format XGPredictor expects.

    Returns None for shots excluded from the model:
      - Penalties         (qualifier 'Penalty')
      - Direct free kicks (qualifier 'Free kick')

    Qualifier column names come from opta_qualifier_types.csv qualifierTypeName.
    """
    # Exclude shot types the model was not trained on
    if _present(row.get('Penalty')) or _present(row.get('Free kick')):
        return None

    x = float(row.get('x') or 0)
    y = float(row.get('y') or 0)

    # ── Spatial features ─────────────────────────────────────────────────────
    dx = _GOAL_X - x
    distance = float(np.sqrt(dx ** 2 + (50.0 - y) ** 2))

    # Angle subtended by the goal posts at the shot location (radians).
    # Formula: |arctan2(post_high - y, dx) - arctan2(post_low - y, dx)|
    # Returns 0 when the shot is behind or level with the goal line.
    if dx > 0:
        angle = float(abs(
            np.arctan2(_GOAL_Y_HIGH - y, dx) -
            np.arctan2(_GOAL_Y_LOW  - y, dx)
        ))
    else:
        angle = 0.0

    # ── Body part ─────────────────────────────────────────────────────────────
    # Opta qualifier 15 = Head, 111 = Diving Header, 20 = Right footed,
    # 72 = Left footed, 21 = Other body part.
    head       = _flag(row, 'Head', 'Diving Header')
    right_foot = _flag(row, 'Right footed')
    left_foot  = _flag(row, 'Left footed')
    other      = _flag(row, 'Other body part')
    # If Opta has not tagged a body part, default to right foot (most common)
    if not (head or right_foot or left_foot or other):
        right_foot = 1

    # ── Pattern of play ───────────────────────────────────────────────────────
    # Opta qualifier IDs: 22=Regular play, 23=Fast break, 24=Set piece,
    # 25=From corner, 96=Corner situation, 160=Throw In set piece.
    # Qualifier 26=Free kick (direct FK) is EXCLUDED from model.
    regular     = _flag(row, 'Regular play')
    fast_break  = _flag(row, 'Fast break')
    set_piece   = _flag(row, 'Set piece')
    from_corner = _flag(row, 'From corner')
    corner_sit  = _flag(row, 'Corner situation')
    throw_in    = _flag(row, 'Throw In set piece')
    # If no pattern qualifier is tagged, default to regular play
    if not (regular or fast_break or set_piece or from_corner or corner_sit or throw_in):
        regular = 1

    # ── Context ───────────────────────────────────────────────────────────────
    # Opta qualifier 29 = Assisted (on the shot), 215 = Individual Play
    assisted   = _flag(row, 'Assisted')
    individual = _flag(row, 'Individual Play')

    # ── Time / period ─────────────────────────────────────────────────────────
    time_min    = float(row.get('time_min') or 0)
    period_id   = int(float(row.get('period_id') or 1))
    period_name = _PERIOD_MAP.get(period_id, 'First Half')

    return {
        'x':                       x,
        'y':                       y,
        'distance_to_goal':        distance,
        'angle_to_goal':           angle,
        'body_part_head':          head,
        'body_part_right_foot':    right_foot,
        'body_part_left_foot':     left_foot,
        'body_part_other':         other,
        'pattern_regular_play':    regular,
        'pattern_fast_break':      fast_break,
        'pattern_set_piece':       set_piece,
        'pattern_from_corner':     from_corner,
        'pattern_corner_situation': corner_sit,
        'pattern_throw_in_set_piece': throw_in,
        'is_assisted':             assisted,
        'is_individual_play':      individual,
        'time_min':                time_min,
        'period_name':             period_name,
        'shot_zone':               None,   # inferred from (x, y) by XGPredictor
    }


# ── Public API ────────────────────────────────────────────────────────────────

def add_xg_column(shots_df: pd.DataFrame) -> pd.DataFrame:
    """
    Add an 'xg' column to a DataFrame of Opta shot events.

    Uses batch prediction (one XGBoost forward pass for the whole DataFrame)
    so it is efficient even for a full season of shots.

    Parameters
    ----------
    shots_df : pd.DataFrame
        Any Opta event DataFrame filtered to shot events.  Expected columns
        include x, y, period_id, time_min, and the shot qualifier columns
        (Head, Right footed, Regular play, etc.).

    Returns
    -------
    pd.DataFrame
        A copy of shots_df with an additional 'xg' column (float, 0–1).
        Penalties and direct free kicks get NaN.
        Rows that fail to produce a prediction also get NaN.
    """
    if shots_df.empty:
        result = shots_df.copy()
        result['xg'] = pd.Series(dtype=float)
        return result

    # Build a shot dict for every row (None = excluded from model)
    shot_dicts = []
    for _, row in shots_df.iterrows():
        try:
            shot_dicts.append(_row_to_shot_dict(row))
        except Exception:
            shot_dicts.append(None)

    # Separate valid shots from excluded ones
    valid_dicts = [d for d in shot_dicts if d is not None]

    try:
        if valid_dicts:
            predictor = _get_predictor()
            xg_preds  = predictor.predict_batch(valid_dicts)
        else:
            xg_preds = []
    except Exception:
        # If the model fails entirely, return NaN for all
        result = shots_df.copy()
        result['xg'] = np.nan
        return result

    # Reassemble: NaN for excluded, predicted value for valid
    xg_values = np.full(len(shots_df), np.nan)
    pred_cursor = 0
    for i, d in enumerate(shot_dicts):
        if d is not None:
            xg_values[i] = xg_preds[pred_cursor]
            pred_cursor += 1

    result = shots_df.copy()
    result['xg'] = xg_values
    return result
