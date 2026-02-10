"""Tab 3: Transitions - attacking and defensive transitions analysis."""
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
    plot_heatmap_on_pitch,
)


def render(transition_data: dict, events_df: pd.DataFrame, pressing_data: dict = None) -> None:
    """Render the Transitions tab."""
    tab_a, tab_b = st.tabs(["Attacking Transitions", "Pressing & Defensive Transitions"])

    with tab_a:
        _render_attacking_transitions(transition_data, events_df)

    with tab_b:
        _render_pressing(pressing_data or {}, events_df)


def _render_attacking_transitions(transition_data: dict, events_df: pd.DataFrame) -> None:
    """Render attacking transitions sub-tab."""
    transitions = transition_data.get("transitions", [])
    metrics = transition_data.get("metrics", {})
    regain_patterns = transition_data.get("regain_patterns", {})

    # Metrics row
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Transitions", metrics.get("total_transitions", 0))
    col2.metric("Counter-Attack Rate", f"{metrics.get('counter_attack_rate', 0)}%")
    col3.metric("Avg Speed", f"{metrics.get('avg_transition_speed', 0)}s")
    col4.metric("Goals from Transitions", metrics.get("goal_count", 0))

    st.divider()

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Counter-Attack Outcomes")
        fig = plot_counter_outcome_distribution(metrics.get("outcome_distribution", {}))
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader("Transition Type Breakdown")
        fig = plot_transition_type_distribution(metrics.get("type_distribution", {}))
        st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # Transition examples on pitch
    st.subheader("Key Transition Examples")
    if transitions:
        # Show up to 3 best transitions (with shots)
        shot_transitions = [t for t in transitions if t["outcome"] != "no_shot"]
        examples = sorted(shot_transitions, key=lambda t: t.get("time_to_shot", 99))[:3]

        if not examples:
            examples = transitions[:3]

        cols = st.columns(min(3, len(examples)))
        for i, trans in enumerate(examples):
            with cols[i]:
                fig = plot_transition_example(events_df, trans)
                st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No transitions detected.")

    st.divider()

    # Regain patterns
    st.subheader("First Action After Regain")
    if regain_patterns:
        fig = _plot_regain_patterns(regain_patterns)
        st.plotly_chart(fig, use_container_width=True)

    # Regain locations heatmap
    st.subheader("Ball Regain Locations")
    regain_x = [t["regain_x"] for t in transitions if not np.isnan(t.get("regain_x", np.nan))]
    regain_y = [t["regain_y"] for t in transitions if not np.isnan(t.get("regain_y", np.nan))]
    if regain_x:
        fig = plot_heatmap_on_pitch(regain_x, regain_y, "Regain Locations")
        st.plotly_chart(fig, use_container_width=True)


def _render_pressing(pressing_data: dict, events_df: pd.DataFrame) -> None:
    """Render pressing sub-tab."""
    pressing_moments = pressing_data.get("pressing_moments", [])
    metrics = pressing_data.get("metrics", {})

    # Metrics row
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Presses", metrics.get("total_presses", 0))
    col2.metric("Press Success Rate", f"{metrics.get('press_success_rate', 0)}%")
    col3.metric("Avg Intensity", f"{metrics.get('avg_intensity', 0)} defenders")

    st.divider()

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Press Trigger Locations")
        press_x = [p["x"] for p in pressing_moments if not np.isnan(p.get("x", np.nan))]
        press_y = [p["y"] for p in pressing_moments if not np.isnan(p.get("y", np.nan))]
        if press_x:
            fig = plot_heatmap_on_pitch(press_x, press_y, "Where Barcelona Presses")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No pressing data available.")

    with col2:
        st.subheader("Successful Regain Locations")
        regain_x = [p["regain_x"] for p in pressing_moments
                     if p.get("regained") and not np.isnan(p.get("regain_x", np.nan))]
        regain_y = [p["regain_y"] for p in pressing_moments
                     if p.get("regained") and not np.isnan(p.get("regain_y", np.nan))]
        if regain_x:
            fig = plot_heatmap_on_pitch(regain_x, regain_y, "Successful Regains")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No regain data available.")

    st.divider()

    # Press success by zone
    zone_rates = metrics.get("zone_success_rates", {})
    zone_counts = metrics.get("zone_counts", {})
    if zone_rates:
        st.subheader("Press Success Rate by Zone")
        fig = _plot_zone_success(zone_rates, zone_counts)
        st.plotly_chart(fig, use_container_width=True)

    # Press intensity timeline
    if pressing_moments:
        st.subheader("Press Intensity Over Time")
        fig = plot_press_intensity_timeline(pressing_moments)
        st.plotly_chart(fig, use_container_width=True)


def plot_counter_outcome_distribution(outcome_dist: dict) -> go.Figure:
    """Pie chart of counter-attack outcomes."""
    if not outcome_dist:
        fig = go.Figure()
        fig.add_annotation(text="No transition data", showarrow=False)
        return fig

    labels = [k.replace("_", " ").title() for k in outcome_dist.keys()]
    values = list(outcome_dist.values())
    colors = [BARCELONA_GOLD, BARCELONA_PRIMARY, BARCELONA_SECONDARY, "#888888", "#CC4444"]

    fig = go.Figure(data=[go.Pie(
        labels=labels, values=values,
        marker=dict(colors=colors[:len(labels)]),
        textinfo="label+percent+value",
        hole=0.3,
    )])
    fig.update_layout(height=300, margin=dict(t=10, b=10))
    return fig


