"""
Team Analysis — Defending Transition sub-tab

Skeleton + callback pattern: the skeleton is rendered immediately on tab
load; all heavy chart computation is deferred to the callback which fires
once the skeleton is in the DOM and again whenever global filters change.
"""

import pandas as pd
import plotly.graph_objects as go
from dash import html, dcc, Input, Output, State
import dash_bootstrap_components as dbc

from utils.config import COLORS
from utils.data_utils import get_all_events, exclude_own_goals, CURRENT_SEASON
from pages.match_analysis_tabs.shared import section_card, kpi_row
from page_utils.competitions import normalize_competitions as _normalize_competitions
from page_utils.visualizations import (
    CHART_LAYOUT_DEFAULTS,
    CHART_CONFIG,
    add_pitch_background,
    PITCH_AXIS_FULL,
    PITCH_AXIS_HALF,
    empty_fig,
    render_lsc_heatmap_img,
    GOLD,
    HOME_COLOR,
    AWAY_COLOR,
)

_GAIN_TYPES     = ['Ball Recovery', 'Tackle', 'Interception']
_TURNOVER_TYPES = ['Miscontrol', 'Dispossessed', 'Error', 'Offside Pass']
_PITCH_BG       = '#151932'
_SKEL_SRC       = 'data:image/png;base64,'


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

def _turnover_events_df(bar: pd.DataFrame) -> pd.DataFrame:
    lost_pass  = bar[(bar['event_type'] == 'Pass') & (bar['outcome'] == 0)]
    other_loss = bar[bar['event_type'].isin(_TURNOVER_TYPES)]
    all_loss   = lost_pass if other_loss.empty else pd.concat([lost_pass, other_loss], ignore_index=True)
    return all_loss.dropna(subset=['x', 'y'])


def _counterpress_scatter(bar: pd.DataFrame) -> go.Figure:
    cp = bar[
        bar['event_type'].isin(['Tackle', 'Interception']) &
        bar['x'].notna() & (bar['x'] > 50)
    ].dropna(subset=['x', 'y'])

    if cp.empty:
        return empty_fig("No counter-press data")

    fig = go.Figure()
    add_pitch_background(fig, half=False)
    for etype, color, symbol in [
        ('Tackle',       GOLD,       'circle'),
        ('Interception', HOME_COLOR, 'diamond'),
    ]:
        subset = cp[cp['event_type'] == etype]
        if subset.empty:
            continue
        fig.add_trace(go.Scatter(
            x=subset['x'], y=subset['y'],
            mode='markers', name=etype,
            marker=dict(color=color, size=7, opacity=0.8, symbol=symbol,
                        line=dict(color='white', width=0.5)),
            text=subset['player_name'].fillna('') if 'player_name' in subset.columns else [''] * len(subset),
            hovertemplate='%{text}<extra>' + etype + '</extra>',
        ))
    fig.update_layout(**CHART_LAYOUT_DEFAULTS, height=380, **PITCH_AXIS_FULL)
    fig.update_layout(legend=dict(orientation='h', y=-0.05, x=0.5, xanchor='center'))
    return fig


def _shots_after_turnovers(opp: pd.DataFrame) -> go.Figure:
    shot_types = ['Goal', 'Saved Shot', 'Miss']
    opp_shots  = exclude_own_goals(opp[opp['event_type'].isin(shot_types)].copy()).dropna(subset=['x', 'y'])

    if opp_shots.empty:
        return empty_fig("No opponent shot data")

    opp_shots = opp_shots.copy()
    opp_shots['x_mirror'] = 100 - opp_shots['x']

    _style = {
        'Goal':       ('star',   AWAY_COLOR, 18),
        'Saved Shot': ('circle', GOLD,       11),
        'Miss':       ('x',      '#888888',  10),
    }

    fig = go.Figure()
    add_pitch_background(fig, half=True)
    for etype, (symbol, color, size) in _style.items():
        subset = opp_shots[opp_shots['event_type'] == etype]
        if subset.empty:
            continue
        fig.add_trace(go.Scatter(
            x=subset['x_mirror'], y=subset['y'],
            mode='markers', name=etype,
            marker=dict(color=color, size=size, symbol=symbol,
                        line=dict(color='white', width=1.5)),
            text=subset['player_name'].fillna('') if 'player_name' in subset.columns else [''] * len(subset),
            hovertemplate='<b>%{text}</b><extra>' + etype + '</extra>',
        ))
    fig.update_layout(**CHART_LAYOUT_DEFAULTS, height=400, **PITCH_AXIS_HALF)
    fig.update_layout(legend=dict(orientation='h', y=-0.05, x=0.5, xanchor='center'))
    return fig


def _turnover_type_donut(turnovers: pd.DataFrame) -> go.Figure:
    if turnovers.empty:
        return empty_fig("No turnover data")

    lost_pass    = int(turnovers[turnovers['event_type'] == 'Pass'].shape[0])
    miscontrol   = int(turnovers[turnovers['event_type'] == 'Miscontrol'].shape[0])
    dispossessed = int(turnovers[turnovers['event_type'] == 'Dispossessed'].shape[0])
    other        = int(turnovers.shape[0] - lost_pass - miscontrol - dispossessed)

    if lost_pass + miscontrol + dispossessed + other == 0:
        return empty_fig("No turnover data")

    fig = go.Figure(go.Pie(
        labels=['Lost Pass', 'Miscontrol', 'Dispossessed', 'Other'],
        values=[lost_pass, miscontrol, dispossessed, other],
        marker_colors=[AWAY_COLOR, GOLD, HOME_COLOR, '#888888'],
        hole=0.45,
        textinfo='label+percent',
        textfont=dict(color='white', size=11),
    ))
    fig.update_layout(**CHART_LAYOUT_DEFAULTS, height=260, showlegend=False)
    fig.update_layout(margin=dict(l=0, r=0, t=20, b=0))
    fig.update_layout(title_text='Turnover Type', title_font_color=GOLD, title_font_size=12)
    return fig


