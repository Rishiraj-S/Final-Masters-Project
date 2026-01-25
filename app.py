"""
CuléVision - FC Barcelona Game Analysis Tool
Main Dash Application
"""

import dash
from dash import html, dcc
import dash_bootstrap_components as dbc
from dash.dependencies import Input, Output
from config import COLORS, APP_CONFIG, NAV_LINKS

# Initialize the Dash app with Bootstrap theme
app = dash.Dash(
    __name__,
    external_stylesheets=[dbc.themes.BOOTSTRAP],
    suppress_callback_exceptions=True,
    title=APP_CONFIG['title']
)

# Navigation Bar
navbar = dbc.Navbar(
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
        ], align="center")
    ], fluid=True),
    color=COLORS['primary_blue'],
    dark=True,
    className="mb-4",
    sticky="top"
)

# Home Page Layout
home_layout = dbc.Container([
    # Home page content will be added here
], fluid=True, className="py-4")

# Placeholder layouts for other pages
match_analysis_layout = dbc.Container([
    html.H2("Match Analysis", style={'color': COLORS['gold']}),
    html.Hr(),
    html.P("Match analysis features will be implemented here.", style={'color': COLORS['text_secondary']})
], fluid=True, className="py-4")

opposition_analysis_layout = dbc.Container([
    html.H2("Opposition Analysis", style={'color': COLORS['gold']}),
    html.Hr(),
    html.P("Opposition scouting and analysis features will be implemented here.", style={'color': COLORS['text_secondary']})
], fluid=True, className="py-4")

team_identity_layout = dbc.Container([
    html.H2("Team Identity", style={'color': COLORS['gold']}),
    html.Hr(),
    html.P("Team identity KPIs and playing style metrics will be implemented here.", style={'color': COLORS['text_secondary']})
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
    elif pathname == '/opposition-analysis':
        return opposition_analysis_layout
    elif pathname == '/team-identity':
        return team_identity_layout
    else:
        return home_layout

# Run the app
if __name__ == '__main__':
    app.run_server(
        debug=APP_CONFIG['debug'],
        host=APP_CONFIG['host'],
        port=APP_CONFIG['port']
    )
