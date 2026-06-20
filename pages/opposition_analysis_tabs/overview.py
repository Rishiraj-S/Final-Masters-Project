"""
Opposition Analysis — Tab 1: Overview

Season-level dashboard for the selected opposition team. Mirrors the Home page
layout, scoped to a single opponent:

  1. Hero banner        — team identity (logo · name · country · competition),
                          season record (W-D-L · GD) and recent form strip
  2. Stat pills bar     — Matches · Points · PPG · GF · GA · CS · Poss · Pass Acc
  3. Competition cards  — per-competition breakdown (only when >1 competition)
  4. Phase cards        — one card per deep-dive tab with metrics + score bar
  5. Charts row         — Game Model Radar
  6. Season summary     — Game Model Radar + Form Trendline (tournament filter
                          & metric toggles) + Top Contributors
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import pandas as pd
import pyarrow.parquet as pq
import plotly.graph_objects as go
from dash import html, dcc
from dash.dependencies import Input, Output, State
from dash.exceptions import PreventUpdate
import dash_bootstrap_components as dbc

from utils.config import COLORS
from utils.logos import (
    get_team_logo_path,
    get_country_flag_path,
    get_tournament_logo_path,
)
from utils.opposition_data_utils import (
    competition_match_event_paths,
    load_opp_events,
    get_opp_team_matches,
    get_team_country,
    _opp_dir,
)
from page_utils.visualizations import (
    CHART_CONFIG,
    GOLD,
    HOME_COLOR,
    AWAY_COLOR,
)
from page_utils.event_filters import SHOT_TYPES as _SHOT_TYPES
from utils.event_utils import get_ball_gains


# ─── Constants ────────────────────────────────────────────────────────────────

BARCA_FONT = "'Barcelona', 'Segoe UI', sans-serif"

_WIN_C  = '#28a745'
_DRAW_C = '#ffc107'
_LOSS_C = '#dc3545'
_GA_C   = '#A5A8B8'

_RESULT_C = {'W': _WIN_C, 'D': _DRAW_C, 'L': _LOSS_C}

# Mirrors home.CHART_LAYOUT so the Form Trendline reads identically.
_CHART_LAYOUT = dict(
    paper_bgcolor='rgba(0,0,0,0)',
    plot_bgcolor='rgba(0,0,0,0)',
    font=dict(color='#E8E9ED', size=12),
    margin=dict(l=40, r=40, t=50, b=40),
)

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
    # `name` is a space-separated comp display (e.g. "England Premier League");
    # get_tournament_logo_path keys on the underscore folder form.
    return get_tournament_logo_path(name.replace(' ', '_'))


def _safe_round(val: float, n: int = 1) -> str:
    try:
        return f'{round(val, n)}'
    except Exception:
        return '—'


# ─── Phase cards (ported 1:1 from the Barça IQ overview) ──────────────────────

_CARD = {
    'backgroundColor': COLORS['dark_secondary'],
    'border':          f'1px solid {COLORS["dark_border"]}',
    'borderRadius':    '8px',
    'padding':         '16px',
    'height':          '100%',
}

_PHASE_COLORS = {
    'Build-up':         HOME_COLOR,
    'Chance Creation':  GOLD,
    'Transitions':      '#51cf66',
    'Def. Structure':   '#5c7cfa',
    'Set Pieces':       '#cc5de8',
}

# Phase → the deep-dive tab it links to (opposition tab labels).
_PHASE_TAB = {
    'Build-up':        'Build-Up',
    'Chance Creation': 'Chance Creation',
    'Transitions':     'Transitions',
    'Def. Structure':  'Defense',
    'Set Pieces':      'Set Pieces',
}


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


def _phase_metrics(opp_ev: pd.DataFrame, bar_ev: pd.DataFrame,
                   results: list[dict]) -> dict:
    """Per-phase metric rows for the phase cards.

    `opp_ev` are the scouted team's own events; `bar_ev` the events of the teams
    they faced. Goals scored/conceded use the own-goal-aware result gf/ga.
    """
    n = max(len(results), 1)

    # ── Build-up ──────────────────────────────────────────────────────────────
    team_passes    = opp_ev[opp_ev['event_type'] == 'Pass'] if not opp_ev.empty else pd.DataFrame()
    against_passes = bar_ev[bar_ev['event_type'] == 'Pass'] if not bar_ev.empty else pd.DataFrame()
    poss_pct = len(team_passes) / max(len(team_passes) + len(against_passes), 1) * 100
    pass_acc = (team_passes['outcome'].eq(1).sum() / max(len(team_passes), 1) * 100
                if not team_passes.empty and 'outcome' in team_passes.columns else 0.0)
    if 'Pass End X' in team_passes.columns and not team_passes.empty:
        _ex  = pd.to_numeric(team_passes['Pass End X'], errors='coerce')
        _sx  = pd.to_numeric(team_passes['x'],          errors='coerce')
        prog = int((team_passes['outcome'].eq(1) & ((_ex - _sx) >= 25)).sum())
    else:
        prog = int(len(team_passes) * 0.15)

    # ── Chance Creation ───────────────────────────────────────────────────────
    shot_types = ['Goal', 'Saved Shot', 'Miss', 'Post', 'Blocked Shot']
    team_shots = opp_ev[opp_ev['event_type'].isin(shot_types)] if not opp_ev.empty else pd.DataFrame()
    n_goals    = sum(r.get('gf', 0) for r in results)
    n_sot      = int(team_shots['event_type'].isin(['Goal', 'Saved Shot']).sum()) if not team_shots.empty else 0
    n_shots    = len(team_shots)
    sot_pct    = n_sot / max(n_shots, 1) * 100

    # ── Transitions ───────────────────────────────────────────────────────────
    gains = (opp_ev[opp_ev['event_type'].isin(['Ball recovery', 'Interception'])]
             if not opp_ev.empty else pd.DataFrame())
    opp_half_gains = (gains[gains['x'].notna() & (gains['x'] >= 50)]
                      if not gains.empty else pd.DataFrame())
    n_conceded = sum(r.get('ga', 0) for r in results)

    # ── Def. Structure ────────────────────────────────────────────────────────
    against_shots = (bar_ev[bar_ev['event_type'].isin(['Goal', 'Saved Shot', 'Miss'])]
                     if not bar_ev.empty else pd.DataFrame())
    opp_s_pm = len(against_shots) / n
    ga_pm    = n_conceded / n
    cs       = sum(1 for r in results if r.get('ga', 1) == 0)

    # ── Set Pieces ────────────────────────────────────────────────────────────
    if not opp_ev.empty:
        fk_passes = (opp_ev[(opp_ev['event_type'] == 'Pass') & (opp_ev['Free kick taken'] == 'Si')]
                     if 'Free kick taken' in opp_ev.columns else opp_ev.head(0))
        corner_passes = (opp_ev[(opp_ev['event_type'] == 'Pass') & (opp_ev['Corner taken'] == 'Si')]
                         if 'Corner taken' in opp_ev.columns else opp_ev.head(0))
        pen_shots = (opp_ev[
            opp_ev['event_type'].isin(['Goal', 'Miss', 'Post', 'Saved Shot']) &
            (opp_ev['Penalty'] == 'Si')
        ] if 'Penalty' in opp_ev.columns else opp_ev.head(0))
    else:
        fk_passes = corner_passes = pen_shots = pd.DataFrame()

    return {
        'Build-up': [
            ('Possession',      f'{poss_pct:.1f}%',                                HOME_COLOR),
            ('Pass Accuracy',   f'{pass_acc:.1f}%',                                GOLD),
            ('Prog. Passes',    f'{prog} ({_safe_round(prog / n, 1)}/m)',          HOME_COLOR),
        ],
        'Chance Creation': [
            ('Goals Scored',    str(n_goals),                                      GOLD),
            ('Shots on Target', f'{n_sot} ({sot_pct:.0f}%)',                       HOME_COLOR),
            ('Shots/Match',     _safe_round(n_shots / n, 1),                       HOME_COLOR),
        ],
        'Transitions': [
            ('Ball Gains/Match', _safe_round(len(gains) / n, 1),                   '#51cf66'),
            ('Opp-Half Gains',  f'{len(opp_half_gains)} ({round(len(opp_half_gains)/max(len(gains),1)*100):.0f}%)', '#51cf66'),
            ('Goals Conceded',  str(n_conceded),                                   AWAY_COLOR),
        ],
        'Def. Structure': [
            ('Shots Conc/Match', _safe_round(opp_s_pm, 1),                         '#5c7cfa'),
            ('Goals Conc/Match', _safe_round(ga_pm, 2),                            AWAY_COLOR),
            ('Clean Sheets',    f'{cs} / {n}',                                     GOLD),
        ],
        'Set Pieces': [
            ('Corners Taken',   str(len(corner_passes)),                           '#cc5de8'),
            ('FK Passes',       str(len(fk_passes)),                               '#cc5de8'),
            ('Penalties Taken', str(len(pen_shots)),                               GOLD),
        ],
    }


def _phase_strip(scores: dict, metrics: dict) -> dbc.Row:
    """One phase card per tactical phase (mirrors the Barça IQ overview strip)."""
    return dbc.Row([
        dbc.Col(
            _phase_card(
                title   = phase,
                tab     = _PHASE_TAB[phase],
                score   = scores.get(phase, 50.0),
                color   = _PHASE_COLORS[phase],
                metrics = metrics.get(phase, []),
            ),
            md=True,
            style={'display': 'flex', 'flexDirection': 'column'},
        )
        for phase in _PHASE_COLORS
    ], className='mb-4 g-2', align='stretch')


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

# Phase axes, in the order they appear on the radar.
RADAR_PHASES = ['Build-up', 'Chance Creation', 'Transitions', 'Def. Structure', 'Set Pieces']

# Ball gains (recoveries + interceptions + won tackles) come from the canonical
# event_utils.get_ball_gains so the team trace and league-average trace use one
# definition with the correct Opta event_type spellings.


def _empty_counts() -> dict:
    return {
        'passes_for': 0, 'passes_against': 0,
        'shots_for': 0, 'goals_for': 0, 'sot_for': 0,
        'gains_for': 0, 'high_gains_for': 0,
        'goals_against': 0, 'sp_all': 0, 'sp_conn': 0,
        'n_matches': 0,
    }


def _scores_from_counts(c: dict) -> dict:
    """Turn aggregated event counts into the five 0–100 phase scores.

    Single source of truth for both the team trace and the league-average
    trace, so the two are always computed identically.
    """
    n = max(c['n_matches'], 1)

    pf, pa = c['passes_for'], c['passes_against']
    buildup = round(pf / max(pf + pa, 1) * 100, 1)

    n_shots, n_goals, n_sot = c['shots_for'], c['goals_for'], c['sot_for']
    sot_pct  = n_sot / max(n_shots, 1) * 100
    goals_pm = n_goals / n
    chance   = min(round(goals_pm / 3.0 * 100, 1), 100)
    if chance < 5 and n_shots > 0:
        chance = min(round(sot_pct * 1.3, 1), 100)

    gains = c['gains_for']
    trans = round(c['high_gains_for'] / max(gains, 1) * 100, 1) if gains > 0 else 50.0

    ga_pm   = c['goals_against'] / n
    def_sc  = max(0.0, min(100.0, round(100 - ga_pm * 25, 1)))

    sp_all = c['sp_all']
    sp_sc  = round(c['sp_conn'] / max(sp_all, 1) * 100, 1) if sp_all > 0 else 50.0

    return {
        'Build-up':        buildup,
        'Chance Creation': chance,
        'Transitions':     trans,
        'Def. Structure':  def_sc,
        'Set Pieces':      sp_sc,
    }


def _counts_for_side(team_df: pd.DataFrame, opp_df: pd.DataFrame) -> dict:
    """Aggregate one team's event counts for a *single* match (vs one opponent)."""
    c = _empty_counts()
    c['n_matches'] = 1

    et = team_df['event_type'] if 'event_type' in team_df.columns else pd.Series(dtype=object)
    c['passes_for']     = int((et == 'Pass').sum())
    c['passes_against'] = int((opp_df['event_type'] == 'Pass').sum()) if 'event_type' in opp_df.columns else 0

    shots = team_df[et.isin(_SHOT_TYPES)] if not team_df.empty else team_df
    c['shots_for'] = len(shots)
    c['goals_for'] = int((shots['event_type'] == 'Goal').sum()) if not shots.empty else 0
    c['sot_for']   = int(shots['event_type'].isin({'Goal', 'Saved Shot'}).sum()) if not shots.empty else 0

    gains = get_ball_gains(team_df) if not team_df.empty else team_df
    c['gains_for'] = len(gains)
    if not gains.empty and 'x' in gains.columns:
        gx = pd.to_numeric(gains['x'], errors='coerce')
        c['high_gains_for'] = int((gx >= 50).sum())

    # League-average proxy for goals conceded: opponent Goal events in this match.
    c['goals_against'] = int((opp_df['event_type'] == 'Goal').sum()) if 'event_type' in opp_df.columns else 0

    for col in ('Free kick taken', 'Corner taken'):
        if col in team_df.columns:
            sp = team_df[(et == 'Pass') & (team_df[col] == 'Si')]
            c['sp_all'] += len(sp)
            if 'outcome' in sp.columns:
                c['sp_conn'] += int((sp['outcome'] == 1).sum())
    return c


