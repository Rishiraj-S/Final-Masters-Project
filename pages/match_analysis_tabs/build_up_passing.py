"""
build_up_passing.py
===================
Build-Up & Passing Structure tab.
Sections:
  1. Pass / Carry / Dribble Stats  (two per-team tables with Full/1H/2H)
  [Filters: Half]  — affect pitch plots only
  2. Pass Network   (interactive Plotly + mplsoccer bg, side-by-side)
  3. Entries into Final Third  (passes, dribbles, carries — interactive)
  4. Entries by Band           (passes, dribbles, carries — interactive)
  [All tables at bottom — unaffected by half filter]
  5. Top Combinations  (pairwise + 3-player)
  6. Player Zone Entries
"""
from __future__ import annotations

import io
import base64
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import matplotlib.pyplot as plt
from mplsoccer import Pitch as _MplPitch
from sklearn.preprocessing import MinMaxScaler
from dash import html, dcc, Input, Output
import dash_bootstrap_components as dbc

from utils.data_utils import get_match_events

from utils.config import COLORS
from utils.xt_utils import add_xt_column as _add_xt_column
from .shared import (
    build_legend_box,
    build_info_box,
    build_team_stats_table,
    CARD_STYLE,
    section_header,
)
from page_utils.visualizations import (
    HOME_COLOR,
    AWAY_COLOR,
    GOLD,
    CHART_CONFIG,
    layout_config,
    add_pitch_background,
    PITCH_AXIS_FULL,
    render_xt_heatmap_img,
)
from page_utils.event_filters import SHOT_TYPES as _SHOT_TYPES


# =============================================================================
# Pitch-zone / flank helpers
# =============================================================================

_ZONE_RANGES  = {'Def. Third': (0, 33.33), 'Mid Third': (33.33, 66.67), 'Fin. Third': (66.67, 100)}
_FLANK_RANGES = {'Left': (0, 33.33), 'Centre': (33.33, 66.67), 'Right': (66.67, 100)}


def _apply_filters(events: pd.DataFrame,
                   half:   str,
                   zones:  list[str],
                   flanks: list[str]) -> pd.DataFrame:
    """Return a filtered copy of events based on half, pitch zone and flank."""
    ev = events.copy()

    # Coerce coords to numeric
    for col in ('x', 'y', 'Pass End X', 'Pass End Y'):
        if col in ev.columns:
            ev[col] = pd.to_numeric(ev[col], errors='coerce')

    # Half filter
    if half == '1':
        ev = ev[ev['period_id'] == 1]
    elif half == '2':
        ev = ev[ev['period_id'] == 2]

    # Zone filter (on start x)
    if zones and set(zones) != set(_ZONE_RANGES):
        masks = []
        for z in zones:
            lo, hi = _ZONE_RANGES[z]
            masks.append((ev['x'] >= lo) & (ev['x'] <= hi))
        ev = ev[pd.concat(masks, axis=1).any(axis=1)]

    # Flank filter (on start y)
    if flanks and set(flanks) != set(_FLANK_RANGES):
        masks = []
        for f in flanks:
            lo, hi = _FLANK_RANGES[f]
            masks.append((ev['y'] >= lo) & (ev['y'] <= hi))
        ev = ev[pd.concat(masks, axis=1).any(axis=1)]

    return ev


# =============================================================================
# Data computation
# =============================================================================

def _count_si(df: pd.DataFrame, col: str) -> int:
    if col not in df.columns:
        return 0
    return int((df[col] == 'Si').sum())


def _build_network(te: pd.DataFrame):
    """Pass-network nodes + edges from sequential event data."""
    cols = ['player_name', 'event_type', 'outcome', 'x', 'y',
            'period_id', 'time_min', 'time_sec']
    ev = te[[c for c in cols if c in te.columns]].copy()
    ev = ev.dropna(subset=['player_name', 'x', 'y'])
    ev = ev.sort_values(['period_id', 'time_min', 'time_sec']).reset_index(drop=True)

    edges: dict[tuple, int] = {}
    for i in range(len(ev) - 1):
        row = ev.iloc[i]
        nxt = ev.iloc[i + 1]
        if (row['event_type'] == 'Pass' and row.get('outcome') == 1
                and pd.notna(nxt.get('player_name'))):
            a, b = str(row['player_name']), str(nxt['player_name'])
            if a != b:
                edges[(a, b)] = edges.get((a, b), 0) + 1

    edges = {k: v for k, v in edges.items() if v >= 2}

    pass_ev = ev[ev['event_type'] == 'Pass']
    if pass_ev.empty:
        return pd.DataFrame(), {}

    nodes = (
        pass_ev.groupby('player_name')
        .agg(x=('x', 'mean'), y=('y', 'mean'))
        .reset_index()
    )

    inv: dict[str, int] = {}
    for (a, b), cnt in edges.items():
        inv[a] = inv.get(a, 0) + cnt
        inv[b] = inv.get(b, 0) + cnt
    nodes['involvement'] = nodes['player_name'].map(lambda p: inv.get(p, 1))

    if len(nodes) > 1 and nodes['involvement'].max() > nodes['involvement'].min():
        sc = MinMaxScaler(feature_range=(14, 36))
        nodes['size'] = sc.fit_transform(nodes[['involvement']]).flatten()
    else:
        nodes['size'] = 22.0

    nodes['label'] = nodes['player_name'].apply(
        lambda n: n.split()[-1] if isinstance(n, str) else n)
    return nodes, edges


def _build_combos(te: pd.DataFrame) -> pd.DataFrame:
    """Top 8 passer → receiver combinations, with full / 1H / 2H counts."""
    ev = te[['player_name', 'event_type', 'outcome',
             'period_id', 'time_min', 'time_sec']].copy()
    ev = ev.dropna(subset=['player_name'])
    ev = ev.sort_values(['period_id', 'time_min', 'time_sec']).reset_index(drop=True)
    combos: dict[tuple, int] = {}
    combos_h1: dict[tuple, int] = {}
    combos_h2: dict[tuple, int] = {}
    for i in range(len(ev) - 1):
        row = ev.iloc[i]
        nxt = ev.iloc[i + 1]
        if (row['event_type'] == 'Pass' and row.get('outcome') == 1
                and pd.notna(nxt.get('player_name'))):
            a = str(row['player_name']).split()[-1]
            b = str(nxt['player_name']).split()[-1]
            if a != b:
                key = (a, b)
                combos[key] = combos.get(key, 0) + 1
                if row['period_id'] == 1:
                    combos_h1[key] = combos_h1.get(key, 0) + 1
                elif row['period_id'] == 2:
                    combos_h2[key] = combos_h2.get(key, 0) + 1
    if not combos:
        return pd.DataFrame(columns=['Combo', 'Total', 'H1', 'H2'])
    rows = [
        {'Combo': f'{a} -> {b}', 'Total': cnt,
         'H1': combos_h1.get((a, b), 0), 'H2': combos_h2.get((a, b), 0)}
        for (a, b), cnt in combos.items()
    ]
    return (pd.DataFrame(rows)
            .sort_values('Total', ascending=False)
            .head(8)
            .reset_index(drop=True))


