"""
Tab 5 -- Defensive Transition

Analyses Barcelona's defensive response immediately after losing possession:
shape recovery, pressing triggers, and opponent counterattack containment.
"""

from dash import html
import dash_bootstrap_components as dbc

from utils.config import COLORS
from .shared import GOLD, section_card, empty_fig


def build_defensive_transition_tab(events):
    """Render the Defensive Transition tab."""
    placeholder = dbc.Card([
        dbc.CardBody([
            html.P(
                "Defensive Transition analysis coming soon.",
                style={'color': COLORS['text_secondary'], 'textAlign': 'center',
                       'marginBottom': '0'},
            )
        ])
    ], className='mb-4')

    return html.Div([placeholder])
