"""
Opposition Analysis — Tab 2: Their Defence

How they press, block, and where they are vulnerable.
Mirrors Team Analysis Tab 3 but framed as 'how to break them down'.
"""

from __future__ import annotations

import pandas as pd
import numpy as np
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

_DEF_ACTIONS = {"Tackle", "Interception", "Clearance"}
_SHOT_EVENTS  = {"Miss", "Post", "Saved Shot", "Goal"}


def _has(df: pd.DataFrame, col: str) -> bool:
    return col in df.columns and df[col].notna().any()


# ── PPDA ──────────────────────────────────────────────────────────────────────

def _ppda_card(opp_ev: pd.DataFrame, bar_ev: pd.DataFrame, n_matches: int) -> html.Div:
    """
    PPDA from the opposition's perspective:
      numerator   = Barcelona passes in their own defensive half (bar_ev x < 40)
      denominator = opposition tackles + interceptions in high block (opp_ev x > 50)
    Lower PPDA = more aggressive press.
    """
    bar_passes = bar_ev[(bar_ev["event_type"] == "Pass") & bar_ev["x"].notna() & (bar_ev["x"] < 40)]
    opp_press  = opp_ev[opp_ev["event_type"].isin(["Tackle", "Interception"]) &
                         opp_ev["x"].notna() & (opp_ev["x"] > 50)]
    ppda = round(len(bar_passes) / max(len(opp_press), 1), 1)

    label = "Aggressive" if ppda < 8 else ("Moderate" if ppda < 14 else "Low")
    color = "#4caf50" if ppda < 8 else ("#ffc107" if ppda < 14 else "#ef5350")

    return section_card("PPDA (Pressing Intensity)", html.Div([
        html.H2(str(ppda), style={"color": color, "marginBottom": "0"}),
        html.P(f"Passes allowed per defensive action  •  {label} press",
               style={"color": COLORS["text_secondary"], "fontSize": "0.85rem"}),
        html.P(f"Based on {n_matches} match(es)",
               style={"color": COLORS["text_secondary"], "fontSize": "0.78rem"}),
    ]))


# ── Press trigger map ─────────────────────────────────────────────────────────

def _draw_opp_press_heatmap(df):
    """Where opponent presses occur."""
    press = df[df["event_type"].isin(["Tackle", "Interception", "Challenge"])]
    if press.empty:
        return ""
    # Opposition focus -> Garnet color
    return render_lsc_heatmap_img(press["x"].tolist(), press["y"].tolist(), color_hex=AWAY_COLOR, half=False)


def _press_trigger_map(opp_ev: pd.DataFrame) -> go.Figure:
    """Heatmap of where the opposition's pressing actions occur."""
    press = opp_ev[opp_ev["event_type"].isin(["Tackle", "Interception", "Foul"])].dropna(subset=["x", "y"])
    if press.empty:
        return empty_fig("No pressing data")
    img = _draw_opp_press_heatmap(opp_ev)
    fig = go.Figure()
    add_pitch_background(fig)
    fig.add_layout_image(dict(
        source=img, x=0, y=100, xref="x", yref="y",
        sizex=100, sizey=100, sizing="stretch", opacity=0.7, layer="above",
    ))
    fig.update_layout(layout_config(height=380, **PITCH_AXIS_FULL,
                                    margin=dict(l=20, r=20, t=30, b=20)))
    return fig


# ── Defensive line height ─────────────────────────────────────────────────────

def _defensive_line_height(opp_ev: pd.DataFrame) -> go.Figure:
    """Distribution of x-coordinates of defensive actions — indicates line height."""
    def_ev = opp_ev[opp_ev["event_type"].isin(_DEF_ACTIONS)].dropna(subset=["x"])
    if def_ev.empty:
        return empty_fig("No defensive action data")

    fig = go.Figure(go.Histogram(
        x=def_ev["x"], nbinsx=20,
        marker_color=AWAY_COLOR, opacity=0.8,
        name="Defensive actions",
    ))
    mean_x = def_ev["x"].mean()
    fig.add_vline(x=mean_x, line_dash="dash", line_color=GOLD,
                  annotation_text=f"Avg: {mean_x:.1f}", annotation_font_color=GOLD)
    fig.update_layout(layout_config(
        height=280, margin=dict(l=40, r=30, t=40, b=40),
        xaxis_title="x (own goal=0, opp goal=100)",
        yaxis_title="Count",
        xaxis_range=[0, 100],
    ))
    return fig


# ── Defensive actions scatter ─────────────────────────────────────────────────

