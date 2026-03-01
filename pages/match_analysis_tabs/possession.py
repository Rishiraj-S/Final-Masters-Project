"""
possession.py
=============
Possession & Build Up tab: pass distribution, territorial control, and ball retention.
Sections: Build Up | Positional Play
"""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
from dash import html, dcc
import dash_bootstrap_components as dbc

from utils.config import COLORS
from page_utils.pitch_zones import get_zone, PitchZone

GOLD = COLORS['gold']
_CARD = {
    'backgroundColor': COLORS['dark_secondary'],
    'border': f'1px solid {COLORS["dark_border"]}',
    'borderRadius': '8px',
    'padding': '16px',
}

_ZONES = ['Defensive Third', 'Middle Third', 'Final Third']
_ZONE_MAP = {
    PitchZone.DEFENSIVE_THIRD: 'Defensive Third',
    PitchZone.MIDDLE_THIRD:    'Middle Third',
    PitchZone.FINAL_THIRD:     'Final Third',
}


# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------

def _zone_label(x: float) -> str:
    return _ZONE_MAP.get(get_zone(x), 'Middle Third')


def _compute(events: pd.DataFrame) -> dict:
    home_team = events['home_team'].iloc[0]
    away_team = events['away_team'].iloc[0]
    out = {}

    for pos, team in (('home', home_team), ('away', away_team)):
        te = events[events['team_position'] == pos]
        passes = te[te['event_type'] == 'Pass']
        succ   = passes[passes['outcome'] == 1]

        zone_counts    = {z: 0 for z in _ZONES}
        own_half_total = 0
        own_half_succ  = 0

        if 'x' in passes.columns:
            for _, row in passes.iterrows():
                x = row.get('x')
                if pd.isna(x):
                    continue
                label = _zone_label(float(x))
                zone_counts[label] += 1
                if float(x) < 50:
                    own_half_total += 1
                    if row.get('outcome') == 1:
                        own_half_succ += 1

        out[pos] = {
            'team':               team,
            'passes':             len(passes),
            'pass_acc':           round(len(succ) / len(passes) * 100, 1) if len(passes) > 0 else 0.0,
            'final_third_passes': zone_counts['Final Third'],
            'mid_third_passes':   zone_counts['Middle Third'],
            'own_half_passes':    own_half_total,
            'own_half_acc':       round(own_half_succ / own_half_total * 100, 1) if own_half_total > 0 else 0.0,
            'turnovers':          len(passes[passes['outcome'] == 0]),
            'zone_counts':        zone_counts,
        }

    total = out['home']['passes'] + out['away']['passes'] or 1
    for pos in ('home', 'away'):
        out[pos]['possession_pct'] = round(out[pos]['passes'] / total * 100, 1)

    return out


# ---------------------------------------------------------------------------
# UI helpers
# ---------------------------------------------------------------------------

def _section_header(title: str) -> html.Div:
    return html.Div([
        html.H5(title, style={
            'color': GOLD, 'fontWeight': '700',
            'marginBottom': '4px', 'fontSize': '1rem',
            'letterSpacing': '0.03em',
        }),
        html.Hr(style={
            'borderColor': COLORS['dark_border'],
            'marginTop': '0', 'marginBottom': '16px',
        }),
    ])


def _possession_bar(home_pct: float, away_pct: float, home_team: str, away_team: str) -> html.Div:
    return html.Div([
        html.Div([
            html.Span(f"{home_pct}%", style={
                'color': GOLD, 'fontWeight': 'bold', 'fontSize': '1.5rem',
            }),
            html.Span(" Possession ", style={
                'color': COLORS['text_secondary'], 'fontSize': '0.9rem', 'margin': '0 10px',
            }),
            html.Span(f"{away_pct}%", style={
                'color': COLORS['text_primary'], 'fontWeight': 'bold', 'fontSize': '1.5rem',
            }),
        ], style={
            'display': 'flex', 'justifyContent': 'center',
            'alignItems': 'center', 'marginBottom': '12px',
        }),
        html.Div([
            html.Div(style={
                'width': f'{home_pct}%', 'height': '14px',
                'backgroundColor': GOLD,
                'borderRadius': '7px 0 0 7px' if home_pct < 100 else '7px',
            }),
            html.Div(style={
                'width': f'{away_pct}%', 'height': '14px',
                'backgroundColor': COLORS['dark_border'],
                'borderRadius': '0 7px 7px 0' if away_pct < 100 else '7px',
            }),
        ], style={'display': 'flex', 'marginBottom': '8px'}),
        html.Div([
            html.Span(home_team, style={'color': COLORS['text_secondary'], 'fontSize': '0.75rem'}),
            html.Span(away_team, style={'color': COLORS['text_secondary'], 'fontSize': '0.75rem'}),
        ], style={'display': 'flex', 'justifyContent': 'space-between'}),
    ])


