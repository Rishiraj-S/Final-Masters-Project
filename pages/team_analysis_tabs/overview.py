"""
Team Analysis — Tab 0: Overview

Aggregates KPIs from all phases into a single summary view.

Shows:
- Season KPI cards (poss%, shots/g, goals/g, PPDA, xGA proxy, clean sheets)
- Phase radar chart (6 tactical dimensions)
- Trend sparklines (rolling 5-match possession, shots, PPDA)
- Territory map (BAR average touch heatmap)
- Game model index (composite phase scores as horizontal bars)
- Phase comparison (BAR vs opponents per-match averages)
"""

from dash import html, dcc
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
import pandas as pd
import numpy as np

from utils.config import COLORS
from utils.data_utils import (
    get_all_events,
    get_match_results,
    filter_own_goals,
    exclude_own_goals,
    CURRENT_SEASON,
)
from pages.match_analysis_tabs.shared import (
    CHART_LAYOUT_DEFAULTS,
    CHART_CONFIG,
    section_card,
    kpi_row,
    empty_fig,
    render_heatmap_img,
    GOLD,
    HOME_COLOR,
    AWAY_COLOR,
)


_COMP_SHORT = {
    'La Liga': 'Liga',
    'Champions League': 'UCL',
    'Copa del Rey': 'Copa',
    'Spanish Super Cup': 'SC',
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _phase_scores(bar, opp, results):
    """
    Compute 0-100 scores for 6 tactical phases.
    Returns dict keyed by phase name.
    """
    scores = {}

    # Build-up quality: pass accuracy in own half (x < 50)
    own_half_passes = bar[(bar['event_type'] == 'Pass') & bar['x'].notna() & (bar['x'] < 50)]
    build_up = round(own_half_passes['outcome'].eq(1).sum() / max(len(own_half_passes), 1) * 100, 1) \
        if not own_half_passes.empty else 50.0
    scores['Build-up'] = min(build_up, 100)

    # Chance creation: key passes + final third entries per 100 touches
    all_passes = bar[bar['event_type'] == 'Pass']
    key_p = int(bar[(bar['event_type'] == 'Pass') & (bar.get('Assist', pd.Series(dtype=str)) == 'Si')].shape[0]) \
        if 'Assist' in bar.columns else 0
    ft_entries = int(bar[bar['x'].notna() & (bar['x'] >= 66)].shape[0])
    total_bar  = max(len(bar), 1)
    chance_score = min(round((key_p * 3 + ft_entries) / total_bar * 100, 1), 100)
    scores['Chance Creation'] = chance_score

    # Pressing intensity: PPDA inverted (lower PPDA = higher score)
    opp_def_passes = opp[(opp['event_type'] == 'Pass') & opp['x'].notna() & (opp['x'] < 40)]
    bar_press      = bar[bar['event_type'].isin(['Tackle', 'Interception']) &
                         bar['x'].notna() & (bar['x'] > 50)]
    ppda = round(len(opp_def_passes) / max(len(bar_press), 1), 1)
    press_score = max(0, min(100, round(100 - ppda * 5, 1)))
    scores['Pressing'] = press_score

    # Defensive structure: 100 - (shots conceded / matches) * 10
    n_matches   = len(set(bar['match_id'].unique())) if 'match_id' in bar.columns else max(len(results), 1)
    opp_shots   = int(opp[opp['event_type'].isin(['Goal', 'Saved Shot', 'Miss'])].shape[0])
    shots_pm    = opp_shots / max(n_matches, 1)
    def_score   = max(0, min(100, round(100 - shots_pm * 5, 1)))
    scores['Def. Structure'] = def_score

    # Transition efficiency: gains in opp half / total gains
    gains = bar[bar['event_type'].isin(['Ball Recovery', 'Tackle', 'Interception'])]
    opp_half_gains = gains[gains['x'].notna() & (gains['x'] > 50)] if not gains.empty else gains
    trans_score = round(len(opp_half_gains) / max(len(gains), 1) * 100, 1) if not gains.empty else 50.0
    scores['Transitions'] = min(trans_score, 100)

    # Set piece threat: set piece shots / total shots
    shot_types = ['Goal', 'Saved Shot', 'Miss']
    bar_shots  = bar[bar['event_type'].isin(shot_types)]
    sp_shots   = bar_shots[bar_shots.get('Set piece', pd.Series(dtype=str)) == 'Si'] \
        if 'Set piece' in bar_shots.columns else bar_shots.head(0)
    sp_score = round(len(sp_shots) / max(len(bar_shots), 1) * 100, 1) \
        if not bar_shots.empty else 25.0
    scores['Set Pieces'] = min(sp_score * 2, 100)  # scale up

    return scores


def _phase_radar(scores):
    """Radar chart from phase scores dict."""
    if not scores:
        return empty_fig("No phase data")

    categories = list(scores.keys())
    values     = [round(scores[c], 1) for c in categories]
    cats_closed = categories + [categories[0]]
    vals_closed = values + [values[0]]

    fig = go.Figure()
    fig.add_trace(go.Scatterpolar(
        r=vals_closed,
        theta=cats_closed,
        fill='toself',
        name='Barcelona',
        line=dict(color=GOLD, width=2),
        fillcolor='rgba(161,120,40,0.3)',
        hovertemplate='%{theta}: %{r:.1f}<extra></extra>',
    ))
    fig.update_layout(
        **CHART_LAYOUT_DEFAULTS,
        height=360,
        polar=dict(
            bgcolor='rgba(0,0,0,0)',
            radialaxis=dict(
                visible=True, range=[0, 100],
                color=COLORS['text_secondary'],
                gridcolor='rgba(255,255,255,0.15)',
                tickfont=dict(size=9),
            ),
            angularaxis=dict(
                color=COLORS['text_secondary'],
                gridcolor='rgba(255,255,255,0.15)',
            ),
        ),
        showlegend=False,
    )
    return fig


def _game_model_index(scores):
    """Horizontal progress bars — one per phase, 0-100."""
    if not scores:
        return html.P("No phase data", style={'color': COLORS['text_secondary']})

    color_map = {
        'Build-up':       HOME_COLOR,
        'Chance Creation': GOLD,
        'Pressing':       AWAY_COLOR,
        'Def. Structure': '#5c7cfa',
        'Transitions':    '#51cf66',
        'Set Pieces':     '#cc5de8',
    }

    bars = []
    for phase, score in scores.items():
        color = color_map.get(phase, GOLD)
        bars.append(html.Div([
            html.Div([
                html.Span(phase, style={
                    'color': COLORS['text_primary'], 'fontSize': '0.85rem',
                    'width': '130px', 'display': 'inline-block',
                }),
                html.Span(f"{score:.0f}", style={
                    'color': color, 'fontWeight': 700, 'fontSize': '0.9rem',
                    'marginLeft': '8px',
                }),
            ], style={'marginBottom': '3px'}),
            html.Div(
                html.Div(style={
                    'width': f"{score}%",
                    'height': '8px',
                    'backgroundColor': color,
                    'borderRadius': '4px',
                    'transition': 'width 0.4s ease',
                }),
                style={
                    'backgroundColor': 'rgba(255,255,255,0.08)',
                    'borderRadius': '4px',
                    'marginBottom': '10px',
                }
            ),
        ]))

    return html.Div(bars, style={'padding': '8px 0'})


def _rolling_trend(results, events, window=5):
    """3-panel sparklines: rolling possession, shots, PPDA over matches."""
    sorted_r = sorted(results, key=lambda r: r['date'])
    if not sorted_r or events.empty:
        return empty_fig("No trend data")

    labels, poss_vals, shot_vals, ppda_vals = [], [], [], []

    for r in sorted_r:
        me = events[events['match_id'] == r['match_id']] if 'match_id' in events.columns else events.head(0)
        if me.empty:
            continue
        bar_ev = me[me['team_code'] == 'BAR']
        opp_ev = me[me['team_code'] != 'BAR']

        bar_p = len(bar_ev[bar_ev['event_type'] == 'Pass'])
        all_p = len(me[me['event_type'] == 'Pass'])
        poss  = round(bar_p / max(all_p, 1) * 100, 1)

        shot_types = ['Goal', 'Saved Shot', 'Miss']
        shots = int(bar_ev[bar_ev['event_type'].isin(shot_types)].shape[0])

        opp_dp = opp_ev[(opp_ev['event_type'] == 'Pass') & opp_ev['x'].notna() & (opp_ev['x'] < 40)]
        bar_pr = bar_ev[bar_ev['event_type'].isin(['Tackle', 'Interception']) &
                        bar_ev['x'].notna() & (bar_ev['x'] > 50)]
        ppda   = round(len(opp_dp) / max(len(bar_pr), 1), 1)

        comp = _COMP_SHORT.get(r['competition'], r['competition'][:4])
        labels.append(f"{r['opponent']} · {comp}")
        poss_vals.append(poss)
        shot_vals.append(shots)
        ppda_vals.append(ppda)

    if len(poss_vals) < 2:
        return empty_fig("Not enough matches for trend")

    x = list(range(1, len(poss_vals) + 1))

    def _rolling_avg(vals, w):
        result = []
        for i in range(len(vals)):
            window_vals = vals[max(0, i - w + 1):i + 1]
            result.append(round(sum(window_vals) / len(window_vals), 1))
        return result

    r_poss = _rolling_avg(poss_vals, window)
    r_shot = _rolling_avg(shot_vals, window)
    r_ppda = _rolling_avg(ppda_vals, window)

    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=x, y=r_poss, name=f'Possession % (roll.{window})',
        line=dict(color=HOME_COLOR, width=2),
        text=labels, hovertemplate='Match %{x}: %{text}<br>Poss: %{y}%<extra></extra>',
    ))
    fig.add_trace(go.Scatter(
        x=x, y=r_ppda, name=f'PPDA (roll.{window})',
        line=dict(color=AWAY_COLOR, width=2, dash='dot'),
        text=labels, hovertemplate='Match %{x}: %{text}<br>PPDA: %{y}<extra></extra>',
        yaxis='y2',
    ))
    fig.add_trace(go.Bar(
        x=x, y=r_shot, name=f'Shots (roll.{window})',
        marker_color='rgba(161,120,40,0.4)',
        hovertemplate='Match %{x}: %{text}<br>Shots: %{y}<extra></extra>',
        text=labels, yaxis='y3',
    ))

    fig.update_layout(
        **CHART_LAYOUT_DEFAULTS,
        height=320,
        xaxis=dict(title='Match #', gridcolor='rgba(255,255,255,0.05)'),
        yaxis=dict(title='Possession %', side='left', range=[0, 100],
                   gridcolor='rgba(255,255,255,0.05)'),
        yaxis2=dict(title='PPDA', overlaying='y', side='right',
                    showgrid=False, range=[0, 30]),
        yaxis3=dict(overlaying='y', side='right', showgrid=False,
                    range=[0, 20], visible=False),
        barmode='overlay',
    )
    fig.update_layout(legend=dict(orientation='h', y=1.05, x=0.5, xanchor='center'))
    return fig