def _phase_scores(opp_ev: pd.DataFrame, bar_ev: pd.DataFrame,
                  results: list[dict]) -> dict:
    """Return the five tactical-phase scores (0–100) for the selected team.

    Aligned with the corresponding analytical tabs:
      Build-up / Chance Creation → buildup + chance_creation tabs
      Transitions → transitions tab   Def. Structure → defence tab
      Set Pieces → set_pieces tab
    """
    c = _counts_for_side(opp_ev, bar_ev)
    # Override the per-match defaults with the team's real season aggregates.
    c['n_matches']     = len(results)
    # Goals conceded comes from the (own-goal-aware) match results, not events.
    c['goals_against'] = sum(r.get('ga', 0) for r in results)
    return _scores_from_counts(c)


# ─── League-average (competition-wide) phase scores ───────────────────────────

# Competition phase averages are expensive (one pass over every match in the
# competition) but stable, so cache them for the app's lifetime. Mirrors the
# module-level league-average caches in match_analysis_tabs.py.
_LEAGUE_AVG_CACHE: dict[str, dict] = {}

# Drop incidental opponents (a single cup tie etc.) from the average so it
# reflects regular participants, not noise.
_MIN_MATCHES_FOR_AVG = 3

_LEAGUE_AVG_READ_COLS = [
    'event_type', 'team_code', 'x', 'outcome', 'Free kick taken', 'Corner taken',
]


