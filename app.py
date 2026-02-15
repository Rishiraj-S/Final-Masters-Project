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
- pages/match_analysis.py: Match Analysis (phase-based post-match analysis)
- pages/team_insights.py: Player Analysis
- pages/opposition_analysis.py: Opposition Analysis
"""

import dash
from dash import html, dcc, callback_context
import dash_bootstrap_components as dbc
from dash.dependencies import Input, Output, State
import json
import subprocess
import threading
import os
import sys

from utils.config import COLORS, APP_CONFIG, NAV_LINKS
from pages import (
    create_home_layout,
    register_home_callbacks,
    register_match_analysis_callbacks,
    register_team_insights_callbacks,
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


def _read_progress():
    """Read the current pipeline progress from the shared JSON file."""
    try:
        if os.path.exists(PROGRESS_FILE):
            with open(PROGRESS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception:
        pass
    return {}


def create_update_overlay():
    """Create the database update overlay with live progress."""
    progress = _read_progress()

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
    info_children.append(
        html.P([html.Strong("Note: "), "Navigation is disabled during this process to ensure data integrity."],
               style={'color': '#ffc107'})
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


_PAGE_TITLES = {
    '/match-analysis': 'Match Analysis',
    '/player-analysis': 'Player Analysis',
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
    if pathname in ('/match-analysis', '/player-analysis', '/opposition-analysis'):
        page_content = _create_under_development_layout(pathname)
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
    Input('update-check-interval', 'n_intervals'),
    prevent_initial_call=True
)
def show_update_overlay(update_status, _n_intervals):
    """Show/hide the database update overlay. Refresh page when update finishes."""
    if update_status and update_status.get('updating'):
        return create_update_overlay(), dash.no_update
    if update_status and update_status.get('finished'):
        # Pipeline finished — force a full page reload to pick up new data
        return html.Div(), '/'
    return html.Div(), dash.no_update


@app.callback(
    Output('update-status-store', 'data'),
    Output('update-check-interval', 'disabled'),
    Input('update-db-button', 'n_clicks'),
    Input('update-check-interval', 'n_intervals'),
    State('update-status-store', 'data'),
    prevent_initial_call=True
)
def handle_database_update(n_clicks, n_intervals, current_status):
    """Handle database update button and monitor update progress."""
    ctx = callback_context
    if not ctx.triggered:
        return current_status, True

    trigger_id = ctx.triggered[0]['prop_id'].split('.')[0]

    if trigger_id == 'update-db-button' and n_clicks:
        # Start the database update process
        def run_pipeline():
            script_dir = os.path.dirname(os.path.abspath(__file__))
            pipeline_path = os.path.join(script_dir, 'opta_pipeline', 'main.py')
            subprocess.run([sys.executable, pipeline_path], cwd=script_dir)

        # Start update in background thread
        thread = threading.Thread(target=run_pipeline, daemon=True)
        thread.start()

        # Store the thread reference (we'll check if it's alive)
        app._update_thread = thread

        return {'updating': True, 'started': True}, False

    if trigger_id == 'update-check-interval':
        # Check if update is still running
        if hasattr(app, '_update_thread') and app._update_thread.is_alive():
            return {'updating': True}, False
        else:
            # Update finished — mark done so clientside reload fires
            return {'updating': False, 'finished': True}, True

    return current_status, True


# =============================================================================
# Register Page Callbacks
# =============================================================================

# Register callbacks from page modules
register_home_callbacks(app)
register_match_analysis_callbacks(app)
register_team_insights_callbacks(app)
register_opposition_analysis_callbacks(app)


# =============================================================================
# Run the Application
# =============================================================================

if __name__ == '__main__':
    print("\n" + "="*60)
    print("  CuléVision - FC Barcelona Game Analysis Tool")
    print("  Login System Enabled")

    app.run_server(
        debug=APP_CONFIG['debug'],
        host=APP_CONFIG['host'],
        port=APP_CONFIG['port']
    )
