"""
CuléVision – Opposition Analysis page

Full opponent scouting: scouting report, possession analysis, defensive shape,
transitions, set pieces, and an exploit map.

Selector cascade: Country → Club → Competition
Global filters:   Date cutoff | Venue | Half
"""

from __future__ import annotations

import pandas as pd
from dash import html, dcc
import dash_bootstrap_components as dbc
from dash.dependencies import Input, Output

from utils.config import COLORS
from utils.opposition_data_utils import (
    SEASON,
    list_available_opponents,
    get_team_competitions,
    get_team_country,
    get_opp_team_events,
    get_opp_all_events,
    get_opp_team_matches,
    _normalize,
)
from pages.opposition_analysis_tabs import (
    build_scouting,
    build_in_possession,
    build_defence,
    build_transitions,
    build_set_pieces,
    build_exploit,
)

CURRENT_SEASON = SEASON

_DROPDOWN_STYLE = {
    'backgroundColor': '#1E2139',
    'color': COLORS['text_primary'],
    'border': f"1px solid {COLORS['dark_border']}",
    'borderRadius': '4px',
}


# ── Helpers ────────────────────────────────────────────────────────────────────

def _no_team_selected() -> html.Div:
    return html.Div(
        html.P(
            "Select a country and team above to begin analysing the opposition.",
            style={
                'color': COLORS['text_secondary'],
                'textAlign': 'center',
                'padding': '4rem 0',
                'fontSize': '1.1rem',
            },
        )
    )


def _no_data_alert() -> dbc.Alert:
    return dbc.Alert(
        [
            html.I(className="fas fa-exclamation-triangle me-2"),
            "No data found for this selection. Run ",
            html.Strong("Scout Opponents"),
            " from the Home page to download opposition data.",
        ],
        color="warning",
        className="mt-3",
    )


def _apply_venue_filter(df: pd.DataFrame, team: str, venue: str) -> pd.DataFrame:
    """Filter events by home/away venue for the scouted team."""
    if venue == 'all' or df.empty or 'home_team' not in df.columns:
        return df
    needle    = _normalize(team)
    is_home   = df['home_team'].fillna('').apply(lambda s: needle in _normalize(s))
    if venue == 'home':
        return df[is_home].copy()
    return df[~is_home].copy()


def _apply_half_filter(df: pd.DataFrame, half: str) -> pd.DataFrame:
    """Filter events to first or second half using period_id column."""
    if half == 'all' or df.empty or 'period_id' not in df.columns:
        return df
    pid = 1 if half == 'first' else 2
    return df[df['period_id'] == pid].copy()


# ── Layout ─────────────────────────────────────────────────────────────────────

