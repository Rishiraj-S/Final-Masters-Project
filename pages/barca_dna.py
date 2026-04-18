"""
CuléVision - Barça DNA (Player Analysis)
Under construction.
"""

from dash import html
import dash_bootstrap_components as dbc
from utils.config import COLORS


def create_player_analysis_layout():
    return dbc.Container([
        dbc.Row([
            dbc.Col([
                html.H2("Barça DNA", style={'color': COLORS['gold']}),
                html.Hr(style={'borderColor': COLORS['dark_border']}),
                dbc.Card([
                    dbc.CardBody([
                        html.H4("Under Construction", className="text-center",
                                style={'color': COLORS['text_primary']}),
                        html.P("Player analysis features are currently under construction.",
                               className="text-center",
                               style={'color': COLORS['text_secondary']}),
                    ])
                ])
            ])
        ])
    ], fluid=True)


def register_player_analysis_callbacks(app):
    pass
