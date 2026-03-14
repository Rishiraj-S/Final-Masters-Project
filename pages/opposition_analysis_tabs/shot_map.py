"""
Shot Map tab — scatter plot of all shots on a grass pitch.
"""

import pandas as pd
from dash import html, dcc

import plotly.graph_objects as go

from utils.opposition_data_utils import (
    SHOT_TYPE_IDS,
    SAVED_TYPE_ID,
    GOAL_TYPE_ID,
)
from pages.match_analysis_tabs.shared import (
    CHART_LAYOUT_DEFAULTS,
    CHART_CONFIG,
    add_pitch_background,
    PITCH_AXIS_FULL,
    section_card,
    empty_fig,
    GOLD,
    HOME_COLOR,
    AWAY_COLOR,
)
from .helpers import no_data

import dash_bootstrap_components as dbc


def build_shot_map(team_ev: pd.DataFrame) -> dbc.Card:
    if team_ev.empty:
        return section_card("Shot Map", empty_fig("No shot data available."))

    shots = team_ev[team_ev["type_id"].isin(SHOT_TYPE_IDS)].dropna(subset=["x", "y"])

    if shots.empty:
        return section_card("Shot Map", empty_fig("No shot data available."))

    off   = shots[~shots["type_id"].isin({SAVED_TYPE_ID, GOAL_TYPE_ID})]
    saved = shots[shots["type_id"] == SAVED_TYPE_ID]
    goals = shots[shots["type_id"] == GOAL_TYPE_ID]

    fig = go.Figure()
    add_pitch_background(fig)

    def _trace(df, color, symbol, name, size):
        if df.empty:
            return
        fig.add_trace(go.Scatter(
            x=df["x"], y=df["y"],
            mode="markers",
            marker=dict(
                size=size, color=color, opacity=0.85,
                symbol=symbol, line=dict(color="white", width=1),
            ),
            name=name,
            hovertemplate=f"{name}<br>x=%{{x:.1f}}, y=%{{y:.1f}}<extra></extra>",
        ))

    _trace(off,   AWAY_COLOR, "circle-open", "Off Target",  9)
    _trace(saved, HOME_COLOR, "circle",      "On Target",  11)
    _trace(goals, GOLD,       "star",        "Goal",       15)

    fig.update_layout(
        **CHART_LAYOUT_DEFAULTS,
        **PITCH_AXIS_FULL,
        height=420,
        legend=dict(orientation="h", yanchor="bottom", y=-0.15,
                    xanchor="center", x=0.5),
    )

    summary = html.Div([
        dbc.Badge(f"{len(goals)} Goals",     color="warning", className="me-2"),
        dbc.Badge(f"{len(saved)} On Target", color="success", className="me-2"),
        dbc.Badge(f"{len(off)} Off Target",  color="danger",  className="me-2"),
    ], className="mb-2")

    return section_card(
        "Shot Map",
        html.Div([summary, dcc.Graph(figure=fig, config=CHART_CONFIG)]),
    )