def _build_kpi(bar: pd.DataFrame, opp: pd.DataFrame) -> html.Div:
    turnovers   = _turnover_events_df(bar)
    n_turnovers = int(len(turnovers))
    oh_losses   = int(turnovers[turnovers['x'] < 50].shape[0]) if not turnovers.empty else 0
    high_cp     = int(bar[bar['event_type'].isin(['Tackle', 'Interception']) &
                          bar['x'].notna() & (bar['x'] > 50)].shape[0])
    tackles_won = int(bar[(bar['event_type'] == 'Tackle') & (bar['outcome'] == 1)].shape[0])
    intercepts  = int(bar[bar['event_type'] == 'Interception'].shape[0])
    opp_shots   = int(opp[opp['event_type'].isin(['Goal', 'Saved Shot', 'Miss'])].shape[0])

    return kpi_row(
        {'turnovers': n_turnovers, 'oh_losses': oh_losses, 'high_cp': high_cp,
         'tack_won': tackles_won, 'intercepts': intercepts, 'opp_shots': opp_shots},
        [('turnovers', 'Turnovers'), ('oh_losses', 'Own-Half Losses'),
         ('high_cp', 'Counter-Press'), ('tack_won', 'Tackles Won'),
         ('intercepts', 'Interceptions'), ('opp_shots', 'Opp Shots')],
        colors={'oh_losses': AWAY_COLOR, 'turnovers': AWAY_COLOR, 'high_cp': HOME_COLOR},
    )


# ---------------------------------------------------------------------------
# Skeleton layout
# ---------------------------------------------------------------------------

def build_defending_transition_skeleton() -> html.Div:
    """Return placeholder layout; all graphs/images are populated by the callback."""
    return html.Div([
        html.Div(id='def-trans-kpi'),
        dbc.Row([
            dbc.Col(section_card(
                "Counter-Press Map — Def. Actions in Opp Half  ● Tackle  ◆ Intercept",
                dcc.Loading(type='circle', color=COLORS['gold'],
                    children=dcc.Graph(id='def-trans-cp-scatter',
                        figure=_skel_fig(380), config=CHART_CONFIG)),
            ), md=6),
            dbc.Col(section_card(
                "Opponent Shots Conceded  ★ Goal  ● Saved  ✕ Miss",
                dcc.Loading(type='circle', color=COLORS['gold'],
                    children=dcc.Graph(id='def-trans-opp-shots',
                        figure=_skel_fig(400), config=CHART_CONFIG)),
            ), md=6),
        ], className='mb-3'),
        dbc.Row([
            dbc.Col([
                section_card(
                    "Turnover Type Breakdown",
                    dcc.Loading(type='circle', color=COLORS['gold'],
                        children=dcc.Graph(id='def-trans-donut',
                            figure=_skel_fig(260), config=CHART_CONFIG)),
                ),
                section_card(
                    "Transition Danger Map — Own-Half Ball Losses",
                    dcc.Loading(type='circle', color=COLORS['gold'],
                        children=html.Img(id='def-trans-danger-img', src=_SKEL_SRC,
                            style={'width': '100%', 'borderRadius': '4px'})),
                ),
            ], md=5),
            dbc.Col(section_card(
                "Counter-Press Heatmap",
                dcc.Loading(type='circle', color=COLORS['gold'],
                    children=html.Img(id='def-trans-cp-heat-img', src=_SKEL_SRC,
                        style={'width': '100%', 'borderRadius': '4px'})),
            ), md=7),
        ], className='mb-3'),
    ])


# ---------------------------------------------------------------------------
# Callbacks
# ---------------------------------------------------------------------------

def register_defending_transition_callbacks(app) -> None:

    @app.callback(
        Output('def-trans-kpi',          'children'),
        Output('def-trans-cp-scatter',   'figure'),
        Output('def-trans-opp-shots',    'figure'),
        Output('def-trans-donut',        'figure'),
        Output('def-trans-danger-img',   'src'),
        Output('def-trans-cp-heat-img',  'src'),
        Input('ta-competition-selector', 'value'),
        Input('ta-venue-selector',       'value'),
        Input('ta-selected-matches',     'data'),
        State('ta-match-data',           'data'),
    )
    def _update(competition, venue, match_ids, match_data):
        def _empty():
            empty = empty_fig("No data")
            return html.Div(), empty, empty, empty, _SKEL_SRC, _SKEL_SRC

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
        opp = events[events['team_code'] != 'BAR']

        if bar.empty:
            return _empty()

        turnovers = _turnover_events_df(bar)

        cp = bar[
            bar['event_type'].isin(['Tackle', 'Interception']) &
            bar['x'].notna() & (bar['x'] > 50)
        ].dropna(subset=['x', 'y'])
        cp_heat_src = (
            render_lsc_heatmap_img(cp['x'].values, cp['y'].values,
                                   color_hex=AWAY_COLOR, half=False)
            if not cp.empty else _SKEL_SRC
        )

        own_half_turnovers = turnovers[turnovers['x'] < 50] if not turnovers.empty else pd.DataFrame()
        danger_src = (
            render_lsc_heatmap_img(own_half_turnovers['x'].values,
                                   own_half_turnovers['y'].values,
                                   color_hex=AWAY_COLOR, half=False)
            if not own_half_turnovers.empty else _SKEL_SRC
        )

        return (
            _build_kpi(bar, opp),
            _counterpress_scatter(bar),
            _shots_after_turnovers(opp),
            _turnover_type_donut(turnovers),
            danger_src,
            cp_heat_src,
        )
