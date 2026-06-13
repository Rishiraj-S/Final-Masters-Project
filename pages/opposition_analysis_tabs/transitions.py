"""
Opposition Analysis — Tab 3: Transitions

Two sub-tabs (skeleton + callback pattern):
  • Attacking Transitions — how the opponent wins possession and attacks
  • Defensive Transitions — how the opponent loses possession and transitions to defence

ID prefix: oat- (opposition attacking transition)
           odt- (opposition defensive transition)

Mirrors team_analysis_tabs/transitions.py, attacking_transition.py and
defensive_transition.py — using opposition event data via load_opp_events().
"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
from dash import html, dcc, Input, Output, State
import dash_bootstrap_components as dbc

from utils.config import COLORS
from utils.opposition_data_utils import load_opp_events, SEASON
from page_utils import PassMap, GOLD, HOME_COLOR, AWAY_COLOR
from page_utils.visualizations import (
    add_pitch_background,
    PITCH_AXIS_FULL,
    render_xt_heatmap_img,
    PITCH_BG,
)
_TRANSITION_WINDOW_SEC = 15

# ── Attacking transition ──────────────────────────────────────────────────────
_GAIN_COLORS = {
    'Ball Recovery': '#22c55e',
    'Interception':  '#3b82f6',
    'Tackle Won':    GOLD,
}
_GAIN_OUTCOME_SYMBOLS = {
    'Goal Scored':     ('star',        14),
    'Shot Taken':      ('triangle-up', 12),
    'Quick Turnover':  ('x',           12),
    'Possession Held': ('circle',      10),
}
_ALL_GAIN_TYPES    = list(_GAIN_COLORS.keys())
_ALL_ATK_OUTCOMES  = list(_GAIN_OUTCOME_SYMBOLS.keys())

# ── Defensive transition ──────────────────────────────────────────────────────
_LOSS_COLORS = {
    'Failed Pass':  '#ef4444',
    'Miscontrol':   '#f97316',
    'Dispossessed': '#3b82f6',
    'Lost Duel':    '#06b6d4',
    'Offside Pass': '#eab308',
    'Error':        '#a855f7',
}
_LOSS_OUTCOME_SYMBOLS = {
    'Goal Conceded':     ('star',         14),
    'Shot Conceded':     ('triangle-up',  12),
    'Opp Recovered':     ('circle',       11),
    'No Clear Threat':   ('square',       10),
}
_ALL_LOSS_TYPES    = list(_LOSS_COLORS.keys())
_ALL_DEF_OUTCOMES  = list(_LOSS_OUTCOME_SYMBOLS.keys())

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
    'textAlign': 'center', 'padding': '4px 6px', 'fontSize': '0.58rem',
    'fontWeight': '700', 'color': COLORS['text_secondary'], 'textTransform': 'uppercase',
    'letterSpacing': '0.05em', 'whiteSpace': 'nowrap',
    'borderBottom': f'1px solid {COLORS["dark_border"]}',
}
_TD = {
    'textAlign': 'center', 'padding': '4px 6px', 'fontSize': '0.68rem',
    'fontWeight': '600', 'color': COLORS['text_primary'], 'whiteSpace': 'nowrap',
}
_NAME_TD = {**_TD, 'textAlign': 'left', 'color': GOLD,
            'maxWidth': '100px', 'overflow': 'hidden', 'textOverflow': 'ellipsis'}

CHART_CFG = {'displayModeBar': False}
_SKEL_SRC = 'data:image/png;base64,'

_BTN_BASE = {
    'display': 'block', 'width': '100%', 'textAlign': 'center',
    'padding': '20px 0', 'fontWeight': '700', 'fontSize': '1rem',
    'letterSpacing': '0.6px', 'textTransform': 'uppercase',
    'backgroundColor': COLORS['dark_secondary'],
    'border': f'1px solid {COLORS["dark_border"]}', 'borderRadius': '0',
}
_BTN_INACTIVE = {**_BTN_BASE, 'color': COLORS['text_secondary']}
_BTN_ACTIVE   = {**_BTN_BASE, 'color': GOLD,
                 'backgroundColor': 'rgba(237, 187, 0, 0.08)',
                 'borderBottom': f'3px solid {GOLD}'}


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


def _no_data():
    return [html.P("No data", style={'color': COLORS['text_secondary'],
                                     'fontSize': '0.75rem', 'textAlign': 'center',
                                     'marginTop': '8px'})]


def _kpi_bar(kpis: list) -> list:
    return [html.Div(kpis, style={'display': 'flex', 'gap': '6px', 'flexWrap': 'wrap'})]


def _kpi_card(value, label, color=COLORS['text_primary']) -> html.Div:
    return html.Div([
        html.Div(str(value), style={'color': color, 'fontWeight': '800',
                                    'fontSize': '1.35rem', 'lineHeight': '1.1'}),
        html.Div(label, style={'color': COLORS['text_secondary'], 'fontSize': '0.60rem',
                               'fontWeight': '600', 'letterSpacing': '0.6px',
                               'textTransform': 'uppercase', 'marginTop': '3px'}),
    ], style={'backgroundColor': COLORS['dark_secondary'],
              'border': f'1px solid {COLORS["dark_border"]}',
              'borderRadius': '6px', 'padding': '8px 10px', 'flex': '1', 'minWidth': '0'})


def _ts(row: pd.Series) -> float:
    """Event timestamp in seconds."""
    return float(row.get('period_id', 1)) * 10000 + float(row.get('time_min', 0)) * 60 + float(row.get('time_sec', 0))


# =============================================================================
# ATTACKING TRANSITIONS  —  data helpers
# =============================================================================

def _extract_gains(opp_ev: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, row in opp_ev.iterrows():
        etype   = row.get('event_type', '')
        outcome = row.get('outcome', 0)
        if etype == 'Ball recovery':
            gain_type = 'Ball Recovery'
        elif etype == 'Interception':
            gain_type = 'Interception'
        elif etype == 'Tackle' and outcome == 1:
            gain_type = 'Tackle Won'
        else:
            continue
        rows.append({
            'gain_type':   gain_type,
            'player_name': row.get('player_name', ''),
            'time_min':    float(row.get('time_min', 0)),
            'time_sec':    float(row.get('time_sec', 0)),
            'period_id':   int(row.get('period_id', 1)),
            'x':           float(row.get('x', 50)) if pd.notna(row.get('x')) else 50.0,
            'y':           float(row.get('y', 50)) if pd.notna(row.get('y')) else 50.0,
            'timestamp':   _ts(row),
        })
    return pd.DataFrame(rows)


def _tag_gain_outcomes(gains: pd.DataFrame, opp_ev: pd.DataFrame) -> pd.DataFrame:
    if gains.empty or opp_ev.empty:
        gains['window_outcome'] = 'Possession Held'
        return gains
    shot_types = ['Goal', 'Saved Shot', 'Miss', 'Post']
    outcomes   = []
    for _, g in gains.iterrows():
        t0     = g['timestamp']
        t1     = t0 + _TRANSITION_WINDOW_SEC
        window = opp_ev[(opp_ev.apply(_ts, axis=1) > t0) &
                        (opp_ev.apply(_ts, axis=1) <= t1)]
        if window.empty:
            outcomes.append('Possession Held')
            continue
        if (window['event_type'] == 'Goal').any():
            outcomes.append('Goal Scored')
        elif window['event_type'].isin(['Saved Shot', 'Miss', 'Post']).any():
            outcomes.append('Shot Taken')
        elif window['event_type'].isin(['Miscontrol', 'Dispossessed', 'Offside Pass', 'Error']).any():
            outcomes.append('Quick Turnover')
        else:
            outcomes.append('Possession Held')
    gains = gains.copy()
    gains['window_outcome'] = outcomes
    return gains


def _atk_pitch_fig(gains: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    add_pitch_background(fig)

    if not gains.empty:
        for gtype, gcolor in _GAIN_COLORS.items():
            grp = gains[gains['gain_type'] == gtype]
            if grp.empty: continue
            for outcome, (symbol, size) in _GAIN_OUTCOME_SYMBOLS.items():
                sub = grp[grp.get('window_outcome', pd.Series(dtype=str)) == outcome] \
                      if 'window_outcome' in grp.columns else grp
                if sub.empty: continue
                mins  = sub['time_min'].fillna('?').astype(int).astype(str) if 'time_min' in sub.columns else pd.Series('?', index=sub.index)
                names = sub['player_name'].fillna('') if 'player_name' in sub.columns else pd.Series('', index=sub.index)
                fig.add_trace(go.Scatter(
                    x=sub['x'], y=sub['y'], mode='markers',
                    name=f'{gtype} ({outcome})',
                    marker=dict(color=gcolor, symbol=symbol, size=size, opacity=0.85,
                                line=dict(color='white', width=1)),
                    customdata=list(zip(names, mins)),
                    hovertemplate=(
                        f'<b>{gtype}</b><br>Outcome: {outcome}<br>'
                        "Player: %{customdata[0]}<br>Min: %{customdata[1]}'<extra></extra>"
                    ),
                    showlegend=True,
                ))

    _add_atk_direction(fig)
    fig.update_layout(
        **PITCH_AXIS_FULL, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
        font=dict(color='#E8E9ED', size=12, family='Arial, sans-serif'),
        margin=dict(l=0, r=0, t=36, b=0), height=600,
        uirevision='oat-pitch-map', hovermode='closest',
        legend=dict(orientation='v', x=0.01, xanchor='left', y=0.99, yanchor='top',
                    bgcolor='rgba(0,0,0,0.55)', font=dict(color=COLORS['text_primary'], size=9)),
    )
    return fig


def _add_atk_direction(fig: go.Figure) -> None:
    fig.add_annotation(
        x=0.5, y=1.02, xref='paper', yref='paper',
        text='<b>➡  Direction of Attack</b>', showarrow=False,
        font=dict(size=10, color='white', family='Arial, sans-serif'),
        xanchor='center', yanchor='bottom',
        bgcolor='rgba(21,25,50,0.8)', bordercolor='#8899CC', borderwidth=1, borderpad=4,
    )


def _atk_kpi_children(gains: pd.DataFrame) -> list:
    n              = len(gains)
    col            = gains['window_outcome'] if not gains.empty and 'window_outcome' in gains.columns else pd.Series(dtype=str)
    goals          = int((col == 'Goal Scored').sum())
    shots          = int((col == 'Shot Taken').sum())
    quick_turnovers = int((col == 'Quick Turnover').sum())
    own_half       = int((gains['x'] < 50).sum()) if not gains.empty else 0
    fin_third      = int((gains['x'] >= 66.67).sum()) if not gains.empty else 0
    return _kpi_bar([
        _kpi_card(n,               'Total Gains',    GOLD),
        _kpi_card(goals,           'Led to Goal',    '#22c55e'),
        _kpi_card(shots,           'Led to Shot',    GOLD),
        _kpi_card(quick_turnovers, 'Quick Turnover', AWAY_COLOR),
        _kpi_card(own_half,        'Own-Half Gains', HOME_COLOR),
        _kpi_card(fin_third,       'Final Third',    HOME_COLOR),
    ])


def _atk_stats_table(gains: pd.DataFrame, top_n: int = 12) -> list:
    if gains.empty or 'player_name' not in gains.columns:
        return _no_data()
    rows_data = []
    for player, grp in gains.groupby('player_name'):
        if not player: continue
        total  = len(grp)
        z1     = int((grp['x'] < 33.33).sum())
        z2     = int(((grp['x'] >= 33.33) & (grp['x'] < 66.67)).sum())
        z3     = int((grp['x'] >= 66.67).sum())
        br     = int((grp['gain_type'] == 'Ball Recovery').sum())
        interc = int((grp['gain_type'] == 'Interception').sum())
        tkl    = int((grp['gain_type'] == 'Tackle Won').sum())
        rows_data.append({'player': player, 'total': total, 'z1': z1, 'z2': z2, 'z3': z3,
                          'br': br, 'int': interc, 'tkl': tkl})
    rows_data.sort(key=lambda r: r['total'], reverse=True)
    rows_data = rows_data[:top_n]
    if not rows_data: return _no_data()

    header = html.Tr([
        html.Th('Player', style={**_TH, 'textAlign': 'left'}),
        html.Th('Tot', style=_TH), html.Th('Z1', style=_TH),
        html.Th('Z2', style=_TH), html.Th('Z3', style=_TH),
        html.Th('BR', style=_TH), html.Th('Int', style=_TH),
        html.Th('Tkl', style=_TH),
    ])
    table_rows = []
    for i, s in enumerate(rows_data):
        bg = (COLORS.get('dark_tertiary', 'rgba(255,255,255,0.03)') if i % 2 == 0 else 'transparent')
        short = s['player'].split()[-1] if s['player'] else '—'
        table_rows.append(html.Tr([
            html.Td(short,        style=_NAME_TD),
            html.Td(str(s['total']), style={**_TD, 'color': GOLD, 'fontWeight': '800'}),
            html.Td(str(s['z1']),  style=_TD), html.Td(str(s['z2']),  style=_TD),
            html.Td(str(s['z3']),  style=_TD), html.Td(str(s['br']),  style=_TD),
            html.Td(str(s['int']), style=_TD), html.Td(str(s['tkl']), style=_TD),
        ], style={'backgroundColor': bg}))
    return [html.Div(html.Table([html.Thead(header), html.Tbody(table_rows)],
                                style={'width': '100%', 'borderCollapse': 'collapse'}),
                     style={'overflowX': 'auto'})]


def _outcomes_donut_fig(gains: pd.DataFrame) -> go.Figure:
    labels = ['Possession Held', 'Quick Turnover', 'Shot Taken', 'Goal Scored']
    colors = ['#6b7280', AWAY_COLOR, GOLD, '#22c55e']
    col    = gains['window_outcome'] if not gains.empty and 'window_outcome' in gains.columns \
             else pd.Series(dtype=str)
    values = [int((col == l).sum()) for l in labels]
    fig = go.Figure(go.Pie(
        labels=labels, values=values,
        marker=dict(colors=colors, line=dict(color=PITCH_BG, width=2)),
        hole=0.55, textinfo='percent', textfont=dict(color='white', size=11),
        hovertemplate='<b>%{label}</b><br>%{value} transitions (%{percent})<extra></extra>',
        sort=False,
    ))
    fig.update_layout(
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
        font=dict(color='#E8E9ED', size=11, family='Arial, sans-serif'),
        height=260, margin=dict(l=0, r=0, t=10, b=0),
        showlegend=True,
        legend=dict(orientation='v', x=1.0, y=0.5, xanchor='left', yanchor='middle',
                    font=dict(color=COLORS['text_primary'], size=9), bgcolor='rgba(0,0,0,0)'),
        uirevision='oat-trans-outcomes',
    )
    return fig


# =============================================================================
# DEFENSIVE TRANSITIONS  —  data helpers
# =============================================================================

def _extract_losses(opp_ev: pd.DataFrame) -> pd.DataFrame:
    _POSS_LOSS_RAW = ['Miscontrol', 'Dispossessed', 'Offside Pass', 'Error']
    rows = []
    for _, row in opp_ev.iterrows():
        etype   = row.get('event_type', '')
        outcome = row.get('outcome', 1)
        if etype == 'Pass' and outcome == 0:
            loss_type = 'Failed Pass'
        elif etype in _POSS_LOSS_RAW:
            loss_type = etype
        elif etype in ('Challenge', 'Aerial') and outcome == 0:
            loss_type = 'Lost Duel'
        else:
            continue
        rows.append({
            'loss_type':   loss_type,
            'player_name': row.get('player_name', ''),
            'time_min':    float(row.get('time_min', 0)),
            'time_sec':    float(row.get('time_sec', 0)),
            'period_id':   int(row.get('period_id', 1)),
            'x':           float(row.get('x', 50)) if pd.notna(row.get('x')) else 50.0,
            'y':           float(row.get('y', 50)) if pd.notna(row.get('y')) else 50.0,
            'timestamp':   _ts(row),
        })
    return pd.DataFrame(rows)


def _tag_loss_outcomes(losses: pd.DataFrame, bar_ev: pd.DataFrame) -> pd.DataFrame:
    if losses.empty or bar_ev.empty:
        losses = losses.copy()
        losses['window_outcome'] = 'No Clear Threat'
        return losses
    shot_types = ['Goal', 'Saved Shot', 'Miss', 'Post']
    outcomes   = []
    for _, g in losses.iterrows():
        t0     = g['timestamp']
        t1     = t0 + _TRANSITION_WINDOW_SEC
        window = bar_ev[(bar_ev.apply(_ts, axis=1) > t0) &
                        (bar_ev.apply(_ts, axis=1) <= t1)]
        if window.empty:
            outcomes.append('No Clear Threat')
            continue
        if (window['event_type'] == 'Goal').any():
            outcomes.append('Goal Conceded')
        elif window['event_type'].isin(['Saved Shot', 'Miss', 'Post']).any():
            outcomes.append('Shot Conceded')
        elif window['event_type'].isin(['Ball recovery', 'Interception']).any():
            outcomes.append('Opp Recovered')
        else:
            outcomes.append('No Clear Threat')
    losses = losses.copy()
    losses['window_outcome'] = outcomes
    return losses


def _def_pitch_fig(losses: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    add_pitch_background(fig)

    if not losses.empty:
        for ltype, lcolor in _LOSS_COLORS.items():
            grp = losses[losses['loss_type'] == ltype]
            if grp.empty: continue
            for outcome, (symbol, size) in _LOSS_OUTCOME_SYMBOLS.items():
                sub = grp[grp.get('window_outcome', pd.Series(dtype=str)) == outcome] \
                      if 'window_outcome' in grp.columns else grp
                if sub.empty: continue
                names = sub['player_name'].fillna('') if 'player_name' in sub.columns else pd.Series('', index=sub.index)
                mins  = sub['time_min'].fillna('?').astype(int).astype(str) if 'time_min' in sub.columns else pd.Series('?', index=sub.index)
                fig.add_trace(go.Scatter(
                    x=sub['x'], y=sub['y'], mode='markers',
                    name=f'{ltype} ({outcome})',
                    marker=dict(color=lcolor, symbol=symbol, size=size, opacity=0.85,
                                line=dict(color='white', width=1)),
                    customdata=list(zip(names, mins)),
                    hovertemplate=(
                        f'<b>{ltype}</b><br>Outcome: {outcome}<br>'
                        "Player: %{customdata[0]}<br>Min: %{customdata[1]}'<extra></extra>"
                    ),
                    showlegend=True,
                ))

    _add_atk_direction(fig)
    fig.update_layout(
        **PITCH_AXIS_FULL, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
        font=dict(color='#E8E9ED', size=12, family='Arial, sans-serif'),
        margin=dict(l=0, r=0, t=36, b=0), height=600,
        uirevision='odt-pitch-map', hovermode='closest',
        legend=dict(orientation='v', x=0.01, xanchor='left', y=0.99, yanchor='top',
                    bgcolor='rgba(0,0,0,0.55)', font=dict(color=COLORS['text_primary'], size=9)),
    )
    return fig


def _def_kpi_children(losses: pd.DataFrame) -> list:
    n          = len(losses)
    col        = losses['window_outcome'] if not losses.empty and 'window_outcome' in losses.columns else pd.Series(dtype=str)
    goals      = int((col == 'Goal Conceded').sum())
    shots      = int((col == 'Shot Conceded').sum())
    recovered  = int((col == 'Opp Recovered').sum())
    own_half   = int((losses['x'] < 50).sum()) if not losses.empty else 0
    def_third  = int((losses['x'] < 33.33).sum()) if not losses.empty else 0
    return _kpi_bar([
        _kpi_card(n,         'Total Losses',  AWAY_COLOR),
        _kpi_card(goals,     'Led to Goal',   AWAY_COLOR),
        _kpi_card(shots,     'Led to Shot',   '#f97316'),
        _kpi_card(recovered, 'Opp Recovered', HOME_COLOR),
        _kpi_card(own_half,  'Own-Half Loss', AWAY_COLOR),
        _kpi_card(def_third, 'Def Third',     AWAY_COLOR),
    ])


def _def_stats_table(losses: pd.DataFrame, top_n: int = 12) -> list:
    if losses.empty or 'player_name' not in losses.columns:
        return _no_data()
    rows_data = []
    for player, grp in losses.groupby('player_name'):
        if not player: continue
        total = len(grp)
        fp    = int((grp['loss_type'] == 'Failed Pass').sum())
        mc    = int((grp['loss_type'] == 'Miscontrol').sum())
        dp    = int((grp['loss_type'] == 'Dispossessed').sum())
        ld    = int((grp['loss_type'] == 'Lost Duel').sum())
        rows_data.append({'player': player, 'total': total,
                          'fp': fp, 'mc': mc, 'dp': dp, 'ld': ld})
    rows_data.sort(key=lambda r: r['total'], reverse=True)
    rows_data = rows_data[:top_n]
    if not rows_data: return _no_data()

    header = html.Tr([
        html.Th('Player', style={**_TH, 'textAlign': 'left'}),
        html.Th('Tot', style=_TH), html.Th('FP', style=_TH),
        html.Th('MC', style=_TH), html.Th('Disp', style=_TH), html.Th('LD', style=_TH),
    ])
    table_rows = []
    for i, s in enumerate(rows_data):
        bg    = (COLORS.get('dark_tertiary', 'rgba(255,255,255,0.03)') if i % 2 == 0 else 'transparent')
        short = s['player'].split()[-1] if s['player'] else '—'
        table_rows.append(html.Tr([
            html.Td(short,           style=_NAME_TD),
            html.Td(str(s['total']), style={**_TD, 'color': GOLD, 'fontWeight': '800'}),
            html.Td(str(s['fp']),    style=_TD), html.Td(str(s['mc']),    style=_TD),
            html.Td(str(s['dp']),    style=_TD), html.Td(str(s['ld']),    style=_TD),
        ], style={'backgroundColor': bg}))
    return [html.Div(html.Table([html.Thead(header), html.Tbody(table_rows)],
                                style={'width': '100%', 'borderCollapse': 'collapse'}),
                     style={'overflowX': 'auto'})]


def _losses_by_zone_donut(losses: pd.DataFrame) -> go.Figure:
    """Donut chart: possession losses split by pitch zone."""
    labels = ['Def Third (Z1)', 'Mid Third (Z2)', 'Att Third (Z3)']
    colors = [AWAY_COLOR, GOLD, HOME_COLOR]
    if not losses.empty and 'x' in losses.columns:
        z1 = int((losses['x'] < 33.33).sum())
        z2 = int(((losses['x'] >= 33.33) & (losses['x'] < 66.67)).sum())
        z3 = int((losses['x'] >= 66.67).sum())
    else:
        z1 = z2 = z3 = 0
    fig = go.Figure(go.Pie(
        labels=labels, values=[z1, z2, z3],
        marker=dict(colors=colors, line=dict(color=PITCH_BG, width=2)),
        hole=0.55, textinfo='percent', textfont=dict(color='white', size=11),
        hovertemplate='<b>%{label}</b><br>%{value} losses (%{percent})<extra></extra>',
        sort=False,
    ))
    fig.update_layout(
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
        font=dict(color='#E8E9ED', size=11, family='Arial, sans-serif'),
        height=220, margin=dict(l=0, r=0, t=10, b=0), showlegend=True,
        legend=dict(orientation='v', x=1.0, y=0.5, xanchor='left', yanchor='middle',
                    font=dict(color=COLORS['text_primary'], size=9), bgcolor='rgba(0,0,0,0)'),
        uirevision='odt-zone-donut',
    )
    return fig


def _loss_outcomes_donut(losses: pd.DataFrame) -> go.Figure:
    labels = ['No Clear Threat', 'Opp Recovered', 'Shot Conceded', 'Goal Conceded']
    colors = ['#6b7280', HOME_COLOR, '#f97316', AWAY_COLOR]
    col    = losses['window_outcome'] if not losses.empty and 'window_outcome' in losses.columns \
             else pd.Series(dtype=str)
    values = [int((col == l).sum()) for l in labels]
    fig = go.Figure(go.Pie(
        labels=labels, values=values,
        marker=dict(colors=colors, line=dict(color=PITCH_BG, width=2)),
        hole=0.55, textinfo='percent', textfont=dict(color='white', size=11),
        hovertemplate='<b>%{label}</b><br>%{value} transitions (%{percent})<extra></extra>',
        sort=False,
    ))
    fig.update_layout(
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
        font=dict(color='#E8E9ED', size=11, family='Arial, sans-serif'),
        height=260, margin=dict(l=0, r=0, t=10, b=0), showlegend=True,
        legend=dict(orientation='v', x=1.0, y=0.5, xanchor='left', yanchor='middle',
                    font=dict(color=COLORS['text_primary'], size=9), bgcolor='rgba(0,0,0,0)'),
        uirevision='odt-trans-outcomes',
    )
    return fig


# =============================================================================
# Skeleton builders
# =============================================================================

def _build_attacking_skeleton(player_opts=None) -> html.Div:
    filter_panel = html.Div([
        html.Div("Filters", style=_SECTION_TITLE),
        html.Div("Player", style=_LABEL_STYLE),
        dcc.Dropdown(id='oat-player-filter', options=player_opts or [], value=None, multi=True,
                     placeholder="All players…", style={'fontSize': '0.75rem'}),
        html.Hr(style={'borderColor': COLORS['dark_border'], 'margin': '10px 0 4px'}),
        html.Div("Gain Type", style=_LABEL_STYLE),
        dcc.Checklist(
            id='oat-gain-type',
            options=[{'label': f'  {t}', 'value': t} for t in _ALL_GAIN_TYPES],
            value=_ALL_GAIN_TYPES,
            inputStyle={'cursor': 'pointer', 'accentColor': GOLD},
            labelStyle={'color': COLORS['text_secondary'], 'fontSize': '0.75rem', 'display': 'block', 'marginBottom': '4px'},
        ),
        html.Hr(style={'borderColor': COLORS['dark_border'], 'margin': '10px 0 4px'}),
        html.Div("Next 15s Outcome", style=_LABEL_STYLE),
        dcc.Checklist(
            id='oat-outcome-filter',
            options=[{'label': f'  {t}', 'value': t} for t in _ALL_ATK_OUTCOMES],
            value=_ALL_ATK_OUTCOMES,
            inputStyle={'cursor': 'pointer', 'accentColor': GOLD},
            labelStyle={'color': COLORS['text_secondary'], 'fontSize': '0.75rem', 'display': 'block', 'marginBottom': '4px'},
        ),
        *PassMap.dash_controls(show=['h1_time', 'h2_time'], id_prefix='oat'),
    ], style=_PANEL_STYLE)

    combined = html.Div([
        html.Div(id='oat-kpi-bar', children=[]),
        html.Hr(style={'borderColor': COLORS['dark_border'], 'margin': '10px 0 14px'}),
        dbc.Row([
            dbc.Col([
                html.Div("Possession Gain Map", style=_SECTION_TITLE),
                html.Div("Location of every possession gain · shape = 15s outcome",
                         style={'color': COLORS['text_secondary'], 'fontSize': '0.62rem',
                                'fontStyle': 'italic', 'marginBottom': '8px'}),
                dcc.Loading(type='circle', color=GOLD, children=dcc.Graph(
                    id='oat-pitch-map', figure=_skel_fig(600), config=CHART_CFG, style={'width': '100%'},
                )),
                html.Hr(style={'borderColor': COLORS['dark_border'], 'margin': '14px 0 10px'}),
                html.Div("Possession Gain Heatmap", style=_SECTION_TITLE),
                dcc.Loading(type='circle', color=GOLD, children=html.Img(
                    id='oat-heatmap-img', src=_SKEL_SRC,
                    style={'width': '100%', 'borderRadius': '6px', 'minHeight': '200px'},
                )),
            ], md=8),
            dbc.Col([
                html.Div("Gains by Player", style={**_SECTION_TITLE, 'fontSize': '0.75rem'}),
                html.Div(style={'marginBottom': '6px'}),
                html.Div(id='oat-stats-table', children=[]),
                html.Hr(style={'borderColor': COLORS['dark_border'], 'margin': '10px 0 8px'}),
                html.Div("Transition Outcome", style={**_SECTION_TITLE, 'marginBottom': '6px'}),
                dcc.Loading(type='circle', color=GOLD, children=dcc.Graph(
                    id='oat-trans-outcomes', figure=_skel_fig(260), config=CHART_CFG, style={'width': '100%'},
                )),
            ], md=4, style={'borderLeft': f'1px solid {COLORS["dark_border"]}', 'paddingLeft': '14px'}),
        ], align='start', className='g-0'),
    ], style=_PANEL_STYLE)

    return html.Div(
        dbc.Row([
            dbc.Col(filter_panel, md=2),
            dbc.Col(combined,     md=10),
        ], align='start', className='g-3'),
    )


def _build_defensive_skeleton(player_opts=None) -> html.Div:
    filter_panel = html.Div([
        html.Div("Filters", style=_SECTION_TITLE),
        html.Div("Player", style=_LABEL_STYLE),
        dcc.Dropdown(id='odt-player-filter', options=player_opts or [], value=None, multi=True,
                     placeholder="All players…", style={'fontSize': '0.75rem'}),
        html.Hr(style={'borderColor': COLORS['dark_border'], 'margin': '10px 0 4px'}),
        html.Div("Loss Type", style=_LABEL_STYLE),
        dcc.Checklist(
            id='odt-loss-type',
            options=[{'label': f'  {t}', 'value': t} for t in _ALL_LOSS_TYPES],
            value=_ALL_LOSS_TYPES,
            inputStyle={'cursor': 'pointer', 'accentColor': GOLD},
            labelStyle={'color': COLORS['text_secondary'], 'fontSize': '0.75rem', 'display': 'block', 'marginBottom': '4px'},
        ),
        html.Hr(style={'borderColor': COLORS['dark_border'], 'margin': '10px 0 4px'}),
        html.Div("Next 15s Outcome", style=_LABEL_STYLE),
        dcc.Checklist(
            id='odt-outcome-filter',
            options=[{'label': f'  {t}', 'value': t} for t in _ALL_DEF_OUTCOMES],
            value=_ALL_DEF_OUTCOMES,
            inputStyle={'cursor': 'pointer', 'accentColor': GOLD},
            labelStyle={'color': COLORS['text_secondary'], 'fontSize': '0.75rem', 'display': 'block', 'marginBottom': '4px'},
        ),
        *PassMap.dash_controls(show=['h1_time', 'h2_time'], id_prefix='odt'),
    ], style=_PANEL_STYLE)

    combined = html.Div([
        html.Div(id='odt-kpi-bar', children=[]),
        html.Hr(style={'borderColor': COLORS['dark_border'], 'margin': '10px 0 14px'}),
        dbc.Row([
            dbc.Col([
                html.Div("Possession Loss Map", style=_SECTION_TITLE),
                html.Div("Location of every possession loss · shape = 15s outcome",
                         style={'color': COLORS['text_secondary'], 'fontSize': '0.62rem',
                                'fontStyle': 'italic', 'marginBottom': '8px'}),
                dcc.Loading(type='circle', color=GOLD, children=dcc.Graph(
                    id='odt-pitch-map', figure=_skel_fig(600), config=CHART_CFG, style={'width': '100%'},
                )),
                html.Hr(style={'borderColor': COLORS['dark_border'], 'margin': '14px 0 10px'}),
                html.Div("Possession Loss Heatmap", style=_SECTION_TITLE),
                dcc.Loading(type='circle', color=GOLD, children=html.Img(
                    id='odt-heatmap-img', src=_SKEL_SRC,
                    style={'width': '100%', 'borderRadius': '6px', 'minHeight': '200px'},
                )),
            ], md=8),
            dbc.Col([
                html.Div("Losses by Player", style={**_SECTION_TITLE, 'fontSize': '0.75rem'}),
                html.Div(style={'marginBottom': '6px'}),
                html.Div(id='odt-stats-table', children=[]),
                html.Hr(style={'borderColor': COLORS['dark_border'], 'margin': '10px 0 8px'}),
                html.Div("Losses by Zone", style={**_SECTION_TITLE, 'marginBottom': '6px'}),
                dcc.Loading(type='circle', color=GOLD, children=dcc.Graph(
                    id='odt-zone-donut', figure=_skel_fig(220), config=CHART_CFG, style={'width': '100%'},
                )),
                html.Hr(style={'borderColor': COLORS['dark_border'], 'margin': '10px 0 8px'}),
                html.Div("Transition Outcome", style={**_SECTION_TITLE, 'marginBottom': '6px'}),
                dcc.Loading(type='circle', color=GOLD, children=dcc.Graph(
                    id='odt-trans-outcomes', figure=_skel_fig(260), config=CHART_CFG, style={'width': '100%'},
                )),
            ], md=4, style={'borderLeft': f'1px solid {COLORS["dark_border"]}', 'paddingLeft': '14px'}),
        ], align='start', className='g-0'),
    ], style=_PANEL_STYLE)

    return html.Div(
        dbc.Row([
            dbc.Col(filter_panel, md=2),
            dbc.Col(combined,     md=10),
        ], align='start', className='g-3'),
    )


# =============================================================================
# Public builder
# =============================================================================

def build_transitions(team: str | None = None,
                      comp_key: str | None = None) -> dbc.Tabs:
    """Return the Transitions tab layout (two skeleton sub-tabs)."""
    atk_player_opts = []
    def_player_opts = []

    if team and comp_key:
        opp_ev, _ = load_opp_events(team, comp_key, 'all', None, None, SEASON)
        if not opp_ev.empty and 'event_type' in opp_ev.columns:
            def _opts(df_sub):
                if 'player_name' not in df_sub.columns: return []
                names = df_sub['player_name'].dropna().unique()
                return sorted([{'label': n, 'value': n} for n in names], key=lambda d: d['label'])

            gain_mask = (
                opp_ev['event_type'].isin(['Ball recovery', 'Interception']) |
                ((opp_ev['event_type'] == 'Tackle') & (opp_ev.get('outcome', pd.Series()) == 1))
            )
            atk_player_opts = _opts(opp_ev[gain_mask])

            loss_mask = (
                ((opp_ev['event_type'] == 'Pass') & (opp_ev.get('outcome', pd.Series()) == 0)) |
                opp_ev['event_type'].isin(['Miscontrol', 'Dispossessed', 'Offside Pass', 'Error']) |
                (opp_ev['event_type'].isin(['Challenge', 'Aerial']) & (opp_ev.get('outcome', pd.Series()) == 0))
            )
            def_player_opts = _opts(opp_ev[loss_mask])

    return dbc.Tabs(
        active_tab='otr-tab-defend',
        children=[
            dbc.Tab(
                html.Div([
                    html.Div('Transition from Attack to Defense',
                             style={'fontSize': '0.95rem', 'color': GOLD,
                                    'fontStyle': 'italic', 'marginBottom': '12px',
                                    'letterSpacing': '0.3px'}),
                    _build_defensive_skeleton(def_player_opts),
                ]),
                label='Defensive Transition',
                tab_id='otr-tab-defend',
                tab_style={'flex': '1'},
                label_style=_BTN_INACTIVE,
                active_label_style=_BTN_ACTIVE,
            ),
            dbc.Tab(
                html.Div([
                    html.Div('Transition from Defense to Attack',
                             style={'fontSize': '0.95rem', 'color': GOLD,
                                    'fontStyle': 'italic', 'marginBottom': '12px',
                                    'letterSpacing': '0.3px'}),
                    _build_attacking_skeleton(atk_player_opts),
                ]),
                label='Attacking Transition',
                tab_id='otr-tab-attack',
                tab_style={'flex': '1'},
                label_style=_BTN_INACTIVE,
                active_label_style=_BTN_ACTIVE,
            ),
        ],
        className='mb-3',
    )


# =============================================================================
# Callbacks
# =============================================================================

def register_transitions_callbacks(app) -> None:
    """Wire filter controls to transition maps."""

    def _apply_time_filter(df: pd.DataFrame, h1_range, h2_range) -> pd.DataFrame:
        if df.empty or 'period_id' not in df.columns or 'time_min' not in df.columns:
            return df
        h1_lo, h1_hi = h1_range
        h2_lo, h2_hi = h2_range
        m1 = (df['period_id'] == 1) & (df['time_min'] >= h1_lo) & (df['time_min'] <= h1_hi)
        m2 = (df['period_id'] == 2) & (df['time_min'] >= h2_lo) & (df['time_min'] <= h2_hi)
        return df[m1 | m2]

    # ── Attacking Transitions ─────────────────────────────────────────────────
    @app.callback(
        Output('oat-kpi-bar',        'children'),
        Output('oat-pitch-map',      'figure'),
        Output('oat-heatmap-img',    'src'),
        Output('oat-stats-table',    'children'),
        Output('oat-trans-outcomes', 'figure'),
        Input('oat-player-filter',   'value'),
        Input('oat-gain-type',       'value'),
        Input('oat-outcome-filter',  'value'),
        Input('oat-h1-time',         'value'),
        Input('oat-h2-time',         'value'),
        Input('oa-team-select',      'value'),
        Input('oa-comp-select',      'value'),
        Input('oa-venue-filter',     'value'),
        Input('oa-selected-matches', 'data'),
        Input('oa-date-filter',      'date'),
    )
    def _update_atk(players, gain_types, outcome_types, h1_range, h2_range,
                    team, comp, venue, match_ids, date_cutoff):

        def _empty():
            return [], _skel_fig(600), _SKEL_SRC, [], _skel_fig(260)

        if not team or not comp:
            return _empty()

        opp_ev, _ = load_opp_events(team, comp, venue or 'all',
                                    match_ids or None, date_cutoff, SEASON)
        if opp_ev.empty:
            return _empty()

        _h1 = tuple(h1_range) if h1_range else (0, 50)
        _h2 = tuple(h2_range) if h2_range else (45, 100)

        all_gains = _extract_gains(opp_ev)
        if all_gains.empty:
            return _empty()

        gains = _apply_time_filter(all_gains, _h1, _h2)
        if players and 'player_name' in gains.columns:
            gains = gains[gains['player_name'].isin(players)]

        gains = _tag_gain_outcomes(gains, opp_ev)

        _types    = gain_types    or _ALL_GAIN_TYPES
        _outcomes = outcome_types or _ALL_ATK_OUTCOMES
        gains_filtered = gains[
            gains['gain_type'].isin(_types) &
            gains['window_outcome'].isin(_outcomes)
        ] if 'window_outcome' in gains.columns else gains[gains['gain_type'].isin(_types)]

        coords = gains_filtered.dropna(subset=['x', 'y'])
        heatmap_src = (
            render_xt_heatmap_img(coords['x'].values, coords['y'].values,
                                  [1.0] * len(coords))
            if len(coords) >= 2 else _SKEL_SRC
        )

        return (
            _atk_kpi_children(gains),
            _atk_pitch_fig(gains_filtered),
            heatmap_src,
            _atk_stats_table(gains),
            _outcomes_donut_fig(gains),
        )

    # ── Defensive Transitions ─────────────────────────────────────────────────
    @app.callback(
        Output('odt-kpi-bar',        'children'),
        Output('odt-pitch-map',      'figure'),
        Output('odt-heatmap-img',    'src'),
        Output('odt-stats-table',    'children'),
        Output('odt-zone-donut',     'figure'),
        Output('odt-trans-outcomes', 'figure'),
        Input('odt-player-filter',   'value'),
        Input('odt-loss-type',       'value'),
        Input('odt-outcome-filter',  'value'),
        Input('odt-h1-time',         'value'),
        Input('odt-h2-time',         'value'),
        Input('oa-team-select',      'value'),
        Input('oa-comp-select',      'value'),
        Input('oa-venue-filter',     'value'),
        Input('oa-selected-matches', 'data'),
        Input('oa-date-filter',      'date'),
    )
    def _update_def(players, loss_types, outcome_types, h1_range, h2_range,
                    team, comp, venue, match_ids, date_cutoff):

        def _empty():
            return [], _skel_fig(600), _SKEL_SRC, [], _skel_fig(220), _skel_fig(260)

        if not team or not comp:
            return _empty()

        opp_ev, bar_ev = load_opp_events(team, comp, venue or 'all',
                                         match_ids or None, date_cutoff, SEASON)
        if opp_ev.empty:
            return _empty()

        _h1 = tuple(h1_range) if h1_range else (0, 50)
        _h2 = tuple(h2_range) if h2_range else (45, 100)

        all_losses = _extract_losses(opp_ev)
        if all_losses.empty:
            return _empty()

        losses = _apply_time_filter(all_losses, _h1, _h2)
        if players and 'player_name' in losses.columns:
            losses = losses[losses['player_name'].isin(players)]

        losses = _tag_loss_outcomes(losses, bar_ev)

        _types    = loss_types    or _ALL_LOSS_TYPES
        _outcomes = outcome_types or _ALL_DEF_OUTCOMES
        losses_filtered = losses[
            losses['loss_type'].isin(_types) &
            losses['window_outcome'].isin(_outcomes)
        ] if 'window_outcome' in losses.columns else losses[losses['loss_type'].isin(_types)]

        coords = losses_filtered.dropna(subset=['x', 'y'])
        heatmap_src = (
            render_xt_heatmap_img(coords['x'].values, coords['y'].values,
                                  [1.0] * len(coords))
            if len(coords) >= 2 else _SKEL_SRC
        )

        return (
            _def_kpi_children(losses),
            _def_pitch_fig(losses_filtered),
            heatmap_src,
            _def_stats_table(losses),
            _losses_by_zone_donut(losses),
            _loss_outcomes_donut(losses),
        )
