"""
CuléVision - FC Barcelona Game Analysis Tool
Main Dash Application with Login System
"""

import dash
from dash import html, dcc, dash_table, callback_context
import dash_bootstrap_components as dbc
from dash.dependencies import Input, Output, State
import plotly.express as px
import plotly.graph_objects as go
import subprocess
import threading
import os
from config import COLORS, APP_CONFIG, NAV_LINKS
from data_utils import (
    get_match_results, get_player_stats, get_season_summary,
    get_top_scorers, get_match_stats, get_match_events_timeline,
    get_all_barcelona_players, get_player_match_stats, get_all_events
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


def create_result_badge(result):
    """Create a colored badge for match result."""
    css_class = f"result-badge result-{result.lower()}"
    return html.Span(result, className=css_class)


def create_stat_card(value, label, color=COLORS['gold']):
    """Create a stat display card."""
    return dbc.Card([
        dbc.CardBody([
            html.Div(str(value), className="stat-value", style={'color': color}),
            html.Div(label, className="stat-label")
        ], className="stat-card")
    ], className="h-100")


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


def create_home_layout(is_admin=False):
    """Create the Home page layout with season overview."""
    # Get data
    summary = get_season_summary()
    results = get_match_results()
    top_scorers = get_top_scorers(10)
    recent_matches = results[:5] if results else []

    # Admin button (only visible for admin users)
    admin_button = html.Div()
    if is_admin:
        admin_button = html.Div([
            dbc.Button(
                [html.I(className="fas fa-database me-2"), "Update Databases"],
                id='update-db-button',
                color="warning",
                className="mb-3",
                style={'fontWeight': 'bold'}
            )
        ], style={'position': 'absolute', 'top': '0', 'right': '15px'})

    # Season stats cards
    stats_row = dbc.Row([
        dbc.Col(create_stat_card(summary.get('matches_played', 0), 'Matches'), width=2),
        dbc.Col(create_stat_card(summary.get('wins', 0), 'Wins', '#28a745'), width=2),
        dbc.Col(create_stat_card(summary.get('draws', 0), 'Draws', '#ffc107'), width=2),
        dbc.Col(create_stat_card(summary.get('losses', 0), 'Losses', '#dc3545'), width=2),
        dbc.Col(create_stat_card(summary.get('goals_for', 0), 'Goals For'), width=2),
        dbc.Col(create_stat_card(summary.get('goals_against', 0), 'Goals Against', '#A5A8B8'), width=2),
    ], className="mb-4")

    # Recent matches table
    recent_matches_rows = []
    for match in recent_matches:
        venue = "H" if match['is_home'] else "A"
        score = f"{match['barca_goals']}-{match['opponent_goals']}"
        recent_matches_rows.append(
            html.Tr([
                html.Td(match['date']),
                html.Td(match['competition'], style={'fontSize': '0.85rem'}),
                html.Td(f"vs {match['opponent']} ({venue})"),
                html.Td(score, style={'fontWeight': 'bold'}),
                html.Td(create_result_badge(match['result']))
            ])
        )

    recent_matches_card = dbc.Card([
        dbc.CardHeader(html.H5("Recent Matches", className="mb-0", style={'color': COLORS['gold']})),
        dbc.CardBody([
            html.Table([
                html.Thead(html.Tr([
                    html.Th("Date"), html.Th("Competition"), html.Th("Match"), html.Th("Score"), html.Th("Result")
                ])),
                html.Tbody(recent_matches_rows)
            ], className="table table-dark table-striped")
        ])
    ])

    # Top scorers table
    scorers_rows = []
    if not top_scorers.empty:
        for _, row in top_scorers.iterrows():
            scorers_rows.append(
                html.Tr([
                    html.Td(row['player']),
                    html.Td(str(row['goals']), style={'fontWeight': 'bold', 'color': COLORS['gold']}),
                    html.Td(str(row['appearances'])),
                    html.Td(str(row['shots']))
                ])
            )

    top_scorers_card = dbc.Card([
        dbc.CardHeader(html.H5("Top Scorers", className="mb-0", style={'color': COLORS['gold']})),
        dbc.CardBody([
            html.Table([
                html.Thead(html.Tr([
                    html.Th("Player"), html.Th("Goals"), html.Th("Apps"), html.Th("Shots")
                ])),
                html.Tbody(scorers_rows)
            ], className="table table-dark table-striped")
        ])
    ])

    # Player stats table (full squad)
    player_stats = get_player_stats()
    players_card = dbc.Card([
        dbc.CardHeader(html.H5("Squad Statistics", className="mb-0", style={'color': COLORS['gold']})),
        dbc.CardBody([
            dash_table.DataTable(
                id='player-stats-table',
                columns=[
                    {'name': 'Player', 'id': 'player'},
                    {'name': 'Goals', 'id': 'goals'},
                    {'name': 'Apps', 'id': 'appearances'},
                    {'name': 'Passes', 'id': 'passes'},
                    {'name': 'Shots', 'id': 'shots'},
                    {'name': 'Tackles', 'id': 'tackles'},
                    {'name': 'Interceptions', 'id': 'interceptions'}
                ],
                data=player_stats.to_dict('records') if not player_stats.empty else [],
                style_table={'overflowX': 'auto'},
                style_cell={
                    'backgroundColor': '#151932',
                    'color': '#E8E9ED',
                    'textAlign': 'left',
                    'padding': '10px'
                },
                style_header={
                    'backgroundColor': '#1E2139',
                    'fontWeight': 'bold',
                    'color': COLORS['gold']
                },
                style_data_conditional=[
                    {'if': {'row_index': 'odd'}, 'backgroundColor': '#1E2139'}
                ],
                page_size=15,
                sort_action='native'
            )
        ])
    ])

    return dbc.Container([
        html.Div([
            html.H2("Season Overview 2025-2026", style={'color': COLORS['gold']}, className="mb-4"),
            admin_button
        ], style={'position': 'relative'}),
        stats_row,
        dbc.Row([
            dbc.Col(recent_matches_card, width=6),
            dbc.Col(top_scorers_card, width=6)
        ], className="mb-4"),
        dbc.Row([
            dbc.Col(players_card, width=12)
        ])
    ], fluid=True, className="py-4")


def create_match_analysis_layout():
    """Create the Match Analysis page layout."""
    results = get_match_results()

    # Match selector dropdown
    match_options = [
        {'label': f"{r['date']} - {r['description']} ({r['competition']})", 'value': r['match_id']}
        for r in results
    ]

    return dbc.Container([
        html.H2("Match Analysis", style={'color': COLORS['gold']}, className="mb-4"),
        html.Hr(),

        dbc.Row([
            dbc.Col([
                html.Label("Select Match:", style={'color': COLORS['text_secondary']}),
                dcc.Dropdown(
                    id='match-selector',
                    options=match_options,
                    value=match_options[0]['value'] if match_options else None,
                    style={'backgroundColor': '#151932', 'color': '#000'}
                )
            ], width=6)
        ], className="mb-4"),

        html.Div(id='match-analysis-content')
    ], fluid=True, className="py-4")


def create_team_insights_layout():
    """Create the Team Insights page layout."""
    players = get_all_barcelona_players()

    player_options = [{'label': p, 'value': p} for p in players if p]

    return dbc.Container([
        html.H2("Team Insights", style={'color': COLORS['gold']}, className="mb-4"),
        html.Hr(),

        dbc.Row([
            dbc.Col([
                html.Label("Select Player:", style={'color': COLORS['text_secondary']}),
                dcc.Dropdown(
                    id='player-selector',
                    options=player_options,
                    value=player_options[0]['value'] if player_options else None,
                    style={'backgroundColor': '#151932'}
                )
            ], width=4)
        ], className="mb-4"),

        html.Div(id='player-insights-content')
    ], fluid=True, className="py-4")


def create_update_overlay():
    """Create the database update overlay."""
    return html.Div([
        html.Div([
            html.Div(className="spinner-border text-warning mb-4", role="status"),
            html.H2("Databases Are Being Updated",
                   style={'color': COLORS['gold'], 'marginBottom': '20px'}),
            html.P("Please wait while the system processes the latest match data...",
                  style={'color': COLORS['text_secondary'], 'fontSize': '1.1rem'}),
            html.Hr(style={'borderColor': COLORS['dark_border'], 'width': '300px', 'margin': '20px auto'}),
            html.Div([
                html.P([html.Strong("What's happening:"), " The pipeline is fetching and processing data from all competitions."],
                      className="mb-2", style={'color': COLORS['text_primary']}),
                html.P([html.Strong("Competitions:"), " La Liga, Copa del Rey, Spanish Super Cup, Champions League"],
                      className="mb-2", style={'color': COLORS['text_primary']}),
                html.P([html.Strong("Note:"), " Navigation is disabled during this process to ensure data integrity."],
                      style={'color': '#ffc107'})
            ], style={'textAlign': 'left', 'maxWidth': '500px', 'margin': '0 auto', 'padding': '20px',
                     'backgroundColor': '#151932', 'borderRadius': '10px', 'border': '1px solid #2A2F4A'}),
            html.Div([
                html.Div(className="spinner-grow spinner-grow-sm text-warning me-2", role="status"),
                html.Span("Processing...", className="pulse-animation", style={'color': COLORS['text_secondary']})
            ], style={'marginTop': '30px'})
        ], style={'textAlign': 'center'})
    ], className="update-overlay", id='update-overlay')


# Main App Layout
app.layout = html.Div([
    # Session storage
    dcc.Store(id='session-store', storage_type='session'),
    dcc.Store(id='update-status-store', data={'updating': False}),

    # Update overlay (hidden by default)
    html.Div(id='update-overlay-container'),

    # Location for URL routing
    dcc.Location(id='url', refresh=False),

    # Interval for checking update status
    dcc.Interval(id='update-check-interval', interval=2000, disabled=True),

    # Main content container
    html.Div(id='main-container')
], style={'backgroundColor': COLORS['dark_bg'], 'minHeight': '100vh'})


# Callback for main container - handles login state
@app.callback(
    Output('main-container', 'children'),
    Output('url', 'pathname'),
    Input('session-store', 'data'),
    Input('url', 'pathname'),
    State('update-status-store', 'data')
)
def update_main_container(session_data, pathname, update_status):
    # Check if user is logged in
    if not session_data or not session_data.get('logged_in'):
        return create_login_layout(), '/'

    # User is logged in - show main app
    user_info = session_data
    is_admin = user_info.get('role') == 'admin'

    # Create navbar
    navbar = create_navbar(user_info)

    # Determine which page to show
    if pathname == '/match-analysis':
        page_content = create_match_analysis_layout()
    elif pathname == '/team-insights':
        page_content = create_team_insights_layout()
    else:
        page_content = create_home_layout(is_admin)
        pathname = '/'

    return html.Div([navbar, html.Div(id='page-content', children=page_content)]), pathname


# Login callback - handles login button click
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


# Logout callback - handles logout button click (separate to avoid referencing non-existent element)
@app.callback(
    Output('session-store', 'data', allow_duplicate=True),
    Input('logout-button', 'n_clicks'),
    prevent_initial_call=True
)
def handle_logout(logout_clicks):
    if logout_clicks:
        return None
    return dash.no_update


# Update overlay callback
@app.callback(
    Output('update-overlay-container', 'children'),
    Input('update-status-store', 'data')
)
def show_update_overlay(update_status):
    if update_status and update_status.get('updating'):
        return create_update_overlay()
    return html.Div()


# Database update callback
@app.callback(
    Output('update-status-store', 'data'),
    Output('update-check-interval', 'disabled'),
    Input('update-db-button', 'n_clicks'),
    Input('update-check-interval', 'n_intervals'),
    State('update-status-store', 'data'),
    prevent_initial_call=True
)
def handle_database_update(n_clicks, n_intervals, current_status):
    ctx = callback_context
    if not ctx.triggered:
        return current_status, True

    trigger_id = ctx.triggered[0]['prop_id'].split('.')[0]

    if trigger_id == 'update-db-button' and n_clicks:
        # Start the database update process
        def run_pipeline():
            script_dir = os.path.dirname(os.path.abspath(__file__))
            pipeline_path = os.path.join(script_dir, 'opta_pipeline', 'main.py')
            subprocess.run(['python', pipeline_path], cwd=script_dir)

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
            # Update finished
            return {'updating': False}, True

    return current_status, True


# Callback for match analysis content
@app.callback(
    Output('match-analysis-content', 'children'),
    Input('match-selector', 'value')
)
def update_match_analysis(match_id):
    if not match_id:
        return html.P("Select a match to view analysis.", style={'color': COLORS['text_secondary']})

    stats = get_match_stats(match_id)
    timeline = get_match_events_timeline(match_id)

    if not stats:
        return html.P("No data available for this match.", style={'color': COLORS['text_secondary']})

    home_team = stats['home_team']
    away_team = stats['away_team']
    home_stats = stats['home']
    away_stats = stats['away']

    # Match header
    match_header = dbc.Card([
        dbc.CardBody([
            dbc.Row([
                dbc.Col(html.H4(home_team, className="text-end"), width=4),
                dbc.Col(html.H2(f"{home_stats['goals']} - {away_stats['goals']}",
                               className="text-center", style={'color': COLORS['gold']}), width=4),
                dbc.Col(html.H4(away_team, className="text-start"), width=4)
            ])
        ])
    ], className="mb-4")

    # Stats comparison
    stat_labels = [
        ('Possession', 'possession', '%'),
        ('Shots', 'shots', ''),
        ('Shots on Target', 'shots_on_target', ''),
        ('Passes', 'passes', ''),
        ('Pass Accuracy', 'pass_accuracy', '%'),
        ('Fouls', 'fouls', ''),
        ('Corners', 'corners', ''),
        ('Yellow Cards', 'yellow_cards', ''),
        ('Red Cards', 'red_cards', '')
    ]

    stats_rows = []
    for label, key, suffix in stat_labels:
        home_val = home_stats.get(key, 0)
        away_val = away_stats.get(key, 0)
        stats_rows.append(
            html.Tr([
                html.Td(f"{home_val}{suffix}", style={'textAlign': 'right', 'fontWeight': 'bold'}),
                html.Td(label, style={'textAlign': 'center', 'color': COLORS['text_secondary']}),
                html.Td(f"{away_val}{suffix}", style={'textAlign': 'left', 'fontWeight': 'bold'})
            ])
        )

    stats_card = dbc.Card([
        dbc.CardHeader(html.H5("Match Statistics", className="mb-0", style={'color': COLORS['gold']})),
        dbc.CardBody([
            html.Table([html.Tbody(stats_rows)], className="table table-dark", style={'width': '100%'})
        ])
    ])

    # Create possession chart
    possession_fig = go.Figure(data=[
        go.Bar(
            y=['Possession'],
            x=[home_stats.get('possession', 50)],
            orientation='h',
            name=home_team,
            marker_color=COLORS['primary_blue'],
            text=[f"{home_stats.get('possession', 50)}%"],
            textposition='inside'
        ),
        go.Bar(
            y=['Possession'],
            x=[away_stats.get('possession', 50)],
            orientation='h',
            name=away_team,
            marker_color=COLORS['garnet'],
            text=[f"{away_stats.get('possession', 50)}%"],
            textposition='inside'
        )
    ])
    possession_fig.update_layout(
        barmode='stack',
        showlegend=True,
        legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='center', x=0.5),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font=dict(color='#E8E9ED'),
        height=120,
        margin=dict(l=20, r=20, t=40, b=20)
    )

    # Shots comparison chart
    shots_fig = go.Figure()
    categories = ['Shots', 'Shots on Target', 'Goals']
    home_values = [home_stats.get('shots', 0), home_stats.get('shots_on_target', 0), home_stats.get('goals', 0)]
    away_values = [away_stats.get('shots', 0), away_stats.get('shots_on_target', 0), away_stats.get('goals', 0)]

    shots_fig.add_trace(go.Bar(x=categories, y=home_values, name=home_team, marker_color=COLORS['primary_blue']))
    shots_fig.add_trace(go.Bar(x=categories, y=away_values, name=away_team, marker_color=COLORS['garnet']))

    shots_fig.update_layout(
        barmode='group',
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font=dict(color='#E8E9ED'),
        height=300,
        margin=dict(l=20, r=20, t=40, b=40),
        legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='center', x=0.5)
    )

    # Timeline
    timeline_items = []
    for event in timeline:
        if event['type'] == 'Goal':
            icon = "⚽"
            color = '#28a745'
        elif event['type'] == 'Card':
            icon = "🟨"
            color = '#ffc107'
        else:
            icon = "🔄"
            color = '#A5A8B8'

        side = 'start' if event['team_position'] == 'home' else 'end'
        timeline_items.append(
            html.Div([
                html.Span(f"{event['minute']}'", style={'fontWeight': 'bold', 'marginRight': '10px'}),
                html.Span(icon, style={'marginRight': '5px'}),
                html.Span(f"{event['player']} ({event['team']})", style={'color': color})
            ], style={'padding': '5px 0', 'textAlign': side})
        )

    timeline_card = dbc.Card([
        dbc.CardHeader(html.H5("Match Timeline", className="mb-0", style={'color': COLORS['gold']})),
        dbc.CardBody(timeline_items if timeline_items else [html.P("No key events recorded.")])
    ])

    return html.Div([
        match_header,
        dbc.Row([
            dbc.Col(stats_card, width=6),
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader(html.H5("Possession", className="mb-0", style={'color': COLORS['gold']})),
                    dbc.CardBody(dcc.Graph(figure=possession_fig, config={'displayModeBar': False}))
                ], className="mb-3"),
                dbc.Card([
                    dbc.CardHeader(html.H5("Shots Analysis", className="mb-0", style={'color': COLORS['gold']})),
                    dbc.CardBody(dcc.Graph(figure=shots_fig, config={'displayModeBar': False}))
                ])
            ], width=6)
        ], className="mb-4"),
        dbc.Row([
            dbc.Col(timeline_card, width=12)
        ])
    ])


