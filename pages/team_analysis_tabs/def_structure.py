"""
Team Analysis — Tab 3: Defensive Structure

Two sub-tabs:
  • Our Defense        — Barcelona's defensive actions (tackles, interceptions,
                         clearances, ball recoveries, blocked shots)
  • Opposition Offense — How opponents attack vs Barca (shots, zones, flanks,
                         space analysis)

Skeleton + callback pattern: skeletons render instantly; data is populated
asynchronously by each sub-tab's own callback.

Coordinate convention (from AGENT_README):
  ALL plots show direction of attack left → right.
  Opta data is per-team normalised (x=0 = own goal, x=100 = opp goal) for
  BOTH Barcelona events AND opponent events — no flipping needed.
"""

import io
import base64

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
from mplsoccer import Pitch

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from dash import html, dcc, Input, Output, State
import dash_bootstrap_components as dbc

from utils.config import COLORS
from utils.data_utils import get_all_events, CURRENT_SEASON
from utils.xg_utils import add_xg_column
from page_utils import PassMap, GOLD, HOME_COLOR, AWAY_COLOR
from page_utils.competitions import normalize_competitions as _normalize_competitions
from page_utils.pitch_zones import BOX_X_MIN, BOX_Y_MIN, BOX_Y_MAX
from page_utils.visualizations import (
    add_pitch_background,
    PITCH_AXIS_FULL,
    PITCH_AXIS_HALF,
    render_xt_heatmap_img,
    PITCH_BG,
)
from page_utils.event_filters import SHOT_TYPES as _SHOT_TYPES


# =============================================================================
# Constants
# =============================================================================

_PITCH_LINE_COLOR = '#8899CC'
_SKEL_SRC         = 'data:image/png;base64,'

_DEF_COLORS = {
    'Tackle':        '#4dabf7',
    'Interception':  '#51cf66',
    'Ball Recovery': '#ffd43b',
    'Clearance':     '#ff922b',
    'Blocked Shot':  '#cc5de8',
    'Foul':          '#ff6b6b',
}
_ALL_DEF_TYPES = list(_DEF_COLORS.keys())
_SHOT_COLORS = {
    'Goal':         '#51cf66',
    'Saved Shot':   '#339af0',
    'Miss':         '#ff6b6b',
    'Post':         '#ffd43b',
    'Blocked Shot': '#cc5de8',
}
_SHOT_SYMBOLS = {
    'Goal':         'star',
    'Saved Shot':   'circle',
    'Miss':         'x',
    'Post':         'diamond',
    'Blocked Shot': 'square',
}

_ENTRY_COLORS = {
    'Pass':    '#32cd32',
    'Dribble': '#ffa500',
    'Carry':   '#00bfff',
}
_ZONE14_COLORS = {
    'Zone 14':          '#ff1493',
    'Left Half Space':  '#00ffff',
    'Right Half Space': '#ffd700',
}

# Six-yard box boundaries (Opta 100×100 scale, attacking end)
_SIX_YARD_X    = 94.2
_SIX_YARD_YMIN = 37.0
_SIX_YARD_YMAX = 63.0


# =============================================================================
# Shared style constants
# =============================================================================

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
_NAME_TD = {
    **_TD, 'textAlign': 'left', 'color': GOLD,
    'maxWidth': '100px', 'overflow': 'hidden', 'textOverflow': 'ellipsis',
}

CHART_CFG = {'displayModeBar': False}



# =============================================================================
# Shared helpers
# =============================================================================

def _skel_fig(height: int = 520) -> go.Figure:
    fig = go.Figure()
    fig.update_layout(
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor=PITCH_BG,
        height=height, margin=dict(l=0, r=0, t=36, b=0),
    )
    return fig


def _apply_global_filters(events, competition, venue, match_ids, match_data):
    """Apply competition / venue / match-selection filters to events DataFrame."""
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

    return events


def _apply_time_filter(df, h1_range, h2_range):
    if 'period_id' not in df.columns or 'time_min' not in df.columns:
        return df
    h1_lo, h1_hi = h1_range
    h2_lo, h2_hi = h2_range
    m1 = (df['period_id'] == 1) & (df['time_min'] >= h1_lo) & (df['time_min'] <= h1_hi)
    m2 = (df['period_id'] == 2) & (df['time_min'] >= h2_lo) & (df['time_min'] <= h2_hi)
    return df[m1 | m2]


def _shot_zone_label(x: float, y: float) -> str:
    if x >= _SIX_YARD_X and _SIX_YARD_YMIN <= y <= _SIX_YARD_YMAX:
        return '6-Yard Box'
    if x >= BOX_X_MIN and BOX_Y_MIN <= y <= BOX_Y_MAX:
        return 'Inside Box'
    if x >= 66.7:
        return 'Outside Box'
    return 'Long Range'


def _kpi_card(value, label, color=None) -> html.Div:
    return html.Div([
        html.Div(str(value), style={
            'color': color or COLORS['text_primary'],
            'fontWeight': '800', 'fontSize': '1.35rem', 'lineHeight': '1.1',
        }),
        html.Div(label, style={
            'color': COLORS['text_secondary'],
            'fontSize': '0.60rem', 'fontWeight': '600',
            'letterSpacing': '0.6px', 'textTransform': 'uppercase',
            'marginTop': '3px',
        }),
    ], style={
        'backgroundColor': COLORS['dark_secondary'],
        'border': f'1px solid {COLORS["dark_border"]}',
        'borderRadius': '6px', 'padding': '8px 10px',
        'flex': '1', 'minWidth': '0',
    })


def _add_attack_direction(fig: go.Figure, label: str = '➡  Direction of Attack') -> None:
    fig.add_annotation(
        x=0.5, y=1.02, xref='paper', yref='paper',
        text=f'<b>{label}</b>',
        showarrow=False,
        font=dict(size=10, color='white', family='Arial, sans-serif'),
        xanchor='center', yanchor='bottom',
        bgcolor='rgba(21,25,50,0.8)',
        bordercolor='#8899CC', borderwidth=1, borderpad=4,
    )


# =============================================================================
# OUR DEFENSE — data / chart functions
# =============================================================================

def _def_kpi_children(bar_def: pd.DataFrame, all_events: pd.DataFrame) -> list:
    """KPI bar for Barcelona's defensive actions."""
    if bar_def.empty:
        total_n = tkl_n = tkl_won_pct = 0
        duel_total = duel_win_pct = 0
        int_n = clr_n = clean_sheets = matches_played = 0
    else:
        total_n  = len(bar_def)
        tackles  = bar_def[bar_def['event_type'] == 'Tackle']
        tkl_n    = len(tackles)
        tkl_won  = (int((tackles['outcome'] == 1).sum())
                    if tkl_n > 0 and 'outcome' in tackles.columns else 0)
        tkl_won_pct = round(tkl_won / tkl_n * 100) if tkl_n > 0 else 0

        challenge_n = int((
            (all_events['team_code'] == 'BAR') &
            (all_events['event_type'] == 'Challenge')
        ).sum())
        duel_total  = tkl_n + challenge_n
        duel_win_pct = round(tkl_n / duel_total * 100) if duel_total > 0 else 0

        int_n = int((bar_def['event_type'] == 'Interception').sum())
        clr_n = int((bar_def['event_type'] == 'Clearance').sum())

        match_ids_in = set(all_events['match_id'].unique())
        opp_goals = set(
            all_events[
                (all_events['team_code'] != 'BAR') &
                (all_events['event_type'] == 'Goal')
            ]['match_id'].unique()
        )
        clean_sheets   = len(match_ids_in - opp_goals)
        matches_played = len(match_ids_in)

    cards = [
        _kpi_card(total_n,                       'Total',           HOME_COLOR),
        _kpi_card(tkl_n,                         'Tackles',         HOME_COLOR),
        _kpi_card(f'{tkl_won_pct}%',             '% Tackles Won',   GOLD),
        _kpi_card(duel_total,                    'Def Duels',       HOME_COLOR),
        _kpi_card(f'{duel_win_pct}%',            '% Duels Won',     GOLD),
        _kpi_card(int_n,                         'Interceptions',   HOME_COLOR),
        _kpi_card(clr_n,                         'Clearances',      HOME_COLOR),
        _kpi_card(f'{clean_sheets}/{matches_played}', 'Clean Sheets', GOLD),
    ]
    return [html.Div(cards, style={'display': 'flex', 'gap': '6px', 'flexWrap': 'wrap'})]