def _build_3player_combos(te: pd.DataFrame) -> pd.DataFrame:
    """Top 8 three-player passer chains (A → B → C), with full / 1H / 2H counts."""
    ev = te[['player_name', 'event_type', 'outcome',
             'period_id', 'time_min', 'time_sec']].copy()
    ev = ev.dropna(subset=['player_name'])
    ev = ev.sort_values(['period_id', 'time_min', 'time_sec']).reset_index(drop=True)
    combos: dict[tuple, int] = {}
    combos_h1: dict[tuple, int] = {}
    combos_h2: dict[tuple, int] = {}
    for i in range(len(ev) - 2):
        r1 = ev.iloc[i]
        r2 = ev.iloc[i + 1]
        r3 = ev.iloc[i + 2]
        if (r1['event_type'] == 'Pass' and r1.get('outcome') == 1
                and r2['event_type'] == 'Pass' and r2.get('outcome') == 1
                and pd.notna(r2.get('player_name'))
                and pd.notna(r3.get('player_name'))):
            a = str(r1['player_name']).split()[-1]
            b = str(r2['player_name']).split()[-1]
            c = str(r3['player_name']).split()[-1]
            if a != b and b != c:
                key = (a, b, c)
                combos[key] = combos.get(key, 0) + 1
                if r1['period_id'] == 1:
                    combos_h1[key] = combos_h1.get(key, 0) + 1
                elif r1['period_id'] == 2:
                    combos_h2[key] = combos_h2.get(key, 0) + 1
    if not combos:
        return pd.DataFrame(columns=['Combo', 'Total', 'H1', 'H2'])
    rows = [
        {'Combo': f'{a} -> {b} -> {c}', 'Total': cnt,
         'H1': combos_h1.get((a, b, c), 0), 'H2': combos_h2.get((a, b, c), 0)}
        for (a, b, c), cnt in combos.items()
    ]
    return (pd.DataFrame(rows)
            .sort_values('Total', ascending=False)
            .head(8)
            .reset_index(drop=True))



def _build_4player_combos(te: pd.DataFrame) -> pd.DataFrame:
    """Top 8 four-player passer chains (A → B → C → D), with full / 1H / 2H counts."""
    ev = te[['player_name', 'event_type', 'outcome',
             'period_id', 'time_min', 'time_sec']].copy()
    ev = ev.dropna(subset=['player_name'])
    ev = ev.sort_values(['period_id', 'time_min', 'time_sec']).reset_index(drop=True)
    combos: dict[tuple, int] = {}
    combos_h1: dict[tuple, int] = {}
    combos_h2: dict[tuple, int] = {}
    for i in range(len(ev) - 3):
        r1 = ev.iloc[i]
        r2 = ev.iloc[i + 1]
        r3 = ev.iloc[i + 2]
        r4 = ev.iloc[i + 3]
        if (r1['event_type'] == 'Pass' and r1.get('outcome') == 1
                and r2['event_type'] == 'Pass' and r2.get('outcome') == 1
                and r3['event_type'] == 'Pass' and r3.get('outcome') == 1
                and pd.notna(r2.get('player_name'))
                and pd.notna(r3.get('player_name'))
                and pd.notna(r4.get('player_name'))):
            a = str(r1['player_name']).split()[-1]
            b = str(r2['player_name']).split()[-1]
            c = str(r3['player_name']).split()[-1]
            d = str(r4['player_name']).split()[-1]
            if a != b and b != c and c != d:
                key = (a, b, c, d)
                combos[key] = combos.get(key, 0) + 1
                if r1['period_id'] == 1:
                    combos_h1[key] = combos_h1.get(key, 0) + 1
                elif r1['period_id'] == 2:
                    combos_h2[key] = combos_h2.get(key, 0) + 1
    if not combos:
        return pd.DataFrame(columns=['Combo', 'Total', 'H1', 'H2'])
    rows = [
        {'Combo': f'{a} -> {b} -> {c} -> {d}', 'Total': cnt,
         'H1': combos_h1.get((a, b, c, d), 0), 'H2': combos_h2.get((a, b, c, d), 0)}
        for (a, b, c, d), cnt in combos.items()
    ]
    return (pd.DataFrame(rows)
            .sort_values('Total', ascending=False)
            .head(8)
            .reset_index(drop=True))


def _build_entries(te: pd.DataFrame, zone: str = 'final_third') -> pd.DataFrame:
    """Build a DataFrame of entries (passes, dribbles, carries) into a target zone.

    Args:
        te:   team events — Opta coordinates are per-team normalised (x=0 own goal,
              x=100 opponent goal), so no coordinate flip is applied or needed.
        zone: 'final_third' or 'zone14'

    Returns:
        DataFrame with columns: player_name, event_label, x, y, end_x, end_y,
                                outcome, time_min, time_sec, period_id,
                                dest_zone, led_to_shot, led_to_goal
    """
    # Full sorted event list for shot/goal look-ahead.
    # IMPORTANT: reset_index(drop=True) here so row positions are 0-based integers.
    te_full = te.sort_values(['period_id', 'time_min', 'time_sec']).reset_index(drop=True)

    relevant_types = ['Pass', 'Take On', 'Ball touch']
    # reset_index() (without drop=True) preserves the old integer index as a column
    # named 'index'. This is used below as a pointer back into te_full rows.
    # Callers MUST pass te with a clean 0-based integer index (reset_index(drop=True))
    # or the 'index' column will not correctly map back to te_full positions.
    ev = (te_full[te_full['event_type'].isin(relevant_types)]
          .dropna(subset=['x', 'y'])
          .reset_index())          # 'index' col = row position in te_full

    entries = []
    for i in range(len(ev)):
        row = ev.iloc[i]
        etype = row['event_type']
        start_x = float(row['x'])

        if etype == 'Pass':
            if pd.notna(row.get('Pass End X')):
                end_x = float(row['Pass End X'])
                end_y = float(row['Pass End Y'])
            else:
                continue
        else:
            # For carries (Ball touch) and dribbles (Take On), infer end from next event
            if i + 1 < len(ev):
                nxt = ev.iloc[i + 1]
                end_x = float(nxt['x'])
                end_y = float(nxt['y'])
            else:
                continue

        start_y = float(row['y'])

        # Check zone crossing
        dest_zone = None
        if zone == 'final_third':
            if not (start_x < 66.67 and end_x >= 66.67):
                continue
            dest_zone = ('Left Band'   if end_y > 66.67
                         else 'Right Band' if end_y < 33.33
                         else 'Centre Band')
        elif zone == 'zone14':
            in_z14 = (66.67 <= end_x <= 83.33) and (37 <= end_y <= 63)
            in_lhs = (end_x > 66.67) and (63 < end_y <= 79)
            in_rhs = (end_x > 66.67) and (21 <= end_y < 37)
            if not (in_z14 or in_lhs or in_rhs):
                continue
            dest_zone = ('Left Band'   if end_y > 66.67
                         else 'Right Band' if end_y < 33.33
                         else 'Centre Band')

        # Map event type to friendly label
        label_map = {'Pass': 'Pass', 'Take On': 'Dribble', 'Ball touch': 'Carry'}
        outcome  = row.get('outcome', None)
        time_min = row.get('time_min', 0)
        time_sec = row.get('time_sec', 0)

        # Check if a shot or goal occurs in the next 5 events (same team)
        te_idx   = int(row['index'])
        next_5   = te_full.iloc[te_idx + 1 : te_idx + 6]
        led_to_shot = bool(next_5['event_type'].isin(_SHOT_TYPES).any()) if not next_5.empty else False
        led_to_goal = bool((next_5['event_type'] == 'Goal').any())       if not next_5.empty else False

        # Receiver name — for successful passes, from the next event in team timeline
        receiver_name = ''
        if etype == 'Pass' and outcome == 1 and te_idx + 1 < len(te_full):
            nxt_full = te_full.iloc[te_idx + 1]
            if pd.notna(nxt_full.get('player_name')):
                receiver_name = str(nxt_full['player_name'])

        entries.append({
            'player_name':   row.get('player_name', ''),
            'event_label':   label_map.get(etype, etype),
            'x':             start_x,
            'y':             start_y,
            'end_x':         end_x,
            'end_y':         end_y,
            'outcome':       outcome,
            'time_min':      time_min,
            'time_sec':      time_sec,
            'period_id':     row.get('period_id', 0),
            'dest_zone':     dest_zone,
            'led_to_shot':   led_to_shot,
            'led_to_goal':   led_to_goal,
            'receiver_name': receiver_name,
        })

    if not entries:
        return pd.DataFrame(columns=[
            'player_name', 'event_label', 'x', 'y', 'end_x', 'end_y',
            'outcome', 'time_min', 'time_sec', 'period_id', 'dest_zone',
            'led_to_shot', 'led_to_goal', 'receiver_name',
        ])
    return pd.DataFrame(entries)


