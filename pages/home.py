"""
CuléVision - Home Page (Season Overview)
Rich dashboard with hero section, tournament overview, season summary
with top contributors and form trendline, and footer navigation.
"""

from pathlib import Path

from dash import html, dcc, callback_context
from dash.dependencies import Input, Output, State
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
import yaml

from utils.config import COLORS
from page_utils.visualizations import CHART_CONFIG

# ── Pipeline config (for modal dropdowns) ────────────────────────────────────

_PIPELINE_CONFIG_PATH = Path(__file__).parent.parent / 'opta_pipeline' / 'config.yaml'
try:
    with open(_PIPELINE_CONFIG_PATH) as _f:
        _pipeline_cfg = yaml.safe_load(_f)

    # All teams: Barcelona first, then all opponents alphabetically
    _all_teams = _pipeline_cfg.get('teams', [])
    _barca     = [t for t in _all_teams if t.get('team_code') == 'BAR']
    _opponents = [t for t in _all_teams if t.get('team_code') != 'BAR']

    _PIPELINE_TEAM_OPTIONS = (
        [{'label': 'All Teams', 'value': ''}]
        + [{'label': t['team_name'], 'value': t['team_name']} for t in _barca]
        + [{'label': t['team_name'], 'value': t['team_name']} for t in _opponents]
    )
    _PIPELINE_COMP_OPTIONS = [{'label': 'All Competitions', 'value': ''}] + [
        {'label': k.replace('_', ' '), 'value': k}
        for k in _pipeline_cfg.get('competitions', {}).keys()
    ]
except Exception:
    _PIPELINE_TEAM_OPTIONS = [{'label': 'All Teams', 'value': ''}]
    _PIPELINE_COMP_OPTIONS = [{'label': 'All Competitions', 'value': ''}]
from utils.data_utils import (
    get_player_stats, get_season_summary,
    get_tournament_summary, get_tournament_match_results,
    get_player_stats_by_competition, get_form_timeline,
    COMPETITION_NAMES,
)
from utils.logos import get_team_logo_path, get_tournament_logo_path

# Player name (from data) -> image file mapping
PLAYER_IMAGES = {
    'R. Lewandowski': 'assets/players/09-Lewandowski.webp',
    'Lamine Yamal': 'assets/players/10-Lamine.webp',
    'Raphinha': 'assets/players/11-Raphinha.webp',
    'Pedri': 'assets/players/08-Pedri.webp',
    'Ferran Torres': 'assets/players/07-Ferran_Torres.webp',
    'Gavi': 'assets/players/06-Gavi.webp',
    'Dani Olmo': 'assets/players/20-Olmo.webp',
    'Fermín López': 'assets/players/16-Fermin.webp',
    'F. de Jong': 'assets/players/21-De_Jong.webp',
    'J. Koundé': 'assets/players/23-Kounde.webp',
    'R. Araujo': 'assets/players/04-Araujo.webp',
    'Pau Cubarsí': 'assets/players/05-Cubarsi.webp',
    'Marc Casadó': 'assets/players/17-Casado.webp',
    'Alejandro Balde': 'assets/players/03-Balde.webp',
    'João Cancelo': 'assets/players/02-Cancelo.webp',
    'M. Rashford': 'assets/players/14-Rashford.webp',
    'A. Christensen': 'assets/players/15-Christensen.webp',
    'W. Szczęsny': 'assets/players/25-Szczesny.webp',
    'Eric García': 'assets/players/24-Eric_Garcia.webp',
    'Marc Bernal': 'assets/players/22-Bernal.webp',
    'Gerard Martín': 'assets/players/18-Martin.webp',
    'Joan García': 'assets/players/01-Joan_Garcia.webp',
    'R. Bardghji': 'assets/players/28-Bardghji.webp',
}

