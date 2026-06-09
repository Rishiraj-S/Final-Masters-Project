"""
page_utils.goal_sequence
========================
Extract and render the event sequences leading up to shots/goals.

Public API
----------
get_goal_sequences(events, team_code, *, lookback_n, lookback_secs)
    -> list[dict]

get_shot_sequence(events, *, team_code, time_min, period_id, ...)
    -> dict | None

render_goal_sequence_frames(sequence, *, figsize, dpi)
    -> dict  {'frames': [b64_png, ...], 'n_frames': int,
              'origin': str, 'title': str}

render_goal_sequence_img(sequence, *, color, figsize, title, dpi)
    -> str   # base64 static PNG fallback (no data-URL prefix)
"""

from __future__ import annotations

import io
import base64
from typing import Any

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patheffects as pe
from matplotlib.lines import Line2D
import numpy as np
import pandas as pd
from mplsoccer import Pitch

from page_utils.visualizations import (
    PITCH_BG, PITCH_LINE_COLOR,
    HOME_COLOR, GOLD,
)
from utils.config import COLORS


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_BUILD_UP_TYPES: frozenset[str] = frozenset({
    'Pass', 'Take On', 'Ball recovery', 'Interception',
    'Ball touch', 'Challenge', 'Tackle',
    'Miss', 'Saved Shot', 'Goal', 'Post',
})

_SHOT_TYPES: frozenset[str] = frozenset({
    'Miss', 'Saved Shot', 'Goal', 'Post', 'Blocked Shot',
})

_EVENT_COLORS: dict[str, str] = {
    'Pass':          '#74c0fc',
    'Ball Carry':    '#adb5bd',
    'Take On':       '#ffd43b',
    'Ball recovery': '#a9e34b',
    'Ball touch':    '#a9e34b',
    'Interception':  '#a9e34b',
    'Challenge':     '#ff922b',
    'Tackle':        '#ff922b',
    'Goal':          GOLD,
    'Saved Shot':    '#4dabf7',
    'Miss':          '#ff6b6b',
    'Post':          '#ffd43b',
}
_DEFAULT_EVENT_COLOR = '#adb5bd'

_DEFAULT_LOOKBACK_N    = 8
_DEFAULT_LOOKBACK_SECS = 30
_ORIGIN_LOOKBACK_SECS  = 60   # wider window for set-piece origin detection

# Badge colour per sequence origin (maps to Bootstrap colour names)
ORIGIN_BADGE_COLOR: dict[str, str] = {
    'Corner':           'warning',
    'Free Kick':        'info',
    'Direct Free Kick': 'info',
    'Throw-in':         'secondary',
    'Goal Kick':        'secondary',
    'Penalty':          'danger',
    'Open Play':        'success',
}


# ---------------------------------------------------------------------------
# Sequence extraction
# ---------------------------------------------------------------------------

def get_goal_sequences(
    events: pd.DataFrame,
    team_code: str,
    *,
    lookback_n: int = _DEFAULT_LOOKBACK_N,
    lookback_secs: int = _DEFAULT_LOOKBACK_SECS,
) -> list[dict[str, Any]]:
    """Return one dict per goal scored by *team_code*.

    Each dict::

        {
            'sequence':   pd.DataFrame,
            'goal_row':   pd.Series,
            'scorer':     str,
            'assister':   str | None,
            'minute':     str,
            'period':     int,
            'team_code':  str,
        }
    """
    if events.empty:
        return []

    ev = _prep(events)
    goals = ev[(ev['event_type'] == 'Goal') & (ev['team_code'] == team_code)]

    sequences: list[dict[str, Any]] = []
    for pos, goal_row in goals.iterrows():
        period = int(goal_row.get('period_id', 1))
        goal_t = goal_row.get('_abs_sec')

        mask = (
            (ev['period_id'] == period) &
            (ev['team_code'] == team_code) &
            (ev['event_type'].isin(_BUILD_UP_TYPES)) &
            (ev.index < pos)
        )
        cands = ev[mask].copy()
        if goal_t is not None and '_abs_sec' in cands.columns:
            cands = cands[
                cands['_abs_sec'].isna() |
                (cands['_abs_sec'] >= goal_t - lookback_secs)
            ]

        seq_df = pd.concat(
            [cands.tail(lookback_n), goal_row.to_frame().T],
            ignore_index=True,
        )
        sequences.append({
            'sequence':  seq_df,
            'goal_row':  goal_row,
            'scorer':    _clean_name(goal_row.get('player_name')),
            'assister':  _last_passer(seq_df),
            'minute':    _format_minute(goal_row),
            'period':    period,
            'team_code': team_code,
        })
    return sequences


