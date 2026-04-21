"""
Team Analysis — Defensive Transition sub-tab

Every time Barcelona loses possession, the team must transition into defence.
The 30-second window after each possession-loss event is defined as the
defensive transition period for this app.

Possession-loss types:
  • Failed Pass   — Pass with outcome == 0
  • Miscontrol    — event_type 'Miscontrol'
  • Dispossessed  — event_type 'Dispossessed' (Opta-explicit dispossession by opponent)
  • Lost Duel     — event_type 'Challenge' outcome == 0 (ground duel/tackle lost)
  • Lost Aerial   — event_type 'Aerial'    outcome == 0 (aerial duel lost)
  • Offside Pass  — event_type 'Offside Pass'
  • Error         — event_type 'Error'

Note: Dispossessed + Lost Duel together cover all opposition tackle/challenge
scenarios. Dispossessed is Opta's explicit tag; Lost Duel catches the remainder
(Challenge is always recorded outcome=0 on the losing side).

Layout:
  Filter panel (md=3) | Main content (md=9)

Main content:
  KPI bar (full width) →
  Row: Possession Loss Map + Heatmap below (md=8) | Stats table (md=4)
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

_TRANSITION_WINDOW_SEC = 30  # seconds after possession loss

# Raw event types that constitute a possession loss (non-Pass, non-outcome-gated)
_POSS_LOSS_RAW = ['Miscontrol', 'Dispossessed', 'Offside Pass', 'Error']

# Color per loss type — filled solid markers
_LOSS_COLORS = {
    'Failed Pass':  '#ef4444',
    'Miscontrol':   '#f97316',
    'Dispossessed': '#3b82f6',
    'Lost Duel':    '#06b6d4',
    'Lost Aerial':  '#8b5cf6',
    'Offside Pass': '#eab308',
    'Error':        '#a855f7',
}

# Shape per transition outcome (fill=True — all solid markers)
_OUTCOME_SYMBOLS = {
    'Goal Conceded':   ('star',          14),
    'Shot Conceded':   ('triangle-up',   12),
    'Barça Recovered': ('circle',        11),
    'No Clear Threat': ('square',        10),
}

_ALL_LOSS_TYPES    = list(_LOSS_COLORS.keys())
_ALL_OUTCOME_TYPES = list(_OUTCOME_SYMBOLS.keys())

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

def _extract_losses(bar: pd.DataFrame, all_events: pd.DataFrame) -> pd.DataFrame:
    """
    Build a DataFrame of BAR possession-loss events with:
      loss_type, player_name, time_min, time_sec, period_id, x, y,
      timestamp (seconds), opponent_player (if available via Related event ID).

    'opponent_player' is populated for Dispossessed events where the Related
    event ID links to an opponent tackle/ball-recovery event.
    """
    rows = []

    # Build a fast lookup: event_id → (player_name, team_code)
    has_event_id  = 'event_id' in all_events.columns
    has_related   = 'Related event ID' in all_events.columns
    has_team_code = 'team_code' in all_events.columns

    if has_event_id and has_team_code:
        eid_to_player = dict(zip(
            all_events['event_id'].astype(str),
            all_events['player_name'].fillna(''),
        ))
        eid_to_team = dict(zip(
            all_events['event_id'].astype(str),
            all_events['team_code'].fillna(''),
        ))
    else:
        eid_to_player = {}
        eid_to_team   = {}

    def _resolve_opponent(row) -> str:
        """Return opponent player name via Related event ID, or empty string."""
        if not has_related:
            return ''
        rid = str(row.get('Related event ID', ''))
        if not rid or rid in ('nan', 'None', ''):
            return ''
        player = eid_to_player.get(rid, '')
        team   = eid_to_team.get(rid, '')
        # Only return if it's NOT a Barcelona player
        if player and team and team != 'BAR':
            return player
        return ''

    for _, row in bar.iterrows():
        etype = row.get('event_type', '')
        outcome = row.get('outcome', 1)

        # Determine loss type
        if etype == 'Pass' and outcome == 0:
            loss_type = 'Failed Pass'
        elif etype == 'Challenge' and outcome == 0:
            loss_type = 'Lost Duel'
        elif etype == 'Aerial' and outcome == 0:
            loss_type = 'Lost Aerial'
        elif etype in _POSS_LOSS_RAW:
            loss_type = etype  # 'Miscontrol', 'Dispossessed', etc.
        else:
            continue

        t_min = row.get('time_min', 0) or 0
        t_sec = row.get('time_sec', 0) or 0
        x     = row.get('x', None)
        y     = row.get('y', None)

        # Only include events with valid coordinates
        if pd.isna(x) or pd.isna(y):
            continue

        opp_player = _resolve_opponent(row) if loss_type == 'Dispossessed' else ''

        rows.append({
            'loss_type':       loss_type,
            'player_name':     row.get('player_name', '') or '',
            'time_min':        int(t_min),
            'time_sec':        int(t_sec),
            'period_id':       row.get('period_id', 1),
            'match_id':        row.get('match_id', ''),
            'x':               float(x),
            'y':               float(y),
            'timestamp':       int(t_min) * 60 + int(t_sec),
            'opponent_player': opp_player,
        })

    return pd.DataFrame(rows) if rows else pd.DataFrame(
        columns=['loss_type', 'player_name', 'time_min', 'time_sec',
                 'period_id', 'match_id', 'x', 'y', 'timestamp', 'opponent_player']
    )


def _opp_events_in_windows(losses: pd.DataFrame, opp: pd.DataFrame) -> pd.DataFrame:
    """
    Return opponent events that occurred within _TRANSITION_WINDOW_SEC seconds
    after any possession loss in the same match and period.
    """
    if losses.empty or opp.empty:
        return pd.DataFrame()

    opp = opp.copy()
    if 'time_min' not in opp.columns or 'time_sec' not in opp.columns:
        return pd.DataFrame()

    opp['timestamp'] = opp['time_min'].fillna(0).astype(int) * 60 + \
                       opp['time_sec'].fillna(0).astype(int)

    result_parts = []
    for (match_id, period_id), loss_grp in losses.groupby(['match_id', 'period_id']):
        opp_slice = opp[
            (opp['match_id'] == match_id) &
            (opp['period_id'] == period_id)
        ]
        if opp_slice.empty:
            continue
        for t_loss in loss_grp['timestamp']:
            window = opp_slice[
                (opp_slice['timestamp'] >= t_loss) &
                (opp_slice['timestamp'] <= t_loss + _TRANSITION_WINDOW_SEC)
            ]
            result_parts.append(window)

    if not result_parts:
        return pd.DataFrame()
    return pd.concat(result_parts, ignore_index=True).drop_duplicates()


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

def _kpi_children(losses: pd.DataFrame, opp_in_windows: pd.DataFrame) -> list:
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

    total      = len(losses)
    own_half   = int((losses['x'] < 50).sum()) if not losses.empty else 0
    def_third  = int((losses['x'] < 33.33).sum()) if not losses.empty else 0
    att_third  = int((losses['x'] >= 66.67).sum()) if not losses.empty else 0

    _shot_types = ['Goal', 'Saved Shot', 'Miss']
    if not opp_in_windows.empty and 'event_type' in opp_in_windows.columns:
        trans_events = len(opp_in_windows)
        shots_faced  = int(opp_in_windows['event_type'].isin(_shot_types).sum())
        goals_faced  = int((opp_in_windows['event_type'] == 'Goal').sum())
    else:
        trans_events = shots_faced = goals_faced = 0

    cards = [
        _card(total,         'Total Losses',   AWAY_COLOR),
        _card(own_half,      'Own-Half Losses', AWAY_COLOR),
        _card(def_third,     'Def Third',       AWAY_COLOR),
        _card(att_third,     'Att Third',       GOLD),
        _card(trans_events,  'Trans. Events',   HOME_COLOR),
        _card(shots_faced,   'Led to Shot',     AWAY_COLOR),
        _card(goals_faced,   'Led to Goal',     AWAY_COLOR),
    ]
    return [html.Div(cards, style={'display': 'flex', 'gap': '6px', 'flexWrap': 'wrap'})]


# =============================================================================
# Possession Loss Pitch Map
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


def _pitch_map_fig(losses: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    add_pitch_background(fig, half=False)

    has_outcome = 'window_outcome' in losses.columns

    # Real data traces — color = loss type, shape = transition outcome
    # showlegend=False; clean dummy traces below carry the legend entries
    for outcome, (symbol, size) in _OUTCOME_SYMBOLS.items():
        for loss_type, color in _LOSS_COLORS.items():
            if has_outcome:
                subset = losses[
                    (losses['loss_type'] == loss_type) &
                    (losses['window_outcome'] == outcome)
                ]
            else:
                subset = losses[losses['loss_type'] == loss_type]

            if subset.empty:
                continue

            custom = []
            for _, row in subset.iterrows():
                player      = row['player_name'] or 'Unknown'
                t_str       = f"{int(row['time_min'])}'"
                opp_line    = (f"<br>Caused by: <b>{row['opponent_player']}</b>"
                               if row.get('opponent_player') else '')
                detail      = row.get('window_detail', '')
                detail_line = f'<br>↳ {detail}' if detail else ''
                custom.append([player, t_str, loss_type, opp_line, outcome, detail_line])

            fig.add_trace(go.Scatter(
                x=subset['x'], y=subset['y'],
                mode='markers',
                name=loss_type,
                legendgroup=f'loss_{loss_type}',
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
                    'How: %{customdata[2]}'
                    '%{customdata[3]}<br>'
                    '<b>Next 30s:</b> %{customdata[4]}'
                    '%{customdata[5]}'
                    '<extra></extra>'
                ),
            ))

    # Legend 1 (top-left) — Loss Type (solid circles, loss colors)
    for i, (loss_type, color) in enumerate(_LOSS_COLORS.items()):
        fig.add_trace(go.Scatter(
            x=[None], y=[None], mode='markers',
            name=loss_type,
            legend='legend',
            legendgroup=f'loss_{loss_type}',
            legendgrouptitle_text='Loss Type' if i == 0 else '',
            showlegend=True,
            marker=dict(color=color, symbol='circle', size=10,
                        line=dict(color='white', width=0.8)),
        ))

    # Legend 2 (top-right) — Next 30s Outcome (shapes, neutral grey)
    for i, (outcome, (symbol, size)) in enumerate(_OUTCOME_SYMBOLS.items()):
        fig.add_trace(go.Scatter(
            x=[None], y=[None], mode='markers',
            name=outcome,
            legend='legend2',
            legendgroup=f'outcome_{outcome}',
            legendgrouptitle_text='Next 30s' if i == 0 else '',
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
        uirevision='def-trans-pitch-map',
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

def _heatmap_src(losses: pd.DataFrame) -> str:
    coords = losses.dropna(subset=['x', 'y'])
    if len(coords) < 2:
        return _SKEL_SRC
    return render_xt_heatmap_img(
        coords['x'].values,
        coords['y'].values,
        [1.0] * len(coords),
    )


# =============================================================================
# Transition window — what happened next
# =============================================================================

_SHOT_TYPES = ['Goal', 'Saved Shot', 'Miss']
_BAR_RECOVERY_TYPES = ['Tackle', 'Interception', 'Ball Recovery']


def _tag_loss_outcomes(
    losses: pd.DataFrame,
    bar: pd.DataFrame,
    opp: pd.DataFrame,
) -> pd.DataFrame:
    """
    Tag each possession-loss row with a 'window_outcome' string describing
    what happened in the 30-second window that followed.

    Priority (highest wins): Goal Conceded > Shot Conceded > BAR Recovery > No Incident.
    Also stores 'window_detail': first opponent shot player name (if any).
    Returns losses with two new columns added in-place.
    """
    if losses.empty:
        losses = losses.copy()
        losses['window_outcome'] = ''
        losses['window_detail']  = ''
        return losses

    opp = opp.copy()
    bar = bar.copy()
    for df in (opp, bar):
        df['_ts'] = df['time_min'].fillna(0).astype(int) * 60 + \
                    df['time_sec'].fillna(0).astype(int)

    outcomes = []
    details  = []

    for (match_id, period_id), grp in losses.groupby(['match_id', 'period_id']):
        opp_sl = opp[(opp['match_id'] == match_id) & (opp['period_id'] == period_id)]
        bar_sl = bar[(bar['match_id'] == match_id) & (bar['period_id'] == period_id)]

        local_outcomes = {}
        local_details  = {}

        for idx, loss_row in grp.iterrows():
            t0 = int(loss_row['timestamp'])
            t1 = t0 + _TRANSITION_WINDOW_SEC

            opp_win = opp_sl[(opp_sl['_ts'] >= t0) & (opp_sl['_ts'] <= t1)]
            bar_win = bar_sl[(bar_sl['_ts'] >= t0) & (bar_sl['_ts'] <= t1)]

            has_goal    = not opp_win.empty and (opp_win['event_type'] == 'Goal').any()
            has_shot    = not opp_win.empty and opp_win['event_type'].isin(_SHOT_TYPES).any()
            has_recover = not bar_win.empty and bar_win['event_type'].isin(_BAR_RECOVERY_TYPES).any()

            if has_goal:
                outcome = 'Goal Conceded'
                goal_rows = opp_win[opp_win['event_type'] == 'Goal']
                scorer = goal_rows['player_name'].iloc[0] if not goal_rows.empty else ''
                detail = f'Scorer: {scorer}' if scorer else ''
            elif has_shot:
                outcome = 'Shot Conceded'
                shot_rows = opp_win[opp_win['event_type'].isin(_SHOT_TYPES)]
                shooter = shot_rows['player_name'].iloc[0] if not shot_rows.empty else ''
                shot_type = shot_rows['event_type'].iloc[0] if not shot_rows.empty else ''
                detail = f'{shot_type} by {shooter}' if shooter else shot_type
            elif has_recover:
                outcome = 'Barça Recovered'
                rec_rows = bar_win[bar_win['event_type'].isin(_BAR_RECOVERY_TYPES)]
                recoverer = rec_rows['player_name'].iloc[0] if not rec_rows.empty else ''
                rec_type  = rec_rows['event_type'].iloc[0] if not rec_rows.empty else ''
                detail = f'{rec_type} — {recoverer}' if recoverer else rec_type
            else:
                outcome = 'No Clear Threat'
                detail  = ''

            local_outcomes[idx] = outcome
            local_details[idx]  = detail

        outcomes.append(local_outcomes)
        details.append(local_details)

    # Flatten back into series aligned to losses index
    all_outcomes = {}
    all_details  = {}
    for d in outcomes:
        all_outcomes.update(d)
    for d in details:
        all_details.update(d)

    losses = losses.copy()
    losses['window_outcome'] = losses.index.map(lambda i: all_outcomes.get(i, 'No Clear Threat'))
    losses['window_detail']  = losses.index.map(lambda i: all_details.get(i, ''))
    return losses



def _transition_outcomes_fig(losses: pd.DataFrame) -> go.Figure:
    """Ring (donut) chart showing how each defensive transition resolved."""
    labels = ['No Clear Threat', 'Barça Recovered', 'Shot Conceded', 'Goal Conceded']
    colors = ['#6b7280',          HOME_COLOR,         '#f97316',       '#ef4444']
    col    = losses['window_outcome'] if not losses.empty and 'window_outcome' in losses.columns \
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
        uirevision='dt-trans-outcomes',
    )
    return fig


def _transition_event_types_fig(opp_in_windows: pd.DataFrame) -> go.Figure:
    """Top-N opponent event types during transition windows."""
    if opp_in_windows.empty or 'event_type' not in opp_in_windows.columns:
        fig = go.Figure()
        fig.update_layout(
            paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor=PITCH_BG,
            height=240, margin=dict(l=10, r=10, t=10, b=10),
        )
        return fig

    counts = (
        opp_in_windows['event_type']
        .value_counts()
        .head(10)
        .sort_values(ascending=True)
    )

    bar_colors = []
    for etype in counts.index:
        if etype in _SHOT_TYPES:
            bar_colors.append('#ef4444')
        elif etype in _BAR_RECOVERY_TYPES:
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
        uirevision='dt-trans-event-types',
    )
    return fig


# =============================================================================
# Stats table
# =============================================================================

def _stats_table_children(losses: pd.DataFrame, top_n: int = 12) -> list:
    _no_data = [html.P("No data", style={
        'color': COLORS['text_secondary'], 'fontSize': '0.75rem',
        'textAlign': 'center', 'marginTop': '8px',
    })]

    if losses.empty or 'player_name' not in losses.columns:
        return _no_data

    rows_data = []
    for player, grp in losses.groupby('player_name'):
        if not player:
            continue
        total    = len(grp)
        def_t    = int((grp['x'] < 33.33).sum())
        mid_t    = int(((grp['x'] >= 33.33) & (grp['x'] < 66.67)).sum())
        att_t    = int((grp['x'] >= 66.67).sum())
        fp       = int((grp['loss_type'] == 'Failed Pass').sum())
        misc     = int((grp['loss_type'] == 'Miscontrol').sum())
        disp     = int((grp['loss_type'] == 'Dispossessed').sum())
        duel     = int((grp['loss_type'] == 'Lost Duel').sum())
        aerial   = int((grp['loss_type'] == 'Lost Aerial').sum())
        rows_data.append({
            'player': player, 'total': total,
            'def': def_t, 'mid': mid_t, 'att': att_t,
            'fp': fp, 'misc': misc, 'disp': disp,
            'duel': duel, 'aerial': aerial,
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
        html.Th('FP',     style=_TH),
        html.Th('Mc',     style=_TH),
        html.Th('Dis',    style=_TH),
        html.Th('Duel',   style=_TH),
        html.Th('Air',    style=_TH),
    ])

    table_rows = []
    for idx, s in enumerate(rows_data):
        bg    = (COLORS.get('dark_tertiary', 'rgba(255,255,255,0.03)')
                 if idx % 2 == 0 else 'transparent')
        short = s['player'].split()[-1] if s['player'] else '—'
        table_rows.append(html.Tr([
            html.Td(short,        style=_NAME_TD),
            html.Td(str(s['total']), style={**_TD, 'color': AWAY_COLOR, 'fontWeight': '700'}),
            html.Td(str(s['def']),   style=_TD),
            html.Td(str(s['mid']),   style=_TD),
            html.Td(str(s['att']),   style={**_TD, 'color': GOLD}),
            html.Td(str(s['fp']),     style={**_TD, 'color': '#ef4444'}),
            html.Td(str(s['misc']),   style={**_TD, 'color': '#f97316'}),
            html.Td(str(s['disp']),   style={**_TD, 'color': '#3b82f6'}),
            html.Td(str(s['duel']),   style={**_TD, 'color': '#06b6d4'}),
            html.Td(str(s['aerial']), style={**_TD, 'color': '#8b5cf6'}),
        ], style={'backgroundColor': bg}))

    legend = html.Div(
        "Z1 = Def Third  ·  Z2 = Mid Third  ·  Z3 = Att Third  ·  "
        "FP = Failed Pass  ·  Mc = Miscontrol  ·  Dis = Dispossessed  ·  "
        "Duel = Lost Ground Duel  ·  Air = Lost Aerial",
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


def _zone_summary_children(losses: pd.DataFrame) -> list:
    """Small zone breakdown summary below the table."""
    if losses.empty:
        return []

    total = max(len(losses), 1)
    z1 = int((losses['x'] < 33.33).sum())
    z2 = int(((losses['x'] >= 33.33) & (losses['x'] < 66.67)).sum())
    z3 = int((losses['x'] >= 66.67).sum())

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
        html.Div("Losses by Zone", style={**_SECTION_TITLE, 'marginBottom': '6px'}),
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
            id='dt-player-filter',
            options=player_options or [],
            value=None,
            multi=True,
            placeholder="All players…",
            style={'fontSize': '0.75rem'},
        ),

        html.Hr(style={'borderColor': COLORS['dark_border'], 'margin': '10px 0 4px'}),
        html.Div("Loss Type", style=_LABEL_STYLE),
        dcc.Checklist(
            id='dt-loss-type',
            options=[{'label': f'  {t}', 'value': t} for t in _ALL_LOSS_TYPES],
            value=_ALL_LOSS_TYPES,
            inputStyle={'cursor': 'pointer', 'accentColor': GOLD},
            labelStyle={
                'color': COLORS['text_secondary'], 'fontSize': '0.75rem',
                'display': 'block', 'marginBottom': '4px',
            },
        ),

        html.Hr(style={'borderColor': COLORS['dark_border'], 'margin': '10px 0 4px'}),
        html.Div("Next 30s Outcome", style=_LABEL_STYLE),
        dcc.Checklist(
            id='dt-outcome-filter',
            options=[{'label': f'  {t}', 'value': t} for t in _ALL_OUTCOME_TYPES],
            value=_ALL_OUTCOME_TYPES,
            inputStyle={'cursor': 'pointer', 'accentColor': GOLD},
            labelStyle={
                'color': COLORS['text_secondary'], 'fontSize': '0.75rem',
                'display': 'block', 'marginBottom': '4px',
            },
        ),

        *PassMap.dash_controls(show=['h1_time', 'h2_time'], id_prefix='dt'),
    ], style=_PANEL_STYLE)


# =============================================================================
# Public builder  (called from transitions.py as build_defending_transition_skeleton)
# =============================================================================

def build_defending_transition_skeleton() -> html.Div:
    """Skeleton layout — all data filled by register_defending_transition_callbacks."""
    events = get_all_events(CURRENT_SEASON)

    player_opts = []
    if not events.empty:
        bar = events[events['team_code'] == 'BAR']
        poss_loss_bar = bar[
            ((bar['event_type'] == 'Pass') & (bar['outcome'] == 0)) |
            bar['event_type'].isin(_POSS_LOSS_RAW)
        ]
        if 'player_name' in poss_loss_bar.columns:
            names = poss_loss_bar['player_name'].dropna().unique()
            player_opts = sorted(
                [{'label': n, 'value': n} for n in names],
                key=lambda d: d['label'],
            )

    # Main content: KPI bar → pitch map (md=8) + stats table (md=4)
    combined = html.Div([
        # KPI bar
        html.Div(id='dt-kpi-bar', children=[]),
        html.Hr(style={'borderColor': COLORS['dark_border'], 'margin': '10px 0 14px'}),

        # Pitch map + heatmap (left) | Stats table (right)
        dbc.Row([
            dbc.Col([
                html.Div("Possession Loss Map", style=_SECTION_TITLE),
                html.Div(
                    "Location of every possession loss · hover for who, when, how · "
                    "opponent causer shown for Dispossessed events",
                    style={
                        'color': COLORS['text_secondary'], 'fontSize': '0.62rem',
                        'fontStyle': 'italic', 'marginBottom': '8px',
                    },
                ),
                dcc.Loading(
                    type='circle', color=GOLD,
                    children=dcc.Graph(
                        id='dt-pitch-map',
                        figure=_skel_fig(520),
                        config=CHART_CFG,
                        style={'width': '100%'},
                    ),
                ),

                html.Hr(style={'borderColor': COLORS['dark_border'], 'margin': '14px 0 10px'}),

                html.Div("Possession Loss Heatmap", style=_SECTION_TITLE),
                html.Div(
                    "Density of all possession losses on the pitch",
                    style={
                        'color': COLORS['text_secondary'], 'fontSize': '0.62rem',
                        'fontStyle': 'italic', 'marginBottom': '8px',
                    },
                ),
                dcc.Loading(
                    type='circle', color=GOLD,
                    children=html.Img(
                        id='dt-heatmap-img',
                        src=_SKEL_SRC,
                        style={'width': '100%', 'borderRadius': '6px', 'minHeight': '200px'},
                    ),
                ),
            ], md=8),

            dbc.Col([
                html.Div("Losses by Player", style={**_SECTION_TITLE, 'fontSize': '0.75rem'}),
                html.Div(style={'marginBottom': '6px'}),
                html.Div(id='dt-stats-table', children=[]),
                html.Div(id='dt-zone-summary', children=[]),

                html.Hr(style={'borderColor': COLORS['dark_border'], 'margin': '10px 0 8px'}),
                html.Div("Transition Outcome", style={**_SECTION_TITLE, 'marginBottom': '6px'}),
                html.Div(
                    "How each 30s window resolved",
                    style={'color': COLORS['text_secondary'], 'fontSize': '0.60rem',
                           'fontStyle': 'italic', 'marginBottom': '6px'},
                ),
                dcc.Loading(
                    type='circle', color=GOLD,
                    children=dcc.Graph(
                        id='dt-trans-outcomes',
                        figure=_skel_fig(260),
                        config=CHART_CFG,
                        style={'width': '100%'},
                    ),
                ),

                html.Hr(style={'borderColor': COLORS['dark_border'], 'margin': '10px 0 8px'}),
                html.Div("Opponent Actions in Window", style={**_SECTION_TITLE, 'marginBottom': '6px'}),
                html.Div(
                    "Top event types by the opposition during transition",
                    style={'color': COLORS['text_secondary'], 'fontSize': '0.60rem',
                           'fontStyle': 'italic', 'marginBottom': '6px'},
                ),
                dcc.Loading(
                    type='circle', color=GOLD,
                    children=dcc.Graph(
                        id='dt-trans-event-types',
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

def register_defending_transition_callbacks(app) -> None:
    """Wire filter controls to KPI bar, pitch map, heatmap, and stats table."""

    @app.callback(
        Output('dt-kpi-bar',           'children'),
        Output('dt-pitch-map',         'figure'),
        Output('dt-heatmap-img',       'src'),
        Output('dt-stats-table',       'children'),
        Output('dt-zone-summary',      'children'),
        Output('dt-trans-outcomes',    'figure'),
        Output('dt-trans-event-types', 'figure'),
        Input('dt-player-filter',     'value'),
        Input('dt-loss-type',         'value'),
        Input('dt-outcome-filter',    'value'),
        Input('dt-h1-time',           'value'),
        Input('dt-h2-time',           'value'),
        State('ta-competition-selector', 'value'),
        State('ta-venue-selector',       'value'),
        State('ta-selected-matches',     'data'),
        State('ta-match-data',           'data'),
    )
    def _update(players, loss_types, outcome_types, h1_range, h2_range,
                competition, venue, match_ids, match_data):

        def _empty():
            return [], _skel_fig(600), _SKEL_SRC, [], [], _skel_fig(260), _skel_fig(280)

        events = get_all_events(CURRENT_SEASON)
        if events.empty:
            return _empty()

        # Global filters (competition / venue / match selection)
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

        # Extract all possession losses (unfiltered, for KPI + heatmap baseline)
        all_losses = _extract_losses(bar, events)
        if all_losses.empty:
            return _empty()

        # Apply time filter
        _h1 = tuple(h1_range) if h1_range else (0, 50)
        _h2 = tuple(h2_range) if h2_range else (45, 100)
        losses = _apply_time_filter(all_losses, _h1, _h2)

        # Apply player filter
        if players and 'player_name' in losses.columns:
            losses = losses[losses['player_name'].isin(players)]

        # Apply loss-type / outcome filters (for pitch map; KPI uses unfiltered)
        _types    = loss_types    if loss_types    else _ALL_LOSS_TYPES
        _outcomes = outcome_types if outcome_types else _ALL_OUTCOME_TYPES

        # Tag each loss with what happened in the next 30 seconds
        opp_in_windows  = _opp_events_in_windows(losses, opp)
        losses          = _tag_loss_outcomes(losses, bar, opp)
        losses_filtered = losses[
            losses['loss_type'].isin(_types) &
            losses['window_outcome'].isin(_outcomes)
        ]

        kpi             = _kpi_children(losses, opp_in_windows)
        pitch_fig       = _pitch_map_fig(losses_filtered)
        heatmap_src     = _heatmap_src(losses_filtered)
        stats_table     = _stats_table_children(losses)
        zone_summary    = _zone_summary_children(losses)
        outcomes_fig    = _transition_outcomes_fig(losses)
        event_types_fig = _transition_event_types_fig(opp_in_windows)

        return (kpi, pitch_fig, heatmap_src,
                stats_table, zone_summary, outcomes_fig, event_types_fig)
