"""
CuléVision - Player Analysis Page
Individual Barcelona player profile with performance evaluation radar,
season statistics, and event pitch maps.
Fixed to 2025-2026 season.
"""

import re
from pathlib import Path

from dash import html, dcc
from dash.dependencies import Input, Output
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
    CHART_LAYOUT_DEFAULTS,
    CHART_CONFIG,
    add_pitch_background,
    PITCH_AXIS_HALF,
    PITCH_AXIS_FULL,
    section_card,
    section_header,
    empty_fig,
    page_header,
    render_lsc_heatmap_img,
    GOLD,
    HOME_COLOR,
    AWAY_COLOR,
)


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

_ALL_COMPETITIONS = [
    {'label': 'All Competitions', 'value': 'all'},
    {'label': 'La Liga',          'value': 'La Liga'},
    {'label': 'Champions League', 'value': 'Champions League'},
    {'label': 'Copa del Rey',     'value': 'Copa del Rey'},
    {'label': 'Spanish Super Cup','value': 'Spanish Super Cup'},
]

_COMP_SHORT = {
    'La Liga':           'Liga',
    'Champions League':  'UCL',
    'Copa del Rey':      'Copa',
    'Spanish Super Cup': 'SC',
}

# Four event maps shown in the dropdown
_EVENT_TYPE_OPTIONS = [
    {'label': 'Touch Heatmap',              'value': 'Touch Heatmap'},
    {'label': 'Shot Map',                   'value': 'Shot Map'},
    {'label': 'Defensive Actions Heatmap',  'value': 'Defensive Actions Heatmap'},
    {'label': 'Defensive Action Locations', 'value': 'Defensive Action Locations'},
]

# Defensive event type → dot colour (matches defensive_structure.py)
_DEF_ACTION_TYPES = {'Tackle', 'Interception', 'Ball Recovery', 'Clearance', 'Blocked Shot'}
_DEF_COLORS = {
    'Tackle':        '#4dabf7',
    'Interception':  '#51cf66',
    'Ball Recovery': '#ffd43b',
    'Clearance':     '#ff922b',
    'Blocked Shot':  '#cc5de8',
}


# ---------------------------------------------------------------------------
# Role constants  (Opta position → simplified bucket)
# ---------------------------------------------------------------------------

