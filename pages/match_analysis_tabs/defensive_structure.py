from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from dash import html, dcc
import dash_bootstrap_components as dbc

from utils.config import COLORS
from utils.data_utils import get_match_events, get_match_results
from page_utils.visualizations import (
    HOME_COLOR, AWAY_COLOR, GOLD, CHART_CONFIG,
    layout_config, add_pitch_background,
    PITCH_AXIS_FULL, render_xt_heatmap_img,
)
from page_utils.event_filters import DEF_ACTION_TYPES
from page_utils.pitch_zones import get_zone, PitchZone
from .shared import (
    CARD_STYLE, section_header, build_legend_box,
    build_team_stats_table,
)

_PITCH_HEIGHT = 480

_DEF_COLORS = {
    'Tackle':        '#4dabf7',
    'Interception':  '#51cf66',
    'Ball recovery': '#ffd43b',
    'Clearance':     '#ff922b',
    'Blocked Shot':  '#cc5de8',
}

_DEF_METRICS = [
    ('Tackles Won',      'tackles_str',     False),
    ('Interceptions',    'interceptions',   False),
    ('Clearances',       'clearances',      False),
    ('Ball Recoveries',  'ball_recoveries', False),
    ('Blocked Shots',    'blocked_shots',   False),
    ('Fouls Committed',  'fouls_committed', False),
    ('Aerial Duels',     'aerials_str',     False),
    ('PPDA',             'ppda',            False),
]

_DEF_RADAR_KEYS = [
    ('Tackles Won',     'tackles_won',     False),
    ('Interceptions',   'interceptions',   False),
    ('Clearances',      'clearances',      False),
    ('Ball Recoveries', 'ball_recoveries', False),
    ('Fouls Committed', 'fouls_committed', False),
    ('Aerials Won',     'aerials_won',     False),
    ('PPDA',            'ppda',            True),
]

_def_league_avg_cache: dict = {}
_def_zone_league_cache: dict = {}

_ZONE_LABELS = ['Z1', 'Z2', 'Z3']  # Z1 = own def third, Z2 = middle, Z3 = final third


def _zone_counts(df: pd.DataFrame) -> list:
    """Count rows by pitch third → [Z1, Z2, Z3]."""
    z1 = z2 = z3 = 0
    if 'x' in df.columns:
        for x_val in pd.to_numeric(df['x'], errors='coerce').dropna():
            z = get_zone(float(x_val))
            if z == PitchZone.FINAL_THIRD:    z3 += 1
            elif z == PitchZone.MIDDLE_THIRD: z2 += 1
            else:                             z1 += 1
    return [z1, z2, z3]


def _compute_half_stats(events: pd.DataFrame, pos: str, period: int | None = None) -> dict:
    home_team = events['home_team'].iloc[0]
    away_team = events['away_team'].iloc[0]
    team = home_team if pos == 'home' else away_team
    te  = events[events['team_position'] == pos]
    opp = events[events['team_position'] != pos]
    if period is not None:
        te  = te[te['period_id'] == period]
        opp = opp[opp['period_id'] == period]
    tackles         = te[te['event_type'] == 'Tackle']
    tackles_won     = tackles[tackles['outcome'] == 1]
    interceptions   = te[te['event_type'] == 'Interception']
    clearances      = te[te['event_type'] == 'Clearance']
    ball_recoveries = te[te['event_type'] == 'Ball recovery']
    blocked_shots   = te[te['event_type'] == 'Blocked Shot']
    fouls_committed = te[te['event_type'] == 'Foul']
    if 'outcome' in te.columns:
        fouls_committed = fouls_committed[fouls_committed['outcome'] == 1]
    aerials     = te[te['event_type'] == 'Aerial']
    aerials_won = aerials[aerials['outcome'] == 1]
    opp_passes  = len(opp[opp['event_type'] == 'Pass'])
    def_actions = len(tackles) + len(interceptions) + len(fouls_committed)
    ppda = round(opp_passes / def_actions, 1) if def_actions > 0 else 0.0
    return {
        'team': team,
        'tackles':         len(tackles),     'tackles_won':     len(tackles_won),
        'tackles_str':     f'{len(tackles_won)}/{len(tackles)}',
        'interceptions':   len(interceptions),
        'clearances':      len(clearances),
        'ball_recoveries': len(ball_recoveries),
        'blocked_shots':   len(blocked_shots),
        'fouls_committed': len(fouls_committed),
        'aerials':         len(aerials),     'aerials_won': len(aerials_won),
        'aerials_str':     f'{len(aerials_won)}/{len(aerials)}',
        'ppda':            ppda,
    }


