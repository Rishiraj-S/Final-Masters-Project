"""
Match Analysis — Transitions tab

Two sub-tabs rendered as full-width column buttons:
  • Defensive Transition  — 30-second windows after possession losses
  • Attacking Transition  — 30-second windows after possession gains

Both home and away teams are shown side-by-side in each sub-tab.
All computation is synchronous (single match, no filter controls needed).
"""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
from dash import html, dcc
import dash_bootstrap_components as dbc

from utils.config import COLORS
from .shared import CARD_STYLE, section_header, build_info_box
from page_utils.visualizations import (
    HOME_COLOR,
    AWAY_COLOR,
    GOLD,
    add_pitch_background,
    PITCH_AXIS_FULL,
    render_lsc_heatmap_img,
    PITCH_BG,
)

# ── Constants ─────────────────────────────────────────────────────────────────

_TRANSITION_WINDOW_SEC = 30

_POSS_LOSS_RAW = ['Miscontrol', 'Dispossessed', 'Offside Pass', 'Error']

_LOSS_COLORS = {
    'Failed Pass':  '#ef4444',
    'Miscontrol':   '#f97316',
    'Dispossessed': '#3b82f6',
    'Lost Duel':    '#06b6d4',
    'Lost Aerial':  '#8b5cf6',
    'Offside Pass': '#eab308',
    'Error':        '#a855f7',
}

_LOSS_OUTCOME_SYMBOLS = {
    'Goal Conceded':   ('star',        14),
    'Shot Conceded':   ('triangle-up', 12),
    'Team Recovered':  ('circle',      11),
    'No Clear Threat': ('square',      10),
}

_GAIN_TYPES_RAW = ['Ball recovery', 'Interception']

_GAIN_COLORS = {
    'Ball recovery': '#22c55e',
    'Interception':  '#3b82f6',
    'Tackle Won':    GOLD,
}

_GAIN_OUTCOME_SYMBOLS = {
    'Goal Scored':     ('star',        14),
    'Shot Taken':      ('triangle-up', 12),
    'Quick Turnover':  ('x',           12),
    'Possession Held': ('circle',      10),
}

_POSS_LOSS_EVENTS = ['Miscontrol', 'Dispossessed', 'Offside Pass', 'Error']
_SHOT_TYPES       = ['Goal', 'Saved Shot', 'Miss']
_RECOVERY_TYPES   = ['Tackle', 'Interception', 'Ball recovery']

_BTN_BASE = {
    'display': 'block',
    'width': '100%',
    'textAlign': 'center',
    'padding': '20px 0',
    'fontWeight': '700',
    'fontSize': '1rem',
    'letterSpacing': '0.6px',
    'textTransform': 'uppercase',
    'backgroundColor': COLORS['dark_secondary'],
    'border': f'1px solid {COLORS["dark_border"]}',
    'borderRadius': '0',
}
_BTN_INACTIVE = {**_BTN_BASE, 'color': COLORS['text_secondary']}
_BTN_ACTIVE   = {**_BTN_BASE, 'color': GOLD,
                 'backgroundColor': 'rgba(237,187,0,0.08)',
                 'borderBottom': f'3px solid {GOLD}'}

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

CHART_CFG   = {'displayModeBar': False}
_SKEL_SRC   = 'data:image/png;base64,'


# ── Pitch annotation helpers ───────────────────────────────────────────────────

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


def _add_third_dividers(fig: go.Figure) -> None:
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
    for x_centre, zone_name in [(16.67, 'Zone 1'), (50.0, 'Zone 2'), (83.33, 'Zone 3')]:
        fig.add_annotation(
            x=x_centre, y=2, xref='x', yref='y',
            text=zone_name,
            showarrow=False,
            font=dict(size=9, color='rgba(255,255,255,0.20)', family='Arial Black'),
            xanchor='center', yanchor='bottom',
        )


def _pitch_layout(uirev: str) -> dict:
    return dict(
        **PITCH_AXIS_FULL,
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font=dict(color='#E8E9ED', size=12, family='Arial, sans-serif'),
        height=520,
        hovermode='closest',
        uirevision=uirev,
        legend=dict(
            orientation='v', x=1.01, y=1.0,
            xanchor='left', yanchor='top',
            bgcolor='rgba(21,25,50,0.88)',
            bordercolor=COLORS.get('dark_border', 'rgba(255,255,255,0.15)'),
            borderwidth=1,
            font=dict(color=COLORS['text_primary'], size=10),
            groupclick='toggleitem',
        ),
        legend2=dict(
            orientation='v', x=1.01, y=0.45,
            xanchor='left', yanchor='top',
            bgcolor='rgba(21,25,50,0.88)',
            bordercolor=COLORS.get('dark_border', 'rgba(255,255,255,0.15)'),
            borderwidth=1,
            font=dict(color=COLORS['text_primary'], size=10),
            groupclick='toggleitem',
        ),
        margin=dict(l=0, r=150, t=36, b=0),
    )


# ═══════════════════════════════════════════════════════════════════════════════
# DEFENSIVE TRANSITION helpers
# ═══════════════════════════════════════════════════════════════════════════════

def _extract_losses(te: pd.DataFrame, all_events: pd.DataFrame) -> pd.DataFrame:
    """Possession-loss events for one team (team_position slice)."""
    has_event_id  = 'event_id' in all_events.columns
    has_related   = 'Related event ID' in all_events.columns
    has_team_pos  = 'team_position' in all_events.columns

    eid_to_player: dict = {}
    eid_to_pos:    dict = {}
    if has_event_id:
        eid_to_player = dict(zip(
            all_events['event_id'].astype(str),
            all_events['player_name'].fillna(''),
        ))
        if has_team_pos:
            eid_to_pos = dict(zip(
                all_events['event_id'].astype(str),
                all_events['team_position'].fillna(''),
            ))

    te_pos = te['team_position'].iloc[0] if (not te.empty and 'team_position' in te.columns) else ''

    def _resolve_opponent(row) -> str:
        if not has_related:
            return ''
        rid = str(row.get('Related event ID', ''))
        if not rid or rid in ('nan', 'None', ''):
            return ''
        player = eid_to_player.get(rid, '')
        pos    = eid_to_pos.get(rid, '')
        if player and pos and pos != te_pos:
            return player
        return ''

    rows = []
    for _, row in te.iterrows():
        etype   = row.get('event_type', '')
        outcome = row.get('outcome', 1)

        if etype == 'Pass' and outcome == 0:
            loss_type = 'Failed Pass'
        elif etype == 'Challenge' and outcome == 0:
            loss_type = 'Lost Duel'
        elif etype == 'Aerial' and outcome == 0:
            loss_type = 'Lost Aerial'
        elif etype in _POSS_LOSS_RAW:
            loss_type = etype
        else:
            continue

        x = row.get('x', None)
        y = row.get('y', None)
        if pd.isna(x) or pd.isna(y):
            continue

        t_min = int(row.get('time_min', 0) or 0)
        t_sec = int(row.get('time_sec', 0) or 0)
        opp_player = _resolve_opponent(row) if loss_type == 'Dispossessed' else ''

        rows.append({
            'loss_type':       loss_type,
            'player_name':     row.get('player_name', '') or '',
            'time_min':        t_min,
            'time_sec':        t_sec,
            'period_id':       row.get('period_id', 1),
            'x':               float(x),
            'y':               float(y),
            'timestamp':       t_min * 60 + t_sec,
            'opponent_player': opp_player,
        })

    return pd.DataFrame(rows) if rows else pd.DataFrame(
        columns=['loss_type', 'player_name', 'time_min', 'time_sec',
                 'period_id', 'x', 'y', 'timestamp', 'opponent_player']
    )


