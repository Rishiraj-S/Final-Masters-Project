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

# ---------------------------------------------------------------------------
# Shot outcome styling constants
# ---------------------------------------------------------------------------
_SHOT_STYLES = [
    ('Goal',       'star',   '#28a745', 18),
    ('Saved Shot', 'circle', GOLD,       12),
    ('Miss',       'x',      COLORS['garnet'], 10),
]

_ZONE_COLS = {
    'Small box-centre':  'Inside 6yd Box',
    'Box-centre':        'Penalty Area',
    'Out of box-centre': 'Outside Box',
    '35+ centre':        '35+ Yards',
}


# ---------------------------------------------------------------------------
# Possession-phase helpers (unchanged)
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Shot analysis helpers
# ---------------------------------------------------------------------------

def _get_fin_shots(tagged_events):
    """Return finishing-phase shot rows only."""
    fin = (tagged_events[tagged_events['possession_phase'] == 'finishing']
           if 'possession_phase' in tagged_events.columns
           else tagged_events.iloc[0:0])
    shot_types = ['Goal', 'Saved Shot', 'Miss']
    return fin[fin['event_type'].isin(shot_types)]


def _build_finishing_map(fin):
    """Shot scatter on a half-pitch: ★ goal · ● saved · ✕ miss."""
    if fin.empty or 'x' not in fin.columns or 'y' not in fin.columns:
        return empty_fig("No shot location data")

    fig = go.Figure()
    add_pitch_background(fig, half=True)

    for evt_type, symbol, color, size in _SHOT_STYLES:
        subset = fin[fin['event_type'] == evt_type]
        if subset.empty:
            continue
        body = subset.apply(
            lambda r: ('Header'     if r.get('Head') == 'Si'
                       else 'Right Foot' if r.get('Right footed') == 'Si'
                       else 'Left Foot'),
            axis=1,
        )
        fig.add_trace(go.Scatter(
            x=subset['x'], y=subset['y'],
            mode='markers', name=evt_type,
            marker=dict(color=color, size=size, symbol=symbol,
                        line=dict(width=1.5, color='white')),
            customdata=list(zip(
                subset.get('player_name', subset.index),
                subset.get('time_min',    ['']*len(subset)),
                body,
            )),
            hovertemplate=(
                "<b>%{customdata[0]}</b> %{customdata[1]}'"
                "<br>%{customdata[2]}"
                "<extra>" + evt_type + "</extra>"
            ),
        ))

    fig.update_layout(**CHART_LAYOUT_DEFAULTS, height=370, **PITCH_AXIS_HALF)
    fig.update_layout(legend=dict(orientation='h', y=-0.06, x=0.5, xanchor='center'))
    return fig


def _build_shot_zone_chart(fin):
    """Overlapping horizontal bars: total shots (blue) vs goals (gold) per zone."""
    zones, shot_counts, goal_counts = [], [], []
    for col, label in _ZONE_COLS.items():
        if col not in fin.columns:
            continue
        mask = fin[col] == 'Si'
        total = int(mask.sum())
        goals = int(fin.loc[mask & (fin['event_type'] == 'Goal')].shape[0])
        if total:
            zones.append(label)
            shot_counts.append(total)
            goal_counts.append(goals)

    if not zones:
        return empty_fig("No zone data")

    fig = go.Figure()
    fig.add_trace(go.Bar(
        y=zones, x=shot_counts, orientation='h',
        name='Shots', marker_color=HOME_COLOR,
        hovertemplate='%{y}: %{x} shots<extra></extra>',
    ))
    fig.add_trace(go.Bar(
        y=zones, x=goal_counts, orientation='h',
        name='Goals', marker_color=GOLD,
        hovertemplate='%{y}: %{x} goals<extra></extra>',
    ))
    fig.update_layout(**CHART_LAYOUT_DEFAULTS, height=220, barmode='overlay', xaxis_title='Count')
    fig.update_layout(legend=dict(orientation='h', y=1.18, x=0.5, xanchor='center'),
                      margin=dict(l=10, r=10, t=10, b=30))
    return fig


def _build_body_part_chart(fin):
    """Donut: Header vs Right Foot vs Left Foot."""
    headed = int((fin['Head'] == 'Si').sum())        if 'Head'         in fin.columns else 0
    right  = int((fin['Right footed'] == 'Si').sum()) if 'Right footed' in fin.columns else 0
    left   = max(len(fin) - headed - right, 0)

    data = [
        ('Header',     headed, HOME_COLOR),
        ('Right Foot', right,  GOLD),
        ('Left Foot',  left,   AWAY_COLOR),
    ]
    data = [(l, v, c) for l, v, c in data if v > 0]
    if not data:
        return empty_fig("No body part data")

    labels, values, colors = zip(*data)
    fig = go.Figure(go.Pie(
        labels=labels, values=values,
        marker_colors=colors,
        hole=0.45, textinfo='label+value',
        textfont=dict(color='white', size=11),
    ))
    fig.update_layout(**CHART_LAYOUT_DEFAULTS, height=220, showlegend=False)
    fig.update_layout(margin=dict(l=0, r=0, t=10, b=0))
    return fig


