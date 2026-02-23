"""
CuléVision - Team Analysis Page
Season-level Barcelona performance across attacking, defending and set pieces.
"""

from dash import html, dcc
from dash.dependencies import Input, Output, State
import dash_bootstrap_components as dbc
import plotly.graph_objects as go

from utils.config import COLORS
from utils.data_utils import (
    get_all_events,
    get_match_results,
    get_player_stats,
    get_player_stats_by_competition,
    get_team_season_stats,
    filter_own_goals,
    CURRENT_SEASON,
)
from pages.match_analysis_tabs.shared import (
    CHART_LAYOUT_DEFAULTS,
    CHART_CONFIG,
    add_pitch_background,
    PITCH_AXIS_HALF,
    PITCH_AXIS_FULL,
    stat_card,
    section_card,
    kpi_row,
    empty_fig,
    page_header,
    GOLD,
    HOME_COLOR,
    AWAY_COLOR,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_ALL_COMPETITIONS = [
    {'label': 'All Competitions', 'value': 'all'},
    {'label': 'La Liga',          'value': 'La Liga'},
    {'label': 'Champions League', 'value': 'Champions League'},
    {'label': 'Copa del Rey',     'value': 'Copa del Rey'},
    {'label': 'Spanish Super Cup','value': 'Spanish Super Cup'},
]

_COMP_SHORT = {
    'La Liga':           'Liga',
    'Champions League':  'UCL',
    'Copa del Rey':      'Copa',
    'Spanish Super Cup': 'SC',
}


def _filter_results(results, season, competition, match_ids=None):
    """Filter match results to season, competition and optionally specific match IDs."""
    season_start = int(season.split('-')[0])
    filtered = [
        r for r in results
        if str(r['date'])[:4] in [str(season_start), str(season_start + 1)]
    ]
    if competition and competition != 'all':
        filtered = [r for r in filtered if r['competition'] == competition]
    if match_ids:
        id_set = set(match_ids)
        filtered = [r for r in filtered if r['match_id'] in id_set]
    return filtered



def _kpi_from_results_and_events(results, events):
    """Compute KPI stats dict from a filtered results list and events DataFrame."""
    wins   = sum(1 for r in results if r['result'] == 'W')
    draws  = sum(1 for r in results if r['result'] == 'D')
    losses = sum(1 for r in results if r['result'] == 'L')
    gf     = sum(r['barca_goals']    for r in results)
    ga     = sum(r['opponent_goals'] for r in results)
    cs     = sum(1 for r in results if r['opponent_goals'] == 0)

    bar = events[events['team_code'] == 'BAR'] if not events.empty else events
    tackles       = int(bar[bar['event_type'] == 'Tackle'].shape[0])
    interceptions = int(bar[bar['event_type'] == 'Interception'].shape[0])
    pass_rows     = bar[bar['event_type'] == 'Pass']
    passes        = int(pass_rows.shape[0])
    pass_acc      = round(
        pass_rows['outcome'].eq(1).sum() / passes * 100, 1
    ) if passes > 0 else 0.0

    shot_types = ['Miss', 'Saved Shot', 'Goal']
    shots    = int(bar[bar['event_type'].isin(shot_types)].shape[0])
    shots_ot = int(bar[bar['event_type'].isin(['Saved Shot', 'Goal'])].shape[0])

    return {
        'matches_played': len(results),
        'wins':           wins,
        'draws':          draws,
        'losses':         losses,
        'goals_scored':   gf,
        'goals_conceded': ga,
        'clean_sheets':   cs,
        'tackles':        tackles,
        'interceptions':  interceptions,
        'passes':         passes,
        'pass_accuracy':  pass_acc,
        'shots':          shots,
        'shots_on_target':shots_ot,
    }


# ---------------------------------------------------------------------------
# Layout
# ---------------------------------------------------------------------------

def create_team_analysis_layout():
    """Create the Team Analysis page layout."""
    return dbc.Container([
        page_header("Team Analysis"),
        html.Hr(),

        # Controls
        dbc.Row([
            dbc.Col([
                html.Label("Competition",
                           style={'color': COLORS['text_secondary'], 'fontSize': '0.85rem'}),
                dcc.Dropdown(
                    id='ta-competition-selector',
                    options=_ALL_COMPETITIONS,
                    value='all',
                    clearable=False,
                    style={'backgroundColor': COLORS['dark_secondary']},
                )
            ], md=3),
            dbc.Col([
                html.Label("Match(es)",
                           style={'color': COLORS['text_secondary'], 'fontSize': '0.85rem'}),
                dcc.Dropdown(
                    id='ta-match-selector',
                    options=[],
                    value=None,
                    multi=True,
                    clearable=True,
                    placeholder="All matches…",
                    style={'backgroundColor': COLORS['dark_secondary']},
                )
            ], md=7),
        ], className="mb-4"),

        # Tabs
        dbc.Tabs(id='ta-tabs', active_tab='ta-tab-overview', children=[
            dbc.Tab(label='Overview',              tab_id='ta-tab-overview'),
            dbc.Tab(label='Attack',                tab_id='ta-tab-attacking'),
            dbc.Tab(label='Attacking Transition',  tab_id='ta-tab-att-transition'),
            dbc.Tab(label='Defense',               tab_id='ta-tab-defending'),
            dbc.Tab(label='Defensive Transition',  tab_id='ta-tab-def-transition'),
            dbc.Tab(label='Set Pieces',            tab_id='ta-tab-setpieces'),
        ], className="mb-3"),

        dcc.Loading(
            id='ta-loading',
            type='circle',
            color=COLORS['gold'],
            children=html.Div(id='ta-content'),
        ),
    ], fluid=True, className="py-4")


# ---------------------------------------------------------------------------
# Tab builders
# ---------------------------------------------------------------------------

def _build_overview(season, competition, match_ids=None):
    all_results = get_match_results()
    results     = _filter_results(all_results, season, competition, match_ids)

    events = get_all_events(season)
    if not events.empty:
        if competition and competition != 'all' and 'competition' in events.columns:
            events = events[events['competition'] == competition]
        if match_ids:
            events = events[events['match_id'].isin(match_ids)]

    if not results:
        return html.P("No data available.", style={'color': COLORS['text_secondary']})

    # Compute KPIs from the (possibly filtered) scope
    if match_ids or (competition and competition != 'all'):
        stats = _kpi_from_results_and_events(results, events)
    else:
        stats = get_team_season_stats(season, competition)
        if not stats:
            stats = _kpi_from_results_and_events(results, events)

    kpi = kpi_row(stats, [
        ('matches_played', 'Played'),
        ('wins',           'Wins'),
        ('draws',          'Draws'),
        ('losses',         'Losses'),
        ('goals_scored',   'Goals For'),
        ('goals_conceded', 'Goals Against'),
        ('clean_sheets',   'Clean Sheets'),
    ], colors={
        'wins': COLORS['primary_blue'],
        'losses': COLORS['garnet'],
        'clean_sheets': COLORS['gold'],
    })

    points = stats['wins'] * 3 + stats['draws']
    pts_card = dbc.Row([
        dbc.Col(stat_card(points, 'Points', COLORS['gold']), md=2)
    ], className="mb-3")

    # Form trendline
    sorted_results = sorted(results, key=lambda x: x['date'])
    cumulative, ppg_vals, labels = [], [], []
    total = 0
    for i, r in enumerate(sorted_results, 1):
        pts = 3 if r['result'] == 'W' else (1 if r['result'] == 'D' else 0)
        total += pts
        cumulative.append(total)
        ppg_vals.append(round(total / i, 2))
        labels.append(f"{r['opponent']} ({r['result']})")

    if cumulative:
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=list(range(1, len(cumulative) + 1)),
            y=cumulative,
            mode='lines+markers',
            name='Cumulative Points',
            line=dict(color=GOLD, width=2),
            marker=dict(size=6),
            text=labels,
            hovertemplate='Match %{x}: %{text}<br>Points: %{y}<extra></extra>',
        ))
        fig.add_trace(go.Scatter(
            x=list(range(1, len(ppg_vals) + 1)),
            y=ppg_vals,
            mode='lines',
            name='PPG',
            line=dict(color=HOME_COLOR, width=1.5, dash='dot'),
            hovertemplate='PPG: %{y}<extra></extra>',
        ))
        fig.update_layout(**CHART_LAYOUT_DEFAULTS, height=300,
                          xaxis_title='Match', yaxis_title='Points')
        trendline = section_card("Form Trendline",
                                 dcc.Graph(figure=fig, config=CHART_CONFIG))
    else:
        trendline = html.Div()

    return html.Div([kpi, pts_card, trendline])


