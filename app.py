"""
CuléVision - FC Barcelona Game Analysis Tool
Main Dash Application Orchestrator with Login System

This is the main entry point for the application. It handles:
- App initialization and configuration
- Authentication (login/logout)
- Navigation routing
- Database update functionality

Individual pages are organized in the pages/ directory:
- pages/home.py: Season Overview
- pages/match_report.py: Match Report (phase-based post-match analysis)
- pages/barca_dna.py: Barça DNA (player analysis)
"""

import io
import dash
import flask
from dash import html, dcc, callback_context
import dash_bootstrap_components as dbc
from dash.dependencies import Input, Output, State
import json
import subprocess
import threading
import os
import sys

from utils.config import COLORS, APP_CONFIG, NAV_LINKS
from utils.data_utils import clear_events_cache
from pages import (
    create_home_layout,
    register_home_callbacks,
    create_match_analysis_layout,
    register_match_analysis_callbacks,
    create_player_analysis_layout,
    register_player_analysis_callbacks,
    create_team_analysis_layout,
    register_team_analysis_callbacks,
    create_opposition_analysis_layout,
    register_opposition_analysis_callbacks,
)

# User credentials
USERS = {
    'Guest': {'password': 'guest', 'role': 'guest'},
    'Rishi': {'password': 'admin', 'role': 'admin'}
}

# Initialize the Dash app with Bootstrap theme
app = dash.Dash(
    __name__,
    external_stylesheets=[dbc.themes.BOOTSTRAP],
    suppress_callback_exceptions=True,
    title=APP_CONFIG['title']
)

# ---------------------------------------------------------------------------
# Flask route: PDF match report (bypasses Dash callback timeout)
# ---------------------------------------------------------------------------

@app.server.route('/download-report/<match_id>')
def serve_match_report(match_id):
    try:
        from utils.pdf_report import generate_match_report_pdf
        pdf_bytes = generate_match_report_pdf(match_id)
        return flask.send_file(
            io.BytesIO(pdf_bytes),
            mimetype='application/pdf',
            as_attachment=True,
            download_name=f'match_report_{match_id}.pdf',
        )
    except Exception as exc:
        import logging
        logging.getLogger(__name__).error("PDF route error for %s: %s", match_id, exc)
        return flask.Response(
            f"Error generating report: {exc}",
            status=500,
            mimetype='text/plain',
        )