# ---------------------------------------------------------------------------
# Single-shot lookup
# ---------------------------------------------------------------------------

def get_shot_sequence(
    events: pd.DataFrame,
    *,
    team_code: str | None = None,
    match_id: str | None = None,
    time_min: int | float,
    period_id: int = 1,
    player_name: str | None = None,
    event_type: str | None = None,
    lookback_n: int = _DEFAULT_LOOKBACK_N,
    lookback_secs: int = _DEFAULT_LOOKBACK_SECS,
) -> dict[str, Any] | None:
    """Find a specific shot and return its build-up sequence, or None."""
    if events.empty:
        return None

    ev = _prep(events)

    mask = ev['event_type'].isin(_SHOT_TYPES)
    if team_code and 'team_code' in ev.columns:
        mask &= ev['team_code'] == team_code
    if match_id and 'match_id' in ev.columns:
        mask &= ev['match_id'] == match_id
    if 'period_id' in ev.columns:
        mask &= ev['period_id'] == period_id
    if event_type:
        mask &= ev['event_type'] == event_type

    time_min_int = int(float(time_min))
    if 'time_min' in ev.columns:
        t = pd.to_numeric(ev['time_min'], errors='coerce')
        mask &= (t - time_min_int).abs() <= 1

    if player_name and 'player_name' in ev.columns:
        pm = ev['player_name'] == player_name
        if pm.any():
            mask &= pm

    cands = ev[mask]
    if cands.empty:
        return None

    shot_pos = cands.index[0]
    shot_row = ev.loc[shot_pos]
    period   = int(shot_row.get('period_id', period_id))
    goal_t   = shot_row.get('_abs_sec')
    tc       = str(shot_row.get('team_code') or team_code or '')

    pre_mask = (
        (ev['period_id'] == period) &
        (ev['team_code'] == tc) &
        (ev['event_type'].isin(_BUILD_UP_TYPES)) &
        (ev.index < shot_pos)
    )
    if match_id and 'match_id' in ev.columns:
        pre_mask &= ev['match_id'] == match_id

    pre = ev[pre_mask].copy()
    if goal_t is not None and '_abs_sec' in pre.columns:
        pre = pre[pre['_abs_sec'].isna() | (pre['_abs_sec'] >= goal_t - lookback_secs)]

    # Classify origin on the wider window before truncating for animation display
    pre_for_origin = ev[pre_mask].copy()
    if goal_t is not None and '_abs_sec' in pre_for_origin.columns:
        pre_for_origin = pre_for_origin[
            pre_for_origin['_abs_sec'].isna() |
            (pre_for_origin['_abs_sec'] >= goal_t - _ORIGIN_LOOKBACK_SECS)
        ]
    origin_df = pd.concat(
        [pre_for_origin, shot_row.to_frame().T],
        ignore_index=True,
    )
    origin = classify_sequence_origin(origin_df)

    seq_df = pd.concat(
        [pre.tail(lookback_n), shot_row.to_frame().T],
        ignore_index=True,
    )

    return {
        'sequence':  seq_df,
        'origin':    origin,
        'goal_row':  shot_row,
        'scorer':    _clean_name(shot_row.get('player_name')),
        'assister':  _last_passer(seq_df),
        'minute':    _format_minute(shot_row),
        'period':    period,
        'team_code': tc,
        'shot_type': str(shot_row.get('event_type', 'Shot')),
    }


# ---------------------------------------------------------------------------
# Sequence origin classifier
# ---------------------------------------------------------------------------

