"""
goalkeeping.py
==============
Goalkeeping tab: match stats (TV-style with half breakdown), goal mouth
visualisation, shot map with trajectory arrows, interactive GK pass map.

Half filter and GK selector both affect all plots.
Match statistics table always shows full-match totals.

Multiple-GK support
-------------------
When a team used more than one goalkeeper the statistics table gains a column
per GK.  The plots area gains a per-team GK selector dropdown:

  All  |  GK1 name  |  GK2 name  …

*All*  → combined shots / passes in a single plot (original layout).
*GKn*  → only that goalkeeper's shots / passes.

The half-filter and GK-filter are independent and compose: e.g. "1st Half +
GK2" shows only GK2's shots that occurred in the first half.
"""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
from dash import html, dcc, ctx
from dash.dependencies import Input, Output, State
import dash_bootstrap_components as dbc

from utils.config import COLORS
from utils.data_utils import get_match_events, count_goals, exclude_own_goals
from utils.xg_utils import add_xg_column

from .shared import (
    CARD_STYLE,
    section_header,
)
from page_utils.visualizations import (
    HOME_COLOR,
    AWAY_COLOR,
    GOLD,
    CHART_CONFIG,
    layout_config,
    add_pitch_background,
    PITCH_AXIS_FULL,
    add_vertical_half_pitch_background,
    VPITCH_AXIS_HALF,
)
from page_utils.event_filters import SHOT_TYPES as _SHOT_TYPES

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_SAVE_COLOR = '#51cf66'
_GOAL_COLOR = '#ff6b6b'
_MISS_COLOR = '#868e96'

# Goal Mouth Y (qualifier 102): raw post positions after 100-y flip ≈ 44.5 / 55.5.
# To make the goal frame visually proportionate we stretch the x-axis 2.5× around the
# goal centre (50).  _GOAL_LEFT / _GOAL_RIGHT are the resulting *display* coordinates;
# the same factor (_GM_X_SCALE) is applied to every shot x so the map stays consistent.
# Goal Mouth Z (qualifier 103) is NOT stretched — empirical crossbar ≈ 38 (max saves
# reach ~35, crossbar post hits ~40).
_GM_CENTER  = 50.0
_GM_X_SCALE = 2.5
_GOAL_LEFT  = _GM_CENTER + (44.5 - _GM_CENTER) * _GM_X_SCALE   # 36.25
_GOAL_RIGHT = _GM_CENTER + (55.5 - _GM_CENTER) * _GM_X_SCALE   # 63.75
_CROSSBAR_Z = 38.0
_GM_Y_COL   = 'Goal Mouth Y Coordinate'
_GM_Z_COL   = 'Goal Mouth Z Coordinate'

_OUTCOME_COLOR = {
    'Goal':         _GOAL_COLOR,
    'Saved Shot':   _SAVE_COLOR,
    'Post':         '#ffd43b',
    'Blocked Shot': '#cc5de8',
    'Miss':         _MISS_COLOR,
}
_OUTCOME_SYMBOL = {
    'Goal':         'star',
    'Saved Shot':   'circle',
    'Post':         'diamond',
    'Blocked Shot': 'square',
    'Miss':         'x',
}

_BTN_BASE   = {'borderRadius': '6px', 'padding': '5px 14px', 'cursor': 'pointer',
               'fontSize': '0.85rem', 'border': f'1px solid {COLORS["dark_border"]}'}
_BTN_ACTIVE = {**_BTN_BASE, 'backgroundColor': GOLD, 'color': '#1A1D2E',
               'border': f'1px solid {GOLD}', 'fontWeight': '600'}
_BTN_IDLE   = {**_BTN_BASE, 'backgroundColor': COLORS['dark_secondary'],
               'color': COLORS['text_primary']}

# Players whose average x is below this threshold qualify as GK-zone candidates
_GK_X_THRESHOLD = 20


# ---------------------------------------------------------------------------
# GK identification
# ---------------------------------------------------------------------------

def _identify_gks(te_gk: pd.DataFrame) -> list:
    """Return GK player names sorted by first event time.

    Always includes the player with the lowest average x (primary GK).
    Any additional player also found in the GK zone (avg x < _GK_X_THRESHOLD)
    is treated as a replacement GK.
    """
    if 'player_name' not in te_gk.columns or 'x' not in te_gk.columns:
        return []
    avg_x = (
        te_gk.dropna(subset=['player_name', 'x'])
        .groupby('player_name')['x'].mean()
        .sort_values()
    )
    if avg_x.empty:
        return []
    primary    = avg_x.index[0]
    candidates = avg_x[avg_x < _GK_X_THRESHOLD].index.tolist()
    if primary not in candidates:
        candidates = [primary] + candidates
    if 'time_min' in te_gk.columns and len(candidates) > 1:
        first_t: dict = {}
        for n in candidates:
            t = pd.to_numeric(
                te_gk.loc[te_gk['player_name'] == n, 'time_min'], errors='coerce'
            ).dropna()
            first_t[n] = float(t.min()) if not t.empty else 999.0
        candidates.sort(key=lambda n: first_t[n])
    return candidates