# Custom CSS for dark theme with login styles
app.index_string = '''
<!DOCTYPE html>
<html>
    <head>
        {%metas%}
        <title>{%title%}</title>
        {%favicon%}
        {%css%}
        <style>
            body {
                background-color: #0A0E27;
                color: #E8E9ED;
            }
            .card {
                background-color: #151932;
                border: 1px solid #2A2F4A;
            }
            .card-header {
                background-color: #1E2139;
                border-bottom: 1px solid #2A2F4A;
            }
            .table {
                color: #E8E9ED;
            }
            .table-dark {
                background-color: #151932;
            }
            .table-striped tbody tr:nth-of-type(odd) {
                background-color: #1E2139;
            }
            .nav-link {
                color: #E8E9ED !important;
            }
            .nav-link:hover {
                color: #EDBB00 !important;
            }
            .nav-link.active {
                color: #EDBB00 !important;
                font-weight: bold;
            }
            .result-badge {
                display: inline-block;
                width: 28px;
                height: 28px;
                line-height: 28px;
                text-align: center;
                border-radius: 4px;
                font-weight: bold;
                font-size: 14px;
            }
            .result-w { background-color: #28a745; color: white; }
            .result-d { background-color: #ffc107; color: black; }
            .result-l { background-color: #dc3545; color: white; }
            .stat-card {
                text-align: center;
                padding: 15px;
            }
            .stat-value {
                font-size: 2.5rem;
                font-weight: bold;
                color: #EDBB00;
            }
            .stat-label {
                font-size: 0.9rem;
                color: #A5A8B8;
            }
            .culevision-brand {
                background: linear-gradient(90deg, #004D98, #A50044);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
                background-clip: text;
            }
            .dash-table-container .dash-spreadsheet-container .dash-spreadsheet-inner table {
                background-color: #151932 !important;
            }
            .login-container {
                min-height: 100vh;
                display: flex;
                align-items: center;
                justify-content: center;
            }
            .login-card {
                width: 400px;
                background-color: #151932;
                border: 1px solid #2A2F4A;
                border-radius: 10px;
                padding: 40px;
            }
            .login-input {
                background-color: #1E2139 !important;
                border: 1px solid #2A2F4A !important;
                color: #E8E9ED !important;
            }
            .login-input:focus {
                background-color: #1E2139 !important;
                border-color: #EDBB00 !important;
                color: #E8E9ED !important;
                box-shadow: 0 0 0 0.2rem rgba(237, 187, 0, 0.25) !important;
            }
            .login-input::placeholder {
                color: #A5A8B8 !important;
            }
            /* Global dark-theme dropdown styles */
            .Select-control {
                background-color: #1E2139 !important;
                border: 1px solid #2A2F4A !important;
            }
            .Select-value-label,
            .Select input {
                color: #E8E9ED !important;
            }
            .Select-placeholder {
                color: #A5A8B8 !important;
            }
            .Select-menu-outer {
                background-color: #1E2139 !important;
                border: 1px solid #2A2F4A !important;
            }
            .VirtualizedSelectOption {
                background-color: #1E2139 !important;
                color: #E8E9ED !important;
            }
            .VirtualizedSelectFocusedOption {
                background-color: #2A2F4A !important;
                color: #EDBB00 !important;
            }
            .Select-arrow {
                border-color: #E8E9ED transparent transparent !important;
            }
            .Select.is-open .Select-arrow {
                border-color: transparent transparent #E8E9ED !important;
            }
            .Select-clear {
                color: #A5A8B8 !important;
            }
            .update-overlay {
                position: fixed;
                top: 0;
                left: 0;
                width: 100%;
                height: 100%;
                background-color: rgba(10, 14, 39, 0.95);
                z-index: 9999;
                display: flex;
                flex-direction: column;
                align-items: center;
                justify-content: center;
            }
            .spinner-border {
                width: 4rem;
                height: 4rem;
            }
            @keyframes pulse {
                0% { opacity: 1; }
                50% { opacity: 0.5; }
                100% { opacity: 1; }
            }
            .pulse-animation {
                animation: pulse 2s infinite;
            }
        </style>
    </head>
    <body>
        {%app_entry%}
        <footer>
            {%config%}
            {%scripts%}
            {%renderer%}
        </footer>
    </body>
</html>
'''


# =============================================================================
# Layout Components
# =============================================================================

def create_login_layout():
    """Create the login page layout."""
    return html.Div([
        html.Div([
            html.Div([
                html.H1("CuléVision", className="culevision-brand text-center mb-2",
                       style={'fontWeight': 'bold', 'fontSize': '3rem'}),
                html.P("FC Barcelona Game Analysis Tool",
                      className="text-center mb-4",
                      style={'color': COLORS['text_secondary']}),
                html.Hr(style={'borderColor': COLORS['dark_border']}),

                # Username dropdown
                html.Label("Username", style={'color': COLORS['text_secondary']}),
                dcc.Dropdown(
                    id='login-username',
                    options=[
                        {'label': 'Guest', 'value': 'Guest'},
                        {'label': 'Rishi (Admin)', 'value': 'Rishi'}
                    ],
                    placeholder='Select user...',
                    className="mb-3",
                    style={'backgroundColor': '#1E2139'}
                ),

                # Password input
                html.Label("Password", style={'color': COLORS['text_secondary']}),
                dbc.Input(
                    id='login-password',
                    type='password',
                    placeholder='Enter password...',
                    className="login-input mb-4"
                ),

                # Error message
                html.Div(id='login-error', className="text-danger mb-3"),

                # Login button
                dbc.Button(
                    "Login",
                    id='login-button',
                    color="warning",
                    className="w-100",
                    style={'fontWeight': 'bold'}
                )
            ], className="login-card")
        ], className="login-container")
    ], style={'backgroundColor': COLORS['dark_bg'], 'minHeight': '100vh'})