def _territory_map(bar):
    """Full-pitch heatmap of Barcelona touch locations."""
    coords = bar.dropna(subset=['x', 'y'])
    if coords.empty:
        return None
    return render_heatmap_img(coords['x'].values, coords['y'].values, cmap='Blues', half=False)


def _phase_comparison_chart(bar, opp, results):
    """Grouped bar: BAR vs Opponents per-match averages for key metrics."""
    n_matches = max(len(results), 1)

    bar_passes = bar[bar['event_type'] == 'Pass']
    opp_passes = opp[opp['event_type'] == 'Pass']
    shot_types = ['Goal', 'Saved Shot', 'Miss']
    bar_shots  = bar[bar['event_type'].isin(shot_types)]
    opp_shots  = opp[opp['event_type'].isin(shot_types)]
    bar_def    = bar[bar['event_type'].isin(['Tackle', 'Interception', 'Clearance'])]
    opp_def    = opp[opp['event_type'].isin(['Tackle', 'Interception', 'Clearance'])]
    bar_goals  = filter_own_goals(bar[bar['event_type'] == 'Goal'].copy())
    opp_goals  = exclude_own_goals(opp[opp['event_type'] == 'Goal'].copy())

    metrics = ['Passes/Match', 'Shots/Match', 'Def Actions/Match', 'Goals/Match']
    bar_vals = [
        round(len(bar_passes) / n_matches, 1),
        round(len(bar_shots)  / n_matches, 1),
        round(len(bar_def)    / n_matches, 1),
        round(len(bar_goals)  / n_matches, 2),
    ]
    opp_vals = [
        round(len(opp_passes) / n_matches, 1),
        round(len(opp_shots)  / n_matches, 1),
        round(len(opp_def)    / n_matches, 1),
        round(len(opp_goals)  / n_matches, 2),
    ]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        name='Barcelona',
        x=metrics, y=bar_vals,
        marker_color=GOLD,
        hovertemplate='%{x}: %{y}<extra>Barcelona</extra>',
    ))
    fig.add_trace(go.Bar(
        name='Opponents',
        x=metrics, y=opp_vals,
        marker_color='rgba(255,255,255,0.25)',
        hovertemplate='%{x}: %{y}<extra>Opponents</extra>',
    ))
    fig.update_layout(
        **CHART_LAYOUT_DEFAULTS,
        height=320,
        barmode='group',
        yaxis_title='Per Match Average',
    )
    fig.update_layout(legend=dict(orientation='h', y=1.05, x=0.5, xanchor='center'))
    return fig