def _gk_boundaries(gk_names: list, te_gk: pd.DataFrame) -> list:
    """Return handoff minutes between consecutive GKs (midpoint heuristic).
    Returns [] for a single GK or when no time data is available.
    """
    if len(gk_names) <= 1 or 'time_min' not in te_gk.columns:
        return []
    last_t:  dict = {}
    first_t: dict = {}
    for n in gk_names:
        t = pd.to_numeric(
            te_gk.loc[te_gk['player_name'] == n, 'time_min'], errors='coerce'
        ).dropna()
        if not t.empty:
            first_t[n] = float(t.min())
            last_t[n]  = float(t.max())
    return [
        (last_t.get(gk_names[i], 45.0) + first_t.get(gk_names[i + 1], 46.0)) / 2
        for i in range(len(gk_names) - 1)
    ]


# ---------------------------------------------------------------------------
# Data computation
# ---------------------------------------------------------------------------

def _compute(events: pd.DataFrame) -> dict:
    home_team = events['home_team'].iloc[0]
    away_team = events['away_team'].iloc[0]

    all_goals = events[events['event_type'] == 'Goal']
    home_goals_total, away_goals_total = count_goals(all_goals)

    out = {}

    for gk_pos, opp_pos, gk_team in (
        ('home', 'away', home_team),
        ('away', 'home', away_team),
    ):
        te_gk  = events[events['team_position'] == gk_pos]
        te_opp = events[events['team_position'] == opp_pos]

        opp_shots = exclude_own_goals(
            te_opp[te_opp['event_type'].isin(_SHOT_TYPES)].copy()
        )

        gk_goals_df = te_gk[te_gk['event_type'] == 'Goal'].copy()
        if 'own goal' in gk_goals_df.columns:
            own_ogs = gk_goals_df[gk_goals_df['own goal'] == 'Si'].copy()
        else:
            own_ogs = gk_goals_df.iloc[:0]
        if not own_ogs.empty:
            if 'x' in own_ogs.columns:
                own_ogs['x'] = 100 - pd.to_numeric(own_ogs['x'], errors='coerce')
            shots_faced_all = pd.concat([opp_shots, own_ogs], ignore_index=True)
        else:
            shots_faced_all = opp_shots

        saves_total      = len(te_opp[te_opp['event_type'] == 'Saved Shot'])
        goals_conc_total = away_goals_total if gk_pos == 'home' else home_goals_total
        sot_total        = saves_total + goals_conc_total
        save_pct_total   = round(saves_total / sot_total * 100, 1) if sot_total > 0 else 0.0

        gk_names   = _identify_gks(te_gk)
        boundaries = _gk_boundaries(gk_names, te_gk)

        def _in_range(df: pd.DataFrame, t0: float, t1):
            if 'time_min' not in df.columns or not boundaries:
                return df
            t    = pd.to_numeric(df['time_min'], errors='coerce')
            mask = t >= t0
            if t1 is not None:
                mask &= (t < t1)
            return df[mask]

        gk_list: list = []
        for i, name in enumerate(gk_names):
            t0: float = 0.0 if i == 0 else boundaries[i - 1]
            t1        = boundaries[i] if i < len(boundaries) else None

            gk_shots  = _in_range(shots_faced_all, t0, t1)
            saved_in  = _in_range(te_opp[te_opp['event_type'] == 'Saved Shot'], t0, t1)
            goals_evt = _in_range(events[events['event_type'] == 'Goal'], t0, t1)
            hg, ag    = count_goals(goals_evt)
            gk_goals  = ag if gk_pos == 'home' else hg
            gk_saves  = len(saved_in)
            gk_sot    = gk_saves + gk_goals
            gk_sv_pct = round(gk_saves / gk_sot * 100, 1) if gk_sot > 0 else 0.0

            gk_evts   = te_gk[te_gk['player_name'] == name]
            passes    = gk_evts[gk_evts['event_type'] == 'Pass'].copy()
            passes_df = (
                passes
                if (not passes.empty
                    and 'Pass End X' in passes.columns
                    and 'Pass End Y' in passes.columns)
                else pd.DataFrame()
            )

            t_label = ''
            if boundaries:
                t_label = f"{int(t0)}'–{int(t1)}'" if t1 is not None else f"{int(t0)}'–FT"

            gk_list.append({
                'name':            name,
                'shots_faced':     gk_shots,
                'gk_passes_df':    passes_df,
                'total_shots':     len(gk_shots),
                'shots_on_target': gk_sot,
                'saves':           gk_saves,
                'goals_conceded':  gk_goals,
                'save_pct':        gk_sv_pct,
                'xg_against':      round(add_xg_column(gk_shots)['xg'].sum(), 2)
                                   if not gk_shots.empty else 0.0,
                'time_label':      t_label,
            })

        xga_total = round(add_xg_column(shots_faced_all)['xg'].sum(), 2) \
            if not shots_faced_all.empty else 0.0

        if not gk_list:
            gk_list = [{
                'name':            '—',
                'shots_faced':     shots_faced_all,
                'gk_passes_df':    pd.DataFrame(),
                'total_shots':     len(shots_faced_all),
                'shots_on_target': sot_total,
                'saves':           saves_total,
                'goals_conceded':  goals_conc_total,
                'save_pct':        save_pct_total,
                'xg_against':      xga_total,
                'time_label':      '',
            }]

        out[gk_pos] = {
            'team':             gk_team,
            'total_shots':      len(shots_faced_all),
            'shots_on_target':  sot_total,
            'saves':            saves_total,
            'goals_conceded':   goals_conc_total,
            'save_pct':         save_pct_total,
            'xg_against':       xga_total,
            'gk_name':          gk_list[0]['name'],
            'opp_shots_df':     shots_faced_all,
            'gk_passes_df':     gk_list[0]['gk_passes_df'],
            'gk_list':          gk_list,
        }

    return out


