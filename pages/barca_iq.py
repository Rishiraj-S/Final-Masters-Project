"""
Team Analysis Page

Serves as the main orchestrator for team-level performance across the season.
Provides a global competition filter, venue filter, and a multi-select calendar
to specify an exact set of matches to analyze.
"""

import calendar
from datetime import datetime
from dash import html, dcc, Input, Output, State, ALL, ctx
import dash_bootstrap_components as dbc
import logging

from utils.config import COLORS
from utils.data_utils import (
    get_match_results,
    CURRENT_SEASON,
)
from utils.logos import get_team_logo_path, get_tournament_logo_path
from page_utils.competitions import ALL_COMPETITIONS as _ALL_COMPETITIONS, normalize_competitions as _normalize_competitions

from pages.team_analysis_tabs.overview import build_overview_tab
from pages.team_analysis_tabs.buildup import build_buildup_tab, register_buildup_callbacks
from pages.team_analysis_tabs.chance_creation import build_chance_creation_tab, register_chance_creation_callbacks
from pages.team_analysis_tabs.def_structure import build_def_structure_tab, register_def_structure_callbacks
from pages.team_analysis_tabs.transitions import build_transitions_tab
from pages.team_analysis_tabs.attacking_transition import register_attacking_transition_callbacks
from pages.team_analysis_tabs.defensive_transition import register_defending_transition_callbacks
from pages.team_analysis_tabs.set_pieces import build_set_pieces_tab, register_set_pieces_callbacks

# UI components from shared, and GOLD from visualizations
from pages.match_analysis_tabs.shared import page_header
from page_utils.visualizations import GOLD

logger = logging.getLogger(__name__)

RESULT_COLORS = {
    'W': '#28a745',
    'D': '#ffc107',
    'L': '#dc3545',
}

# ---------------------------------------------------------------------------
# Calendar Builder
# ---------------------------------------------------------------------------

