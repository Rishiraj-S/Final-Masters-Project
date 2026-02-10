"""Transition and pressing analysis for Barcelona matches."""
from __future__ import annotations

from collections import defaultdict

import numpy as np
import pandas as pd

from barcelona_postmatch_app.config import (
    EVENT_TYPES,
    FAST_COUNTER_WINDOW,
    PRESS_REGAIN_WINDOW,
    SHOT_TYPES,
    TRANSITION_TIME_WINDOW,
)
from barcelona_postmatch_app.utils.helpers import distance_opta, qualifier_is_set


def identify_attacking_transitions(events_df: pd.DataFrame, sequences_df: pd.DataFrame = None) -> dict:
    """Identify and analyze Barcelona's attacking transitions.

    Returns dict with:
        transitions: list of transition dicts
        metrics: aggregated transition metrics
        regain_patterns: first-action distribution after regains
    """
    # Always get the full sequence list (not just Barcelona's)
    from barcelona_postmatch_app.processing.event_processor import identify_possession_sequences
    all_sequences = identify_possession_sequences(events_df)

    if all_sequences.empty:
        return {"transitions": [], "metrics": _empty_transition_metrics(), "regain_patterns": {}}

    # Sort by sequence_id to ensure order
    all_sequences = all_sequences.sort_values("sequence_id").reset_index(drop=True)
    transitions = []

    for i in range(1, len(all_sequences)):
        seq_row = all_sequences.iloc[i]
        prev_row = all_sequences.iloc[i - 1]

        # A transition is when Barcelona gains possession from the opposition
        if not seq_row["is_barca"] or prev_row["is_barca"]:
            continue

        start_idx = seq_row["start_idx"]
        end_idx = seq_row["end_idx"]
        start_sec = seq_row["start_second"]
        duration = seq_row["duration"]

        # Get sequence events
        mask = (events_df.index >= start_idx) & (events_df.index <= end_idx) & (events_df["is_barca"])
        seq_events = events_df.loc[mask]

        if seq_events.empty:
            continue

        # Check for shot within transition window
        shots = seq_events[seq_events["event_type_id"].isin(SHOT_TYPES)]
        has_shot = not shots.empty

        time_to_shot = None
        if has_shot:
            first_shot = shots.iloc[0]
            time_to_shot = first_shot["match_seconds"] - start_sec

        # Count passes in transition
        passes = seq_events[seq_events["event_type_id"] == EVENT_TYPES["pass"]]
        pass_count = len(passes)

        # Regain location
        first_event = seq_events.iloc[0]
        regain_x = first_event.get("x_norm", first_event.get("x", np.nan))
        regain_y = first_event.get("y_norm", first_event.get("y", np.nan))

        # Classify transition
        if has_shot and time_to_shot is not None and time_to_shot <= FAST_COUNTER_WINDOW:
            trans_type = "fast_counter"
        elif has_shot and time_to_shot is not None and time_to_shot <= TRANSITION_TIME_WINDOW:
            trans_type = "delayed_counter"
        elif has_shot:
            trans_type = "slow_attack"
        else:
            trans_type = "failed"

        # Determine outcome
        if has_shot:
            shot = shots.iloc[0]
            if shot["event_type_id"] == EVENT_TYPES.get("goal", 16):
                outcome = "goal"
            elif shot["event_type_id"] == EVENT_TYPES.get("saved_shot", 15):
                outcome = "saved"
            else:
                outcome = "shot_off_target"
        else:
            outcome = "no_shot"

        transitions.append({
            "sequence_id": seq_row["sequence_id"],
            "start_second": start_sec,
            "duration": duration,
            "time_to_shot": time_to_shot,
            "pass_count": pass_count,
            "type": trans_type,
            "outcome": outcome,
            "regain_x": regain_x,
            "regain_y": regain_y,
            "start_idx": start_idx,
            "end_idx": end_idx,
            "minute": first_event.get("minute", first_event.get("time_min", 0)),
        })

    metrics = calculate_transition_metrics(transitions)
    regain_patterns = analyze_regain_patterns(events_df, transitions)

    return {
        "transitions": transitions,
        "metrics": metrics,
        "regain_patterns": regain_patterns,
    }


