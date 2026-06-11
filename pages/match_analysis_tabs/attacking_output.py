from __future__ import annotations
import math
import pandas as pd
import plotly.graph_objects as go
from dash import html, dcc
import dash_bootstrap_components as dbc
from utils.config import COLORS
from utils.data_utils import exclude_own_goals
from utils.xg_utils import add_xg_column
from utils.match_data_adapter import get_match_metadata, compute_team_kpis
from utils.data_utils import get_match_results, get_match_events
from .shared import CARD_STYLE, section_header, build_info_box, build_legend_box
from page_utils.visualizations import HOME_COLOR, AWAY_COLOR, GOLD, CHART_CONFIG, layout_config, add_pitch_background, add_vertical_half_pitch_background, PITCH_AXIS_FULL, VPITCH_AXIS_HALF, render_xt_heatmap_img
from page_utils.event_filters import SHOT_TYPES
from page_utils.pitch_zones import BOX_X_MIN, BOX_Y_MIN, BOX_Y_MAX

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

_SI = ('N/A', '', 'nan', None)


def _count_from_box(shots: pd.DataFrame) -> int:
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

        shots = exclude_own_goals(sorted_te[sorted_te['event_type'].isin(SHOT_TYPES)].copy())
        shots = add_xg_column(shots)
        goals = shots[shots['event_type'] == 'Goal']
        shots['shot_type'] = shots.apply(_get_shot_type, axis=1)

        if 'Assist' in sorted_te.columns:
            key_passes = sorted_te[
                (sorted_te['event_type'] == 'Pass') &
                pd.to_numeric(sorted_te['Assist'], errors='coerce').isin([13, 14, 15, 16])
            ].copy()
        else:
            key_passes = pd.DataFrame()

        carry_lines: list = []
        if not key_passes.empty:
            _carry_types = {'Take On', 'Carry', 'Ball touch'}
            for ki in key_passes.index:
                kp   = sorted_te.iloc[ki]
                pe_x = pd.to_numeric(kp.get('Pass End X'), errors='coerce')
                pe_y = pd.to_numeric(kp.get('Pass End Y'), errors='coerce')
                if pd.isna(pe_x) or pd.isna(pe_y):
                    continue
                shot_pos, shot_row = None, None
                for j in range(ki + 1, min(ki + 8, len(sorted_te))):
                    if sorted_te.iloc[j]['event_type'] in SHOT_TYPES:
                        shot_pos, shot_row = j, sorted_te.iloc[j]
                        break
                if shot_pos is None:
                    continue
                sx = pd.to_numeric(shot_row.get('x'), errors='coerce')
                sy = pd.to_numeric(shot_row.get('y'), errors='coerce')
                if pd.isna(sx) or pd.isna(sy):
                    continue
                if ((float(sx) - float(pe_x)) ** 2 + (float(sy) - float(pe_y)) ** 2) ** 0.5 < 4.0:
                    continue
                shooter = shot_row.get('player_name')
                mid_pts: list = []
                for k in range(ki + 1, shot_pos):
                    ev = sorted_te.iloc[k]
                    if ev['event_type'] in _carry_types and ev.get('player_name') == shooter:
                        mx = pd.to_numeric(ev.get('x'), errors='coerce')
                        my = pd.to_numeric(ev.get('y'), errors='coerce')
                        if pd.notna(mx) and pd.notna(my):
                            mid_pts.append((float(mx), float(my)))
                pts = [(float(pe_x), float(pe_y))] + mid_pts + [(float(sx), float(sy))]
                carry_lines.append({'points': pts, 'is_goal': shot_row['event_type'] == 'Goal'})

        shooter_counts = shots['player_name'].dropna().value_counts().head(5).reset_index()
        shooter_counts.columns = ['Player', 'S']
        goal_counts = goals['player_name'].dropna().value_counts()
        shooter_counts['G'] = (
            shooter_counts['Player'].map(goal_counts).fillna(0).astype(int)
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
            'carry_lines':  carry_lines,
        }
    return out