def _build_multi_calendar_grid(year: int, month: int, match_data: list[dict], selected_match_ids: list[str]) -> html.Div:
    """
    Build a monthly calendar grid. Matches are rendered as clickable buttons.
    Supports selecting multiple matches.
    """
    cal = calendar.Calendar(firstweekday=0)
    month_days = cal.monthdayscalendar(year, month)

    matches_by_day = {}
    for m in match_data:
        m_date = str(m.get('date', ''))[:10]
        if len(m_date) == 10:
            m_year, m_month, m_day = int(m_date[:4]), int(m_date[5:7]), int(m_date[8:10])
            if m_year == year and m_month == month:
                matches_by_day.setdefault(m_day, []).append(m)

    days_of_week = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
    header = html.Div(
        [html.Div(d, style={
            'flex': '1', 'textAlign': 'center', 'padding': '8px 0',
            'color': COLORS['text_secondary'], 'fontWeight': 'bold',
            'fontSize': '0.8rem',
        }) for d in days_of_week],
        style={'display': 'flex', 'borderBottom': f'1px solid {COLORS["dark_border"]}'}
    )

    week_rows = []
    for week in month_days:
        day_cells = []
        for day_num in week:
            if day_num == 0:
                day_cells.append(html.Div(style={'flex': '1', 'minHeight': '80px'}))
                continue

            day_matches = matches_by_day.get(day_num, [])
            cell_children = [
                html.Div(str(day_num), style={
                    'fontSize': '0.75rem',
                    'color': COLORS['text_secondary'],
                    'marginBottom': '2px',
                })
            ]

            for m in day_matches:
                match_id = m.get('match_id')
                is_selected = match_id in selected_match_ids
                result_color = RESULT_COLORS.get(m.get('result', ''), COLORS['text_secondary'])
                is_home = m.get('is_home', True)
                opponent = m.get('opponent', '???')
                score = f"{m.get('barca_goals', 0)}-{m.get('opponent_goals', 0)}"
                venue_marker = 'H' if is_home else 'A'
                competition = m.get('competition', '')

                opp_logo_path = get_team_logo_path(opponent)
                tourn_logo_path = get_tournament_logo_path(competition)

                logo_children = []
                if opp_logo_path:
                    logo_children.append(html.Img(
                        src=opp_logo_path,
                        style={'height': '20px', 'width': '20px', 'objectFit': 'contain', 'marginRight': '4px', 'flexShrink': '0'},
                    ))
                logo_children.append(html.Span(opponent, style={
                    'fontSize': '0.8rem', 'fontWeight': 'bold', 'color': '#E8E9ED',
                    'lineHeight': '1.2', 'overflow': 'hidden', 'textOverflow': 'ellipsis', 'whiteSpace': 'nowrap',
                }))

                tourn_children = []
                if tourn_logo_path:
                    tourn_children.append(html.Img(
                        src=tourn_logo_path,
                        style={'height': '14px', 'width': '14px', 'objectFit': 'contain', 'marginRight': '3px'},
                    ))
                comp_short = {
                    'La Liga': 'Liga',
                    'Champions League': 'UCL',
                    'Copa del Rey': 'Copa',
                    'Spanish Super Cup': 'Super Cup',
                }.get(competition, competition[:6])
                tourn_children.append(html.Span(comp_short, style={
                    'fontSize': '0.65rem', 'color': COLORS['text_primary'],
                }))

                check_span = html.Span('✓ ', style={
                    'color': GOLD, 'fontSize': '0.7rem',
                    'fontWeight': '700', 'marginRight': '2px',
                }) if is_selected else None

                cell_children.append(
                    html.Button(
                        html.Div([
                            html.Div(([check_span] if check_span else []) + logo_children, style={
                                'display': 'flex', 'alignItems': 'center', 'overflow': 'hidden',
                            }),
                            html.Div([
                                html.Span(f"{score} ({venue_marker})", style={
                                    'fontSize': '0.7rem', 'color': GOLD if is_selected else result_color,
                                    'fontWeight': 'bold', 'marginRight': '6px',
                                }),
                                html.Span(tourn_children, style={
                                    'display': 'inline-flex', 'alignItems': 'center',
                                    'backgroundColor': 'rgba(255, 255, 255, 0.08)',
                                    'borderRadius': '3px', 'padding': '1px 4px',
                                }),
                            ], style={'display': 'flex', 'alignItems': 'center', 'marginTop': '2px'}),
                        ]),
                        id={'type': 'ta-cal-match-btn', 'match_id': m['match_id']},
                        n_clicks=0,
                        style={
                            'background': 'rgba(237, 187, 0, 0.15)' if is_selected else 'none',
                            'border': 'none',
                            'borderLeft': f'3px solid {GOLD if is_selected else result_color}',
                            'padding': '4px 6px', 'cursor': 'pointer',
                            'width': '100%', 'textAlign': 'left',
                            'borderRadius': '0 4px 4px 0',
                            'marginBottom': '2px',
                        },
                    )
                )

            has_match = len(day_matches) > 0
            cell_style = {
                'flex': '1', 'minHeight': '80px', 'padding': '4px',
                'borderRight': f'1px solid {COLORS["dark_border"]}',
                'borderBottom': f'1px solid {COLORS["dark_border"]}',
            }
            if has_match:
                cell_style['backgroundColor'] = '#2A2F4A'
                cell_style['borderBottom'] = f'2px solid {GOLD}'
            today = datetime.now()
            if year == today.year and month == today.month and day_num == today.day:
                cell_style['boxShadow'] = f'inset 0 0 0 1px {GOLD}'

            day_cells.append(html.Div(cell_children, style=cell_style))

        week_rows.append(html.Div(day_cells, style={'display': 'flex'}))

    return html.Div([header] + week_rows, style={
        'border': f'1px solid {COLORS["dark_border"]}',
        'borderRadius': '8px', 'overflow': 'hidden',
        'backgroundColor': COLORS['dark_secondary'],
    })


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

    @app.callback(
        Output('ta-calendar-month', 'data'),
        Output('ta-month-label', 'children'),
        Input('ta-prev-month', 'n_clicks'),
        Input('ta-next-month', 'n_clicks'),
        State('ta-calendar-month', 'data'),
        prevent_initial_call=True,
    )
    def navigate_month(prev_clicks, next_clicks, current):
        triggered = ctx.triggered_id
        year, month = current['year'], current['month']
        if triggered == 'ta-prev-month':
            month -= 1
            if month < 1:
                month, year = 12, year - 1
        elif triggered == 'ta-next-month':
            month += 1
            if month > 12:
                month, year = 1, year + 1
        return {'year': year, 'month': month}, f"{calendar.month_name[month]} {year}"

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
        Output('ta-selected-matches', 'data'),
        Input({'type': 'ta-cal-match-btn', 'match_id': ALL}, 'n_clicks'),
        Input('ta-clear-selection-btn', 'n_clicks'),
        State('ta-selected-matches', 'data'),
        prevent_initial_call=True,
    )
    def update_selected_matches(n_clicks_list, clear_n_clicks, current_matches):
        if not ctx.triggered_id:
            return current_matches
        if ctx.triggered_id == 'ta-clear-selection-btn':
            return []
            
        # Prevent callback from firing just because new calendar buttons are rendered
        trigger = ctx.triggered[0]
        if trigger['value'] is None or trigger['value'] == 0:
            return current_matches
            
        match_id = ctx.triggered_id['match_id']
        if current_matches is None:
            current_matches = []
        if match_id in current_matches:
            current_matches.remove(match_id)
        else:
            current_matches.append(match_id)
        return current_matches

    @app.callback(
        Output('ta-selected-indicator-text', 'children'),
        Output('ta-clear-selection-btn', 'style'),
        Input('ta-selected-matches', 'data'),
    )
    def update_selected_indicator(match_ids):
        if not match_ids:
            return html.Div("All Matches (Default)", style={'color': COLORS['text_secondary'], 'fontSize': '0.9rem'}), {'display': 'none'}
        
        count = len(match_ids)
        text = html.Span(f"{count} Match{'es' if count > 1 else ''} Selected", style={
            'color': GOLD, 'fontWeight': 'bold', 'marginRight': '12px', 'fontSize': '0.95rem',
        })
        btn_style = {
            'display': 'inline-block', 'background': 'none', 'border': f'1px solid {COLORS["dark_border"]}',
            'color': COLORS['text_primary'], 'borderRadius': '4px', 'padding': '4px 10px', 'cursor': 'pointer', 'fontSize': '0.8rem',
        }
        return text, btn_style

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