def calculate_transition_metrics(transitions: list[dict]) -> dict:
    """Calculate aggregated transition metrics."""
    if not transitions:
        return _empty_transition_metrics()

    total = len(transitions)
    with_shot = [t for t in transitions if t["outcome"] != "no_shot"]
    fast = [t for t in transitions if t["type"] == "fast_counter"]
    delayed = [t for t in transitions if t["type"] == "delayed_counter"]
    goals = [t for t in transitions if t["outcome"] == "goal"]

    speeds = [t["time_to_shot"] for t in with_shot if t["time_to_shot"] is not None]
    avg_speed = float(np.mean(speeds)) if speeds else 0

    pass_counts = [t["pass_count"] for t in transitions]
    avg_passes = float(np.mean(pass_counts)) if pass_counts else 0

    outcome_dist = defaultdict(int)
    type_dist = defaultdict(int)
    for t in transitions:
        outcome_dist[t["outcome"]] += 1
        type_dist[t["type"]] += 1

    return {
        "total_transitions": total,
        "counter_attack_rate": round(len(with_shot) / total * 100, 1) if total > 0 else 0,
        "fast_counter_count": len(fast),
        "delayed_counter_count": len(delayed),
        "goal_count": len(goals),
        "avg_transition_speed": round(avg_speed, 1),
        "avg_passes_per_transition": round(avg_passes, 1),
        "outcome_distribution": dict(outcome_dist),
        "type_distribution": dict(type_dist),
    }


def _empty_transition_metrics() -> dict:
    return {
        "total_transitions": 0, "counter_attack_rate": 0,
        "fast_counter_count": 0, "delayed_counter_count": 0,
        "goal_count": 0, "avg_transition_speed": 0,
        "avg_passes_per_transition": 0, "outcome_distribution": {},
        "type_distribution": {},
    }


def identify_pressing_moments(events_df: pd.DataFrame) -> list[dict]:
    """Identify moments where Barcelona presses the opposition.

    A pressing moment is when the opposition has the ball and Barcelona
    performs defensive actions (tackles, interceptions, challenges) nearby.
    """
    pressing_moments = []

    # Get opposition possession events
    opp_events = events_df[~events_df["is_barca"]].copy()
    barca_events = events_df[events_df["is_barca"]].copy()

    # Defensive action types
    defensive_actions = {
        EVENT_TYPES["tackle"],
        EVENT_TYPES["interception"],
        EVENT_TYPES["challenge"],
        EVENT_TYPES["ball_recovery"],
    }

    barca_defensive = barca_events[barca_events["event_type_id"].isin(defensive_actions)]

    for _, def_event in barca_defensive.iterrows():
        t = def_event["match_seconds"]
        x = def_event.get("x_norm", def_event.get("x", np.nan))
        y = def_event.get("y_norm", def_event.get("y", np.nan))
        period = def_event["period_id"]

        if pd.isna(x) or pd.isna(y):
            continue

        # Check if opposition had ball just before
        opp_before = opp_events[
            (opp_events["match_seconds"] >= t - 5) &
            (opp_events["match_seconds"] <= t) &
            (opp_events["period_id"] == period)
        ]

        if opp_before.empty:
            continue

        # Count Barcelona defenders involved (nearby defensive actions in +-3 seconds)
        nearby_barca = barca_defensive[
            (barca_defensive["match_seconds"] >= t - 3) &
            (barca_defensive["match_seconds"] <= t + 3) &
            (barca_defensive["period_id"] == period)
        ]
        defenders_involved = nearby_barca["player_id"].nunique()

        # Check if regain occurred within PRESS_REGAIN_WINDOW
        regain_window = barca_events[
            (barca_events["match_seconds"] >= t) &
            (barca_events["match_seconds"] <= t + PRESS_REGAIN_WINDOW) &
            (barca_events["period_id"] == period) &
            (barca_events["event_type_id"].isin({
                EVENT_TYPES["pass"], EVENT_TYPES["ball_recovery"],
                EVENT_TYPES["interception"],
            }))
        ]
        regained = not regain_window.empty

        regain_x, regain_y = np.nan, np.nan
        if regained:
            first_regain = regain_window.iloc[0]
            regain_x = first_regain.get("x_norm", first_regain.get("x", np.nan))
            regain_y = first_regain.get("y_norm", first_regain.get("y", np.nan))

        pressing_moments.append({
            "match_seconds": t,
            "minute": def_event.get("minute", def_event.get("time_min", 0)),
            "x": x,
            "y": y,
            "defenders_involved": defenders_involved,
            "regained": regained,
            "regain_x": regain_x,
            "regain_y": regain_y,
            "event_type": def_event["event_type"],
            "player_name": str(def_event.get("player_name", "")),
            "period": period,
        })

    return pressing_moments