def _compute(events: pd.DataFrame) -> dict:
    home_team = events['home_team'].iloc[0]
    away_team = events['away_team'].iloc[0]
    out = {}

    for pos, team in (('home', home_team), ('away', away_team)):
        te = events[events['team_position'] == pos].copy().reset_index(drop=True)

        for col in ('x', 'y', 'Pass End X', 'Pass End Y'):
            if col in te.columns:
                te[col] = pd.to_numeric(te[col], errors='coerce')

        passes   = te[te['event_type'] == 'Pass']
        succ_p   = passes[passes['outcome'] == 1]
        carries  = te[te['event_type'] == 'Ball touch']
        dribbles = te[te['event_type'] == 'Take On']
        succ_d   = dribbles[dribbles['outcome'] == 1]

        total_p = len(passes)
        total_d = len(dribbles)

        into_ft = 0
        if 'Pass End X' in passes.columns:
            into_ft = int((passes['Pass End X'].dropna() > 66.67).sum())

        nodes, edges = _build_network(te)
        combos = _build_combos(te)
        combos3 = _build_3player_combos(te)
        combos4 = _build_4player_combos(te)

        # Entries data
        entries_ft = _build_entries(te, zone='final_third')
        entries_z14 = _build_entries(te, zone='zone14')

        # Per-player dribble stats
        if not dribbles.empty and 'player_name' in dribbles.columns:
            _drib_grp = (
                dribbles.groupby('player_name', as_index=False)
                .agg(attempts=('outcome', 'count'),
                     successful=('outcome', lambda s: int((s == 1).sum())))
            )
            _drib_grp['success_rate'] = (
                _drib_grp['successful'] / _drib_grp['attempts'] * 100
            ).round(1)
            player_drib_stats = (
                _drib_grp.sort_values('attempts', ascending=False)
                .head(8).reset_index(drop=True)
            )
        else:
            player_drib_stats = pd.DataFrame(
                columns=['player_name', 'attempts', 'successful', 'success_rate']
            )

        # ── Possession touch map data ─────────────────────────────────────
        touches = te.dropna(subset=['x', 'y'])
        touch_x = touches['x'].tolist()
        touch_y = touches['y'].tolist()

        # Per-player possession %: share of team's total touch-events
        if not touches.empty and 'player_name' in touches.columns:
            total_t = max(len(touches), 1)
            t_h1 = touches[touches['period_id'] == 1] if 'period_id' in touches.columns else pd.DataFrame()
            t_h2 = touches[touches['period_id'] == 2] if 'period_id' in touches.columns else pd.DataFrame()
            total_h1 = max(len(t_h1), 1)
            total_h2 = max(len(t_h2), 1)

            g_tot = touches.groupby('player_name').size().rename('total')
            g_h1  = (t_h1.groupby('player_name').size().rename('h1')
                     if not t_h1.empty else pd.Series(dtype=float, name='h1'))
            g_h2  = (t_h2.groupby('player_name').size().rename('h2')
                     if not t_h2.empty else pd.Series(dtype=float, name='h2'))
            poss_df = pd.concat([g_tot, g_h1, g_h2], axis=1).fillna(0).reset_index()
            poss_df.columns = ['player_name', 'total', 'h1', 'h2']
            poss_df['pct']    = (poss_df['total'] / total_t  * 100).round(1)
            poss_df['pct_h1'] = (poss_df['h1']    / total_h1 * 100).round(1)
            poss_df['pct_h2'] = (poss_df['h2']    / total_h2 * 100).round(1)
            poss_df = (poss_df.sort_values('pct', ascending=False)
                       .head(12).reset_index(drop=True))
        else:
            poss_df = pd.DataFrame(
                columns=['player_name', 'total', 'h1', 'h2', 'pct', 'pct_h1', 'pct_h2'])

        out[pos] = {
            'team':     team,
            'passes':   total_p,
            'pass_acc': round(len(succ_p) / total_p * 100, 1) if total_p else 0.0,
            'long_balls':  _count_si(passes, 'Long ball'),
            'crosses':     _count_si(passes, 'Cross'),
            'thru_balls':  _count_si(passes, 'Through ball'),
            'into_ft':     into_ft,
            'carries': len(carries),
            'dribbles':  total_d,
            'drib_succ': len(succ_d),
            'drib_acc':  round(len(succ_d) / total_d * 100, 1) if total_d else 0.0,
            'player_drib_stats': player_drib_stats,
            'nodes':  nodes,
            'edges':  edges,
            'combos': combos,
            'combos3': combos3,
            'combos4': combos4,
            'entries_ft':  entries_ft,
            'entries_z14': entries_z14,
            'touch_x':     touch_x,
            'touch_y':     touch_y,
            'player_poss_df': poss_df,
        }
    return out


def _compute_half_stats(events: pd.DataFrame, pos: str, period: int | None = None) -> dict:
    """Compute passing / carry / dribble stats for a single team, optionally per-half."""
    home_team = events['home_team'].iloc[0]
    away_team = events['away_team'].iloc[0]
    team = home_team if pos == 'home' else away_team

    te = events[events['team_position'] == pos].copy()
    if period is not None:
        te = te[te['period_id'] == period]

    for col in ('x', 'y', 'Pass End X', 'Pass End Y'):
        if col in te.columns:
            te[col] = pd.to_numeric(te[col], errors='coerce')

    passes   = te[te['event_type'] == 'Pass']
    succ_p   = passes[passes['outcome'] == 1]
    carries  = te[te['event_type'] == 'Ball touch']
    dribbles = te[te['event_type'] == 'Take On']
    succ_d   = dribbles[dribbles['outcome'] == 1]

    total_p = len(passes)
    total_d = len(dribbles)

    into_ft = 0
    if 'Pass End X' in passes.columns:
        into_ft = int((passes['Pass End X'].dropna() > 66.67).sum())

    total_xt = round(float(_add_xt_column(passes)['xT'].sum()), 3) if total_p > 0 else 0.0

    return {
        'team':       team,
        'passes':     total_p,
        'pass_acc':   round(len(succ_p) / total_p * 100, 1) if total_p else 0.0,
        'long_balls': _count_si(passes, 'Long ball'),
        'crosses':    _count_si(passes, 'Cross'),
        'thru_balls': _count_si(passes, 'Through ball'),
        'into_ft':    into_ft,
        'total_xt':   total_xt,
        'carries':    len(carries),
        'dribbles':   total_d,
        'drib_succ':  len(succ_d),
        'drib_acc':   round(len(succ_d) / total_d * 100, 1) if total_d else 0.0,
    }


# =============================================================================
# Figure builders
# =============================================================================

_PITCH_HEIGHT = 480  # px — slightly larger for better football pitch ratio

_ENTRY_COLORS = {
    'Pass':    '#32cd32',
    'Dribble': '#ffa500',
    'Carry':   '#00bfff',
}

_BAND_COLORS = {
    'Left Band':   '#00ffff',
    'Centre Band': '#ff1493',
    'Right Band':  '#ffd700',
}