def _file_team_counts(path) -> list[dict]:
    """Per-team count dicts for the (up to two) teams in one match parquet."""
    try:
        names = set(pq.ParquetFile(path).schema.names)
        cols  = [c for c in _LEAGUE_AVG_READ_COLS if c in names]
        df    = pd.read_parquet(path, columns=cols)
    except Exception:
        return []
    if df.empty or 'team_code' not in df.columns:
        return []
    vc = df['team_code'].value_counts()
    codes = [c for c in vc.index[:2]
             if isinstance(c, str) and c.upper() not in ('N/A', 'NONE', '')]
    if len(codes) < 2:
        return []
    out = []
    for code in codes:
        other = codes[1] if code == codes[0] else codes[0]
        team_df = df[df['team_code'] == code]
        opp_df  = df[df['team_code'] == other]
        counts  = _counts_for_side(team_df, opp_df)
        counts['team_code'] = code
        out.append(counts)
    return out


def _competition_phase_averages(comp_key: str) -> dict | None:
    """Average phase scores across all regular participants in a competition.

    Each team's season aggregate is scored with the same formula as the
    selected team, then the per-team scores are averaged. Returns None when the
    competition has no usable data.
    """
    if not comp_key or comp_key == 'all':
        return None
    if comp_key in _LEAGUE_AVG_CACHE:
        return _LEAGUE_AVG_CACHE[comp_key]

    paths = competition_match_event_paths(comp_key)
    if not paths:
        _LEAGUE_AVG_CACHE[comp_key] = None
        return None

    # Parquet reads release the GIL — fan out the per-match scan.
    if len(paths) > 4:
        with ThreadPoolExecutor(max_workers=min(8, len(paths))) as ex:
            per_file = list(ex.map(_file_team_counts, paths))
    else:
        per_file = [_file_team_counts(p) for p in paths]

    # Accumulate each team's season aggregate.
    by_team: dict[str, dict] = {}
    for file_counts in per_file:
        for c in file_counts:
            code = c['team_code']
            agg  = by_team.setdefault(code, _empty_counts())
            for k in agg:
                agg[k] += c[k]

    team_scores = [_scores_from_counts(agg)
                   for agg in by_team.values()
                   if agg['n_matches'] >= _MIN_MATCHES_FOR_AVG]
    if not team_scores:
        _LEAGUE_AVG_CACHE[comp_key] = None
        return None

    avg = {p: round(sum(s[p] for s in team_scores) / len(team_scores), 1)
           for p in RADAR_PHASES}
    _LEAGUE_AVG_CACHE[comp_key] = avg
    return avg


# ─── Chart helpers ────────────────────────────────────────────────────────────

# Dashed-line palette for league-average traces (one per competition).
_AVG_PALETTE = [GOLD, '#E06C9F', '#5BC0BE', '#F5A623']


def _hex_to_rgba(hex_color: str, alpha: float = 0.16) -> str:
    h = hex_color.lstrip('#')
    if len(h) == 3:
        h = ''.join(c * 2 for c in h)
    try:
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        return f'rgba({r},{g},{b},{alpha})'
    except (ValueError, IndexError):
        return f'rgba(0,160,220,{alpha})'