def _half_stats(events: pd.DataFrame, gk_pos: str, opp_pos: str) -> dict:
    te_opp = events[events['team_position'] == opp_pos]
    saved  = te_opp[te_opp['event_type'] == 'Saved Shot']
    half_goals = events[events['event_type'] == 'Goal']
    hg, ag     = count_goals(half_goals)
    goals_conc = ag if gk_pos == 'home' else hg
    shots      = exclude_own_goals(te_opp[te_opp['event_type'].isin(_SHOT_TYPES)].copy())
    sot = len(saved) + goals_conc
    return {
        'total_shots':      len(shots),
        'shots_on_target':  sot,
        'saves':            len(saved),
        'goals_conceded':   goals_conc,
        'save_pct':         round(len(saved) / sot * 100, 1) if sot > 0 else 0.0,
        'xg_against':       round(add_xg_column(shots)['xg'].sum(), 2) if not shots.empty else 0.0,
    }


# ---------------------------------------------------------------------------
# Plot data helpers (resolve what to show based on GK filter)
# ---------------------------------------------------------------------------

def _team_shots(team_data: dict, gk_filter: str) -> pd.DataFrame:
    """Shots to display: all combined, or a single GK's subset."""
    if gk_filter in ('all', None, ''):
        return team_data['opp_shots_df']
    try:
        idx = int(gk_filter)
        if 0 <= idx < len(team_data['gk_list']):
            return team_data['gk_list'][idx]['shots_faced']
    except (ValueError, IndexError):
        pass
    return team_data['opp_shots_df']


def _team_passes(team_data: dict, gk_filter: str) -> tuple:
    """(passes_df, gk_name_label) for the pass map."""
    if gk_filter in ('all', None, ''):
        frames = [gk['gk_passes_df'] for gk in team_data['gk_list']
                  if not gk['gk_passes_df'].empty]
        combined = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
        return combined, 'All GKs'
    try:
        idx = int(gk_filter)
        if 0 <= idx < len(team_data['gk_list']):
            gk = team_data['gk_list'][idx]
            return gk['gk_passes_df'], gk['name']
    except (ValueError, IndexError):
        pass
    return team_data['gk_passes_df'], team_data['gk_name']


def _plot_title(team_data: dict, gk_filter: str) -> str:
    """Display label used as plot title / goal mouth title."""
    if gk_filter in ('all', None, ''):
        return team_data['team']
    try:
        idx = int(gk_filter)
        if 0 <= idx < len(team_data['gk_list']):
            gk = team_data['gk_list'][idx]
            label = f"{team_data['team']}: {gk['name']}"
            if gk['time_label']:
                label += f" ({gk['time_label']})"
            return label
    except (ValueError, IndexError):
        pass
    return team_data['team']


# ---------------------------------------------------------------------------
# Match statistics tables
# ---------------------------------------------------------------------------

def _gk_stats_table(team_name: str, color: str, gk_name: str,
                    full: dict, h1: dict, h2: dict) -> html.Div:
    """Single-GK stats: Full / 1st Half / 2nd Half columns."""
    _METRICS = [
        ('Shots Faced',     'total_shots'),
        ('Shots on Target', 'shots_on_target'),
        ('Saves',           'saves'),
        ('Goals Conceded',  'goals_conceded'),
        ('xGA',             'xg_against'),
        ('Save %',          'save_pct'),
    ]
    _col = {'textAlign': 'center', 'padding': '6px 12px',
            'fontSize': '0.82rem', 'fontWeight': '600', 'color': COLORS['text_primary']}
    _hdr = {'textAlign': 'center', 'padding': '6px 12px',
            'fontSize': '0.68rem', 'fontWeight': '700',
            'color': COLORS['text_secondary'],
            'textTransform': 'uppercase', 'letterSpacing': '0.06em',
            'borderBottom': f'1px solid {COLORS["dark_border"]}'}
    _lbl = {'padding': '6px 12px', 'fontSize': '0.8rem',
            'color': COLORS['text_secondary'], 'whiteSpace': 'nowrap'}

    def _fmt(key, d):
        v = d.get(key, 0)
        if key == 'save_pct':   return f"{v:.1f}%"
        if key == 'xg_against': return f"{v:.2f}"
        return str(int(v))

    header = html.Tr([
        html.Th('', style=_hdr),
        html.Th('Full', style=_hdr),
        html.Th('1st Half', style=_hdr),
        html.Th('2nd Half', style=_hdr),
    ])
    rows = []
    for i, (label, key) in enumerate(_METRICS):
        bg = COLORS.get('dark_tertiary', 'rgba(255,255,255,0.03)') if i % 2 == 0 else 'transparent'
        rows.append(html.Tr([
            html.Td(label, style=_lbl),
            html.Td(_fmt(key, full), style=_col),
            html.Td(_fmt(key, h1),   style=_col),
            html.Td(_fmt(key, h2),   style=_col),
        ], style={'backgroundColor': bg}))

    return html.Div([
        html.Div(team_name, style={
            'color': color, 'fontWeight': '700', 'fontSize': '0.95rem',
            'marginBottom': '4px', 'borderBottom': f'2px solid {color}',
            'paddingBottom': '6px',
        }),
        html.Div(f"GK: {gk_name}", style={
            'color': COLORS['text_secondary'], 'fontSize': '0.82rem',
            'marginBottom': '10px',
        }),
        html.Table([html.Thead(header), html.Tbody(rows)],
                   style={'width': '100%', 'borderCollapse': 'collapse'}),
    ], style=CARD_STYLE)