def create_navbar(user_info):
    """Create navigation bar with user info and logout."""
    username = user_info.get('username', 'User')
    role = user_info.get('role', 'guest')

    return dbc.Navbar(
        dbc.Container([
            dbc.Row([
                dbc.Col([
                    html.H2("CuléVision", className="mb-0 culevision-brand",
                           style={'fontWeight': 'bold'})
                ], width="auto"),
            ], align="center", className="g-0"),

            dbc.Row([
                dbc.Col([
                    dbc.Nav([
                        dbc.NavItem(dbc.NavLink(link['label'], href=link['href'], active="exact"))
                        for link in NAV_LINKS
                    ], navbar=True, className="ms-auto")
                ])
            ], align="center"),

            dbc.Row([
                dbc.Col([
                    html.Div([
                        html.Span(f"{username}",
                                 style={'color': COLORS['gold'], 'marginRight': '10px', 'fontWeight': 'bold'}),
                        html.Span(f"({role.title()})",
                                 style={'color': COLORS['text_secondary'], 'marginRight': '15px', 'fontSize': '0.85rem'}),
                        dbc.Button("Logout", id='logout-button', color="outline-light", size="sm")
                    ], style={'display': 'flex', 'alignItems': 'center'})
                ], width="auto")
            ], align="center")
        ], fluid=True),
        color=COLORS['primary_blue'],
        dark=True,
        className="mb-4",
        sticky="top"
    )


PROGRESS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             'opta_pipeline', 'logs', 'progress.json')
OPP_PROGRESS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                  'opposition_pipeline', 'logs', 'progress.json')


