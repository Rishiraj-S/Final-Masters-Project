"""
Team Analysis — Tab 3: Defensive Structure

Layout (filter + content):
  Filter panel (md=3) | Main content (md=9)

Main content:
  KPI bar (full width) →
  Row: Def Action Map + Heatmap + Fouls/Offsides (md=8) | Top Defenders table (md=4)

Filters: player, action type, half-time sliders.
Skeleton + callback pattern, same as buildup.py and chance_creation.py.
"""

import pandas as pd
import plotly.graph_objects as go
from dash import html, dcc, Input, Output, State
import dash_bootstrap_components as dbc

from utils.config import COLORS
from utils.data_utils import get_all_events, CURRENT_SEASON
from page_utils import PassMap, GOLD, HOME_COLOR, AWAY_COLOR
from page_utils.competitions import normalize_competitions as _normalize_competitions
from page_utils.visualizations import (
    add_pitch_background,
    PITCH_AXIS_FULL,
    render_lsc_heatmap_img,
)


# =============================================================================
# Constants
# =============================================================================

PITCH_BG = '#151932'

_DEF_ACTION_TYPES = ['Tackle', 'Interception', 'Ball Recovery', 'Clearance', 'Blocked Shot']

_DEF_COLORS = {
    'Tackle':        '#4dabf7',
    'Interception':  '#51cf66',
    'Ball Recovery': '#ffd43b',
    'Clearance':     '#ff922b',
    'Blocked Shot':  '#cc5de8',
}
_DEF_SYMBOLS = {
    'Tackle':        'circle',
    'Interception':  'diamond',
    'Ball Recovery': 'square',
    'Clearance':     'triangle-up',
    'Blocked Shot':  'x',
}

_LABEL_STYLE = {
    'color': GOLD,
    'fontSize': '0.70rem',
    'fontWeight': '700',
    'letterSpacing': '0.8px',
    'textTransform': 'uppercase',
    'marginBottom': '5px',
    'marginTop': '14px',
}
_PANEL_STYLE = {
    'backgroundColor': COLORS['dark_secondary'],
    'border': f'1px solid {COLORS["dark_border"]}',
    'borderRadius': '6px',
    'padding': '14px 12px',
    'overflowY': 'auto',
    'maxHeight': '80vh',
}
_SECTION_TITLE = {
    'color': GOLD,
    'fontWeight': '700',
    'fontSize': '0.82rem',
    'letterSpacing': '1px',
    'textTransform': 'uppercase',
    'paddingBottom': '8px',
    'borderBottom': f'1px solid {COLORS["dark_border"]}',
}
_TH = {
    'textAlign': 'center', 'padding': '4px 6px',
    'fontSize': '0.58rem', 'fontWeight': '700',
    'color': COLORS['text_secondary'], 'textTransform': 'uppercase',
    'letterSpacing': '0.05em', 'whiteSpace': 'nowrap',
    'borderBottom': f'1px solid {COLORS["dark_border"]}',
}
_TD = {
    'textAlign': 'center', 'padding': '4px 6px',
    'fontSize': '0.68rem', 'fontWeight': '600',
    'color': COLORS['text_primary'], 'whiteSpace': 'nowrap',
}
_NAME = {**_TD, 'textAlign': 'left', 'color': GOLD,
         'maxWidth': '90px', 'overflow': 'hidden', 'textOverflow': 'ellipsis'}

CHART_CFG = {'displayModeBar': False}


# =============================================================================
# Skeleton
# =============================================================================

def _skel_fig(height: int = 480) -> go.Figure:
    fig = go.Figure()
    fig.update_layout(
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor=PITCH_BG,
        height=height, margin=dict(l=0, r=0, t=36, b=0),
    )
    return fig


# =============================================================================
# Data helpers
# =============================================================================