def classify_sequence_origin(seq_df: pd.DataFrame) -> str:
    """Return the tactical origin of the sequence: Penalty, Corner, Free Kick, or Open Play.

    Uses the same qualifier columns as set_pieces.py to ensure consistent labels.
    """
    if seq_df.empty:
        return 'Open Play'

    # Penalty: shot row has Penalty == 'Si'
    for _, row in seq_df.iterrows():
        if str(row.get('event_type', '')) not in _SHOT_TYPES:
            continue
        if row.get('Penalty') == 'Si':
            return 'Penalty'

    # Corner: any pass has Corner taken == 'Si'
    for _, row in seq_df.iterrows():
        if str(row.get('event_type', '')) != 'Pass':
            continue
        if row.get('Corner taken') == 'Si':
            return 'Corner'

    # Free Kick: pass has Free kick taken == 'Si', or shot has Free kick == 'Si'
    for _, row in seq_df.iterrows():
        etype = str(row.get('event_type', ''))
        if etype == 'Pass' and row.get('Free kick taken') == 'Si':
            return 'Free Kick'
        if etype in _SHOT_TYPES and row.get('Free kick') == 'Si':
            return 'Free Kick'

    return 'Open Play'


# ---------------------------------------------------------------------------
# Carry insertion  (ported from innntento2gif.insert_conduction_events)
# ---------------------------------------------------------------------------

def _insert_carry_events(df: pd.DataFrame) -> pd.DataFrame:
    """Insert synthetic 'Ball Carry' rows where end-of-event to start-of-next
    gap exceeds 2 pitch units."""
    included = {'Pass'} | _SHOT_TYPES
    rows = df[df['event_type'].isin(included)].copy().reset_index(drop=True)

    if len(rows) < 2:
        return rows

    new_rows: list[dict] = []
    for i in range(len(rows) - 1):
        cur = rows.iloc[i]
        nxt = rows.iloc[i + 1]
        new_rows.append(cur.to_dict())

        end_x = pd.to_numeric(cur.get('Pass End X'), errors='coerce')
        end_y = pd.to_numeric(cur.get('Pass End Y'), errors='coerce')
        if pd.isna(end_x):
            end_x = pd.to_numeric(cur.get('x'), errors='coerce')
        if pd.isna(end_y):
            end_y = pd.to_numeric(cur.get('y'), errors='coerce')

        nxt_x = pd.to_numeric(nxt.get('x'), errors='coerce')
        nxt_y = pd.to_numeric(nxt.get('y'), errors='coerce')

        if pd.notna(end_x) and pd.notna(nxt_x):
            gap_x = abs(float(nxt_x) - float(end_x))
            gap_y = abs(float(nxt_y) - float(end_y)) if (pd.notna(nxt_y) and pd.notna(end_y)) else 0.0
            if gap_x > 2 or gap_y > 2:
                carry = nxt.to_dict()
                carry['event_type'] = 'Ball Carry'
                carry['x']          = float(end_x)
                carry['y']          = float(end_y) if pd.notna(end_y) else float(nxt_y or 50)
                carry['Pass End X'] = float(nxt_x)
                carry['Pass End Y'] = float(nxt_y) if pd.notna(nxt_y) else float(end_y or 50)
                new_rows.append(carry)

    new_rows.append(rows.iloc[-1].to_dict())
    return pd.DataFrame(new_rows).reset_index(drop=True)


# ---------------------------------------------------------------------------
# Motion animation helpers
# ---------------------------------------------------------------------------

_N_INTERP = 10  # sub-frames rendered per event (10 × 80 ms ≈ 0.8 s per action)


def _ease_out(t: float) -> float:
    """Quadratic ease-out — ball decelerates as it arrives."""
    return 1.0 - (1.0 - t) ** 2


def _resolve_ends(row: pd.Series, is_shot: bool) -> tuple[float, float, float, float]:
    """Return (x, y, end_x, end_y) for a row, clamping shots toward goal centre."""
    x = float(row['x'])
    y = float(row['y'])
    _ex = pd.to_numeric(row.get('Pass End X'), errors='coerce')
    _ey = pd.to_numeric(row.get('Pass End Y'), errors='coerce')
    end_x = float(_ex) if pd.notna(_ex) else x
    end_y = float(_ey) if pd.notna(_ey) else y
    if is_shot:
        end_x, end_y = 100.0, 50.0
    return x, y, end_x, end_y


