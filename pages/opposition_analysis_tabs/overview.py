"""
Opposition Analysis — Tab 1: Overview

Season-level dashboard for the selected opposition team.

Layout (top → bottom):
  1. Season banner   — W/D/L record, GD, form strip, key KPIs
  2. Stat pills row  — GF · GA · CS · Matches · Pass Acc · Possession
  3. Phase cards     — Build-up · Chance Creation · Transitions · Def. Structure · Set Pieces
  4. Rolling form sparkline + per-match bar comparison
"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
from dash import html, dcc
import dash_bootstrap_components as dbc

from utils.config import COLORS
from page_utils.visualizations import (
    CHART_CONFIG,
    empty_fig,
    GOLD,
    HOME_COLOR,
    AWAY_COLOR,
)
from page_utils.event_filters import SHOT_TYPES as _SHOT_TYPES


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


def _phase_card(title: str, score: float, color: str,
                metrics: list[tuple[str, str, str]]) -> html.Div:
    return html.Div([
        html.Div(style={
            'height': '3px', 'backgroundColor': color,
            'borderRadius': '6px 6px 0 0',
            'margin': '-16px -16px 14px -16px',
        }),
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
    ], style={**_CARD, 'padding': '16px'})


def _form_strip(results: list[dict], n: int = 10) -> html.Div:
    recent = sorted(results, key=lambda r: str(r.get('date', '')))[-n:]
    return html.Div([
        html.Span(
            r.get('result', '?'),
            title=f"{r.get('opponent', '')} ({r.get('competition', '')})",
            style={
                'backgroundColor': _RESULT_BG.get(r.get('result', '?'), '#444'),
                'color':           _RESULT_TEXT.get(r.get('result', '?'), 'white'),
                'fontWeight': '800', 'fontSize': '0.62rem',
                'padding': '3px 8px', 'borderRadius': '4px',
                'letterSpacing': '0.5px', 'display': 'inline-block',
                'cursor': 'default',
            },
        )
        for r in recent
    ], style={'display': 'flex', 'gap': '4px', 'flexWrap': 'wrap'})


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
        'borderRadius': '8px', 'padding': '10px 16px',
        'flex': '1', 'minWidth': '0', 'textAlign': 'center',
    })


# ─── Computation helpers ──────────────────────────────────────────────────────

def _safe_round(val: float, n: int = 1) -> str:
    try:
        return f'{round(val, n)}'
    except Exception:
        return '—'


def _compute_phases(opp_ev: pd.DataFrame, bar_ev: pd.DataFrame,
                    results: list[dict]) -> tuple[dict, dict]:
    """Return (scores, metrics) for the five tactical phases.

    Calculations are aligned with the corresponding tab:
      Build-up        → buildup_attack.py  (pass map + shot map)
      Chance Creation → buildup_attack.py  (shot map)
      Transitions     → transitions.py     (attacking / defensive transition)
      Def. Structure  → defence.py
      Set Pieces      → set_pieces.py
    """
    n_matches = max(len(results), 1)

    # ── Build-up (aligns with pass map tab) ───────────────────────────────────
    opp_passes = opp_ev[opp_ev['event_type'] == 'Pass'] if not opp_ev.empty else pd.DataFrame()
    bar_passes = bar_ev[bar_ev['event_type'] == 'Pass'] if not bar_ev.empty else pd.DataFrame()
    total_pass_n = len(opp_passes) + len(bar_passes)

    poss_pct = round(len(opp_passes) / max(total_pass_n, 1) * 100, 1)
    pass_acc = (round(opp_passes['outcome'].eq(1).sum() / max(len(opp_passes), 1) * 100, 1)
                if not opp_passes.empty and 'outcome' in opp_passes.columns else 0.0)

    if not opp_passes.empty and 'Pass End X' in opp_passes.columns:
        _ex  = pd.to_numeric(opp_passes['Pass End X'], errors='coerce')
        _sx  = pd.to_numeric(opp_passes['x'],          errors='coerce')
        prog = int((opp_passes['outcome'].eq(1) & ((_ex - _sx) >= 25)).sum())
    else:
        prog = int(len(opp_passes) * 0.15)

    buildup_score = poss_pct

    # ── Chance Creation (aligns with shot map tab) ────────────────────────────
    opp_shots = opp_ev[opp_ev['event_type'].isin(_SHOT_TYPES)] if not opp_ev.empty else pd.DataFrame()
    n_goals = int((opp_shots['event_type'] == 'Goal').sum())   if not opp_shots.empty else 0
    n_sot   = int(opp_shots['event_type'].isin({'Goal', 'Saved Shot'}).sum()) if not opp_shots.empty else 0
    n_shots = len(opp_shots)
    sot_pct = n_sot / max(n_shots, 1) * 100

    goals_pm     = n_goals / n_matches
    chance_score = min(round(goals_pm / 3.0 * 100, 1), 100)
    if chance_score < 5 and n_shots > 0:
        chance_score = min(round(sot_pct * 1.3, 1), 100)

    # ── Transitions (aligns with transitions.py gain types) ───────────────────
    # Matches _ALL_GAIN_TYPES = ['Ball Recovery', 'Interception', 'Tackle Won']
    _GAIN_TYPES = {'Ball Recovery', 'Interception', 'Tackle Won'}
    gains     = opp_ev[opp_ev['event_type'].isin(_GAIN_TYPES)] if not opp_ev.empty else pd.DataFrame()
    opp_gains = gains[gains['x'].notna() & (gains['x'] >= 50)] if not gains.empty else pd.DataFrame()
    trans_score = round(len(opp_gains) / max(len(gains), 1) * 100, 1) if not gains.empty else 50.0

    # ── Defensive Structure (aligns with defence.py) ──────────────────────────
    # Opposition's defensive actions mirror _ALL_DEF_TYPES in defence.py
    _DEF_TYPES  = {'Tackle', 'Interception', 'Ball Recovery', 'Clearance', 'Blocked Shot'}
    opp_def     = opp_ev[opp_ev['event_type'].isin(_DEF_TYPES)] if not opp_ev.empty else pd.DataFrame()

    # Barcelona shots conceded by opponent (bar_ev shots)
    bar_shots  = (bar_ev[bar_ev['event_type'].isin({'Goal', 'Saved Shot', 'Miss', 'Post', 'Blocked Shot'})]
                  if not bar_ev.empty else pd.DataFrame())
    bar_s_pm   = len(bar_shots) / n_matches
    ga_pm      = sum(r.get('ga', 0) for r in results) / n_matches
    cs         = sum(1 for r in results if r.get('ga', 1) == 0)
    def_score  = max(0.0, min(100.0, round(100 - ga_pm * 25, 1)))

    # ── Set Pieces (aligns with set_pieces.py) ────────────────────────────────
    if not opp_ev.empty:
        fk_passes = (opp_ev[(opp_ev['event_type'] == 'Pass') & (opp_ev['Free kick taken'] == 'Si')]
                     if 'Free kick taken' in opp_ev.columns else pd.DataFrame())
        corner_passes = (opp_ev[(opp_ev['event_type'] == 'Pass') & (opp_ev['Corner taken'] == 'Si')]
                         if 'Corner taken' in opp_ev.columns else pd.DataFrame())
        sp_all   = pd.concat([fk_passes, corner_passes], ignore_index=True)
        sp_conn  = (sp_all[sp_all['outcome'] == 1]
                    if not sp_all.empty and 'outcome' in sp_all.columns
                    else pd.DataFrame())
        sp_score = round(len(sp_conn) / max(len(sp_all), 1) * 100, 1) if not sp_all.empty else 50.0
    else:
        fk_passes = corner_passes = sp_all = pd.DataFrame()
        sp_score  = 50.0

    scores = {
        'Build-up':        buildup_score,
        'Chance Creation': chance_score,
        'Transitions':     trans_score,
        'Def. Structure':  def_score,
        'Set Pieces':      sp_score,
    }
    metrics = {
        'Build-up': [
            ('Possession',     f'{poss_pct:.1f}%',                                HOME_COLOR),
            ('Pass Accuracy',  f'{pass_acc:.1f}%',                                GOLD),
            ('Prog. Passes',   f'{prog} ({_safe_round(prog / n_matches, 1)}/m)',  HOME_COLOR),
        ],
        'Chance Creation': [
            ('Goals Scored',    str(n_goals),                                      GOLD),
            ('Shots on Target', f'{n_sot} ({sot_pct:.0f}%)',                       HOME_COLOR),
            ('Shots/Match',     _safe_round(n_shots / n_matches, 1),               HOME_COLOR),
        ],
        'Transitions': [
            ('Ball Gains/Match', _safe_round(len(gains) / n_matches, 1),           '#51cf66'),
            ('Opp-Half Gains',   f'{len(opp_gains)} ({round(len(opp_gains) / max(len(gains), 1) * 100):.0f}%)',
                                 '#51cf66'),
            ('Goals Scored',     str(n_goals),                                     AWAY_COLOR),
        ],
        'Def. Structure': [
            ('Def. Actions',     str(len(opp_def)),                                '#5c7cfa'),
            ('Barca Shots/M',    _safe_round(bar_s_pm, 1),                         AWAY_COLOR),
            ('Clean Sheets',     f'{cs} / {n_matches}',                            GOLD),
        ],
        'Set Pieces': [
            ('Corners Taken',    str(len(corner_passes)),                          '#cc5de8'),
            ('FK Passes',        str(len(fk_passes)),                              '#cc5de8'),
            ('Set Piece Conn%',  f'{sp_score:.0f}%',                               GOLD),
        ],
    }
    return scores, metrics


# ─── Chart helpers ────────────────────────────────────────────────────────────

def _radar_fig(scores: dict) -> go.Figure:
    phases   = list(scores.keys())
    vals     = [scores[p] for p in phases]
    vals_c   = vals + [vals[0]]
    phases_c = phases + [phases[0]]

    fig = go.Figure(go.Scatterpolar(
        r=vals_c, theta=phases_c,
        fill='toself',
        fillcolor='rgba(0, 160, 220, 0.18)',
        line=dict(color=HOME_COLOR, width=2),
        marker=dict(color=HOME_COLOR, size=6),
        hovertemplate='%{theta}: %{r:.0f}/100<extra></extra>',
    ))
    fig.update_layout(
        polar=dict(
            bgcolor='rgba(21,25,50,0.6)',
            radialaxis=dict(range=[0, 100], showticklabels=False,
                            gridcolor='rgba(255,255,255,0.1)'),
            angularaxis=dict(tickfont=dict(color=COLORS['text_secondary'], size=10),
                             gridcolor='rgba(255,255,255,0.1)'),
        ),
        paper_bgcolor='rgba(0,0,0,0)',
        showlegend=False,
        height=280,
        margin=dict(l=50, r=50, t=20, b=20),
    )
    return fig


def _rolling_form_fig(results: list[dict], window: int = 5) -> go.Figure:
    sorted_r = sorted(results, key=lambda r: str(r.get('date', '')))
    pts_map  = {'W': 3, 'D': 1, 'L': 0}
    pts_vals = [pts_map.get(r.get('result', 'L'), 0) for r in sorted_r]
    dates    = [str(r.get('date', ''))[:10] for r in sorted_r]

    rolling = []
    for i in range(len(pts_vals)):
        lo = max(0, i - window + 1)
        rolling.append(sum(pts_vals[lo:i+1]) / (i - lo + 1))

    colors = [_RESULT_BG.get(r.get('result', 'L'), '#888') for r in sorted_r]

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=dates, y=rolling, mode='lines+markers',
        line=dict(color=HOME_COLOR, width=2),
        marker=dict(color=colors, size=8, line=dict(color='white', width=1)),
        hovertemplate='%{x}: %{y:.2f} pts avg<extra></extra>',
    ))
    fig.add_hline(y=1.0, line=dict(color=GOLD, dash='dot', width=1), opacity=0.4)
    fig.update_layout(
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(21,25,50,0.6)',
        height=280, margin=dict(l=30, r=10, t=10, b=40),
        xaxis=dict(showgrid=False, tickfont=dict(size=8, color=COLORS['text_secondary'])),
        yaxis=dict(showgrid=True, gridcolor='rgba(255,255,255,0.06)',
                   tickfont=dict(size=9, color=COLORS['text_secondary']),
                   range=[0, 3.2], title='Pts avg'),
        showlegend=False,
    )
    return fig


def _per_match_bar_fig(results: list[dict]) -> go.Figure:
    sorted_r = sorted(results, key=lambda r: str(r.get('date', '')))[-10:]
    labels   = [f"{r.get('opponent', '?')[:12]} ({r.get('result', '?')})" for r in sorted_r]
    gf_vals  = [r.get('gf', 0) for r in sorted_r]
    ga_vals  = [r.get('ga', 0) for r in sorted_r]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        y=labels, x=gf_vals, name='Goals For', orientation='h',
        marker=dict(color=HOME_COLOR), text=gf_vals,
        textposition='inside', textfont=dict(color='white', size=10),
        hovertemplate='GF: %{x}<extra></extra>',
    ))
    fig.add_trace(go.Bar(
        y=labels, x=[-g for g in ga_vals], name='Goals Against', orientation='h',
        marker=dict(color=AWAY_COLOR), text=ga_vals,
        textposition='inside', textfont=dict(color='white', size=10),
        hovertemplate='GA: %{x}<extra></extra>',
    ))
    fig.update_layout(
        barmode='relative',
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(21,25,50,0.6)',
        height=max(180, len(sorted_r) * 28),
        margin=dict(l=10, r=10, t=10, b=10),
        xaxis=dict(showgrid=False, zeroline=True,
                   zerolinecolor='rgba(255,255,255,0.2)',
                   showticklabels=False, fixedrange=True),
        yaxis=dict(showgrid=False, tickfont=dict(size=9, color=COLORS['text_secondary'])),
        legend=dict(orientation='h', y=1.05, font=dict(color=COLORS['text_secondary'], size=9)),
    )
    return fig


# ─── Public builder ───────────────────────────────────────────────────────────

def build_overview(team: str, country: str, comp_key: str,
                   all_results: list[dict], opp_ev: pd.DataFrame,
                   bar_ev: pd.DataFrame, n_matches: int) -> html.Div:
    """Build the Overview tab. Called synchronously from opposition_analysis.py."""
    if not all_results and opp_ev.empty:
        return html.P("No data available for this selection.",
                      style={'color': COLORS['text_secondary'], 'padding': '2rem 0'})

    wins  = sum(1 for r in all_results if r.get('result') == 'W')
    draws = sum(1 for r in all_results if r.get('result') == 'D')
    loss  = sum(1 for r in all_results if r.get('result') == 'L')
    gf    = sum(r.get('gf', 0) for r in all_results)
    ga    = sum(r.get('ga', 0) for r in all_results)
    cs    = sum(1 for r in all_results if r.get('ga', 1) == 0)
    pts   = wins * 3 + draws
    ppg   = round(pts / max(n_matches, 1), 2)

    # Possession — pass share across both teams (mirrors build-up tab logic)
    opp_pass_n = int((opp_ev['event_type'] == 'Pass').sum()) if not opp_ev.empty else 0
    bar_pass_n = int((bar_ev['event_type'] == 'Pass').sum()) if not bar_ev.empty else 0
    poss_pct   = round(opp_pass_n / max(opp_pass_n + bar_pass_n, 1) * 100, 1)

    pass_acc = 0.0
    if not opp_ev.empty and 'event_type' in opp_ev.columns:
        opp_passes = opp_ev[opp_ev['event_type'] == 'Pass']
        if not opp_passes.empty and 'outcome' in opp_passes.columns:
            pass_acc = round(opp_passes['outcome'].eq(1).sum() / max(len(opp_passes), 1) * 100, 1)

    gd      = gf - ga
    gd_sign = '+' if gd >= 0 else ''
    gd_col  = GOLD if gd >= 0 else AWAY_COLOR

    # ── Season banner ─────────────────────────────────────────────────────────
    left = html.Div([
        html.Div([
            html.Span(f'{wins}', style={'color': '#22c55e', 'fontWeight': '900', 'fontSize': '1.8rem'}),
            html.Span('W  ', style={'color': COLORS['text_secondary'], 'fontSize': '0.9rem', 'fontWeight': '600', 'marginRight': '8px'}),
            html.Span(f'{draws}', style={'color': '#f59f00', 'fontWeight': '900', 'fontSize': '1.8rem'}),
            html.Span('D  ', style={'color': COLORS['text_secondary'], 'fontSize': '0.9rem', 'fontWeight': '600', 'marginRight': '8px'}),
            html.Span(f'{loss}', style={'color': '#ef4444', 'fontWeight': '900', 'fontSize': '1.8rem'}),
            html.Span('L', style={'color': COLORS['text_secondary'], 'fontSize': '0.9rem', 'fontWeight': '600'}),
        ], style={'lineHeight': '1.1', 'letterSpacing': '1px'}),
        html.Div(f'GD {gd_sign}{gd}', style={
            'color': gd_col, 'fontSize': '0.82rem',
            'fontWeight': '700', 'marginTop': '6px',
        }),
    ], style={'flex': '1', 'minWidth': '0'})

    center = html.Div([
        html.Div('LAST 10', style={
            'color': COLORS['text_secondary'], 'fontSize': '0.56rem',
            'fontWeight': '700', 'letterSpacing': '1.2px',
            'textTransform': 'uppercase', 'marginBottom': '8px',
        }),
        _form_strip(all_results, 10),
    ], style={'flex': '1.5', 'minWidth': '0', 'paddingLeft': '20px'})

    def _qs(val, label, color=COLORS['text_primary']):
        return html.Div([
            html.Div(str(val), style={'fontWeight': '800', 'fontSize': '1.3rem', 'color': color, 'lineHeight': '1.1'}),
            html.Div(label, style={'color': COLORS['text_secondary'], 'fontSize': '0.55rem', 'fontWeight': '700', 'letterSpacing': '0.5px', 'textTransform': 'uppercase', 'marginTop': '2px'}),
        ], style={'textAlign': 'center', 'flex': '1'})

    right = html.Div([
        _qs(pts,             'Points',    GOLD),
        _qs(f'{ppg:.2f}',    'Pts/Game',  GOLD),
        _qs(f'{poss_pct:.1f}%', 'Possession', HOME_COLOR),
        _qs(n_matches,       'Matches',   COLORS['text_primary']),
    ], style={'display': 'flex', 'gap': '10px', 'flex': '2', 'minWidth': '0'})

    banner = html.Div(
        html.Div([left, center, right],
                 style={'display': 'flex', 'alignItems': 'center', 'gap': '24px'}),
        style={
            'background': 'linear-gradient(135deg, rgba(26,29,46,0.95) 0%, rgba(42,47,74,0.98) 100%)',
            'border': f'1px solid {COLORS["dark_border"]}',
            'borderLeft': f'4px solid {GOLD}',
            'borderRadius': '10px', 'padding': '20px 24px', 'marginBottom': '14px',
        },
    )

    # ── Stat pills ────────────────────────────────────────────────────────────
    pills = html.Div([
        _stat_pill(str(gf),            'Goals For',    GOLD),
        _stat_pill(str(ga),            'Goals Against', AWAY_COLOR),
        _stat_pill(str(cs),            'Clean Sheets', HOME_COLOR),
        _stat_pill(str(n_matches),     'Matches',      COLORS['text_primary']),
        _stat_pill(f'{pass_acc:.1f}%', 'Pass Acc.',    HOME_COLOR),
        _stat_pill(f'{poss_pct:.1f}%', 'Possession',   GOLD),
    ], style={'display': 'flex', 'gap': '8px', 'flexWrap': 'wrap', 'marginBottom': '14px'})

    # ── Phase cards ───────────────────────────────────────────────────────────
    scores, metrics = _compute_phases(opp_ev, bar_ev, all_results)

    phase_cards = dbc.Row([
        dbc.Col(_phase_card(phase, scores[phase], _PHASE_COLORS[phase], metrics[phase]), md=True)
        for phase in scores
    ], className='g-2 mb-4')

    # ── Bottom row ────────────────────────────────────────────────────────────
    _hdr = {
        'color': GOLD, 'fontSize': '0.72rem', 'fontWeight': '700',
        'letterSpacing': '0.8px', 'textTransform': 'uppercase', 'marginBottom': '8px',
    }

    bottom_row = dbc.Row([
        dbc.Col(html.Div([
            dbc.Row([
                dbc.Col([
                    html.Div("Game Model Radar", style=_hdr),
                    dcc.Graph(figure=_radar_fig(scores), config=CHART_CONFIG,
                              style={'width': '100%'}),
                ], md=6),
                dbc.Col([
                    html.Div("Rolling Form (5-match avg)", style=_hdr),
                    dcc.Graph(figure=_rolling_form_fig(all_results), config=CHART_CONFIG,
                              style={'width': '100%'}),
                ], md=6),
            ], className='g-2'),
        ], style={
            'backgroundColor': COLORS['dark_secondary'],
            'border': f'1px solid {COLORS["dark_border"]}',
            'borderRadius': '8px', 'padding': '14px',
        }), md=7),

        dbc.Col(html.Div([
            html.Div("Last 10 Matches — GF vs GA", style=_hdr),
            dcc.Graph(figure=_per_match_bar_fig(all_results), config=CHART_CONFIG,
                      style={'width': '100%'}),
        ], style={
            'backgroundColor': COLORS['dark_secondary'],
            'border': f'1px solid {COLORS["dark_border"]}',
            'borderRadius': '8px', 'padding': '14px',
        }), md=5),
    ], className='g-3')

    return html.Div([banner, pills, phase_cards, bottom_row])