def _add_attack_direction(fig: go.Figure, **_) -> None:
    """Add direction-of-attack label above the pitch, centred horizontally."""
    fig.add_annotation(
        x=0.5, y=1.0, xref='paper', yref='paper',
        xanchor='center', yanchor='bottom',
        text='➡ Direction of Attack',
        showarrow=False,
        font=dict(color='black', size=16, family='Arial'),
        align='center',
        bgcolor='rgba(255,255,255,0.7)',
        borderpad=3,
    )


def _network_fig(nodes: pd.DataFrame, edges: dict, color: str, is_home: bool = True) -> go.Figure:
    fig = go.Figure()
    add_pitch_background(fig)

    if edges:
        max_cnt = max(edges.values())
        for (a, b), cnt in edges.items():
            an = nodes[nodes['player_name'] == a]
            bn = nodes[nodes['player_name'] == b]
            if an.empty or bn.empty:
                continue
            x0, y0 = float(an.iloc[0]['x']), float(an.iloc[0]['y'])
            x1, y1 = float(bn.iloc[0]['x']), float(bn.iloc[0]['y'])
            width = 1.0 + (cnt / max_cnt) * 5.0

            # Edge hover at midpoint — single invisible marker carrying the count
            if (b, a) in edges:
                dx, dy   = x1 - x0, y1 - y0
                length   = (dx**2 + dy**2) ** 0.5 or 1.0
                ox, oy   = -dy / length * 2.5, dx / length * 2.5
                xm, ym   = (x0 + x1) / 2 + ox, (y0 + y1) / 2 + oy
                t        = np.linspace(0, 1, 25)
                cx = (1-t)**2 * x0 + 2*(1-t)*t * xm + t**2 * x1
                cy = (1-t)**2 * y0 + 2*(1-t)*t * ym + t**2 * y1
            else:
                cx, cy = [x0, x1], [y0, y1]
                xm, ym = (x0 + x1) / 2, (y0 + y1) / 2

            fig.add_trace(go.Scatter(
                x=cx, y=cy, mode='lines',
                line=dict(color=color, width=width),
                opacity=0.55, hoverinfo='skip', showlegend=False,
            ))
            # Midpoint hover bubble (transparent, captures edge hover)
            short_a = str(a).split()[-1]
            short_b = str(b).split()[-1]
            fig.add_trace(go.Scatter(
                x=[xm], y=[ym], mode='markers',
                marker=dict(size=14, color='rgba(0,0,0,0)', opacity=0),
                customdata=[[short_a, short_b, cnt]],
                hovertemplate=(
                    '<b>%{customdata[0]} → %{customdata[1]}</b><br>'
                    'Passes: %{customdata[2]}'
                    '<extra></extra>'
                ),
                showlegend=False,
            ))

    if not nodes.empty:
        fig.add_trace(go.Scatter(
            x=nodes['x'], y=nodes['y'],
            mode='markers+text',
            marker=dict(size=nodes['size'], color=color,
                        line=dict(width=2, color='white')),
            text=nodes['label'],
            textposition='middle center',
            textfont=dict(size=8, color='white', family='Arial Black'),
            customdata=nodes[['player_name', 'involvement']].values,
            hovertemplate=(
                '<b>%{customdata[0]}</b><br>'
                'Pass involvement: %{customdata[1]:.0f} connections'
                '<extra></extra>'
            ),
            showlegend=False,
        ))

    # ── Legend: node sizes (use itemsizing='trace' to show actual sizes) ──
    for size, label in ((34, 'High involvement'), (22, 'Medium'), (14, 'Low')):
        fig.add_trace(go.Scatter(
            x=[None], y=[None], mode='markers',
            marker=dict(size=size, color=color, line=dict(width=2, color='white')),
            name=label, showlegend=True, legendgroup='nodes',
        ))
    # ── Legend: line widths ───────────────────────────────────────────────
    for width, label in ((6.0, 'Frequent (≥8)'),
                         (3.5, 'Moderate (4–7)'),
                         (1.0, 'Occasional (2–3)')):
        fig.add_trace(go.Scatter(
            x=[None], y=[None], mode='lines',
            line=dict(color=color, width=width),
            name=label, showlegend=True, legendgroup='edges',
        ))

    _add_attack_direction(fig, is_home=is_home)
    fig.update_layout(
        **PITCH_AXIS_FULL,
        **layout_config(
            height=_PITCH_HEIGHT, margin=dict(l=0, r=0, t=48, b=0),
            legend=dict(
                orientation='v', x=0.01, xanchor='left', y=0.99, yanchor='top',
                bgcolor='rgba(0,0,0,0.55)',
                font=dict(color=COLORS['text_primary'], size=9),
                itemsizing='trace',
            ),
        ),
        hovermode='closest',
    )
    return fig