def _build_shot_timeline(tagged_events):
    """
    Dot-per-shot timeline across 90 minutes.
    Home shots on top lane, away shots on bottom.
    ★ goal  ● saved  ✕ miss
    """
    shot_types = ['Goal', 'Saved Shot', 'Miss']
    shots = tagged_events[tagged_events['event_type'].isin(shot_types)].copy()
    shots = shots.dropna(subset=['time_min'])

    if shots.empty:
        return empty_fig("No shot timeline data")

    color_map  = {'Goal': '#28a745', 'Saved Shot': GOLD,   'Miss': COLORS['garnet']}
    symbol_map = {'Goal': 'star',    'Saved Shot': 'circle','Miss': 'x'}
    size_map   = {'Goal': 18,        'Saved Shot': 11,      'Miss': 10}

    fig = go.Figure()

    # Half-time divider
    fig.add_vline(x=45, line_dash='dash',
                  line_color='rgba(255,255,255,0.25)', line_width=1)
    fig.add_annotation(x=45.5, y=1.0, xref='x', yref='paper',
                       text='HT', showarrow=False,
                       font=dict(color='rgba(255,255,255,0.35)', size=9))

    for team_pos, y_val in [('home', 0.72), ('away', 0.28)]:
        side_shots = (shots[shots['team_position'] == team_pos]
                      if 'team_position' in shots.columns else shots)
        for etype in shot_types:
            subset = side_shots[side_shots['event_type'] == etype]
            if subset.empty:
                continue
            player_col = (subset['player_name']
                          if 'player_name' in subset.columns
                          else subset['event_type'])
            fig.add_trace(go.Scatter(
                x=subset['time_min'],
                y=[y_val] * len(subset),
                mode='markers',
                name=etype,
                showlegend=(team_pos == 'home'),
                marker=dict(
                    color=color_map[etype],
                    size=size_map[etype],
                    symbol=symbol_map[etype],
                    line=dict(width=1, color='white'),
                ),
                text=player_col,
                hovertemplate="<b>%{text}</b> (%{x}')<extra>" + etype + "</extra>",
            ))

    fig.update_layout(
        **CHART_LAYOUT_DEFAULTS, height=160,
        xaxis=dict(title='Minute', range=[-2, 97],
                   tickmode='linear', tick0=0, dtick=15,
                   gridcolor='rgba(255,255,255,0.08)'),
        yaxis=dict(tickvals=[0.28, 0.72], ticktext=['Away', 'Home'],
                   showgrid=False, range=[0, 1]),
    )
    fig.update_layout(legend=dict(orientation='h', y=1.2, x=0.5, xanchor='center'),
                      margin=dict(l=50, r=10, t=10, b=30))
    return fig


# ---------------------------------------------------------------------------
# Main tab builder
# ---------------------------------------------------------------------------

def build_attack_tab(events):
    """Render the Organised Possession tab."""
    tagged     = tag_possession_phases(events)
    bu_stats   = get_build_up_stats(tagged)
    prog_stats = get_progression_stats(tagged)
    fb_stats   = get_fast_break_stats(tagged)
    fin_stats  = get_finishing_stats(tagged)

    fin = _get_fin_shots(tagged)

    # Phase distribution pie
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

    bu_map   = _build_phase_action_map(tagged, 'build_up',    'Build Up Actions')
    prog_map = _build_phase_action_map(tagged, 'progression',  'Progression Actions')

    shot_map   = _build_finishing_map(fin)
    zone_chart = _build_shot_zone_chart(fin)
    body_chart = _build_body_part_chart(fin)
    timeline   = _build_shot_timeline(tagged)

    return html.Div([
        html.H4("Organised Possession Analysis", style={'color': GOLD},
                className="mb-3"),
        html.P("Barcelona's possession decomposed into four analytical sub-phases.",
               style={'color': COLORS['text_secondary']}),

        # ── Phase overview ────────────────────────────────────────────────
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
            dbc.Col(section_card("Fast Break", [
                kpi_row(fb_stats, [
                    ('total_actions', 'Actions'), ('shots', 'Shots'),
                    ('goals', 'Goals'),
                ], colors={'goals': '#28a745'}),
            ]), width=6),
        ], className="mb-3"),

        # ── Finishing / Shot Analysis ─────────────────────────────────────
        html.H5("Finishing & Shot Analysis",
                style={
                    'color': GOLD,
                    'borderBottom': f'1px solid {COLORS["dark_border"]}',
                    'paddingBottom': '6px', 'marginBottom': '14px',
                }),

        kpi_row(fin_stats, [
            ('total_shots', 'Shots'),
            ('on_target',   'On Target'),
            ('goals',       'Goals'),
            ('headed',      'Headers'),
            ('right_foot',  'Right Foot'),
            ('left_foot',   'Left Foot'),
        ], colors={'goals': '#28a745', 'on_target': HOME_COLOR}),

        dbc.Row([
            dbc.Col(
                section_card("Shot Map  ★ Goal  ● Saved  ✕ Miss", [
                    dcc.Graph(figure=shot_map, config=CHART_CONFIG),
                ]),
                md=7,
            ),
            dbc.Col([
                section_card("Shot Zones", [
                    dcc.Graph(figure=zone_chart, config=CHART_CONFIG),
                ]),
                section_card("Body Part", [
                    dcc.Graph(figure=body_chart, config=CHART_CONFIG),
                ]),
            ], md=5),
        ], className="mb-3"),

        section_card("Shot Timeline", [
            dcc.Graph(figure=timeline, config=CHART_CONFIG),
        ]),
    ])