_ZONE_COLS = {
    'Small box-centre':  'Inside 6yd Box',
    'Box-centre':        'Penalty Area',
    'Out of box-centre': 'Outside Box',
    '35+ centre':        '35+ Yards',
}

_SHOT_STYLE = {
    'Goal':       ('star',   GOLD,       18),
    'Saved Shot': ('circle', HOME_COLOR, 11),
    'Miss':       ('x',      AWAY_COLOR, 10),
}


def _shot_zone_chart(shots):
    """Overlapping horizontal bars — shots (blue) vs goals (gold) per zone."""
    zones, shot_counts, goal_counts = [], [], []
    for col, label in _ZONE_COLS.items():
        if col not in shots.columns:
            continue
        mask  = shots[col] == 'Si'
        total = int(mask.sum())
        goals = int(shots.loc[mask & (shots['event_type'] == 'Goal')].shape[0])
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


def _body_part_chart(shots):
    """Donut — Header vs Right Foot vs Left Foot."""
    headed = int((shots['Head'] == 'Si').sum())         if 'Head'         in shots.columns else 0
    right  = int((shots['Right footed'] == 'Si').sum()) if 'Right footed' in shots.columns else 0
    left   = max(len(shots) - headed - right, 0)

    data = [('Header', headed, HOME_COLOR), ('Right Foot', right, GOLD), ('Left Foot', left, AWAY_COLOR)]
    data = [(l, v, c) for l, v, c in data if v > 0]
    if not data:
        return empty_fig("No body part data")

    labels, values, colors = zip(*data)
    fig = go.Figure(go.Pie(
        labels=labels, values=values, marker_colors=colors,
        hole=0.45, textinfo='label+value', textfont=dict(color='white', size=11),
    ))
    fig.update_layout(**CHART_LAYOUT_DEFAULTS, height=220, showlegend=False)
    fig.update_layout(margin=dict(l=0, r=0, t=10, b=0))
    return fig