def _radar_fig(scores: dict, team_name: str,
               league_avgs: list[tuple[str, dict, str]] | None = None) -> go.Figure:
    """Game-model radar, styled after the Match Report performance radars.

    scores       — the selected team's five phase scores.
    team_name    — legend label for the team trace.
    league_avgs  — list of (label, scores, color) league-average overlays, one
                   per competition the team plays in.
    """
    phases   = RADAR_PHASES
    phases_c = phases + [phases[0]]

    fig = go.Figure()

    # League-average overlays first, so the team sits on top.
    for label, avg, color in (league_avgs or []):
        av_c = [avg.get(p, 0) for p in phases]
        av_c = av_c + [av_c[0]]
        fig.add_trace(go.Scatterpolar(
            r=av_c, theta=phases_c, mode='lines', name=label,
            line=dict(color=color, width=1.5, dash='dot'), opacity=0.9,
            hovertemplate=f'<b>{label}</b><br>%{{theta}}: %{{r:.0f}}/100<extra></extra>',
        ))

    vals   = [scores.get(p, 0) for p in phases]
    vals_c = vals + [vals[0]]
    fig.add_trace(go.Scatterpolar(
        r=vals_c, theta=phases_c, mode='lines+markers+text', name=team_name,
        fill='toself', fillcolor=_hex_to_rgba(HOME_COLOR, 0.18),
        line=dict(color=HOME_COLOR, width=2), marker=dict(color=HOME_COLOR, size=6),
        text=[f'{v:.0f}' for v in vals_c], textposition='top center',
        textfont=dict(size=10, color='#FFFFFF'),
        hovertemplate=f'<b>{team_name}</b><br>%{{theta}}: %{{r:.0f}}/100<extra></extra>',
    ))

    fig.update_layout(
        polar=dict(
            bgcolor='rgba(26,29,46,0.6)',
            radialaxis=dict(range=[0, 105], showticklabels=False,
                            gridcolor='rgba(255,255,255,0.08)',
                            linecolor='rgba(255,255,255,0.08)'),
            angularaxis=dict(tickfont=dict(color=COLORS['text_primary'], size=10),
                             gridcolor='rgba(255,255,255,0.08)',
                             linecolor='rgba(255,255,255,0.08)'),
        ),
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
        showlegend=True,
        legend=dict(x=0.5, y=-0.08, xanchor='center', yanchor='top',
                    orientation='h', font=dict(color=COLORS['text_primary'], size=10),
                    bgcolor='rgba(0,0,0,0)'),
        height=420,
        margin=dict(l=60, r=60, t=30, b=70),
        hoverlabel=dict(bgcolor='#1A1D2E', font_color='white', font_size=12),
    )
    return fig


def _radar_message_fig(msg: str) -> go.Figure:
    """An empty radar carrying a centered message (e.g. no tournament picked)."""
    fig = go.Figure()
    fig.update_layout(
        polar=dict(bgcolor='rgba(26,29,46,0.6)',
                   radialaxis=dict(range=[0, 105], showticklabels=False, visible=False),
                   angularaxis=dict(visible=False)),
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
        showlegend=False, height=420, margin=dict(l=60, r=60, t=30, b=70),
        annotations=[dict(text=msg, x=0.5, y=0.5, xref='paper', yref='paper',
                          showarrow=False, font=dict(color=COLORS['text_secondary'], size=13))],
    )
    return fig


def _comp_color_map(comp_keys: list[str]) -> dict:
    """Stable competition → palette-colour map (order = comp_keys order)."""
    return {ck: _AVG_PALETTE[i % len(_AVG_PALETTE)] for i, ck in enumerate(comp_keys)}


def _build_league_avgs(comp_keys: list[str], color_map: dict) -> list[tuple[str, dict, str]]:
    """League-average overlays for the given competitions (skips empty ones)."""
    out: list[tuple[str, dict, str]] = []
    for ck in comp_keys:
        avg = _competition_phase_averages(ck)
        if avg:
            label = f"{_comp_display(ck.replace('_', ' '))} avg"
            out.append((label, avg, color_map.get(ck, GOLD)))
    return out


def _filter_results(results: list[dict], date_cutoff: str | None,
                    venue: str | None) -> list[dict]:
    """Date-cutoff + venue filter (mirrors opposition_analysis._filter_results)."""
    out = results
    if date_cutoff:
        cut = date_cutoff[:10]
        out = [r for r in out if str(r.get('date', '')) <= cut]
    if venue == 'home':
        out = [r for r in out if r.get('is_home')]
    elif venue == 'away':
        out = [r for r in out if not r.get('is_home')]
    return out


def _team_scores_for_comps(team: str, country: str, comp_keys: list[str],
                           venue: str | None, date_cutoff: str | None,
                           match_ids: list | None) -> dict:
    """Recompute the team's phase scores across a subset of competitions."""
    opp_frames, bar_frames, results = [], [], []
    for ck in comp_keys:
        opp, bar = load_opp_events(team, ck, venue or 'all', match_ids, date_cutoff)
        if not opp.empty:
            opp_frames.append(opp)
        if not bar.empty:
            bar_frames.append(bar)
        rs = _filter_results(get_opp_team_matches(team, country, ck), date_cutoff, venue)
        if match_ids:
            rs = [r for r in rs if r.get('match_id') in match_ids]
        results.extend(rs)
    opp_ev = pd.concat(opp_frames, ignore_index=True) if opp_frames else pd.DataFrame()
    bar_ev = pd.concat(bar_frames, ignore_index=True) if bar_frames else pd.DataFrame()
    return _phase_scores(opp_ev, bar_ev, results)


def _radar_panel(team: str, comp_keys: list[str], init_fig: go.Figure,
                 header_style: dict, panel_style: dict) -> html.Div:
    """Radar panel: header + (optional) tournament checkboxes + the graph."""
    children = [html.Div('Game Model Radar', style=header_style)]

    # Tournament filter only makes sense when more than one is in view.
    if len(comp_keys) > 1:
        color_map = _comp_color_map(comp_keys)
        children.append(html.Div(
            dcc.Checklist(
                id='oa-radar-tourn-filter',
                options=[{'label': _comp_display(ck.replace('_', ' ')), 'value': ck}
                         for ck in comp_keys],
                value=list(comp_keys),
                inline=True,
                inputStyle={'marginRight': '5px', 'cursor': 'pointer',
                            'accentColor': GOLD},
                labelStyle={'marginRight': '14px', 'color': COLORS['text_secondary'],
                            'fontSize': '0.78rem', 'cursor': 'pointer'},
                style={'display': 'flex', 'flexWrap': 'wrap', 'rowGap': '4px'},
            ),
            style={'marginBottom': '6px'},
        ))

    children.append(dcc.Graph(id='oa-radar-graph', figure=init_fig,
                              config=CHART_CONFIG, style={'width': '100%'}))
    # Carries the full competition list so the callback can rebuild stable colours.
    children.append(dcc.Store(id='oa-radar-compkeys', data=list(comp_keys)))
    return html.Div(children, style=panel_style)


# ─── Overall Season Summary (ported from home.py, scoped to the team) ─────────

