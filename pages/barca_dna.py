"""
CuléVision - Barça DNA (Player Analysis)
Profile card, season stats, attribute radar, and heatmap.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

import pandas as pd
from scipy.stats import percentileofscore
import plotly.graph_objects as go
from dash import html, dcc, Input, Output, no_update
import dash_bootstrap_components as dbc

from utils.config import COLORS
from utils.data_utils import get_all_events, get_match_results, exclude_own_goals, COMPETITION_NAMES, CURRENT_SEASON
from utils.event_utils import (
    compute_event_stats,
    get_long_balls, get_crosses,
    get_shots_on_target,
    get_successful_tackles, get_interceptions, get_ball_recoveries, get_clearances,
)
from utils.xg_utils import add_xg_column
from utils.player_analysis.metrics import compute_player_stats
from page_utils.event_filters import SHOT_TYPES as _SHOT_TYPES
from page_utils.visualizations import (
    render_lsc_heatmap_img,
    add_vertical_half_pitch_background,
    VPITCH_AXIS_HALF,
    PITCH_BG,
    HOME_COLOR,
)
from pages.match_analysis_tabs.shared import page_header

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_PLAYER_IMG_DIR = Path(__file__).parent.parent / "assets" / "players"


_COMP_OPTIONS = [
    {"label": "All Competitions", "value": "all"},
] + [{"label": v, "value": v} for v in COMPETITION_NAMES.values()]

_RADAR_DIMS  = ["ATT", "TEC", "TAC", "DEF", "CRE"]
_DIM_METRICS = {
    "ATT": ["goals_app", "shots_app", "shot_acc", "assists_app"],
    "TEC": ["pass_acc", "takeon_pct"],
    "TAC": ["intercepts_app", "recoveries_app", "clearances_app"],
    "DEF": ["tackles_app", "intercepts_app", "recoveries_app", "clearances_app", "aerial_win_pct"],
    "CRE": ["key_passes_app", "assists_app", "takeon_pct"],
}

_GOLD             = COLORS.get("gold", "#EDBB00")
_BARCA_BLUE       = "#004D98"   # Barça royal blue
_BARCA_BLUE_LIGHT = "#1974D2"   # electric blue
_BARCA_GARNET     = "#A50044"   # Barça garnet
_BARCA_GARNET_MID = "#D4145A"   # lighter garnet

_SHOT_OUTCOME_COLOR = {
    "Goal":         _GOLD,            # gold — glorious
    "Saved Shot":   _BARCA_BLUE,      # blue — on target
    "Miss":         _BARCA_GARNET,    # garnet — off target
    "Post":         _BARCA_GARNET_MID,# mid-garnet — so close
    "Blocked Shot": _BARCA_BLUE_LIGHT,# lighter blue — blocked
}
_SHOT_OUTCOME_SYMBOL = {
    "Goal":         "star",
    "Saved Shot":   "circle",
    "Miss":         "x",
    "Post":         "diamond",
    "Blocked Shot": "square",
}

_card_style = {
    "backgroundColor": COLORS["dark_secondary"],
    "border": f"1px solid {COLORS['dark_border']}",
    "borderRadius": "10px",
    "height": "100%",
}

_section_title_style = {
    "color": _GOLD,
    "fontSize": "0.78rem",
    "fontWeight": "700",
    "textTransform": "uppercase",
    "letterSpacing": "0.08em",
    "marginBottom": "14px",
}

_label_style = {
    "color": COLORS["text_secondary"],
    "fontSize": "0.75rem",
    "fontWeight": "700",
    "letterSpacing": "0.08em",
    "marginBottom": "4px",
    "display": "block",
}

# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def _get_player_image_url(jersey: str) -> str | None:
    """Return Dash-relative URL for player image matched by jersey number."""
    try:
        j = int(str(jersey).strip())
        prefix = f"{j:02d}-"
        for fname in os.listdir(_PLAYER_IMG_DIR):
            if fname.startswith(prefix):
                return f"assets/players/{fname}"
    except (ValueError, OSError):
        pass
    return None



def _load_player_options() -> list[dict]:
    try:
        ev = get_all_events(CURRENT_SEASON)
        if ev.empty:
            return []
        names = sorted(ev[ev["team_code"] == "BAR"]["player_name"].dropna().unique())
        return [{"label": n, "value": n} for n in names]
    except Exception:
        logger.exception("Failed to load player options")
        return []


def _get_match_label(match_id, res_by_id: dict) -> str:
    m = res_by_id.get(str(match_id), {})
    if not m:
        return str(match_id)
    date  = str(m.get("date", ""))[:10]
    opp   = m.get("opponent", "?")
    bg    = m.get("barca_goals", 0)
    og    = m.get("opponent_goals", 0)
    comp  = m.get("competition", "")
    return f"{date} · {comp} vs {opp} ({bg}–{og})"


def _compute_radar_scores(player_stats: dict, peers: list[dict]) -> dict[str, int]:
    pool = peers + [player_stats]
    def _avg(s: dict, metrics: list[str]) -> float:
        return sum(s.get(m, 0) or 0 for m in metrics) / len(metrics)
    return {
        dim: round(percentileofscore([_avg(s, metrics) for s in pool], _avg(player_stats, metrics), kind="rank"))
        for dim, metrics in _DIM_METRICS.items()
    }


def _radar_figure(scores: dict[str, int]) -> go.Figure:
    vals   = [scores.get(d, 0) for d in _RADAR_DIMS]
    vals_c = vals + [vals[0]]
    dims_c = _RADAR_DIMS + [_RADAR_DIMS[0]]

    fig = go.Figure()
    fig.add_trace(go.Scatterpolar(
        r=vals_c,
        theta=dims_c,
        fill="toself",
        fillcolor="rgba(237, 187, 0, 0.18)",
        line=dict(color=_GOLD, width=2.5),
        marker=dict(size=7, color=_GOLD),
        hovertemplate="%{theta}: %{r:.0f}<extra></extra>",
    ))
    # Center dot
    fig.add_trace(go.Scatterpolar(
        r=[0],
        theta=[_RADAR_DIMS[0]],
        mode="markers",
        marker=dict(size=7, color=_GOLD),
        hoverinfo="skip",
        showlegend=False,
    ))
    fig.update_layout(
        polar=dict(
            bgcolor="rgba(0,0,0,0)",
            radialaxis=dict(
                visible=False, range=[0, 100],
                showticklabels=False, ticks="",
                showgrid=False, showline=False,
            ),
            angularaxis=dict(
                tickfont=dict(color=COLORS["text_primary"], size=14, family="Arial Black, Arial"),
                showgrid=False,
                showline=True,
                linecolor="rgba(255,255,255,0.35)",
                linewidth=1.5,
                gridcolor="rgba(0,0,0,0)",
            ),
        ),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=70, r=70, t=50, b=50),
        showlegend=False,
    )
    return fig


def _empty_radar() -> go.Figure:
    vals = [0] * len(_RADAR_DIMS)
    fig  = go.Figure()
    fig.add_trace(go.Scatterpolar(
        r=vals + [0],
        theta=_RADAR_DIMS + [_RADAR_DIMS[0]],
        line=dict(color="rgba(255,255,255,0.1)"),
    ))
    fig.add_trace(go.Scatterpolar(
        r=[0],
        theta=[_RADAR_DIMS[0]],
        mode="markers",
        marker=dict(size=7, color="rgba(255,255,255,0.3)"),
        hoverinfo="skip",
        showlegend=False,
    ))
    fig.update_layout(
        polar=dict(
            bgcolor="rgba(0,0,0,0)",
            radialaxis=dict(range=[0, 100], showticklabels=False, showgrid=False, showline=False, visible=False),
            angularaxis=dict(
                tickfont=dict(color=COLORS["text_secondary"], size=14),
                showgrid=False,
                showline=True,
                linecolor="rgba(255,255,255,0.25)",
                linewidth=1.5,
                gridcolor="rgba(0,0,0,0)",
            ),
        ),
        paper_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=70, r=70, t=50, b=50),
        showlegend=False,
    )
    return fig


def _stat_card(label: str, value: str) -> html.Div:
    return html.Div([
        html.Div(value, style={
            "fontSize": "1.55rem", "fontWeight": "bold",
            "color": _GOLD, "lineHeight": "1.1",
        }),
        html.Div(label, style={
            "fontSize": "0.68rem", "color": COLORS["text_secondary"],
            "textTransform": "uppercase", "letterSpacing": "0.05em",
            "marginTop": "3px",
        }),
    ], style={
        "backgroundColor": COLORS["dark_bg"] if "dark_bg" in COLORS else "#0A0E27",
        "border": f"1px solid {COLORS['dark_border']}",
        "borderRadius": "8px",
        "padding": "12px 14px",
        "textAlign": "center",
        "flex": "1",
        "minWidth": "75px",
    })


def _radar_info_row(abbr: str, title: str, desc: str) -> html.Div:
    return html.Div([
        html.Div([
            html.Span(abbr, style={
                "color": _GOLD, "fontWeight": "700", "fontSize": "0.78rem",
                "minWidth": "32px", "display": "inline-block",
                "letterSpacing": "0.05em",
            }),
            html.Span(title, style={
                "color": COLORS["text_primary"], "fontWeight": "600",
                "fontSize": "0.78rem",
            }),
        ]),
        html.Div(desc, style={
            "color": COLORS["text_secondary"], "fontSize": "0.72rem",
            "paddingLeft": "32px", "lineHeight": "1.3",
        }),
    ], style={"marginBottom": "10px"})


def _bio_row(label: str, val: str) -> html.Div:
    return html.Div([
        html.Span(label, style={
            "color": COLORS["text_secondary"], "fontSize": "0.72rem",
            "fontWeight": "700", "marginRight": "8px",
            "minWidth": "44px", "display": "inline-block",
            "textTransform": "uppercase", "letterSpacing": "0.05em",
        }),
        html.Span(val, style={
            "color": COLORS["text_primary"], "fontSize": "0.88rem",
        }),
    ], style={"marginBottom": "7px"})


# ---------------------------------------------------------------------------
# Shooting panel helpers
# ---------------------------------------------------------------------------

def _empty_shot_map() -> go.Figure:
    fig = go.Figure()
    add_vertical_half_pitch_background(fig)
    fig.update_layout(
        **VPITCH_AXIS_HALF,
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor=PITCH_BG,
        height=340, margin=dict(l=0, r=0, t=8, b=0),
    )
    return fig


def _player_shot_map(shots: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    add_vertical_half_pitch_background(fig)

    if not shots.empty and "x" in shots.columns:
        for etype in _SHOT_TYPES:
            grp = shots[shots["event_type"] == etype]
            if grp.empty:
                continue
            fig_x = (100 - grp["y"]).tolist()
            fig_y = grp["x"].tolist()
            xg_vals = grp["xg"].fillna(0.0).tolist() if "xg" in grp.columns else [0.0] * len(grp)
            sizes = (
                [16] * len(grp) if etype == "Goal"
                else [max(8, min(20, int(v * 60 + 8))) for v in xg_vals]
            )
            times = (
                grp["time_min"].fillna(0).astype(int).tolist()
                if "time_min" in grp.columns else [0] * len(grp)
            )
            fig.add_trace(go.Scatter(
                x=fig_x, y=fig_y,
                mode="markers", name=etype,
                marker=dict(
                    color=_SHOT_OUTCOME_COLOR.get(etype, _GOLD),
                    symbol=_SHOT_OUTCOME_SYMBOL.get(etype, "circle"),
                    size=sizes, opacity=0.88,
                    line=dict(color="white", width=1),
                ),
                customdata=list(zip(times, xg_vals)),
                hovertemplate="%{customdata[0]}' | xG: %{customdata[1]:.2f}<extra>" + etype + "</extra>",
            ))

    fig.update_layout(
        **VPITCH_AXIS_HALF,
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor=PITCH_BG,
        height=340, margin=dict(l=0, r=0, t=8, b=0),
        hoverlabel=dict(bgcolor="#1A1D2E", font_color="white", font_size=12),
        legend=dict(
            x=0.01, y=0.01, xanchor="left", yanchor="bottom",
            orientation="v",
            font=dict(color=COLORS["text_primary"], size=10),
            bgcolor="rgba(26,29,46,0.80)",
            bordercolor=COLORS.get("dark_border", "rgba(255,255,255,0.15)"),
            borderwidth=1,
        ),
    )
    return fig


def _shot_donut(shots: pd.DataFrame) -> go.Figure:
    if shots.empty or "event_type" not in shots.columns:
        counts = {et: 0 for et in _SHOT_TYPES}
    else:
        counts = {et: int((shots["event_type"] == et).sum()) for et in _SHOT_TYPES}
    labels = [et for et in _SHOT_TYPES if counts[et] > 0]
    values = [counts[et] for et in labels]
    colors = [_SHOT_OUTCOME_COLOR.get(et, _GOLD) for et in labels]
    total  = sum(values)

    fig = go.Figure(go.Pie(
        labels=labels, values=values,
        hole=0.58,
        marker=dict(colors=colors, line=dict(color="rgba(0,0,0,0.3)", width=1.5)),
        textinfo="percent",
        textfont=dict(color="white", size=11),
        hovertemplate="%{label}: %{value}<extra></extra>",
        sort=False,
    ))
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        height=300, margin=dict(l=10, r=10, t=10, b=10),
        showlegend=True,
        legend=dict(
            x=0.5, y=-0.08, xanchor="center", yanchor="top",
            orientation="h",
            font=dict(color=COLORS["text_primary"], size=10),
            bgcolor="rgba(0,0,0,0)",
        ),
        annotations=[dict(
            text=f"<b>{total}</b><br>shots",
            x=0.5, y=0.5, xref="paper", yref="paper",
            showarrow=False,
            font=dict(color=_GOLD, size=20),
        )],
    )
    return fig


def _shot_stat_row(label: str, value: str, color: str | None = None) -> html.Div:
    return html.Div([
        html.Span(label, style={
            "color": COLORS["text_secondary"],
            "fontSize": "0.72rem", "fontWeight": "600",
            "textTransform": "none" if label.startswith("x") else "uppercase",
            "letterSpacing": "0" if label.startswith("x") else "0.05em",
            "flex": "1",
        }),
        html.Span(value, style={
            "color": color or COLORS["text_primary"],
            "fontSize": "0.88rem", "fontWeight": "700",
        }),
    ], style={
        "display": "flex", "justifyContent": "space-between",
        "alignItems": "center",
        "padding": "7px 0",
        "borderBottom": f"1px solid {COLORS['dark_border']}",
    })


def _fmt(value: int | float, per90: bool, pct: bool = False, decimals: int = 2) -> str:
    """Format a stat value for display. pct=True means it's already a percentage — never scale it."""
    if pct:
        return f"{value:.1f}%"
    if per90:
        return f"{value:.{decimals}f}"
    return str(int(round(value)))