def _build_attacking(season, competition, match_ids=None):
    events = get_all_events(season)
    if events.empty:
        return html.P("No data available.", style={'color': COLORS['text_secondary']})

    if competition and competition != 'all' and 'competition' in events.columns:
        events = events[events['competition'] == competition]
    if match_ids:
        events = events[events['match_id'].isin(match_ids)]

    bar = events[events['team_code'] == 'BAR']

    # ── Shot map with distinct symbols ★ goal · ● saved · ✕ miss ──────────
    shot_types = ['Goal', 'Saved Shot', 'Miss']
    shots = bar[bar['event_type'].isin(shot_types)].dropna(subset=['x', 'y'])

    if not shots.empty:
        fig_shots = go.Figure()
        add_pitch_background(fig_shots, half=True)
        for etype, (symbol, color, size) in _SHOT_STYLE.items():
            subset = shots[shots['event_type'] == etype]
            if subset.empty:
                continue
            body = subset.apply(
                lambda r: ('Header'     if r.get('Head') == 'Si'
                           else 'Right Foot' if r.get('Right footed') == 'Si'
                           else 'Left Foot'),
                axis=1,
            )
            fig_shots.add_trace(go.Scatter(
                x=subset['x'], y=subset['y'],
                mode='markers', name=etype,
                marker=dict(color=color, size=size, symbol=symbol,
                            line=dict(color='white', width=1.5)),
                customdata=list(zip(
                    subset.get('player_name', subset.index),
                    body,
                )),
                hovertemplate=(
                    '<b>%{customdata[0]}</b><br>%{customdata[1]}'
                    '<extra>' + etype + '</extra>'
                ),
            ))
        fig_shots.update_layout(**CHART_LAYOUT_DEFAULTS, height=400, **PITCH_AXIS_HALF)
        fig_shots.update_layout(legend=dict(orientation='h', y=-0.05, x=0.5, xanchor='center'))
        shot_map = section_card("Shot Map  ★ Goal  ● Saved  ✕ Miss",
                                dcc.Graph(figure=fig_shots, config=CHART_CONFIG))
    else:
        shot_map = section_card("Shot Map", empty_fig("No shot data"))

    # ── Zone + body part breakdown ─────────────────────────────────────────
    zone_card = section_card("Shot Zones",
                             dcc.Graph(figure=_shot_zone_chart(shots), config=CHART_CONFIG))
    body_card = section_card("Body Part",
                             dcc.Graph(figure=_body_part_chart(shots), config=CHART_CONFIG))

    # ── Top scorers ────────────────────────────────────────────────────────
    if match_ids:
        goal_ev = filter_own_goals(bar[bar['event_type'] == 'Goal'].copy())
        scorers_series = goal_ev.groupby('player_name').size().sort_values(ascending=False).head(10)
        if not scorers_series.empty:
            fig_scorers = go.Figure(go.Bar(
                x=scorers_series.values,
                y=scorers_series.index,
                orientation='h',
                marker_color=GOLD,
                hovertemplate='%{y}: %{x} goals<extra></extra>',
            ))
            fig_scorers.update_layout(**CHART_LAYOUT_DEFAULTS, height=350,
                                      xaxis_title='Goals', yaxis=dict(autorange='reversed'))
            scorers_card = section_card("Top Scorers",
                                        dcc.Graph(figure=fig_scorers, config=CHART_CONFIG))
        else:
            scorers_card = section_card("Top Scorers", empty_fig("No goals in selection"))
    else:
        player_stats = get_player_stats(season)
        if not player_stats.empty:
            if competition and competition != 'all':
                comp_stats = get_player_stats_by_competition(competition, season)
                if not comp_stats.empty:
                    player_stats = comp_stats
            top10 = player_stats[player_stats['goals'] > 0].head(10)
            fig_scorers = go.Figure(go.Bar(
                x=top10['goals'], y=top10['player'],
                orientation='h',
                marker_color=GOLD,
                hovertemplate='%{y}: %{x} goals<extra></extra>',
            ))
            fig_scorers.update_layout(**CHART_LAYOUT_DEFAULTS, height=350,
                                      xaxis_title='Goals', yaxis=dict(autorange='reversed'))
            scorers_card = section_card("Top Scorers",
                                        dcc.Graph(figure=fig_scorers, config=CHART_CONFIG))
        else:
            scorers_card = section_card("Top Scorers", empty_fig("No scorer data"))

    # ── Goals by match ─────────────────────────────────────────────────────
    results = _filter_results(get_match_results(), season, competition, match_ids)
    results_sorted = sorted(results, key=lambda x: x['date'])
    if results_sorted:
        result_colors = {'W': HOME_COLOR, 'D': COLORS['gold'], 'L': AWAY_COLOR}
        fig_goals = go.Figure(go.Bar(
            x=[f"{r['opponent']} ({r['date']})" for r in results_sorted],
            y=[r['barca_goals'] for r in results_sorted],
            marker_color=[result_colors.get(r['result'], GOLD) for r in results_sorted],
            hovertemplate='%{x}<br>Goals: %{y}<extra></extra>',
        ))
        fig_goals.update_layout(**CHART_LAYOUT_DEFAULTS, height=300,
                                xaxis_tickangle=-45, yaxis_title='Goals Scored')
        goals_card = section_card("Goals by Match",
                                  dcc.Graph(figure=fig_goals, config=CHART_CONFIG))
    else:
        goals_card = html.Div()

    return html.Div([
        dbc.Row([
            dbc.Col(shot_map, md=7),
            dbc.Col([zone_card, body_card], md=5),
        ], className="mb-3"),
        dbc.Row([
            dbc.Col(scorers_card, md=6),
            dbc.Col(goals_card,   md=6),
        ]),
        goals_card,
    ])


