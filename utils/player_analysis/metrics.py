"""
Player metric computation and rating engine for CuléVision.

Adapted from player_analysis_engine.py to work with the project's
Opta event-parquet data format (events DataFrame) rather than Opta Excel files.

Key functions
-------------
compute_player_stats(events)
    Compute per-player stat dict from a filtered events DataFrame.

get_player_percentiles(player_stats, all_peer_stats)
    Return {metric_key: percentile_0_to_100} for every stat key.

get_player_ratings(player_stats, all_peer_stats)
    Return A/B/C/D letter grades and percentiles for Attack, Possession,
    Defense, and Overall dimensions.
"""

from __future__ import annotations

import pandas as pd
from scipy.stats import percentileofscore

from utils.event_utils import (
    get_passes, get_goals, get_shots, get_shots_on_target,
    get_goal_assists, get_key_passes,
    get_take_ons, get_aerials,
    get_tackles, get_interceptions, get_ball_recoveries, get_clearances,
)


# ---------------------------------------------------------------------------
# Metric definitions per role
# Each entry is a list of (display_label, stat_key) pairs.
# ---------------------------------------------------------------------------

# Attacking / possession metrics shown on the first pizza plot
POSITION_PIZZA_ATT: dict[str, list[tuple[str, str]]] = {
    "GK": [
        ("Pass Acc %",     "pass_acc"),
        ("Clearances/App", "clearances_app"),
        ("Recoveries/App", "recoveries_app"),
        ("Aerial Win %",   "aerial_win_pct"),
        ("Key Passes/App", "key_passes_app"),
    ],
    "CB": [
        ("Pass Acc %",     "pass_acc"),
        ("Goals/App",      "goals_app"),
        ("Assists/App",    "assists_app"),
        ("Aerial Win %",   "aerial_win_pct"),
        ("Key Passes/App", "key_passes_app"),
    ],
    "FB": [
        ("Pass Acc %",     "pass_acc"),
        ("Take On %",      "takeon_pct"),
        ("Key Passes/App", "key_passes_app"),
        ("Assists/App",    "assists_app"),
        ("Goals/App",      "goals_app"),
    ],
    "DM": [
        ("Pass Acc %",     "pass_acc"),
        ("Key Passes/App", "key_passes_app"),
        ("Take On %",      "takeon_pct"),
        ("Goals/App",      "goals_app"),
        ("Assists/App",    "assists_app"),
    ],
    "CM": [
        ("Pass Acc %",     "pass_acc"),
        ("Key Passes/App", "key_passes_app"),
        ("Take On %",      "takeon_pct"),
        ("Goals/App",      "goals_app"),
        ("Assists/App",    "assists_app"),
    ],
    "AM": [
        ("Pass Acc %",     "pass_acc"),
        ("Key Passes/App", "key_passes_app"),
        ("Goals/App",      "goals_app"),
        ("Assists/App",    "assists_app"),
        ("Shots/App",      "shots_app"),
    ],
    "Winger": [
        ("Goals/App",      "goals_app"),
        ("Assists/App",    "assists_app"),
        ("Take On %",      "takeon_pct"),
        ("Key Passes/App", "key_passes_app"),
        ("Shots/App",      "shots_app"),
    ],
    "ST": [
        ("Goals/App",      "goals_app"),
        ("Shots/App",      "shots_app"),
        ("Shot on Tgt %",  "shot_acc"),
        ("Assists/App",    "assists_app"),
        ("Key Passes/App", "key_passes_app"),
    ],
}

