"""Tab 2: Possession Analysis - deep dive into Barcelona's possession patterns."""
from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from barcelona_postmatch_app.config import (
    BARCELONA_GOLD,
    BARCELONA_PRIMARY,
    BARCELONA_SECONDARY,
    EVENT_TYPES,
)
from barcelona_postmatch_app.visualization.utils import (
    draw_pitch,
    plot_heatmap_on_pitch,
    plot_passing_network_on_pitch,
)

PHASE_COLORS = {
    "build_up": "#4ECDC4",
    "progression": "#45B7D1",
    "final_third": "#FF6B6B",
    "transition": "#FFA07A",
    "set_piece": "#DDA0DD",
    "other": "#888888",
}


def render(phases: dict, events_df: pd.DataFrame) -> None:
    """Render the Possession Analysis tab."""
    if not phases or not isinstance(phases, dict):
        st.warning("No possession data available for this match.")
        return

    phase_summary = phases.get("phase_summary", {})
    seq_df = phases.get("sequences_df", pd.DataFrame())
    passing_networks = phases.get("passing_networks", {})
    final_third_entries = phases.get("final_third_entries", {})

    # Row 1: Possession breakdown + pass direction
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Possession by Phase")
        fig = plot_possession_breakdown(phase_summary)
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader("Pass Direction Distribution")
        fig = plot_pass_direction_distribution(events_df)
        st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # Row 2: Phase metrics table
    st.subheader("Phase Metrics")
    _display_phase_metrics_table(phase_summary)

    st.divider()

    # Row 3: Passing networks
    st.subheader("Passing Networks by Phase")
    net_cols = st.columns(3)
    for i, (phase, title) in enumerate([
        ("build_up", "Build-Up"),
        ("progression", "Progression"),
        ("final_third", "Final Third"),
    ]):
        with net_cols[i]:
            network = passing_networks.get(phase, {})
            fig = plot_passing_network(network, title)
            st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # Row 4: Progressive passes + final third entries
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Progressive Passes")
        fig = plot_progressive_passes(events_df)
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader("Final Third Entry Methods")
        fig = plot_final_third_entries(final_third_entries)
        st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # Row 5: Pressure resistance
    st.subheader("Pressure Resistance by Phase")
    fig = plot_pressure_resistance(phase_summary)
    st.plotly_chart(fig, use_container_width=True)


def plot_possession_breakdown(phase_summary: dict) -> go.Figure:
    """Pie chart of possession time by phase."""
    labels = []
    values = []
    colors = []

    for phase, metrics in phase_summary.items():
        if isinstance(metrics, dict) and metrics.get("total_duration", 0) > 0:
            labels.append(phase.replace("_", " ").title())
            values.append(metrics["total_duration"])
            colors.append(PHASE_COLORS.get(phase, "#888888"))

    if not labels:
        fig = go.Figure()
        fig.add_annotation(text="No possession data", showarrow=False, font=dict(size=16))
        return fig

    fig = go.Figure(data=[go.Pie(
        labels=labels,
        values=values,
        marker=dict(colors=colors),
        textinfo="label+percent",
        hole=0.4,
    )])

    fig.update_layout(
        height=350,
        margin=dict(t=20, b=20),
        showlegend=True,
        legend=dict(orientation="h", y=-0.1),
    )
    return fig


def plot_pass_direction_distribution(events_df: pd.DataFrame) -> go.Figure:
    """Bar chart of forward vs sideways vs backward passes."""
    barca_passes = events_df[
        (events_df["is_barca"]) &
        (events_df["event_type_id"] == EVENT_TYPES["pass"]) &
        (events_df["direction"] != "unknown")
    ]

    if barca_passes.empty:
        fig = go.Figure()
        fig.add_annotation(text="No pass data", showarrow=False, font=dict(size=16))
        return fig

    direction_counts = barca_passes["direction"].value_counts()
    total = len(barca_passes)

    categories = ["forward", "sideways", "backward"]
    counts = [direction_counts.get(d, 0) for d in categories]
    pcts = [round(c / total * 100, 1) for c in counts]
    colors = ["#FF6B6B", "#45B7D1", "#4ECDC4"]

    fig = go.Figure(data=[go.Bar(
        x=[c.title() for c in categories],
        y=pcts,
        marker_color=colors,
        text=[f"{p}%<br>({c})" for p, c in zip(pcts, counts)],
        textposition="auto",
    )])

    fig.update_layout(
        yaxis=dict(title="% of Passes"),
        height=350,
        margin=dict(t=20),
    )
    return fig


