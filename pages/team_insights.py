"""
CuléVision - Team Insights Page
Displays player statistics, performance charts, and match history
"""

from dash import html, dcc
from dash.dependencies import Input, Output
import dash_bootstrap_components as dbc
import plotly.express as px
import plotly.graph_objects as go
from utils.config import COLORS
from utils.data_utils import get_all_barcelona_players, get_player_stats, get_player_match_stats


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


def create_team_insights_layout():
    """Create the Team Insights page layout."""
    players = get_all_barcelona_players()

    player_options = [{'label': p, 'value': p} for p in players if p]

    return dbc.Container([
        html.H2("Team Insights", style={'color': COLORS['gold']}, className="mb-4"),
        html.Hr(),

        dbc.Row([
            dbc.Col([
                html.Label("Select Player:", style={'color': COLORS['text_secondary']}),
                dcc.Dropdown(
                    id='player-selector',
                    options=player_options,
                    value=player_options[0]['value'] if player_options else None,
                    style={'backgroundColor': '#151932'}
                )
            ], width=4)
        ], className="mb-4"),

        html.Div(id='player-insights-content')
    ], fluid=True, className="py-4")


def register_team_insights_callbacks(app):
    """Register callbacks for team insights page."""

    @app.callback(
        Output('player-insights-content', 'children'),
        Input('player-selector', 'value')
    )
    def update_player_insights(player_name):
        if not player_name:
            return html.P("Select a player to view insights.", style={'color': COLORS['text_secondary']})

        # Get player season stats
        all_stats = get_player_stats()
        player_row = all_stats[all_stats['player'] == player_name]

        if player_row.empty:
            return html.P("No data available for this player.", style={'color': COLORS['text_secondary']})

        player_stats = player_row.iloc[0]

        # Get match-by-match stats
        match_stats = get_player_match_stats(player_name)

        # Player header card
        header_card = dbc.Card([
            dbc.CardBody([
                html.H3(player_name, style={'color': COLORS['gold']}),
                html.P("FC Barcelona", style={'color': COLORS['text_secondary']})
            ])
        ], className="mb-4")

        # Season stats cards
        stats_row = dbc.Row([
            dbc.Col(create_stat_card(player_stats['goals'], 'Goals'), width=2),
            dbc.Col(create_stat_card(player_stats['appearances'], 'Appearances'), width=2),
            dbc.Col(create_stat_card(player_stats['passes'], 'Passes'), width=2),
            dbc.Col(create_stat_card(player_stats['shots'], 'Shots'), width=2),
            dbc.Col(create_stat_card(player_stats['tackles'], 'Tackles'), width=2),
            dbc.Col(create_stat_card(player_stats['interceptions'], 'Interceptions'), width=2),
        ], className="mb-4")

        # Goals over time chart
        if match_stats:
            matches_with_goals = [m for m in match_stats if m['goals'] > 0]
            if matches_with_goals:
                goals_fig = px.bar(
                    x=[m['date'] for m in match_stats],
                    y=[m['goals'] for m in match_stats],
                    labels={'x': 'Date', 'y': 'Goals'},
                    title='Goals by Match'
                )
                goals_fig.update_layout(
                    paper_bgcolor='rgba(0,0,0,0)',
                    plot_bgcolor='rgba(0,0,0,0)',
                    font=dict(color='#E8E9ED'),
                    height=300
                )
                goals_fig.update_traces(marker_color=COLORS['gold'])
            else:
                goals_fig = go.Figure()
                goals_fig.update_layout(
                    paper_bgcolor='rgba(0,0,0,0)',
                    plot_bgcolor='rgba(0,0,0,0)',
                    font=dict(color='#E8E9ED'),
                    height=300,
                    annotations=[dict(text="No goals scored", x=0.5, y=0.5, showarrow=False)]
                )

            # Activity chart (passes per match)
            activity_fig = px.line(
                x=[m['date'] for m in match_stats],
                y=[m['passes'] for m in match_stats],
                labels={'x': 'Date', 'y': 'Passes'},
                title='Passing Activity by Match'
            )
            activity_fig.update_layout(
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                font=dict(color='#E8E9ED'),
                height=300
            )
            activity_fig.update_traces(line_color=COLORS['primary_blue'])

        else:
            goals_fig = go.Figure()
            activity_fig = go.Figure()

        # Match history table
        match_rows = []
        for match in match_stats[:10]:
            match_rows.append(
                html.Tr([
                    html.Td(match['date']),
                    html.Td(match['description'][:30] + '...' if len(match['description']) > 30 else match['description']),
                    html.Td(str(match['goals']), style={'color': COLORS['gold'] if match['goals'] > 0 else COLORS['text_secondary']}),
                    html.Td(str(match['passes'])),
                    html.Td(str(match['shots']))
                ])
            )

        match_history_card = dbc.Card([
            dbc.CardHeader(html.H5("Recent Match Performance", className="mb-0", style={'color': COLORS['gold']})),
            dbc.CardBody([
                html.Table([
                    html.Thead(html.Tr([
                        html.Th("Date"), html.Th("Match"), html.Th("Goals"), html.Th("Passes"), html.Th("Shots")
                    ])),
                    html.Tbody(match_rows)
                ], className="table table-dark table-striped")
            ])
        ])

        return html.Div([
            header_card,
            stats_row,
            dbc.Row([
                dbc.Col([
                    dbc.Card([
                        dbc.CardBody(dcc.Graph(figure=goals_fig, config={'displayModeBar': False}))
                    ])
                ], width=6),
                dbc.Col([
                    dbc.Card([
                        dbc.CardBody(dcc.Graph(figure=activity_fig, config={'displayModeBar': False}))
                    ])
                ], width=6)
            ], className="mb-4"),
            dbc.Row([
                dbc.Col(match_history_card, width=12)
            ])
        ])
