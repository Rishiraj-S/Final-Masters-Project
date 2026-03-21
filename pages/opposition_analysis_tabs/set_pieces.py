"""
Opposition Analysis — Tab 4: Their Set Pieces

Attacking set pieces (threat to us) and defending set pieces (opportunity for us).
Mirrors Team Analysis Tab 5, adapted for the opposition.

NOTE: Opposition qualifier columns are stored as 1.0/NaN (not 'Si').
"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
from dash import html, dcc
import dash_bootstrap_components as dbc

from utils.config import COLORS
from pages.match_analysis_tabs.shared import (
    layout_config,
    CHART_CONFIG,
    add_pitch_background,
    PITCH_AXIS_FULL,
    section_card,
    kpi_row,
    empty_fig,
    GOLD,
    HOME_COLOR,
    AWAY_COLOR,
)
from .helpers import no_data

_SHOT_EVENTS = {"Miss", "Post", "Saved Shot", "Goal"}


def _has(df: pd.DataFrame, col: str) -> bool:
    return col in df.columns and df[col].notna().any()


def _q(df: pd.DataFrame, col: str) -> pd.Series:
    """Return boolean mask for rows where qualifier column equals 1.0."""
    if col not in df.columns:
        return pd.Series(False, index=df.index)
    return df[col] == 1.0


# ── Corner delivery donut ─────────────────────────────────────────────────────

def _corner_delivery(opp_ev: pd.DataFrame) -> go.Figure:
    """Inswing / Outswing / Short corner split."""
    corners = opp_ev[opp_ev["event_type"] == "Corner Awarded"]
    if corners.empty:
        corners = opp_ev[_q(opp_ev, "Corner taken")]
    if corners.empty:
        return empty_fig("No corner data")

    inswing  = int(_q(corners, "Inswinger").sum())
    outswing = int(_q(corners, "Outswinger").sum())
    straight = int(_q(corners, "Straight").sum())
    short    = int(corners[corners["x"].notna() & (corners["Pass End X"].notna() if "Pass End X" in corners.columns else pd.Series(False, index=corners.index))].shape[0]) if "Pass End X" in corners.columns else 0

    other = max(len(corners) - inswing - outswing - straight - short, 0)
    lv = [(l, v) for l, v in [("Inswing", inswing), ("Outswing", outswing), ("Straight", straight), ("Short", short), ("Other", other)] if v > 0]
    if not lv:
        lv = [("Corners", len(corners))]

    labels, values = zip(*lv)
    fig = go.Figure(go.Pie(
        labels=list(labels), values=list(values), hole=0.5,
        marker_colors=[AWAY_COLOR, HOME_COLOR, GOLD, "#888", "#555"],
    ))
    fig.update_layout(layout_config(
        height=260, margin=dict(l=20, r=20, t=30, b=20), showlegend=True,
    ))
    return fig


# ── Corner target zones ────────────────────────────────────────────────────────

def _corner_targets(opp_ev: pd.DataFrame) -> go.Figure:
    """Headed shots and aerials from corners — where deliveries target."""
    corner_mask = _q(opp_ev, "From corner") | _q(opp_ev, "Corner taken")
    corner_ev   = opp_ev[corner_mask]

    heads = corner_ev[
        corner_ev["event_type"].isin(_SHOT_EVENTS | {"Aerial"}) & corner_ev["x"].notna() & corner_ev["y"].notna()
    ]
    if heads.empty:
        return empty_fig("No corner target data")

    fig = go.Figure()
    add_pitch_background(fig)
    goals  = heads[heads["event_type"] == "Goal"]
    other  = heads[heads["event_type"] != "Goal"]
    for df, color, symbol, name, sz in [
        (other, HOME_COLOR, "circle",  "Header/Shot",  9),
        (goals, GOLD,       "star",    "Goal",        14),
    ]:
        if not df.empty:
            fig.add_trace(go.Scatter(
                x=df["x"], y=df["y"], mode="markers",
                marker=dict(size=sz, color=color, opacity=0.8,
                            symbol=symbol, line=dict(color="white", width=0.8)),
                name=name,
            ))
    fig.update_layout(layout_config(height=380, **PITCH_AXIS_FULL,
                                    margin=dict(l=20, r=20, t=30, b=40)))
    fig.update_layout(legend=dict(orientation="h", yanchor="bottom", y=-0.15,
                                  xanchor="center", x=0.5))
    return fig


# ── Free kick types ────────────────────────────────────────────────────────────

def _free_kick_chart(opp_ev: pd.DataFrame) -> go.Figure:
    """Direct vs indirect FK and shot scatter."""
    fk = opp_ev[_q(opp_ev, "Free kick taken") | (opp_ev["event_type"] == "Pass") & _q(opp_ev, "Free kick")]
    if fk.empty:
        fk = opp_ev[opp_ev["event_type"] == "Pass"][_q(opp_ev[opp_ev["event_type"] == "Pass"], "Free kick taken")]
    if fk.empty:
        return empty_fig("No free kick data")

    direct   = fk[_q(fk, "Direct free")]
    indirect = fk[~_q(fk, "Direct free")]

    direct_shots = opp_ev[opp_ev["event_type"].isin(_SHOT_EVENTS) & _q(opp_ev, "Free kick")].dropna(subset=["x", "y"])

    fig = go.Figure()
    add_pitch_background(fig)
    if not direct.dropna(subset=["x", "y"]).empty:
        df = direct.dropna(subset=["x", "y"])
        fig.add_trace(go.Scatter(x=df["x"], y=df["y"], mode="markers",
                                  marker=dict(size=8, color=GOLD, opacity=0.7, symbol="circle",
                                              line=dict(color="white", width=0.5)),
                                  name="Direct FK"))
    if not indirect.dropna(subset=["x", "y"]).empty:
        df = indirect.dropna(subset=["x", "y"])
        fig.add_trace(go.Scatter(x=df["x"], y=df["y"], mode="markers",
                                  marker=dict(size=8, color=HOME_COLOR, opacity=0.7, symbol="circle-open",
                                              line=dict(color="white", width=0.5)),
                                  name="Indirect FK"))
    if not direct_shots.empty:
        fig.add_trace(go.Scatter(x=direct_shots["x"], y=direct_shots["y"], mode="markers",
                                  marker=dict(size=12, color=AWAY_COLOR, opacity=0.9, symbol="star",
                                              line=dict(color="white", width=1)),
                                  name="FK Shot"))
    fig.update_layout(layout_config(height=380, **PITCH_AXIS_FULL,
                                    margin=dict(l=20, r=20, t=30, b=40)))
    fig.update_layout(legend=dict(orientation="h", yanchor="bottom", y=-0.15,
                                  xanchor="center", x=0.5))
    return fig


# ── Aerial duel win rate ───────────────────────────────────────────────────────

def _aerial_chart(opp_ev: pd.DataFrame) -> go.Figure:
    aerials = opp_ev[opp_ev["event_type"] == "Aerial"]
    if aerials.empty:
        return empty_fig("No aerial data")

    won  = int(aerials["outcome"].eq(1).sum())
    lost = int((aerials["outcome"] != 1).sum())
    total = won + lost
    pct  = round(won / total * 100, 1) if total else 0

    fig = go.Figure(go.Bar(
        x=["Won", "Lost"],
        y=[won, lost],
        marker_color=[GOLD, AWAY_COLOR],
        text=[f"{won} ({pct}%)", f"{lost} ({100-pct:.1f}%)"],
        textposition="outside",
    ))
    fig.update_layout(layout_config(
        height=260, margin=dict(l=40, r=30, t=50, b=30),
        title=dict(text=f"Aerial Duels — Win Rate: {pct}%", font=dict(size=12)),
        yaxis_title="Count",
    ))
    return fig


# ── Set pieces conceded (by opposition) ───────────────────────────────────────

def _set_pieces_conceded(bar_ev: pd.DataFrame) -> go.Figure:
    """Barcelona shots from set pieces — shows where the opposition concedes."""
    sp_mask = _q(bar_ev, "Set piece") | _q(bar_ev, "From corner") | _q(bar_ev, "Free kick")
    shots   = bar_ev[bar_ev["event_type"].isin(_SHOT_EVENTS) & sp_mask].dropna(subset=["x", "y"])

    if shots.empty:
        return empty_fig("No set piece shots conceded")

    goals = shots[shots["event_type"] == "Goal"]
    other = shots[shots["event_type"] != "Goal"]

    fig = go.Figure()
    add_pitch_background(fig)
    for df, color, symbol, name, sz in [
        (other, AWAY_COLOR, "circle", "Shot",  9),
        (goals, GOLD,       "star",   "Goal", 14),
    ]:
        if not df.empty:
            fig.add_trace(go.Scatter(
                x=df["x"], y=df["y"], mode="markers",
                marker=dict(size=sz, color=color, opacity=0.85,
                            symbol=symbol, line=dict(color="white", width=1)),
                name=name,
            ))

    n_goals = len(goals)
    n_shots = len(shots)
    fig.update_layout(layout_config(
        height=380, **PITCH_AXIS_FULL,
        title=dict(text=f"Set piece shots vs them: {n_shots}  |  Goals: {n_goals}",
                   font=dict(color=COLORS["text_secondary"], size=11)),
        margin=dict(l=20, r=20, t=50, b=40),
    ))
    fig.update_layout(legend=dict(orientation="h", yanchor="bottom", y=-0.15,
                                  xanchor="center", x=0.5))
    return fig


# ── Set piece balance card ────────────────────────────────────────────────────

def _set_piece_balance(opp_ev: pd.DataFrame, bar_ev: pd.DataFrame) -> html.Div:
    sp_mask_opp = _q(opp_ev, "Set piece") | _q(opp_ev, "From corner") | _q(opp_ev, "Free kick")
    sp_mask_bar = _q(bar_ev, "Set piece") | _q(bar_ev, "From corner") | _q(bar_ev, "Free kick")

    opp_shots = len(opp_ev[opp_ev["event_type"].isin(_SHOT_EVENTS) & sp_mask_opp])
    bar_shots = len(bar_ev[bar_ev["event_type"].isin(_SHOT_EVENTS) & sp_mask_bar])
    opp_goals = len(opp_ev[opp_ev["event_type"] == "Goal"][sp_mask_opp.reindex(opp_ev[opp_ev["event_type"] == "Goal"].index, fill_value=False)])
    bar_goals = len(bar_ev[bar_ev["event_type"] == "Goal"][sp_mask_bar.reindex(bar_ev[bar_ev["event_type"] == "Goal"].index, fill_value=False)])

    def _pill(label, val, color):
        return html.Span([
            html.Span(label, style={"color": COLORS["text_secondary"], "fontSize": "0.78rem", "marginRight": "4px"}),
            html.Span(str(val), style={"color": color, "fontWeight": "bold"}),
        ], style={"background": "#1E2139", "border": f"1px solid {COLORS['dark_border']}",
                  "borderRadius": "6px", "padding": "4px 10px", "marginRight": "8px", "display": "inline-block"})

    return html.Div([
        html.Div([
            html.Span("Their attacking set pieces  ", style={"color": COLORS["text_secondary"], "fontSize": "0.85rem"}),
            _pill("Shots", opp_shots, AWAY_COLOR),
            _pill("Goals", opp_goals, AWAY_COLOR),
        ], className="mb-2"),
        html.Div([
            html.Span("Our set pieces vs them      ", style={"color": COLORS["text_secondary"], "fontSize": "0.85rem"}),
            _pill("Shots", bar_shots, GOLD),
            _pill("Goals", bar_goals, GOLD),
        ]),
    ])


# ── Public builder ─────────────────────────────────────────────────────────────

def build_set_pieces(opp_ev: pd.DataFrame, bar_ev: pd.DataFrame) -> html.Div:
    if opp_ev.empty:
        return no_data("No event data available.")

    hr = html.Hr(style={"borderColor": COLORS["dark_border"], "margin": "1rem 0"})

    # Attacking set pieces (threat to us)
    atk_section = html.Div([
        html.H6("Their Attacking Set Pieces (Threat to Us)", style={"color": GOLD, "marginBottom": "0.5rem"}),
        dbc.Row([
            dbc.Col(section_card("Corner Delivery", dcc.Graph(figure=_corner_delivery(opp_ev), config=CHART_CONFIG)), md=4),
            dbc.Col(section_card("Corner Target Zones", dcc.Graph(figure=_corner_targets(opp_ev), config=CHART_CONFIG)), md=8),
        ], className="mb-3"),
        dbc.Row([
            dbc.Col(section_card("Free Kick Map", dcc.Graph(figure=_free_kick_chart(opp_ev), config=CHART_CONFIG)), md=6),
            dbc.Col(section_card("Aerial Duels", dcc.Graph(figure=_aerial_chart(opp_ev), config=CHART_CONFIG)), md=6),
        ], className="mb-3"),
    ])

    # Defending set pieces (opportunity for us)
    def_section = html.Div([
        html.H6("Their Defending Set Pieces (Opportunity for Us)", style={"color": GOLD, "marginBottom": "0.5rem"}),
        dbc.Row([
            dbc.Col(section_card("Set Pieces Conceded", dcc.Graph(figure=_set_pieces_conceded(bar_ev), config=CHART_CONFIG)), md=8),
            dbc.Col(section_card("Set Piece Balance", _set_piece_balance(opp_ev, bar_ev)), md=4),
        ], className="mb-3"),
    ])

    return html.Div([atk_section, hr, def_section])
