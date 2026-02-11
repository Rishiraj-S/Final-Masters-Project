"""
CuléVision - Match Analysis Page

Orchestrator module that wires together the layout shell (dropdowns + tabs)
and delegates rendering of each tab to specialised modules inside
``match_analysis_tabs/``.

Tab modules:
    overview.py     -- Match Overview (TV-style stat bars)
    possession.py   -- Organised Possession
    transitions.py  -- Transitions
    set_pieces.py   -- Set Pieces
    contested.py    -- Contested Phases
"""

from dash import html, dcc
from dash.dependencies import Input, Output
import dash_bootstrap_components as dbc

from utils.config import COLORS
from utils.data_utils import get_match_results, get_match_events

from .match_analysis_tabs import (
    build_overview_tab,
    build_possession_tab,
    build_transitions_tab,
    build_setpieces_tab,
    build_contested_tab,
)

GOLD = COLORS['gold']


# =============================================================================
# Page layout
# =============================================================================

def create_match_analysis_layout():
    """
    Create the Match Analysis page layout.

    Contains tournament and match selector dropdowns and a tabbed interface
    for the five analysis phases.
    """
    results = get_match_results()

    # Build tournament options from unique competitions
    competitions = sorted(set(r['competition'] for r in results))
    tournament_options = [{'label': 'All Tournaments', 'value': 'all'}] + [
        {'label': comp, 'value': comp} for comp in competitions
    ]

    # Build match options (all matches initially)
    match_options = [
        {'label': f"{r['date']} - {r['description']} ({r['competition']})",
         'value': r['match_id']}
        for r in results
    ]

    # Store match results for client-side filtering
    match_data = [
        {'match_id': r['match_id'], 'competition': r['competition'],
         'label': f"{r['date']} - {r['description']} ({r['competition']})"}
        for r in results
    ]

    tab_style = {'backgroundColor': COLORS['dark_secondary']}
    active_style = {'backgroundColor': COLORS['dark_tertiary'],
                    'borderBottom': f'2px solid {GOLD}'}

    tabs = dbc.Tabs([
        dbc.Tab(label="Match Overview", tab_id="tab-overview",
                tab_style=tab_style, active_tab_style=active_style),
        dbc.Tab(label="Organised Possession", tab_id="tab-possession",
                tab_style=tab_style, active_tab_style=active_style),
        dbc.Tab(label="Transitions", tab_id="tab-transitions",
                tab_style=tab_style, active_tab_style=active_style),
        dbc.Tab(label="Set Pieces", tab_id="tab-setpieces",
                tab_style=tab_style, active_tab_style=active_style),
        dbc.Tab(label="Contested Phases", tab_id="tab-contested",
                tab_style=tab_style, active_tab_style=active_style),
    ], id="pma-tabs", active_tab="tab-overview", className="mb-4")

    return dbc.Container([
        dcc.Store(id='pma-match-data', data=match_data),

        html.H2("Match Analysis", style={'color': GOLD}, className="mb-4"),
        html.Hr(),

        dbc.Row([
            dbc.Col([
                html.Label("Select Tournament:",
                           style={'color': COLORS['text_secondary']}),
                dcc.Dropdown(
                    id='pma-tournament-selector',
                    options=tournament_options,
                    value='all',
                    style={'backgroundColor': '#151932', 'color': '#000'},
                ),
            ], width=4),
            dbc.Col([
                html.Label("Select Match:",
                           style={'color': COLORS['text_secondary']}),
                dcc.Dropdown(
                    id='pma-match-selector',
                    options=match_options,
                    value=match_options[0]['value'] if match_options else None,
                    style={'backgroundColor': '#151932', 'color': '#000'},
                ),
            ], width=8),
        ], className="mb-4"),

        tabs,
        html.Div(id='pma-tab-content'),
    ], fluid=True, className="py-4")


# =============================================================================
# Callback registration
# =============================================================================

def register_match_analysis_callbacks(app):
    """Register all callbacks for the match analysis page."""

    @app.callback(
        Output('pma-match-selector', 'options'),
        Output('pma-match-selector', 'value'),
        Input('pma-tournament-selector', 'value'),
        Input('pma-match-data', 'data'),
    )
    def filter_matches_by_tournament(tournament, match_data):
        """Filter match dropdown options based on selected tournament."""
        if not match_data:
            return [], None

        if tournament and tournament != 'all':
            filtered = [m for m in match_data if m['competition'] == tournament]
        else:
            filtered = match_data

        options = [{'label': m['label'], 'value': m['match_id']} for m in filtered]
        value = options[0]['value'] if options else None
        return options, value

    @app.callback(
        Output('pma-tab-content', 'children'),
        Input('pma-match-selector', 'value'),
        Input('pma-tabs', 'active_tab'),
    )
    def update_pma_content(match_id, active_tab):
        """Load match events and delegate rendering to the active tab module."""
        if not match_id:
            return html.P("Select a match to begin analysis.",
                          style={'color': COLORS['text_secondary']})

        events = get_match_events(match_id)
        if events.empty:
            return html.P("No event data available for this match.",
                          style={'color': COLORS['text_secondary']})

        tab_builders = {
            'tab-overview': build_overview_tab,
            'tab-possession': build_possession_tab,
            'tab-transitions': build_transitions_tab,
            'tab-setpieces': build_setpieces_tab,
            'tab-contested': build_contested_tab,
        }

        builder = tab_builders.get(active_tab, build_overview_tab)
        return builder(events)
