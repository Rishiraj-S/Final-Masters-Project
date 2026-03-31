"""
Team Analysis — Attacking Transition sub-tab

Skeleton + callback pattern: the skeleton is rendered immediately on tab
load; all heavy chart computation is deferred to the callback which fires
once the skeleton is in the DOM and again whenever global filters change.
"""

import pandas as pd
import plotly.graph_objects as go
from dash import html, dcc, Input, Output, State
import dash_bootstrap_components as dbc

from utils.config import COLORS
from utils.data_utils import get_all_events, filter_own_goals, CURRENT_SEASON
from pages.match_analysis_tabs.shared import section_card, kpi_row
from page_utils.competitions import normalize_competitions as _normalize_competitions
from page_utils.visualizations import (
    CHART_LAYOUT_DEFAULTS,
    CHART_CONFIG,
    add_pitch_background,
    PITCH_AXIS_FULL,
    empty_fig,
    GOLD,
    HOME_COLOR,
    AWAY_COLOR,
)

_GAIN_TYPES = ['Ball Recovery', 'Tackle', 'Interception']
_PITCH_BG   = '#151932'
_SKEL_SRC   = 'data:image/png;base64,'


# ---------------------------------------------------------------------------
# Skeleton figure
# ---------------------------------------------------------------------------

def _skel_fig(height: int = 400) -> go.Figure:
    fig = go.Figure()
    fig.update_layout(
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor=_PITCH_BG,
        height=height, margin=dict(l=0, r=0, t=0, b=0),
    )
    return fig


# ---------------------------------------------------------------------------
# Chart builders
# ---------------------------------------------------------------------------

def _counter_attacks_scatter(bar: pd.DataFrame) -> go.Figure:
    gains = bar[
        bar['event_type'].isin(_GAIN_TYPES) &
        bar['x'].notna() & (bar['x'] < 50) &
        bar['y'].notna()
    ]
    if gains.empty:
        return empty_fig("No counter-attack start data")

    color_map = {'Ball Recovery': GOLD, 'Tackle': HOME_COLOR, 'Interception': AWAY_COLOR}
    fig = go.Figure()
    add_pitch_background(fig, half=False)
    for etype, color in color_map.items():
        subset = gains[gains['event_type'] == etype]
        if subset.empty:
            continue
        fig.add_trace(go.Scatter(
            x=subset['x'], y=subset['y'],
            mode='markers', name=etype,
            marker=dict(color=color, size=8, opacity=0.8,
                        line=dict(color='white', width=0.5)),
            text=subset['player_name'].fillna('') if 'player_name' in subset.columns else [''] * len(subset),
            hovertemplate='%{text}<extra>' + etype + '</extra>',
        ))
    fig.update_layout(**CHART_LAYOUT_DEFAULTS, height=400, **PITCH_AXIS_FULL)
    fig.update_layout(legend=dict(orientation='h', y=-0.05, x=0.5, xanchor='center'))
    return fig


def _recovery_to_shot_funnel(bar: pd.DataFrame) -> go.Figure:
    gains       = bar[bar['event_type'].isin(_GAIN_TYPES)]
    n_gains     = int(len(gains))
    own_h_gains = int(gains[gains['x'].notna() & (gains['x'] < 50)].shape[0])
    n_shots     = int(bar[bar['event_type'].isin(['Miss', 'Saved Shot', 'Goal'])].shape[0])
    n_goals     = int(len(filter_own_goals(bar[bar['event_type'] == 'Goal'].copy())))

    if n_gains == 0:
        return empty_fig("No transition data")

    fig = go.Figure(go.Funnel(
        y=['Total Gains', 'Own-Half Gains\n(Counter Starts)', 'Shots', 'Goals'],
        x=[n_gains, own_h_gains, n_shots, n_goals],
        textinfo='value+percent initial',
        marker=dict(color=[GOLD, HOME_COLOR, AWAY_COLOR, '#51cf66']),
        textfont=dict(color='white', size=11),
        hovertemplate='%{y}: %{x}<extra></extra>',
    ))
    fig.update_layout(**CHART_LAYOUT_DEFAULTS, height=340)
    fig.update_layout(margin=dict(l=10, r=10, t=20, b=10))
    return fig


def _gains_zone_bar(bar: pd.DataFrame) -> go.Figure:
    gains = bar[bar['event_type'].isin(_GAIN_TYPES) & bar['x'].notna()]
    if gains.empty:
        return empty_fig("No gain zone data")

    own = int(gains[gains['x'] < 33].shape[0])
    mid = int(gains[(gains['x'] >= 33) & (gains['x'] < 66)].shape[0])
    fin = int(gains[gains['x'] >= 66].shape[0])

    fig = go.Figure(go.Bar(
        y=['Own Third', 'Mid Third', 'Final Third'],
        x=[own, mid, fin],
        orientation='h',
        marker_color=[AWAY_COLOR, GOLD, HOME_COLOR],
        hovertemplate='%{y}: %{x} gains<extra></extra>',
    ))
    fig.update_layout(**CHART_LAYOUT_DEFAULTS, height=210, xaxis_title='Possession Gains')
    fig.update_layout(margin=dict(l=10, r=10, t=10, b=30))
    return fig