def _entries_fig(entries_df: pd.DataFrame, zone: str,
                 color: str, is_home: bool = True) -> go.Figure:
    """Interactive Plotly pitch figure for entries into final third, coloured by band."""
    fig = go.Figure()
    add_pitch_background(fig)

    if not entries_df.empty:
        entries_df = entries_df.copy()
        entries_df['time_display'] = entries_df.apply(
            lambda r: f"{int(r['time_min'])}:{int(r['time_sec']):02d}", axis=1
        )
        entries_df['outcome_label'] = entries_df['outcome'].map(
            {1: '✓ Successful', 0: '✗ Unsuccessful'}
        ).fillna('—')
        entries_df['shot_label'] = entries_df.apply(
            lambda r: '<br>⚽ Led to Goal'
                      if r.get('led_to_goal', False)
                      else ('<br>🎯 Led to Shot' if r.get('led_to_shot', False) else ''),
            axis=1,
        )
        if 'receiver_name' not in entries_df.columns:
            entries_df['receiver_name'] = ''

        if 'dest_zone' in entries_df.columns and entries_df['dest_zone'].notna().any():
            color_iter = _BAND_COLORS.items()
            group_col  = 'dest_zone'
        else:
            color_iter = _ENTRY_COLORS.items()
            group_col  = 'event_label'

        for group_name, ecolor in color_iter:
            subset = entries_df[entries_df[group_col] == group_name]
            if subset.empty:
                continue

            passes_sub    = subset[subset['event_label'] == 'Pass']
            nonpasses_sub = subset[subset['event_label'] != 'Pass']

            # ── Arrow / line drawing ──────────────────────────────────────
            if zone == 'zone14':
                # Passes → solid annotation arrows
                for _, row in passes_sub.iterrows():
                    fig.add_annotation(
                        x=row['end_x'], y=row['end_y'],
                        ax=row['x'], ay=row['y'],
                        xref='x', yref='y', axref='x', ayref='y',
                        showarrow=True, arrowhead=2, arrowsize=1.5,
                        arrowwidth=2, arrowcolor=ecolor, opacity=0.65,
                    )
                # Dribbles / Carries → dashed scatter lines (batched)
                if not nonpasses_sub.empty:
                    xs, ys = [], []
                    for _, row in nonpasses_sub.iterrows():
                        xs.extend([row['x'], row['end_x'], None])
                        ys.extend([row['y'], row['end_y'], None])
                    fig.add_trace(go.Scatter(
                        x=xs, y=ys, mode='lines',
                        line=dict(color=ecolor, width=2, dash='dash'),
                        showlegend=False, hoverinfo='skip',
                    ))
            else:
                # Final third → all solid annotation arrows (existing behaviour)
                for _, row in subset.iterrows():
                    fig.add_annotation(
                        x=row['end_x'], y=row['end_y'],
                        ax=row['x'], ay=row['y'],
                        xref='x', yref='y', axref='x', ayref='y',
                        showarrow=True, arrowhead=2, arrowsize=1.5,
                        arrowwidth=2, arrowcolor=ecolor, opacity=0.65,
                    )

            # ── Scatter hover traces ──────────────────────────────────────
            legend_name = f'{group_name} ({len(subset)})'
            legend_shown = False

            # Passes — show passer → receiver
            if not passes_sub.empty:
                if zone == 'zone14':
                    cd = passes_sub[['player_name', 'receiver_name', 'event_label',
                                     'time_display', 'outcome_label', 'shot_label']].values
                    ht = (
                        f'<b>{group_name}</b><br>'
                        'Pass: %{customdata[0]} → %{customdata[1]}<br>'
                        'Time: %{customdata[3]}<br>'
                        '%{customdata[4]}'
                        '%{customdata[5]}'
                        '<extra></extra>'
                    )
                else:
                    cd = passes_sub[['player_name', 'receiver_name',
                                     'time_display', 'outcome_label', 'shot_label']].values
                    ht = (
                        f'<b>{group_name}</b><br>'
                        '%{customdata[0]} → %{customdata[1]}<br>'
                        'Time: %{customdata[2]}<br>'
                        '%{customdata[3]}'
                        '%{customdata[4]}'
                        '<extra></extra>'
                    )
                fig.add_trace(go.Scatter(
                    x=passes_sub['end_x'], y=passes_sub['end_y'],
                    mode='markers',
                    marker=dict(size=8, color=ecolor, line=dict(width=1.5, color='white')),
                    customdata=cd,
                    hovertemplate=ht,
                    name=legend_name, showlegend=True,
                    legendgroup=group_name,
                ))
                legend_shown = True

            # Non-passes — player only
            if not nonpasses_sub.empty:
                if zone == 'zone14':
                    cd = nonpasses_sub[['player_name', 'event_label',
                                        'time_display', 'outcome_label', 'shot_label']].values
                    ht = (
                        f'<b>{group_name}</b><br>'
                        '%{customdata[1]}: %{customdata[0]}<br>'
                        'Time: %{customdata[2]}<br>'
                        '%{customdata[3]}'
                        '%{customdata[4]}'
                        '<extra></extra>'
                    )
                else:
                    cd = nonpasses_sub[['player_name',
                                        'time_display', 'outcome_label', 'shot_label']].values
                    ht = (
                        f'<b>{group_name}</b><br>'
                        '%{customdata[0]}<br>'
                        'Time: %{customdata[1]}<br>'
                        '%{customdata[2]}'
                        '%{customdata[3]}'
                        '<extra></extra>'
                    )
                fig.add_trace(go.Scatter(
                    x=nonpasses_sub['end_x'], y=nonpasses_sub['end_y'],
                    mode='markers',
                    marker=dict(size=8, color=ecolor, line=dict(width=1.5, color='white')),
                    customdata=cd,
                    hovertemplate=ht,
                    name=legend_name if not legend_shown else '',
                    showlegend=not legend_shown,
                    legendgroup=group_name,
                ))

    # Draw zone boundaries
    if zone == 'final_third':
        fig.add_shape(
            type='line', x0=66.67, y0=0, x1=66.67, y1=100,
            line=dict(color='yellow', width=2, dash='dash'),
        )
        fig.add_shape(
            type='line', x0=0, y0=66.67, x1=100, y1=66.67,
            line=dict(color='white', width=1.5, dash='dot'),
        )
        fig.add_shape(
            type='line', x0=0, y0=33.33, x1=100, y1=33.33,
            line=dict(color='white', width=1.5, dash='dot'),
        )
        fig.add_annotation(
            x=4, y=83, text='Left Band', showarrow=False,
            font=dict(color='#00ffff', size=9, family='Arial Black'),
            bgcolor='rgba(0,0,0,0.5)', borderpad=2,
        )
        fig.add_annotation(
            x=4, y=50, text='Centre Band', showarrow=False,
            font=dict(color='#ff1493', size=9, family='Arial Black'),
            bgcolor='rgba(0,0,0,0.5)', borderpad=2,
        )
        fig.add_annotation(
            x=4, y=17, text='Right Band', showarrow=False,
            font=dict(color='#ffd700', size=9, family='Arial Black'),
            bgcolor='rgba(0,0,0,0.5)', borderpad=2,
        )
    elif zone == 'zone14':
        fig.add_shape(
            type='rect', x0=66.67, y0=37, x1=83.33, y1=63,
            line=dict(color='rgba(255,255,255,0.25)', width=1, dash='dash'),
            fillcolor='rgba(255,255,255,0.03)',
        )
        fig.add_shape(
            type='rect', x0=66.67, y0=63, x1=100, y1=79,
            line=dict(color='rgba(255,255,255,0.25)', width=1, dash='dash'),
            fillcolor='rgba(255,255,255,0.03)',
        )
        fig.add_shape(
            type='rect', x0=66.67, y0=21, x1=100, y1=37,
            line=dict(color='rgba(255,255,255,0.25)', width=1, dash='dash'),
            fillcolor='rgba(255,255,255,0.03)',
        )
        fig.add_annotation(
            x=75, y=50, text='Zone 14', showarrow=False,
            font=dict(color='rgba(255,255,255,0.35)', size=8, family='Arial'),
            bgcolor='rgba(0,0,0,0)', borderpad=2,
        )
        fig.add_shape(
            type='line', x0=0, y0=66.67, x1=100, y1=66.67,
            line=dict(color='white', width=1.5, dash='dot'),
        )
        fig.add_shape(
            type='line', x0=0, y0=33.33, x1=100, y1=33.33,
            line=dict(color='white', width=1.5, dash='dot'),
        )
        fig.add_annotation(
            x=4, y=83, text='Left Band', showarrow=False,
            font=dict(color='#00ffff', size=9, family='Arial Black'),
            bgcolor='rgba(0,0,0,0.5)', borderpad=2,
        )
        fig.add_annotation(
            x=4, y=50, text='Centre Band', showarrow=False,
            font=dict(color='#ff1493', size=9, family='Arial Black'),
            bgcolor='rgba(0,0,0,0.5)', borderpad=2,
        )
        fig.add_annotation(
            x=4, y=17, text='Right Band', showarrow=False,
            font=dict(color='#ffd700', size=9, family='Arial Black'),
            bgcolor='rgba(0,0,0,0.5)', borderpad=2,
        )

    _add_attack_direction(fig, is_home=is_home)

    fig.update_layout(
        **PITCH_AXIS_FULL,
        **layout_config(
            height=_PITCH_HEIGHT, margin=dict(l=0, r=0, t=48, b=0),
            legend=dict(
                orientation='v', x=0.99, xanchor='right', y=0.99, yanchor='top',
                bgcolor='rgba(0,0,0,0.55)',
                font=dict(color=COLORS['text_primary'], size=9),
            ),
        ),
        hovermode='closest',
    )
    return fig


# =============================================================================
# UI helpers
# =============================================================================