def _def_pitch_fig(def_events: pd.DataFrame) -> go.Figure:
    """Full-pitch scatter of Barca defensive actions, coloured by action type."""
    fig = go.Figure()
    add_pitch_background(fig, half=False)

    for action_type, color in _DEF_COLORS.items():
        subset = def_events[def_events['event_type'] == action_type].dropna(subset=['x', 'y'])
        if subset.empty:
            continue

        custom = []
        for _, row in subset.iterrows():
            player      = row.get('player_name', '') or 'Unknown'
            t_str       = f"{int(row.get('time_min', 0))}'"
            outcome_str = 'Won' if row.get('outcome', 0) == 1 else 'Lost'
            custom.append([player, t_str, action_type, outcome_str])

        fig.add_trace(go.Scatter(
            x=subset['x'], y=subset['y'],
            mode='markers', name=action_type,
            marker=dict(
                color=color, size=9, opacity=0.85,
                line=dict(color='white', width=0.6),
            ),
            customdata=custom,
            hovertemplate=(
                '<b>%{customdata[0]}</b>  %{customdata[1]}<br>'
                'Action: %{customdata[2]}<br>'
                'Outcome: %{customdata[3]}'
                '<extra></extra>'
            ),
        ))

    _add_attack_direction(fig)
    fig.update_layout(
        **PITCH_AXIS_FULL,
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
        font=dict(color='#E8E9ED', size=12, family='Arial, sans-serif'),
        height=540,
        hovermode='closest',
        uirevision='ds-def-pitch',
        legend=dict(
            orientation='v', x=1.01, y=1.0,
            xanchor='left', yanchor='top',
            bgcolor='rgba(21,25,50,0.88)',
            bordercolor=COLORS['dark_border'], borderwidth=1,
            font=dict(color=COLORS['text_primary'], size=10),
        ),
        margin=dict(l=0, r=130, t=36, b=0),
    )
    return fig


def _def_heatmap_src(def_events: pd.DataFrame) -> str:
    coords = def_events.dropna(subset=['x', 'y'])
    if len(coords) < 2:
        return _SKEL_SRC
    return render_xt_heatmap_img(
        coords['x'].values, coords['y'].values,
        [1.0] * len(coords),
    )


_FOUL_COLOR    = '#ff922b'
_OFFSIDE_COLOR = '#74c0fc'


def _annotate_foul_cards(foul_ev: pd.DataFrame, card_ev: pd.DataFrame) -> pd.DataFrame:
    """Add card_type column ('none', 'yellow', 'red') to foul events by matching player+minute."""
    foul_ev = foul_ev.copy()
    foul_ev['card_type'] = 'none'
    if card_ev.empty or 'player_name' not in card_ev.columns:
        return foul_ev
    yellow_set: set = set()
    red_set: set = set()
    for _, row in card_ev.iterrows():
        player = row.get('player_name', '')
        minute = row.get('time_min', -1)
        if 'Red Card' in card_ev.columns and row.get('Red Card') == 'Si':
            red_set.add((player, minute))
        elif 'Yellow Card' in card_ev.columns and row.get('Yellow Card') == 'Si':
            yellow_set.add((player, minute))
        elif 'Second yellow' in card_ev.columns and row.get('Second yellow') == 'Si':
            yellow_set.add((player, minute))

    def _card_type(row):
        key = (row.get('player_name', ''), row.get('time_min', -1))
        if key in red_set:
            return 'red'
        if key in yellow_set:
            return 'yellow'
        return 'none'

    foul_ev['card_type'] = foul_ev.apply(_card_type, axis=1)
    return foul_ev


def _foul_offside_fig(foul_ev: pd.DataFrame, offside_ev: pd.DataFrame) -> go.Figure:
    """Full-pitch scatter of fouls (colored by card outcome) and offsides provoked (blue)."""
    fig = go.Figure()
    add_pitch_background(fig, half=False)

    foul_groups = [
        ('none',   'Foul',       _FOUL_COLOR, 'circle'),
        ('yellow', 'Foul (YC)', '#ffd43b',    'circle'),
        ('red',    'Foul (RC)', '#ff6b6b',    'circle'),
    ]
    foul_ev = foul_ev.dropna(subset=['x', 'y'])
    for card_val, label, color, symbol in foul_groups:
        if 'card_type' in foul_ev.columns:
            subset = foul_ev[foul_ev['card_type'] == card_val]
        else:
            subset = foul_ev if card_val == 'none' else pd.DataFrame()
        if subset.empty:
            continue
        custom = [
            [row.get('player_name', '') or 'Unknown', f"{int(row.get('time_min', 0))}'"]
            for _, row in subset.iterrows()
        ]
        fig.add_trace(go.Scatter(
            x=subset['x'], y=subset['y'],
            mode='markers', name=label,
            marker=dict(color=color, size=8, symbol=symbol, opacity=0.85,
                        line=dict(color='white', width=0.5)),
            customdata=custom,
            hovertemplate=(
                '<b>%{customdata[0]}</b>  %{customdata[1]}<br>'
                f'{label}<extra></extra>'
            ),
        ))

    offside_ev = offside_ev.dropna(subset=['x', 'y'])
    if not offside_ev.empty:
        custom = [
            [row.get('player_name', '') or 'Unknown', f"{int(row.get('time_min', 0))}'"]
            for _, row in offside_ev.iterrows()
        ]
        fig.add_trace(go.Scatter(
            x=offside_ev['x'], y=offside_ev['y'],
            mode='markers', name='Offside Provoked',
            marker=dict(color=_OFFSIDE_COLOR, size=8, symbol='diamond', opacity=0.85,
                        line=dict(color='white', width=0.5)),
            customdata=custom,
            hovertemplate=(
                '<b>%{customdata[0]}</b>  %{customdata[1]}<br>'
                'Offside Provoked<extra></extra>'
            ),
        ))

    _add_attack_direction(fig)
    fig.update_layout(
        **PITCH_AXIS_FULL,
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
        font=dict(color='#E8E9ED', size=12, family='Arial, sans-serif'),
        height=540,
        hovermode='closest',
        uirevision='ds-foul-map',
        legend=dict(
            orientation='v', x=1.01, y=1.0,
            xanchor='left', yanchor='top',
            bgcolor='rgba(21,25,50,0.88)',
            bordercolor=COLORS['dark_border'], borderwidth=1,
            font=dict(color=COLORS['text_primary'], size=10),
        ),
        margin=dict(l=0, r=130, t=36, b=0),
    )
    return fig


def _foul_player_table(team_events: pd.DataFrame, top_n: int = 15) -> list:
    """Per-player fouls, offsides provoked, and card breakdown table."""
    _no_data = [html.P("No data", style={
        'color': COLORS['text_secondary'], 'fontSize': '0.75rem',
        'textAlign': 'center', 'marginTop': '8px',
    })]
    if team_events.empty or 'player_name' not in team_events.columns:
        return _no_data

    rows_data = []
    for player, grp in team_events.groupby('player_name'):
        if not player:
            continue
        fouls    = int((grp['event_type'] == 'Foul').sum())
        offsides = int((grp['event_type'] == 'Offside provoked').sum())
        cards    = grp[grp['event_type'] == 'Card']
        yellows  = int((cards['Yellow Card'].eq('Si')).sum()) if not cards.empty and 'Yellow Card' in cards.columns else 0
        reds     = int((cards['Red Card'].eq('Si')).sum()) if not cards.empty and 'Red Card' in cards.columns else 0
        if fouls + offsides + yellows + reds == 0:
            continue
        rows_data.append({
            'player':   player,
            'fouls':    fouls,
            'offsides': offsides,
            'yellow':   yellows,
            'red':      reds,
        })

    rows_data.sort(key=lambda r: r['fouls'], reverse=True)
    rows_data = rows_data[:top_n]
    if not rows_data:
        return _no_data

    header = html.Tr([
        html.Th('Player', style={**_TH, 'textAlign': 'left'}),
        html.Th('Fls',    style=_TH),
        html.Th('Off',    style=_TH),
        html.Th('YC',     style=_TH),
        html.Th('RC',     style=_TH),
    ])
    table_rows = []
    for idx, s in enumerate(rows_data):
        bg    = (COLORS.get('dark_tertiary', 'rgba(255,255,255,0.03)')
                 if idx % 2 == 0 else 'transparent')
        short = s['player'].split()[-1] if s['player'] else '—'
        table_rows.append(html.Tr([
            html.Td(short,              style=_NAME_TD),
            html.Td(str(s['fouls']),    style={**_TD, 'color': _FOUL_COLOR}),
            html.Td(str(s['offsides']), style={**_TD, 'color': _OFFSIDE_COLOR}),
            html.Td(str(s['yellow']),   style={**_TD, 'color': '#ffd43b'}),
            html.Td(str(s['red']),      style={**_TD, 'color': '#ff6b6b'}),
        ], style={'backgroundColor': bg}))

    legend = html.Div(
        "Fls = Fouls  ·  Off = Offsides Provoked  ·  YC = Yellow  ·  RC = Red",
        style={'color': COLORS['text_secondary'], 'fontSize': '0.55rem',
               'fontStyle': 'italic', 'marginBottom': '4px'},
    )
    return [
        legend,
        html.Div(
            html.Table([html.Thead(header), html.Tbody(table_rows)],
                       style={'width': '100%', 'borderCollapse': 'collapse'}),
            style={'overflowX': 'auto'},
        ),
    ]


