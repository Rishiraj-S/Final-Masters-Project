"""
CuléVision – Opposition Analysis page

Full opponent scouting across five tabs:
  Overview         — season record, form, style radar, key players
  Build Up & Attack — pass map, shot map, zone distribution
  Transitions      — offensive and defensive transitions
  Defense          — defensive actions, pressing, shots allowed
  Set Pieces       — corners, free kicks, throw-ins

Selector cascade: Country → Club → Competition
Global filters:   Date cutoff | Venue
Calendar:         Select specific matches for analysis
"""

from __future__ import annotations

import calendar
from datetime import datetime

from dash import html, dcc
from dash.dependencies import Input, Output, State, ALL
from dash import ctx
import dash_bootstrap_components as dbc

from utils.config import COLORS
from utils.opposition_data_utils import (
    SEASON,
    list_available_opponents,
    get_team_competitions,
    get_team_country,
    get_opp_team_matches,
    load_opp_events,
)
from pages.opposition_analysis_tabs import (
    build_overview,
    build_buildup,
    build_chance_creation,
    build_transitions,
    build_defence,
    build_set_pieces,
    register_overview_callbacks,
    register_buildup_callbacks,
    register_chance_creation_callbacks,
    register_transitions_callbacks,
    register_defence_callbacks,
    register_set_pieces_callbacks,
)
from pages.match_report import page_header
from utils.logos import get_team_logo_path, get_tournament_logo_path, get_country_flag_path
from page_utils.visualizations import GOLD
from page_utils.match_calendar import build_calendar_grid, register_calendar_callbacks

CURRENT_SEASON = SEASON

_DROPDOWN_STYLE = {
    'backgroundColor': '#1E2139',
    'color': COLORS['text_primary'],
    'border': f"1px solid {COLORS['dark_border']}",
    'borderRadius': '4px',
}

_LOGO_LABEL_STYLE = {'display': 'flex', 'alignItems': 'center', 'gap': '8px'}
_LOGO_IMG_STYLE   = {'height': '20px', 'width': '20px', 'objectFit': 'contain', 'flexShrink': '0'}


def _country_option(country: str) -> dict:
    flag_path = get_country_flag_path(country)
    children  = []
    if flag_path:
        children.append(html.Img(src=flag_path, style=_LOGO_IMG_STYLE))
    children.append(html.Span(country))
    return {'label': html.Div(children, style=_LOGO_LABEL_STYLE), 'value': country}


def _team_option(team: str) -> dict:
    logo_path = get_team_logo_path(team)
    children  = []
    if logo_path:
        children.append(html.Img(src=logo_path, style=_LOGO_IMG_STYLE))
    children.append(html.Span(team))
    return {'label': html.Div(children, style=_LOGO_LABEL_STYLE), 'value': team}


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
            html.I(className='fas fa-exclamation-triangle me-2'),
            'No data found for this selection. Run ',
            html.Strong('Scout Opponents'),
            ' from the Home page to download opposition data.',
        ],
        color='warning',
        className='mt-3',
    )


# Short competition labels for the calendar badge (covers all 21 comps).
_COMP_SHORT = {
    'Spain_Primera_Division':   'La Liga',
    'Spain_Copa_del_Rey':       'Copa',
    'Spain_Super_Cup':          'Supercopa',
    'UEFA_Champions_League':    'UCL',
    'UEFA_Europa_League':       'UEL',
    'UEFA_Conference_League':   'UECL',
    'England_Premier_League':   'EPL',
    'England_FA_Cup':           'FA Cup',
    'England_EFL_Cup':          'EFL Cup',
    'Germany_Bundesliga':       'Bundesliga',
    'Germany_DFB_Pokal':        'DFB-Pokal',
    'Belgium_First_Division_A': 'Pro League',
    'Belgium_Cup':              'Belg. Cup',
    'France_Ligue_1':           'Ligue 1',
    'France_Coupe_de_France':   'Coupe FR',
    'Greece_Super_League':      'Super Lg',
    'Greece_Cup':               'GR Cup',
    'Denmark_Superliga':        'Superliga',
    'Denmark_DBU_Pokalen':      'DBU Cup',
    'Czech_First_League':       'Chance Lg',
    'Czech_Cup':                'CZ Cup',
}
def _comp_short(comp_key: str) -> str:
    return _COMP_SHORT.get(comp_key, (comp_key or '').replace('_', ' '))


def _comp_logo(comp_key: str) -> str:
    # TOURNAMENT_LOGOS is keyed by competition folder key, so pass it directly.
    return get_tournament_logo_path(comp_key)


