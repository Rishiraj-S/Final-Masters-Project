"""
Wyscout position-based metric weights for CuléVision's 5-dimension performance radar.

Weights are derived from the position-specific Excel files in assets/wyscout_things/,
translated from Spanish to English.  Each Excel file encodes per-position importance
scores (0-100) for two axes:
  column "0"   -> offensive / attack relevance
  column "0.1" -> defensive relevance
"""

from __future__ import annotations

from pathlib import Path
import pandas as pd

_ASSETS_DIR = Path(__file__).parent.parent.parent / "assets" / "wyscout_things"

# Role -> Excel file stem
_ROLE_TO_FILE: dict[str, str] = {
    "GK":     "variables_wyscout_portero_og",
    "CB":     "variables_wyscout_defensa",
    "FB":     "variables_wyscout_lateral",
    "DM":     "variables_wyscout_centrocampista_defensivo",
    "CM":     "variables_wyscout_centrocampista_ofensivo",
    "AM":     "variables_wyscout_centrocampista_ofensivo",
    "Winger": "variables_wyscout_extremo",
    "ST":     "variables_wyscout_delantero_centro_og",
}

# Spanish metric name in the Excel Jugador column -> our internal stat key
_SPANISH_TO_METRIC: dict[str, str] = {
    "Goles":                              "goals_app",
    "Remates/90":                         "shots_app",
    "Tiros a la portería, %":             "shot_acc",
    "Asistencias/90":                     "assists_app",
    "Jugadas claves/90":                  "key_passes_app",
    "Precisión pases, %":                 "pass_acc",
    "Regates realizados, %":              "takeon_pct",
    "Duelos aéreos ganados, %":           "aerial_win_pct",
    "Duelos defensivos/90":               "tackles_app",
    "Interceptaciones/90":                "intercepts_app",
    "Acciones defensivas realizadas/90":  "recoveries_app",
    "Tiros interceptados/90":             "clearances_app",
}

# Metric groups for each of the 5 radar dimensions
ATTACK_METRICS:    list[str] = ["goals_app", "shots_app", "shot_acc", "assists_app", "key_passes_app"]
DEFENSE_METRICS:   list[str] = ["tackles_app", "intercepts_app", "recoveries_app", "clearances_app", "aerial_win_pct"]
TECHNICAL_METRICS: list[str] = ["pass_acc", "takeon_pct", "key_passes_app", "shot_acc"]
PHYSICAL_METRICS:  list[str] = ["aerial_win_pct", "tackles_app"]

# English labels and descriptions for each dimension
DIMENSION_INFO: dict[str, tuple[str, str]] = {
    "Attack":    (
        "Scoring & Creativity",
        "Goals, shots, shot accuracy, assists and key passes — "
        "weighted by position-specific importance",
    ),
    "Defense":   (
        "Defensive Contribution",
        "Tackles, interceptions, recoveries, clearances and aerial win rate — "
        "weighted by position-specific importance",
    ),
    "Technical": (
        "Technical Quality",
        "Pass accuracy, dribble success rate, key passes and shot accuracy on target — "
        "equal weight across positions",
    ),
    "Physical":  (
        "Physical Duels",
        "Aerial duel win rate and defensive duel frequency — "
        "proxy for dominance in physical contests",
    ),
    "Overall":   (
        "Composite Score",
        "Simple average of Attack, Defense, Technical and Physical percentile scores",
    ),
}

# Internal cache: role -> {metric_key: (attack_w, defense_w)}
_cache: dict[str, dict[str, tuple[float, float]]] = {}


def _load_role_weights(role: str) -> dict[str, tuple[float, float]]:
    """Read the Excel file for a role and return {metric_key: (attack_w, defense_w)}."""
    if role in _cache:
        return _cache[role]

    fname = _ROLE_TO_FILE.get(role)
    if not fname:
        _cache[role] = {}
        return {}

    fpath = _ASSETS_DIR / f"{fname}.xlsx"
    if not fpath.exists():
        _cache[role] = {}
        return {}

    df = pd.read_excel(fpath)
    # Columns: Jugador (col 0), attack weight (col 1), defense weight (col 2)
    col_metric  = df.columns[0]
    col_attack  = df.columns[1]
    col_defense = df.columns[2]

    result: dict[str, tuple[float, float]] = {}
    for _, row in df.iterrows():
        spanish = str(row[col_metric]).strip()
        if spanish in _SPANISH_TO_METRIC:
            key   = _SPANISH_TO_METRIC[spanish]
            w_att = float(row[col_attack])  if pd.notna(row[col_attack])  else 0.0
            w_def = float(row[col_defense]) if pd.notna(row[col_defense]) else 0.0
            # Keep maximum weight if the same metric appears on multiple rows
            prev_att, prev_def = result.get(key, (0.0, 0.0))
            result[key] = (max(prev_att, w_att), max(prev_def, w_def))

    _cache[role] = result
    return result


def get_attack_weights(role: str) -> dict[str, float]:
    """Return {metric_key: attack_weight} for the given role (0-100 scale)."""
    weights = _load_role_weights(role)
    result  = {m: weights.get(m, (0.0, 0.0))[0] for m in ATTACK_METRICS}
    if sum(result.values()) == 0:
        result = {m: 1.0 for m in ATTACK_METRICS}
    return result


def get_defense_weights(role: str) -> dict[str, float]:
    """Return {metric_key: defense_weight} for the given role (0-100 scale)."""
    weights = _load_role_weights(role)
    result  = {m: weights.get(m, (0.0, 0.0))[1] for m in DEFENSE_METRICS}
    if sum(result.values()) == 0:
        result = {m: 1.0 for m in DEFENSE_METRICS}
    return result