CHART_LAYOUT = dict(
    paper_bgcolor='rgba(0,0,0,0)',
    plot_bgcolor='rgba(0,0,0,0)',
    font=dict(color='#E8E9ED', size=12),
    margin=dict(l=40, r=40, t=50, b=40),
)


BARCA_FONT = "'Barcelona', 'Segoe UI', sans-serif"


# ── Helper builders ─────────────────────────────────────────────────────────

def _result_color(result):
    return {'W': '#28a745', 'D': '#ffc107', 'L': '#dc3545'}.get(result, '#A5A8B8')


def _build_recent_form(comp_name):
    """Build the recent form badges for a tournament card (last 5 matches)."""
    results = get_tournament_match_results(comp_name)
    last_5 = results[:5]

    if not last_5:
        return html.Div()

    badges = []
    for m in reversed(last_5):
        color = _result_color(m['result'])
        score = f"{m['barca_goals']}-{m['opponent_goals']}"
        opp_logo = get_team_logo_path(m['opponent'])

        logo_el = html.Div(
            m['opponent'][:3].upper(),
            title=m['opponent'],
            style={'width': '22px', 'height': '22px', 'lineHeight': '22px',
                   'textAlign': 'center', 'fontSize': '0.5rem', 'fontWeight': 700,
                   'color': COLORS['text_secondary'], 'backgroundColor': COLORS['dark_bg'],
                   'borderRadius': '50%', 'marginBottom': '2px'}
        )
        if opp_logo:
            logo_el = html.Img(
                src=opp_logo, title=m['opponent'],
                style={'width': '22px', 'height': '22px', 'objectFit': 'contain',
                       'marginBottom': '2px'}
            )

        badges.append(html.Div([
            logo_el,
            html.Div(m['result'], style={
                'backgroundColor': color,
                'color': 'white' if m['result'] != 'D' else 'black',
                'width': '20px', 'height': '20px', 'lineHeight': '20px',
                'textAlign': 'center', 'borderRadius': '3px',
                'fontWeight': 700, 'fontSize': '0.6rem',
                'margin': '0 auto',
            }),
            html.Div(score, style={
                'fontSize': '0.6rem', 'color': COLORS['text_secondary'],
                'textAlign': 'center', 'marginTop': '1px',
            }),
        ], style={
            'textAlign': 'center', 'width': '36px', 'flexShrink': '0',
            'display': 'flex', 'flexDirection': 'column', 'alignItems': 'center',
        }))

    return html.Div([
        html.Div("Recent Form", style={
            'fontSize': '0.7rem', 'color': COLORS['text_secondary'],
            'textAlign': 'center', 'marginBottom': '0.25rem',
            'fontWeight': 600, 'marginTop': '0.5rem',
        }),
        html.Div(badges, style={
            'display': 'flex', 'justifyContent': 'center', 'gap': '0.4rem'
        }),
    ])


def _create_hero_section(is_admin=False):
    """Top: centered FCB logo + subtitle."""
    admin_btn = html.Div()
    if is_admin:
        admin_btn = html.Div([
            dbc.Button(
                [html.I(className="fas fa-database me-2"), "Update Databases"],
                id='update-db-button', color="warning",
                style={'fontWeight': 'bold'}
            ),
        ], style={
            'position': 'absolute', 'top': '1rem', 'right': '1.5rem', 'zIndex': 2,
        })

    return html.Div([
        admin_btn,
        html.Div([
            html.Img(src='assets/logos/team/barcelona.svg', className="hero-logo",
                     style={'height': '150px'}),
            html.H2("A Game Analysis Tool for FC Barcelona",
                     style={'fontFamily': BARCA_FONT, 'color': COLORS['text_primary'],
                            'marginTop': '1rem', 'fontSize': '1.8rem',
                            'letterSpacing': '0.5px'}),
        ], className="text-center"),
    ], className="hero-section")