def _gk_stats_table_multi(team_name: str, color: str, gk_list: list) -> html.Div:
    """Multi-GK stats: one column per GK (independent of the plot filter)."""
    _METRICS = [
        ('Shots Faced',     'total_shots'),
        ('Shots on Target', 'shots_on_target'),
        ('Saves',           'saves'),
        ('Goals Conceded',  'goals_conceded'),
        ('xGA',             'xg_against'),
        ('Save %',          'save_pct'),
    ]
    _col = {'textAlign': 'center', 'padding': '6px 12px',
            'fontSize': '0.82rem', 'fontWeight': '600', 'color': COLORS['text_primary']}
    _hdr = {'textAlign': 'center', 'padding': '6px 12px',
            'fontSize': '0.68rem', 'fontWeight': '700',
            'color': COLORS['text_secondary'],
            'textTransform': 'uppercase', 'letterSpacing': '0.06em',
            'borderBottom': f'1px solid {COLORS["dark_border"]}'}
    _lbl = {'padding': '6px 12px', 'fontSize': '0.8rem',
            'color': COLORS['text_secondary'], 'whiteSpace': 'nowrap'}

    def _fmt(key, d):
        v = d.get(key, 0)
        if key == 'save_pct':   return f"{v:.1f}%"
        if key == 'xg_against': return f"{v:.2f}"
        return str(int(v))

    gk_headers = [html.Th('', style=_hdr)]
    for gk in gk_list:
        gk_headers.append(html.Th(
            html.Div([
                html.Div(gk['name'],       style={'fontSize': '0.72rem', 'fontWeight': '700',
                                                   'color': COLORS['text_primary']}),
                html.Div(gk['time_label'], style={'fontSize': '0.62rem',
                                                   'color': COLORS['text_secondary']}),
            ]),
            style=_hdr,
        ))

    rows = []
    for i, (label, key) in enumerate(_METRICS):
        bg = COLORS.get('dark_tertiary', 'rgba(255,255,255,0.03)') if i % 2 == 0 else 'transparent'
        rows.append(html.Tr(
            [html.Td(label, style=_lbl)] + [html.Td(_fmt(key, gk), style=_col) for gk in gk_list],
            style={'backgroundColor': bg},
        ))

    return html.Div([
        html.Div(team_name, style={
            'color': color, 'fontWeight': '700', 'fontSize': '0.95rem',
            'marginBottom': '10px', 'borderBottom': f'2px solid {color}',
            'paddingBottom': '6px',
        }),
        html.Table([html.Thead(html.Tr(gk_headers)), html.Tbody(rows)],
                   style={'width': '100%', 'borderCollapse': 'collapse'}),
    ], style=CARD_STYLE)


def _match_stats_section(hs: dict, as_: dict,
                          h1_hs: dict, h2_hs: dict,
                          h1_as: dict, h2_as: dict) -> html.Div:
    def _block(td: dict, color: str, h1: dict, h2: dict) -> html.Div:
        gk_list = td['gk_list']
        if len(gk_list) == 1:
            full = {k: td[k] for k in ('total_shots', 'shots_on_target',
                                        'saves', 'goals_conceded', 'xg_against', 'save_pct')}
            return _gk_stats_table(td['team'], color, gk_list[0]['name'], full, h1, h2)
        return _gk_stats_table_multi(td['team'], color, gk_list)

    return html.Div([
        section_header('GK Statistics'),
        dbc.Row([
            dbc.Col(_block(hs, HOME_COLOR, h1_hs, h2_hs), md=6, className='mb-3'),
            dbc.Col(_block(as_, AWAY_COLOR, h1_as, h2_as), md=6, className='mb-3'),
        ], className='g-3'),
    ], style={'marginBottom': '36px'})


# ---------------------------------------------------------------------------
# Goal mouth visualisation
# ---------------------------------------------------------------------------

