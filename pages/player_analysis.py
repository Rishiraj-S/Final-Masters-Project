"""
CuléVision - Player Analysis Page
Individual Barcelona player profile with shot map, touch heatmap and match log.
Fixed to 2025-2026 season.
"""

import re
from pathlib import Path

from dash import html, dcc
from dash.dependencies import Input, Output, State
import dash_bootstrap_components as dbc
import plotly.graph_objects as go

from utils.config import COLORS
from utils.data_utils import (
    get_all_barcelona_players,
    get_player_stats,
    get_player_stats_by_competition,
    get_player_match_stats,
    get_player_events,
    get_all_events,
    get_match_results,
    filter_own_goals,
    CURRENT_SEASON,
)
from pages.match_analysis_tabs.shared import (
    CHART_LAYOUT_DEFAULTS,
    CHART_CONFIG,
    add_pitch_background,
    PITCH_AXIS_HALF,
    section_card,
    kpi_row,
    empty_fig,
    page_header,
    render_heatmap_img,
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

_PLACEHOLDER_IMG = '/assets/logos/team/FC-Barcelona-v2002.svg'

_ALL_COMPETITIONS = [
    {'label': 'All Competitions', 'value': 'all'},
    {'label': 'La Liga',          'value': 'La Liga'},
    {'label': 'Champions League', 'value': 'Champions League'},
    {'label': 'Copa del Rey',     'value': 'Copa del Rey'},
    {'label': 'Spanish Super Cup','value': 'Spanish Super Cup'},
]

# Short competition abbreviations for match selector labels
_COMP_SHORT = {
    'La Liga':           'Liga',
    'Champions League':  'UCL',
    'Copa del Rey':      'Copa',
    'Spanish Super Cup': 'SC',
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _extract_jersey_and_position(player_ev):
    """Extract jersey number and primary position from event rows."""
    jersey_num = None
    position = None

    jersey_col = 'Jersey Number'
    if jersey_col in player_ev.columns:
        vals = player_ev[jersey_col].dropna()
        vals = vals[~vals.isin(['N/A', ''])]
        if not vals.empty:
            try:
                jersey_num = int(float(vals.iloc[0]))
            except (ValueError, TypeError):
                pass

    pos_col = 'position'
    if pos_col in player_ev.columns:
        positions = player_ev[pos_col].dropna()
        positions = positions[~positions.isin(['', 'N/A'])]
        if not positions.empty:
            position = positions.mode().iloc[0]

    return jersey_num, position


def _player_profile_card(player_name, jersey_num, position, stats=None):
    """Build the player profile card — 3 sections: image | profile | stats."""
    img_src = _PLAYER_IMAGE_MAP.get(jersey_num, _PLACEHOLDER_IMG)
    jersey_text   = f'#{jersey_num}' if jersey_num else '—'
    position_text = position if position else '—'
    stats = stats or {}

    _COL_DIVIDER = f'1px solid {COLORS["dark_border"]}'

    # ── Col 1: Player photo ────────────────────────────────────────────────
    col_image = dbc.Col([
        html.Img(
            src=img_src,
            style={
                'width': '100%',
                'maxWidth': '280px',
                'borderRadius': '10px',
                'display': 'block',
                'margin': '0 auto',
                'boxShadow': '0 8px 28px rgba(0,0,0,0.55)',
            }
        ),
    ], md=4, className="d-flex align-items-center justify-content-center py-2")

    # ── Col 2: Profile details (left-bordered inner wrapper) ───────────────
    col_profile = dbc.Col([
        html.Div([
            html.H4(player_name,
                    style={'color': GOLD, 'marginBottom': '2px', 'fontWeight': 700,
                           'fontSize': '1.25rem'}),
            html.P('FC Barcelona',
                   style={'color': COLORS['text_secondary'], 'marginBottom': '16px',
                          'fontSize': '0.82rem', 'letterSpacing': '0.4px'}),

            # Jersey + position as inline badges
            html.Div([
                html.Span(jersey_text, style={
                    'backgroundColor': GOLD, 'color': '#000',
                    'borderRadius': '4px', 'padding': '2px 9px',
                    'fontSize': '0.78rem', 'fontWeight': 700, 'marginRight': '6px',
                }),
                html.Span(position_text, style={
                    'color': COLORS['text_secondary'], 'fontSize': '0.82rem',
                }),
            ], className='mb-4'),

            _detail_row('Club',   'FC Barcelona'),
            _detail_row('Season', '2025 – 2026'),
        ], style={
            'borderLeft': _COL_DIVIDER,
            'paddingLeft': '24px',
            'height': '100%',
        }),
    ], md=3, className="py-2")

    # ── Col 3: Season statistics (left-bordered inner wrapper) ────────────
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
        highlight = key == 'goals'
        return html.Div([
            html.Div(val, style={
                'fontSize': '1.55rem', 'fontWeight': 700, 'lineHeight': '1',
                'color': GOLD if highlight else COLORS['text_primary'],
            }),
            html.Div(label, style={
                'fontSize': '0.6rem', 'color': COLORS['text_secondary'],
                'marginTop': '5px', 'textTransform': 'uppercase', 'letterSpacing': '0.5px',
            }),
        ], style={
            'textAlign': 'center',
            'padding': '12px 6px',
            'backgroundColor': 'rgba(0,0,0,0.25)',
            'borderRadius': '6px',
            'border': _COL_DIVIDER,
        })

    col_stats = dbc.Col([
        html.Div([
            html.Small("Season Statistics", style={
                'color': GOLD, 'fontWeight': 600, 'display': 'block',
                'marginBottom': '12px', 'textTransform': 'uppercase',
                'letterSpacing': '0.6px', 'fontSize': '0.7rem',
            }),
            html.Div(
                [_stat_box(k, l) for k, l in stat_items],
                style={
                    'display': 'grid',
                    'gridTemplateColumns': 'repeat(3, 1fr)',
                    'gap': '8px',
                }
            ),
        ], style={
            'borderLeft': _COL_DIVIDER,
            'paddingLeft': '24px',
            'height': '100%',
        }),
    ], md=5, className="py-2")

    return dbc.Card([
        dbc.CardBody([
            dbc.Row([col_image, col_profile, col_stats], align="center",
                    className="g-0"),
        ], style={'padding': '1.25rem 1.5rem'})
    ], style={
        'backgroundColor': COLORS['dark_secondary'],
        'border': f'1px solid {COLORS["dark_border"]}',
        'borderTop': f'3px solid {GOLD}',
        'borderRadius': '8px',
        'overflow': 'hidden',
    })


def _detail_row(label, value):
    return dbc.Row([
        dbc.Col(html.Small(label, style={'color': COLORS['text_secondary']}), width=5),
        dbc.Col(html.Small(value, style={'color': COLORS['text_primary'],
                                         'fontWeight': '600'}), width=7),
    ], className='mb-2')


def _build_match_options(player_name, competition):
    """Build match dropdown options for a given player and competition filter."""
    match_stats = get_player_match_stats(player_name, CURRENT_SEASON)
    if competition and competition != 'all':
        match_stats = [m for m in match_stats if m.get('competition') == competition]

    results_map = {r['match_id']: r for r in get_match_results()}

    options = []
    for m in match_stats:
        mid = m['match_id']
        r = results_map.get(mid, {})
        opponent  = r.get('opponent', str(m.get('description', mid))[:20])
        res       = r.get('result', '')
        date      = str(m.get('date', ''))[:10]
        comp      = m.get('competition', '')
        comp_tag  = _COMP_SHORT.get(comp, comp[:4])
        label = f"{date}  {opponent}  ({res})" + (f"  · {comp_tag}" if competition == 'all' else '')
        options.append({'label': label, 'value': mid})

    return options


# ---------------------------------------------------------------------------
# Layout
# ---------------------------------------------------------------------------

def create_player_analysis_layout():
    """Create the Player Analysis page layout."""
    players = get_all_barcelona_players(CURRENT_SEASON)
    player_options = [{'label': p, 'value': p} for p in players if p]

    return dbc.Container([
        page_header("Player Analysis"),
        html.Hr(),

        # ── 1. Player selector ────────────────────────────────────────────
        dbc.Row([
            dbc.Col([
                html.Label("Player",
                           style={'color': COLORS['text_secondary'], 'fontSize': '0.85rem'}),
                dcc.Dropdown(
                    id='pa-player-selector',
                    options=player_options,
                    value=player_options[0]['value'] if player_options else None,
                    clearable=False,
                    style={'backgroundColor': COLORS['dark_secondary']},
                )
            ], md=5),
        ], className="mb-4"),

        # ── 2. Player profile (populated by callback) ─────────────────────
        html.Div(id='pa-profile', className="mb-4"),

        # ── 3. Tournament + Match selectors ───────────────────────────────
        dbc.Row([
            dbc.Col([
                html.Label("Competition",
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
                html.Label("Match(es)",
                           style={'color': COLORS['text_secondary'], 'fontSize': '0.85rem'}),
                dcc.Dropdown(
                    id='pa-match-selector',
                    options=[],
                    value=None,
                    multi=True,
                    clearable=True,
                    placeholder="All matches…",
                    style={'backgroundColor': COLORS['dark_secondary']},
                )
            ], md=7),
        ], className="mb-4"),

        # ── 4. Content ────────────────────────────────────────────────────
        dcc.Loading(
            id='pa-loading',
            type='circle',
            color=COLORS['gold'],
            children=html.Div(id='pa-content'),
        ),
    ], fluid=True, className="py-4")


# ---------------------------------------------------------------------------
# Callbacks
# ---------------------------------------------------------------------------

def register_player_analysis_callbacks(app):
    """Register all Player Analysis callbacks."""

    # -- Profile card (updates on player change alone) --------------------
    @app.callback(
        Output('pa-profile', 'children'),
        Input('pa-player-selector', 'value'),
    )
    def update_pa_profile(player_name):
        if not player_name:
            return html.Div()
        player_ev = get_player_events(player_name, CURRENT_SEASON)
        jersey_num, position = _extract_jersey_and_position(player_ev)

        # Compute full-season stats for the profile sidebar
        stats = {}
        if not player_ev.empty:
            stats['appearances'] = int(player_ev['match_id'].nunique())
            stats['goals']       = int(
                filter_own_goals(
                    player_ev[player_ev['event_type'] == 'Goal']
                ).shape[0]
            )
            stats['shots']       = int(
                player_ev[player_ev['event_type'].isin(
                    ['Miss', 'Saved Shot', 'Goal']
                )].shape[0]
            )
            stats['tackles']     = int(
                player_ev[player_ev['event_type'] == 'Tackle'].shape[0]
            )
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

    # -- Match selector options (updates on player OR competition change) --
    @app.callback(
        Output('pa-match-selector', 'options'),
        Output('pa-match-selector', 'value'),
        Input('pa-player-selector', 'value'),
        Input('pa-competition-selector', 'value'),
    )
    def update_pa_match_options(player_name, competition):
        if not player_name:
            return [], None
        options = _build_match_options(player_name, competition)
        return options, None   # None = all matches by default

    # -- Main stats content -----------------------------------------------
    @app.callback(
        Output('pa-content', 'children'),
        Input('pa-player-selector', 'value'),
        Input('pa-competition-selector', 'value'),
        Input('pa-match-selector', 'value'),
    )
    def update_pa_content(player_name, competition, selected_matches):
        if not player_name:
            return html.P("Select a player to view analysis.",
                          style={'color': COLORS['text_secondary']})

        # Raw events for this player (unfiltered first, then scoped)
        player_ev = get_player_events(
            player_name,
            CURRENT_SEASON,
            competition if competition != 'all' else None,
        )

        # Apply match filter if specific matches were chosen
        if selected_matches:
            player_ev = player_ev[player_ev['match_id'].isin(selected_matches)]

        # -- KPI stats --
        all_stats = get_player_stats(CURRENT_SEASON)
        player_row = all_stats[all_stats['player'] == player_name]

        if player_row.empty:
            return html.P("No data available for this player.",
                          style={'color': COLORS['text_secondary']})

        ps = player_row.iloc[0]
        appearances = int(ps['appearances']) if ps['appearances'] > 0 else 1
        passes_per_match = round(ps['passes'] / appearances, 1)

        # If filtered to specific matches/competition, derive KPIs from filtered events
        if selected_matches or (competition and competition != 'all'):
            ps_goals = int(
                filter_own_goals(
                    player_ev[player_ev['event_type'] == 'Goal']
                ).shape[0]
            )
            unique_matches = player_ev['match_id'].nunique()
            ps_appearances = unique_matches
            ps_shots = int(
                player_ev[player_ev['event_type'].isin(['Miss', 'Saved Shot', 'Goal'])].shape[0]
            )
            pass_count = int(player_ev[player_ev['event_type'] == 'Pass'].shape[0])
            ps_passes_pm = round(pass_count / max(unique_matches, 1), 1)
        else:
            ps_goals       = int(ps['goals'])
            ps_appearances = int(ps['appearances'])
            ps_shots       = int(ps['shots'])
            ps_passes_pm   = passes_per_match

        tackles      = len(player_ev[player_ev['event_type'] == 'Tackle'])
        interceptions = len(player_ev[player_ev['event_type'] == 'Interception'])

        stats_kpi = kpi_row(
            {
                'goals':         ps_goals,
                'appearances':   ps_appearances,
                'shots':         ps_shots,
                'passes_pm':     ps_passes_pm,
                'tackles':       tackles,
                'interceptions': interceptions,
            },
            [
                ('goals',         'Goals'),
                ('appearances',   'Appearances'),
                ('shots',         'Shots'),
                ('passes_pm',     'Passes / Match'),
                ('tackles',       'Tackles'),
                ('interceptions', 'Interceptions'),
            ],
            colors={'goals': GOLD},
        )

        stats_card = dbc.Card([
            dbc.CardBody([
                html.H6("Stats", style={'color': GOLD, 'marginBottom': '16px'}),
                stats_kpi,
            ])
        ], style={'backgroundColor': COLORS['dark_secondary'],
                  'border': f'1px solid {COLORS["dark_border"]}',
                  'marginBottom': '24px'})

        # -- Shot map --
        shot_types = ['Miss', 'Saved Shot', 'Goal']
        shots = player_ev[player_ev['event_type'].isin(shot_types)].dropna(subset=['x', 'y'])

        if not shots.empty:
            color_map = {'Goal': GOLD, 'Saved Shot': HOME_COLOR, 'Miss': AWAY_COLOR}
            fig_shots = go.Figure()
            add_pitch_background(fig_shots, half=True)
            for etype, color in color_map.items():
                subset = shots[shots['event_type'] == etype]
                if subset.empty:
                    continue
                fig_shots.add_trace(go.Scatter(
                    x=subset['x'], y=subset['y'],
                    mode='markers',
                    name=etype,
                    marker=dict(color=color, size=11, line=dict(color='white', width=1)),
                    text=subset['time_min'].astype(str) + "'",
                    hovertemplate='%{text}<extra>' + etype + '</extra>',
                ))
            fig_shots.update_layout(**CHART_LAYOUT_DEFAULTS, height=380, **PITCH_AXIS_HALF)
            shot_map = section_card("Shot Map",
                                    dcc.Graph(figure=fig_shots, config=CHART_CONFIG))
        else:
            shot_map = section_card("Shot Map", empty_fig("No shots recorded"))

        # -- Touch heatmap --
        touch_data = player_ev.dropna(subset=['x', 'y'])
        if not touch_data.empty:
            img_src = render_heatmap_img(touch_data['x'].tolist(), touch_data['y'].tolist())
            heatmap = section_card(
                "Touch Heatmap",
                html.Img(src=img_src, style={'width': '100%', 'borderRadius': '4px'}),
            )
        else:
            heatmap = section_card("Touch Heatmap", empty_fig("No touch data"))

        # -- Match log --
        match_stats = get_player_match_stats(player_name, CURRENT_SEASON)
        if competition and competition != 'all':
            match_stats = [m for m in match_stats if m.get('competition') == competition]
        if selected_matches:
            match_stats = [m for m in match_stats if m['match_id'] in set(selected_matches)]

        if match_stats:
            rows = []
            for m in match_stats:
                desc = m['description']
                short_desc = (desc[:28] + '…') if len(desc) > 30 else desc
                goal_color = COLORS['gold'] if m['goals'] > 0 else COLORS['text_secondary']
                rows.append(html.Tr([
                    html.Td(str(m['date'])[:10]),
                    html.Td(m.get('competition', '')),
                    html.Td(short_desc),
                    html.Td(str(m['goals']),
                            style={'color': goal_color, 'fontWeight': 'bold'}),
                    html.Td(str(m['passes'])),
                    html.Td(str(m['shots'])),
                    html.Td(str(m.get('tackles', 0))),
                ]))
            match_log = section_card("Match Log", html.Table([
                html.Thead(html.Tr([
                    html.Th("Date"), html.Th("Competition"), html.Th("Match"),
                    html.Th("Goals"), html.Th("Passes"),
                    html.Th("Shots"), html.Th("Tackles"),
                ])),
                html.Tbody(rows),
            ], className="table table-dark table-striped table-sm"))
        else:
            match_log = section_card("Match Log", html.P(
                "No matches found.", style={'color': COLORS['text_secondary']}
            ))

        return html.Div([
            stats_card,
            dbc.Row([
                dbc.Col(shot_map, md=6),
                dbc.Col(heatmap, md=6),
            ], className="mb-3"),
            match_log,
        ])