def _def_player_table(def_events: pd.DataFrame, bar_events: pd.DataFrame,
                      top_n: int = 15) -> list:
    """Per-player defensive action breakdown table.

    Columns: Total | Tkl | T% | Duels | D% | Int | Clr
    Defensive Duel = Tackle (won) + Challenge (lost ground duel, event_type 45).
    Duel Win % = Tackles / (Tackles + Challenges).
    """
    _no_data = [html.P("No data", style={
        'color': COLORS['text_secondary'], 'fontSize': '0.75rem',
        'textAlign': 'center', 'marginTop': '8px',
    })]
    if def_events.empty or 'player_name' not in def_events.columns:
        return _no_data

    # Build challenge lookup per player from full bar events
    challenges_by_player: dict[str, int] = {}
    if not bar_events.empty and 'player_name' in bar_events.columns:
        chal = bar_events[bar_events['event_type'] == 'Challenge']
        if not chal.empty:
            challenges_by_player = chal.groupby('player_name').size().to_dict()

    rows_data = []
    for player, grp in def_events.groupby('player_name'):
        if not player:
            continue
        tackles  = grp[grp['event_type'] == 'Tackle']
        tkl_tot  = len(tackles)
        tkl_won  = (
            int((tackles['outcome'] == 1).sum())
            if tkl_tot > 0 and 'outcome' in tackles.columns
            else 0
        )
        challenges   = challenges_by_player.get(player, 0)
        duel_total   = tkl_tot + challenges
        rows_data.append({
            'player':     player,
            'total':      len(grp),
            'tkl':        tkl_tot,
            'tkl_won':    tkl_won,
            'duel_total': duel_total,
            'int':        int((grp['event_type'] == 'Interception').sum()),
            'clr':        int((grp['event_type'] == 'Clearance').sum()),
        })

    rows_data.sort(key=lambda r: r['total'], reverse=True)
    rows_data = rows_data[:top_n]
    if not rows_data:
        return _no_data

    header = html.Tr([
        html.Th('Player', style={**_TH, 'textAlign': 'left'}),
        html.Th('Tot',    style=_TH),
        html.Th('Tkl',   style=_TH),
        html.Th('T%',    style=_TH),
        html.Th('Duels', style=_TH),
        html.Th('D%',    style=_TH),
        html.Th('Int',   style=_TH),
        html.Th('Clr',   style=_TH),
    ])
    table_rows = []
    for idx, s in enumerate(rows_data):
        bg       = (COLORS.get('dark_tertiary', 'rgba(255,255,255,0.03)')
                    if idx % 2 == 0 else 'transparent')
        short    = s['player'].split()[-1] if s['player'] else '—'
        tkl_pct  = (f"{round(s['tkl_won'] / s['tkl'] * 100)}%"
                    if s['tkl'] > 0 else '—')
        duel_pct = (f"{round(s['tkl'] / s['duel_total'] * 100)}%"
                    if s['duel_total'] > 0 else '—')
        table_rows.append(html.Tr([
            html.Td(short,              style=_NAME_TD),
            html.Td(str(s['total']),    style={**_TD, 'color': HOME_COLOR, 'fontWeight': '700'}),
            html.Td(str(s['tkl']),      style={**_TD, 'color': '#4dabf7'}),
            html.Td(tkl_pct,            style={**_TD, 'color': GOLD}),
            html.Td(str(s['duel_total']), style={**_TD, 'color': '#a78bfa'}),
            html.Td(duel_pct,           style={**_TD, 'color': GOLD}),
            html.Td(str(s['int']),      style={**_TD, 'color': '#51cf66'}),
            html.Td(str(s['clr']),      style={**_TD, 'color': '#ff922b'}),
        ], style={'backgroundColor': bg}))

    legend = html.Div(
        "Tkl = Tackles  ·  T% = Tackle Win%  ·  "
        "Duels = Def Duels (Tkl + Challenge)  ·  D% = Duel Win%  ·  "
        "Int = Interceptions  ·  Clr = Clearances",
        style={'color': COLORS['text_secondary'], 'fontSize': '0.55rem',
               'fontStyle': 'italic', 'marginBottom': '4px'},
    )
    return [
        legend,
        html.Div(
            html.Table(
                [html.Thead(header), html.Tbody(table_rows)],
                style={'width': '100%', 'borderCollapse': 'collapse'},
            ),
            style={'overflowX': 'auto'},
        ),
    ]


def _def_zone_summary(def_events: pd.DataFrame) -> list:
    """Zone bar showing pressing height (where Barca wins the ball back)."""
    if def_events.empty:
        return []

    total = max(len(def_events), 1)
    z1 = int((def_events['x'] < 33.33).sum())
    z2 = int(((def_events['x'] >= 33.33) & (def_events['x'] < 66.67)).sum())
    z3 = int((def_events['x'] >= 66.67).sum())

    def _row(label, count, color):
        pct = round(count / total * 100)
        return html.Div([
            html.Span(label, style={
                'color': COLORS['text_secondary'], 'fontSize': '0.68rem',
                'minWidth': '90px',
            }),
            html.Div(style={
                'flex': '1', 'height': '6px',
                'backgroundColor': COLORS['dark_border'],
                'borderRadius': '3px', 'overflow': 'hidden', 'margin': '0 8px',
            }, children=[
                html.Div(style={
                    'width': f'{pct}%', 'height': '100%',
                    'backgroundColor': color, 'borderRadius': '3px',
                }),
            ]),
            html.Span(f'{count}  ({pct}%)', style={
                'color': color, 'fontSize': '0.68rem', 'fontWeight': '700',
                'minWidth': '60px', 'textAlign': 'right',
            }),
        ], style={'display': 'flex', 'alignItems': 'center', 'padding': '4px 0'})

    return [
        html.Hr(style={'borderColor': COLORS['dark_border'], 'margin': '10px 0 8px'}),
        html.Div("Pressing Height", style={**_SECTION_TITLE, 'marginBottom': '6px'}),
        html.Div(
            "Where Barca wins the ball back",
            style={'color': COLORS['text_secondary'], 'fontSize': '0.60rem',
                   'fontStyle': 'italic', 'marginBottom': '6px'},
        ),
        _row('Own Third (Z1)',  z1, AWAY_COLOR),
        _row('Mid Third (Z2)',  z2, GOLD),
        _row('Att Third (Z3)', z3, HOME_COLOR),
    ]


def _def_zone_donut_fig(def_events: pd.DataFrame) -> go.Figure:
    """Donut chart: pressing height — where Barca wins the ball back."""
    labels = ['Def Third (Z1)', 'Mid Third (Z2)', 'Att Third (Z3)']
    colors = [AWAY_COLOR, GOLD, HOME_COLOR]
    if def_events.empty:
        z1 = z2 = z3 = 0
    else:
        z1 = int((def_events['x'] < 33.33).sum())
        z2 = int(((def_events['x'] >= 33.33) & (def_events['x'] < 66.67)).sum())
        z3 = int((def_events['x'] >= 66.67).sum())
    fig = go.Figure(go.Pie(
        labels=labels, values=[z1, z2, z3],
        marker=dict(colors=colors, line=dict(color=PITCH_BG, width=2)),
        hole=0.55, textinfo='percent', textfont=dict(color='white', size=11),
        hovertemplate='<b>%{label}</b><br>%{value} actions (%{percent})<extra></extra>',
        sort=False,
    ))
    fig.update_layout(
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
        font=dict(color='#E8E9ED', size=11, family='Arial, sans-serif'),
        height=220, margin=dict(l=0, r=0, t=10, b=0), showlegend=True,
        legend=dict(orientation='v', x=1.0, y=0.5, xanchor='left', yanchor='middle',
                    font=dict(color=COLORS['text_primary'], size=9), bgcolor='rgba(0,0,0,0)'),
        uirevision='ds-def-zone-donut',
    )
    return fig


def _offsides_only_fig(offside_ev: pd.DataFrame) -> go.Figure:
    """Full-pitch scatter of offsides provoked only."""
    fig = go.Figure()
    add_pitch_background(fig, half=False)
    offside_ev = offside_ev.dropna(subset=['x', 'y'])
    if not offside_ev.empty:
        custom = [
            [row.get('player_name', '') or 'Unknown', f"{int(row.get('time_min', 0))}'"]
            for _, row in offside_ev.iterrows()
        ]
        fig.add_trace(go.Scatter(
            x=offside_ev['x'], y=offside_ev['y'],
            mode='markers', name='Offside Provoked',
            marker=dict(color=_OFFSIDE_COLOR, size=8, symbol='diamond', opacity=0.85,
                        line=dict(color='white', width=0.5)),
            customdata=custom,
            hovertemplate='<b>%{customdata[0]}</b>  %{customdata[1]}<br>Offside Provoked<extra></extra>',
        ))
    _add_attack_direction(fig)
    fig.update_layout(
        **PITCH_AXIS_FULL,
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
        font=dict(color='#E8E9ED', size=12, family='Arial, sans-serif'),
        height=540, hovermode='closest', uirevision='ds-offside-map',
        legend=dict(
            orientation='v', x=1.01, y=1.0, xanchor='left', yanchor='top',
            bgcolor='rgba(21,25,50,0.88)',
            bordercolor=COLORS['dark_border'], borderwidth=1,
            font=dict(color=COLORS['text_primary'], size=10),
        ),
        margin=dict(l=0, r=130, t=36, b=0),
    )
    return fig