# Defending metrics shown on the second pizza plot
POSITION_PIZZA_DEF: dict[str, list[tuple[str, str]]] = {
    "GK": [
        ("Tackles/App",    "tackles_app"),
        ("Intercepts/App", "intercepts_app"),
        ("Aerial Win %",   "aerial_win_pct"),
        ("Clearances/App", "clearances_app"),
        ("Recoveries/App", "recoveries_app"),
    ],
    "CB": [
        ("Tackles/App",    "tackles_app"),
        ("Intercepts/App", "intercepts_app"),
        ("Clearances/App", "clearances_app"),
        ("Aerial Win %",   "aerial_win_pct"),
        ("Recoveries/App", "recoveries_app"),
    ],
    "FB": [
        ("Tackles/App",    "tackles_app"),
        ("Intercepts/App", "intercepts_app"),
        ("Clearances/App", "clearances_app"),
        ("Aerial Win %",   "aerial_win_pct"),
        ("Recoveries/App", "recoveries_app"),
    ],
    "DM": [
        ("Tackles/App",    "tackles_app"),
        ("Intercepts/App", "intercepts_app"),
        ("Aerial Win %",   "aerial_win_pct"),
        ("Clearances/App", "clearances_app"),
        ("Recoveries/App", "recoveries_app"),
    ],
    "CM": [
        ("Tackles/App",    "tackles_app"),
        ("Intercepts/App", "intercepts_app"),
        ("Recoveries/App", "recoveries_app"),
        ("Clearances/App", "clearances_app"),
        ("Aerial Win %",   "aerial_win_pct"),
    ],
    "AM": [
        ("Tackles/App",    "tackles_app"),
        ("Intercepts/App", "intercepts_app"),
        ("Recoveries/App", "recoveries_app"),
        ("Take On %",      "takeon_pct"),
        ("Pass Acc %",     "pass_acc"),
    ],
    "Winger": [
        ("Tackles/App",    "tackles_app"),
        ("Intercepts/App", "intercepts_app"),
        ("Recoveries/App", "recoveries_app"),
        ("Pass Acc %",     "pass_acc"),
        ("Aerial Win %",   "aerial_win_pct"),
    ],
    "ST": [
        ("Aerial Win %",   "aerial_win_pct"),
        ("Tackles/App",    "tackles_app"),
        ("Intercepts/App", "intercepts_app"),
        ("Recoveries/App", "recoveries_app"),
        ("Take On %",      "takeon_pct"),
    ],
}

