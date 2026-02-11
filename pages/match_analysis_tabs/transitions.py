"""
Tab 3 -- Transitions

Analyses moments immediately after possession changes:
counterattacks (15s window) and counter-pressing (5s window).
"""

import pandas as pd
from dash import html, dcc
import dash_bootstrap_components as dbc
import plotly.graph_objects as go

from utils.config import COLORS
from utils.match_data_adapter import (
    get_transition_summary,
    get_counterattack_sequences,
    get_counterpress_sequences,
)

from .shared import (
    CHART_LAYOUT_DEFAULTS, CHART_CONFIG,
    HOME_COLOR, AWAY_COLOR, GOLD,
    empty_fig, section_card, kpi_row,
    add_pitch_shapes_full,
)


def _build_transition_map(sequences, title):
    """Build a pitch map showing transition starting points."""
    if not sequences:
        return empty_fig(f"No {title.lower()} data")

    origins = []
    for seq in sequences:
        if not seq.empty and 'x' in seq.columns and 'y' in seq.columns:
            first = seq.iloc[0]
            origins.append({
                'x': first['x'], 'y': first['y'],
                'minute': first.get('time_min', 0),
                'player': first.get('player_name', ''),
            })

    if not origins:
        return empty_fig(f"No coordinate data for {title.lower()}")

    origins_df = pd.DataFrame(origins)

    fig = go.Figure()
    add_pitch_shapes_full(fig)

    fig.add_trace(go.Scatter(
        x=origins_df['x'], y=origins_df['y'],
        mode='markers',
        marker=dict(color=GOLD, size=12, symbol='circle',
                    line=dict(width=1, color='white')),
        text=[f"{r['player']} {int(r['minute'])}'" for _, r in origins_df.iterrows()],
        hovertemplate='%{text}<extra></extra>',
        showlegend=False,
    ))

    fig.update_layout(
        **CHART_LAYOUT_DEFAULTS, height=350,
        title=dict(text=title, font=dict(size=13, color=GOLD)),
        xaxis=dict(range=[-1, 101], showgrid=False, zeroline=False,
                   showticklabels=False, fixedrange=True),
        yaxis=dict(range=[-1, 101], showgrid=False, zeroline=False,
                   showticklabels=False, scaleanchor='x', fixedrange=True),
    )
    return fig


def build_transitions_tab(events):
    """Render the Transitions tab."""
    summary = get_transition_summary(events)
    ca_sequences = get_counterattack_sequences(events)
    cp_sequences = get_counterpress_sequences(events)

    ca_kpis = kpi_row(summary, [
        ('counterattacks', 'Counter Attacks'),
        ('counterattack_shots', 'CA Shots'),
        ('counterattack_goals', 'CA Goals'),
    ], colors={'counterattack_goals': '#28a745'})

    cp_kpis = kpi_row(summary, [
        ('counterpresses', 'Counter Presses'),
        ('counterpress_recoveries', 'Recoveries'),
    ])

    ca_map = _build_transition_map(ca_sequences, 'Counterattack Origins')
    cp_map = _build_transition_map(cp_sequences, 'Counter-Press Locations')

    # Counterattack detail table
    ca_table_rows = []
    for seq in ca_sequences[:10]:
        start_event = seq.iloc[0]
        shot_events = seq[seq['event_type'].isin(['Miss', 'Saved Shot', 'Goal'])]
        outcome = shot_events.iloc[-1]['event_type'] if not shot_events.empty else 'No shot'
        duration = ((seq.iloc[-1]['time_min'] * 60 + seq.iloc[-1]['time_sec']) -
                    (seq.iloc[0]['time_min'] * 60 + seq.iloc[0]['time_sec']))
        ca_table_rows.append(html.Tr([
            html.Td(f"{int(start_event.get('time_min', 0))}'"),
            html.Td(str(start_event.get('player_name', ''))),
            html.Td(str(start_event.get('event_type', ''))),
            html.Td(f"{len(seq)} events"),
            html.Td(f"{duration}s"),
            html.Td(outcome, style={
                'color': '#28a745' if outcome == 'Goal' else COLORS['text_primary'],
            }),
        ]))

    ca_table = html.Table([
        html.Thead(html.Tr([
            html.Th("Min"), html.Th("Player"), html.Th("Trigger"),
            html.Th("Events"), html.Th("Duration"), html.Th("Outcome"),
        ])),
        html.Tbody(ca_table_rows if ca_table_rows else [
            html.Tr([html.Td("No counterattacks detected", colSpan=6,
                              style={'color': COLORS['text_secondary']})])
        ])
    ], className="table table-dark table-striped")

    return html.Div([
        html.H4("Transition Analysis", style={'color': GOLD}, className="mb-3"),
        html.P("Analysis of moments immediately after possession changes.",
               style={'color': COLORS['text_secondary']}),

        dbc.Row([
            dbc.Col(section_card("Counterattacks (15s window)", [
                ca_kpis,
                dcc.Graph(figure=ca_map, config=CHART_CONFIG),
            ]), width=6),
            dbc.Col(section_card("Counter-Pressing (5s window)", [
                cp_kpis,
                dcc.Graph(figure=cp_map, config=CHART_CONFIG),
            ]), width=6),
        ], className="mb-3"),

        dbc.Row([
            dbc.Col(section_card("Counterattack Details", [ca_table]), width=12),
        ]),
    ])
