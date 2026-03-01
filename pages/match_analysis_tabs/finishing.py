"""
finishing.py
============
Finishing tab: shots, goals, and attacking efficiency.
Sections: Summary | Shot Types | Shot Zones
"""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
from dash import html, dcc
import dash_bootstrap_components as dbc

from utils.config import COLORS

GOLD = COLORS['gold']
_CARD = {
    'backgroundColor': COLORS['dark_secondary'],
    'border': f'1px solid {COLORS["dark_border"]}',
    'borderRadius': '8px',
    'padding': '16px',
}

_SHOT_TYPES = {'Miss', 'Saved Shot', 'Goal'}
_SOT_TYPES  = {'Saved Shot', 'Goal'}

# x-axis: 0 = own goal → 100 = opponent goal (from performing team's perspective)
_BOX_X          = 83   # rough penalty area boundary
_FINAL_THIRD_X  = 66   # start of final third


# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------

def _compute(events: pd.DataFrame) -> dict:
    home_team = events['home_team'].iloc[0]
    away_team = events['away_team'].iloc[0]
    out = {}

    for pos, team in (('home', home_team), ('away', away_team)):
        te = events[events['team_position'] == pos]

        shots  = te[te['event_type'].isin(_SHOT_TYPES)]
        sot    = te[te['event_type'].isin(_SOT_TYPES)]
        goals  = te[te['event_type'] == 'Goal']
        misses = te[te['event_type'] == 'Miss']
        saved  = te[te['event_type'] == 'Saved Shot']

        n_shots = len(shots)
        n_sot   = len(sot)
        n_goals = len(goals)

        conversion_rate = round(n_goals / n_shots * 100, 1) if n_shots > 0 else 0.0
        shot_accuracy   = round(n_sot   / n_shots * 100, 1) if n_shots > 0 else 0.0

        # Zone breakdown (only when x coordinate is available)
        in_box = out_of_box = final_third_out = 0
        if 'x' in shots.columns:
            for _, row in shots.iterrows():
                x = row.get('x')
                if pd.isna(x):
                    continue
                x = float(x)
                if x >= _BOX_X:
                    in_box += 1
                elif x >= _FINAL_THIRD_X:
                    final_third_out += 1
                else:
                    out_of_box += 1

        out[pos] = {
            'team':            team,
            'shots':           n_shots,
            'sot':             n_sot,
            'goals':           n_goals,
            'misses':          len(misses),
            'saved':           len(saved),
            'conversion_rate': conversion_rate,
            'shot_accuracy':   shot_accuracy,
            'in_box':          in_box,
            'final_third_out': final_third_out,
            'out_of_box':      out_of_box,
        }

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

def build_finishing_tab(events: pd.DataFrame, **_) -> html.Div:
    """Build the Finishing tab layout."""
    if events.empty:
        return html.P("No event data.", style={"color": COLORS["text_secondary"]})

    d = _compute(events)
    hs, as_ = d['home'], d['away']

    # ── Summary ────────────────────────────────────────────────────────────
    summary = html.Div([
        _section_header("Summary"),
        dbc.Row([
            _metric_card("Shots",           hs['shots'],           as_['shots']),
            _metric_card("Shots on Target", hs['sot'],             as_['sot']),
            _metric_card("Goals",           hs['goals'],           as_['goals']),
            _metric_card("Shot Accuracy",   hs['shot_accuracy'],   as_['shot_accuracy'],   is_pct=True),
        ], className="g-3", style={'marginBottom': '12px'}),
        dbc.Row([
            _metric_card("Conversion Rate", hs['conversion_rate'], as_['conversion_rate'], is_pct=True, md=4),
            _metric_card("Saved",           hs['saved'],           as_['saved'],           md=4),
            _metric_card("Missed",          hs['misses'],          as_['misses'],          md=4),
        ], className="g-3"),
    ], style={'marginBottom': '32px'})

    # ── Shot Types ─────────────────────────────────────────────────────────
    shot_types = html.Div([
        _section_header("Shot Types"),
        html.Div([
            html.Div("Shot Outcome Breakdown", style={
                'color': COLORS['text_secondary'], 'fontWeight': '500',
                'marginBottom': '10px', 'fontSize': '0.85rem',
            }),
            _bar_chart(
                hs['team'], as_['team'],
                ['Goals', 'Saved', 'Missed'],
                [hs['goals'], hs['saved'], hs['misses']],
                [as_['goals'], as_['saved'], as_['misses']],
                y_title='Shots',
            ),
        ], style=_CARD),
    ], style={'marginBottom': '32px'})

    # ── Shot Zones ─────────────────────────────────────────────────────────
    shot_zones = html.Div([
        _section_header("Shot Zones"),
        html.Div([
            html.Div("Shot Origin", style={
                'color': COLORS['text_secondary'], 'fontWeight': '500',
                'marginBottom': '10px', 'fontSize': '0.85rem',
            }),
            _bar_chart(
                hs['team'], as_['team'],
                ['Inside Box', 'Final Third (outside box)', 'Long Range'],
                [hs['in_box'], hs['final_third_out'], hs['out_of_box']],
                [as_['in_box'], as_['final_third_out'], as_['out_of_box']],
                y_title='Shots',
            ),
        ], style=_CARD),
    ])

    return html.Div([summary, shot_types, shot_zones], style={'marginTop': '16px'})