def _read_progress(progress_file=None):
    """Read the current pipeline progress from the shared JSON file."""
    if progress_file is None:
        progress_file = PROGRESS_FILE
    try:
        if os.path.exists(progress_file):
            with open(progress_file, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception:
        pass
    return {}


def create_update_overlay():
    """Create the database update overlay with live progress."""
    progress = _read_progress(PROGRESS_FILE)

    competition = progress.get('competition', '')
    stage = progress.get('stage', '')
    detail = progress.get('detail', '')
    comp_idx = progress.get('current_competition', 0)
    comp_total = progress.get('total_competitions', 0)
    match_idx = progress.get('current_match', 0)
    match_total = progress.get('total_matches', 0)

    # Build the live status line
    if competition and stage:
        status_text = f"{stage}: {competition}"
        if stage == "Downloading" and match_total > 0:
            detail_text = f"Match {match_idx}/{match_total} — {detail}"
        elif detail:
            detail_text = detail
        else:
            detail_text = ""
        competition_line = f"Competition {comp_idx}/{comp_total}" if comp_total else ""
    else:
        status_text = "Initializing pipeline..."
        detail_text = ""
        competition_line = ""

    match_pct = round(match_idx / match_total * 100) if match_total > 0 else 0
    comp_pct  = round(comp_idx  / comp_total  * 100) if comp_total  > 0 else 0

    info_children = []
    if competition_line:
        info_children.append(
            html.P([html.Strong("Progress: "), competition_line],
                   className="mb-2", style={'color': COLORS['text_primary']})
        )
    info_children.append(
        html.P([html.Strong("Stage: "), status_text],
               className="mb-2", style={'color': COLORS['text_primary']})
    )
    if detail_text:
        info_children.append(
            html.P([html.Strong("Current: "), detail_text],
                   className="mb-2", style={'color': COLORS['gold']})
        )

    # Competition-level progress bar
    if comp_total > 0:
        info_children.append(html.Div([
            html.Div([
                html.Span("Competitions", style={'color': COLORS['text_secondary'], 'fontSize': '0.75rem'}),
                html.Span(f"{comp_idx}/{comp_total}  ({comp_pct}%)",
                          style={'color': COLORS['gold'], 'fontSize': '0.75rem', 'fontWeight': 'bold'}),
            ], style={'display': 'flex', 'justifyContent': 'space-between', 'marginBottom': '4px'}),
            html.Div(html.Div(style={
                'width': f'{comp_pct}%', 'height': '6px',
                'backgroundColor': COLORS['gold'], 'borderRadius': '3px',
                'transition': 'width 0.4s ease',
            }), style={'backgroundColor': '#2A2F4A', 'borderRadius': '3px', 'marginBottom': '10px'}),
        ]))

    # Match-level progress bar
    if match_total > 0:
        info_children.append(html.Div([
            html.Div([
                html.Span("Matches", style={'color': COLORS['text_secondary'], 'fontSize': '0.75rem'}),
                html.Span(f"{match_idx}/{match_total}  ({match_pct}%)",
                          style={'color': '#17a2b8', 'fontSize': '0.75rem', 'fontWeight': 'bold'}),
            ], style={'display': 'flex', 'justifyContent': 'space-between', 'marginBottom': '4px'}),
            html.Div(html.Div(style={
                'width': f'{match_pct}%', 'height': '6px',
                'backgroundColor': '#17a2b8', 'borderRadius': '3px',
                'transition': 'width 0.4s ease',
            }), style={'backgroundColor': '#2A2F4A', 'borderRadius': '3px', 'marginBottom': '10px'}),
        ]))

    info_children.append(
        html.P([html.Strong("Note: "), "Navigation is disabled during this process to ensure data integrity."],
               style={'color': '#ffc107', 'marginTop': '8px'})
    )

    return html.Div([
        html.Div([
            html.Div(className="spinner-border text-warning mb-4", role="status"),
            html.H2("Databases Are Being Updated",
                   style={'color': COLORS['gold'], 'marginBottom': '20px'}),
            html.P("Please wait while the system processes the latest match data...",
                  style={'color': COLORS['text_secondary'], 'fontSize': '1.1rem'}),
            html.Hr(style={'borderColor': COLORS['dark_border'], 'width': '300px', 'margin': '20px auto'}),
            html.Div(info_children,
                     style={'textAlign': 'left', 'maxWidth': '500px', 'margin': '0 auto', 'padding': '20px',
                            'backgroundColor': '#151932', 'borderRadius': '10px', 'border': '1px solid #2A2F4A'}),
            html.Div([
                html.Div(className="spinner-grow spinner-grow-sm text-warning me-2", role="status"),
                html.Span("Processing...", className="pulse-animation", style={'color': COLORS['text_secondary']})
            ], style={'marginTop': '30px'})
        ], style={'textAlign': 'center'})
    ], className="update-overlay", id='update-overlay')


def create_opp_update_overlay():
    """Create the opposition pipeline update overlay with live progress."""
    progress = _read_progress(OPP_PROGRESS_FILE)

    team        = progress.get('team', '')
    competition = progress.get('competition', '')
    stage       = progress.get('stage', '')
    detail      = progress.get('detail', '')
    team_idx    = progress.get('current_team', 0)
    total_teams = progress.get('total_teams', 0)
    match_idx   = progress.get('current_match', 0)
    match_total = progress.get('total_matches', 0)

    if team and stage:
        status_text = f"{stage}: {team}"
        if competition:
            status_text += f"  —  {competition}"
        if stage == "Downloading" and match_total > 0:
            detail_text = f"Match {match_idx}/{match_total} — {detail}"
        elif detail:
            detail_text = detail
        else:
            detail_text = ""
        progress_line = f"Team {team_idx}/{total_teams}" if total_teams else ""
    else:
        status_text   = "Initializing opposition pipeline..."
        detail_text   = ""
        progress_line = ""

    team_pct  = round(team_idx   / total_teams  * 100) if total_teams  > 0 else 0
    match_pct = round(match_idx  / match_total  * 100) if match_total  > 0 else 0

    info_children = []
    if progress_line:
        info_children.append(
            html.P([html.Strong("Progress: "), progress_line],
                   className="mb-2", style={'color': COLORS['text_primary']})
        )
    info_children.append(
        html.P([html.Strong("Stage: "), status_text],
               className="mb-2", style={'color': COLORS['text_primary']})
    )
    if detail_text:
        info_children.append(
            html.P([html.Strong("Current: "), detail_text],
                   className="mb-2", style={'color': '#17a2b8'})
        )

    # Team-level progress bar
    if total_teams > 0:
        info_children.append(html.Div([
            html.Div([
                html.Span("Teams", style={'color': COLORS['text_secondary'], 'fontSize': '0.75rem'}),
                html.Span(f"{team_idx}/{total_teams}  ({team_pct}%)",
                          style={'color': '#17a2b8', 'fontSize': '0.75rem', 'fontWeight': 'bold'}),
            ], style={'display': 'flex', 'justifyContent': 'space-between', 'marginBottom': '4px'}),
            html.Div(html.Div(style={
                'width': f'{team_pct}%', 'height': '6px',
                'backgroundColor': '#17a2b8', 'borderRadius': '3px',
                'transition': 'width 0.4s ease',
            }), style={'backgroundColor': '#2A2F4A', 'borderRadius': '3px', 'marginBottom': '10px'}),
        ]))

    # Match-level progress bar
    if match_total > 0:
        info_children.append(html.Div([
            html.Div([
                html.Span("Matches", style={'color': COLORS['text_secondary'], 'fontSize': '0.75rem'}),
                html.Span(f"{match_idx}/{match_total}  ({match_pct}%)",
                          style={'color': COLORS['gold'], 'fontSize': '0.75rem', 'fontWeight': 'bold'}),
            ], style={'display': 'flex', 'justifyContent': 'space-between', 'marginBottom': '4px'}),
            html.Div(html.Div(style={
                'width': f'{match_pct}%', 'height': '6px',
                'backgroundColor': COLORS['gold'], 'borderRadius': '3px',
                'transition': 'width 0.4s ease',
            }), style={'backgroundColor': '#2A2F4A', 'borderRadius': '3px', 'marginBottom': '10px'}),
        ]))

    info_children.append(
        html.P([html.Strong("Note: "), "Navigation is disabled during this process to ensure data integrity."],
               style={'color': '#ffc107', 'marginTop': '8px'})
    )

    return html.Div([
        html.Div([
            html.Div(className="spinner-border text-info mb-4", role="status"),
            html.H2("Scouting Opposition Databases",
                   style={'color': '#17a2b8', 'marginBottom': '20px'}),
            html.P("Please wait while the system downloads opposition match data...",
                  style={'color': COLORS['text_secondary'], 'fontSize': '1.1rem'}),
            html.Hr(style={'borderColor': COLORS['dark_border'], 'width': '300px', 'margin': '20px auto'}),
            html.Div(info_children,
                     style={'textAlign': 'left', 'maxWidth': '500px', 'margin': '0 auto',
                            'padding': '20px', 'backgroundColor': '#151932',
                            'borderRadius': '10px', 'border': '1px solid #2A2F4A'}),
            html.Div([
                html.Div(className="spinner-grow spinner-grow-sm text-info me-2", role="status"),
                html.Span("Processing...", className="pulse-animation",
                          style={'color': COLORS['text_secondary']})
            ], style={'marginTop': '30px'})
        ], style={'textAlign': 'center'})
    ], className="update-overlay", id='update-overlay')


_PAGE_TITLES = {
    '/match-report': 'Match Report',
    '/barca-dna': 'Barça DNA',
    '/barca-iq': 'Barça IQ',
    '/opposition-analysis': 'Opposition Analysis',
}


def _create_under_development_layout(pathname):
    """Create a placeholder page for tabs that are under development."""
    title = _PAGE_TITLES.get(pathname, 'Page')
    return dbc.Container([
        dbc.Row([
            dbc.Col([
                html.H2(title, style={'color': COLORS['gold']}),
            ])
        ], className="mb-4"),
        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        html.H4("Under Development", className="text-center",
                                style={'color': COLORS['text_primary']}),
                        html.P(f"{title} features are currently under development.",
                               className="text-center",
                               style={'color': COLORS['text_secondary']})
                    ])
                ])
            ])
        ])
    ], fluid=True)