def _compute(events: pd.DataFrame) -> dict:
    home_team = events['home_team'].iloc[0]
    away_team = events['away_team'].iloc[0]
    out = {}
    for pos, team in (('home', home_team), ('away', away_team)):
        te  = events[events['team_position'] == pos]
        opp = events[events['team_position'] != pos]
        tackles         = te[te['event_type'] == 'Tackle']
        interceptions   = te[te['event_type'] == 'Interception']
        clearances      = te[te['event_type'] == 'Clearance']
        ball_recoveries = te[te['event_type'] == 'Ball recovery']
        blocked_shots   = te[te['event_type'] == 'Blocked Shot']
        all_def = pd.concat([tackles, interceptions, ball_recoveries])
        high_count = mid_count = low_count = 0
        if 'x' in all_def.columns:
            for x_val in all_def['x'].dropna():
                z = get_zone(float(x_val))
                if z == PitchZone.FINAL_THIRD:     high_count += 1
                elif z == PitchZone.MIDDLE_THIRD:  mid_count  += 1
                else:                              low_count  += 1
        heatmap_x = all_def['x'].dropna().tolist() if 'x' in all_def.columns else []
        heatmap_y = all_def['y'].dropna().tolist() if 'y' in all_def.columns else []
        all_actions = pd.concat([tackles, interceptions, ball_recoveries, clearances, blocked_shots])

        def _player_stats(df):
            if df.empty:
                return pd.DataFrame(columns=['Player', 'Actions', 'Tackles', 'Interceptions',
                                             'Recoveries', 'Clearances', 'Blocks'])
            return (
                df.groupby('player_name')
                .agg(
                    Actions=('event_type', 'count'),
                    Tackles=('event_type', lambda s: (s == 'Tackle').sum()),
                    Interceptions=('event_type', lambda s: (s == 'Interception').sum()),
                    Recoveries=('event_type', lambda s: (s == 'Ball recovery').sum()),
                    Clearances=('event_type', lambda s: (s == 'Clearance').sum()),
                    Blocks=('event_type', lambda s: (s == 'Blocked Shot').sum()),
                )
                .reset_index()
                .rename(columns={'player_name': 'Player'})
                .sort_values('Actions', ascending=False)
                .head(8).reset_index(drop=True)
            )

        player_full = _player_stats(all_actions)
        h1_acts = all_actions[all_actions['period_id'] == 1] if 'period_id' in all_actions.columns else pd.DataFrame()
        h2_acts = all_actions[all_actions['period_id'] == 2] if 'period_id' in all_actions.columns else pd.DataFrame()
        player_h1 = _player_stats(h1_acts)
        player_h2 = _player_stats(h2_acts)
        def_events_df = te[te['event_type'].isin(DEF_ACTION_TYPES)].copy()
        fouls_df = te[te['event_type'] == 'Foul'].copy()
        if 'outcome' in fouls_df.columns:
            fouls_df = fouls_df[fouls_df['outcome'] == 1]
        offsides_df = opp[opp['event_type'] == 'Offside Pass'].copy()
        out[pos] = {
            'team': team,
            'high_press': high_count, 'mid_press': mid_count, 'low_press': low_count,
            'zone_counts': _zone_counts(def_events_df),
            'heatmap_x': heatmap_x, 'heatmap_y': heatmap_y,
            'player_full': player_full, 'player_h1': player_h1, 'player_h2': player_h2,
            'def_events_df': def_events_df, 'fouls_df': fouls_df, 'offsides_df': offsides_df,
        }
    return out


