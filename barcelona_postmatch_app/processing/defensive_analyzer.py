"""Defensive structure and performance analysis for Barcelona matches."""
from __future__ import annotations

from collections import defaultdict

import numpy as np
import pandas as pd

from barcelona_postmatch_app.config import EVENT_TYPES, FORMATION_MAP, SHOT_TYPES
from barcelona_postmatch_app.utils.helpers import (
    compute_xg_simple,
    distance_opta,
    qualifier_is_set,
)


def detect_formations(events_df: pd.DataFrame, barca_code: str) -> dict:
    """Detect Barcelona's formation and changes throughout the match.

    Returns:
        primary_formation: str (e.g., "4-3-3")
        formation_timeline: list of {minute, formation}
    """
    # Get team setup and formation change events
    setup_events = events_df[
        (events_df["event_type_id"].isin({EVENT_TYPES["team_setup"], EVENT_TYPES["formation_change"]})) &
        (events_df["team_code"] == barca_code)
    ].sort_values("match_seconds")

    formations = []
    primary = "Unknown"

    for _, row in setup_events.iterrows():
        fm_id = str(row.get("Team Formation", "N/A"))
        if fm_id == "N/A":
            fm_id = str(row.get("formation", ""))

        formation = FORMATION_MAP.get(fm_id, fm_id)
        if formation and formation != "N/A" and formation != "":
            minute = row.get("minute", row.get("time_min", 0))
            formations.append({"minute": minute, "formation": formation, "period": row["period_id"]})
            if not formations or primary == "Unknown":
                primary = formation

    return {
        "primary_formation": primary,
        "formation_timeline": formations,
    }


def analyze_defensive_shape(events_df: pd.DataFrame) -> dict:
    """Analyze Barcelona's defensive shape throughout the match.

    Returns dict with:
        shape_timeline: list of {minute, compactness, line_depth}
        avg_compactness: float
        avg_line_depth: float
        formation_data: from detect_formations
        duel_data: from identify_duels
        interceptions: from extract_interceptions
        opposition_threat: from analyze_opposition_threat
        metrics: comprehensive defensive metrics
    """
    barca_code = None
    barca_events = events_df[events_df["is_barca"]]
    if not barca_events.empty:
        barca_code = barca_events.iloc[0]["team_code"]

    if barca_code is None:
        return _empty_defensive_data()

    # Formation detection
    formation_data = detect_formations(events_df, barca_code)

    # Defensive shape timeline
    shape_timeline = _compute_defensive_shape_timeline(events_df, barca_code)

    # Duels
    duels = identify_duels(events_df, barca_code)
    duel_metrics = calculate_duel_metrics(duels)

    # Interceptions
    interceptions = extract_interceptions(events_df, barca_code)

    # Opposition threat
    opp_threat = analyze_opposition_threat(events_df, barca_code)

    # Comprehensive metrics
    metrics = calculate_defensive_metrics(
        shape_timeline, duel_metrics, interceptions, opp_threat
    )

    return {
        "formation_data": formation_data,
        "shape_timeline": shape_timeline,
        "duels": duels,
        "duel_metrics": duel_metrics,
        "interceptions": interceptions,
        "opposition_threat": opp_threat,
        "metrics": metrics,
    }