def _create_season_overview_header(summary):
    """Season Overview heading + stats bar."""
    stat_pills = []
    pill_data = [
        (summary.get('matches_played', 0), 'Matches', COLORS['gold']),
        (summary.get('wins', 0), 'Wins', '#28a745'),
        (summary.get('draws', 0), 'Draws', '#ffc107'),
        (summary.get('losses', 0), 'Losses', '#dc3545'),
        (summary.get('goals_for', 0), 'Goals For', COLORS['gold']),
        (summary.get('goals_against', 0), 'Goals Against', '#A5A8B8'),
    ]
    for value, label, color in pill_data:
        stat_pills.append(html.Div([
            html.Div(str(value), className="hero-stat-value", style={'color': color}),
            html.Div(label, className="hero-stat-label"),
        ], className="hero-stat-pill"))

    return html.Div([
        html.H3("Season Overview 2025\u201326", className="section-header",
                 style={'fontFamily': BARCA_FONT, 'fontSize': '2.2rem',
                        'marginTop': '0.5rem', 'borderBottom': 'none',
                        'marginBottom': '0.75rem'}),
        html.Div(stat_pills, className="hero-stats-bar"),
    ], className="mb-3")


def _create_tournament_card(comp_name, stats):
    """Single tournament overview card - dark themed with yellow logo circle."""
    logo = get_tournament_logo_path(comp_name)
    win_pct = stats.get('win_rate', 0)

    # Logo inside a yellow circle
    logo_circle = html.Div([
        html.Img(src=logo, className="tournament-logo") if logo else html.Div(),
    ], className="tournament-logo-circle")

    # Build recent form directly (no collapse)
    recent_form = _build_recent_form(comp_name)

    return dbc.Col([
        html.Div([
            dbc.CardBody([
                # Logo circle + name
                html.Div([
                    logo_circle,
                    html.H6(comp_name, className="mt-2 mb-1",
                             style={'color': COLORS['text_primary'], 'fontWeight': 700,
                                    'fontSize': '0.95rem', 'fontFamily': BARCA_FONT}),
                ], className="text-center mb-2"),

                # W-D-L record
                html.Div([
                    html.Span(f"W{stats['wins']}", className="tournament-record-item",
                              style={'color': '#fff', 'backgroundColor': '#28a745'}),
                    html.Span(f"D{stats['draws']}", className="tournament-record-item",
                              style={'color': '#0A0E27', 'backgroundColor': '#ffc107'}),
                    html.Span(f"L{stats['losses']}", className="tournament-record-item",
                              style={'color': '#fff', 'backgroundColor': '#dc3545'}),
                ], className="tournament-record justify-content-center"),

                # GF/GA + Possession
                html.Div([
                    html.Div([
                        html.Span(f"{stats['goals_for']}", style={
                            'fontWeight': 700, 'color': COLORS['gold']}),
                        html.Span(" GF  ", style={
                            'color': COLORS['text_secondary'], 'fontSize': '0.8rem'}),
                        html.Span(f"{stats['goals_against']}", style={
                            'fontWeight': 700, 'color': '#A5A8B8'}),
                        html.Span(" GA", style={
                            'color': COLORS['text_secondary'], 'fontSize': '0.8rem'}),
                    ], className="text-center", style={'fontSize': '0.9rem'}),
                    html.Div([
                        html.Span(f"Possession: {stats['avg_possession']}%",
                                  style={'color': COLORS['text_secondary'], 'fontSize': '0.8rem'}),
                    ], className="text-center mt-1"),
                ], className="my-2"),

                # Win rate bar
                html.Div([
                    html.Div(style={'width': f"{win_pct}%"},
                             className="tournament-win-bar-fill")
                ], className="tournament-win-bar"),
                html.Div(f"{win_pct}% win rate", className="tournament-expand-hint"),

                # Recent form (shown directly)
                recent_form,
            ])
        ], className="tournament-card h-100")
    ], lg=3, md=6, sm=12, className="mb-3")


