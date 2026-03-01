"""
transition.py
=============
Transition tab: ball-win events, counter-attack patterns, and ball progression.
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

_WIN_TYPES = {'Ball Recovery', 'Interception', 'Tackle'}
_SHOT_TYPES = {'Miss', 'Saved Shot', 'Goal'}


# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------

def _compute(events: pd.DataFrame) -> dict:
    home_team = events['home_team'].iloc[0]
    away_team = events['away_team'].iloc[0]
    out = {'home_team': home_team, 'away_team': away_team, 'teams': {}}

    for pos, team in (('home', home_team), ('away', away_team)):
        te = events[events['team_position'] == pos]

        ball_recoveries = te[te['event_type'] == 'Ball Recovery']
        interceptions   = te[te['event_type'] == 'Interception']
        tackles_won     = te[(te['event_type'] == 'Tackle') & (te['outcome'] == 1)]

        # Where on the pitch ball wins happen
        win_events = pd.concat([ball_recoveries, interceptions, tackles_won])
        zone_counts = {'Defensive Third': 0, 'Middle Third': 0, 'High Press (Final Third)': 0}
        if 'x' in win_events.columns:
            for x_val in win_events['x'].dropna():
                z = get_zone(float(x_val))
                if z == PitchZone.DEFENSIVE_THIRD:
                    zone_counts['Defensive Third'] += 1
                elif z == PitchZone.MIDDLE_THIRD:
                    zone_counts['Middle Third'] += 1
                else:
                    zone_counts['High Press (Final Third)'] += 1

        # Transitions ending in a shot: within 5 events after a ball win
        sorted_te = te.sort_values(['period_id', 'time_min', 'time_sec']).reset_index(drop=True)
        win_idx = sorted_te.index[sorted_te['event_type'].isin(_WIN_TYPES)].tolist()
        counter_shots = sum(
            1 for i in win_idx
            if sorted_te.iloc[i:min(i + 6, len(sorted_te))]['event_type'].isin(_SHOT_TYPES).any()
        )

        # Forward play: passes originating in defensive/mid that land in opponent half
        passes = te[te['event_type'] == 'Pass']
        opp_half_passes = 0
        if 'x' in passes.columns:
            opp_half_passes = int((passes['x'].dropna() > 50).sum())

        out['teams'][pos] = {
            'team': team,
            'ball_wins': len(win_events),
            'ball_recoveries': len(ball_recoveries),
            'interceptions': len(interceptions),
            'tackles_won': len(tackles_won),
            'counter_shots': counter_shots,
            'opp_half_passes': opp_half_passes,
            'zone_counts': zone_counts,
        }

    return out


# ---------------------------------------------------------------------------
# UI components
# ---------------------------------------------------------------------------

def _metric_card(label: str, home_val, away_val) -> dbc.Col:
    return dbc.Col(html.Div([
        html.Div(label, style={
            'color': COLORS['text_secondary'], 'fontSize': '0.72rem',
            'marginBottom': '10px', 'textAlign': 'center',
        }),
        html.Div([
            html.Span(str(home_val), style={
                'color': GOLD, 'fontWeight': 'bold', 'fontSize': '1.2rem',
            }),
            html.Span(" / ", style={'color': COLORS['dark_border'], 'margin': '0 4px'}),
            html.Span(str(away_val), style={
                'color': COLORS['text_primary'], 'fontWeight': 'bold', 'fontSize': '1.2rem',
            }),
        ], style={'textAlign': 'center'}),
    ], style=_CARD), md=3)


def _win_type_chart(hs: dict, as_: dict) -> dcc.Graph:
    categories = ['Ball Recoveries', 'Interceptions', 'Tackles Won']
    fig = go.Figure([
        go.Bar(
            name=hs['team'],
            x=categories,
            y=[hs['ball_recoveries'], hs['interceptions'], hs['tackles_won']],
            marker_color=GOLD, opacity=0.85,
        ),
        go.Bar(
            name=as_['team'],
            x=categories,
            y=[as_['ball_recoveries'], as_['interceptions'], as_['tackles_won']],
            marker_color=COLORS['text_secondary'], opacity=0.85,
        ),
    ])
    fig.update_layout(
        barmode='group',
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font={'color': COLORS['text_primary'], 'size': 11},
        margin={'l': 40, 'r': 10, 't': 10, 'b': 40},
        height=250,
        legend={'orientation': 'h', 'y': -0.25, 'font': {'size': 10}},
        xaxis={'gridcolor': COLORS['dark_border']},
        yaxis={'gridcolor': COLORS['dark_border']},
    )
    return dcc.Graph(figure=fig, config={'displayModeBar': False})


def _zone_chart(hs: dict, as_: dict) -> dcc.Graph:
    zones = list(hs['zone_counts'].keys())
    fig = go.Figure([
        go.Bar(
            name=hs['team'],
            x=zones,
            y=list(hs['zone_counts'].values()),
            marker_color=GOLD, opacity=0.85,
        ),
        go.Bar(
            name=as_['team'],
            x=zones,
            y=list(as_['zone_counts'].values()),
            marker_color=COLORS['text_secondary'], opacity=0.85,
        ),
    ])
    fig.update_layout(
        barmode='group',
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font={'color': COLORS['text_primary'], 'size': 11},
        margin={'l': 40, 'r': 10, 't': 10, 'b': 40},
        height=250,
        legend={'orientation': 'h', 'y': -0.25, 'font': {'size': 10}},
        xaxis={'gridcolor': COLORS['dark_border']},
        yaxis={'gridcolor': COLORS['dark_border']},
    )
    return dcc.Graph(figure=fig, config={'displayModeBar': False})


# ---------------------------------------------------------------------------
# Tab builder
# ---------------------------------------------------------------------------

def build_transition_tab(events: pd.DataFrame, **_) -> html.Div:
    """Build the Transition tab layout."""
    if events.empty:
        return html.P("No event data.", style={"color": COLORS["text_secondary"]})

    d = _compute(events)
    hs, as_ = d['teams']['home'], d['teams']['away']

    return html.Div([
        dbc.Row([
            _metric_card("Total Ball Wins", hs['ball_wins'], as_['ball_wins']),
            _metric_card("Interceptions", hs['interceptions'], as_['interceptions']),
            _metric_card("Tackles Won", hs['tackles_won'], as_['tackles_won']),
            _metric_card("Transitions → Shot", hs['counter_shots'], as_['counter_shots']),
        ], className="g-3", style={'marginBottom': '16px'}),
        dbc.Row([
            dbc.Col(html.Div([
                html.H6("Ball Win Type", style={
                    'color': GOLD, 'fontWeight': 'bold',
                    'marginBottom': '12px', 'fontSize': '0.9rem',
                }),
                _win_type_chart(hs, as_),
            ], style=_CARD), md=6),
            dbc.Col(html.Div([
                html.H6("Ball Win Location", style={
                    'color': GOLD, 'fontWeight': 'bold',
                    'marginBottom': '12px', 'fontSize': '0.9rem',
                }),
                _zone_chart(hs, as_),
            ], style=_CARD), md=6),
        ], className="g-3"),
    ], style={'marginTop': '16px'})
