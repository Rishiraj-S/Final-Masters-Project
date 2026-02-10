"""Possession phase analysis for Barcelona matches."""
from __future__ import annotations

from collections import defaultdict

import numpy as np
import pandas as pd

from barcelona_postmatch_app.config import EVENT_TYPES, SET_PIECE_QUALIFIERS
from barcelona_postmatch_app.processing.event_processor import (
    calculate_sequence_metrics,
    is_progressive_pass,
)
from barcelona_postmatch_app.utils.helpers import qualifier_is_set


def classify_possession_phases(events_df: pd.DataFrame) -> dict:
    """Classify and aggregate Barcelona's possession into phases.

    Returns dict with keys:
        sequences_df: DataFrame of all sequences with metrics
        phase_summary: dict of phase_type -> aggregated metrics
        passing_networks: dict of phase_type -> network data
        final_third_entries: dict of entry_method -> count
    """
    from barcelona_postmatch_app.processing.event_processor import identify_possession_sequences

    seq_df = identify_possession_sequences(events_df)

    if seq_df.empty:
        return {
            "sequences_df": pd.DataFrame(),
            "phase_summary": {},
            "passing_networks": {},
            "final_third_entries": {},
        }

    # Only Barcelona sequences
    barca_seq = seq_df[seq_df["is_barca"]].copy()

    # Add sequence type from event processor
    from barcelona_postmatch_app.processing.event_processor import classify_sequence_type
    barca_seq["sequence_type"] = barca_seq.apply(
        lambda r: classify_sequence_type(events_df, r), axis=1
    )

    # Calculate metrics per sequence
    metrics_list = []
    for _, seq_row in barca_seq.iterrows():
        m = calculate_sequence_metrics(events_df, seq_row)
        m["sequence_id"] = seq_row["sequence_id"]
        m["sequence_type"] = seq_row["sequence_type"]
        metrics_list.append(m)

    if metrics_list:
        metrics_df = pd.DataFrame(metrics_list)
        # Drop columns that already exist in barca_seq to avoid duplicates
        drop_cols = ["outcome", "event_count", "sequence_type", "duration"]
        merge_cols = metrics_df.drop(columns=[c for c in drop_cols if c in metrics_df.columns], errors="ignore")
        barca_seq = barca_seq.merge(
            merge_cols,
            on="sequence_id",
            how="left",
        )

    # Phase summary
    phase_summary = {}
    total_duration = events_df["match_seconds"].max() - events_df["match_seconds"].min()
    if total_duration <= 0:
        total_duration = 1

    for phase_type in ["build_up", "progression", "final_third", "transition", "set_piece"]:
        phase_seqs = barca_seq[barca_seq["sequence_type"] == phase_type]
        phase_summary[phase_type] = calculate_phase_metrics(phase_seqs, total_duration)

    # Build passing networks per phase
    passing_networks = {}
    for phase_type in ["build_up", "progression", "final_third"]:
        phase_seqs = barca_seq[barca_seq["sequence_type"] == phase_type]
        passing_networks[phase_type] = build_passing_network(events_df, phase_seqs)

    # Analyze final third entries
    final_third_entries = analyze_final_third_entries(events_df, barca_seq)

    return {
        "sequences_df": barca_seq,
        "phase_summary": phase_summary,
        "passing_networks": passing_networks,
        "final_third_entries": final_third_entries,
    }


def calculate_phase_metrics(phase_sequences: pd.DataFrame, total_duration: float) -> dict:
    """Calculate aggregated metrics for a possession phase."""
    if phase_sequences.empty:
        return {
            "count": 0, "total_duration": 0, "possession_pct": 0,
            "avg_duration": 0, "total_passes": 0, "pass_completion": 0,
            "progressive_passes": 0, "progressive_rate": 0,
            "avg_pass_length": 0, "pressure_resistance": 0,
            "outcomes": {},
        }

    count = len(phase_sequences)
    total_dur = float(phase_sequences["duration"].sum())
    possession_pct = (total_dur / total_duration * 100) if total_duration > 0 else 0

    total_passes = int(phase_sequences["pass_count"].sum()) if "pass_count" in phase_sequences else 0
    completed = int(phase_sequences["completed_passes"].sum()) if "completed_passes" in phase_sequences else 0
    progressive = int(phase_sequences["progressive_passes"].sum()) if "progressive_passes" in phase_sequences else 0

    up_count = int(phase_sequences["under_pressure_count"].sum()) if "under_pressure_count" in phase_sequences else 0
    up_completed = int(phase_sequences["under_pressure_completed"].sum()) if "under_pressure_completed" in phase_sequences else 0

    lengths = phase_sequences["avg_pass_length"] if "avg_pass_length" in phase_sequences else pd.Series(dtype=float)
    avg_len = float(lengths.mean()) if not lengths.empty else 0

    outcomes = phase_sequences["outcome"].value_counts().to_dict() if "outcome" in phase_sequences else {}

    return {
        "count": count,
        "total_duration": total_dur,
        "possession_pct": round(possession_pct, 1),
        "avg_duration": round(total_dur / count, 1) if count > 0 else 0,
        "total_passes": total_passes,
        "pass_completion": round(completed / total_passes * 100, 1) if total_passes > 0 else 0,
        "progressive_passes": progressive,
        "progressive_rate": round(progressive / total_passes * 100, 1) if total_passes > 0 else 0,
        "avg_pass_length": round(avg_len, 1),
        "pressure_resistance": round(up_completed / up_count * 100, 1) if up_count > 0 else 0,
        "outcomes": outcomes,
    }