def _compute_def_league_avg(events: pd.DataFrame) -> dict:
    global _def_league_avg_cache
    competition = ''
    if 'competition' in events.columns and not events.empty:
        competition = str(events['competition'].iloc[0])
    if not competition:
        try:
            from utils.match_data_adapter import get_match_metadata
            competition = get_match_metadata(events).get('competition', '')
        except Exception:
            pass
    if not competition:
        return {}
    if competition in _def_league_avg_cache:
        return _def_league_avg_cache[competition]
    try:
        keys = [k for _, k, _ in _DEF_RADAR_KEYS]
        accumulated: dict = {k: [] for k in keys}
        for r in get_match_results():
            if r.get('competition') != competition:
                continue
            try:
                ev = get_match_events(r['match_id'])
                if ev.empty:
                    continue
                for pos in ('home', 'away'):
                    s = _compute_half_stats(ev, pos)
                    for k in keys:
                        v = s.get(k, 0)
                        if isinstance(v, (int, float)) and not pd.isna(v):
                            accumulated[k].append(float(v))
            except Exception:
                continue
        avg = {k: round(sum(v) / len(v), 2) if v else 0.0 for k, v in accumulated.items()}
        _def_league_avg_cache[competition] = avg
        return avg
    except Exception:
        return {}


def _compute_def_zone_league_avg(events: pd.DataFrame) -> list:
    """Average defensive-action count per zone [Z1, Z2, Z3] across the competition (per team-match)."""
    global _def_zone_league_cache
    competition = ''
    if 'competition' in events.columns and not events.empty:
        competition = str(events['competition'].iloc[0])
    if not competition:
        try:
            from utils.match_data_adapter import get_match_metadata
            competition = get_match_metadata(events).get('competition', '')
        except Exception:
            pass
    if not competition:
        return [0.0, 0.0, 0.0]
    if competition in _def_zone_league_cache:
        return _def_zone_league_cache[competition]
    try:
        acc = [[], [], []]
        for r in get_match_results():
            if r.get('competition') != competition:
                continue
            try:
                ev = get_match_events(r['match_id'])
                if ev.empty:
                    continue
                for pos in ('home', 'away'):
                    te  = ev[ev['team_position'] == pos]
                    ddf = te[te['event_type'].isin(DEF_ACTION_TYPES)]
                    for i, c in enumerate(_zone_counts(ddf)):
                        acc[i].append(c)
            except Exception:
                continue
        avg = [round(sum(v) / len(v), 1) if v else 0.0 for v in acc]
        _def_zone_league_cache[competition] = avg
        return avg
    except Exception:
        return [0.0, 0.0, 0.0]


def _def_zone_bar_fig(zone_counts: list, league_avg: list, color: str) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=_ZONE_LABELS, y=zone_counts, name='This Match', marker_color=color,
        text=[str(int(v)) for v in zone_counts], textposition='outside',
        textfont=dict(color=COLORS['text_primary'], size=10), cliponaxis=False,
        hovertemplate='%{x}<br>This Match: %{y}<extra></extra>',
    ))
    fig.add_trace(go.Bar(
        x=_ZONE_LABELS, y=league_avg, name='League Avg', marker_color=GOLD, opacity=0.55,
        text=[f'{v:.1f}' for v in league_avg], textposition='outside',
        textfont=dict(color=GOLD, size=10), cliponaxis=False,
        hovertemplate='%{x}<br>League Avg: %{y}<extra></extra>',
    ))
    fig.update_layout(
        barmode='group', height=_PITCH_HEIGHT,
        margin=dict(l=8, r=8, t=40, b=80),
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
        title=dict(text='Actions by Zone', x=0.5, xanchor='center',
                   font=dict(color=color, size=12)),
        legend=dict(orientation='h', x=0.5, xanchor='center', y=-0.08, yanchor='top',
                    font=dict(color=COLORS['text_primary'], size=9), bgcolor='rgba(0,0,0,0)'),
        xaxis=dict(tickfont=dict(color=COLORS['text_primary'], size=10), showgrid=False),
        yaxis=dict(tickfont=dict(color=COLORS['text_secondary'], size=9),
                   gridcolor='rgba(255,255,255,0.08)', zeroline=False),
        bargap=0.3, bargroupgap=0.12,
    )
    return fig


def _hex_to_rgba_def(hex_color: str, alpha: float = 0.12) -> str:
    h = hex_color.lstrip('#')
    if len(h) == 3:
        h = ''.join(c * 2 for c in h)
    try:
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        return f'rgba({r},{g},{b},{alpha})'
    except (ValueError, IndexError):
        return f'rgba(128,128,128,{alpha})'