def _draw_motion_frame(
    fig: plt.Figure,
    ax: plt.Axes,
    pitch: Pitch,
    valid: pd.DataFrame,
    event_idx: int,
    t: float,
    title: str,
) -> None:
    """Render one sub-frame of the sequence animation.

    t ∈ [0, 1] is the progress through *event_idx*.

    Trail (events 0 … event_idx-1):
        Dimmed arrows + small numbered dots — show the build-up path.

    Active event (event_idx):
        Full arrow + interpolated positions.
        - Ball Carry : player AND ball move together along the path.
        - Pass       : player stays at origin, ball moves; receiving player
                       fades in at destination once ball passes half-way.
        - Shot       : player stays, ball flies toward goal.
    """
    ax.cla()
    pitch.draw(ax=ax)

    # ── Trail ─────────────────────────────────────────────────────────
    step = 0
    for i in range(event_idx):
        row      = valid.iloc[i]
        etype    = str(row.get('event_type', ''))
        ec       = _EVENT_COLORS.get(etype, _DEFAULT_EVENT_COLOR)
        is_carry = etype == 'Ball Carry'
        is_shot  = etype in _SHOT_TYPES
        x, y, end_x, end_y = _resolve_ends(row, is_shot)

        if etype in ('Pass', 'Ball Carry') and (abs(end_x - x) > 0.5 or abs(end_y - y) > 0.5):
            pitch.arrows(x, y, end_x, end_y, ax=ax,
                         width=0.7 if is_carry else 1.2,
                         headwidth=2 if is_carry else 3,
                         headlength=2 if is_carry else 3,
                         color=ec,
                         alpha=0.20 if is_carry else 0.38,
                         zorder=3 if is_carry else 4)
        elif is_shot:
            pitch.arrows(x, y, end_x, end_y, ax=ax,
                         width=1.2, headwidth=3, headlength=3,
                         color=ec, alpha=0.38, zorder=4)

        if not is_carry:
            step += 1
            pitch.scatter(x, y, ax=ax, s=90, marker='o',
                          c=ec, edgecolors='white', linewidths=0.6,
                          alpha=0.38, zorder=5)
            ax.text(x, y, str(step), fontsize=5, fontweight='bold',
                    color='white', ha='center', va='center',
                    zorder=6, alpha=0.45,
                    path_effects=[pe.withStroke(linewidth=1, foreground='black')])

    # ── Active event ──────────────────────────────────────────────────
    row      = valid.iloc[event_idx]
    etype    = str(row.get('event_type', ''))
    ec       = _EVENT_COLORS.get(etype, _DEFAULT_EVENT_COLOR)
    is_goal  = etype == 'Goal'
    is_carry = etype == 'Ball Carry'
    is_shot  = etype in _SHOT_TYPES
    x, y, end_x, end_y = _resolve_ends(row, is_shot)

    # Full arrow for the active event
    if etype in ('Pass', 'Ball Carry') and (abs(end_x - x) > 0.5 or abs(end_y - y) > 0.5):
        pitch.arrows(x, y, end_x, end_y, ax=ax,
                     width=0.8 if is_carry else 1.6,
                     headwidth=3 if is_carry else 5,
                     headlength=3 if is_carry else 5,
                     color=ec,
                     alpha=0.40 if is_carry else 0.88,
                     zorder=3 if is_carry else 4)
    elif is_shot:
        pitch.arrows(x, y, end_x, end_y, ax=ax,
                     width=1.6, headwidth=5, headlength=5,
                     color=ec, alpha=0.90, zorder=4)

    te = _ease_out(t)

    if is_carry:
        # ── Carry: player and white ball travel together ───────────────
        px = x + te * (end_x - x)
        py = y + te * (end_y - y)
        pitch.scatter(px, py, ax=ax, s=200, marker='o',
                      c=ec, edgecolors='white', linewidths=0.9,
                      alpha=1.0, zorder=5)
        pitch.scatter(px, py, ax=ax, s=65, marker='o',
                      c='white', edgecolors='#777', linewidths=0.6,
                      alpha=1.0, zorder=8)
    else:
        # ── Pass / Shot: player stays, ball moves ─────────────────────
        step += 1
        if is_goal:
            pitch.scatter(x, y, ax=ax, s=440, marker='*',
                          c=GOLD, edgecolors='white', linewidths=0.9,
                          alpha=1.0, zorder=6)
        else:
            pitch.scatter(x, y, ax=ax, s=200, marker='o',
                          c=ec, edgecolors='white', linewidths=0.9,
                          alpha=1.0, zorder=5)
            ax.text(x, y, str(step), fontsize=6.5, fontweight='bold',
                    color='white', ha='center', va='center', zorder=7,
                    path_effects=[pe.withStroke(linewidth=1.5, foreground='black')])

        # Receiving player fades in at pass destination once ball is half-way
        if not is_shot and t > 0.5 and event_idx + 1 < len(valid):
            nxt      = valid.iloc[event_idx + 1]
            nxt_type = str(nxt.get('event_type', ''))
            if nxt_type not in _SHOT_TYPES and nxt_type != 'Ball Carry':
                recv_alpha = min(1.0, (t - 0.5) * 2.0) * 0.75
                recv_ec    = _EVENT_COLORS.get(nxt_type, _DEFAULT_EVENT_COLOR)
                pitch.scatter(end_x, end_y, ax=ax, s=200, marker='o',
                              c=recv_ec, edgecolors='white', linewidths=0.9,
                              alpha=recv_alpha, zorder=5)

        # White ball travels from origin toward destination / goal
        bx = x + te * (end_x - x)
        by = y + te * (end_y - y)
        pitch.scatter(bx, by, ax=ax, s=90, marker='o',
                      c='white', edgecolors='#777', linewidths=0.8,
                      alpha=1.0, zorder=8)

    # ── Bottom-left label ─────────────────────────────────────────────
    cur_name = _clean_name(row.get('player_name'))
    if cur_name:
        action = ('carries' if is_carry
                  else 'GOAL!' if is_goal
                  else 'shoots' if is_shot
                  else 'passes')
        ax.text(1, 3, f'{cur_name}  ·  {action}',
                fontsize=7.5, color='white', fontweight='bold',
                ha='left', va='bottom', zorder=9, transform=ax.transData,
                path_effects=[pe.withStroke(linewidth=3, foreground=PITCH_BG)])

    fig.suptitle(title, color=COLORS['text_primary'],
                 fontsize=9, fontweight='bold', y=0.98)