def _build_defending(season, competition, match_ids=None):
    all_results = get_match_results()
    results     = _filter_results(all_results, season, competition, match_ids)

    events = get_all_events(season)
    if not events.empty:
        if competition and competition != 'all' and 'competition' in events.columns:
            events = events[events['competition'] == competition]
        if match_ids:
            events = events[events['match_id'].isin(match_ids)]

    if not results:
        return html.P("No data available.", style={'color': COLORS['text_secondary']})

    if match_ids or (competition and competition != 'all'):
        stats = _kpi_from_results_and_events(results, events)
    else:
        stats = get_team_season_stats(season, competition)
        if not stats:
            stats = _kpi_from_results_and_events(results, events)

    kpi = kpi_row(stats, [
        ('goals_conceded', 'Goals Conceded'),
        ('clean_sheets',   'Clean Sheets'),
        ('tackles',        'Tackles'),
        ('interceptions',  'Interceptions'),
    ], colors={'goals_conceded': AWAY_COLOR, 'clean_sheets': GOLD})

    results_sorted = sorted(results, key=lambda x: x['date'])
    if results_sorted:
        fig = go.Figure(go.Bar(
            x=[f"{r['opponent']} ({r['date']})" for r in results_sorted],
            y=[r['opponent_goals'] for r in results_sorted],
            marker_color=AWAY_COLOR,
            hovertemplate='%{x}<br>Conceded: %{y}<extra></extra>',
        ))
        for i, r in enumerate(results_sorted):
            if r['opponent_goals'] == 0:
                fig.add_annotation(x=i, y=0.1, text="CS",
                                   showarrow=False, font=dict(color=GOLD, size=11))
        fig.update_layout(**CHART_LAYOUT_DEFAULTS, height=300,
                          xaxis_tickangle=-45, yaxis_title='Goals Conceded')
        conceded_card = section_card("Goals Conceded by Match",
                                     dcc.Graph(figure=fig, config=CHART_CONFIG))
    else:
        conceded_card = html.Div()

    return html.Div([kpi, conceded_card])