# ---------------------------------------------------------------------------
# Public builder
# ---------------------------------------------------------------------------

def build_overview_tab(season, competitions, match_ids=None):
    """Build the Overview tab content."""
    all_results = get_match_results()
    results = [
        r for r in all_results
        if str(r['date'])[:4] in [season.split('-')[0], season.split('-')[1]]
    ]
    if competitions:
        results = [r for r in results if r['competition'] in competitions]
    if match_ids:
        id_set  = set(match_ids)
        results = [r for r in results if r['match_id'] in id_set]

    if not results:
        return html.P("No data for selected filters.", style={'color': COLORS['text_secondary']})

    events = get_all_events(season)
    if not events.empty:
        if competitions and 'competition' in events.columns:
            events = events[events['competition'].isin(competitions)]
        if match_ids:
            events = events[events['match_id'].isin(match_ids)]

    bar = events[events['team_code'] == 'BAR'] if not events.empty else events
    opp = events[events['team_code'] != 'BAR'] if not events.empty else events

    n_matches = len(results)

    # ── KPI row ──────────────────────────────────────────────────────────────
    wins  = sum(1 for r in results if r['result'] == 'W')
    draws = sum(1 for r in results if r['result'] == 'D')
    loss  = sum(1 for r in results if r['result'] == 'L')
    pts   = wins * 3 + draws
    ppg   = round(pts / max(n_matches, 1), 2)
    gf    = sum(r['barca_goals']    for r in results)
    ga    = sum(r['opponent_goals'] for r in results)
    cs    = sum(1 for r in results if r['opponent_goals'] == 0)

    bar_passes = bar[bar['event_type'] == 'Pass'] if not bar.empty else bar
    all_passes = events[events['event_type'] == 'Pass'] if not events.empty else events
    poss       = round(len(bar_passes) / max(len(all_passes), 1) * 100, 1)

    opp_shots = int(opp[opp['event_type'].isin(['Goal', 'Saved Shot', 'Miss'])].shape[0]) \
        if not opp.empty else 0
    opp_goals_pm = round(ga / max(n_matches, 1), 2)

    opp_dp  = opp[(opp['event_type'] == 'Pass') & opp['x'].notna() & (opp['x'] < 40)] \
        if not opp.empty else opp
    bar_pr  = bar[bar['event_type'].isin(['Tackle', 'Interception']) &
                  bar['x'].notna() & (bar['x'] > 50)] if not bar.empty else bar
    ppda    = round(len(opp_dp) / max(len(bar_pr), 1), 1)

    kpi = kpi_row(
        {
            'record':   f"{wins}W-{draws}D-{loss}L",
            'pts':      pts,
            'ppg':      ppg,
            'poss':     f"{poss}%",
            'ppda':     ppda,
            'gf':       gf,
            'ga':       ga,
            'cs':       cs,
            'opp_xga':  round(opp_shots / max(n_matches, 1), 1),
        },
        [
            ('record',  'Record'),
            ('pts',     'Points'),
            ('ppg',     'PPG'),
            ('poss',    'Possession'),
            ('ppda',    'PPDA'),
            ('gf',      'Goals For'),
            ('ga',      'Goals Against'),
            ('cs',      'Clean Sheets'),
            ('opp_xga', 'Opp Shots/Match'),
        ],
        colors={
            'pts':    GOLD,
            'ppg':    GOLD,
            'poss':   HOME_COLOR,
            'cs':     HOME_COLOR,
            'ppda':   AWAY_COLOR,
            'ga':     AWAY_COLOR,
        },
    )

    # ── Phase scores ─────────────────────────────────────────────────────────
    scores = _phase_scores(bar, opp, results) if not bar.empty else {}

    # ── Section cards ─────────────────────────────────────────────────────────
    radar_card = section_card(
        "Phase Profile Radar — 6 Tactical Dimensions",
        dcc.Graph(figure=_phase_radar(scores), config=CHART_CONFIG),
    )

    gmi_card = section_card(
        "Game Model Index — Phase Scores (0 – 100)",
        _game_model_index(scores),
    )

    trend_card = section_card(
        "Trend Sparklines — Rolling 5-Match: Possession · PPDA · Shots",
        dcc.Graph(figure=_rolling_trend(results, events), config=CHART_CONFIG),
    )

    comparison_card = section_card(
        "Phase Comparison — Barcelona vs Opponents (per match avg.)",
        dcc.Graph(figure=_phase_comparison_chart(bar, opp, results), config=CHART_CONFIG),
    )

    territory_src = _territory_map(bar)
    territory_card = section_card(
        "Territory Map — Average Touch Locations",
        html.Img(src=territory_src, style={'width': '100%', 'borderRadius': '4px'}),
    ) if territory_src else html.Div()

    return html.Div([
        kpi,
        dbc.Row([
            dbc.Col(radar_card,   md=5),
            dbc.Col(gmi_card,     md=7),
        ], className='mb-3'),
        dbc.Row([
            dbc.Col(trend_card,      md=7),
            dbc.Col(territory_card,  md=5),
        ], className='mb-3'),
        dbc.Row([
            dbc.Col(comparison_card, md=12),
        ], className='mb-3'),
    ])
