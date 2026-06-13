"""
Team Analysis Page

Serves as the main orchestrator for team-level performance across the season.
Provides a global competition filter, venue filter, and a multi-select calendar
to specify an exact set of matches to analyze.
"""

import calendar
from datetime import datetime
from dash import html, dcc, Input, Output, State, ALL, ctx
from dash.exceptions import PreventUpdate
import dash_bootstrap_components as dbc
import logging

from utils.config import COLORS
from utils.data_utils import (
    get_match_results,
    CURRENT_SEASON,
)
from utils.logos import get_team_logo_path, get_tournament_logo_path
from page_utils.competitions import ALL_COMPETITIONS as _ALL_COMPETITIONS, normalize_competitions as _normalize_competitions
from page_utils.match_calendar import build_calendar_grid, register_calendar_callbacks

from pages.team_analysis_tabs.overview import (
    build_overview_tab,
    _barca_scores_for_comps,
    _comp_color_map,
    _build_league_avgs,
    _radar_fig,
    _radar_message_fig,
    _form_trendline_fig,
)
from pages.team_analysis_tabs.buildup import build_buildup_tab, register_buildup_callbacks
from pages.team_analysis_tabs.chance_creation import build_chance_creation_tab, register_chance_creation_callbacks
from pages.team_analysis_tabs.def_structure import build_def_structure_tab, register_def_structure_callbacks
from pages.team_analysis_tabs.transitions import build_transitions_tab
from pages.team_analysis_tabs.attacking_transition import register_attacking_transition_callbacks
from pages.team_analysis_tabs.defensive_transition import register_defending_transition_callbacks
from pages.team_analysis_tabs.set_pieces import build_set_pieces_tab, register_set_pieces_callbacks

# UI components from shared, and GOLD from visualizations
from pages.match_report import page_header
from page_utils.visualizations import GOLD

logger = logging.getLogger(__name__)

# Short competition labels for the calendar badge (keyed by display name).
_TA_COMP_SHORT = {
    'La Liga': 'Liga',
    'Champions League': 'UCL',
    'Copa del Rey': 'Copa',
    'Spanish Super Cup': 'Super Cup',
}


def _ta_comp_short(competition: str) -> str:
    return _TA_COMP_SHORT.get(competition, (competition or '')[:6])


# ---------------------------------------------------------------------------
# Calendar Builder
# ---------------------------------------------------------------------------

def _build_multi_calendar_grid(year: int, month: int, match_data: list[dict], selected_match_ids: list[str]) -> html.Div:
    """Barça IQ calendar grid — thin wrapper over the shared builder."""
    return build_calendar_grid(
        year, month, match_data, selected_match_ids,
        id_type='ta-cal-match-btn',
        score_fn=lambda m: f"{m.get('barca_goals', 0)}-{m.get('opponent_goals', 0)}",
        comp_value_fn=lambda m: m.get('competition', ''),
        comp_short_fn=_ta_comp_short,
        comp_logo_fn=get_tournament_logo_path,
    )


# ---------------------------------------------------------------------------
# Layout
# ---------------------------------------------------------------------------