def _combo_table(combos: pd.DataFrame, color: str) -> html.Div:
    """Passing combination table — Combination | N (1H / 2H)."""
    if combos.empty:
        return html.Div('No data', style={
            'color': COLORS['text_secondary'], 'fontSize': '0.8rem',
            'textAlign': 'center', 'marginTop': '12px',
        })
    _th = {
        'color': COLORS['text_secondary'], 'fontSize': '0.65rem',
        'fontWeight': '600', 'padding': '5px 8px',
        'borderBottom': f'1px solid {COLORS["dark_border"]}',
        'textTransform': 'uppercase',
    }
    header = html.Tr([
        html.Th('Combination', style=_th),
        html.Th('N (1H / 2H)', style={**_th, 'textAlign': 'right'}),
    ])
    rows = []
    for i, row in combos.iterrows():
        bg = COLORS.get('dark_tertiary', 'rgba(255,255,255,0.03)') if i % 2 == 0 else 'transparent'
        count_str = f"{int(row['Total'])} ({int(row['H1'])} / {int(row['H2'])})"
        rows.append(html.Tr([
            html.Td(row['Combo'], style={
                'color': color, 'fontSize': '0.78rem',
                'padding': '4px 8px', 'fontWeight': '500',
            }),
            html.Td(count_str, style={
                'color': COLORS['text_primary'], 'fontSize': '0.78rem',
                'padding': '4px 8px', 'textAlign': 'right', 'fontWeight': '600',
            }),
        ], style={'backgroundColor': bg}))
    return html.Div(
        html.Table([html.Thead(header), html.Tbody(rows)],
                   style={'width': '100%', 'borderCollapse': 'collapse'}),
        style={'overflowX': 'auto'},
    )


def _pitch_card(title: str, fig: go.Figure, color: str) -> dbc.Col:
    return dbc.Col(
        html.Div([
            html.Div(title, style={
                'color': color, 'fontWeight': '600',
                'fontSize': '0.85rem', 'marginBottom': '8px',
                'textAlign': 'center',
            }),
            dcc.Graph(figure=fig, config=CHART_CONFIG),
        ], style=CARD_STYLE),
        md=6, className='mb-3',
    )


def _build_player_entries_table(entries_ft: pd.DataFrame, entries_z14: pd.DataFrame) -> pd.DataFrame:
    """Aggregate per-player entry counts with 1H/2H breakdown.

    Returns DataFrame with columns:
        player_name, ft_total, ft_h1, ft_h2,
        z14_total, z14_h1, z14_h2,
        lhs_total, lhs_h1, lhs_h2,
        rhs_total, rhs_h1, rhs_h2
    """
    def _counts(df: pd.DataFrame, zone_filter=None) -> pd.DataFrame:
        if df.empty:
            return pd.DataFrame(columns=['player_name', 'total', 'h1', 'h2'])
        d = df.copy()
        if zone_filter is not None:
            d = d[d['dest_zone'] == zone_filter]
        if d.empty:
            return pd.DataFrame(columns=['player_name', 'total', 'h1', 'h2'])
        grp = d.groupby('player_name')
        total = grp.size().rename('total')
        h1 = grp.apply(lambda g: (g['period_id'] == 1).sum()).rename('h1')
        h2 = grp.apply(lambda g: (g['period_id'] == 2).sum()).rename('h2')
        return pd.concat([total, h1, h2], axis=1).reset_index()

    ft  = _counts(entries_ft)
    lb  = _counts(entries_z14, 'Left Band')
    cb  = _counts(entries_z14, 'Centre Band')
    rb  = _counts(entries_z14, 'Right Band')

    # Collect all players
    all_players = set()
    for df in [ft, lb, cb, rb]:
        if not df.empty:
            all_players.update(df['player_name'].tolist())
    if not all_players:
        return pd.DataFrame()

    result = pd.DataFrame({'player_name': sorted(all_players)})
    for prefix, df in [('ft', ft), ('lb', lb), ('cb', cb), ('rb', rb)]:
        if df.empty:
            result[f'{prefix}_total'] = 0
            result[f'{prefix}_h1']    = 0
            result[f'{prefix}_h2']    = 0
        else:
            merged = result.merge(df.rename(columns={'total': f'{prefix}_total',
                                                      'h1': f'{prefix}_h1',
                                                      'h2': f'{prefix}_h2'}),
                                  on='player_name', how='left')
            result = merged.fillna(0)
            for c in [f'{prefix}_total', f'{prefix}_h1', f'{prefix}_h2']:
                result[c] = result[c].astype(int)

    # Sort by total entries descending
    result['_grand_total'] = result['ft_total'] + result['lb_total'] + result['cb_total'] + result['rb_total']
    result = result[result['_grand_total'] > 0].sort_values('_grand_total', ascending=False).drop(columns='_grand_total').reset_index(drop=True)
    return result


def _player_entries_table(df: pd.DataFrame, color: str) -> html.Div:
    """Per-player zone-entry counts table with (1H/2H) breakdown."""
    _hdr = {
        'textAlign': 'center', 'padding': '6px 8px',
        'fontSize': '0.63rem', 'fontWeight': '700',
        'color': COLORS['text_secondary'],
        'textTransform': 'uppercase', 'letterSpacing': '0.06em',
        'borderBottom': f'1px solid {COLORS["dark_border"]}',
        'whiteSpace': 'nowrap',
    }
    _lbl = {
        'padding': '5px 8px', 'fontSize': '0.77rem',
        'color': COLORS['text_primary'], 'whiteSpace': 'nowrap',
        'maxWidth': '150px', 'overflow': 'hidden', 'textOverflow': 'ellipsis',
    }
    _val = {
        'textAlign': 'center', 'padding': '5px 8px',
        'fontSize': '0.76rem', 'fontWeight': '600',
        'color': COLORS['text_primary'], 'whiteSpace': 'nowrap',
    }

    if df.empty:
        return html.Div('No entry data', style={
            'color': COLORS['text_secondary'], 'fontSize': '0.8rem',
            'textAlign': 'center', 'marginTop': '8px',
        })

    def _fmt(total, h1, h2):
        return f"{int(total)}({int(h1)}/{int(h2)})"

    header = html.Tr([
        html.Th('Player',        style={**_hdr, 'textAlign': 'left'}),
        html.Th('Final Third',   style=_hdr),
        html.Th('Left Band',     style=_hdr),
        html.Th('Centre Band',   style=_hdr),
        html.Th('Right Band',    style=_hdr),
    ])
    rows = []
    for i, row in df.iterrows():
        bg = (COLORS.get('dark_tertiary', 'rgba(255,255,255,0.03)')
              if i % 2 == 0 else 'transparent')
        short_name = str(row['player_name']).split()[-1] if pd.notna(row['player_name']) else '—'
        rows.append(html.Tr([
            html.Td(short_name, style={**_lbl, 'color': color}),
            html.Td(_fmt(row['ft_total'], row['ft_h1'], row['ft_h2']), style=_val),
            html.Td(_fmt(row['lb_total'], row['lb_h1'], row['lb_h2']), style=_val),
            html.Td(_fmt(row['cb_total'], row['cb_h1'], row['cb_h2']), style=_val),
            html.Td(_fmt(row['rb_total'], row['rb_h1'], row['rb_h2']), style=_val),
        ], style={'backgroundColor': bg}))

    return html.Div(
        html.Table(
            [html.Thead(header), html.Tbody(rows)],
            style={'width': '100%', 'borderCollapse': 'collapse'},
        ),
        style={'overflowX': 'auto'},
    )