def _match_event_metrics(opp_ev: pd.DataFrame, bar_ev: pd.DataFrame) -> dict:
    """Per-match event-derived metrics keyed by match_id.

    Returns {match_id: {poss, pass_acc, ppda, papp}} where
      poss     — possession % (team passes / all passes)
      pass_acc — pass accuracy %
      ppda     — passes allowed per defensive action (lower = more pressing)
      papp     — average completed passes per possession
    `opp_ev` are the scouted team's events; `bar_ev` the opponents'.
    """
    out: dict = {}
    if opp_ev.empty or 'match_id' not in opp_ev.columns:
        return out

    have_bar = (not bar_ev.empty) and ('match_id' in bar_ev.columns)
    for mid, te in opp_ev.groupby('match_id'):
        oe = bar_ev[bar_ev['match_id'] == mid] if have_bar else pd.DataFrame()

        tp = te[te['event_type'] == 'Pass']
        op = oe[oe['event_type'] == 'Pass'] if not oe.empty else pd.DataFrame()
        n_tp, n_op = len(tp), len(op)

        poss = round(n_tp / max(n_tp + n_op, 1) * 100, 1)
        pass_acc = (round(tp['outcome'].eq(1).sum() / max(n_tp, 1) * 100, 1)
                    if 'outcome' in tp.columns and n_tp else 0.0)

        # PPDA: opponent passes in their own build-up (x<40) ÷ our pressing
        # actions (tackles + interceptions) in the attacking half (x>50).
        if not op.empty and 'x' in op.columns:
            opp_build = op[pd.to_numeric(op['x'], errors='coerce') < 40]
        else:
            opp_build = op
        if 'x' in te.columns:
            press = te[te['event_type'].isin(['Tackle', 'Interception']) &
                       (pd.to_numeric(te['x'], errors='coerce') > 50)]
        else:
            press = te.head(0)
        ppda = round(len(opp_build) / max(len(press), 1), 2)

        # Passes per possession: completed passes ÷ possessions, where a
        # possession ends in a shot or a turnover (dispossession / failed
        # pass / failed take-on).
        shots   = te[te['event_type'].isin(_SHOT_TYPES)]
        disp    = te[te['event_type'] == 'Dispossessed']
        bad_pass = tp[tp['outcome'].eq(0)] if 'outcome' in tp.columns else tp.head(0)
        bad_to   = (te[(te['event_type'] == 'Take On') & (te['outcome'] == 0)]
                    if 'outcome' in te.columns else te.head(0))
        possessions = len(shots) + len(disp) + len(bad_pass) + len(bad_to)
        papp = round(n_tp / max(possessions, 1), 2)

        out[mid] = {'poss': float(poss), 'pass_acc': float(pass_acc),
                    'ppda': float(ppda), 'papp': float(papp)}
    return out


def _season_timeline(results: list[dict], event_metrics: dict | None = None) -> list[dict]:
    """Chronological per-match rows feeding the Form Trendline."""
    em = event_metrics or {}
    tl = []
    for r in sorted(results, key=lambda r: str(r.get('date', ''))):
        res = r.get('result', '')
        pts = 3 if res == 'W' else (1 if res == 'D' else 0)
        mid = r.get('match_id')
        m   = em.get(mid, {})
        tl.append({
            'date':        str(r.get('date', ''))[:10],
            'match_id':    mid,
            'opponent':    r.get('opponent', ''),
            'result':      res,
            'gf':          r.get('gf', 0),
            'ga':          r.get('ga', 0),
            'points':      pts,
            'competition': r.get('competition', ''),
            'poss':        m.get('poss'),
            'pass_acc':    m.get('pass_acc'),
            'ppda':        m.get('ppda'),
            'papp':        m.get('papp'),
        })
    return tl


# Per-match metric registry: key → (label, colour, axis). 'y2' (right axis,
# 0–100) holds the percentage metrics so they don't dwarf PPG/GF/GA on the left.
_TREND_METRICS = [
    ('gf',       'Goals Scored',        '#28a745', 'y'),
    ('ga',       'Goals Conceded',      '#dc3545', 'y'),
    ('ppda',     'PPDA',                '#E06C9F', 'y'),
    ('papp',     'Passes / Possession', '#cc5de8', 'y'),
    ('poss',     'Possession %',        HOME_COLOR, 'y2'),
    ('pass_acc', 'Pass Accuracy %',     '#5BC0BE', 'y2'),
]
_PCT_METRICS = {'poss', 'pass_acc'}


def _form_trendline_fig(timeline: list[dict], metrics: list[str]) -> go.Figure:
    """Form Trendline — PPG (cumulative) plus toggleable per-match metrics.

    Percentage metrics (Possession, Pass Accuracy) render on a right-hand 0–100
    axis; everything else shares the left axis.
    """
    metrics = metrics or []
    fig = go.Figure()

    if timeline:
        dates = [t['date'] for t in timeline]
        hover = [f"{t['opponent']} ({t['result']})<br>{t['competition']}"
                 for t in timeline]

        if 'ppg' in metrics:
            cum_pts, ppg_vals = 0, []
            for i, t in enumerate(timeline, 1):
                cum_pts += t['points']
                ppg_vals.append(round(cum_pts / i, 2))
            marker_colors = [_RESULT_C.get(t['result'], _GA_C) for t in timeline]
            fig.add_trace(go.Scatter(
                x=dates, y=ppg_vals, mode='lines+markers', name='Points Per Game',
                line=dict(color=GOLD, width=2),
                marker=dict(color=marker_colors, size=8, line=dict(color=GOLD, width=1)),
                text=hover, hovertemplate='%{text}<br>PPG: %{y}<extra></extra>',
                fill='tozeroy', fillcolor='rgba(237, 187, 0, 0.06)',
            ))

        for key, name, color, axis in _TREND_METRICS:
            if key not in metrics:
                continue
            fig.add_trace(go.Scatter(
                x=dates, y=[t.get(key) for t in timeline], mode='lines+markers',
                name=name, yaxis=axis,
                line=dict(color=color, width=2, dash='dot'),
                marker=dict(color=color, size=6),
                text=hover, hovertemplate='%{text}<br>' + name + ': %{y}<extra></extra>',
                connectgaps=False,
            ))

    layout = dict(
        **_CHART_LAYOUT,
        height=350,
        xaxis=dict(title='', gridcolor='rgba(255,255,255,0.05)', showgrid=True),
        yaxis=dict(title='', gridcolor='rgba(255,255,255,0.05)', showgrid=True),
        legend=dict(orientation='h', yanchor='bottom', y=1.02,
                    xanchor='center', x=0.5,
                    font=dict(color=COLORS['text_primary'], size=11)),
        showlegend=True,
    )
    if any(m in _PCT_METRICS for m in metrics):
        layout['yaxis2'] = dict(title='%', overlaying='y', side='right',
                                range=[0, 100], showgrid=False,
                                tickfont=dict(size=9))
    fig.update_layout(**layout)
    return fig


