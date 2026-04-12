"""
CuléVision - Player Analysis Page
Individual Barcelona player profile with performance evaluation radar,
season statistics, and event pitch maps.
Fixed to 2025-2026 season.
"""

import re
from pathlib import Path

from dash import html, dcc, Input, Output
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
from utils.config import COLORS
from utils.data_utils import (
    get_all_barcelona_players,
    get_player_stats,
    get_player_match_stats,
    get_player_events,
    get_all_events,
    get_match_results,
    filter_own_goals,
    exclude_own_goals,
    CURRENT_SEASON,
)
from utils.player_analysis import (
    compute_player_stats,
    compute_5d_scores,
)
from pages.match_analysis_tabs.shared import (
    section_card,
    section_header,
    page_header,
)
from page_utils.visualizations import (
    CHART_LAYOUT_DEFAULTS,
    CHART_CONFIG,
    add_pitch_background,
    PITCH_AXIS_HALF,
    PITCH_AXIS_FULL,
    empty_fig,
    render_lsc_heatmap_img,
    GOLD,
    HOME_COLOR,
    AWAY_COLOR,
    build_radar_fig,
    build_metric_explanation_card,
)
from page_utils.competitions import ALL_COMPETITIONS as _ALL_COMPETITIONS, COMP_SHORT as _COMP_SHORT
from page_utils.event_filters import DEF_ACTION_TYPES as _DEF_ACTION_TYPES, DEF_COLORS as _DEF_COLORS
from page_utils.pitch_zones import is_in_penalty_box
from utils.xg_utils import add_xg_column


# ---------------------------------------------------------------------------
# Player image map  (jersey number → Dash asset path)
# ---------------------------------------------------------------------------

def _build_player_image_map() -> dict:
    players_dir = Path(__file__).parent.parent / 'assets' / 'players'
    result = {}
    if players_dir.exists():
        for f in players_dir.glob('*.webp'):
            m = re.match(r'^(\d+)-', f.name)
            if m:
                result[int(m.group(1))] = f'/assets/players/{f.name}'
    return result


_PLAYER_IMAGE_MAP = _build_player_image_map()
_PLACEHOLDER_IMG  = '/assets/logos/team/FC-Barcelona-v2002.svg'


# ---------------------------------------------------------------------------
# Competition / match label helpers
# ---------------------------------------------------------------------------

_ALL_COMPETITIONS = [{'label': 'All Competitions', 'value': 'all'}] + _ALL_COMPETITIONS

_MAP_PAIR_OPTIONS = [
    {'label': 'Heatmap + Shot Map',          'value': 'heatmap_shots'},
    {'label': 'Heatmap + Defensive Actions', 'value': 'heatmap_defence'},
]


# ---------------------------------------------------------------------------
# Role constants  (Opta position → simplified bucket)
# ---------------------------------------------------------------------------

_ROLE_MAP = {
    'GK':  'GK',
    'CB':  'CB', 'LCB': 'CB', 'RCB': 'CB',
    'RB':  'FB', 'LB':  'FB', 'RWB': 'FB', 'LWB': 'FB',
    'CDM': 'DM', 'DM':  'DM',
    'CM':  'CM', 'MC':  'CM', 'LCM': 'CM', 'RCM': 'CM',
    'CAM': 'AM', 'AM':  'AM', 'LAM': 'AM', 'RAM': 'AM',
    'RW':  'Winger', 'LW':  'Winger',
    'RM':  'Winger', 'LM':  'Winger',
    'CF':  'ST', 'ST':  'ST', 'SS':  'ST',
}

_ROLE_LABELS = {
    'GK':     'Goalkeeper',
    'CB':     'Centre Back',
    'FB':     'Full Back',
    'DM':     'Defensive Midfielder',
    'CM':     'Central Midfielder',
    'AM':     'Attacking Midfielder',
    'Winger': 'Winger',
    'ST':     'Striker',
}


# ---------------------------------------------------------------------------
# Profile card
# ---------------------------------------------------------------------------

def _extract_jersey_and_position(player_ev):
    jersey_num = None
    position   = None

    if 'Jersey Number' in player_ev.columns:
        vals = player_ev['Jersey Number'].dropna()
        vals = vals[~vals.isin(['N/A', ''])]
        if not vals.empty:
            try:
                jersey_num = int(float(vals.iloc[0]))
            except (ValueError, TypeError):
                pass

    if 'position' in player_ev.columns:
        positions = player_ev['position'].dropna()
        positions = positions[~positions.isin(['', 'N/A'])]
        if not positions.empty:
            position = positions.mode().iloc[0]

    return jersey_num, position


def _detail_row(label, value):
    return dbc.Row([
        dbc.Col(html.Small(label, style={'color': COLORS['text_secondary']}), width=5),
        dbc.Col(html.Small(value, style={'color': COLORS['text_primary'], 'fontWeight': '600'}), width=7),
    ], className='mb-2')


