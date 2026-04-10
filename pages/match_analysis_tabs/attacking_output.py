"""
attacking_output.py
===================
Attacking Output tab: shot maps, top shooters, final-third actions.
Sections: KPI Row (shooters + stat bars) | Shot Map | Final Third Actions
"""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
from dash import html, dcc
import dash_bootstrap_components as dbc

from utils.config import COLORS
from utils.data_utils import exclude_own_goals
from utils.xg_utils import add_xg_column
from page_utils.pitch_zones import BOX_X_MIN, BOX_Y_MIN, BOX_Y_MAX
from page_utils.event_filters import SHOT_TYPES as _SHOT_TYPES

from .shared import (
    build_legend_box,
    build_info_box,
    CARD_STYLE,
    section_header,
)
from page_utils.visualizations import (
    HOME_COLOR,
    AWAY_COLOR,
    GOLD,
    CHART_CONFIG,
    layout_config,
    add_vertical_half_pitch_background,
    VPITCH_AXIS_HALF,
)

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
# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------

_SI = ('N/A', '', 'nan', None)


def _count_from_box(shots: pd.DataFrame) -> int:
    """Count shots from inside the attacking penalty box (vectorised)."""
    if not {'x', 'y'}.issubset(shots.columns) or shots.empty:
        return 0
    x = pd.to_numeric(shots['x'], errors='coerce')
    y = pd.to_numeric(shots['y'], errors='coerce')
    return int(((x >= BOX_X_MIN) & (y >= BOX_Y_MIN) & (y <= BOX_Y_MAX)).sum())


def _get_shot_type(row) -> str:
    def _present(col):
        return str(row.get(col, 'N/A')) not in _SI
    if _present('Penalty'):        return 'Penalty'
    if _present('Diving Header'):  return 'Diving Header'
    if _present('Head'):           return 'Header'
    if _present('Overhead'):       return 'Overhead / Bicycle'
    if _present('Volley'):         return 'Volley'
    if _present('Half Volley'):    return 'Half Volley'
    if _present('Left footed'):    return 'Left foot'
    if _present('Right footed'):   return 'Right foot'
    return 'Shot'


def _compute(events: pd.DataFrame) -> dict:
    home_team = events['home_team'].iloc[0]
    away_team = events['away_team'].iloc[0]
    out = {}

    for pos, team in (('home', home_team), ('away', away_team)):
        te = events[events['team_position'] == pos]

        sorted_te = te.sort_values(['period_id', 'time_min']).reset_index(drop=True)
        prev_acts = [''] * len(sorted_te)
        for i in range(1, len(sorted_te)):
            pr        = sorted_te.iloc[i - 1]
            prev_type = str(pr.get('event_type', '') or '')
            prev_plr  = str(pr.get('player_name', '') or '').strip()
            if prev_type == 'Pass' and prev_plr:
                prev_acts[i] = f'Pass ({prev_plr})'
            elif prev_type in ('Take On', 'Carry') and prev_plr:
                prev_acts[i] = f'{prev_type} ({prev_plr})'
            else:
                prev_acts[i] = prev_type
        sorted_te['prev_action'] = prev_acts

        shots = exclude_own_goals(
            sorted_te[sorted_te['event_type'].isin(_SHOT_TYPES)].copy()
        )
        shots = add_xg_column(shots)
        goals = shots[shots['event_type'] == 'Goal']
        shots['shot_type'] = shots.apply(_get_shot_type, axis=1)

        # Key passes (intentional assists leading to any shot)
        if 'Intentional Assist' in sorted_te.columns:
            key_passes = sorted_te[
                (sorted_te['event_type'] == 'Pass') &
                (sorted_te['Intentional Assist'] == 'Si')
            ].copy()
        else:
            key_passes = pd.DataFrame()

        shooter_counts = (
            shots['player_name'].dropna().value_counts().head(5).reset_index()
        )
        shooter_counts.columns = ['Player', 'Shots']
        goal_counts = goals['player_name'].dropna().value_counts()
        shooter_counts['Goals'] = (
            shooter_counts['Player'].map(goal_counts).fillna(0).astype(int)
        )
        # Goal assists per player
        if not key_passes.empty and 'Assist' in key_passes.columns:
            assist_counts = key_passes[
                pd.to_numeric(key_passes['Assist'], errors='coerce') == 16
            ]['player_name'].dropna().value_counts()
        else:
            assist_counts = pd.Series(dtype=int)
        shooter_counts['Assists'] = (
            shooter_counts['Player'].map(assist_counts).fillna(0).astype(int)
        )
        if 'xg' in shots.columns:
            xg_per_player = shots.groupby('player_name')['xg'].sum().round(2)
            shooter_counts['xG'] = (
                shooter_counts['Player'].map(xg_per_player).fillna(0.0).round(2)
            )

        out[pos] = {
            'team':         team,
            'shots':        shots,
            'key_passes':   key_passes,
            'goals':        len(goals),
            'total_shots':  len(shots),
            'total_xg':     round(shots['xg'].sum(), 2) if 'xg' in shots.columns else None,
            'on_target':    len(te[te['event_type'] == 'Saved Shot']) + len(goals),
            'from_box':     _count_from_box(shots),
            'top_shooters': shooter_counts,
        }
    return out