def _apply_filters(da: pd.DataFrame, *, action_types, players, outcomes,
                   h1_range, h2_range) -> pd.DataFrame:
    if action_types:
        da = da[da['event_type'].isin(action_types)]

    if outcomes is not None and len(outcomes) < 2 and 'outcome' in da.columns:
        if 'success' in outcomes:
            da = da[da['outcome'] == 1]
        elif 'fail' in outcomes:
            da = da[da['outcome'] != 1]
        elif not outcomes:
            return da.iloc[:0]

    if players and 'player_name' in da.columns:
        da = da[da['player_name'].isin(players)]

    if 'period_id' in da.columns and 'time_min' in da.columns:
        h1_lo, h1_hi = h1_range
        h2_lo, h2_hi = h2_range
        m1 = (da['period_id'] == 1) & (da['time_min'] >= h1_lo) & (da['time_min'] <= h1_hi)
        m2 = (da['period_id'] == 2) & (da['time_min'] >= h2_lo) & (da['time_min'] <= h2_hi)
        da = da[m1 | m2]

    return da


def _ppda(bar: pd.DataFrame, events: pd.DataFrame) -> float:
    opp   = events[events['team_code'] != 'BAR']
    opp_p = opp[(opp['event_type'] == 'Pass') & opp['x'].notna() & (opp['x'].astype(float) < 40)]
    bar_pr = bar[
        bar['event_type'].isin(['Tackle', 'Interception']) &
        bar['x'].notna() & (bar['x'].astype(float) > 50)
    ]
    return round(len(opp_p) / max(len(bar_pr), 1), 1)


# =============================================================================
# KPI bar
# =============================================================================

def _kpi_children(bar: pd.DataFrame, events: pd.DataFrame) -> list:
    def _card(value, label, color=COLORS['text_primary']):
        return html.Div([
            html.Div(str(value), style={
                'color': color, 'fontWeight': '800',
                'fontSize': '1.35rem', 'lineHeight': '1.1',
            }),
            html.Div(label, style={
                'color': COLORS['text_secondary'],
                'fontSize': '0.60rem', 'fontWeight': '600',
                'letterSpacing': '0.6px',
                'textTransform': 'uppercase',
                'marginTop': '3px',
            }),
        ], style={
            'backgroundColor': COLORS['dark_secondary'],
            'border': f'1px solid {COLORS["dark_border"]}',
            'borderRadius': '6px',
            'padding': '8px 10px',
            'flex': '1',
            'minWidth': '0',
        })

    da = bar[bar['event_type'].isin(_DEF_ACTION_TYPES)]

    tackles     = int((bar['event_type'] == 'Tackle').sum())
    intercepts  = int((bar['event_type'] == 'Interception').sum())
    clearances  = int((bar['event_type'] == 'Clearance').sum())
    recoveries  = int((bar['event_type'] == 'Ball Recovery').sum())
    blocked     = int((bar['event_type'] == 'Blocked Shot').sum())

    aerials     = bar[bar['event_type'] == 'Aerial']
    aerial_wins = int(aerials[aerials['outcome'] == 1].shape[0]) if 'outcome' in aerials.columns else 0

    def_press   = da[da['x'].notna() & (da['x'].astype(float) > 50)]
    press_pct   = round(len(def_press) / max(len(da), 1) * 100, 1)

    fouls = int((bar['event_type'] == 'Foul').shape[0])

    ppda_val = _ppda(bar, events)

    cards = [
        _card(ppda_val,           'PPDA',         AWAY_COLOR),
        _card(tackles,            'Tackles',       HOME_COLOR),
        _card(intercepts,         'Interceptions', GOLD),
        _card(clearances,         'Clearances',    COLORS['text_primary']),
        _card(recoveries,         'Recoveries',    HOME_COLOR),
        _card(blocked,            'Blocks',        COLORS['text_primary']),
        _card(aerial_wins,        'Aerial Wins',   GOLD),
        _card(f'{press_pct}%',    'High Press',    AWAY_COLOR),
        _card(fouls,              'Fouls',         COLORS['text_primary']),
    ]
    return [html.Div(cards, style={'display': 'flex', 'gap': '6px', 'flexWrap': 'wrap'})]


# =============================================================================
# Defensive action map
# =============================================================================

