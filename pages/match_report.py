"""
CuléVision - Match Report Page

Orchestrates the calendar selector, score headline, and a single scrolling
page of all match-analysis sections, delegating rendering to the modules
inside ``match_analysis_tabs/``.
"""

import calendar
import logging
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
from utils.match_data_adapter import get_match_metadata, compute_team_kpis

from page_utils.visualizations import GOLD, CHART_CONFIG

from .match_analysis_tabs import (
    build_overview_tab,
    register_overview_callbacks,
    build_attacking_output_tab,
    build_build_up_passing_tab,
    register_build_up_passing_callbacks,
    build_defensive_structure_tab,
    register_defensive_structure_callbacks,
    build_transitions_counterpressing_tab,
    register_transitions_counterpressing_callbacks,
    build_goalkeeping_tab,
    register_goalkeeping_callbacks,
    build_player_stats_tab,
    register_player_stats_callbacks,
    build_attack_radar,
    build_def_radar,
    build_bup_radar,
)
from .match_analysis_tabs.shared import page_header  # re-exported for other pages

log = logging.getLogger(__name__)

RESULT_COLORS = {'W': '#28a745', 'D': '#ffc107', 'L': '#dc3545'}


# =============================================================================
# Calendar builder
# =============================================================================

def _build_calendar_grid(year, month, matches, selected_match_id=None):
    matches_by_day = {}
    for m in matches:
        try:
            d = datetime.strptime(str(m['date'])[:10], '%Y-%m-%d')
            if d.year == year and d.month == month:
                matches_by_day.setdefault(d.day, []).append(m)
        except (ValueError, TypeError):
            continue

    cal = calendar.Calendar(firstweekday=0)
    weeks = cal.monthdayscalendar(year, month)

    day_names = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
    header = html.Div(
        [html.Div(d, style={
            'flex': '1', 'textAlign': 'center', 'padding': '8px 0',
            'color': COLORS['text_secondary'], 'fontWeight': 'bold', 'fontSize': '0.8rem',
        }) for d in day_names],
        style={'display': 'flex', 'borderBottom': f'1px solid {COLORS["dark_border"]}'}
    )

    week_rows = []
    for week in weeks:
        day_cells = []
        for day_num in week:
            if day_num == 0:
                day_cells.append(html.Div(style={'flex': '1', 'minHeight': '80px'}))
            else:
                day_matches = matches_by_day.get(day_num, [])
                cell_children = [
                    html.Div(str(day_num), style={
                        'fontSize': '0.75rem', 'color': COLORS['text_secondary'],
                        'marginBottom': '2px',
                    })
                ]
                for m in day_matches:
                    match_id = m.get('match_id')
                    is_selected = str(match_id) == str(selected_match_id) if selected_match_id else False
                    result_color = RESULT_COLORS.get(m.get('result', ''), COLORS['text_secondary'])
                    is_home = m.get('is_home', True)
                    opponent = m.get('opponent', '???')
                    score = f"{m.get('barca_goals', 0)}-{m.get('opponent_goals', 0)}"
                    venue_marker = 'H' if is_home else 'A'
                    competition = m.get('competition', '')
                    opp_logo_path   = get_team_logo_path(opponent)
                    tourn_logo_path = get_tournament_logo_path(competition)

                    logo_children = []
                    if opp_logo_path:
                        logo_children.append(html.Img(
                            src=opp_logo_path,
                            style={'height': '20px', 'width': '20px', 'objectFit': 'contain',
                                   'marginRight': '4px', 'flexShrink': '0'},
                        ))
                    logo_children.append(html.Span(opponent, style={
                        'fontSize': '0.8rem', 'fontWeight': 'bold', 'color': '#E8E9ED',
                        'lineHeight': '1.2', 'overflow': 'hidden',
                        'textOverflow': 'ellipsis', 'whiteSpace': 'nowrap',
                    }))

                    tourn_children = []
                    if tourn_logo_path:
                        tourn_children.append(html.Img(
                            src=tourn_logo_path,
                            style={'height': '14px', 'width': '14px',
                                   'objectFit': 'contain', 'marginRight': '3px'},
                        ))
                    comp_short = {
                        'La Liga': 'Liga', 'Champions League': 'UCL',
                        'Copa del Rey': 'Copa', 'Spanish Super Cup': 'Super Cup',
                    }.get(competition, competition[:6])
                    tourn_children.append(html.Span(comp_short, style={
                        'fontSize': '0.65rem', 'color': COLORS['text_primary'],
                    }))

                    check_span = html.Span(
                        '✓ ', style={'color': GOLD, 'fontSize': '0.7rem',
                                     'fontWeight': '700', 'marginRight': '2px'},
                    ) if is_selected else None

                    cell_children.append(
                        html.Button(
                            html.Div([
                                html.Div(([check_span] if check_span else []) + logo_children, style={
                                    'display': 'flex', 'alignItems': 'center', 'overflow': 'hidden',
                                }),
                                html.Div([
                                    html.Span(f"{score} ({venue_marker})", style={
                                        'fontSize': '0.7rem',
                                        'color': GOLD if is_selected else result_color,
                                        'fontWeight': 'bold', 'marginRight': '6px',
                                    }),
                                    html.Span(tourn_children, style={
                                        'display': 'inline-flex', 'alignItems': 'center',
                                        'backgroundColor': 'rgba(255,255,255,0.08)',
                                        'borderRadius': '3px', 'padding': '1px 4px',
                                    }),
                                ], style={'display': 'flex', 'alignItems': 'center',
                                          'marginTop': '2px'}),
                            ]),
                            id={'type': 'cal-match-btn', 'match_id': m['match_id']},
                            n_clicks=0,
                            style={
                                'background': 'rgba(237,187,0,0.15)' if is_selected else 'none',
                                'border': 'none',
                                'borderLeft': f'3px solid {GOLD if is_selected else result_color}',
                                'padding': '4px 6px', 'cursor': 'pointer',
                                'width': '100%', 'textAlign': 'left',
                                'borderRadius': '0 4px 4px 0', 'marginBottom': '2px',
                            },
                        )
                    )

                cell_style = {
                    'flex': '1', 'minHeight': '90px', 'padding': '4px',
                    'borderRight': f'1px solid {COLORS["dark_border"]}',
                    'borderBottom': f'1px solid {COLORS["dark_border"]}',
                }
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
# Section shell — static skeleton; each section loaded by its own callback
# =============================================================================