# ---------------------------------------------------------------------------
# Interactive frame renderer
# ---------------------------------------------------------------------------

def render_goal_sequence_frames(
    sequence: dict[str, Any],
    *,
    figsize: tuple[float, float] = (8, 5.5),
    dpi: int = 75,
) -> dict[str, Any]:
    """Render the sequence as a smooth motion animation.

    Generates *_N_INTERP* PNG frames per event (ball interpolated along the
    path) so the Dash Interval player shows fluid motion at ~80 ms per frame.

    Returns
    -------
    dict with keys:
        'frames'   : list[str]  — base64 PNG (no data-URL prefix)
        'n_frames' : int
        'origin'   : str
        'title'    : str
    """
    seq_df   = sequence['sequence']
    scorer   = sequence.get('scorer', '')
    assister = sequence.get('assister')
    minute   = sequence.get('minute', '')

    parts = [scorer]
    if assister:
        parts.append(f'assist: {assister}')
    if minute:
        parts.append(minute)
    title = '   ·   '.join(p for p in parts if p)

    origin = sequence.get('origin') or classify_sequence_origin(seq_df)

    df_rich = _insert_carry_events(seq_df)
    valid   = df_rich[df_rich['x'].notna() & df_rich['y'].notna()].reset_index(drop=True)
    n       = len(valid)

    if n == 0:
        b64 = render_goal_sequence_img(sequence, figsize=figsize, title=title)
        return {'frames': [b64], 'n_frames': 1, 'n_events': 1, 'origin': origin, 'title': title}

    pitch = Pitch(
        pitch_type='opta',
        pitch_color=PITCH_BG,
        line_color=PITCH_LINE_COLOR,
        linewidth=1.2,
    )

    frames: list[str] = []
    for event_idx in range(n):
        for sub_idx in range(_N_INTERP):
            t = sub_idx / (_N_INTERP - 1)   # 0.0 → 1.0
            fig, ax = pitch.draw(figsize=figsize)
            fig.patch.set_facecolor(PITCH_BG)
            _draw_motion_frame(fig, ax, pitch, valid, event_idx, t, title)
            buf = io.BytesIO()
            fig.savefig(buf, format='png', bbox_inches='tight',
                        facecolor=fig.get_facecolor(), dpi=dpi)
            buf.seek(0)
            frames.append(base64.b64encode(buf.read()).decode())
            plt.close(fig)

    # Hold on the last frame so the viewer can see the final state
    frames.extend([frames[-1]] * 6)

    return {
        'frames':   frames,
        'n_frames': len(frames),
        'n_events': n,             # number of pitch events (excludes hold frames)
        'origin':   origin,
        'title':    title,
    }