def create_team_analysis_layout():
    """Return the full Team Analysis page layout."""
    
    results = get_match_results()
    results = sorted(results, key=lambda r: str(r['date']))
    match_data = []
    for r in results:
        match_data.append({
            'match_id': r['match_id'],
            'date': str(r['date'])[:10],
            'competition': r['competition'],
            'opponent': r.get('opponent', ''),
            'is_home': r.get('is_home', True),
            'barca_goals': r.get('barca_goals', 0),
            'opponent_goals': r.get('opponent_goals', 0),
            'result': r.get('result', ''),
        })

    if match_data:
        latest = match_data[-1]['date']
        init_year, init_month = int(latest[:4]), int(latest[5:7])
    else:
        now = datetime.now()
        init_year, init_month = now.year, now.month

    return dbc.Container([
        dcc.Store(id='ta-match-data', data=match_data),
        dcc.Store(id='ta-calendar-month', data={'year': init_year, 'month': init_month}),
        dcc.Store(id='ta-selected-matches', data=[]),
        
        page_header("Barça IQ"),
        html.Hr(),

        # ── Filters & Calendar Control Row ───────────────────────────────────
        dbc.Row([
            dbc.Col([
                html.Label("Competition", style={'color': COLORS['text_secondary'], 'fontSize': '0.85rem'}),
                dcc.Dropdown(
                    id='ta-competition-selector',
                    options=_ALL_COMPETITIONS,
                    value=None, multi=True, clearable=True,
                    placeholder="All Competitions…",
                    style={'backgroundColor': COLORS['dark_secondary']},
                ),
            ], md=2),
            dbc.Col([
                html.Label("Venue", style={'color': COLORS['text_secondary'], 'fontSize': '0.85rem'}),
                dcc.Dropdown(
                    id='ta-venue-selector',
                    options=[
                        {'label': 'All Venues', 'value': 'All'},
                        {'label': 'Home', 'value': 'Home'},
                        {'label': 'Away', 'value': 'Away'}
                    ],
                    value='All', clearable=False,
                    style={'backgroundColor': COLORS['dark_secondary']},
                ),
            ], md=2),
            dbc.Col([
                html.Div([
                    html.Button("◀", id='ta-prev-month', n_clicks=0, style={
                        'background': 'none', 'border': f'1px solid {COLORS["dark_border"]}',
                        'color': COLORS['text_primary'], 'borderRadius': '6px',
                        'padding': '6px 14px', 'cursor': 'pointer', 'fontSize': '1rem',
                    }),
                    html.Div(
                        f"{calendar.month_name[init_month]} {init_year}",
                        id='ta-month-label',
                        style={
                            'width': '140px', 'textAlign': 'center', 'fontWeight': 'bold',
                            'fontSize': '1.1rem', 'color': COLORS['text_primary'], 'display': 'inline-block'
                        },
                    ),
                    html.Button("▶", id='ta-next-month', n_clicks=0, style={
                        'background': 'none', 'border': f'1px solid {COLORS["dark_border"]}',
                        'color': COLORS['text_primary'], 'borderRadius': '6px',
                        'padding': '6px 14px', 'cursor': 'pointer', 'fontSize': '1rem',
                    }),
                ], style={'display': 'flex', 'alignItems': 'center', 'justifyContent': 'center', 'paddingTop': '22px'}),
            ], md=4),
            dbc.Col([
                html.Div([
                    html.Div(id='ta-selected-indicator-text', style={'display': 'inline-block'}),
                    html.Button("Clear", id='ta-clear-selection-btn', n_clicks=0, style={'display': 'none'}),
                ], id='ta-selected-indicator', style={
                    'paddingTop': '22px', 'textAlign': 'right',
                    'display': 'flex', 'alignItems': 'center', 'justifyContent': 'flex-end',
                }),
            ], md=4),
        ], className="mb-3"),

        html.Div(id='ta-calendar-container', className="mb-4"),

        # ── Tabs ─────────────────────────────────────────────────────────────
        dbc.Tabs(
            id='ta-tabs',
            active_tab='ta-tab-overview',
            children=[
                dbc.Tab(label='Overview',        tab_id='ta-tab-overview'),
                dbc.Tab(label='Build-up',        tab_id='ta-tab-buildup'),
                dbc.Tab(label='Chance Creation', tab_id='ta-tab-chance'),
                dbc.Tab(label='Transitions',     tab_id='ta-tab-transitions'),
                dbc.Tab(label='Def. Structure',  tab_id='ta-tab-def-struct'),
                dbc.Tab(label='Set Pieces',      tab_id='ta-tab-setpieces'),
            ],
            className="mb-3",
        ),

        dcc.Loading(
            id='ta-loading',
            type='circle',
            color=COLORS['gold'],
            children=html.Div(id='ta-content'),
        ),

    ], fluid=True, className="py-4")


# ---------------------------------------------------------------------------
# Callbacks
# ---------------------------------------------------------------------------

