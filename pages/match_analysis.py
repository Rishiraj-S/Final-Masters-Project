"""
CuléVision - Match Analysis Page
Displays detailed match analysis with statistics, possession charts, and timeline
"""

from dash import html, dcc
from dash.dependencies import Input, Output
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
from utils.config import COLORS
from utils.data_utils import get_match_results, get_match_stats, get_match_events_timeline


def create_match_analysis_layout():
    """Create the Match Analysis page layout."""
    results = get_match_results()

    # Match selector dropdown
    match_options = [
        {'label': f"{r['date']} - {r['description']} ({r['competition']})", 'value': r['match_id']}
        for r in results
    ]

    return dbc.Container([
        html.H2("Match Analysis", style={'color': COLORS['gold']}, className="mb-4"),
        html.Hr(),

        dbc.Row([
            dbc.Col([
                html.Label("Select Match:", style={'color': COLORS['text_secondary']}),
                dcc.Dropdown(
                    id='match-selector',
                    options=match_options,
                    value=match_options[0]['value'] if match_options else None,
                    style={'backgroundColor': '#151932', 'color': '#000'}
                )
            ], width=6)
        ], className="mb-4"),

        html.Div(id='match-analysis-content')
    ], fluid=True, className="py-4")


def register_match_analysis_callbacks(app):
    """Register callbacks for match analysis page."""

    @app.callback(
        Output('match-analysis-content', 'children'),
        Input('match-selector', 'value')
    )
    def update_match_analysis(match_id):
        if not match_id:
            return html.P("Select a match to view analysis.", style={'color': COLORS['text_secondary']})

        stats = get_match_stats(match_id)
        timeline = get_match_events_timeline(match_id)

        if not stats:
            return html.P("No data available for this match.", style={'color': COLORS['text_secondary']})

        home_team = stats['home_team']
        away_team = stats['away_team']
        home_stats = stats['home']
        away_stats = stats['away']

        # Match header
        match_header = dbc.Card([
            dbc.CardBody([
                dbc.Row([
                    dbc.Col(html.H4(home_team, className="text-end"), width=4),
                    dbc.Col(html.H2(f"{home_stats['goals']} - {away_stats['goals']}",
                                   className="text-center", style={'color': COLORS['gold']}), width=4),
                    dbc.Col(html.H4(away_team, className="text-start"), width=4)
                ])
            ])
        ], className="mb-4")

        # Stats comparison
        stat_labels = [
            ('Possession', 'possession', '%'),
            ('Shots', 'shots', ''),
            ('Shots on Target', 'shots_on_target', ''),
            ('Passes', 'passes', ''),
            ('Pass Accuracy', 'pass_accuracy', '%'),
            ('Fouls', 'fouls', ''),
            ('Corners', 'corners', ''),
            ('Yellow Cards', 'yellow_cards', ''),
            ('Red Cards', 'red_cards', '')
        ]

        stats_rows = []
        for label, key, suffix in stat_labels:
            home_val = home_stats.get(key, 0)
            away_val = away_stats.get(key, 0)
            stats_rows.append(
                html.Tr([
                    html.Td(f"{home_val}{suffix}", style={'textAlign': 'right', 'fontWeight': 'bold'}),
                    html.Td(label, style={'textAlign': 'center', 'color': COLORS['text_secondary']}),
                    html.Td(f"{away_val}{suffix}", style={'textAlign': 'left', 'fontWeight': 'bold'})
                ])
            )

        stats_card = dbc.Card([
            dbc.CardHeader(html.H5("Match Statistics", className="mb-0", style={'color': COLORS['gold']})),
            dbc.CardBody([
                html.Table([html.Tbody(stats_rows)], className="table table-dark", style={'width': '100%'})
            ])
        ])

        # Create possession chart
        possession_fig = go.Figure(data=[
            go.Bar(
                y=['Possession'],
                x=[home_stats.get('possession', 50)],
                orientation='h',
                name=home_team,
                marker_color=COLORS['primary_blue'],
                text=[f"{home_stats.get('possession', 50)}%"],
                textposition='inside'
            ),
            go.Bar(
                y=['Possession'],
                x=[away_stats.get('possession', 50)],
                orientation='h',
                name=away_team,
                marker_color=COLORS['garnet'],
                text=[f"{away_stats.get('possession', 50)}%"],
                textposition='inside'
            )
        ])
        possession_fig.update_layout(
            barmode='stack',
            showlegend=True,
            legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='center', x=0.5),
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            font=dict(color='#E8E9ED'),
            height=120,
            margin=dict(l=20, r=20, t=40, b=20)
        )

        # Shots comparison chart
        shots_fig = go.Figure()
        categories = ['Shots', 'Shots on Target', 'Goals']
        home_values = [home_stats.get('shots', 0), home_stats.get('shots_on_target', 0), home_stats.get('goals', 0)]
        away_values = [away_stats.get('shots', 0), away_stats.get('shots_on_target', 0), away_stats.get('goals', 0)]

        shots_fig.add_trace(go.Bar(x=categories, y=home_values, name=home_team, marker_color=COLORS['primary_blue']))
        shots_fig.add_trace(go.Bar(x=categories, y=away_values, name=away_team, marker_color=COLORS['garnet']))

        shots_fig.update_layout(
            barmode='group',
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            font=dict(color='#E8E9ED'),
            height=300,
            margin=dict(l=20, r=20, t=40, b=40),
            legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='center', x=0.5)
        )

        # Timeline
        timeline_items = []
        for event in timeline:
            if event['type'] == 'Goal':
                icon = "⚽"
                color = '#28a745'
            elif event['type'] == 'Card':
                icon = "🟨"
                color = '#ffc107'
            else:
                icon = "🔄"
                color = '#A5A8B8'

            side = 'start' if event['team_position'] == 'home' else 'end'
            timeline_items.append(
                html.Div([
                    html.Span(f"{event['minute']}'", style={'fontWeight': 'bold', 'marginRight': '10px'}),
                    html.Span(icon, style={'marginRight': '5px'}),
                    html.Span(f"{event['player']} ({event['team']})", style={'color': color})
                ], style={'padding': '5px 0', 'textAlign': side})
            )

        timeline_card = dbc.Card([
            dbc.CardHeader(html.H5("Match Timeline", className="mb-0", style={'color': COLORS['gold']})),
            dbc.CardBody(timeline_items if timeline_items else [html.P("No key events recorded.")])
        ])

        return html.Div([
            match_header,
            dbc.Row([
                dbc.Col(stats_card, width=6),
                dbc.Col([
                    dbc.Card([
                        dbc.CardHeader(html.H5("Possession", className="mb-0", style={'color': COLORS['gold']})),
                        dbc.CardBody(dcc.Graph(figure=possession_fig, config={'displayModeBar': False}))
                    ], className="mb-3"),
                    dbc.Card([
                        dbc.CardHeader(html.H5("Shots Analysis", className="mb-0", style={'color': COLORS['gold']})),
                        dbc.CardBody(dcc.Graph(figure=shots_fig, config={'displayModeBar': False}))
                    ])
                ], width=6)
            ], className="mb-4"),
            dbc.Row([
                dbc.Col(timeline_card, width=12)
            ])
        ])
