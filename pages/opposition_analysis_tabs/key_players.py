"""
Key Players tab — top scorers, most passes, defensive leaders.
"""

import pandas as pd
from dash import html, dcc

import dash_bootstrap_components as dbc
import plotly.graph_objects as go

from utils.opposition_data_utils import (
    GOAL_TYPE_ID,
    PASS_TYPE_ID,
    TACKLE_TYPE_ID,
    INTERCEPTION_TYPE_ID,
)
from pages.match_analysis_tabs.shared import (
    CHART_LAYOUT_DEFAULTS,
    CHART_CONFIG,
    section_card,
    empty_fig,
    GOLD,
    HOME_COLOR,
    AWAY_COLOR,
)
from .helpers import no_data


def build_key_players(team_ev: pd.DataFrame) -> html.Div:
    if team_ev.empty:
        return no_data("No player data available.")

    import pandas as _pd

    goals_by = (
        team_ev[team_ev["type_id"] == GOAL_TYPE_ID]
        .groupby("player_name").size()
        .sort_values(ascending=False).head(7)
    )
    passes_by = (
        team_ev[team_ev["type_id"] == PASS_TYPE_ID]
        .groupby("player_name").size()
        .sort_values(ascending=False).head(7)
    )
    def_by = (
        team_ev[team_ev["type_id"].isin({TACKLE_TYPE_ID, INTERCEPTION_TYPE_ID})]
        .groupby("player_name").size()
        .sort_values(ascending=False).head(7)
    )
    # Goal assists: passes where Assist qualifier == 16
    _passes = team_ev[team_ev["type_id"] == PASS_TYPE_ID]
    if not _passes.empty and "Assist" in _passes.columns:
        _assist_mask = _pd.to_numeric(_passes["Assist"], errors="coerce") == 16
        assists_by = (
            _passes[_assist_mask]["player_name"].dropna()
            .value_counts().head(7)
        )
    else:
        assists_by = _pd.Series(dtype=int)

    def _hbar(series, color, title):
        if series.empty:
            return section_card(title, empty_fig("No data"))
        fig = go.Figure(go.Bar(
            x=series.values, y=series.index,
            orientation="h", marker_color=color,
            hovertemplate="%{y}: %{x}<extra></extra>",
        ))
        fig.update_layout(
            **CHART_LAYOUT_DEFAULTS, height=300,
            yaxis=dict(autorange="reversed"),
        )
        return section_card(title, dcc.Graph(figure=fig, config=CHART_CONFIG))

    return html.Div([
        dbc.Row([
            dbc.Col(_hbar(goals_by,   GOLD,       "Top Scorers"),       md=6),
            dbc.Col(_hbar(assists_by, HOME_COLOR,  "Top Assisters"),     md=6),
        ], className="mb-3"),
        dbc.Row([
            dbc.Col(_hbar(passes_by,  AWAY_COLOR,  "Most Passes"),       md=6),
            dbc.Col(_hbar(def_by,     AWAY_COLOR,  "Defensive Leaders"), md=6),
        ]),
    ])