# ---------------------------------------------------------------------------
# Static PNG fallback
# ---------------------------------------------------------------------------

def render_goal_sequence_img(
    sequence: dict[str, Any],
    *,
    color: str = HOME_COLOR,
    figsize: tuple[float, float] = (8, 5.5),
    title: str | None = None,
    dpi: int = 120,
) -> str:
    """Render a static PNG of the full sequence (all events visible at once).

    Returns base64-encoded PNG (no data-URL prefix).
    """
    seq_df   = sequence['sequence']
    scorer   = sequence.get('scorer', '')
    assister = sequence.get('assister')
    minute   = sequence.get('minute', '')

    if title is None:
        parts = [scorer]
        if assister:
            parts.append(f'assist: {assister}')
        if minute:
            parts.append(minute)
        title = '   ·   '.join(p for p in parts if p)

    pitch = Pitch(
        pitch_type='opta',
        pitch_color=PITCH_BG,
        line_color=PITCH_LINE_COLOR,
        linewidth=1.2,
    )
    fig, ax = pitch.draw(figsize=figsize)
    fig.patch.set_facecolor(PITCH_BG)

    valid = seq_df[seq_df['x'].notna() & seq_df['y'].notna()].reset_index(drop=True)

    if valid.empty:
        fig.suptitle(title, color=COLORS['text_primary'], fontsize=10, fontweight='bold', y=0.97)
        result = _fig_to_b64(fig, dpi)
        plt.close(fig)
        return result

    n = len(valid)
    for i, row in valid.iterrows():
        etype   = str(row.get('event_type', ''))
        ec      = _EVENT_COLORS.get(etype, _DEFAULT_EVENT_COLOR)
        is_goal = etype == 'Goal'
        x, y    = float(row['x']), float(row['y'])

        if i < n - 1:
            next_row = valid.iloc[i + 1]
            nx, ny   = float(next_row['x']), float(next_row['y'])
            if etype == 'Pass':
                ex = pd.to_numeric(row.get('Pass End X'), errors='coerce')
                ey = pd.to_numeric(row.get('Pass End Y'), errors='coerce')
                if pd.notna(ex) and pd.notna(ey):
                    nx, ny = float(ex), float(ey)
            if abs(nx - x) > 0.5 or abs(ny - y) > 0.5:
                pitch.arrows(x, y, nx, ny, ax=ax,
                             width=1.2, headwidth=4, headlength=4,
                             color=ec, alpha=0.85, zorder=4)

        if is_goal:
            pitch.scatter(x, y, ax=ax, s=380, marker='*',
                          c=GOLD, edgecolors='white', linewidths=0.7, zorder=6)
        else:
            pitch.scatter(x, y, ax=ax, s=130, marker='o',
                          c=ec, edgecolors='white', linewidths=0.7, zorder=5)

        ax.text(x, y, str(i + 1), fontsize=6, fontweight='bold',
                color='white' if not is_goal else PITCH_BG,
                ha='center', va='center', zorder=7,
                path_effects=[pe.withStroke(linewidth=1.5, foreground='black')])

    _seen: set[str] = set()
    for _, row in valid.iterrows():
        etype = str(row.get('event_type', ''))
        if etype not in {'Pass', 'Goal', 'Take On'}:
            continue
        pname = _clean_name(row.get('player_name'))
        if not pname or pname in _seen:
            continue
        x, y  = float(row['x']), float(row['y'])
        short = pname.split()[-1] if ' ' in pname else pname
        ax.text(x, y + 5, short, fontsize=5.5, color=COLORS['text_secondary'],
                ha='center', va='bottom', zorder=6,
                path_effects=[pe.withStroke(linewidth=1.5, foreground=PITCH_BG)])
        _seen.add(pname)

    present = valid['event_type'].unique()
    legend_handles = [
        Line2D([0], [0], marker='o', color='none',
               markerfacecolor=_EVENT_COLORS.get(t, _DEFAULT_EVENT_COLOR),
               markersize=7, label=t)
        for t in _EVENT_COLORS if t in present
    ]
    if legend_handles:
        ax.legend(handles=legend_handles, loc='lower left', fontsize=6,
                  framealpha=0.35, facecolor=PITCH_BG,
                  edgecolor=COLORS['dark_border'], labelcolor=COLORS['text_secondary'],
                  ncol=min(len(legend_handles), 4))

    fig.suptitle(title, color=COLORS['text_primary'], fontsize=10, fontweight='bold', y=0.98)
    plt.tight_layout(pad=0.3)
    result = _fig_to_b64(fig, dpi)
    plt.close(fig)
    return result


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _prep(events: pd.DataFrame) -> pd.DataFrame:
    ev = events.copy()
    for col in ('x', 'y', 'Pass End X', 'Pass End Y'):
        if col in ev.columns:
            ev[col] = pd.to_numeric(ev[col], errors='coerce')
    ev = _add_abs_seconds(ev)
    return ev.reset_index(drop=True)