def _player_profile_card(player_name, jersey_num, position, stats=None):
    img_src       = _PLAYER_IMAGE_MAP.get(jersey_num, _PLACEHOLDER_IMG)
    jersey_text   = f'#{jersey_num}' if jersey_num else '—'
    position_text = position if position else '—'
    stats         = stats or {}
    _DIV = f'1px solid {COLORS["dark_border"]}'

    col_image = dbc.Col([
        html.Img(src=img_src, style={
            'width': '100%', 'maxWidth': '280px',
            'borderRadius': '10px', 'display': 'block', 'margin': '0 auto',
            'boxShadow': '0 8px 28px rgba(0,0,0,0.55)',
        }),
    ], md=4, className='d-flex align-items-center justify-content-center py-2')

    col_profile = dbc.Col([
        html.Div([
            html.H4(player_name, style={'color': GOLD, 'marginBottom': '2px',
                                        'fontWeight': 700, 'fontSize': '1.25rem'}),
            html.P('FC Barcelona', style={'color': COLORS['text_secondary'],
                                          'marginBottom': '16px', 'fontSize': '0.82rem',
                                          'letterSpacing': '0.4px'}),
            html.Div([
                html.Span(jersey_text, style={
                    'backgroundColor': GOLD, 'color': '#000',
                    'borderRadius': '4px', 'padding': '2px 9px',
                    'fontSize': '0.78rem', 'fontWeight': 700, 'marginRight': '6px',
                }),
                html.Span(position_text, style={'color': COLORS['text_secondary'], 'fontSize': '0.82rem'}),
            ], className='mb-4'),
            _detail_row('Club',   'FC Barcelona'),
            _detail_row('Season', '2025 – 2026'),
        ], style={'borderLeft': _DIV, 'paddingLeft': '24px', 'height': '100%'}),
    ], md=3, className='py-2')

    stat_items = [
        ('appearances', 'Apps'), ('goals', 'Goals'), ('shots', 'Shots'),
        ('tackles', 'Tackles'), ('interceptions', 'Interceptions'), ('pass_acc', 'Pass Acc'),
    ]

    def _stat_box(key, label):
        if key == 'pass_acc':
            raw = stats.get(key)
            val = f"{raw}%" if raw is not None else '—'
        else:
            val = str(stats.get(key, '—'))
        hi = key == 'goals'
        return html.Div([
            html.Div(val, style={
                'fontSize': '1.55rem', 'fontWeight': 700, 'lineHeight': '1',
                'color': GOLD if hi else COLORS['text_primary'],
            }),
            html.Div(label, style={
                'fontSize': '0.6rem', 'color': COLORS['text_secondary'],
                'marginTop': '5px', 'textTransform': 'uppercase', 'letterSpacing': '0.5px',
            }),
        ], style={
            'textAlign': 'center', 'padding': '12px 6px',
            'backgroundColor': 'rgba(0,0,0,0.25)', 'borderRadius': '6px', 'border': _DIV,
        })

    col_stats = dbc.Col([
        html.Div([
            html.Small('Season Statistics', style={
                'color': GOLD, 'fontWeight': 600, 'display': 'block',
                'marginBottom': '12px', 'textTransform': 'uppercase',
                'letterSpacing': '0.6px', 'fontSize': '0.7rem',
            }),
            html.Div(
                [_stat_box(k, l) for k, l in stat_items],
                style={'display': 'grid', 'gridTemplateColumns': 'repeat(3, 1fr)', 'gap': '8px'},
            ),
        ], style={'borderLeft': _DIV, 'paddingLeft': '24px', 'height': '100%'}),
    ], md=5, className='py-2')

    return dbc.Card([
        dbc.CardBody([
            dbc.Row([col_image, col_profile, col_stats], align='center', className='g-0'),
        ], style={'padding': '1.25rem 1.5rem'})
    ], style={
        'backgroundColor': COLORS['dark_secondary'],
        'border': f'1px solid {COLORS["dark_border"]}',
        'borderTop': f'3px solid {GOLD}',
        'borderRadius': '8px',
        'overflow': 'hidden',
    })


# ---------------------------------------------------------------------------
# Match selector helper
# ---------------------------------------------------------------------------

def _build_match_options(player_name, competition):
    match_stats = get_player_match_stats(player_name, CURRENT_SEASON)
    if competition and competition != 'all':
        match_stats = [m for m in match_stats if m.get('competition') == competition]

    results_map = {r['match_id']: r for r in get_match_results()}
    options     = []
    for m in match_stats:
        mid      = m['match_id']
        r        = results_map.get(mid, {})
        opponent = r.get('opponent', str(m.get('description', mid))[:20])
        res      = r.get('result', '')
        date     = str(m.get('date', ''))[:10]
        comp     = m.get('competition', '')
        comp_tag = _COMP_SHORT.get(comp, comp[:4])
        label    = f"{date}  {opponent}  ({res})" + (f"  · {comp_tag}" if competition == 'all' else '')
        options.append({'label': label, 'value': mid})
    return options


# ---------------------------------------------------------------------------
# Performance section
# ---------------------------------------------------------------------------

def _build_performance_section(
    player_name: str,
    d5: dict,
    n_peers: int,
    role: str,
    role_label_override: str | None = None,
) -> html.Div:
    """5-axis radar + dimension guide side-by-side."""
    role_label = role_label_override if role_label_override else _ROLE_LABELS.get(role, role)
    radar_fig  = build_radar_fig(player_name, d5, n_peers)

    return html.Div([
        section_header(
            'Performance Evaluation',
            subtitle=f'{role_label} · percentile rank vs {n_peers} positional peers',
        ),
        dbc.Row([
            dbc.Col(dcc.Graph(figure=radar_fig, config=CHART_CONFIG), md=7),
            dbc.Col(build_metric_explanation_card(n_peers, role_label), md=5),
        ], className='mb-4 g-3'),
    ])


# ---------------------------------------------------------------------------
# Visual helpers shared by section builders
# ---------------------------------------------------------------------------

def _bar_row(label, value, max_val, color=HOME_COLOR):
    """Label + value + horizontal fill bar."""
    pct = min(value / max(max_val, 1) * 100, 100)
    return html.Div([
        html.Div([
            html.Span(label, style={'color': COLORS['text_secondary'], 'fontSize': '0.78rem'}),
            html.Span(str(value), style={
                'color': COLORS['text_primary'], 'fontSize': '0.78rem', 'fontWeight': 600,
            }),
        ], style={'display': 'flex', 'justifyContent': 'space-between', 'marginBottom': '3px'}),
        html.Div(
            html.Div(style={
                'width': f'{pct:.1f}%', 'height': '100%',
                'backgroundColor': color, 'borderRadius': '2px',
            }),
            style={
                'height': '6px', 'backgroundColor': COLORS['dark_border'],
                'borderRadius': '2px', 'marginBottom': '8px',
            },
        ),
    ])


