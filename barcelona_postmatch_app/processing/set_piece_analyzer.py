"""Set piece analysis for Barcelona matches."""
from __future__ import annotations

from collections import defaultdict

import numpy as np
import pandas as pd

from barcelona_postmatch_app.config import EVENT_TYPES, SHOT_TYPES
from barcelona_postmatch_app.utils.helpers import (
    compute_xg_simple,
    qualifier_is_set,
    safe_float,
)


def detect_set_pieces(events_df: pd.DataFrame) -> dict:
    """Detect and classify all set pieces in the match.

    Returns dict with:
        attacking: list of Barcelona attacking set pieces
        defensive: list of opposition attacking set pieces (Barcelona defending)
        metrics: aggregated metrics
    """
    attacking = []
    defensive = []

    for idx, row in events_df.iterrows():
        sp_type = _classify_set_piece_type(row)
        if sp_type is None:
            continue

        is_barca = row["is_barca"]
        x = row.get("x_norm", row.get("x", np.nan))
        y = row.get("y_norm", row.get("y", np.nan))
        x_end = row.get("x_end_norm", row.get("x_end", np.nan))
        y_end = row.get("y_end_norm", row.get("y_end", np.nan))

        # Find subsequent events (next 15 events or 30 seconds)
        subsequent = events_df.loc[idx:]
        subsequent = subsequent[
            subsequent["match_seconds"] <= row["match_seconds"] + 30
        ].head(15)

        # Check for shots in the sequence
        shots = subsequent[subsequent["event_type_id"].isin(SHOT_TYPES)]
        has_shot = not shots.empty
        has_goal = not shots[shots["event_type_id"] == EVENT_TYPES["goal"]].empty if has_shot else False

        # Delivery classification
        delivery = extract_set_piece_delivery(row)

        # Calculate xG if shot exists
        xg = 0.0
        if has_shot:
            for _, shot in shots.iterrows():
                sx = shot.get("x_norm", shot.get("x", np.nan))
                sy = shot.get("y_norm", shot.get("y", np.nan))
                is_header = qualifier_is_set(shot.get("Head"))
                if not np.isnan(sx):
                    xg += compute_xg_simple(sx, sy, is_header)

        sp_data = {
            "event_idx": idx,
            "type": sp_type,
            "x": x,
            "y": y,
            "x_end": x_end,
            "y_end": y_end,
            "team_code": row["team_code"],
            "is_barca": is_barca,
            "player_name": str(row.get("player_name", "")),
            "minute": row.get("minute", row.get("time_min", 0)),
            "period": row["period_id"],
            "delivery": delivery,
            "has_shot": has_shot,
            "has_goal": has_goal,
            "xg": xg,
            "outcome": _determine_set_piece_outcome(subsequent, is_barca),
        }

        if is_barca:
            attacking.append(sp_data)
        else:
            defensive.append(sp_data)

    metrics = calculate_set_piece_metrics(attacking, defensive)

    return {
        "attacking": attacking,
        "defensive": defensive,
        "metrics": metrics,
    }


def _classify_set_piece_type(row: pd.Series) -> str | None:
    """Determine if an event is a set piece and what type."""
    # Corner
    if qualifier_is_set(row.get("Corner taken")):
        return "corner"

    # Free kick
    if qualifier_is_set(row.get("Free kick taken")):
        return "free_kick"

    # Throw in
    if qualifier_is_set(row.get("Throw in")):
        return "throw_in"

    # Goal kick
    if qualifier_is_set(row.get("Goal Kick")):
        return "goal_kick"

    # Corner awarded event type
    if row["event_type_id"] == EVENT_TYPES.get("corner_awarded", 6):
        return "corner"

    return None


def extract_set_piece_delivery(row: pd.Series) -> dict:
    """Classify the delivery type of a set piece."""
    delivery = {
        "type": "standard",
        "inswinger": False,
        "outswinger": False,
        "short": False,
        "long": False,
        "driven": False,
        "floated": False,
        "to_head": False,
    }

    # Check qualifiers
    if qualifier_is_set(row.get("Inswinging")):
        delivery["inswinger"] = True
        delivery["type"] = "inswinger"
    elif qualifier_is_set(row.get("Outswinging")):
        delivery["outswinger"] = True
        delivery["type"] = "outswinger"

    # Short vs long
    length = safe_float(row.get("Length"))
    if not np.isnan(length):
        if length < 15:
            delivery["short"] = True
        else:
            delivery["long"] = True

    # Cross qualifiers
    if qualifier_is_set(row.get("Cross")):
        delivery["type"] = "cross"
    if qualifier_is_set(row.get("Long ball")):
        delivery["long"] = True

    if qualifier_is_set(row.get("Head")):
        delivery["to_head"] = True

    return delivery


