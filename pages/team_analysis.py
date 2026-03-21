"""
CuléVision - Team Analysis Page

Game-model focused longitudinal dashboard (season / rolling matches).
6 tabs covering the full tactical fingerprint of FC Barcelona,
structured according to the game model phase mapping:

  Tab 0 — Overview          Aggregates KPIs across all phases
  Tab 1 — Build-up          How we play out & progress
  Tab 2 — Chance Creation   How we create & finish
  Tab 3 — Def. Structure    Where & how we defend
  Tab 4 — Transitions       Offensive & defensive transition
  Tab 5 — Set Pieces        Corners, free kicks, throw-ins
"""

from dash import html, dcc
from dash.dependencies import Input, Output
import dash_bootstrap_components as dbc

from utils.config import COLORS
from utils.data_utils import get_match_results, CURRENT_SEASON

from pages.match_analysis_tabs.shared import page_header, GOLD
from pages.team_analysis_tabs import (
    build_overview_tab,
    build_buildup_tab,
    build_chance_creation_tab,
    build_def_structure_tab,
    build_transitions_tab,
    build_set_pieces_tab,
)


# ---------------------------------------------------------------------------
# Competition / match helpers
# ---------------------------------------------------------------------------

_ALL_COMPETITIONS = [
    {'label': 'La Liga',          'value': 'La Liga'},
    {'label': 'Champions League', 'value': 'Champions League'},
    {'label': 'Copa del Rey',     'value': 'Copa del Rey'},
    {'label': 'Spanish Super Cup','value': 'Spanish Super Cup'},
]

_COMP_SHORT = {
    'La Liga':           'Liga',
    'Champions League':  'UCL',
    'Copa del Rey':      'Copa',
    'Spanish Super Cup': 'SC',
}


def _normalize_competitions(competition):
    if not competition:
        return None
    if isinstance(competition, str):
        return None if competition == 'all' else [competition]
    return list(competition) or None


# ---------------------------------------------------------------------------
# Layout
# ---------------------------------------------------------------------------

def create_team_analysis_layout():
    """Return the full Team Analysis page layout."""
    return dbc.Container([
        page_header("Team Analysis"),
        html.Hr(),

        # ── Filters ──────────────────────────────────────────────────────────
        dbc.Row([
            dbc.Col([
                html.Label("Competition",
                           style={'color': COLORS['text_secondary'], 'fontSize': '0.85rem'}),
                dcc.Dropdown(
                    id='ta-competition-selector',
                    options=_ALL_COMPETITIONS,
                    value=None,
                    multi=True,
                    clearable=True,
                    placeholder="All Competitions…",
                    style={'backgroundColor': COLORS['dark_secondary']},
                ),
            ], md=3),
            dbc.Col([
                html.Label("Match(es)",
                           style={'color': COLORS['text_secondary'], 'fontSize': '0.85rem'}),
                dcc.Dropdown(
                    id='ta-match-selector',
                    options=[],
                    value=None,
                    multi=True,
                    clearable=True,
                    placeholder="All matches…",
                    style={'backgroundColor': COLORS['dark_secondary']},
                ),
            ], md=7),
        ], className="mb-4"),

        # ── Tabs ─────────────────────────────────────────────────────────────
        dbc.Tabs(
            id='ta-tabs',
            active_tab='ta-tab-overview',
            children=[
                dbc.Tab(label='Overview',        tab_id='ta-tab-overview'),
                dbc.Tab(label='Build-up',        tab_id='ta-tab-buildup'),
                dbc.Tab(label='Chance Creation', tab_id='ta-tab-chance'),
                dbc.Tab(label='Def. Structure',  tab_id='ta-tab-def-struct'),
                dbc.Tab(label='Transitions',     tab_id='ta-tab-transitions'),
                dbc.Tab(label='Set Pieces',      tab_id='ta-tab-setpieces'),
            ],
            className="mb-3",
        ),

        dcc.Loading(
            id='ta-loading',
            type='circle',
            color=COLORS['gold'],
            children=html.Div(id='ta-content'),
        ),

    ], fluid=True, className="py-4")


# ---------------------------------------------------------------------------
# Callbacks
# ---------------------------------------------------------------------------

def register_team_analysis_callbacks(app):
    """Register all Team Analysis callbacks with the Dash app."""

    # ── Match selector updates when competition filter changes ────────────────
    @app.callback(
        Output('ta-match-selector', 'options'),
        Output('ta-match-selector', 'value'),
        Input('ta-competition-selector', 'value'),
    )
    def update_ta_match_options(competition):
        competitions = _normalize_competitions(competition)
        results = get_match_results()
        if competitions:
            results = [r for r in results if r['competition'] in competitions]
        results = sorted(results, key=lambda x: x['date'], reverse=True)

        show_tag = not competitions or len(competitions) > 1
        options  = []
        for r in results:
            comp_tag = _COMP_SHORT.get(r['competition'], r['competition'][:4])
            label    = (
                f"{str(r['date'])[:10]}  vs  {r['opponent']}  ({r['result']})"
                + (f"  · {comp_tag}" if show_tag else '')
            )
            options.append({'label': label, 'value': r['match_id']})

        return options, None

    # ── Tab content renderer ──────────────────────────────────────────────────
    @app.callback(
        Output('ta-content', 'children'),
        Input('ta-competition-selector', 'value'),
        Input('ta-tabs',                 'active_tab'),
        Input('ta-match-selector',       'value'),
    )
    def render_ta_content(competition, active_tab, match_ids):
        match_ids    = match_ids or None
        competitions = _normalize_competitions(competition)

        kwargs = dict(
            season=CURRENT_SEASON,
            competitions=competitions,
            match_ids=match_ids,
        )

        dispatch = {
            'ta-tab-overview':     build_overview_tab,
            'ta-tab-buildup':      build_buildup_tab,
            'ta-tab-chance':       build_chance_creation_tab,
            'ta-tab-def-struct':   build_def_structure_tab,
            'ta-tab-transitions':  build_transitions_tab,
            'ta-tab-setpieces':    build_set_pieces_tab,
        }

        builder = dispatch.get(active_tab)
        if builder:
            return builder(**kwargs)
        return html.Div()