def _sub_label(text):
    return html.Small(text, style={
        'color': GOLD, 'fontWeight': 600, 'display': 'block',
        'textTransform': 'uppercase', 'letterSpacing': '0.5px',
        'fontSize': '0.65rem', 'marginBottom': '6px',
    })


# ---------------------------------------------------------------------------
# KPI strip
# ---------------------------------------------------------------------------

def _kpi_card(label, value_str, bar_pct, color=GOLD):
    pct = min(max(bar_pct, 0.0), 100.0)
    return dbc.Col(html.Div([
        html.Div(value_str, style={
            'fontSize': '1.7rem', 'fontWeight': 800, 'lineHeight': '1',
            'color': color,
        }),
        html.Div(label, style={
            'fontSize': '0.62rem', 'color': COLORS['text_secondary'],
            'textTransform': 'uppercase', 'letterSpacing': '0.5px',
            'marginTop': '4px',
        }),
        html.Div(
            html.Div(style={
                'width': f'{pct:.1f}%', 'height': '100%',
                'backgroundColor': color, 'borderRadius': '1px',
            }),
            style={
                'height': '3px', 'borderRadius': '1px',
                'backgroundColor': COLORS['dark_border'], 'marginTop': '10px',
            },
        ),
    ], style={
        'textAlign': 'center', 'padding': '16px 10px',
        'backgroundColor': COLORS['dark_secondary'],
        'border': f'1px solid {COLORS["dark_border"]}',
        'borderTop': f'2px solid {color}',
        'borderRadius': '6px', 'height': '100%',
    }), xs=6, sm=4, md=2)


def build_kpi_strip(goals, assists, xg_diff, key_passes, takeon_succ, duels_won_pct):
    xg_color = '#51cf66' if xg_diff >= 0 else AWAY_COLOR
    xg_str   = ('+' if xg_diff >= 0 else '') + f'{xg_diff:.2f}'
    xg_pct   = min(abs(xg_diff) / 5 * 100, 100)
    return dbc.Row([
        _kpi_card('Goals',          str(goals),          min(goals / 30 * 100, 100), GOLD),
        _kpi_card('Assists',        str(assists),        min(assists / 20 * 100, 100), '#51cf66'),
        _kpi_card('xG Diff',        xg_str,             xg_pct, xg_color),
        _kpi_card('Key Passes',     str(key_passes),    min(key_passes / 60 * 100, 100), '#339af0'),
        _kpi_card('Succ. Dribbles', str(takeon_succ),   min(takeon_succ / 50 * 100, 100), '#ffd43b'),
        _kpi_card('Duels Won',      f'{duels_won_pct}%', duels_won_pct, AWAY_COLOR),
    ], className='g-3 mb-4', align='stretch')


# ---------------------------------------------------------------------------
# Finishing section
# ---------------------------------------------------------------------------

def build_finishing_section(ps_goals, xg_total, ps_shots, shots_on_target, shot_ev):
    shot_acc = round(shots_on_target / max(ps_shots, 1) * 100, 1)

    # Goals vs xG horizontal bar
    fig_gx = go.Figure()
    fig_gx.add_trace(go.Bar(
        y=['xG'],
        x=[round(xg_total, 2)],
        orientation='h',
        name='xG',
        marker_color=HOME_COLOR,
        opacity=0.85,
        text=[f'{xg_total:.2f}'],
        textposition='outside',
    ))
    fig_gx.add_trace(go.Bar(
        y=['Goals'],
        x=[ps_goals],
        orientation='h',
        name='Goals',
        marker_color=GOLD,
        text=[str(ps_goals)],
        textposition='outside',
    ))
    x_max = max(ps_goals, xg_total, 1) * 1.3
    fig_gx.update_layout(**CHART_LAYOUT_DEFAULTS)
    fig_gx.update_layout(
        height=130,
        margin=dict(l=0, r=40, t=8, b=8),
        showlegend=False,
        barmode='group',
        xaxis=dict(
            range=[0, x_max], showgrid=False, zeroline=False,
            showticklabels=False, color=COLORS['text_secondary'],
        ),
        yaxis=dict(showgrid=False, color=COLORS['text_secondary'], tickfont=dict(size=11)),
    )

    # Shot accuracy bar
    acc_bar = html.Div([
        _sub_label('Shot Accuracy'),
        html.Div([
            html.Span(f'{shot_acc}%', style={
                'color': COLORS['text_primary'], 'fontWeight': 700, 'fontSize': '1.1rem',
            }),
            html.Span(f'  ({shots_on_target} on target / {ps_shots} shots)', style={
                'color': COLORS['text_secondary'], 'fontSize': '0.75rem',
            }),
        ], style={'marginBottom': '6px'}),
        html.Div(
            html.Div(style={
                'width': f'{shot_acc:.1f}%', 'height': '100%',
                'backgroundColor': '#51cf66', 'borderRadius': '2px',
            }),
            style={'height': '8px', 'backgroundColor': COLORS['dark_border'], 'borderRadius': '2px'},
        ),
    ], style={'marginTop': '14px'})

    # Location + body-part breakdown
    inside_box = outside_box = 0
    right_shots = left_shots = head_shots = 0
    if shot_ev is not None and not shot_ev.empty and 'x' in shot_ev.columns and 'y' in shot_ev.columns:
        mask_box   = shot_ev.apply(lambda r: is_in_penalty_box(r['x'], r['y']), axis=1)
        inside_box  = int(mask_box.sum())
        outside_box = len(shot_ev) - inside_box
        if 'Right footed' in shot_ev.columns:
            right_shots = int(shot_ev['Right footed'].notna().sum())
        if 'Left footed' in shot_ev.columns:
            left_shots  = int(shot_ev['Left footed'].notna().sum())
        if 'Head' in shot_ev.columns:
            head_shots  = int(shot_ev['Head'].notna().sum())

    box_max  = max(inside_box, outside_box, 1)
    foot_max = max(right_shots, left_shots, head_shots, 1)

    breakdown = html.Div([
        _sub_label('Shot Location'),
        _bar_row('Inside Box',  inside_box,  box_max, GOLD),
        _bar_row('Outside Box', outside_box, box_max, HOME_COLOR),
        html.Div(style={'marginTop': '10px'}),
        _sub_label('Body Part'),
        _bar_row('Right Foot', right_shots, foot_max, '#339af0'),
        _bar_row('Left Foot',  left_shots,  foot_max, '#74c0fc'),
        _bar_row('Header',     head_shots,  foot_max, '#cc5de8'),
    ])

    return section_card('Finishing', dbc.Row([
        dbc.Col([
            _sub_label('Goals vs xG'),
            dcc.Graph(figure=fig_gx, config=CHART_CONFIG),
            acc_bar,
        ], md=5),
        dbc.Col(breakdown, md=7),
    ], className='g-3'))