def analyze_set_piece_positioning(events_df: pd.DataFrame, set_piece_event_idx: int) -> dict:
    """Analyze player positions during a set piece delivery."""
    sp_event = events_df.loc[set_piece_event_idx]
    sp_time = sp_event["match_seconds"]
    period = sp_event["period_id"]

    # Get events within 2 seconds of set piece (player touches/positions)
    nearby = events_df[
        (events_df["match_seconds"] >= sp_time - 2) &
        (events_df["match_seconds"] <= sp_time + 5) &
        (events_df["period_id"] == period) &
        (events_df["x"].notna())
    ]

    barca_positions = []
    opp_positions = []

    for _, evt in nearby.iterrows():
        pos_data = {
            "player_name": str(evt.get("player_name", "")),
            "x": evt.get("x_norm", evt.get("x", np.nan)),
            "y": evt.get("y_norm", evt.get("y", np.nan)),
        }
        if evt["is_barca"]:
            barca_positions.append(pos_data)
        else:
            opp_positions.append(pos_data)

    return {
        "attacking_positions": barca_positions if sp_event["is_barca"] else opp_positions,
        "defensive_positions": opp_positions if sp_event["is_barca"] else barca_positions,
    }


def _determine_set_piece_outcome(subsequent_events: pd.DataFrame, is_barca_attacking: bool) -> str:
    """Determine the outcome of a set piece sequence."""
    for _, evt in subsequent_events.iterrows():
        if evt["event_type_id"] == EVENT_TYPES["goal"]:
            return "goal"
        if evt["event_type_id"] in {EVENT_TYPES["saved_shot"], EVENT_TYPES["miss"], EVENT_TYPES["post"]}:
            return "shot"
        if evt["event_type_id"] == EVENT_TYPES["clearance"]:
            return "cleared"
        if evt["event_type_id"] in {EVENT_TYPES["out"], EVENT_TYPES["foul"]}:
            return "dead_ball"
    return "retained"


def calculate_set_piece_metrics(attacking: list[dict], defensive: list[dict]) -> dict:
    """Calculate aggregated set piece metrics."""
    # Attacking metrics
    atk_total = len(attacking)
    atk_shots = sum(1 for sp in attacking if sp["has_shot"])
    atk_goals = sum(1 for sp in attacking if sp["has_goal"])
    atk_xg = sum(sp["xg"] for sp in attacking)

    atk_by_type = defaultdict(lambda: {"total": 0, "shots": 0, "goals": 0})
    for sp in attacking:
        t = sp["type"]
        atk_by_type[t]["total"] += 1
        if sp["has_shot"]:
            atk_by_type[t]["shots"] += 1
        if sp["has_goal"]:
            atk_by_type[t]["goals"] += 1

    # Delivery effectiveness
    delivery_eff = defaultdict(lambda: {"total": 0, "shots": 0})
    for sp in attacking:
        dt = sp["delivery"]["type"]
        delivery_eff[dt]["total"] += 1
        if sp["has_shot"]:
            delivery_eff[dt]["shots"] += 1

    # Defensive metrics
    def_total = len(defensive)
    def_shots = sum(1 for sp in defensive if sp["has_shot"])
    def_goals = sum(1 for sp in defensive if sp["has_goal"])
    def_xg = sum(sp["xg"] for sp in defensive)

    def_by_type = defaultdict(lambda: {"total": 0, "shots": 0, "goals": 0})
    for sp in defensive:
        t = sp["type"]
        def_by_type[t]["total"] += 1
        if sp["has_shot"]:
            def_by_type[t]["shots"] += 1
        if sp["has_goal"]:
            def_by_type[t]["goals"] += 1

    return {
        "attacking": {
            "total": atk_total,
            "shots": atk_shots,
            "goals": atk_goals,
            "conversion_rate": round(atk_shots / atk_total * 100, 1) if atk_total > 0 else 0,
            "xg": round(atk_xg, 2),
            "by_type": dict(atk_by_type),
            "delivery_effectiveness": dict(delivery_eff),
        },
        "defensive": {
            "total": def_total,
            "shots_conceded": def_shots,
            "goals_conceded": def_goals,
            "xg_against": round(def_xg, 2),
            "by_type": dict(def_by_type),
        },
    }