# ---------------------------------------------------------------------------
# Per-half stats helpers
# ---------------------------------------------------------------------------

def _compute_team_stats(events: pd.DataFrame, pos: str) -> tuple[dict, dict, dict]:
    """Return (full, h1, h2) stat dicts for one team position."""
    def _stats(ev: pd.DataFrame) -> dict:
        te = ev[ev['team_position'] == pos]
        shots = add_xg_column(exclude_own_goals(te[te['event_type'].isin(_SHOT_TYPES)].copy()))
        goals = shots[shots['event_type'] == 'Goal']
        return {
            'shots':     len(shots),
            'on_target': len(te[te['event_type'] == 'Saved Shot']) + len(goals),
            'goals':     len(goals),
            'xg':        round(shots['xg'].sum(), 2) if 'xg' in shots.columns else None,
            'from_box':  _count_from_box(shots),
        }
    h1 = events[events['period_id'] == 1] if 'period_id' in events.columns else events.iloc[:0]
    h2 = events[events['period_id'] == 2] if 'period_id' in events.columns else events.iloc[:0]
    return _stats(events), _stats(h1), _stats(h2)


# ---------------------------------------------------------------------------
# UI helpers
# ---------------------------------------------------------------------------




def _team_stats_table(
    team_name: str, color: str,
    full: dict, h1: dict, h2: dict,
) -> html.Div:
    """Single-team stats table with Full / 1st Half / 2nd Half columns."""
    _METRICS = [
        ('Total Shots',     'shots'),
        ('Shots on Target', 'on_target'),
        ('Goals',           'goals'),
        ('xG',              'xg'),
        ('Shots from Box',  'from_box'),
    ]
    _col_style = {'textAlign': 'center', 'padding': '6px 12px',
                  'fontSize': '0.82rem', 'fontWeight': '600',
                  'color': COLORS['text_primary']}
    _hdr_style = {'textAlign': 'center', 'padding': '6px 12px',
                  'fontSize': '0.68rem', 'fontWeight': '700',
                  'color': COLORS['text_secondary'],
                  'textTransform': 'uppercase', 'letterSpacing': '0.06em',
                  'borderBottom': f'1px solid {COLORS["dark_border"]}'}
    _lbl_style = {'padding': '6px 12px', 'fontSize': '0.8rem',
                  'color': COLORS['text_secondary'], 'whiteSpace': 'nowrap'}

    header = html.Tr([
        html.Th('', style=_hdr_style),
        html.Th('Full', style=_hdr_style),
        html.Th('1st Half', style=_hdr_style),
        html.Th('2nd Half', style=_hdr_style),
    ])
    rows = []
    for i, (label, key) in enumerate(_METRICS):
        bg = COLORS.get('dark_tertiary', 'rgba(255,255,255,0.03)') if i % 2 == 0 else 'transparent'
        rows.append(html.Tr([
            html.Td(label, style=_lbl_style),
            html.Td(str(full.get(key, 0)), style=_col_style),
            html.Td(str(h1.get(key, 0)),   style=_col_style),
            html.Td(str(h2.get(key, 0)),   style=_col_style),
        ], style={'backgroundColor': bg}))

    return html.Div([
        html.Div(team_name, style={
            'color': color, 'fontWeight': '700', 'fontSize': '0.95rem',
            'marginBottom': '10px',
            'borderBottom': f'2px solid {color}',
            'paddingBottom': '6px',
        }),
        html.Table(
            [html.Thead(header), html.Tbody(rows)],
            style={'width': '100%', 'borderCollapse': 'collapse'},
        ),
    ], style=CARD_STYLE)


