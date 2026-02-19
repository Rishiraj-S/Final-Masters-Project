"""
CuléVision - Match Analysis Page

Orchestrator module that wires together the layout shell (calendar selector + tabs)
and delegates rendering of each tab to specialised modules inside
``match_analysis_tabs/``.

Tab modules:
    overview.py     -- Match Overview (TV-style stat bars)
    possession.py   -- Organised Possession
    transitions.py  -- Transitions
    set_pieces.py   -- Set Pieces
    contested.py    -- Contested Phases
"""

import calendar
from datetime import datetime

from dash import html, dcc, ctx, ALL
from dash.dependencies import Input, Output, State
import dash_bootstrap_components as dbc

from utils.config import COLORS
from utils.data_utils import get_match_results, get_match_events
from utils.logos import (
    get_team_logo_path, get_tournament_logo_path,
    team_logo_img, tournament_logo_img,
)

from .match_analysis_tabs import (
    build_overview_tab,
    build_attack_tab,
    build_attacking_transition_tab,
    build_defence_tab,
    build_defensive_transition_tab,
    build_setpieces_tab,
)
from .match_analysis_tabs.shared import page_header

GOLD = COLORS['gold']
RESULT_COLORS = {'W': '#28a745', 'D': '#ffc107', 'L': '#dc3545'}


# =============================================================================
# Calendar builder
# =============================================================================

def _build_calendar_grid(year, month, matches):
    """Build a calendar grid for the given month with match markers."""
    # Index matches by day
    matches_by_day = {}
    for m in matches:
        try:
            d = datetime.strptime(str(m['date'])[:10], '%Y-%m-%d')
            if d.year == year and d.month == month:
                matches_by_day.setdefault(d.day, []).append(m)
        except (ValueError, TypeError):
            continue

    cal = calendar.Calendar(firstweekday=0)  # Monday first
    weeks = cal.monthdayscalendar(year, month)

    # Header row (day names)
    day_names = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
    header = html.Div(
        [html.Div(d, style={
            'flex': '1', 'textAlign': 'center', 'padding': '8px 0',
            'color': COLORS['text_secondary'], 'fontWeight': 'bold',
            'fontSize': '0.8rem',
        }) for d in day_names],
        style={'display': 'flex', 'borderBottom': f'1px solid {COLORS["dark_border"]}'}
    )

    # Week rows
    week_rows = []
    for week in weeks:
        day_cells = []
        for day_num in week:
            if day_num == 0:
                day_cells.append(html.Div(
                    style={'flex': '1', 'minHeight': '80px'}
                ))
            else:
                day_matches = matches_by_day.get(day_num, [])
                cell_children = [
                    html.Div(str(day_num), style={
                        'fontSize': '0.75rem', 'color': COLORS['text_secondary'],
                        'marginBottom': '2px',
                    })
                ]

                for m in day_matches:
                    result_color = RESULT_COLORS.get(m.get('result', ''), COLORS['text_secondary'])
                    is_home = m.get('is_home', True)
                    opponent = m.get('opponent', '???')
                    score = f"{m.get('barca_goals', 0)}-{m.get('opponent_goals', 0)}"
                    venue_marker = 'H' if is_home else 'A'
                    competition = m.get('competition', '')

                    # Build logo + team name row
                    opp_logo_path = get_team_logo_path(opponent)
                    tourn_logo_path = get_tournament_logo_path(competition)

                    logo_children = []
                    if opp_logo_path:
                        logo_children.append(html.Img(
                            src=opp_logo_path,
                            style={'height': '20px', 'width': '20px',
                                   'objectFit': 'contain', 'marginRight': '4px',
                                   'flexShrink': '0'},
                        ))
                    logo_children.append(html.Span(opponent, style={
                        'fontSize': '0.8rem', 'fontWeight': 'bold',
                        'color': '#E8E9ED', 'lineHeight': '1.2',
                        'overflow': 'hidden', 'textOverflow': 'ellipsis',
                        'whiteSpace': 'nowrap',
                    }))

                    # Tournament badge
                    tourn_children = []
                    if tourn_logo_path:
                        tourn_children.append(html.Img(
                            src=tourn_logo_path,
                            style={'height': '14px', 'width': '14px',
                                   'objectFit': 'contain', 'marginRight': '3px'},
                        ))
                    # Short competition label
                    comp_short = {
                        'La Liga': 'Liga',
                        'Champions League': 'UCL',
                        'Copa del Rey': 'Copa',
                        'Spanish Super Cup': 'Super Cup',
                    }.get(competition, competition[:6])
                    tourn_children.append(html.Span(comp_short, style={
                        'fontSize': '0.65rem', 'color': COLORS['text_primary'],
                    }))

                    cell_children.append(
                        html.Button(
                            html.Div([
                                # Opponent logo + name
                                html.Div(logo_children, style={
                                    'display': 'flex', 'alignItems': 'center',
                                    'overflow': 'hidden',
                                }),
                                # Score + venue + tournament
                                html.Div([
                                    html.Span(f"{score} ({venue_marker})", style={
                                        'fontSize': '0.7rem', 'color': result_color,
                                        'fontWeight': 'bold', 'marginRight': '6px',
                                    }),
                                    html.Span(tourn_children, style={
                                        'display': 'inline-flex', 'alignItems': 'center',
                                        'backgroundColor': 'rgba(255, 255, 255, 0.08)',
                                        'borderRadius': '3px', 'padding': '1px 4px',
                                    }),
                                ], style={
                                    'display': 'flex', 'alignItems': 'center',
                                    'marginTop': '2px',
                                }),
                            ]),
                            id={'type': 'cal-match-btn', 'match_id': m['match_id']},
                            n_clicks=0,
                            style={
                                'background': 'none', 'border': 'none',
                                'borderLeft': f'3px solid {result_color}',
                                'padding': '4px 6px', 'cursor': 'pointer',
                                'width': '100%', 'textAlign': 'left',
                                'borderRadius': '0 4px 4px 0',
                                'marginBottom': '2px',
                            },
                        )
                    )

                has_match = len(day_matches) > 0
                cell_style = {
                    'flex': '1', 'minHeight': '90px', 'padding': '4px',
                    'borderRight': f'1px solid {COLORS["dark_border"]}',
                    'borderBottom': f'1px solid {COLORS["dark_border"]}',
                }
                # Highlight match days with a brighter background
                if has_match:
                    cell_style['backgroundColor'] = '#2A2F4A'
                    cell_style['borderBottom'] = f'2px solid {GOLD}'
                # Highlight today
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