# ---------------------------------------------------------------------------
# Passing & creativity section
# ---------------------------------------------------------------------------

def build_passing_section(pass_rows, n_passes, pass_acc, key_passes, assists):
    # KPI row
    def _inline_kpi(label, val, color=GOLD):
        return html.Div([
            html.Div(str(val), style={
                'fontSize': '1.5rem', 'fontWeight': 800, 'color': color, 'lineHeight': '1',
            }),
            html.Div(label, style={
                'fontSize': '0.6rem', 'color': COLORS['text_secondary'],
                'textTransform': 'uppercase', 'letterSpacing': '0.4px', 'marginTop': '3px',
            }),
        ], style={
            'textAlign': 'center', 'padding': '10px 14px',
            'backgroundColor': 'rgba(0,0,0,0.2)',
            'border': f'1px solid {COLORS["dark_border"]}',
            'borderTop': f'2px solid {color}',
            'borderRadius': '6px',
        })

    kpi_row = html.Div([
        _inline_kpi('Key Passes', key_passes, '#339af0'),
        _inline_kpi('Assists',    assists,    '#51cf66'),
        _inline_kpi('Total Passes', n_passes, GOLD),
    ], style={'display': 'flex', 'gap': '10px', 'marginBottom': '18px'})

    # Accuracy bars
    own_h_rows   = pass_rows[pass_rows['x'] < 50]  if 'x' in pass_rows.columns else pass_rows.iloc[0:0]
    opp_h_rows   = pass_rows[pass_rows['x'] >= 50] if 'x' in pass_rows.columns else pass_rows.iloc[0:0]
    long_rows    = pass_rows[pass_rows['Long ball'].notna()]  if 'Long ball' in pass_rows.columns else pass_rows.iloc[0:0]
    cross_rows   = pass_rows[pass_rows['Cross'].notna()]      if 'Cross'     in pass_rows.columns else pass_rows.iloc[0:0]

    def _acc(rows):
        n = len(rows)
        if n == 0:
            return 0.0
        return round(rows['outcome'].eq(1).sum() / n * 100, 1)

    own_h_acc  = _acc(own_h_rows)
    opp_h_acc  = _acc(opp_h_rows)
    long_acc   = _acc(long_rows)
    cross_acc  = _acc(cross_rows)

    acc_bars = html.Div([
        _sub_label('Pass Accuracy by Zone'),
        _bar_row(f'Overall ({pass_acc}%)',          pass_acc, 100, GOLD),
        _bar_row(f'Own Half ({own_h_acc}%)',         own_h_acc,  100, '#339af0'),
        _bar_row(f'Opp. Half ({opp_h_acc}%)',        opp_h_acc,  100, '#74c0fc'),
        _bar_row(f'Long Balls ({long_acc}%)',        long_acc,   100, '#ffd43b'),
        _bar_row(f'Crosses ({cross_acc}%)',          cross_acc,  100, '#cc5de8'),
    ])

    return section_card('Passing & Creativity', html.Div([kpi_row, acc_bars]))


# ---------------------------------------------------------------------------
# Progression & possession section
# ---------------------------------------------------------------------------

def build_progression_section(takeon_att, takeon_succ, takeon_pct, player_ev):
    dispossessed = int(
        (player_ev['event_type'] == 'Dispossessed').sum()
    ) if not player_ev.empty else 0
    touches = int(
        player_ev[~player_ev['event_type'].isin(['Card', 'Offside Pass', 'Foul'])].shape[0]
    ) if not player_ev.empty else 0

    # Dribble grouped bars
    fig_dr = go.Figure()
    fig_dr.add_trace(go.Bar(
        name='Attempted',
        x=['Dribbles'],
        y=[takeon_att],
        marker_color=COLORS['dark_border'],
        width=0.35,
    ))
    fig_dr.add_trace(go.Bar(
        name='Successful',
        x=['Dribbles'],
        y=[takeon_succ],
        marker_color='#ffd43b',
        width=0.35,
    ))
    fig_dr.update_layout(**CHART_LAYOUT_DEFAULTS)
    fig_dr.update_layout(
        height=160,
        barmode='group',
        margin=dict(l=0, r=0, t=8, b=8),
        showlegend=True,
        legend=dict(
            orientation='h', y=1.25, x=0,
            font=dict(size=10, color=COLORS['text_secondary']),
            bgcolor='rgba(0,0,0,0)',
        ),
        xaxis=dict(showgrid=False, showticklabels=True, color=COLORS['text_secondary']),
        yaxis=dict(showgrid=False, zeroline=False, color=COLORS['text_secondary']),
    )

    poss_max = max(touches, dispossessed, 1)
    poss_bars = html.Div([
        _sub_label('Possession'),
        _bar_row('Total Touches',     touches,       poss_max, HOME_COLOR),
        _bar_row('Possession Lost',   dispossessed,  poss_max, AWAY_COLOR),
    ], style={'marginTop': '8px'})

    dribble_pct_bar = html.Div([
        _sub_label(f'Dribble Success  {takeon_pct}%'),
        html.Div(
            html.Div(style={
                'width': f'{takeon_pct:.1f}%', 'height': '100%',
                'backgroundColor': '#ffd43b', 'borderRadius': '2px',
            }),
            style={'height': '8px', 'backgroundColor': COLORS['dark_border'], 'borderRadius': '2px'},
        ),
    ], style={'marginTop': '10px'})

    return section_card('Progression & Possession', dbc.Row([
        dbc.Col([
            dcc.Graph(figure=fig_dr, config=CHART_CONFIG),
            dribble_pct_bar,
        ], md=5),
        dbc.Col(poss_bars, md=7),
    ], className='g-3'))