def _scale(value: int | float, minutes: float, per90: bool) -> float:
    """Scale a counting stat to per-90 if requested."""
    if not per90:
        return value
    return value * 90.0 / max(minutes, 1.0)


# ---------------------------------------------------------------------------
# Passing / Possession donut helpers
# ---------------------------------------------------------------------------

def _stat_donut(
    labels: list[str],
    values: list[int],
    colors: list[str],
    center_count: int | float,
    center_label: str,
) -> go.Figure:
    active = [(l, v, c) for l, v, c in zip(labels, values, colors) if v > 0]
    if not active:
        labels, values, colors = ["No data"], [1], ["rgba(255,255,255,0.1)"]
        center_count = 0
    else:
        labels, values, colors = zip(*active)  # type: ignore[assignment]

    fig = go.Figure(go.Pie(
        labels=list(labels), values=list(values),
        hole=0.58,
        marker=dict(
            colors=list(colors),
            line=dict(color="rgba(0,0,0,0.3)", width=1.5),
        ),
        textinfo="percent",
        textfont=dict(color="white", size=11),
        hovertemplate="%{label}: %{value}<extra></extra>",
        sort=False,
    ))
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        height=280, margin=dict(l=10, r=10, t=10, b=10),
        showlegend=True,
        legend=dict(
            x=0.5, y=-0.08, xanchor="center", yanchor="top",
            orientation="h",
            font=dict(color=COLORS["text_primary"], size=10),
            bgcolor="rgba(0,0,0,0)",
        ),
        annotations=[dict(
            text=f"<b>{center_count}</b><br>{center_label}",
            x=0.5, y=0.5, xref="paper", yref="paper",
            showarrow=False,
            font=dict(color=_GOLD, size=18),
        )],
    )
    return fig