_SECTIONS = [
    ("overview",    "Overview"),
    ("attack",      "Attack"),
    ("buildup",     "Build-Up & Passing"),
    ("defense",     "Defense"),
    ("transitions", "Transitions & Counterpressing"),
    ("goalkeeping", "Goalkeeping"),
    ("playerstats", "Player Stats"),
]


def _section_divider(title):
    return html.Div(title, style={
        'color': GOLD, 'fontWeight': '800', 'fontSize': '1.1rem',
        'letterSpacing': '1px', 'textTransform': 'uppercase',
        'paddingTop': '32px', 'paddingBottom': '10px',
        'borderBottom': f'2px solid {GOLD}', 'marginBottom': '20px',
        'textAlign': 'center',
    })


def _sections_shell():
    children = []
    for key, title in _SECTIONS:
        if key == 'attack':
            children.append(
                dcc.Loading(
                    type='circle', color=GOLD,
                    children=html.Div(id='pma-radars'),
                )
            )
        children.append(_section_divider(title))
        children.append(
            dcc.Loading(
                type='circle', color=GOLD,
                children=html.Div(id=f'pma-sec-{key}'),
            )
        )
    return html.Div(children)


# =============================================================================
# Page layout
# =============================================================================

def create_match_analysis_layout():
    results = get_match_results()
    results = sorted(results, key=lambda r: str(r['date']))
    competitions = sorted(set(r['competition'] for r in results))
    tournament_options = [{'label': 'All Tournaments', 'value': 'all'}] + [
        {'label': comp, 'value': comp} for comp in competitions
    ]
    match_data = []
    for r in results:
        match_data.append({
            'match_id':       r['match_id'],
            'date':           str(r['date'])[:10],
            'competition':    r['competition'],
            'description':    r['description'],
            'home_team':      r['home_team'],
            'away_team':      r['away_team'],
            'opponent':       r.get('opponent', ''),
            'is_home':        r.get('is_home', True),
            'barca_goals':    r.get('barca_goals', 0),
            'opponent_goals': r.get('opponent_goals', 0),
            'result':         r.get('result', ''),
        })
    if match_data:
        latest_match    = max(match_data, key=lambda m: str(m['date']))
        default_match_id = latest_match['match_id']
        latest          = latest_match['date']
        init_year       = int(latest[:4])
        init_month      = int(latest[5:7])
    else:
        now = datetime.now()
        init_year, init_month = now.year, now.month
        default_match_id = None

    month_name = calendar.month_name[init_month]
    return dbc.Container([
        dcc.Store(id='pma-match-data',      data=match_data),
        dcc.Store(id='pma-calendar-month',  data={'year': init_year, 'month': init_month}),
        dcc.Store(id='pma-selected-match',  data=default_match_id),
        html.H2("Match Report", style={'color': COLORS['text_primary'], 'fontWeight': 'bold',
                                        'textAlign': 'center'}),
        html.Hr(),
        dbc.Row([
            dbc.Col([
                html.Label("Filter by Tournament:",
                           style={'color': COLORS['text_secondary'], 'fontSize': '0.85rem'}),
                dcc.Dropdown(
                    id='pma-tournament-selector',
                    options=tournament_options, value='all',
                    clearable=False, className="culevision-dropdown mb-2",
                ),
            ], md=3),
            dbc.Col([
                html.Div([
                    html.Button("◀", id='pma-prev-month', n_clicks=0, style={
                        'background': 'none', 'border': f'1px solid {COLORS["dark_border"]}',
                        'color': COLORS['text_primary'], 'borderRadius': '6px',
                        'padding': '6px 14px', 'cursor': 'pointer', 'fontSize': '1rem',
                    }),
                    html.H4(id='pma-month-label', children=f"{month_name} {init_year}",
                            className="mb-0 mx-4",
                            style={'color': COLORS['text_primary'], 'display': 'inline'}),
                    html.Button("▶", id='pma-next-month', n_clicks=0, style={
                        'background': 'none', 'border': f'1px solid {COLORS["dark_border"]}',
                        'color': COLORS['text_primary'], 'borderRadius': '6px',
                        'padding': '6px 14px', 'cursor': 'pointer', 'fontSize': '1rem',
                    }),
                ], style={'display': 'flex', 'alignItems': 'center',
                          'justifyContent': 'center', 'paddingTop': '22px'}),
            ], md=5),
            dbc.Col([html.Div(id='pma-selected-indicator', style={'paddingTop': '10px'})], md=4),
        ], className="mb-3"),
        html.Div(id='pma-calendar-container', className="mb-4"),
        html.Div(
            html.A(
                [html.I(className="fas fa-file-pdf", style={'marginRight': '8px'}),
                 "Download Match Report"],
                id='pma-report-link', href='#', target='_blank', className='report-btn',
                style={
                    'display': 'inline-block', 'backgroundColor': GOLD, 'color': '#1A1D2E',
                    'border': 'none', 'borderRadius': '8px', 'padding': '10px 22px',
                    'cursor': 'pointer', 'fontWeight': '700', 'fontSize': '0.88rem',
                    'letterSpacing': '0.03em', 'textDecoration': 'none',
                },
            ),
            className="mb-3",
        ),
        html.Div(id='pma-score-headline', className="mb-3"),
        _sections_shell(),
    ], fluid=True, className="py-4")