def _build_attacking_transition(season, competition, match_ids=None):
    """Attacking transition: possession gains and counter-attack opportunities."""
    events = get_all_events(season)
    if events.empty:
        return html.P("No data available.", style={'color': COLORS['text_secondary']})

    if competition and competition != 'all' and 'competition' in events.columns:
        events = events[events['competition'] == competition]
    if match_ids:
        events = events[events['match_id'].isin(match_ids)]

    bar = events[events['team_code'] == 'BAR']

    # Possession gains: Ball Recovery, Tackle (won), Interception
    gain_types = ['Ball Recovery', 'Tackle', 'Interception']
    gains = bar[bar['event_type'].isin(gain_types)].dropna(subset=['x', 'y'])

    ball_recoveries = int(bar[bar['event_type'] == 'Ball Recovery'].shape[0])
    tackles_won     = int(
        bar[(bar['event_type'] == 'Tackle') & (bar['outcome'] == 1)].shape[0]
    )
    interceptions   = int(bar[bar['event_type'] == 'Interception'].shape[0])
    # "Counter starts": gains deep in own half (x < 40 → plenty of space ahead)
    counter_starts  = int(gains[gains['x'] < 40].shape[0])

    kpi = kpi_row(
        {
            'ball_recoveries': ball_recoveries,
            'tackles_won':     tackles_won,
            'interceptions':   interceptions,
            'counter_starts':  counter_starts,
        },
        [
            ('ball_recoveries', 'Ball Recoveries'),
            ('tackles_won',     'Tackles Won'),
            ('interceptions',   'Interceptions'),
            ('counter_starts',  'Own-Third Recoveries'),
        ],
        colors={'ball_recoveries': GOLD, 'counter_starts': HOME_COLOR},
    )

    # Possession gains scatter (full pitch, coloured by type)
    if not gains.empty:
        color_map_g = {
            'Ball Recovery': GOLD,
            'Tackle':        HOME_COLOR,
            'Interception':  AWAY_COLOR,
        }
        fig_gains = go.Figure()
        add_pitch_background(fig_gains, half=False)
        for etype, color in color_map_g.items():
            subset = gains[gains['event_type'] == etype]
            if subset.empty:
                continue
            player_col = subset['player_name'] if 'player_name' in subset.columns else subset['event_type']
            fig_gains.add_trace(go.Scatter(
                x=subset['x'], y=subset['y'],
                mode='markers', name=etype,
                marker=dict(color=color, size=7, opacity=0.75,
                            line=dict(color='white', width=0.5)),
                text=player_col,
                hovertemplate='%{text}<extra>' + etype + '</extra>',
            ))
        fig_gains.update_layout(**CHART_LAYOUT_DEFAULTS, height=400, **PITCH_AXIS_FULL)
        gains_card = section_card("Possession Gains",
                                  dcc.Graph(figure=fig_gains, config=CHART_CONFIG))
    else:
        gains_card = section_card("Possession Gains", empty_fig("No possession gain data"))

    # Gains per match bar chart
    results = _filter_results(get_match_results(), season, competition, match_ids)
    results_sorted = sorted(results, key=lambda x: x['date'])
    if results_sorted and not gains.empty:
        counts = [
            int(gains[gains['match_id'] == r['match_id']].shape[0])
            for r in results_sorted
        ]
        fig_pm = go.Figure(go.Bar(
            x=[f"{r['opponent']} ({str(r['date'])[:10]})" for r in results_sorted],
            y=counts,
            marker_color=GOLD,
            hovertemplate='%{x}<br>Possession Gains: %{y}<extra></extra>',
        ))
        fig_pm.update_layout(**CHART_LAYOUT_DEFAULTS, height=280,
                             xaxis_tickangle=-45, yaxis_title='Possession Gains')
        pm_card = section_card("Possession Gains per Match",
                               dcc.Graph(figure=fig_pm, config=CHART_CONFIG))
    else:
        pm_card = html.Div()

    return html.Div([kpi, gains_card, pm_card])


