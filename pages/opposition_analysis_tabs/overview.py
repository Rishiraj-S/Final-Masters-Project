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

# NOTE: kept verbatim from the original radar logic so the displayed team score
# is unchanged. (These strings don't all match the raw Opta event_type spelling,
# but team and league-average traces use the *same* counting, so the comparison
# stays internally consistent.)
_GAIN_TYPES = {'Ball Recovery', 'Interception', 'Tackle Won'}


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

    gains = team_df[et.isin(_GAIN_TYPES)] if not team_df.empty else team_df
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

    # League average for each competition the team is in (within this view).
    if comp_key == 'all':
        comp_keys = sorted({r.get('competition_key') for r in all_results
                            if r.get('competition_key')})
    else:
        comp_keys = [comp_key]

    color_map   = _comp_color_map(comp_keys)
    league_avgs = _build_league_avgs(comp_keys, color_map)

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
        dbc.Col(_radar_panel(team, comp_keys,
                             _radar_fig(scores, team, league_avgs), _hdr, _panel),
                md=6, className='mb-3'),
        dbc.Col(html.Div([
            html.Div('Last 10 Matches — GF vs GA', style=_hdr),
            dcc.Graph(figure=_per_match_bar_fig(all_results), config=CHART_CONFIG, style={'width': '100%'}),
        ], style=_panel), md=6, className='mb-3'),
    ], className='g-3')

    children.append(charts_row)

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