def _player_contributions(opp_ev: pd.DataFrame) -> list[dict]:
    """Goals / assists / appearances per player from the team's own events."""
    if opp_ev.empty or 'player_name' not in opp_ev.columns:
        return []

    goals = opp_ev[opp_ev['event_type'] == 'Goal']
    goal_ct = goals.groupby('player_name').size() if not goals.empty else pd.Series(dtype=int)

    if 'Assist' in opp_ev.columns:
        ass = opp_ev[(opp_ev['event_type'] == 'Pass') & (opp_ev['Assist'].astype(str) == '16')]
        ass_ct = ass.groupby('player_name').size() if not ass.empty else pd.Series(dtype=int)
    else:
        ass_ct = pd.Series(dtype=int)

    apps = (opp_ev.groupby('player_name')['match_id'].nunique()
            if 'match_id' in opp_ev.columns else pd.Series(dtype=int))

    rows = []
    for p in set(goal_ct.index) | set(ass_ct.index):
        if not isinstance(p, str) or p.strip() in ('', 'N/A', 'None'):
            continue
        rows.append({
            'player':  p,
            'goals':   int(goal_ct.get(p, 0)),
            'assists': int(ass_ct.get(p, 0)),
            'apps':    int(apps.get(p, 0)),
        })
    rows.sort(key=lambda r: (-r['goals'], -r['assists']))
    return rows


def _contributor_card(player: str, goals: int, assists: int, apps: int) -> dbc.Col:
    """Player contributor card — name + contributions only (no photo: opposition
    players have no image assets)."""
    return dbc.Col([
        html.Div([
            html.Div(player, style={
                'fontWeight': 700, 'color': COLORS['text_primary'], 'fontSize': '0.9rem',
                'fontFamily': BARCA_FONT, 'textAlign': 'center', 'marginBottom': '0.5rem',
                'whiteSpace': 'nowrap', 'overflow': 'hidden', 'textOverflow': 'ellipsis'}),
            html.Div([
                html.Div([
                    html.Div(str(goals), className='player-stat-num'),
                    html.Div('Goals', className='player-stat-lbl'),
                ], className='player-stat-item'),
                html.Div([
                    html.Div(str(assists), className='player-stat-num'),
                    html.Div('Assists', className='player-stat-lbl'),
                ], className='player-stat-item'),
                html.Div([
                    html.Div(str(apps), className='player-stat-num'),
                    html.Div('Apps', className='player-stat-lbl'),
                ], className='player-stat-item'),
            ], className='player-stat-row'),
        ], className='player-contrib-card h-100',
           style={'display': 'flex', 'flexDirection': 'column', 'justifyContent': 'center'}),
    ], lg=True, md=4, sm=6, className='mb-3')


def _build_contributors(opp_ev: pd.DataFrame, n: int = 5) -> list:
    rows = _player_contributions(opp_ev)
    top  = [r for r in rows if r['goals'] > 0][:n]
    if not top:
        return [html.P('No scorer data available for this selection.',
                       style={'color': COLORS['text_secondary']})]
    return [_contributor_card(r['player'], r['goals'], r['assists'], r['apps']) for r in top]


# ─── Starting-formation usage ─────────────────────────────────────────────────

# Only the small subset of lineup columns needed to read starting formations.
_LINEUP_FORM_COLS = ['match_id', 'team_position', 'formation', 'role']

# Shared panel heading style (matches the "Game Model Radar" header in _radar_panel).
_PANEL_HDR = {
    'color': COLORS['gold'], 'fontSize': '0.72rem', 'fontWeight': 700,
    'letterSpacing': '0.8px', 'textTransform': 'uppercase', 'marginBottom': '8px',
}


def _fmt_formation(formation) -> str:
    """'3421' → '3-4-2-1' for display; falls back to the raw string."""
    digits = [c for c in str(formation).strip() if c.isdigit()]
    return '-'.join(digits) if digits else (str(formation).strip() or '—')


def _match_formations(comp_keys: list[str], results: list[dict]) -> dict[str, str]:
    """Map each match the team played → its starting-formation string.

    Reads the lineup parquet for each match (targeted by the match_id suffix in
    the filename) and selects the team's own side via ``is_home`` from the
    result row — never by team-name matching.
    """
    home_by_mid = {str(r.get('match_id')): bool(r.get('is_home'))
                   for r in results if r.get('match_id') is not None}
    if not home_by_mid:
        return {}

    # Restrict each competition scan to the match_ids actually in view.
    mids_by_comp: dict[str, set] = {}
    for r in results:
        mid = r.get('match_id')
        ck  = r.get('competition_key')
        if mid is None or not ck:
            continue
        mids_by_comp.setdefault(ck, set()).add(str(mid))

    out: dict[str, str] = {}
    for ck in comp_keys:
        wanted = mids_by_comp.get(ck)
        if not wanted:
            continue
        folder = _opp_dir(ck, 'lineup')
        if not folder.exists():
            continue
        # Index lineup files by their trailing match_id segment.
        mid_to_file = {f.stem.rsplit('_', 1)[-1]: f
                       for f in folder.iterdir() if f.suffix == '.parquet'}
        for mid in wanted:
            path = mid_to_file.get(mid)
            if path is None:
                continue
            try:
                names = set(pq.ParquetFile(path).schema.names)
                use   = [c for c in _LINEUP_FORM_COLS if c in names]
                df    = pd.read_parquet(path, columns=use)
            except Exception:
                continue
            if df.empty or 'formation' not in df.columns:
                continue
            side = 'home' if home_by_mid.get(mid) else 'away'
            tg = df[df['team_position'] == side] if 'team_position' in df.columns else df
            if 'role' in tg.columns:
                starters = tg[tg['role'] == 'Start']
                if not starters.empty:
                    tg = starters
            if tg.empty:
                continue
            form = str(tg['formation'].iloc[0]).strip()
            if not form or form.upper() in ('N/A', 'NONE', '0', ''):
                continue
            out[mid] = form
    return out


def _formation_counts(match_formations: dict[str, str]) -> list[tuple[str, int]]:
    """(formation, n_matches) sorted ascending so the most-used lands on top of
    a horizontal bar chart."""
    counts: dict[str, int] = {}
    for form in match_formations.values():
        counts[form] = counts.get(form, 0) + 1
    return sorted(counts.items(), key=lambda kv: (kv[1], kv[0]))