# =============================================================================
# Callbacks
# =============================================================================

def register_match_analysis_callbacks(app):

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
        return {'year': year, 'month': month}, f"{calendar.month_name[month]} {year}"

    @app.callback(
        Output('pma-calendar-container', 'children'),
        Input('pma-calendar-month', 'data'),
        Input('pma-tournament-selector', 'value'),
        Input('pma-match-data', 'data'),
        Input('pma-selected-match', 'data'),
    )
    def render_calendar(cal_month, tournament, match_data, selected_match_id):
        if not match_data:
            return html.P("No match data available.", style={'color': COLORS['text_secondary']})
        year, month = cal_month['year'], cal_month['month']
        filtered = ([m for m in match_data if m['competition'] == tournament]
                    if tournament and tournament != 'all' else match_data)
        return _build_calendar_grid(year, month, filtered, selected_match_id)

    @app.callback(
        Output('pma-selected-match', 'data'),
        Input({'type': 'cal-match-btn', 'match_id': ALL}, 'n_clicks'),
        State('pma-selected-match', 'data'),
        prevent_initial_call=True,
    )
    def select_match_from_calendar(n_clicks_list, current_match):
        if not ctx.triggered_id or not any(n_clicks_list):
            return current_match
        return ctx.triggered_id['match_id']

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
        home_team   = match['home_team']
        away_team   = match['away_team']
        competition = match.get('competition', '')
        match_date  = match.get('date', '')
        venue       = 'Home' if match.get('is_home') else 'Away'
        try:
            dt = datetime.strptime(match_date, '%Y-%m-%d')
            formatted_date = dt.strftime('%d %b %Y')
        except (ValueError, TypeError):
            formatted_date = match_date
        return html.Div([
            html.Div("Selected Match", style={
                'color': GOLD, 'fontSize': '0.8rem', 'fontWeight': 'bold',
                'marginBottom': '8px', 'letterSpacing': '0.03em',
            }),
            html.Div([
                tournament_logo_img(competition, '16px'),
                html.Span(competition, style={'color': COLORS['text_secondary'],
                                              'fontSize': '0.7rem', 'marginLeft': '4px'}),
                html.Span(f" · {venue}", style={'color': GOLD, 'fontSize': '0.7rem',
                                                'fontWeight': 'bold'}),
            ], style={'display': 'flex', 'alignItems': 'center', 'marginBottom': '6px'}),
            html.Div([
                team_logo_img(home_team, '28px'),
                html.Span(home_team, style={'color': COLORS['text_primary'], 'fontWeight': 'bold',
                                            'fontSize': '0.85rem', 'marginLeft': '6px'}),
                html.Span("vs", style={'color': COLORS['text_secondary'], 'fontSize': '0.75rem',
                                       'margin': '0 8px'}),
                team_logo_img(away_team, '28px'),
                html.Span(away_team, style={'color': COLORS['text_primary'], 'fontWeight': 'bold',
                                            'fontSize': '0.85rem', 'marginLeft': '6px'}),
            ], style={'display': 'flex', 'alignItems': 'center', 'marginBottom': '4px'}),
            html.Div(formatted_date, style={'color': COLORS['text_secondary'],
                                            'fontSize': '0.75rem'}),
        ], style={
            'backgroundColor': COLORS['dark_secondary'],
            'border': f'1px solid {COLORS["dark_border"]}',
            'borderRadius': '8px', 'padding': '10px 14px',
        })

    @app.callback(
        Output('pma-score-headline', 'children'),
        Input('pma-selected-match', 'data'),
    )
    def update_score_headline(match_id):
        if not match_id:
            return None
        events = get_match_events(match_id)
        if events.empty:
            return None
        meta        = get_match_metadata(events)
        home_kpis   = compute_team_kpis(events, 'home')
        away_kpis   = compute_team_kpis(events, 'away')
        home_team   = meta.get('home_team', 'Home')
        away_team   = meta.get('away_team', 'Away')
        competition = meta.get('competition', '')
        raw_time    = str(meta.get('time', '') or '')
        kickoff_str = raw_time[:5] if len(raw_time) >= 5 else raw_time
        venue       = str(meta.get('venue', '') or '')
        return dbc.Card([dbc.CardBody([
            html.Div([
                html.Div([tournament_logo_img(competition, '80px')], style={
                    'width': '110px', 'height': '110px', 'borderRadius': '50%',
                    'background': GOLD, 'padding': '15px',
                    'display': 'flex', 'alignItems': 'center', 'justifyContent': 'center',
                }),
                html.Div(competition, style={'color': COLORS['text_primary'], 'fontSize': '1rem',
                                             'fontWeight': '500', 'marginTop': '6px'}),
            ], style={'display': 'flex', 'flexDirection': 'column',
                      'alignItems': 'center', 'marginBottom': '16px'}),
            dbc.Row([
                dbc.Col([
                    html.Div([team_logo_img(home_team, '88px')],
                             style={'textAlign': 'right', 'marginBottom': '6px'}),
                    html.H3(home_team, className="text-end mb-0", style={'fontWeight': '600'}),
                    html.Small("Home", className="text-end d-block",
                               style={'color': COLORS['text_secondary']}),
                ], width=4),
                dbc.Col([
                    html.H1(f"{home_kpis['goals']}  -  {away_kpis['goals']}",
                            className="text-center mb-1",
                            style={'color': GOLD, 'fontWeight': '900',
                                   'fontSize': '3.5rem', 'letterSpacing': '0.15em',
                                   # override the global gradient-text h1 rule so the score is gold
                                   'background': 'none', 'WebkitTextFillColor': GOLD,
                                   'WebkitBackgroundClip': 'border-box'}),
                    html.Div([
                        html.I(className="fas fa-clock",
                               style={'marginRight': '5px', 'fontSize': '0.75rem'}),
                        html.Span(f"KO {kickoff_str}" if kickoff_str else ''),
                    ], style={'textAlign': 'center', 'color': COLORS['text_secondary'],
                              'fontSize': '0.82rem', 'marginBottom': '3px'}),
                    html.Div([
                        html.I(className="fas fa-map-marker-alt",
                               style={'marginRight': '5px', 'fontSize': '0.75rem'}),
                        html.Span(venue or '—'),
                    ], style={'textAlign': 'center', 'color': COLORS['text_secondary'],
                              'fontSize': '0.82rem'}),
                ], width=4),
                dbc.Col([
                    html.Div([team_logo_img(away_team, '88px')],
                             style={'textAlign': 'left', 'marginBottom': '6px'}),
                    html.H3(away_team, className="text-start mb-0", style={'fontWeight': '600'}),
                    html.Small("Away", className="text-start d-block",
                               style={'color': COLORS['text_secondary']}),
                ], width=4),
            ], align="center"),
        ])])

    @app.callback(
        Output('pma-radars', 'children'),
        Input('pma-selected-match', 'data'),
    )
    def update_radars(match_id):
        import traceback
        if not match_id:
            return None
        try:
            events = get_match_events(match_id)
            if events.empty:
                return None
            atk_fig = build_attack_radar(events)
            def_fig = build_def_radar(events)
            bup_fig = build_bup_radar(events)
        except Exception as e:
            log.error("Radar section failed: %s\n%s", e, traceback.format_exc())
            return html.P(f"Error rendering radars: {e}",
                          style={'color': '#dc3545', 'fontSize': '0.85rem'})
        for fig in (atk_fig, def_fig, bup_fig):
            if fig is not None:
                fig.update_layout(height=420, margin=dict(l=50, r=50, t=20, b=60))

        _card_style = {
            'backgroundColor': COLORS['dark_secondary'],
            'border': f'1px solid {COLORS["dark_border"]}',
            'borderRadius': '8px', 'padding': '12px 8px',
        }
        _title_style = {
            'color': GOLD, 'fontWeight': '700', 'fontSize': '0.82rem',
            'textAlign': 'center', 'marginBottom': '2px',
            'textTransform': 'uppercase', 'letterSpacing': '0.06em',
        }

        def _radar_col(title, fig):
            body = (
                dcc.Graph(figure=fig, config=CHART_CONFIG)
                if fig is not None
                else html.Div("No data", style={'color': COLORS['text_secondary'],
                                                'textAlign': 'center', 'padding': '40px 0'})
            )
            return dbc.Col(
                html.Div([html.Div(title, style=_title_style), body], style=_card_style),
                lg=4, md=12, className='mb-3',
            )

        return html.Div([
            _section_divider("Performance Radars"),
            dbc.Row([
                _radar_col("Attack", atk_fig),
                _radar_col("Defence", def_fig),
                _radar_col("Possession & Build-Up", bup_fig),
            ], className='g-3'),
        ])

    def _section_cb(sec_id, builder_fn):
        """Register one section callback."""
        import traceback

        @app.callback(
            Output(f'pma-sec-{sec_id}', 'children'),
            Input('pma-selected-match', 'data'),
        )
        def _cb(match_id, _fn=builder_fn, _key=sec_id):
            if not match_id:
                return html.P("Select a match from the calendar.",
                              style={'color': COLORS['text_secondary']})
            events = get_match_events(match_id)
            if events.empty:
                return html.P("No event data available.",
                              style={'color': COLORS['text_secondary']})
            try:
                return _fn(events)
            except Exception as e:
                log.error("Section '%s' failed: %s\n%s", _key, e, traceback.format_exc())
                return html.P(f"Error rendering section: {e}",
                              style={'color': '#dc3545', 'fontSize': '0.85rem'})

    _section_cb("overview",    build_overview_tab)
    _section_cb("attack",      build_attacking_output_tab)
    _section_cb("buildup",     build_build_up_passing_tab)
    _section_cb("defense",     build_defensive_structure_tab)
    _section_cb("transitions", build_transitions_counterpressing_tab)
    _section_cb("goalkeeping", build_goalkeeping_tab)
    _section_cb("playerstats", build_player_stats_tab)

    @app.callback(
        Output('pma-report-link', 'href'),
        Input('pma-selected-match', 'data'),
    )
    def update_report_link(match_id):
        if not match_id:
            return '#'
        return f'/download-report/{match_id}'

    register_overview_callbacks(app)
    register_build_up_passing_callbacks(app)
    register_defensive_structure_callbacks(app)
    register_transitions_counterpressing_callbacks(app)
    register_goalkeeping_callbacks(app)
    register_player_stats_callbacks(app)