def _build_defensive_transition(season, competition, match_ids=None):
    """Defensive transition: pressing intensity and defensive shape."""
    events = get_all_events(season)
    if events.empty:
        return html.P("No data available.", style={'color': COLORS['text_secondary']})

    if competition and competition != 'all' and 'competition' in events.columns:
        events = events[events['competition'] == competition]
    if match_ids:
        events = events[events['match_id'].isin(match_ids)]

    bar = events[events['team_code'] == 'BAR']

    def_actions = bar[bar['event_type'].isin(['Tackle', 'Interception'])].dropna(subset=['x', 'y'])
    # High press: defensive actions in opposition's half (x > 50 in Opta = attacking half)
    high_press = def_actions[def_actions['x'] > 50]
    fouls      = bar[bar['event_type'] == 'Foul']

    press_pct = round(len(high_press) / max(len(def_actions), 1) * 100, 1)

    kpi = kpi_row(
        {
            'def_actions': len(def_actions),
            'high_press':  len(high_press),
            'press_pct':   press_pct,
            'fouls':       len(fouls),
        },
        [
            ('def_actions', 'Defensive Actions'),
            ('high_press',  'High Press Actions'),
            ('press_pct',   'High Press %'),
            ('fouls',       'Fouls Conceded'),
        ],
        colors={'high_press': GOLD, 'press_pct': HOME_COLOR},
    )

    # Defensive actions scatter (full pitch)
    if not def_actions.empty:
        fig_def = go.Figure()
        add_pitch_background(fig_def, half=False)
        tackles   = def_actions[def_actions['event_type'] == 'Tackle']
        intercepts = def_actions[def_actions['event_type'] == 'Interception']
        if not tackles.empty:
            fig_def.add_trace(go.Scatter(
                x=tackles['x'], y=tackles['y'],
                mode='markers', name='Tackle',
                marker=dict(color=HOME_COLOR, size=7, opacity=0.75,
                            line=dict(color='white', width=0.5)),
                hovertemplate='Tackle<extra></extra>',
            ))
        if not intercepts.empty:
            fig_def.add_trace(go.Scatter(
                x=intercepts['x'], y=intercepts['y'],
                mode='markers', name='Interception',
                marker=dict(color=AWAY_COLOR, size=7, opacity=0.75,
                            symbol='diamond', line=dict(color='white', width=0.5)),
                hovertemplate='Interception<extra></extra>',
            ))
        fig_def.update_layout(**CHART_LAYOUT_DEFAULTS, height=400, **PITCH_AXIS_FULL)
        def_card = section_card("Defensive Actions Map",
                                dcc.Graph(figure=fig_def, config=CHART_CONFIG))
    else:
        def_card = section_card("Defensive Actions Map", empty_fig("No defensive action data"))

    # Defensive actions per match
    results = _filter_results(get_match_results(), season, competition, match_ids)
    results_sorted = sorted(results, key=lambda x: x['date'])
    if results_sorted:
        counts = [
            int(def_actions[def_actions['match_id'] == r['match_id']].shape[0])
            if not def_actions.empty else 0
            for r in results_sorted
        ]
        fig_pm = go.Figure(go.Bar(
            x=[f"{r['opponent']} ({str(r['date'])[:10]})" for r in results_sorted],
            y=counts,
            marker_color=HOME_COLOR,
            hovertemplate='%{x}<br>Defensive Actions: %{y}<extra></extra>',
        ))
        fig_pm.update_layout(**CHART_LAYOUT_DEFAULTS, height=280,
                             xaxis_tickangle=-45, yaxis_title='Defensive Actions')
        pm_card = section_card("Defensive Actions per Match",
                               dcc.Graph(figure=fig_pm, config=CHART_CONFIG))
    else:
        pm_card = html.Div()

    return html.Div([kpi, def_card, pm_card])