def _opp_events_in_windows(losses: pd.DataFrame, opp: pd.DataFrame) -> pd.DataFrame:
    """Opponent events within 30s after any possession loss (by period)."""
    if losses.empty or opp.empty:
        return pd.DataFrame()

    opp = opp.copy()
    if 'time_min' not in opp.columns or 'time_sec' not in opp.columns:
        return pd.DataFrame()

    opp['_ts'] = opp['time_min'].fillna(0).astype(int) * 60 + \
                 opp['time_sec'].fillna(0).astype(int)

    parts = []
    for period_id, loss_grp in losses.groupby('period_id'):
        opp_sl = opp[opp['period_id'] == period_id]
        if opp_sl.empty:
            continue
        for t_loss in loss_grp['timestamp']:
            window = opp_sl[
                (opp_sl['_ts'] >= t_loss) &
                (opp_sl['_ts'] <= t_loss + _TRANSITION_WINDOW_SEC)
            ]
            parts.append(window)

    if not parts:
        return pd.DataFrame()
    return pd.concat(parts, ignore_index=True).drop_duplicates()


def _tag_loss_outcomes(
    losses: pd.DataFrame,
    te: pd.DataFrame,
    opp: pd.DataFrame,
) -> pd.DataFrame:
    """Tag each loss row with window_outcome and window_detail."""
    if losses.empty:
        losses = losses.copy()
        losses['window_outcome'] = ''
        losses['window_detail']  = ''
        return losses

    te  = te.copy()
    opp = opp.copy()
    for df in (te, opp):
        df['_ts'] = df['time_min'].fillna(0).astype(int) * 60 + \
                    df['time_sec'].fillna(0).astype(int)

    all_outcomes: dict = {}
    all_details:  dict = {}

    for period_id, grp in losses.groupby('period_id'):
        opp_sl = opp[opp['period_id'] == period_id]
        te_sl  = te[te['period_id']  == period_id]

        for idx, loss_row in grp.iterrows():
            t0 = int(loss_row['timestamp'])
            t1 = t0 + _TRANSITION_WINDOW_SEC

            opp_win = opp_sl[(opp_sl['_ts'] >= t0) & (opp_sl['_ts'] <= t1)]
            te_win  = te_sl[ (te_sl['_ts']  >= t0) & (te_sl['_ts']  <= t1)]

            has_goal    = not opp_win.empty and (opp_win['event_type'] == 'Goal').any()
            has_shot    = not opp_win.empty and opp_win['event_type'].isin(_SHOT_TYPES).any()
            has_recover = not te_win.empty  and te_win['event_type'].isin(_RECOVERY_TYPES).any()

            if has_goal:
                goal_rows = opp_win[opp_win['event_type'] == 'Goal']
                scorer    = goal_rows['player_name'].iloc[0] if not goal_rows.empty else ''
                outcome   = 'Goal Conceded'
                detail    = f'Scorer: {scorer}' if scorer else ''
            elif has_shot:
                shot_rows = opp_win[opp_win['event_type'].isin(_SHOT_TYPES)]
                shooter   = shot_rows['player_name'].iloc[0] if not shot_rows.empty else ''
                shot_type = shot_rows['event_type'].iloc[0]  if not shot_rows.empty else ''
                outcome   = 'Shot Conceded'
                detail    = f'{shot_type} by {shooter}' if shooter else shot_type
            elif has_recover:
                rec_rows  = te_win[te_win['event_type'].isin(_RECOVERY_TYPES)]
                recoverer = rec_rows['player_name'].iloc[0] if not rec_rows.empty else ''
                rec_type  = rec_rows['event_type'].iloc[0]  if not rec_rows.empty else ''
                outcome   = 'Team Recovered'
                detail    = f'{rec_type} — {recoverer}' if recoverer else rec_type
            else:
                outcome = 'No Clear Threat'
                detail  = ''

            all_outcomes[idx] = outcome
            all_details[idx]  = detail

    losses = losses.copy()
    losses['window_outcome'] = losses.index.map(lambda i: all_outcomes.get(i, 'No Clear Threat'))
    losses['window_detail']  = losses.index.map(lambda i: all_details.get(i, ''))
    return losses