def _player_possession_table(poss_df: pd.DataFrame, color: str) -> html.Div:
    """Per-player possession % table — format: total%(1H%/2H%)."""
    if poss_df.empty:
        return html.Div('No data', style={
            'color': COLORS['text_secondary'], 'fontSize': '0.8rem',
            'textAlign': 'center', 'marginTop': '12px',
        })

    _hdr = {
        'fontSize': '0.65rem', 'fontWeight': '700', 'padding': '5px 8px',
        'color': COLORS['text_secondary'], 'textTransform': 'uppercase',
        'letterSpacing': '0.04em',
        'borderBottom': f'1px solid {COLORS["dark_border"]}',
    }
    _lbl = {
        'padding': '4px 8px', 'fontSize': '0.77rem',
        'color': COLORS['text_primary'], 'whiteSpace': 'nowrap',
    }
    _val = {
        'textAlign': 'right', 'padding': '4px 8px',
        'fontSize': '0.76rem', 'fontWeight': '600',
        'color': COLORS['text_primary'], 'whiteSpace': 'nowrap',
    }

    header = html.Tr([
        html.Th('Player',     style={**_hdr, 'textAlign': 'left'}),
        html.Th('Touch %',    style={**_hdr, 'textAlign': 'right'}),
    ])
    rows = []
    for i, row in poss_df.iterrows():
        bg = (COLORS.get('dark_tertiary', 'rgba(255,255,255,0.03)')
              if i % 2 == 0 else 'transparent')
        short_name = str(row['player_name']).split()[-1] if pd.notna(row['player_name']) else '—'
        pct_str = f"{row['pct']}% ({row['pct_h1']}%/{row['pct_h2']}%)"
        rows.append(html.Tr([
            html.Td(short_name, style={**_lbl, 'color': color}),
            html.Td(pct_str,    style=_val),
        ], style={'backgroundColor': bg}))

    return html.Div(
        html.Table(
            [html.Thead(header), html.Tbody(rows)],
            style={'width': '100%', 'borderCollapse': 'collapse'},
        ),
        style={'overflowX': 'auto'},
    )


# =============================================================================
# Stats metrics definition
# =============================================================================

_BUP_METRICS = [
    ('Total Passes',     'passes',     False),
    ('Pass Accuracy',    'pass_acc',   True),
    ('Positional xT',    'total_xt',   False),
    ('Into Final Third', 'into_ft',    False),
    ('Long Balls',       'long_balls', False),
    ('Crosses',          'crosses',    False),
    ('Through Balls',    'thru_balls', False),
    ('Ball Carries',     'carries',    False),
    ('Dribble Attempts', 'dribbles',   False),
    ('Dribbles Won',     'drib_succ',  False),
    ('Dribble Success',  'drib_acc',   True),
]


# =============================================================================
# Section renderers
# =============================================================================

def _render_stats(events: pd.DataFrame) -> html.Div:
    """Stats tables — always uses full match data (no filters)."""
    if events.empty:
        return html.P('No event data.', style={'color': COLORS['text_secondary']})

    # Per-half computation
    h_full = _compute_half_stats(events, 'home')
    h_h1   = _compute_half_stats(events, 'home', 1)
    h_h2   = _compute_half_stats(events, 'home', 2)
    a_full = _compute_half_stats(events, 'away')
    a_h1   = _compute_half_stats(events, 'away', 1)
    a_h2   = _compute_half_stats(events, 'away', 2)

    return html.Div([
        section_header('Pass / Carry / Dribble Stats'),
        build_info_box('Performance breakdown by half — Passing, Carries & Dribbles'),
        dbc.Row([
            dbc.Col(build_team_stats_table(
                h_full['team'], HOME_COLOR, _BUP_METRICS, h_full, h_h1, h_h2,
            ), md=6, className='mb-3'),
            dbc.Col(build_team_stats_table(
                a_full['team'], AWAY_COLOR, _BUP_METRICS, a_full, a_h1, a_h2,
            ), md=6, className='mb-3'),
        ], className='g-3'),
    ], style={'marginBottom': '8px'})


def _render_possession(events: pd.DataFrame) -> html.Div:
    """Possession touch heatmaps + per-player touch % tables (full match, static)."""
    if events.empty:
        return html.P('No event data.', style={'color': COLORS['text_secondary']})
    d   = _compute(events)
    hs  = d['home']
    as_ = d['away']

    def _heatmap_card(team, color, touch_x, touch_y):
        img_src = render_xt_heatmap_img(touch_x, touch_y, [1.0] * len(touch_x))
        return html.Div([
            html.Div(team, style={
                'color': color, 'fontWeight': '700',
                'fontSize': '0.85rem', 'marginBottom': '8px', 'textAlign': 'center',
            }),
            html.Img(src=img_src, style={'width': '100%', 'borderRadius': '6px'}),
        ], style=CARD_STYLE)

    heatmap_row = dbc.Row([
        dbc.Col(_heatmap_card(hs['team'], HOME_COLOR, hs['touch_x'], hs['touch_y']),
                md=6, className='mb-3'),
        dbc.Col(_heatmap_card(as_['team'], AWAY_COLOR, as_['touch_x'], as_['touch_y']),
                md=6, className='mb-3'),
    ], className='g-3')

    table_row = dbc.Row([
        dbc.Col(html.Div([
            html.Div(hs['team'], style={
                'color': HOME_COLOR, 'fontWeight': '700',
                'fontSize': '0.85rem', 'marginBottom': '8px',
            }),
            _player_possession_table(hs['player_poss_df'], HOME_COLOR),
        ], style=CARD_STYLE), md=6, className='mb-3'),
        dbc.Col(html.Div([
            html.Div(as_['team'], style={
                'color': AWAY_COLOR, 'fontWeight': '700',
                'fontSize': '0.85rem', 'marginBottom': '8px',
            }),
            _player_possession_table(as_['player_poss_df'], AWAY_COLOR),
        ], style=CARD_STYLE), md=6, className='mb-3'),
    ], className='g-3')

    return html.Div([
        section_header('Possession Touch Map'),
        build_info_box('Touch density across the pitch — darker = more activity. Marginal curves show x/y distributions.'),
        heatmap_row,
        section_header('Player Touch Distribution'),
        build_info_box('Each player\'s share of team touch-events — format: full%(1H%/2H%)'),
        table_row,
    ], style={'marginBottom': '36px'})


def _render_network(events: pd.DataFrame) -> html.Div:
    """Pass Network section — re-rendered when filters change."""
    if events.empty:
        return html.P('No event data.', style={'color': COLORS['text_secondary']})
    d   = _compute(events)
    hs  = d['home']
    as_ = d['away']
    return html.Div([
        section_header('Pass Network'),
        build_info_box('Node size = pass involvement · Edge width = connection frequency · Hover nodes/edges for details'),
        dbc.Row([
            _pitch_card(hs['team'], _network_fig(hs['nodes'], hs['edges'], HOME_COLOR, is_home=True),  HOME_COLOR),
            _pitch_card(as_['team'], _network_fig(as_['nodes'], as_['edges'], AWAY_COLOR, is_home=False), AWAY_COLOR),
        ], className='g-3'),
    ], style={'marginBottom': '36px'})


