"""Tab 4: Set Piece Analysis - attacking and defensive set pieces."""
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
    get_team_colors,
    plot_heatmap_on_pitch,
)


def render(set_piece_data: dict, events_df: pd.DataFrame) -> None:
    """Render the Set Pieces tab."""
    if not set_piece_data or not isinstance(set_piece_data, dict):
        st.warning("No set piece data available.")
        return

    tab_a, tab_b = st.tabs(["Attacking Set Pieces", "Defensive Set Pieces"])

    with tab_a:
        _render_attacking(set_piece_data, events_df)

    with tab_b:
        _render_defensive(set_piece_data, events_df)


def _render_attacking(data: dict, events_df: pd.DataFrame) -> None:
    """Render attacking set pieces sub-tab."""
    attacking = data.get("attacking", [])
    metrics = data.get("metrics", {}).get("attacking", {})

    # Metrics row
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Set Pieces", metrics.get("total", 0))
    col2.metric("Shots Created", metrics.get("shots", 0))
    col3.metric("Goals Scored", metrics.get("goals", 0))
    col4.metric("Conversion Rate", f"{metrics.get('conversion_rate', 0)}%")

    st.divider()

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Set Piece Delivery Locations")
        fig = plot_corner_delivery_heatmap(attacking)
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader("Delivery Type Effectiveness")
        fig = plot_delivery_effectiveness(metrics.get("delivery_effectiveness", {}))
        st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # Set pieces by type
    st.subheader("Set Pieces by Type")
    by_type = metrics.get("by_type", {})
    if by_type:
        _display_type_breakdown(by_type)

    st.divider()

    # Outcomes table
    st.subheader("All Attacking Set Pieces")
    create_set_piece_outcomes_table(attacking)


def _render_defensive(data: dict, events_df: pd.DataFrame) -> None:
    """Render defensive set pieces sub-tab."""
    defensive = data.get("defensive", [])
    metrics = data.get("metrics", {}).get("defensive", {})

    # Metrics row
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Opp. Set Pieces", metrics.get("total", 0))
    col2.metric("Shots Conceded", metrics.get("shots_conceded", 0))
    col3.metric("Goals Conceded", metrics.get("goals_conceded", 0))
    col4.metric("xG Against", metrics.get("xg_against", 0))

    st.divider()

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Opposition Set Piece Threat Areas")
        fig = plot_opposition_threats(defensive)
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader("Defensive Set Pieces by Type")
        by_type = metrics.get("by_type", {})
        if by_type:
            _display_type_breakdown(by_type)
        else:
            st.info("No defensive set piece data.")

    st.divider()

    st.subheader("All Defensive Set Pieces")
    create_set_piece_outcomes_table(defensive, defending=True)


def plot_corner_delivery_heatmap(set_pieces: list[dict]) -> go.Figure:
    """Heatmap of set piece delivery start and end locations."""
    fig = draw_pitch()

    if not set_pieces:
        fig.update_layout(title="No set piece data")
        return fig

    for sp in set_pieces:
        x = sp.get("x", np.nan)
        y = sp.get("y", np.nan)
        xe = sp.get("x_end", np.nan)
        ye = sp.get("y_end", np.nan)

        if np.isnan(x) or np.isnan(y):
            continue

        # Draw delivery origin
        fig.add_trace(go.Scatter(
            x=[x], y=[y],
            mode="markers",
            marker=dict(size=8, color=BARCELONA_SECONDARY, symbol="circle"),
            hoverinfo="text",
            text=f"{sp.get('type', '')} by {sp.get('player_name', '')}<br>{sp.get('minute', '')}' - {sp.get('outcome', '')}",
            showlegend=False,
        ))

        # Draw delivery path if end coordinates available
        if not np.isnan(xe) and not np.isnan(ye):
            color = BARCELONA_GOLD if sp.get("has_shot") else "rgba(255,255,255,0.3)"
            fig.add_trace(go.Scatter(
                x=[x, xe], y=[y, ye],
                mode="lines",
                line=dict(color=color, width=1.5, dash="dot"),
                showlegend=False,
                hoverinfo="skip",
            ))

    fig.update_layout(title="Set Piece Deliveries", height=450)
    return fig


def plot_delivery_effectiveness(delivery_eff: dict) -> go.Figure:
    """Bar chart of delivery type effectiveness."""
    if not delivery_eff:
        fig = go.Figure()
        fig.add_annotation(text="No delivery data", showarrow=False)
        fig.update_layout(height=350)
        return fig

    types = []
    shot_rates = []
    totals = []

    for dt, data in delivery_eff.items():
        if isinstance(data, dict) and data.get("total", 0) > 0:
            types.append(dt.replace("_", " ").title())
            rate = data["shots"] / data["total"] * 100
            shot_rates.append(round(rate, 1))
            totals.append(data["total"])

    fig = go.Figure(data=[go.Bar(
        x=types,
        y=shot_rates,
        marker_color=BARCELONA_PRIMARY,
        text=[f"{r}%<br>(n={t})" for r, t in zip(shot_rates, totals)],
        textposition="auto",
    )])

    fig.update_layout(
        yaxis=dict(title="Shot Conversion Rate (%)", range=[0, 100]),
        height=350,
    )
    return fig


def plot_opposition_threats(defensive_sps: list[dict]) -> go.Figure:
    """Heatmap of opposition set piece threat locations."""
    if not defensive_sps:
        fig = draw_pitch()
        fig.update_layout(title="No opposition set piece threats")
        return fig

    x_vals = [sp["x"] for sp in defensive_sps if not np.isnan(sp.get("x", np.nan))]
    y_vals = [sp["y"] for sp in defensive_sps if not np.isnan(sp.get("y", np.nan))]

    fig = plot_heatmap_on_pitch(x_vals, y_vals, "Opposition Set Piece Threats")
    return fig


def create_set_piece_outcomes_table(set_pieces: list[dict], defending: bool = False) -> None:
    """Display table of all set pieces with outcomes."""
    if not set_pieces:
        st.info("No set pieces to display.")
        return

    rows = []
    for sp in set_pieces:
        rows.append({
            "Minute": sp.get("minute", ""),
            "Type": sp.get("type", "").replace("_", " ").title(),
            "Taker": sp.get("player_name", ""),
            "Delivery": sp.get("delivery", {}).get("type", "standard").title(),
            "Outcome": sp.get("outcome", "").replace("_", " ").title(),
            "Shot?": "Yes" if sp.get("has_shot") else "No",
            "Goal?": "Yes" if sp.get("has_goal") else "No",
            "xG": round(sp.get("xg", 0), 2),
        })

    df = pd.DataFrame(rows)
    st.dataframe(df, hide_index=True, use_container_width=True)


def _display_type_breakdown(by_type: dict) -> None:
    """Display set piece breakdown by type as metrics."""
    cols = st.columns(min(4, max(1, len(by_type))))
    for i, (sp_type, data) in enumerate(by_type.items()):
        if not isinstance(data, dict):
            continue
        col_idx = i % len(cols)
        with cols[col_idx]:
            total = data.get("total", 0)
            shots = data.get("shots", 0)
            goals = data.get("goals", 0)
            st.metric(
                sp_type.replace("_", " ").title(),
                f"{total} total",
                f"{shots} shots, {goals} goals",
            )