def _gk_stats_children(shots: pd.DataFrame, gk_events: pd.DataFrame | None = None) -> list:
    """Goalkeeper stats block shown below the Shot Map / Shooting Zones row.

    shots      — shots the GK had to face (opponent shots in def_structure context)
    gk_events  — events from the GK's own team (to extract Save, Punch, Claim, etc.)
    """
    _GK_ACTIONS = ['Save', 'Keeper pick-up', 'Keeper Sweeper', 'Claim', 'Punch', 'Smother']

    if shots.empty:
        saves = goals = sot = box_saves = 0
        save_pct = 0.0
        xga = gsave = 0.0
    else:
        try:
            shots_xg = add_xg_column(shots.copy())
            xga = round(float(shots_xg['xg'].fillna(0).sum()), 2)
        except Exception:
            shots_xg = shots.copy()
            shots_xg['xg'] = 0.0
            xga = 0.0

        saves    = int((shots['event_type'] == 'Saved Shot').sum())
        goals    = int((shots['event_type'] == 'Goal').sum())
        sot      = saves + goals
        save_pct = round(saves / max(sot, 1) * 100, 1)
        gsave    = round(xga - goals, 2)

        saved_only = shots[shots['event_type'] == 'Saved Shot']
        box_saves  = int(
            saved_only.apply(
                lambda r: r['x'] >= BOX_X_MIN and BOX_Y_MIN <= r['y'] <= BOX_Y_MAX,
                axis=1,
            ).sum()
        ) if not saved_only.empty else 0

    punches = sweeper = claims = pickups = smothers = 0
    if gk_events is not None and not gk_events.empty and 'event_type' in gk_events.columns:
        gk_ev = gk_events[gk_events['event_type'].isin(_GK_ACTIONS)]
        vc    = gk_ev['event_type'].value_counts()
        punches  = int(vc.get('Punch',         0))
        sweeper  = int(vc.get('Keeper Sweeper', 0))
        claims   = int(vc.get('Claim',          0))
        pickups  = int(vc.get('Keeper pick-up', 0))
        smothers = int(vc.get('Smother',        0))

    gsave_color = HOME_COLOR if gsave >= 0 else AWAY_COLOR
    gsave_str   = f'+{gsave:.2f}' if gsave >= 0 else f'{gsave:.2f}'

    kpi_cards = [
        _kpi_card(saves,          'Saves',           HOME_COLOR),
        _kpi_card(goals,          'Conceded',         AWAY_COLOR),
        _kpi_card(f'{save_pct}%', 'Save %',           GOLD),
        _kpi_card(sot,            'On Target Faced',  HOME_COLOR),
        _kpi_card(f'{xga:.2f}',   'xG Against',       GOLD),
        _kpi_card(gsave_str,      'GSAvE',            gsave_color),
        _kpi_card(box_saves,      'Box Saves',        HOME_COLOR),
        _kpi_card(len(shots) - sot, 'Off Target',    COLORS['text_primary']),
    ]

    action_parts = []
    for label, count in [('Punches', punches), ('Claims', claims),
                          ('Sweeper', sweeper), ('Pick-ups', pickups),
                          ('Smothers', smothers)]:
        if count > 0:
            action_parts.append(
                html.Span([
                    html.Span(f'{label}: ', style={
                        'color': COLORS['text_secondary'], 'fontSize': '0.70rem',
                    }),
                    html.Span(str(count), style={
                        'color': GOLD, 'fontWeight': '700', 'fontSize': '0.70rem',
                    }),
                ])
            )

    action_row = html.Div(
        children=(
            [action_parts[0]] +
            [item for part in action_parts[1:]
             for item in [html.Span('  ·  ', style={'color': COLORS['text_secondary'],
                                                    'fontSize': '0.70rem'}), part]]
        ) if action_parts else [html.Span('No GK action data', style={
            'color': COLORS['text_secondary'], 'fontSize': '0.70rem', 'fontStyle': 'italic',
        })],
        style={'marginTop': '8px', 'display': 'flex', 'flexWrap': 'wrap', 'gap': '4px',
               'alignItems': 'center'},
    )

    return [
        html.Hr(style={'borderColor': COLORS['dark_border'], 'margin': '18px 0 14px'}),
        html.Div("Goalkeeper Statistics", style=_SECTION_TITLE),
        html.Div(
            "GSAvE = xG Against − Goals Conceded  ·  positive = better than expected",
            style={'color': COLORS['text_secondary'], 'fontSize': '0.62rem',
                   'fontStyle': 'italic', 'marginBottom': '8px'},
        ),
        html.Div(kpi_cards, style={'display': 'flex', 'gap': '6px', 'flexWrap': 'wrap'}),
        action_row,
    ]



# =============================================================================
# OUR DEFENSE — filter panel + skeleton
# =============================================================================

def _def_filter_panel(player_opts=None) -> html.Div:
    return html.Div([
        html.Div("Filters", style=_SECTION_TITLE),

        html.Div("Player", style=_LABEL_STYLE),
        dcc.Dropdown(
            id='ds-def-player',
            options=player_opts or [],
            value=None, multi=True,
            placeholder="All players…",
            style={'fontSize': '0.75rem'},
        ),

        *PassMap.dash_controls(
            show=['outcome', 'bands', 'h1_time', 'h2_time'],
            id_prefix='ds-def',
        ),

        html.Div("Zone of Action", style=_LABEL_STYLE),
        dcc.Checklist(
            id='ds-def-start-third',
            options=[
                {'label': ' Zone 1', 'value': 'defensive'},
                {'label': ' Zone 2', 'value': 'middle'},
                {'label': ' Zone 3', 'value': 'final'},
            ],
            value=['defensive', 'middle', 'final'],
            inputStyle={'marginRight': '4px'},
            labelStyle={'display': 'flex', 'alignItems': 'center',
                        'fontSize': '0.72rem', 'color': COLORS['text_primary'],
                        'marginBottom': '3px'},
            style={'marginBottom': '8px'},
        ),
        html.Div("Action Type", style=_LABEL_STYLE),
        dcc.Checklist(
            id='ds-def-action-type',
            options=[{'label': f' {t}', 'value': t} for t in _ALL_DEF_TYPES],
            value=list(_ALL_DEF_TYPES),
            inputStyle={'marginRight': '4px'},
            labelStyle={'display': 'flex', 'alignItems': 'center',
                        'fontSize': '0.72rem', 'color': COLORS['text_primary'],
                        'marginBottom': '3px'},
            style={'marginBottom': '8px'},
        ),
    ], style=_PANEL_STYLE)


