"""
CuléVision - Opposition Analysis Page
Full team profile for opponents based on their matches vs Barcelona.
"""

from dash import html, dcc
from dash.dependencies import Input, Output, State
import dash_bootstrap_components as dbc
import plotly.graph_objects as go

from utils.config import COLORS
from utils.data_utils import (
    get_all_events,
    get_all_teams,
    get_team_events,
    get_match_results,
    CURRENT_SEASON,
    filter_own_goals,
)
from pages.match_analysis_tabs.shared import (
    CHART_LAYOUT_DEFAULTS,
    CHART_CONFIG,
    add_pitch_background,
    PITCH_AXIS_FULL,
    stat_card,
    section_card,
    kpi_row,
    empty_fig,
    page_header,
    render_heatmap_img,
    GOLD,
    HOME_COLOR,
    AWAY_COLOR,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_ALL_COMPETITIONS = [
    {'label': 'All Competitions', 'value': 'all'},
    {'label': 'La Liga',          'value': 'La Liga'},
    {'label': 'Champions League', 'value': 'Champions League'},
    {'label': 'Copa del Rey',     'value': 'Copa del Rey'},
    {'label': 'Spanish Super Cup','value': 'Spanish Super Cup'},
]



def _filter_results_for_opponent(team_name, competition):
    """Get match results filtered to a specific opponent."""
    results = get_match_results()
    results = [r for r in results if r['opponent'] == team_name]
    if competition and competition != 'all':
        results = [r for r in results if r['competition'] == competition]
    return results


def _h2h_record(results):
    """Compute H2H summary dict from a filtered results list."""
    barca_wins = sum(1 for r in results if r['result'] == 'W')
    draws      = sum(1 for r in results if r['result'] == 'D')
    opp_wins   = sum(1 for r in results if r['result'] == 'L')
    barca_gf   = sum(r['barca_goals'] for r in results)
    barca_ga   = sum(r['opponent_goals'] for r in results)
    return {
        'matches':    len(results),
        'barca_wins': barca_wins,
        'draws':      draws,
        'opp_wins':   opp_wins,
        'barca_gf':   barca_gf,
        'barca_ga':   barca_ga,
    }


# ---------------------------------------------------------------------------
# Tab builders
# ---------------------------------------------------------------------------

def _build_h2h(team_name, competition):
    results = _filter_results_for_opponent(team_name, competition)
    if not results:
        return html.P("No head-to-head data found.", style={'color': COLORS['text_secondary']})

    rec = _h2h_record(results)
    kpi = kpi_row(rec, [
        ('matches',    'Matches'),
        ('barca_wins', 'Barça Wins'),
        ('draws',      'Draws'),
        ('opp_wins',   f'{team_name} Wins'),
        ('barca_gf',   'Barça GF'),
        ('barca_ga',   'Barça GA'),
    ], colors={
        'barca_wins': HOME_COLOR,
        'opp_wins':   AWAY_COLOR,
    })

    result_color = {'W': '#1a5c2a', 'D': '#5c4a1a', 'L': '#5c1a1a'}
    rows = []
    for r in sorted(results, key=lambda x: x['date'], reverse=True):
        if r['is_home']:
            home, away = 'Barcelona', r['opponent']
            score = f"{r['barca_goals']} – {r['opponent_goals']}"
        else:
            home, away = r['opponent'], 'Barcelona'
            score = f"{r['opponent_goals']} – {r['barca_goals']}"
        result_badge = dbc.Badge(r['result'],
                                 color='success' if r['result'] == 'W'
                                 else ('warning' if r['result'] == 'D' else 'danger'),
                                 className="me-1")
        rows.append(html.Tr([
            html.Td(str(r['date'])[:10]),
            html.Td(r['competition']),
            html.Td(home),
            html.Td(score, style={'fontWeight': 'bold', 'textAlign': 'center'}),
            html.Td(away),
            html.Td(result_badge),
        ], style={'backgroundColor': result_color.get(r['result'], 'transparent')}))

    table = section_card("Match History", html.Table([
        html.Thead(html.Tr([
            html.Th("Date"), html.Th("Competition"),
            html.Th("Home"), html.Th("Score", style={'textAlign': 'center'}),
            html.Th("Away"), html.Th("Result"),
        ])),
        html.Tbody(rows),
    ], className="table table-dark table-sm"))

    return html.Div([kpi, table])


def _build_tactical(team_name, competition):
    team_ev = get_team_events(team_name, CURRENT_SEASON, competition if competition != 'all' else None)
    if team_ev.empty:
        return html.P("No event data available.", style={'color': COLORS['text_secondary']})

    # Most common formation
    formation_col = 'formation'
    formation_text = "N/A"
    if formation_col in team_ev.columns:
        formations = team_ev[formation_col].dropna()
        formations = formations[formations != '']
        if not formations.empty:
            formation_text = formations.mode().iloc[0]

    formation_badge = dbc.Row([
        dbc.Col([
            dbc.Card([
                dbc.CardBody([
                    html.P("Most Used Formation", className="mb-1",
                           style={'color': COLORS['text_secondary'], 'fontSize': '0.85rem'}),
                    html.H2(formation_text, style={'color': GOLD, 'marginBottom': 0}),
                ])
            ])
        ], md=3)
    ], className="mb-3")

    # KPI stats
    passes = team_ev[team_ev['event_type'] == 'Pass']
    pass_acc = round(
        len(passes[passes['outcome'] == 1]) / len(passes) * 100, 1
    ) if len(passes) > 0 else 0.0

    # Possession: pass share relative to all events in those matches
    all_match_ids = team_ev['match_id'].unique()

    all_match_events = get_all_events(CURRENT_SEASON)
    if not all_match_events.empty:
        all_match_events = all_match_events[all_match_events['match_id'].isin(all_match_ids)]
        all_passes = len(all_match_events[all_match_events['event_type'] == 'Pass'])
        possession = round(len(passes) / all_passes * 100, 1) if all_passes > 0 else 50.0
    else:
        possession = 50.0

    shots = team_ev[team_ev['event_type'].isin(['Miss', 'Saved Shot', 'Goal'])]

    # Pressing proxy: tackles + interceptions in Barcelona's half
    # In Opta coords, x=0 is the team's own goal, x=100 is opponent's goal.
    # When the opposition is in Barça's half, their x < 50.
    defensive_actions = team_ev[
        team_ev['event_type'].isin(['Tackle', 'Interception']) &
        (team_ev['x'] < 50)
    ]

    stat_kpi = kpi_row(
        {
            'passes':       len(passes),
            'pass_acc':     pass_acc,
            'shots':        len(shots),
            'possession':   possession,
            'high_press':   len(defensive_actions),
        },
        [
            ('passes',     'Passes'),
            ('pass_acc',   'Pass Accuracy %'),
            ('shots',      'Shots vs Barça'),
            ('possession', 'Possession %'),
            ('high_press', 'High Press Actions'),
        ],
    )

    # Touch heatmap
    touch_data = team_ev.dropna(subset=['x', 'y'])
    if not touch_data.empty:
        img_src = render_heatmap_img(
            touch_data['x'].tolist(), touch_data['y'].tolist(),
            cmap='RdYlBu_r', fallback_color=AWAY_COLOR,
        )
        heatmap = section_card(
            "Touch Heatmap (vs Barça)",
            html.Img(src=img_src, style={'width': '100%', 'borderRadius': '4px'}),
        )
    else:
        heatmap = section_card("Touch Heatmap", empty_fig("No touch data"))

    return html.Div([formation_badge, stat_kpi, heatmap])


def _build_key_players(team_name, competition):
    team_ev = get_team_events(team_name, CURRENT_SEASON, competition if competition != 'all' else None)
    if team_ev.empty:
        return html.P("No player data available.", style={'color': COLORS['text_secondary']})

    # Goals (excluding own goals)
    goal_events = team_ev[team_ev['event_type'] == 'Goal']
    goal_events = filter_own_goals(goal_events)
    goals_by_player = goal_events.groupby('player_name').size().sort_values(ascending=False).head(5)

    # Passes
    passes_by_player = (
        team_ev[team_ev['event_type'] == 'Pass']
        .groupby('player_name').size()
        .sort_values(ascending=False)
        .head(5)
    )

    # Defensive actions (tackles + interceptions)
    def_actions = team_ev[team_ev['event_type'].isin(['Tackle', 'Interception'])]
    def_by_player = def_actions.groupby('player_name').size().sort_values(ascending=False).head(5)

    def _hbar(series, color, title):
        if series.empty:
            return section_card(title, empty_fig("No data"))
        fig = go.Figure(go.Bar(
            x=series.values,
            y=series.index,
            orientation='h',
            marker_color=color,
            hovertemplate='%{y}: %{x}<extra></extra>',
        ))
        fig.update_layout(**CHART_LAYOUT_DEFAULTS, height=280,
                          yaxis=dict(autorange='reversed'))
        return section_card(title, dcc.Graph(figure=fig, config=CHART_CONFIG))

    return html.Div([
        dbc.Row([
            dbc.Col(_hbar(goals_by_player,   GOLD,      "Top Scorers"), md=4),
            dbc.Col(_hbar(passes_by_player,  HOME_COLOR,"Most Passes"), md=4),
            dbc.Col(_hbar(def_by_player,     AWAY_COLOR,"Defensive Leaders"), md=4),
        ])
    ])


# ---------------------------------------------------------------------------
# Layout
# ---------------------------------------------------------------------------

def create_opposition_analysis_layout():
    """Create the Opposition Analysis page layout."""
    return dbc.Container([
        page_header("Opposition Analysis"),
        html.Hr(),

        # Controls
        dbc.Row([
            dbc.Col([
                html.Label("Competition", style={'color': COLORS['text_secondary'], 'fontSize': '0.85rem'}),
                dcc.Dropdown(
                    id='oa-competition-selector',
                    options=_ALL_COMPETITIONS,
                    value='all',
                    clearable=False,
                    style={'backgroundColor': COLORS['dark_secondary']},
                )
            ], md=3),
            dbc.Col([
                html.Label("Team", style={'color': COLORS['text_secondary'], 'fontSize': '0.85rem'}),
                dcc.Dropdown(
                    id='oa-team-selector',
                    options=[],
                    value=None,
                    clearable=False,
                    style={'backgroundColor': COLORS['dark_secondary']},
                )
            ], md=4),
        ], className="mb-4"),

        dbc.Tabs(id='oa-tabs', active_tab='oa-tab-h2h', children=[
            dbc.Tab(label='Head to Head',      tab_id='oa-tab-h2h'),
            dbc.Tab(label='Tactical Profile',  tab_id='oa-tab-tactical'),
            dbc.Tab(label='Key Players',       tab_id='oa-tab-keyplayers'),
        ], className="mb-3"),

        dcc.Loading(
            id='oa-loading',
            type='circle',
            color=COLORS['gold'],
            children=html.Div(id='oa-content'),
        ),
    ], fluid=True, className="py-4")


# ---------------------------------------------------------------------------
# Callbacks
# ---------------------------------------------------------------------------

def register_opposition_analysis_callbacks(app):
    """Register all Opposition Analysis callbacks."""

    @app.callback(
        Output('oa-team-selector', 'options'),
        Output('oa-team-selector', 'value'),
        Input('oa-competition-selector', 'value'),
    )
    def update_oa_team_options(competition):
        teams = get_all_teams(
            season=CURRENT_SEASON,
            competition=competition if competition != 'all' else None,
        )
        options = [{'label': t, 'value': t} for t in teams]
        value = options[0]['value'] if options else None
        return options, value

    @app.callback(
        Output('oa-content', 'children'),
        Input('oa-team-selector', 'value'),
        Input('oa-competition-selector', 'value'),
        Input('oa-tabs', 'active_tab'),
    )
    def update_oa_content(team_name, competition, active_tab):
        if not team_name:
            return html.P("Select a team to view analysis.",
                          style={'color': COLORS['text_secondary']})

        results = _filter_results_for_opponent(team_name, competition)
        rec = _h2h_record(results)

        # Header card with H2H summary
        header = dbc.Card([
            dbc.CardBody(dbc.Row([
                dbc.Col([
                    html.H3(team_name, style={'color': COLORS['gold'], 'marginBottom': '4px'}),
                    html.P(
                        f"vs Barcelona  |  {rec['barca_wins']}W – {rec['draws']}D – {rec['opp_wins']}L  "
                        f"|  Barça {rec['barca_gf']} – {rec['barca_ga']} opp",
                        style={'color': COLORS['text_secondary'], 'marginBottom': 0},
                    ),
                ])
            ]))
        ], className="mb-3")

        if active_tab == 'oa-tab-h2h':
            tab_content = _build_h2h(team_name, competition)
        elif active_tab == 'oa-tab-tactical':
            tab_content = _build_tactical(team_name, competition)
        elif active_tab == 'oa-tab-keyplayers':
            tab_content = _build_key_players(team_name, competition)
        else:
            tab_content = html.Div()

        return html.Div([header, tab_content])