def _defending_donut(tackles: int, intercepts: int, recoveries: int, clearances: int) -> go.Figure:
    return _stat_donut(
        ["Tackles", "Interceptions", "Recoveries", "Clearances"],
        [tackles, intercepts, recoveries, clearances],
        [_BARCA_BLUE, _BARCA_GARNET, _GOLD, _BARCA_BLUE_LIGHT],
        tackles + intercepts + recoveries + clearances,
        "actions",
    )


def _passing_donut(accurate: int, inaccurate: int) -> go.Figure:
    return _stat_donut(
        ["Accurate", "Inaccurate"],
        [accurate, inaccurate],
        [_BARCA_BLUE, _BARCA_GARNET],
        accurate + inaccurate,
        "passes",
    )


def _possession_donut(def_t: int, mid_t: int, att_t: int) -> go.Figure:
    return _stat_donut(
        ["Def. Third", "Mid. Third", "Att. Third"],
        [def_t, mid_t, att_t],
        [_BARCA_GARNET, _BARCA_BLUE, _GOLD],
        def_t + mid_t + att_t,
        "touches",
    )


# ---------------------------------------------------------------------------
# Layout
# ---------------------------------------------------------------------------

def create_player_analysis_layout():
    player_opts  = _load_player_options()
    init_player  = player_opts[0]["value"] if player_opts else None

    return dbc.Container([
        # ── Page header ───────────────────────────────────────────────────────
        page_header("Barça DNA"),
        html.Hr(style={"borderColor": COLORS["dark_border"], "marginTop": "6px"}),

        # ── Player selector ───────────────────────────────────────────────────
        dbc.Row([
            dbc.Col([
                html.Label("PLAYER", style=_label_style),
                dcc.Dropdown(
                    id="pa-player",
                    options=player_opts,
                    value=init_player,
                    clearable=False,
                    placeholder="Select player…",
                    style={"backgroundColor": COLORS["dark_secondary"]},
                ),
            ], md=4, xs=12),
        ], className="mb-4"),

        # ── Section 1: Profile + Season Stats (single full-width panel) ─────────
        dbc.Row([
            dbc.Col(
                dbc.Card([
                    dbc.CardBody([
                        dbc.Row([
                            # Photo
                            dbc.Col(
                                html.Img(
                                    id="pa-player-img",
                                    style={
                                        "width": "320px", "height": "320px",
                                        "objectFit": "cover", "borderRadius": "8px",
                                        "border": f"2px solid {COLORS['dark_border']}",
                                        "backgroundColor": COLORS["dark_secondary"],
                                        "display": "block",
                                    },
                                ),
                                width="auto",
                            ),
                            # Bio
                            dbc.Col(
                                html.Div(id="pa-bio", style={"paddingLeft": "14px"}),
                                md=3,
                            ),
                            # Divider
                            dbc.Col(
                                html.Div(style={
                                    "borderLeft": f"1px solid {COLORS['dark_border']}",
                                    "height": "100%", "minHeight": "80px",
                                }),
                                width="auto",
                                className="d-none d-md-block",
                            ),
                            # Season stats
                            dbc.Col([
                                html.Div("Season Stats", style={**_section_title_style, "marginBottom": "10px"}),
                                html.Div(id="pa-season-stats"),
                            ]),
                        ], align="center"),
                    ], style={"padding": "18px"}),
                ], style=_card_style),
                xs=12, className="mb-3",
            ),
        ], className="mb-3"),

        # ── Section 2: Comp + Match filters ──────────────────────────────────
        dbc.Row([
            dbc.Col([
                html.Label("COMP", style=_label_style),
                dcc.Dropdown(
                    id="pa-competition",
                    options=_COMP_OPTIONS,
                    value="all",
                    clearable=False,
                    style={"backgroundColor": COLORS["dark_secondary"]},
                ),
            ], md=3, xs=12, className="mb-3"),

            dbc.Col([
                html.Label("MATCH", style=_label_style),
                dcc.Dropdown(
                    id="pa-match",
                    options=[{"label": "All Matches", "value": "all"}],
                    value="all",
                    clearable=False,
                    style={"backgroundColor": COLORS["dark_secondary"]},
                ),
            ], md=5, xs=12, className="mb-3"),

            dbc.Col([
                html.Label("VIEW", style=_label_style),
                dbc.RadioItems(
                    id="pa-display-mode",
                    options=[
                        {"label": "Total",  "value": "total"},
                        {"label": "Per 90", "value": "per90"},
                    ],
                    value="total",
                    className="btn-group",
                    inputClassName="btn-check",
                    labelClassName="btn btn-outline-warning btn-sm",
                    labelCheckedClassName="active",
                    style={"display": "flex"},
                ),
            ], md=2, xs=12, className="mb-3", style={"display": "flex", "flexDirection": "column", "justifyContent": "flex-end"}),
        ], className="mb-3"),

        # ── Section 3: Radar + Heatmap ────────────────────────────────────────
        dbc.Row([
            dbc.Col(
                dbc.Card([
                    dbc.CardBody([
                        html.Div("Attribute Overview", style=_section_title_style),
                        dbc.Row([
                            # Radar chart
                            dbc.Col(
                                dcc.Loading(
                                    type="circle", color=_GOLD,
                                    children=dcc.Graph(
                                        id="pa-radar",
                                        config={"displayModeBar": False},
                                        style={"height": "420px"},
                                        figure=_empty_radar(),
                                    ),
                                ),
                                md=9, xs=12,
                            ),
                            # Info box
                            dbc.Col(
                                html.Div([
                                    _radar_info_row("ATT", "Attacking",  "Goals, shots, shot accuracy, assists."),
                                    _radar_info_row("TEC", "Technical",  "Pass accuracy and take-on success rate."),
                                    _radar_info_row("TAC", "Tactical",   "Interceptions, recoveries, clearances."),
                                    _radar_info_row("DEF", "Defensive",  "Tackles, interceptions, recoveries, clearances, aerial win %."),
                                    _radar_info_row("CRE", "Creativity", "Key passes, assists, take-on success."),
                                ], style={"paddingLeft": "8px"}),
                                md=3, xs=12,
                                className="d-flex align-items-center",
                            ),
                        ], align="center"),
                    ], style={"padding": "18px"}),
                ], style=_card_style),
                md=6, xs=12, className="mb-3",
            ),

            dbc.Col(
                dbc.Card([
                    dbc.CardBody([
                        html.Div("Heatmap", style=_section_title_style),
                        dcc.Loading(
                            type="circle", color=_GOLD,
                            children=html.Img(
                                id="pa-heatmap",
                                style={
                                    "width": "75%", "borderRadius": "6px",
                                    "display": "block", "margin": "0 auto",
                                },
                            ),
                        ),
                    ], style={"padding": "18px"}),
                ], style=_card_style),
                md=6, xs=12, className="mb-3",
            ),
        ]),

        # ── Section 4: Shooting Panel ─────────────────────────────────────────
        dbc.Row([
            dbc.Col(
                dbc.Card([
                    dbc.CardBody([
                        html.Div("Shooting", style=_section_title_style),
                        dbc.Row([

                            # Left: shot stats
                            dbc.Col(
                                html.Div(id="pa-shot-stats"),
                                md=3, xs=12,
                            ),

                            # Middle: donut
                            dbc.Col(
                                dcc.Loading(
                                    type="circle", color=_GOLD,
                                    children=dcc.Graph(
                                        id="pa-shot-donut",
                                        config={"displayModeBar": False},
                                        figure=_shot_donut(pd.DataFrame()),
                                        style={"height": "300px"},
                                    ),
                                ),
                                md=3, xs=12,
                            ),

                            # Right: shot map
                            dbc.Col(
                                dcc.Loading(
                                    type="circle", color=_GOLD,
                                    children=dcc.Graph(
                                        id="pa-shot-map",
                                        config={"displayModeBar": False},
                                        figure=_empty_shot_map(),
                                        style={"height": "340px"},
                                    ),
                                ),
                                md=6, xs=12,
                            ),
                        ], align="start", className="g-2"),
                    ], style={"padding": "18px"}),
                ], style=_card_style),
                xs=12, className="mb-3",
            ),
        ]),

        # ── Section 5: Passing + Possession ──────────────────────────────────
        dbc.Row([
            # Passing card
            dbc.Col(
                dbc.Card([
                    dbc.CardBody([
                        html.Div("Passing", style=_section_title_style),
                        dbc.Row([
                            dbc.Col(
                                html.Div(id="pa-pass-stats"),
                                md=5, xs=12,
                            ),
                            dbc.Col(
                                dcc.Loading(
                                    type="circle", color=_GOLD,
                                    children=dcc.Graph(
                                        id="pa-pass-donut",
                                        config={"displayModeBar": False},
                                        figure=_passing_donut(0, 0),
                                        style={"height": "280px"},
                                    ),
                                ),
                                md=7, xs=12,
                            ),
                        ], align="center", className="g-2"),
                    ], style={"padding": "18px"}),
                ], style=_card_style),
                md=6, xs=12, className="mb-3",
            ),

            # Possession card
            dbc.Col(
                dbc.Card([
                    dbc.CardBody([
                        html.Div("Possession", style=_section_title_style),
                        dbc.Row([
                            dbc.Col(
                                html.Div(id="pa-poss-stats"),
                                md=5, xs=12,
                            ),
                            dbc.Col(
                                dcc.Loading(
                                    type="circle", color=_GOLD,
                                    children=dcc.Graph(
                                        id="pa-poss-donut",
                                        config={"displayModeBar": False},
                                        figure=_possession_donut(0, 0, 0),
                                        style={"height": "280px"},
                                    ),
                                ),
                                md=7, xs=12,
                            ),
                        ], align="center", className="g-2"),
                    ], style={"padding": "18px"}),
                ], style=_card_style),
                md=6, xs=12, className="mb-3",
            ),
        ], className="mb-3"),

        # ── Section 6: Defending + Discipline ────────────────────────────────
        dbc.Row([
            # Defending
            dbc.Col(
                dbc.Card([
                    dbc.CardBody([
                        html.Div("Defending", style=_section_title_style),
                        dbc.Row([
                            dbc.Col(
                                html.Div(id="pa-def-stats"),
                                md=5, xs=12,
                            ),
                            dbc.Col(
                                dcc.Loading(
                                    type="circle", color=_GOLD,
                                    children=dcc.Graph(
                                        id="pa-def-donut",
                                        config={"displayModeBar": False},
                                        figure=_defending_donut(0, 0, 0, 0),
                                        style={"height": "280px"},
                                    ),
                                ),
                                md=7, xs=12,
                            ),
                        ], align="center", className="g-2"),
                    ], style={"padding": "18px"}),
                ], style=_card_style),
                md=8, xs=12, className="mb-3",
            ),

            # Discipline
            dbc.Col(
                dbc.Card([
                    dbc.CardBody([
                        html.Div("Discipline", style=_section_title_style),
                        html.Div(id="pa-disc-stats"),
                    ], style={"padding": "18px"}),
                ], style={**_card_style, "height": "100%"}),
                md=4, xs=12, className="mb-3",
            ),
        ], className="mb-3"),

    ], fluid=True, className="py-4")