def _losses_zone_donut_card(losses: pd.DataFrame, opp_in_windows: pd.DataFrame, color: str) -> list:
    z1 = int((losses['x'] < 33.33).sum())                                   if not losses.empty else 0
    z2 = int(((losses['x'] >= 33.33) & (losses['x'] < 66.67)).sum())        if not losses.empty else 0
    z3 = int((losses['x'] >= 66.67).sum())                                   if not losses.empty else 0
    total = z1 + z2 + z3

    fig = go.Figure(go.Pie(
        labels=['Z1 · Def Third', 'Z2 · Mid Third', 'Z3 · Att Third'],
        values=[z1, z2, z3] if total > 0 else [1, 1, 1],
        hole=0.65,
        marker=dict(colors=['#ef4444', '#f97316', '#22c55e'],
                    line=dict(color='rgba(0,0,0,0.2)', width=1.5)),
        textinfo='none',
        hovertemplate='<b>%{label}</b>: %{value} (%{percent})<extra></extra>',
        sort=False,
    ))
    fig.add_annotation(text=str(total), x=0.5, y=0.58, showarrow=False,
                       font=dict(color='white', size=22, family='Arial Black'),
                       xref='paper', yref='paper')
    fig.add_annotation(text='Total Losses', x=0.5, y=0.42, showarrow=False,
                       font=dict(color=COLORS['text_secondary'], size=9),
                       xref='paper', yref='paper')
    fig.update_layout(
        paper_bgcolor='rgba(0,0,0,0)', showlegend=True,
        legend=dict(orientation='h', x=0.5, xanchor='center', y=-0.08,
                    font=dict(color=COLORS['text_primary'], size=9),
                    bgcolor='rgba(0,0,0,0)', itemsizing='constant'),
        margin=dict(l=5, r=5, t=10, b=30), height=230,
    )

    if not opp_in_windows.empty and 'event_type' in opp_in_windows.columns:
        shots_faced = int(opp_in_windows['event_type'].isin(_SHOT_TYPES).sum())
        goals_faced = int((opp_in_windows['event_type'] == 'Goal').sum())
    else:
        shots_faced = goals_faced = 0

    stats = [
        ('Led to Shot', str(shots_faced), color),
        ('Led to Goal', str(goals_faced), '#ef4444'),
    ]
    stats_panel = html.Div([
        html.Div([
            html.Div(val, style={
                'color': c, 'fontWeight': '800', 'fontSize': '1.6rem', 'lineHeight': '1.1',
            }),
            html.Div(lbl, style={
                'color': COLORS['text_secondary'], 'fontSize': '0.60rem',
                'fontWeight': '600', 'letterSpacing': '0.5px',
                'textTransform': 'uppercase', 'marginTop': '3px',
            }),
        ], style={
            'backgroundColor': COLORS['dark_secondary'],
            'border': f'1px solid {COLORS["dark_border"]}',
            'borderRadius': '6px', 'padding': '10px 12px',
            'flex': '1',
        })
        for lbl, val, c in stats
    ], style={
        'display': 'flex', 'flexDirection': 'column', 'gap': '8px',
        'justifyContent': 'center', 'flex': '1',
        'paddingLeft': '16px', 'minWidth': '0',
    })

    return [html.Div([
        dcc.Graph(figure=fig, config=CHART_CFG,
                  style={'flex': '0 0 55%', 'minWidth': '0'}),
        stats_panel,
    ], style={'display': 'flex', 'alignItems': 'center'})]


def _loss_pitch_map(losses: pd.DataFrame, uirev: str) -> go.Figure:
    fig = go.Figure()
    add_pitch_background(fig, half=False)
    has_outcome = 'window_outcome' in losses.columns

    for outcome, (symbol, size) in _LOSS_OUTCOME_SYMBOLS.items():
        for loss_type, clr in _LOSS_COLORS.items():
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
                x=subset['x'], y=subset['y'], mode='markers',
                name=loss_type, legendgroup=f'loss_{loss_type}',
                showlegend=False,
                marker=dict(color=clr, symbol=symbol, size=size,
                            opacity=0.90, line=dict(color='white', width=0.8)),
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

    for i, (lt, clr) in enumerate(_LOSS_COLORS.items()):
        fig.add_trace(go.Scatter(
            x=[None], y=[None], mode='markers',
            name=lt, legend='legend', legendgroup=f'loss_{lt}',
            legendgrouptitle_text='Loss Type' if i == 0 else '',
            showlegend=True,
            marker=dict(color=clr, symbol='circle', size=10,
                        line=dict(color='white', width=0.8)),
        ))

    for i, (outcome, (symbol, size)) in enumerate(_LOSS_OUTCOME_SYMBOLS.items()):
        fig.add_trace(go.Scatter(
            x=[None], y=[None], mode='markers',
            name=outcome, legend='legend2', legendgroup=f'outcome_{outcome}',
            legendgrouptitle_text='Next 30s' if i == 0 else '',
            showlegend=True,
            marker=dict(color='#e2e8f0', symbol=symbol, size=size,
                        line=dict(color='white', width=0.8)),
        ))

    _add_third_dividers(fig)
    _add_attack_direction(fig)
    fig.update_layout(**_pitch_layout(uirev))
    return fig


