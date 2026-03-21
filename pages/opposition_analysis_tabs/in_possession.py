"""
Opposition Analysis — Tab 1: Their Possession

How they build up, progress, create and finish.
Mirrors Team Analysis Tabs 1+2 but framed as 'what we will face'.
"""

from __future__ import annotations

import pandas as pd
import numpy as np
import plotly.graph_objects as go
from dash import html, dcc
import dash_bootstrap_components as dbc

from utils.config import COLORS
from pages.match_analysis_tabs.shared import (
    layout_config,
    CHART_CONFIG,
    add_pitch_background,
    PITCH_AXIS_FULL,
    PITCH_AXIS_HALF,
    section_card,
    kpi_row,
    empty_fig,
    render_heatmap_img,
    GOLD,
    HOME_COLOR,
    AWAY_COLOR,
)
from .helpers import no_data

_SHOT_EVENTS   = {"Miss", "Post", "Saved Shot", "Goal"}
_LEFT_MAX      = 33
_RIGHT_MIN     = 67


def _has(df: pd.DataFrame, col: str) -> bool:
    return col in df.columns and df[col].notna().any()


# ── Build-up style ─────────────────────────────────────────────────────────────

def _buildup_style(opp_ev: pd.DataFrame) -> go.Figure:
    """GK distribution: Short / Long / Keeper Throw donut."""
    passes = opp_ev[(opp_ev["event_type"] == "Pass") & opp_ev["x"].notna() & (opp_ev["x"] < 15)]
    if passes.empty:
        return empty_fig("No GK distribution data")

    short = int(_has(passes, "Goal Kick") and passes["Goal Kick"].eq(1.0).sum() or 0)
    long_ = int(_has(passes, "Long ball") and passes["Long ball"].eq(1.0).sum() or 0)
    kt    = int(_has(passes, "Keeper Throw") and passes["Keeper Throw"].eq(1.0).sum() or 0)
    other = max(len(passes) - short - long_ - kt, 0)

    labels = ["Short", "Long", "Keeper Throw", "Other"]
    values = [short, long_, kt, other]
    # Remove zeros
    lv = [(l, v) for l, v in zip(labels, values) if v > 0]
    if not lv:
        lv = [("Passes", len(passes))]
    labels, values = zip(*lv)

    fig = go.Figure(go.Pie(
        labels=list(labels), values=list(values),
        hole=0.5,
        marker_colors=[GOLD, AWAY_COLOR, HOME_COLOR, "#555"],
    ))
    fig.update_layout(layout_config(
        height=260, margin=dict(l=20, r=20, t=30, b=20),
        showlegend=True,
    ))
    return fig


# ── Pass network ───────────────────────────────────────────────────────────────

def _pass_network(opp_ev: pd.DataFrame) -> go.Figure:
    """Top player-pair pass connections rendered on a half-pitch."""
    passes = opp_ev[opp_ev["event_type"] == "Pass"].dropna(subset=["player_name", "x", "y"])
    if passes.empty or not _has(opp_ev, "Pass End X"):
        return empty_fig("No pass network data")

    # Average position per player
    avg_pos = passes.groupby("player_name")[["x", "y"]].mean()

    # Count pairs (sequential consecutive passes approximation: use available data)
    # Use Pass End X/Y to draw lines
    passes_end = passes.dropna(subset=["Pass End X", "Pass End Y"])
    if passes_end.empty:
        return empty_fig("No pass endpoint data")

    # Aggregate by player: mean position + pass count
    player_counts = passes.groupby("player_name").size().sort_values(ascending=False).head(11)
    top_players   = set(player_counts.index)

    fig = go.Figure()
    add_pitch_background(fig)

    # Draw pass lines between consecutive passes in same match
    passes_sorted = passes_end.sort_values(["match_id", "time_min", "time_sec"] if "time_min" in passes_end.columns else ["match_id"]) \
                               if "match_id" in passes_end.columns else passes_end

    # Pair connections: group by match, find p→q connections
    pair_counts: dict[tuple, int] = {}
    for _, grp in (passes_sorted.groupby("match_id") if "match_id" in passes_sorted.columns else [(None, passes_sorted)]):
        players_seq = grp["player_name"].tolist()
        for i in range(len(players_seq) - 1):
            a, b = players_seq[i], players_seq[i+1]
            if a != b and a in top_players and b in top_players:
                key = tuple(sorted([a, b]))
                pair_counts[key] = pair_counts.get(key, 0) + 1

    if pair_counts:
        max_c = max(pair_counts.values())
        for (a, b), cnt in sorted(pair_counts.items(), key=lambda x: -x[1])[:15]:
            if a in avg_pos.index and b in avg_pos.index:
                x0, y0 = avg_pos.loc[a, "x"], avg_pos.loc[a, "y"]
                x1, y1 = avg_pos.loc[b, "x"], avg_pos.loc[b, "y"]
                width = max(1, cnt / max_c * 6)
                fig.add_trace(go.Scatter(
                    x=[x0, x1], y=[y0, y1],
                    mode="lines",
                    line=dict(color=f"rgba(200,200,200,{min(cnt/max_c+0.2,0.85):.2f})", width=width),
                    showlegend=False, hoverinfo="skip",
                ))

    # Player nodes
    if not avg_pos.empty:
        top_df = avg_pos.loc[avg_pos.index.isin(top_players)]
        sizes  = [max(8, player_counts.get(p, 1) / player_counts.max() * 22) for p in top_df.index]
        fig.add_trace(go.Scatter(
            x=top_df["x"], y=top_df["y"],
            mode="markers+text",
            marker=dict(size=sizes, color=HOME_COLOR, line=dict(color="white", width=1.5)),
            text=[p.split()[-1] for p in top_df.index],
            textfont=dict(size=9, color="white"),
            textposition="top center",
            name="Player",
            hovertext=top_df.index,
            hovertemplate="%{hovertext}<extra></extra>",
        ))

    fig.update_layout(layout_config(height=420, **PITCH_AXIS_FULL, showlegend=False,
                                    margin=dict(l=20, r=20, t=30, b=20)))
    return fig