def _build_setpieces(season, competition, match_ids=None):
    events = get_all_events(season)
    if events.empty:
        return html.P("No data available.", style={'color': COLORS['text_secondary']})

    if competition and competition != 'all' and 'competition' in events.columns:
        events = events[events['competition'] == competition]
    if match_ids:
        events = events[events['match_id'].isin(match_ids)]

    bar = events[events['team_code'] == 'BAR']

    corners = bar[bar['event_type'] == 'Corner Awarded']
    fk_types = ['Free Kick', 'Indirect Free Kick']
    free_kicks = bar[bar['event_type'].isin(fk_types)] if any(
        t in bar['event_type'].unique() for t in fk_types
    ) else bar[bar['event_type'] == 'Foul']

    corner_goals = 0
    if 'From corner' in events.columns:
        corner_goals = len(bar[
            (bar['event_type'] == 'Goal') & (bar['From corner'] == 'Si')
        ])

    penalty_goals = 0
    if 'Penalty' in events.columns:
        penalty_goals = len(bar[
            (bar['event_type'] == 'Goal') & (bar['Penalty'] == 'Si')
        ])

    kpi = kpi_row(
        {
            'corners':       len(corners),
            'corner_goals':  corner_goals,
            'free_kicks':    len(free_kicks),
            'penalty_goals': penalty_goals,
        },
        [
            ('corners',       'Corners'),
            ('corner_goals',  'Corner Goals'),
            ('free_kicks',    'Free Kicks'),
            ('penalty_goals', 'Penalty Goals'),
        ],
        colors={'corner_goals': GOLD, 'penalty_goals': GOLD},
    )

    corners_xy = corners.dropna(subset=['x', 'y'])
    if not corners_xy.empty:
        fig_corners = go.Figure()
        add_pitch_background(fig_corners, half=False)
        fig_corners.add_trace(go.Scatter(
            x=corners_xy['x'], y=corners_xy['y'],
            mode='markers',
            marker=dict(color=GOLD, size=9, line=dict(color='white', width=1)),
            hovertemplate='Corner at (%{x:.1f}, %{y:.1f})<extra></extra>',
        ))
        fig_corners.update_layout(**CHART_LAYOUT_DEFAULTS, height=360, **PITCH_AXIS_FULL)
        corners_card = section_card("Corner Locations",
                                    dcc.Graph(figure=fig_corners, config=CHART_CONFIG))
    else:
        corners_card = section_card("Corner Locations", empty_fig("No corner data"))

    return html.Div([kpi, corners_card])


