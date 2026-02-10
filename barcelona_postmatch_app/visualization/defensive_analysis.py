"""Tab 5: Defensive Performance - defensive structure, duels, and threats."""
from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from barcelona_postmatch_app.config import (
    BARCELONA_GOLD,
    BARCELONA_PRIMARY,
    BARCELONA_SECONDARY,
)
from barcelona_postmatch_app.visualization.utils import (
    draw_pitch,
    get_color_by_performance,
    plot_heatmap_on_pitch,
)


def render(defensive_data: dict, events_df: pd.DataFrame) -> None:
    """Render the Defensive Performance tab."""
    if not defensive_data or not isinstance(defensive_data, dict):
        st.warning("No defensive data available.")
        return

    metrics = defensive_data.get("metrics", {})
    formation_data = defensive_data.get("formation_data", {})
    shape_timeline = defensive_data.get("shape_timeline", [])
    duels = defensive_data.get("duels", [])
    duel_metrics = defensive_data.get("duel_metrics", {})
    interceptions = defensive_data.get("interceptions", [])
    opp_threat = defensive_data.get("opposition_threat", {})

    # Metrics row
    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Formation", formation_data.get("primary_formation", "N/A"))
    col2.metric("Compactness", f"{metrics.get('compactness_index', 0)}")
    col3.metric("Duel Win Rate", f"{metrics.get('duel_win_rate', 0)}%")
    col4.metric("Interceptions", metrics.get("total_interceptions", 0))
    col5.metric("xGA", metrics.get("total_xga", 0))

    st.divider()

    # Row 1: Formation + Compactness timeline
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Average Positions (Defensive)")
        fig = plot_formation_diagram(events_df)
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader("Defensive Compactness Over Time")
        fig = plot_compactness_timeline(shape_timeline)
        st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # Row 2: Duels
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Duel Locations")
        fig = plot_duel_heatmap(duels)
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader("Duel Success Rate by Type")
        fig = plot_duel_success_rate(duel_metrics)
        st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # Row 3: Interceptions + Opposition threats
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Interception Map")
        fig = plot_interception_heatmap(interceptions)
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader("Opposition Threat Map (xGA)")
        fig = plot_xga_heatmap(opp_threat)
        st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # Player duel performance table
    st.subheader("Player Duel Performance")
    _display_player_duel_table(duel_metrics)


def plot_formation_diagram(events_df: pd.DataFrame) -> go.Figure:
    """Plot average player positions on the pitch."""
    fig = draw_pitch()

    barca_events = events_df[
        (events_df["is_barca"]) &
        (events_df["player_id"].notna()) &
        (events_df["player_name"].notna()) &
        (events_df["x_norm"].notna()) &
        (events_df["y_norm"].notna())
    ]

    if barca_events.empty:
        fig.update_layout(title="No position data")
        return fig

    # Calculate average position per player
    player_positions = barca_events.groupby("player_id").agg(
        avg_x=("x_norm", "mean"),
        avg_y=("y_norm", "mean"),
        name=("player_name", "first"),
        events=("event_id", "count"),
    ).reset_index()

    # Filter to players with enough events (likely starters)
    player_positions = player_positions[player_positions["events"] >= 5]
    player_positions = player_positions.nlargest(11, "events")

    for _, player in player_positions.iterrows():
        fig.add_trace(go.Scatter(
            x=[player["avg_x"]],
            y=[player["avg_y"]],
            mode="markers+text",
            marker=dict(
                size=25,
                color=BARCELONA_PRIMARY,
                line=dict(width=2, color=BARCELONA_GOLD),
            ),
            text=player["name"].split()[-1] if isinstance(player["name"], str) else "",
            textposition="top center",
            textfont=dict(color="white", size=10),
            hoverinfo="text",
            hovertext=f"{player['name']}<br>Avg pos: ({player['avg_x']:.1f}, {player['avg_y']:.1f})<br>Events: {player['events']}",
            showlegend=False,
        ))

    fig.update_layout(title="Average Defensive Positions", height=450)
    return fig