# ── Progression corridors ──────────────────────────────────────────────────────

def _progression_corridors(opp_ev: pd.DataFrame) -> go.Figure:
    """Forward passes split by left / centre / right corridor."""
    passes = opp_ev[(opp_ev["event_type"] == "Pass") & opp_ev["y"].notna()]
    if passes.empty:
        return empty_fig("No pass data")

    left   = passes[passes["y"] <= _LEFT_MAX]
    centre = passes[(passes["y"] > _LEFT_MAX) & (passes["y"] < _RIGHT_MIN)]
    right  = passes[passes["y"] >= _RIGHT_MIN]

    n_left, n_cent, n_right = len(left), len(centre), len(right)
    total = max(n_left + n_cent + n_right, 1)

    fig = go.Figure(go.Bar(
        x=["Left", "Centre", "Right"],
        y=[n_left / total * 100, n_cent / total * 100, n_right / total * 100],
        marker_color=[AWAY_COLOR, GOLD, HOME_COLOR],
        text=[f"{v:.0f}%" for v in [n_left/total*100, n_cent/total*100, n_right/total*100]],
        textposition="outside",
    ))
    fig.update_layout(layout_config(
        height=280, margin=dict(l=40, r=30, t=40, b=40),
        yaxis_title="% of passes", yaxis_range=[0, 80],
    ))
    return fig


# ── Shot map ───────────────────────────────────────────────────────────────────

def _shot_map(opp_ev: pd.DataFrame) -> go.Figure:
    shots = opp_ev[opp_ev["event_type"].isin(_SHOT_EVENTS)].dropna(subset=["x", "y"])
    if shots.empty:
        return empty_fig("No shot data")

    goals = shots[shots["event_type"] == "Goal"]
    on_t  = shots[shots["event_type"] == "Saved Shot"]
    off_t = shots[shots["event_type"].isin({"Miss", "Post"})]

    fig = go.Figure()
    add_pitch_background(fig)

    def _trace(df, color, symbol, name, size):
        if df.empty:
            return
        fig.add_trace(go.Scatter(
            x=df["x"], y=df["y"], mode="markers",
            marker=dict(size=size, color=color, opacity=0.85,
                        symbol=symbol, line=dict(color="white", width=1)),
            name=name,
            hovertemplate=f"{name}<br>x=%{{x:.1f}}, y=%{{y:.1f}}<extra></extra>",
        ))

    _trace(off_t, AWAY_COLOR, "circle-open", "Off Target",  9)
    _trace(on_t,  HOME_COLOR, "circle",      "On Target",  11)
    _trace(goals, GOLD,       "star",        "Goal",       15)

    fig.update_layout(layout_config(height=400, **PITCH_AXIS_FULL,
                                    margin=dict(l=20, r=20, t=30, b=40)))
    fig.update_layout(legend=dict(orientation="h", yanchor="bottom", y=-0.15,
                                  xanchor="center", x=0.5))
    return fig


# ── Crossing tendencies ────────────────────────────────────────────────────────

def _crossing_tendencies(opp_ev: pd.DataFrame) -> go.Figure:
    if not _has(opp_ev, "Cross"):
        return empty_fig("No cross data")
    crosses = opp_ev[(opp_ev["event_type"] == "Pass") & (opp_ev["Cross"] == 1.0)].dropna(subset=["x", "y"])
    if crosses.empty:
        return empty_fig("No cross data")

    succ = crosses[crosses["outcome"] == 1]
    fail = crosses[crosses["outcome"] != 1]

    fig = go.Figure()
    add_pitch_background(fig)
    for df, color, name in [(succ, GOLD, "Successful"), (fail, AWAY_COLOR, "Unsuccessful")]:
        if not df.empty:
            fig.add_trace(go.Scatter(
                x=df["x"], y=df["y"], mode="markers",
                marker=dict(size=8, color=color, opacity=0.8, line=dict(color="white", width=0.5)),
                name=name,
                hovertemplate=f"{name}<br>x=%{{x:.1f}}, y=%{{y:.1f}}<extra></extra>",
            ))

    total = len(crosses)
    acc   = round(len(succ) / total * 100, 1) if total else 0
    fig.update_layout(layout_config(height=380, **PITCH_AXIS_FULL,
                                    title=dict(text=f"Crosses: {total}  |  Accuracy: {acc}%",
                                               font=dict(color=COLORS["text_secondary"], size=11)),
                                    margin=dict(l=20, r=20, t=50, b=40)))
    fig.update_layout(legend=dict(orientation="h", yanchor="bottom", y=-0.15, xanchor="center", x=0.5))
    return fig


