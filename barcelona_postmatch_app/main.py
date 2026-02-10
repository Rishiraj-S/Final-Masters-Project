"""Barcelona Post-Match Analysis App - Streamlit Entry Point."""
from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

# Add project root to path so imports work when running via `streamlit run`
_project_root = str(Path(__file__).resolve().parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from barcelona_postmatch_app.config import BARCELONA_PRIMARY, BARCELONA_SECONDARY, BARCELONA_GOLD
from barcelona_postmatch_app.data.loader import load_available_matches, load_match_data
from barcelona_postmatch_app.processing.event_processor import tag_all_events
from barcelona_postmatch_app.processing.possession_analyzer import classify_possession_phases
from barcelona_postmatch_app.processing.transition_analyzer import (
    identify_attacking_transitions,
    identify_pressing_moments,
    calculate_pressing_metrics,
)
from barcelona_postmatch_app.processing.set_piece_analyzer import detect_set_pieces
from barcelona_postmatch_app.processing.defensive_analyzer import analyze_defensive_shape
from barcelona_postmatch_app.processing.kpi_calculator import calculate_all_kpis
from barcelona_postmatch_app.visualization import (
    match_overview,
    possession_analysis,
    transitions_analysis,
    set_pieces_analysis,
    defensive_analysis,
    kpi_dashboard,
)

# ──────────────────────────────────────────────────────────────
# Page config
# ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Barcelona Post-Match Analysis",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ──────────────────────────────────────────────────────────────
# Custom CSS
# ──────────────────────────────────────────────────────────────
st.markdown(f"""
<style>
    .stApp {{
        background-color: #0E1117;
    }}
    .stTabs [data-baseweb="tab-list"] {{
        gap: 8px;
    }}
    .stTabs [data-baseweb="tab"] {{
        background-color: {BARCELONA_SECONDARY}20;
        border-radius: 4px;
        padding: 8px 16px;
    }}
    .stTabs [aria-selected="true"] {{
        background-color: {BARCELONA_PRIMARY};
    }}
    .stMetric > div {{
        background-color: {BARCELONA_SECONDARY}10;
        padding: 10px;
        border-radius: 8px;
        border-left: 3px solid {BARCELONA_PRIMARY};
    }}
</style>
""", unsafe_allow_html=True)


# ──────────────────────────────────────────────────────────────
# Sidebar
# ──────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown(f"""
    <h2 style='color:{BARCELONA_GOLD};'>Barcelona Post-Match Analysis</h2>
    """, unsafe_allow_html=True)

    st.caption("Tactical insights from Opta event data")

    # Load available matches
    with st.spinner("Loading match list..."):
        available_matches = load_available_matches()

    if not available_matches:
        st.error("No Barcelona match data found. Check that `opta_pipeline/data/result/` contains parquet files.")
        st.stop()

    # Match selector
    match_labels = [m["label"] for m in available_matches]
    selected_idx = st.selectbox(
        "Select Match",
        range(len(match_labels)),
        format_func=lambda i: match_labels[i],
    )
    selected_match = available_matches[selected_idx]

    st.divider()

    # Time period filter
    time_period = st.radio(
        "Analyze Period",
        ["Full Match", "First Half", "Second Half"],
        horizontal=True,
    )

    st.divider()
    st.caption(f"Match: {selected_match['description']}")
    st.caption(f"Date: {selected_match['date']}")
    st.caption(f"League: {selected_match['league'].replace('_', ' ')}")
    st.caption(f"Season: {selected_match['season']}")


# ──────────────────────────────────────────────────────────────
# Main content
# ──────────────────────────────────────────────────────────────

@st.cache_data(show_spinner="Loading match data...")
def _load_match(match_parquet: str, event_parquet: str, match_id: str):
    """Load and return match data (cached by file paths)."""
    match_info = {
        "match_parquet": match_parquet,
        "event_parquet": event_parquet,
        "match_id": match_id,
    }
    return load_match_data(match_info)


@st.cache_data(show_spinner="Processing match events...")
def _process_match(
    _events_hash: str,
    events_parquet: str,
    match_parquet: str,
    match_id: str,
    period_filter: str,
):
    """Process all match data (cached)."""
    match_info = {
        "match_parquet": match_parquet,
        "event_parquet": events_parquet,
        "match_id": match_id,
    }
    events_df, metadata = load_match_data(match_info)

    # Apply period filter
    if period_filter == "First Half":
        events_df = events_df[events_df["period_id"] == 1].copy()
    elif period_filter == "Second Half":
        events_df = events_df[events_df["period_id"] == 2].copy()

    # Tag all events
    events_tagged = tag_all_events(events_df)

    # Run all analyzers
    phases = classify_possession_phases(events_tagged)
    seq_df = phases.get("sequences_df", None)

    transitions = identify_attacking_transitions(events_tagged, seq_df)
    pressing_moments = identify_pressing_moments(events_tagged)
    pressing_metrics = calculate_pressing_metrics(pressing_moments)
    pressing_data = {"pressing_moments": pressing_moments, "metrics": pressing_metrics}

    set_pieces = detect_set_pieces(events_tagged)
    defensive = analyze_defensive_shape(events_tagged)

    kpis = calculate_all_kpis({
        "events": events_tagged,
        "phases": phases,
        "transitions": transitions,
        "pressing": pressing_data,
        "defensive": defensive,
    })

    return events_tagged, metadata, phases, transitions, pressing_data, set_pieces, defensive, kpis


# Load and process
try:
    events_hash = f"{selected_match['match_id']}_{time_period}"

    (
        events_df,
        metadata,
        phases,
        transitions,
        pressing_data,
        set_pieces,
        defensive,
        kpis,
    ) = _process_match(
        events_hash,
        selected_match["event_parquet"],
        selected_match["match_parquet"],
        selected_match["match_id"],
        time_period,
    )
except FileNotFoundError as e:
    st.error(f"Could not load match data: {e}")
    st.stop()
except Exception as e:
    st.error(f"Error processing match: {e}")
    st.exception(e)
    st.stop()


# ──────────────────────────────────────────────────────────────
# Tabs
# ──────────────────────────────────────────────────────────────
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "Match Overview",
    "Possession Analysis",
    "Transitions",
    "Set Pieces",
    "Defensive Performance",
    "KPI Dashboard",
])

with tab1:
    match_overview.render(metadata, events_df)

with tab2:
    possession_analysis.render(phases, events_df)

with tab3:
    transitions_analysis.render(transitions, events_df, pressing_data)

with tab4:
    set_pieces_analysis.render(set_pieces, events_df)

with tab5:
    defensive_analysis.render(defensive, events_df)

with tab6:
    kpi_dashboard.render(kpis)