def _filter_results(results: list[dict], date_cutoff: str | None,
                    venue: str | None) -> list[dict]:
    """Apply the date-cutoff and venue filters to a match-result list.

    Shared by the calendar loader and the Overview renderer so both honour the
    same selection.  Match-id selection is handled separately (it *is* the
    calendar's output).
    """
    out = results
    if date_cutoff:
        cut = date_cutoff[:10]
        out = [r for r in out if str(r.get('date', '')) <= cut]
    if venue == 'home':
        out = [r for r in out if r.get('is_home')]
    elif venue == 'away':
        out = [r for r in out if not r.get('is_home')]
    return out


# ── Calendar Builder ────────────────────────────────────────────────────────────

def _build_oa_calendar_grid(
    year: int, month: int,
    match_data: list[dict],
    selected_match_ids: list[str],
) -> html.Div:
    """Opposition calendar grid — thin wrapper over the shared builder."""
    return build_calendar_grid(
        year, month, match_data, selected_match_ids,
        id_type='oa-cal-match-btn',
        score_fn=lambda m: f"{m.get('gf', 0)}-{m.get('ga', 0)}",
        comp_value_fn=lambda m: m.get('competition_key', ''),
        comp_short_fn=_comp_short,
        comp_logo_fn=_comp_logo,
        opp_logo_size=18, opp_logo_margin=3, opp_font='0.75rem',
        tourn_logo_size=12, tourn_logo_margin=2, tourn_font='0.6rem',
        tourn_pad='1px 3px',
        score_font='0.65rem', score_margin=4,
        button_padding='3px 5px',
    )


# ── Layout ─────────────────────────────────────────────────────────────────────

def create_opposition_analysis_layout() -> dbc.Container:
    opponents       = list_available_opponents()
    countries       = sorted({o.get('country', '') for o in opponents if o.get('country')})
    country_options = [_country_option(c) for c in countries]

    now = datetime.now()
    init_year, init_month = now.year, now.month

    return dbc.Container([
        dcc.Store(id='oa-match-data',       data=[]),
        dcc.Store(id='oa-calendar-month',   data={'year': init_year, 'month': init_month}),
        dcc.Store(id='oa-selected-matches', data=[]),

        page_header('Opposition Analysis'),
        html.Hr(),

        # ── Selector cascade + Filters ────────────────────────────────────────
        dbc.Row([
            dbc.Col([
                html.Label('Country', style={'color': COLORS['text_secondary'], 'fontSize': '0.85rem'}),
                dcc.Dropdown(
                    id='oa-country-select', options=country_options,
                    placeholder='Select country…', style=_DROPDOWN_STYLE, clearable=False,
                    optionHeight=36,
                ),
            ], md=2),
            dbc.Col([
                html.Label('Club', style={'color': COLORS['text_secondary'], 'fontSize': '0.85rem'}),
                dcc.Dropdown(
                    id='oa-team-select', options=[], placeholder='Select country first…',
                    style=_DROPDOWN_STYLE, clearable=False, disabled=True,
                    optionHeight=36,
                ),
            ], md=3),
            dbc.Col([
                html.Label('Competition', style={'color': COLORS['text_secondary'], 'fontSize': '0.85rem'}),
                dcc.Dropdown(
                    id='oa-comp-select', options=[], placeholder='Select club first…',
                    style=_DROPDOWN_STYLE, clearable=False, disabled=True,
                ),
            ], md=2),
            dbc.Col([
                html.Label('Show matches up to', style={'color': COLORS['text_secondary'], 'fontSize': '0.85rem'}),
                dcc.DatePickerSingle(
                    id='oa-date-filter', placeholder='All dates',
                    display_format='DD MMM YYYY', clearable=True,
                    style={'width': '100%'}, className='dark-date-picker',
                ),
            ], md=2),
            dbc.Col([
                html.Label('Venue', style={'color': COLORS['text_secondary'], 'fontSize': '0.85rem'}),
                dcc.Dropdown(
                    id='oa-venue-filter',
                    options=[
                        {'label': 'All Venues', 'value': 'all'},
                        {'label': 'Home Only',  'value': 'home'},
                        {'label': 'Away Only',  'value': 'away'},
                    ],
                    value='all', clearable=False, style=_DROPDOWN_STYLE,
                ),
            ], md=3),
        ], className='mb-3'),

        # ── Calendar Navigation Row ───────────────────────────────────────────
        dbc.Row([
            dbc.Col([
                html.Div([
                    html.Button('◀', id='oa-prev-month', n_clicks=0, style={
                        'background': 'none', 'border': f'1px solid {COLORS["dark_border"]}',
                        'color': COLORS['text_primary'], 'borderRadius': '6px',
                        'padding': '6px 14px', 'cursor': 'pointer', 'fontSize': '1rem',
                    }),
                    html.Div(
                        f"{calendar.month_name[init_month]} {init_year}",
                        id='oa-month-label',
                        style={
                            'width': '150px', 'textAlign': 'center', 'fontWeight': 'bold',
                            'fontSize': '1.1rem', 'color': COLORS['text_primary'],
                            'display': 'inline-block',
                        },
                    ),
                    html.Button('▶', id='oa-next-month', n_clicks=0, style={
                        'background': 'none', 'border': f'1px solid {COLORS["dark_border"]}',
                        'color': COLORS['text_primary'], 'borderRadius': '6px',
                        'padding': '6px 14px', 'cursor': 'pointer', 'fontSize': '1rem',
                    }),
                ], style={'display': 'flex', 'alignItems': 'center', 'gap': '8px'}),
            ], md=4),
            dbc.Col([
                html.Div([
                    html.Div(id='oa-selected-indicator-text', style={'display': 'inline-block'}),
                    html.Button('Clear', id='oa-clear-selection-btn', n_clicks=0,
                                style={'display': 'none'}),
                ], id='oa-selected-indicator', style={
                    'textAlign': 'right', 'display': 'flex',
                    'alignItems': 'center', 'justifyContent': 'flex-end',
                }),
            ], md=8),
        ], className='mb-2'),

        html.Div(id='oa-calendar-container', className='mb-4'),

        # ── Tabs ──────────────────────────────────────────────────────────────
        dbc.Tabs(
            id='oa-tabs',
            active_tab='oa-tab-overview',
            children=[
                dbc.Tab(label='Overview',         tab_id='oa-tab-overview'),
                dbc.Tab(label='Build-Up',         tab_id='oa-tab-buildup'),
                dbc.Tab(label='Chance Creation',  tab_id='oa-tab-chance'),
                dbc.Tab(label='Transitions',      tab_id='oa-tab-transitions'),
                dbc.Tab(label='Defense',          tab_id='oa-tab-defense'),
                dbc.Tab(label='Set Pieces',       tab_id='oa-tab-setpieces'),
            ],
            className='mb-3',
        ),

        dcc.Loading(
            id='oa-loading',
            type='circle',
            color=COLORS['gold'],
            children=html.Div(id='oa-tab-content'),
        ),

    ], fluid=True, className='py-4')