def plot_transition_type_distribution(type_dist: dict) -> go.Figure:
    """Bar chart of transition types."""
    if not type_dist:
        fig = go.Figure()
        fig.add_annotation(text="No data", showarrow=False)
        return fig

    labels = [k.replace("_", " ").title() for k in type_dist.keys()]
    values = list(type_dist.values())

    fig = go.Figure(data=[go.Bar(
        x=labels, y=values,
        marker_color=[BARCELONA_PRIMARY, BARCELONA_SECONDARY, "#888888", "#CC4444"],
        text=values,
        textposition="auto",
    )])
    fig.update_layout(height=300, yaxis=dict(title="Count"))
    return fig


def plot_transition_example(events_df: pd.DataFrame, transition: dict) -> go.Figure:
    """Draw a transition's ball path on the pitch."""
    fig = draw_pitch()

    start_idx = transition["start_idx"]
    end_idx = transition["end_idx"]

    mask = (events_df.index >= start_idx) & (events_df.index <= end_idx) & (events_df["is_barca"])
    seq = events_df.loc[mask]

    x_points, y_points, texts = [], [], []

    for _, evt in seq.iterrows():
        x = evt.get("x_norm", evt.get("x", np.nan))
        y = evt.get("y_norm", evt.get("y", np.nan))
        if np.isnan(x) or np.isnan(y):
            continue
        x_points.append(x)
        y_points.append(y)
        texts.append(f"{evt.get('player_name', '')} ({evt['event_type']})")

    if x_points:
        # Draw path
        fig.add_trace(go.Scatter(
            x=x_points, y=y_points,
            mode="lines+markers",
            line=dict(color=BARCELONA_GOLD, width=2),
            marker=dict(size=8, color=BARCELONA_PRIMARY),
            text=texts,
            hoverinfo="text",
            showlegend=False,
        ))

        # Highlight start and end
        fig.add_trace(go.Scatter(
            x=[x_points[0]], y=[y_points[0]],
            mode="markers",
            marker=dict(size=14, color="green", symbol="circle"),
            name="Regain",
            showlegend=True,
        ))

        if len(x_points) > 1:
            fig.add_trace(go.Scatter(
                x=[x_points[-1]], y=[y_points[-1]],
                mode="markers",
                marker=dict(size=14, color="red", symbol="star"),
                name="End",
                showlegend=True,
            ))

    title_parts = [
        f"{transition.get('minute', '')}' - {transition['type'].replace('_', ' ').title()}",
        f"({transition['outcome'].replace('_', ' ')})",
    ]
    if transition.get("time_to_shot") is not None:
        title_parts.append(f"Speed: {transition['time_to_shot']:.1f}s")

    fig.update_layout(
        title=" ".join(title_parts),
        height=350,
        legend=dict(x=0.5, y=-0.05, xanchor="center", orientation="h"),
    )
    return fig


def plot_press_intensity_timeline(pressing_moments: list[dict]) -> go.Figure:
    """Line chart of press intensity over match time."""
    if not pressing_moments:
        return go.Figure()

    minutes = [p["minute"] for p in pressing_moments]
    intensities = [p["defenders_involved"] for p in pressing_moments]

    # Rolling average (5-event window)
    window = min(5, len(intensities))
    if window > 1:
        rolling = pd.Series(intensities).rolling(window, min_periods=1).mean().tolist()
    else:
        rolling = intensities

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=minutes, y=intensities,
        mode="markers",
        marker=dict(size=5, color=BARCELONA_SECONDARY, opacity=0.5),
        name="Individual",
    ))
    fig.add_trace(go.Scatter(
        x=minutes, y=rolling,
        mode="lines",
        line=dict(color=BARCELONA_PRIMARY, width=3),
        name="Rolling Avg",
    ))

    fig.add_vline(x=45, line_dash="dash", line_color="white", opacity=0.3)

    fig.update_layout(
        xaxis=dict(title="Minute"),
        yaxis=dict(title="Defenders Involved"),
        height=300,
        legend=dict(x=0.02, y=0.98),
    )
    return fig


def _plot_regain_patterns(patterns: dict) -> go.Figure:
    """Bar chart of first action after ball regain."""
    labels = [k.replace("_", " ").title() for k in patterns.keys()]
    values = list(patterns.values())

    fig = go.Figure(data=[go.Bar(
        x=labels, y=values,
        marker_color=BARCELONA_PRIMARY,
        text=values,
        textposition="auto",
    )])
    fig.update_layout(height=300, yaxis=dict(title="Count"))
    return fig


def _plot_zone_success(zone_rates: dict, zone_counts: dict) -> go.Figure:
    """Bar chart of press success rate by pitch zone."""
    zones = list(zone_rates.keys())
    rates = list(zone_rates.values())
    counts = [zone_counts.get(z, 0) for z in zones]

    labels = [z.replace("_", " ").title() for z in zones]

    fig = go.Figure(data=[go.Bar(
        x=labels, y=rates,
        marker_color=BARCELONA_SECONDARY,
        text=[f"{r}%<br>(n={c})" for r, c in zip(rates, counts)],
        textposition="auto",
    )])
    fig.update_layout(
        yaxis=dict(title="Success Rate (%)", range=[0, 100]),
        height=300,
    )
    return fig
