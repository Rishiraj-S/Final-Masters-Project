"""
xT predictor — grid-based expected threat.

xT(pass) = xT_grid[destination_cell] - xT_grid[origin_cell]
           clipped at 0 (threat-decreasing passes score 0, not negative).

Artifact (written by train.py):
  xt_grid.npy — (16, 12) xT value per pitch cell

Reference:
  soccermatics.readthedocs.io/en/latest/gallery/lesson4/plot_ExpectedThreat.html

KNOWN LIMITATIONS — caveat any player ranking built on this column:
  - Ball carries are NOT Opta events and are invisible. A winger who carries
    from x=60 to x=85 before crossing gets zero xT for the carry; it accrues
    to whoever passed to x=60. Ball-carrying wingers and progressive
    midfielders are systematically under-credited vs. accurate passers.
  - xT is a zone property, not action-level causation. Early passes in long
    chains are labelled with the same zone value as late passes.
"""

from pathlib import Path

import numpy as np
import pandas as pd

_MODEL_DIR = Path(__file__).resolve().parent
_xt_grid: np.ndarray | None = None


def _load() -> np.ndarray:
    global _xt_grid
    if _xt_grid is None:
        p = _MODEL_DIR / "xt_grid.npy"
        if not p.exists():
            raise FileNotFoundError(
                f"xt_grid.npy not found at {p}. Run `python xT_model/train.py` first."
            )
        _xt_grid = np.load(p)
    return _xt_grid


def _lookup(x, y) -> np.ndarray:
    grid    = _load()
    M, N    = grid.shape
    x       = np.asarray(x, dtype=float)
    y       = np.asarray(y, dtype=float)
    i       = np.clip((x / 100.0 * M).astype(int), 0, M - 1)
    j       = np.clip((y / 100.0 * N).astype(int), 0, N - 1)
    return grid[i, j]


def predict_xt(x1, y1, x2, y2) -> float | np.ndarray:
    """
    xT gained by moving the ball from (x1, y1) to (x2, y2).

    Parameters
    ----------
    x1, y1 : pass-start coordinates (0–100)
    x2, y2 : pass-end   coordinates (0–100)

    Returns
    -------
    float or numpy array — xT value(s), non-negative
    """
    x1, y1, x2, y2 = (np.atleast_1d(np.asarray(v, float)) for v in (x1, y1, x2, y2))
    xt = np.maximum(_lookup(x2, y2) - _lookup(x1, y1), 0.0)
    return xt if len(xt) > 1 else float(xt[0])


def add_xt_column(passes_df: pd.DataFrame) -> pd.DataFrame:
    """
    Add an 'xT' column to a DataFrame of pass events.

    Expects columns: x, y, Pass End X, Pass End Y
    Rows with missing coords get xT = 0.
    """
    df    = passes_df.copy()
    valid = (
        df["x"].notna() & df["y"].notna()
        & df["Pass End X"].notna() & df["Pass End Y"].notna()
    )
    df["xT"] = 0.0
    if valid.any():
        df.loc[valid, "xT"] = predict_xt(
            df.loc[valid, "x"].values,
            df.loc[valid, "y"].values,
            df.loc[valid, "Pass End X"].values,
            df.loc[valid, "Pass End Y"].values,
        )
    return df