# =============================================================================
# Main App Layout
# =============================================================================

app.layout = html.Div([
    # Session storage
    dcc.Store(id='session-store', storage_type='session'),
    dcc.Store(id='update-status-store', data={'updating': False}),
    dcc.Store(id='opp-update-status-store', data={'updating': False}),

    # Update overlay (hidden by default)
    html.Div(id='update-overlay-container'),

    # Location for URL routing
    dcc.Location(id='url', refresh=False),

    # Separate Location for forcing full page reload after pipeline update
    dcc.Location(id='_refresh-url', refresh=True),

    # Interval for checking update status
    dcc.Interval(id='update-check-interval', interval=2000, disabled=True),

    # Main content container
    html.Div(id='main-container')
], style={'backgroundColor': COLORS['dark_bg'], 'minHeight': '100vh'})


# =============================================================================
# Callbacks - Authentication
# =============================================================================

@app.callback(
    Output('main-container', 'children'),
    Output('url', 'pathname'),
    Input('session-store', 'data'),
    Input('url', 'pathname'),
    State('update-status-store', 'data')
)
def update_main_container(session_data, pathname, update_status):
    """Main routing callback - handles login state and page navigation."""
    # Check if user is logged in
    if not session_data or not session_data.get('logged_in'):
        return create_login_layout(), '/'

    # User is logged in - show main app
    user_info = session_data
    is_admin = user_info.get('role') == 'admin'

    # Create navbar
    navbar = create_navbar(user_info)

    # Determine which page to show based on URL
    if pathname == '/match-report':
        page_content = create_match_analysis_layout()
    elif pathname == '/barca-dna':
        page_content = create_player_analysis_layout()
    elif pathname == '/barca-iq':
        page_content = create_team_analysis_layout()
    elif pathname == '/opposition-analysis':
        page_content = create_opposition_analysis_layout()
    else:
        page_content = create_home_layout(is_admin)
        pathname = '/'

    return html.Div([navbar, html.Div(id='page-content', children=page_content)]), pathname