def _render_combos(events: pd.DataFrame) -> html.Div:
    """Combination tables — always full match data, unaffected by half filter."""
    if events.empty:
        return html.P('No event data.', style={'color': COLORS['text_secondary']})
    d   = _compute(events)
    hs  = d['home']
    as_ = d['away']
    combo_section = html.Div([
        section_header('Top Combinations'),
        build_info_box('Most frequent passer → receiver combinations · N (1H / 2H)'),
        dbc.Row([
            dbc.Col(html.Div([
                html.Div(hs['team'], style={
                    'color': HOME_COLOR, 'fontWeight': '700',
                    'fontSize': '0.85rem', 'marginBottom': '8px',
                }),
                _combo_table(hs['combos'], HOME_COLOR),
            ], style=CARD_STYLE), md=6, className='mb-3'),
            dbc.Col(html.Div([
                html.Div(as_['team'], style={
                    'color': AWAY_COLOR, 'fontWeight': '700',
                    'fontSize': '0.85rem', 'marginBottom': '8px',
                }),
                _combo_table(as_['combos'], AWAY_COLOR),
            ], style=CARD_STYLE), md=6, className='mb-3'),
        ], className='g-3'),
    ], style={'marginBottom': '24px'})
    combo3_section = html.Div([
        section_header('Top 3-Player Combinations'),
        build_info_box('Most frequent three-player passing chains (A → B → C) · N (1H / 2H)'),
        dbc.Row([
            dbc.Col(html.Div([
                html.Div(hs['team'], style={
                    'color': HOME_COLOR, 'fontWeight': '700',
                    'fontSize': '0.85rem', 'marginBottom': '8px',
                }),
                _combo_table(hs['combos3'], HOME_COLOR),
            ], style=CARD_STYLE), md=6, className='mb-3'),
            dbc.Col(html.Div([
                html.Div(as_['team'], style={
                    'color': AWAY_COLOR, 'fontWeight': '700',
                    'fontSize': '0.85rem', 'marginBottom': '8px',
                }),
                _combo_table(as_['combos3'], AWAY_COLOR),
            ], style=CARD_STYLE), md=6, className='mb-3'),
        ], className='g-3'),
    ], style={'marginBottom': '24px'})
    combo4_section = html.Div([
        section_header('Top 4-Player Combinations'),
        build_info_box('Most frequent four-player passing chains (A → B → C → D) · N (1H / 2H)'),
        dbc.Row([
            dbc.Col(html.Div([
                html.Div(hs['team'], style={
                    'color': HOME_COLOR, 'fontWeight': '700',
                    'fontSize': '0.85rem', 'marginBottom': '8px',
                }),
                _combo_table(hs['combos4'], HOME_COLOR),
            ], style=CARD_STYLE), md=6, className='mb-3'),
            dbc.Col(html.Div([
                html.Div(as_['team'], style={
                    'color': AWAY_COLOR, 'fontWeight': '700',
                    'fontSize': '0.85rem', 'marginBottom': '8px',
                }),
                _combo_table(as_['combos4'], AWAY_COLOR),
            ], style=CARD_STYLE), md=6, className='mb-3'),
        ], className='g-3'),
    ], style={'marginBottom': '24px'})
    return html.Div([combo_section, combo3_section, combo4_section])


def _render_entries(events: pd.DataFrame) -> html.Div:
    """Entry pitch plots — re-rendered when filters change."""
    if events.empty:
        return html.P('No event data.', style={'color': COLORS['text_secondary']})
    d   = _compute(events)
    hs  = d['home']
    as_ = d['away']
    ft_home_total  = len(hs['entries_ft'])
    ft_away_total  = len(as_['entries_ft'])
    entries_ft_section = html.Div([
        section_header('Final Third Entries by Band'),
        build_info_box(
            'Passes, dribbles and carries crossing the final third line, coloured by destination band. '
            'Left Band: y > 66.67 · Centre Band: 33.33–66.67 · Right Band: y < 33.33. '
            'Hover for player, time, outcome and whether it led to a shot or goal.'
        ),
        dbc.Row([
            _pitch_card(
                f"{hs['team']} ({ft_home_total} entries)",
                _entries_fig(hs['entries_ft'], 'final_third', HOME_COLOR, is_home=True),
                HOME_COLOR,
            ),
            _pitch_card(
                f"{as_['team']} ({ft_away_total} entries)",
                _entries_fig(as_['entries_ft'], 'final_third', AWAY_COLOR, is_home=False),
                AWAY_COLOR,
            ),
        ], className='g-3'),
    ], style={'marginBottom': '36px'})
    z14_home_total = len(hs['entries_z14'])
    z14_away_total = len(as_['entries_z14'])
    entries_z14_section = html.Div([
        section_header('Zone 14 Entries by Band'),
        build_info_box(
            'Passes (solid arrows), dribbles and carries (dashed lines) ending in Zone 14, '
            'Left Half Space or Right Half Space. '
            'Coloured by band — Left (y > 66.67), Centre (33.33–66.67), Right (y < 33.33).'
        ),
        dbc.Row([
            _pitch_card(
                f"{hs['team']} ({z14_home_total} entries)",
                _entries_fig(hs['entries_z14'], 'zone14', HOME_COLOR, is_home=True),
                HOME_COLOR,
            ),
            _pitch_card(
                f"{as_['team']} ({z14_away_total} entries)",
                _entries_fig(as_['entries_z14'], 'zone14', AWAY_COLOR, is_home=False),
                AWAY_COLOR,
            ),
        ], className='g-3'),
    ], style={'marginBottom': '36px'})
    return html.Div([entries_ft_section, entries_z14_section])


def _render_tables(events: pd.DataFrame) -> html.Div:
    """Player entries table — always uses full match data (no half filter)."""
    if events.empty:
        return html.P('No event data.', style={'color': COLORS['text_secondary']})
    d   = _compute(events)
    hs  = d['home']
    as_ = d['away']
    home_df = _build_player_entries_table(hs['entries_ft'], hs['entries_z14'])
    away_df = _build_player_entries_table(as_['entries_ft'], as_['entries_z14'])
    return html.Div([
        section_header('Player Zone Entries'),
        build_info_box('Final Third entries per player broken down by band — format: total(1H/2H)'),
        dbc.Row([
            dbc.Col(html.Div([
                html.Div(hs['team'], style={
                    'color': HOME_COLOR, 'fontWeight': '700',
                    'fontSize': '0.85rem', 'marginBottom': '8px',
                }),
                _player_entries_table(home_df, HOME_COLOR),
            ], style=CARD_STYLE), md=6, className='mb-3'),
            dbc.Col(html.Div([
                html.Div(as_['team'], style={
                    'color': AWAY_COLOR, 'fontWeight': '700',
                    'fontSize': '0.85rem', 'marginBottom': '8px',
                }),
                _player_entries_table(away_df, AWAY_COLOR),
            ], style=CARD_STYLE), md=6, className='mb-3'),
        ], className='g-3'),
    ])


# =============================================================================
# Public entry-point
# =============================================================================

def build_build_up_passing_tab(events: pd.DataFrame, **_) -> html.Div:
    """Build the Build-Up & Passing tab."""
    if events.empty:
        return html.P('No event data.', style={'color': COLORS['text_secondary']})

    return html.Div([
        _render_stats(events),
        _render_possession(events),
        _render_network(events),
        _render_combos(events),
        html.Div([
            html.Div([
                html.Span('Half:', style={
                    'color': COLORS['text_secondary'], 'fontSize': '0.75rem', 'marginRight': '8px',
                }),
                dcc.RadioItems(
                    id='bup-half',
                    options=[
                        {'label': 'Full', 'value': 'all'},
                        {'label': '1H',   'value': '1'},
                        {'label': '2H',   'value': '2'},
                    ],
                    value='all',
                    inline=True,
                    inputStyle={'cursor': 'pointer', 'accentColor': COLORS['gold']},
                    labelStyle={
                        'color': COLORS['text_secondary'], 'fontSize': '0.75rem',
                        'cursor': 'pointer', 'marginRight': '12px',
                    },
                ),
            ], style={'display': 'flex', 'alignItems': 'center', 'padding': '8px 0 4px'}),
            html.Div(id='bup-entries-section', children=_render_entries(events)),
        ]),
        _render_tables(events),
    ], style={'marginTop': '16px'})


def register_build_up_passing_callbacks(app) -> None:

    @app.callback(
        Output('bup-entries-section', 'children'),
        Input('bup-half', 'value'),
        Input('pma-selected-match', 'data'),
    )
    def _update_bup_entries(half, match_id):
        if not match_id:
            return html.P('No match selected.', style={'color': COLORS['text_secondary']})
        events = get_match_events(match_id)
        if events.empty:
            return html.P('No event data.', style={'color': COLORS['text_secondary']})
        if half == '1' and 'period_id' in events.columns:
            events = events[events['period_id'] == 1]
        elif half == '2' and 'period_id' in events.columns:
            events = events[events['period_id'] == 2]
        return _render_entries(events)