def _compute_defensive_shape_timeline(
    events_df: pd.DataFrame, barca_code: str
) -> list[dict]:
    """Compute defensive compactness and line depth over 5-minute intervals."""
    timeline = []

    # Get defensive events (when opposition has ball)
    opp_possession = events_df[~events_df["is_barca"]]
    if opp_possession.empty:
        return timeline

    max_minute = int(events_df["minute"].max()) if "minute" in events_df else 90
    interval = 5

    for start_min in range(0, max_minute + 1, interval):
        end_min = start_min + interval

        # Get Barcelona's positions during this interval (all events)
        barca_in_window = events_df[
            (events_df["is_barca"]) &
            (events_df["minute"] >= start_min) &
            (events_df["minute"] < end_min) &
            (events_df["x_norm"].notna()) &
            (events_df["y_norm"].notna())
        ]

        if len(barca_in_window) < 3:
            continue

        x_values = barca_in_window["x_norm"].values
        y_values = barca_in_window["y_norm"].values

        # Defensive line depth: average x of deepest 4 players (lowest x = closest to own goal)
        sorted_x = np.sort(x_values)
        if len(sorted_x) >= 4:
            line_depth = float(np.mean(sorted_x[:4]))
        else:
            line_depth = float(np.mean(sorted_x))

        # Compactness: standard deviation of positions (lower = more compact)
        x_spread = float(np.std(x_values))
        y_spread = float(np.std(y_values))
        compactness_raw = x_spread + y_spread

        # Normalize compactness to 0-100 (higher = more compact)
        # Typical combined std range: 15-60 for Opta coords. Scale accordingly.
        compactness = max(0, min(100, (1 - (compactness_raw - 15) / 50) * 100))

        timeline.append({
            "minute_start": start_min,
            "minute_end": end_min,
            "compactness": round(compactness, 1),
            "line_depth": round(line_depth, 1),
            "x_spread": round(x_spread, 1),
            "y_spread": round(y_spread, 1),
        })

    return timeline


def identify_duels(events_df: pd.DataFrame, barca_code: str) -> list[dict]:
    """Find all duels involving Barcelona players."""
    duel_types = {
        EVENT_TYPES["tackle"]: "ground",
        EVENT_TYPES["aerial"]: "aerial",
        EVENT_TYPES["challenge"]: "ground",
    }

    duels = []
    for _, row in events_df.iterrows():
        etype = row["event_type_id"]
        if etype not in duel_types:
            continue
        if row["team_code"] != barca_code:
            continue

        x = row.get("x_norm", row.get("x", np.nan))
        y = row.get("y_norm", row.get("y", np.nan))

        duels.append({
            "event_idx": row.name,
            "type": duel_types[etype],
            "event_type": row["event_type"],
            "won": row["outcome"] == 1,
            "x": x,
            "y": y,
            "player_name": str(row.get("player_name", "")),
            "player_id": str(row.get("player_id", "")),
            "minute": row.get("minute", row.get("time_min", 0)),
        })

    return duels


def calculate_duel_metrics(duels: list[dict]) -> dict:
    """Calculate aggregated duel metrics."""
    if not duels:
        return {
            "total": 0, "won": 0, "win_rate": 0,
            "aerial_total": 0, "aerial_won": 0, "aerial_rate": 0,
            "ground_total": 0, "ground_won": 0, "ground_rate": 0,
            "player_performance": {},
        }

    total = len(duels)
    won = sum(1 for d in duels if d["won"])

    aerial = [d for d in duels if d["type"] == "aerial"]
    ground = [d for d in duels if d["type"] == "ground"]

    aerial_won = sum(1 for d in aerial if d["won"])
    ground_won = sum(1 for d in ground if d["won"])

    # Player performance
    player_duels = defaultdict(lambda: {"total": 0, "won": 0, "name": ""})
    for d in duels:
        pid = d["player_id"]
        player_duels[pid]["total"] += 1
        player_duels[pid]["name"] = d["player_name"]
        if d["won"]:
            player_duels[pid]["won"] += 1

    player_perf = {
        pid: {
            "name": data["name"],
            "total": data["total"],
            "won": data["won"],
            "rate": round(data["won"] / data["total"] * 100, 1) if data["total"] > 0 else 0,
        }
        for pid, data in player_duels.items()
    }

    return {
        "total": total,
        "won": won,
        "win_rate": round(won / total * 100, 1) if total > 0 else 0,
        "aerial_total": len(aerial),
        "aerial_won": aerial_won,
        "aerial_rate": round(aerial_won / len(aerial) * 100, 1) if aerial else 0,
        "ground_total": len(ground),
        "ground_won": ground_won,
        "ground_rate": round(ground_won / len(ground) * 100, 1) if ground else 0,
        "player_performance": player_perf,
    }


def extract_interceptions(events_df: pd.DataFrame, barca_code: str) -> list[dict]:
    """Extract all interceptions by Barcelona players."""
    interceptions = []

    intercept_events = events_df[
        (events_df["event_type_id"] == EVENT_TYPES["interception"]) &
        (events_df["team_code"] == barca_code)
    ]

    for _, row in intercept_events.iterrows():
        x = row.get("x_norm", row.get("x", np.nan))
        y = row.get("y_norm", row.get("y", np.nan))

        interceptions.append({
            "x": x,
            "y": y,
            "player_name": str(row.get("player_name", "")),
            "player_id": str(row.get("player_id", "")),
            "minute": row.get("minute", row.get("time_min", 0)),
        })

    return interceptions