def _loss_stats_table(losses: pd.DataFrame, color: str, top_n: int = 10) -> list:
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
        rows_data.append({
            'player': player,
            'total':  len(grp),
            'def':    int((grp['x'] < 33.33).sum()),
            'mid':    int(((grp['x'] >= 33.33) & (grp['x'] < 66.67)).sum()),
            'att':    int((grp['x'] >= 66.67).sum()),
            'fp':     int((grp['loss_type'] == 'Failed Pass').sum()),
            'misc':   int((grp['loss_type'] == 'Miscontrol').sum()),
            'disp':   int((grp['loss_type'] == 'Dispossessed').sum()),
            'duel':   int((grp['loss_type'] == 'Lost Duel').sum()),
            'aerial': int((grp['loss_type'] == 'Lost Aerial').sum()),
        })

    rows_data.sort(key=lambda r: r['total'], reverse=True)
    rows_data = rows_data[:top_n]
    if not rows_data:
        return _no_data

    header = html.Tr([
        html.Th('Player', style={**_TH, 'textAlign': 'left'}),
        html.Th('Tot',    style=_TH), html.Th('Z1', style=_TH),
        html.Th('Z2',     style=_TH), html.Th('Z3', style=_TH),
        html.Th('FP',     style=_TH), html.Th('Mc', style=_TH),
        html.Th('Dis',    style=_TH), html.Th('Duel', style=_TH),
        html.Th('Air',    style=_TH),
    ])
    table_rows = []
    for idx, s in enumerate(rows_data):
        bg    = (COLORS.get('dark_tertiary', 'rgba(255,255,255,0.03)')
                 if idx % 2 == 0 else 'transparent')
        short = s['player'].split()[-1] if s['player'] else '—'
        table_rows.append(html.Tr([
            html.Td(short,           style=_NAME_TD),
            html.Td(str(s['total']), style={**_TD, 'color': color, 'fontWeight': '700'}),
            html.Td(str(s['def']),   style=_TD),
            html.Td(str(s['mid']),   style=_TD),
            html.Td(str(s['att']),   style={**_TD, 'color': GOLD}),
            html.Td(str(s['fp']),    style={**_TD, 'color': '#ef4444'}),
            html.Td(str(s['misc']),  style={**_TD, 'color': '#f97316'}),
            html.Td(str(s['disp']),  style={**_TD, 'color': '#3b82f6'}),
            html.Td(str(s['duel']),  style={**_TD, 'color': '#06b6d4'}),
            html.Td(str(s['aerial']),style={**_TD, 'color': '#8b5cf6'}),
        ], style={'backgroundColor': bg}))

    legend = html.Div(
        "Z1=Def Third · Z2=Mid Third · Z3=Att Third · "
        "FP=Failed Pass · Mc=Miscontrol · Dis=Dispossessed · "
        "Duel=Lost Duel · Air=Lost Aerial",
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


def _loss_zone_summary(losses: pd.DataFrame, color: str) -> list:
    if losses.empty:
        return []
    total = max(len(losses), 1)
    z1 = int((losses['x'] < 33.33).sum())
    z2 = int(((losses['x'] >= 33.33) & (losses['x'] < 66.67)).sum())
    z3 = int((losses['x'] >= 66.67).sum())

    def _row(label, count, c):
        pct = round(count / total * 100)
        return html.Div([
            html.Span(label, style={'color': COLORS['text_secondary'],
                                    'fontSize': '0.68rem', 'minWidth': '80px'}),
            html.Div(style={'flex': '1', 'height': '6px',
                            'backgroundColor': COLORS['dark_border'],
                            'borderRadius': '3px', 'overflow': 'hidden',
                            'margin': '0 8px'}, children=[
                html.Div(style={'width': f'{pct}%', 'height': '100%',
                                'backgroundColor': c, 'borderRadius': '3px'}),
            ]),
            html.Span(f'{count}  ({pct}%)', style={'color': c, 'fontSize': '0.68rem',
                                                    'fontWeight': '700', 'minWidth': '60px',
                                                    'textAlign': 'right'}),
        ], style={'display': 'flex', 'alignItems': 'center', 'padding': '4px 0'})

    return [
        html.Hr(style={'borderColor': COLORS['dark_border'], 'margin': '10px 0 8px'}),
        html.Div("Losses by Zone", style={**_SECTION_TITLE, 'marginBottom': '6px'}),
        _row('Zone 1 (Def Third)', z1, color),
        _row('Zone 2 (Mid Third)', z2, GOLD),
        _row('Zone 3 (Att Third)', z3, COLORS['text_primary']),
    ]


def _def_outcome_donut(losses: pd.DataFrame, uirev: str) -> go.Figure:
    labels = ['No Clear Threat', 'Team Recovered', 'Shot Conceded', 'Goal Conceded']
    colors = ['#6b7280', HOME_COLOR, '#f97316', '#ef4444']
    col    = losses['window_outcome'] if not losses.empty and 'window_outcome' in losses.columns \
             else pd.Series(dtype=str)
    values = [int((col == l).sum()) for l in labels]
    fig = go.Figure(go.Pie(
        labels=labels, values=values,
        marker=dict(colors=colors, line=dict(color=PITCH_BG, width=2)),
        hole=0.55, textinfo='percent',
        textfont=dict(color='white', size=11),
        hovertemplate='<b>%{label}</b><br>%{value} (%{percent})<extra></extra>',
        sort=False,
    ))
    fig.update_layout(
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
        font=dict(color='#E8E9ED', size=11, family='Arial, sans-serif'),
        height=260, margin=dict(l=0, r=0, t=10, b=0),
        showlegend=True,
        legend=dict(orientation='v', x=1.0, y=0.5, xanchor='left', yanchor='middle',
                    font=dict(color=COLORS['text_primary'], size=9),
                    bgcolor='rgba(0,0,0,0)'),
        uirevision=uirev,
    )
    return fig


def _def_event_types_bar(opp_in_windows: pd.DataFrame, uirev: str) -> go.Figure:
    if opp_in_windows.empty or 'event_type' not in opp_in_windows.columns:
        fig = go.Figure()
        fig.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor=PITCH_BG,
                          height=240, margin=dict(l=10, r=10, t=10, b=10))
        return fig

    counts = (opp_in_windows['event_type'].value_counts()
              .head(10).sort_values(ascending=True))
    bar_colors = []
    for etype in counts.index:
        if etype in _SHOT_TYPES:
            bar_colors.append('#ef4444')
        elif etype in _RECOVERY_TYPES:
            bar_colors.append(GOLD)
        elif etype == 'Pass':
            bar_colors.append('#3b82f6')
        else:
            bar_colors.append('#6b7280')

    fig = go.Figure(go.Bar(
        y=counts.index.tolist(), x=counts.values.tolist(),
        orientation='h', marker_color=bar_colors,
        hovertemplate='%{y}: %{x}<extra></extra>',
    ))
    fig.update_layout(
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor=PITCH_BG,
        font=dict(color='#E8E9ED', size=10, family='Arial, sans-serif'),
        height=280, margin=dict(l=10, r=10, t=10, b=10),
        xaxis=dict(showgrid=False, zeroline=False, title='Count',
                   title_font=dict(size=9), tickfont=dict(size=9)),
        yaxis=dict(showgrid=False, tickfont=dict(size=10)),
        showlegend=False, uirevision=uirev,
    )
    return fig



# ═══════════════════════════════════════════════════════════════════════════════
# ATTACKING TRANSITION helpers
# ═══════════════════════════════════════════════════════════════════════════════

def _extract_gains(te: pd.DataFrame) -> pd.DataFrame:
    """Possession-gain events for one team (team_position slice)."""
    rows = []
    for _, row in te.iterrows():
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
            'x':           float(x),
            'y':           float(y),
            'timestamp':   t_min * 60 + t_sec,
        })

    return pd.DataFrame(rows) if rows else pd.DataFrame(
        columns=['gain_type', 'player_name', 'time_min', 'time_sec',
                 'period_id', 'x', 'y', 'timestamp']
    )


def _team_events_in_windows(gains: pd.DataFrame, te: pd.DataFrame) -> pd.DataFrame:
    """Team events within 30s after each possession gain (by period)."""
    if gains.empty or te.empty:
        return pd.DataFrame()

    te = te.copy()
    te['_ts'] = te['time_min'].fillna(0).astype(int) * 60 + \
                te['time_sec'].fillna(0).astype(int)

    parts = []
    for period_id, grp in gains.groupby('period_id'):
        te_sl = te[te['period_id'] == period_id]
        if te_sl.empty:
            continue
        for t_gain in grp['timestamp']:
            window = te_sl[
                (te_sl['_ts'] > t_gain) &
                (te_sl['_ts'] <= t_gain + _TRANSITION_WINDOW_SEC)
            ]
            parts.append(window)

    if not parts:
        return pd.DataFrame()
    return pd.concat(parts, ignore_index=True).drop_duplicates()


