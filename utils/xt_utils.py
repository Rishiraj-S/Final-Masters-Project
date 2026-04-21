"""
xt_utils.py
===========
Bridge between Opta event data and the grid-based xT model.

Public API
----------
    add_xt_column(passes_df) -> pd.DataFrame
        Accepts any Opta pass event DataFrame and returns a copy with an 'xT'
        column added.  Rows with missing coordinates get xT = 0.

The xT grid is loaded once (lazy singleton) so the .npy file is only read on
the first call, not on every page load.

IMPORTANT — player ranking caveat
----------------------------------
Ball carries are NOT recorded as Opta events.  A winger who carries from
x=60 to x=85 before crossing gets zero xT for the carry; it accrues to
whoever passed to x=60.  Ball-carrying wingers and progressive midfielders
are systematically under-credited versus accurate passers.  Caveat any
per-player xT ranking built on this column.
"""

from __future__ import annotations

import pandas as pd


def add_xt_column(passes_df: pd.DataFrame) -> pd.DataFrame:
    """
    Add an 'xT' column to a DataFrame of Opta pass events.

    Parameters
    ----------
    passes_df : pd.DataFrame
        Any Opta event DataFrame filtered to pass events.  Expected columns:
        x, y, Pass End X, Pass End Y.

    Returns
    -------
    pd.DataFrame
        A copy of passes_df with an additional 'xT' column (float, ≥ 0).
        Rows with missing coordinates get xT = 0.
    """
    from xT_model.predictor import add_xt_column as _add_xt
    return _add_xt(passes_df)