def _build_def_radar_fig(home_stats, away_stats, league_avg, home_team, away_team) -> go.Figure:
    labels  = [lbl for lbl, _, _   in _DEF_RADAR_KEYS]
    keys    = [k   for _,   k, _   in _DEF_RADAR_KEYS]
    inverts = [inv for _,   _, inv in _DEF_RADAR_KEYS]

    def _raw(stats):
        return [float(stats.get(k, 0) or 0) for k in keys]

    hv_raw = _raw(home_stats); av_raw = _raw(away_stats)
    lv_raw = _raw(league_avg) if league_avg else None

    def _transform(vals):
        return [1.0 / v if inv and v > 0 else v for v, inv in zip(vals, inverts)]

    hv = _transform(hv_raw); av = _transform(av_raw)
    lv = _transform(lv_raw) if lv_raw is not None else None
    norm_h, norm_a, norm_l = [], [], []
    for i in range(len(keys)):
        candidates = [hv[i], av[i]] + ([lv[i]] if lv else [])
        max_v = max(candidates) if max(candidates) > 0 else 1.0
        norm_h.append(round(hv[i] / max_v * 100, 1))
        norm_a.append(round(av[i] / max_v * 100, 1))
        if lv:
            norm_l.append(round(lv[i] / max_v * 100, 1))
    labels_c = labels + [labels[0]]
    norm_h_c = norm_h + [norm_h[0]]; norm_a_c = norm_a + [norm_a[0]]
    hv_raw_c = hv_raw + [hv_raw[0]]; av_raw_c = av_raw + [av_raw[0]]
    if lv:
        norm_l_c = norm_l + [norm_l[0]]; lv_raw_c = lv_raw + [lv_raw[0]]

    def _fmt(v):
        return f'{v:.1f}' if v != int(v) else str(int(v))

    fig = go.Figure()
    if lv:
        fig.add_trace(go.Scatterpolar(
            r=norm_l_c, theta=labels_c, mode='lines', name='League Avg',
            line=dict(color=GOLD, width=1.5, dash='dot'), opacity=0.85,
            customdata=[[_fmt(lv_raw_c[i])] for i in range(len(labels_c))],
            hovertemplate='<b>League Avg</b><br>%{theta}: %{customdata[0]}<extra></extra>',
        ))
    fig.add_trace(go.Scatterpolar(
        r=norm_a_c, theta=labels_c, mode='lines+markers+text', name=away_team,
        fill='toself', fillcolor=_hex_to_rgba_def(AWAY_COLOR, 0.12),
        line=dict(color=AWAY_COLOR, width=2), marker=dict(size=5, color=AWAY_COLOR),
        text=[_fmt(av_raw_c[i]) for i in range(len(labels_c))],
        textposition='bottom center', textfont=dict(size=10, color='#FFFFFF'),
        customdata=[[_fmt(av_raw_c[i])] for i in range(len(labels_c))],
        hovertemplate=f'<b>{away_team}</b><br>%{{theta}}: %{{customdata[0]}}<extra></extra>',
    ))
    fig.add_trace(go.Scatterpolar(
        r=norm_h_c, theta=labels_c, mode='lines+markers+text', name=home_team,
        fill='toself', fillcolor=_hex_to_rgba_def(HOME_COLOR, 0.12),
        line=dict(color=HOME_COLOR, width=2), marker=dict(size=5, color=HOME_COLOR),
        text=[_fmt(hv_raw_c[i]) for i in range(len(labels_c))],
        textposition='top center', textfont=dict(size=10, color='#FFFFFF'),
        customdata=[[_fmt(hv_raw_c[i])] for i in range(len(labels_c))],
        hovertemplate=f'<b>{home_team}</b><br>%{{theta}}: %{{customdata[0]}}<extra></extra>',
    ))
    fig.update_layout(
        polar=dict(
            bgcolor='rgba(26,29,46,0.6)',
            radialaxis=dict(visible=True, range=[0, 105], showticklabels=False,
                            gridcolor='rgba(255,255,255,0.08)', linecolor='rgba(255,255,255,0.08)'),
            angularaxis=dict(tickfont=dict(size=10, color=COLORS['text_primary']),
                             gridcolor='rgba(255,255,255,0.08)', linecolor='rgba(255,255,255,0.08)'),
        ),
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', showlegend=True,
        legend=dict(x=0.5, y=-0.06, xanchor='center', yanchor='top', orientation='h',
                    font=dict(color=COLORS['text_primary'], size=11), bgcolor='rgba(0,0,0,0)'),
        height=540, margin=dict(l=80, r=80, t=30, b=80),
        hoverlabel=dict(bgcolor='#1A1D2E', font_color='white', font_size=12),
    )
    return fig