def _metric_card(label: str, home_val, away_val, is_pct: bool = False, md: int = 3) -> dbc.Col:
    fmt = (lambda v: f"{v}%") if is_pct else str
    return dbc.Col(html.Div([
        html.Div(label, style={
            'color': COLORS['text_secondary'], 'fontSize': '0.72rem',
            'marginBottom': '10px', 'textAlign': 'center',
        }),
        html.Div([
            html.Span(fmt(home_val), style={
                'color': GOLD, 'fontWeight': 'bold', 'fontSize': '1.2rem',
            }),
            html.Span(" / ", style={'color': COLORS['dark_border'], 'margin': '0 4px'}),
            html.Span(fmt(away_val), style={
                'color': COLORS['text_primary'], 'fontWeight': 'bold', 'fontSize': '1.2rem',
            }),
        ], style={'textAlign': 'center'}),
    ], style=_CARD), md=md)


def _bar_chart(home_team: str, away_team: str,
               categories: list, home_vals: list, away_vals: list,
               y_title: str = '') -> dcc.Graph:
    fig = go.Figure([
        go.Bar(name=home_team, x=categories, y=home_vals,
               marker_color=GOLD, opacity=0.85),
        go.Bar(name=away_team, x=categories, y=away_vals,
               marker_color=COLORS['text_secondary'], opacity=0.85),
    ])
    fig.update_layout(
        barmode='group',
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font={'color': COLORS['text_primary'], 'size': 11},
        margin={'l': 40, 'r': 10, 't': 10, 'b': 40},
        height=220,
        legend={'orientation': 'h', 'y': -0.3, 'font': {'size': 10}},
        xaxis={'gridcolor': COLORS['dark_border']},
        yaxis={'gridcolor': COLORS['dark_border'], 'title': y_title},
    )
    return dcc.Graph(figure=fig, config={'displayModeBar': False})


# ---------------------------------------------------------------------------
# Tab builder
# ---------------------------------------------------------------------------

def build_possession_tab(events: pd.DataFrame, **_) -> html.Div:
    """Build the Possession Phase tab layout."""
    if events.empty:
        return html.P("No event data.", style={"color": COLORS["text_secondary"]})

    d = _compute(events)
    hs, as_ = d['home'], d['away']

    # ── Stats ─────────────────────────────────────────────────────────────
    stats_row = html.Div([
        html.Div(
            _possession_bar(hs['possession_pct'], as_['possession_pct'], hs['team'], as_['team']),
            style={**_CARD, 'marginBottom': '12px'},
        ),
        dbc.Row([
            _metric_card("Total Passes",        hs['passes'],             as_['passes']),
            _metric_card("Pass Accuracy",        hs['pass_acc'],           as_['pass_acc'],           is_pct=True),
            _metric_card("Final Third Passes",   hs['final_third_passes'], as_['final_third_passes']),
            _metric_card("Failed Passes",        hs['turnovers'],          as_['turnovers']),
        ], className="g-3"),
    ], style={'marginBottom': '32px'})

    # ── Build Up ───────────────────────────────────────────────────────────
    build_up = html.Div([
        _section_header("Build Up"),
        dbc.Row([
            _metric_card("Own Half Passes",     hs['own_half_passes'], as_['own_half_passes'],  md=4),
            _metric_card("Own Half Pass Acc.",  hs['own_half_acc'],    as_['own_half_acc'],     is_pct=True, md=4),
            _metric_card("Mid Third Passes",    hs['mid_third_passes'], as_['mid_third_passes'], md=4),
        ], className="g-3"),
    ], style={'marginBottom': '32px'})

    # ── Positional Play ────────────────────────────────────────────────────
    positional = html.Div([
        _section_header("Positional Play"),
        html.Div([
            html.Div("Pass Distribution by Zone", style={
                'color': COLORS['text_secondary'], 'fontWeight': '500',
                'marginBottom': '10px', 'fontSize': '0.85rem',
            }),
            _bar_chart(
                hs['team'], as_['team'],
                _ZONES,
                [hs['zone_counts'].get(z, 0) for z in _ZONES],
                [as_['zone_counts'].get(z, 0) for z in _ZONES],
                y_title='Passes',
            ),
        ], style=_CARD),
    ], style={'marginBottom': '32px'})

    return html.Div([stats_row, build_up, positional], style={'marginTop': '16px'})