def _tag_gain_outcomes(gains: pd.DataFrame, te: pd.DataFrame) -> pd.DataFrame:
    """Tag each gain row with window_outcome and window_detail."""
    if gains.empty:
        gains = gains.copy()
        gains['window_outcome'] = ''
        gains['window_detail']  = ''
        return gains

    te = te.copy()
    te['_ts'] = te['time_min'].fillna(0).astype(int) * 60 + \
                te['time_sec'].fillna(0).astype(int)

    _loss_events = _POSS_LOSS_EVENTS[:]

    all_outcomes: dict = {}
    all_details:  dict = {}

    for period_id, grp in gains.groupby('period_id'):
        te_sl = te[te['period_id'] == period_id]

        for idx, gain_row in grp.iterrows():
            t0 = int(gain_row['timestamp'])
            t1 = t0 + _TRANSITION_WINDOW_SEC

            te_win = te_sl[(te_sl['_ts'] > t0) & (te_sl['_ts'] <= t1)]

            has_goal     = not te_win.empty and (te_win['event_type'] == 'Goal').any()
            has_shot     = not te_win.empty and te_win['event_type'].isin(_SHOT_TYPES).any()
            has_turnover = not te_win.empty and (
                te_win['event_type'].isin(_loss_events).any() or
                (not te_win[te_win['event_type'] == 'Pass'].empty and
                 te_win[te_win['event_type'] == 'Pass']['outcome'].eq(0).any()) or
                ((te_win['event_type'] == 'Challenge') & (te_win['outcome'] == 0)).any()
            )

            if has_goal:
                goal_rows = te_win[te_win['event_type'] == 'Goal']
                scorer    = goal_rows['player_name'].iloc[0] if not goal_rows.empty else ''
                outcome   = 'Goal Scored'
                detail    = f'by {scorer}' if scorer else ''
            elif has_shot:
                shot_rows = te_win[te_win['event_type'].isin(_SHOT_TYPES)]
                shooter   = shot_rows['player_name'].iloc[0] if not shot_rows.empty else ''
                shot_type = shot_rows['event_type'].iloc[0]  if not shot_rows.empty else ''
                outcome   = 'Shot Taken'
                detail    = f'{shot_type} — {shooter}' if shooter else shot_type
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


def _gains_zone_donut_card(gains: pd.DataFrame, te_in_windows: pd.DataFrame, color: str) -> list:
    z1 = int((gains['x'] < 33.33).sum())                                    if not gains.empty else 0
    z2 = int(((gains['x'] >= 33.33) & (gains['x'] < 66.67)).sum())         if not gains.empty else 0
    z3 = int((gains['x'] >= 66.67).sum())                                   if not gains.empty else 0
    total = z1 + z2 + z3

    fig = go.Figure(go.Pie(
        labels=['Z1 · Def Third', 'Z2 · Mid Third', 'Z3 · Att Third'],
        values=[z1, z2, z3] if total > 0 else [1, 1, 1],
        hole=0.65,
        marker=dict(colors=['#6b7280', '#f97316', '#22c55e'],
                    line=dict(color='rgba(0,0,0,0.2)', width=1.5)),
        textinfo='none',
        hovertemplate='<b>%{label}</b>: %{value} (%{percent})<extra></extra>',
        sort=False,
    ))
    fig.add_annotation(text=str(total), x=0.5, y=0.58, showarrow=False,
                       font=dict(color='white', size=22, family='Arial Black'),
                       xref='paper', yref='paper')
    fig.add_annotation(text='Total Gains', x=0.5, y=0.42, showarrow=False,
                       font=dict(color=COLORS['text_secondary'], size=9),
                       xref='paper', yref='paper')
    fig.update_layout(
        paper_bgcolor='rgba(0,0,0,0)', showlegend=True,
        legend=dict(orientation='h', x=0.5, xanchor='center', y=-0.08,
                    font=dict(color=COLORS['text_primary'], size=9),
                    bgcolor='rgba(0,0,0,0)', itemsizing='constant'),
        margin=dict(l=5, r=5, t=10, b=30), height=230,
    )

    if not te_in_windows.empty and 'event_type' in te_in_windows.columns:
        shots_taken  = int(te_in_windows['event_type'].isin(_SHOT_TYPES).sum())
        goals_scored = int((te_in_windows['event_type'] == 'Goal').sum())
    else:
        shots_taken = goals_scored = 0

    col = gains['window_outcome'] if not gains.empty and 'window_outcome' in gains.columns \
          else pd.Series(dtype=str)
    quick_turnovers = int((col == 'Quick Turnover').sum())

    stats = [
        ('Led to Shot',     str(shots_taken),     GOLD),
        ('Led to Goal',     str(goals_scored),     '#22c55e'),
        ('Quick Turnovers', str(quick_turnovers),  AWAY_COLOR),
    ]
    stats_panel = html.Div([
        html.Div([
            html.Div(val, style={
                'color': c, 'fontWeight': '800', 'fontSize': '1.6rem', 'lineHeight': '1.1',
            }),
            html.Div(lbl, style={
                'color': COLORS['text_secondary'], 'fontSize': '0.60rem',
                'fontWeight': '600', 'letterSpacing': '0.5px',
                'textTransform': 'uppercase', 'marginTop': '3px',
            }),
        ], style={
            'backgroundColor': COLORS['dark_secondary'],
            'border': f'1px solid {COLORS["dark_border"]}',
            'borderRadius': '6px', 'padding': '10px 12px',
            'flex': '1',
        })
        for lbl, val, c in stats
    ], style={
        'display': 'flex', 'flexDirection': 'column', 'gap': '8px',
        'justifyContent': 'center', 'flex': '1',
        'paddingLeft': '16px', 'minWidth': '0',
    })

    return [html.Div([
        dcc.Graph(figure=fig, config=CHART_CFG,
                  style={'flex': '0 0 55%', 'minWidth': '0'}),
        stats_panel,
    ], style={'display': 'flex', 'alignItems': 'center'})]


def _gain_pitch_map(gains: pd.DataFrame, uirev: str) -> go.Figure:
    fig = go.Figure()
    add_pitch_background(fig, half=False)
    has_outcome = 'window_outcome' in gains.columns

    for outcome, (symbol, size) in _GAIN_OUTCOME_SYMBOLS.items():
        for gain_type, clr in _GAIN_COLORS.items():
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
                x=subset['x'], y=subset['y'], mode='markers',
                name=gain_type, legendgroup=f'gain_{gain_type}',
                showlegend=False,
                marker=dict(color=clr, symbol=symbol, size=size,
                            opacity=0.90, line=dict(color='white', width=0.8)),
                customdata=custom,
                hovertemplate=(
                    '<b>%{customdata[0]}</b><br>'
                    'Time: %{customdata[1]}<br>'
                    'How: %{customdata[2]}<br>'
                    '<b>Next 30s:</b> %{customdata[3]}'
                    '%{customdata[4]}'
                    '<extra></extra>'
                ),
            ))

    for i, (gt, clr) in enumerate(_GAIN_COLORS.items()):
        fig.add_trace(go.Scatter(
            x=[None], y=[None], mode='markers',
            name=gt, legend='legend', legendgroup=f'gain_{gt}',
            legendgrouptitle_text='Gain Type' if i == 0 else '',
            showlegend=True,
            marker=dict(color=clr, symbol='circle', size=10,
                        line=dict(color='white', width=0.8)),
        ))

    for i, (outcome, (symbol, size)) in enumerate(_GAIN_OUTCOME_SYMBOLS.items()):
        fig.add_trace(go.Scatter(
            x=[None], y=[None], mode='markers',
            name=outcome, legend='legend2', legendgroup=f'outcome_{outcome}',
            legendgrouptitle_text='Next 30s' if i == 0 else '',
            showlegend=True,
            marker=dict(color='#e2e8f0', symbol=symbol, size=size,
                        line=dict(color='white', width=0.8)),
        ))

    _add_third_dividers(fig)
    _add_attack_direction(fig)
    fig.update_layout(**_pitch_layout(uirev))
    return fig