def _add_attack_direction(fig: go.Figure) -> None:
    fig.add_annotation(
        x=0.5, y=1.0, xref='paper', yref='paper',
        xanchor='center', yanchor='bottom',
        text='➡ Direction of Attack', showarrow=False,
        font=dict(color='black', size=16, family='Arial'),
        align='center', bgcolor='rgba(255,255,255,0.7)', borderpad=3,
    )


def _def_action_map(def_events_df: pd.DataFrame, team_color: str,
                    fouls_df: pd.DataFrame | None = None,
                    offsides_df: pd.DataFrame | None = None) -> dcc.Graph:
    fig = go.Figure()
    add_pitch_background(fig)
    if not def_events_df.empty and 'x' in def_events_df.columns:
        for action_type, group in def_events_df.groupby('event_type'):
            valid = group.dropna(subset=['x', 'y'])
            if valid.empty:
                continue
            customdata = [[name, t, action_type]
                          for name, t in zip(valid['player_name'].fillna('Unknown').tolist(),
                                             valid['time_min'].fillna(0).astype(int).tolist())]
            fig.add_trace(go.Scatter(
                x=valid['x'].tolist(), y=valid['y'].tolist(), mode='markers', name=action_type,
                marker=dict(color=_DEF_COLORS.get(action_type, team_color), size=8, opacity=0.75,
                            line=dict(color='rgba(0,0,0,0.3)', width=0.5)),
                customdata=customdata,
                hovertemplate='<b>%{customdata[0]}</b><br>Minute: %{customdata[1]}\'<br>Action: %{customdata[2]}<extra></extra>',
            ))
    if fouls_df is not None and not fouls_df.empty and 'x' in fouls_df.columns:
        valid = fouls_df.dropna(subset=['x', 'y'])
        if not valid.empty:
            zones = (valid['Zone'].fillna('—').where(valid['Zone'] != 'N/A', '—').tolist()
                     if 'Zone' in valid.columns else ['—'] * len(valid))
            customdata = [[name, t, 'Foul', z]
                          for name, t, z in zip(valid['player_name'].fillna('Unknown').tolist(),
                                                valid['time_min'].fillna(0).astype(int).tolist(), zones)]
            fig.add_trace(go.Scatter(
                x=valid['x'].tolist(), y=valid['y'].tolist(), mode='markers', name='Foul',
                marker=dict(color='#ff6b6b', size=10, symbol='x', opacity=0.85,
                            line=dict(color='white', width=1)),
                customdata=customdata,
                hovertemplate="<b>%{customdata[0]}</b><br>Minute: %{customdata[1]}'<br>Event: %{customdata[2]}<br>Zone: %{customdata[3]}<extra></extra>",
            ))
    if offsides_df is not None and not offsides_df.empty and 'x' in offsides_df.columns:
        valid = offsides_df.dropna(subset=['x', 'y'])
        if not valid.empty:
            customdata = [[name, t, 'Offside Pass']
                          for name, t in zip(valid['player_name'].fillna('Unknown').tolist(),
                                             valid['time_min'].fillna(0).astype(int).tolist())]
            fig.add_trace(go.Scatter(
                x=valid['x'].tolist(), y=valid['y'].tolist(), mode='markers', name='Offside',
                marker=dict(color='#ffd43b', size=10, symbol='triangle-up', opacity=0.85,
                            line=dict(color='white', width=1)),
                customdata=customdata,
                hovertemplate="<b>%{customdata[0]}</b><br>Minute: %{customdata[1]}'<br>Event: %{customdata[2]}<extra></extra>",
            ))
    _add_attack_direction(fig)
    fig.update_layout(**layout_config(
        **PITCH_AXIS_FULL, height=_PITCH_HEIGHT, margin=dict(l=0, r=0, t=48, b=80),
        legend=dict(orientation='h', x=0.5, xanchor='center', y=-0.08, yanchor='top',
                    bgcolor='rgba(0,0,0,0)', font=dict(color=COLORS['text_primary'], size=9)),
    ))
    return dcc.Graph(figure=fig, config=CHART_CONFIG)