# ── Average positions ──────────────────────────────────────────────────────────

def _avg_positions(opp_ev: pd.DataFrame) -> go.Figure:
    touches = opp_ev.dropna(subset=["player_name", "x", "y"])
    if touches.empty:
        return empty_fig("No position data")

    avg = (
        touches.groupby("player_name")[["x", "y"]]
        .mean()
        .assign(n=touches.groupby("player_name").size())
        .sort_values("n", ascending=False)
        .head(11)
    )

    fig = go.Figure()
    add_pitch_background(fig)
    fig.add_trace(go.Scatter(
        x=avg["x"], y=avg["y"],
        mode="markers+text",
        marker=dict(size=14, color=HOME_COLOR, line=dict(color="white", width=2)),
        text=[p.split()[-1] for p in avg.index],
        textfont=dict(size=9, color="white"),
        textposition="top center",
        hovertext=avg.index,
        hovertemplate="%{hovertext}<br>x=%{x:.1f}, y=%{y:.1f}<extra></extra>",
        showlegend=False,
    ))
    fig.update_layout(layout_config(height=380, **PITCH_AXIS_FULL,
                                    margin=dict(l=20, r=20, t=30, b=20)))
    return fig


# ── Public builder ─────────────────────────────────────────────────────────────

def build_in_possession(opp_ev: pd.DataFrame, team: str) -> html.Div:
    if opp_ev.empty:
        return no_data("No event data available for this team.")

    hr = html.Hr(style={"borderColor": COLORS["dark_border"], "margin": "1rem 0"})
    passes = opp_ev[opp_ev["event_type"] == "Pass"]
    shots  = opp_ev[opp_ev["event_type"].isin(_SHOT_EVENTS)]

    pass_n   = len(passes)
    pass_acc = round(passes["outcome"].eq(1).sum() / max(pass_n, 1) * 100, 1)
    shot_n   = len(shots)

    top_kpi = kpi_row(
        {"pass_n": pass_n, "pass_acc": pass_acc, "shots": shot_n},
        [("pass_n", "Passes"), ("pass_acc", "Pass Acc %"), ("shots", "Shots")],
    )

    # Build-up section
    build_section = html.Div([
        html.H6("Build-up from the Back", style={"color": GOLD, "marginBottom": "0.5rem"}),
        dbc.Row([
            dbc.Col(section_card("GK Distribution", dcc.Graph(figure=_buildup_style(opp_ev), config=CHART_CONFIG)), md=4),
            dbc.Col(section_card("Progression Corridors (L/C/R)", dcc.Graph(figure=_progression_corridors(opp_ev), config=CHART_CONFIG)), md=4),
            dbc.Col(section_card("Average Positions", dcc.Graph(figure=_avg_positions(opp_ev), config=CHART_CONFIG)), md=4),
        ], className="mb-3"),
    ])

    # Pass network section
    network_section = html.Div([
        html.H6("Passing Patterns", style={"color": GOLD, "marginBottom": "0.5rem"}),
        dbc.Row([
            dbc.Col(section_card("Pass Network", dcc.Graph(figure=_pass_network(opp_ev), config=CHART_CONFIG)), md=6),
            dbc.Col(section_card("Crossing Tendencies", dcc.Graph(figure=_crossing_tendencies(opp_ev), config=CHART_CONFIG)), md=6),
        ], className="mb-3"),
    ])

    # Finishing section
    finishing_section = html.Div([
        html.H6("Chance Creation & Finishing", style={"color": GOLD, "marginBottom": "0.5rem"}),
        dbc.Row([
            dbc.Col(section_card("Shot Map", html.Div([
                html.Div([
                    dbc.Badge(f"{len(shots[shots['event_type']=='Goal'])} Goals",     color="warning", className="me-2"),
                    dbc.Badge(f"{len(shots[shots['event_type']=='Saved Shot'])} On Target", color="success", className="me-2"),
                    dbc.Badge(f"{len(shots[shots['event_type'].isin({'Miss','Post'})]) } Off Target", color="danger", className="me-2"),
                ], className="mb-2"),
                dcc.Graph(figure=_shot_map(opp_ev), config=CHART_CONFIG),
            ])), md=12),
        ], className="mb-3"),
    ])

    return html.Div([top_kpi, hr, build_section, hr, network_section, hr, finishing_section])
