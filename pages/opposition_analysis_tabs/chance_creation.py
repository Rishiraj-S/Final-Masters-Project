"""
Opposition Analysis — Chance Creation (Shot Map)

Skeleton + callback pattern. All data loaded via load_opp_events() in the callback.
ID prefix: occ-

Public API:
  build_chance_creation(team, comp_key)  → html.Div  (skeleton, immediate return)
  register_chance_creation_callbacks(app)            (wires occ- controls)
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from dash import html, dcc, Input, Output, State
import dash_bootstrap_components as dbc

from utils.config import COLORS
from utils.opposition_data_utils import load_opp_events, SEASON
from utils.xg_utils import add_xg_column
from page_utils import PassMap, GOLD, HOME_COLOR
from page_utils.visualizations import (
    add_vertical_half_pitch_background,
    VPITCH_AXIS_HALF,
    PITCH_BG,
)
from page_utils.event_filters import SHOT_TYPES as _SHOT_TYPES


# =============================================================================
# Constants
# =============================================================================

_OUTCOME_COLOR = {
    'Goal':         '#51cf66',
    'Saved Shot':   '#339af0',
    'Miss':         '#ff6b6b',
    'Post':         '#ffd43b',
    'Blocked Shot': '#cc5de8',
}
_OUTCOME_SYMBOL = {
    'Goal':         'star',
    'Saved Shot':   'circle',
    'Miss':         'x',
    'Post':         'diamond',
    'Blocked Shot': 'square',
}

_LABEL_STYLE = {
    'color': GOLD, 'fontSize': '0.70rem', 'fontWeight': '700',
    'letterSpacing': '0.8px', 'textTransform': 'uppercase',
    'marginBottom': '5px', 'marginTop': '14px',
}
_PANEL_STYLE = {
    'backgroundColor': COLORS['dark_secondary'],
    'border': f'1px solid {COLORS["dark_border"]}',
    'borderRadius': '6px', 'padding': '14px 12px',
    'overflowY': 'auto', 'maxHeight': '80vh',
}
_SECTION_TITLE = {
    'color': GOLD, 'fontWeight': '700', 'fontSize': '0.82rem',
    'letterSpacing': '1px', 'textTransform': 'uppercase',
    'paddingBottom': '8px', 'borderBottom': f'1px solid {COLORS["dark_border"]}',
}
_TH = {
    'textAlign': 'center', 'padding': '4px 6px',
    'fontSize': '0.58rem', 'fontWeight': '700',
    'color': COLORS['text_secondary'], 'textTransform': 'uppercase',
    'letterSpacing': '0.05em', 'whiteSpace': 'nowrap',
    'borderBottom': f'1px solid {COLORS["dark_border"]}',
}
_TH_NOCASE = {**_TH, 'textTransform': 'none', 'letterSpacing': '0'}
_TD = {
    'textAlign': 'center', 'padding': '4px 6px',
    'fontSize': '0.68rem', 'fontWeight': '600',
    'color': COLORS['text_primary'], 'whiteSpace': 'nowrap',
}
_NAME_TD = {
    **_TD, 'textAlign': 'left', 'color': GOLD,
    'maxWidth': '90px', 'overflow': 'hidden', 'textOverflow': 'ellipsis',
}

CHART_CFG = {'displayModeBar': False}


# =============================================================================
# Skeleton figure
# =============================================================================

def _skel_fig(height: int = 520) -> go.Figure:
    fig = go.Figure()
    fig.update_layout(
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor=PITCH_BG,
        height=height, margin=dict(l=0, r=0, t=36, b=0),
    )
    return fig


# =============================================================================
# Data helpers
# =============================================================================

def _get_shots(opp_ev: pd.DataFrame) -> pd.DataFrame:
    shots = opp_ev[opp_ev['event_type'].isin(_SHOT_TYPES)].copy()
    shots = shots.dropna(subset=['x', 'y'])
    if shots.empty:
        return shots
    return add_xg_column(shots)


def _apply_shot_filters(shots, *, outcomes, bands, players,
                        h1_range, h2_range) -> pd.DataFrame:
    if outcomes:
        shots = shots[shots['event_type'].isin(outcomes)]
    if bands and len(bands) < 3 and 'y' in shots.columns:
        y    = pd.to_numeric(shots['y'], errors='coerce')
        mask = pd.Series(False, index=shots.index)
        if 'left'   in bands: mask |= y > 66.67
        if 'centre' in bands: mask |= (y >= 33.33) & (y <= 66.67)
        if 'right'  in bands: mask |= y < 33.33
        shots = shots[mask]
    if players and 'player_name' in shots.columns:
        shots = shots[shots['player_name'].isin(players)]
    if 'period_id' in shots.columns and 'time_min' in shots.columns:
        h1_lo, h1_hi = h1_range
        h2_lo, h2_hi = h2_range
        m1 = (shots['period_id'] == 1) & (shots['time_min'] >= h1_lo) & (shots['time_min'] <= h1_hi)
        m2 = (shots['period_id'] == 2) & (shots['time_min'] >= h2_lo) & (shots['time_min'] <= h2_hi)
        shots = shots[m1 | m2]
    return shots


# =============================================================================
# Chart builders
# =============================================================================

def _shot_map_fig(shots: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    add_vertical_half_pitch_background(fig)

    _base = dict(
        **VPITCH_AXIS_HALF,
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor=PITCH_BG,
        height=520, margin=dict(l=0, r=0, t=8, b=0),
        hoverlabel=dict(bgcolor='#1A1D2E', font_color='white', font_size=12),
        legend=dict(
            x=0.01, y=0.01, xanchor='left', yanchor='bottom',
            orientation='v', font=dict(color=COLORS['text_primary'], size=10),
            bgcolor='rgba(26,29,46,0.80)',
            bordercolor=COLORS.get('dark_border', 'rgba(255,255,255,0.15)'),
            borderwidth=1,
        ),
    )

    if not shots.empty:
        for etype in _SHOT_TYPES:
            grp = shots[shots['event_type'] == etype]
            if grp.empty:
                continue
            xg_vals = (grp['xg'].fillna(0.05) if 'xg' in grp.columns
                       else pd.Series(0.05, index=grp.index))
            sizes   = (xg_vals * 120 + 12).clip(upper=50)
            mins    = (grp['time_min'].fillna('?').astype(str)
                       if 'time_min' in grp.columns
                       else pd.Series('?', index=grp.index))
            names   = (grp['player_name'].fillna('Unknown')
                       if 'player_name' in grp.columns
                       else pd.Series('Unknown', index=grp.index))
            xg_disp = xg_vals.round(3).astype(str)

            # Opta: x = distance from own goal, y = pitch width
            # Vertical half-pitch: fig_x = 100-y, fig_y = x
            fig.add_trace(go.Scatter(
                x=(100 - grp['y']).tolist(),
                y=grp['x'].tolist(),
                mode='markers',
                name=etype,
                marker=dict(
                    color=_OUTCOME_COLOR.get(etype, '#888'),
                    symbol=_OUTCOME_SYMBOL.get(etype, 'circle'),
                    size=sizes.tolist(),
                    opacity=0.85,
                    line=dict(color='white', width=1),
                ),
                customdata=list(zip(names, mins, xg_disp)),
                hovertemplate=(
                    f'<b>{etype}</b><br>'
                    'Player: %{customdata[0]}<br>'
                    "Min: %{customdata[1]}'<br>"
                    'xG: %{customdata[2]}<extra></extra>'
                ),
            ))

    fig.update_layout(**_base, uirevision='occ-shot-map')
    return fig


def _kpi_children(shots: pd.DataFrame) -> list:
    def _card(value, label, color=COLORS['text_primary'], preserve_case=False):
        return html.Div([
            html.Div(str(value), style={
                'color': color, 'fontWeight': '800',
                'fontSize': '1.35rem', 'lineHeight': '1.1',
            }),
            html.Div(label, style={
                'color': COLORS['text_secondary'], 'fontSize': '0.60rem',
                'fontWeight': '600',
                'letterSpacing': '0' if preserve_case else '0.6px',
                'textTransform': 'none' if preserve_case else 'uppercase',
                'marginTop': '3px',
            }),
        ], style={
            'backgroundColor': COLORS['dark_secondary'],
            'border': f'1px solid {COLORS["dark_border"]}',
            'borderRadius': '6px', 'padding': '8px 10px',
            'flex': '1', 'minWidth': '0',
        })

    total_shots = len(shots)
    shots_ot    = int(shots['event_type'].isin(['Goal', 'Saved Shot']).sum()) if not shots.empty else 0
    goals       = int((shots['event_type'] == 'Goal').sum()) if not shots.empty else 0
    xg_total    = round(shots['xg'].sum(), 2) if not shots.empty and 'xg' in shots.columns else 0.0
    box_shots   = int((shots['x'] >= 83).sum()) if not shots.empty and 'x' in shots.columns else 0
    big_chances = (
        int(shots['Big Chance'].eq('Si').sum())
        if not shots.empty and 'Big Chance' in shots.columns else 0
    )

    return [html.Div([
        _card(total_shots,        'Shots',       COLORS['text_primary']),
        _card(shots_ot,           'On Target',   HOME_COLOR),
        _card(goals,              'Goals',        GOLD),
        _card(f'{xg_total:.2f}',  'xG',          HOME_COLOR, preserve_case=True),
        _card(box_shots,          'Box Shots',   COLORS['text_primary']),
        _card(big_chances,        'Big Chances', GOLD),
    ], style={'display': 'flex', 'gap': '6px', 'flexWrap': 'wrap'})]


def _scorers_table_children(shots: pd.DataFrame, top_n: int = 10) -> list:
    _no_data = [html.P("No data", style={
        'color': COLORS['text_secondary'], 'fontSize': '0.75rem', 'textAlign': 'center',
    })]
    if shots.empty or 'player_name' not in shots.columns:
        return _no_data

    rows_data = []
    for player, grp in shots.groupby('player_name'):
        g  = int((grp['event_type'] == 'Goal').sum())
        sh = len(grp)
        xg = round(grp['xg'].sum(), 2) if 'xg' in grp.columns else 0.0
        rows_data.append({'player': player, 'g': g, 'sh': sh, 'xg': xg})

    rows_data.sort(key=lambda x: (x['g'], x['xg']), reverse=True)
    rows_data = rows_data[:top_n]

    if not rows_data:
        return _no_data

    header = html.Tr([
        html.Th('Player', style={**_TH, 'textAlign': 'left'}),
        html.Th('G',   style=_TH),
        html.Th('Sh',  style=_TH),
        html.Th('xG',  style=_TH_NOCASE),
    ])
    table_rows = []
    for i, s in enumerate(rows_data):
        bg    = (COLORS.get('dark_tertiary', 'rgba(255,255,255,0.03)')
                 if i % 2 == 0 else 'transparent')
        short = s['player'].split()[-1] if s['player'] else '—'
        table_rows.append(html.Tr([
            html.Td(short,              style=_NAME_TD),
            html.Td(str(s['g']),        style={**_TD, 'color': GOLD, 'fontWeight': '800'}),
            html.Td(str(s['sh']),       style=_TD),
            html.Td(f"{s['xg']:.2f}",   style={**_TD, 'color': HOME_COLOR}),
        ], style={'backgroundColor': bg}))

    return [html.Div(
        html.Table([html.Thead(header), html.Tbody(table_rows)],
                   style={'width': '100%', 'borderCollapse': 'collapse'}),
        style={'overflowX': 'auto'},
    )]


# =============================================================================
# Public builder
# =============================================================================

def build_chance_creation(team: str | None = None,
                          comp_key: str | None = None) -> html.Div:
    """Return the Chance Creation tab skeleton. Callback populates all charts."""
    player_opts = []
    if team and comp_key:
        opp_ev, _ = load_opp_events(team, comp_key, 'all', None, None, SEASON)
        if not opp_ev.empty and 'event_type' in opp_ev.columns:
            shots = opp_ev[opp_ev['event_type'].isin(_SHOT_TYPES)]
            if 'player_name' in shots.columns:
                names       = shots['player_name'].dropna().unique()
                player_opts = sorted([{'label': n, 'value': n} for n in names],
                                     key=lambda d: d['label'])

    filter_panel = html.Div([
        html.Div("Filters", style=_SECTION_TITLE),
        html.Div("Player", style=_LABEL_STYLE),
        dcc.Dropdown(
            id='occ-player-filter', options=player_opts, value=None, multi=True,
            placeholder="All players…", style={'fontSize': '0.75rem'},
        ),
        html.Hr(style={'borderColor': COLORS['dark_border'], 'margin': '10px 0 4px'}),
        html.Div("Shot Outcome", style=_LABEL_STYLE),
        dcc.Checklist(
            id='occ-shot-outcome',
            options=[{'label': f' {t}', 'value': t} for t in _SHOT_TYPES],
            value=list(_SHOT_TYPES),
            inputStyle={'cursor': 'pointer', 'accentColor': GOLD},
            labelStyle={'color': COLORS['text_secondary'], 'fontSize': '0.75rem',
                        'display': 'block', 'marginBottom': '4px'},
        ),
        html.Hr(style={'borderColor': COLORS['dark_border'], 'margin': '10px 0 4px'}),
        html.Div("Band", style=_LABEL_STYLE),
        dcc.Checklist(
            id='occ-bands',
            options=[
                {'label': ' Left',   'value': 'left'},
                {'label': ' Centre', 'value': 'centre'},
                {'label': ' Right',  'value': 'right'},
            ],
            value=['left', 'centre', 'right'],
            inline=True,
            inputStyle={'cursor': 'pointer', 'accentColor': GOLD, 'marginRight': '4px'},
            labelStyle={'color': COLORS['text_secondary'], 'fontSize': '0.75rem',
                        'marginRight': '10px'},
        ),
        *PassMap.dash_controls(show=['h1_time', 'h2_time'], id_prefix='occ'),
    ], style=_PANEL_STYLE)

    main_content = html.Div([
        html.Div(id='occ-kpi-bar', children=[]),
        html.Hr(style={'borderColor': COLORS['dark_border'], 'margin': '10px 0 14px'}),
        dbc.Row([
            dbc.Col([
                html.Div("Shot Map", style=_SECTION_TITLE),
                html.Div(
                    "Dot size proportional to xG · star = goal · circle = saved · ✕ = miss",
                    style={'color': COLORS['text_secondary'], 'fontSize': '0.62rem',
                           'fontStyle': 'italic', 'marginBottom': '8px'},
                ),
                dcc.Loading(
                    type='circle', color=GOLD,
                    children=dcc.Graph(
                        id='occ-shot-map', figure=_skel_fig(520),
                        config=CHART_CFG, style={'width': '100%'},
                    ),
                ),
            ], md=8),
            dbc.Col([
                html.Div("Top Scorers",
                         style={**_SECTION_TITLE, 'fontSize': '0.75rem'}),
                html.Div(style={'marginBottom': '6px'}),
                html.Div(id='occ-scorers-table', children=[]),
            ], md=4, style={
                'borderLeft': f'1px solid {COLORS["dark_border"]}',
                'paddingLeft': '14px',
            }),
        ], align='start', className='g-0'),
    ], style=_PANEL_STYLE)

    return html.Div(
        dbc.Row([
            dbc.Col(filter_panel, md=2),
            dbc.Col(main_content, md=10),
        ], align='start', className='g-3'),
    )


# =============================================================================
# Callbacks
# =============================================================================

def register_chance_creation_callbacks(app) -> None:
    """Wire occ- filter controls to the shot map, KPI bar, and scorers table."""

    @app.callback(
        Output('occ-kpi-bar',        'children'),
        Output('occ-shot-map',       'figure'),
        Output('occ-scorers-table',  'children'),
        Input('occ-player-filter',   'value'),
        Input('occ-shot-outcome',    'value'),
        Input('occ-bands',           'value'),
        Input('occ-h1-time',         'value'),
        Input('occ-h2-time',         'value'),
        State('oa-team-select',      'value'),
        State('oa-comp-select',      'value'),
        State('oa-venue-filter',     'value'),
        State('oa-selected-matches', 'data'),
        State('oa-date-filter',      'date'),
    )
    def _update_chance_creation(players, outcomes, bands, h1_range, h2_range,
                                team, comp, venue, match_ids, date_cutoff):

        def _empty():
            return [], _skel_fig(520), []

        if not team or not comp:
            return _empty()

        opp_ev, _ = load_opp_events(team, comp, venue or 'all',
                                    match_ids or None, date_cutoff, SEASON)
        if opp_ev.empty:
            return _empty()

        _h1 = tuple(h1_range) if h1_range else (0, 50)
        _h2 = tuple(h2_range) if h2_range else (45, 100)

        all_shots = _get_shots(opp_ev)
        if all_shots.empty:
            return _empty()

        map_shots = _apply_shot_filters(
            all_shots.copy(),
            outcomes=outcomes or _SHOT_TYPES,
            bands=bands       or ['left', 'centre', 'right'],
            players=players   or None,
            h1_range=_h1, h2_range=_h2,
        )

        return (
            _kpi_children(map_shots),
            _shot_map_fig(map_shots),
            _scorers_table_children(map_shots),
        )