def plot_passing_network(network: dict, title: str) -> go.Figure:
    """Draw a passing network on the pitch for a specific phase."""
    nodes = network.get("nodes", {})
    edges = network.get("edges", {})

    fig = plot_passing_network_on_pitch(nodes, edges, title=title, min_passes=1)
    fig.update_layout(height=400)
    return fig


def plot_progressive_passes(events_df: pd.DataFrame) -> go.Figure:
    """Scatter plot of progressive passes on pitch."""
    fig = draw_pitch()

    prog_passes = events_df[
        (events_df["is_barca"]) &
        (events_df["event_type_id"] == EVENT_TYPES["pass"]) &
        (events_df["is_progressive"] == True)
    ]

    if prog_passes.empty:
        fig.update_layout(title="No progressive passes")
        return fig

    for _, p in prog_passes.iterrows():
        x = p.get("x_norm", p.get("x", np.nan))
        y = p.get("y_norm", p.get("y", np.nan))
        xe = p.get("x_end_norm", p.get("x_end", np.nan))
        ye = p.get("y_end_norm", p.get("y_end", np.nan))

        if any(np.isnan(v) for v in [x, y, xe, ye]):
            continue

        fig.add_trace(go.Scatter(
            x=[x, xe], y=[y, ye],
            mode="lines+markers",
            marker=dict(size=[6, 8], color=[BARCELONA_SECONDARY, BARCELONA_PRIMARY]),
            line=dict(color=BARCELONA_GOLD, width=1.5),
            hoverinfo="text",
            text=f"{p.get('player_name', '')}<br>{p.get('minute', '')}'",
            showlegend=False,
        ))

    fig.update_layout(title=f"Progressive Passes ({len(prog_passes)})", height=450)
    return fig


def plot_final_third_entries(entries: dict) -> go.Figure:
    """Pie chart of final third entry methods."""
    if not entries:
        fig = go.Figure()
        fig.add_annotation(text="No final third entries", showarrow=False, font=dict(size=16))
        return fig

    labels = [k.replace("_", " ").title() for k in entries.keys()]
    values = list(entries.values())
    colors = ["#FF6B6B", "#45B7D1", "#4ECDC4", "#FFA07A", "#DDA0DD", "#888888"]

    fig = go.Figure(data=[go.Pie(
        labels=labels,
        values=values,
        marker=dict(colors=colors[:len(labels)]),
        textinfo="label+percent+value",
        hole=0.3,
    )])

    fig.update_layout(height=350, margin=dict(t=20, b=20))
    return fig


def plot_pressure_resistance(phase_summary: dict) -> go.Figure:
    """Bar chart of pressure resistance by phase."""
    phases = []
    resistances = []
    colors = []

    for phase, metrics in phase_summary.items():
        if isinstance(metrics, dict):
            phases.append(phase.replace("_", " ").title())
            resistances.append(metrics.get("pressure_resistance", 0))
            colors.append(PHASE_COLORS.get(phase, "#888888"))

    if not phases:
        fig = go.Figure()
        fig.add_annotation(text="No data", showarrow=False)
        return fig

    fig = go.Figure(data=[go.Bar(
        x=phases,
        y=resistances,
        marker_color=colors,
        text=[f"{r}%" for r in resistances],
        textposition="auto",
    )])

    fig.update_layout(
        yaxis=dict(title="Pressure Resistance (%)", range=[0, 100]),
        height=350,
    )
    return fig


def _display_phase_metrics_table(phase_summary: dict) -> None:
    """Display a table of metrics for each phase."""
    rows = []
    for phase, metrics in phase_summary.items():
        if not isinstance(metrics, dict):
            continue
        rows.append({
            "Phase": phase.replace("_", " ").title(),
            "Sequences": metrics.get("count", 0),
            "Avg Duration (s)": metrics.get("avg_duration", 0),
            "Possession %": metrics.get("possession_pct", 0),
            "Total Passes": metrics.get("total_passes", 0),
            "Pass Completion %": metrics.get("pass_completion", 0),
            "Progressive Passes": metrics.get("progressive_passes", 0),
            "Pressure Resistance %": metrics.get("pressure_resistance", 0),
        })

    if rows:
        st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
    else:
        st.info("No phase metrics available.")
