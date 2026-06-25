"""
Team Analysis — Tab 0: Overview

Visual introduction to the five deep-dive tabs.

Layout (top → bottom):
  1. Season snapshot banner  — record, form strip, key KPIs
  2. Stat pills row          — GF · GA · CS · Matches · Pass Acc · PPDA
  3. Phase cards strip       — one card per deep-dive tab with metrics + score bar
  4. Game-model radar  ⟺  Form Trendline (tournament filter & metric toggles)
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import pandas as pd
import pyarrow.parquet as pq
import plotly.graph_objects as go
from dash import html, dcc
import dash_bootstrap_components as dbc

from utils.config import COLORS
from utils.data_utils import (
    get_all_events,
    get_match_results,
    filter_own_goals,
    exclude_own_goals,
    COMPETITION_NAMES,
    CURRENT_SEASON,
)
from utils.opposition_data_utils import competition_match_event_paths
from page_utils.visualizations import (
    CHART_CONFIG,
    layout_config,
    empty_fig,
    GOLD,
    HOME_COLOR,
    AWAY_COLOR,
)
from page_utils.competitions import COMP_SHORT as _COMP_SHORT
from page_utils.event_filters import SHOT_TYPES as _SHOT_TYPES
from utils.event_utils import get_ball_gains, compute_ppda

# Barcelona competition display name → data-folder key (inverse of COMPETITION_NAMES).
_DISPLAY_TO_FOLDER = {v: k for k, v in COMPETITION_NAMES.items()}


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
    gains     = (bar[bar['event_type'].isin(['Ball recovery', 'Interception'])]
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


# ─── Game-model radar: league-average infrastructure ─────────────────────────
# Ported 1:1 from the Opposition Analysis overview so the Barça IQ radar matches
# it exactly: Match-Report styling, value labels, legend, per-competition
# league-average overlays and an interactive tournament filter.

# Phase axes, in the order they appear on the radar (must match _compute_phases).
RADAR_PHASES = ['Build-up', 'Chance Creation', 'Transitions', 'Def. Structure', 'Set Pieces']

# Ball gains (recoveries + interceptions + won tackles) come from the canonical
# event_utils.get_ball_gains so the team trace and league-average trace use one
# definition with the correct Opta event_type spellings.

# Competition phase averages are expensive (one pass over every match in the
# competition) but stable, so cache them for the app's lifetime.
_LEAGUE_AVG_CACHE: dict[str, dict] = {}
_MIN_MATCHES_FOR_AVG = 3
_LEAGUE_AVG_READ_COLS = [
    'event_type', 'team_code', 'x', 'outcome', 'Free kick taken', 'Corner taken',
]

# Dashed-line palette for league-average traces (one per competition).
_AVG_PALETTE = [GOLD, '#E06C9F', '#5BC0BE', '#F5A623']


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

    c['goals_against'] = int((opp_df['event_type'] == 'Goal').sum()) if 'event_type' in opp_df.columns else 0

    for col in ('Free kick taken', 'Corner taken'):
        if col in team_df.columns:
            sp = team_df[(et == 'Pass') & (team_df[col] == 'Si')]
            c['sp_all'] += len(sp)
            if 'outcome' in sp.columns:
                c['sp_conn'] += int((sp['outcome'] == 1).sum())
    return c


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

    Each team's season aggregate is scored with the same formula as Barcelona,
    then the per-team scores are averaged. Returns None when the competition has
    no usable data. `comp_key` is the data-folder key (e.g. Spain_Primera_Division).
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


def _comps_in_view(results: list[dict]) -> list[str]:
    """Folder keys for the competitions present in a Barcelona result set."""
    keys = set()
    for r in results:
        disp = r.get('competition', '')
        keys.add(_DISPLAY_TO_FOLDER.get(disp, disp.replace(' ', '_')))
    return sorted(k for k in keys if k)


def _comp_color_map(comp_keys: list[str]) -> dict:
    """Stable competition → palette-colour map (order = comp_keys order)."""
    return {ck: _AVG_PALETTE[i % len(_AVG_PALETTE)] for i, ck in enumerate(comp_keys)}


def _build_league_avgs(comp_keys: list[str], color_map: dict) -> list[tuple[str, dict, str]]:
    """League-average overlays for the given competitions (skips empty ones)."""
    out: list[tuple[str, dict, str]] = []
    for ck in comp_keys:
        avg = _competition_phase_averages(ck)
        if avg:
            label = f"{COMPETITION_NAMES.get(ck, ck.replace('_', ' '))} avg"
            out.append((label, avg, color_map.get(ck, GOLD)))
    return out


def _barca_scores_for_comps(comp_keys: list[str], venue: str | None,
                            match_ids: list | None) -> dict:
    """Recompute Barcelona's phase scores across a subset of competitions.

    Mirrors the filtering in build_overview_tab so the radar callback and the
    initial render agree. `comp_keys` are data-folder keys.
    """
    comps_display = [COMPETITION_NAMES.get(ck, ck.replace('_', ' ')) for ck in comp_keys]

    results = [r for r in get_match_results() if r.get('competition') in comps_display]
    if venue and venue != 'All':
        is_home = (venue == 'Home')
        results = [r for r in results if r.get('is_home') == is_home]
    if match_ids:
        id_set  = set(match_ids)
        results = [r for r in results if r.get('match_id') in id_set]
    if not results:
        return {k: 50.0 for k in RADAR_PHASES}

    events = get_all_events(CURRENT_SEASON)
    if not events.empty:
        events = events[events['competition'].isin(comps_display)]
        rid    = {r['match_id'] for r in results}
        if 'match_id' in events.columns:
            events = events[events['match_id'].isin(rid)]

    bar = events[events['team_code'] == 'BAR'] if not events.empty else pd.DataFrame()
    opp = events[events['team_code'] != 'BAR'] if not events.empty else pd.DataFrame()
    if bar.empty:
        return {k: 50.0 for k in RADAR_PHASES}
    scores, _ = _compute_phases(bar, opp, results, events)
    return scores


# ─── Chart helpers ────────────────────────────────────────────────────────────

def _hex_to_rgba(hex_color: str, alpha: float = 0.16) -> str:
    h = hex_color.lstrip('#')
    if len(h) == 3:
        h = ''.join(c * 2 for c in h)
    try:
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        return f'rgba({r},{g},{b},{alpha})'
    except (ValueError, IndexError):
        return f'rgba(0,160,220,{alpha})'


def _radar_fig(scores: dict, team_name: str = 'Barça',
               league_avgs: list[tuple[str, dict, str]] | None = None) -> go.Figure:
    """Game-model radar, styled after the Match Report performance radars.

    scores       — Barcelona's five phase scores.
    team_name    — legend label for the team trace.
    league_avgs  — list of (label, scores, color) league-average overlays, one
                   per competition in view.
    """
    if not scores:
        return empty_fig('No phase data')

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


# Section-header style shared by the radar panel (matches the nested `_sec`).
_SEC_STYLE = {
    'color': GOLD, 'fontWeight': '700', 'fontSize': '0.72rem',
    'letterSpacing': '1px', 'textTransform': 'uppercase',
    'paddingBottom': '10px',
    'borderBottom': f'1px solid {COLORS["dark_border"]}',
    'marginBottom': '12px',
}


def _radar_panel(comp_keys: list[str], init_fig: go.Figure) -> html.Div:
    """Radar panel: header + (optional) tournament checkboxes + the graph."""
    children = [html.Div('Game Model Radar', style=_SEC_STYLE)]

    # Tournament filter only makes sense when more than one is in view.
    if len(comp_keys) > 1:
        children.append(html.Div(
            dcc.Checklist(
                id='ta-radar-tourn-filter',
                options=[{'label': COMPETITION_NAMES.get(ck, ck.replace('_', ' ')), 'value': ck}
                         for ck in comp_keys],
                value=list(comp_keys),
                inline=True,
                inputStyle={'marginRight': '5px', 'cursor': 'pointer', 'accentColor': GOLD},
                labelStyle={'marginRight': '14px', 'color': COLORS['text_secondary'],
                            'fontSize': '0.78rem', 'cursor': 'pointer'},
                style={'display': 'flex', 'flexWrap': 'wrap', 'rowGap': '4px'},
            ),
            style={'marginBottom': '6px'},
        ))

    children.append(dcc.Graph(id='ta-radar-graph', figure=init_fig,
                              config=CHART_CONFIG, style={'width': '100%'}))
    # Carries the full competition list so the callback can rebuild stable colours.
    children.append(dcc.Store(id='ta-radar-compkeys', data=list(comp_keys)))
    return html.Div(children, style=_CARD)


# ─── Form Trendline (ported from the Opposition Analysis overview) ────────────

_TREND_RESULT_C = {'W': '#28a745', 'D': '#ffc107', 'L': '#dc3545'}
_TREND_GA_C     = '#A5A8B8'

_TREND_LAYOUT = dict(
    paper_bgcolor='rgba(0,0,0,0)',
    plot_bgcolor='rgba(0,0,0,0)',
    font=dict(color='#E8E9ED', size=12),
    margin=dict(l=40, r=40, t=50, b=40),
)

# Per-match metric registry: key → (label, colour, axis). 'y2' (right axis,
# 0–100) holds the percentage metrics so they don't dwarf PPG/GF/GA on the left.
_TREND_METRICS = [
    ('gf',       'Goals Scored',        '#28a745', 'y'),
    ('ga',       'Goals Conceded',      '#dc3545', 'y'),
    ('ppda',     'PPDA',                AWAY_COLOR, 'y'),
    ('papp',     'Passes / Possession', '#cc5de8', 'y'),
    ('poss',     'Possession %',        HOME_COLOR, 'y2'),
    ('pass_acc', 'Pass Accuracy %',     '#5BC0BE', 'y2'),
]
_PCT_METRICS = {'poss', 'pass_acc'}


def _match_event_metrics(bar: pd.DataFrame, opp: pd.DataFrame) -> dict:
    """Per-match event-derived metrics keyed by match_id.

    Returns {match_id: {poss, pass_acc, ppda, papp}}. `bar` are Barcelona's
    events, `opp` the opponents'.
    """
    out: dict = {}
    if bar.empty or 'match_id' not in bar.columns:
        return out

    have_opp = (not opp.empty) and ('match_id' in opp.columns)
    for mid, te in bar.groupby('match_id'):
        oe = opp[opp['match_id'] == mid] if have_opp else pd.DataFrame()

        tp = te[te['event_type'] == 'Pass']
        op = oe[oe['event_type'] == 'Pass'] if not oe.empty else pd.DataFrame()
        n_tp, n_op = len(tp), len(op)

        poss = round(n_tp / max(n_tp + n_op, 1) * 100, 1)
        pass_acc = (round(tp['outcome'].eq(1).sum() / max(n_tp, 1) * 100, 1)
                    if 'outcome' in tp.columns and n_tp else 0.0)

        # PPDA — opponent passes in their own 60% ÷ our defensive actions in our
        # attacking 60% (canonical high-press definition in event_utils).
        ppda = compute_ppda(te, oe)

        # Passes per possession: completed passes ÷ possessions, where a
        # possession ends in a shot or a turnover.
        shots    = te[te['event_type'].isin(['Goal', 'Saved Shot', 'Miss', 'Post', 'Blocked Shot'])]
        disp     = te[te['event_type'] == 'Dispossessed']
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
            'gf':          r.get('barca_goals', 0),
            'ga':          r.get('opponent_goals', 0),
            'points':      pts,
            'competition': r.get('competition', ''),
            'poss':        m.get('poss'),
            'pass_acc':    m.get('pass_acc'),
            'ppda':        m.get('ppda'),
            'papp':        m.get('papp'),
        })
    return tl


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
            marker_colors = [_TREND_RESULT_C.get(t['result'], _TREND_GA_C) for t in timeline]
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
        **_TREND_LAYOUT,
        height=350,
        title=dict(text='Form Trendline', font=dict(color=GOLD, size=14)),
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


def _trendline_card(timeline: list[dict]) -> html.Div:
    """Form Trendline card — tournament filter + metric toggles + the graph."""
    comps_in_view: list[str] = []
    seen = set()
    for t in timeline:
        c = t.get('competition')
        if c and c not in seen:
            seen.add(c)
            comps_in_view.append(c)
    tourn_options = ([{'label': 'All Competitions', 'value': 'all'}] +
                     [{'label': c, 'value': c} for c in comps_in_view])

    return html.Div([
        html.Div('Form Trendline', style=_SEC_STYLE),

        # Tournament filter (mirrors the Home page).
        dbc.Row([
            dbc.Col([
                html.Label('Filter by Tournament:', style={
                    'color': COLORS['text_secondary'], 'fontSize': '0.8rem',
                    'marginRight': '0.5rem'}),
                dcc.Dropdown(
                    id='ta-summary-tourn',
                    options=tourn_options,
                    value='all',
                    clearable=False,
                    className='culevision-dropdown',
                    style={'width': '250px'},
                ),
            ], width='auto', className='d-flex align-items-center'),
        ], className='mb-2'),

        html.Div([
            html.Label('Metrics:', style={
                'color': COLORS['text_secondary'],
                'fontSize': '0.8rem', 'marginRight': '0.5rem'}),
            dcc.Checklist(
                id='ta-summary-metrics',
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
        ], className='mb-2'),

        dcc.Graph(id='ta-form-trendline',
                  figure=_form_trendline_fig(timeline, ['ppg']),
                  config=CHART_CONFIG),
        dcc.Store(id='ta-summary-timeline', data=timeline),
    ], style=_CARD)


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

    ppda = compute_ppda(bar, opp)

    pass_acc = (round(bar_passes['outcome'].eq(1).sum() / max(len(bar_passes), 1) * 100, 1)
                if not bar_passes.empty else 0.0)

    _all_ft_x  = pd.to_numeric(all_passes['x'], errors='coerce') if not all_passes.empty else pd.Series(dtype=float)
    _bar_ft_x  = pd.to_numeric(bar_passes['x'], errors='coerce') if not bar_passes.empty else pd.Series(dtype=float)
    _all_ft_n  = int((_all_ft_x.dropna() > 66.67).sum())
    _bar_ft_n  = int((_bar_ft_x.dropna() > 66.67).sum())
    field_tilt = round(_bar_ft_n / _all_ft_n * 100, 1) if _all_ft_n > 0 else 0.0

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

    # Row 2: Stat pills (GF · GA · CS · Matches · Pass Acc · Field Tilt)
    stat_pills = html.Div([
        _stat_pill(str(gf),               'Goals For',      GOLD),
        _stat_pill(str(ga),               'Goals Against',  AWAY_COLOR),
        _stat_pill(str(cs),               'Clean Sheets',   HOME_COLOR),
        _stat_pill(f'{pass_acc:.1f}%',    'Pass Accuracy',  GOLD),
        _stat_pill(f'{field_tilt:.1f}%',  'Field Tilt',     HOME_COLOR),
        _stat_pill(str(n_matches),        'Matches',        COLORS['text_secondary']),
    ], style={'display': 'flex', 'gap': '8px', 'marginBottom': '14px'})

    # Row 3: Phase cards strip
    phase_strip = dbc.Row([
        dbc.Col(
            _phase_card(
                title   = phase,
                tab     = phase,
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
    # League average for each competition in view, overlaid as dotted traces.
    comp_keys   = _comps_in_view(results)
    color_map   = _comp_color_map(comp_keys)
    league_avgs = _build_league_avgs(comp_keys, color_map)
    radar_card  = _radar_panel(comp_keys, _radar_fig(scores, 'Barça', league_avgs))

    timeline   = _season_timeline(results, _match_event_metrics(bar, opp))
    trend_card = _trendline_card(timeline)

    return html.Div([
        banner,
        stat_pills,
        phase_strip,
        dbc.Row([
            dbc.Col(radar_card, md=4),
            dbc.Col(trend_card, md=8),
        ], className='mb-3 g-2'),
    ])
