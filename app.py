"""
CuléVision - FC Barcelona Game Analysis Tool
Main Dash Application
"""

import dash
from dash import html, dcc
import dash_bootstrap_components as dbc
from dash.dependencies import Input, Output

# Initialize the Dash app with Bootstrap theme
app = dash.Dash(
    __name__,
    external_stylesheets=[dbc.themes.BOOTSTRAP],
    suppress_callback_exceptions=True,
    title="CuléVision - FC Barcelona Analytics"
)

# FC Barcelona Brand Colors
COLORS = {
    'primary_blue': '#004D98',
    'garnet': '#A50044',
    'gold': '#EDBB00',
    'white': '#FFFFFF',
    'light_gray': '#F8F9FA',
    'dark_gray': '#343A40'
}

# Navigation Bar
navbar = dbc.Navbar(
    dbc.Container([
        dbc.Row([
            dbc.Col([
                html.Div([
                    html.H3("CuléVision", className="mb-0",
                           style={'color': COLORS['white'], 'fontWeight': 'bold'}),
                    html.Small("FC Barcelona Analytics",
                              style={'color': COLORS['gold'], 'fontSize': '0.8rem'})
                ])
            ], width="auto"),
        ], align="center", className="g-0"),

        dbc.Row([
            dbc.Col([
                dbc.Nav([
                    dbc.NavItem(dbc.NavLink("Home", href="/", active="exact")),
                    dbc.NavItem(dbc.NavLink("Match Analysis", href="/match-analysis", active="exact")),
                    dbc.NavItem(dbc.NavLink("Rival Analysis", href="/rival-analysis", active="exact")),
                    dbc.NavItem(dbc.NavLink("Team Identity", href="/team-identity", active="exact")),
                    dbc.NavItem(dbc.NavLink("Live Alerts", href="/live-alerts", active="exact")),
                ], navbar=True, className="ms-auto")
            ])
        ], align="center")
    ], fluid=True),
    color=COLORS['primary_blue'],
    dark=True,
    className="mb-4",
    sticky="top"
)

# Home Page Layout
home_layout = dbc.Container([
    dbc.Row([
        dbc.Col([
            html.Div([
                html.H1("Welcome to CuléVision",
                       className="text-center mb-4",
                       style={'color': COLORS['primary_blue'], 'fontWeight': 'bold'}),
                html.Hr(style={'borderColor': COLORS['garnet'], 'borderWidth': '3px'}),

                html.P([
                    "Professional football analytics dashboard built specifically for ",
                    html.Strong("FC Barcelona", style={'color': COLORS['garnet']}),
                    ". Powered by Opta event data for comprehensive match analysis and tactical insights."
                ], className="lead text-center mb-5"),
            ], className="mb-5")
        ])
    ]),

    # Feature Cards
    dbc.Row([
        dbc.Col([
            dbc.Card([
                dbc.CardBody([
                    html.H4("⚽ Match Analysis", className="card-title",
                           style={'color': COLORS['primary_blue']}),
                    html.P("Automated analysis reducing review time from 3-4 hours to 30 minutes.",
                          className="card-text"),
                ])
            ], className="h-100 shadow-sm")
        ], md=6, lg=4, className="mb-4"),

        dbc.Col([
            dbc.Card([
                dbc.CardBody([
                    html.H4("🎯 Rival Analysis", className="card-title",
                           style={'color': COLORS['primary_blue']}),
                    html.P("Comprehensive opposition scouting and SWOT analysis.",
                          className="card-text"),
                ])
            ], className="h-100 shadow-sm")
        ], md=6, lg=4, className="mb-4"),

        dbc.Col([
            dbc.Card([
                dbc.CardBody([
                    html.H4("🏆 Team Identity", className="card-title",
                           style={'color': COLORS['primary_blue']}),
                    html.P("KPIs defining Barcelona's playing style and game model.",
                          className="card-text"),
                ])
            ], className="h-100 shadow-sm")
        ], md=6, lg=4, className="mb-4"),

        dbc.Col([
            dbc.Card([
                dbc.CardBody([
                    html.H4("🚨 Live Alerts", className="card-title",
                           style={'color': COLORS['primary_blue']}),
                    html.P("Real-time detection of critical match moments.",
                          className="card-text"),
                ])
            ], className="h-100 shadow-sm")
        ], md=6, lg=4, className="mb-4"),

        dbc.Col([
            dbc.Card([
                dbc.CardBody([
                    html.H4("💬 Virtual Assistant", className="card-title",
                           style={'color': COLORS['primary_blue']}),
                    html.P("Interactive query and analysis capabilities.",
                          className="card-text"),
                ])
            ], className="h-100 shadow-sm")
        ], md=6, lg=4, className="mb-4"),

        dbc.Col([
            dbc.Card([
                dbc.CardBody([
                    html.H4("📊 Data Insights", className="card-title",
                           style={'color': COLORS['primary_blue']}),
                    html.P("Deep dive into match statistics and performance metrics.",
                          className="card-text"),
                ])
            ], className="h-100 shadow-sm")
        ], md=6, lg=4, className="mb-4"),
    ], className="mb-5"),

    # Status Section
    dbc.Row([
        dbc.Col([
            dbc.Alert([
                html.H5("📍 Current Status", className="alert-heading",
                       style={'color': COLORS['primary_blue']}),
                html.P("Version 0.1.0 - Foundation"),
                html.Hr(),
                html.P("This is the foundational structure. Features will be implemented incrementally.",
                      className="mb-0")
            ], color="light", className="border-start border-5",
               style={'borderLeftColor': COLORS['garnet'] + ' !important'})
        ])
    ])
], fluid=True, className="py-4")

# Placeholder layouts for other pages
match_analysis_layout = dbc.Container([
    html.H2("Match Analysis", style={'color': COLORS['primary_blue']}),
    html.Hr(),
    html.P("Match analysis features will be implemented here.")
], fluid=True, className="py-4")

rival_analysis_layout = dbc.Container([
    html.H2("Rival Analysis", style={'color': COLORS['primary_blue']}),
    html.Hr(),
    html.P("Rival scouting and analysis features will be implemented here.")
], fluid=True, className="py-4")

team_identity_layout = dbc.Container([
    html.H2("Team Identity", style={'color': COLORS['primary_blue']}),
    html.Hr(),
    html.P("Team identity KPIs and playing style metrics will be implemented here.")
], fluid=True, className="py-4")

live_alerts_layout = dbc.Container([
    html.H2("Live Alerts", style={'color': COLORS['primary_blue']}),
    html.Hr(),
    html.P("Real-time match alerts will be implemented here.")
], fluid=True, className="py-4")

# Main App Layout
app.layout = html.Div([
    dcc.Location(id='url', refresh=False),
    navbar,
    html.Div(id='page-content')
])

# Callback for page navigation
@app.callback(
    Output('page-content', 'children'),
    Input('url', 'pathname')
)
def display_page(pathname):
    if pathname == '/match-analysis':
        return match_analysis_layout
    elif pathname == '/rival-analysis':
        return rival_analysis_layout
    elif pathname == '/team-identity':
        return team_identity_layout
    elif pathname == '/live-alerts':
        return live_alerts_layout
    else:
        return home_layout

# Run the app
if __name__ == '__main__':
    app.run_server(debug=True, host='0.0.0.0', port=8050)
