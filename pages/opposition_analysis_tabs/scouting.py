"""
Opposition Analysis — Tab 0: Scouting Report

Who are they? Season profile, form, style, key players.
Answers 'what do they look like on paper' before drilling into phases.
"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
from dash import html, dcc
import dash_bootstrap_components as dbc

from utils.config import COLORS
from utils.opposition_data_utils import (
    PASS_TYPE_ID,
    SHOT_TYPE_IDS,
    GOAL_TYPE_ID,
    TACKLE_TYPE_ID,
    INTERCEPTION_TYPE_ID,
    SETUP_TYPE_ID,
    _normalize,
)
from pages.match_analysis_tabs.shared import section_card
from page_utils.visualizations import (
    layout_config,
    CHART_CONFIG,
    empty_fig,
    GOLD,
    HOME_COLOR,
    AWAY_COLOR,
)
from .helpers import no_data

_BADGE_COLOR = {"W": "success", "D": "warning", "L": "danger"}
_RESULT_BG   = {"W": "#1a5c2a", "D": "#5c4a1a", "L": "#5c1a1a"}


# ── Helpers ────────────────────────────────────────────────────────────────────

def _stat_pill(label: str, value: str) -> html.Span:
    return html.Span([
        html.Span(label, style={"color": COLORS["text_secondary"], "fontSize": "0.78rem", "marginRight": "4px"}),
        html.Span(value, style={"color": COLORS["text_primary"], "fontWeight": "bold", "fontSize": "0.9rem"}),
    ], style={
        "background": "#1E2139",
        "border": f"1px solid {COLORS['dark_border']}",
        "borderRadius": "6px",
        "padding": "4px 10px",
        "marginRight": "8px",
        "marginBottom": "6px",
        "display": "inline-block",
    })


def _season_stats_row(results: list[dict]) -> html.Div:
    n     = len(results)
    wins  = sum(1 for r in results if r["result"] == "W")
    draws = sum(1 for r in results if r["result"] == "D")
    loss  = sum(1 for r in results if r["result"] == "L")
    gf    = sum(r["gf"] for r in results)
    ga    = sum(r["ga"] for r in results)
    ppg   = round((wins * 3 + draws) / n, 2) if n else 0
    return html.Div([
        _stat_pill("P",   str(n)),
        _stat_pill("W",   str(wins)),
        _stat_pill("D",   str(draws)),
        _stat_pill("L",   str(loss)),
        _stat_pill("GF",  str(gf)),
        _stat_pill("GA",  str(ga)),
        _stat_pill("GD",  f"{gf - ga:+d}"),
        _stat_pill("PPG", str(ppg)),
    ], style={"flexWrap": "wrap", "display": "flex"})


def _form_strip(results: list[dict], n: int = 10) -> html.Div:
    last_n = results[-n:]
    badges = [
        dbc.Badge(
            r["result"],
            color=_BADGE_COLOR[r["result"]],
            className="me-1 mb-1",
            title=f"{r['date'][:10]}  vs {r['opponent']}  {r['gf']}–{r['ga']}",
        )
        for r in last_n
    ]
    return html.Div(badges or [html.Span("–", style={"color": COLORS["text_secondary"]})],
                    style={"fontSize": "1.1rem"})


def _home_away_table(results: list[dict]) -> html.Table:
    def _row_stats(subset):
        n = len(subset)
        if not n:
            return "–", "–", "–", "–", "–", "–"
        wins  = sum(1 for r in subset if r["result"] == "W")
        draws = sum(1 for r in subset if r["result"] == "D")
        loss  = sum(1 for r in subset if r["result"] == "L")
        gf    = sum(r["gf"] for r in subset)
        ga    = sum(r["ga"] for r in subset)
        return str(n), str(wins), str(draws), str(loss), f"{gf}:{ga}", f"{gf-ga:+d}"

    home = [r for r in results if r.get("is_home")]
    away = [r for r in results if not r.get("is_home")]

    th_style = {"color": COLORS["text_secondary"], "fontSize": "0.8rem", "padding": "4px 8px"}
    td_style = {"color": COLORS["text_primary"],   "fontSize": "0.85rem", "padding": "4px 8px"}

    def _tr(label, subset, color):
        p, w, d, l, score, gd = _row_stats(subset)
        return html.Tr([
            html.Td(dbc.Badge(label, color=color), style=td_style),
            html.Td(p,     style=td_style),
            html.Td(w,     style=td_style),
            html.Td(d,     style=td_style),
            html.Td(l,     style=td_style),
            html.Td(score, style=td_style),
            html.Td(gd,    style=td_style),
        ])

    return html.Table([
        html.Thead(html.Tr([
            html.Th("Venue",  style=th_style), html.Th("P", style=th_style),
            html.Th("W",      style=th_style), html.Th("D", style=th_style),
            html.Th("L",      style=th_style), html.Th("Score", style=th_style),
            html.Th("GD",     style=th_style),
        ])),
        html.Tbody([_tr("Home", home, "primary"), _tr("Away", away, "secondary")]),
    ], className="table table-dark table-sm")


def _style_radar(opp_ev: pd.DataFrame, all_results: list[dict]) -> go.Figure:
    """Hexagonal style radar: Possession, Pass Acc, Pressing, Direct play, Aerial, Goals/G."""
    n = max(len(all_results), 1)

    passes   = opp_ev[opp_ev["event_type"] == "Pass"]
    pass_n   = max(len(passes), 1)
    pass_acc = round(passes["outcome"].eq(1).sum() / pass_n * 100, 1) if pass_n else 0

    shots    = opp_ev[opp_ev["event_type_id" if "event_type_id" in opp_ev.columns else "type_id"].isin(SHOT_TYPE_IDS)]
    goals    = opp_ev[opp_ev["event_type"] == "Goal"] if "Goal" in opp_ev["event_type"].values else \
               (opp_ev[opp_ev["type_id"] == GOAL_TYPE_ID] if "type_id" in opp_ev.columns else \
                (opp_ev[opp_ev["event_type_id"] == GOAL_TYPE_ID] if "event_type_id" in opp_ev.columns else pd.DataFrame()))
    tackles  = opp_ev[opp_ev["event_type"] == "Tackle"]
    intercpt = opp_ev[opp_ev["event_type"] == "Interception"]

    long_col  = "Long ball"
    direct_pct = round(
        passes[long_col].eq(1.0).sum() / pass_n * 100, 1
    ) if long_col in passes.columns else 0

    aerial_w = opp_ev[(opp_ev["event_type"] == "Aerial") & (opp_ev["outcome"] == 1)]
    aerial_t = opp_ev[opp_ev["event_type"] == "Aerial"]
    aerial_pct = round(len(aerial_w) / max(len(aerial_t), 1) * 100, 1)

    def_actions = len(tackles) + len(intercpt)
    press_score = min(round(def_actions / n / 15 * 100, 1), 100)  # normalised proxy

    goals_pg = round(len(goals) / n, 2) if not goals.empty else 0
    goal_score = min(round(goals_pg / 2.5 * 100, 1), 100)

    categories = ["Pass Accuracy", "Direct Play", "Pressing", "Aerial", "Goals/G", "Pass Accuracy"]
    values = [
        min(pass_acc, 100),
        direct_pct,
        press_score,
        aerial_pct,
        goal_score,
        min(pass_acc, 100),
    ]

    fig = go.Figure(go.Scatterpolar(
        r=values, theta=categories,
        fill="toself",
        fillcolor=f"rgba({int(GOLD[1:3],16)},{int(GOLD[3:5],16)},{int(GOLD[5:7],16)},0.25)",
        line=dict(color=GOLD, width=2),
        name="Style",
    ))
    fig.update_layout(layout_config(
        polar=dict(
            bgcolor="rgba(0,0,0,0)",
            radialaxis=dict(visible=True, range=[0, 100], gridcolor="#333", tickfont=dict(size=9)),
            angularaxis=dict(gridcolor="#333"),
        ),
        showlegend=False,
        height=300,
        margin=dict(l=40, r=40, t=30, b=30),
    ))
    return fig


def _formation_bar(opp_ev: pd.DataFrame) -> go.Figure:
    if "formation" not in opp_ev.columns:
        return empty_fig("Formation data unavailable")
    formations = (
        opp_ev[opp_ev["event_type"] == "Team setp up"]["formation"]
        .dropna()
        .value_counts()
        .head(6)
    )
    if formations.empty:
        return empty_fig("No formation data")
    fig = go.Figure(go.Bar(
        x=formations.values, y=formations.index,
        orientation="h", marker_color=HOME_COLOR,
    ))
    fig.update_layout(layout_config(
        height=220, margin=dict(l=80, r=30, t=30, b=30),
        yaxis=dict(autorange="reversed"),
        xaxis_title="Matches",
    ))
    return fig


def _key_players_charts(opp_ev: pd.DataFrame) -> html.Div:
    def _hbar(series, color, title):
        if series.empty:
            return section_card(title, empty_fig("No data"))
        fig = go.Figure(go.Bar(
            x=series.values, y=series.index,
            orientation="h", marker_color=color,
            hovertemplate="%{y}: %{x}<extra></extra>",
        ))
        fig.update_layout(layout_config(
            height=280, margin=dict(l=120, r=30, t=30, b=30),
            yaxis=dict(autorange="reversed"),
        ))
        return section_card(title, dcc.Graph(figure=fig, config=CHART_CONFIG))

    type_col = "type_id" if "type_id" in opp_ev.columns else "event_type_id"

    goals_by = (
        opp_ev[opp_ev["event_type"] == "Goal"]
        .groupby("player_name").size().sort_values(ascending=False).head(7)
    )
    passes_by = (
        opp_ev[opp_ev["event_type"] == "Pass"]
        .groupby("player_name").size().sort_values(ascending=False).head(7)
    )
    def_by = (
        opp_ev[opp_ev["event_type"].isin(["Tackle", "Interception"])]
        .groupby("player_name").size().sort_values(ascending=False).head(7)
    )
    assists_by = pd.Series(dtype=int)
    if "Assist" in opp_ev.columns:
        _passes = opp_ev[opp_ev["event_type"] == "Pass"]
        _am = pd.to_numeric(_passes["Assist"], errors="coerce").eq(16)
        assists_by = _passes[_am]["player_name"].dropna().value_counts().head(7)

    return html.Div([
        dbc.Row([
            dbc.Col(_hbar(goals_by,   GOLD,      "Top Scorers"),       md=6),
            dbc.Col(_hbar(assists_by, HOME_COLOR, "Top Assisters"),     md=6),
        ], className="mb-3"),
        dbc.Row([
            dbc.Col(_hbar(passes_by,  AWAY_COLOR, "Most Passes"),       md=6),
            dbc.Col(_hbar(def_by,     AWAY_COLOR, "Defensive Leaders"), md=6),
        ]),
    ])


def _match_history_table(results: list[dict]) -> html.Table:
    rows = []
    for r in results:
        venue_badge = dbc.Badge("H" if r.get("is_home") else "A",
                                color="primary" if r.get("is_home") else "secondary",
                                className="me-1")
        score_color = {"W": "#4caf50", "D": "#ffc107", "L": "#ef5350"}.get(r["result"], "#fff")
        rows.append(html.Tr([
            html.Td(str(r["date"])[:10],   style={"color": COLORS["text_secondary"], "fontSize": "0.82rem", "whiteSpace": "nowrap"}),
            html.Td(r.get("competition", ""), style={"fontSize": "0.75rem", "color": COLORS["text_secondary"]}),
            html.Td(venue_badge),
            html.Td(r["opponent"],         style={"fontWeight": "500"}),
            html.Td(f"{r['gf']} – {r['ga']}", style={"fontWeight": "bold", "color": score_color, "textAlign": "center"}),
            html.Td(dbc.Badge(r["result"], color=_BADGE_COLOR[r["result"]])),
        ], style={"backgroundColor": _RESULT_BG.get(r["result"], "transparent")}))
    return html.Table([
        html.Thead(html.Tr([
            html.Th("Date"), html.Th("Comp"), html.Th(""), html.Th("Opponent"),
            html.Th("Score", style={"textAlign": "center"}), html.Th("Result"),
        ])),
        html.Tbody(rows),
    ], className="table table-dark table-sm table-hover")


# ── Public builder ─────────────────────────────────────────────────────────────

def build_scouting(
    team: str,
    country: str,
    comp_key: str,
    all_results: list[dict],
    opp_ev: pd.DataFrame,
    n_matches: int,
) -> html.Div:
    if not all_results and opp_ev.empty:
        return no_data(f"No data found for {team}.")

    hr = html.Hr(style={"borderColor": COLORS["dark_border"], "margin": "1rem 0"})

    # ── Row 1: season stats + radar ───────────────────────────────────────────
    stats_card = section_card("Season Profile", _season_stats_row(all_results))
    radar_card = section_card("Style Radar", dcc.Graph(figure=_style_radar(opp_ev, all_results), config=CHART_CONFIG))

    row1 = dbc.Row([
        dbc.Col(stats_card, md=7),
        dbc.Col(radar_card, md=5),
    ], className="mb-3")

    # ── Row 2: form strip + home/away split ───────────────────────────────────
    form_card   = section_card("Recent Form (last 10)", _form_strip(all_results))
    ha_card     = section_card("Home vs Away Split", _home_away_table(all_results))

    row2 = dbc.Row([
        dbc.Col(form_card, md=5),
        dbc.Col(ha_card,   md=7),
    ], className="mb-3")

    # ── Row 3: formation + key players ───────────────────────────────────────
    form_chart = section_card("Formation Usage", dcc.Graph(figure=_formation_bar(opp_ev), config=CHART_CONFIG))

    row3 = dbc.Row([dbc.Col(form_chart, md=5)], className="mb-3")

    # ── Key players ───────────────────────────────────────────────────────────
    kp_section = html.Div([
        html.H6("Key Players", style={"color": GOLD, "marginBottom": "0.5rem"}),
        _key_players_charts(opp_ev),
    ], className="mb-3")

    # ── Match history ─────────────────────────────────────────────────────────
    history = section_card("Match History", _match_history_table(all_results))

    return html.Div([row1, hr, row2, hr, row3, kp_section, hr, history])