def plot_compactness_timeline(shape_timeline: list[dict]) -> go.Figure:
    """Line chart of compactness index over time."""
    fig = go.Figure()

    if not shape_timeline:
        fig.add_annotation(text="No compactness data", showarrow=False)
        return fig

    minutes = [(s["minute_start"] + s["minute_end"]) / 2 for s in shape_timeline]
    compactness = [s["compactness"] for s in shape_timeline]
    line_depth = [s["line_depth"] for s in shape_timeline]

    fig.add_trace(go.Scatter(
        x=minutes, y=compactness,
        mode="lines+markers",
        name="Compactness Index",
        line=dict(color=BARCELONA_PRIMARY, width=3),
        marker=dict(size=6),
    ))

    fig.add_trace(go.Scatter(
        x=minutes, y=line_depth,
        mode="lines+markers",
        name="Line Depth",
        line=dict(color=BARCELONA_GOLD, width=2, dash="dot"),
        marker=dict(size=5),
        yaxis="y2",
    ))

    fig.add_vline(x=45, line_dash="dash", line_color="white", opacity=0.3)

    fig.update_layout(
        xaxis=dict(title="Minute"),
        yaxis=dict(title="Compactness (0-100)", range=[0, 100]),
        yaxis2=dict(
            title="Line Depth (Opta x)", overlaying="y", side="right",
            range=[0, 60],
        ),
        height=350,
        legend=dict(x=0.02, y=0.98),
    )
    return fig


def plot_duel_heatmap(duels: list[dict]) -> go.Figure:
    """Heatmap of duel locations."""
    if not duels:
        fig = draw_pitch()
        fig.update_layout(title="No duel data")
        return fig

    x_vals = [d["x"] for d in duels if not np.isnan(d.get("x", np.nan))]
    y_vals = [d["y"] for d in duels if not np.isnan(d.get("y", np.nan))]

    fig = plot_heatmap_on_pitch(x_vals, y_vals, "Duel Locations")
    return fig


def plot_duel_success_rate(duel_metrics: dict) -> go.Figure:
    """Bar chart of duel success rate by type."""
    categories = ["Total", "Aerial", "Ground"]
    rates = [
        duel_metrics.get("win_rate", 0),
        duel_metrics.get("aerial_rate", 0),
        duel_metrics.get("ground_rate", 0),
    ]
    totals = [
        duel_metrics.get("total", 0),
        duel_metrics.get("aerial_total", 0),
        duel_metrics.get("ground_total", 0),
    ]

    colors = [get_color_by_performance(r) for r in rates]

    fig = go.Figure(data=[go.Bar(
        x=categories,
        y=rates,
        marker_color=colors,
        text=[f"{r}%<br>(n={t})" for r, t in zip(rates, totals)],
        textposition="auto",
    )])

    fig.update_layout(
        yaxis=dict(title="Win Rate (%)", range=[0, 100]),
        height=350,
    )
    return fig


def plot_interception_heatmap(interceptions: list[dict]) -> go.Figure:
    """Heatmap of interception locations."""
    if not interceptions:
        fig = draw_pitch()
        fig.update_layout(title="No interceptions")
        return fig

    x_vals = [i["x"] for i in interceptions if not np.isnan(i.get("x", np.nan))]
    y_vals = [i["y"] for i in interceptions if not np.isnan(i.get("y", np.nan))]

    fig = plot_heatmap_on_pitch(x_vals, y_vals, "Interception Locations")
    return fig


def plot_xga_heatmap(opp_threat: dict) -> go.Figure:
    """Heatmap of opposition shot locations (xGA)."""
    shots = opp_threat.get("shots", [])

    if not shots:
        fig = draw_pitch()
        fig.update_layout(title="No opposition shots")
        return fig

    fig = draw_pitch()

    for s in shots:
        x = s.get("x", np.nan)
        y = s.get("y", np.nan)
        if np.isnan(x) or np.isnan(y):
            continue

        xg = s.get("xg", 0)
        size = max(8, xg * 40)
        color = BARCELONA_GOLD if s.get("is_goal") else ("#FF4444" if s.get("is_on_target") else "#888888")

        fig.add_trace(go.Scatter(
            x=[x], y=[y],
            mode="markers",
            marker=dict(size=size, color=color, line=dict(width=1, color="white")),
            hoverinfo="text",
            text=f"{s.get('player_name', 'Unknown')}<br>xG: {xg:.2f}<br>{s.get('event_type', '')}<br>{s.get('minute', '')}'",
            showlegend=False,
        ))

    fig.update_layout(
        title=f"Opposition Shots (xGA: {opp_threat.get('total_xga', 0)})",
        height=450,
    )
    return fig


def _display_player_duel_table(duel_metrics: dict) -> None:
    """Display per-player duel performance table."""
    player_perf = duel_metrics.get("player_performance", {})

    if not player_perf:
        st.info("No player duel data available.")
        return

    rows = []
    for pid, data in player_perf.items():
        rows.append({
            "Player": data.get("name", "Unknown"),
            "Total Duels": data.get("total", 0),
            "Won": data.get("won", 0),
            "Win Rate (%)": data.get("rate", 0),
        })

    df = pd.DataFrame(rows).sort_values("Total Duels", ascending=False)
    st.dataframe(df, hide_index=True, use_container_width=True)