# ---------------------------------------------------------------------------
# Callbacks
# ---------------------------------------------------------------------------

def register_team_analysis_callbacks(app):
    """Register all Team Analysis callbacks."""

    # -- Match selector options (updates when competition changes) ---------
    @app.callback(
        Output('ta-match-selector', 'options'),
        Output('ta-match-selector', 'value'),
        Input('ta-competition-selector', 'value'),
    )
    def update_ta_match_options(competition):
        results = get_match_results()
        if competition and competition != 'all':
            results = [r for r in results if r['competition'] == competition]
        results = sorted(results, key=lambda x: x['date'], reverse=True)

        options = []
        for r in results:
            comp_tag = _COMP_SHORT.get(r['competition'], r['competition'][:4])
            label = (
                f"{str(r['date'])[:10]}  vs  {r['opponent']}  ({r['result']})"
                + (f"  · {comp_tag}" if competition == 'all' else '')
            )
            options.append({'label': label, 'value': r['match_id']})

        return options, None   # None = all matches selected by default

    # -- Tab content -------------------------------------------------------
    @app.callback(
        Output('ta-content', 'children'),
        Input('ta-competition-selector', 'value'),
        Input('ta-tabs', 'active_tab'),
        Input('ta-match-selector', 'value'),
    )
    def update_ta_content(competition, active_tab, match_ids):
        # Normalise: empty list → None (treat as "all matches")
        match_ids = match_ids or None

        if active_tab == 'ta-tab-overview':
            return _build_overview(CURRENT_SEASON, competition, match_ids)
        elif active_tab == 'ta-tab-attacking':
            return _build_attacking(CURRENT_SEASON, competition, match_ids)
        elif active_tab == 'ta-tab-att-transition':
            return _build_attacking_transition(CURRENT_SEASON, competition, match_ids)
        elif active_tab == 'ta-tab-defending':
            return _build_defending(CURRENT_SEASON, competition, match_ids)
        elif active_tab == 'ta-tab-def-transition':
            return _build_defensive_transition(CURRENT_SEASON, competition, match_ids)
        elif active_tab == 'ta-tab-setpieces':
            return _build_setpieces(CURRENT_SEASON, competition, match_ids)
        return html.Div()