# =============================================================================
# Page layout
# =============================================================================

def create_match_analysis_layout():
    """Create the Match Analysis page layout."""
    results = get_match_results()
    results = sorted(results, key=lambda r: str(r['date']))

    competitions = sorted(set(r['competition'] for r in results))
    tournament_options = [{'label': 'All Tournaments', 'value': 'all'}] + [
        {'label': comp, 'value': comp} for comp in competitions
    ]

    match_data = []
    for r in results:
        match_data.append({
            'match_id': r['match_id'],
            'date': str(r['date'])[:10],
            'competition': r['competition'],
            'description': r['description'],
            'home_team': r['home_team'],
            'away_team': r['away_team'],
            'opponent': r.get('opponent', ''),
            'is_home': r.get('is_home', True),
            'barca_goals': r.get('barca_goals', 0),
            'opponent_goals': r.get('opponent_goals', 0),
            'result': r.get('result', ''),
        })

    if match_data:
        latest = match_data[-1]['date']
        init_year = int(latest[:4])
        init_month = int(latest[5:7])
    else:
        now = datetime.now()
        init_year, init_month = now.year, now.month

    default_match_id = match_data[-1]['match_id'] if match_data else None

    tab_style = {'backgroundColor': COLORS['dark_secondary']}
    active_style = {'backgroundColor': COLORS['dark_tertiary'],
                    'borderBottom': f'2px solid {GOLD}'}

    tabs = dbc.Tabs([
        dbc.Tab(label="Match Overview",        tab_id="tab-overview",
                tab_style=tab_style, active_tab_style=active_style),
        dbc.Tab(label="Attack",                tab_id="tab-attack",
                tab_style=tab_style, active_tab_style=active_style),
        dbc.Tab(label="Attacking Transition",  tab_id="tab-attacking-transition",
                tab_style=tab_style, active_tab_style=active_style),
        dbc.Tab(label="Defence",               tab_id="tab-defence",
                tab_style=tab_style, active_tab_style=active_style),
        dbc.Tab(label="Defensive Transition",  tab_id="tab-defensive-transition",
                tab_style=tab_style, active_tab_style=active_style),
        dbc.Tab(label="Set Pieces",            tab_id="tab-setpieces",
                tab_style=tab_style, active_tab_style=active_style),
    ], id="pma-tabs", active_tab="tab-overview", className="mb-4")

    month_name = calendar.month_name[init_month]

    return dbc.Container([
        dcc.Store(id='pma-match-data', data=match_data),
        dcc.Store(id='pma-calendar-month', data={'year': init_year, 'month': init_month}),
        dcc.Store(id='pma-selected-match', data=default_match_id),

        page_header("Match Analysis"),
        html.Hr(),

        # Calendar controls row
        dbc.Row([
            # Tournament filter
            dbc.Col([
                html.Label("Filter by Tournament:",
                           style={'color': COLORS['text_secondary'], 'fontSize': '0.85rem'}),
                dcc.Dropdown(
                    id='pma-tournament-selector',
                    options=tournament_options,
                    value='all',
                    clearable=False,
                    className="culevision-dropdown mb-2",
                ),
            ], md=3),

            # Month navigation
            dbc.Col([
                html.Div([
                    html.Button("◀", id='pma-prev-month', n_clicks=0, style={
                        'background': 'none', 'border': f'1px solid {COLORS["dark_border"]}',
                        'color': COLORS['text_primary'], 'borderRadius': '6px',
                        'padding': '6px 14px', 'cursor': 'pointer', 'fontSize': '1rem',
                    }),
                    html.H4(id='pma-month-label',
                             children=f"{month_name} {init_year}",
                             className="mb-0 mx-4",
                             style={'color': COLORS['text_primary'], 'display': 'inline'}),
                    html.Button("▶", id='pma-next-month', n_clicks=0, style={
                        'background': 'none', 'border': f'1px solid {COLORS["dark_border"]}',
                        'color': COLORS['text_primary'], 'borderRadius': '6px',
                        'padding': '6px 14px', 'cursor': 'pointer', 'fontSize': '1rem',
                    }),
                ], style={'display': 'flex', 'alignItems': 'center', 'justifyContent': 'center',
                          'paddingTop': '22px'}),
            ], md=5),

            # Selected match indicator
            dbc.Col([
                html.Div(id='pma-selected-indicator', style={'paddingTop': '10px'}),
            ], md=4),
        ], className="mb-3"),

        # Calendar grid
        html.Div(id='pma-calendar-container', className="mb-4"),

        tabs,
        html.Div(id='pma-tab-content'),
    ], fluid=True, className="py-4")


