"""
Opposition Analysis — Tab 1: Overview

Season-level dashboard for the selected opposition team. Mirrors the Home page
layout, scoped to a single opponent:

  1. Hero banner        — team identity (logo · name · country · competition),
                          season record (W-D-L · GD) and recent form strip
  2. Stat pills bar     — Matches · Points · PPG · GF · GA · CS · Poss · Pass Acc
  3. Competition cards  — per-competition breakdown (only when >1 competition)
  4. Charts row         — Game Model Radar + Last-10 GF vs GA
"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
from dash import html, dcc
import dash_bootstrap_components as dbc

from utils.config import COLORS
from utils.logos import (
    get_team_logo_path,
    get_country_flag_path,
    get_tournament_logo_path,
)
from page_utils.visualizations import (
    CHART_CONFIG,
    GOLD,
    HOME_COLOR,
    AWAY_COLOR,
)
from page_utils.event_filters import SHOT_TYPES as _SHOT_TYPES


# ─── Constants ────────────────────────────────────────────────────────────────

BARCA_FONT = "'Barcelona', 'Segoe UI', sans-serif"

_WIN_C  = '#28a745'
_DRAW_C = '#ffc107'
_LOSS_C = '#dc3545'
_GA_C   = '#A5A8B8'

_RESULT_C = {'W': _WIN_C, 'D': _DRAW_C, 'L': _LOSS_C}

# Opposition competition display name → Home-page tournament logo key.
_COMP_LOGO_KEY = {
    'Spain Primera Division': 'La Liga',
    'UEFA Champions League':  'Champions League',
    'Spain Copa del Rey':     'Copa del Rey',
    'Spain Supercopa':        'Spanish Super Cup',
}
# Nicer display labels where the raw key is clunky.
_COMP_DISPLAY = {
    'Spain Primera Division': 'La Liga',
    'UEFA Champions League':  'Champions League',
    'Spain Copa del Rey':     'Copa del Rey',
    'Spain Supercopa':        'Supercopa',
}


def _comp_display(name: str) -> str:
    return _COMP_DISPLAY.get(name, name)


def _comp_logo_path(name: str) -> str:
    return get_tournament_logo_path(_COMP_LOGO_KEY.get(name, name))


def _safe_round(val: float, n: int = 1) -> str:
    try:
        return f'{round(val, n)}'
    except Exception:
        return '—'


# ─── Reusable visual components ───────────────────────────────────────────────

def _stat_pill(value: str, label: str, color: str = COLORS['text_primary']) -> html.Div:
    """A single hero stat pill (reuses Home-page `.hero-stat-pill` styling)."""
    return html.Div([
        html.Div(str(value), className='hero-stat-value', style={'color': color}),
        html.Div(label, className='hero-stat-label'),
    ], className='hero-stat-pill')


def _recent_form(results: list[dict], n: int = 8) -> html.Div:
    """Recent-form strip: opponent crest + W/D/L badge + scoreline."""
    recent = sorted(results, key=lambda r: str(r.get('date', '')))[-n:]
    if not recent:
        return html.Div()

    badges = []
    for r in recent:
        res   = r.get('result', '?')
        color = _RESULT_C.get(res, _GA_C)
        opp   = r.get('opponent', '')
        score = f"{r.get('gf', 0)}-{r.get('ga', 0)}"
        logo  = get_team_logo_path(opp)

        crest = (html.Img(src=logo, title=opp,
                          style={'width': '20px', 'height': '20px',
                                 'objectFit': 'contain', 'marginBottom': '2px'})
                 if logo else
                 html.Div(opp[:3].upper(), title=opp,
                          style={'width': '20px', 'height': '20px', 'lineHeight': '20px',
                                 'textAlign': 'center', 'fontSize': '0.45rem', 'fontWeight': 700,
                                 'color': COLORS['text_secondary'], 'backgroundColor': COLORS['dark_bg'],
                                 'borderRadius': '50%', 'marginBottom': '2px'}))

        badges.append(html.Div([
            crest,
            html.Div(res, style={
                'backgroundColor': color,
                'color': 'black' if res == 'D' else 'white',
                'width': '20px', 'height': '20px', 'lineHeight': '20px',
                'textAlign': 'center', 'borderRadius': '3px',
                'fontWeight': 700, 'fontSize': '0.6rem', 'margin': '0 auto',
            }),
            html.Div(score, style={
                'fontSize': '0.58rem', 'color': COLORS['text_secondary'],
                'textAlign': 'center', 'marginTop': '1px',
            }),
        ], title=f"{opp} ({r.get('competition', '')})", style={
            'textAlign': 'center', 'width': '34px', 'flexShrink': '0',
            'display': 'flex', 'flexDirection': 'column', 'alignItems': 'center',
        }))

    return html.Div([
        html.Div('RECENT FORM', style={
            'fontSize': '0.6rem', 'color': COLORS['text_secondary'],
            'fontWeight': 700, 'letterSpacing': '1px', 'marginBottom': '6px',
        }),
        html.Div(badges, style={'display': 'flex', 'gap': '6px', 'flexWrap': 'wrap'}),
    ], style={'marginTop': '14px'})


def _competition_card(comp_name: str, results: list[dict]) -> dbc.Col:
    """Per-competition summary card (mirrors Home-page tournament card)."""
    wins  = sum(1 for r in results if r.get('result') == 'W')
    draws = sum(1 for r in results if r.get('result') == 'D')
    loss  = sum(1 for r in results if r.get('result') == 'L')
    gf    = sum(r.get('gf', 0) for r in results)
    ga    = sum(r.get('ga', 0) for r in results)
    played = max(len(results), 1)
    win_pct = round(wins / played * 100)

    logo = _comp_logo_path(comp_name)
    logo_circle = html.Div(
        html.Img(src=logo, className='tournament-logo') if logo else
        html.Span(_comp_display(comp_name)[:3].upper(),
                  style={'fontWeight': 800, 'color': COLORS['dark_bg'], 'fontSize': '1rem'}),
        className='tournament-logo-circle',
    )

    return dbc.Col(html.Div(dbc.CardBody([
        html.Div([
            logo_circle,
            html.H6(_comp_display(comp_name), className='mt-2 mb-1', style={
                'color': COLORS['text_primary'], 'fontWeight': 700,
                'fontSize': '0.95rem', 'fontFamily': BARCA_FONT,
            }),
        ], className='text-center mb-2'),

        html.Div([
            html.Span(f'W{wins}', className='tournament-record-item',
                      style={'color': '#fff', 'backgroundColor': _WIN_C}),
            html.Span(f'D{draws}', className='tournament-record-item',
                      style={'color': '#0A0E27', 'backgroundColor': _DRAW_C}),
            html.Span(f'L{loss}', className='tournament-record-item',
                      style={'color': '#fff', 'backgroundColor': _LOSS_C}),
        ], className='tournament-record justify-content-center'),

        html.Div([
            html.Span(str(gf), style={'fontWeight': 700, 'color': COLORS['gold']}),
            html.Span(' GF   ', style={'color': COLORS['text_secondary'], 'fontSize': '0.8rem'}),
            html.Span(str(ga), style={'fontWeight': 700, 'color': _GA_C}),
            html.Span(' GA', style={'color': COLORS['text_secondary'], 'fontSize': '0.8rem'}),
        ], className='text-center my-2', style={'fontSize': '0.9rem'}),

        html.Div(html.Div(style={'width': f'{win_pct}%'}, className='tournament-win-bar-fill'),
                 className='tournament-win-bar'),
        html.Div(f'{win_pct}% win rate · {len(results)} matches', className='tournament-expand-hint'),
    ]), className='tournament-card h-100'), lg=3, md=6, sm=12, className='mb-3')


# ─── Computation helpers ──────────────────────────────────────────────────────

def _phase_scores(opp_ev: pd.DataFrame, bar_ev: pd.DataFrame,
                  results: list[dict]) -> dict:
    """Return the five tactical-phase scores (0–100) used by the radar.

    Aligned with the corresponding analytical tabs:
      Build-up / Chance Creation → buildup + chance_creation tabs
      Transitions → transitions tab   Def. Structure → defence tab
      Set Pieces → set_pieces tab
    """
    n_matches = max(len(results), 1)

    opp_passes = opp_ev[opp_ev['event_type'] == 'Pass'] if not opp_ev.empty else pd.DataFrame()
    bar_passes = bar_ev[bar_ev['event_type'] == 'Pass'] if not bar_ev.empty else pd.DataFrame()
    total_pass_n = len(opp_passes) + len(bar_passes)
    buildup_score = round(len(opp_passes) / max(total_pass_n, 1) * 100, 1)

    opp_shots = opp_ev[opp_ev['event_type'].isin(_SHOT_TYPES)] if not opp_ev.empty else pd.DataFrame()
    n_goals = int((opp_shots['event_type'] == 'Goal').sum()) if not opp_shots.empty else 0
    n_sot   = int(opp_shots['event_type'].isin({'Goal', 'Saved Shot'}).sum()) if not opp_shots.empty else 0
    n_shots = len(opp_shots)
    sot_pct = n_sot / max(n_shots, 1) * 100
    goals_pm     = n_goals / n_matches
    chance_score = min(round(goals_pm / 3.0 * 100, 1), 100)
    if chance_score < 5 and n_shots > 0:
        chance_score = min(round(sot_pct * 1.3, 1), 100)

    _GAIN_TYPES = {'Ball Recovery', 'Interception', 'Tackle Won'}
    gains     = opp_ev[opp_ev['event_type'].isin(_GAIN_TYPES)] if not opp_ev.empty else pd.DataFrame()
    opp_gains = gains[gains['x'].notna() & (gains['x'] >= 50)] if not gains.empty else pd.DataFrame()
    trans_score = round(len(opp_gains) / max(len(gains), 1) * 100, 1) if not gains.empty else 50.0

    ga_pm     = sum(r.get('ga', 0) for r in results) / n_matches
    def_score = max(0.0, min(100.0, round(100 - ga_pm * 25, 1)))

    if not opp_ev.empty:
        fk = (opp_ev[(opp_ev['event_type'] == 'Pass') & (opp_ev['Free kick taken'] == 'Si')]
              if 'Free kick taken' in opp_ev.columns else pd.DataFrame())
        ck = (opp_ev[(opp_ev['event_type'] == 'Pass') & (opp_ev['Corner taken'] == 'Si')]
              if 'Corner taken' in opp_ev.columns else pd.DataFrame())
        sp_all  = pd.concat([fk, ck], ignore_index=True)
        sp_conn = (sp_all[sp_all['outcome'] == 1]
                   if not sp_all.empty and 'outcome' in sp_all.columns else pd.DataFrame())
        sp_score = round(len(sp_conn) / max(len(sp_all), 1) * 100, 1) if not sp_all.empty else 50.0
    else:
        sp_score = 50.0

    return {
        'Build-up':        buildup_score,
        'Chance Creation': chance_score,
        'Transitions':     trans_score,
        'Def. Structure':  def_score,
        'Set Pieces':      sp_score,
    }


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
        height=300,
        margin=dict(l=50, r=50, t=20, b=20),
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
        height=max(200, len(sorted_r) * 30),
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

    # ── Aggregates ────────────────────────────────────────────────────────────
    wins  = sum(1 for r in all_results if r.get('result') == 'W')
    draws = sum(1 for r in all_results if r.get('result') == 'D')
    loss  = sum(1 for r in all_results if r.get('result') == 'L')
    gf    = sum(r.get('gf', 0) for r in all_results)
    ga    = sum(r.get('ga', 0) for r in all_results)
    cs    = sum(1 for r in all_results if r.get('ga', 1) == 0)
    pts   = wins * 3 + draws
    ppg   = round(pts / max(n_matches, 1), 2)
    gd    = gf - ga
    gd_sign = '+' if gd >= 0 else ''
    gd_col  = _WIN_C if gd > 0 else (_DRAW_C if gd == 0 else _LOSS_C)

    opp_pass_n = int((opp_ev['event_type'] == 'Pass').sum()) if not opp_ev.empty else 0
    bar_pass_n = int((bar_ev['event_type'] == 'Pass').sum()) if not bar_ev.empty else 0
    poss_pct   = round(opp_pass_n / max(opp_pass_n + bar_pass_n, 1) * 100, 1)

    pass_acc = 0.0
    if not opp_ev.empty and 'event_type' in opp_ev.columns:
        opp_passes = opp_ev[opp_ev['event_type'] == 'Pass']
        if not opp_passes.empty and 'outcome' in opp_passes.columns:
            pass_acc = round(opp_passes['outcome'].eq(1).sum() / max(len(opp_passes), 1) * 100, 1)

    # ── Hero banner ───────────────────────────────────────────────────────────
    logo = get_team_logo_path(team)
    crest = (html.Img(src=logo, className='hero-logo', style={'height': '96px'})
             if logo else
             html.Div(team[:3].upper(), style={
                 'width': '96px', 'height': '96px', 'lineHeight': '96px',
                 'textAlign': 'center', 'fontWeight': 800, 'fontSize': '1.6rem',
                 'color': COLORS['gold'], 'backgroundColor': COLORS['dark_bg'],
                 'borderRadius': '50%'}))

    flag = get_country_flag_path(country)
    comp_label = 'All Competitions' if comp_key == 'all' else _comp_display(comp_key.replace('_', ' '))
    subtitle = html.Div([
        html.Img(src=flag, style={'height': '14px', 'marginRight': '7px',
                                  'borderRadius': '2px', 'objectFit': 'contain'}) if flag else html.Span(),
        html.Span(f'{country}  ·  {comp_label}  ·  2025–26', style={
            'color': COLORS['text_secondary'], 'fontSize': '0.85rem', 'letterSpacing': '0.4px',
        }),
    ], style={'display': 'flex', 'alignItems': 'center', 'marginTop': '4px'})

    identity = html.Div([
        crest,
        html.Div([
            html.H2(team, style={
                'fontFamily': BARCA_FONT, 'color': COLORS['text_primary'],
                'fontSize': '2rem', 'margin': 0, 'letterSpacing': '0.5px',
            }),
            subtitle,
        ], style={'marginLeft': '20px'}),
    ], style={'display': 'flex', 'alignItems': 'center', 'flex': '1', 'minWidth': '0'})

    record = html.Div([
        html.Div([
            html.Span(str(wins), style={'color': _WIN_C, 'fontWeight': 900, 'fontSize': '2rem'}),
            html.Span('W ', style={'color': COLORS['text_secondary'], 'fontSize': '0.85rem',
                                   'fontWeight': 600, 'marginRight': '10px'}),
            html.Span(str(draws), style={'color': _DRAW_C, 'fontWeight': 900, 'fontSize': '2rem'}),
            html.Span('D ', style={'color': COLORS['text_secondary'], 'fontSize': '0.85rem',
                                   'fontWeight': 600, 'marginRight': '10px'}),
            html.Span(str(loss), style={'color': _LOSS_C, 'fontWeight': 900, 'fontSize': '2rem'}),
            html.Span('L', style={'color': COLORS['text_secondary'], 'fontSize': '0.85rem',
                                  'fontWeight': 600}),
        ], style={'letterSpacing': '1px', 'lineHeight': '1.1', 'textAlign': 'right'}),
        html.Div(f'Goal Difference  {gd_sign}{gd}', style={
            'color': gd_col, 'fontSize': '0.82rem', 'fontWeight': 700,
            'marginTop': '8px', 'textAlign': 'right',
        }),
    ], style={'flexShrink': '0'})

    hero = html.Div([
        html.Div([identity, record], style={
            'display': 'flex', 'alignItems': 'center',
            'justifyContent': 'space-between', 'gap': '24px', 'flexWrap': 'wrap',
        }),
        _recent_form(all_results, 8),
    ], className='hero-section', style={'padding': '2rem 2.25rem'})

    # ── Stat pills ────────────────────────────────────────────────────────────
    pills = html.Div([
        _stat_pill(n_matches,           'Matches',       COLORS['gold']),
        _stat_pill(pts,                 'Points',        COLORS['gold']),
        _stat_pill(f'{ppg:.2f}',        'Pts / Game',    HOME_COLOR),
        _stat_pill(gf,                  'Goals For',     COLORS['gold']),
        _stat_pill(ga,                  'Goals Against', _GA_C),
        _stat_pill(f'{cs}',             'Clean Sheets',  HOME_COLOR),
        _stat_pill(f'{poss_pct:.1f}%',  'Possession',    COLORS['gold']),
        _stat_pill(f'{pass_acc:.1f}%',  'Pass Acc.',     HOME_COLOR),
    ], className='hero-stats-bar', style={'marginTop': 0, 'marginBottom': '1.75rem'})

    children = [hero, pills]

    # ── Competition breakdown (only when more than one competition) ───────────
    by_comp: dict[str, list[dict]] = {}
    for r in all_results:
        by_comp.setdefault(r.get('competition', '—'), []).append(r)

    if len(by_comp) > 1:
        comp_cards = [_competition_card(name, res)
                      for name, res in sorted(by_comp.items(), key=lambda kv: -len(kv[1]))]
        children.append(html.Div([
            html.H4('Competition Breakdown', className='section-header', style={'fontFamily': BARCA_FONT}),
            dbc.Row(comp_cards),
        ], className='mb-4'))

    # ── Charts row ────────────────────────────────────────────────────────────
    scores = _phase_scores(opp_ev, bar_ev, all_results)
    _hdr = {
        'color': COLORS['gold'], 'fontSize': '0.72rem', 'fontWeight': 700,
        'letterSpacing': '0.8px', 'textTransform': 'uppercase', 'marginBottom': '8px',
    }
    _panel = {
        'backgroundColor': COLORS['dark_secondary'],
        'border': f'1px solid {COLORS["dark_border"]}',
        'borderRadius': '12px', 'padding': '16px', 'height': '100%',
    }

    charts_row = dbc.Row([
        dbc.Col(html.Div([
            html.Div('Game Model Radar', style=_hdr),
            dcc.Graph(figure=_radar_fig(scores), config=CHART_CONFIG, style={'width': '100%'}),
        ], style=_panel), md=6, className='mb-3'),
        dbc.Col(html.Div([
            html.Div('Last 10 Matches — GF vs GA', style=_hdr),
            dcc.Graph(figure=_per_match_bar_fig(all_results), config=CHART_CONFIG, style={'width': '100%'}),
        ], style=_panel), md=6, className='mb-3'),
    ], className='g-3')

    children.append(charts_row)

    return html.Div(children)
