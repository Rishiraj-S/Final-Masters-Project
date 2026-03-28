import dash
from dash import html, dcc
import dash_bootstrap_components as dbc
import numpy as np

# Import everything from the package root
from page_utils import (
    GOLD, CHART_CONFIG,
    render_pass_map_img, render_lsc_heatmap_img,
    build_scatter_pitch_fig, build_pass_map_fig
)

app = dash.Dash(__name__, external_stylesheets=[dbc.themes.DARKLY])

# --- Generate Dummy Data for Testing ---
np.random.seed(42)
x_test = np.random.uniform(50, 100, 20)
y_test = np.random.uniform(10, 90, 20)
x_end_test = x_test + np.random.uniform(-5, 10, 20)
y_end_test = y_test + np.random.uniform(-10, 10, 20)
outcomes = np.random.choice([0, 1], 20)

# --- Build Figures (Purely via Library Calls) ---

# 1. Pitch Scatter Figure
pitch_fig = build_scatter_pitch_fig(x_test, y_test, title='Scatter Pitch Test', name='Test Points')

# 2. Interactive Pass Map Figure
pass_fig = build_pass_map_fig(x_test, y_test, x_end_test, y_end_test, outcomes=outcomes, title='Interactive Pass Map')

# 3. Static Image URIs
pass_map_uri = render_pass_map_img(x_test, y_test, x_end_test, y_end_test, outcomes=outcomes)
lsc_heatmap_uri = render_lsc_heatmap_img(x_test, y_test, color_hex=GOLD, show_zone_pcts=True)

# --- Layout ---
app.layout = dbc.Container([
    dbc.Row(dbc.Col(html.H1("Visualization Library Test Page", className="text-center my-4", style={'color': GOLD}))),
    
    dbc.Row([
        dbc.Col([
            html.H4("Scatter Pitch (Library Call)", className="text-center"),
            dcc.Graph(figure=pitch_fig, config=CHART_CONFIG)
        ], md=6),
        dbc.Col([
            html.H4("Interactive Pass Map (Library Call)", className="text-center"),
            dcc.Graph(figure=pass_fig, config=CHART_CONFIG)
        ], md=6),
    ], className="mb-5"),
    
    dbc.Row([
        dbc.Col([
            html.H4("Pass Map (mplsoccer Static)", className="text-center"),
            html.Img(src=pass_map_uri, style={'width': '100%', 'borderRadius': '8px'})
        ], md=6),
        dbc.Col([
            html.H4("LSC Zone Heatmap", className="text-center"),
            html.Img(src=lsc_heatmap_uri, style={'width': '100%', 'borderRadius': '8px'})
        ], md=6),
    ]),
    
], fluid=True, style={'backgroundColor': '#0b0d17', 'minHeight': '100vh', 'paddingBottom': '50px'})

if __name__ == "__main__":
    app.run(debug=True, port=8051)