# =============================================================================
# Callback registration
# =============================================================================

def register_match_analysis_callbacks(app):
    """Register all callbacks for the match analysis page."""

    # --- Month navigation ---
    @app.callback(
        Output('pma-calendar-month', 'data'),
        Output('pma-month-label', 'children'),
        Input('pma-prev-month', 'n_clicks'),
        Input('pma-next-month', 'n_clicks'),
        State('pma-calendar-month', 'data'),
        prevent_initial_call=True,
    )
    def navigate_month(prev_clicks, next_clicks, current):
        triggered = ctx.triggered_id
        year, month = current['year'], current['month']

        if triggered == 'pma-prev-month':
            month -= 1
            if month < 1:
                month, year = 12, year - 1
        elif triggered == 'pma-next-month':
            month += 1
            if month > 12:
                month, year = 1, year + 1

        label = f"{calendar.month_name[month]} {year}"
        return {'year': year, 'month': month}, label

    # --- Render calendar grid ---
    @app.callback(
        Output('pma-calendar-container', 'children'),
        Input('pma-calendar-month', 'data'),
        Input('pma-tournament-selector', 'value'),
        Input('pma-match-data', 'data'),
    )
    def render_calendar(cal_month, tournament, match_data):
        if not match_data:
            return html.P("No match data available.",
                          style={'color': COLORS['text_secondary']})

        year, month = cal_month['year'], cal_month['month']

        if tournament and tournament != 'all':
            filtered = [m for m in match_data if m['competition'] == tournament]
        else:
            filtered = match_data

        return _build_calendar_grid(year, month, filtered)

    # --- Match selection from calendar click ---
    @app.callback(
        Output('pma-selected-match', 'data'),
        Input({'type': 'cal-match-btn', 'match_id': ALL}, 'n_clicks'),
        State('pma-selected-match', 'data'),
        prevent_initial_call=True,
    )
    def select_match_from_calendar(n_clicks_list, current_match):
        if not ctx.triggered_id:
            return current_match
        return ctx.triggered_id['match_id']

    # --- Selected match indicator ---
    @app.callback(
        Output('pma-selected-indicator', 'children'),
        Input('pma-selected-match', 'data'),
        Input('pma-match-data', 'data'),
    )
    def update_selected_indicator(match_id, match_data):
        if not match_id or not match_data:
            return html.Span("No match selected",
                             style={'color': COLORS['text_secondary'], 'fontSize': '0.85rem'})

        match = next((m for m in match_data if m['match_id'] == match_id), None)
        if not match:
            return html.Span("No match selected",
                             style={'color': COLORS['text_secondary'], 'fontSize': '0.85rem'})

        home_team = match['home_team']
        away_team = match['away_team']
        competition = match.get('competition', '')
        match_date = match.get('date', '')
        venue = 'Home' if match.get('is_home') else 'Away'

        # Format date nicely
        try:
            dt = datetime.strptime(match_date, '%Y-%m-%d')
            formatted_date = dt.strftime('%d %b %Y')
        except (ValueError, TypeError):
            formatted_date = match_date

        return html.Div([
            # Header
            html.Div("Selected Match", style={
                'color': GOLD, 'fontSize': '0.8rem', 'fontWeight': 'bold',
                'marginBottom': '8px', 'letterSpacing': '0.03em',
            }),

            # Tournament badge
            html.Div([
                tournament_logo_img(competition, '16px'),
                html.Span(competition, style={
                    'color': COLORS['text_secondary'], 'fontSize': '0.7rem',
                    'marginLeft': '4px',
                }),
                html.Span(f" · {venue}", style={
                    'color': GOLD, 'fontSize': '0.7rem', 'fontWeight': 'bold',
                }),
            ], style={'display': 'flex', 'alignItems': 'center', 'marginBottom': '6px'}),

            # Teams row with logos
            html.Div([
                # Home team
                team_logo_img(home_team, '28px'),
                html.Span(home_team, style={
                    'color': COLORS['text_primary'], 'fontWeight': 'bold',
                    'fontSize': '0.85rem', 'marginLeft': '6px',
                }),
                # vs
                html.Span("vs", style={
                    'color': COLORS['text_secondary'], 'fontSize': '0.75rem',
                    'margin': '0 8px',
                }),
                # Away team
                team_logo_img(away_team, '28px'),
                html.Span(away_team, style={
                    'color': COLORS['text_primary'], 'fontWeight': 'bold',
                    'fontSize': '0.85rem', 'marginLeft': '6px',
                }),
            ], style={'display': 'flex', 'alignItems': 'center', 'marginBottom': '4px'}),

            # Date
            html.Div(formatted_date, style={
                'color': COLORS['text_secondary'], 'fontSize': '0.75rem',
            }),
        ], style={
            'backgroundColor': COLORS['dark_secondary'],
            'border': f'1px solid {COLORS["dark_border"]}',
            'borderRadius': '8px', 'padding': '10px 14px',
        })

    # --- Tab content ---
    @app.callback(
        Output('pma-tab-content', 'children'),
        Input('pma-selected-match', 'data'),
        Input('pma-tabs', 'active_tab'),
    )
    def update_pma_content(match_id, active_tab):
        if not match_id:
            return html.P("Select a match from the calendar to begin analysis.",
                          style={'color': COLORS['text_secondary']})

        events = get_match_events(match_id)
        if events.empty:
            return html.P("No event data available for this match.",
                          style={'color': COLORS['text_secondary']})

        tab_builders = {
            'tab-overview':              build_overview_tab,
            'tab-attack':                build_attack_tab,
            'tab-attacking-transition':  build_attacking_transition_tab,
            'tab-defence':               build_defence_tab,
            'tab-defensive-transition':  build_defensive_transition_tab,
            'tab-setpieces':             build_setpieces_tab,
        }

        builder = tab_builders.get(active_tab, build_overview_tab)
        return builder(events)