def _build_our_defense_skeleton(player_opts=None) -> html.Div:
    content = html.Div([
        html.Div(id='ds-def-kpi', children=[]),
        html.Hr(style={'borderColor': COLORS['dark_border'], 'margin': '10px 0 14px'}),

        dbc.Row([
            dbc.Col([
                html.Div("Defensive Action Map", style=_SECTION_TITLE),
                html.Div(
                    "All defensive actions · hover for player, time, and outcome",
                    style={'color': COLORS['text_secondary'], 'fontSize': '0.62rem',
                           'fontStyle': 'italic', 'marginBottom': '8px'},
                ),
                dcc.Loading(type='circle', color=GOLD, children=dcc.Graph(
                    id='ds-def-pitch', figure=_skel_fig(540), config=CHART_CFG,
                    style={'width': '100%'},
                )),

                html.Hr(style={'borderColor': COLORS['dark_border'], 'margin': '14px 0 10px'}),
                html.Div("Defensive Action Heatmap", style=_SECTION_TITLE),
                html.Div(
                    "Density of all defensive events — darker = higher concentration",
                    style={'color': COLORS['text_secondary'], 'fontSize': '0.62rem',
                           'fontStyle': 'italic', 'marginBottom': '8px'},
                ),
                dcc.Loading(type='circle', color=GOLD, children=html.Img(
                    id='ds-def-heatmap', src=_SKEL_SRC,
                    style={'width': '100%', 'borderRadius': '6px', 'minHeight': '180px'},
                )),

            ], md=8),

            dbc.Col([
                html.Div("By Player", style={**_SECTION_TITLE, 'fontSize': '0.75rem'}),
                html.Div(style={'marginBottom': '6px'}),
                html.Div(id='ds-def-table', children=[]),

                html.Hr(style={'borderColor': COLORS['dark_border'], 'margin': '10px 0 8px'}),
                html.Div("Pressing Height", style={**_SECTION_TITLE, 'marginBottom': '6px'}),
                html.Div(
                    "Where Barca wins the ball back",
                    style={'color': COLORS['text_secondary'], 'fontSize': '0.60rem',
                           'fontStyle': 'italic', 'marginBottom': '4px'},
                ),
                dcc.Graph(id='ds-def-zone-donut', figure=_skel_fig(220), config=CHART_CFG,
                          style={'width': '100%'}),

                html.Hr(style={'borderColor': COLORS['dark_border'], 'margin': '10px 0 8px'}),
                html.Div("Vulnerable Flanks", style={**_SECTION_TITLE, 'fontSize': '0.75rem'}),
                html.Div(
                    "Where opponents attack (att half events by y-channel)",
                    style={'color': COLORS['text_secondary'], 'fontSize': '0.60rem',
                           'fontStyle': 'italic', 'marginBottom': '6px'},
                ),
                dcc.Loading(type='circle', color=GOLD, children=dcc.Graph(
                    id='ds-def-flank-fig', figure=_skel_fig(180), config=CHART_CFG,
                    style={'width': '100%'},
                )),

            ], md=4, style={
                'borderLeft': f'1px solid {COLORS["dark_border"]}',
                'paddingLeft': '14px',
            }),
        ], align='start', className='g-0'),

        html.Hr(style={'borderColor': COLORS['dark_border'], 'margin': '18px 0 14px'}),

        dbc.Row([
            dbc.Col([
                html.Div("Offsides Provoked", style=_SECTION_TITLE),
                html.Div(
                    "Offsides provoked (◆) — hover for player and minute",
                    style={'color': COLORS['text_secondary'], 'fontSize': '0.62rem',
                           'fontStyle': 'italic', 'marginBottom': '8px'},
                ),
                dcc.Loading(type='circle', color=GOLD, children=dcc.Graph(
                    id='ds-foul-map', figure=_skel_fig(540), config=CHART_CFG,
                    style={'width': '100%'},
                )),
            ], md=8),

            dbc.Col([
                html.Div("Discipline", style={**_SECTION_TITLE, 'fontSize': '0.75rem'}),
                html.Div(style={'marginBottom': '6px'}),
                html.Div(id='ds-foul-table', children=[]),
            ], md=4, style={
                'borderLeft': f'1px solid {COLORS["dark_border"]}',
                'paddingLeft': '14px',
            }),
        ], align='start', className='g-0'),

        html.Hr(style={'borderColor': COLORS['dark_border'], 'margin': '18px 0 14px'}),

        dbc.Row([
            dbc.Col([
                html.Div("Entries into Final Third",
                         style={**_SECTION_TITLE, 'borderBottom': 'none',
                                'paddingBottom': '4px', 'fontSize': '0.72rem'}),
                dcc.Loading(type='circle', color=GOLD, children=dcc.Graph(
                    id='ds-opp-ft-fig', figure=_skel_fig(480), config=CHART_CFG,
                    style={'width': '100%'},
                )),
                html.Div(id='ds-opp-ft-table', children=[], style={'marginTop': '8px'}),
            ], md=6),
            dbc.Col([
                html.Div("Zone 14 & Half Spaces",
                         style={**_SECTION_TITLE, 'borderBottom': 'none',
                                'paddingBottom': '4px', 'fontSize': '0.72rem'}),
                dcc.Loading(type='circle', color=GOLD, children=dcc.Graph(
                    id='ds-opp-z14-fig', figure=_skel_fig(480), config=CHART_CFG,
                    style={'width': '100%'},
                )),
                html.Div(id='ds-opp-z14-table', children=[], style={'marginTop': '8px'}),
            ], md=6, style={
                'borderLeft': f'1px solid {COLORS["dark_border"]}',
                'paddingLeft': '14px',
            }),
        ], align='start', className='g-0'),

        html.Div(id='ds-gk-stats', children=[]),

        html.Hr(style={'borderColor': COLORS['dark_border'], 'margin': '18px 0 14px'}),

        dbc.Row([
            dbc.Col([
                html.Div("Opposition Shot Map", style=_SECTION_TITLE),
                html.Div(
                    "Where opponents shoot from · size = xG · stars = goals",
                    style={'color': COLORS['text_secondary'], 'fontSize': '0.62rem',
                           'fontStyle': 'italic', 'marginBottom': '8px'},
                ),
                dcc.Loading(type='circle', color=GOLD, children=dcc.Graph(
                    id='ds-opp-shot-map', figure=_skel_fig(480), config=CHART_CFG,
                    style={'width': '100%', 'height': '480px'},
                )),
            ], md=6),

            dbc.Col([
                html.Div("Shooting Zones", style=_SECTION_TITLE),
                html.Div(
                    "% of shots conceded from each zone",
                    style={'color': COLORS['text_secondary'], 'fontSize': '0.62rem',
                           'fontStyle': 'italic', 'marginBottom': '8px'},
                ),
                dcc.Loading(type='circle', color=GOLD, children=html.Img(
                    id='ds-opp-zone-donut', src='',
                    style={
                        'width': '100%',
                        'height': '480px',
                        'objectFit': 'contain',
                        'display': 'block',
                        'borderRadius': '4px',
                    },
                )),
            ], md=6, style={
                'borderLeft': f'1px solid {COLORS["dark_border"]}',
                'paddingLeft': '14px',
            }),
        ], align='start', className='g-0'),
    ], style=_PANEL_STYLE)

    return html.Div(
        dbc.Row([
            dbc.Col(_def_filter_panel(player_opts), md=2),
            dbc.Col(content,                        md=10),
        ], align='start', className='g-3'),
    )


# =============================================================================
# OPPOSITION OFFENSE — data / chart functions
# =============================================================================

def _opp_shot_map_fig(opp_shots: pd.DataFrame) -> go.Figure:
    """
    Horizontal half-pitch scatter of opposition shots.
    Raw Opta coordinates used directly (x = 50–100, y = 0–100).
    Dot size proportional to xG; goals are stars.
    """
    fig = go.Figure()
    add_pitch_background(fig, half=True)

    if not opp_shots.empty:
        try:
            opp_shots = add_xg_column(opp_shots.copy())
        except Exception:
            opp_shots['xg'] = 0.0

    _base = dict(
        **PITCH_AXIS_HALF,
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor=PITCH_BG,
        height=480, margin=dict(l=0, r=0, t=30, b=0),
        hoverlabel=dict(bgcolor='#1A1D2E', font_color='white', font_size=12),
        legend=dict(
            x=0.01, y=0.99, xanchor='left', yanchor='top',
            orientation='v',
            font=dict(color=COLORS['text_primary'], size=10),
            bgcolor='rgba(26,29,46,0.80)',
            bordercolor=COLORS.get('dark_border', 'rgba(255,255,255,0.15)'),
            borderwidth=1,
        ),
    )

    for etype in _SHOT_TYPES:
        grp = opp_shots[opp_shots['event_type'] == etype].dropna(subset=['x', 'y'])
        if grp.empty:
            continue

        xg_vals = (grp['xg'].fillna(0.0).tolist()
                   if 'xg' in grp.columns else [0.0] * len(grp))
        sizes = ([16] * len(grp) if etype == 'Goal'
                 else [max(8, min(20, int(v * 60 + 8))) for v in xg_vals])

        player_names = (grp['player_name'].fillna('Unknown').tolist()
                        if 'player_name' in grp.columns else ['Unknown'] * len(grp))
        times = (grp['time_min'].fillna(0).astype(int).tolist()
                 if 'time_min' in grp.columns else [0] * len(grp))

        fig.add_trace(go.Scatter(
            x=grp['x'].tolist(), y=grp['y'].tolist(),
            mode='markers', name=etype,
            marker=dict(
                color=_SHOT_COLORS[etype],
                symbol=_SHOT_SYMBOLS[etype],
                size=sizes, opacity=0.88,
                line=dict(color='white', width=1),
            ),
            customdata=list(zip(player_names, times, xg_vals)),
            hovertemplate=(
                '<b>%{customdata[0]}</b><br>'
                "%{customdata[1]}' | xG: %{customdata[2]:.2f}"
                '<extra>' + etype + '</extra>'
            ),
        ))

    _add_attack_direction(fig)
    fig.update_layout(**_base)
    return fig




