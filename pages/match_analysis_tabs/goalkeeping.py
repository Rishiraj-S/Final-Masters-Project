"""
goalkeeping.py
==============
Goalkeeping tab: match stats (TV-style with half breakdown), goal mouth
visualisation, shot map with trajectory arrows, interactive GK pass map.

Half filter affects all plots; match statistics table is always full-match.
"""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
from dash import html, dcc, ctx
from dash.dependencies import Input, Output, State
import dash_bootstrap_components as dbc

from utils.config import COLORS
from utils.data_utils import get_match_events, count_goals, exclude_own_goals

from .shared import (
    HOME_COLOR, AWAY_COLOR, GOLD,
    CHART_CONFIG, layout_config,
    add_pitch_background, PITCH_AXIS_FULL,
    add_vertical_half_pitch_background, VPITCH_AXIS_HALF,
    CARD_STYLE, section_header,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_SHOT_TYPES = {'Miss', 'Saved Shot', 'Goal', 'Post', 'Blocked Shot'}

_SAVE_COLOR = '#51cf66'
_GOAL_COLOR = '#ff6b6b'
_MISS_COLOR = '#868e96'

# Goal mouth coordinate constants (Opta 0-100 scale)
_GOAL_LEFT  = 36.8
_GOAL_RIGHT = 63.2
_CROSSBAR_Z = 32.0
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


# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------

def _compute(events: pd.DataFrame) -> dict:
    home_team = events['home_team'].iloc[0]
    away_team = events['away_team'].iloc[0]

    # Own-goal-aware totals for the full match
    all_goals = events[events['event_type'] == 'Goal']
    home_goals_total, away_goals_total = count_goals(all_goals)

    out = {}

    for gk_pos, opp_pos, gk_team in (
        ('home', 'away', home_team),
        ('away', 'home', away_team),
    ):
        te_gk  = events[events['team_position'] == gk_pos]
        te_opp = events[events['team_position'] == opp_pos]

        # Opponent shots — exclude their own goals (those count FOR this GK's team)
        opp_shots = exclude_own_goals(
            te_opp[te_opp['event_type'].isin(_SHOT_TYPES)].copy()
        )

        # Own goals by THIS team count AGAINST this GK — add them to the shots faced
        gk_goals = te_gk[te_gk['event_type'] == 'Goal'].copy()
        if 'own goal' in gk_goals.columns:
            own_ogs = gk_goals[gk_goals['own goal'] == 'Si']
        else:
            own_ogs = gk_goals.iloc[:0]
        if not own_ogs.empty:
            # Invert x so OG origins appear at the attacking end of the shot map.
            own_ogs = own_ogs.copy()
            if 'x' in own_ogs.columns:
                own_ogs['x'] = 100 - pd.to_numeric(own_ogs['x'], errors='coerce')
            shots_faced = pd.concat([opp_shots, own_ogs], ignore_index=True)
        else:
            shots_faced = opp_shots

        saved_shots = te_opp[te_opp['event_type'] == 'Saved Shot']

        saves_made     = len(saved_shots)
        goals_conceded = away_goals_total if gk_pos == 'home' else home_goals_total
        shots_on_target = saves_made + goals_conceded
        save_pct = round(saves_made / shots_on_target * 100, 1) if shots_on_target > 0 else 0.0

        # Identify GK: player with lowest average x (nearest own goal)
        gk_name      = None
        gk_passes_df = pd.DataFrame()
        if 'player_name' in te_gk.columns and 'x' in te_gk.columns:
            avg_x = (
                te_gk.dropna(subset=['player_name', 'x'])
                .groupby('player_name')['x'].mean()
            )
            if not avg_x.empty:
                gk_name = avg_x.idxmin()
                gk_evts = te_gk[te_gk['player_name'] == gk_name]
                passes  = gk_evts[gk_evts['event_type'] == 'Pass'].copy()
                if (not passes.empty
                        and 'Pass End X' in passes.columns
                        and 'Pass End Y' in passes.columns):
                    gk_passes_df = passes

        out[gk_pos] = {
            'team':             gk_team,
            'total_shots':      len(shots_faced),
            'shots_on_target':  shots_on_target,
            'saves':            saves_made,
            'goals_conceded':   goals_conceded,
            'save_pct':         save_pct,
            'gk_name':          gk_name or '—',
            'opp_shots_df':     shots_faced,
            'gk_passes_df':     gk_passes_df,
        }

    return out


def _half_stats(events: pd.DataFrame, gk_pos: str, opp_pos: str) -> dict:
    te_opp = events[events['team_position'] == opp_pos]
    saved  = te_opp[te_opp['event_type'] == 'Saved Shot']
    # Exclude opponent OGs — they count for this GK's team, not against
    half_goals = events[events['event_type'] == 'Goal']
    hg, ag     = count_goals(half_goals)
    goals_conc = ag if gk_pos == 'home' else hg
    shots      = exclude_own_goals(te_opp[te_opp['event_type'].isin(_SHOT_TYPES)].copy())
    sot        = len(saved) + goals_conc
    return {
        'total_shots':      len(shots),
        'shots_on_target':  sot,
        'saves':            len(saved),
        'goals_conceded':   goals_conc,
        'save_pct':         round(len(saved) / sot * 100, 1) if sot > 0 else 0.0,
    }


# ---------------------------------------------------------------------------
# Match statistics (TV-style with half breakdown)
# ---------------------------------------------------------------------------

def _gk_stats_table(team_name: str, color: str, gk_name: str,
                    full: dict, h1: dict, h2: dict) -> html.Div:
    """Single-team GK stats table with Full / 1st Half / 2nd Half columns."""
    _METRICS = [
        ('Shots Faced',     'total_shots'),
        ('Shots on Target', 'shots_on_target'),
        ('Saves',           'saves'),
        ('Goals Conceded',  'goals_conceded'),
        ('Save %',          'save_pct'),
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

    def _fmt(key, d):
        v = d.get(key, 0)
        return f"{v:.1f}%" if key == 'save_pct' else str(int(v))

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
            html.Td(_fmt(key, full), style=_col_style),
            html.Td(_fmt(key, h1),   style=_col_style),
            html.Td(_fmt(key, h2),   style=_col_style),
        ], style={'backgroundColor': bg}))

    return html.Div([
        html.Div(team_name, style={
            'color': color, 'fontWeight': '700', 'fontSize': '0.95rem',
            'marginBottom': '4px',
            'borderBottom': f'2px solid {color}',
            'paddingBottom': '6px',
        }),
        html.Div(f"GK: {gk_name}", style={
            'color': COLORS['text_secondary'], 'fontSize': '0.82rem',
            'marginBottom': '10px',
        }),
        html.Table(
            [html.Thead(header), html.Tbody(rows)],
            style={'width': '100%', 'borderCollapse': 'collapse'},
        ),
    ], style=CARD_STYLE)