def _create_tournament_section(tournament_data):
    """Section: Tournament overview cards."""
    cards = []
    for comp_name in ['La Liga', 'Champions League', 'Copa del Rey', 'Spanish Super Cup']:
        if comp_name in tournament_data:
            cards.append(_create_tournament_card(comp_name, tournament_data[comp_name]))

    return html.Div([
        html.H4("Tournament Overview", className="section-header",
                 style={'fontFamily': BARCA_FONT}),
        dbc.Row(cards),
    ], className="mb-4")


def _create_season_summary_section():
    """Section: Overall Season Summary with tournament filter, form trendline, and top contributors."""
    comp_options = [{'label': 'All Competitions', 'value': 'all'}]
    for name in COMPETITION_NAMES.values():
        comp_options.append({'label': name, 'value': name})

    return html.Div([
        html.H4("Overall Season Summary", className="section-header",
                 style={'fontFamily': BARCA_FONT}),

        # Tournament filter
        dbc.Row([
            dbc.Col([
                html.Label("Filter by Tournament:",
                           style={'color': COLORS['text_secondary'], 'fontSize': '0.85rem',
                                  'marginRight': '0.5rem'}),
                dcc.Dropdown(
                    id='season-summary-filter',
                    options=comp_options,
                    value='all',
                    clearable=False,
                    className="culevision-dropdown",
                    style={'width': '250px'},
                ),
            ], width="auto", className="d-flex align-items-center"),
        ], className="mb-3"),

        # Form trendline with metric selector
        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        dbc.Row([
                            dbc.Col([
                                html.Label("Metrics:",
                                           style={'color': COLORS['text_secondary'],
                                                  'fontSize': '0.8rem', 'marginRight': '0.5rem'}),
                                dcc.Checklist(
                                    id='trendline-metrics',
                                    options=[
                                        {'label': ' Points Per Game', 'value': 'ppg'},
                                        {'label': ' Goals Scored', 'value': 'gf'},
                                        {'label': ' Goals Conceded', 'value': 'ga'},
                                    ],
                                    value=['ppg'],
                                    inline=True,
                                    className="trendline-checklist",
                                    style={'display': 'flex', 'gap': '1rem',
                                           'color': COLORS['text_primary'], 'fontSize': '0.85rem'},
                                ),
                            ]),
                        ], className="mb-2"),
                        dcc.Graph(id='form-trendline-chart', config=CHART_CONFIG),
                    ])
                ])
            ], width=12, className="mb-3"),
        ]),

        # Top contributors
        html.H5("Top Contributors", className="mb-3",
                 style={'color': COLORS['gold'], 'fontFamily': BARCA_FONT,
                        'fontWeight': 600, 'fontSize': '1.15rem'}),
        dbc.Row(id='contributors-content'),
    ], className="mb-4")


def _create_player_card(player, goals, assists, appearances, img_path=None):
    """Single player contributor card - dark themed, no rank badge."""
    photo = html.Div(
        html.I(className="fas fa-user", style={'fontSize': '2.5rem', 'color': COLORS['text_secondary']}),
        className="player-photo d-flex align-items-center justify-content-center"
    )
    if img_path:
        photo = html.Img(src=img_path, className="player-photo")

    return dbc.Col([
        html.Div([
            photo,
            html.Div(player, style={
                'fontWeight': 700, 'color': COLORS['text_primary'], 'fontSize': '0.9rem',
                'fontFamily': BARCA_FONT, 'marginTop': '0.25rem'}),
            html.Div([
                html.Div([
                    html.Div(str(goals), className="player-stat-num"),
                    html.Div("Goals", className="player-stat-lbl"),
                ], className="player-stat-item"),
                html.Div([
                    html.Div(str(assists), className="player-stat-num"),
                    html.Div("Assists", className="player-stat-lbl"),
                ], className="player-stat-item"),
                html.Div([
                    html.Div(str(appearances), className="player-stat-num"),
                    html.Div("Apps", className="player-stat-lbl"),
                ], className="player-stat-item"),
            ], className="player-stat-row"),
        ], className="player-contrib-card h-100")
    ], lg=True, md=4, sm=6, className="mb-3")