def _formation_bar_fig(usage: list[tuple[str, int]]) -> go.Figure:
    """Horizontal bar chart of starting formation (y) vs matches used in (x)."""
    fig = go.Figure()
    if not usage:
        fig.update_layout(
            **_CHART_LAYOUT, height=220,
            xaxis=dict(visible=False), yaxis=dict(visible=False),
            annotations=[dict(text='No lineup data available for this selection.',
                              x=0.5, y=0.5, xref='paper', yref='paper', showarrow=False,
                              font=dict(color=COLORS['text_secondary'], size=12))],
        )
        return fig

    labels = [_fmt_formation(f) for f, _ in usage]
    counts = [c for _, c in usage]
    max_c  = max(counts)

    fig.add_trace(go.Bar(
        x=counts, y=labels, orientation='h',
        marker=dict(color=HOME_COLOR, line=dict(color=GOLD, width=1)),
        text=counts, textposition='outside', cliponaxis=False,
        textfont=dict(color=COLORS['text_primary'], size=11),
        hovertemplate='Formation %{y}<br>Matches: %{x}<extra></extra>',
    ))
    fig.update_layout(
        **_CHART_LAYOUT,
        height=max(220, 46 * len(usage) + 80),
        bargap=0.35,
        xaxis=dict(title='Matches', gridcolor='rgba(255,255,255,0.05)', showgrid=True,
                   dtick=1, range=[0, max_c + max(1, round(max_c * 0.15))], zeroline=False),
        yaxis=dict(title='', gridcolor='rgba(255,255,255,0.05)', showgrid=False,
                   automargin=True),
        showlegend=False,
    )
    return fig


def _formation_table(results: list[dict], match_formations: dict[str, str],
                     selected_match_ids: list | None) -> html.Div:
    """Per-match formation table for the 25% side column.

    Only populated when matches are picked in the calendar; otherwise shows a
    prompt. ``results`` is already filtered to the selected matches upstream.
    """
    if not selected_match_ids:
        return html.Div(
            'Select matches in the calendar to list each match’s starting formation.',
            style={'color': COLORS['text_secondary'], 'fontSize': '0.8rem',
                   'lineHeight': '1.4', 'padding': '0.5rem 0.25rem'},
        )

    sel = {str(m) for m in selected_match_ids}
    rows_in = [r for r in results if str(r.get('match_id')) in sel]
    rows_in.sort(key=lambda r: str(r.get('date', '')))

    _th = {'color': COLORS['gold'], 'textAlign': 'left', 'padding': '6px 8px',
           'borderBottom': f'1px solid {COLORS["dark_border"]}', 'fontSize': '0.66rem',
           'textTransform': 'uppercase', 'letterSpacing': '0.5px', 'position': 'sticky',
           'top': 0, 'backgroundColor': COLORS['dark_secondary']}
    _td = {'padding': '6px 8px', 'borderBottom': f'1px solid {COLORS["dark_border"]}',
           'verticalAlign': 'middle'}

    body_rows = []
    for r in rows_in:
        mid   = str(r.get('match_id'))
        form  = match_formations.get(mid)
        opp   = r.get('opponent', '')
        ha    = 'H' if r.get('is_home') else 'A'
        date  = str(r.get('date', ''))[:10]
        ha_col = HOME_COLOR if r.get('is_home') else _GA_C
        body_rows.append(html.Tr([
            html.Td([
                html.Div([
                    html.Span(ha, style={'color': ha_col, 'fontWeight': 700,
                                         'fontSize': '0.62rem', 'marginRight': '5px'}),
                    html.Span(opp, style={'color': COLORS['text_primary'],
                                          'fontWeight': 600, 'fontSize': '0.78rem'}),
                ]),
                html.Div(date, style={'color': COLORS['text_secondary'], 'fontSize': '0.62rem'}),
            ], style=_td),
            html.Td(_fmt_formation(form) if form else '—', style={
                **_td, 'color': COLORS['gold'], 'fontWeight': 700,
                'fontSize': '0.82rem', 'textAlign': 'right', 'whiteSpace': 'nowrap',
            }),
        ]))

    if not body_rows:
        return html.Div('No formation data for the selected matches.',
                        style={'color': COLORS['text_secondary'], 'fontSize': '0.8rem',
                               'padding': '0.5rem 0.25rem'})

    table = html.Table([
        html.Thead(html.Tr([
            html.Th('Match', style=_th),
            html.Th('Formation', style={**_th, 'textAlign': 'right'}),
        ])),
        html.Tbody(body_rows),
    ], style={'width': '100%', 'borderCollapse': 'collapse', 'color': COLORS['text_primary']})

    return html.Div(table, style={'maxHeight': '420px', 'overflowY': 'auto'})


