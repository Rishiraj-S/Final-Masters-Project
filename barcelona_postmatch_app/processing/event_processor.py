"""Core event qualification and sequencing logic."""
from __future__ import annotations

import numpy as np
import pandas as pd

from barcelona_postmatch_app.config import (
    EVENT_TYPES,
    PROGRESSIVE_DISTANCE,
    SHOT_TYPES,
    SET_PIECE_QUALIFIERS,
    TRANSITION_TIME_WINDOW,
)
from barcelona_postmatch_app.utils.helpers import (
    distance_opta,
    qualifier_is_set,
    safe_float,
)


# ---------------------------------------------------------------------------
# Single-event classifiers
# ---------------------------------------------------------------------------

def is_progressive_pass(x: float, y: float, x_end: float, y_end: float) -> bool:
    """Check if a pass is progressive (advances the ball toward the opponent's goal).

    Uses normalized coordinates where the team attacks left-to-right (x=0 own goal, x=100 opp goal).
    A pass is progressive if it moves >=10 Opta x-units toward the opponent goal.
    """
    if any(np.isnan(v) for v in [x, y, x_end, y_end]):
        return False
    x_gain = x_end - x
    return x_gain >= PROGRESSIVE_DISTANCE


def is_under_pressure(events_df: pd.DataFrame, event_idx: int) -> bool:
    """Check if an event was performed under pressure.

    Uses the Opta 'Involved Player' or proximity heuristic:
    Look for opposition events within ~2 seconds and close proximity.
    """
    if event_idx < 0 or event_idx >= len(events_df):
        return False

    row = events_df.iloc[event_idx]

    # Check if the event has a defensive pressure qualifier
    if qualifier_is_set(row.get("Defensive", None)):
        return True

    # Heuristic: look at nearby events from opposition within 2-second window
    team = row.get("team_code")
    t = row.get("match_seconds", 0)
    x, y = row.get("x", np.nan), row.get("y", np.nan)

    if pd.isna(x) or pd.isna(y):
        return False

    window = events_df[
        (events_df["team_code"] != team) &
        (events_df["match_seconds"] >= t - 2) &
        (events_df["match_seconds"] <= t + 2) &
        (events_df["x"].notna()) &
        (events_df["y"].notna())
    ]

    for _, opp in window.iterrows():
        dist = distance_opta(x, y, opp["x"], opp["y"])
        if dist <= 5.0:  # ~5 Opta units ≈ ~5m on pitch
            return True

    return False


def get_event_location_zone(x: float, y: float) -> str:
    """Classify event location zone using normalized coordinates (attacking L->R).

    Returns zone string like 'final_third_right', 'middle_third_center', etc.
    """
    if np.isnan(x) or np.isnan(y):
        return "unknown"

    # Third classification
    if x < 33.3:
        third = "own_third"
    elif x < 66.7:
        third = "middle_third"
    else:
        third = "final_third"

    # Width classification
    if y < 33.3:
        width = "left"
    elif y < 66.7:
        width = "center"
    else:
        width = "right"

    return f"{third}_{width}"


def get_directional_action(x: float, y: float, x_end: float, y_end: float) -> str:
    """Classify pass direction as forward, sideways, or backward."""
    if any(np.isnan(v) for v in [x, y, x_end, y_end]):
        return "unknown"

    x_diff = x_end - x
    y_diff = abs(y_end - y)

    if x_diff > 5:
        return "forward"
    elif x_diff < -5:
        return "backward"
    else:
        return "sideways"


# ---------------------------------------------------------------------------
# Possession sequence identification
# ---------------------------------------------------------------------------

POSSESSION_CHANGE_EVENTS = {
    EVENT_TYPES["turnover"],
    EVENT_TYPES["dispossessed"],
    EVENT_TYPES["interception"],
    EVENT_TYPES["tackle"],
    EVENT_TYPES["ball_recovery"],
}

SEQUENCE_END_EVENTS = SHOT_TYPES | {
    EVENT_TYPES["foul"],
    EVENT_TYPES["out"],
}

SET_PIECE_EVENT_TYPES = {
    EVENT_TYPES["corner_awarded"],
}