def _match_stats_section(hs: dict, as_: dict,
                          h1_hs: dict, h2_hs: dict,
                          h1_as: dict, h2_as: dict) -> html.Div:
    """Static full-match GK stats tables (home | away) with half breakdown."""
    home_full = {k: hs[k] for k in ('total_shots', 'shots_on_target', 'saves', 'goals_conceded', 'save_pct')}
    away_full = {k: as_[k] for k in ('total_shots', 'shots_on_target', 'saves', 'goals_conceded', 'save_pct')}
    return html.Div([
        section_header('GK Statistics'),
        dbc.Row([
            dbc.Col(_gk_stats_table(hs['team'], HOME_COLOR, hs['gk_name'],
                                    home_full, h1_hs, h2_hs), md=6, className='mb-3'),
            dbc.Col(_gk_stats_table(as_['team'], AWAY_COLOR, as_['gk_name'],
                                    away_full, h1_as, h2_as), md=6, className='mb-3'),
        ], className='g-3'),
    ], style={'marginBottom': '36px'})


# ---------------------------------------------------------------------------
# Goal mouth visualisation
# ---------------------------------------------------------------------------

def _goal_mouth_viz(opp_shots_df: pd.DataFrame,
                    gk_team_color: str, gk_team: str) -> dcc.Graph:
    POST_W = 0.7
    shapes = [
        dict(type='rect',
             x0=_GOAL_LEFT, x1=_GOAL_RIGHT, y0=0, y1=_CROSSBAR_Z,
             fillcolor='rgba(255,255,255,0.07)', line=dict(width=0)),
        dict(type='rect',
             x0=_GOAL_LEFT - POST_W, x1=_GOAL_LEFT, y0=0, y1=_CROSSBAR_Z + POST_W,
             fillcolor='white', line=dict(width=0)),
        dict(type='rect',
             x0=_GOAL_RIGHT, x1=_GOAL_RIGHT + POST_W, y0=0, y1=_CROSSBAR_Z + POST_W,
             fillcolor='white', line=dict(width=0)),
        dict(type='rect',
             x0=_GOAL_LEFT - POST_W, x1=_GOAL_RIGHT + POST_W,
             y0=_CROSSBAR_Z, y1=_CROSSBAR_Z + POST_W,
             fillcolor='white', line=dict(width=0)),
        dict(type='line', x0=20, x1=80, y0=0, y1=0,
             line=dict(color='rgba(255,255,255,0.25)', width=1, dash='dot')),
        *[dict(type='line', x0=v, x1=v, y0=0, y1=_CROSSBAR_Z,
               line=dict(color='rgba(255,255,255,0.07)', width=1))
          for v in [40, 43, 46, 50, 54, 57, 60]],
        *[dict(type='line', x0=_GOAL_LEFT, x1=_GOAL_RIGHT, y0=h, y1=h,
               line=dict(color='rgba(255,255,255,0.07)', width=1))
          for h in [8, 16, 24]],
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
            fig.add_trace(go.Scatter(
                x=(100 - grp[_GM_Y_COL]).tolist(), y=grp[_GM_Z_COL].tolist(),
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
        yaxis=dict(range=[-4, 68], showgrid=False, zeroline=False, visible=False),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='#0d1a35',
        margin=dict(l=10, r=10, t=40, b=60),
        height=430,
        font=dict(color=COLORS['text_primary']),
        legend=dict(orientation='h', y=-0.14, x=0.5, xanchor='center',
                    font=dict(color=COLORS['text_primary'], size=10),
                    bgcolor='rgba(0,0,0,0)'),
        title=dict(text=f'<b>Goal Mouth — {gk_team} GK</b>', x=0.5,
                   font=dict(color=gk_team_color, size=12)),
    )
    return dcc.Graph(figure=fig, config=CHART_CONFIG)


# ---------------------------------------------------------------------------
# Shot map with trajectory arrows
# ---------------------------------------------------------------------------

def _shot_map_fig(shots: pd.DataFrame, team_color: str, team_name: str) -> go.Figure:
    """
    Vertical attacking-half pitch showing shot origins.
    Dashed lines connect each shot start to its goal-mouth Y position (goal line).
    """
    fig = go.Figure()
    add_vertical_half_pitch_background(fig)

    _common = dict(
        **VPITCH_AXIS_HALF,
        height=520,
        margin=dict(l=10, r=10, t=44, b=20),
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
        grp = shots[shots['event_type'] == outcome].copy()
        if grp.empty:
            continue
        color  = _OUTCOME_COLOR.get(outcome, team_color)
        symbol = _OUTCOME_SYMBOL.get(outcome, 'circle')
        valid  = grp[grp['x'].notna() & grp['y'].notna()].copy()
        if valid.empty:
            continue

        # Vertical pitch: fig_x = 100 - pitch_y (flip left-right), fig_y = pitch_x
        fig_x = (100 - valid['y']).tolist()
        fig_y = valid['x'].tolist()
        names = valid['player_name'].fillna('Unknown').tolist() if 'player_name' in valid.columns else [''] * len(valid)
        mins  = valid['time_min'].fillna(0).astype(int).tolist() if 'time_min' in valid.columns else [0] * len(valid)
        og_flags = (
            [' (own goal)' if v == 'Si' else '' for v in valid['own goal'].fillna('')]
            if 'own goal' in valid.columns else [''] * len(valid)
        )

        # Trajectory lines: shot origin → goal mouth Y (at x=100)
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


# ---------------------------------------------------------------------------
# GK pass map (interactive full-pitch Plotly)
# ---------------------------------------------------------------------------

def _gk_pass_map(gk_passes_df: pd.DataFrame, team_color: str, gk_name: str) -> go.Figure:
    """
    Interactive full-pitch Plotly figure: GK pass origins with directional lines
    to pass end location. Successful passes = team color, unsuccessful = red.
    """
    fig = go.Figure()
    add_pitch_background(fig)

    if not gk_passes_df.empty and 'Pass End X' in gk_passes_df.columns:
        passes = gk_passes_df.copy()
        passes['Pass End X'] = pd.to_numeric(passes['Pass End X'], errors='coerce')
        passes['Pass End Y'] = pd.to_numeric(passes['Pass End Y'], errors='coerce')
        passes = passes.dropna(subset=['x', 'y', 'Pass End X', 'Pass End Y'])

        for success, (color, label, opacity) in {
            True:  (team_color,  'Successful', 0.75),
            False: ('#ff6b6b',   'Unsuccessful', 0.60),
        }.items():
            if 'outcome' in passes.columns:
                grp = passes[passes['outcome'] == (1 if success else 0)]
            else:
                grp = passes if success else passes.iloc[:0]

            if grp.empty:
                continue

            # Lines: start → end
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

            # Endpoint arrowheads (small filled circles)
            fig.add_trace(go.Scatter(
                x=grp['Pass End X'].tolist(), y=grp['Pass End Y'].tolist(),
                mode='markers', showlegend=False,
                marker=dict(color=color, size=5, opacity=opacity * 0.7,
                            symbol='circle'),
                hoverinfo='skip',
            ))

            # Start markers with hover
            names = grp['player_name'].fillna(gk_name).tolist() if 'player_name' in grp.columns else [gk_name] * len(grp)
            mins  = grp['time_min'].fillna(0).astype(int).tolist() if 'time_min' in grp.columns else [0] * len(grp)
            fig.add_trace(go.Scatter(
                x=grp['x'].tolist(), y=grp['y'].tolist(),
                mode='markers', name=label,
                marker=dict(color=color, size=9, opacity=opacity,
                            symbol='circle', line=dict(color='white', width=1)),
                customdata=list(zip(names, mins)),
                hovertemplate=(
                    f'<b>{label} Pass</b><br>'
                    '%{customdata[0]}<br>'
                    "%{customdata[1]}'<extra></extra>"
                ),
            ))

    fig.update_layout(**layout_config(
        **PITCH_AXIS_FULL,
        height=480,
        margin=dict(l=0, r=0, t=48, b=0),
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
              'marginBottom': '20px'})


# ---------------------------------------------------------------------------
# Filterable plot block
# ---------------------------------------------------------------------------

def _render_gk_plots(events: pd.DataFrame) -> html.Div:
    """Build goal mouth + shot map + pass map for the given (possibly filtered) events."""
    d = _compute(events)
    hs, as_ = d['home'], d['away']

    goal_mouth = html.Div([
        section_header("Goal Mouth — Shots Faced"),
        dbc.Row([
            dbc.Col(html.Div([_goal_mouth_viz(hs['opp_shots_df'], HOME_COLOR, hs['team'])],
                             style=CARD_STYLE), md=6, className='mb-3'),
            dbc.Col(html.Div([_goal_mouth_viz(as_['opp_shots_df'], AWAY_COLOR, as_['team'])],
                             style=CARD_STYLE), md=6, className='mb-3'),
        ], className='g-3'),
    ], style={'marginBottom': '32px'})

    shot_maps = html.Div([
        section_header("Shot Faced Map"),
        dbc.Row([
            dbc.Col(dcc.Graph(figure=_shot_map_fig(hs['opp_shots_df'], HOME_COLOR, hs['team']),
                              config=CHART_CONFIG), md=6, className='mb-3'),
            dbc.Col(dcc.Graph(figure=_shot_map_fig(as_['opp_shots_df'], AWAY_COLOR, as_['team']),
                              config=CHART_CONFIG), md=6, className='mb-3'),
        ], className='g-2'),
    ], style={'marginBottom': '32px'})

    pass_maps = html.Div([
        section_header("GK Pass Map"),
        dbc.Row([
            dbc.Col(html.Div([
                html.Div(f"{hs['team']} — GK: {hs['gk_name']}", style={
                    'color': HOME_COLOR, 'fontWeight': '600',
                    'fontSize': '0.85rem', 'marginBottom': '8px', 'textAlign': 'center',
                }),
                dcc.Graph(
                    figure=_gk_pass_map(hs['gk_passes_df'], HOME_COLOR, hs['gk_name']),
                    config=CHART_CONFIG,
                )
            ], style=CARD_STYLE), md=6, className='mb-3'),
            dbc.Col(html.Div([
                html.Div(f"{as_['team']} — GK: {as_['gk_name']}", style={
                    'color': AWAY_COLOR, 'fontWeight': '600',
                    'fontSize': '0.85rem', 'marginBottom': '8px', 'textAlign': 'center',
                }),
                dcc.Graph(
                    figure=_gk_pass_map(as_['gk_passes_df'], AWAY_COLOR, as_['gk_name']),
                    config=CHART_CONFIG,
                )
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

    # Per-half stats for the static stat bars
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
        val = {'gk-half-full': 'full', 'gk-half-1': '1', 'gk-half-2': '2'}.get(triggered, current)
        styles = [_BTN_ACTIVE if val == k else _BTN_IDLE for k in ('full', '1', '2')]
        return (*styles, val)

    @app.callback(
        Output('gk-plots-content', 'children'),
        Input('gk-half-store', 'data'),
        State('pma-selected-match', 'data'),
        prevent_initial_call=True,
    )
    def _update_gk_plots(half, match_id):
        if not match_id:
            return html.P("No match selected.", style={'color': COLORS['text_secondary']})
        events = get_match_events(match_id)
        if events.empty:
            return html.P("No data.", style={'color': COLORS['text_secondary']})
        if half != 'full' and 'period_id' in events.columns:
            events = events[events['period_id'] == int(half)]
        return _render_gk_plots(events)