def _shot_map_fig(shots: pd.DataFrame, key_passes: pd.DataFrame,
                  team_color: str, team_name: str) -> go.Figure:
    fig = go.Figure()
    add_vertical_half_pitch_background(fig)

    _common = dict(
        **VPITCH_AXIS_HALF,
        height=500, margin=dict(l=10, r=10, t=44, b=20),
        title=dict(text=f'<b>{team_name}</b>', x=0.5,
                   font=dict(color=team_color, size=13)),
        annotations=[dict(x=0.98, y=0.97, xref='paper', yref='paper',
                          text='▲ Attacking Direction', showarrow=False,
                          font=dict(color='black', size=16, family='Arial'),
                          xanchor='right', yanchor='top',
                          bgcolor='rgba(255,255,255,0.7)', borderpad=3)],
    )
    if shots.empty or 'x' not in shots.columns or 'y' not in shots.columns:
        fig.update_layout(**layout_config(**_common))
        return fig

    # ── Assist arrows (drawn first so shots render on top) ───────────────────
    # Vertical pitch: fig_x = 100 - pitch_y  (flip so left-right is correct),
    #                 fig_y = pitch_x
    if not key_passes.empty and 'Pass End X' in key_passes.columns:
        kp = key_passes.copy()
        kp['Pass End X'] = pd.to_numeric(kp['Pass End X'], errors='coerce')
        kp['Pass End Y'] = pd.to_numeric(kp['Pass End Y'], errors='coerce')
        kp['x']         = pd.to_numeric(kp['x'],           errors='coerce')
        kp['y']         = pd.to_numeric(kp['y'],           errors='coerce')
        kp = kp.dropna(subset=['x', 'y', 'Pass End X', 'Pass End Y'])
        if not kp.empty:
            is_goal_assist = (
                pd.to_numeric(kp['Assist'], errors='coerce') == 16
                if 'Assist' in kp.columns
                else pd.Series(False, index=kp.index)
            )
            for is_goal, grp in kp.groupby(is_goal_assist):
                color   = GOLD if is_goal else 'rgba(220,220,220,0.55)'
                width   = 3.0  if is_goal else 2.0
                opacity = 0.95 if is_goal else 0.65
                label   = 'Goal Assist' if is_goal else 'Key Pass'
                # Lines
                xs_l, ys_l = [], []
                for _, row in grp.iterrows():
                    xs_l.extend([100 - float(row['y']), 100 - float(row['Pass End Y']), None])
                    ys_l.extend([float(row['x']),            float(row['Pass End X']),  None])
                fig.add_trace(go.Scatter(
                    x=xs_l, y=ys_l, mode='lines',
                    line=dict(color=color, width=width),
                    opacity=opacity, showlegend=False, hoverinfo='skip',
                ))
                # Endpoint dot (no hover)
                fig.add_trace(go.Scatter(
                    x=(100 - grp['Pass End Y']).tolist(),
                    y=grp['Pass End X'].tolist(),
                    mode='markers', name=label,
                    marker=dict(color=color, size=9 if is_goal else 7,
                                symbol='circle', opacity=opacity,
                                line=dict(color='white', width=1.5 if is_goal else 1)),
                    showlegend=True, hoverinfo='skip',
                ))

    for outcome, group in shots.groupby('event_type'):
        valid = group[group['x'].notna() & group['y'].notna()].copy()
        fig_x = (100 - valid['y']).tolist()
        fig_y = valid['x'].tolist()
        if not fig_x:
            continue
        player_names = valid['player_name'].fillna('Unknown').tolist()
        times        = valid['time_min'].fillna(0).astype(int).tolist()
        prev_acts    = (valid['prev_action'].fillna('—').tolist()
                        if 'prev_action' in valid.columns else ['—'] * len(valid))
        shot_types   = (valid['shot_type'].fillna('Shot').tolist()
                        if 'shot_type' in valid.columns else ['Shot'] * len(valid))
        og_flags     = (
            [' (own goal)' if v == 'Si' else '' for v in valid['own goal'].fillna('')]
            if 'own goal' in valid.columns else [''] * len(valid)
        )
        xg_vals = (valid['xg'].fillna(0).tolist()
                   if 'xg' in valid.columns else [0] * len(valid))
        # Size goals at 16, other shots scaled by xG (min 8, max 18)
        if outcome == 'Goal':
            sizes = [16] * len(valid)
        else:
            sizes = [max(8, min(18, int(v * 60 + 8))) for v in xg_vals]
        fig.add_trace(go.Scatter(
            x=fig_x, y=fig_y, mode='markers', name=outcome,
            marker=dict(color=_OUTCOME_COLOR.get(outcome, team_color),
                        symbol=_OUTCOME_SYMBOL.get(outcome, 'circle'),
                        size=sizes,
                        opacity=0.88, line=dict(color='white', width=1)),
            customdata=[[p, t, a, st, og, xg] for p, t, a, st, og, xg
                        in zip(player_names, times, prev_acts, shot_types, og_flags, xg_vals)],
            hovertemplate=(
                '<b>%{customdata[0]}%{customdata[4]}</b><br>'
                "%{customdata[1]}' | %{customdata[3]}<br>"
                'xG: %{customdata[5]:.2f}<br>'
                'Preceding: %{customdata[2]}<extra></extra>'
            ),
        ))

    fig.update_layout(**layout_config(
        **_common,
        hoverlabel=dict(bgcolor='#1A1D2E', font_color='white', font_size=12),
        legend=dict(
            x=0.01, y=0.01,
            xanchor='left', yanchor='bottom',
            orientation='v',
            font=dict(color=COLORS['text_primary'], size=10),
            bgcolor='rgba(26,29,46,0.80)',
            bordercolor=COLORS.get('dark_border', 'rgba(255,255,255,0.15)'),
            borderwidth=1,
        ),
    ))
    return fig