def _goal_mouth_viz(opp_shots_df: pd.DataFrame,
                    gk_team_color: str, gk_team: str) -> dcc.Graph:
    POST_W = 0.7
    shapes = [
        dict(type='rect', x0=_GOAL_LEFT, x1=_GOAL_RIGHT, y0=0, y1=_CROSSBAR_Z,
             fillcolor='rgba(255,255,255,0.07)', line=dict(width=0)),
        dict(type='rect', x0=_GOAL_LEFT - POST_W, x1=_GOAL_LEFT,
             y0=0, y1=_CROSSBAR_Z + POST_W, fillcolor='white', line=dict(width=0)),
        dict(type='rect', x0=_GOAL_RIGHT, x1=_GOAL_RIGHT + POST_W,
             y0=0, y1=_CROSSBAR_Z + POST_W, fillcolor='white', line=dict(width=0)),
        dict(type='rect', x0=_GOAL_LEFT - POST_W, x1=_GOAL_RIGHT + POST_W,
             y0=_CROSSBAR_Z, y1=_CROSSBAR_Z + POST_W, fillcolor='white', line=dict(width=0)),
        dict(type='line', x0=20, x1=80, y0=0, y1=0,
             line=dict(color='rgba(255,255,255,0.25)', width=1, dash='dot')),
        *[dict(type='line', x0=v, x1=v, y0=0, y1=_CROSSBAR_Z,
               line=dict(color='rgba(255,255,255,0.07)', width=1))
          for v in [43.0, 46.5, 50.0, 53.5, 57.0]],
        *[dict(type='line', x0=_GOAL_LEFT, x1=_GOAL_RIGHT, y0=h, y1=h,
               line=dict(color='rgba(255,255,255,0.07)', width=1))
          for h in [13, 25]],
    ]
    _STYLE = [
        ('Goal',         _GOAL_COLOR, 'star',    18),
        ('Saved Shot',   _SAVE_COLOR, 'circle',  15),
        ('Post',         '#ffd43b',   'diamond', 15),
        ('Blocked Shot', '#cc5de8',   'square',  13),
        ('Miss',         _MISS_COLOR, 'x',       13),
    ]

    fig = go.Figure()

    if (not opp_shots_df.empty
            and _GM_Y_COL in opp_shots_df.columns
            and _GM_Z_COL in opp_shots_df.columns):
        for outcome, color, symbol, size in _STYLE:
            grp = opp_shots_df[opp_shots_df['event_type'] == outcome].copy()
            if grp.empty:
                continue
            grp[_GM_Y_COL] = pd.to_numeric(grp[_GM_Y_COL], errors='coerce')
            grp[_GM_Z_COL] = pd.to_numeric(grp[_GM_Z_COL], errors='coerce')
            grp = grp.dropna(subset=[_GM_Y_COL, _GM_Z_COL])
            if grp.empty:
                continue
            names    = grp['player_name'].fillna('Unknown').tolist() if 'player_name' in grp.columns else [''] * len(grp)
            mins     = grp['time_min'].fillna('?').astype(str).tolist() if 'time_min' in grp.columns else ['?'] * len(grp)
            og_flags = (
                [' (OG)' if v == 'Si' else '' for v in grp['own goal'].fillna('')]
                if 'own goal' in grp.columns else [''] * len(grp)
            )
            x_raw = 100 - grp[_GM_Y_COL]
            x_disp = (_GM_CENTER + (x_raw - _GM_CENTER) * _GM_X_SCALE).tolist()
            fig.add_trace(go.Scatter(
                x=x_disp, y=grp[_GM_Z_COL].tolist(),
                mode='markers', name=outcome,
                marker=dict(color=color, symbol=symbol, size=size, opacity=0.92,
                            line=dict(color='white', width=1)),
                customdata=list(zip(names, mins, og_flags)),
                hovertemplate=(
                    '<b>' + outcome + '%{customdata[2]}</b><br>'
                    'Player: %{customdata[0]}<br>'
                    "Min: %{customdata[1]}'<extra></extra>"
                ),
            ))

    fig.update_layout(
        shapes=shapes,
        xaxis=dict(range=[20, 80], showgrid=False, zeroline=False, visible=False),
        yaxis=dict(range=[-4, 55], showgrid=False, zeroline=False, visible=False),
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='#0d1a35',
        margin=dict(l=10, r=10, t=40, b=60), height=430,
        font=dict(color=COLORS['text_primary']),
        legend=dict(orientation='h', y=-0.14, x=0.5, xanchor='center',
                    font=dict(color=COLORS['text_primary'], size=10),
                    bgcolor='rgba(0,0,0,0)'),
        title=dict(text=f'<b>Goal Mouth — {gk_team} GK</b>', x=0.5,
                   font=dict(color=gk_team_color, size=12)),
    )
    return dcc.Graph(figure=fig, config=CHART_CONFIG)


# ---------------------------------------------------------------------------
# Shot map
# ---------------------------------------------------------------------------