def _season_summary_section(timeline: list[dict], contributor_cards: list,
                            radar_panel: html.Div,
                            formation_fig: go.Figure,
                            formation_table: html.Div) -> html.Div:
    """Overall Season Summary — Game Model Radar + Form Trendline + Starting
    Formations + Top Contributors.

    The radar sits on the left, under the same heading; the trendline (with
    metric toggles) fills the right column. Below them, the starting-formation
    bar chart (75%) sits beside a per-match formation table (25%).
    """
    # Distinct competitions in view → tournament filter options.
    comps_in_view: list[str] = []
    seen = set()
    for t in timeline:
        c = t.get('competition')
        if c and c not in seen:
            seen.add(c)
            comps_in_view.append(c)
    tourn_options = ([{'label': 'All Competitions', 'value': 'all'}] +
                     [{'label': _comp_display(c), 'value': c} for c in comps_in_view])

    trendline_card = dbc.Card([dbc.CardBody([
        html.Div('Form Trendline', style=_PANEL_HDR),
        # Tournament filter (mirrors the Home page).
        dbc.Row([
            dbc.Col([
                html.Label('Filter by Tournament:', style={
                    'color': COLORS['text_secondary'], 'fontSize': '0.8rem',
                    'marginRight': '0.5rem'}),
                dcc.Dropdown(
                    id='oa-summary-tourn',
                    options=tourn_options,
                    value='all',
                    clearable=False,
                    className='culevision-dropdown',
                    style={'width': '250px'},
                ),
            ], width='auto', className='d-flex align-items-center'),
        ], className='mb-2'),

        dbc.Row([
            dbc.Col([
                html.Label('Metrics:', style={
                    'color': COLORS['text_secondary'],
                    'fontSize': '0.8rem', 'marginRight': '0.5rem'}),
                dcc.Checklist(
                    id='oa-summary-metrics',
                    options=[
                        {'label': ' Points Per Game',      'value': 'ppg'},
                        {'label': ' Goals Scored',         'value': 'gf'},
                        {'label': ' Goals Conceded',       'value': 'ga'},
                        {'label': ' Possession %',         'value': 'poss'},
                        {'label': ' Pass Accuracy %',      'value': 'pass_acc'},
                        {'label': ' PPDA',                 'value': 'ppda'},
                        {'label': ' Passes / Possession',  'value': 'papp'},
                    ],
                    value=['ppg'],
                    inline=True,
                    className='trendline-checklist',
                    style={'display': 'flex', 'flexWrap': 'wrap', 'gap': '1rem',
                           'color': COLORS['text_primary'], 'fontSize': '0.85rem'},
                ),
            ]),
        ], className='mb-2'),
        dcc.Graph(id='oa-form-trendline',
                  figure=_form_trendline_fig(timeline, ['ppg']),
                  config=CHART_CONFIG),
        dcc.Store(id='oa-summary-timeline', data=timeline),
    ])])

    return html.Div([
        html.H4('Overall Season Summary', className='section-header',
                style={'fontFamily': BARCA_FONT}),

        # Radar + Form Trendline side-by-side …
        dbc.Row([
            dbc.Col(radar_panel, lg=5, md=12, className='mb-3'),
            dbc.Col(trendline_card, lg=7, md=12, className='mb-3'),
        ], className='g-3'),

        # … Starting Formations (75%) + per-match formation table (25%) …
        dbc.Row([
            dbc.Col(
                dbc.Card([dbc.CardBody([
                    html.Div('Starting Formations', style=_PANEL_HDR),
                    dcc.Graph(figure=formation_fig, config=CHART_CONFIG),
                ])]),
                lg=9, md=12, className='mb-3',
            ),
            dbc.Col(
                dbc.Card([dbc.CardBody([
                    html.Div('Formation by Match', style=_PANEL_HDR),
                    formation_table,
                ])], className='h-100'),
                lg=3, md=12, className='mb-3',
            ),
        ], className='g-3 mb-4', align='stretch'),

        # … Top Contributors end-to-end below (mirrors the Home page).
        html.H5('Top Contributors', className='mb-3',
                style={'color': COLORS['gold'], 'fontFamily': BARCA_FONT,
                       'fontWeight': 600, 'fontSize': '1.15rem'}),
        dbc.Row(contributor_cards),
    ], className='mb-4')


# ─── Public builder ───────────────────────────────────────────────────────────

def build_overview(team: str, country: str, comp_key: str,
                   all_results: list[dict], opp_ev: pd.DataFrame,
                   bar_ev: pd.DataFrame, n_matches: int,
                   selected_match_ids: list | None = None) -> html.Div:
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

    # ── Phase cards strip (mirrors the Barça IQ overview) ─────────────────────
    scores = _phase_scores(opp_ev, bar_ev, all_results)
    children.append(_phase_strip(scores, _phase_metrics(opp_ev, bar_ev, all_results)))

    # ── Charts row ────────────────────────────────────────────────────────────
    # League average for each competition the team is in (within this view).
    if comp_key == 'all':
        comp_keys = sorted({r.get('competition_key') for r in all_results
                            if r.get('competition_key')})
    else:
        comp_keys = [comp_key]

    color_map   = _comp_color_map(comp_keys)
    league_avgs = _build_league_avgs(comp_keys, color_map)

    _panel = {
        'backgroundColor': COLORS['dark_secondary'],
        'border': f'1px solid {COLORS["dark_border"]}',
        'borderRadius': '12px', 'padding': '16px', 'height': '100%',
    }

    # ── Overall Season Summary (radar + trendline + formations + contributors) ─
    timeline         = _season_timeline(all_results, _match_event_metrics(opp_ev, bar_ev))
    radar_panel      = _radar_panel(team, comp_keys,
                                    _radar_fig(scores, team, league_avgs), _PANEL_HDR, _panel)
    match_formations = _match_formations(comp_keys, all_results)
    formation_fig    = _formation_bar_fig(_formation_counts(match_formations))
    formation_table  = _formation_table(all_results, match_formations, selected_match_ids)
    children.append(_season_summary_section(
        timeline, _build_contributors(opp_ev, n=5), radar_panel,
        formation_fig, formation_table))

    return html.Div(children)


# ─── Callbacks ────────────────────────────────────────────────────────────────

def register_overview_callbacks(app) -> None:
    """Wire the Game Model Radar's tournament checkboxes to the radar figure."""

    @app.callback(
        Output('oa-radar-graph', 'figure'),
        Input('oa-radar-tourn-filter', 'value'),
        State('oa-team-select',      'value'),
        State('oa-date-filter',      'date'),
        State('oa-venue-filter',     'value'),
        State('oa-selected-matches', 'data'),
        State('oa-radar-compkeys',   'data'),
        prevent_initial_call=True,
    )
    def _update_radar(selected, team, date_cutoff, venue, match_ids, comp_keys):
        if not team:
            raise PreventUpdate

        comp_keys = comp_keys or []
        selected  = [c for c in (selected or []) if c in comp_keys]
        if not selected:
            return _radar_message_fig('Select at least one tournament')

        country     = get_team_country(team)
        color_map   = _comp_color_map(comp_keys)
        scores      = _team_scores_for_comps(team, country, selected,
                                             venue, date_cutoff, match_ids)
        league_avgs = _build_league_avgs(selected, color_map)
        return _radar_fig(scores, team, league_avgs)

    # ── Form Trendline: tournament filter + metric checkboxes → figure ────────
    @app.callback(
        Output('oa-form-trendline', 'figure'),
        Input('oa-summary-metrics', 'value'),
        Input('oa-summary-tourn',   'value'),
        State('oa-summary-timeline', 'data'),
        prevent_initial_call=True,
    )
    def _update_trendline(metrics, tournament, timeline):
        timeline = timeline or []
        if tournament and tournament != 'all':
            timeline = [t for t in timeline if t.get('competition') == tournament]
        return _form_trendline_fig(timeline, metrics or [])