def _build_top_contributors(stats_df, n=5):
    """Build the player cards from a stats DataFrame."""
    if stats_df.empty:
        return [html.P("No player data available.", style={'color': COLORS['text_secondary']})]

    top = stats_df[stats_df['goals'] > 0].head(n)
    if top.empty:
        return [html.P("No scorers in this competition.", style={'color': COLORS['text_secondary']})]

    cards = []
    for _, row in top.iterrows():
        img = PLAYER_IMAGES.get(row['player'])
        cards.append(_create_player_card(
            row['player'], int(row['goals']),
            int(row.get('assists', 0)),
            int(row['appearances']), img
        ))
    return cards


def _create_footer_nav():
    """Section: Quick-link footer navigation — 2×2 grid of all four pages."""
    links = [
        {
            'title': 'Barça DNA',
            'desc': 'Individual Barcelona player profiles, shot maps, touch heatmaps and match-by-match performance logs across all competitions.',
            'href': '/barca-dna',
            'icon': 'fas fa-running',
        },
        {
            'title': 'Barça IQ',
            'desc': "Season-wide FC Barcelona performance across attack, defence, attacking & defensive transitions and set pieces — filterable by competition and match.",
            'href': '/barca-iq',
            'icon': 'fas fa-chart-bar',
        },
        {
            'title': 'Match Report',
            'desc': 'Phase-based post-match tactical breakdown: overview, attack, defence, transitions and set pieces — with a downloadable PDF report.',
            'href': '/match-report',
            'icon': 'fas fa-futbol',
        },
        {
            'title': 'Opposition Analysis',
            'desc': "Scout upcoming opponents — match history, tactical tendencies, shot maps, key players and more across their full season data.",
            'href': '/opposition-analysis',
            'icon': 'fas fa-binoculars',
        },
    ]

    def _nav_col(link):
        return dbc.Col([
            html.A([
                html.Div([
                    html.Div(html.I(className=link['icon']), className="footer-nav-icon"),
                    html.Div(link['title'], className="footer-nav-title"),
                    html.Div(link['desc'], className="footer-nav-desc"),
                ], className="footer-nav-card")
            ], href=link['href'], style={'textDecoration': 'none'}),
        ], lg=6, md=6, className="mb-3")

    return html.Div([
        html.H4("Explore More", className="section-header",
                 style={'fontFamily': BARCA_FONT}),
        dbc.Row([_nav_col(links[0]), _nav_col(links[1])]),
        dbc.Row([_nav_col(links[2]), _nav_col(links[3])]),
    ], className="mb-4")


# ── Pipeline modal ────────────────────────────────────────────────────────────