def _shot_map_fig(shots: pd.DataFrame, team_color: str, team_name: str) -> go.Figure:
    fig = go.Figure()
    add_vertical_half_pitch_background(fig)

    _common = dict(
        **VPITCH_AXIS_HALF,
        height=520, margin=dict(l=10, r=10, t=44, b=20),
        title=dict(text=f'<b>{team_name}</b>', x=0.5,
                   font=dict(color=team_color, size=13)),
        annotations=[dict(
            x=0.98, y=0.97, xref='paper', yref='paper',
            text='▲ Attacking Direction', showarrow=False,
            font=dict(color='black', size=16, family='Arial'),
            xanchor='right', yanchor='top',
            bgcolor='rgba(255,255,255,0.7)', borderpad=3,
        )],
    )

    if shots.empty or 'x' not in shots.columns:
        fig.update_layout(**layout_config(**_common))
        return fig

    for outcome in ['Goal', 'Saved Shot', 'Post', 'Blocked Shot', 'Miss']:
        grp   = shots[shots['event_type'] == outcome].copy()
        if grp.empty:
            continue
        color  = _OUTCOME_COLOR.get(outcome, team_color)
        symbol = _OUTCOME_SYMBOL.get(outcome, 'circle')
        valid  = grp[grp['x'].notna() & grp['y'].notna()].copy()
        if valid.empty:
            continue

        fig_x    = (100 - valid['y']).tolist()
        fig_y    = valid['x'].tolist()
        names    = valid['player_name'].fillna('Unknown').tolist() if 'player_name' in valid.columns else [''] * len(valid)
        mins     = valid['time_min'].fillna(0).astype(int).tolist() if 'time_min' in valid.columns else [0] * len(valid)
        og_flags = (
            [' (own goal)' if v == 'Si' else '' for v in valid['own goal'].fillna('')]
            if 'own goal' in valid.columns else [''] * len(valid)
        )

        if _GM_Y_COL in valid.columns:
            gm_y = pd.to_numeric(valid[_GM_Y_COL], errors='coerce')
            xs_l, ys_l = [], []
            for sx, sy, gmy in zip(fig_x, fig_y, gm_y):
                if pd.notna(gmy):
                    xs_l.extend([sx, 100 - float(gmy), None])
                    ys_l.extend([sy, 100.0, None])
            if xs_l:
                fig.add_trace(go.Scatter(
                    x=xs_l, y=ys_l, mode='lines',
                    line=dict(color=color, width=2.5),
                    opacity=0.65, showlegend=False, hoverinfo='skip',
                ))

        size = 15 if outcome == 'Goal' else 10
        fig.add_trace(go.Scatter(
            x=fig_x, y=fig_y, mode='markers', name=outcome,
            marker=dict(color=color, symbol=symbol, size=size,
                        opacity=0.88, line=dict(color='white', width=1)),
            customdata=list(zip(names, mins, og_flags)),
            hovertemplate=(
                f'<b>{outcome}%{{customdata[2]}}</b><br>'
                '<b>%{customdata[0]}</b><br>'
                "%{customdata[1]}'<extra></extra>"
            ),
        ))

    fig.update_layout(**layout_config(
        **_common,
        hoverlabel=dict(bgcolor='#1A1D2E', font_color='white', font_size=12),
        legend=dict(
            x=0.01, y=0.01, xanchor='left', yanchor='bottom', orientation='v',
            font=dict(color=COLORS['text_primary'], size=10),
            bgcolor='rgba(26,29,46,0.80)',
            bordercolor=COLORS.get('dark_border', 'rgba(255,255,255,0.15)'),
            borderwidth=1,
        ),
    ))
    return fig


# ---------------------------------------------------------------------------
# GK pass map
# ---------------------------------------------------------------------------

def _gk_pass_map(gk_passes_df: pd.DataFrame, team_color: str, gk_name: str) -> go.Figure:
    fig = go.Figure()
    add_pitch_background(fig)

    if not gk_passes_df.empty and 'Pass End X' in gk_passes_df.columns:
        passes = gk_passes_df.copy()
        passes['Pass End X'] = pd.to_numeric(passes['Pass End X'], errors='coerce')
        passes['Pass End Y'] = pd.to_numeric(passes['Pass End Y'], errors='coerce')
        passes = passes.dropna(subset=['x', 'y', 'Pass End X', 'Pass End Y'])

        for success, (color, label, opacity) in {
            True:  (team_color, 'Successful', 0.75),
            False: ('#ff6b6b',  'Unsuccessful', 0.60),
        }.items():
            if 'outcome' in passes.columns:
                grp = passes[passes['outcome'] == (1 if success else 0)]
            else:
                grp = passes if success else passes.iloc[:0]
            if grp.empty:
                continue

            xs_l, ys_l = [], []
            for _, row in grp.iterrows():
                xs_l.extend([row['x'], row['Pass End X'], None])
                ys_l.extend([row['y'], row['Pass End Y'], None])
            if xs_l:
                fig.add_trace(go.Scatter(
                    x=xs_l, y=ys_l, mode='lines',
                    line=dict(color=color, width=1.5),
                    opacity=opacity * 0.6,
                    showlegend=False, hoverinfo='skip',
                ))

            fig.add_trace(go.Scatter(
                x=grp['Pass End X'].tolist(), y=grp['Pass End Y'].tolist(),
                mode='markers', showlegend=False,
                marker=dict(color=color, size=5, opacity=opacity * 0.7, symbol='circle'),
                hoverinfo='skip',
            ))

            names = grp['player_name'].fillna(gk_name).tolist() if 'player_name' in grp.columns else [gk_name] * len(grp)
            mins  = grp['time_min'].fillna(0).astype(int).tolist() if 'time_min' in grp.columns else [0] * len(grp)
            fig.add_trace(go.Scatter(
                x=grp['x'].tolist(), y=grp['y'].tolist(),
                mode='markers', name=label,
                marker=dict(color=color, size=9, opacity=opacity,
                            symbol='circle', line=dict(color='white', width=1)),
                customdata=list(zip(names, mins)),
                hovertemplate=(
                    f'<b>{label} Pass</b><br>%{{customdata[0]}}<br>'
                    "%{customdata[1]}'<extra></extra>"
                ),
            ))

    fig.update_layout(**layout_config(
        **PITCH_AXIS_FULL,
        height=480, margin=dict(l=0, r=0, t=48, b=0),
        legend=dict(orientation='v', x=0.01, xanchor='left', y=0.99, yanchor='top',
                    bgcolor='rgba(0,0,0,0.55)',
                    font=dict(color=COLORS['text_primary'], size=9)),
        hoverlabel=dict(bgcolor='#1A1D2E', font_color='white', font_size=12),
        annotations=[dict(
            x=0.5, y=1.0, xref='paper', yref='paper',
            text='➡ Direction of Attack', showarrow=False,
            font=dict(color='black', size=16, family='Arial'),
            xanchor='center', yanchor='bottom',
            bgcolor='rgba(255,255,255,0.7)', borderpad=3,
        )],
    ))
    return fig