def _player_defensive_table(player_full: pd.DataFrame, player_h1: pd.DataFrame,
                             player_h2: pd.DataFrame, color: str, team_name: str) -> html.Div:
    if player_full.empty:
        return html.Div("No data", style={'color': COLORS['text_secondary']})
    _hdr = {'fontSize': '0.65rem', 'fontWeight': '700', 'padding': '5px 8px',
            'color': COLORS['text_secondary'], 'textTransform': 'uppercase',
            'letterSpacing': '0.04em', 'borderBottom': f'1px solid {COLORS["dark_border"]}'}
    _val = {'fontSize': '0.78rem', 'padding': '4px 8px', 'color': COLORS['text_primary'], 'textAlign': 'center'}
    cols = ['Player', 'Actions', 'Tackles', 'Int.', 'Rec.', 'Clr.', 'Blk.', '1H', '2H']
    header = html.Tr([html.Th(c, style=_hdr) for c in cols])
    rows = []
    for i, (_, row) in enumerate(player_full.iterrows()):
        bg = COLORS['dark_tertiary'] if i % 2 == 0 else 'transparent'
        pname = row.get('Player', '')
        h1_row = player_h1[player_h1['Player'] == pname]
        h2_row = player_h2[player_h2['Player'] == pname]
        h1_total = int(h1_row['Actions'].iloc[0]) if not h1_row.empty else 0
        h2_total = int(h2_row['Actions'].iloc[0]) if not h2_row.empty else 0
        short_name = str(pname).split()[-1] if pname else ''
        cells = [
            html.Td(short_name, style={**_val, 'color': color, 'fontWeight': '600',
                                        'textAlign': 'left', 'whiteSpace': 'nowrap'}),
            html.Td(str(int(row.get('Actions', 0))), style=_val),
            html.Td(str(int(row.get('Tackles', 0))), style=_val),
            html.Td(str(int(row.get('Interceptions', 0))), style=_val),
            html.Td(str(int(row.get('Recoveries', 0))), style=_val),
            html.Td(str(int(row.get('Clearances', 0))), style=_val),
            html.Td(str(int(row.get('Blocks', 0))), style=_val),
            html.Td(str(h1_total), style={**_val, 'color': COLORS['text_secondary']}),
            html.Td(str(h2_total), style={**_val, 'color': COLORS['text_secondary']}),
        ]
        rows.append(html.Tr(cells, style={'backgroundColor': bg}))
    return html.Div([
        html.Div(team_name, style={'color': color, 'fontWeight': '700', 'fontSize': '0.95rem',
                                   'marginBottom': '10px', 'borderBottom': f'2px solid {color}',
                                   'paddingBottom': '6px'}),
        html.Div(html.Table([html.Thead(header), html.Tbody(rows)],
                             style={'width': '100%', 'borderCollapse': 'collapse'}),
                 style={'overflowX': 'auto'}),
    ], style=CARD_STYLE)


def _def_action_heatmap(x_vals: list, y_vals: list, team: str, color: str) -> html.Div:
    label = html.Div(f"Defensive Actions — {team}", style={
        'color': color, 'fontWeight': '600', 'fontSize': '0.85rem',
        'marginBottom': '8px', 'textAlign': 'center',
    })
    if len(x_vals) < 2:
        return html.Div([label, html.Div("Not enough data",
                                          style={'color': COLORS['text_secondary'], 'textAlign': 'center', 'fontSize': '0.8rem'})],
                        style=CARD_STYLE)
    img_src = render_xt_heatmap_img(x_vals, y_vals, [1.0] * len(x_vals))
    return html.Div([label, html.Img(src=img_src, style={'width': '100%', 'borderRadius': '6px'})],
                    style=CARD_STYLE)