# Stat keys contributing to each rating dimension
_RATING_KEYS: dict[str, list[str]] = {
    "attack":     ["goals_app", "shots_app", "shot_acc", "assists_app", "key_passes_app"],
    "possession": ["pass_acc", "takeon_pct", "key_passes_app"],
    "defense":    ["tackles_app", "intercepts_app", "recoveries_app", "clearances_app", "aerial_win_pct"],
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _assign_letter(percentile: float) -> str:
    if percentile > 75:
        return "A"
    elif percentile > 50:
        return "B"
    elif percentile > 25:
        return "C"
    return "D"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def compute_player_stats(events: pd.DataFrame) -> dict | None:
    """
    Compute a stat dict for a single player from their events DataFrame.

    Parameters
    ----------
    events : pd.DataFrame
        All events for one player (already filtered to that player).

    Returns
    -------
    dict with keys: apps, goals_app, shots_app, shot_acc, assists_app,
        key_passes_app, pass_acc, takeon_pct, aerial_win_pct,
        tackles_app, intercepts_app, recoveries_app, clearances_app.
    None if the player has no appearances.
    """
    if events is None or events.empty:
        return None

    apps = int(events["match_id"].nunique())
    if apps == 0:
        return None

    def _per_app(n: int) -> float:
        return round(n / apps, 3)

    # Passes
    pass_rows = get_passes(events)
    n_passes  = len(pass_rows)
    pass_acc  = round(pass_rows["outcome"].eq(1).sum() / max(n_passes, 1) * 100, 1)

    # Goals
    goals = len(get_goals(events))

    # Shots
    shots           = len(get_shots(events))
    shots_on_target = len(get_shots_on_target(events))
    shot_acc        = round(shots_on_target / max(shots, 1) * 100, 1)

    # Assists and key passes via canonical Assist qualifier encoding
    assists    = len(get_goal_assists(events))
    key_passes = len(get_key_passes(events))

    # Take-ons
    takeon_rows = get_take_ons(events)
    takeon_att  = len(takeon_rows)
    takeon_succ = int(takeon_rows["outcome"].eq(1).sum()) if takeon_att > 0 else 0
    takeon_pct  = round(takeon_succ / max(takeon_att, 1) * 100, 1)

    # Aerial duels
    aerial_rows    = get_aerials(events)
    aerial_att     = len(aerial_rows)
    aerial_won     = int(aerial_rows["outcome"].eq(1).sum()) if aerial_att > 0 else 0
    aerial_win_pct = round(aerial_won / max(aerial_att, 1) * 100, 1)

    # Defensive actions
    tackles    = len(get_tackles(events))
    intercepts = len(get_interceptions(events))
    recoveries = len(get_ball_recoveries(events))
    clearances = len(get_clearances(events))

    return {
        "apps":           apps,
        "goals_app":      _per_app(goals),
        "shots_app":      _per_app(shots),
        "shot_acc":       shot_acc,
        "assists_app":    _per_app(assists),
        "key_passes_app": _per_app(key_passes),
        "pass_acc":       pass_acc,
        "takeon_pct":     takeon_pct,
        "aerial_win_pct": aerial_win_pct,
        "tackles_app":    _per_app(tackles),
        "intercepts_app": _per_app(intercepts),
        "recoveries_app": _per_app(recoveries),
        "clearances_app": _per_app(clearances),
    }


def get_player_percentiles(
    player_stats: dict,
    all_peer_stats: list[dict],
) -> dict[str, int]:
    """
    Return {metric_key: percentile (0-100)} for every key in player_stats,
    ranked against all_peer_stats (positional peers, excluding the player).

    The player is included in the pool for the rank calculation.
    """
    if not all_peer_stats:
        return {k: 50 for k in player_stats if k != "apps"}

    pool = all_peer_stats + [player_stats]
    result: dict[str, int] = {}

    for key in player_stats:
        if key == "apps":
            continue
        values     = [s.get(key, 0) for s in pool]
        player_val = player_stats.get(key, 0)
        pct        = percentileofscore(values, player_val, kind="rank")
        result[key] = round(pct)

    return result


def compute_5d_scores(
    player_stats: dict,
    all_peer_stats: list[dict],
    role: str,
) -> dict[str, int]:
    """
    Compute 5-dimension percentile scores for a player vs their positional peers.

    Weights for Attack and Defense are loaded from the Wyscout position files
    (assets/wyscout_weights/).  Technical and Physical use equal weights.
    Overall is the simple average of all four dimensions.

    Returns
    -------
    dict with keys: attack, defense, technical, physical, overall (all 0-100).
    """
    from utils.player_analysis.wyscout_weights import (
        get_attack_weights,
        get_defense_weights,
        ATTACK_METRICS,
        DEFENSE_METRICS,
        TECHNICAL_METRICS,
        PHYSICAL_METRICS,
    )

    pool = all_peer_stats + [player_stats]

    def _weighted_score(stats: dict, metrics: list[str], weights: dict[str, float]) -> float:
        total_w = sum(weights.get(m, 0.0) for m in metrics)
        if total_w == 0:
            return 0.0
        return sum(stats.get(m, 0.0) * weights.get(m, 0.0) for m in metrics) / total_w

    def _dim_pct(metrics: list[str], weights: dict[str, float] | None = None) -> int:
        if weights is None:
            weights = {m: 1.0 for m in metrics}
        scores  = [_weighted_score(s, metrics, weights) for s in pool]
        p_score = _weighted_score(player_stats, metrics, weights)
        return round(percentileofscore(scores, p_score, kind="rank"))

    att_w = get_attack_weights(role)
    def_w = get_defense_weights(role)

    attack    = _dim_pct(ATTACK_METRICS,    att_w)
    defense   = _dim_pct(DEFENSE_METRICS,   def_w)
    technical = _dim_pct(TECHNICAL_METRICS)
    physical  = _dim_pct(PHYSICAL_METRICS)
    overall   = round((attack + defense + technical + physical) / 4)

    return {
        "attack":    attack,
        "defense":   defense,
        "technical": technical,
        "physical":  physical,
        "overall":   overall,
    }


def get_player_ratings(
    player_stats: dict,
    all_peer_stats: list[dict],
) -> dict:
    """
    Compute A/B/C/D letter grades and percentile ranks for attack,
    possession, defense, and overall performance.

    Returns
    -------
    dict with structure::

        {
            'attack':     {'letter': 'A', 'percentile': 82},
            'possession': {'letter': 'B', 'percentile': 65},
            'defense':    {'letter': 'C', 'percentile': 35},
            'overall':    {'letter': 'B', 'percentile': 61},
            'n_peers':    15,
        }
    """
    pool = all_peer_stats + [player_stats]

    def _dim_score(s: dict, keys: list[str], maxvals: dict) -> float:
        """Normalised average score for a player across a set of metric keys."""
        vals = [s.get(k, 0) / max(maxvals.get(k, 1e-9), 1e-9) for k in keys]
        return sum(vals) / len(vals)

    ratings: dict = {}
    dim_percentiles: list[float] = []

    for dim, keys in _RATING_KEYS.items():
        maxvals = {k: max(s.get(k, 0) for s in pool) for k in keys}
        scores  = [_dim_score(s, keys, maxvals) for s in pool]
        player_score = _dim_score(player_stats, keys, maxvals)
        pct = round(percentileofscore(scores, player_score, kind="rank"))
        ratings[dim] = {"letter": _assign_letter(pct), "percentile": pct}
        dim_percentiles.append(pct)

    overall_pct = round(sum(dim_percentiles) / len(dim_percentiles))
    ratings["overall"] = {"letter": _assign_letter(overall_pct), "percentile": overall_pct}
    ratings["n_peers"] = len(pool)

    return ratings
