"""
Team Analysis — Tab 0: Overview

Visual introduction to the five deep-dive tabs.

Layout (top → bottom):
  1. Season snapshot banner  — record, form strip, key KPIs
  2. Stat pills row          — GF · GA · CS · Matches · Pass Acc · PPDA
  3. Phase cards strip       — one card per deep-dive tab with metrics + score bar
  4. Game-model radar  ⟺  Rolling form sparkline
  5. Barcelona vs Opponents per-match comparison (horizontal bars)
"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
from dash import html, dcc
import dash_bootstrap_components as dbc

from utils.config import COLORS
from utils.data_utils import (
    get_all_events,
    get_match_results,
    filter_own_goals,
    exclude_own_goals,
    CURRENT_SEASON,
)
from page_utils.visualizations import (
    CHART_CONFIG,
    layout_config,
    empty_fig,
    GOLD,
    HOME_COLOR,
    AWAY_COLOR,
)


# ─── Constants ────────────────────────────────────────────────────────────────

_RESULT_BG   = {'W': '#22c55e', 'D': '#f59f00', 'L': '#ef4444'}
_RESULT_TEXT = {'W': '#14532d', 'D': '#78350f',  'L': 'white'}

_PHASE_COLORS = {
    'Build-up':         HOME_COLOR,
    'Chance Creation':  GOLD,
    'Transitions':      '#51cf66',
    'Def. Structure':   '#5c7cfa',
    'Set Pieces':       '#cc5de8',
}

_PHASE_TAB = {
    'Build-up':         'Build-up',
    'Chance Creation':  'Chance Creation',
    'Transitions':      'Transitions',
    'Def. Structure':   'Def. Structure',
    'Set Pieces':       'Set Pieces',
}

_COMP_SHORT = {
    'La Liga': 'Liga',
    'Champions League': 'UCL',
    'Copa del Rey': 'Copa',
    'Spanish Super Cup': 'SC',
}

_CARD = {
    'backgroundColor': COLORS['dark_secondary'],
    'border':          f'1px solid {COLORS["dark_border"]}',
    'borderRadius':    '8px',
    'padding':         '16px',
    'height':          '100%',
}


# ─── Reusable visual components ───────────────────────────────────────────────

def _score_bar(score: float, color: str) -> html.Div:
    pct = max(0.0, min(100.0, score))
    return html.Div(
        html.Div(style={
            'width': f'{pct:.0f}%', 'height': '5px',
            'backgroundColor': color, 'borderRadius': '3px',
            'transition': 'width 0.5s ease',
        }),
        style={
            'backgroundColor': 'rgba(255,255,255,0.08)',
            'borderRadius': '3px', 'marginBottom': '10px',
        },
    )


def _metric_row(label: str, value: str, color: str = COLORS['text_primary']) -> html.Div:
    return html.Div([
        html.Span(label, style={
            'color': COLORS['text_secondary'], 'fontSize': '0.72rem', 'flex': '1',
        }),
        html.Span(value, style={
            'color': color, 'fontWeight': '700', 'fontSize': '0.80rem',
        }),
    ], style={
        'display': 'flex', 'alignItems': 'center',
        'padding': '5px 0', 'borderBottom': f'1px solid {COLORS["dark_border"]}',
    })


def _phase_card(title: str, tab: str, score: float, color: str,
                metrics: list[tuple[str, str, str]]) -> html.Div:
    """Intro card for one tactical phase — colored top accent, score bar, 3 metric rows."""
    return html.Div([
        # Colored top accent line (sits flush against the card top edge)
        html.Div(style={
            'height': '3px', 'backgroundColor': color,
            'borderRadius': '6px 6px 0 0',
            'margin': '-16px -16px 14px -16px',
        }),
        # Phase title + score badge
        html.Div([
            html.Div(title, style={
                'color': color, 'fontWeight': '800',
                'fontSize': '0.76rem', 'letterSpacing': '0.8px',
                'textTransform': 'uppercase',
            }),
            html.Div([
                html.Span(f'{score:.0f}', style={
                    'color': color, 'fontWeight': '800', 'fontSize': '1.05rem',
                }),
                html.Span('/100', style={
                    'color': COLORS['text_secondary'], 'fontSize': '0.56rem',
                }),
            ]),
        ], style={
            'display': 'flex', 'justifyContent': 'space-between',
            'alignItems': 'center', 'marginBottom': '8px',
        }),
        _score_bar(score, color),
        html.Div([_metric_row(lbl, val, col) for lbl, val, col in metrics]),
        html.Div([
            html.Span('Explore → ', style={
                'color': color, 'fontSize': '0.58rem', 'opacity': '0.8',
                'fontStyle': 'italic',
            }),
            html.Span(f'{tab} tab', style={
                'color': color, 'fontSize': '0.58rem', 'fontWeight': '600',
                'opacity': '0.8',
            }),
        ], style={'marginTop': '10px', 'display': 'flex', 'alignItems': 'center'}),
    ], style={**_CARD, 'padding': '16px'})


def _form_strip(results: list[dict], n: int = 10) -> html.Div:
    """Last N results as W/D/L colored badges."""
    recent = sorted(results, key=lambda r: str(r['date']))[-n:]
    return html.Div([
        html.Span(
            r.get('result', '?'),
            title=f"{r.get('opponent', '')} ({_COMP_SHORT.get(r.get('competition', ''), '')})",
            style={
                'backgroundColor': _RESULT_BG.get(r.get('result', '?'), '#444'),
                'color':           _RESULT_TEXT.get(r.get('result', '?'), 'white'),
                'fontWeight': '800',
                'fontSize':   '0.62rem',
                'padding':    '3px 8px',
                'borderRadius': '4px',
                'letterSpacing': '0.5px',
                'display': 'inline-block',
                'cursor': 'default',
            },
        )
        for r in recent
    ], style={'display': 'flex', 'gap': '4px', 'flexWrap': 'wrap'})


def _season_banner(results: list[dict], wins: int, draws: int, loss: int,
                   pts: int, ppg: float, poss: float, ppda: float,
                   gf: int, ga: int) -> html.Div:
    gd      = gf - ga
    gd_sign = '+' if gd >= 0 else ''
    gd_col  = GOLD if gd >= 0 else AWAY_COLOR

    # Left block: record + goal difference
    left = html.Div([
        html.Div(
            [
                html.Span(f'{wins}', style={'color': '#22c55e', 'fontWeight': '900', 'fontSize': '1.8rem'}),
                html.Span('W  ', style={'color': COLORS['text_secondary'], 'fontSize': '0.9rem', 'fontWeight': '600', 'marginRight': '8px'}),
                html.Span(f'{draws}', style={'color': '#f59f00', 'fontWeight': '900', 'fontSize': '1.8rem'}),
                html.Span('D  ', style={'color': COLORS['text_secondary'], 'fontSize': '0.9rem', 'fontWeight': '600', 'marginRight': '8px'}),
                html.Span(f'{loss}', style={'color': '#ef4444', 'fontWeight': '900', 'fontSize': '1.8rem'}),
                html.Span('L', style={'color': COLORS['text_secondary'], 'fontSize': '0.9rem', 'fontWeight': '600'}),
            ],
            style={'lineHeight': '1.1', 'letterSpacing': '1px'},
        ),
        html.Div(f'GD {gd_sign}{gd}', style={
            'color': gd_col, 'fontSize': '0.82rem',
            'fontWeight': '700', 'marginTop': '6px', 'letterSpacing': '0.5px',
        }),
    ], style={'flex': '1', 'minWidth': '0'})

    # Center block: form strip
    center = html.Div([
        html.Div('LAST 10', style={
            'color': COLORS['text_secondary'], 'fontSize': '0.56rem',
            'fontWeight': '700', 'letterSpacing': '1.2px',
            'textTransform': 'uppercase', 'marginBottom': '8px',
        }),
        _form_strip(results, 10),
    ], style={'flex': '1.5', 'minWidth': '0', 'paddingLeft': '20px'})

    # Right block: 4 quick-stat tiles
    def _qs(val, label, color=COLORS['text_primary']):
        return html.Div([
            html.Div(str(val), style={
                'fontWeight': '800', 'fontSize': '1.3rem',
                'color': color, 'lineHeight': '1.1',
            }),
            html.Div(label, style={
                'color': COLORS['text_secondary'], 'fontSize': '0.55rem',
                'fontWeight': '700', 'letterSpacing': '0.5px',
                'textTransform': 'uppercase', 'marginTop': '2px',
            }),
        ], style={'textAlign': 'center', 'flex': '1'})

    right = html.Div([
        _qs(pts,           'Points',    GOLD),
        _qs(f'{ppg:.2f}',  'Pts/Game',  GOLD),
        _qs(f'{poss:.1f}%','Possession',HOME_COLOR),
        _qs(f'{ppda}',     'PPDA',      AWAY_COLOR),
    ], style={'display': 'flex', 'gap': '10px', 'flex': '2', 'minWidth': '0'})

    return html.Div(
        html.Div([left, center, right],
                 style={'display': 'flex', 'alignItems': 'center', 'gap': '24px'}),
        style={
            'background': 'linear-gradient(135deg, rgba(26,29,46,0.95) 0%, rgba(42,47,74,0.98) 100%)',
            'border':     f'1px solid {COLORS["dark_border"]}',
            'borderLeft': f'4px solid {GOLD}',
            'borderRadius': '10px',
            'padding': '20px 24px',
            'marginBottom': '14px',
        },
    )


def _stat_pill(val: str, label: str, color: str = COLORS['text_primary']) -> html.Div:
    return html.Div([
        html.Div(val, style={
            'fontWeight': '800', 'fontSize': '1.35rem',
            'color': color, 'lineHeight': '1',
        }),
        html.Div(label, style={
            'color': COLORS['text_secondary'], 'fontSize': '0.55rem',
            'fontWeight': '700', 'letterSpacing': '0.5px',
            'textTransform': 'uppercase', 'marginTop': '3px',
        }),
    ], style={
        'backgroundColor': COLORS['dark_secondary'],
        'border': f'1px solid {COLORS["dark_border"]}',
        'borderRadius': '8px',
        'padding': '10px 16px',
        'flex': '1', 'minWidth': '0',
        'textAlign': 'center',
    })


# ─── Computation helpers ──────────────────────────────────────────────────────

def _safe_pct(num: float, den: float, decimals: int = 1) -> str:
    return '—' if den == 0 else f'{num / den * 100:.{decimals}f}%'


def _safe_round(val: float, n: int = 1) -> str:
    try:
        return f'{round(val, n)}'
    except Exception:
        return '—'


def _compute_phases(bar: pd.DataFrame, opp: pd.DataFrame,
                    results: list[dict],
                    events: pd.DataFrame) -> tuple[dict, dict]:
    """
    Return (scores, metrics) for the five deep-dive phases.
    scores  : phase_name → float [0, 100]
    metrics : phase_name → list of (label, value_str, color)
    """
    n_matches = max(len(results), 1)

    # ── Build-up ──────────────────────────────────────────────────────────────
    bar_passes = bar[bar['event_type'] == 'Pass'] if not bar.empty else pd.DataFrame()
    all_passes = events[events['event_type'] == 'Pass'] if not events.empty else pd.DataFrame()

    poss_pct  = len(bar_passes) / max(len(all_passes), 1) * 100
    pass_acc  = (bar_passes['outcome'].eq(1).sum() / max(len(bar_passes), 1) * 100
                 if not bar_passes.empty else 0.0)

    if 'Pass End X' in bar_passes.columns and not bar_passes.empty:
        _ex   = pd.to_numeric(bar_passes['Pass End X'], errors='coerce')
        _sx   = pd.to_numeric(bar_passes['x'],          errors='coerce')
        prog  = int((bar_passes['outcome'].eq(1) & ((_ex - _sx) >= 25)).sum())
    else:
        prog  = int(len(bar_passes) * 0.15)

    buildup_score = round(poss_pct, 1)   # possession is naturally 0-100

    # ── Chance Creation ───────────────────────────────────────────────────────
    shot_types = ['Goal', 'Saved Shot', 'Miss', 'Post', 'Blocked Shot']
    bar_shots  = (exclude_own_goals(bar[bar['event_type'].isin(shot_types)].copy())
                  if not bar.empty else pd.DataFrame())
    n_goals    = int((bar_shots['event_type'] == 'Goal').sum()) if not bar_shots.empty else 0
    n_sot      = int(bar_shots['event_type'].isin(['Goal', 'Saved Shot']).sum()) if not bar_shots.empty else 0
    n_shots    = len(bar_shots)
    sot_pct    = n_sot / max(n_shots, 1) * 100

    # Score: goals/match scaled (3 goals/match → 100)
    goals_pm      = n_goals / n_matches
    chance_score  = min(round(goals_pm / 3.0 * 100, 1), 100)
    if chance_score < 5 and n_shots > 0:           # fallback for low-scoring samples
        chance_score = min(round(sot_pct * 1.3, 1), 100)

    # ── Transitions ───────────────────────────────────────────────────────────
    gains     = (bar[bar['event_type'].isin(['Ball Recovery', 'Interception'])]
                 if not bar.empty else pd.DataFrame())
    opp_gains = (gains[gains['x'].notna() & (gains['x'] >= 50)]
                 if not gains.empty else pd.DataFrame())
    trans_score = round(len(opp_gains) / max(len(gains), 1) * 100, 1) if not gains.empty else 50.0
    n_conceded  = sum(r.get('opponent_goals', 0) for r in results)

    # ── Defensive Structure ───────────────────────────────────────────────────
    opp_shots = (opp[opp['event_type'].isin(['Goal', 'Saved Shot', 'Miss'])]
                 if not opp.empty else pd.DataFrame())
    opp_s_pm  = len(opp_shots) / n_matches
    ga_pm     = n_conceded / n_matches
    cs        = sum(1 for r in results if r.get('opponent_goals', 1) == 0)
    # Score: 100 − GA/match × 25  →  0 GA/match = 100, 4 GA/match = 0
    def_score = max(0.0, min(100.0, round(100 - ga_pm * 25, 1)))

    # ── Set Pieces ────────────────────────────────────────────────────────────
    if not bar.empty:
        fk_passes = (bar[(bar['event_type'] == 'Pass') & (bar['Free kick taken'] == 'Si')]
                     if 'Free kick taken' in bar.columns else bar.head(0))
        corner_passes = (bar[(bar['event_type'] == 'Pass') & (bar['Corner taken'] == 'Si')]
                         if 'Corner taken' in bar.columns else bar.head(0))
        pen_shots = (bar[
            bar['event_type'].isin(['Goal', 'Miss', 'Post', 'Saved Shot']) &
            (bar['Penalty'] == 'Si')
        ] if 'Penalty' in bar.columns else bar.head(0))
        sp_all   = pd.concat([fk_passes, corner_passes], ignore_index=True)
        sp_conn  = sp_all[sp_all['outcome'] == 1] if not sp_all.empty and 'outcome' in sp_all.columns else pd.DataFrame()
        sp_score = round(len(sp_conn) / max(len(sp_all), 1) * 100, 1) if not sp_all.empty else 50.0
    else:
        fk_passes = corner_passes = pen_shots = sp_all = sp_conn = pd.DataFrame()
        sp_score  = 50.0

    # ── Assemble outputs ──────────────────────────────────────────────────────
    scores = {
        'Build-up':        buildup_score,
        'Chance Creation': chance_score,
        'Transitions':     trans_score,
        'Def. Structure':  def_score,
        'Set Pieces':      sp_score,
    }

    metrics = {
        'Build-up': [
            ('Possession',      f'{poss_pct:.1f}%',                               HOME_COLOR),
            ('Pass Accuracy',   f'{pass_acc:.1f}%',                               GOLD),
            ('Prog. Passes',    f'{prog} ({_safe_round(prog / n_matches, 1)}/m)',  HOME_COLOR),
        ],
        'Chance Creation': [
            ('Goals Scored',    str(n_goals),                                      GOLD),
            ('Shots on Target', f'{n_sot} ({sot_pct:.0f}%)',                       HOME_COLOR),
            ('Shots/Match',     _safe_round(n_shots / n_matches, 1),              HOME_COLOR),
        ],
        'Transitions': [
            ('Ball Gains/Match', _safe_round(len(gains) / n_matches, 1),           '#51cf66'),
            ('Opp-Half Gains',  f'{len(opp_gains)} ({round(len(opp_gains)/max(len(gains),1)*100):.0f}%)', '#51cf66'),
            ('Goals Conceded',  str(n_conceded),                                   AWAY_COLOR),
        ],
        'Def. Structure': [
            ('Shots Conc/Match', _safe_round(opp_s_pm, 1),                        '#5c7cfa'),
            ('Goals Conc/Match', _safe_round(ga_pm, 2),                           AWAY_COLOR),
            ('Clean Sheets',    f'{cs} / {n_matches}',                             GOLD),
        ],
        'Set Pieces': [
            ('Corners Taken',   str(len(corner_passes)),                           '#cc5de8'),
            ('FK Passes',       str(len(fk_passes)),                              '#cc5de8'),
            ('Penalties Taken', str(len(pen_shots)),                               GOLD),
        ],
    }

    return scores, metrics


# ─── Chart helpers ────────────────────────────────────────────────────────────

def _radar_fig(scores: dict) -> go.Figure:
    if not scores:
        return empty_fig('No phase data')
    categories  = list(scores.keys())
    values      = [round(scores[c], 1) for c in categories]
    cats_closed = categories + [categories[0]]
    vals_closed = values     + [values[0]]

    fig = go.Figure()
    fig.add_trace(go.Scatterpolar(
        r=vals_closed,
        theta=cats_closed,
        fill='toself',
        name='Barça',
        line=dict(color=GOLD, width=2.5),
        fillcolor='rgba(161,120,40,0.22)',
        hovertemplate='%{theta}: %{r:.1f}<extra></extra>',
    ))
    fig.update_layout(**layout_config(
        height=340,
        polar=dict(
            bgcolor='rgba(0,0,0,0)',
            radialaxis=dict(
                visible=True, range=[0, 100],
                color=COLORS['text_secondary'],
                gridcolor='rgba(255,255,255,0.10)',
                tickfont=dict(size=8),
            ),
            angularaxis=dict(
                color=COLORS['text_secondary'],
                gridcolor='rgba(255,255,255,0.10)',
                tickfont=dict(size=10, color='white'),
            ),
        ),
        showlegend=False,
        margin=dict(l=30, r=30, t=20, b=20),
    ))
    return fig


def _rolling_trend(results: list[dict], events: pd.DataFrame, window: int = 5) -> go.Figure:
    """Rolling possession / shots / PPDA across the season."""
    sorted_r = sorted(results, key=lambda r: r['date'])
    if not sorted_r or events.empty:
        return empty_fig('No trend data')

    labels, poss_vals, shot_vals, ppda_vals = [], [], [], []
    for r in sorted_r:
        me = (events[events['match_id'] == r['match_id']]
              if 'match_id' in events.columns else events.head(0))
        if me.empty:
            continue
        bar_ev = me[me['team_code'] == 'BAR']
        opp_ev = me[me['team_code'] != 'BAR']

        bar_p = len(bar_ev[bar_ev['event_type'] == 'Pass'])
        all_p = len(me[me['event_type'] == 'Pass'])
        poss_vals.append(round(bar_p / max(all_p, 1) * 100, 1))

        shot_vals.append(int(bar_ev[bar_ev['event_type'].isin(['Goal', 'Saved Shot', 'Miss'])].shape[0]))

        opp_dp  = opp_ev[(opp_ev['event_type'] == 'Pass') &
                          opp_ev['x'].notna() & (opp_ev['x'] < 40)]
        bar_pr  = bar_ev[bar_ev['event_type'].isin(['Tackle', 'Interception']) &
                          bar_ev['x'].notna() & (bar_ev['x'] > 50)]
        ppda_vals.append(round(len(opp_dp) / max(len(bar_pr), 1), 1))

        comp = _COMP_SHORT.get(r['competition'], r['competition'][:4])
        labels.append(f"{r['opponent']} · {comp}")

    if len(poss_vals) < 2:
        return empty_fig('Not enough matches for trend')

    x = list(range(1, len(poss_vals) + 1))

    def _roll(vals, w):
        return [
            round(sum(vals[max(0, i - w + 1):i + 1]) /
                  len(vals[max(0, i - w + 1):i + 1]), 1)
            for i in range(len(vals))
        ]

    r_poss = _roll(poss_vals, window)
    r_shot = _roll(shot_vals, window)
    r_ppda = _roll(ppda_vals, window)

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=x, y=r_poss, name=f'Possession % (roll.{window})',
        line=dict(color=HOME_COLOR, width=2.2),
        text=labels, hovertemplate='Match %{x}: %{text}<br>Poss: %{y}%<extra></extra>',
    ))
    fig.add_trace(go.Scatter(
        x=x, y=r_ppda, name=f'PPDA (roll.{window})',
        line=dict(color=AWAY_COLOR, width=2.2, dash='dot'),
        text=labels, hovertemplate='Match %{x}: %{text}<br>PPDA: %{y}<extra></extra>',
        yaxis='y2',
    ))
    fig.add_trace(go.Bar(
        x=x, y=r_shot, name=f'Shots (roll.{window})',
        marker_color='rgba(161,120,40,0.35)',
        text=labels, hovertemplate='Match %{x}: %{text}<br>Shots: %{y}<extra></extra>',
        yaxis='y3',
    ))
    fig.update_layout(**layout_config(
        height=320,
        xaxis=dict(title='Match #', gridcolor='rgba(255,255,255,0.05)', tickfont=dict(size=9)),
        yaxis=dict(title='Possession %', side='left', range=[0, 100],
                   gridcolor='rgba(255,255,255,0.05)', tickfont=dict(size=9)),
        yaxis2=dict(title='PPDA', overlaying='y', side='right',
                    showgrid=False, range=[0, 25], tickfont=dict(size=9)),
        yaxis3=dict(overlaying='y', side='right', showgrid=False,
                    range=[0, 18], visible=False),
        barmode='overlay',
        legend=dict(orientation='h', y=1.08, x=0.5, xanchor='center',
                    font=dict(size=9), bgcolor='rgba(0,0,0,0)'),
        margin=dict(l=40, r=50, t=30, b=30),
    ))
    return fig


def _comparison_fig(bar: pd.DataFrame, opp: pd.DataFrame, results: list) -> go.Figure:
    """Horizontal grouped bars: Barcelona vs Opponents per-match averages."""
    n   = max(len(results), 1)
    bp  = bar[bar['event_type'] == 'Pass']
    op  = opp[opp['event_type'] == 'Pass']
    st  = ['Goal', 'Saved Shot', 'Miss']
    bs  = bar[bar['event_type'].isin(st)]
    os_ = opp[opp['event_type'].isin(st)]
    bd  = bar[bar['event_type'].isin(['Tackle', 'Interception', 'Clearance'])]
    od  = opp[opp['event_type'].isin(['Tackle', 'Interception', 'Clearance'])]
    bg  = filter_own_goals(bar[bar['event_type'] == 'Goal'].copy())
    og  = exclude_own_goals(opp[opp['event_type'] == 'Goal'].copy())

    metrics  = ['Goals/Match', 'Def. Actions/Match', 'Shots/Match', 'Passes/Match']
    bar_vals = [round(len(bg)/n, 2), round(len(bd)/n, 1),
                round(len(bs)/n, 1), round(len(bp)/n, 1)]
    opp_vals = [round(len(og)/n, 2), round(len(od)/n, 1),
                round(len(os_)/n, 1), round(len(op)/n, 1)]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        name='Barcelona', y=metrics, x=bar_vals,
        orientation='h', marker_color=GOLD,
        hovertemplate='%{y}: <b>%{x}</b><extra>Barcelona</extra>',
    ))
    fig.add_trace(go.Bar(
        name='Opponents', y=metrics, x=opp_vals,
        orientation='h', marker_color='rgba(255,255,255,0.20)',
        hovertemplate='%{y}: <b>%{x}</b><extra>Opponents</extra>',
    ))
    fig.update_layout(**layout_config(
        height=260,
        barmode='group',
        xaxis=dict(title='Per Match', gridcolor='rgba(255,255,255,0.05)',
                   tickfont=dict(size=9)),
        yaxis=dict(tickfont=dict(size=9)),
        legend=dict(orientation='h', y=1.08, x=0.5, xanchor='center',
                    font=dict(size=9), bgcolor='rgba(0,0,0,0)'),
        margin=dict(l=10, r=20, t=30, b=30),
    ))
    return fig


# ─── Public builder ───────────────────────────────────────────────────────────

def build_overview_tab(season: str, competitions: list | None, match_ids: list | None):
    """
    Build and return the Overview tab layout.
    Signature matches all other tab builders for uniform dispatch in team_analysis.py.
    """
    # ── Data fetching & filtering ─────────────────────────────────────────────
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
        return html.P(
            'No data for the selected filters.',
            style={'color': COLORS['text_secondary'], 'padding': '2rem 0'},
        )

    events = get_all_events(season)
    if not events.empty:
        if competitions and 'competition' in events.columns:
            events = events[events['competition'].isin(competitions)]
        if match_ids:
            events = events[events['match_id'].isin(match_ids)]

    bar = events[events['team_code'] == 'BAR'] if not events.empty else pd.DataFrame()
    opp = events[events['team_code'] != 'BAR'] if not events.empty else pd.DataFrame()

    # ── Season headline numbers ───────────────────────────────────────────────
    n_matches = len(results)
    wins  = sum(1 for r in results if r['result'] == 'W')
    draws = sum(1 for r in results if r['result'] == 'D')
    loss  = sum(1 for r in results if r['result'] == 'L')
    pts   = wins * 3 + draws
    ppg   = round(pts / max(n_matches, 1), 2)
    gf    = sum(r['barca_goals']    for r in results)
    ga    = sum(r['opponent_goals'] for r in results)
    cs    = sum(1 for r in results if r['opponent_goals'] == 0)

    bar_passes = bar[bar['event_type'] == 'Pass'] if not bar.empty else pd.DataFrame()
    all_passes = events[events['event_type'] == 'Pass'] if not events.empty else pd.DataFrame()
    poss       = round(len(bar_passes) / max(len(all_passes), 1) * 100, 1)

    opp_dp = (opp[(opp['event_type'] == 'Pass') & opp['x'].notna() & (opp['x'] < 40)]
              if not opp.empty else pd.DataFrame())
    bar_pr = (bar[bar['event_type'].isin(['Tackle', 'Interception']) &
                  bar['x'].notna() & (bar['x'] > 50)]
              if not bar.empty else pd.DataFrame())
    ppda   = round(len(opp_dp) / max(len(bar_pr), 1), 1)

    pass_acc = (round(bar_passes['outcome'].eq(1).sum() / max(len(bar_passes), 1) * 100, 1)
                if not bar_passes.empty else 0.0)

    # ── Phase scores + metrics ────────────────────────────────────────────────
    scores, phase_metrics = (
        _compute_phases(bar, opp, results, events)
        if not bar.empty
        else ({k: 50.0 for k in _PHASE_COLORS}, {})
    )

    # ── Layout assembly ───────────────────────────────────────────────────────

    def _sec(text: str) -> html.Div:
        return html.Div(text, style={
            'color': GOLD, 'fontWeight': '700', 'fontSize': '0.72rem',
            'letterSpacing': '1px', 'textTransform': 'uppercase',
            'paddingBottom': '10px',
            'borderBottom': f'1px solid {COLORS["dark_border"]}',
            'marginBottom': '12px',
        })

    # Row 1: Season snapshot banner
    banner = _season_banner(results, wins, draws, loss, pts, ppg, poss, ppda, gf, ga)

    # Row 2: Stat pills (GF · GA · CS · Matches · Pass Acc)
    stat_pills = html.Div([
        _stat_pill(str(gf),           'Goals For',      GOLD),
        _stat_pill(str(ga),           'Goals Against',  AWAY_COLOR),
        _stat_pill(str(cs),           'Clean Sheets',   HOME_COLOR),
        _stat_pill(f'{pass_acc:.1f}%','Pass Accuracy',  GOLD),
        _stat_pill(str(n_matches),    'Matches',        COLORS['text_secondary']),
    ], style={'display': 'flex', 'gap': '8px', 'marginBottom': '14px'})

    # Row 3: Phase cards strip
    phase_strip = dbc.Row([
        dbc.Col(
            _phase_card(
                title   = phase,
                tab     = _PHASE_TAB[phase],
                score   = scores.get(phase, 50.0),
                color   = _PHASE_COLORS[phase],
                metrics = phase_metrics.get(phase, []),
            ),
            md=True,
            style={'display': 'flex', 'flexDirection': 'column'},
        )
        for phase in _PHASE_COLORS
    ], className='mb-3 g-2', align='stretch')

    # Row 4: Radar (md=4) + Rolling form (md=8)
    radar_card = html.Div([
        _sec('Game Model Radar'),
        dcc.Graph(figure=_radar_fig(scores), config=CHART_CONFIG),
    ], style=_CARD)

    trend_card = html.Div([
        _sec(f'Rolling {5}-Match Form  ·  Possession · PPDA · Shots'),
        dcc.Graph(figure=_rolling_trend(results, events), config=CHART_CONFIG),
    ], style=_CARD)

    # Row 5: Barcelona vs Opponents
    comp_card = html.Div([
        _sec('Barcelona vs Opponents — Per-Match Averages'),
        dcc.Graph(figure=_comparison_fig(bar, opp, results), config=CHART_CONFIG),
    ], style=_CARD)

    return html.Div([
        banner,
        stat_pills,
        phase_strip,
        dbc.Row([
            dbc.Col(radar_card, md=4),
            dbc.Col(trend_card, md=8),
        ], className='mb-3 g-2'),
        dbc.Row([
            dbc.Col(comp_card, md=12),
        ], className='mb-3 g-2'),
    ])