def calculate_pressing_metrics(pressing_moments: list[dict]) -> dict:
    """Calculate aggregated pressing metrics."""
    if not pressing_moments:
        return {
            "total_presses": 0, "press_success_rate": 0,
            "avg_intensity": 0, "press_locations": [],
            "regain_locations": [],
        }

    total = len(pressing_moments)
    successful = sum(1 for p in pressing_moments if p["regained"])
    intensities = [p["defenders_involved"] for p in pressing_moments]

    press_locs = [(p["x"], p["y"]) for p in pressing_moments if not np.isnan(p["x"])]
    regain_locs = [
        (p["regain_x"], p["regain_y"]) for p in pressing_moments
        if p["regained"] and not np.isnan(p["regain_x"])
    ]

    # Zone distribution
    zone_success = defaultdict(lambda: {"total": 0, "success": 0})
    for p in pressing_moments:
        x = p["x"]
        if np.isnan(x):
            continue
        if x < 33.3:
            zone = "own_third"
        elif x < 66.7:
            zone = "middle_third"
        else:
            zone = "final_third"
        zone_success[zone]["total"] += 1
        if p["regained"]:
            zone_success[zone]["success"] += 1

    zone_rates = {
        z: round(d["success"] / d["total"] * 100, 1) if d["total"] > 0 else 0
        for z, d in zone_success.items()
    }

    return {
        "total_presses": total,
        "press_success_rate": round(successful / total * 100, 1) if total > 0 else 0,
        "avg_intensity": round(float(np.mean(intensities)), 1),
        "press_locations": press_locs,
        "regain_locations": regain_locs,
        "zone_success_rates": zone_rates,
        "zone_counts": {z: d["total"] for z, d in zone_success.items()},
    }


def analyze_regain_patterns(events_df: pd.DataFrame, transitions: list[dict]) -> dict:
    """Analyze what Barcelona does immediately after regaining possession."""
    patterns = defaultdict(int)

    for trans in transitions:
        start_idx = trans["start_idx"]
        # Get first event after regain
        mask = (events_df.index >= start_idx) & (events_df["is_barca"])
        first_events = events_df.loc[mask].head(2)

        if len(first_events) < 1:
            continue

        first = first_events.iloc[0]
        etype = first["event_type_id"]

        if etype == EVENT_TYPES["pass"]:
            patterns["pass"] += 1
        elif etype == EVENT_TYPES["take_on"]:
            patterns["dribble"] += 1
        elif etype in SHOT_TYPES:
            patterns["shot"] += 1
        elif etype == EVENT_TYPES["clearance"]:
            patterns["clearance"] += 1
        else:
            patterns["other"] += 1

    return dict(patterns)