def _build_opp_entries(opp_events: pd.DataFrame, zone: str) -> pd.DataFrame:
    """Entries into final third or Zone 14/Half Spaces from opposition events.

    Identical logic to buildup.py `_build_entries_bar` but applied to the
    opponent team instead of BAR.
    """
    _EMPTY_COLS = [
        'player_name', 'event_label', 'x', 'y', 'end_x', 'end_y',
        'outcome', 'time_min', 'time_sec', 'period_id',
        'dest_zone', 'led_to_shot', 'led_to_goal', 'receiver_name',
    ]
    if opp_events.empty:
        return pd.DataFrame(columns=_EMPTY_COLS)

    relevant_types = ['Pass', 'Take On', 'Ball touch']
    te = opp_events.sort_values(
        ['period_id', 'time_min', 'time_sec']).reset_index(drop=True)

    is_shot = te['event_type'].isin(_SHOT_TYPES)
    is_goal = te['event_type'] == 'Goal'
    led_shot = pd.Series(False, index=te.index)
    led_goal = pd.Series(False, index=te.index)
    for _off in range(1, 6):
        led_shot |= is_shot.shift(-_off, fill_value=False)
        led_goal |= is_goal.shift(-_off, fill_value=False)

    te['_led_to_shot'] = led_shot
    te['_led_to_goal'] = led_goal
    te['_next_x']      = te['x'].shift(-1)
    te['_next_y']      = te['y'].shift(-1)
    te['_next_player'] = te['player_name'].shift(-1)

    ev = te[te['event_type'].isin(relevant_types) &
            te['x'].notna() & te['y'].notna()].copy()
    if ev.empty:
        return pd.DataFrame(columns=_EMPTY_COLS)

    is_pass = ev['event_type'] == 'Pass'
    has_end = 'Pass End X' in ev.columns and 'Pass End Y' in ev.columns
    if has_end:
        px = pd.to_numeric(ev['Pass End X'], errors='coerce')
        py = pd.to_numeric(ev['Pass End Y'], errors='coerce')
    else:
        px = pd.Series(np.nan, index=ev.index)
        py = pd.Series(np.nan, index=ev.index)

    ev['end_x'] = np.where(is_pass, px, ev['_next_x'])
    ev['end_y'] = np.where(is_pass, py, ev['_next_y'])
    ev = ev.dropna(subset=['end_x', 'end_y'])
    if ev.empty:
        return pd.DataFrame(columns=_EMPTY_COLS)

    sx = ev['x'].astype(float)
    ex = ev['end_x'].astype(float)
    ey = ev['end_y'].astype(float)

    if zone == 'final_third':
        ev = ev[(sx < 66.67) & (ex >= 66.67)].copy()
        ev['dest_zone'] = None
    elif zone == 'zone14':
        in_z14 = ex.between(66.67, 83.33) & ey.between(37, 63)
        in_lhs = (ex > 66.67) & (ey > 63)  & (ey <= 79)
        in_rhs = (ex > 66.67) & (ey >= 21) & (ey < 37)
        ev = ev[in_z14 | in_lhs | in_rhs].copy()
        ev['dest_zone'] = np.select(
            [in_z14.loc[ev.index], in_lhs.loc[ev.index]],
            ['Zone 14', 'Left Half Space'],
            default='Right Half Space',
        )

    if ev.empty:
        return pd.DataFrame(columns=_EMPTY_COLS)

    ev['event_label'] = ev['event_type'].map(
        {'Pass': 'Pass', 'Take On': 'Dribble', 'Ball touch': 'Carry'})
    suc_pass = (ev['event_type'] == 'Pass') & (
        pd.to_numeric(ev['outcome'], errors='coerce').eq(1)
        if 'outcome' in ev.columns else pd.Series(False, index=ev.index)
    )
    ev['receiver_name'] = np.where(suc_pass, ev['_next_player'].fillna(''), '')

    return ev.rename(columns={
        '_led_to_shot': 'led_to_shot',
        '_led_to_goal': 'led_to_goal',
    })[_EMPTY_COLS].reset_index(drop=True)