def identify_possession_sequences(events_df: pd.DataFrame) -> pd.DataFrame:
    """Split match events into possession sequences.

    A new sequence starts when:
    - Possession changes team
    - A set piece occurs
    - A period starts/ends

    Returns DataFrame with columns:
        sequence_id, team_code, is_barca, start_idx, end_idx,
        start_second, end_second, duration, event_count, outcome
    """
    # Filter to on-ball events only (exclude team setup, formation changes, etc.)
    play_events = events_df[
        events_df["event_type_id"].isin(
            {1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16,
             44, 45, 49, 50, 51, 61, 74}
        )
    ].copy()

    if play_events.empty:
        return pd.DataFrame()

    sequences = []
    seq_id = 0
    current_team = None
    seq_start_idx = None
    seq_start_second = 0
    current_period = None

    for idx, (df_idx, row) in enumerate(play_events.iterrows()):
        team = row["team_code"]
        period = row["period_id"]
        event_type = row["event_type_id"]

        # Period change forces new sequence
        if period != current_period:
            if seq_start_idx is not None and current_team is not None:
                _finalize_sequence(
                    sequences, seq_id, current_team, seq_start_idx, prev_idx,
                    seq_start_second, prev_second, play_events, events_df,
                )
                seq_id += 1
            current_team = team
            current_period = period
            seq_start_idx = df_idx
            seq_start_second = row["match_seconds"]

        # Team change = new sequence
        elif team != current_team:
            if seq_start_idx is not None and current_team is not None:
                _finalize_sequence(
                    sequences, seq_id, current_team, seq_start_idx, prev_idx,
                    seq_start_second, prev_second, play_events, events_df,
                )
                seq_id += 1
            current_team = team
            seq_start_idx = df_idx
            seq_start_second = row["match_seconds"]

        prev_idx = df_idx
        prev_second = row["match_seconds"]

    # Finalize last sequence
    if seq_start_idx is not None and current_team is not None:
        _finalize_sequence(
            sequences, seq_id, current_team, seq_start_idx, prev_idx,
            seq_start_second, prev_second, play_events, events_df,
        )

    if not sequences:
        return pd.DataFrame()

    seq_df = pd.DataFrame(sequences)
    return seq_df


def _finalize_sequence(
    sequences: list,
    seq_id: int,
    team_code: str,
    start_idx: int,
    end_idx: int,
    start_second: float,
    end_second: float,
    play_events: pd.DataFrame,
    events_df: pd.DataFrame,
) -> None:
    """Create a sequence record and append to list."""
    # Get sequence events from the full events_df using index range
    seq_events = events_df.loc[start_idx:end_idx]
    last_event = events_df.loc[end_idx] if end_idx in events_df.index else seq_events.iloc[-1]
    last_type = int(last_event.get("event_type_id", 0))

    if last_type in SHOT_TYPES:
        outcome = "shot"
    elif last_type == EVENT_TYPES.get("foul", 0):
        outcome = "foul_won"
    elif last_type in {EVENT_TYPES.get("out", 0)}:
        outcome = "out_of_play"
    elif last_type in POSSESSION_CHANGE_EVENTS:
        outcome = "turnover"
    else:
        outcome = "other"

    is_barca = events_df.loc[start_idx, "is_barca"] if start_idx in events_df.index else False
    duration = max(0, end_second - start_second)

    sequences.append({
        "sequence_id": seq_id,
        "team_code": team_code,
        "is_barca": bool(is_barca),
        "start_idx": start_idx,
        "end_idx": end_idx,
        "start_second": start_second,
        "end_second": end_second,
        "duration": duration,
        "event_count": len(seq_events),
        "outcome": outcome,
    })


# ---------------------------------------------------------------------------
# Sequence classification
# ---------------------------------------------------------------------------

def classify_sequence_type(events_df: pd.DataFrame, seq_row: pd.Series) -> str:
    """Classify a possession sequence type based on its events.

    Types: build_up, progression, final_third, transition, set_piece
    """
    start_idx = seq_row["start_idx"]
    end_idx = seq_row["end_idx"]
    duration = seq_row["duration"]

    # Get events in this sequence that belong to the possessing team
    mask = (events_df.index >= start_idx) & (events_df.index <= end_idx)
    seq = events_df.loc[mask]

    if seq.empty:
        return "other"

    team_events = seq[seq["team_code"] == seq_row["team_code"]]
    if team_events.empty:
        return "other"

    first_event = team_events.iloc[0]

    # Check for set piece
    for q_name in SET_PIECE_QUALIFIERS.values():
        if qualifier_is_set(first_event.get(q_name)):
            return "set_piece"

    # Check for corner event
    if first_event["event_type_id"] == EVENT_TYPES.get("corner_awarded", 0):
        return "set_piece"

    # Count passes
    passes = team_events[team_events["event_type_id"] == EVENT_TYPES["pass"]]
    pass_count = len(passes)

    # Check for transition (fast, few passes)
    if duration <= TRANSITION_TIME_WINDOW and pass_count <= 5:
        return "transition"

    # Classify by average x position of events
    avg_x = team_events["x_norm"].mean() if "x_norm" in team_events.columns else team_events["x"].mean()

    if pd.isna(avg_x):
        return "other"

    if avg_x < 40:
        return "build_up"
    elif avg_x < 65:
        return "progression"
    else:
        return "final_third"


