"""
Team Analysis — Attacking Transition sub-tab

Every time Barcelona wins possession during the opposition's in-possession
phase, the team transitions into attack.
The 15-second window after each possession-gain event is defined as the
attacking transition period for this app.

Possession-gain types:
  • Ball Recovery  — event_type 'Ball Recovery'
  • Interception   — event_type 'Interception'
  • Tackle Won     — event_type 'Tackle' with outcome == 1

15-second window outcomes (what BAR did after winning the ball):
  Goal Scored    — BAR scored within 15s
  Shot Taken     — BAR shot (no goal) within 15s
  Quick Turnover — BAR lost possession again within 15s without shooting
  Possession Held — none of the above

Layout:
  Filter panel (md=3) | Main content (md=9)

Main content:
  KPI bar (full width) →
  Row: Possession Gain Map + Heatmap below (md=8) | Stats table (md=4)
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
    render_xt_heatmap_img,
    PITCH_BG,
)

_TRANSITION_WINDOW_SEC = 15  # seconds after possession gain

# Gain event types
_GAIN_TYPES_RAW = ['Ball Recovery', 'Interception']  # always a gain
# Tackle outcome=1 handled separately

# Color per gain type
_GAIN_COLORS = {
    'Ball Recovery': '#22c55e',
    'Interception':  '#3b82f6',
    'Tackle Won':    GOLD,
}

# Shape + size per transition outcome
_OUTCOME_SYMBOLS = {
    'Goal Scored':      ('star',         14),
    'Shot Taken':       ('triangle-up',  12),
    'Quick Turnover':   ('x',            12),
    'Possession Held':  ('circle',       10),
}

_ALL_GAIN_TYPES    = list(_GAIN_COLORS.keys())
_ALL_OUTCOME_TYPES = list(_OUTCOME_SYMBOLS.keys())

# Possession-loss types (to detect Quick Turnover within the window)
_POSS_LOSS_EVENTS = ['Miscontrol', 'Dispossessed', 'Offside Pass', 'Error']

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
_SKEL_SRC  = 'data:image/png;base64,'


# =============================================================================
# Skeleton figure placeholder
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

def _extract_gains(bar: pd.DataFrame) -> pd.DataFrame:
    """
    Build a DataFrame of BAR possession-gain events with:
      gain_type, player_name, time_min, time_sec, period_id, x, y, timestamp.
    """
    rows = []
    for _, row in bar.iterrows():
        etype   = row.get('event_type', '')
        outcome = row.get('outcome', 0)

        if etype in _GAIN_TYPES_RAW:
            gain_type = etype
        elif etype == 'Tackle' and outcome == 1:
            gain_type = 'Tackle Won'
        else:
            continue

        x = row.get('x', None)
        y = row.get('y', None)
        if pd.isna(x) or pd.isna(y):
            continue

        t_min = int(row.get('time_min', 0) or 0)
        t_sec = int(row.get('time_sec', 0) or 0)

        rows.append({
            'gain_type':   gain_type,
            'player_name': row.get('player_name', '') or '',
            'time_min':    t_min,
            'time_sec':    t_sec,
            'period_id':   row.get('period_id', 1),
            'match_id':    row.get('match_id', ''),
            'x':           float(x),
            'y':           float(y),
            'timestamp':   t_min * 60 + t_sec,
        })

    return pd.DataFrame(rows) if rows else pd.DataFrame(
        columns=['gain_type', 'player_name', 'time_min', 'time_sec',
                 'period_id', 'match_id', 'x', 'y', 'timestamp']
    )


def _tag_gain_outcomes(
    gains: pd.DataFrame,
    bar: pd.DataFrame,
) -> pd.DataFrame:
    """
    Tag each possession-gain row with a 'window_outcome' string describing
    what BAR did in the 15-second window that followed.

    Priority: Goal Scored > Shot Taken > Quick Turnover > Possession Held.
    Also stores 'window_detail': relevant player/event info.
    """
    if gains.empty:
        gains = gains.copy()
        gains['window_outcome'] = ''
        gains['window_detail']  = ''
        return gains

    bar = bar.copy()
    bar['_ts'] = bar['time_min'].fillna(0).astype(int) * 60 + \
                 bar['time_sec'].fillna(0).astype(int)

    _shot_types  = ['Goal', 'Saved Shot', 'Miss']
    _loss_events = _POSS_LOSS_EVENTS + ['Miscontrol', 'Dispossessed']

    all_outcomes = {}
    all_details  = {}

    for (match_id, period_id), grp in gains.groupby(['match_id', 'period_id']):
        bar_sl = bar[(bar['match_id'] == match_id) & (bar['period_id'] == period_id)]

        for idx, gain_row in grp.iterrows():
            t0 = int(gain_row['timestamp'])
            t1 = t0 + _TRANSITION_WINDOW_SEC

            bar_win = bar_sl[(bar_sl['_ts'] > t0) & (bar_sl['_ts'] <= t1)]

            has_goal    = not bar_win.empty and (bar_win['event_type'] == 'Goal').any()
            has_shot    = not bar_win.empty and bar_win['event_type'].isin(_shot_types).any()
            has_turnover = not bar_win.empty and (
                bar_win['event_type'].isin(_loss_events).any() or
                (bar_win[bar_win['event_type'] == 'Pass']['outcome'].eq(0).any()
                 if not bar_win[bar_win['event_type'] == 'Pass'].empty else False) or
                ((bar_win['event_type'] == 'Challenge') & (bar_win['outcome'] == 0)).any()
            )

            if has_goal:
                goal_rows = bar_win[bar_win['event_type'] == 'Goal']
                scorer    = goal_rows['player_name'].iloc[0] if not goal_rows.empty else ''
                outcome = 'Goal Scored'
                detail  = f'by {scorer}' if scorer else ''
            elif has_shot:
                shot_rows  = bar_win[bar_win['event_type'].isin(_shot_types)]
                shooter    = shot_rows['player_name'].iloc[0] if not shot_rows.empty else ''
                shot_type  = shot_rows['event_type'].iloc[0]  if not shot_rows.empty else ''
                outcome = 'Shot Taken'
                detail  = f'{shot_type} — {shooter}' if shooter else shot_type
            elif has_turnover:
                outcome = 'Quick Turnover'
                detail  = ''
            else:
                outcome = 'Possession Held'
                detail  = ''

            all_outcomes[idx] = outcome
            all_details[idx]  = detail

    gains = gains.copy()
    gains['window_outcome'] = gains.index.map(lambda i: all_outcomes.get(i, 'Possession Held'))
    gains['window_detail']  = gains.index.map(lambda i: all_details.get(i, ''))
    return gains


def _bar_events_in_windows(gains: pd.DataFrame, bar: pd.DataFrame) -> pd.DataFrame:
    """BAR events within _TRANSITION_WINDOW_SEC after each possession gain."""
    if gains.empty or bar.empty:
        return pd.DataFrame()

    bar = bar.copy()
    bar['_ts'] = bar['time_min'].fillna(0).astype(int) * 60 + \
                 bar['time_sec'].fillna(0).astype(int)

    parts = []
    for (match_id, period_id), grp in gains.groupby(['match_id', 'period_id']):
        bar_sl = bar[(bar['match_id'] == match_id) & (bar['period_id'] == period_id)]
        if bar_sl.empty:
            continue
        for t_gain in grp['timestamp']:
            window = bar_sl[
                (bar_sl['_ts'] > t_gain) &
                (bar_sl['_ts'] <= t_gain + _TRANSITION_WINDOW_SEC)
            ]
            parts.append(window)

    if not parts:
        return pd.DataFrame()
    return pd.concat(parts, ignore_index=True).drop_duplicates()


def _apply_time_filter(df: pd.DataFrame, h1_range, h2_range) -> pd.DataFrame:
    if 'period_id' not in df.columns or 'time_min' not in df.columns:
        return df
    h1_lo, h1_hi = h1_range
    h2_lo, h2_hi = h2_range
    m1 = (df['period_id'] == 1) & (df['time_min'] >= h1_lo) & (df['time_min'] <= h1_hi)
    m2 = (df['period_id'] == 2) & (df['time_min'] >= h2_lo) & (df['time_min'] <= h2_hi)
    return df[m1 | m2]


# =============================================================================
# KPI bar
# =============================================================================

def _kpi_children(gains: pd.DataFrame, bar_in_windows: pd.DataFrame) -> list:
    def _card(value, label, color=COLORS['text_primary']):
        return html.Div([
            html.Div(str(value), style={
                'color': color, 'fontWeight': '800',
                'fontSize': '1.35rem', 'lineHeight': '1.1',
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
            'borderRadius': '6px',
            'padding': '8px 10px',
            'flex': '1', 'minWidth': '0',
        })

    total       = len(gains)
    own_half    = int((gains['x'] < 50).sum())  if not gains.empty else 0
    opp_half    = int((gains['x'] >= 50).sum()) if not gains.empty else 0
    fin_third   = int((gains['x'] >= 66.67).sum()) if not gains.empty else 0

    _shot_types = ['Goal', 'Saved Shot', 'Miss']
    if not bar_in_windows.empty and 'event_type' in bar_in_windows.columns:
        shots_taken = int(bar_in_windows['event_type'].isin(_shot_types).sum())
        goals_scored = int((bar_in_windows['event_type'] == 'Goal').sum())
    else:
        shots_taken = goals_scored = 0

    col = gains['window_outcome'] if not gains.empty and 'window_outcome' in gains.columns \
          else pd.Series(dtype=str)
    quick_turnovers = int((col == 'Quick Turnover').sum())

    cards = [
        _card(total,          'Total Gains',     HOME_COLOR),
        _card(own_half,       'Own-Half Gains',  GOLD),
        _card(opp_half,       'Opp-Half Gains',  HOME_COLOR),
        _card(fin_third,      'Final Third',     HOME_COLOR),
        _card(shots_taken,    'Led to Shot',     GOLD),
        _card(goals_scored,   'Led to Goal',     '#22c55e'),
        _card(quick_turnovers,'Quick Turnovers', AWAY_COLOR),
    ]
    return [html.Div(cards, style={'display': 'flex', 'gap': '6px', 'flexWrap': 'wrap'})]


# =============================================================================
# Possession Gain Pitch Map
# =============================================================================

def _add_attack_direction(fig: go.Figure) -> None:
    fig.add_annotation(
        x=0.5, y=1.02, xref='paper', yref='paper',
        text='<b>➡  Direction of Attack</b>',
        showarrow=False,
        font=dict(size=10, color='white', family='Arial, sans-serif'),
        xanchor='center', yanchor='bottom',
        bgcolor='rgba(21,25,50,0.8)',
        bordercolor='#8899CC',
        borderwidth=1, borderpad=4,
    )


def _pitch_map_fig(gains: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    add_pitch_background(fig, half=False)

    has_outcome = 'window_outcome' in gains.columns

    # Real data traces — color = gain type, shape = transition outcome
    for outcome, (symbol, size) in _OUTCOME_SYMBOLS.items():
        for gain_type, color in _GAIN_COLORS.items():
            if has_outcome:
                subset = gains[
                    (gains['gain_type'] == gain_type) &
                    (gains['window_outcome'] == outcome)
                ]
            else:
                subset = gains[gains['gain_type'] == gain_type]

            if subset.empty:
                continue

            custom = []
            for _, row in subset.iterrows():
                player      = row['player_name'] or 'Unknown'
                t_str       = f"{int(row['time_min'])}'"
                detail      = row.get('window_detail', '')
                detail_line = f'<br>↳ {detail}' if detail else ''
                custom.append([player, t_str, gain_type, outcome, detail_line])

            fig.add_trace(go.Scatter(
                x=subset['x'], y=subset['y'],
                mode='markers',
                name=gain_type,
                legendgroup=f'gain_{gain_type}',
                showlegend=False,
                marker=dict(
                    color=color,
                    symbol=symbol,
                    size=size,
                    opacity=0.90,
                    line=dict(color='white', width=0.8),
                ),
                customdata=custom,
                hovertemplate=(
                    '<b>%{customdata[0]}</b><br>'
                    'Time: %{customdata[1]}<br>'
                    'How: %{customdata[2]}<br>'
                    '<b>Next 15s:</b> %{customdata[3]}'
                    '%{customdata[4]}'
                    '<extra></extra>'
                ),
            ))

    # Legend 1 (top-left) — Gain Type (solid circles, gain colors)
    for i, (gain_type, color) in enumerate(_GAIN_COLORS.items()):
        fig.add_trace(go.Scatter(
            x=[None], y=[None], mode='markers',
            name=gain_type,
            legend='legend',
            legendgroup=f'gain_{gain_type}',
            legendgrouptitle_text='Gain Type' if i == 0 else '',
            showlegend=True,
            marker=dict(color=color, symbol='circle', size=10,
                        line=dict(color='white', width=0.8)),
        ))

    # Legend 2 (top-right) — Next 15s Outcome (shapes, neutral grey)
    for i, (outcome, (symbol, size)) in enumerate(_OUTCOME_SYMBOLS.items()):
        fig.add_trace(go.Scatter(
            x=[None], y=[None], mode='markers',
            name=outcome,
            legend='legend2',
            legendgroup=f'outcome_{outcome}',
            legendgrouptitle_text='Next 15s' if i == 0 else '',
            showlegend=True,
            marker=dict(color='#e2e8f0', symbol=symbol, size=size,
                        line=dict(color='white', width=0.8)),
        ))

    # Third dividers
    for x_pos, label in ((100 / 3, 'Z1  Def Third'), (200 / 3, 'Z3  Att Third')):
        fig.add_shape(
            type='line',
            x0=x_pos, x1=x_pos, y0=-2, y1=102,
            xref='x', yref='y',
            line=dict(color='rgba(255,255,255,0.15)', width=1.5, dash='dash'),
            layer='above',
        )
        fig.add_annotation(
            x=x_pos, y=103, xref='x', yref='y',
            text=f'<b>{label}</b>',
            showarrow=False,
            font=dict(size=8, color='rgba(255,255,255,0.40)', family='Arial, sans-serif'),
            xanchor='center', yanchor='bottom',
        )

    # Zone labels
    for x_centre, zone_name in [(16.67, 'Zone 1'), (50.0, 'Zone 2'), (83.33, 'Zone 3')]:
        fig.add_annotation(
            x=x_centre, y=2, xref='x', yref='y',
            text=zone_name,
            showarrow=False,
            font=dict(size=9, color='rgba(255,255,255,0.20)', family='Arial Black'),
            xanchor='center', yanchor='bottom',
        )

    _add_attack_direction(fig)
    fig.update_layout(
        **PITCH_AXIS_FULL,
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font=dict(color='#E8E9ED', size=12, family='Arial, sans-serif'),
        height=600,
        hovermode='closest',
        uirevision='atk-trans-pitch-map',
        legend=dict(
            orientation='v',
            x=1.01, y=1.0,
            xanchor='left', yanchor='top',
            bgcolor='rgba(21,25,50,0.88)',
            bordercolor=COLORS.get('dark_border', 'rgba(255,255,255,0.15)'),
            borderwidth=1,
            font=dict(color=COLORS['text_primary'], size=10),
            groupclick='toggleitem',
        ),
        legend2=dict(
            orientation='v',
            x=1.01, y=0.45,
            xanchor='left', yanchor='top',
            bgcolor='rgba(21,25,50,0.88)',
            bordercolor=COLORS.get('dark_border', 'rgba(255,255,255,0.15)'),
            borderwidth=1,
            font=dict(color=COLORS['text_primary'], size=10),
            groupclick='toggleitem',
        ),
        margin=dict(l=0, r=150, t=36, b=0),
    )
    return fig


# =============================================================================
# Heatmap
# =============================================================================

def _heatmap_src(gains: pd.DataFrame) -> str:
    coords = gains.dropna(subset=['x', 'y'])
    if len(coords) < 2:
        return _SKEL_SRC
    return render_xt_heatmap_img(
        coords['x'].values,
        coords['y'].values,
        [1.0] * len(coords),
    )


# =============================================================================
# Transition outcome ring chart
# =============================================================================

def _transition_outcomes_fig(gains: pd.DataFrame) -> go.Figure:
    """Ring (donut) chart showing how each attacking transition resolved."""
    labels = ['Possession Held', 'Quick Turnover', 'Shot Taken', 'Goal Scored']
    colors = ['#6b7280',          AWAY_COLOR,        GOLD,          '#22c55e']
    col    = gains['window_outcome'] if not gains.empty and 'window_outcome' in gains.columns \
             else pd.Series(dtype=str)
    values = [int((col == l).sum()) for l in labels]

    fig = go.Figure(go.Pie(
        labels=labels,
        values=values,
        marker=dict(colors=colors, line=dict(color=PITCH_BG, width=2)),
        hole=0.55,
        textinfo='percent',
        textfont=dict(color='white', size=11),
        hovertemplate='<b>%{label}</b><br>%{value} transitions (%{percent})<extra></extra>',
        sort=False,
    ))
    fig.update_layout(
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font=dict(color='#E8E9ED', size=11, family='Arial, sans-serif'),
        height=260,
        margin=dict(l=0, r=0, t=10, b=0),
        showlegend=True,
        legend=dict(
            orientation='v',
            x=1.0, y=0.5,
            xanchor='left', yanchor='middle',
            font=dict(color=COLORS['text_primary'], size=9),
            bgcolor='rgba(0,0,0,0)',
        ),
        uirevision='atk-trans-outcomes',
    )
    return fig


# =============================================================================
# BAR event types in window bar chart
# =============================================================================

def _transition_event_types_fig(bar_in_windows: pd.DataFrame) -> go.Figure:
    """Top-N BAR event types during attacking transition windows."""
    if bar_in_windows.empty or 'event_type' not in bar_in_windows.columns:
        fig = go.Figure()
        fig.update_layout(
            paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor=PITCH_BG,
            height=280, margin=dict(l=10, r=10, t=10, b=10),
        )
        return fig

    _shot_types = ['Goal', 'Saved Shot', 'Miss']

    counts = (
        bar_in_windows['event_type']
        .value_counts()
        .head(10)
        .sort_values(ascending=True)
    )

    bar_colors = []
    for etype in counts.index:
        if etype == 'Goal':
            bar_colors.append('#22c55e')
        elif etype in _shot_types:
            bar_colors.append(GOLD)
        elif etype == 'Pass':
            bar_colors.append('#3b82f6')
        else:
            bar_colors.append('#6b7280')

    fig = go.Figure(go.Bar(
        y=counts.index.tolist(),
        x=counts.values.tolist(),
        orientation='h',
        marker_color=bar_colors,
        hovertemplate='%{y}: %{x}<extra></extra>',
    ))
    fig.update_layout(
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor=PITCH_BG,
        font=dict(color='#E8E9ED', size=10, family='Arial, sans-serif'),
        height=280,
        margin=dict(l=10, r=10, t=10, b=10),
        xaxis=dict(showgrid=False, zeroline=False, title='Count',
                   title_font=dict(size=9), tickfont=dict(size=9)),
        yaxis=dict(showgrid=False, tickfont=dict(size=10)),
        showlegend=False,
        uirevision='atk-trans-event-types',
    )
    return fig


# =============================================================================
# Stats table
# =============================================================================

def _stats_table_children(gains: pd.DataFrame, top_n: int = 12) -> list:
    _no_data = [html.P("No data", style={
        'color': COLORS['text_secondary'], 'fontSize': '0.75rem',
        'textAlign': 'center', 'marginTop': '8px',
    })]

    if gains.empty or 'player_name' not in gains.columns:
        return _no_data

    rows_data = []
    for player, grp in gains.groupby('player_name'):
        if not player:
            continue
        total  = len(grp)
        z1     = int((grp['x'] < 33.33).sum())
        z2     = int(((grp['x'] >= 33.33) & (grp['x'] < 66.67)).sum())
        z3     = int((grp['x'] >= 66.67).sum())
        br     = int((grp['gain_type'] == 'Ball Recovery').sum())
        interc = int((grp['gain_type'] == 'Interception').sum())
        tkl    = int((grp['gain_type'] == 'Tackle Won').sum())
        rows_data.append({
            'player': player, 'total': total,
            'z1': z1, 'z2': z2, 'z3': z3,
            'br': br, 'int': interc, 'tkl': tkl,
        })

    rows_data.sort(key=lambda r: r['total'], reverse=True)
    rows_data = rows_data[:top_n]

    if not rows_data:
        return _no_data

    header = html.Tr([
        html.Th('Player', style={**_TH, 'textAlign': 'left'}),
        html.Th('Tot',    style=_TH),
        html.Th('Z1',     style=_TH),
        html.Th('Z2',     style=_TH),
        html.Th('Z3',     style=_TH),
        html.Th('BR',     style=_TH),
        html.Th('Int',    style=_TH),
        html.Th('Tkl',    style=_TH),
    ])

    table_rows = []
    for idx, s in enumerate(rows_data):
        bg    = (COLORS.get('dark_tertiary', 'rgba(255,255,255,0.03)')
                 if idx % 2 == 0 else 'transparent')
        short = s['player'].split()[-1] if s['player'] else '—'
        table_rows.append(html.Tr([
            html.Td(short,          style=_NAME_TD),
            html.Td(str(s['total']),style={**_TD, 'color': HOME_COLOR, 'fontWeight': '700'}),
            html.Td(str(s['z1']),   style=_TD),
            html.Td(str(s['z2']),   style=_TD),
            html.Td(str(s['z3']),   style={**_TD, 'color': GOLD}),
            html.Td(str(s['br']),   style={**_TD, 'color': '#22c55e'}),
            html.Td(str(s['int']),  style={**_TD, 'color': '#3b82f6'}),
            html.Td(str(s['tkl']),  style={**_TD, 'color': GOLD}),
        ], style={'backgroundColor': bg}))

    legend = html.Div(
        "Z1 = Def Third  ·  Z2 = Mid Third  ·  Z3 = Att Third  ·  "
        "BR = Ball Recovery  ·  Int = Interception  ·  Tkl = Tackle Won",
        style={
            'color': COLORS['text_secondary'], 'fontSize': '0.55rem',
            'fontStyle': 'italic', 'marginBottom': '4px',
        },
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


def _zone_summary_children(gains: pd.DataFrame) -> list:
    if gains.empty:
        return []

    total = max(len(gains), 1)
    z1 = int((gains['x'] < 33.33).sum())
    z2 = int(((gains['x'] >= 33.33) & (gains['x'] < 66.67)).sum())
    z3 = int((gains['x'] >= 66.67).sum())

    def _zone_row(label, count, color):
        pct = round(count / total * 100)
        return html.Div([
            html.Span(label, style={
                'color': COLORS['text_secondary'], 'fontSize': '0.68rem',
                'minWidth': '80px',
            }),
            html.Div(style={
                'flex': '1', 'height': '6px',
                'backgroundColor': COLORS['dark_border'],
                'borderRadius': '3px', 'overflow': 'hidden',
                'margin': '0 8px',
            }, children=[
                html.Div(style={
                    'width': f'{pct}%', 'height': '100%',
                    'backgroundColor': color, 'borderRadius': '3px',
                }),
            ]),
            html.Span(f'{count}  ({pct}%)', style={
                'color': color, 'fontSize': '0.68rem',
                'fontWeight': '700', 'minWidth': '60px', 'textAlign': 'right',
            }),
        ], style={'display': 'flex', 'alignItems': 'center', 'padding': '4px 0'})

    return [
        html.Hr(style={'borderColor': COLORS['dark_border'], 'margin': '10px 0 8px'}),
        html.Div("Gains by Zone", style={**_SECTION_TITLE, 'marginBottom': '6px'}),
        _zone_row('Zone 1 (Def Third)', z1, AWAY_COLOR),
        _zone_row('Zone 2 (Mid Third)', z2, GOLD),
        _zone_row('Zone 3 (Att Third)', z3, HOME_COLOR),
    ]


# =============================================================================
# Filter panel
# =============================================================================

def _filter_panel(player_options=None) -> html.Div:
    return html.Div([
        html.Div("Filters", style=_SECTION_TITLE),

        html.Div("Player", style=_LABEL_STYLE),
        dcc.Dropdown(
            id='at-player-filter',
            options=player_options or [],
            value=None,
            multi=True,
            placeholder="All players…",
            style={'fontSize': '0.75rem'},
        ),

        html.Hr(style={'borderColor': COLORS['dark_border'], 'margin': '10px 0 4px'}),
        html.Div("Gain Type", style=_LABEL_STYLE),
        dcc.Checklist(
            id='at-gain-type',
            options=[{'label': f'  {t}', 'value': t} for t in _ALL_GAIN_TYPES],
            value=_ALL_GAIN_TYPES,
            inputStyle={'cursor': 'pointer', 'accentColor': GOLD},
            labelStyle={
                'color': COLORS['text_secondary'], 'fontSize': '0.75rem',
                'display': 'block', 'marginBottom': '4px',
            },
        ),

        html.Hr(style={'borderColor': COLORS['dark_border'], 'margin': '10px 0 4px'}),
        html.Div("Next 15s Outcome", style=_LABEL_STYLE),
        dcc.Checklist(
            id='at-outcome-filter',
            options=[{'label': f'  {t}', 'value': t} for t in _ALL_OUTCOME_TYPES],
            value=_ALL_OUTCOME_TYPES,
            inputStyle={'cursor': 'pointer', 'accentColor': GOLD},
            labelStyle={
                'color': COLORS['text_secondary'], 'fontSize': '0.75rem',
                'display': 'block', 'marginBottom': '4px',
            },
        ),

        *PassMap.dash_controls(show=['h1_time', 'h2_time'], id_prefix='at'),
    ], style=_PANEL_STYLE)


# =============================================================================
# Public builder  (called from transitions.py as build_attacking_transition_skeleton)
# =============================================================================

def build_attacking_transition_skeleton() -> html.Div:
    """Skeleton layout — all data filled by register_attacking_transition_callbacks."""
    events = get_all_events(CURRENT_SEASON)

    player_opts = []
    if not events.empty:
        bar = events[events['team_code'] == 'BAR']
        gain_bar = bar[
            bar['event_type'].isin(_GAIN_TYPES_RAW) |
            ((bar['event_type'] == 'Tackle') & (bar['outcome'] == 1))
        ]
        if 'player_name' in gain_bar.columns:
            names = gain_bar['player_name'].dropna().unique()
            player_opts = sorted(
                [{'label': n, 'value': n} for n in names],
                key=lambda d: d['label'],
            )

    combined = html.Div([
        # KPI bar
        html.Div(id='at-kpi-bar', children=[]),
        html.Hr(style={'borderColor': COLORS['dark_border'], 'margin': '10px 0 14px'}),

        dbc.Row([
            dbc.Col([
                html.Div("Possession Gain Map", style=_SECTION_TITLE),
                html.Div(
                    "Location of every possession gain · hover for who, when, how · "
                    "shape shows what Barcelona did in the next 15 seconds",
                    style={
                        'color': COLORS['text_secondary'], 'fontSize': '0.62rem',
                        'fontStyle': 'italic', 'marginBottom': '8px',
                    },
                ),
                dcc.Loading(
                    type='circle', color=GOLD,
                    children=dcc.Graph(
                        id='at-pitch-map',
                        figure=_skel_fig(600),
                        config=CHART_CFG,
                        style={'width': '100%'},
                    ),
                ),

                html.Hr(style={'borderColor': COLORS['dark_border'], 'margin': '14px 0 10px'}),

                html.Div("Possession Gain Heatmap", style=_SECTION_TITLE),
                html.Div(
                    "Density of all possession gains on the pitch",
                    style={
                        'color': COLORS['text_secondary'], 'fontSize': '0.62rem',
                        'fontStyle': 'italic', 'marginBottom': '8px',
                    },
                ),
                dcc.Loading(
                    type='circle', color=GOLD,
                    children=html.Img(
                        id='at-heatmap-img',
                        src=_SKEL_SRC,
                        style={'width': '100%', 'borderRadius': '6px', 'minHeight': '200px'},
                    ),
                ),
            ], md=8),

            dbc.Col([
                html.Div("Gains by Player", style={**_SECTION_TITLE, 'fontSize': '0.75rem'}),
                html.Div(style={'marginBottom': '6px'}),
                html.Div(id='at-stats-table', children=[]),
                html.Div(id='at-zone-summary', children=[]),

                html.Hr(style={'borderColor': COLORS['dark_border'], 'margin': '10px 0 8px'}),
                html.Div("Transition Outcome", style={**_SECTION_TITLE, 'marginBottom': '6px'}),
                html.Div(
                    "How each 15s window resolved",
                    style={'color': COLORS['text_secondary'], 'fontSize': '0.60rem',
                           'fontStyle': 'italic', 'marginBottom': '6px'},
                ),
                dcc.Loading(
                    type='circle', color=GOLD,
                    children=dcc.Graph(
                        id='at-trans-outcomes',
                        figure=_skel_fig(260),
                        config=CHART_CFG,
                        style={'width': '100%'},
                    ),
                ),

                html.Hr(style={'borderColor': COLORS['dark_border'], 'margin': '10px 0 8px'}),
                html.Div("Barça Actions in Window", style={**_SECTION_TITLE, 'marginBottom': '6px'}),
                html.Div(
                    "Top event types by Barcelona during transition",
                    style={'color': COLORS['text_secondary'], 'fontSize': '0.60rem',
                           'fontStyle': 'italic', 'marginBottom': '6px'},
                ),
                dcc.Loading(
                    type='circle', color=GOLD,
                    children=dcc.Graph(
                        id='at-trans-event-types',
                        figure=_skel_fig(280),
                        config=CHART_CFG,
                        style={'width': '100%'},
                    ),
                ),
            ], md=4, style={
                'borderLeft': f'1px solid {COLORS["dark_border"]}',
                'paddingLeft': '14px',
            }),
        ], align='start', className='g-0'),
    ], style=_PANEL_STYLE)

    return html.Div(
        dbc.Row([
            dbc.Col(_filter_panel(player_opts), md=2),
            dbc.Col(combined,                   md=10),
        ], align='start', className='g-3'),
    )


# =============================================================================
# Callbacks
# =============================================================================

def register_attacking_transition_callbacks(app) -> None:
    """Wire filter controls to KPI bar, pitch map, heatmap, and stats table."""

    @app.callback(
        Output('at-kpi-bar',           'children'),
        Output('at-pitch-map',         'figure'),
        Output('at-heatmap-img',       'src'),
        Output('at-stats-table',       'children'),
        Output('at-zone-summary',      'children'),
        Output('at-trans-outcomes',    'figure'),
        Output('at-trans-event-types', 'figure'),
        Input('at-player-filter',      'value'),
        Input('at-gain-type',          'value'),
        Input('at-outcome-filter',     'value'),
        Input('at-h1-time',            'value'),
        Input('at-h2-time',            'value'),
        State('ta-competition-selector', 'value'),
        State('ta-venue-selector',       'value'),
        State('ta-selected-matches',     'data'),
        State('ta-match-data',           'data'),
    )
    def _update(players, gain_types, outcome_types, h1_range, h2_range,
                competition, venue, match_ids, match_data):

        def _empty():
            return [], _skel_fig(600), _SKEL_SRC, [], [], _skel_fig(260), _skel_fig(280)

        events = get_all_events(CURRENT_SEASON)
        if events.empty:
            return _empty()

        # Global filters
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

        # Extract all possession gains
        all_gains = _extract_gains(bar)
        if all_gains.empty:
            return _empty()

        # Apply time filter
        _h1 = tuple(h1_range) if h1_range else (0, 50)
        _h2 = tuple(h2_range) if h2_range else (45, 100)
        gains = _apply_time_filter(all_gains, _h1, _h2)

        # Apply player filter
        if players and 'player_name' in gains.columns:
            gains = gains[gains['player_name'].isin(players)]

        # Tag each gain with what happened in the next 15 seconds
        bar_in_windows = _bar_events_in_windows(gains, bar)
        gains          = _tag_gain_outcomes(gains, bar)

        # Apply gain-type / outcome filters for pitch map
        _types    = gain_types    if gain_types    else _ALL_GAIN_TYPES
        _outcomes = outcome_types if outcome_types else _ALL_OUTCOME_TYPES
        gains_filtered = gains[
            gains['gain_type'].isin(_types) &
            gains['window_outcome'].isin(_outcomes)
        ]

        kpi             = _kpi_children(gains, bar_in_windows)
        pitch_fig       = _pitch_map_fig(gains_filtered)
        heatmap_src     = _heatmap_src(gains_filtered)
        stats_table     = _stats_table_children(gains)
        zone_summary    = _zone_summary_children(gains)
        outcomes_fig    = _transition_outcomes_fig(gains)
        event_types_fig = _transition_event_types_fig(bar_in_windows)

        return (kpi, pitch_fig, heatmap_src,
                stats_table, zone_summary, outcomes_fig, event_types_fig)
