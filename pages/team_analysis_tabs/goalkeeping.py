"""
Team Analysis — Tab 6: Goalkeeping & Shot Prevention

Answers: Is our defensive system or our goalkeeper carrying the defense?

Shows:
- KPIs: shots faced, goals conceded, save rate, clean sheets, goals/game
- Shots faced map (opponent shots — mirrored to show Barcelona's goal)
- Goals conceded map
- Goals conceded by match bar chart
- Save rate trend over season
- Shots faced by zone breakdown
"""

from dash import html, dcc
import dash_bootstrap_components as dbc
import plotly.graph_objects as go

from utils.config import COLORS
from utils.data_utils import (
    get_all_events,
    get_match_results,
    exclude_own_goals,
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
    GOLD,
    HOME_COLOR,
    AWAY_COLOR,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _shots_faced_map(opp_events):
    """Half-pitch map of all opponent shots (mirrored to show Barca's defensive half)."""
    shot_types = ['Goal', 'Saved Shot', 'Miss']
    shots = exclude_own_goals(
        opp_events[opp_events['event_type'].isin(shot_types)].copy()
    ).dropna(subset=['x', 'y'])

    if shots.empty:
        return empty_fig("No opponent shot data")

    shots = shots.copy()
    shots['x_m'] = 100 - shots['x']   # mirror: opp attacks from right → show on left half

    _style = {
        'Goal':       ('star',   AWAY_COLOR, 18),
        'Saved Shot': ('circle', GOLD,       12),
        'Miss':       ('x',      '#888888',  9),
    }

    fig = go.Figure()
    add_pitch_background(fig, half=True)

    for etype, (symbol, color, size) in _style.items():
        subset = shots[shots['event_type'] == etype]
        if subset.empty:
            continue
        fig.add_trace(go.Scatter(
            x=subset['x_m'], y=subset['y'],
            mode='markers', name=etype,
            marker=dict(color=color, size=size, symbol=symbol,
                        line=dict(color='white', width=1.5)),
            text=subset['player_name'].fillna(''),
            hovertemplate='<b>%{text}</b><extra>' + etype + '</extra>',
        ))

    fig.update_layout(**CHART_LAYOUT_DEFAULTS, height=400, **PITCH_AXIS_HALF)
    fig.update_layout(legend=dict(orientation='h', y=-0.05, x=0.5, xanchor='center'))
    return fig


def _goals_conceded_map(opp_events):
    """Half-pitch map of goals scored against Barcelona (mirrored)."""
    goals = exclude_own_goals(
        opp_events[opp_events['event_type'] == 'Goal'].copy()
    ).dropna(subset=['x', 'y'])

    if goals.empty:
        return empty_fig("No goals conceded data")

    goals = goals.copy()
    goals['x_m'] = 100 - goals['x']

    fig = go.Figure()
    add_pitch_background(fig, half=True)
    fig.add_trace(go.Scatter(
        x=goals['x_m'], y=goals['y'],
        mode='markers',
        marker=dict(color=AWAY_COLOR, size=14, symbol='star',
                    line=dict(color='white', width=1.5)),
        text=goals['player_name'].fillna(''),
        hovertemplate='<b>%{text}</b><extra>Goal Conceded</extra>',
        name='Goal Conceded',
    ))
    fig.update_layout(**CHART_LAYOUT_DEFAULTS, height=380, **PITCH_AXIS_HALF)
    return fig


def _goals_conceded_by_match(results):
    """Bar chart of goals conceded per match."""
    results_sorted = sorted(results, key=lambda x: x['date'])
    if not results_sorted:
        return empty_fig("No match data")

    labels = [f"{r['opponent']} ({str(r['date'])[:10]})" for r in results_sorted]
    values = [r['opponent_goals'] for r in results_sorted]
    colors = [AWAY_COLOR if v > 0 else GOLD for v in values]

    fig = go.Figure(go.Bar(
        x=labels, y=values,
        marker_color=colors,
        hovertemplate='%{x}<br>Goals Conceded: %{y}<extra></extra>',
    ))

    # Annotate clean sheets
    for i, (label, val) in enumerate(zip(labels, values)):
        if val == 0:
            fig.add_annotation(x=i, y=0.05, text="CS",
                               showarrow=False, font=dict(color=GOLD, size=11))

    fig.update_layout(
        **CHART_LAYOUT_DEFAULTS, height=300,
        xaxis_tickangle=-45,
        yaxis_title='Goals Conceded',
    )
    return fig


def _save_rate_trend(results, opp_events):
    """Line chart: rolling save % across matches."""
    results_sorted = sorted(results, key=lambda x: x['date'])
    if not results_sorted:
        return empty_fig("No match data")

    shot_types = ['Saved Shot', 'Goal']
    save_rates, labels = [], []

    for r in results_sorted:
        match_opp = opp_events[opp_events['match_id'] == r['match_id']]
        shots_on  = match_opp[match_opp['event_type'].isin(shot_types)]
        saved     = match_opp[match_opp['event_type'] == 'Saved Shot']
        n_sot     = len(shots_on)
        rate      = round(len(saved) / n_sot * 100, 1) if n_sot > 0 else None
        save_rates.append(rate)
        comp_short = {'La Liga': 'Liga', 'Champions League': 'UCL',
                      'Copa del Rey': 'Copa', 'Spanish Super Cup': 'SC'}
        labels.append(f"{r['opponent']} · {comp_short.get(r['competition'], r['competition'][:4])}")

    valid = [(i, l, v) for i, (l, v) in enumerate(zip(labels, save_rates), 1) if v is not None]
    if not valid:
        return empty_fig("No on-target shot data")

    xs, ls, ys = zip(*valid)
    fig = go.Figure(go.Scatter(
        x=list(xs), y=list(ys),
        mode='lines+markers',
        line=dict(color=GOLD, width=2),
        marker=dict(size=7),
        text=list(ls),
        hovertemplate='%{text}<br>Save Rate: %{y}%<extra></extra>',
    ))
    fig.add_hline(y=70, line=dict(color='rgba(255,255,255,0.2)', dash='dot'),
                  annotation_text='70%', annotation_position='right')
    fig.update_layout(
        **CHART_LAYOUT_DEFAULTS, height=280,
        xaxis_title='Match',
        yaxis_title='Save Rate %',
        yaxis=dict(range=[0, 105]),
    )
    return fig


def _shots_faced_zone_bar(opp_events):
    """Horizontal bar: opponent shots by distance zone."""
    shot_types = ['Goal', 'Saved Shot', 'Miss']
    shots = opp_events[opp_events['event_type'].isin(shot_types)]

    if shots.empty or 'x' not in shots.columns:
        return empty_fig("No shot zone data")

    shots = shots.dropna(subset=['x'])
    # Opp x > 80 → inside box; 66-80 → edge of box; < 66 → outside box
    inside  = int(shots[shots['x'] > 80].shape[0])
    edge    = int(shots[(shots['x'] >= 66) & (shots['x'] <= 80)].shape[0])
    outside = int(shots[shots['x'] < 66].shape[0])

    fig = go.Figure(go.Bar(
        y=['Outside Box', 'Box Edge', 'Inside Box'],
        x=[outside, edge, inside],
        orientation='h',
        marker_color=[GOLD, HOME_COLOR, AWAY_COLOR],
        hovertemplate='%{y}: %{x} shots<extra></extra>',
    ))
    fig.update_layout(
        **CHART_LAYOUT_DEFAULTS, height=200,
        xaxis_title='Shots Faced',
        margin=dict(l=10, r=10, t=10, b=30),
    )
    return fig


# ---------------------------------------------------------------------------
# Public builder
# ---------------------------------------------------------------------------

def build_goalkeeping_tab(season, competitions, match_ids=None):
    """Build the Goalkeeping & Shot Prevention tab content."""
    events = get_all_events(season)
    if events.empty:
        return html.P("No data available.", style={'color': COLORS['text_secondary']})

    if competitions and 'competition' in events.columns:
        events = events[events['competition'].isin(competitions)]
    if match_ids:
        events = events[events['match_id'].isin(match_ids)]

    opp = exclude_own_goals(events[events['team_code'] != 'BAR'].copy())

    all_results = get_match_results()
    results = [r for r in all_results
               if str(r['date'])[:4] in [season.split('-')[0], season.split('-')[1]]]
    if competitions:
        results = [r for r in results if r['competition'] in competitions]
    if match_ids:
        id_set = set(match_ids)
        results = [r for r in results if r['match_id'] in id_set]

    if not results:
        return html.P("No data for this selection.", style={'color': COLORS['text_secondary']})

    # ── KPIs ────────────────────────────────────────────────────────────────
    shot_types = ['Goal', 'Saved Shot', 'Miss']
    sot_types  = ['Goal', 'Saved Shot']

    shots_faced = int(opp[opp['event_type'].isin(shot_types)].shape[0])
    sot_faced   = int(opp[opp['event_type'].isin(sot_types)].shape[0])
    saves       = int(opp[opp['event_type'] == 'Saved Shot'].shape[0])
    save_rate   = round(saves / max(sot_faced, 1) * 100, 1)
    goals_con   = sum(r['opponent_goals'] for r in results)
    cs          = sum(1 for r in results if r['opponent_goals'] == 0)
    matches     = len(results)
    gpg         = round(goals_con / max(matches, 1), 2)

    kpi = kpi_row(
        {
            'shots_faced': shots_faced,
            'sot_faced':   sot_faced,
            'saves':       saves,
            'save_rate':   f"{save_rate}%",
            'goals_con':   goals_con,
            'cs':          cs,
            'gpg':         gpg,
        },
        [
            ('shots_faced', 'Shots Faced'),
            ('sot_faced',   'On Target'),
            ('saves',       'Saves'),
            ('save_rate',   'Save Rate'),
            ('goals_con',   'Goals Conceded'),
            ('cs',          'Clean Sheets'),
            ('gpg',         'Goals/Game'),
        ],
        colors={'save_rate': GOLD, 'cs': GOLD, 'goals_con': AWAY_COLOR, 'gpg': AWAY_COLOR},
    )

    # ── Cards ────────────────────────────────────────────────────────────────
    shots_map_card  = section_card("Shots Faced  ★ Goal  ● Saved  ✕ Miss",
                                    dcc.Graph(figure=_shots_faced_map(opp), config=CHART_CONFIG))
    goals_map_card  = section_card("Goals Conceded Locations",
                                    dcc.Graph(figure=_goals_conceded_map(opp), config=CHART_CONFIG))
    conceded_card   = section_card("Goals Conceded by Match",
                                    dcc.Graph(figure=_goals_conceded_by_match(results), config=CHART_CONFIG))
    save_trend_card = section_card("Save Rate per Match",
                                    dcc.Graph(figure=_save_rate_trend(results, opp), config=CHART_CONFIG))
    zone_card       = section_card("Shots Faced by Zone",
                                    dcc.Graph(figure=_shots_faced_zone_bar(opp), config=CHART_CONFIG))

    return html.Div([
        kpi,
        dbc.Row([
            dbc.Col(shots_map_card, md=6),
            dbc.Col(goals_map_card, md=6),
        ], className="mb-3"),
        dbc.Row([
            dbc.Col(conceded_card,   md=7),
            dbc.Col([save_trend_card, zone_card], md=5),
        ]),
    ])