@app.callback(
    Output('session-store', 'data', allow_duplicate=True),
    Output('login-error', 'children'),
    Input('login-button', 'n_clicks'),
    State('login-username', 'value'),
    State('login-password', 'value'),
    State('session-store', 'data'),
    prevent_initial_call=True
)
def handle_login(login_clicks, username, password, current_session):
    """Handle login button click."""
    if not login_clicks:
        return current_session, ""

    if not username or not password:
        return current_session, "Please select a user and enter password."

    if username in USERS and USERS[username]['password'] == password:
        return {
            'logged_in': True,
            'username': username,
            'role': USERS[username]['role']
        }, ""
    else:
        return current_session, "Invalid credentials. Please try again."


@app.callback(
    Output('session-store', 'data', allow_duplicate=True),
    Input('logout-button', 'n_clicks'),
    prevent_initial_call=True
)
def handle_logout(logout_clicks):
    """Handle logout button click."""
    if logout_clicks:
        return None
    return dash.no_update


# =============================================================================
# Callbacks - Database Update
# =============================================================================

@app.callback(
    Output('update-overlay-container', 'children'),
    Output('_refresh-url', 'pathname'),
    Input('update-status-store', 'data'),
    Input('opp-update-status-store', 'data'),
    prevent_initial_call=True
)
def show_update_overlay(update_status, opp_update_status):
    """Show/hide the database update overlay. Refresh page when update finishes."""
    if update_status and update_status.get('updating'):
        return create_update_overlay(), dash.no_update
    if update_status and update_status.get('finished'):
        return html.Div(), '/'
    if opp_update_status and opp_update_status.get('updating'):
        return create_opp_update_overlay(), dash.no_update
    if opp_update_status and opp_update_status.get('finished'):
        return html.Div(), '/'
    return html.Div(), dash.no_update