def _fouls_offsides_map(fouls_df: pd.DataFrame, offsides_df: pd.DataFrame) -> dcc.Graph:
    fig = go.Figure()
    add_pitch_background(fig)
    if not fouls_df.empty and 'x' in fouls_df.columns:
        valid = fouls_df.dropna(subset=['x', 'y'])
        if not valid.empty:
            zones = (valid['Zone'].fillna('—').astype(str).where(valid['Zone'] != 'N/A', '—').tolist()
                     if 'Zone' in valid.columns else ['—'] * len(valid))
            customdata = [[name, t, 'Foul', z]
                          for name, t, z in zip(valid['player_name'].fillna('Unknown').tolist(),
                                                valid['time_min'].fillna(0).astype(int).tolist(), zones)]
            fig.add_trace(go.Scatter(
                x=valid['x'].tolist(), y=valid['y'].tolist(), mode='markers', name='Foul',
                marker=dict(color='#ff6b6b', size=10, symbol='x', opacity=0.85,
                            line=dict(color='white', width=1)),
                customdata=customdata,
                hovertemplate="<b>%{customdata[0]}</b><br>Minute: %{customdata[1]}'<br>Event: %{customdata[2]}<br>Zone: %{customdata[3]}<extra></extra>",
            ))
    if not offsides_df.empty and 'x' in offsides_df.columns:
        valid = offsides_df.dropna(subset=['x', 'y'])
        if not valid.empty:
            customdata = [[name, t, 'Offside Pass']
                          for name, t in zip(valid['player_name'].fillna('Unknown').tolist(),
                                             valid['time_min'].fillna(0).astype(int).tolist())]
            fig.add_trace(go.Scatter(
                x=valid['x'].tolist(), y=valid['y'].tolist(), mode='markers', name='Offside',
                marker=dict(color='#ffd43b', size=10, symbol='triangle-up', opacity=0.85,
                            line=dict(color='white', width=1)),
                customdata=customdata,
                hovertemplate="<b>%{customdata[0]}</b><br>Minute: %{customdata[1]}'<br>Event: %{customdata[2]}<extra></extra>",
            ))
    _add_attack_direction(fig)
    fig.update_layout(**layout_config(
        **PITCH_AXIS_FULL, height=_PITCH_HEIGHT, margin=dict(l=0, r=0, t=48, b=0),
        legend=dict(orientation='v', x=0.01, xanchor='left', y=0.99, yanchor='top',
                    bgcolor='rgba(0,0,0,0.55)', font=dict(color=COLORS['text_primary'], size=9)),
    ))
    return dcc.Graph(figure=fig, config=CHART_CONFIG)


def _render_def_plots(events: pd.DataFrame) -> html.Div:
    if events.empty:
        return html.P("No event data.", style={"color": COLORS["text_secondary"]})
    d = _compute(events)
    hs, as_ = d['home'], d['away']
    zone_league_avg = _compute_def_zone_league_avg(events)

    def _team_card(data, color):
        return dbc.Col(html.Div([
            html.Div(data['team'], style={'color': color, 'fontWeight': '700',
                                          'fontSize': '0.85rem', 'marginBottom': '8px'}),
            dbc.Row([
                dbc.Col(_def_action_map(data['def_events_df'], color,
                                        data['fouls_df'], data['offsides_df']), md=9),
                dbc.Col(dcc.Graph(figure=_def_zone_bar_fig(data['zone_counts'], zone_league_avg, color),
                                  config=CHART_CONFIG), md=3),
            ], className='g-2', align='start'),
            html.Div(_player_defensive_table(data['player_full'], data['player_h1'], data['player_h2'],
                                             color, data['team']), style={'marginTop': '12px'}),
        ], style=CARD_STYLE), md=6, className='mb-3')

    return html.Div([
        section_header("Defensive Action Map"),
        build_legend_box([
            ('●', 'Tackle',       '#4dabf7'), ('●', 'Interception', '#51cf66'),
            ('●', 'Recovery',     '#ffd43b'), ('●', 'Clearance',    '#ff922b'),
            ('●', 'Block',        '#cc5de8'), ('✕', 'Foul',         '#ff6b6b'),
            ('▲', 'Offside',      '#ffd43b'),
        ]),
        dbc.Row([
            _team_card(hs, HOME_COLOR),
            _team_card(as_, AWAY_COLOR),
        ], className='g-3'),
    ], style={'marginBottom': '32px'})


def build_defensive_structure_tab(events: pd.DataFrame, **_) -> html.Div:
    if events.empty:
        return html.P("No event data.", style={"color": COLORS["text_secondary"]})
    return html.Div([_render_def_plots(events)], style={'marginTop': '16px'})


def build_def_radar(events: pd.DataFrame):
    if events.empty:
        return None
    home_team  = str(events['home_team'].iloc[0]) if 'home_team' in events.columns else 'Home'
    away_team  = str(events['away_team'].iloc[0]) if 'away_team' in events.columns else 'Away'
    h_full     = _compute_half_stats(events, 'home')
    a_full     = _compute_half_stats(events, 'away')
    league_avg = _compute_def_league_avg(events)
    return _build_def_radar_fig(h_full, a_full, league_avg, home_team, away_team)


def register_defensive_structure_callbacks(app) -> None:
    pass