def _shot_map_fig(shots: pd.DataFrame, key_passes: pd.DataFrame,
                  team_color: str, team_name: str,
                  carry_lines: list | None = None) -> go.Figure:
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
                clr     = GOLD if is_goal else 'rgba(220,220,220,0.55)'
                width   = 3.0  if is_goal else 2.0
                opacity = 0.95 if is_goal else 0.65
                label   = 'Goal Assist' if is_goal else 'Key Pass'
                xs_l, ys_l = [], []
                for _, row in grp.iterrows():
                    xs_l.extend([100 - float(row['y']), 100 - float(row['Pass End Y']), None])
                    ys_l.extend([float(row['x']),       float(row['Pass End X']),        None])
                fig.add_trace(go.Scatter(
                    x=xs_l, y=ys_l, mode='lines',
                    line=dict(color=clr, width=width),
                    opacity=opacity, showlegend=False, hoverinfo='skip',
                ))
                fig.add_trace(go.Scatter(
                    x=(100 - grp['Pass End Y']).tolist(),
                    y=grp['Pass End X'].tolist(),
                    mode='markers', name=label,
                    marker=dict(color=clr, size=9 if is_goal else 7,
                                symbol='circle', opacity=opacity,
                                line=dict(color='white', width=1.5 if is_goal else 1)),
                    showlegend=True, hoverinfo='skip',
                ))

    if carry_lines:
        _legend_added: dict = {'goal': False, 'other': False}
        for cl in carry_lines:
            is_goal = cl['is_goal']
            clr     = GOLD if is_goal else 'rgba(220,220,220,0.55)'
            opacity = 0.85 if is_goal else 0.55
            pts     = cl['points']
            fig_xs  = [100 - p[1] for p in pts]
            fig_ys  = [p[0]       for p in pts]
            key_    = 'goal' if is_goal else 'other'
            show_lg = not _legend_added[key_]
            fig.add_trace(go.Scatter(
                x=fig_xs, y=fig_ys, mode='lines',
                line=dict(color=clr, width=2, dash='dot'),
                opacity=opacity,
                name=('Carry (goal)' if is_goal else 'Carry') if show_lg else '',
                showlegend=show_lg, hoverinfo='skip',
            ))
            _legend_added[key_] = True

    for outcome, group in shots.groupby('event_type'):
        valid    = group[group['x'].notna() & group['y'].notna()].copy()
        fig_x    = (100 - valid['y']).tolist()
        fig_y    = valid['x'].tolist()
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
        xg_vals = (valid['xg'].fillna(0).tolist() if 'xg' in valid.columns else [0] * len(valid))
        if outcome == 'Goal':
            sizes = [16] * len(valid)
        else:
            sizes = [max(8, min(18, int(v * 60 + 8))) for v in xg_vals]
        fig.add_trace(go.Scatter(
            x=fig_x, y=fig_y, mode='markers', name=outcome,
            marker=dict(color=_OUTCOME_COLOR.get(outcome, team_color),
                        symbol=_OUTCOME_SYMBOL.get(outcome, 'circle'),
                        size=sizes, opacity=0.88, line=dict(color='white', width=1)),
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
            x=0.01, y=0.01, xanchor='left', yanchor='bottom', orientation='v',
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
            'textTransform': 'none' if col.startswith('x') else 'uppercase',
            'letterSpacing': '0' if col.startswith('x') else '0.04em',
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


def build_attacking_output_tab(events: pd.DataFrame, **_) -> html.Div:
    if events.empty:
        return html.P("No event data.", style={"color": COLORS["text_secondary"]})

    _shot_mask = events['event_type'].isin(SHOT_TYPES)
    if 'xg' not in events.columns and _shot_mask.any():
        events = events.copy()
        _shots_enriched = add_xg_column(events.loc[_shot_mask].copy())
        if 'xg' in _shots_enriched.columns:
            events.loc[_shot_mask, 'xg'] = _shots_enriched['xg'].values

    d = _compute(events)
    hs, as_ = d['home'], d['away']

    def _shooter_card(data, color):
        return html.Div([
            html.Div('Top Performers', style={
                'color': color, 'fontWeight': '700', 'fontSize': '0.78rem',
                'textTransform': 'uppercase', 'letterSpacing': '0.04em',
                'marginBottom': '8px',
            }),
            _player_table(data['top_shooters'], color),
        ])

    def _team_block(data, color):
        return dbc.Col(dbc.Row([
            dbc.Col(dcc.Graph(
                figure=_shot_map_fig(data['shots'], data.get('key_passes', pd.DataFrame()),
                                     color, data['team'], data.get('carry_lines', [])),
                config=CHART_CONFIG), md=9),
            dbc.Col(_shooter_card(data, color), md=3,
                    style={'overflowY': 'auto', 'maxHeight': '500px'}),
        ], className='g-2', align='start'), md=6, className='mb-3')

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
            _team_block(hs, HOME_COLOR),
            _team_block(as_, AWAY_COLOR),
        ], className='g-3'),
    ], style={'marginBottom': '36px'})

    return html.Div([shot_map_section], style={'marginTop': '16px'})


_ATK_RADAR_KEYS = [
    ('Goals',           'goals'),
    ('Shots',           'shots'),
    ('Shots on Target', 'shots_on_target'),
    ('xG',              'xg'),
    ('Assists',         'assists'),
    ('Shots from Box',  'box_shots'),
    ('Crosses',         'crosses'),
]

_atk_league_avg_cache: dict = {}