def _gain_stats_table(gains: pd.DataFrame, color: str, top_n: int = 10) -> list:
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
        rows_data.append({
            'player': player,
            'total':  len(grp),
            'z1':     int((grp['x'] < 33.33).sum()),
            'z2':     int(((grp['x'] >= 33.33) & (grp['x'] < 66.67)).sum()),
            'z3':     int((grp['x'] >= 66.67).sum()),
            'br':     int((grp['gain_type'] == 'Ball recovery').sum()),
            'int':    int((grp['gain_type'] == 'Interception').sum()),
            'tkl':    int((grp['gain_type'] == 'Tackle Won').sum()),
        })

    rows_data.sort(key=lambda r: r['total'], reverse=True)
    rows_data = rows_data[:top_n]
    if not rows_data:
        return _no_data

    header = html.Tr([
        html.Th('Player', style={**_TH, 'textAlign': 'left'}),
        html.Th('Tot', style=_TH), html.Th('Z1', style=_TH),
        html.Th('Z2',  style=_TH), html.Th('Z3', style=_TH),
        html.Th('BR',  style=_TH), html.Th('Int', style=_TH),
        html.Th('Tkl', style=_TH),
    ])
    table_rows = []
    for idx, s in enumerate(rows_data):
        bg    = (COLORS.get('dark_tertiary', 'rgba(255,255,255,0.03)')
                 if idx % 2 == 0 else 'transparent')
        short = s['player'].split()[-1] if s['player'] else '—'
        table_rows.append(html.Tr([
            html.Td(short,          style=_NAME_TD),
            html.Td(str(s['total']),style={**_TD, 'color': color, 'fontWeight': '700'}),
            html.Td(str(s['z1']),   style=_TD),
            html.Td(str(s['z2']),   style=_TD),
            html.Td(str(s['z3']),   style={**_TD, 'color': GOLD}),
            html.Td(str(s['br']),   style={**_TD, 'color': '#22c55e'}),
            html.Td(str(s['int']),  style={**_TD, 'color': '#3b82f6'}),
            html.Td(str(s['tkl']),  style={**_TD, 'color': GOLD}),
        ], style={'backgroundColor': bg}))

    legend = html.Div(
        "Z1=Def Third · Z2=Mid Third · Z3=Att Third · "
        "BR=Ball recovery · Int=Interception · Tkl=Tackle Won",
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


def _gain_zone_summary(gains: pd.DataFrame, color: str) -> list:
    if gains.empty:
        return []
    total = max(len(gains), 1)
    z1 = int((gains['x'] < 33.33).sum())
    z2 = int(((gains['x'] >= 33.33) & (gains['x'] < 66.67)).sum())
    z3 = int((gains['x'] >= 66.67).sum())

    def _row(label, count, c):
        pct = round(count / total * 100)
        return html.Div([
            html.Span(label, style={'color': COLORS['text_secondary'],
                                    'fontSize': '0.68rem', 'minWidth': '80px'}),
            html.Div(style={'flex': '1', 'height': '6px',
                            'backgroundColor': COLORS['dark_border'],
                            'borderRadius': '3px', 'overflow': 'hidden',
                            'margin': '0 8px'}, children=[
                html.Div(style={'width': f'{pct}%', 'height': '100%',
                                'backgroundColor': c, 'borderRadius': '3px'}),
            ]),
            html.Span(f'{count}  ({pct}%)', style={'color': c, 'fontSize': '0.68rem',
                                                    'fontWeight': '700', 'minWidth': '60px',
                                                    'textAlign': 'right'}),
        ], style={'display': 'flex', 'alignItems': 'center', 'padding': '4px 0'})

    return [
        html.Hr(style={'borderColor': COLORS['dark_border'], 'margin': '10px 0 8px'}),
        html.Div("Gains by Zone", style={**_SECTION_TITLE, 'marginBottom': '6px'}),
        _row('Zone 1 (Def Third)', z1, AWAY_COLOR),
        _row('Zone 2 (Mid Third)', z2, GOLD),
        _row('Zone 3 (Att Third)', z3, color),
    ]


def _atk_outcome_donut(gains: pd.DataFrame, uirev: str) -> go.Figure:
    labels = ['Possession Held', 'Quick Turnover', 'Shot Taken', 'Goal Scored']
    colors = ['#6b7280', AWAY_COLOR, GOLD, '#22c55e']
    col    = gains['window_outcome'] if not gains.empty and 'window_outcome' in gains.columns \
             else pd.Series(dtype=str)
    values = [int((col == l).sum()) for l in labels]
    fig = go.Figure(go.Pie(
        labels=labels, values=values,
        marker=dict(colors=colors, line=dict(color=PITCH_BG, width=2)),
        hole=0.55, textinfo='percent',
        textfont=dict(color='white', size=11),
        hovertemplate='<b>%{label}</b><br>%{value} (%{percent})<extra></extra>',
        sort=False,
    ))
    fig.update_layout(
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
        font=dict(color='#E8E9ED', size=11, family='Arial, sans-serif'),
        height=260, margin=dict(l=0, r=0, t=10, b=0),
        showlegend=True,
        legend=dict(orientation='v', x=1.0, y=0.5, xanchor='left', yanchor='middle',
                    font=dict(color=COLORS['text_primary'], size=9),
                    bgcolor='rgba(0,0,0,0)'),
        uirevision=uirev,
    )
    return fig


def _atk_event_types_bar(te_in_windows: pd.DataFrame, uirev: str) -> go.Figure:
    if te_in_windows.empty or 'event_type' not in te_in_windows.columns:
        fig = go.Figure()
        fig.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor=PITCH_BG,
                          height=240, margin=dict(l=10, r=10, t=10, b=10))
        return fig

    counts = (te_in_windows['event_type'].value_counts()
              .head(10).sort_values(ascending=True))
    bar_colors = []
    for etype in counts.index:
        if etype == 'Goal':
            bar_colors.append('#22c55e')
        elif etype in _SHOT_TYPES:
            bar_colors.append(GOLD)
        elif etype == 'Pass':
            bar_colors.append('#3b82f6')
        else:
            bar_colors.append('#6b7280')

    fig = go.Figure(go.Bar(
        y=counts.index.tolist(), x=counts.values.tolist(),
        orientation='h', marker_color=bar_colors,
        hovertemplate='%{y}: %{x}<extra></extra>',
    ))
    fig.update_layout(
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor=PITCH_BG,
        font=dict(color='#E8E9ED', size=10, family='Arial, sans-serif'),
        height=280, margin=dict(l=10, r=10, t=10, b=10),
        xaxis=dict(showgrid=False, zeroline=False, title='Count',
                   title_font=dict(size=9), tickfont=dict(size=9)),
        yaxis=dict(showgrid=False, tickfont=dict(size=10)),
        showlegend=False, uirevision=uirev,
    )
    return fig