def build_passing_network(events_df: pd.DataFrame, phase_sequences: pd.DataFrame) -> dict:
    """Build a passing network for the given phase sequences.

    Returns:
        {
            "nodes": {player_id: {"name": str, "avg_x": float, "avg_y": float, "pass_count": int}},
            "edges": {(from_id, to_id): count}
        }
    """
    nodes = defaultdict(lambda: {"name": "", "x_sum": 0, "y_sum": 0, "count": 0, "pass_count": 0})
    edges = defaultdict(int)

    for _, seq_row in phase_sequences.iterrows():
        start_idx = seq_row["start_idx"]
        end_idx = seq_row["end_idx"]

        mask = (
            (events_df.index >= start_idx) &
            (events_df.index <= end_idx) &
            (events_df["event_type_id"] == EVENT_TYPES["pass"]) &
            (events_df["outcome"] == 1) &
            (events_df["is_barca"])
        )
        passes = events_df.loc[mask]

        for i in range(len(passes)):
            p = passes.iloc[i]
            pid = str(p.get("player_id", ""))
            pname = str(p.get("player_name", ""))
            x = p.get("x_norm", p.get("x", np.nan))
            y = p.get("y_norm", p.get("y", np.nan))

            if pid and pid != "nan":
                nodes[pid]["name"] = pname
                if not np.isnan(x):
                    nodes[pid]["x_sum"] += x
                    nodes[pid]["y_sum"] += y
                    nodes[pid]["count"] += 1
                nodes[pid]["pass_count"] += 1

            # Find next event by same team to determine receiver
            if i + 1 < len(passes):
                next_p = passes.iloc[i + 1]
                next_pid = str(next_p.get("player_id", ""))
                if pid and next_pid and pid != "nan" and next_pid != "nan" and pid != next_pid:
                    edges[(pid, next_pid)] += 1

    # Compute averages
    node_data = {}
    for pid, data in nodes.items():
        if data["count"] > 0:
            node_data[pid] = {
                "name": data["name"],
                "avg_x": data["x_sum"] / data["count"],
                "avg_y": data["y_sum"] / data["count"],
                "pass_count": data["pass_count"],
            }

    return {"nodes": node_data, "edges": dict(edges)}


def analyze_final_third_entries(events_df: pd.DataFrame, barca_sequences: pd.DataFrame) -> dict:
    """Analyze how Barcelona enters the final third.

    Returns distribution of entry methods.
    """
    entries = defaultdict(int)

    for _, seq_row in barca_sequences.iterrows():
        start_idx = seq_row["start_idx"]
        end_idx = seq_row["end_idx"]

        mask = (events_df.index >= start_idx) & (events_df.index <= end_idx) & (events_df["is_barca"])
        seq_events = events_df.loc[mask]

        entered_final_third = False
        prev_x = None

        for _, evt in seq_events.iterrows():
            x = evt.get("x_norm", evt.get("x", np.nan))
            if np.isnan(x):
                continue

            # Check if this event enters the final third
            if x >= 66.7 and (prev_x is None or prev_x < 66.7):
                entered_final_third = True
                etype = evt["event_type_id"]

                if etype == EVENT_TYPES["pass"]:
                    if qualifier_is_set(evt.get("Through ball")):
                        entries["through_ball"] += 1
                    else:
                        entries["pass"] += 1
                elif etype == EVENT_TYPES["take_on"]:
                    entries["dribble"] += 1
                elif etype == EVENT_TYPES["ball_recovery"]:
                    entries["recovery"] += 1
                elif seq_row.get("sequence_type") == "set_piece":
                    entries["set_piece"] += 1
                else:
                    entries["other"] += 1
                break  # Only count the first entry per sequence

            prev_x = x

    return dict(entries)