def _turnover_zones_map(bar: pd.DataFrame) -> go.Figure:
    gains = bar[bar['event_type'].isin(_GAIN_TYPES)].dropna(subset=['x', 'y'])
    if gains.empty:
        return empty_fig("No turnover zone data")

    def zone_color(x):
        if x < 33: return AWAY_COLOR
        if x < 66: return GOLD
        return HOME_COLOR

    fig = go.Figure()
    add_pitch_background(fig, half=False)
    fig.add_trace(go.Scatter(
        x=gains['x'], y=gains['y'],
        mode='markers',
        marker=dict(color=gains['x'].map(zone_color), size=6, opacity=0.7,
                    line=dict(color='white', width=0.3)),
        text=gains['player_name'].fillna('') if 'player_name' in gains.columns else [''] * len(gains),
        hovertemplate='%{text}<br>(%{x:.0f}, %{y:.0f})<extra>Ball Won</extra>',
        showlegend=False,
    ))
    for label, col in [('Own Third', AWAY_COLOR), ('Mid Third', GOLD), ('Final Third', HOME_COLOR)]:
        fig.add_trace(go.Scatter(x=[None], y=[None], mode='markers',
                                 marker=dict(color=col, size=8), name=label))
    fig.update_layout(**CHART_LAYOUT_DEFAULTS, height=380, **PITCH_AXIS_FULL)
    fig.update_layout(legend=dict(orientation='h', y=-0.05, x=0.5, xanchor='center'))
    return fig


def _build_kpi(bar: pd.DataFrame) -> html.Div:
    gains          = bar[bar['event_type'].isin(_GAIN_TYPES)]
    n_gains        = int(len(gains))
    own_half_gains = int(gains[gains['x'].notna() & (gains['x'] < 50)].shape[0])
    final_third_g  = int(gains[gains['x'].notna() & (gains['x'] >= 66)].shape[0])
    fast_breaks    = int(bar[bar['Fast break'] == 'Si'].shape[0]) \
        if 'Fast break' in bar.columns else 0
    n_shots        = int(bar[bar['event_type'].isin(['Miss', 'Saved Shot', 'Goal'])].shape[0])
    n_goals        = int(len(filter_own_goals(bar[bar['event_type'] == 'Goal'].copy())))

    return kpi_row(
        {'gains': n_gains, 'oh_gains': own_half_gains, 'ft_gains': final_third_g,
         'fast_break': fast_breaks, 'shots': n_shots, 'goals': n_goals},
        [('gains', 'Total Gains'), ('oh_gains', 'Own-Half Gains'),
         ('ft_gains', 'Final Third Gains'), ('fast_break', 'Fast Breaks'),
         ('shots', 'Shots'), ('goals', 'Goals')],
        colors={'oh_gains': GOLD, 'ft_gains': HOME_COLOR, 'fast_break': AWAY_COLOR},
    )


# ---------------------------------------------------------------------------
# Skeleton layout
# ---------------------------------------------------------------------------

def build_attacking_transition_skeleton() -> html.Div:
    """Return placeholder layout; all graphs are populated by the callback."""
    return html.Div([
        html.Div(id='atk-trans-kpi'),
        dbc.Row([
            dbc.Col(section_card(
                "Counter-Attack Starts — Gains in Own Half  ● Recovery  ● Tackle  ◆ Intercept",
                dcc.Loading(type='circle', color=COLORS['gold'],
                    children=dcc.Graph(id='atk-trans-counter-scatter',
                        figure=_skel_fig(400), config=CHART_CONFIG)),
            ), md=6),
            dbc.Col([
                section_card(
                    "Recovery → Shot Funnel",
                    dcc.Loading(type='circle', color=COLORS['gold'],
                        children=dcc.Graph(id='atk-trans-funnel',
                            figure=_skel_fig(340), config=CHART_CONFIG)),
                ),
                section_card(
                    "Gains by Zone",
                    dcc.Loading(type='circle', color=COLORS['gold'],
                        children=dcc.Graph(id='atk-trans-zones-bar',
                            figure=_skel_fig(210), config=CHART_CONFIG)),
                ),
            ], md=6),
        ], className='mb-3'),
        dbc.Row([
            dbc.Col(section_card(
                "Turnover Zones — Where Barça Wins the Ball",
                dcc.Loading(type='circle', color=COLORS['gold'],
                    children=dcc.Graph(id='atk-trans-zones-map',
                        figure=_skel_fig(380), config=CHART_CONFIG)),
            ), md=12),
        ], className='mb-3'),
    ])


# ---------------------------------------------------------------------------
# Callbacks
# ---------------------------------------------------------------------------

def register_attacking_transition_callbacks(app) -> None:

    @app.callback(
        Output('atk-trans-kpi',             'children'),
        Output('atk-trans-counter-scatter', 'figure'),
        Output('atk-trans-funnel',          'figure'),
        Output('atk-trans-zones-bar',       'figure'),
        Output('atk-trans-zones-map',       'figure'),
        Input('ta-competition-selector',    'value'),
        Input('ta-venue-selector',          'value'),
        Input('ta-selected-matches',        'data'),
        State('ta-match-data',              'data'),
    )
    def _update(competition, venue, match_ids, match_data):
        def _empty():
            empty = empty_fig("No data")
            return html.Div(), empty, empty, empty, empty

        events = get_all_events(CURRENT_SEASON)
        if events.empty:
            return _empty()

        comps = _normalize_competitions(competition)
        if comps and 'competition' in events.columns:
            events = events[events['competition'].isin(comps)]

        effective_ids = match_ids if match_ids else None
        if effective_ids == []:
            effective_ids = None

        if venue and venue != 'All' and match_data:
            is_home   = (venue == 'Home')
            venue_ids = [m['match_id'] for m in match_data if m.get('is_home') == is_home]
            effective_ids = (
                venue_ids if effective_ids is None
                else list(set(effective_ids) & set(venue_ids))
            )

        if effective_ids:
            events = events[events['match_id'].isin(effective_ids)]

        bar = events[events['team_code'] == 'BAR']
        if bar.empty:
            return _empty()

        return (
            _build_kpi(bar),
            _counter_attacks_scatter(bar),
            _recovery_to_shot_funnel(bar),
            _gains_zone_bar(bar),
            _turnover_zones_map(bar),
        )
