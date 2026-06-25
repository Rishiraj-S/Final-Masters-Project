"""
Team Analysis — Transitions tab

Orchestrates two sub-tabs rendered as full-width column buttons:
  • Attacking Transition  → attacking_transition.py
  • Defending Transition  → defending_transition.py

Both sub-tabs use the skeleton + callback pattern: skeletons render
instantly and charts are populated asynchronously by their own callbacks.
"""

from dash import html, dcc
import dash_bootstrap_components as dbc

from utils.config import COLORS
from page_utils.visualizations import GOLD

from pages.team_analysis_tabs.attacking_transition import build_attacking_transition_skeleton
from pages.team_analysis_tabs.defensive_transition import build_defending_transition_skeleton


_BTN_BASE = {
    'display': 'block',
    'width': '100%',
    'textAlign': 'center',
    'padding': '20px 0',
    'fontWeight': '700',
    'fontSize': '1rem',
    'letterSpacing': '0.6px',
    'textTransform': 'uppercase',
    'backgroundColor': COLORS['dark_secondary'],
    'border': f'1px solid {COLORS["dark_border"]}',
    'borderRadius': '0',
}
_BTN_INACTIVE = {**_BTN_BASE, 'color': COLORS['text_secondary']}
_BTN_ACTIVE   = {**_BTN_BASE, 'color': GOLD,
                 'backgroundColor': 'rgba(237, 187, 0, 0.08)',
                 'borderBottom': f'3px solid {GOLD}'}


def build_transitions_tab(**_):
    """Return the Transitions tab layout — two skeleton sub-tabs."""
    return dcc.Tabs(
        value='ta-trans-defend',
        children=[
            dcc.Tab(
                html.Div([
                    html.Div('Transition from Attack to Defense',
                             style={'fontSize': '0.95rem', 'color': GOLD,
                                    'fontStyle': 'italic', 'marginBottom': '12px',
                                    'letterSpacing': '0.3px'}),
                    build_defending_transition_skeleton(),
                ]),
                label='Defensive Transition',
                value='ta-trans-defend',
                style={**_BTN_INACTIVE, 'flex': '1'},
                selected_style={**_BTN_ACTIVE, 'flex': '1'},
            ),
            dcc.Tab(
                html.Div([
                    html.Div('Transition from Defense to Attack',
                             style={'fontSize': '0.95rem', 'color': GOLD,
                                    'fontStyle': 'italic', 'marginBottom': '12px',
                                    'letterSpacing': '0.3px'}),
                    build_attacking_transition_skeleton(),
                ]),
                label='Attacking Transition',
                value='ta-trans-attack',
                style={**_BTN_INACTIVE, 'flex': '1'},
                selected_style={**_BTN_ACTIVE, 'flex': '1'},
            ),
        ],
        className='mb-3',
    )
