"""
Tactical Profile tab — formation, aggregate stats, touch heatmap.
"""

import pandas as pd
from dash import html

import dash_bootstrap_components as dbc

from utils.opposition_data_utils import (
    get_opp_possession,
    SETUP_TYPE_ID,
    PASS_TYPE_ID,
    SHOT_TYPE_IDS,
    SAVED_TYPE_ID,
    GOAL_TYPE_ID,
    FOUL_TYPE_ID,
)
from pages.match_analysis_tabs.shared import (
    section_card,
    kpi_row,
    empty_fig,
    render_heatmap_img,
    GOLD,
    AWAY_COLOR,
)
from .helpers import no_data

CURRENT_SEASON = "2025-2026"

_LABEL_STYLE = {"color": "#8a8a8a", "fontSize": "0.85rem"}


def build_tactical(
    team_ev: pd.DataFrame, team: str, country: str, competition: str
) -> html.Div:
    if team_ev.empty:
        return no_data("No event data available for this team.")

    # Formation from typeId=34 (Team setup) events
    setup_ev   = team_ev[team_ev["type_id"] == SETUP_TYPE_ID]
    formations = (
        setup_ev["formation"].dropna()
        if "formation" in team_ev.columns
        else pd.Series(dtype=str)
    )
    formation_text = str(formations.mode().iloc[0]) if not formations.empty else "N/A"

    formation_card = dbc.Row([
        dbc.Col(dbc.Card(dbc.CardBody([
            html.P("Most Used Formation", className="mb-1", style=_LABEL_STYLE),
            html.H2(formation_text, style={"color": GOLD, "marginBottom": 0}),
        ])), md=3),
    ], className="mb-3")

    passes   = team_ev[team_ev["type_id"] == PASS_TYPE_ID]
    pass_n   = len(passes)
    pass_acc = (
        round(passes["outcome"].eq(1).sum() / pass_n * 100, 1)
        if pass_n > 0 else 0.0
    )
    shots  = team_ev[team_ev["type_id"].isin(SHOT_TYPE_IDS)]
    sot    = team_ev[team_ev["type_id"].isin({SAVED_TYPE_ID, GOAL_TYPE_ID})]
    goals  = team_ev[team_ev["type_id"] == GOAL_TYPE_ID]
    fouls  = team_ev[team_ev["type_id"] == FOUL_TYPE_ID]
    poss   = get_opp_possession(team, country, competition, CURRENT_SEASON)

    stats = kpi_row(
        {
            "passes":   pass_n,
            "pass_acc": pass_acc,
            "shots":    len(shots),
            "sot":      len(sot),
            "goals":    len(goals),
            "fouls":    len(fouls),
            "poss":     poss,
        },
        [
            ("passes",   "Passes"),
            ("pass_acc", "Pass Acc %"),
            ("shots",    "Shots"),
            ("sot",      "Shots on Target"),
            ("goals",    "Goals Scored"),
            ("fouls",    "Fouls"),
            ("poss",     "Possession %"),
        ],
    )

    touch = team_ev.dropna(subset=["x", "y"])
    if not touch.empty:
        img = render_heatmap_img(
            touch["x"].tolist(), touch["y"].tolist(),
            cmap="RdYlBu_r", fallback_color=AWAY_COLOR,
        )
        heatmap = section_card(
            "Touch Heatmap",
            html.Img(src=img, style={"width": "100%", "borderRadius": "4px"}),
        )
    else:
        heatmap = section_card("Touch Heatmap", empty_fig("No touch data"))

    return html.Div([formation_card, stats, heatmap])
