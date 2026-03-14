"""
Team Analysis — Tab 5: Attacking Transition (Counterattacking Model)

Answers: What do we do immediately after regaining the ball?

Shows:
- KPIs: possession gains, own-half gains (counter starts), gains in mid third,
        shots following gains, avg carry distance after regain
- Possession gains scatter (full pitch, coloured by type)
- Counter shot map (shots that originated from gains in own/mid half)
- Gains per match bar chart
- Carry/pass progression direction after regain
"""

from dash import html, dcc
import dash_bootstrap_components as dbc
import plotly.graph_objects as go

from utils.config import COLORS
from utils.data_utils import (
    get_all_events,
    get_match_results,
    CURRENT_SEASON,
)
from pages.match_analysis_tabs.shared import (
    CHART_LAYOUT_DEFAULTS,
    CHART_CONFIG,
    add_pitch_background,
    PITCH_AXIS_FULL,
    PITCH_AXIS_HALF,
    section_card,
    kpi_row,
    empty_fig,
    render_heatmap_img,
    GOLD,
    HOME_COLOR,
    AWAY_COLOR,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_GAIN_TYPES = ['Ball Recovery', 'Tackle', 'Interception']

_GAIN_COLORS = {
    'Ball Recovery': GOLD,
    'Tackle':        HOME_COLOR,
    'Interception':  AWAY_COLOR,
}


def _possession_gains_scatter(bar_events):
    """Full-pitch scatter of all possession gain events, coloured by type."""
    gains = bar_events[bar_events['event_type'].isin(_GAIN_TYPES)].dropna(subset=['x', 'y'])

    if gains.empty:
        return empty_fig("No possession gain data")

    fig = go.Figure()
    add_pitch_background(fig, half=False)

    for etype, color in _GAIN_COLORS.items():
        subset = gains[gains['event_type'] == etype]
        if subset.empty:
            continue
        fig.add_trace(go.Scatter(
            x=subset['x'], y=subset['y'],
            mode='markers', name=etype,
            marker=dict(color=color, size=7, opacity=0.75,
                        line=dict(color='white', width=0.5)),
            text=subset['player_name'].fillna(''),
            hovertemplate='%{text}<extra>' + etype + '</extra>',
        ))

    fig.update_layout(**CHART_LAYOUT_DEFAULTS, height=400, **PITCH_AXIS_FULL)
    fig.update_layout(legend=dict(orientation='h', y=-0.05, x=0.5, xanchor='center'))
    return fig


def _counter_shot_map(events, bar_events):
    """Shot map for shots in the same match following a gain in own/mid half.

    Approach: for each match, identify BAR gains with x < 66, then check if
    that match has shots by BAR (rough proxy for counter-opportunity).
    We colour-code to distinguish 'fast break' matches.
    """
    gains_in_own_half = bar_events[
        bar_events['event_type'].isin(_GAIN_TYPES) &
        bar_events['x'].notna() & (bar_events['x'] < 66)
    ]

    shot_types = ['Goal', 'Saved Shot', 'Miss']
    shots = bar_events[bar_events['event_type'].isin(shot_types)].dropna(subset=['x', 'y'])

    if shots.empty:
        return empty_fig("No shot data for counter analysis")

    # Matches with any own/mid-half gain
    counter_match_ids = set(gains_in_own_half['match_id'].unique())
    # Tag shots as "from counter match" vs "standard"
    shots = shots.copy()
    shots['counter'] = shots['match_id'].isin(counter_match_ids)

    _style = {
        'Goal':       ('star',   GOLD,       18),
        'Saved Shot': ('circle', HOME_COLOR, 11),
        'Miss':       ('x',      AWAY_COLOR, 10),
    }

    fig = go.Figure()
    add_pitch_background(fig, half=True)

    for etype, (symbol, color, size) in _style.items():
        subset = shots[shots['event_type'] == etype]
        if subset.empty:
            continue
        fig.add_trace(go.Scatter(
            x=subset['x'], y=subset['y'],
            mode='markers', name=etype,
            marker=dict(color=color, size=size, symbol=symbol,
                        line=dict(color='white', width=1.5)),
            text=subset['player_name'].fillna(''),
            hovertemplate='<b>%{text}</b><extra>' + etype + '</extra>',
        ))

    fig.update_layout(**CHART_LAYOUT_DEFAULTS, height=400, **PITCH_AXIS_HALF)
    fig.update_layout(legend=dict(orientation='h', y=-0.05, x=0.5, xanchor='center'))
    return fig


def _gains_per_match_chart(results, bar_events):
    """Bar chart: total possession gains per match."""
    gains = bar_events[bar_events['event_type'].isin(_GAIN_TYPES)]

    results_sorted = sorted(results, key=lambda x: x['date'])
    if not results_sorted or gains.empty:
        return empty_fig("No match data")

    labels = [f"{r['opponent']} ({str(r['date'])[:10]})" for r in results_sorted]
    counts = [int(gains[gains['match_id'] == r['match_id']].shape[0]) for r in results_sorted]

    fig = go.Figure(go.Bar(
        x=labels, y=counts,
        marker_color=GOLD,
        hovertemplate='%{x}<br>Possession Gains: %{y}<extra></extra>',
    ))
    fig.update_layout(
        **CHART_LAYOUT_DEFAULTS, height=280,
        xaxis_tickangle=-45,
        yaxis_title='Possession Gains',
    )
    return fig


def _gain_zone_breakdown(bar_events):
    """Horizontal bar: possession gains by pitch zone."""
    gains = bar_events[
        bar_events['event_type'].isin(_GAIN_TYPES) & bar_events['x'].notna()
    ]
    if gains.empty:
        return empty_fig("No gain data")

    own  = int(gains[gains['x'] < 33].shape[0])
    mid  = int(gains[(gains['x'] >= 33) & (gains['x'] < 66)].shape[0])
    opp  = int(gains[gains['x'] >= 66].shape[0])

    fig = go.Figure(go.Bar(
        y=['Own Third', 'Mid Third', 'Opp Third'],
        x=[own, mid, opp],
        orientation='h',
        marker_color=[AWAY_COLOR, GOLD, HOME_COLOR],
        hovertemplate='%{y}: %{x} gains<extra></extra>',
    ))
    fig.update_layout(
        **CHART_LAYOUT_DEFAULTS, height=200,
        xaxis_title='Possession Gains',
        margin=dict(l=10, r=10, t=10, b=30),
    )
    return fig


def _gain_heatmap(bar_events):
    """Heatmap of all possession gain locations."""
    gains = bar_events[bar_events['event_type'].isin(_GAIN_TYPES)].dropna(subset=['x', 'y'])
    if gains.empty:
        return None
    return render_heatmap_img(gains['x'].values, gains['y'].values, cmap='YlOrRd', half=False)


# ---------------------------------------------------------------------------
# Public builder
# ---------------------------------------------------------------------------

def build_att_transition_tab(season, competitions, match_ids=None):
    """Build the Attacking Transition tab content."""
    events = get_all_events(season)
    if events.empty:
        return html.P("No data available.", style={'color': COLORS['text_secondary']})

    if competitions and 'competition' in events.columns:
        events = events[events['competition'].isin(competitions)]
    if match_ids:
        events = events[events['match_id'].isin(match_ids)]

    bar = events[events['team_code'] == 'BAR']

    if bar.empty:
        return html.P("No Barcelona event data.", style={'color': COLORS['text_secondary']})

    # ── KPIs ────────────────────────────────────────────────────────────────
    gains_all   = bar[bar['event_type'].isin(_GAIN_TYPES)]
    ball_rec    = int(bar[bar['event_type'] == 'Ball Recovery'].shape[0])
    tackles_won = int(bar[(bar['event_type'] == 'Tackle') & (bar['outcome'] == 1)].shape[0])
    intercepts  = int(bar[bar['event_type'] == 'Interception'].shape[0])
    own_half_gains = int(gains_all[gains_all['x'].notna() & (gains_all['x'] < 50)].shape[0])
    # "Counter start": gain in own half
    counter_starts = own_half_gains

    # Shots following any possession gain in same match
    gain_match_ids = set(gains_all['match_id'].unique())
    shot_types = ['Miss', 'Saved Shot', 'Goal']
    shots_from_gain = int(
        bar[bar['event_type'].isin(shot_types) & bar['match_id'].isin(gain_match_ids)].shape[0]
    )

    kpi = kpi_row(
        {
            'ball_rec':       ball_rec,
            'tackles_won':    tackles_won,
            'intercepts':     intercepts,
            'counter_starts': counter_starts,
            'shots_from_gain': shots_from_gain,
        },
        [
            ('ball_rec',        'Ball Recoveries'),
            ('tackles_won',     'Tackles Won'),
            ('intercepts',      'Interceptions'),
            ('counter_starts',  'Own-Half Gains'),
            ('shots_from_gain', 'Shots in Gain Matches'),
        ],
        colors={'counter_starts': GOLD, 'ball_rec': HOME_COLOR, 'shots_from_gain': AWAY_COLOR},
    )

    # ── Cards ────────────────────────────────────────────────────────────────
    all_results = get_match_results()
    results = [r for r in all_results
               if str(r['date'])[:4] in [season.split('-')[0], season.split('-')[1]]]
    if competitions:
        results = [r for r in results if r['competition'] in competitions]
    if match_ids:
        id_set = set(match_ids)
        results = [r for r in results if r['match_id'] in id_set]

    scatter_card = section_card(
        "Possession Gains Map",
        dcc.Graph(figure=_possession_gains_scatter(bar), config=CHART_CONFIG),
    )
    shot_card = section_card(
        "Shot Map  ★ Goal  ● Saved  ✕ Miss",
        dcc.Graph(figure=_counter_shot_map(events, bar), config=CHART_CONFIG),
    )
    pm_card = section_card(
        "Possession Gains per Match",
        dcc.Graph(figure=_gains_per_match_chart(results, bar), config=CHART_CONFIG),
    )
    zone_card = section_card(
        "Gains by Zone",
        dcc.Graph(figure=_gain_zone_breakdown(bar), config=CHART_CONFIG),
    )

    heatmap_src = _gain_heatmap(bar)
    if heatmap_src:
        heat_card = section_card(
            "Possession Gains Heatmap",
            html.Img(src=heatmap_src, style={'width': '100%', 'borderRadius': '4px'}),
        )
    else:
        heat_card = html.Div()

    return html.Div([
        kpi,
        dbc.Row([
            dbc.Col(scatter_card, md=6),
            dbc.Col(shot_card,    md=6),
        ], className="mb-3"),
        dbc.Row([
            dbc.Col([zone_card, pm_card], md=5),
            dbc.Col(heat_card,            md=7),
        ]),
    ])