def _compute_atk_league_avg(events: pd.DataFrame) -> dict:
    global _atk_league_avg_cache

    competition = ''
    if 'competition' in events.columns and not events.empty:
        competition = str(events['competition'].iloc[0])
    if not competition:
        try:
            competition = get_match_metadata(events).get('competition', '')
        except Exception:
            pass
    if not competition:
        return {}
    if competition in _atk_league_avg_cache:
        return _atk_league_avg_cache[competition]

    try:
        keys = [k for _, k in _ATK_RADAR_KEYS]
        accumulated: dict = {k: [] for k in keys}
        for r in get_match_results():
            if r.get('competition') != competition:
                continue
            try:
                ev = get_match_events(r['match_id'])
                if ev.empty:
                    continue
                for pos in ('home', 'away'):
                    s = compute_team_kpis(ev, pos)
                    for k in keys:
                        v = s.get(k, 0)
                        if isinstance(v, (int, float)) and not math.isnan(float(v)):
                            accumulated[k].append(float(v))
            except Exception:
                continue
        avg = {k: round(sum(v) / len(v), 2) if v else 0.0 for k, v in accumulated.items()}
        _atk_league_avg_cache[competition] = avg
        return avg
    except Exception:
        return {}


def _hex_to_rgba_atk(hex_color: str, alpha: float = 0.12) -> str:
    h = hex_color.lstrip('#')
    if len(h) == 3:
        h = ''.join(c * 2 for c in h)
    try:
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        return f'rgba({r},{g},{b},{alpha})'
    except (ValueError, IndexError):
        return f'rgba(128,128,128,{alpha})'


def _build_atk_radar_fig(home_stats, away_stats, league_avg, home_team, away_team):
    labels = [lbl for lbl, _ in _ATK_RADAR_KEYS]
    keys   = [k   for _,   k in _ATK_RADAR_KEYS]

    def _raw(stats):
        return [float(stats.get(k, 0) or 0) for k in keys]

    hv = _raw(home_stats); av = _raw(away_stats)
    lv = _raw(league_avg) if league_avg else None
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
    hv_c = hv + [hv[0]]; av_c = av + [av[0]]
    if lv:
        norm_l_c = norm_l + [norm_l[0]]; lv_c = lv + [lv[0]]

    def _fmt(v):
        return f'{v:.2f}' if isinstance(v, float) and v != int(v) else str(int(v))

    fig = go.Figure()
    if lv:
        fig.add_trace(go.Scatterpolar(
            r=norm_l_c, theta=labels_c, mode='lines', name='League Avg',
            line=dict(color=GOLD, width=1.5, dash='dot'), opacity=0.85,
            customdata=[[_fmt(lv_c[i])] for i in range(len(labels_c))],
            hovertemplate='<b>League Avg</b><br>%{theta}: %{customdata[0]}<extra></extra>',
        ))
    fig.add_trace(go.Scatterpolar(
        r=norm_a_c, theta=labels_c, mode='lines+markers+text', name=away_team,
        fill='toself', fillcolor=_hex_to_rgba_atk(AWAY_COLOR, 0.12),
        line=dict(color=AWAY_COLOR, width=2), marker=dict(size=5, color=AWAY_COLOR),
        text=[_fmt(av_c[i]) for i in range(len(labels_c))],
        textposition='bottom center', textfont=dict(size=10, color='#FFFFFF'),
        customdata=[[_fmt(av_c[i])] for i in range(len(labels_c))],
        hovertemplate=f'<b>{away_team}</b><br>%{{theta}}: %{{customdata[0]}}<extra></extra>',
    ))
    fig.add_trace(go.Scatterpolar(
        r=norm_h_c, theta=labels_c, mode='lines+markers+text', name=home_team,
        fill='toself', fillcolor=_hex_to_rgba_atk(HOME_COLOR, 0.12),
        line=dict(color=HOME_COLOR, width=2), marker=dict(size=5, color=HOME_COLOR),
        text=[_fmt(hv_c[i]) for i in range(len(labels_c))],
        textposition='top center', textfont=dict(size=10, color='#FFFFFF'),
        customdata=[[_fmt(hv_c[i])] for i in range(len(labels_c))],
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


def build_attack_radar(events: pd.DataFrame):
    if events.empty:
        return None
    home_team  = str(events['home_team'].iloc[0]) if 'home_team' in events.columns else 'Home'
    away_team  = str(events['away_team'].iloc[0]) if 'away_team' in events.columns else 'Away'
    home_stats = compute_team_kpis(events, 'home')
    away_stats = compute_team_kpis(events, 'away')
    league_avg = _compute_atk_league_avg(events)
    return _build_atk_radar_fig(home_stats, away_stats, league_avg, home_team, away_team)


def register_attacking_output_callbacks(app) -> None:
    pass
