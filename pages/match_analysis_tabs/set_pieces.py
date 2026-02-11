"""
Tab 4 -- Set Pieces

Corners, free kicks, throw-ins, and penalties from attacking and
defending perspectives.
"""

from dash import html, dcc
import dash_bootstrap_components as dbc
import plotly.graph_objects as go

from utils.config import COLORS
from utils.match_data_adapter import (
    get_set_piece_summary,
    get_set_piece_events,
)

from .shared import (
    CHART_LAYOUT_DEFAULTS, CHART_CONFIG,
    HOME_COLOR, AWAY_COLOR, GOLD,
    empty_fig, section_card,
    add_pitch_shapes_full,
)


def _build_set_piece_map(sp_events, title):
    """Build a pitch map for set piece locations."""
    if sp_events is None or sp_events.empty:
        return empty_fig(f"No spatial data for {title.lower()}")
    if 'x' not in sp_events.columns or 'y' not in sp_events.columns:
        return empty_fig(f"No coordinates for {title.lower()}")

    valid = sp_events.dropna(subset=['x', 'y'])
    if valid.empty:
        return empty_fig(f"No valid coordinates for {title.lower()}")

    fig = go.Figure()
    add_pitch_shapes_full(fig)

    fig.add_trace(go.Scatter(
        x=valid['x'], y=valid['y'],
        mode='markers',
        marker=dict(color=GOLD, size=10, symbol='diamond',
                    line=dict(width=1, color='white')),
        text=[f"{r.get('player_name', '')} {int(r.get('time_min', 0))}'"
              for _, r in valid.iterrows()],
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


def build_setpieces_tab(events):
    """Render the Set Pieces tab."""
    sp_summary = get_set_piece_summary(events)
    att = sp_summary.get('attacking', {})
    defe = sp_summary.get('defending', {})
    barca_sp = get_set_piece_events(events, 'BAR')

    sp_types = ['corners', 'free_kicks', 'throw_ins', 'penalties']
    sp_labels = {
        'corners': 'Corners', 'free_kicks': 'Free Kicks',
        'throw_ins': 'Throw-Ins', 'penalties': 'Penalties',
    }

    att_rows = []
    def_rows = []
    for sp_type in sp_types:
        a = att.get(sp_type, {'count': 0, 'shots': 0, 'goals': 0})
        d = defe.get(sp_type, {'count': 0, 'shots': 0, 'goals': 0})
        att_rows.append(html.Tr([
            html.Td(sp_labels[sp_type]),
            html.Td(str(a['count']), style={'fontWeight': 'bold', 'color': GOLD}),
            html.Td(str(a['shots'])),
            html.Td(str(a['goals']), style={
                'color': '#28a745' if a['goals'] > 0 else COLORS['text_primary'],
            }),
        ]))
        def_rows.append(html.Tr([
            html.Td(sp_labels[sp_type]),
            html.Td(str(d['count']), style={'fontWeight': 'bold', 'color': GOLD}),
            html.Td(str(d['shots'])),
            html.Td(str(d['goals']), style={
                'color': '#dc3545' if d['goals'] > 0 else COLORS['text_primary'],
            }),
        ]))

    att_table = html.Table([
        html.Thead(html.Tr([
            html.Th("Type"), html.Th("Count"), html.Th("Shots"), html.Th("Goals"),
        ])),
        html.Tbody(att_rows),
    ], className="table table-dark table-striped")

    def_table = html.Table([
        html.Thead(html.Tr([
            html.Th("Type"), html.Th("Count"), html.Th("Shots Conceded"),
            html.Th("Goals Conceded"),
        ])),
        html.Tbody(def_rows),
    ], className="table table-dark table-striped")

    corner_map = _build_set_piece_map(barca_sp.get('corners', None),
                                       'Corner Delivery Locations')
    fk_map = _build_set_piece_map(barca_sp.get('free_kicks', None),
                                   'Free Kick Locations')

    sp_chart = go.Figure()
    sp_names = [sp_labels[t] for t in sp_types]
    att_counts = [att.get(t, {}).get('count', 0) for t in sp_types]
    def_counts = [defe.get(t, {}).get('count', 0) for t in sp_types]

    sp_chart.add_trace(go.Bar(x=sp_names, y=att_counts,
                               name='Attacking (Barcelona)', marker_color=HOME_COLOR))
    sp_chart.add_trace(go.Bar(x=sp_names, y=def_counts,
                               name='Defending', marker_color=AWAY_COLOR))
    sp_chart.update_layout(**CHART_LAYOUT_DEFAULTS, barmode='group', height=300,
                            yaxis_title='Count')

    return html.Div([
        html.H4("Set Piece Analysis", style={'color': GOLD}, className="mb-3"),
        html.P("Breakdown of dead-ball situations for attacking and defending phases.",
               style={'color': COLORS['text_secondary']}),

        dbc.Row([
            dbc.Col(section_card("Attacking Set Pieces (Barcelona)", [att_table]),
                    width=6),
            dbc.Col(section_card("Defending Set Pieces (Opponent)", [def_table]),
                    width=6),
        ], className="mb-3"),

        dbc.Row([
            dbc.Col(section_card("Set Piece Overview", [
                dcc.Graph(figure=sp_chart, config=CHART_CONFIG),
            ]), width=12),
        ], className="mb-3"),

        dbc.Row([
            dbc.Col(section_card("Corner Locations", [
                dcc.Graph(figure=corner_map, config=CHART_CONFIG),
            ]), width=6),
            dbc.Col(section_card("Free Kick Locations", [
                dcc.Graph(figure=fk_map, config=CHART_CONFIG),
            ]), width=6),
        ]),
    ])