def _opp_entries_fig(entries_df: pd.DataFrame, zone: str) -> go.Figure:
    """Plotly pitch showing opposition entries into the final third or Zone 14."""
    fig = go.Figure()
    add_pitch_background(fig, half=False)

    if not entries_df.empty:
        df = entries_df.copy()
        mins = df['time_min'].fillna(0).astype(int)
        secs = df['time_sec'].fillna(0).astype(int)
        df['time_display'] = (
            mins.astype(str) + ':' +
            (secs // 10).astype(str) + (secs % 10).astype(str)
        )
        df['outcome_label'] = df['outcome'].map(
            {1: '✓ Successful', 0: '✗ Unsuccessful'}).fillna('—')
        df['shot_label'] = np.where(
            df['led_to_goal'].fillna(False), '<br>⚽ Led to Goal',
            np.where(df['led_to_shot'].fillna(False), '<br>🎯 Led to Shot', ''))
        if 'receiver_name' not in df.columns:
            df['receiver_name'] = ''

        color_iter = _ZONE14_COLORS.items() if zone == 'zone14' else _ENTRY_COLORS.items()
        group_col  = 'dest_zone'            if zone == 'zone14' else 'event_label'

        new_annotations: list = []
        _ann = dict(xref='x', yref='y', axref='x', ayref='y',
                    showarrow=True, arrowhead=2, arrowsize=1.5,
                    arrowwidth=2, opacity=0.65)

        for group_name, ecolor in color_iter:
            subset = df[df[group_col] == group_name]
            if subset.empty:
                continue

            passes_sub    = subset[subset['event_label'] == 'Pass']
            nonpasses_sub = subset[subset['event_label'] != 'Pass']

            if zone == 'zone14':
                for _, r in passes_sub.iterrows():
                    new_annotations.append({**_ann, 'arrowcolor': ecolor,
                        'x': r['end_x'], 'y': r['end_y'],
                        'ax': r['x'], 'ay': r['y']})
                if not nonpasses_sub.empty:
                    _x  = nonpasses_sub['x'].values
                    _ex = nonpasses_sub['end_x'].values
                    _y  = nonpasses_sub['y'].values
                    _ey = nonpasses_sub['end_y'].values
                    seg  = np.empty(len(_x) * 3, dtype=object)
                    segy = np.empty(len(_y) * 3, dtype=object)
                    seg[0::3]  = _x;  seg[1::3]  = _ex;  seg[2::3]  = None
                    segy[0::3] = _y;  segy[1::3] = _ey;  segy[2::3] = None
                    fig.add_trace(go.Scatter(
                        x=seg.tolist(), y=segy.tolist(), mode='lines',
                        line=dict(color=ecolor, width=2, dash='dash'),
                        showlegend=False, hoverinfo='skip'))
            else:
                for _, r in subset.iterrows():
                    new_annotations.append({**_ann, 'arrowcolor': ecolor,
                        'x': r['end_x'], 'y': r['end_y'],
                        'ax': r['x'], 'ay': r['y']})

            legend_name  = f'{group_name} ({len(subset)})'
            legend_shown = False

            if not passes_sub.empty:
                if zone == 'zone14':
                    cd = passes_sub[['player_name', 'receiver_name', 'event_label',
                                     'time_display', 'outcome_label', 'shot_label']].values
                    ht = (f'<b>{group_name}</b><br>'
                          'Pass: %{customdata[0]} → %{customdata[1]}<br>'
                          'Time: %{customdata[3]}<br>%{customdata[4]}%{customdata[5]}'
                          '<extra></extra>')
                else:
                    cd = passes_sub[['player_name', 'receiver_name',
                                     'time_display', 'outcome_label', 'shot_label']].values
                    ht = (f'<b>{group_name}</b><br>'
                          '%{customdata[0]} → %{customdata[1]}<br>'
                          'Time: %{customdata[2]}<br>%{customdata[3]}%{customdata[4]}'
                          '<extra></extra>')
                fig.add_trace(go.Scatter(
                    x=passes_sub['end_x'], y=passes_sub['end_y'], mode='markers',
                    marker=dict(size=8, color=ecolor, line=dict(width=1.5, color='white')),
                    customdata=cd, hovertemplate=ht,
                    name=legend_name, showlegend=True, legendgroup=group_name))
                legend_shown = True

            if not nonpasses_sub.empty:
                if zone == 'zone14':
                    cd = nonpasses_sub[['player_name', 'event_label',
                                        'time_display', 'outcome_label', 'shot_label']].values
                    ht = (f'<b>{group_name}</b><br>'
                          '%{customdata[1]}: %{customdata[0]}<br>'
                          'Time: %{customdata[2]}<br>%{customdata[3]}%{customdata[4]}'
                          '<extra></extra>')
                else:
                    cd = nonpasses_sub[['player_name',
                                        'time_display', 'outcome_label', 'shot_label']].values
                    ht = (f'<b>{group_name}</b><br>'
                          '%{customdata[0]}<br>'
                          'Time: %{customdata[1]}<br>%{customdata[2]}%{customdata[3]}'
                          '<extra></extra>')
                fig.add_trace(go.Scatter(
                    x=nonpasses_sub['end_x'], y=nonpasses_sub['end_y'], mode='markers',
                    marker=dict(size=8, color=ecolor, line=dict(width=1.5, color='white')),
                    customdata=cd, hovertemplate=ht,
                    name=legend_name if not legend_shown else '',
                    showlegend=not legend_shown, legendgroup=group_name))

        if new_annotations:
            fig.update_layout(annotations=list(fig.layout.annotations) + new_annotations)

    if zone == 'final_third':
        fig.add_shape(type='line', x0=66.67, y0=0, x1=66.67, y1=100,
                      line=dict(color='yellow', width=3, dash='dash'))
        fig.add_annotation(x=83, y=96, text='Final Third', showarrow=False,
                           font=dict(color='yellow', size=11, family='Arial Black'),
                           bgcolor='rgba(0,0,0,0.5)', borderpad=4)
    elif zone == 'zone14':
        fig.add_shape(type='rect', x0=66.67, y0=37, x1=83.33, y1=63,
                      line=dict(color='#ff1493', width=2, dash='dash'),
                      fillcolor='rgba(255,20,147,0.08)')
        fig.add_annotation(x=75, y=50, text='Zone 14', showarrow=False,
                           font=dict(color='#ff1493', size=10, family='Arial Black'),
                           bgcolor='rgba(0,0,0,0.5)', borderpad=3)
        fig.add_shape(type='rect', x0=66.67, y0=63, x1=100, y1=79,
                      line=dict(color='#00ffff', width=2, dash='dash'),
                      fillcolor='rgba(0,255,255,0.08)')
        fig.add_annotation(x=83, y=71, text='Left HS', showarrow=False,
                           font=dict(color='#00ffff', size=10, family='Arial Black'),
                           bgcolor='rgba(0,0,0,0.5)', borderpad=3)
        fig.add_shape(type='rect', x0=66.67, y0=21, x1=100, y1=37,
                      line=dict(color='#ffd700', width=2, dash='dash'),
                      fillcolor='rgba(255,215,0,0.08)')
        fig.add_annotation(x=83, y=29, text='Right HS', showarrow=False,
                           font=dict(color='#ffd700', size=10, family='Arial Black'),
                           bgcolor='rgba(0,0,0,0.5)', borderpad=3)

    _add_attack_direction(fig)
    fig.update_layout(
        **PITCH_AXIS_FULL,
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
        font=dict(color='#E8E9ED', size=12, family='Arial, sans-serif'),
        margin=dict(l=0, r=0, t=36, b=0),
        height=480,
        uirevision=f'ds-opp-entries-{zone}',
        hovermode='closest',
        legend=dict(
            orientation='v', x=0.01, xanchor='left', y=0.99, yanchor='top',
            bgcolor='rgba(0,0,0,0.55)',
            font=dict(color=COLORS['text_primary'], size=9),
        ),
    )
    return fig


def _opp_entries_table(entries_df: pd.DataFrame, top_n: int = 5) -> list:
    """Top-N player table for opposition zone entries."""
    _no_data = [html.P("No data", style={
        'color': COLORS['text_secondary'], 'fontSize': '0.75rem',
        'textAlign': 'center', 'marginTop': '8px',
    })]
    if entries_df.empty or 'player_name' not in entries_df.columns:
        return _no_data

    df = entries_df.copy()
    df['_band'] = pd.cut(
        pd.to_numeric(df['y'], errors='coerce').fillna(50),
        bins=[-0.1, 33.33, 66.67, 100.1],
        labels=['Right', 'Centre', 'Left'],
    )

    rows_data = []
    for player, grp in df.groupby('player_name'):
        total  = len(grp)
        left   = int((grp['_band'] == 'Left').sum())
        centre = int((grp['_band'] == 'Centre').sum())
        right  = int((grp['_band'] == 'Right').sum())
        suc    = int(grp['outcome'].eq(1).sum())
        fail   = int(grp['outcome'].eq(0).sum())
        shot_n = int(grp['led_to_shot'].fillna(False).sum()) if 'led_to_shot' in grp.columns else 0
        goal_n = int(grp['led_to_goal'].fillna(False).sum()) if 'led_to_goal' in grp.columns else 0
        rows_data.append({
            'player': player, 'total': total,
            'left': left, 'centre': centre, 'right': right,
            'suc': suc, 'fail': fail,
            'succ_pct': round(suc / max(total, 1) * 100),
            'shot_pct': round(shot_n / max(total, 1) * 100),
            'goal_pct': round(goal_n / max(total, 1) * 100),
        })

    rows_data.sort(key=lambda x: x['total'], reverse=True)
    rows_data = rows_data[:top_n]

    header = html.Tr([
        html.Th('Player', style={**_TH, 'textAlign': 'left'}),
        html.Th('#',      style=_TH),
        html.Th('L',      style=_TH),
        html.Th('C',      style=_TH),
        html.Th('R',      style=_TH),
        html.Th('Suc',    style=_TH),
        html.Th('Fail',   style=_TH),
        html.Th('Succ%',  style=_TH),
        html.Th('Shot%',  style=_TH),
        html.Th('Goal%',  style=_TH),
    ])
    table_rows = []
    for i, s in enumerate(rows_data):
        bg    = (COLORS.get('dark_tertiary', 'rgba(255,255,255,0.03)')
                 if i % 2 == 0 else 'transparent')
        short = s['player'].split()[-1] if s['player'] else '—'
        pct_color = (GOLD if s['succ_pct'] >= 70
                     else AWAY_COLOR if s['succ_pct'] < 40
                     else COLORS['text_primary'])
        shot_color = GOLD if s['shot_pct'] >= 40 else COLORS['text_primary']
        goal_color = GOLD if s['goal_pct'] >= 15 else COLORS['text_primary']
        table_rows.append(html.Tr([
            html.Td(short,                style=_NAME_TD),
            html.Td(str(s['total']),      style=_TD),
            html.Td(str(s['left']),       style=_TD),
            html.Td(str(s['centre']),     style=_TD),
            html.Td(str(s['right']),      style=_TD),
            html.Td(str(s['suc']),        style={**_TD, 'color': HOME_COLOR}),
            html.Td(str(s['fail']),       style={**_TD, 'color': AWAY_COLOR}),
            html.Td(f"{s['succ_pct']}%", style={**_TD, 'color': pct_color, 'fontWeight': '700'}),
            html.Td(f"{s['shot_pct']}%", style={**_TD, 'color': shot_color, 'fontWeight': '700'}),
            html.Td(f"{s['goal_pct']}%", style={**_TD, 'color': goal_color, 'fontWeight': '700'}),
        ], style={'backgroundColor': bg}))

    return [
        html.Div("L = left flank (y>67)  ·  C = centre  ·  R = right flank (y<33)", style={
            'color': COLORS['text_secondary'], 'fontSize': '0.55rem',
            'fontStyle': 'italic', 'marginBottom': '4px',
        }),
        html.Div(
            html.Table(
                [html.Thead(header), html.Tbody(table_rows)],
                style={'width': '100%', 'borderCollapse': 'collapse'},
            ),
            style={'overflowX': 'auto'},
        ),
    ]


# ---------------------------------------------------------------------------
# Shot zone definitions for the half-pitch zone map
# (key, label, x_min, x_max, y_min, y_max) — non-overlapping, covering full half
# ---------------------------------------------------------------------------
_SHOT_ZONE_DEFS = [
    ('long_range',   'Long\nRange',         50.0,  66.7,  0.0,        100.0),
    ('right_wing',   'Right\nWing',         66.7, 100.0,  0.0,        BOX_Y_MIN),
    ('r_halfspace',  'Right\nHalf-Space',   66.7,  83.0,  BOX_Y_MIN,  37.0),
    ('outside_cen',  'Outside\nBox',        66.7,  83.0,  37.0,       63.0),
    ('l_halfspace',  'Left\nHalf-Space',    66.7,  83.0,  63.0,       BOX_Y_MAX),
    ('left_wing',    'Left\nWing',          66.7, 100.0,  BOX_Y_MAX, 100.0),
    ('right_box',    'Right\nBox',          83.0, 100.0,  BOX_Y_MIN,  37.0),
    ('cen_penalty',  'Central\nBox',        83.0,  94.2,  37.0,       63.0),
    ('six_yard',     '6-Yard\nBox',         94.2, 100.0,  37.0,       63.0),
    ('left_box',     'Left\nBox',           83.0, 100.0,  63.0,       BOX_Y_MAX),
]


def _classify_shot_zone(x: float, y: float) -> str:
    if y < BOX_Y_MIN:  return 'right_wing'
    if y > BOX_Y_MAX:  return 'left_wing'
    if x < 66.7:       return 'long_range'
    if x < 83.0:
        if y < 37.0:   return 'r_halfspace'
        if y > 63.0:   return 'l_halfspace'
        return 'outside_cen'
    if y < 37.0:       return 'right_box'
    if y > 63.0:       return 'left_box'
    if x >= 94.2:      return 'six_yard'
    return 'cen_penalty'


def _opp_zone_img(opp_shots: pd.DataFrame) -> str:
    """Half-pitch zone map showing % of shots from each zone."""
    if opp_shots.empty:
        return ''
    shots = opp_shots.dropna(subset=['x', 'y'])
    if shots.empty:
        return ''

    # Count shots per zone
    counts = {z[0]: 0 for z in _SHOT_ZONE_DEFS}
    for _, row in shots.iterrows():
        counts[_classify_shot_zone(float(row['x']), float(row['y']))] += 1
    n_total = max(len(shots), 1)
    pcts = {k: v / n_total * 100 for k, v in counts.items()}
    max_pct = max(pcts.values()) if pcts else 1.0

    pitch = Pitch(
        pitch_type='opta', pitch_color=PITCH_BG, line_color=_PITCH_LINE_COLOR,
        linewidth=1.5, stripe=False, goal_type='box', half=True,
        pad_top=10, pad_bottom=4, pad_left=2, pad_right=4,
    )
    fig_mpl, ax = pitch.draw(figsize=(5, 4.5))

    for key, label, x0, x1, y0, y1 in _SHOT_ZONE_DEFS:
        pct = pcts.get(key, 0.0)
        alpha = 0.10 + 0.65 * (pct / max(max_pct, 0.01))

        ax.add_patch(Rectangle(
            (x0, y0), x1 - x0, y1 - y0,
            facecolor=COLORS['garnet'], alpha=alpha,
            edgecolor=(1, 1, 1, 0.3), linewidth=0.5, zorder=2,
        ))

        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        zone_w, zone_h = x1 - x0, y1 - y0
        small = zone_w < 12 or zone_h < 18
        fsize_pct = 5.5 if small else 7.5
        fsize_lbl = fsize_pct - 1.5

        ax.text(cx, cy + 2, f'{pct:.0f}%',
                ha='center', va='center',
                fontsize=fsize_pct, color='white', fontweight='bold', zorder=3)
        ax.text(cx, cy - 2, label,
                ha='center', va='top',
                fontsize=fsize_lbl, color='#cccccc', zorder=3,
                multialignment='center')

    # Direction of attack — styled box matching _add_attack_direction
    ax.annotate('→  Direction of Attack',
                xy=(75, 104), xycoords='data',
                ha='center', va='center',
                fontsize=7, color='white', fontweight='bold',
                annotation_clip=False, zorder=5,
                bbox=dict(
                    facecolor='#151932', edgecolor='#8899CC',
                    boxstyle='round,pad=0.4', linewidth=1,
                ))

    buf = io.BytesIO()
    fig_mpl.savefig(buf, format='png', dpi=130, bbox_inches='tight',
                    pad_inches=0.05, facecolor=PITCH_BG)
    buf.seek(0)
    result = base64.b64encode(buf.read()).decode()
    plt.close(fig_mpl)
    return result


def _opp_flank_fig(opp_att_events: pd.DataFrame) -> go.Figure:
    """
    Horizontal bar: opponent attacking event distribution by y-channel.

    Channels are from the opponent's coordinate frame (x > 50 = their att half):
      Low y  (< 33) = Opp left flank  / Barca's right side
      Mid y (33–67) = Central channel
      High y (> 67) = Opp right flank / Barca's left side
    """
    _empty = go.Figure()
    _empty.update_layout(
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor=PITCH_BG,
        height=180, margin=dict(l=10, r=10, t=10, b=10),
    )

    if opp_att_events.empty:
        return _empty

    att = opp_att_events[opp_att_events['x'] > 50].dropna(subset=['y'])
    if att.empty:
        return _empty

    left_n    = int((att['y'] < 33.33).sum())
    central_n = int(((att['y'] >= 33.33) & (att['y'] <= 66.67)).sum())
    right_n   = int((att['y'] > 66.67).sum())

    # Displayed top-to-bottom: Opp Right → Central → Opp Left
    channels = ['Opp Right / Barca Left', 'Central', 'Opp Left / Barca Right']
    counts   = [right_n, central_n, left_n]
    colors   = [AWAY_COLOR, GOLD, HOME_COLOR]

    fig = go.Figure(go.Bar(
        x=counts, y=channels,
        orientation='h',
        marker=dict(color=colors, line=dict(color=PITCH_BG, width=1)),
        text=[str(c) for c in counts],
        textposition='inside',
        textfont=dict(color='white', size=11),
        hovertemplate='%{y}: %{x} events<extra></extra>',
    ))
    fig.update_layout(
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(21,25,50,0.6)',
        height=180,
        margin=dict(l=10, r=10, t=10, b=10),
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False, fixedrange=True),
        yaxis=dict(
            showgrid=False, zeroline=False, fixedrange=True,
            tickfont=dict(color=COLORS['text_secondary'], size=10),
        ),
        showlegend=False,
        uirevision='ds-opp-flank',
    )
    return fig