def _player_table(df: pd.DataFrame, color: str) -> html.Div:
    if df.empty:
        return html.Div("No data", style={'color': COLORS['text_secondary'], 'fontSize': '0.8rem'})
    header_cells = [
        html.Th(col, style={
            'color': COLORS['text_secondary'], 'fontSize': '0.7rem',
            'fontWeight': '600', 'padding': '6px 10px',
            'borderBottom': f'1px solid {COLORS["dark_border"]}',
            'textTransform': 'uppercase', 'letterSpacing': '0.04em',
        }) for col in df.columns
    ]
    rows = []
    for i, (_, row) in enumerate(df.iterrows()):
        bg = COLORS['dark_tertiary'] if i % 2 == 0 else 'transparent'
        cells = [
            html.Td(str(val), style={
                'color': color if j == 0 else COLORS['text_primary'],
                'fontSize': '0.82rem', 'padding': '5px 10px',
                'fontWeight': '600' if j == 0 else 'normal',
            }) for j, val in enumerate(row)
        ]
        rows.append(html.Tr(cells, style={'backgroundColor': bg}))
    return html.Table([html.Thead(html.Tr(header_cells)), html.Tbody(rows)],
                      style={'width': '100%', 'borderCollapse': 'collapse'})


# ---------------------------------------------------------------------------
# Tab builder
# ---------------------------------------------------------------------------

