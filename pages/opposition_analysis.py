"""
CuléVision – Opposition Analysis page

Full opponent scouting page: season results, tactical profile, key players,
and shot map.  Driven by data produced by opposition_pipeline/.

Selector cascade: Country → Club → Competition
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
    get_opp_team_matches,
)
from pages.opposition_analysis_tabs import (
    build_summary,
    build_tactical,
    build_key_players,
    build_shot_map,
)

CURRENT_SEASON = SEASON

_DROPDOWN_STYLE = {
    'backgroundColor': '#1E2139',
    'color': COLORS['text_primary'],
    'border': f"1px solid {COLORS['dark_border']}",
    'borderRadius': '4px',
}


# ── Helpers ───────────────────────────────────────────────────────────────────

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


# ── Layout ────────────────────────────────────────────────────────────────────

def create_opposition_analysis_layout() -> dbc.Container:
    opponents = list_available_opponents()

    # Unique countries, sorted alphabetically
    countries = sorted({o.get('country', '') for o in opponents if o.get('country')})
    country_options = [{'label': c, 'value': c} for c in countries]

    return dbc.Container([
        # Page title
        dbc.Row([
            dbc.Col(
                html.H2(
                    "Opposition Analysis",
                    style={'color': COLORS['gold'], 'marginBottom': '0.25rem'},
                )
            ),
        ], className="mb-3"),

        # Selector row — cascade: Country → Club → Competition
        dbc.Row([
            dbc.Col([
                html.Label(
                    "Country",
                    style={'color': COLORS['text_secondary'], 'fontSize': '0.85rem'},
                ),
                dcc.Dropdown(
                    id='oa-country-select',
                    options=country_options,
                    placeholder="Select country…",
                    style=_DROPDOWN_STYLE,
                    clearable=False,
                ),
            ], md=3),
            dbc.Col([
                html.Label(
                    "Club",
                    style={'color': COLORS['text_secondary'], 'fontSize': '0.85rem'},
                ),
                dcc.Dropdown(
                    id='oa-team-select',
                    options=[],
                    placeholder="Select country first…",
                    style=_DROPDOWN_STYLE,
                    clearable=False,
                    disabled=True,
                ),
            ], md=4),
            dbc.Col([
                html.Label(
                    "Competition",
                    style={'color': COLORS['text_secondary'], 'fontSize': '0.85rem'},
                ),
                dcc.Dropdown(
                    id='oa-comp-select',
                    options=[],
                    placeholder="Select club first…",
                    style=_DROPDOWN_STYLE,
                    clearable=False,
                    disabled=True,
                ),
            ], md=3),
        ], className="mb-4"),

        # Date filter row
        dbc.Row([
            dbc.Col([
                html.Label(
                    "Show matches up to",
                    style={'color': COLORS['text_secondary'], 'fontSize': '0.85rem'},
                ),
                dcc.DatePickerSingle(
                    id='oa-date-filter',
                    placeholder='All dates',
                    display_format='DD MMM YYYY',
                    clearable=True,
                    style={'width': '100%'},
                    className='dark-date-picker',
                ),
            ], md=3),
        ], className="mb-4"),

        # Analysis tabs
        dbc.Tabs(
            [
                dbc.Tab(label="Season Summary",   tab_id="oa-tab-summary"),
                dbc.Tab(label="Tactical Profile", tab_id="oa-tab-tactical"),
                dbc.Tab(label="Key Players",      tab_id="oa-tab-players"),
                dbc.Tab(label="Shot Map",         tab_id="oa-tab-shots"),
            ],
            id='oa-tabs',
            active_tab='oa-tab-summary',
            className="mb-4",
        ),

        html.Div(id='oa-tab-content'),

    ], fluid=True, style={'paddingTop': '1rem'})


# ── Callbacks ─────────────────────────────────────────────────────────────────

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
        teams = sorted(
            [o['team_name'] for o in opponents if o.get('country') == country]
        )
        options = [{'label': t, 'value': t} for t in teams]
        return options, None, False

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
        comps = get_team_competitions(team)
        options = [{'label': 'All Competitions', 'value': 'all'}]
        for c in comps:
            options.append({'label': c.replace('_', ' '), 'value': c})
        return options, 'all', False

    @app.callback(
        Output('oa-tab-content', 'children'),
        Input('oa-tabs', 'active_tab'),
        Input('oa-team-select', 'value'),
        Input('oa-comp-select', 'value'),
        Input('oa-date-filter', 'date'),
        prevent_initial_call=False,
    )
    def render_tab(active_tab: str, team: str | None, comp_key: str | None,
                   date_cutoff: str | None):
        if not team:
            return _no_team_selected()

        if not comp_key:
            return html.P(
                "Select a competition to continue.",
                style={'color': COLORS['text_secondary'], 'padding': '2rem 0'},
            )

        country   = get_team_country(team)
        all_comps = get_team_competitions(team)

        # ── Load team events ─────────────────────────────────────────────────
        if comp_key == 'all':
            frames = [
                get_opp_team_events(team, country, c, CURRENT_SEASON)
                for c in all_comps
            ]
            non_empty = [f for f in frames if not f.empty]
            team_ev = (
                pd.concat(non_empty, ignore_index=True)
                if non_empty else pd.DataFrame()
            )
        else:
            team_ev = get_opp_team_events(team, country, comp_key, CURRENT_SEASON)

        # ── Apply date filter to events ───────────────────────────────────────
        if date_cutoff and not team_ev.empty and 'match_date' in team_ev.columns:
            team_ev = team_ev[team_ev['match_date'].astype(str).str[:10] <= date_cutoff[:10]]

        # ── Match count ──────────────────────────────────────────────────────
        if comp_key == 'all':
            all_results: list[dict] = []
            for c in all_comps:
                all_results.extend(
                    get_opp_team_matches(team, country, c, CURRENT_SEASON)
                )
        else:
            all_results = get_opp_team_matches(team, country, comp_key, CURRENT_SEASON)

        # ── Apply date filter to results ──────────────────────────────────────
        if date_cutoff:
            cutoff = date_cutoff[:10]
            all_results = [r for r in all_results if r.get('date', '') <= cutoff]

        n_matches = len(all_results)

        # ── Guard: no data at all ────────────────────────────────────────────
        if n_matches == 0 and team_ev.empty:
            return _no_data_alert()

        # ── Route to tab builder ─────────────────────────────────────────────
        if active_tab == 'oa-tab-summary':
            if comp_key == 'all':
                sections = []
                for c in all_comps:
                    comp_section = build_summary(team, country, c, date_cutoff)
                    sections.append(html.Div([
                        html.H5(
                            c.replace('_', ' '),
                            style={
                                'color': COLORS['gold'],
                                'marginTop': '1.5rem',
                                'marginBottom': '0.5rem',
                            },
                        ),
                        comp_section,
                    ]))
                content = html.Div(sections) if sections else _no_data_alert()
            else:
                content = build_summary(team, country, comp_key, date_cutoff)

        elif active_tab == 'oa-tab-tactical':
            content = build_tactical(team_ev, team, country, comp_key)

        elif active_tab == 'oa-tab-players':
            content = build_key_players(team_ev)

        elif active_tab == 'oa-tab-shots':
            content = build_shot_map(team_ev)

        else:
            content = html.P("Unknown tab.", style={'color': COLORS['text_secondary']})

        return content