# ---------------------------------------------------------------------------
# Half filter bar
# ---------------------------------------------------------------------------

def _filter_bar_gk(active: str = 'full') -> html.Div:
    return html.Div([
        dcc.Store(id='gk-half-store', data=active),
        html.Span("Half:", style={
            'color': COLORS['text_secondary'], 'fontSize': '0.85rem',
            'marginRight': '10px', 'alignSelf': 'center',
        }),
        html.Button("Full Match", id='gk-half-full', n_clicks=0,
                    style=_BTN_ACTIVE if active == 'full' else _BTN_IDLE),
        html.Button("1st Half",   id='gk-half-1',    n_clicks=0,
                    style=_BTN_ACTIVE if active == '1' else _BTN_IDLE),
        html.Button("2nd Half",   id='gk-half-2',    n_clicks=0,
                    style=_BTN_ACTIVE if active == '2' else _BTN_IDLE),
    ], style={'display': 'flex', 'gap': '8px', 'alignItems': 'center',
              'marginBottom': '16px'})


# ---------------------------------------------------------------------------
# GK selector row
# ---------------------------------------------------------------------------

def _build_gk_selector_row(d: dict) -> html.Div:
    """Per-team GK filter dropdowns.

    Always rendered (Dash requires IDs to be stable), but the row is invisible
    when neither team used multiple goalkeepers.  Each dropdown shows:
      All GKs  |  GK1 name (time)  |  GK2 name (time)  …
    """
    home_gks   = d['home']['gk_list']
    away_gks   = d['away']['gk_list']
    home_multi = len(home_gks) > 1
    away_multi = len(away_gks) > 1

    def _opts(gk_list):
        return [{'label': 'All GKs', 'value': 'all'}] + [
            {'label': gk['name'] + (f" ({gk['time_label']})" if gk['time_label'] else ''),
             'value': str(i)}
            for i, gk in enumerate(gk_list)
        ]

    _lbl_style = {'fontSize': '0.85rem', 'marginRight': '8px',
                  'alignSelf': 'center', 'whiteSpace': 'nowrap'}

    home_block = html.Div([
        html.Span(f"{d['home']['team']} GK:", style={**_lbl_style, 'color': HOME_COLOR}),
        dcc.Dropdown(
            id='gk-home-filter', options=_opts(home_gks), value='all',
            clearable=False, className='culevision-dropdown', style={'minWidth': '220px'},
        ),
    ], style={'display': 'flex' if home_multi else 'none',
              'alignItems': 'center', 'gap': '8px'})

    away_block = html.Div([
        html.Span(f"{d['away']['team']} GK:", style={**_lbl_style, 'color': AWAY_COLOR}),
        dcc.Dropdown(
            id='gk-away-filter', options=_opts(away_gks), value='all',
            clearable=False, className='culevision-dropdown', style={'minWidth': '220px'},
        ),
    ], style={'display': 'flex' if away_multi else 'none',
              'alignItems': 'center', 'gap': '8px'})

    outer = 'flex' if (home_multi or away_multi) else 'none'
    return html.Div(
        [home_block, away_block],
        style={'display': outer, 'gap': '24px', 'alignItems': 'center',
               'marginBottom': '20px', 'flexWrap': 'wrap'},
    )


# ---------------------------------------------------------------------------
# Filterable plot block
# ---------------------------------------------------------------------------