# =============================================================================
# Public builders
# =============================================================================


def build_def_structure_skeleton() -> html.Div:
    events = get_all_events(CURRENT_SEASON)

    player_opts = []
    if not events.empty:
        bar = events[events['team_code'] == 'BAR']
        def_bar = bar[bar['event_type'].isin(_ALL_DEF_TYPES)]
        if 'player_name' in def_bar.columns:
            names = def_bar['player_name'].dropna().unique()
            player_opts = sorted(
                [{'label': n, 'value': n} for n in names],
                key=lambda d: d['label'],
            )

    return _build_our_defense_skeleton(player_opts)


def build_def_structure_tab(**_) -> dbc.Tabs:
    return build_def_structure_skeleton()


# =============================================================================
# Callbacks
# =============================================================================

def register_def_structure_callbacks(app) -> None:
    """Wire filter controls to charts for both Defensive Structure sub-tabs."""

    # ── Our Defensive Actions ─────────────────────────────────────────────────
    @app.callback(
        Output('ds-def-kpi',           'children'),
        Output('ds-def-pitch',         'figure'),
        Output('ds-def-heatmap',       'src'),
        Output('ds-def-table',         'children'),
        Output('ds-def-zone-donut',    'figure'),
        Output('ds-foul-map',          'figure'),
        Output('ds-foul-table',        'children'),
        Output('ds-def-flank-fig',     'figure'),
        Output('ds-opp-ft-fig',        'figure'),
        Output('ds-opp-ft-table',      'children'),
        Output('ds-opp-z14-fig',       'figure'),
        Output('ds-opp-z14-table',     'children'),
        Output('ds-opp-shot-map',      'figure'),
        Output('ds-opp-zone-donut',    'src'),
        Output('ds-gk-stats',          'children'),
        Input('ds-def-player',         'value'),
        Input('ds-def-outcome',        'value'),
        Input('ds-def-start-third',    'value'),
        Input('ds-def-bands',          'value'),
        Input('ds-def-h1-time',        'value'),
        Input('ds-def-h2-time',        'value'),
        Input('ds-def-action-type',    'value'),
        State('ta-competition-selector', 'value'),
        State('ta-venue-selector',       'value'),
        State('ta-selected-matches',     'data'),
        State('ta-match-data',           'data'),
    )
    def _update_our_defense(players, outcomes, start_thirds, bands,
                             h1_range, h2_range, action_types,
                             competition, venue, match_ids, match_data):

        def _empty():
            return ([], _skel_fig(540), _SKEL_SRC, [], _skel_fig(220), _skel_fig(420), [],
                    _skel_fig(180), _skel_fig(480), [], _skel_fig(480), [], _skel_fig(480), '', [])

        events = get_all_events(CURRENT_SEASON)
        if events.empty:
            return _empty()

        events = _apply_global_filters(events, competition, venue, match_ids, match_data)
        if events.empty:
            return _empty()

        bar     = events[events['team_code'] == 'BAR']
        bar_def = bar[bar['event_type'].isin(_ALL_DEF_TYPES)].dropna(subset=['x', 'y'])

        if action_types:
            bar_def = bar_def[bar_def['event_type'].isin(action_types)]

        _h1 = tuple(h1_range) if h1_range else (0, 50)
        _h2 = tuple(h2_range) if h2_range else (45, 100)
        bar_def_time = _apply_time_filter(bar_def, _h1, _h2)

        bar_def_filtered = PassMap.filter(
            bar_def_time,
            outcomes=outcomes,
            start_thirds=start_thirds,
            bands=bands,
            h1_range=_h1,
            h2_range=_h2,
        )
        if players and 'player_name' in bar_def_filtered.columns:
            bar_def_filtered = bar_def_filtered[bar_def_filtered['player_name'].isin(players)]

        bar_offsides = bar[bar['event_type'] == 'Offside provoked'].dropna(subset=['x', 'y'])

        opp       = events[events['team_code'] != 'BAR']
        opp_shots = opp[opp['event_type'].isin(_SHOT_TYPES)].dropna(subset=['x', 'y'])
        opp_time  = _apply_time_filter(opp, _h1, _h2)

        entries_ft  = _build_opp_entries(opp, 'final_third')
        entries_z14 = _build_opp_entries(opp, 'zone14')

        return (
            _def_kpi_children(bar_def, events),
            _def_pitch_fig(bar_def_filtered),
            _def_heatmap_src(bar_def_filtered),
            _def_player_table(bar_def, bar),
            _def_zone_donut_fig(bar_def),
            _offsides_only_fig(bar_offsides),
            _foul_player_table(bar),
            _opp_flank_fig(opp_time),
            _opp_entries_fig(entries_ft,  'final_third'),
            _opp_entries_table(entries_ft),
            _opp_entries_fig(entries_z14, 'zone14'),
            _opp_entries_table(entries_z14),
            _opp_shot_map_fig(opp_shots),
            f'data:image/png;base64,{_opp_zone_img(opp_shots)}',
            _gk_stats_children(opp_shots, bar),
        )