def calculate_sequence_metrics(events_df: pd.DataFrame, seq_row: pd.Series) -> dict:
    """Calculate detailed metrics for a single possession sequence."""
    start_idx = seq_row["start_idx"]
    end_idx = seq_row["end_idx"]

    mask = (events_df.index >= start_idx) & (events_df.index <= end_idx)
    seq = events_df.loc[mask]
    team_events = seq[seq["team_code"] == seq_row["team_code"]]

    if team_events.empty:
        return _empty_sequence_metrics()

    passes = team_events[team_events["event_type_id"] == EVENT_TYPES["pass"]]
    completed_passes = passes[passes["outcome"] == 1]

    # Progressive passes
    progressive = 0
    for _, p in passes.iterrows():
        x = p.get("x_norm", p.get("x", np.nan))
        y = p.get("y_norm", p.get("y", np.nan))
        xe = p.get("x_end_norm", p.get("x_end", np.nan))
        ye = p.get("y_end_norm", p.get("y_end", np.nan))
        if is_progressive_pass(x, y, xe, ye):
            progressive += 1

    pass_count = len(passes)
    completed_count = len(completed_passes)

    # Under pressure passes (simplified - check for opposition events nearby)
    under_pressure_count = 0
    under_pressure_completed = 0
    for p_idx in passes.index:
        pos = events_df.index.get_loc(p_idx)
        if is_under_pressure(events_df, pos):
            under_pressure_count += 1
            if events_df.iloc[pos]["outcome"] == 1:
                under_pressure_completed += 1

    # Average pass length
    lengths = passes["pass_length"].dropna()
    avg_length = float(lengths.mean()) if not lengths.empty else 0.0

    return {
        "duration": seq_row["duration"],
        "pass_count": pass_count,
        "completed_passes": completed_count,
        "pass_completion": (completed_count / pass_count * 100) if pass_count > 0 else 0,
        "progressive_passes": progressive,
        "progressive_rate": (progressive / pass_count * 100) if pass_count > 0 else 0,
        "avg_pass_length": avg_length,
        "under_pressure_count": under_pressure_count,
        "under_pressure_completed": under_pressure_completed,
        "pressure_resistance": (
            under_pressure_completed / under_pressure_count * 100
            if under_pressure_count > 0 else 0
        ),
        "outcome": seq_row["outcome"],
        "event_count": seq_row["event_count"],
    }


def _empty_sequence_metrics() -> dict:
    return {
        "duration": 0, "pass_count": 0, "completed_passes": 0,
        "pass_completion": 0, "progressive_passes": 0, "progressive_rate": 0,
        "avg_pass_length": 0, "under_pressure_count": 0,
        "under_pressure_completed": 0, "pressure_resistance": 0,
        "outcome": "other", "event_count": 0,
    }


# ---------------------------------------------------------------------------
# Main tagging function
# ---------------------------------------------------------------------------

def tag_all_events(events_df: pd.DataFrame) -> pd.DataFrame:
    """Tag every event with additional analytical columns.

    Adds: is_progressive, is_under_pressure, location_zone, direction,
          sequence_id, sequence_type, sequence_outcome
    """
    df = events_df.copy()
    n = len(df)

    # Initialize columns
    df["is_progressive"] = False
    df["location_zone"] = "unknown"
    df["direction"] = "unknown"

    # Tag passes
    pass_mask = df["event_type_id"] == EVENT_TYPES["pass"]
    for idx in df[pass_mask].index:
        row = df.loc[idx]
        x = row.get("x_norm", row.get("x", np.nan))
        y = row.get("y_norm", row.get("y", np.nan))
        xe = row.get("x_end_norm", row.get("x_end", np.nan))
        ye = row.get("y_end_norm", row.get("y_end", np.nan))

        df.at[idx, "is_progressive"] = is_progressive_pass(x, y, xe, ye)
        df.at[idx, "direction"] = get_directional_action(x, y, xe, ye)

    # Tag all events with location zone
    for idx in df.index:
        row = df.loc[idx]
        x = row.get("x_norm", row.get("x", np.nan))
        y = row.get("y_norm", row.get("y", np.nan))
        df.at[idx, "location_zone"] = get_event_location_zone(x, y)

    # Identify possession sequences
    seq_df = identify_possession_sequences(df)

    # Initialize sequence columns
    df["sequence_id"] = -1
    df["sequence_type"] = "unknown"
    df["sequence_outcome"] = "unknown"

    if not seq_df.empty:
        for _, seq_row in seq_df.iterrows():
            sid = seq_row["sequence_id"]
            start = seq_row["start_idx"]
            end = seq_row["end_idx"]
            seq_type = classify_sequence_type(df, seq_row)
            outcome = seq_row["outcome"]

            mask = (df.index >= start) & (df.index <= end)
            df.loc[mask, "sequence_id"] = sid
            df.loc[mask, "sequence_type"] = seq_type
            df.loc[mask, "sequence_outcome"] = outcome

    return df