def build_attacking_output_tab(events: pd.DataFrame, **_) -> html.Div:
    if events.empty:
        return html.P("No event data.", style={"color": COLORS["text_secondary"]})

    # Pre-compute xG for all shot rows once.  Every helper that calls
    # add_xg_column() on a slice of these events will detect the 'xg'
    # column already present and return immediately — reducing model
    # inference from ~7 calls down to 1.
    _shot_mask = events['event_type'].isin(_SHOT_TYPES)
    if 'xg' not in events.columns and _shot_mask.any():
        events = events.copy()
        _shots_enriched = add_xg_column(events.loc[_shot_mask].copy())
        if 'xg' in _shots_enriched.columns:
            events.loc[_shot_mask, 'xg'] = _shots_enriched['xg'].values

    d = _compute(events)
    hs, as_ = d['home'], d['away']

    # ── Per-half stats ────────────────────────────────────────────────────
    h_full, h_h1, h_h2 = _compute_team_stats(events, 'home')
    a_full, a_h1, a_h2 = _compute_team_stats(events, 'away')

    # ── Section 1: Match Statistics ───────────────────────────────────────
    stats_section = html.Div([
        section_header('Match Statistics'),
        build_info_box('Shots · Shots on Target · Goals · Shots from Box — split by half'),
        dbc.Row([
            dbc.Col(_team_stats_table(hs['team'], HOME_COLOR, h_full, h_h1, h_h2),
                    md=6, className='mb-3'),
            dbc.Col(_team_stats_table(as_['team'], AWAY_COLOR, a_full, a_h1, a_h2),
                    md=6, className='mb-3'),
        ], className='g-3'),
    ], style={'marginBottom': '36px'})

    # ── Section 2: Shot Maps ──────────────────────────────────────────────
    shot_map_section = html.Div([
        section_header('Shot Map'),
        build_legend_box([
            ('★', 'Goal',    '#51cf66'),
            ('●', 'Saved',   '#339af0'),
            ('✕', 'Miss',    '#ff6b6b'),
            ('◆', 'Post',    '#ffd43b'),
            ('■', 'Blocked', '#cc5de8'),
        ]),
        dbc.Row([
            dbc.Col(dcc.Graph(figure=_shot_map_fig(hs['shots'],  hs.get('key_passes',  pd.DataFrame()), HOME_COLOR, hs['team']),
                              config=CHART_CONFIG), md=6, className='mb-3'),
            dbc.Col(dcc.Graph(figure=_shot_map_fig(as_['shots'], as_.get('key_passes', pd.DataFrame()), AWAY_COLOR, as_['team']),
                              config=CHART_CONFIG), md=6, className='mb-3'),
        ], className='g-2'),
    ], style={'marginBottom': '36px'})

    # ── Section 3: Top Performers ─────────────────────────────────────────
    def _shooter_card(data, color):
        return html.Div([
            html.Div(data['team'], style={
                'color': color, 'fontWeight': '700', 'fontSize': '0.9rem',
                'marginBottom': '10px',
                'borderBottom': f'2px solid {color}', 'paddingBottom': '6px',
            }),
            _player_table(data['top_shooters'], color),
        ], style=CARD_STYLE)

    top_performers_section = html.Div([
        section_header('Top Performers', 'Top 5 players by shot attempts'),
        dbc.Row([
            dbc.Col(_shooter_card(hs, HOME_COLOR),  md=6, className='mb-3'),
            dbc.Col(_shooter_card(as_, AWAY_COLOR), md=6, className='mb-3'),
        ], className='g-3'),
    ])

    return html.Div(
        [stats_section, shot_map_section, top_performers_section],
        style={'marginTop': '16px'},
    )
