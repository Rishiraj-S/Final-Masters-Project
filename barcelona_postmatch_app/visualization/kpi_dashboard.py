"""Tab 6: KPI Dashboard - Barcelona-specific KPIs with context."""
from __future__ import annotations

import io

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from barcelona_postmatch_app.config import (
    BARCELONA_GOLD,
    BARCELONA_PRIMARY,
    BARCELONA_SECONDARY,
)
from barcelona_postmatch_app.visualization.utils import get_color_by_performance


def render(kpis: dict) -> None:
    """Render the KPI Dashboard tab."""
    if not kpis:
        st.warning("No KPI data available.")
        return

    st.subheader("Key Performance Indicators")

    # Top 5 KPIs as metric cards
    create_kpi_cards(kpis)

    st.divider()

    # Detailed KPI table
    st.subheader("Full KPI Summary")
    create_kpi_table(kpis)

    st.divider()

    # Pass risk profile breakdown
    risk = kpis.get("pass_risk_profile", {})
    if isinstance(risk.get("value"), dict):
        st.subheader("Pass Risk Profile")
        fig = _plot_risk_profile(risk["value"])
        st.plotly_chart(fig, use_container_width=True)

    # Phase duration breakdown
    phase_dur = kpis.get("phase_duration", {})
    if isinstance(phase_dur.get("value"), dict):
        st.subheader("Average Phase Duration")
        fig = _plot_phase_durations(phase_dur["value"])
        st.plotly_chart(fig, use_container_width=True)

    # Final third entry breakdown
    ft_entries = kpis.get("final_third_entries", {})
    if isinstance(ft_entries.get("detail"), dict):
        st.subheader("Final Third Entry Methods (%)")
        fig = _plot_entry_methods(ft_entries["detail"])
        st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # Download report
    st.subheader("Export Report")
    _generate_download(kpis)


def create_kpi_cards(kpis: dict) -> None:
    """Display top KPIs as Streamlit metric cards."""
    card_kpis = [
        "progressive_pass_rate",
        "press_success_rate",
        "transition_speed",
        "possession_efficiency",
        "defensive_compactness",
    ]

    cols = st.columns(len(card_kpis))

    for i, kpi_key in enumerate(card_kpis):
        kpi = kpis.get(kpi_key, {})
        if not kpi:
            continue

        name = kpi.get("name", kpi_key)
        value = kpi.get("value", 0)
        unit = kpi.get("unit", "")
        context = kpi.get("context", "")
        benchmark = kpi.get("benchmark")

        # Format value
        if isinstance(value, dict):
            display_value = "See details"
        elif isinstance(value, float):
            display_value = f"{value:.1f}{unit}"
        else:
            display_value = f"{value}{unit}"

        # Calculate delta for comparison
        delta = None
        if benchmark and isinstance(value, (int, float)):
            diff = value - benchmark
            delta = f"{diff:+.1f} vs avg"

        with cols[i]:
            st.metric(label=name, value=display_value, delta=delta)
            st.caption(context)


def create_kpi_table(kpis: dict) -> None:
    """Display all KPIs in table format."""
    rows = []

    for kpi_key, kpi_data in kpis.items():
        if not isinstance(kpi_data, dict):
            continue

        value = kpi_data.get("value", 0)
        if isinstance(value, dict):
            # Format dict values nicely
            value_str = ", ".join(f"{k}: {v}" for k, v in value.items())
        elif isinstance(value, float):
            value_str = f"{value:.1f}"
        else:
            value_str = str(value)

        benchmark = kpi_data.get("benchmark")
        benchmark_str = str(benchmark) if benchmark is not None else "-"

        rows.append({
            "KPI": kpi_data.get("name", kpi_key),
            "Value": value_str,
            "Unit": kpi_data.get("unit", ""),
            "Detail": str(kpi_data.get("detail", "")),
            "Benchmark": benchmark_str,
            "Context": kpi_data.get("context", ""),
        })

    if rows:
        df = pd.DataFrame(rows)
        st.dataframe(df, hide_index=True, use_container_width=True)
    else:
        st.info("No KPIs to display.")


def _plot_risk_profile(risk_data: dict) -> go.Figure:
    """Bar chart of pass risk distribution."""
    categories = ["Safe", "Medium", "Risky"]
    values = [risk_data.get("safe", 0), risk_data.get("medium", 0), risk_data.get("risky", 0)]
    colors = ["#4ECDC4", BARCELONA_SECONDARY, "#FF6B6B"]

    fig = go.Figure(data=[go.Bar(
        x=categories, y=values,
        marker_color=colors,
        text=[f"{v}%" for v in values],
        textposition="auto",
    )])

    fig.update_layout(
        yaxis=dict(title="% of Passes", range=[0, 100]),
        height=300,
    )
    return fig


def _plot_phase_durations(durations: dict) -> go.Figure:
    """Bar chart of average phase durations."""
    labels = [k.replace("_", " ").title() for k in durations.keys()]
    values = list(durations.values())
    colors = ["#4ECDC4", "#45B7D1", "#FF6B6B"]

    fig = go.Figure(data=[go.Bar(
        x=labels, y=values,
        marker_color=colors[:len(labels)],
        text=[f"{v:.1f}s" for v in values],
        textposition="auto",
    )])

    fig.update_layout(
        yaxis=dict(title="Avg Duration (seconds)"),
        height=300,
    )
    return fig


def _plot_entry_methods(entry_pcts: dict) -> go.Figure:
    """Pie chart of final third entry method percentages."""
    labels = [k.replace("_", " ").title() for k in entry_pcts.keys()]
    values = list(entry_pcts.values())

    fig = go.Figure(data=[go.Pie(
        labels=labels, values=values,
        textinfo="label+percent",
        hole=0.3,
        marker=dict(colors=[BARCELONA_PRIMARY, BARCELONA_SECONDARY, BARCELONA_GOLD, "#4ECDC4", "#FF6B6B"]),
    )])
    fig.update_layout(height=300, margin=dict(t=10, b=10))
    return fig


def _generate_download(kpis: dict) -> None:
    """Generate downloadable CSV report of KPIs."""
    rows = []
    for kpi_key, kpi_data in kpis.items():
        if not isinstance(kpi_data, dict):
            continue
        value = kpi_data.get("value", 0)
        if isinstance(value, dict):
            value_str = str(value)
        else:
            value_str = str(value)

        rows.append({
            "KPI": kpi_data.get("name", kpi_key),
            "Value": value_str,
            "Unit": kpi_data.get("unit", ""),
            "Detail": str(kpi_data.get("detail", "")),
            "Context": kpi_data.get("context", ""),
        })

    if rows:
        df = pd.DataFrame(rows)
        csv = df.to_csv(index=False)
        st.download_button(
            label="Download KPI Report (CSV)",
            data=csv,
            file_name="barcelona_kpi_report.csv",
            mime="text/csv",
        )