def create_opposition_analysis_layout() -> dbc.Container:
    opponents      = list_available_opponents()
    countries      = sorted({o.get('country', '') for o in opponents if o.get('country')})
    country_options = [{'label': c, 'value': c} for c in countries]

    return dbc.Container([
        # Page title
        dbc.Row([
            dbc.Col(html.H2(
                "Opposition Analysis",
                style={'color': COLORS['gold'], 'marginBottom': '0.25rem'},
            ))
        ], className="mb-3"),

        # Selector cascade: Country → Club → Competition
        dbc.Row([
            dbc.Col([
                html.Label("Country", style={'color': COLORS['text_secondary'], 'fontSize': '0.85rem'}),
                dcc.Dropdown(
                    id='oa-country-select', options=country_options,
                    placeholder="Select country…", style=_DROPDOWN_STYLE, clearable=False,
                ),
            ], md=3),
            dbc.Col([
                html.Label("Club", style={'color': COLORS['text_secondary'], 'fontSize': '0.85rem'}),
                dcc.Dropdown(
                    id='oa-team-select', options=[], placeholder="Select country first…",
                    style=_DROPDOWN_STYLE, clearable=False, disabled=True,
                ),
            ], md=4),
            dbc.Col([
                html.Label("Competition", style={'color': COLORS['text_secondary'], 'fontSize': '0.85rem'}),
                dcc.Dropdown(
                    id='oa-comp-select', options=[], placeholder="Select club first…",
                    style=_DROPDOWN_STYLE, clearable=False, disabled=True,
                ),
            ], md=3),
        ], className="mb-3"),

        # Global filters: Date | Venue | Half
        dbc.Row([
            dbc.Col([
                html.Label("Show matches up to", style={'color': COLORS['text_secondary'], 'fontSize': '0.85rem'}),
                dcc.DatePickerSingle(
                    id='oa-date-filter', placeholder='All dates',
                    display_format='DD MMM YYYY', clearable=True,
                    style={'width': '100%'}, className='dark-date-picker',
                ),
            ], md=3),
            dbc.Col([
                html.Label("Venue", style={'color': COLORS['text_secondary'], 'fontSize': '0.85rem'}),
                dcc.Dropdown(
                    id='oa-venue-filter',
                    options=[
                        {'label': 'All Venues', 'value': 'all'},
                        {'label': 'Home Only',  'value': 'home'},
                        {'label': 'Away Only',  'value': 'away'},
                    ],
                    value='all', clearable=False, style=_DROPDOWN_STYLE,
                ),
            ], md=2),
            dbc.Col([
                html.Label("Half", style={'color': COLORS['text_secondary'], 'fontSize': '0.85rem'}),
                dcc.Dropdown(
                    id='oa-half-filter',
                    options=[
                        {'label': 'Full Match', 'value': 'all'},
                        {'label': '1st Half',   'value': 'first'},
                        {'label': '2nd Half',   'value': 'second'},
                    ],
                    value='all', clearable=False, style=_DROPDOWN_STYLE,
                ),
            ], md=2),
        ], className="mb-4"),

        # Analysis tabs
        dbc.Tabs(
            [
                dbc.Tab(label="Scouting",      tab_id="oa-tab-scouting"),
                dbc.Tab(label="In Possession", tab_id="oa-tab-possession"),
                dbc.Tab(label="Out of Poss.",  tab_id="oa-tab-defence"),
                dbc.Tab(label="Transitions",   tab_id="oa-tab-transitions"),
                dbc.Tab(label="Set Pieces",    tab_id="oa-tab-setpieces"),
                dbc.Tab(label="Exploits",      tab_id="oa-tab-exploit"),
            ],
            id='oa-tabs',
            active_tab='oa-tab-scouting',
            className="mb-4",
        ),

        html.Div(id='oa-tab-content'),

    ], fluid=True, style={'paddingTop': '1rem'})


# ── Callbacks ──────────────────────────────────────────────────────────────────