def _create_pipeline_modal():
    """Admin-only modal for the unified data extraction pipeline."""
    _label = {'color': COLORS['text_secondary'], 'fontSize': '0.85rem', 'fontWeight': 600,
               'marginBottom': '0.4rem', 'display': 'block'}
    _hint  = {'color': COLORS['text_secondary'], 'fontSize': '0.8rem', 'marginBottom': '0.35rem'}

    return dbc.Modal([
        dbc.ModalHeader(
            dbc.ModalTitle([
                html.I(className="fas fa-database me-2", style={'color': COLORS['gold']}),
                "Update Databases",
            ]),
            style={'backgroundColor': COLORS['dark_secondary'],
                   'borderBottom': f"1px solid {COLORS['dark_border']}",
                   'color': COLORS['text_primary']},
        ),
        dbc.ModalBody([
            html.P(
                "Download and transform match event data. "
                "Leave Team and Competition blank to run the full pipeline for all teams.",
                style={'color': COLORS['text_secondary'], 'marginBottom': '1.25rem'},
            ),

            # ── Filters row ───────────────────────────────────────────────
            dbc.Row([
                dbc.Col([
                    html.Label("Team", style=_label),
                    dcc.Dropdown(
                        id='opp-team-select',
                        options=_PIPELINE_TEAM_OPTIONS,
                        value='',
                        clearable=False,
                        placeholder="All Teams",
                        style={'backgroundColor': COLORS['dark_tertiary']},
                    ),
                ], width=6),
                dbc.Col([
                    html.Label("Competition", style=_label),
                    dcc.Dropdown(
                        id='opp-comp-select',
                        options=_PIPELINE_COMP_OPTIONS,
                        value='',
                        clearable=False,
                        placeholder="All Competitions",
                        style={'backgroundColor': COLORS['dark_tertiary']},
                    ),
                ], width=6),
            ], className="mb-3"),

            # ── Options ───────────────────────────────────────────────────
            html.Label("Options", style=_label),
            dbc.Checklist(
                id='opp-pipeline-options',
                options=[
                    {'label': ' Force Re-scrape  (ignore Scoresway cache)',
                     'value': 'force_rescrape'},
                    {'label': ' Transform Only  (skip downloads, re-process existing JSONs)',
                     'value': 'transform_only'},
                ],
                value=[],
                style={'color': COLORS['text_primary'], 'fontSize': '0.9rem'},
                className="mb-3",
            ),

            # ── Info box ──────────────────────────────────────────────────
            html.Div([
                html.P([html.Strong("Full run: ", style={'color': COLORS['text_primary']}),
                        "scrapes Scoresway pages, downloads all match JSONs via browser, "
                        "transforms to Parquet."],
                       style=_hint),
                html.P([html.Strong("Force Re-scrape: ", style={'color': COLORS['text_primary']}),
                        "re-fetches competition result pages instead of using the local CSV cache."],
                       style=_hint),
                html.P([html.Strong("Transform Only: ", style={'color': COLORS['text_primary']}),
                        "re-processes previously downloaded JSONs. "
                        "No browser or network required."],
                       style={**_hint, 'marginBottom': 0}),
            ], style={
                'backgroundColor': COLORS['dark_bg'],
                'border': f"1px solid {COLORS['dark_border']}",
                'borderRadius': '6px', 'padding': '0.85rem',
            }),
        ], style={'backgroundColor': COLORS['dark_secondary'], 'color': COLORS['text_primary']}),

        dbc.ModalFooter([
            dbc.Button("Cancel", id='opp-modal-cancel', color="secondary", className="me-2"),
            dbc.Button(
                [html.I(className="fas fa-play me-2"), "Run Pipeline"],
                id='update-opp-run-button', color="warning",
                style={'fontWeight': 'bold'},
            ),
        ], style={'backgroundColor': COLORS['dark_secondary'],
                  'borderTop': f"1px solid {COLORS['dark_border']}"}),
    ],
        id='opp-pipeline-modal',
        is_open=False,
        size="lg",
        backdrop="static",
    )


# ── Main layout ─────────────────────────────────────────────────────────────

def create_home_layout(is_admin=False):
    """Create the Home page layout."""
    summary = get_season_summary()
    tournament_data = get_tournament_summary()

    children = [
        _create_hero_section(is_admin),
        _create_season_overview_header(summary),
        _create_tournament_section(tournament_data),
        _create_season_summary_section(),
        _create_footer_nav(),
    ]
    if is_admin:
        children.append(_create_pipeline_modal())

    return dbc.Container(children, fluid=True, className="py-4")


# ── Callbacks ───────────────────────────────────────────────────────────────

