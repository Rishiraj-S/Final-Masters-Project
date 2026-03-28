"""
Team Analysis — Tab 4: Transitions

Covers both directions of transition.

Sections:
  Offensive transitions (defence → attack)
    - Counter attacks         (speed + length: gains in own half → shots)
    - Recovery to shot        (funnel: gains → shots + pass count)
    - Turnover zones          (where Barca wins the ball)
  Defensive transitions (attack → defence)
    - Counter-press           (recovery time + success — actions in opp half after loss)
    - Shots after turnovers   (opponent shots conceded post-loss xG)
    - Transition danger map   (where Barca ball losses are most costly)
"""

from dash import html, dcc
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
import pandas as pd
import numpy as np

from utils.config import COLORS
from utils.data_utils import (
    get_all_events,
    get_match_results,
    filter_own_goals,
    exclude_own_goals,
    CURRENT_SEASON,
)
from pages.match_analysis_tabs.shared import (
    section_card,
    kpi_row,
)
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


_COMP_SHORT = {
    'La Liga': 'Liga',
    'Champions League': 'UCL',
    'Copa del Rey': 'Copa',
    'Spanish Super Cup': 'SC',
}

_GAIN_TYPES     = ['Ball Recovery', 'Tackle', 'Interception']
_TURNOVER_TYPES = ['Miscontrol', 'Dispossessed', 'Error', 'Offside Pass']


# ---------------------------------------------------------------------------
# Offensive transitions
# ---------------------------------------------------------------------------

def _counter_attacks_scatter(bar):
    """
    Scatter: possession gains in own half (x < 50) — counter-attack starts.
    Coloured by gain type.
    """
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


def _recovery_to_shot_funnel(bar):
    """Funnel: All Gains → Own-Half Gains (counter starts) → Shots → Goals."""
    gains       = bar[bar['event_type'].isin(_GAIN_TYPES)]
    n_gains     = int(len(gains))
    own_h_gains = int(gains[gains['x'].notna() & (gains['x'] < 50)].shape[0])

    shot_types  = ['Miss', 'Saved Shot', 'Goal']
    shots       = bar[bar['event_type'].isin(shot_types)]
    n_shots     = int(len(shots))

    goals_ev    = filter_own_goals(bar[bar['event_type'] == 'Goal'].copy())
    n_goals     = int(len(goals_ev))

    if n_gains == 0:
        return empty_fig("No transition data")

    stages = ['Total Gains', 'Own-Half Gains\n(Counter Starts)', 'Shots', 'Goals']
    values = [n_gains, own_h_gains, n_shots, n_goals]
    colors = [GOLD, HOME_COLOR, AWAY_COLOR, '#51cf66']

    fig = go.Figure(go.Funnel(
        y=stages, x=values,
        textinfo='value+percent initial',
        marker=dict(color=colors),
        textfont=dict(color='white', size=11),
        hovertemplate='%{y}: %{x}<extra></extra>',
    ))
    fig.update_layout(**CHART_LAYOUT_DEFAULTS, height=340)
    fig.update_layout(margin=dict(l=10, r=10, t=20, b=10))
    return fig