def _defensive_actions_scatter(opp_ev: pd.DataFrame) -> go.Figure:
    tackles   = opp_ev[opp_ev["event_type"] == "Tackle"].dropna(subset=["x", "y"])
    intercpts = opp_ev[opp_ev["event_type"] == "Interception"].dropna(subset=["x", "y"])
    clearances = opp_ev[opp_ev["event_type"] == "Clearance"].dropna(subset=["x", "y"])

    if tackles.empty and intercpts.empty and clearances.empty:
        return empty_fig("No defensive action data")

    fig = go.Figure()
    add_pitch_background(fig)

    for df, color, name, symbol in [
        (tackles,    AWAY_COLOR, "Tackle",       "circle"),
        (intercpts,  HOME_COLOR, "Interception", "triangle-up"),
        (clearances, GOLD,       "Clearance",    "square"),
    ]:
        if not df.empty:
            fig.add_trace(go.Scatter(
                x=df["x"], y=df["y"], mode="markers",
                marker=dict(size=7, color=color, opacity=0.7,
                            symbol=symbol, line=dict(color="white", width=0.5)),
                name=name,
                hovertemplate=f"{name}<br>x=%{{x:.1f}}, y=%{{y:.1f}}<extra></extra>",
            ))

    fig.update_layout(layout_config(height=400, **PITCH_AXIS_FULL,
                                    margin=dict(l=20, r=20, t=30, b=40)))
    fig.update_layout(legend=dict(orientation="h", yanchor="bottom", y=-0.15,
                                  xanchor="center", x=0.5))
    return fig


# ── Shots allowed (by Barcelona) ─────────────────────────────────────────────

def _shots_allowed_map(bar_ev: pd.DataFrame) -> go.Figure:
    """Scatter of Barcelona shots — shows where the opposition allowed attempts."""
    shots = bar_ev[bar_ev["event_type"].isin(_SHOT_EVENTS)].dropna(subset=["x", "y"])
    if shots.empty:
        return empty_fig("No shot data")

    goals = shots[shots["event_type"] == "Goal"]
    on_t  = shots[shots["event_type"] == "Saved Shot"]
    off_t = shots[shots["event_type"].isin({"Miss", "Post"})]

    fig = go.Figure()
    add_pitch_background(fig)

    for df, color, symbol, name, size in [
        (off_t, "#666",      "circle-open", "Off Target",  8),
        (on_t,  AWAY_COLOR,  "circle",      "On Target",  10),
        (goals, GOLD,        "star",        "Goal",       14),
    ]:
        if not df.empty:
            fig.add_trace(go.Scatter(
                x=df["x"], y=df["y"], mode="markers",
                marker=dict(size=size, color=color, opacity=0.85,
                            symbol=symbol, line=dict(color="white", width=1)),
                name=name,
                hovertemplate=f"{name}<br>x=%{{x:.1f}}, y=%{{y:.1f}}<extra></extra>",
            ))

    n_goals = len(goals)
    n_shots = len(shots)
    fig.update_layout(layout_config(
        height=400, **PITCH_AXIS_FULL,
        title=dict(text=f"Conceded: {n_goals} goals from {n_shots} shots",
                   font=dict(color=COLORS["text_secondary"], size=11)),
        margin=dict(l=20, r=20, t=50, b=40),
    ))
    fig.update_layout(legend=dict(orientation="h", yanchor="bottom", y=-0.15,
                                  xanchor="center", x=0.5))
    return fig


# ── Weak-side analysis ────────────────────────────────────────────────────────

def _weak_side_chart(bar_ev: pd.DataFrame) -> go.Figure:
    """Barcelona shots split by left/centre/right side of the pitch — where opposition is exposed."""
    shots = bar_ev[bar_ev["event_type"].isin(_SHOT_EVENTS)].dropna(subset=["y"])
    if shots.empty:
        return empty_fig("No shot data for side analysis")

    left   = shots[shots["y"] <= 33]
    centre = shots[(shots["y"] > 33) & (shots["y"] < 67)]
    right  = shots[shots["y"] >= 67]

    fig = go.Figure(go.Bar(
        x=["Left", "Centre", "Right"],
        y=[len(left), len(centre), len(right)],
        marker_color=[AWAY_COLOR, GOLD, HOME_COLOR],
        text=[str(v) for v in [len(left), len(centre), len(right)]],
        textposition="outside",
    ))
    fig.update_layout(layout_config(
        height=260, margin=dict(l=40, r=30, t=40, b=40),
        yaxis_title="Shots conceded",
        title=dict(text="Shots Conceded by Side", font=dict(size=12)),
    ))
    return fig