def register_team_analysis_callbacks(app):
    """Register all Team Analysis callbacks."""
    register_buildup_callbacks(app)
    register_chance_creation_callbacks(app)
    register_def_structure_callbacks(app)
    register_attacking_transition_callbacks(app)
    register_defending_transition_callbacks(app)
    register_set_pieces_callbacks(app)

    # Month navigation, multi-select toggle and selection indicator (shared).
    register_calendar_callbacks(app, 'ta')

    # ── Game Model Radar: tournament checkboxes → radar figure ────────────────
    @app.callback(
        Output('ta-radar-graph', 'figure'),
        Input('ta-radar-tourn-filter', 'value'),
        State('ta-venue-selector',   'value'),
        State('ta-selected-matches', 'data'),
        State('ta-radar-compkeys',   'data'),
        prevent_initial_call=True,
    )
    def _update_radar(selected, venue, match_ids, comp_keys):
        comp_keys = comp_keys or []
        selected  = [c for c in (selected or []) if c in comp_keys]
        if not selected:
            return _radar_message_fig('Select at least one tournament')

        match_ids   = match_ids or None
        color_map   = _comp_color_map(comp_keys)
        scores      = _barca_scores_for_comps(selected, venue, match_ids)
        league_avgs = _build_league_avgs(selected, color_map)
        return _radar_fig(scores, 'Barça', league_avgs)

    # ── Form Trendline: tournament filter + metric checkboxes → figure ────────
    @app.callback(
        Output('ta-form-trendline', 'figure'),
        Input('ta-summary-metrics', 'value'),
        Input('ta-summary-tourn',   'value'),
        State('ta-summary-timeline', 'data'),
        prevent_initial_call=True,
    )
    def _update_trendline(metrics, tournament, timeline):
        timeline = timeline or []
        if tournament and tournament != 'all':
            timeline = [t for t in timeline if t.get('competition') == tournament]
        return _form_trendline_fig(timeline, metrics or [])

    @app.callback(
        Output('ta-calendar-container', 'children'),
        Input('ta-calendar-month', 'data'),
        Input('ta-competition-selector', 'value'),
        Input('ta-venue-selector', 'value'),
        Input('ta-match-data', 'data'),
        Input('ta-selected-matches', 'data'),
    )
    def render_calendar(cal_month, competition, venue, match_data, selected_match_ids):
        if not match_data:
            return html.P("No match data available.")
        year, month = cal_month['year'], cal_month['month']
        
        filtered = match_data
        competitions = _normalize_competitions(competition)
        if competitions:
            filtered = [m for m in filtered if m['competition'] in competitions]
            
        if venue and venue != 'All':
            is_home = (venue == 'Home')
            filtered = [m for m in filtered if m.get('is_home') == is_home]
            
        return _build_multi_calendar_grid(year, month, filtered, selected_match_ids)

    @app.callback(
        Output('ta-content', 'children'),
        Input('ta-competition-selector', 'value'),
        Input('ta-venue-selector', 'value'),
        Input('ta-tabs', 'active_tab'),
        Input('ta-selected-matches', 'data'),
        State('ta-match-data', 'data'),
    )
    def render_ta_content(competition, venue, active_tab, match_ids, match_data):
        match_ids = match_ids or None
        if match_ids == []:
            match_ids = None

        if venue and venue != 'All' and match_data:
            is_home = (venue == 'Home')
            venue_match_ids = [m['match_id'] for m in match_data if m.get('is_home') == is_home]
            if match_ids is None:
                match_ids = venue_match_ids
            else:
                match_ids = list(set(match_ids) & set(venue_match_ids))
                if not match_ids:
                    match_ids = ['__NONE__']

        competitions = _normalize_competitions(competition)
        kwargs = dict(season=CURRENT_SEASON, competitions=competitions, match_ids=match_ids)

        dispatch = {
            'ta-tab-overview':     build_overview_tab,
            'ta-tab-buildup':      build_buildup_tab,
            'ta-tab-chance':       build_chance_creation_tab,
            'ta-tab-def-struct':   build_def_structure_tab,
            'ta-tab-transitions':  build_transitions_tab,
            'ta-tab-setpieces':    build_set_pieces_tab,
        }
        builder = dispatch.get(active_tab)
        if builder:
            return builder(**kwargs)
        return html.Div()
