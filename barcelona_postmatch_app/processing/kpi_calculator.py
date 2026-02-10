"""Barcelona-specific KPI calculations."""
from __future__ import annotations

import numpy as np
import pandas as pd

from barcelona_postmatch_app.config import EVENT_TYPES, LEAGUE_AVERAGES, SHOT_TYPES
from barcelona_postmatch_app.utils.helpers import qualifier_is_set, safe_float


def calculate_all_kpis(processed_data: dict) -> dict:
    """Calculate all 10 Barcelona-specific KPIs.

    Args:
        processed_data: dict with keys:
            events: tagged events DataFrame
            phases: possession phase data from possession_analyzer
            transitions: transition data from transition_analyzer
            pressing: pressing data from transition_analyzer
            defensive: defensive data from defensive_analyzer

    Returns:
        dict of {kpi_name: {"value": ..., "unit": ..., "context": ..., "benchmark": ...}}
    """
    events = processed_data.get("events", pd.DataFrame())
    phases = processed_data.get("phases", {})
    transitions = processed_data.get("transitions", {})
    pressing = processed_data.get("pressing", {})
    defensive = processed_data.get("defensive", {})

    kpis = {}

    # KPI 1: Progressive Pass Rate
    kpis["progressive_pass_rate"] = _kpi_progressive_pass_rate(events)

    # KPI 2: Press Success Rate
    kpis["press_success_rate"] = _kpi_press_success_rate(pressing)

    # KPI 3: Transition Speed
    kpis["transition_speed"] = _kpi_transition_speed(transitions)

    # KPI 4: Final Third Entry Methods
    kpis["final_third_entries"] = _kpi_final_third_entries(phases)

    # KPI 5: Expected Possession Value
    kpis["epv_change"] = _kpi_epv_change(events, phases)

    # KPI 6: Pass Risk Profile
    kpis["pass_risk_profile"] = _kpi_pass_risk_profile(events)

    # KPI 7: Possession Efficiency
    kpis["possession_efficiency"] = _kpi_possession_efficiency(events, phases)

    # KPI 8: Defensive Compactness
    kpis["defensive_compactness"] = _kpi_defensive_compactness(defensive)

    # KPI 9: Press Intensity
    kpis["press_intensity"] = _kpi_press_intensity(pressing)

    # KPI 10: Phase Duration
    kpis["phase_duration"] = _kpi_phase_duration(phases)

    return kpis


def _kpi_progressive_pass_rate(events: pd.DataFrame) -> dict:
    """KPI 1: Progressive Pass Rate."""
    if events.empty:
        return _empty_kpi("Progressive Pass Rate", "%")

    barca_passes = events[
        (events["is_barca"]) &
        (events["event_type_id"] == EVENT_TYPES["pass"])
    ]
    total = len(barca_passes)
    progressive = barca_passes["is_progressive"].sum() if "is_progressive" in barca_passes else 0

    value = round(progressive / total * 100, 1) if total > 0 else 0

    return {
        "name": "Progressive Pass Rate",
        "value": value,
        "unit": "%",
        "detail": f"{int(progressive)} of {total} passes",
        "benchmark": LEAGUE_AVERAGES.get("progressive_pass_rate", 0),
        "context": _context_vs_benchmark(value, LEAGUE_AVERAGES.get("progressive_pass_rate", 0)),
    }


def _kpi_press_success_rate(pressing: dict) -> dict:
    """KPI 2: Press Success Rate."""
    metrics = pressing.get("metrics", {}) if isinstance(pressing, dict) else {}
    value = metrics.get("press_success_rate", 0)
    total = metrics.get("total_presses", 0)

    return {
        "name": "Press Success Rate",
        "value": value,
        "unit": "%",
        "detail": f"{total} pressing actions",
        "benchmark": LEAGUE_AVERAGES.get("press_success_rate", 0),
        "context": _context_vs_benchmark(value, LEAGUE_AVERAGES.get("press_success_rate", 0)),
    }


def _kpi_transition_speed(transitions: dict) -> dict:
    """KPI 3: Transition Speed."""
    metrics = transitions.get("metrics", {}) if isinstance(transitions, dict) else {}
    value = metrics.get("avg_transition_speed", 0)

    return {
        "name": "Transition Speed",
        "value": value,
        "unit": "sec",
        "detail": f"{metrics.get('total_transitions', 0)} transitions",
        "benchmark": LEAGUE_AVERAGES.get("transition_speed", 0),
        "context": "Faster" if value < LEAGUE_AVERAGES.get("transition_speed", 99) else "Slower" + " than avg",
    }


def _kpi_final_third_entries(phases: dict) -> dict:
    """KPI 4: Final Third Entry Methods."""
    entries = phases.get("final_third_entries", {}) if isinstance(phases, dict) else {}
    total = sum(entries.values()) if entries else 0

    if total == 0:
        return _empty_kpi("Final Third Entries", "count")

    distribution = {k: round(v / total * 100, 1) for k, v in entries.items()}

    return {
        "name": "Final Third Entries",
        "value": total,
        "unit": "entries",
        "detail": distribution,
        "benchmark": None,
        "context": f"Most common: {max(entries, key=entries.get) if entries else 'N/A'}",
    }