# ── Top defenders table ────────────────────────────────────────────────────────

def _top_defenders(opp_ev: pd.DataFrame) -> html.Div:
    def_ev = opp_ev[opp_ev["event_type"].isin(_DEF_ACTIONS | {"Aerial"})]
    if def_ev.empty or "player_name" not in def_ev.columns:
        return html.P("No data", style={"color": COLORS["text_secondary"]})

    stats = def_ev.groupby(["player_name", "event_type"]).size().unstack(fill_value=0)
    for col in ["Tackle", "Interception", "Clearance", "Aerial"]:
        if col not in stats.columns:
            stats[col] = 0
    stats["Total"] = stats[["Tackle", "Interception", "Clearance"]].sum(axis=1)
    top = stats.sort_values("Total", ascending=False).head(8).reset_index()

    th_s = {"color": COLORS["text_secondary"], "fontSize": "0.8rem", "padding": "4px 8px"}
    td_s = {"color": COLORS["text_primary"],   "fontSize": "0.85rem", "padding": "4px 8px"}

    rows = [html.Tr([html.Td(r["player_name"], style=td_s),
                     html.Td(r["Tackle"],       style=td_s),
                     html.Td(r["Interception"], style=td_s),
                     html.Td(r["Clearance"],    style=td_s),
                     html.Td(r["Total"],        style=td_s)])
            for _, r in top.iterrows()]

    return html.Table([
        html.Thead(html.Tr([html.Th("Player", style=th_s), html.Th("Tackles", style=th_s),
                             html.Th("Interceptions", style=th_s), html.Th("Clearances", style=th_s),
                             html.Th("Total", style=th_s)])),
        html.Tbody(rows),
    ], className="table table-dark table-sm")


# ── Public builder ─────────────────────────────────────────────────────────────

def build_defence(
    opp_ev: pd.DataFrame,
    bar_ev: pd.DataFrame,
    n_matches: int,
) -> html.Div:
    if opp_ev.empty:
        return no_data("No event data available.")

    hr = html.Hr(style={"borderColor": COLORS["dark_border"], "margin": "1rem 0"})

    def_ev   = opp_ev[opp_ev["event_type"].isin(_DEF_ACTIONS)]
    n_tackle = len(opp_ev[opp_ev["event_type"] == "Tackle"])
    n_int    = len(opp_ev[opp_ev["event_type"] == "Interception"])
    n_clear  = len(opp_ev[opp_ev["event_type"] == "Clearance"])

    top_kpi = kpi_row(
        {"tackles": n_tackle, "interceptions": n_int, "clearances": n_clear},
        [("tackles", "Tackles"), ("interceptions", "Interceptions"), ("clearances", "Clearances")],
    )

    # Pressing section
    pressing_section = html.Div([
        html.H6("Pressing Behaviour (High Block)", style={"color": GOLD, "marginBottom": "0.5rem"}),
        dbc.Row([
            dbc.Col(_ppda_card(opp_ev, bar_ev, n_matches), md=4),
            dbc.Col(section_card("Press Trigger Map", dcc.Graph(figure=_press_trigger_map(opp_ev), config=CHART_CONFIG)), md=8),
        ], className="mb-3"),
    ])

    # Defensive block section
    block_section = html.Div([
        html.H6("Defensive Block", style={"color": GOLD, "marginBottom": "0.5rem"}),
        dbc.Row([
            dbc.Col(section_card("Defensive Line Height", dcc.Graph(figure=_defensive_line_height(opp_ev), config=CHART_CONFIG)), md=5),
            dbc.Col(section_card("Defensive Actions Map", dcc.Graph(figure=_defensive_actions_scatter(opp_ev), config=CHART_CONFIG)), md=7),
        ], className="mb-3"),
    ])

    # Vulnerabilities section
    vuln_section = html.Div([
        html.H6("Vulnerabilities When Defending", style={"color": GOLD, "marginBottom": "0.5rem"}),
        dbc.Row([
            dbc.Col(section_card("Shots Allowed Map", dcc.Graph(figure=_shots_allowed_map(bar_ev), config=CHART_CONFIG)), md=7),
            dbc.Col(section_card("Shots Conceded by Side", dcc.Graph(figure=_weak_side_chart(bar_ev), config=CHART_CONFIG)), md=5),
        ], className="mb-3"),
    ])

    defenders_section = section_card("Top Defenders", _top_defenders(opp_ev))

    return html.Div([top_kpi, hr, pressing_section, hr, block_section, hr, vuln_section, defenders_section])