# ═══════════════════════════════════════════════════════════════════════════════
# Public builder
# ═══════════════════════════════════════════════════════════════════════════════

def build_transitions_counterpressing_tab(events: pd.DataFrame, **_) -> html.Div:
    if events.empty:
        return html.P("No event data.", style={"color": COLORS["text_secondary"]})

    home_team = events['home_team'].iloc[0] if 'home_team' in events.columns else 'Home'
    away_team = events['away_team'].iloc[0] if 'away_team' in events.columns else 'Away'

    home_te = events[events['team_position'] == 'home']
    away_te = events[events['team_position'] == 'away']

    # ── Precompute — Defensive Transition ─────────────────────────────────────
    home_losses  = _extract_losses(home_te, events)
    home_opp_win = _opp_events_in_windows(home_losses, away_te)
    home_losses  = _tag_loss_outcomes(home_losses, home_te, away_te)

    away_losses  = _extract_losses(away_te, events)
    away_opp_win = _opp_events_in_windows(away_losses, home_te)
    away_losses  = _tag_loss_outcomes(away_losses, away_te, home_te)

    # ── Precompute — Attacking Transition ──────────────────────────────────────
    home_gains  = _extract_gains(home_te)
    home_te_win = _team_events_in_windows(home_gains, home_te)
    home_gains  = _tag_gain_outcomes(home_gains, home_te)

    away_gains  = _extract_gains(away_te)
    away_te_win = _team_events_in_windows(away_gains, away_te)
    away_gains  = _tag_gain_outcomes(away_gains, away_te)

    def _hm(df, color):
        valid = df.dropna(subset=['x', 'y'])
        if len(valid) < 2:
            return _SKEL_SRC
        return render_lsc_heatmap_img(valid['x'].values, valid['y'].values,
                                      color_hex=color, half=False)

    def _name(label, color):
        return html.Div(label, style={
            'color': color, 'fontWeight': '700',
            'fontSize': '0.85rem', 'marginBottom': '8px',
        })

    # ════════════════════════════════════════════════════════════════════════════
    # DEFENSIVE TRANSITION sub-tab
    # ════════════════════════════════════════════════════════════════════════════

    def_content = html.Div([
        html.Div(
            'Transition from Attack to Defence — 30-second windows after possession losses',
            style={'fontSize': '0.85rem', 'color': COLORS['text_secondary'],
                   'fontStyle': 'italic', 'marginBottom': '20px', 'letterSpacing': '0.3px'},
        ),

        section_header('Possession Loss Stats'),
        build_info_box(
            'KPI breakdown — total losses by zone and opponent threat in the 30s window'
        ),
        dbc.Row([
            dbc.Col(html.Div([_name(home_team, HOME_COLOR),
                              *_losses_zone_donut_card(home_losses, home_opp_win, HOME_COLOR)],
                             style=CARD_STYLE), md=6, className='mb-3'),
            dbc.Col(html.Div([_name(away_team, AWAY_COLOR),
                              *_losses_zone_donut_card(away_losses, away_opp_win, AWAY_COLOR)],
                             style=CARD_STYLE), md=6, className='mb-3'),
        ], className='g-3'),

        section_header('Possession Loss Map'),
        build_info_box(
            'Location of every possession loss · colour = loss type · shape = 30s outcome · hover for detail'
        ),
        dbc.Row([
            dbc.Col(html.Div([_name(home_team, HOME_COLOR),
                              dcc.Graph(figure=_loss_pitch_map(home_losses, 'def-pitch-home'),
                                        config=CHART_CFG, style={'width': '100%'})],
                             style=CARD_STYLE), md=6, className='mb-3'),
            dbc.Col(html.Div([_name(away_team, AWAY_COLOR),
                              dcc.Graph(figure=_loss_pitch_map(away_losses, 'def-pitch-away'),
                                        config=CHART_CFG, style={'width': '100%'})],
                             style=CARD_STYLE), md=6, className='mb-3'),
        ], className='g-3'),

        section_header('Possession Loss Heatmap'),
        build_info_box('Density of all possession losses across the pitch'),
        dbc.Row([
            dbc.Col(html.Div([_name(home_team, HOME_COLOR),
                              html.Img(src=_hm(home_losses, HOME_COLOR),
                                       style={'width': '100%', 'borderRadius': '6px'})],
                             style=CARD_STYLE), md=6, className='mb-3'),
            dbc.Col(html.Div([_name(away_team, AWAY_COLOR),
                              html.Img(src=_hm(away_losses, AWAY_COLOR),
                                       style={'width': '100%', 'borderRadius': '6px'})],
                             style=CARD_STYLE), md=6, className='mb-3'),
        ], className='g-3'),

        section_header('Losses by Player'),
        build_info_box(
            'Top 10 players by possession losses · '
            'FP=Failed Pass · Mc=Miscontrol · Dis=Dispossessed · Duel=Lost Duel · Air=Lost Aerial'
        ),
        dbc.Row([
            dbc.Col(html.Div([_name(home_team, HOME_COLOR),
                              *_loss_stats_table(home_losses, HOME_COLOR)],
                             style=CARD_STYLE), md=6, className='mb-3'),
            dbc.Col(html.Div([_name(away_team, AWAY_COLOR),
                              *_loss_stats_table(away_losses, AWAY_COLOR)],
                             style=CARD_STYLE), md=6, className='mb-3'),
        ], className='g-3'),

        section_header('Transition Outcomes'),
        build_info_box('How each 30-second window after a possession loss resolved'),
        dbc.Row([
            dbc.Col(html.Div([_name(home_team, HOME_COLOR),
                              dcc.Graph(figure=_def_outcome_donut(home_losses, 'def-donut-home'),
                                        config=CHART_CFG, style={'width': '100%'})],
                             style=CARD_STYLE), md=6, className='mb-3'),
            dbc.Col(html.Div([_name(away_team, AWAY_COLOR),
                              dcc.Graph(figure=_def_outcome_donut(away_losses, 'def-donut-away'),
                                        config=CHART_CFG, style={'width': '100%'})],
                             style=CARD_STYLE), md=6, className='mb-3'),
        ], className='g-3'),

        section_header('Opponent Actions in Transition Window'),
        build_info_box(
            'Top event types by the opposition in the 30 seconds following a possession loss'
        ),
        dbc.Row([
            dbc.Col(html.Div([_name(home_team, HOME_COLOR),
                              dcc.Graph(figure=_def_event_types_bar(home_opp_win, 'def-bar-home'),
                                        config=CHART_CFG, style={'width': '100%'})],
                             style=CARD_STYLE), md=6, className='mb-3'),
            dbc.Col(html.Div([_name(away_team, AWAY_COLOR),
                              dcc.Graph(figure=_def_event_types_bar(away_opp_win, 'def-bar-away'),
                                        config=CHART_CFG, style={'width': '100%'})],
                             style=CARD_STYLE), md=6, className='mb-3'),
        ], className='g-3'),
    ], style={'paddingTop': '16px'})

    # ════════════════════════════════════════════════════════════════════════════
    # ATTACKING TRANSITION sub-tab
    # ════════════════════════════════════════════════════════════════════════════

    atk_content = html.Div([
        html.Div(
            'Transition from Defence to Attack — 30-second windows after possession gains',
            style={'fontSize': '0.85rem', 'color': COLORS['text_secondary'],
                   'fontStyle': 'italic', 'marginBottom': '20px', 'letterSpacing': '0.3px'},
        ),

        section_header('Possession Gain Stats'),
        build_info_box(
            'KPI breakdown — total gains by zone, shots and goals within the 30s window'
        ),
        dbc.Row([
            dbc.Col(html.Div([_name(home_team, HOME_COLOR),
                              *_gains_zone_donut_card(home_gains, home_te_win, HOME_COLOR)],
                             style=CARD_STYLE), md=6, className='mb-3'),
            dbc.Col(html.Div([_name(away_team, AWAY_COLOR),
                              *_gains_zone_donut_card(away_gains, away_te_win, AWAY_COLOR)],
                             style=CARD_STYLE), md=6, className='mb-3'),
        ], className='g-3'),

        section_header('Possession Gain Map'),
        build_info_box(
            'Location of every possession gain · colour = gain type · shape = 30s outcome · hover for detail'
        ),
        dbc.Row([
            dbc.Col(html.Div([_name(home_team, HOME_COLOR),
                              dcc.Graph(figure=_gain_pitch_map(home_gains, 'atk-pitch-home'),
                                        config=CHART_CFG, style={'width': '100%'})],
                             style=CARD_STYLE), md=6, className='mb-3'),
            dbc.Col(html.Div([_name(away_team, AWAY_COLOR),
                              dcc.Graph(figure=_gain_pitch_map(away_gains, 'atk-pitch-away'),
                                        config=CHART_CFG, style={'width': '100%'})],
                             style=CARD_STYLE), md=6, className='mb-3'),
        ], className='g-3'),

        section_header('Possession Gain Heatmap'),
        build_info_box('Density of all possession gains across the pitch'),
        dbc.Row([
            dbc.Col(html.Div([_name(home_team, HOME_COLOR),
                              html.Img(src=_hm(home_gains, HOME_COLOR),
                                       style={'width': '100%', 'borderRadius': '6px'})],
                             style=CARD_STYLE), md=6, className='mb-3'),
            dbc.Col(html.Div([_name(away_team, AWAY_COLOR),
                              html.Img(src=_hm(away_gains, AWAY_COLOR),
                                       style={'width': '100%', 'borderRadius': '6px'})],
                             style=CARD_STYLE), md=6, className='mb-3'),
        ], className='g-3'),

        section_header('Gains by Player'),
        build_info_box(
            'Top 10 players by possession gains · '
            'BR=Ball recovery · Int=Interception · Tkl=Tackle Won'
        ),
        dbc.Row([
            dbc.Col(html.Div([_name(home_team, HOME_COLOR),
                              *_gain_stats_table(home_gains, HOME_COLOR)],
                             style=CARD_STYLE), md=6, className='mb-3'),
            dbc.Col(html.Div([_name(away_team, AWAY_COLOR),
                              *_gain_stats_table(away_gains, AWAY_COLOR)],
                             style=CARD_STYLE), md=6, className='mb-3'),
        ], className='g-3'),

        section_header('Transition Outcomes'),
        build_info_box('How each 30-second window after a possession gain resolved'),
        dbc.Row([
            dbc.Col(html.Div([_name(home_team, HOME_COLOR),
                              dcc.Graph(figure=_atk_outcome_donut(home_gains, 'atk-donut-home'),
                                        config=CHART_CFG, style={'width': '100%'})],
                             style=CARD_STYLE), md=6, className='mb-3'),
            dbc.Col(html.Div([_name(away_team, AWAY_COLOR),
                              dcc.Graph(figure=_atk_outcome_donut(away_gains, 'atk-donut-away'),
                                        config=CHART_CFG, style={'width': '100%'})],
                             style=CARD_STYLE), md=6, className='mb-3'),
        ], className='g-3'),

        section_header('Team Actions in Transition Window'),
        build_info_box(
            'Top event types by each team in the 30 seconds following a possession gain'
        ),
        dbc.Row([
            dbc.Col(html.Div([_name(home_team, HOME_COLOR),
                              dcc.Graph(figure=_atk_event_types_bar(home_te_win, 'atk-bar-home'),
                                        config=CHART_CFG, style={'width': '100%'})],
                             style=CARD_STYLE), md=6, className='mb-3'),
            dbc.Col(html.Div([_name(away_team, AWAY_COLOR),
                              dcc.Graph(figure=_atk_event_types_bar(away_te_win, 'atk-bar-away'),
                                        config=CHART_CFG, style={'width': '100%'})],
                             style=CARD_STYLE), md=6, className='mb-3'),
        ], className='g-3'),
    ], style={'paddingTop': '16px'})

    return html.Div([
        dbc.Tabs(
            active_tab='tc-def-trans',
            children=[
                dbc.Tab(
                    def_content,
                    label='Defensive Transition',
                    tab_id='tc-def-trans',
                    tab_style={'flex': '1'},
                    label_style=_BTN_INACTIVE,
                    active_label_style=_BTN_ACTIVE,
                ),
                dbc.Tab(
                    atk_content,
                    label='Attacking Transition',
                    tab_id='tc-atk-trans',
                    tab_style={'flex': '1'},
                    label_style=_BTN_INACTIVE,
                    active_label_style=_BTN_ACTIVE,
                ),
            ],
            className='mb-3',
        ),
    ], style={'marginTop': '16px'})


def register_transitions_counterpressing_callbacks(app) -> None:
    pass