def _kpi_epv_change(events: pd.DataFrame, phases: dict) -> dict:
    """KPI 5: Expected Possession Value change (simplified as xG per phase)."""
    if events.empty:
        return _empty_kpi("xG by Phase", "xG")

    phase_summary = phases.get("phase_summary", {}) if isinstance(phases, dict) else {}

    # Calculate xG generated by Barcelona
    barca_shots = events[
        (events["is_barca"]) &
        (events["event_type_id"].isin(SHOT_TYPES))
    ]

    from barcelona_postmatch_app.utils.helpers import compute_xg_simple
    total_xg = 0.0
    for _, shot in barca_shots.iterrows():
        x = shot.get("x_norm", shot.get("x", np.nan))
        y = shot.get("y_norm", shot.get("y", np.nan))
        is_header = qualifier_is_set(shot.get("Head"))
        if not np.isnan(x):
            total_xg += compute_xg_simple(x, y, is_header)

    return {
        "name": "Total xG Generated",
        "value": round(total_xg, 2),
        "unit": "xG",
        "detail": f"{len(barca_shots)} shots",
        "benchmark": None,
        "context": f"From {len(barca_shots)} shots",
    }


def _kpi_pass_risk_profile(events: pd.DataFrame) -> dict:
    """KPI 6: Pass Risk Profile."""
    if events.empty:
        return _empty_kpi("Pass Risk Profile", "%")

    barca_passes = events[
        (events["is_barca"]) &
        (events["event_type_id"] == EVENT_TYPES["pass"])
    ]

    total = len(barca_passes)
    if total == 0:
        return _empty_kpi("Pass Risk Profile", "%")

    safe_count = 0
    medium_count = 0
    risky_count = 0

    for _, p in barca_passes.iterrows():
        length = safe_float(p.get("pass_length"))
        direction = p.get("direction", "unknown")

        if np.isnan(length):
            medium_count += 1
            continue

        if length < 15 and direction == "backward":
            safe_count += 1
        elif length < 15 and direction == "sideways":
            safe_count += 1
        elif length > 30 or (direction == "forward" and length > 20):
            risky_count += 1
        else:
            medium_count += 1

    return {
        "name": "Pass Risk Profile",
        "value": {
            "safe": round(safe_count / total * 100, 1),
            "medium": round(medium_count / total * 100, 1),
            "risky": round(risky_count / total * 100, 1),
        },
        "unit": "%",
        "detail": f"{total} total passes",
        "benchmark": None,
        "context": "Risk distribution of passes",
    }


def _kpi_possession_efficiency(events: pd.DataFrame, phases: dict) -> dict:
    """KPI 7: Possession Efficiency (shots per 100 possessions)."""
    seq_df = phases.get("sequences_df", pd.DataFrame()) if isinstance(phases, dict) else pd.DataFrame()

    if seq_df is None or (isinstance(seq_df, pd.DataFrame) and seq_df.empty):
        return _empty_kpi("Possession Efficiency", "shots/100 poss")

    total_sequences = len(seq_df)
    shot_sequences = len(seq_df[seq_df["outcome"] == "shot"]) if "outcome" in seq_df else 0

    value = round(shot_sequences / total_sequences * 100, 1) if total_sequences > 0 else 0

    return {
        "name": "Possession Efficiency",
        "value": value,
        "unit": "shots/100 poss",
        "detail": f"{shot_sequences} shots from {total_sequences} possessions",
        "benchmark": LEAGUE_AVERAGES.get("possession_efficiency", 0),
        "context": _context_vs_benchmark(value, LEAGUE_AVERAGES.get("possession_efficiency", 0)),
    }


def _kpi_defensive_compactness(defensive: dict) -> dict:
    """KPI 8: Defensive Compactness Index."""
    metrics = defensive.get("metrics", {}) if isinstance(defensive, dict) else {}
    value = metrics.get("compactness_index", 0)

    return {
        "name": "Defensive Compactness",
        "value": value,
        "unit": "index",
        "detail": f"Line depth: {metrics.get('avg_line_depth', 0)}",
        "benchmark": LEAGUE_AVERAGES.get("defensive_compactness", 0),
        "context": _context_vs_benchmark(value, LEAGUE_AVERAGES.get("defensive_compactness", 0)),
    }


def _kpi_press_intensity(pressing: dict) -> dict:
    """KPI 9: Press Intensity Index."""
    metrics = pressing.get("metrics", {}) if isinstance(pressing, dict) else {}
    value = metrics.get("avg_intensity", 0)

    return {
        "name": "Press Intensity",
        "value": value,
        "unit": "defenders/press",
        "detail": f"{metrics.get('total_presses', 0)} pressing events",
        "benchmark": LEAGUE_AVERAGES.get("press_intensity", 0),
        "context": _context_vs_benchmark(value, LEAGUE_AVERAGES.get("press_intensity", 0)),
    }


def _kpi_phase_duration(phases: dict) -> dict:
    """KPI 10: Average Phase Duration."""
    phase_summary = phases.get("phase_summary", {}) if isinstance(phases, dict) else {}

    durations = {}
    for phase_type in ["build_up", "progression", "final_third"]:
        pm = phase_summary.get(phase_type, {})
        durations[phase_type] = pm.get("avg_duration", 0) if isinstance(pm, dict) else 0

    return {
        "name": "Avg Phase Duration",
        "value": durations,
        "unit": "sec",
        "detail": "By possession phase",
        "benchmark": None,
        "context": "Build-up longest = patient approach" if durations.get("build_up", 0) > durations.get("final_third", 0) else "Direct approach",
    }


def _context_vs_benchmark(value: float, benchmark: float) -> str:
    """Generate context string comparing value to benchmark."""
    if benchmark == 0:
        return "No benchmark"
    diff = value - benchmark
    pct = round(abs(diff) / benchmark * 100, 0)
    if diff > 0:
        return f"{pct}% above league avg ({benchmark})"
    elif diff < 0:
        return f"{pct}% below league avg ({benchmark})"
    return f"At league average ({benchmark})"


def _empty_kpi(name: str, unit: str) -> dict:
    return {
        "name": name,
        "value": 0,
        "unit": unit,
        "detail": "No data",
        "benchmark": None,
        "context": "Insufficient data",
    }
