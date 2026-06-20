"""
Grid-based Expected Threat (xT) model.

Follows the Soccermatics approach:
  soccermatics.readthedocs.io/en/latest/gallery/lesson4/plot_ExpectedThreat.html

Each pitch cell (i, j) stores the expected threat from controlling the ball there.
Solved by the Bellman equation iterated to convergence:

  xT[i,j] = P(shoot | i,j) * P(goal | shoot, i,j)
           + P(move  | i,j) * sum_{k,l} T[i,j,k,l] * xT[k,l]

Where:
  P(shoot) = shots / (shots + passes) per cell
  P(goal)  = goals / shots per cell
  P(move)  = passes / (shots + passes) per cell
  T        = transition matrix: P(pass ends in k,l | pass starts in i,j)

NOTE: Opta event data does not include ball carries. All moves are passes.
Ball-carrying wingers and progressive midfielders will be under-credited when
this grid is used for player ranking.

Run:  python xT_model/train.py
Saves: xT_model/xt_grid.npy  — shape (M, N)
"""

import glob
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.ndimage import gaussian_filter

warnings.filterwarnings("ignore")

ROOT      = Path(__file__).resolve().parent.parent
MODEL_DIR = Path(__file__).resolve().parent

M, N = 16, 12          # grid cells along x (length) and y (width)
SHOT_TYPES = {"Goal", "Miss", "Saved Shot", "Post"}
NEEDED     = ["event_type", "x", "y", "Pass End X", "Pass End Y"]


# ── Data loading ──────────────────────────────────────────────────────────────

def load_events() -> pd.DataFrame:
    # Current data layout is data/2025-26/{Country}/{Competition}/match_event/.
    # The old data/barcelona|opposition/** paths were removed — globbing them
    # loaded zero files and silently overwrote the shipped xt_grid.npy with a
    # near-uniform useless grid.
    files = glob.glob(
        str(ROOT / "data" / "2025-26" / "**" / "match_event" / "*.parquet"),
        recursive=True,
    )
    print(f"Loading {len(files)} match files ...")
    dfs = []
    for f in files:
        try:
            dfs.append(pd.read_parquet(f, columns=NEEDED))
        except Exception:
            pass
    if not dfs:
        raise RuntimeError(
            f"No parquet files found under {ROOT / 'data' / '2025-26'}. "
            "Refusing to train on an empty set (would overwrite xt_grid.npy "
            "with a useless grid). Check the data path."
        )
    df = pd.concat(dfs, ignore_index=True)
    for col in ["x", "y", "Pass End X", "Pass End Y"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    print(f"Total events loaded: {len(df):,}")
    return df


# ── Grid helpers ──────────────────────────────────────────────────────────────

def to_cell(x, y, m=M, n=N):
    """Map (x, y) coordinates in [0, 100] to grid indices (i, j)."""
    i = np.clip((np.asarray(x, float) / 100.0 * m).astype(int), 0, m - 1)
    j = np.clip((np.asarray(y, float) / 100.0 * n).astype(int), 0, n - 1)
    return i, j


# ── Model ─────────────────────────────────────────────────────────────────────

def build_xt_grid(df: pd.DataFrame, n_iter: int = 10, smooth_sigma: float = 1.0):
    """
    Compute the xT grid from event data.

    Parameters
    ----------
    df          : event DataFrame (must contain NEEDED columns)
    n_iter      : max Bellman iterations (convergence usually within 5)
    smooth_sigma: Gaussian kernel sigma for smoothing sparse-cell noise

    Returns
    -------
    xT : (M, N) numpy array of xT values
    """
    shots  = df[df["event_type"].isin(SHOT_TYPES) & df["x"].notna() & df["y"].notna()].copy()
    passes = df[
        (df["event_type"] == "Pass")
        & df["x"].notna() & df["y"].notna()
        & df["Pass End X"].notna() & df["Pass End Y"].notna()
    ].copy()
    print(f"  Shots : {len(shots):,}   Passes : {len(passes):,}")

    # Cell indices
    si, sj = to_cell(shots["x"].values,          shots["y"].values)
    pi, pj = to_cell(passes["x"].values,          passes["y"].values)
    ei, ej = to_cell(passes["Pass End X"].values, passes["Pass End Y"].values)
    goals_mask = (shots["event_type"].values == "Goal")

    # ── Count arrays ──────────────────────────────────────────────────────────
    shot_count  = np.zeros((M, N))
    goal_count  = np.zeros((M, N))
    pass_count  = np.zeros((M, N))

    np.add.at(shot_count, (si, sj), 1)
    np.add.at(goal_count, (si[goals_mask], sj[goals_mask]), 1)
    np.add.at(pass_count, (pi, pj), 1)

    action_count = shot_count + pass_count   # total ball-in-zone actions

    # ── Probabilities (Laplace smoothing: +1 pseudocount avoids 0/0) ─────────
    shot_prob = (shot_count + 1) / (action_count + 2)   # P(shoot | in zone)
    move_prob = (pass_count + 1) / (action_count + 2)   # P(move  | in zone)
    goal_prob = (goal_count + 1) / (shot_count  + 2)    # P(goal  | shoot from zone)

    # ── Transition matrix T[i,j,k,l] ─────────────────────────────────────────
    print("  Building transition matrix ...")
    T = np.zeros((M, N, M, N))
    np.add.at(T, (pi, pj, ei, ej), 1)
    T /= np.maximum(pass_count[:, :, np.newaxis, np.newaxis], 1)

    # ── Iterative Bellman solution ────────────────────────────────────────────
    # xT[i,j] = P(shoot)*P(goal) + P(move)*sum_{k,l} T[i,j,k,l]*xT[k,l]
    xT = shot_prob * goal_prob
    print("  Iterating ...")
    for it in range(n_iter):
        xT_new = shot_prob * goal_prob + move_prob * np.einsum("ijkl,kl->ij", T, xT)
        delta   = float(np.max(np.abs(xT_new - xT)))
        xT      = xT_new
        print(f"    iter {it + 1:2d}  max_delta={delta:.2e}")
        if delta < 1e-6:
            break

    # ── Gaussian smoothing to reduce sparse-cell noise ────────────────────────
    xT = gaussian_filter(xT, sigma=smooth_sigma)
    xT = np.clip(xT, 0, None)

    print(f"\n  xT range: [{xT.min():.5f}, {xT.max():.5f}]")
    print(f"  Defensive-half mean: {xT[:M//2, :].mean():.5f}")
    print(f"  Attacking-half mean: {xT[M//2:, :].mean():.5f}")
    return xT


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    df = load_events()
    xT = build_xt_grid(df)
    out = MODEL_DIR / "xt_grid.npy"
    np.save(out, xT)
    print(f"\nSaved {out}  shape={xT.shape}")
