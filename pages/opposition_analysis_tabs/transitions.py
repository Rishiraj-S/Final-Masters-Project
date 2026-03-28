"""
Opposition Analysis — Tab 3: Their Transitions

Offensive transitions (threat to us) and defensive transitions (opportunity for us).
Mirrors Team Analysis Tab 4, adapted for the opposition's perspective.
"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
from dash import html, dcc
import dash_bootstrap_components as dbc

from utils.config import COLORS
from pages.match_analysis_tabs.shared import (
    section_card,
    kpi_row,
)
from page_utils.visualizations import (
    layout_config,
    CHART_CONFIG,
    add_pitch_background,
    PITCH_AXIS_FULL,
    empty_fig,
    render_lsc_heatmap_img,
    GOLD,
    HOME_COLOR,
    AWAY_COLOR,
)
from .helpers import no_data

_RECOVERY_EVENTS  = {"Ball recovery", "Interception", "Tackle"}
_TURNOVER_EVENTS  = {"Dispossessed", "Error"}
_SHOT_EVENTS      = {"Miss", "Post", "Saved Shot", "Goal"}


def _has(df: pd.DataFrame, col: str) -> bool:
    return col in df.columns and df[col].notna().any()


# ── Ball recovery zones ────────────────────────────────────────────────────────

def _recovery_zones_map(opp_ev: pd.DataFrame) -> go.Figure:
    """Heatmap of where the opposition wins the ball back."""
    gains = opp_ev[opp_ev["event_type"].isin(_RECOVERY_EVENTS)].dropna(subset=["x", "y"])
    if gains.empty:
        return empty_fig("No ball recovery data")

    # The instruction was to replace render_heatmap_img with render_lsc_heatmap_img.
    # The original call was `render_heatmap_img(gains["x"].tolist(), gains["y"].tolist(), cmap="YlGn")`
    # `render_lsc_heatmap_img` expects `color_hex` and `half` arguments.
    # Assuming the intent is to use AWAY_COLOR for opposition and full pitch.
    img = render_lsc_heatmap_img(gains["x"].tolist(), gains["y"].tolist(), color_hex=AWAY_COLOR, half=False)
    fig = go.Figure()
    add_pitch_background(fig)
    fig.add_layout_image(dict(
        source=img, x=0, y=100, xref="x", yref="y",
        sizex=100, sizey=100, sizing="stretch", opacity=0.65, layer="above",
    ))
    fig.update_layout(layout_config(height=380, **PITCH_AXIS_FULL,
                                    margin=dict(l=20, r=20, t=30, b=20)))
    return fig


# ── Top counter runners ────────────────────────────────────────────────────────

def _top_counter_runners(opp_ev: pd.DataFrame) -> go.Figure:
    """Players with most ball recoveries — proxy for who leads transitions."""
    gains = opp_ev[opp_ev["event_type"].isin(_RECOVERY_EVENTS)]
    if gains.empty or "player_name" not in gains.columns:
        return empty_fig("No ball recovery data")

    top = gains.groupby("player_name").size().sort_values(ascending=False).head(8)
    fig = go.Figure(go.Bar(
        x=top.values, y=top.index,
        orientation="h", marker_color=HOME_COLOR,
        hovertemplate="%{y}: %{x}<extra></extra>",
    ))
    fig.update_layout(layout_config(
        height=300, margin=dict(l=130, r=30, t=30, b=30),
        yaxis=dict(autorange="reversed"),
        xaxis_title="Ball recoveries",
    ))
    return fig


# ── Fast break / counter attack pattern ───────────────────────────────────────

def _counter_attack_chart(opp_ev: pd.DataFrame) -> go.Figure:
    """Passes with Fast break qualifier — counter-attack activity map."""
    if not _has(opp_ev, "Fast break"):
        return empty_fig("No fast break data")
    fast = opp_ev[(opp_ev["event_type"] == "Pass") & (opp_ev["Fast break"] == 1.0)].dropna(subset=["x", "y"])
    if fast.empty:
        return empty_fig("No fast break / counter data")

    succ = fast[fast["outcome"] == 1]
    fail = fast[fast["outcome"] != 1]

    fig = go.Figure()
    add_pitch_background(fig)
    for df, color, name in [(succ, GOLD, "Successful"), (fail, AWAY_COLOR, "Unsuccessful")]:
        if not df.empty:
            fig.add_trace(go.Scatter(
                x=df["x"], y=df["y"], mode="markers",
                marker=dict(size=8, color=color, opacity=0.8,
                            line=dict(color="white", width=0.5)),
                name=name,
            ))
    fig.update_layout(layout_config(height=380, **PITCH_AXIS_FULL,
                                    margin=dict(l=20, r=20, t=30, b=40)))
    fig.update_layout(legend=dict(orientation="h", yanchor="bottom", y=-0.15,
                                  xanchor="center", x=0.5))
    return fig


# ── Turnover danger zones ─────────────────────────────────────────────────────

def _turnover_zones(opp_ev: pd.DataFrame) -> go.Figure:
    """Where the opposition loses possession — exploitation opportunities."""
    turnovers = opp_ev[opp_ev["event_type"].isin(_TURNOVER_EVENTS)].dropna(subset=["x", "y"])
    if turnovers.empty:
        return empty_fig("No turnover data")

    fig = go.Figure()
    add_pitch_background(fig)
    fig.add_trace(go.Scatter(
        x=turnovers["x"], y=turnovers["y"],
        mode="markers",
        marker=dict(size=8, color=AWAY_COLOR, opacity=0.7,
                    line=dict(color="white", width=0.5)),
        name="Turnovers",
        hovertemplate="x=%{x:.1f}, y=%{y:.1f}<extra></extra>",
    ))
    fig.update_layout(layout_config(height=380, **PITCH_AXIS_FULL,
                                    margin=dict(l=20, r=20, t=30, b=20)))
    return fig


# ── Exposed after loss (shots conceded by opposition) ─────────────────────────

def _exposed_after_loss(bar_ev: pd.DataFrame) -> go.Figure:
    """Barcelona shots following a turnover by the opposition — their defensive vulnerability."""
    shots = bar_ev[bar_ev["event_type"].isin(_SHOT_EVENTS)].dropna(subset=["x", "y"])
    if _has(bar_ev, "Fast break"):
        fast_shots = shots[shots["Fast break"] == 1.0]
        if not fast_shots.empty:
            shots = fast_shots

    if shots.empty:
        return empty_fig("No fast transition shot data")

    goals = shots[shots["event_type"] == "Goal"]
    other = shots[shots["event_type"] != "Goal"]

    fig = go.Figure()
    add_pitch_background(fig)
    for df, color, symbol, name, sz in [
        (other, AWAY_COLOR, "circle",  "Shot", 9),
        (goals, GOLD,       "star",    "Goal", 14),
    ]:
        if not df.empty:
            fig.add_trace(go.Scatter(
                x=df["x"], y=df["y"], mode="markers",
                marker=dict(size=sz, color=color, opacity=0.85,
                            symbol=symbol, line=dict(color="white", width=1)),
                name=name,
            ))
    fig.update_layout(layout_config(height=380, **PITCH_AXIS_FULL,
                                    margin=dict(l=20, r=20, t=30, b=40)))
    fig.update_layout(legend=dict(orientation="h", yanchor="bottom", y=-0.15,
                                  xanchor="center", x=0.5))
    return fig


# ── Public builder ─────────────────────────────────────────────────────────────

def build_transitions(
    opp_ev: pd.DataFrame,
    bar_ev: pd.DataFrame,
    team: str,
) -> html.Div:
    if opp_ev.empty:
        return no_data("No event data available.")

    hr = html.Hr(style={"borderColor": COLORS["dark_border"], "margin": "1rem 0"})

    gains    = opp_ev[opp_ev["event_type"].isin(_RECOVERY_EVENTS)]
    turns    = opp_ev[opp_ev["event_type"].isin(_TURNOVER_EVENTS)]
    n_fast   = int(opp_ev["Fast break"].eq(1.0).sum()) if _has(opp_ev, "Fast break") else 0

    top_kpi = kpi_row(
        {"recoveries": len(gains), "turnovers": len(turns), "counters": n_fast},
        [("recoveries", "Ball Recoveries"), ("turnovers", "Turnovers"), ("counters", "Fast Breaks")],
    )

    # Offensive transitions
    off_section = html.Div([
        html.H6("Their Offensive Transitions (Threat to Us)", style={"color": GOLD, "marginBottom": "0.5rem"}),
        dbc.Row([
            dbc.Col(section_card("Ball Recovery Zones", dcc.Graph(figure=_recovery_zones_map(opp_ev), config=CHART_CONFIG)), md=6),
            dbc.Col(section_card("Counter Attack Pattern", dcc.Graph(figure=_counter_attack_chart(opp_ev), config=CHART_CONFIG)), md=6),
        ], className="mb-3"),
        dbc.Row([
            dbc.Col(section_card("Top Counter Runners", dcc.Graph(figure=_top_counter_runners(opp_ev), config=CHART_CONFIG)), md=6),
        ], className="mb-3"),
    ])

    # Defensive transitions (opportunity for us)
    def_section = html.Div([
        html.H6("Their Defensive Transitions (Opportunity for Us)", style={"color": GOLD, "marginBottom": "0.5rem"}),
        dbc.Row([
            dbc.Col(section_card("Turnover Zones", dcc.Graph(figure=_turnover_zones(opp_ev), config=CHART_CONFIG)), md=6),
            dbc.Col(section_card("Exposed After Loss", dcc.Graph(figure=_exposed_after_loss(bar_ev), config=CHART_CONFIG)), md=6),
        ], className="mb-3"),
    ])

    return html.Div([top_kpi, hr, off_section, hr, def_section])