def register_home_callbacks(app):
    """Register interactive callbacks for the home page."""
    from dash import no_update

    @app.callback(
        Output('opp-pipeline-modal', 'is_open'),
        Input('update-db-button', 'n_clicks'),
        Input('opp-modal-cancel', 'n_clicks'),
        Input('update-opp-run-button', 'n_clicks'),
        State('opp-pipeline-modal', 'is_open'),
        prevent_initial_call=True,
    )
    def toggle_pipeline_modal(open_clicks, cancel_clicks, run_clicks, is_open):
        ctx = callback_context
        if not ctx.triggered:
            return is_open
        trigger = ctx.triggered[0]['prop_id'].split('.')[0]
        if trigger == 'update-db-button':
            return True
        return False  # cancel or run both close

    # Combined: form trendline + top contributors, both filtered by tournament
    @app.callback(
        Output('form-trendline-chart', 'figure'),
        Output('contributors-content', 'children'),
        Input('season-summary-filter', 'value'),
        Input('trendline-metrics', 'value'),
    )
    def update_season_summary(competition, metrics):
        # --- Form timeline ---
        all_timeline = get_form_timeline()

        if competition and competition != 'all':
            timeline = [t for t in all_timeline if t['competition'] == competition]
        else:
            timeline = all_timeline

        form_fig = go.Figure()

        if timeline:
            dates = [t['date'] for t in timeline]

            if 'ppg' in (metrics or []):
                cum_pts = 0
                ppg_vals = []
                for i, t in enumerate(timeline, 1):
                    cum_pts += t['points']
                    ppg_vals.append(round(cum_pts / i, 2))

                marker_colors = [_result_color(t['result']) for t in timeline]
                hover_text = [f"{t['opponent']} ({t['result']})<br>{t['competition']}"
                              for t in timeline]
                form_fig.add_trace(go.Scatter(
                    x=dates, y=ppg_vals, mode='lines+markers',
                    name='Points Per Game',
                    line=dict(color=COLORS['gold'], width=2),
                    marker=dict(color=marker_colors, size=8,
                                line=dict(color=COLORS['gold'], width=1)),
                    text=hover_text,
                    hovertemplate='%{text}<br>PPG: %{y}<extra></extra>',
                    fill='tozeroy', fillcolor='rgba(237, 187, 0, 0.06)',
                ))

            if 'gf' in (metrics or []):
                gf_vals = [t.get('barca_goals', 0) for t in timeline]
                form_fig.add_trace(go.Scatter(
                    x=dates, y=gf_vals, mode='lines+markers',
                    name='Goals Scored',
                    line=dict(color='#28a745', width=2, dash='dot'),
                    marker=dict(color='#28a745', size=6),
                    hovertemplate='Goals Scored: %{y}<extra></extra>',
                ))

            if 'ga' in (metrics or []):
                ga_vals = [t.get('opponent_goals', 0) for t in timeline]
                form_fig.add_trace(go.Scatter(
                    x=dates, y=ga_vals, mode='lines+markers',
                    name='Goals Conceded',
                    line=dict(color='#dc3545', width=2, dash='dot'),
                    marker=dict(color='#dc3545', size=6),
                    hovertemplate='Goals Conceded: %{y}<extra></extra>',
                ))

        form_fig.update_layout(
            **CHART_LAYOUT,
            height=350,
            title=dict(text='Form Trendline', font=dict(color=COLORS['gold'], size=14)),
            xaxis=dict(title='', gridcolor='rgba(255,255,255,0.05)', showgrid=True),
            yaxis=dict(title='', gridcolor='rgba(255,255,255,0.05)', showgrid=True),
            legend=dict(orientation='h', yanchor='bottom', y=1.02,
                        xanchor='center', x=0.5,
                        font=dict(color=COLORS['text_primary'], size=11)),
            showlegend=True,
        )

        # --- Top contributors ---
        if competition == 'all' or not competition:
            stats = get_player_stats()
        else:
            stats = get_player_stats_by_competition(competition)

        cards = _build_top_contributors(stats, n=5)

        return form_fig, cards
