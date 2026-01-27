"""
CuléVision - Home Page (Season Overview)
Displays season statistics, recent matches, top scorers, and squad statistics
"""

from dash import html, dash_table
import dash_bootstrap_components as dbc
from utils.config import COLORS
from utils.data_utils import (
    get_match_results, get_player_stats, get_season_summary, get_top_scorers
)


def create_result_badge(result):
    """Create a colored badge for match result."""
    css_class = f"result-badge result-{result.lower()}"
    return html.Span(result, className=css_class)


def create_stat_card(value, label, color=None):
    """Create a stat display card."""
    if color is None:
        color = COLORS['gold']
    return dbc.Card([
        dbc.CardBody([
            html.Div(str(value), className="stat-value", style={'color': color}),
            html.Div(label, className="stat-label")
        ], className="stat-card")
    ], className="h-100")


def create_home_layout(is_admin=False):
    """Create the Home page layout with season overview."""
    # Get data
    summary = get_season_summary()
    results = get_match_results()
    top_scorers = get_top_scorers(10)
    recent_matches = results[:5] if results else []

    # Admin button (only visible for admin users)
    admin_button = html.Div()
    if is_admin:
        admin_button = html.Div([
            dbc.Button(
                [html.I(className="fas fa-database me-2"), "Update Databases"],
                id='update-db-button',
                color="warning",
                className="mb-3",
                style={'fontWeight': 'bold'}
            )
        ], style={'position': 'absolute', 'top': '0', 'right': '15px'})

    # Season stats cards
    stats_row = dbc.Row([
        dbc.Col(create_stat_card(summary.get('matches_played', 0), 'Matches'), width=2),
        dbc.Col(create_stat_card(summary.get('wins', 0), 'Wins', '#28a745'), width=2),
        dbc.Col(create_stat_card(summary.get('draws', 0), 'Draws', '#ffc107'), width=2),
        dbc.Col(create_stat_card(summary.get('losses', 0), 'Losses', '#dc3545'), width=2),
        dbc.Col(create_stat_card(summary.get('goals_for', 0), 'Goals For'), width=2),
        dbc.Col(create_stat_card(summary.get('goals_against', 0), 'Goals Against', '#A5A8B8'), width=2),
    ], className="mb-4")

    # Recent matches table
    recent_matches_rows = []
    for match in recent_matches:
        venue = "H" if match['is_home'] else "A"
        score = f"{match['barca_goals']}-{match['opponent_goals']}"
        recent_matches_rows.append(
            html.Tr([
                html.Td(match['date']),
                html.Td(match['competition'], style={'fontSize': '0.85rem'}),
                html.Td(f"vs {match['opponent']} ({venue})"),
                html.Td(score, style={'fontWeight': 'bold'}),
                html.Td(create_result_badge(match['result']))
            ])
        )

    recent_matches_card = dbc.Card([
        dbc.CardHeader(html.H5("Recent Matches", className="mb-0", style={'color': COLORS['gold']})),
        dbc.CardBody([
            html.Table([
                html.Thead(html.Tr([
                    html.Th("Date"), html.Th("Competition"), html.Th("Match"), html.Th("Score"), html.Th("Result")
                ])),
                html.Tbody(recent_matches_rows)
            ], className="table table-dark table-striped")
        ])
    ])

    # Top scorers table
    scorers_rows = []
    if not top_scorers.empty:
        for _, row in top_scorers.iterrows():
            scorers_rows.append(
                html.Tr([
                    html.Td(row['player']),
                    html.Td(str(row['goals']), style={'fontWeight': 'bold', 'color': COLORS['gold']}),
                    html.Td(str(row['appearances'])),
                    html.Td(str(row['shots']))
                ])
            )

    top_scorers_card = dbc.Card([
        dbc.CardHeader(html.H5("Top Scorers", className="mb-0", style={'color': COLORS['gold']})),
        dbc.CardBody([
            html.Table([
                html.Thead(html.Tr([
                    html.Th("Player"), html.Th("Goals"), html.Th("Apps"), html.Th("Shots")
                ])),
                html.Tbody(scorers_rows)
            ], className="table table-dark table-striped")
        ])
    ])

    # Player stats table (full squad)
    player_stats = get_player_stats()
    players_card = dbc.Card([
        dbc.CardHeader(html.H5("Squad Statistics", className="mb-0", style={'color': COLORS['gold']})),
        dbc.CardBody([
            dash_table.DataTable(
                id='player-stats-table',
                columns=[
                    {'name': 'Player', 'id': 'player'},
                    {'name': 'Goals', 'id': 'goals'},
                    {'name': 'Apps', 'id': 'appearances'},
                    {'name': 'Passes', 'id': 'passes'},
                    {'name': 'Shots', 'id': 'shots'},
                    {'name': 'Tackles', 'id': 'tackles'},
                    {'name': 'Interceptions', 'id': 'interceptions'}
                ],
                data=player_stats.to_dict('records') if not player_stats.empty else [],
                style_table={'overflowX': 'auto'},
                style_cell={
                    'backgroundColor': '#151932',
                    'color': '#E8E9ED',
                    'textAlign': 'left',
                    'padding': '10px'
                },
                style_header={
                    'backgroundColor': '#1E2139',
                    'fontWeight': 'bold',
                    'color': COLORS['gold']
                },
                style_data_conditional=[
                    {'if': {'row_index': 'odd'}, 'backgroundColor': '#1E2139'}
                ],
                page_size=15,
                sort_action='native'
            )
        ])
    ])

    return dbc.Container([
        html.Div([
            html.H2("Season Overview 2025-2026", style={'color': COLORS['gold']}, className="mb-4"),
            admin_button
        ], style={'position': 'relative'}),
        stats_row,
        dbc.Row([
            dbc.Col(recent_matches_card, width=6),
            dbc.Col(top_scorers_card, width=6)
        ], className="mb-4"),
        dbc.Row([
            dbc.Col(players_card, width=12)
        ])
    ], fluid=True, className="py-4")
