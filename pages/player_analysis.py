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
import numpy as np

from utils.config import COLORS
from utils.data_utils import (
    get_all_barcelona_players,
    get_player_stats,
    get_player_stats_by_competition,
    get_player_match_stats,
    get_player_events,
    get_all_events,
    get_match_results,
    get_match_lineup,
    filter_own_goals,
    exclude_own_goals,
    CURRENT_SEASON,
)
from pages.match_analysis_tabs.shared import (
    CHART_LAYOUT_DEFAULTS,
    CHART_CONFIG,
    add_pitch_background,
    PITCH_AXIS_HALF,
    PITCH_AXIS_FULL,
    section_card,
    kpi_row,
    empty_fig,
    page_header,
    render_heatmap_img,
    render_pass_map_img,
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

# Event types available in the interactive pitch map selector
_EVENT_TYPE_OPTIONS = [
    {'label': 'Pass',          'value': 'Pass'},
    {'label': 'Touch Heatmap', 'value': 'Touch Heatmap'},
    {'label': 'Shot Map',      'value': 'Shot Map'},
    {'label': 'Tackle',        'value': 'Tackle'},
    {'label': 'Interception',  'value': 'Interception'},
    {'label': 'Take On',       'value': 'Take On'},
    {'label': 'Clearance',     'value': 'Clearance'},
    {'label': 'Foul',          'value': 'Foul'},
    {'label': 'Ball Recovery', 'value': 'Ball Recovery'},
    {'label': 'Goal',          'value': 'Goal'},
    {'label': 'Saved Shot',    'value': 'Saved Shot'},
    {'label': 'Miss',          'value': 'Miss'},
]

_PASS_ZONE_MARKS = {0: '0', 33: '33', 66: '66', 100: '100'}


# ---------------------------------------------------------------------------
# Role constants (Opta position label → simplified role bucket)
# ---------------------------------------------------------------------------

_ROLE_MAP = {
    'Goalkeeper':                 'GK',
    'Centre Back':                'CB',
    'Right Centre Back':          'CB',
    'Left Centre Back':           'CB',
    'Right Back':                 'FB',
    'Left Back':                  'FB',
    'Right Wing Back':            'FB',
    'Left Wing Back':             'FB',
    'Defensive Midfielder':       'DM',
    'Centre Midfielder':          'CM',
    'Right Centre Midfielder':    'CM',
    'Left Centre Midfielder':     'CM',
    'Attacking Midfielder':       'AM',
    'Right Attacking Midfielder': 'AM',
    'Left Attacking Midfielder':  'AM',
    'Right Midfielder':           'Winger',
    'Left Midfielder':            'Winger',
    'Right Winger':               'Winger',
    'Left Winger':                'Winger',
    'Centre Forward':             'ST',
    'Second Striker':             'ST',
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


def _load_season_lineups(season):
    """Load and combine lineup data for all matches in a season."""
    import pandas as pd
    results = get_match_results()
    season_start = season.split('-')[0]
    season_end   = season.split('-')[1]
    results = [
        r for r in results
        if str(r['date'])[:4] in (season_start, season_end)
    ]
    frames = []
    for r in results:
        df = get_match_lineup(r['match_id'])
        if not df.empty:
            frames.append(df)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def _player_role(player_name, lineup_df):
    """Return the most-frequent role bucket for a player from lineup data."""
    if lineup_df.empty or 'player_name' not in lineup_df.columns or 'position' not in lineup_df.columns:
        return None
    rows = lineup_df[lineup_df['player_name'] == player_name]['position'].dropna()
    roles = [_ROLE_MAP[p] for p in rows if p in _ROLE_MAP]
    return max(set(roles), key=roles.count) if roles else None


def _peers_for_role(role, lineup_df):
    """Return sorted list of player names who play the given role."""
    if lineup_df.empty or role is None:
        return []
    peer_map = {}
    for _, row in lineup_df.iterrows():
        name = row.get('player_name', '')
        pos  = row.get('position', '')
        r    = _ROLE_MAP.get(pos)
        if name and r == role:
            peer_map.setdefault(name, []).append(r)
    return sorted(peer_map.keys())


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

        # ── 4. Stats & Radars (Dynamic) ───────────────────────────────────
        dcc.Loading(
            id='pa-stats-radars-loading',
            type='circle',
            color=COLORS['gold'],
            children=html.Div(id='pa-stats-radars', className="mb-4"),
        ),

        # ── 5. Analysis filter row ────────────────────────────────────────
        dbc.Row([
            dbc.Col([
                html.Label("Event Pitch Map",
                           style={'color': COLORS['text_secondary'], 'fontSize': '0.85rem'}),
                dcc.Dropdown(
                    id='pa-event-type-selector',
                    options=_EVENT_TYPE_OPTIONS,
                    value='Pass',
                    clearable=False,
                    style={'backgroundColor': COLORS['dark_secondary']},
                ),
            ], md=3),
            dbc.Col([
                html.Label("Pass Start Zone (x)",
                           style={'color': COLORS['text_secondary'], 'fontSize': '0.85rem'}),
                dcc.RangeSlider(
                    id='pa-pass-start-zone',
                    min=0, max=100, step=1,
                    value=[0, 100],
                    marks=_PASS_ZONE_MARKS,
                    tooltip={'placement': 'bottom', 'always_visible': False},
                ),
            ], md=4),
            dbc.Col([
                html.Label("Pass End Zone (x)",
                           style={'color': COLORS['text_secondary'], 'fontSize': '0.85rem'}),
                dcc.RangeSlider(
                    id='pa-pass-end-zone',
                    min=0, max=100, step=1,
                    value=[0, 100],
                    marks=_PASS_ZONE_MARKS,
                    tooltip={'placement': 'bottom', 'always_visible': False},
                ),
            ], md=4),
        ], className="mb-4"),

        # ── 6. Plots & Match Log (Dynamic) ────────────────────────────────
        dcc.Loading(
            id='pa-plots-log-loading',
            type='circle',
            color=COLORS['gold'],
            children=html.Div(id='pa-plots-log'),
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

    # -- 1. Stats and Radar Plots Callback --
    @app.callback(
        Output('pa-stats-radars', 'children'),
        Input('pa-player-selector', 'value'),
        Input('pa-competition-selector', 'value'),
        Input('pa-match-selector', 'value'),
    )
    def update_pa_stats_radars(player_name, competition, selected_matches):
        if not player_name:
            return html.P("Select a player to view analysis.",
                          style={'color': COLORS['text_secondary']})

        # Base events for player
        player_ev = get_player_events(
            player_name,
            CURRENT_SEASON,
            competition if competition != 'all' else None,
        )
        if selected_matches:
            player_ev = player_ev[player_ev['match_id'].isin(selected_matches)]

        # Base KPIs from pre-computed stats
        all_stats = get_player_stats(CURRENT_SEASON)
        player_row = all_stats[all_stats['player'] == player_name]

        if player_row.empty:
            return html.P("No data available for this player.",
                          style={'color': COLORS['text_secondary']})

        ps = player_row.iloc[0]
        appearances = int(ps['appearances']) if ps['appearances'] > 0 else 1
        passes_per_match = round(ps['passes'] / appearances, 1)

        # Re-derive goals/apps if filtered
        if selected_matches or (competition and competition != 'all'):
            ps_goals = int(
                filter_own_goals(player_ev[player_ev['event_type'] == 'Goal']).shape[0]
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

        # ---- RADAR PLOTS ----
        lineup_df   = _load_season_lineups(CURRENT_SEASON)
        role        = _player_role(player_name, lineup_df)
        peers       = _peers_for_role(role, lineup_df)

        radar_cards = html.Div()
        if role and len(peers) > 1:
            label = _ROLE_LABELS.get(role, role)
            bar_events_all = get_all_events(CURRENT_SEASON)
            if not bar_events_all.empty:
                bar_events_all = bar_events_all[bar_events_all['team_code'] == 'BAR']

            # Compile peer stats (unfiltered by match so the /90 average is stable)
            peer_stats = []
            for p in peers:
                pe = bar_events_all[bar_events_all['player_name'] == p]
                apps = int(pe['match_id'].nunique())
                if apps == 0:
                    continue
                goals = int(filter_own_goals(pe[pe['event_type'] == 'Goal']).shape[0])
                passes = int(pe[pe['event_type'] == 'Pass'].shape[0])
                shots = int(pe[pe['event_type'].isin(['Miss', 'Saved Shot', 'Goal'])].shape[0])
                takeons = int(pe[pe['event_type'] == 'Take On'].shape[0])
                
                pass_rows = pe[pe['event_type'] == 'Pass']
                pass_acc = round(pass_rows['outcome'].eq(1).sum() / max(len(pass_rows), 1) * 100, 1)
                
                tackles = int(pe[pe['event_type'] == 'Tackle'].shape[0])
                intercepts = int(pe[pe['event_type'] == 'Interception'].shape[0])
                recoveries = int(pe[pe['event_type'] == 'Ball Recovery'].shape[0])
                clearances = int(pe[pe['event_type'] == 'Clearance'].shape[0])
                
                aerials = pe[pe['event_type'] == 'Aerial']
                aerial_win_pct = round(aerials['outcome'].eq(1).sum() / max(len(aerials), 1) * 100, 1)

                peer_stats.append({
                    'player': p, 'apps': apps,
                    'is_current': p == player_name,
                    'goals': goals, 'passes': passes, 'shots': shots, 'takeons': takeons, 'pass_acc': pass_acc,
                    'tackles': tackles, 'intercepts': intercepts, 'recoveries': recoveries, 
                    'clearances': clearances, 'aerial_win_pct': aerial_win_pct
                })

            cur_s = next((s for s in peer_stats if s['is_current']), None)
            avg_s = [s for s in peer_stats if not s['is_current']]
            
            def _per_app(val, apps): return round(val / max(apps, 1), 2)
            def _avg(key, is_rate=True): 
                if not avg_s: return 0
                if is_rate:
                    return round(sum(s[key] for s in avg_s) / max(sum(s['apps'] for s in avg_s), 1), 2)
                return round(sum(s[key] for s in avg_s) / len(avg_s), 1)

            if cur_s and avg_s:
                # 1. Attacking Radar
                att_cats = ['Goals/App', 'Shots/App', 'Passes/App', 'Pass Acc %', 'Take Ons/App']
                att_cur = [
                    _per_app(cur_s['goals'], cur_s['apps']),
                    _per_app(cur_s['shots'], cur_s['apps']),
                    _per_app(cur_s['passes'], cur_s['apps']),
                    cur_s['pass_acc'],
                    _per_app(cur_s['takeons'], cur_s['apps'])
                ]
                att_avg = [
                    _avg('goals'), _avg('shots'), _avg('passes'), 
                    _avg('pass_acc', False), _avg('takeons')
                ]

                # 2. Defending Radar
                def_cats = ['Tackles/App', 'Intercepts/App', 'Recoveries/App', 'Clearances/App', 'Aerial Win %']
                def_cur = [
                    _per_app(cur_s['tackles'], cur_s['apps']),
                    _per_app(cur_s['intercepts'], cur_s['apps']),
                    _per_app(cur_s['recoveries'], cur_s['apps']),
                    _per_app(cur_s['clearances'], cur_s['apps']),
                    cur_s['aerial_win_pct']
                ]
                def_avg = [
                    _avg('tackles'), _avg('intercepts'), _avg('recoveries'), 
                    _avg('clearances'), _avg('aerial_win_pct', False)
                ]

                def _build_radar(title, cats, cur_vals, avg_vals):
                    maxvals = [max(a, b, 0.001) for a, b in zip(cur_vals, avg_vals)]
                    cur_norm = [v / m * 100 for v, m in zip(cur_vals, maxvals)]
                    avg_norm = [v / m * 100 for v, m in zip(avg_vals, maxvals)]
                    
                    cats_closed = cats + [cats[0]]
                    cur_closed = cur_norm + [cur_norm[0]]
                    avg_closed = avg_norm + [avg_norm[0]]

                    fig = go.Figure()
                    fig.add_trace(go.Scatterpolar(
                        r=cur_closed, theta=cats_closed, fill='toself',
                        name=player_name, line=dict(color=GOLD, width=2),
                        fillcolor='rgba(161,120,40,0.3)',
                        hovertemplate='%{theta}: %{r:.1f}<extra></extra>',
                    ))
                    fig.add_trace(go.Scatterpolar(
                        r=avg_closed, theta=cats_closed, fill='toself',
                        name=f'{label} Avg', line=dict(color=HOME_COLOR, width=2, dash='dot'),
                        fillcolor='rgba(31,119,180,0.15)',
                        hovertemplate='%{theta}: %{r:.1f}<extra></extra>',
                    ))
                    fig.update_layout(
                        **CHART_LAYOUT_DEFAULTS, height=320,
                        margin=dict(t=30, b=30, l=40, r=40),
                        polar=dict(
                            bgcolor='rgba(0,0,0,0)',
                            radialaxis=dict(visible=True, range=[0, 100], color=COLORS['text_secondary'], gridcolor='rgba(255,255,255,0.15)'),
                            angularaxis=dict(color=COLORS['text_secondary'], gridcolor='rgba(255,255,255,0.15)'),
                        ),
                        legend=dict(orientation="h", yanchor="bottom", y=-0.2, xanchor="center", x=0.5)
                    )
                    from pages.match_analysis_tabs.shared import section_card
                    return section_card(title, dcc.Graph(figure=fig, config=CHART_CONFIG))

                radar_cards = dbc.Row([
                    dbc.Col(_build_radar("Attacking & Possession", att_cats, att_cur, att_avg), md=6),
                    dbc.Col(_build_radar("Defending", def_cats, def_cur, def_avg), md=6),
                ], className="mb-4")

        return html.Div([stats_card, radar_cards])


    # -- 2. Dynamic Plot and Match Log Callback --
    @app.callback(
        Output('pa-plots-log', 'children'),
        Input('pa-player-selector', 'value'),
        Input('pa-competition-selector', 'value'),
        Input('pa-match-selector', 'value'),
        Input('pa-event-type-selector', 'value'),
        Input('pa-pass-start-zone', 'value'),
        Input('pa-pass-end-zone', 'value'),
    )
    def update_pa_plots_log(player_name, competition, selected_matches,
                            event_type, pass_start_zone, pass_end_zone):
        if not player_name:
            return html.Div()

        player_ev = get_player_events(
            player_name, CURRENT_SEASON,
            competition if competition != 'all' else None,
        )
        if selected_matches:
            player_ev = player_ev[player_ev['match_id'].isin(selected_matches)]
            
        dynamic_plot = html.Div()

        # Conditionally render the selected plot type
        if event_type == 'Touch Heatmap':
            touch_data = player_ev.dropna(subset=['x', 'y'])
            if not touch_data.empty:
                img_src = render_heatmap_img(touch_data['x'].tolist(), touch_data['y'].tolist())
                dynamic_plot = section_card("Touch Heatmap", html.Img(src=img_src, style={'width': '100%', 'borderRadius': '4px'}))
            else:
                dynamic_plot = section_card("Touch Heatmap", empty_fig("No touch data"))

        elif event_type == 'Shot Map':
            shot_types = ['Miss', 'Saved Shot', 'Goal', 'Post', 'Blocked Shot']
            shots = exclude_own_goals(player_ev[player_ev['event_type'].isin(shot_types)].copy()).dropna(subset=['x', 'y'])
            if not shots.empty:
                color_map = {'Goal': GOLD, 'Saved Shot': HOME_COLOR, 'Miss': AWAY_COLOR, 'Post': '#ffd43b', 'Blocked Shot': '#cc5de8'}
                fig_shots = go.Figure()
                add_pitch_background(fig_shots, half=True)
                for etype, color in color_map.items():
                    subset = shots[shots['event_type'] == etype]
                    if subset.empty: continue
                    fig_shots.add_trace(go.Scatter(
                        x=subset['x'], y=subset['y'], mode='markers', name=etype,
                        marker=dict(color=color, size=11, line=dict(color='white', width=1)),
                        text=subset['time_min'].astype(str) + "'",
                        hovertemplate='%{text}<extra>' + etype + '</extra>',
                    ))
                fig_shots.update_layout(**CHART_LAYOUT_DEFAULTS, height=450, **PITCH_AXIS_HALF)
                dynamic_plot = section_card("Shot Map", dcc.Graph(figure=fig_shots, config=CHART_CONFIG))
            else:
                dynamic_plot = section_card("Shot Map", empty_fig("No shots recorded"))

        elif event_type == 'Pass':
            passes_df = player_ev[player_ev['event_type'] == 'Pass'].copy()
            end_x_col, end_y_col = 'Pass End X', 'Pass End Y'
            has_end_coords = (end_x_col in passes_df.columns and end_y_col in passes_df.columns)
            
            if has_end_coords:
                passes_df = passes_df.dropna(subset=['x', 'y', end_x_col, end_y_col])
                passes_df[end_x_col] = passes_df[end_x_col].replace({'N/A': np.nan, '': np.nan}).astype(float)
                passes_df[end_y_col] = passes_df[end_y_col].replace({'N/A': np.nan, '': np.nan}).astype(float)
                passes_df = passes_df.dropna(subset=[end_x_col, end_y_col])
                if pass_start_zone:
                    passes_df = passes_df[passes_df['x'].between(pass_start_zone[0], pass_start_zone[1])]
                if pass_end_zone:
                    passes_df = passes_df[passes_df[end_x_col].between(pass_end_zone[0], pass_end_zone[1])]
            
            n_passes = len(passes_df)
            if has_end_coords and n_passes > 0:
                oc = passes_df['outcome'] if 'outcome' in passes_df.columns else None
                pm_src = render_pass_map_img(
                    passes_df['x'].values, passes_df['y'].values,
                    passes_df[end_x_col].values, passes_df[end_y_col].values,
                    outcomes=oc.values if oc is not None else None,
                )
                dynamic_plot = section_card(f"Pass Map ({n_passes} passes)", html.Img(src=pm_src, style={'width': '100%', 'borderRadius': '4px'}))
            elif not has_end_coords and n_passes > 0:
                pm_src = render_heatmap_img(passes_df['x'].dropna().values, passes_df['y'].dropna().values, cmap='Blues')
                dynamic_plot = section_card(f"Pass Origins ({n_passes} passes)", html.Img(src=pm_src, style={'width': '100%', 'borderRadius': '4px'}))
            else:
                dynamic_plot = section_card("Pass Map", empty_fig("No passes in selected zone"))

        else:
            # Generic Event Pitch Map
            ev_df = player_ev[player_ev['event_type'] == event_type].dropna(subset=['x', 'y'])
            fig_ev = go.Figure()
            add_pitch_background(fig_ev, half=False)
            if not ev_df.empty:
                def _ev_color(row): return HOME_COLOR if row.get('outcome') == 1 else (AWAY_COLOR if row.get('outcome') == 0 else GOLD)
                fig_ev.add_trace(go.Scatter(
                    x=ev_df['x'], y=ev_df['y'], mode='markers',
                    marker=dict(size=12, color=ev_df.apply(_ev_color, axis=1).tolist(), line=dict(color='white', width=1)),
                    text=ev_df['time_min'].astype(str) + "'",
                    hovertemplate='%{text}<extra>' + event_type + '</extra>',
                    name=event_type,
                ))
            fig_ev.update_layout(**CHART_LAYOUT_DEFAULTS, height=450, **PITCH_AXIS_FULL)
            dynamic_plot = section_card(f"{event_type} Map ({len(ev_df)} events)", dcc.Graph(figure=fig_ev, config=CHART_CONFIG))


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
                    html.Td(str(m['goals']), style={'color': goal_color, 'fontWeight': 'bold'}),
                    html.Td(str(m['passes'])),
                    html.Td(str(m['shots'])),
                    html.Td(str(m.get('tackles', 0))),
                ]))
            match_log = section_card("Match Log", html.Table([
                html.Thead(html.Tr([
                    html.Th("Date"), html.Th("Competition"), html.Th("Match"),
                    html.Th("Goals"), html.Th("Passes"), html.Th("Shots"), html.Th("Tackles"),
                ])),
                html.Tbody(rows),
            ], className="table table-dark table-striped table-sm"))
        else:
            match_log = section_card("Match Log", html.P("No matches found.", style={'color': COLORS['text_secondary']}))

        return html.Div([
            dbc.Row([dbc.Col(dynamic_plot, md=8, className="mx-auto")], className="mb-4"),
            match_log
        ])