def _last_passer(seq_df: pd.DataFrame) -> str | None:
    if len(seq_df) < 2:
        return None
    prev = seq_df.iloc[-2]
    if prev.get('event_type') == 'Pass':
        raw = prev.get('player_name')
        return str(raw) if raw and str(raw) != 'nan' else None
    return None


def _add_abs_seconds(events: pd.DataFrame) -> pd.DataFrame:
    ev = events.copy()
    if 'time_min' in ev.columns and 'time_sec' in ev.columns:
        mins = pd.to_numeric(ev['time_min'], errors='coerce').fillna(0)
        secs = pd.to_numeric(ev['time_sec'], errors='coerce').fillna(0)
        pid  = pd.to_numeric(ev.get('period_id', 1), errors='coerce').fillna(1).clip(lower=1)
        ev['_abs_sec'] = (pid - 1) * 5400 + mins * 60 + secs
    else:
        ev['_abs_sec'] = np.nan
    return ev


def _format_minute(row: pd.Series) -> str:
    raw = row.get('time_min')
    if raw is None:
        return ''
    try:
        t_min  = int(float(raw))
        period = int(float(row.get('period_id', 1)))
    except (TypeError, ValueError):
        return ''
    if period == 1 and t_min > 45:
        return f"45+{t_min - 45}'"
    if period == 2 and t_min > 90:
        return f"90+{t_min - 90}'"
    return f"{t_min}'"


def _clean_name(raw: Any) -> str:
    if raw is None:
        return ''
    s = str(raw).strip()
    return '' if s.lower() in ('nan', 'none', '') else s


def _fig_to_b64(fig, dpi: int = 120) -> str:
    buf = io.BytesIO()
    fig.savefig(buf, format='png', bbox_inches='tight',
                facecolor=fig.get_facecolor(), dpi=dpi)
    buf.seek(0)
    return base64.b64encode(buf.read()).decode()
