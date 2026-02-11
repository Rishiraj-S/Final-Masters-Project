"""
Tab 5 -- Contested Phases

Moments when neither team has clear possession: aerial/ground duels,
loose balls, and scrambles.
"""

import pandas as pd
from dash import html, dcc
import dash_bootstrap_components as dbc
import plotly.graph_objects as go

from utils.config import COLORS
from utils.match_data_adapter import (
    get_match_metadata,
    get_contested_summary,
    get_contested_phase_events,
)

from .shared import (
    CHART_LAYOUT_DEFAULTS, CHART_CONFIG,
    HOME_COLOR, AWAY_COLOR, GOLD,
    empty_fig, section_card, kpi_row,
    add_pitch_shapes_full,
)


def _build_contested_map(contested_df, title):
    """Build a pitch scatter map for contested events."""
    if contested_df is None or contested_df.empty:
        return empty_fig(f"No data for {title.lower()}")
    if 'x' not in contested_df.columns or 'y' not in contested_df.columns:
        return empty_fig(f"No coordinates for {title.lower()}")

    fig = go.Figure()
    add_pitch_shapes_full(fig)

    for team_code, color, name in [('BAR', HOME_COLOR, 'Barcelona')]:
        team = (contested_df[contested_df['team_code'] == team_code]
                if 'team_code' in contested_df.columns else contested_df)
        won = team[team['outcome'] == 1] if 'outcome' in team.columns else team.iloc[0:0]
        lost = team[team['outcome'] == 0] if 'outcome' in team.columns else team.iloc[0:0]

        if not won.empty:
            fig.add_trace(go.Scatter(
                x=won['x'], y=won['y'], mode='markers', name=f'{name} Won',
                marker=dict(color='#28a745', size=8, symbol='circle',
                            line=dict(width=1, color='white')),
            ))
        if not lost.empty:
            fig.add_trace(go.Scatter(
                x=lost['x'], y=lost['y'], mode='markers', name=f'{name} Lost',
                marker=dict(color='#dc3545', size=8, symbol='x',
                            line=dict(width=1, color='white')),
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


def _build_contested_heatmap(events_df, title):
    """Build a heatmap of all contested phase events."""
    if events_df.empty or 'x' not in events_df.columns or 'y' not in events_df.columns:
        return empty_fig("No spatial data for contested phases")

    fig = go.Figure(data=go.Histogram2d(
        x=events_df['x'].dropna(),
        y=events_df['y'].dropna(),
        nbinsx=20, nbinsy=15,
        colorscale=[[0, 'rgba(0,0,0,0)'], [0.3, 'rgba(165,0,68,0.4)'],
                     [0.7, 'rgba(237,187,0,0.6)'], [1, 'rgba(237,187,0,0.9)']],
        showscale=False,
    ))

    add_pitch_shapes_full(fig)

    fig.update_layout(
        **CHART_LAYOUT_DEFAULTS, height=400,
        title=dict(text=title, font=dict(size=13, color=GOLD)),
        xaxis=dict(range=[-1, 101], showgrid=False, zeroline=False,
                   showticklabels=False, fixedrange=True),
        yaxis=dict(range=[-1, 101], showgrid=False, zeroline=False,
                   showticklabels=False, scaleanchor='x', fixedrange=True),
    )
    return fig


def build_contested_tab(events):
    """Render the Contested Phases tab."""
    summary = get_contested_summary(events)
    contested = get_contested_phase_events(events)

    meta = get_match_metadata(events)
    opp_name = (meta.get('away_team', 'Opponent')
                if meta.get('barca_is_home')
                else meta.get('home_team', 'Opponent'))

    barca_duels = summary.get('duels', {}).get('barcelona', {})
    opp_duels = summary.get('duels', {}).get('opponent', {})

    duel_fig = go.Figure()
    duel_cats = ['Total', 'Won', 'Lost']
    duel_fig.add_trace(go.Bar(
        x=duel_cats,
        y=[barca_duels.get('total', 0), barca_duels.get('won', 0),
           barca_duels.get('lost', 0)],
        name='Barcelona', marker_color=HOME_COLOR,
    ))
    duel_fig.add_trace(go.Bar(
        x=duel_cats,
        y=[opp_duels.get('total', 0), opp_duels.get('won', 0),
           opp_duels.get('lost', 0)],
        name=opp_name, marker_color=AWAY_COLOR,
    ))
    duel_fig.update_layout(**CHART_LAYOUT_DEFAULTS, barmode='group', height=300,
                            yaxis_title='Count')

    duel_map = _build_contested_map(contested.get('duels', None), 'Duel Locations')

    lb_summary = summary.get('loose_balls', {})
    lb_barca = lb_summary.get('barcelona', {})
    lb_opp = lb_summary.get('opponent', {})
    scr_summary = summary.get('scrambles', {})

    # Combined heatmap
    all_contested = []
    for key in ['duels', 'scrambles', 'loose_balls']:
        df = contested.get(key)
        if df is not None and not df.empty:
            all_contested.append(df)

    if all_contested:
        all_df = pd.concat(all_contested, ignore_index=True)
        contested_heatmap = _build_contested_heatmap(all_df, 'Contested Phase Heatmap')
    else:
        contested_heatmap = empty_fig("No contested phase data")

    return html.Div([
        html.H4("Contested Phases Analysis", style={'color': GOLD}, className="mb-3"),
        html.P("Analysis of moments when possession is disputed: duels, loose balls, "
               "and scrambles.", style={'color': COLORS['text_secondary']}),

        dbc.Row([
            dbc.Col(section_card("Duels", [
                dcc.Graph(figure=duel_fig, config=CHART_CONFIG),
            ]), width=6),
            dbc.Col(section_card("Duel Locations", [
                dcc.Graph(figure=duel_map, config=CHART_CONFIG),
            ]), width=6),
        ], className="mb-3"),

        dbc.Row([
            dbc.Col(section_card("Loose Balls", [
                dbc.Row([
                    dbc.Col([
                        html.H6("Barcelona", style={'color': HOME_COLOR}),
                        kpi_row(lb_barca, [
                            ('total', 'Total'), ('won', 'Won'), ('lost', 'Lost'),
                        ]),
                    ], width=6),
                    dbc.Col([
                        html.H6(opp_name, style={'color': AWAY_COLOR}),
                        kpi_row(lb_opp, [
                            ('total', 'Total'), ('won', 'Won'), ('lost', 'Lost'),
                        ]),
                    ], width=6),
                ]),
            ]), width=6),
            dbc.Col(section_card("Scrambles", [
                kpi_row(scr_summary, [('total', 'Total Scramble Events')]),
                html.P(
                    "Scramble events are tagged via Opta qualifier. If no explicit "
                    "tags exist in the data, this section will show zero.",
                    style={'color': COLORS['text_secondary'], 'fontSize': '0.85rem'},
                ),
            ]), width=6),
        ], className="mb-3"),

        dbc.Row([
            dbc.Col(section_card("Contested Phase Heatmap", [
                dcc.Graph(figure=contested_heatmap, config=CHART_CONFIG),
            ]), width=12),
        ]),
    ])