@app.callback(
    Output('update-status-store', 'data'),
    Output('opp-update-status-store', 'data'),
    Output('update-check-interval', 'disabled'),
    Input('update-db-button', 'n_clicks'),
    Input('update-opp-run-button', 'n_clicks'),
    Input('update-check-interval', 'n_intervals'),
    State('update-status-store', 'data'),
    State('opp-update-status-store', 'data'),
    State('opp-team-select', 'value'),
    State('opp-comp-select', 'value'),
    State('opp-pipeline-options', 'value'),
    prevent_initial_call=True
)
def handle_database_update(n_clicks, opp_clicks, n_intervals,
                            current_status, opp_status,
                            opp_team, opp_comp, opp_options):
    """Handle pipeline update buttons and monitor progress for both pipelines."""
    ctx = callback_context
    if not ctx.triggered:
        return current_status, opp_status, True

    trigger_id = ctx.triggered[0]['prop_id'].split('.')[0]
    script_dir = os.path.dirname(os.path.abspath(__file__))

    # ── Barcelona pipeline ──────────────────────────────────────────────────
    if trigger_id == 'update-db-button' and n_clicks:
        if hasattr(app, '_update_thread') and app._update_thread.is_alive():
            return {'updating': True}, opp_status, False

        def run_pipeline():
            pipeline_path = os.path.join(script_dir, 'opta_pipeline', 'main.py')
            result = subprocess.run([sys.executable, pipeline_path], cwd=script_dir)
            if result.returncode != 0:
                log_path = os.path.join(script_dir, 'opta_pipeline', 'logs', 'pipeline_error.log')
                os.makedirs(os.path.dirname(log_path), exist_ok=True)
                with open(log_path, 'w') as f:
                    f.write(f"Pipeline exited with code: {result.returncode}\n")
                    f.write("Check opta_pipeline/logs/pipeline.log for details.\n")

        thread = threading.Thread(target=run_pipeline, daemon=True)
        thread.start()
        app._update_thread = thread
        return {'updating': True, 'started': True}, opp_status, False

    # ── Opposition pipeline ─────────────────────────────────────────────────
    if trigger_id == 'update-opp-run-button' and opp_clicks:
        if hasattr(app, '_opp_update_thread') and app._opp_update_thread.is_alive():
            return current_status, {'updating': True}, False

        opp_pipeline_path = os.path.join(script_dir, 'opposition_pipeline', 'main.py')
        cmd = [sys.executable, opp_pipeline_path]
        if opp_team:
            cmd += ['--team', opp_team]
        if opp_comp:
            cmd += ['--competition', opp_comp]
        options = opp_options or []
        if 'force_rescrape' in options:
            cmd.append('--force-rescrape')
        if 'transform_only' in options:
            cmd.append('--transform-only')

        def run_opp_pipeline(cmd=cmd):
            result = subprocess.run(cmd, cwd=script_dir)
            if result.returncode != 0:
                log_path = os.path.join(script_dir, 'opposition_pipeline', 'logs', 'pipeline_error.log')
                os.makedirs(os.path.dirname(log_path), exist_ok=True)
                with open(log_path, 'w') as f:
                    f.write(f"Pipeline exited with code: {result.returncode}\n")
                    f.write("Check opposition_pipeline/logs/pipeline.log for details.\n")

        opp_thread = threading.Thread(target=run_opp_pipeline, daemon=True)
        opp_thread.start()
        app._opp_update_thread = opp_thread
        return current_status, {'updating': True, 'started': True}, False

    # ── Interval: check both threads ────────────────────────────────────────
    if trigger_id == 'update-check-interval':
        barca_alive = hasattr(app, '_update_thread') and app._update_thread.is_alive()
        opp_alive   = hasattr(app, '_opp_update_thread') and app._opp_update_thread.is_alive()

        new_barca = current_status or {}
        new_opp   = opp_status or {}

        if new_barca.get('updating') and not barca_alive:
            clear_events_cache()
            new_barca = {'updating': False, 'finished': True}

        if new_opp.get('updating') and not opp_alive:
            new_opp = {'updating': False, 'finished': True}

        interval_disabled = not (barca_alive or opp_alive)
        return new_barca, new_opp, interval_disabled

    return current_status, opp_status, True



# =============================================================================
# Register Page Callbacks
# =============================================================================

# Register callbacks from page modules
register_home_callbacks(app)
register_match_analysis_callbacks(app)
register_player_analysis_callbacks(app)
register_team_analysis_callbacks(app)
register_opposition_analysis_callbacks(app)


# =============================================================================
# Run the Application
# =============================================================================

if __name__ == '__main__':
    print("\n" + "="*60)
    print("  CuléVision - FC Barcelona Game Analysis Tool")
    print("  Login System Enabled")

    app.run(
        debug=APP_CONFIG['debug'],
        host=APP_CONFIG['host'],
        port=APP_CONFIG['port']
    )