_ROLE_MAP = {
    # Goalkeepers
    'GK':  'GK',
    # Centre backs
    'CB':  'CB', 'LCB': 'CB', 'RCB': 'CB',
    # Full backs / wing backs
    'RB':  'FB', 'LB':  'FB', 'RWB': 'FB', 'LWB': 'FB',
    # Defensive mids
    'CDM': 'DM', 'DM':  'DM',
    # Central mids
    'CM':  'CM', 'MC':  'CM', 'LCM': 'CM', 'RCM': 'CM',
    # Attacking mids
    'CAM': 'AM', 'AM':  'AM', 'LAM': 'AM', 'RAM': 'AM',
    # Wingers / wide mids
    'RW':  'Winger', 'LW':  'Winger',
    'RM':  'Winger', 'LM':  'Winger',
    # Strikers / forwards
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
# 5-Dimension radar definitions (Attack / Defense / Technical / Physical / Overall)
# ---------------------------------------------------------------------------

_5D_KEYS   = ['attack', 'defense', 'technical', 'physical', 'overall']
_5D_LABELS = ['Attack', 'Defense', 'Technical', 'Physical', 'Overall']

_5D_INFO: dict[str, tuple[str, str]] = {
    'Attack':    (
        'Scoring & Creativity',
        'Goals, shots, shot accuracy, assists and key passes — '
        'weighted by position-specific importance',
    ),
    'Defense':   (
        'Defensive Contribution',
        'Tackles, interceptions, recoveries, clearances and aerial win rate — '
        'weighted by position-specific importance',
    ),
    'Technical': (
        'Technical Quality',
        'Pass accuracy, dribble success rate, key passes and shot on target — '
        'equal weight across positions',
    ),
    'Physical':  (
        'Physical Duels',
        'Aerial duel win rate and defensive duel frequency — '
        'proxy for dominance in physical contests',
    ),
    'Overall':   (
        'Composite Score',
        'Simple average of Attack, Defense, Technical and Physical percentile scores',
    ),
}

_5D_COLORS: dict[str, str] = {
    'Attack':    GOLD,
    'Defense':   AWAY_COLOR,
    'Technical': HOME_COLOR,
    'Physical':  '#51cf66',
    'Overall':   COLORS['text_primary'],
}




# ---------------------------------------------------------------------------
# Profile card helpers
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
        dbc.Col(html.Small(value, style={'color': COLORS['text_primary'],
                                         'fontWeight': '600'}), width=7),
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
        ('appearances',   'Apps'),
        ('goals',         'Goals'),
        ('shots',         'Shots'),
        ('tackles',       'Tackles'),
        ('interceptions', 'Interceptions'),
        ('pass_acc',      'Pass Acc'),
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
# Performance Evaluation radar builders
# ---------------------------------------------------------------------------

def _build_radar_fig(player_name: str, d5: dict, n_peers: int) -> go.Figure:
    """Build a 5-axis Plotly polar radar from 5-dimension percentile scores."""
    r_player = [d5.get(k, 50) for k in _5D_KEYS]
    r_avg    = [50] * len(_5D_LABELS)

    fig = go.Figure()

    # Average reference ring (dashed Barça blue)
    fig.add_trace(go.Scatterpolar(
        r=r_avg + [r_avg[0]],
        theta=_5D_LABELS + [_5D_LABELS[0]],
        mode='lines',
        name=f'Positional Average ({n_peers} peers)',
        line=dict(color=HOME_COLOR, width=2, dash='dot'),
        fill='toself',
        fillcolor='rgba(0, 77, 152, 0.12)',
        hoverinfo='skip',
    ))

    # Player filled area (gold)
    fig.add_trace(go.Scatterpolar(
        r=r_player + [r_player[0]],
        theta=_5D_LABELS + [_5D_LABELS[0]],
        mode='lines+markers',
        name=player_name,
        line=dict(color=GOLD, width=2.5),
        fill='toself',
        fillcolor='rgba(237, 187, 0, 0.22)',
        marker=dict(color=GOLD, size=8, line=dict(color='white', width=1)),
        hovertemplate='<b>%{theta}</b><br>Percentile: <b>%{r}</b><extra></extra>',
    ))

    fig.update_layout(
        polar=dict(
            bgcolor='rgba(0,0,0,0)',
            radialaxis=dict(
                range=[0, 100],
                visible=True,
                tickvals=[25, 50, 75, 100],
                tickfont=dict(size=9, color=COLORS['text_secondary']),
                gridcolor=COLORS['dark_border'],
                linecolor=COLORS['dark_border'],
                tickangle=0,
            ),
            angularaxis=dict(
                tickfont=dict(size=13, color=COLORS['text_primary']),
                gridcolor=COLORS['dark_border'],
                linecolor=COLORS['dark_border'],
            ),
        ),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font=dict(color=COLORS['text_primary'], size=12),
        showlegend=True,
        legend=dict(
            font=dict(color=COLORS['text_primary'], size=10),
            bgcolor='rgba(0,0,0,0)',
            x=0.5, y=-0.10, xanchor='center', orientation='h',
        ),
        height=450,
        margin=dict(l=70, r=70, t=40, b=70),
    )
    return fig


def _build_metric_explanation_card(n_peers: int, role_label: str) -> dbc.Card:
    """Card explaining each of the 5 radar dimensions."""
    sections = []
    for dim, (subtitle, desc) in _5D_INFO.items():
        color = _5D_COLORS[dim]
        sections.append(html.Div([
            html.Div(dim.upper(), style={
                'color': color, 'fontWeight': '700',
                'fontSize': '0.65rem', 'letterSpacing': '0.8px',
                'textTransform': 'uppercase',
                'marginTop': '12px' if sections else '0',
                'marginBottom': '3px',
            }),
            html.Div(subtitle, style={
                'color': COLORS['text_primary'], 'fontWeight': '600',
                'fontSize': '0.76rem', 'marginBottom': '2px',
                'paddingLeft': '10px', 'borderLeft': f'2px solid {color}',
            }),
            html.Div(desc, style={
                'color': COLORS['text_secondary'], 'fontSize': '0.70rem',
                'lineHeight': '1.4', 'paddingLeft': '10px',
            }),
        ]))

    footer = html.Div([
        html.Hr(style={'borderColor': COLORS['dark_border'], 'margin': '12px 0 8px'}),
        html.Small(
            f'Percentile rank vs {n_peers} positional peers ({role_label}).  '
            '100 = top, 50 = average.  Weights are position-specific.',
            style={'color': COLORS['text_secondary'], 'fontSize': '0.69rem', 'lineHeight': '1.5'},
        ),
    ])

    return dbc.Card([
        dbc.CardHeader(html.H6('Dimension Guide', style={'color': GOLD, 'marginBottom': 0})),
        dbc.CardBody([*sections, footer]),
    ], style={
        'backgroundColor': COLORS['dark_secondary'],
        'border': f'1px solid {COLORS["dark_border"]}',
        'height': '100%',
    })


def _build_performance_section(
    player_name: str,
    d5: dict,
    n_peers: int,
    role: str,
    role_label_override: str | None = None,
) -> html.Div:
    """Assemble the 5-axis radar + dimension guide side-by-side."""
    role_label = role_label_override if role_label_override else _ROLE_LABELS.get(role, role)
    radar_fig  = _build_radar_fig(player_name, d5, n_peers)

    return html.Div([
        section_header(
            'Performance Evaluation',
            subtitle=f'{role_label} · percentile rank vs {n_peers} positional peers',
        ),
        dbc.Row([
            dbc.Col(dcc.Graph(figure=radar_fig, config=CHART_CONFIG), md=7),
            dbc.Col(_build_metric_explanation_card(n_peers, role_label), md=5),
        ], className='mb-4 g-3'),
    ])


# ---------------------------------------------------------------------------
# Layout
# ---------------------------------------------------------------------------

def create_player_analysis_layout():
    players        = get_all_barcelona_players(CURRENT_SEASON)
    player_options = [{'label': p, 'value': p} for p in players if p]

    return dbc.Container([
        page_header('Player Analysis'),
        html.Hr(),

        # 1. Player selector
        dbc.Row([
            dbc.Col([
                html.Label('Player',
                           style={'color': COLORS['text_secondary'], 'fontSize': '0.85rem'}),
                dcc.Dropdown(
                    id='pa-player-selector',
                    options=player_options,
                    value=player_options[0]['value'] if player_options else None,
                    clearable=False,
                    style={'backgroundColor': COLORS['dark_secondary']},
                )
            ], md=5),
        ], className='mb-4'),

        # 2. Player profile card
        html.Div(id='pa-profile', className='mb-4'),

        # 3. Competition + Match selectors
        dbc.Row([
            dbc.Col([
                html.Label('Competition',
                           style={'color': COLORS['text_secondary'], 'fontSize': '0.85rem'}),
                dcc.Dropdown(
                    id='pa-competition-selector',
                    options=_ALL_COMPETITIONS,
                    value='all',
                    clearable=False,
                    style={'backgroundColor': COLORS['dark_secondary']},
                )
            ], md=3),
            dbc.Col([
                html.Label('Match(es)',
                           style={'color': COLORS['text_secondary'], 'fontSize': '0.85rem'}),
                dcc.Dropdown(
                    id='pa-match-selector',
                    options=[],
                    value=None,
                    multi=True,
                    clearable=True,
                    placeholder='All matches…',
                    style={'backgroundColor': COLORS['dark_secondary']},
                )
            ], md=7),
        ], className='mb-4'),

        # 4. Performance Evaluation radar + Season stats (dynamic)
        dcc.Loading(
            id='pa-stats-loading',
            type='circle',
            color=COLORS['gold'],
            children=html.Div(id='pa-stats-section', className='mb-4'),
        ),

        # 5. Event map selector
        dbc.Row([
            dbc.Col([
                html.Label('Event Pitch Map',
                           style={'color': COLORS['text_secondary'], 'fontSize': '0.85rem'}),
                dcc.Dropdown(
                    id='pa-event-type-selector',
                    options=_EVENT_TYPE_OPTIONS,
                    value='Touch Heatmap',
                    clearable=False,
                    style={'backgroundColor': COLORS['dark_secondary']},
                ),
            ], md=4),
        ], className='mb-4'),

        # 6. Event map + Match log (dynamic)
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

    # ── Performance radar + Season stats ─────────────────────────────────
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
            ps_goals       = int(filter_own_goals(player_ev[player_ev['event_type'] == 'Goal']).shape[0])
            ps_appearances = int(player_ev['match_id'].nunique())
            ps_shots       = int(player_ev[player_ev['event_type'].isin(['Miss', 'Saved Shot', 'Goal'])].shape[0])
        else:
            ps_goals       = int(ps['goals'])
            ps_appearances = int(ps['appearances'])
            ps_shots       = int(ps['shots'])

        # Derived stats from event rows
        pass_rows       = player_ev[player_ev['event_type'] == 'Pass']
        n_passes        = len(pass_rows)
        pass_acc        = round(pass_rows['outcome'].eq(1).sum() / max(n_passes, 1) * 100, 1)
        shots_on_target = len(player_ev[player_ev['event_type'].isin(['Saved Shot', 'Goal'])])
        shot_acc        = round(shots_on_target / max(ps_shots, 1) * 100, 1)

        assists    = int(pd.to_numeric(pass_rows['Assist'],    errors='coerce').eq(16).sum()) if 'Assist'    in pass_rows.columns else 0
        key_passes = int(pd.to_numeric(pass_rows['Key Pass'], errors='coerce').eq(1).sum())  if 'Key Pass' in pass_rows.columns else 0

        takeons      = player_ev[player_ev['event_type'] == 'Take On']
        takeon_att   = len(takeons)
        takeon_succ  = int(takeons['outcome'].eq(1).sum()) if 'outcome' in takeons.columns else 0
        takeon_pct   = round(takeon_succ / max(takeon_att, 1) * 100, 1)

        tackles      = len(player_ev[player_ev['event_type'] == 'Tackle'])
        interceptions = len(player_ev[player_ev['event_type'] == 'Interception'])
        recoveries   = len(player_ev[player_ev['event_type'] == 'Ball Recovery'])
        clearances   = len(player_ev[player_ev['event_type'] == 'Clearance'])

        aerials      = player_ev[player_ev['event_type'] == 'Aerial']
        aerial_att   = len(aerials)
        aerial_won   = int(aerials['outcome'].eq(1).sum()) if 'outcome' in aerials.columns else 0
        aerial_pct   = round(aerial_won / max(aerial_att, 1) * 100, 1)

        fouls        = len(player_ev[player_ev['event_type'] == 'Foul'])
        card_rows    = player_ev[player_ev['event_type'] == 'Card']
        yellows      = int(card_rows['Yellow Card'].eq('Si').sum()) if 'Yellow Card' in card_rows.columns else 0
        reds         = int(card_rows['Red Card'].eq('Si').sum())    if 'Red Card'    in card_rows.columns else 0

        goals_per_app  = round(ps_goals  / max(ps_appearances, 1), 2)
        passes_per_app = round(n_passes  / max(ps_appearances, 1), 1)
        shots_per_app  = round(ps_shots  / max(ps_appearances, 1), 1)

        # ── Stats table helpers ───────────────────────────────────────────
        def _stat_row(label, value, highlight=False):
            return html.Tr([
                html.Td(label, style={'color': COLORS['text_secondary'], 'paddingRight': '24px',
                                      'fontSize': '0.82rem', 'whiteSpace': 'nowrap',
                                      'paddingTop': '5px', 'paddingBottom': '5px'}),
                html.Td(str(value), style={
                    'color': GOLD if highlight else COLORS['text_primary'],
                    'textAlign': 'right',
                    'fontWeight': '600' if highlight else '400',
                    'fontSize': '0.88rem',
                }),
            ])

        def _sec_hdr(title):
            return html.Tr([html.Td(title, colSpan=2, style={
                'color': GOLD, 'fontSize': '0.68rem', 'fontWeight': 700,
                'textTransform': 'uppercase', 'letterSpacing': '0.8px',
                'paddingTop': '14px', 'paddingBottom': '4px',
                'borderBottom': f'1px solid {COLORS["dark_border"]}',
            })])

        stat_rows = [
            _sec_hdr('Attacking'),
            _stat_row('Appearances',     ps_appearances),
            _stat_row('Goals',           ps_goals,        highlight=True),
            _stat_row('Assists',         assists),
            _stat_row('Goals / App',     goals_per_app),
            _stat_row('Shots',           ps_shots),
            _stat_row('Shots on Target', shots_on_target),
            _stat_row('Shot Accuracy',   f'{shot_acc}%'),
            _sec_hdr('Possession'),
            _stat_row('Passes',          n_passes),
            _stat_row('Pass Accuracy',   f'{pass_acc}%'),
            _stat_row('Key Passes',      key_passes),
            _stat_row('Passes / App',    passes_per_app),
            _stat_row('Shots / App',     shots_per_app),
            _stat_row('Take Ons',        takeon_att),
            _stat_row('Take On Success', f'{takeon_succ} ({takeon_pct}%)'),
            _sec_hdr('Defending'),
            _stat_row('Tackles',         tackles),
            _stat_row('Interceptions',   interceptions),
            _stat_row('Ball Recoveries', recoveries),
            _stat_row('Clearances',      clearances),
            _stat_row('Aerial Duels Won',f'{aerial_won} / {aerial_att}'),
            _stat_row('Aerial Win %',    f'{aerial_pct}%'),
            _sec_hdr('Discipline'),
            _stat_row('Fouls',           fouls),
            _stat_row('Yellow Cards',    yellows),
            _stat_row('Red Cards',       reds),
        ]

        stats_card = dbc.Card([
            dbc.CardBody([
                html.H6('Season Statistics', style={'color': GOLD, 'marginBottom': '12px'}),
                html.Table(
                    html.Tbody(stat_rows),
                    style={'width': '100%', 'borderCollapse': 'collapse'},
                ),
            ])
        ], style={'backgroundColor': COLORS['dark_secondary'],
                  'border': f'1px solid {COLORS["dark_border"]}',
                  'marginBottom': '24px'})

        # ── Performance Evaluation radar ──────────────────────────────────
        # Derive role and peers directly from the events position column
        # (avoids lineup-parquet dependency which may be incomplete).
        perf_section = html.Div()

        bar_events_all = get_all_events(CURRENT_SEASON)
        if not bar_events_all.empty and 'team_code' in bar_events_all.columns:
            bar_events_all = bar_events_all[bar_events_all['team_code'] == 'BAR']

        if not bar_events_all.empty and 'position' in bar_events_all.columns:
            # Player's most common position
            player_pos_series = (
                bar_events_all[bar_events_all['player_name'] == player_name]['position']
                .dropna()
            )
            player_pos_series = player_pos_series[~player_pos_series.isin(['', 'N/A'])]
            position_mode = player_pos_series.mode()
            opta_position = position_mode.iloc[0] if not position_mode.empty else None
            role = _ROLE_MAP.get(opta_position) if opta_position else None

            if role:
                # Build position lookup for all Barcelona players
                clean_pos = bar_events_all.dropna(subset=['position', 'player_name'])
                clean_pos = clean_pos[~clean_pos['position'].isin(['', 'N/A'])]
                pos_by_player = (
                    clean_pos
                    .groupby('player_name')['position']
                    .agg(lambda s: s.mode().iloc[0] if not s.mode().empty else None)
                )

                # Same-role peers first; fall back to full squad if none
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

        # Return: radar first, then stats table below
        return html.Div([perf_section, stats_card])

    # ── Event map + Match log ─────────────────────────────────────────────
    @app.callback(
        Output('pa-plots-log', 'children'),
        Input('pa-player-selector', 'value'),
        Input('pa-competition-selector', 'value'),
        Input('pa-match-selector', 'value'),
        Input('pa-event-type-selector', 'value'),
    )
    def update_pa_plots_log(player_name, competition, selected_matches, event_type):
        if not player_name:
            return html.Div()

        player_ev = get_player_events(
            player_name, CURRENT_SEASON,
            competition if competition != 'all' else None,
        )
        if selected_matches:
            player_ev = player_ev[player_ev['match_id'].isin(selected_matches)]

        # ── Touch Heatmap ─────────────────────────────────────────────────
        if event_type == 'Touch Heatmap':
            touch = player_ev.dropna(subset=['x', 'y'])
            if not touch.empty:
                img = render_lsc_heatmap_img(touch['x'].tolist(), touch['y'].tolist(), HOME_COLOR, show_zone_pcts=True)
                plot = section_card('Touch Heatmap',
                                    html.Img(src=img, style={'width': '100%', 'borderRadius': '4px'}))
            else:
                plot = section_card('Touch Heatmap', empty_fig('No touch data'))

        # ── Shot Map ──────────────────────────────────────────────────────
        elif event_type == 'Shot Map':
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
                for etype, color in color_map.items():
                    sub = shot_ev[shot_ev['event_type'] == etype]
                    if sub.empty:
                        continue
                    fig_s.add_trace(go.Scatter(
                        x=sub['x'], y=sub['y'], mode='markers', name=etype,
                        marker=dict(color=color, size=11, line=dict(color='white', width=1)),
                        text=sub['time_min'].astype(str) + "'",
                        hovertemplate='%{text}<extra>' + etype + '</extra>',
                    ))
                fig_s.update_layout(**CHART_LAYOUT_DEFAULTS, height=450, **PITCH_AXIS_HALF)
                plot = section_card('Shot Map', dcc.Graph(figure=fig_s, config=CHART_CONFIG))
            else:
                plot = section_card('Shot Map', empty_fig('No shots recorded'))

        # ── Defensive Actions Heatmap (LSC style, same as match analysis) ─
        elif event_type == 'Defensive Actions Heatmap':
            def_ev = player_ev[
                player_ev['event_type'].isin(_DEF_ACTION_TYPES)
            ].dropna(subset=['x', 'y'])

            x_vals = def_ev['x'].tolist()
            y_vals = def_ev['y'].tolist()

            if len(x_vals) >= 2:
                img = render_lsc_heatmap_img(x_vals, y_vals, HOME_COLOR, show_zone_pcts=True)
                plot = section_card(
                    f'Defensive Actions Heatmap  ({len(x_vals)} events)',
                    html.Img(src=img, style={'width': '100%', 'borderRadius': '4px'}),
                )
            else:
                plot = section_card('Defensive Actions Heatmap', empty_fig('No defensive events'))

        # ── Defensive Action Locations (scatter, matches def_structure.py) ─
        elif event_type == 'Defensive Action Locations':
            def_ev = player_ev[
                player_ev['event_type'].isin(_DEF_ACTION_TYPES)
            ].dropna(subset=['x', 'y'])

            fig_d = go.Figure()
            add_pitch_background(fig_d)

            for action_type, color in _DEF_COLORS.items():
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
                    marker=dict(color=color, size=9, opacity=0.80,
                                line=dict(color='rgba(0,0,0,0.3)', width=0.5)),
                    customdata=customdata,
                    hovertemplate=(
                        '<b>%{customdata[0]}</b><br>'
                        "Minute: %{customdata[1]}'<br>"
                        'Action: %{customdata[2]}'
                        '<extra></extra>'
                    ),
                ))

            fig_d.update_layout(**CHART_LAYOUT_DEFAULTS, height=470, **PITCH_AXIS_FULL)
            fig_d.update_layout(legend=dict(
                orientation='v', x=0.01, xanchor='left', y=0.99, yanchor='top',
                bgcolor='rgba(0,0,0,0.55)',
                font=dict(color=COLORS['text_primary'], size=9),
            ))
            n_events = len(def_ev)
            plot = section_card(
                f'Defensive Action Locations  ({n_events} events)',
                dcc.Graph(figure=fig_d, config=CHART_CONFIG),
            )

        else:
            plot = html.Div()

        # ── Match log ─────────────────────────────────────────────────────
        match_stats = get_player_match_stats(player_name, CURRENT_SEASON)
        if competition and competition != 'all':
            match_stats = [m for m in match_stats if m.get('competition') == competition]
        if selected_matches:
            match_stats = [m for m in match_stats if m['match_id'] in set(selected_matches)]

        if match_stats:
            rows = []
            for m in match_stats:
                desc       = m['description']
                short_desc = (desc[:28] + '…') if len(desc) > 30 else desc
                goal_color = COLORS['gold'] if m['goals'] > 0 else COLORS['text_secondary']
                rows.append(html.Tr([
                    html.Td(str(m['date'])[:10]),
                    html.Td(m.get('competition', '')),
                    html.Td(short_desc),
                    html.Td(str(m['goals']),           style={'color': goal_color, 'fontWeight': 'bold'}),
                    html.Td(str(m['passes'])),
                    html.Td(str(m['shots'])),
                    html.Td(str(m.get('tackles', 0))),
                ]))
            match_log = section_card('Match Log', html.Table([
                html.Thead(html.Tr([
                    html.Th('Date'), html.Th('Competition'), html.Th('Match'),
                    html.Th('Goals'), html.Th('Passes'), html.Th('Shots'), html.Th('Tackles'),
                ])),
                html.Tbody(rows),
            ], className='table table-dark table-striped table-sm'))
        else:
            match_log = section_card(
                'Match Log',
                html.P('No matches found.', style={'color': COLORS['text_secondary']}),
            )

        return html.Div([
            dbc.Row([dbc.Col(plot, md=9, className='mx-auto')], className='mb-4'),
            match_log,
        ])