def _render_gk_plots(
    events: pd.DataFrame,
    home_gk: str = 'all',
    away_gk: str = 'all',
) -> html.Div:
    """Render goal mouth + shot map + pass map.

    Always produces a single home | away pair of plots.
    The GK filter controls WHICH shots / passes are shown:
      'all'  → combined data for the whole team
      '0'/'1' → only that goalkeeper's data
    """
    d = _compute(events)
    hs  = d['home']
    as_ = d['away']

    h_shots  = _team_shots(hs,  home_gk)
    a_shots  = _team_shots(as_, away_gk)
    h_passes, h_gk_name = _team_passes(hs,  home_gk)
    a_passes, a_gk_name = _team_passes(as_, away_gk)
    h_title  = _plot_title(hs,  home_gk)
    a_title  = _plot_title(as_, away_gk)

    goal_mouth = html.Div([
        section_header("Goal Mouth — Shots Faced"),
        dbc.Row([
            dbc.Col(html.Div([_goal_mouth_viz(h_shots, HOME_COLOR, h_title)],
                             style=CARD_STYLE), md=6, className='mb-3'),
            dbc.Col(html.Div([_goal_mouth_viz(a_shots, AWAY_COLOR, a_title)],
                             style=CARD_STYLE), md=6, className='mb-3'),
        ], className='g-3'),
    ], style={'marginBottom': '32px'})

    shot_maps = html.Div([
        section_header("Shot Faced Map"),
        dbc.Row([
            dbc.Col(dcc.Graph(figure=_shot_map_fig(h_shots, HOME_COLOR, h_title),
                              config=CHART_CONFIG), md=6, className='mb-3'),
            dbc.Col(dcc.Graph(figure=_shot_map_fig(a_shots, AWAY_COLOR, a_title),
                              config=CHART_CONFIG), md=6, className='mb-3'),
        ], className='g-2'),
    ], style={'marginBottom': '32px'})

    pass_maps = html.Div([
        section_header("GK Pass Map"),
        dbc.Row([
            dbc.Col(html.Div([
                html.Div(f"{hs['team']} — GK: {h_gk_name}", style={
                    'color': HOME_COLOR, 'fontWeight': '600',
                    'fontSize': '0.85rem', 'marginBottom': '8px', 'textAlign': 'center',
                }),
                dcc.Graph(figure=_gk_pass_map(h_passes, HOME_COLOR, h_gk_name),
                          config=CHART_CONFIG),
            ], style=CARD_STYLE), md=6, className='mb-3'),
            dbc.Col(html.Div([
                html.Div(f"{as_['team']} — GK: {a_gk_name}", style={
                    'color': AWAY_COLOR, 'fontWeight': '600',
                    'fontSize': '0.85rem', 'marginBottom': '8px', 'textAlign': 'center',
                }),
                dcc.Graph(figure=_gk_pass_map(a_passes, AWAY_COLOR, a_gk_name),
                          config=CHART_CONFIG),
            ], style=CARD_STYLE), md=6, className='mb-3'),
        ], className='g-3'),
    ])

    return html.Div([goal_mouth, shot_maps, pass_maps])


# ---------------------------------------------------------------------------
# Tab builder
# ---------------------------------------------------------------------------

def build_goalkeeping_tab(events: pd.DataFrame, **_) -> html.Div:
    if events.empty:
        return html.P("No event data.", style={"color": COLORS["text_secondary"]})

    d = _compute(events)
    hs, as_ = d['home'], d['away']

    h1 = events[events['period_id'] == 1] if 'period_id' in events.columns else events.iloc[:0]
    h2 = events[events['period_id'] == 2] if 'period_id' in events.columns else events.iloc[:0]
    h1_hs = _half_stats(h1, 'home', 'away')
    h2_hs = _half_stats(h2, 'home', 'away')
    h1_as = _half_stats(h1, 'away', 'home')
    h2_as = _half_stats(h2, 'away', 'home')

    stats_section = _match_stats_section(hs, as_, h1_hs, h2_hs, h1_as, h2_as)

    return html.Div([
        stats_section,
        _filter_bar_gk(),
        _build_gk_selector_row(d),
        html.Div(id='gk-plots-content', children=_render_gk_plots(events)),
    ], style={'marginTop': '16px'})


# ---------------------------------------------------------------------------
# Callbacks
# ---------------------------------------------------------------------------

def register_goalkeeping_callbacks(app) -> None:

    @app.callback(
        Output('gk-half-full', 'style'),
        Output('gk-half-1',    'style'),
        Output('gk-half-2',    'style'),
        Output('gk-half-store', 'data'),
        Input('gk-half-full', 'n_clicks'),
        Input('gk-half-1',    'n_clicks'),
        Input('gk-half-2',    'n_clicks'),
        State('gk-half-store', 'data'),
        prevent_initial_call=True,
    )
    def _toggle_gk_half(_f, _1, _2, current):
        triggered = ctx.triggered_id or 'gk-half-full'
        val       = {'gk-half-full': 'full', 'gk-half-1': '1', 'gk-half-2': '2'}.get(triggered, current)
        styles    = [_BTN_ACTIVE if val == k else _BTN_IDLE for k in ('full', '1', '2')]
        return (*styles, val)

    @app.callback(
        Output('gk-plots-content', 'children'),
        Input('gk-half-store',  'data'),
        Input('gk-home-filter', 'value'),
        Input('gk-away-filter', 'value'),
        State('pma-selected-match', 'data'),
        prevent_initial_call=True,
    )
    def _update_gk_plots(half, home_gk, away_gk, match_id):
        if not match_id:
            return html.P("No match selected.", style={'color': COLORS['text_secondary']})
        events = get_match_events(match_id)
        if events.empty:
            return html.P("No data.", style={'color': COLORS['text_secondary']})
        if half != 'full' and 'period_id' in events.columns:
            events = events[events['period_id'] == int(half)]
        return _render_gk_plots(events, home_gk or 'all', away_gk or 'all')