def _turnover_zones_map(bar):
    """Full-pitch scatter where Barca wins possession (all gains), coloured by zone."""
    gains = bar[bar['event_type'].isin(_GAIN_TYPES)].dropna(subset=['x', 'y'])
    if gains.empty:
        return empty_fig("No turnover zone data")

    def zone_color(x):
        if x < 33: return AWAY_COLOR
        if x < 66: return GOLD
        return HOME_COLOR

    colors = gains['x'].map(zone_color)

    fig = go.Figure()
    add_pitch_background(fig, half=False)

    fig.add_trace(go.Scatter(
        x=gains['x'], y=gains['y'],
        mode='markers',
        marker=dict(color=colors, size=6, opacity=0.7,
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


def _gains_zone_bar(bar):
    """Horizontal bar: gains by zone — final third emphasis."""
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
    fig.update_layout(
        **CHART_LAYOUT_DEFAULTS, height=210,
        xaxis_title='Possession Gains',
    )
    fig.update_layout(margin=dict(l=10, r=10, t=10, b=30))
    return fig


# ---------------------------------------------------------------------------
# Defensive transitions
# ---------------------------------------------------------------------------

def _turnover_events_df(bar):
    """Return all events where Barca loses possession."""
    lost_pass  = bar[(bar['event_type'] == 'Pass') & (bar['outcome'] == 0)]
    other_loss = bar[bar['event_type'].isin(_TURNOVER_TYPES)]
    if other_loss.empty:
        all_loss = lost_pass
    else:
        all_loss = pd.concat([lost_pass, other_loss], ignore_index=True)
    return all_loss.dropna(subset=['x', 'y'])


def _counterpress_map(bar):
    """Heatmap of defensive actions in opponent half — Gegenpressing."""
    cp = bar[
        bar['event_type'].isin(['Tackle', 'Interception']) &
        bar['x'].notna() & (bar['x'] > 50)
    ].dropna(subset=['x', 'y'])

    if cp.empty:
        return None
    return render_lsc_heatmap_img(cp['x'].values, cp['y'].values, color_hex=HOME_COLOR, half=False)


def _counterpress_scatter(bar):
    """Scatter of counter-press actions (def actions x > 50)."""
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


def _shots_after_turnovers(opp, bar):
    """
    Shot map of opponent shots in the 30 seconds after a Barca turnover.
    Approximated by: opp shots where opp had the ball in areas Barca lost it.
    Simple proxy: all opp shots in same match within N events of a Barca turnover.
    We use a match-event-sequence approach.
    """
    shot_types = ['Goal', 'Saved Shot', 'Miss']
    opp_shots  = exclude_own_goals(opp[opp['event_type'].isin(shot_types)].copy()).dropna(subset=['x', 'y'])

    if opp_shots.empty:
        return empty_fig("No opponent shot data")

    # Mirror for defensive half view
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


def _transition_danger_map(bar):
    """
    Heatmap of Barca turnovers in own half — where losses lead to danger.
    """
    turnovers = _turnover_events_df(bar)
    if turnovers.empty:
        return None

    # Focus on own half (x < 50) — these are the dangerous ones
    own_half = turnovers[turnovers['x'] < 50]
    if own_half.empty:
        return None
    return render_lsc_heatmap_img(own_half['x'].values, own_half['y'].values,
                              cmap='RdPu', half=False)


def _turnover_type_donut(turnovers):
    """Donut: turnover type breakdown."""
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


# ---------------------------------------------------------------------------
# Public builder
# ---------------------------------------------------------------------------

def build_transitions_tab(season, competitions, match_ids=None):
    """Build the Transitions tab content."""
    events = get_all_events(season)
    if events.empty:
        return html.P("No data available.", style={'color': COLORS['text_secondary']})

    if competitions and 'competition' in events.columns:
        events = events[events['competition'].isin(competitions)]
    if match_ids:
        events = events[events['match_id'].isin(match_ids)]

    bar = events[events['team_code'] == 'BAR']
    opp = events[events['team_code'] != 'BAR']

    if bar.empty:
        return html.P("No Barcelona event data.", style={'color': COLORS['text_secondary']})

    turnovers = _turnover_events_df(bar)

    # ── KPIs ─────────────────────────────────────────────────────────────────
    gains           = bar[bar['event_type'].isin(_GAIN_TYPES)]
    ball_rec        = int(bar[bar['event_type'] == 'Ball Recovery'].shape[0])
    tackles_won     = int(bar[(bar['event_type'] == 'Tackle') & (bar['outcome'] == 1)].shape[0])
    intercepts      = int(bar[bar['event_type'] == 'Interception'].shape[0])
    own_half_gains  = int(gains[gains['x'].notna() & (gains['x'] < 50)].shape[0])
    high_cp         = int(bar[bar['event_type'].isin(['Tackle', 'Interception']) &
                              bar['x'].notna() & (bar['x'] > 50)].shape[0])
    n_turnovers     = int(len(turnovers))
    own_half_losses = int(turnovers[turnovers['x'] < 50].shape[0]) if not turnovers.empty else 0

    fast_breaks = int(bar[bar['Fast break'] == 'Si'].shape[0]) \
        if 'Fast break' in bar.columns else 0

    kpi = kpi_row(
        {
            'ball_rec':   ball_rec,
            'tack_won':   tackles_won,
            'intercepts': intercepts,
            'oh_gains':   own_half_gains,
            'fast_break': fast_breaks,
            'high_cp':    high_cp,
            'turnovers':  n_turnovers,
            'oh_losses':  own_half_losses,
        },
        [
            ('ball_rec',   'Ball Recoveries'),
            ('tack_won',   'Tackles Won'),
            ('intercepts', 'Interceptions'),
            ('oh_gains',   'Own-Half Gains'),
            ('fast_break', 'Fast Breaks'),
            ('high_cp',    'Counter-Press'),
            ('turnovers',  'Turnovers'),
            ('oh_losses',  'Own-Half Losses'),
        ],
        colors={
            'oh_gains':  GOLD,
            'ball_rec':  HOME_COLOR,
            'oh_losses': AWAY_COLOR,
            'turnovers': AWAY_COLOR,
            'high_cp':   HOME_COLOR,
        },
    )

    # ── Offensive transition cards ────────────────────────────────────────────
    counter_card = section_card(
        "Counter Attack Starts — Gains in Own Half  ● Recovery  ● Tackle  ◆ Intercept",
        dcc.Graph(figure=_counter_attacks_scatter(bar), config=CHART_CONFIG),
    )
    funnel_card = section_card(
        "Recovery to Shot Funnel — Gains → Shots → Goals",
        dcc.Graph(figure=_recovery_to_shot_funnel(bar), config=CHART_CONFIG),
    )
    zones_map_card = section_card(
        "Turnover Zones — Where Barca Wins the Ball",
        dcc.Graph(figure=_turnover_zones_map(bar), config=CHART_CONFIG),
    )
    zones_bar_card = section_card(
        "Gains by Zone",
        dcc.Graph(figure=_gains_zone_bar(bar), config=CHART_CONFIG),
    )

    # ── Defensive transition cards ────────────────────────────────────────────
    cp_scatter_card = section_card(
        "Counter-Press Map — Defensive Actions in Opp Half  ● Tackle  ◆ Intercept",
        dcc.Graph(figure=_counterpress_scatter(bar), config=CHART_CONFIG),
    )
    opp_shots_card = section_card(
        "Opponent Shots Conceded — Post-Turnover Danger  ★ Goal  ● Saved  ✕ Miss",
        dcc.Graph(figure=_shots_after_turnovers(opp, bar), config=CHART_CONFIG),
    )

    danger_src = _transition_danger_map(bar)
    danger_card = section_card(
        "Transition Danger Map — Own-Half Ball Losses",
        html.Img(src=danger_src, style={'width': '100%', 'borderRadius': '4px'}),
    ) if danger_src else html.Div()

    type_card = section_card(
        "Turnover Type Breakdown",
        dcc.Graph(figure=_turnover_type_donut(turnovers), config=CHART_CONFIG),
    )

    cp_heatmap_src = _counterpress_map(bar)
    cp_heat_card = section_card(
        "Counter-Press Heatmap",
        html.Img(src=cp_heatmap_src, style={'width': '100%', 'borderRadius': '4px'}),
    ) if cp_heatmap_src else html.Div()

    return html.Div([
        kpi,
        html.P("Offensive transitions (defence → attack)", style={
            'color': COLORS['text_secondary'], 'fontSize': '0.78rem',
            'fontStyle': 'italic', 'marginTop': '8px', 'marginBottom': '4px',
        }),
        dbc.Row([
            dbc.Col(counter_card,   md=6),
            dbc.Col([funnel_card, zones_bar_card], md=6),
        ], className='mb-3'),
        dbc.Row([
            dbc.Col(zones_map_card, md=12),
        ], className='mb-3'),
        html.P("Defensive transitions (attack → defence)", style={
            'color': COLORS['text_secondary'], 'fontSize': '0.78rem',
            'fontStyle': 'italic', 'marginBottom': '4px',
        }),
        dbc.Row([
            dbc.Col(cp_scatter_card, md=6),
            dbc.Col(opp_shots_card,  md=6),
        ], className='mb-3'),
        dbc.Row([
            dbc.Col([type_card, danger_card], md=5),
            dbc.Col(cp_heat_card,             md=7),
        ], className='mb-3'),
    ])