# ---------------------------------------------------------------------------
# Defensive section
# ---------------------------------------------------------------------------

def build_defensive_section(tackles, interceptions, recoveries, clearances,
                             aerial_won, aerial_att, aerial_pct):
    def_max = max(tackles, interceptions, recoveries, clearances, 1)
    return section_card('Defensive Work', html.Div([
        _bar_row('Tackles',         tackles,       def_max, '#51cf66'),
        _bar_row('Interceptions',   interceptions, def_max, '#51cf66'),
        _bar_row('Ball Recoveries', recoveries,    def_max, '#94d82d'),
        _bar_row('Clearances',      clearances,    def_max, '#a9e34b'),
        html.Div(style={'marginTop': '10px'}),
        _sub_label(f'Aerial Duels Won  {aerial_pct}%  ({aerial_won}/{aerial_att})'),
        html.Div(
            html.Div(style={
                'width': f'{aerial_pct:.1f}%', 'height': '100%',
                'backgroundColor': '#51cf66', 'borderRadius': '2px',
            }),
            style={'height': '8px', 'backgroundColor': COLORS['dark_border'], 'borderRadius': '2px'},
        ),
    ]))


# ---------------------------------------------------------------------------
# Trend chart
# ---------------------------------------------------------------------------

def build_trend_chart(match_stats):
    """Line chart of goals and shots per match over time."""
    import pandas as pd

    if not match_stats:
        return html.Div()

    df = pd.DataFrame(match_stats).sort_values('date').reset_index(drop=True)
    x_labels = [str(r['date'])[:10] for _, r in df.iterrows()]

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=x_labels,
        y=df['shots'].tolist(),
        name='Shots',
        mode='lines+markers',
        line=dict(color=HOME_COLOR, width=2),
        marker=dict(size=6),
    ))
    fig.add_trace(go.Scatter(
        x=x_labels,
        y=df['goals'].tolist(),
        name='Goals',
        mode='lines+markers',
        line=dict(color=GOLD, width=2, dash='dot'),
        marker=dict(size=7, symbol='star'),
    ))
    fig.update_layout(**CHART_LAYOUT_DEFAULTS)
    fig.update_layout(
        height=220,
        margin=dict(l=0, r=0, t=10, b=40),
        legend=dict(
            orientation='h', x=0, y=1.15,
            font=dict(size=11, color=COLORS['text_secondary']),
            bgcolor='rgba(0,0,0,0)',
        ),
        xaxis=dict(
            showgrid=False, tickangle=-45,
            tickfont=dict(size=9, color=COLORS['text_secondary']),
            color=COLORS['text_secondary'],
        ),
        yaxis=dict(
            showgrid=True,
            gridcolor=COLORS['dark_border'],
            zeroline=False,
            color=COLORS['text_secondary'],
            tickfont=dict(size=9),
        ),
    )
    return section_card(
        'Match Trend — Goals & Shots',
        dcc.Graph(figure=fig, config=CHART_CONFIG),
    )


# ---------------------------------------------------------------------------
# Layout
# ---------------------------------------------------------------------------

def create_player_analysis_layout():
    players        = get_all_barcelona_players(CURRENT_SEASON)
    player_options = [{'label': p, 'value': p} for p in players if p]

    _dd_style = {'backgroundColor': COLORS['dark_secondary']}
    _lbl      = {'color': COLORS['text_secondary'], 'fontSize': '0.85rem'}

    return dbc.Container([
        page_header('Barça DNA'),
        html.Hr(style={'borderColor': COLORS['dark_border']}),

        # ── Filters ──────────────────────────────────────────────────────
        dbc.Row([
            dbc.Col([
                html.Label('Player', style=_lbl),
                dcc.Dropdown(
                    id='pa-player-selector',
                    options=player_options,
                    value=player_options[0]['value'] if player_options else None,
                    clearable=False,
                    style=_dd_style,
                ),
            ], md=5),
        ], className='mb-4'),

        # ── Profile card (dynamic) ───────────────────────────────────────
        html.Div(id='pa-profile', className='mb-2'),

        # ── Competition + Match selectors ────────────────────────────────
        dbc.Row([
            dbc.Col([
                html.Label('Competition', style=_lbl),
                dcc.Dropdown(
                    id='pa-competition-selector',
                    options=_ALL_COMPETITIONS,
                    value='all',
                    clearable=False,
                    style=_dd_style,
                ),
            ], md=3),
            dbc.Col([
                html.Label('Match(es)', style=_lbl),
                dcc.Dropdown(
                    id='pa-match-selector',
                    options=[],
                    value=None,
                    multi=True,
                    clearable=True,
                    placeholder='All matches…',
                    style=_dd_style,
                ),
            ], md=7),
        ], className='mb-4'),

        # ── Radar + Season stats (dynamic) ───────────────────────────────
        dcc.Loading(
            id='pa-stats-loading',
            type='circle',
            color=COLORS['gold'],
            children=html.Div(id='pa-stats-section', className='mb-4'),
        ),

        # ── Pitch map pair selector ──────────────────────────────────────
        dbc.Row([
            dbc.Col([
                html.Label('Pitch Maps', style=_lbl),
                dcc.Dropdown(
                    id='pa-event-type-selector',
                    options=_MAP_PAIR_OPTIONS,
                    value='heatmap_shots',
                    clearable=False,
                    style=_dd_style,
                ),
            ], md=4),
        ], className='mb-4'),

        # ── Event map + Match log (dynamic) ──────────────────────────────
        dcc.Loading(
            id='pa-plots-loading',
            type='circle',
            color=COLORS['gold'],
            children=html.Div(id='pa-plots-log'),
        ),
    ], fluid=True, className='py-4')