# ── Callbacks ──────────────────────────────────────────────────────────────────

def register_opposition_analysis_callbacks(app) -> None:
    # Register tab callbacks (skeleton + callback pattern)
    register_overview_callbacks(app)
    register_buildup_callbacks(app)
    register_chance_creation_callbacks(app)
    register_transitions_callbacks(app)
    register_defence_callbacks(app)
    register_set_pieces_callbacks(app)

    # Month navigation, multi-select toggle and selection indicator (shared).
    # Both Stores are also written by page-specific callbacks (load_match_data,
    # reset_selection_on_team_change), so the shared writers allow duplicates.
    register_calendar_callbacks(
        app, 'oa',
        month_allow_duplicate=True,
        selection_allow_duplicate=True,
    )

    # ── Country → Team options ────────────────────────────────────────────────
    @app.callback(
        Output('oa-team-select', 'options'),
        Output('oa-team-select', 'value'),
        Output('oa-team-select', 'disabled'),
        Input('oa-country-select', 'value'),
        prevent_initial_call=True,
    )
    def update_team_options(country):
        if not country:
            return [], None, True
        opponents = list_available_opponents()
        teams     = sorted([o['team_name'] for o in opponents if o.get('country') == country])
        return [_team_option(t) for t in teams], None, False

    # ── Team → Competition options ─────────────────────────────────────────────
    @app.callback(
        Output('oa-comp-select', 'options'),
        Output('oa-comp-select', 'value'),
        Output('oa-comp-select', 'disabled'),
        Input('oa-team-select', 'value'),
        prevent_initial_call=True,
    )
    def update_comp_options(team):
        if not team:
            return [], None, True
        comps   = get_team_competitions(team)
        options = [{'label': 'All Competitions', 'value': 'all'}]
        for c in comps:
            options.append({'label': c.replace('_', ' '), 'value': c})
        return options, 'all', False

    # ── Team/Comp/Filters → load match data + init calendar month ────────────
    # The calendar reflects the active venue + date filters, so the matches you
    # can see and select are exactly those that feed the tabs.  Changing only a
    # filter keeps the current month in view; changing team/comp jumps to the
    # latest matching match.
    @app.callback(
        Output('oa-match-data',     'data'),
        Output('oa-calendar-month', 'data'),
        Output('oa-month-label',    'children'),
        Input('oa-team-select',  'value'),
        Input('oa-comp-select',  'value'),
        Input('oa-venue-filter', 'value'),
        Input('oa-date-filter',  'date'),
        State('oa-calendar-month', 'data'),
        prevent_initial_call=True,
    )
    def load_match_data(team, comp, venue, date_cutoff, cur_month):
        now = datetime.now()
        default_month = {'year': now.year, 'month': now.month}
        default_label = f"{calendar.month_name[now.month]} {now.year}"

        if not team or not comp:
            return [], default_month, default_label

        country   = get_team_country(team)
        all_comps = get_team_competitions(team)

        if comp == 'all':
            results = []
            for c in all_comps:
                results.extend(get_opp_team_matches(team, country, c, CURRENT_SEASON))
        else:
            results = get_opp_team_matches(team, country, comp, CURRENT_SEASON)

        results = _filter_results(results, date_cutoff, venue)
        results.sort(key=lambda r: r.get('date', ''))

        # Keep the current month when only a filter changed; otherwise jump to
        # the latest matching match (or fall back to the current month).
        filter_only = ctx.triggered_id in ('oa-venue-filter', 'oa-date-filter')
        if filter_only and cur_month:
            month_data = cur_month
        elif results:
            latest     = results[-1]['date']
            month_data = {'year': int(latest[:4]), 'month': int(latest[5:7])}
        else:
            month_data = default_month

        label = f"{calendar.month_name[month_data['month']]} {month_data['year']}"
        return results, month_data, label

    # ── Reset match selection when team changes ───────────────────────────────
    @app.callback(
        Output('oa-selected-matches', 'data'),
        Input('oa-team-select', 'value'),
        prevent_initial_call=True,
    )
    def reset_selection_on_team_change(_):
        return []

    # ── Render calendar grid ──────────────────────────────────────────────────
    @app.callback(
        Output('oa-calendar-container', 'children'),
        Input('oa-calendar-month',   'data'),
        Input('oa-match-data',       'data'),
        Input('oa-selected-matches', 'data'),
    )
    def render_calendar(cal_month, match_data, selected_match_ids):
        if not match_data:
            return html.P(
                "Select a team and competition above to see the match calendar.",
                style={'color': COLORS['text_secondary'], 'fontSize': '0.9rem', 'padding': '1rem 0'},
            )
        year, month = cal_month['year'], cal_month['month']
        return _build_oa_calendar_grid(year, month, match_data, selected_match_ids or [])

    # ── Main tab renderer ─────────────────────────────────────────────────────
    @app.callback(
        Output('oa-tab-content', 'children'),
        Input('oa-tabs',              'active_tab'),
        Input('oa-team-select',       'value'),
        Input('oa-comp-select',       'value'),
        Input('oa-date-filter',       'date'),
        Input('oa-venue-filter',      'value'),
        Input('oa-selected-matches',  'data'),
        prevent_initial_call=False,
    )
    def render_tab(
        active_tab: str,
        team: str | None,
        comp_key: str | None,
        date_cutoff: str | None,
        venue_filter: str,
        selected_match_ids: list | None,
    ):
        if not team:
            return _no_team_selected()
        if not comp_key:
            return html.P(
                'Select a competition to continue.',
                style={'color': COLORS['text_secondary'], 'padding': '2rem 0'},
            )

        country   = get_team_country(team)
        all_comps = get_team_competitions(team)

        # ── Overview: load data synchronously (no callbacks) ──────────────────
        if active_tab == 'oa-tab-overview':
            # Events: unified loader applies venue + date + match-id filters and
            # splits opp_ev / opponent-ev robustly by team_code.
            opp_ev, bar_ev = load_opp_events(
                team, comp_key, venue_filter or 'all',
                selected_match_ids, date_cutoff, CURRENT_SEASON,
            )

            # Results: same filters via the shared helper.
            if comp_key == 'all':
                all_results: list[dict] = []
                for c in all_comps:
                    all_results.extend(get_opp_team_matches(team, country, c, CURRENT_SEASON))
            else:
                all_results = get_opp_team_matches(team, country, comp_key, CURRENT_SEASON)

            all_results = _filter_results(all_results, date_cutoff, venue_filter)
            if selected_match_ids:
                all_results = [r for r in all_results if r.get('match_id') in selected_match_ids]

            n_matches = len(all_results)
            if n_matches == 0 and opp_ev.empty:
                return _no_data_alert()
            return build_overview(team, country, comp_key, all_results, opp_ev, bar_ev, n_matches)

        # ── All other tabs: return skeleton; callbacks populate charts ─────────
        if active_tab == 'oa-tab-buildup':
            return build_buildup(team, comp_key)

        if active_tab == 'oa-tab-chance':
            return build_chance_creation(team, comp_key)

        if active_tab == 'oa-tab-transitions':
            return build_transitions(team, comp_key)

        if active_tab == 'oa-tab-defense':
            return build_defence(team, comp_key)

        if active_tab == 'oa-tab-setpieces':
            return build_set_pieces(team, comp_key)

        return html.P('Unknown tab.', style={'color': COLORS['text_secondary']})
