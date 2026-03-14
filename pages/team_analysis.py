"""
CuléVision - Team Analysis Page

Game-model focused longitudinal dashboard (season / rolling matches).
7 tabs covering the full tactical fingerprint of FC Barcelona.
"""

from dash import html, dcc
from dash.dependencies import Input, Output
import dash_bootstrap_components as dbc

from utils.config import COLORS
from utils.data_utils import get_match_results, CURRENT_SEASON

from pages.match_analysis_tabs.shared import page_header, GOLD
from pages.team_analysis_tabs import (
    build_identity_tab,
    build_in_possession_tab,
    build_out_of_possession_tab,
    build_def_transition_tab,
    build_att_transition_tab,
    build_goalkeeping_tab,
)


# ---------------------------------------------------------------------------
# Competition / match helpers (shared with callbacks)
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
            active_tab='ta-tab-identity',
            children=[
                dbc.Tab(label='Team Identity',         tab_id='ta-tab-identity'),
                dbc.Tab(label='In Possession',         tab_id='ta-tab-in-poss'),
                dbc.Tab(label='Out of Possession',     tab_id='ta-tab-out-poss'),
                dbc.Tab(label='Defensive Transition',  tab_id='ta-tab-def-trans'),
                dbc.Tab(label='Attacking Transition',  tab_id='ta-tab-att-trans'),
                dbc.Tab(label='Goalkeeping',           tab_id='ta-tab-gk'),
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

    # ── Match selector: updates when competition filter changes ──────────────
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
        options = []
        for r in results:
            comp_tag = _COMP_SHORT.get(r['competition'], r['competition'][:4])
            label = (
                f"{str(r['date'])[:10]}  vs  {r['opponent']}  ({r['result']})"
                + (f"  · {comp_tag}" if show_tag else '')
            )
            options.append({'label': label, 'value': r['match_id']})

        return options, None   # default: all matches selected

    # ── Tab content renderer ─────────────────────────────────────────────────
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
            'ta-tab-identity':  build_identity_tab,
            'ta-tab-in-poss':   build_in_possession_tab,
            'ta-tab-out-poss':  build_out_of_possession_tab,
            'ta-tab-def-trans': build_def_transition_tab,
            'ta-tab-att-trans': build_att_transition_tab,
            'ta-tab-gk':        build_goalkeeping_tab,
        }

        builder = dispatch.get(active_tab)
        if builder:
            return builder(**kwargs)
        return html.Div()