# ---------------------------------------------------------------------------
# Callbacks
# ---------------------------------------------------------------------------

def register_player_analysis_callbacks(app):

    # ── Profile card ──────────────────────────────────────────────────────
    @app.callback(
        Output('pa-profile', 'children'),
        Input('pa-player-selector', 'value'),
    )
    def update_pa_profile(player_name):
        if not player_name:
            return html.Div()
        player_ev  = get_player_events(player_name, CURRENT_SEASON)
        jersey_num, position = _extract_jersey_and_position(player_ev)

        stats = {}
        if not player_ev.empty:
            stats['appearances'] = int(player_ev['match_id'].nunique())
            stats['goals']       = int(
                filter_own_goals(player_ev[player_ev['event_type'] == 'Goal']).shape[0]
            )
            stats['shots']       = int(
                player_ev[player_ev['event_type'].isin(['Miss', 'Saved Shot', 'Goal'])].shape[0]
            )
            stats['tackles']     = int(player_ev[player_ev['event_type'] == 'Tackle'].shape[0])
            stats['interceptions'] = int(
                player_ev[player_ev['event_type'] == 'Interception'].shape[0]
            )
            pass_rows = player_ev[player_ev['event_type'] == 'Pass']
            n_passes  = len(pass_rows)
            if n_passes > 0:
                stats['pass_acc'] = round(
                    pass_rows['outcome'].eq(1).sum() / n_passes * 100, 1
                )
        return _player_profile_card(player_name, jersey_num, position, stats)

    # ── Match selector options ────────────────────────────────────────────
    @app.callback(
        Output('pa-match-selector', 'options'),
        Output('pa-match-selector', 'value'),
        Input('pa-player-selector', 'value'),
        Input('pa-competition-selector', 'value'),
    )
    def update_pa_match_options(player_name, competition):
        if not player_name:
            return [], None
        return _build_match_options(player_name, competition), None

    # ── Performance radar + visual sections ──────────────────────────────
    @app.callback(
        Output('pa-stats-section', 'children'),
        Input('pa-player-selector', 'value'),
        Input('pa-competition-selector', 'value'),
        Input('pa-match-selector', 'value'),
    )
    def update_pa_stats(player_name, competition, selected_matches):
        if not player_name:
            return html.P('Select a player to view analysis.',
                          style={'color': COLORS['text_secondary']})

        import pandas as pd

        player_ev = get_player_events(
            player_name, CURRENT_SEASON,
            competition if competition != 'all' else None,
        )
        if selected_matches:
            player_ev = player_ev[player_ev['match_id'].isin(selected_matches)]

        all_stats  = get_player_stats(CURRENT_SEASON)
        player_row = all_stats[all_stats['player'] == player_name]
        if player_row.empty:
            return html.P('No data available for this player.',
                          style={'color': COLORS['text_secondary']})

        ps = player_row.iloc[0]
        if selected_matches or (competition and competition != 'all'):
            ps_goals = int(filter_own_goals(player_ev[player_ev['event_type'] == 'Goal']).shape[0])
            ps_shots = int(player_ev[player_ev['event_type'].isin(['Miss', 'Saved Shot', 'Goal'])].shape[0])
        else:
            ps_goals = int(ps['goals'])
            ps_shots = int(ps['shots'])

        pass_rows       = player_ev[player_ev['event_type'] == 'Pass']
        n_passes        = len(pass_rows)
        pass_acc        = round(pass_rows['outcome'].eq(1).sum() / max(n_passes, 1) * 100, 1)
        shots_on_target = len(player_ev[player_ev['event_type'].isin(['Saved Shot', 'Goal'])])

        assists    = int(pd.to_numeric(pass_rows['Assist'],    errors='coerce').eq(16).sum()) if 'Assist'    in pass_rows.columns else 0
        key_passes = int(pd.to_numeric(pass_rows['Key Pass'], errors='coerce').eq(1).sum())  if 'Key Pass' in pass_rows.columns else 0

        takeons      = player_ev[player_ev['event_type'] == 'Take On']
        takeon_att   = len(takeons)
        takeon_succ  = int(takeons['outcome'].eq(1).sum()) if 'outcome' in takeons.columns else 0
        takeon_pct   = round(takeon_succ / max(takeon_att, 1) * 100, 1)

        tackles       = len(player_ev[player_ev['event_type'] == 'Tackle'])
        interceptions = len(player_ev[player_ev['event_type'] == 'Interception'])
        recoveries    = len(player_ev[player_ev['event_type'] == 'Ball Recovery'])
        clearances    = len(player_ev[player_ev['event_type'] == 'Clearance'])

        aerials    = player_ev[player_ev['event_type'] == 'Aerial']
        aerial_att = len(aerials)
        aerial_won = int(aerials['outcome'].eq(1).sum()) if 'outcome' in aerials.columns else 0
        aerial_pct = round(aerial_won / max(aerial_att, 1) * 100, 1)

        # ── xG ────────────────────────────────────────────────────────────
        shot_ev_raw = exclude_own_goals(
            player_ev[player_ev['event_type'].isin(
                ['Miss', 'Saved Shot', 'Goal', 'Post', 'Blocked Shot']
            )].copy()
        ).dropna(subset=['x', 'y'])
        shot_ev_xg = add_xg_column(shot_ev_raw)
        xg_total = float(shot_ev_xg['xg'].sum()) if 'xg' in shot_ev_xg.columns else 0.0

        # ── Performance Evaluation radar ──────────────────────────────────
        perf_section = html.Div()

        bar_events_all = get_all_events(CURRENT_SEASON)
        if not bar_events_all.empty and 'team_code' in bar_events_all.columns:
            bar_events_all = bar_events_all[bar_events_all['team_code'] == 'BAR']

        if not bar_events_all.empty and 'position' in bar_events_all.columns:
            player_pos_series = (
                bar_events_all[bar_events_all['player_name'] == player_name]['position']
                .dropna()
            )
            player_pos_series = player_pos_series[~player_pos_series.isin(['', 'N/A'])]
            position_mode = player_pos_series.mode()
            opta_position = position_mode.iloc[0] if not position_mode.empty else None
            role = _ROLE_MAP.get(opta_position) if opta_position else None

            if role:
                clean_pos = bar_events_all.dropna(subset=['position', 'player_name'])
                clean_pos = clean_pos[~clean_pos['position'].isin(['', 'N/A'])]
                pos_by_player = (
                    clean_pos
                    .groupby('player_name')['position']
                    .agg(lambda s: s.mode().iloc[0] if not s.mode().empty else None)
                )
                peer_names = [
                    p for p, pos in pos_by_player.items()
                    if _ROLE_MAP.get(pos) == role and p != player_name
                ]
                full_squad_fallback = len(peer_names) == 0
                if full_squad_fallback:
                    peer_names = [p for p in pos_by_player.index if p != player_name]

                all_peer_stats = []
                for p in peer_names:
                    pe = bar_events_all[bar_events_all['player_name'] == p]
                    s  = compute_player_stats(pe)
                    if s:
                        all_peer_stats.append(s)

                cur_stats = compute_player_stats(
                    bar_events_all[bar_events_all['player_name'] == player_name]
                )

                if cur_stats and all_peer_stats:
                    d5 = compute_5d_scores(cur_stats, all_peer_stats, role)
                    role_label = _ROLE_LABELS.get(role, role)
                    if full_squad_fallback:
                        role_label += ' · vs full squad'
                    perf_section = _build_performance_section(
                        player_name, d5, len(all_peer_stats), role,
                        role_label_override=role_label,
                    )

        # ── Assemble dashboard sections ───────────────────────────────────
        left_col = html.Div([
            build_finishing_section(
                ps_goals, xg_total, ps_shots, shots_on_target, shot_ev_xg,
            ),
            html.Div(style={'marginTop': '20px'}),
            build_progression_section(takeon_att, takeon_succ, takeon_pct, player_ev),
        ])

        right_col = html.Div([
            build_passing_section(pass_rows, n_passes, pass_acc, key_passes, assists),
            html.Div(style={'marginTop': '20px'}),
            build_defensive_section(
                tackles, interceptions, recoveries, clearances,
                aerial_won, aerial_att, aerial_pct,
            ),
        ])

        return html.Div([
            perf_section,
            dbc.Row([
                dbc.Col(left_col,  md=6),
                dbc.Col(right_col, md=6),
            ], className='g-4'),
        ])

    # ── Pitch maps + trend + match log ───────────────────────────────────
    @app.callback(
        Output('pa-plots-log', 'children'),
        Input('pa-player-selector', 'value'),
        Input('pa-competition-selector', 'value'),
        Input('pa-match-selector', 'value'),
        Input('pa-event-type-selector', 'value'),
    )
    def update_pa_plots_log(player_name, competition, selected_matches, map_pair):
        if not player_name:
            return html.Div()

        player_ev = get_player_events(
            player_name, CURRENT_SEASON,
            competition if competition != 'all' else None,
        )
        if selected_matches:
            player_ev = player_ev[player_ev['match_id'].isin(selected_matches)]

        # ── Left map: always touch heatmap ────────────────────────────────
        touch = player_ev.dropna(subset=['x', 'y'])
        if not touch.empty:
            hm_img = render_lsc_heatmap_img(
                touch['x'].tolist(), touch['y'].tolist(),
                HOME_COLOR, show_zone_pcts=True,
            )
            left_map = section_card(
                'Touch Heatmap',
                html.Img(src=hm_img, style={'width': '100%', 'borderRadius': '4px'}),
            )
        else:
            left_map = section_card('Touch Heatmap', empty_fig('No touch data'))

        # ── Right map: driven by selector ─────────────────────────────────
        if map_pair == 'heatmap_shots':
            shot_ev = exclude_own_goals(
                player_ev[player_ev['event_type'].isin(
                    ['Miss', 'Saved Shot', 'Goal', 'Post', 'Blocked Shot']
                )].copy()
            ).dropna(subset=['x', 'y'])

            if not shot_ev.empty:
                color_map = {
                    'Goal':         GOLD,
                    'Saved Shot':   HOME_COLOR,
                    'Miss':         AWAY_COLOR,
                    'Post':         '#ffd43b',
                    'Blocked Shot': '#cc5de8',
                }
                fig_s = go.Figure()
                add_pitch_background(fig_s, half=True)
                for etype, clr in color_map.items():
                    sub = shot_ev[shot_ev['event_type'] == etype]
                    if sub.empty:
                        continue
                    fig_s.add_trace(go.Scatter(
                        x=sub['x'], y=sub['y'], mode='markers', name=etype,
                        marker=dict(color=clr, size=11, line=dict(color='white', width=1)),
                        text=sub['time_min'].astype(str) + "'",
                        hovertemplate='%{text}<extra>' + etype + '</extra>',
                    ))
                fig_s.update_layout(**CHART_LAYOUT_DEFAULTS, height=450, **PITCH_AXIS_HALF)
                right_map = section_card(
                    f'Shot Map  ({len(shot_ev)} shots)',
                    dcc.Graph(figure=fig_s, config=CHART_CONFIG),
                )
            else:
                right_map = section_card('Shot Map', empty_fig('No shots recorded'))

        else:  # heatmap_defence
            def_ev = player_ev[
                player_ev['event_type'].isin(_DEF_ACTION_TYPES)
            ].dropna(subset=['x', 'y'])

            fig_d = go.Figure()
            add_pitch_background(fig_d)
            for action_type, clr in _DEF_COLORS.items():
                sub = def_ev[def_ev['event_type'] == action_type]
                if sub.empty:
                    continue
                customdata = [
                    [r.get('player_name', ''), int(r.get('time_min', 0)), action_type]
                    for _, r in sub.iterrows()
                ]
                fig_d.add_trace(go.Scatter(
                    x=sub['x'].tolist(), y=sub['y'].tolist(),
                    mode='markers', name=action_type,
                    marker=dict(color=clr, size=9, opacity=0.80,
                                line=dict(color='rgba(0,0,0,0.3)', width=0.5)),
                    customdata=customdata,
                    hovertemplate=(
                        '<b>%{customdata[0]}</b><br>'
                        "Minute: %{customdata[1]}'<br>"
                        'Action: %{customdata[2]}'
                        '<extra></extra>'
                    ),
                ))
            fig_d.update_layout(**CHART_LAYOUT_DEFAULTS, height=450, **PITCH_AXIS_FULL)
            fig_d.update_layout(legend=dict(
                orientation='v', x=0.01, xanchor='left', y=0.99, yanchor='top',
                bgcolor='rgba(0,0,0,0.55)',
                font=dict(color=COLORS['text_primary'], size=9),
            ))
            right_map = section_card(
                f'Defensive Action Locations  ({len(def_ev)} events)',
                dcc.Graph(figure=fig_d, config=CHART_CONFIG),
            )

        maps_row = dbc.Row([
            dbc.Col(left_map,  md=6),
            dbc.Col(right_map, md=6),
        ], className='g-4 mb-4')

        # ── Trend chart ───────────────────────────────────────────────────
        match_stats = get_player_match_stats(player_name, CURRENT_SEASON)
        if competition and competition != 'all':
            match_stats = [m for m in match_stats if m.get('competition') == competition]
        if selected_matches:
            match_stats = [m for m in match_stats if m['match_id'] in set(selected_matches)]

        trend = build_trend_chart(match_stats)

        # ── Match log ─────────────────────────────────────────────────────
        if match_stats:
            _th = {'color': COLORS['text_secondary'], 'fontSize': '0.72rem',
                   'textTransform': 'uppercase', 'letterSpacing': '0.5px',
                   'fontWeight': 600, 'paddingBottom': '8px',
                   'borderBottom': f'1px solid {COLORS["dark_border"]}'}
            rows = []
            for m in match_stats:
                desc       = m['description']
                short_desc = (desc[:28] + '…') if len(desc) > 30 else desc
                g          = m['goals']
                s          = m['shots']
                goal_chip  = html.Span(str(g), style={
                    'backgroundColor': GOLD if g > 0 else 'transparent',
                    'color': '#000' if g > 0 else COLORS['text_secondary'],
                    'borderRadius': '4px',
                    'padding': '1px 7px' if g > 0 else '0',
                    'fontWeight': 700 if g > 0 else 400,
                    'fontSize': '0.82rem',
                })
                rows.append(html.Tr([
                    html.Td(str(m['date'])[:10],       style={'fontSize': '0.8rem', 'color': COLORS['text_secondary']}),
                    html.Td(m.get('competition', ''),  style={'fontSize': '0.8rem', 'color': COLORS['text_secondary']}),
                    html.Td(short_desc,                style={'fontSize': '0.82rem', 'color': COLORS['text_primary']}),
                    html.Td(goal_chip),
                    html.Td(str(m['passes']),           style={'fontSize': '0.82rem', 'textAlign': 'right'}),
                    html.Td(str(s),                     style={
                        'fontSize': '0.82rem', 'textAlign': 'right',
                        'color': HOME_COLOR if s >= 3 else COLORS['text_primary'],
                        'fontWeight': 600 if s >= 3 else 400,
                    }),
                    html.Td(str(m.get('tackles', 0)),   style={'fontSize': '0.82rem', 'textAlign': 'right'}),
                ], style={'borderBottom': f'1px solid {COLORS["dark_border"]}'}))

            match_log = section_card('Match Log', html.Table([
                html.Thead(html.Tr([
                    html.Th('Date',        style=_th),
                    html.Th('Competition', style=_th),
                    html.Th('Match',       style=_th),
                    html.Th('Goals',       style={**_th, 'textAlign': 'center'}),
                    html.Th('Passes',      style={**_th, 'textAlign': 'right'}),
                    html.Th('Shots',       style={**_th, 'textAlign': 'right'}),
                    html.Th('Tackles',     style={**_th, 'textAlign': 'right'}),
                ])),
                html.Tbody(rows),
            ], style={'width': '100%', 'borderCollapse': 'collapse'}))
        else:
            match_log = section_card(
                'Match Log',
                html.P('No matches found.', style={'color': COLORS['text_secondary']}),
            )

        return html.Div([maps_row, trend, html.Div(style={'marginTop': '20px'}), match_log])