def _action_map_fig(da: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    add_pitch_background(fig, half=False)

    if not da.empty and 'x' in da.columns:
        for etype in _DEF_ACTION_TYPES:
            grp = da[da['event_type'] == etype].dropna(subset=['x', 'y'])
            if grp.empty:
                continue

            player = (grp['player_name'].fillna('Unknown').tolist()
                      if 'player_name' in grp.columns else ['Unknown'] * len(grp))
            mins   = (grp['time_min'].fillna(0).astype(int).tolist()
                      if 'time_min' in grp.columns else [0] * len(grp))

            fig.add_trace(go.Scatter(
                x=grp['x'].tolist(), y=grp['y'].tolist(),
                mode='markers', name=etype,
                marker=dict(
                    color=_DEF_COLORS.get(etype, GOLD),
                    symbol=_DEF_SYMBOLS.get(etype, 'circle'),
                    size=8, opacity=0.80,
                    line=dict(color='white', width=0.7),
                ),
                customdata=list(zip(player, mins)),
                hovertemplate=(
                    '<b>%{customdata[0]}</b><br>'
                    "%{customdata[1]}'"
                    '<extra>' + etype + '</extra>'
                ),
            ))

    fig.update_layout(
        **PITCH_AXIS_FULL,
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor=PITCH_BG,
        height=480, margin=dict(l=0, r=115, t=8, b=0),
        hoverlabel=dict(bgcolor='#1A1D2E', font_color='white', font_size=12),
        legend=dict(
            x=1.01, y=1.0, xanchor='left', yanchor='top',
            orientation='v',
            font=dict(color=COLORS['text_primary'], size=10),
            bgcolor='rgba(26,29,46,0.80)',
            bordercolor=COLORS.get('dark_border', 'rgba(255,255,255,0.15)'),
            borderwidth=1,
        ),
    )
    return fig


# =============================================================================
# Defensive heatmap
# =============================================================================

def _heatmap_src(da: pd.DataFrame) -> str:
    coords = da.dropna(subset=['x', 'y'])
    if len(coords) < 2:
        return ''
    return render_lsc_heatmap_img(
        coords['x'].values, coords['y'].values,
        color_hex=AWAY_COLOR, half=False,
    )


# =============================================================================
# Fouls & offsides map
# =============================================================================

def _fouls_offsides_fig(bar: pd.DataFrame, events: pd.DataFrame,
                        h1_range, h2_range) -> go.Figure:
    fig = go.Figure()
    add_pitch_background(fig, half=False)

    h1_lo, h1_hi = h1_range
    h2_lo, h2_hi = h2_range

    def _time_filter(df):
        if 'period_id' not in df.columns or 'time_min' not in df.columns:
            return df
        m1 = (df['period_id'] == 1) & (df['time_min'] >= h1_lo) & (df['time_min'] <= h1_hi)
        m2 = (df['period_id'] == 2) & (df['time_min'] >= h2_lo) & (df['time_min'] <= h2_hi)
        return df[m1 | m2]

    # Fouls committed by BAR
    fouls = _time_filter(bar[bar['event_type'] == 'Foul'].copy()).dropna(subset=['x', 'y'])
    if not fouls.empty:
        player = (fouls['player_name'].fillna('Unknown').tolist()
                  if 'player_name' in fouls.columns else ['Unknown'] * len(fouls))
        mins   = (fouls['time_min'].fillna(0).astype(int).tolist()
                  if 'time_min' in fouls.columns else [0] * len(fouls))
        fig.add_trace(go.Scatter(
            x=fouls['x'].tolist(), y=fouls['y'].tolist(),
            mode='markers', name='Foul',
            marker=dict(color='#ff6b6b', symbol='x', size=10, opacity=0.85,
                        line=dict(color='white', width=1)),
            customdata=list(zip(player, mins)),
            hovertemplate=(
                '<b>%{customdata[0]}</b><br>'
                "%{customdata[1]}'"
                '<extra>Foul</extra>'
            ),
        ))

    # Offsides caught by BAR = opponent's Offside Pass events
    # (opponent played the ball; their player was caught offside by BAR's defensive line)
    opp = events[events['team_code'] != 'BAR']
    offsides = _time_filter(
        opp[opp['event_type'] == 'Offside Pass'].copy()
    ).dropna(subset=['x', 'y'])
    if not offsides.empty:
        player = (offsides['player_name'].fillna('Unknown').tolist()
                  if 'player_name' in offsides.columns else ['Unknown'] * len(offsides))
        mins   = (offsides['time_min'].fillna(0).astype(int).tolist()
                  if 'time_min' in offsides.columns else [0] * len(offsides))
        fig.add_trace(go.Scatter(
            x=offsides['x'].tolist(), y=offsides['y'].tolist(),
            mode='markers', name='Offside',
            marker=dict(color='#ffd43b', symbol='triangle-up', size=10, opacity=0.85,
                        line=dict(color='white', width=1)),
            customdata=list(zip(player, mins)),
            hovertemplate=(
                '<b>%{customdata[0]}</b><br>'
                "%{customdata[1]}'"
                '<extra>Offside</extra>'
            ),
        ))

    fig.update_layout(
        **PITCH_AXIS_FULL,
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor=PITCH_BG,
        height=480, margin=dict(l=0, r=0, t=8, b=0),
        hoverlabel=dict(bgcolor='#1A1D2E', font_color='white', font_size=12),
        legend=dict(
            x=0.01, y=0.01, xanchor='left', yanchor='bottom',
            orientation='v',
            font=dict(color=COLORS['text_primary'], size=10),
            bgcolor='rgba(26,29,46,0.80)',
            bordercolor=COLORS.get('dark_border', 'rgba(255,255,255,0.15)'),
            borderwidth=1,
        ),
    )
    return fig


# =============================================================================
# Top defenders table
# =============================================================================

def _defenders_table_children(bar: pd.DataFrame, top_n: int = 10) -> list:
    _no_data = [html.P("No data", style={
        'color': COLORS['text_secondary'], 'fontSize': '0.75rem', 'textAlign': 'center',
    })]

    types = ['Tackle', 'Interception', 'Clearance', 'Ball Recovery', 'Blocked Shot']
    da = bar[bar['event_type'].isin(types)]
    if da.empty or 'player_name' not in da.columns:
        return _no_data

    rows_data = []
    for player, grp in da.groupby('player_name'):
        t   = int((grp['event_type'] == 'Tackle').sum())
        i   = int((grp['event_type'] == 'Interception').sum())
        cl  = int((grp['event_type'] == 'Clearance').sum())
        br  = int((grp['event_type'] == 'Ball Recovery').sum())
        bl  = int((grp['event_type'] == 'Blocked Shot').sum())
        tot = t + i + cl + br + bl
        rows_data.append({'player': player, 't': t, 'i': i, 'cl': cl,
                          'br': br, 'bl': bl, 'tot': tot})

    rows_data.sort(key=lambda x: x['tot'], reverse=True)
    rows_data = rows_data[:top_n]

    if not rows_data:
        return _no_data

    header = html.Tr([
        html.Th('Player', style={**_TH, 'textAlign': 'left'}),
        html.Th('Tk',     style=_TH),
        html.Th('Int',    style=_TH),
        html.Th('Clr',    style=_TH),
        html.Th('Rec',    style=_TH),
        html.Th('Blk',    style=_TH),
        html.Th('Tot',    style=_TH),
    ])
    table_rows = []
    for idx, s in enumerate(rows_data):
        bg = (COLORS.get('dark_tertiary', 'rgba(255,255,255,0.03)')
              if idx % 2 == 0 else 'transparent')
        short = s['player'].split()[-1] if s['player'] else '—'
        table_rows.append(html.Tr([
            html.Td(short,        style=_NAME),
            html.Td(str(s['t']),  style={**_TD, 'color': _DEF_COLORS['Tackle']}),
            html.Td(str(s['i']),  style={**_TD, 'color': _DEF_COLORS['Interception']}),
            html.Td(str(s['cl']), style=_TD),
            html.Td(str(s['br']), style=_TD),
            html.Td(str(s['bl']), style=_TD),
            html.Td(str(s['tot']), style={**_TD, 'color': GOLD, 'fontWeight': '700'}),
        ], style={'backgroundColor': bg}))

    return [html.Div(
        html.Table([html.Thead(header), html.Tbody(table_rows)],
                   style={'width': '100%', 'borderCollapse': 'collapse'}),
        style={'overflowX': 'auto'},
    )]


# =============================================================================
# Filter panel
# =============================================================================

def _filter_panel(player_options=None) -> html.Div:
    return html.Div([
        html.Div("Filters", style=_SECTION_TITLE),

        html.Div("Player", style=_LABEL_STYLE),
        dcc.Dropdown(
            id='ds-player-filter',
            options=player_options or [],
            value=None,
            multi=True,
            placeholder="All players…",
            style={'fontSize': '0.75rem'},
        ),

        html.Hr(style={'borderColor': COLORS['dark_border'], 'margin': '10px 0 4px'}),
        html.Div("Action Type", style=_LABEL_STYLE),
        dcc.Checklist(
            id='ds-action-type',
            options=[
                {'label': ' Tackle',        'value': 'Tackle'},
                {'label': ' Interception',  'value': 'Interception'},
                {'label': ' Ball Recovery', 'value': 'Ball Recovery'},
                {'label': ' Clearance',     'value': 'Clearance'},
                {'label': ' Blocked Shot',  'value': 'Blocked Shot'},
            ],
            value=_DEF_ACTION_TYPES,
            inputStyle={'cursor': 'pointer', 'accentColor': GOLD},
            labelStyle={'color': COLORS['text_secondary'], 'fontSize': '0.75rem',
                        'display': 'block', 'marginBottom': '4px'},
        ),

        html.Hr(style={'borderColor': COLORS['dark_border'], 'margin': '10px 0 4px'}),
        html.Div("Outcome", style=_LABEL_STYLE),
        dcc.Checklist(
            id='ds-outcome-filter',
            options=[
                {'label': ' Successful',   'value': 'success'},
                {'label': ' Unsuccessful', 'value': 'fail'},
            ],
            value=['success', 'fail'],
            inline=True,
            inputStyle={'cursor': 'pointer', 'accentColor': GOLD, 'marginRight': '4px'},
            labelStyle={'color': COLORS['text_secondary'], 'fontSize': '0.75rem',
                        'marginRight': '10px'},
        ),

        *PassMap.dash_controls(show=['h1_time', 'h2_time'], id_prefix='ds'),
    ], style=_PANEL_STYLE)


# =============================================================================
# Public builder
# =============================================================================

def build_def_structure_tab(season, competitions, match_ids=None) -> html.Div:
    """Skeleton layout — all data filled by register_def_structure_callbacks."""
    events = get_all_events(season)
    if events.empty:
        return html.P("No data available.", style={'color': COLORS['text_secondary']})

    if competitions and 'competition' in events.columns:
        events = events[events['competition'].isin(competitions)]
    if match_ids:
        events = events[events['match_id'].isin(match_ids)]

    bar = events[events['team_code'] == 'BAR']
    if bar.empty:
        return html.P("No Barcelona event data.", style={'color': COLORS['text_secondary']})

    # Player options seeded from all available defensive actions
    da = bar[bar['event_type'].isin(_DEF_ACTION_TYPES)]
    player_opts = []
    if 'player_name' in da.columns:
        names = da['player_name'].dropna().unique()
        player_opts = sorted([{'label': n, 'value': n} for n in names],
                             key=lambda d: d['label'])

    main_content = html.Div([
        # KPI bar — full width
        html.Div(id='ds-kpi-bar', children=[]),
        html.Hr(style={'borderColor': COLORS['dark_border'], 'margin': '10px 0 14px'}),

        # Maps (md=8) | Defenders table (md=4)
        dbc.Row([
            dbc.Col([
                # ── Defensive Actions Map ──────────────────────────────────
                html.Div("Defensive Actions Map", style=_SECTION_TITLE),
                dcc.Loading(
                    type='circle', color=GOLD,
                    children=dcc.Graph(
                        id='ds-action-map',
                        figure=_skel_fig(480),
                        config=CHART_CFG,
                        style={'width': '100%'},
                    ),
                ),

                html.Hr(style={'borderColor': COLORS['dark_border'], 'margin': '14px 0 10px'}),

                # ── Defensive Heatmap ──────────────────────────────────────
                html.Div("Defensive Actions Heatmap", style=_SECTION_TITLE),
                html.Div(
                    "Density of tackles, interceptions and ball recoveries",
                    style={'color': COLORS['text_secondary'], 'fontSize': '0.62rem',
                           'fontStyle': 'italic', 'marginBottom': '8px'},
                ),
                dcc.Loading(
                    type='circle', color=GOLD,
                    children=html.Img(
                        id='ds-heatmap-img',
                        src='',
                        style={'width': '100%', 'borderRadius': '6px',
                               'minHeight': '200px'},
                    ),
                ),

                html.Hr(style={'borderColor': COLORS['dark_border'], 'margin': '14px 0 10px'}),

                # ── Fouls & Offsides ───────────────────────────────────────
                html.Div("Fouls & Offsides", style=_SECTION_TITLE),
                dcc.Loading(
                    type='circle', color=GOLD,
                    children=dcc.Graph(
                        id='ds-fouls-map',
                        figure=_skel_fig(480),
                        config=CHART_CFG,
                        style={'width': '100%'},
                    ),
                ),
            ], md=8),

            dbc.Col([
                html.Div("Top Defenders", style={**_SECTION_TITLE, 'fontSize': '0.75rem'}),
                html.Div(style={'marginBottom': '6px'}),
                html.Div(id='ds-defenders-table', children=[]),
            ], md=4, style={
                'borderLeft': f'1px solid {COLORS["dark_border"]}',
                'paddingLeft': '14px',
            }),
        ], align='start', className='g-0'),
    ], style=_PANEL_STYLE)

    return html.Div(
        dbc.Row([
            dbc.Col(_filter_panel(player_opts), md=3),
            dbc.Col(main_content,               md=9),
        ], align='start', className='g-3'),
    )


# =============================================================================
# Callbacks
# =============================================================================

def register_def_structure_callbacks(app) -> None:
    """Wire filter controls to the action map, heatmap, fouls map, and table."""

    @app.callback(
        Output('ds-kpi-bar',          'children'),
        Output('ds-action-map',       'figure'),
        Output('ds-heatmap-img',      'src'),
        Output('ds-fouls-map',        'figure'),
        Output('ds-defenders-table',  'children'),
        Input('ds-player-filter',    'value'),
        Input('ds-action-type',      'value'),
        Input('ds-outcome-filter',   'value'),
        Input('ds-h1-time',          'value'),
        Input('ds-h2-time',          'value'),
        State('ta-competition-selector', 'value'),
        State('ta-venue-selector',       'value'),
        State('ta-selected-matches',     'data'),
        State('ta-match-data',           'data'),
    )
    def _update(players, action_types, outcomes, h1_range, h2_range,
                competition, venue, match_ids, match_data):

        def _empty():
            return [], _skel_fig(480), '', _skel_fig(480), []

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

        _h1 = tuple(h1_range) if h1_range else (0, 50)
        _h2 = tuple(h2_range) if h2_range else (45, 100)
        _types = action_types if action_types else _DEF_ACTION_TYPES

        # KPI always uses all actions (no action-type filter so values are stable)
        kpi = _kpi_children(bar, events)

        # Filtered defensive actions for map + heatmap
        da_all = bar[bar['event_type'].isin(_DEF_ACTION_TYPES)].copy()
        da_filtered = _apply_filters(
            da_all,
            action_types=_types,
            players=players or None,
            outcomes=outcomes if outcomes is not None else ['success', 'fail'],
            h1_range=_h1, h2_range=_h2,
        )

        action_fig  = _action_map_fig(da_filtered)
        heatmap_src = _heatmap_src(da_filtered)
        fouls_fig   = _fouls_offsides_fig(bar, events, _h1, _h2)

        # Defenders table uses player filter only (all action types, full time range)
        da_for_table = bar[bar['event_type'].isin(_DEF_ACTION_TYPES)].copy()
        if players and 'player_name' in da_for_table.columns:
            da_for_table = da_for_table[da_for_table['player_name'].isin(players)]

        defenders = _defenders_table_children(da_for_table)

        return kpi, action_fig, heatmap_src, fouls_fig, defenders