def register_opposition_analysis_callbacks(app) -> None:

    @app.callback(
        Output('oa-team-select', 'options'),
        Output('oa-team-select', 'value'),
        Output('oa-team-select', 'disabled'),
        Input('oa-country-select', 'value'),
        prevent_initial_call=True,
    )
    def update_team_options(country: str | None):
        if not country:
            return [], None, True
        opponents = list_available_opponents()
        teams     = sorted([o['team_name'] for o in opponents if o.get('country') == country])
        return [{'label': t, 'value': t} for t in teams], None, False

    @app.callback(
        Output('oa-comp-select', 'options'),
        Output('oa-comp-select', 'value'),
        Output('oa-comp-select', 'disabled'),
        Input('oa-team-select', 'value'),
        prevent_initial_call=True,
    )
    def update_comp_options(team: str | None):
        if not team:
            return [], None, True
        comps   = get_team_competitions(team)
        options = [{'label': 'All Competitions', 'value': 'all'}]
        for c in comps:
            options.append({'label': c.replace('_', ' '), 'value': c})
        return options, 'all', False

    @app.callback(
        Output('oa-tab-content', 'children'),
        Input('oa-tabs',         'active_tab'),
        Input('oa-team-select',  'value'),
        Input('oa-comp-select',  'value'),
        Input('oa-date-filter',  'date'),
        Input('oa-venue-filter', 'value'),
        Input('oa-half-filter',  'value'),
        prevent_initial_call=False,
    )
    def render_tab(
        active_tab: str,
        team: str | None,
        comp_key: str | None,
        date_cutoff: str | None,
        venue_filter: str,
        half_filter: str,
    ):
        if not team:
            return _no_team_selected()
        if not comp_key:
            return html.P(
                "Select a competition to continue.",
                style={'color': COLORS['text_secondary'], 'padding': '2rem 0'},
            )

        country   = get_team_country(team)
        all_comps = get_team_competitions(team)

        # ── Load all events (both teams) ──────────────────────────────────────
        if comp_key == 'all':
            frames = [get_opp_all_events(team, country, c, CURRENT_SEASON) for c in all_comps]
            non_empty = [f for f in frames if not f.empty]
            all_ev = pd.concat(non_empty, ignore_index=True) if non_empty else pd.DataFrame()
        else:
            all_ev = get_opp_all_events(team, country, comp_key, CURRENT_SEASON)

        # ── Date filter ───────────────────────────────────────────────────────
        if date_cutoff and not all_ev.empty and 'match_date' in all_ev.columns:
            all_ev = all_ev[all_ev['match_date'].astype(str).str[:10] <= date_cutoff[:10]]

        # ── Venue + half filters ──────────────────────────────────────────────
        all_ev = _apply_venue_filter(all_ev, team, venue_filter or 'all')
        all_ev = _apply_half_filter(all_ev, half_filter or 'all')

        # ── Split into opp_ev (scouted team) and bar_ev (Barcelona) ──────────
        if not all_ev.empty and 'team_name' in all_ev.columns:
            needle  = _normalize(team)
            is_opp  = all_ev['team_name'].fillna('').apply(lambda s: needle in _normalize(s))
            opp_ev  = all_ev[is_opp].copy()
            bar_ev  = all_ev[~is_opp].copy()
        else:
            opp_ev = all_ev.copy()
            bar_ev = pd.DataFrame()

        # ── Match results ─────────────────────────────────────────────────────
        if comp_key == 'all':
            all_results: list[dict] = []
            for c in all_comps:
                all_results.extend(get_opp_team_matches(team, country, c, CURRENT_SEASON))
        else:
            all_results = get_opp_team_matches(team, country, comp_key, CURRENT_SEASON)

        if date_cutoff:
            cutoff      = date_cutoff[:10]
            all_results = [r for r in all_results if r.get('date', '') <= cutoff]

        if venue_filter == 'home':
            all_results = [r for r in all_results if r.get('is_home')]
        elif venue_filter == 'away':
            all_results = [r for r in all_results if not r.get('is_home')]

        n_matches = len(all_results)

        # ── Guard: nothing to show ────────────────────────────────────────────
        if n_matches == 0 and opp_ev.empty:
            return _no_data_alert()

        # ── Route to tab builder ──────────────────────────────────────────────
        if active_tab == 'oa-tab-scouting':
            content = build_scouting(team, country, comp_key, all_results, opp_ev, n_matches)

        elif active_tab == 'oa-tab-possession':
            content = build_in_possession(opp_ev, team)

        elif active_tab == 'oa-tab-defence':
            content = build_defence(opp_ev, bar_ev, n_matches)

        elif active_tab == 'oa-tab-transitions':
            content = build_transitions(opp_ev, bar_ev, team)

        elif active_tab == 'oa-tab-setpieces':
            content = build_set_pieces(opp_ev, bar_ev)

        elif active_tab == 'oa-tab-exploit':
            content = build_exploit(opp_ev, bar_ev, team, n_matches)

        else:
            content = html.P("Unknown tab.", style={'color': COLORS['text_secondary']})

        return content