# Callback for player insights content
@app.callback(
    Output('player-insights-content', 'children'),
    Input('player-selector', 'value')
)
def update_player_insights(player_name):
    if not player_name:
        return html.P("Select a player to view insights.", style={'color': COLORS['text_secondary']})

    # Get player season stats
    all_stats = get_player_stats()
    player_row = all_stats[all_stats['player'] == player_name]

    if player_row.empty:
        return html.P("No data available for this player.", style={'color': COLORS['text_secondary']})

    player_stats = player_row.iloc[0]

    # Get match-by-match stats
    match_stats = get_player_match_stats(player_name)

    # Player header card
    header_card = dbc.Card([
        dbc.CardBody([
            html.H3(player_name, style={'color': COLORS['gold']}),
            html.P("FC Barcelona", style={'color': COLORS['text_secondary']})
        ])
    ], className="mb-4")

    # Season stats cards
    stats_row = dbc.Row([
        dbc.Col(create_stat_card(player_stats['goals'], 'Goals'), width=2),
        dbc.Col(create_stat_card(player_stats['appearances'], 'Appearances'), width=2),
        dbc.Col(create_stat_card(player_stats['passes'], 'Passes'), width=2),
        dbc.Col(create_stat_card(player_stats['shots'], 'Shots'), width=2),
        dbc.Col(create_stat_card(player_stats['tackles'], 'Tackles'), width=2),
        dbc.Col(create_stat_card(player_stats['interceptions'], 'Interceptions'), width=2),
    ], className="mb-4")

    # Goals over time chart
    if match_stats:
        matches_with_goals = [m for m in match_stats if m['goals'] > 0]
        if matches_with_goals:
            goals_fig = px.bar(
                x=[m['date'] for m in match_stats],
                y=[m['goals'] for m in match_stats],
                labels={'x': 'Date', 'y': 'Goals'},
                title='Goals by Match'
            )
            goals_fig.update_layout(
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                font=dict(color='#E8E9ED'),
                height=300
            )
            goals_fig.update_traces(marker_color=COLORS['gold'])
        else:
            goals_fig = go.Figure()
            goals_fig.update_layout(
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                font=dict(color='#E8E9ED'),
                height=300,
                annotations=[dict(text="No goals scored", x=0.5, y=0.5, showarrow=False)]
            )

        # Activity chart (passes per match)
        activity_fig = px.line(
            x=[m['date'] for m in match_stats],
            y=[m['passes'] for m in match_stats],
            labels={'x': 'Date', 'y': 'Passes'},
            title='Passing Activity by Match'
        )
        activity_fig.update_layout(
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            font=dict(color='#E8E9ED'),
            height=300
        )
        activity_fig.update_traces(line_color=COLORS['primary_blue'])

    else:
        goals_fig = go.Figure()
        activity_fig = go.Figure()

    # Match history table
    match_rows = []
    for match in match_stats[:10]:
        match_rows.append(
            html.Tr([
                html.Td(match['date']),
                html.Td(match['description'][:30] + '...' if len(match['description']) > 30 else match['description']),
                html.Td(str(match['goals']), style={'color': COLORS['gold'] if match['goals'] > 0 else COLORS['text_secondary']}),
                html.Td(str(match['passes'])),
                html.Td(str(match['shots']))
            ])
        )

    match_history_card = dbc.Card([
        dbc.CardHeader(html.H5("Recent Match Performance", className="mb-0", style={'color': COLORS['gold']})),
        dbc.CardBody([
            html.Table([
                html.Thead(html.Tr([
                    html.Th("Date"), html.Th("Match"), html.Th("Goals"), html.Th("Passes"), html.Th("Shots")
                ])),
                html.Tbody(match_rows)
            ], className="table table-dark table-striped")
        ])
    ])

    return html.Div([
        header_card,
        stats_row,
        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardBody(dcc.Graph(figure=goals_fig, config={'displayModeBar': False}))
                ])
            ], width=6),
            dbc.Col([
                dbc.Card([
                    dbc.CardBody(dcc.Graph(figure=activity_fig, config={'displayModeBar': False}))
                ])
            ], width=6)
        ], className="mb-4"),
        dbc.Row([
            dbc.Col(match_history_card, width=12)
        ])
    ])


# Run the app
if __name__ == '__main__':
    print("\n" + "="*60)
    print("  CuléVision - FC Barcelona Game Analysis Tool")
    print("  Login System Enabled")
    print("="*60)
    print("\n  Available Users:")
    print("    - Guest (password: guest)")
    print("    - Rishi (Admin) (password: admin)")
    print("\n  Admin users can update databases from the Home tab.")
    print("="*60 + "\n")

    app.run_server(
        debug=APP_CONFIG['debug'],
        host=APP_CONFIG['host'],
        port=APP_CONFIG['port']
    )