def analyze_opposition_threat(events_df: pd.DataFrame, barca_code: str) -> dict:
    """Analyze where opposition creates threats against Barcelona."""
    opp_events = events_df[events_df["team_code"] != barca_code]
    opp_shots = opp_events[opp_events["event_type_id"].isin(SHOT_TYPES)]

    shot_data = []
    total_xg = 0.0

    for _, shot in opp_shots.iterrows():
        # For opposition, flip coordinates to show from Barcelona's defensive perspective
        x = shot.get("x", np.nan)
        y = shot.get("y", np.nan)
        is_header = qualifier_is_set(shot.get("Head"))
        xg = compute_xg_simple(x, y, is_header)
        total_xg += xg

        shot_data.append({
            "x": x,
            "y": y,
            "event_type": shot["event_type"],
            "is_goal": shot["event_type_id"] == EVENT_TYPES["goal"],
            "is_on_target": shot["event_type_id"] in {EVENT_TYPES["saved_shot"], EVENT_TYPES["goal"]},
            "xg": xg,
            "player_name": str(shot.get("player_name", "")),
            "minute": shot.get("minute", shot.get("time_min", 0)),
        })

    # xGA by region
    xga_by_zone = defaultdict(float)
    for s in shot_data:
        x = s["x"]
        if np.isnan(x):
            continue
        if x >= 83:
            zone = "box"
        elif x >= 66:
            zone = "edge_of_box"
        else:
            zone = "long_range"
        xga_by_zone[zone] += s["xg"]

    return {
        "shots": shot_data,
        "total_shots": len(shot_data),
        "shots_on_target": sum(1 for s in shot_data if s["is_on_target"]),
        "goals_conceded": sum(1 for s in shot_data if s["is_goal"]),
        "total_xga": round(total_xg, 2),
        "xga_by_zone": dict(xga_by_zone),
    }


def calculate_defensive_metrics(
    shape_timeline: list[dict],
    duel_metrics: dict,
    interceptions: list[dict],
    opp_threat: dict,
) -> dict:
    """Calculate comprehensive defensive metrics."""
    avg_compactness = 0.0
    avg_line_depth = 0.0
    if shape_timeline:
        avg_compactness = round(np.mean([s["compactness"] for s in shape_timeline]), 1)
        avg_line_depth = round(np.mean([s["line_depth"] for s in shape_timeline]), 1)

    return {
        "compactness_index": avg_compactness,
        "avg_line_depth": avg_line_depth,
        "duel_win_rate": duel_metrics.get("win_rate", 0),
        "aerial_win_rate": duel_metrics.get("aerial_rate", 0),
        "ground_duel_rate": duel_metrics.get("ground_rate", 0),
        "total_interceptions": len(interceptions),
        "total_shots_conceded": opp_threat.get("total_shots", 0),
        "shots_on_target_conceded": opp_threat.get("shots_on_target", 0),
        "goals_conceded": opp_threat.get("goals_conceded", 0),
        "total_xga": opp_threat.get("total_xga", 0),
    }


def _empty_defensive_data() -> dict:
    return {
        "formation_data": {"primary_formation": "Unknown", "formation_timeline": []},
        "shape_timeline": [],
        "duels": [],
        "duel_metrics": calculate_duel_metrics([]),
        "interceptions": [],
        "opposition_threat": {
            "shots": [], "total_shots": 0, "shots_on_target": 0,
            "goals_conceded": 0, "total_xga": 0, "xga_by_zone": {},
        },
        "metrics": {
            "compactness_index": 0, "avg_line_depth": 0,
            "duel_win_rate": 0, "aerial_win_rate": 0, "ground_duel_rate": 0,
            "total_interceptions": 0, "total_shots_conceded": 0,
            "shots_on_target_conceded": 0, "goals_conceded": 0, "total_xga": 0,
        },
    }
