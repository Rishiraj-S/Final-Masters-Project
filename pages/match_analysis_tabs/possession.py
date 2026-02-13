"""
Tab 2 -- Organised Possession

Decomposes Barcelona's possession into four sub-phases:
Build Up, Progression, Fast Break, Finishing.
"""

from dash import html, dcc
import dash_bootstrap_components as dbc
import plotly.graph_objects as go

from utils.config import COLORS
from utils.match_data_adapter import (
    tag_possession_phases,
    get_build_up_stats,
    get_progression_stats,
    get_fast_break_stats,
    get_finishing_stats,
)

from .shared import (
    CHART_LAYOUT_DEFAULTS, CHART_CONFIG,
    HOME_COLOR, AWAY_COLOR, GOLD,
    empty_fig, section_card, kpi_row,
    add_pitch_background, PITCH_AXIS_FULL, PITCH_AXIS_HALF,
)


def _build_phase_action_map(tagged_events, phase, title):
    """Build a heatmap of actions for a specific possession phase."""
    phase_df = (tagged_events[tagged_events['possession_phase'] == phase]
                if 'possession_phase' in tagged_events.columns
                else tagged_events.iloc[0:0])

    if phase_df.empty or 'x' not in phase_df.columns or 'y' not in phase_df.columns:
        return empty_fig(f"No spatial data for {title}")

    fig = go.Figure(data=go.Histogram2d(
        x=phase_df['x'].dropna(),
        y=phase_df['y'].dropna(),
        nbinsx=20, nbinsy=15,
        colorscale=[[0, 'rgba(0,0,0,0)'], [0.5, 'rgba(0,77,152,0.5)'],
                     [1, 'rgba(237,187,0,0.9)']],
        showscale=False,
    ))

    add_pitch_background(fig)

    fig.update_layout(
        **CHART_LAYOUT_DEFAULTS, height=300,
        title=dict(text=title, font=dict(size=13, color=GOLD)),
        **PITCH_AXIS_FULL,
    )
    return fig


def _build_finishing_map(tagged_events):
    """Build a shot map for the finishing phase."""
    fin = (tagged_events[tagged_events['possession_phase'] == 'finishing']
           if 'possession_phase' in tagged_events.columns
           else tagged_events.iloc[0:0])

    if fin.empty or 'x' not in fin.columns or 'y' not in fin.columns:
        return empty_fig("No shot location data")

    fig = go.Figure()
    add_pitch_background(fig, half=True)

    for evt_type, symbol, color, size in [
        ('Goal', 'star', '#28a745', 18),
        ('Saved Shot', 'circle', GOLD, 12),
        ('Miss', 'x', COLORS['garnet'], 10),
    ]:
        subset = fin[fin['event_type'] == evt_type]
        if subset.empty:
            continue
        fig.add_trace(go.Scatter(
            x=subset['x'], y=subset['y'],
            mode='markers', name=evt_type,
            marker=dict(color=color, size=size, symbol=symbol,
                        line=dict(width=1, color='white')),
            text=[f"{r.get('player_name', '')} {r.get('time_min', '')}'"
                  for _, r in subset.iterrows()],
            hovertemplate='%{text}<extra></extra>',
        ))

    fig.update_layout(
        **CHART_LAYOUT_DEFAULTS, height=300,
        **PITCH_AXIS_HALF,
    )
    return fig


def build_possession_tab(events):
    """Render the Organised Possession tab."""
    tagged = tag_possession_phases(events)
    bu_stats = get_build_up_stats(tagged)
    prog_stats = get_progression_stats(tagged)
    fb_stats = get_fast_break_stats(tagged)
    fin_stats = get_finishing_stats(tagged)

    # Phase distribution pie chart
    phase_counts = (tagged['possession_phase'].value_counts()
                    if 'possession_phase' in tagged.columns else {})
    phase_labels = {
        'build_up': 'Build Up', 'progression': 'Progression',
        'fast_break': 'Fast Break', 'finishing': 'Finishing',
        'unclassified': 'Other',
    }
    phase_colors = {
        'build_up': '#004D98', 'progression': '#1a75d1',
        'fast_break': '#EDBB00', 'finishing': '#A50044',
        'unclassified': '#2A2F4A',
    }

    if not phase_counts.empty:
        dist_fig = go.Figure(data=[go.Pie(
            labels=[phase_labels.get(k, k) for k in phase_counts.index],
            values=phase_counts.values,
            marker_colors=[phase_colors.get(k, '#555') for k in phase_counts.index],
            hole=0.4, textinfo='label+percent',
            textfont=dict(color='white'),
        )])
        dist_fig.update_layout(**CHART_LAYOUT_DEFAULTS, height=300, showlegend=False)
    else:
        dist_fig = empty_fig("No phase data")

    bu_map = _build_phase_action_map(tagged, 'build_up', 'Build Up Actions')
    prog_map = _build_phase_action_map(tagged, 'progression', 'Progression Actions')
    fin_map = _build_finishing_map(tagged)

    return html.Div([
        html.H4("Organised Possession Analysis", style={'color': GOLD},
                 className="mb-3"),
        html.P("Barcelona's possession decomposed into four analytical sub-phases.",
               style={'color': COLORS['text_secondary']}),

        dbc.Row([
            dbc.Col(section_card("Phase Distribution", [
                dcc.Graph(figure=dist_fig, config=CHART_CONFIG),
            ]), width=4),
            dbc.Col(section_card("Build Up", [
                kpi_row(bu_stats, [
                    ('total_passes', 'Passes'), ('pass_accuracy', 'Accuracy %'),
                    ('progressive_passes', 'Progressive'), ('total_actions', 'Actions'),
                ]),
                dcc.Graph(figure=bu_map, config=CHART_CONFIG),
            ]), width=8),
        ], className="mb-3"),

        dbc.Row([
            dbc.Col(section_card("Progression", [
                kpi_row(prog_stats, [
                    ('through_balls', 'Through Balls'), ('long_balls', 'Long Balls'),
                    ('crosses', 'Crosses'), ('switches_of_play', 'Switches'),
                    ('take_ons_successful', 'Take Ons Won'),
                ]),
                dcc.Graph(figure=prog_map, config=CHART_CONFIG),
            ]), width=6),
            dbc.Col(html.Div([
                section_card("Fast Break", [
                    kpi_row(fb_stats, [
                        ('total_actions', 'Actions'), ('shots', 'Shots'),
                        ('goals', 'Goals'),
                    ], colors={'goals': '#28a745'}),
                ]),
                section_card("Finishing", [
                    kpi_row(fin_stats, [
                        ('total_shots', 'Shots'), ('on_target', 'On Target'),
                        ('goals', 'Goals'), ('headed', 'Headers'),
                        ('right_foot', 'Right Foot'), ('left_foot', 'Left Foot'),
                    ], colors={'goals': '#28a745'}),
                    dcc.Graph(figure=fin_map, config=CHART_CONFIG),
                ]),
            ]), width=6),
        ]),
    ])