# ---------------------------------------------------------------------------
# Callbacks
# ---------------------------------------------------------------------------

def register_player_analysis_callbacks(app):

    @app.callback(
        Output("pa-match", "options"),
        Output("pa-match", "value"),
        Input("pa-player", "value"),
        Input("pa-competition", "value"),
    )
    def update_match_options(player_name, competition):
        base = [{"label": "All Matches", "value": "all"}]
        if not player_name:
            return base, "all"
        try:
            ev        = get_all_events(CURRENT_SEASON)
            results   = get_match_results()
            res_by_id = {str(r["match_id"]): r for r in results}

            bar_ev = ev[ev["team_code"] == "BAR"]
            if competition and competition != "all":
                bar_ev = bar_ev[bar_ev["competition"] == competition]
            p_ev = bar_ev[bar_ev["player_name"] == player_name]
            if p_ev.empty:
                return base, "all"

            opts = [base[0]]
            for mid in sorted(p_ev["match_id"].unique()):
                opts.append({"label": _get_match_label(mid, res_by_id), "value": str(mid)})
            return opts, "all"
        except Exception:
            logger.exception("update_match_options failed")
            return base, "all"

    @app.callback(
        Output("pa-player-img", "src"),
        Output("pa-bio", "children"),
        Output("pa-season-stats", "children"),
        Input("pa-player", "value"),
    )
    def update_profile(player_name):
        blank = (no_update, html.P("—", style={"color": COLORS["text_secondary"]}),
                 html.P("—", style={"color": COLORS["text_secondary"]}))
        if not player_name:
            return blank

        try:
            ev     = get_all_events(CURRENT_SEASON)
            bar_ev = ev[ev["team_code"] == "BAR"]
            p_ev   = bar_ev[bar_ev["player_name"] == player_name]
            if p_ev.empty:
                return blank

            jersey = (
                str(p_ev["Jersey Number"].dropna().iloc[0])
                if "Jersey Number" in p_ev.columns and not p_ev["Jersey Number"].dropna().empty
                else "—"
            )
            position = (
                str(p_ev["position"].dropna().mode().iloc[0])
                if "position" in p_ev.columns and not p_ev["position"].dropna().empty
                else "—"
            )
            img_url = _get_player_image_url(jersey) or "assets/logos/team/FC-Barcelona-v2002.svg"

            bio = html.Div([
                html.Div(player_name, style={
                    "color": COLORS["text_primary"],
                    "fontSize": "1.4rem",
                    "fontWeight": "700",
                    "marginBottom": "10px",
                    "lineHeight": "1.2",
                }),
                _bio_row("#",      jersey),
                _bio_row("Pos",    position),
                _bio_row("Club",   "FC Barcelona"),
                _bio_row("Season", CURRENT_SEASON),
            ])

            stats = compute_event_stats(p_ev)
            if not stats:
                return img_url, bio, html.P("No stats", style={"color": COLORS["text_secondary"]})

            row1 = html.Div([
                _stat_card("Matches",  str(stats.get("apps", 0) or 0)),
                _stat_card("Minutes",  str(stats.get("total_minutes", 0) or 0)),
                _stat_card("Yellow",   str(stats.get("yellow_cards", 0) or 0)),
                _stat_card("Red",      str(stats.get("red_cards", 0) or 0)),
            ], style={"display": "flex", "gap": "8px", "marginBottom": "8px", "flexWrap": "wrap"})

            row2 = html.Div([
                _stat_card("Goals",   str(stats.get("goals", 0) or 0)),
                _stat_card("Assists", str(stats.get("assists", 0) or 0)),
            ], style={"display": "flex", "gap": "8px", "flexWrap": "wrap"})

            return img_url, bio, html.Div([row1, row2])

        except Exception:
            logger.exception("update_profile failed")
            return blank

    @app.callback(
        Output("pa-radar", "figure"),
        Input("pa-player", "value"),
        Input("pa-competition", "value"),
        Input("pa-match", "value"),
    )
    def update_radar(player_name, competition, match_id):
        if not player_name:
            return _empty_radar()
        try:
            ev     = get_all_events(CURRENT_SEASON)
            bar_ev = ev[ev["team_code"] == "BAR"]
            if competition and competition != "all":
                bar_ev = bar_ev[bar_ev["competition"] == competition]
            if match_id and match_id != "all":
                bar_ev = bar_ev[bar_ev["match_id"].astype(str) == str(match_id)]

            p_ev = bar_ev[bar_ev["player_name"] == player_name]
            if p_ev.empty:
                return _empty_radar()

            player_stats = compute_player_stats(p_ev)
            if not player_stats:
                return _empty_radar()

            peers = []
            for pname in bar_ev["player_name"].dropna().unique():
                if pname == player_name:
                    continue
                s = compute_player_stats(bar_ev[bar_ev["player_name"] == pname])
                if s:
                    peers.append(s)

            scores = _compute_radar_scores(player_stats, peers)
            return _radar_figure(scores)

        except Exception:
            logger.exception("update_radar failed")
            return _empty_radar()

    @app.callback(
        Output("pa-heatmap", "src"),
        Input("pa-player", "value"),
        Input("pa-competition", "value"),
        Input("pa-match", "value"),
    )
    def update_heatmap(player_name, competition, match_id):
        if not player_name:
            return no_update
        try:
            ev     = get_all_events(CURRENT_SEASON)
            bar_ev = ev[ev["team_code"] == "BAR"]
            if competition and competition != "all":
                bar_ev = bar_ev[bar_ev["competition"] == competition]
            if match_id and match_id != "all":
                bar_ev = bar_ev[bar_ev["match_id"].astype(str) == str(match_id)]

            p_ev = bar_ev[bar_ev["player_name"] == player_name]
            if p_ev.empty:
                return no_update

            x = p_ev["x"].dropna().tolist()
            y = p_ev["y"].dropna().tolist()
            if len(x) < 5:
                return no_update

            return render_lsc_heatmap_img(
                x, y,
                COLORS["garnet"],
                show_zone_pcts=True,
                text_color=COLORS["gold"],
            )

        except Exception:
            logger.exception("update_heatmap failed")
            return no_update

    @app.callback(
        Output("pa-shot-stats",    "children"),
        Output("pa-shot-donut",    "figure"),
        Output("pa-shot-map",      "figure"),
        Input("pa-player",         "value"),
        Input("pa-competition",    "value"),
        Input("pa-match",          "value"),
        Input("pa-display-mode",   "value"),
    )
    def update_shooting_panel(player_name, competition, match_id, display_mode):
        p90 = display_mode == "per90"
        _empty = (
            html.P("—", style={"color": COLORS["text_secondary"]}),
            _shot_donut(pd.DataFrame()),
            _empty_shot_map(),
        )
        if not player_name:
            return _empty
        try:
            ev     = get_all_events(CURRENT_SEASON)
            bar_ev = ev[ev["team_code"] == "BAR"]
            if competition and competition != "all":
                bar_ev = bar_ev[bar_ev["competition"] == competition]
            if match_id and match_id != "all":
                bar_ev = bar_ev[bar_ev["match_id"].astype(str) == str(match_id)]

            p_ev = bar_ev[bar_ev["player_name"] == player_name]
            if p_ev.empty:
                return _empty

            shots = exclude_own_goals(
                p_ev[p_ev["event_type"].isin(_SHOT_TYPES)].copy()
            ).dropna(subset=["x", "y"])

            if shots.empty:
                return _empty

            shots  = add_xg_column(shots)
            stats  = compute_event_stats(p_ev)
            mins   = float(stats.get("total_minutes", 1) or 1)

            goals     = int((shots["event_type"] == "Goal").sum())
            xg        = round(shots["xg"].sum(), 2) if "xg" in shots.columns else 0.0
            total     = len(shots)
            on_tgt    = int(shots["event_type"].isin(["Goal", "Saved Shot"]).sum())
            pen_mask  = (
                shots["Penalty"].eq("Si")
                if "Penalty" in shots.columns
                else pd.Series(False, index=shots.index)
            )
            pen_goals = int((shots["event_type"] == "Goal")[pen_mask].sum())
            np_xg     = round(shots.loc[~pen_mask, "xg"].sum(), 2) if "xg" in shots.columns else 0.0

            stats_children = html.Div([
                _shot_stat_row("Goals",           _fmt(_scale(goals,     mins, p90), p90), "#51cf66"),
                _shot_stat_row("xG",              _fmt(_scale(xg,        mins, p90), p90), _GOLD),
                _shot_stat_row("Penalty Goals",   _fmt(_scale(pen_goals, mins, p90), p90)),
                _shot_stat_row("Non-penalty xG",  _fmt(_scale(np_xg,     mins, p90), p90), HOME_COLOR),
                _shot_stat_row("Shots",           _fmt(_scale(total,     mins, p90), p90)),
                _shot_stat_row("Shots on Target", _fmt(_scale(on_tgt,    mins, p90), p90), "#339af0"),
            ])

            return stats_children, _shot_donut(shots), _player_shot_map(shots)

        except Exception:
            logger.exception("update_shooting_panel failed")
            return _empty

    @app.callback(
        Output("pa-pass-stats",    "children"),
        Output("pa-pass-donut",    "figure"),
        Output("pa-poss-stats",    "children"),
        Output("pa-poss-donut",    "figure"),
        Input("pa-player",         "value"),
        Input("pa-competition",    "value"),
        Input("pa-match",          "value"),
        Input("pa-display-mode",   "value"),
    )
    def update_pass_poss_panels(player_name, competition, match_id, display_mode):
        p90 = display_mode == "per90"
        _empty_pass = html.P("—", style={"color": COLORS["text_secondary"]})
        _empty_out = (_empty_pass, _passing_donut(0, 0), _empty_pass, _possession_donut(0, 0, 0))
        if not player_name:
            return _empty_out
        try:
            ev     = get_all_events(CURRENT_SEASON)
            bar_ev = ev[ev["team_code"] == "BAR"]
            if competition and competition != "all":
                bar_ev = bar_ev[bar_ev["competition"] == competition]
            if match_id and match_id != "all":
                bar_ev = bar_ev[bar_ev["match_id"].astype(str) == str(match_id)]

            p_ev = bar_ev[bar_ev["player_name"] == player_name]
            if p_ev.empty:
                return _empty_out

            stats = compute_event_stats(p_ev)
            if not stats:
                return _empty_out

            mins = float(stats.get("total_minutes", 1) or 1)

            # ── Passing ───────────────────────────────────────────────────────
            passes   = int(stats.get("passes", 0) or 0)
            pass_acc = float(stats.get("pass_acc", 0) or 0)
            accurate   = round(passes * pass_acc / 100)
            inaccurate = passes - accurate

            lb_acc = float(stats.get("long_ball_acc", 0) or 0)
            cr_acc = float(stats.get("cross_acc", 0)   or 0)
            kp     = int(stats.get("key_passes", 0)    or 0)
            ast    = int(stats.get("assists", 0)        or 0)

            # xA — sum of xG for shots immediately following this player's passes
            sort_cols = [c for c in ["match_id", "period_id", "time_min", "time_sec"]
                         if c in bar_ev.columns]
            te = bar_ev.sort_values(sort_cols).reset_index(drop=True)
            _is_shot = te["event_type"].isin(_SHOT_TYPES) & te["x"].notna()
            _xg_col  = pd.Series(0.0, index=te.index)
            if _is_shot.any():
                _shot_xg = add_xg_column(te[_is_shot].copy())
                _xg_col.loc[_shot_xg.index] = _shot_xg["xg"].fillna(0.0)
            _next_type  = te["event_type"].shift(-1)
            _next_xg    = _xg_col.shift(-1, fill_value=0.0)
            _same_match = (
                te["match_id"] == te["match_id"].shift(-1, fill_value="")
                if "match_id" in te.columns else pd.Series(True, index=te.index)
            )
            _xa_mask = (
                (te["event_type"] == "Pass") &
                _next_type.isin(_SHOT_TYPES) &
                _same_match &
                (te["player_name"] == player_name)
            )
            xa = round(float(_next_xg[_xa_mask].sum()), 2)

            # Big chances created
            _is_bc = (
                te["event_type"].isin(_SHOT_TYPES) &
                (te["Big Chance"].eq("Si") if "Big Chance" in te.columns else pd.Series(False, index=te.index))
            )
            _bc_mask = (
                (te["event_type"] == "Pass") &
                _is_bc.shift(-1, fill_value=False) &
                _same_match &
                (te["player_name"] == player_name)
            )
            big_chances_created = int(_bc_mask.sum())

            lb_rows  = get_long_balls(p_ev)
            acc_lb   = int(lb_rows["outcome"].eq(1).sum()) if not lb_rows.empty else 0
            cr_rows  = get_crosses(p_ev)
            acc_cr   = int(cr_rows["outcome"].eq(1).sum()) if not cr_rows.empty else 0

            pass_stats = html.Div([
                _shot_stat_row("Assists",             _fmt(_scale(ast,                 mins, p90), p90), _GOLD),
                _shot_stat_row("xA",                  _fmt(_scale(xa,                  mins, p90), p90), HOME_COLOR),
                _shot_stat_row("Successful Passes",   _fmt(_scale(accurate,            mins, p90), p90)),
                _shot_stat_row("Successful Passes %", _fmt(pass_acc, p90, pct=True),              "#51cf66"),
                _shot_stat_row("Accurate Long Balls", _fmt(_scale(acc_lb,              mins, p90), p90)),
                _shot_stat_row("Accurate LB %",       _fmt(lb_acc,  p90, pct=True)),
                _shot_stat_row("Chances Created",     _fmt(_scale(kp,                  mins, p90), p90), _GOLD),
                _shot_stat_row("Big Chances Created", _fmt(_scale(big_chances_created, mins, p90), p90), _GOLD),
                _shot_stat_row("Successful Crosses",  _fmt(_scale(acc_cr,              mins, p90), p90)),
                _shot_stat_row("Successful Cross %",  _fmt(cr_acc,  p90, pct=True)),
            ])

            # ── Possession ────────────────────────────────────────────────────
            take_ons   = int(stats.get("take_ons", 0)        or 0)
            to_pct     = float(stats.get("takeon_pct", 0)    or 0)
            succ_drib  = round(take_ons * to_pct / 100)
            duel_pct   = float(stats.get("duel_pct", 0)      or 0)
            aerials    = int(stats.get("aerials", 0)          or 0)
            aer_pct    = float(stats.get("aerial_win_pct", 0) or 0)
            aer_won    = round(aerials * aer_pct / 100)
            duels_won  = aer_won + round(take_ons * to_pct / 100)
            touches    = int(stats.get("touches", 0)          or 0)
            dispos     = int(stats.get("dispossessions", 0)   or 0)
            pen_fouls  = int(stats.get("penalty_fouls", 0)    or 0)

            x_num = pd.to_numeric(p_ev["x"], errors="coerce")
            touches_box = int((x_num >= 83).sum())

            fouls_committed  = int(stats.get("fouls", 0) or 0)
            fouls_total_rows = int((p_ev["event_type"] == "Foul").sum())
            fouls_won        = max(0, fouls_total_rows - fouls_committed)

            poss_stats = html.Div([
                _shot_stat_row("Successful Dribbles",   _fmt(_scale(succ_drib,   mins, p90), p90), "#51cf66"),
                _shot_stat_row("Successful Dribbles %", _fmt(to_pct,   p90, pct=True),            "#51cf66"),
                _shot_stat_row("Duels Won",             _fmt(_scale(duels_won,   mins, p90), p90)),
                _shot_stat_row("Duels Won %",           _fmt(duel_pct, p90, pct=True)),
                _shot_stat_row("Touches",               _fmt(_scale(touches,     mins, p90), p90)),
                _shot_stat_row("Touches in Opp Box",    _fmt(_scale(touches_box, mins, p90), p90), _GOLD),
                _shot_stat_row("Dispossessed",          _fmt(_scale(dispos,      mins, p90), p90), "#ff6b6b"),
                _shot_stat_row("Fouls Won",             _fmt(_scale(fouls_won,   mins, p90), p90)),
                _shot_stat_row("Penalties Awarded",     _fmt(_scale(pen_fouls,   mins, p90), p90)),
            ])

            # Touch-zone donut — composition doesn't change with per-90 mode
            x_vals = pd.to_numeric(p_ev["x"], errors="coerce").dropna()
            def_t = int((x_vals < 33.33).sum())
            mid_t = int(((x_vals >= 33.33) & (x_vals <= 66.67)).sum())
            att_t = int((x_vals > 66.67).sum())

            return (
                pass_stats,
                _passing_donut(accurate, inaccurate),
                poss_stats,
                _possession_donut(def_t, mid_t, att_t),
            )

        except Exception:
            logger.exception("update_pass_poss_panels failed")
            return _empty_out

    @app.callback(
        Output("pa-def-stats",   "children"),
        Output("pa-def-donut",   "figure"),
        Input("pa-player",       "value"),
        Input("pa-competition",  "value"),
        Input("pa-match",        "value"),
        Input("pa-display-mode", "value"),
    )
    def update_defending_panel(player_name, competition, match_id, display_mode):
        p90 = display_mode == "per90"
        _empty = (
            html.P("—", style={"color": COLORS["text_secondary"]}),
            _defending_donut(0, 0, 0, 0),
        )
        if not player_name:
            return _empty
        try:
            ev     = get_all_events(CURRENT_SEASON)
            bar_ev = ev[ev["team_code"] == "BAR"]
            if competition and competition != "all":
                bar_ev = bar_ev[bar_ev["competition"] == competition]
            if match_id and match_id != "all":
                bar_ev = bar_ev[bar_ev["match_id"].astype(str) == str(match_id)]

            p_ev = bar_ev[bar_ev["player_name"] == player_name]
            if p_ev.empty:
                return _empty

            stats = compute_event_stats(p_ev)
            if not stats:
                return _empty

            apps = int(p_ev["match_id"].nunique()) or 1
            mins = float(stats.get("total_minutes", 1) or 1)

            tackles    = int(stats.get("tackles", 0)        or 0)
            intercepts = round((stats.get("intercepts_app", 0) or 0) * apps)
            recoveries = round((stats.get("recoveries_app", 0) or 0) * apps)
            clearances = round((stats.get("clearances_app", 0) or 0) * apps)
            fouls      = int(stats.get("fouls", 0)           or 0)
            def_contribs = tackles + intercepts + recoveries + clearances

            # Possession won in final third (x > 66.67)
            x_num = pd.to_numeric(p_ev["x"], errors="coerce")
            succ_tackles_ft = int(
                (get_successful_tackles(p_ev)[
                    pd.to_numeric(get_successful_tackles(p_ev)["x"], errors="coerce") > 66.67
                ].shape[0]) if not get_successful_tackles(p_ev).empty else 0
            )
            recov_ft = int(
                (get_ball_recoveries(p_ev)[x_num.reindex(get_ball_recoveries(p_ev).index) > 66.67].shape[0])
                if not get_ball_recoveries(p_ev).empty else 0
            )
            intcpt_ft = int(
                (get_interceptions(p_ev)[x_num.reindex(get_interceptions(p_ev).index) > 66.67].shape[0])
                if not get_interceptions(p_ev).empty else 0
            )
            pwft3 = succ_tackles_ft + recov_ft + intcpt_ft

            # Opponent data — clean sheets stay as total; goals conceded / xG Against scale
            player_match_ids = set(p_ev["match_id"].unique())
            opp_ev = ev[
                (ev["team_code"] != "BAR") &
                (ev["match_id"].isin(player_match_ids))
            ]
            opp_goals = int((opp_ev["event_type"] == "Goal").sum())
            clean_sheets = sum(
                1 for mid in player_match_ids
                if int((opp_ev[opp_ev["match_id"] == mid]["event_type"] == "Goal").sum()) == 0
            )
            opp_shots = opp_ev[opp_ev["event_type"].isin(_SHOT_TYPES)].copy()
            if not opp_shots.empty:
                opp_shots = add_xg_column(opp_shots)
                xg_against = round(opp_shots["xg"].sum(), 2) if "xg" in opp_shots.columns else 0.0
            else:
                xg_against = 0.0

            def_stats = html.Div([
                _shot_stat_row("Def. Contributions", _fmt(_scale(def_contribs, mins, p90), p90), _GOLD),
                _shot_stat_row("Tackles",            _fmt(_scale(tackles,      mins, p90), p90)),
                _shot_stat_row("Interceptions",      _fmt(_scale(intercepts,   mins, p90), p90), "#339af0"),
                _shot_stat_row("Fouls Committed",    _fmt(_scale(fouls,        mins, p90), p90)),
                _shot_stat_row("Recoveries",         _fmt(_scale(recoveries,   mins, p90), p90), "#ffd43b"),
                _shot_stat_row("Poss. Won Final 3rd",_fmt(_scale(pwft3,        mins, p90), p90), "#51cf66"),
                _shot_stat_row("Dribbled Past",      "—"),
                _shot_stat_row("Clearances",         _fmt(_scale(clearances,   mins, p90), p90), "#cc5de8"),
                _shot_stat_row("Clean Sheets",       str(clean_sheets),                          "#51cf66"),
                _shot_stat_row("Goals Conceded",     _fmt(_scale(opp_goals,    mins, p90), p90), "#ff6b6b"),
                _shot_stat_row("xG AGAINST",         _fmt(_scale(xg_against,   mins, p90), p90), HOME_COLOR),
            ])

            return def_stats, _defending_donut(tackles, intercepts, recoveries, clearances)

        except Exception:
            logger.exception("update_defending_panel failed")
            return _empty

    @app.callback(
        Output("pa-disc-stats", "children"),
        Input("pa-player",      "value"),
        Input("pa-competition", "value"),
        Input("pa-match",       "value"),
    )
    def update_discipline_panel(player_name, competition, match_id):
        _empty = html.P("—", style={"color": COLORS["text_secondary"]})
        if not player_name:
            return _empty
        try:
            ev     = get_all_events(CURRENT_SEASON)
            bar_ev = ev[ev["team_code"] == "BAR"]
            if competition and competition != "all":
                bar_ev = bar_ev[bar_ev["competition"] == competition]
            if match_id and match_id != "all":
                bar_ev = bar_ev[bar_ev["match_id"].astype(str) == str(match_id)]

            p_ev = bar_ev[bar_ev["player_name"] == player_name]
            if p_ev.empty:
                return _empty

            stats = compute_event_stats(p_ev)
            if not stats:
                return _empty

            yellows = int(stats.get("yellow_cards", 0) or 0)
            reds    = int(stats.get("red_cards", 0)    or 0)

            def _draw_card(color, count):
                return html.Div([
                    html.Div(
                        str(count),
                        style={
                            "color": "white" if color == "#E8003D" else "#1a1a1a",
                            "fontWeight": "900",
                            "fontSize": "63px",
                            "lineHeight": "1",
                        },
                    ),
                ], style={
                    "width": "120px",
                    "height": "171px",
                    "backgroundColor": color,
                    "borderRadius": "11px",
                    "display": "flex",
                    "alignItems": "center",
                    "justifyContent": "center",
                    "boxShadow": "2px 3px 8px rgba(0,0,0,0.5)",
                    "margin": "0 16px",
                })

            return html.Div([
                html.Div([
                    html.Div([
                        _draw_card("#FFD700", yellows),
                        html.Div("Yellow", style={"color": COLORS["text_secondary"], "fontSize": "11px", "marginTop": "6px", "textAlign": "center"}),
                    ], style={"display": "flex", "flexDirection": "column", "alignItems": "center"}),
                    html.Div([
                        _draw_card("#E8003D", reds),
                        html.Div("Red", style={"color": COLORS["text_secondary"], "fontSize": "11px", "marginTop": "6px", "textAlign": "center"}),
                    ], style={"display": "flex", "flexDirection": "column", "alignItems": "center"}),
                ], style={"display": "flex", "flexDirection": "row", "justifyContent": "center", "alignItems": "flex-start", "paddingTop": "16px"}),
            ])

        except Exception:
            logger.exception("update_discipline_panel failed")
            return _empty
