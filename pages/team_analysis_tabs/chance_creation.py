"""
Team Analysis — Tab 2: Chance Creation & Finishing

Layout (4 equal vertical parts):
  Filter panel (md=3) | Shot Map (md=6) | Scorers + Assisters tables (md=3)

KPI bar spans the full content area above the main columns.
Filters: player, shot outcome, shot origin (open-play / set-piece), half-time sliders.
All heavy computation is deferred to the callback (skeleton pattern, same as buildup.py).
"""

import pandas as pd
import numpy as np
import plotly.graph_objects as go
from dash import html, dcc, Input, Output, State
import dash_bootstrap_components as dbc

from utils.config import COLORS
from utils.data_utils import get_all_events, exclude_own_goals, CURRENT_SEASON
from utils.xg_utils import add_xg_column
from page_utils import PassMap, GOLD, HOME_COLOR
from page_utils.competitions import normalize_competitions as _normalize_competitions
from page_utils.visualizations import (
    add_vertical_half_pitch_background,
    VPITCH_AXIS_HALF,
    PITCH_BG,
    render_lsc_heatmap_img,
)
from page_utils.event_filters import SHOT_TYPES as _SHOT_TYPES


# =============================================================================
# Constants
# =============================================================================

_OUTCOME_COLOR = {
    'Goal':         '#51cf66',
    'Saved Shot':   '#339af0',
    'Miss':         '#ff6b6b',
    'Post':         '#ffd43b',
    'Blocked Shot': '#cc5de8',
}
_OUTCOME_SYMBOL = {
    'Goal':         'star',
    'Saved Shot':   'circle',
    'Miss':         'x',
    'Post':         'diamond',
    'Blocked Shot': 'square',
}

_LABEL_STYLE = {
    'color': GOLD,
    'fontSize': '0.70rem',
    'fontWeight': '700',
    'letterSpacing': '0.8px',
    'textTransform': 'uppercase',
    'marginBottom': '5px',
    'marginTop': '14px',
}
_PANEL_STYLE = {
    'backgroundColor': COLORS['dark_secondary'],
    'border': f'1px solid {COLORS["dark_border"]}',
    'borderRadius': '6px',
    'padding': '14px 12px',
    'overflowY': 'auto',
    'maxHeight': '80vh',
}
_SECTION_TITLE = {
    'color': GOLD,
    'fontWeight': '700',
    'fontSize': '0.82rem',
    'letterSpacing': '1px',
    'textTransform': 'uppercase',
    'paddingBottom': '8px',
    'borderBottom': f'1px solid {COLORS["dark_border"]}',
}
_TH = {
    'textAlign': 'center', 'padding': '4px 6px',
    'fontSize': '0.58rem', 'fontWeight': '700',
    'color': COLORS['text_secondary'], 'textTransform': 'uppercase',
    'letterSpacing': '0.05em', 'whiteSpace': 'nowrap',
    'borderBottom': f'1px solid {COLORS["dark_border"]}',
}
# For headers whose text must not be uppercased (e.g. xG, xA)
_TH_NOCASE = {**_TH, 'textTransform': 'none', 'letterSpacing': '0'}
_TD = {
    'textAlign': 'center', 'padding': '4px 6px',
    'fontSize': '0.68rem', 'fontWeight': '600',
    'color': COLORS['text_primary'], 'whiteSpace': 'nowrap',
}
_NAME = {**_TD, 'textAlign': 'left', 'color': GOLD,
         'maxWidth': '90px', 'overflow': 'hidden', 'textOverflow': 'ellipsis'}

CHART_CFG = {'displayModeBar': False}


# =============================================================================
# Skeleton
# =============================================================================

def _skel_fig(height: int = 520) -> go.Figure:
    """Empty placeholder figure shown before the callback fires."""
    fig = go.Figure()
    fig.update_layout(
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor=PITCH_BG,
        height=height, margin=dict(l=0, r=0, t=36, b=0),
    )
    return fig


# =============================================================================
# Data helpers
# =============================================================================

# Qualifiers on the SHOT row that identify set-piece-derived shots
_SP_SHOT_COLS = ['From corner', 'Free kick', 'Set piece', 'Throw In set piece', 'Corner situation']
# Qualifiers on the PASS row that identify set-piece passes (corner/FK/throw-in taken)
_SP_PASS_COLS = ['Corner taken', 'Free kick taken', 'Throw In']


def _add_sp_flag(shots: pd.DataFrame, bar: pd.DataFrame) -> pd.DataFrame:
    """
    Add _is_sp_shot boolean column to shots.

    A shot is flagged True when EITHER:
      (a) Direct qualifier on the shot row:
          'From corner', 'Free kick', 'Set piece', 'Throw In set piece',
          or 'Corner situation' == 'Si'
      (b) Indirect: the immediately preceding BAR event (same match) is a
          set-piece pass ('Corner taken', 'Free kick taken', or 'Throw In' == 'Si')

    Penalties are left unchanged (they don't carry the above qualifiers).
    """
    shots = shots.copy()

    # (a) Direct flags on shot rows
    direct = pd.Series(False, index=shots.index)
    for col in _SP_SHOT_COLS:
        if col in shots.columns:
            direct |= shots[col].eq('Si')
    shots['_is_sp_shot'] = direct

    # (b) Indirect: shot preceded by a set-piece pass in the same match
    present_sp_pass = [c for c in _SP_PASS_COLS if c in bar.columns]
    if not present_sp_pass:
        return shots

    sort_cols = [c for c in ['match_id', 'period_id', 'time_min', 'time_sec']
                 if c in bar.columns]
    # reset_index() keeps a column 'index' = original bar index
    te = bar.sort_values(sort_cols).reset_index()

    sp_pass = pd.Series(False, index=te.index)
    for col in present_sp_pass:
        sp_pass |= te[col].eq('Si')
    sp_pass = sp_pass & (te['event_type'] == 'Pass')

    is_shot_te = te['event_type'].isin(_SHOT_TYPES)
    same_match = (
        (te['match_id'] == te['match_id'].shift(1, fill_value=''))
        if 'match_id' in te.columns
        else pd.Series(True, index=te.index)
    )
    # Row i is a shot that immediately follows a SP pass in the same match
    indirect = is_shot_te & sp_pass.shift(1, fill_value=False) & same_match

    orig_indirect_idx = set(te.loc[indirect, 'index'].tolist())
    shots['_is_sp_shot'] = shots['_is_sp_shot'] | shots.index.isin(orig_indirect_idx)
    return shots


def _get_bar_shots(bar: pd.DataFrame) -> pd.DataFrame:
    """Return BAR shot rows with xG and _is_sp_shot columns, excluding own goals."""
    shots = exclude_own_goals(
        bar[bar['event_type'].isin(_SHOT_TYPES)].copy()
    ).dropna(subset=['x', 'y'])
    if shots.empty:
        return shots
    shots = add_xg_column(shots)
    shots = _add_sp_flag(shots, bar)
    return shots


def _compute_key_pass_stats(bar: pd.DataFrame) -> pd.DataFrame:
    """
    Vectorised: for each BAR pass immediately followed by a shot (same match),
    record the player, whether it led to a goal, and the shot's xG (= xA credit).

    Returns DataFrame columns: player_name, is_goal_assist, shot_xg
    """
    _empty = pd.DataFrame(columns=['player_name', 'is_goal_assist', 'shot_xg'])
    if bar.empty:
        return _empty

    sort_cols = [c for c in ['match_id', 'period_id', 'time_min', 'time_sec']
                 if c in bar.columns]
    te = bar.sort_values(sort_cols).reset_index(drop=True)

    # Compute xG for shot rows
    is_shot = te['event_type'].isin(_SHOT_TYPES) & te['x'].notna() & te['y'].notna()
    te['_xg'] = 0.0
    if is_shot.any():
        shot_rows = add_xg_column(te[is_shot].copy())
        te.loc[shot_rows.index, '_xg'] = shot_rows['xg']
    te['_xg'] = te['_xg'].fillna(0.0)

    # Shift: look at what follows each event
    te['_next_etype'] = te['event_type'].shift(-1)
    te['_next_xg']    = te['_xg'].shift(-1, fill_value=0.0)
    te['_same_match'] = (
        te['match_id'] == te['match_id'].shift(-1)
        if 'match_id' in te.columns
        else pd.Series(True, index=te.index)
    )

    kp_mask = (
        (te['event_type'] == 'Pass') &
        te['_next_etype'].isin(_SHOT_TYPES) &
        te['_same_match'] &
        te['player_name'].notna()
    )
    if not kp_mask.any():
        return _empty

    kp = te[kp_mask][['player_name', '_next_etype', '_next_xg']].copy()
    kp.columns = ['player_name', 'next_type', 'shot_xg']
    kp['is_goal_assist'] = kp['next_type'] == 'Goal'
    return kp[['player_name', 'is_goal_assist', 'shot_xg']].reset_index(drop=True)


def _get_key_passes_for_map(bar: pd.DataFrame, map_shots: pd.DataFrame) -> pd.DataFrame:
    """
    Return BAR passes that are key passes for shots in map_shots.

    Two types:
      1. Standard KP  — pass immediately before (shift -1) any shot in map_shots.
      2. SP KP        — set-piece pass (Corner taken / Free kick taken / Throw In)
                        within 6 events before a shot that carries a SP qualifier
                        (From corner / Free kick / Set piece / Throw In set piece /
                        Corner situation). Catches multi-touch sequences such as
                        corner → header → shot where the corner kick itself is the
                        originating key pass.

    led_to_goal: True when any of the next 6 events in the same match is a Goal
    that is also present in map_shots.

    Returns DataFrame columns: x, y, end_x, end_y, player_name, led_to_goal
    """
    if bar.empty or map_shots.empty:
        return pd.DataFrame()

    sort_cols = [c for c in ['match_id', 'period_id', 'time_min', 'time_sec']
                 if c in bar.columns]
    te = bar.sort_values(sort_cols).reset_index()   # 'index' col = original bar index

    map_orig_idx   = set(map_shots.index.tolist())
    is_shot_in_map = te['event_type'].isin(_SHOT_TYPES) & te['index'].isin(map_orig_idx)

    same_match_fwd = (
        (te['match_id'] == te['match_id'].shift(-1, fill_value=''))
        if 'match_id' in te.columns else pd.Series(True, index=te.index)
    )
    te['_next_in_map'] = is_shot_in_map.shift(-1, fill_value=False)
    te['_next_etype']  = te['event_type'].shift(-1, fill_value='')

    # 1. Standard KP: pass directly before any shot in map_shots
    kp_mask = (te['event_type'] == 'Pass') & te['_next_in_map'] & same_match_fwd

    # 2. SP KP: set-piece pass within 6 events before a SP-qualified shot in map_shots
    _SP_PASS_PRESENT = [c for c in _SP_PASS_COLS if c in te.columns]
    _SP_SHOT_PRESENT = [c for c in _SP_SHOT_COLS if c in te.columns]

    if _SP_PASS_PRESENT and _SP_SHOT_PRESENT:
        sp_qual = pd.Series(False, index=te.index)
        for col in _SP_SHOT_PRESENT:
            sp_qual |= te[col].eq('Si')
        is_sp_shot_in_map = is_shot_in_map & sp_qual

        is_sp_pass = pd.Series(False, index=te.index)
        for col in _SP_PASS_PRESENT:
            is_sp_pass |= te[col].eq('Si')
        is_sp_pass = is_sp_pass & (te['event_type'] == 'Pass')

        for offset in range(1, 7):
            same_match_back = (
                (te['match_id'] == te['match_id'].shift(offset, fill_value=''))
                if 'match_id' in te.columns else pd.Series(True, index=te.index)
            )
            kp_mask = kp_mask | (
                is_sp_pass &
                is_sp_shot_in_map.shift(-offset, fill_value=False) &
                same_match_back
            )

    if not kp_mask.any():
        return pd.DataFrame()

    # led_to_goal: any of the next 6 events (same match) is a Goal in map_shots
    goal_orig_idx = set(
        map_shots[map_shots['event_type'] == 'Goal'].index.tolist()
        if 'event_type' in map_shots.columns else []
    )
    te['_led_to_goal'] = False
    for offset in range(1, 7):
        same_match_off = (
            (te['match_id'] == te['match_id'].shift(-offset, fill_value=''))
            if 'match_id' in te.columns else pd.Series(True, index=te.index)
        )
        te['_led_to_goal'] = te['_led_to_goal'] | (
            te['index'].shift(-offset, fill_value=-1).isin(goal_orig_idx) &
            same_match_off
        )

    kp = te[kp_mask].copy()

    end_x = (pd.to_numeric(kp['Pass End X'], errors='coerce')
             if 'Pass End X' in kp.columns else pd.Series(np.nan, index=kp.index))
    end_y = (pd.to_numeric(kp['Pass End Y'], errors='coerce')
             if 'Pass End Y' in kp.columns else pd.Series(np.nan, index=kp.index))

    result = pd.DataFrame({
        'x':           pd.to_numeric(kp['x'], errors='coerce').values,
        'y':           pd.to_numeric(kp['y'], errors='coerce').values,
        'end_x':       end_x.values,
        'end_y':       end_y.values,
        'player_name': kp['player_name'].values if 'player_name' in kp.columns else [None] * len(kp),
        'led_to_goal': kp['_led_to_goal'].values,
    })
    return result.dropna(subset=['x', 'y', 'end_x', 'end_y']).reset_index(drop=True)


def _get_carry_lines(events: pd.DataFrame, map_shots: pd.DataFrame) -> list[dict]:
    """
    For each key pass whose shot is in map_shots, trace any carry/dribble events
    (Take On / Carry / Ball touch by the shooter) between pass-end and shot.

    Returns list of {'points': [(opta_x, opta_y), …], 'led_to_goal': bool}.
    Only included when distance from pass-end to shot >= 4 Opta units.
    """
    if events.empty or map_shots.empty:
        return []

    sort_cols = [c for c in ['match_id', 'period_id', 'time_min', 'time_sec']
                 if c in events.columns]
    te = events.sort_values(sort_cols).reset_index()  # 'index' = original events idx

    map_orig_idx  = set(map_shots.index.tolist())
    goal_orig_idx = set(
        map_shots[map_shots['event_type'] == 'Goal'].index.tolist()
    )
    _carry_types = {'Take On', 'Carry', 'Ball touch'}

    is_shot_in_map = te['event_type'].isin(_SHOT_TYPES) & te['index'].isin(map_orig_idx)
    same_match_fwd = (
        (te['match_id'] == te['match_id'].shift(-1, fill_value=''))
        if 'match_id' in te.columns else pd.Series(True, index=te.index)
    )
    te['_next_in_map'] = is_shot_in_map.shift(-1, fill_value=False)
    kp_mask = (te['event_type'] == 'Pass') & te['_next_in_map'] & same_match_fwd

    _SP_PASS_PRESENT = [c for c in _SP_PASS_COLS if c in te.columns]
    _SP_SHOT_PRESENT = [c for c in _SP_SHOT_COLS if c in te.columns]
    if _SP_PASS_PRESENT and _SP_SHOT_PRESENT:
        sp_qual = pd.Series(False, index=te.index)
        for col in _SP_SHOT_PRESENT:
            sp_qual |= te[col].eq('Si')
        is_sp_shot_in_map = is_shot_in_map & sp_qual
        is_sp_pass = pd.Series(False, index=te.index)
        for col in _SP_PASS_PRESENT:
            is_sp_pass |= te[col].eq('Si')
        is_sp_pass = is_sp_pass & (te['event_type'] == 'Pass')
        for offset in range(1, 7):
            same_match_back = (
                (te['match_id'] == te['match_id'].shift(offset, fill_value=''))
                if 'match_id' in te.columns else pd.Series(True, index=te.index)
            )
            kp_mask = kp_mask | (
                is_sp_pass &
                is_sp_shot_in_map.shift(-offset, fill_value=False) &
                same_match_back
            )

    kp_positions = te.index[kp_mask].tolist()
    if not kp_positions:
        return []

    carry_lines: list[dict] = []
    for ki in kp_positions:
        kp_row = te.iloc[ki]
        pe_x = pd.to_numeric(kp_row.get('Pass End X'), errors='coerce')
        pe_y = pd.to_numeric(kp_row.get('Pass End Y'), errors='coerce')
        if pd.isna(pe_x) or pd.isna(pe_y):
            continue
        shot_pos, shot_row = None, None
        for j in range(ki + 1, min(ki + 8, len(te))):
            ev = te.iloc[j]
            if 'match_id' in te.columns and ev.get('match_id') != kp_row.get('match_id'):
                break
            if ev['event_type'] in _SHOT_TYPES and ev['index'] in map_orig_idx:
                shot_pos, shot_row = j, ev
                break
        if shot_pos is None:
            continue
        sx = pd.to_numeric(shot_row.get('x'), errors='coerce')
        sy = pd.to_numeric(shot_row.get('y'), errors='coerce')
        if pd.isna(sx) or pd.isna(sy):
            continue
        if ((float(sx) - float(pe_x)) ** 2 + (float(sy) - float(pe_y)) ** 2) ** 0.5 < 4.0:
            continue
        shooter = shot_row.get('player_name')
        led_to_goal = shot_row['index'] in goal_orig_idx
        mid_pts: list[tuple[float, float]] = []
        for k in range(ki + 1, shot_pos):
            ev = te.iloc[k]
            if ev['event_type'] in _carry_types and ev.get('player_name') == shooter:
                mx = pd.to_numeric(ev.get('x'), errors='coerce')
                my = pd.to_numeric(ev.get('y'), errors='coerce')
                if pd.notna(mx) and pd.notna(my):
                    mid_pts.append((float(mx), float(my)))
        pts = [(float(pe_x), float(pe_y))] + mid_pts + [(float(sx), float(sy))]
        carry_lines.append({'points': pts, 'led_to_goal': led_to_goal})

    return carry_lines


def _apply_shot_filters(shots: pd.DataFrame, *,
                        outcomes, method, bands, players,
                        h1_range, h2_range) -> pd.DataFrame:
    """Apply all active filters to a shots DataFrame."""
    if outcomes:
        shots = shots[shots['event_type'].isin(outcomes)]

    if method is not None:
        show_op = 'open_play' in method
        show_sp = 'set_piece' in method
        if show_op and not show_sp and 'Set piece' in shots.columns:
            shots = shots[~shots['Set piece'].eq('Si')]
        elif show_sp and not show_op and 'Set piece' in shots.columns:
            shots = shots[shots['Set piece'].eq('Si')]
        # both checked → show all; neither checked → empty

    if bands and len(bands) < 3 and 'y' in shots.columns:
        y = pd.to_numeric(shots['y'], errors='coerce')
        band_mask = pd.Series(False, index=shots.index)
        if 'left'   in bands: band_mask |= y > 66.67
        if 'centre' in bands: band_mask |= (y >= 33.33) & (y <= 66.67)
        if 'right'  in bands: band_mask |= y < 33.33
        shots = shots[band_mask]

    if players and 'player_name' in shots.columns:
        shots = shots[shots['player_name'].isin(players)]

    if 'period_id' in shots.columns and 'time_min' in shots.columns:
        h1_lo, h1_hi = h1_range
        h2_lo, h2_hi = h2_range
        m1 = (shots['period_id'] == 1) & (shots['time_min'] >= h1_lo) & (shots['time_min'] <= h1_hi)
        m2 = (shots['period_id'] == 2) & (shots['time_min'] >= h2_lo) & (shots['time_min'] <= h2_hi)
        shots = shots[m1 | m2]

    return shots


# =============================================================================
# KPI bar
# =============================================================================

def _kpi_children(shots: pd.DataFrame, kp_stats: pd.DataFrame) -> list:
    """Row of KPI stat cards spanning the full content width."""
    def _card(value, label, color=COLORS['text_primary'], preserve_case=False):
        return html.Div([
            html.Div(str(value), style={
                'color': color, 'fontWeight': '800',
                'fontSize': '1.35rem', 'lineHeight': '1.1',
            }),
            html.Div(label, style={
                'color': COLORS['text_secondary'],
                'fontSize': '0.60rem', 'fontWeight': '600',
                'letterSpacing': '0' if preserve_case else '0.6px',
                'textTransform': 'none' if preserve_case else 'uppercase',
                'marginTop': '3px',
            }),
        ], style={
            'backgroundColor': COLORS['dark_secondary'],
            'border': f'1px solid {COLORS["dark_border"]}',
            'borderRadius': '6px',
            'padding': '8px 10px',
            'flex': '1',
            'minWidth': '0',
        })

    total_shots = len(shots)
    shots_ot    = int(shots['event_type'].isin(['Goal', 'Saved Shot']).sum())
    goals_total = int((shots['event_type'] == 'Goal').sum())

    pen_goals = (
        int(shots[(shots['event_type'] == 'Goal') & shots['Penalty'].eq('Si')].shape[0])
        if 'Penalty' in shots.columns else 0
    )
    np_goals = goals_total - pen_goals

    sp_goals = (
        int(shots[(shots['event_type'] == 'Goal') &
                  shots['_is_sp_shot'].fillna(False)].shape[0])
        if '_is_sp_shot' in shots.columns else 0
    )

    xg_total    = round(shots['xg'].sum(), 2) if 'xg' in shots.columns else 0.0
    box_shots   = int((shots['x'] >= 83).sum()) if 'x' in shots.columns else 0
    big_chances = (
        int(shots['Big Chance'].eq('Si').sum())
        if 'Big Chance' in shots.columns else 0
    )

    assists  = int(kp_stats['is_goal_assist'].sum()) if not kp_stats.empty else 0
    xa_total = round(kp_stats['shot_xg'].sum(), 2)   if not kp_stats.empty else 0.0
    kp_total = len(kp_stats)

    cards = [
        _card(total_shots,          'Shots',        COLORS['text_primary']),
        _card(shots_ot,             'On Target',     HOME_COLOR),
        _card(np_goals,             'NP Goals',      GOLD),
        _card(sp_goals,             'Set Piece G',   COLORS['text_primary']),
        _card(f'{xg_total:.2f}',    'xG',            HOME_COLOR,             preserve_case=True),
        _card(assists,              'Assists',        GOLD),
        _card(kp_total,             'Key Passes',    COLORS['text_primary']),
        _card(f'{xa_total:.2f}',    'xA',            HOME_COLOR,             preserve_case=True),
        _card(box_shots,            'Box Shots',     COLORS['text_primary']),
        _card(big_chances,          'Big Chances',   GOLD),
    ]
    return [html.Div(cards, style={
        'display': 'flex', 'gap': '6px', 'flexWrap': 'wrap',
    })]


# =============================================================================
# Shot map
# =============================================================================

def _shot_map_fig(shots: pd.DataFrame,
                  key_passes: pd.DataFrame | None = None,
                  carry_lines: list | None = None) -> go.Figure:
    """Vertical half-pitch shot map. Dot size proportional to xG; goals are stars.

    key_passes: optional DataFrame (x, y, end_x, end_y, led_to_goal) —
                when provided, draws pass lines behind the shot markers.
                Gold thick line = pass led to goal; dim white = other key pass.
    carry_lines: optional list of {'points': [(opta_x, opta_y), …], 'led_to_goal': bool} —
                 when provided, draws dotted lines for carries between pass-end and shot.
    """
    fig = go.Figure()
    add_vertical_half_pitch_background(fig)

    _base = dict(
        **VPITCH_AXIS_HALF,
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor=PITCH_BG,
        height=520, margin=dict(l=0, r=0, t=8, b=0),
        hoverlabel=dict(bgcolor='#1A1D2E', font_color='white', font_size=12),
        legend=dict(
            x=0.01, y=0.01, xanchor='left', yanchor='bottom',
            orientation='v',
            font=dict(color=COLORS['text_primary'], size=10),
            bgcolor='rgba(26,29,46,0.80)',
            bordercolor=COLORS.get('dark_border', 'rgba(255,255,255,0.15)'),
            borderwidth=1,
        ),
    )

    # ── Pass lines (drawn first so shot markers render on top) ─────────────
    if key_passes is not None and not key_passes.empty:
        for is_goal_flag, color, lwidth, opacity, legend_label in [
            (False, 'rgba(210,210,210,0.35)', 1.2, 0.55, None),
            (True,  GOLD,                     2.4, 0.90, 'Goal Assist Pass'),
        ]:
            grp = key_passes[key_passes['led_to_goal'] == is_goal_flag]
            if grp.empty:
                continue

            # Vectorised segment builder: [x_start, x_end, NaN, ...]
            n = len(grp)
            xs = np.empty(n * 3); xs[:] = np.nan
            ys = np.empty(n * 3); ys[:] = np.nan
            # Vertical pitch: fig_x = 100 − Opta_y,  fig_y = Opta_x
            xs[0::3] = 100 - grp['y'].values
            xs[1::3] = 100 - grp['end_y'].values
            ys[0::3] = grp['x'].values
            ys[1::3] = grp['end_x'].values

            fig.add_trace(go.Scatter(
                x=xs.tolist(), y=ys.tolist(),
                mode='lines',
                line=dict(color=color, width=lwidth),
                opacity=opacity,
                showlegend=False,
                hoverinfo='skip',
            ))

            # Filled circle at the pass endpoint (arrowhead substitute)
            fig.add_trace(go.Scatter(
                x=(100 - grp['end_y']).tolist(),
                y=grp['end_x'].tolist(),
                mode='markers',
                name=legend_label or '',
                showlegend=bool(legend_label),
                marker=dict(
                    color=color, size=6 if not is_goal_flag else 8,
                    symbol='circle', opacity=opacity,
                    line=dict(color='white', width=0.8),
                ),
                hoverinfo='skip',
            ))

    # ── Carry / dribble lines (dotted, pass-end → shot) ─────────────────────
    if carry_lines:
        _legend_added: dict[str, bool] = {'goal': False, 'other': False}
        for cl in carry_lines:
            led_to_goal = cl['led_to_goal']
            color   = GOLD if led_to_goal else 'rgba(220,220,220,0.55)'
            opacity = 0.85 if led_to_goal else 0.55
            pts     = cl['points']
            fig_xs  = [100 - p[1] for p in pts]
            fig_ys  = [p[0]       for p in pts]
            key     = 'goal' if led_to_goal else 'other'
            show_lg = not _legend_added[key]
            fig.add_trace(go.Scatter(
                x=fig_xs, y=fig_ys, mode='lines',
                line=dict(color=color, width=2, dash='dot'),
                opacity=opacity,
                name=('Carry (goal)' if led_to_goal else 'Carry') if show_lg else '',
                showlegend=show_lg,
                hoverinfo='skip',
            ))
            _legend_added[key] = True

    # ── Shot markers ───────────────────────────────────────────────────────
    if not shots.empty and 'x' in shots.columns:
        for etype in _SHOT_TYPES:
            grp = shots[shots['event_type'] == etype].copy()
            if grp.empty:
                continue

            # Vertical pitch mapping: fig_x = 100 − Opta_y, fig_y = Opta_x
            fig_x = (100 - grp['y']).tolist()
            fig_y = grp['x'].tolist()

            xg_vals = (grp['xg'].fillna(0.0).tolist()
                       if 'xg' in grp.columns else [0.0] * len(grp))
            sizes = ([16] * len(grp) if etype == 'Goal'
                     else [max(8, min(20, int(v * 60 + 8))) for v in xg_vals])

            player_names = (grp['player_name'].fillna('Unknown').tolist()
                            if 'player_name' in grp.columns else ['Unknown'] * len(grp))
            times = (grp['time_min'].fillna(0).astype(int).tolist()
                     if 'time_min' in grp.columns else [0] * len(grp))

            fig.add_trace(go.Scatter(
                x=fig_x, y=fig_y,
                mode='markers', name=etype,
                marker=dict(
                    color=_OUTCOME_COLOR.get(etype, GOLD),
                    symbol=_OUTCOME_SYMBOL.get(etype, 'circle'),
                    size=sizes, opacity=0.88,
                    line=dict(color='white', width=1),
                ),
                customdata=list(zip(player_names, times, xg_vals)),
                hovertemplate=(
                    '<b>%{customdata[0]}</b><br>'
                    "%{customdata[1]}' | xG: %{customdata[2]:.2f}"
                    '<extra>' + etype + '</extra>'
                ),
            ))

    fig.update_layout(**_base)
    return fig


# =============================================================================
# Tables
# =============================================================================

def _scorers_table_children(shots: pd.DataFrame, top_n: int = 8) -> list:
    """Top-N goalscorer table: Player | G | NP-G | Sh | xG | Conv%"""
    _no_data = [html.P("No data", style={
        'color': COLORS['text_secondary'], 'fontSize': '0.75rem', 'textAlign': 'center',
    })]
    if shots.empty or 'player_name' not in shots.columns:
        return _no_data

    rows_data = []
    for player, grp in shots.groupby('player_name'):
        g  = int((grp['event_type'] == 'Goal').sum())
        if 'Penalty' in grp.columns:
            np_g = int(grp[(grp['event_type'] == 'Goal') &
                           ~grp['Penalty'].eq('Si')].shape[0])
        else:
            np_g = g
        sh   = len(grp)
        xg   = round(grp['xg'].sum(), 2) if 'xg' in grp.columns else 0.0
        conv = round(g / max(sh, 1) * 100)
        rows_data.append({'player': player, 'g': g, 'np_g': np_g,
                          'sh': sh, 'xg': xg, 'conv': conv})

    rows_data.sort(key=lambda x: (x['g'], x['xg']), reverse=True)
    rows_data = rows_data[:top_n]

    if not rows_data:
        return _no_data

    header = html.Tr([
        html.Th('Player', style={**_TH, 'textAlign': 'left'}),
        html.Th('G',      style=_TH),
        html.Th('NP-G',   style=_TH),
        html.Th('Sh',     style=_TH),
        html.Th('xG',     style=_TH_NOCASE),
        html.Th('Conv%',  style=_TH),
    ])
    table_rows = []
    for i, s in enumerate(rows_data):
        bg = (COLORS.get('dark_tertiary', 'rgba(255,255,255,0.03)')
              if i % 2 == 0 else 'transparent')
        short = s['player'].split()[-1] if s['player'] else '—'
        conv_color = (GOLD if s['conv'] >= 25
                      else COLORS['garnet'] if s['conv'] < 10
                      else COLORS['text_primary'])
        table_rows.append(html.Tr([
            html.Td(short,             style=_NAME),
            html.Td(str(s['g']),       style={**_TD, 'color': GOLD}),
            html.Td(str(s['np_g']),    style=_TD),
            html.Td(str(s['sh']),      style=_TD),
            html.Td(f"{s['xg']:.1f}",  style={**_TD, 'color': HOME_COLOR}),
            html.Td(f"{s['conv']}%",   style={**_TD, 'color': conv_color}),
        ], style={'backgroundColor': bg}))

    return [html.Div(
        html.Table([html.Thead(header), html.Tbody(table_rows)],
                   style={'width': '100%', 'borderCollapse': 'collapse'}),
        style={'overflowX': 'auto'},
    )]


def _assisters_table_children(kp_stats: pd.DataFrame, top_n: int = 8) -> list:
    """Top-N assister table: Player | A | KP | xA"""
    _no_data = [html.P("No data", style={
        'color': COLORS['text_secondary'], 'fontSize': '0.75rem', 'textAlign': 'center',
    })]
    if kp_stats.empty or 'player_name' not in kp_stats.columns:
        return _no_data

    rows_data = []
    for player, grp in kp_stats.groupby('player_name'):
        a  = int(grp['is_goal_assist'].sum())
        kp = len(grp)
        xa = round(grp['shot_xg'].sum(), 2)
        rows_data.append({'player': player, 'a': a, 'kp': kp, 'xa': xa})

    rows_data.sort(key=lambda x: (x['a'], x['xa']), reverse=True)
    rows_data = rows_data[:top_n]

    if not rows_data:
        return _no_data

    header = html.Tr([
        html.Th('Player', style={**_TH, 'textAlign': 'left'}),
        html.Th('A',      style=_TH),
        html.Th('KP',     style=_TH),
        html.Th('xA',     style=_TH_NOCASE),
    ])
    table_rows = []
    for i, s in enumerate(rows_data):
        bg = (COLORS.get('dark_tertiary', 'rgba(255,255,255,0.03)')
              if i % 2 == 0 else 'transparent')
        short = s['player'].split()[-1] if s['player'] else '—'
        table_rows.append(html.Tr([
            html.Td(short,            style=_NAME),
            html.Td(str(s['a']),      style={**_TD, 'color': GOLD}),
            html.Td(str(s['kp']),     style=_TD),
            html.Td(f"{s['xa']:.2f}", style={**_TD, 'color': HOME_COLOR}),
        ], style={'backgroundColor': bg}))

    return [html.Div(
        html.Table([html.Thead(header), html.Tbody(table_rows)],
                   style={'width': '100%', 'borderCollapse': 'collapse'}),
        style={'overflowX': 'auto'},
    )]


# =============================================================================
# Filter panel
# =============================================================================

def _filter_panel(player_options=None) -> html.Div:
    return html.Div([
        html.Div("Filters", style=_SECTION_TITLE),

        html.Div("Player", style=_LABEL_STYLE),
        dcc.Dropdown(
            id='cc-player-filter',
            options=player_options or [],
            value=None,
            multi=True,
            placeholder="All players…",
            style={'fontSize': '0.75rem'},
        ),

        html.Hr(style={'borderColor': COLORS['dark_border'], 'margin': '10px 0 4px'}),
        html.Div("Shot Outcome", style=_LABEL_STYLE),
        dcc.Checklist(
            id='cc-shot-outcome',
            options=[
                {'label': ' Goal',         'value': 'Goal'},
                {'label': ' Saved Shot',   'value': 'Saved Shot'},
                {'label': ' Miss',         'value': 'Miss'},
                {'label': ' Post',         'value': 'Post'},
                {'label': ' Blocked Shot', 'value': 'Blocked Shot'},
            ],
            value=['Goal', 'Saved Shot', 'Miss', 'Post', 'Blocked Shot'],
            inputStyle={'cursor': 'pointer', 'accentColor': GOLD},
            labelStyle={'color': COLORS['text_secondary'], 'fontSize': '0.75rem',
                        'display': 'block', 'marginBottom': '4px'},
        ),

        html.Hr(style={'borderColor': COLORS['dark_border'], 'margin': '10px 0 4px'}),
        html.Div("Band", style=_LABEL_STYLE),
        dcc.Checklist(
            id='cc-bands',
            options=[
                {'label': ' Left',   'value': 'left'},
                {'label': ' Centre', 'value': 'centre'},
                {'label': ' Right',  'value': 'right'},
            ],
            value=['left', 'centre', 'right'],
            inline=True,
            inputStyle={'cursor': 'pointer', 'accentColor': GOLD, 'marginRight': '4px'},
            labelStyle={'color': COLORS['text_secondary'], 'fontSize': '0.75rem',
                        'marginRight': '10px'},
        ),

        html.Hr(style={'borderColor': COLORS['dark_border'], 'margin': '10px 0 4px'}),
        html.Div("Shot Origin", style=_LABEL_STYLE),
        dcc.Checklist(
            id='cc-shot-method',
            options=[
                {'label': ' Open Play', 'value': 'open_play'},
                {'label': ' Set Piece', 'value': 'set_piece'},
            ],
            value=['open_play', 'set_piece'],
            inline=True,
            inputStyle={'cursor': 'pointer', 'accentColor': GOLD, 'marginRight': '4px'},
            labelStyle={'color': COLORS['text_secondary'], 'fontSize': '0.75rem',
                        'marginRight': '10px'},
        ),

        *PassMap.dash_controls(show=['h1_time', 'h2_time'], id_prefix='cc'),
    ], style=_PANEL_STYLE)


# =============================================================================
# Public builder
# =============================================================================

def build_chance_creation_tab(season, competitions, match_ids=None) -> html.Div:
    """Skeleton layout — all data filled by register_chance_creation_callbacks."""
    events = get_all_events(season)
    if events.empty:
        return html.P("No data available.", style={'color': COLORS['text_secondary']})

    if competitions and 'competition' in events.columns:
        events = events[events['competition'].isin(competitions)]
    if match_ids:
        events = events[events['match_id'].isin(match_ids)]

    bar = events[events['team_code'] == 'BAR']
    if bar.empty:
        return html.P("No Barcelona event data.", style={'color': COLORS['text_secondary']})

    # Player options seeded from all available shots
    shots = exclude_own_goals(
        bar[bar['event_type'].isin(_SHOT_TYPES)].copy()
    )
    player_opts = []
    if 'player_name' in shots.columns:
        names = shots['player_name'].dropna().unique()
        player_opts = sorted([{'label': n, 'value': n} for n in names],
                             key=lambda d: d['label'])

    # --- Main content panel (right of filter) ---
    main_content = html.Div([
        # KPI bar — full width of content area
        html.Div(id='cc-kpi-bar', children=[]),
        html.Hr(style={'borderColor': COLORS['dark_border'], 'margin': '10px 0 14px'}),

        # Shot map (md=8 of the 9-col content) | Tables (md=4 of 9)
        dbc.Row([
            dbc.Col([
                html.Div([
                    html.Div("Shot Map",
                             style={**_SECTION_TITLE, 'borderBottom': 'none',
                                    'paddingBottom': '0', 'flex': '1'}),
                    dcc.Checklist(
                        id='cc-show-kp',
                        options=[{'label': ' Key passes', 'value': 'show'}],
                        value=[],
                        inputStyle={'cursor': 'pointer', 'accentColor': GOLD},
                        labelStyle={'color': COLORS['text_secondary'],
                                    'fontSize': '0.60rem', 'cursor': 'pointer'},
                    ),
                ], style={
                    'display': 'flex', 'alignItems': 'center', 'gap': '8px',
                    'borderBottom': f'1px solid {COLORS["dark_border"]}',
                    'paddingBottom': '8px', 'marginBottom': '8px',
                }),
                dcc.Loading(
                    type='circle', color=GOLD,
                    children=dcc.Graph(
                        id='cc-shot-map',
                        figure=_skel_fig(520),
                        config=CHART_CFG,
                        style={'width': '100%'},
                    ),
                ),
                html.Hr(style={'borderColor': COLORS['dark_border'],
                               'margin': '14px 0 10px'}),
                html.Div("Shooting Zones",
                         style={**_SECTION_TITLE, 'fontSize': '0.75rem',
                                'borderBottom': 'none', 'paddingBottom': '4px'}),
                html.Div("Shot density by pitch zone — count and share per zone",
                         style={'color': COLORS['text_secondary'], 'fontSize': '0.62rem',
                                'fontStyle': 'italic', 'marginBottom': '6px'}),
                html.Img(id='cc-zone-map', style={'width': '100%', 'borderRadius': '6px'}),
            ], md=8),

            dbc.Col([
                html.Div("Top Scorers",
                         style={**_SECTION_TITLE, 'fontSize': '0.75rem'}),
                html.Div(style={'marginBottom': '6px'}),
                html.Div(id='cc-scorers-table', children=[]),

                html.Hr(style={'borderColor': COLORS['dark_border'],
                               'margin': '16px 0 12px'}),

                html.Div("Top Assisters",
                         style={**_SECTION_TITLE, 'fontSize': '0.75rem'}),
                html.Div(style={'marginBottom': '6px'}),
                html.Div(id='cc-assisters-table', children=[]),
            ], md=4, style={
                'borderLeft': f'1px solid {COLORS["dark_border"]}',
                'paddingLeft': '14px',
            }),
        ], align='start', className='g-0'),
    ], style=_PANEL_STYLE)

    return html.Div(
        dbc.Row([
            dbc.Col(_filter_panel(player_opts), md=2),
            dbc.Col(main_content,               md=10),
        ], align='start', className='g-3'),
    )


# =============================================================================
# Callbacks
# =============================================================================

def register_chance_creation_callbacks(app) -> None:
    """Wire filter controls to the shot map, KPI bar, and stat tables."""

    @app.callback(
        Output('cc-kpi-bar',            'children'),
        Output('cc-shot-map',           'figure'),
        Output('cc-zone-map',           'src'),
        Output('cc-scorers-table',      'children'),
        Output('cc-assisters-table',    'children'),
        Input('cc-player-filter',    'value'),
        Input('cc-shot-outcome',     'value'),
        Input('cc-shot-method',      'value'),
        Input('cc-bands',            'value'),
        Input('cc-h1-time',          'value'),
        Input('cc-h2-time',          'value'),
        Input('cc-show-kp',          'value'),
        State('ta-competition-selector', 'value'),
        State('ta-venue-selector',       'value'),
        State('ta-selected-matches',     'data'),
        State('ta-match-data',           'data'),
    )
    def _update(players, outcomes, method, bands, h1_range, h2_range, show_kp,
                competition, venue, match_ids, match_data):

        def _empty():
            return [], _skel_fig(520), '', [], []

        events = get_all_events(CURRENT_SEASON)
        if events.empty:
            return _empty()

        comps = _normalize_competitions(competition)
        if comps and 'competition' in events.columns:
            events = events[events['competition'].isin(comps)]

        effective_ids = match_ids if match_ids else None
        if effective_ids == []:
            effective_ids = None

        if venue and venue != 'All' and match_data:
            is_home   = (venue == 'Home')
            venue_ids = [m['match_id'] for m in match_data if m.get('is_home') == is_home]
            effective_ids = (
                venue_ids if effective_ids is None
                else list(set(effective_ids) & set(venue_ids))
            )

        if effective_ids:
            events = events[events['match_id'].isin(effective_ids)]

        bar = events[events['team_code'] == 'BAR']
        if bar.empty:
            return _empty()

        _h1 = tuple(h1_range) if h1_range else (0,  50)
        _h2 = tuple(h2_range) if h2_range else (45, 100)

        # All shots for KPIs and tables (outcome/method filters don't affect stats)
        all_shots = _get_bar_shots(bar)
        kpi_shots = _apply_shot_filters(
            all_shots.copy(),
            outcomes=_SHOT_TYPES,
            method=['open_play', 'set_piece'],
            bands=bands or ['left', 'centre', 'right'],
            players=players or None,
            h1_range=_h1, h2_range=_h2,
        )

        # Shot map respects all filters including outcome, method, and bands
        map_shots = _apply_shot_filters(
            all_shots.copy(),
            outcomes=outcomes  or _SHOT_TYPES,
            method=method      or ['open_play', 'set_piece'],
            bands=bands        or ['left', 'centre', 'right'],
            players=players    or None,
            h1_range=_h1, h2_range=_h2,
        )

        # Key pass stats for KPIs and assister table (player + time filter only)
        kp_stats = _compute_key_pass_stats(bar)
        if players and 'player_name' in kp_stats.columns:
            kp_stats = kp_stats[kp_stats['player_name'].isin(players)]

        kpi   = _kpi_children(kpi_shots, kp_stats)

        kp_for_map = (
            _get_key_passes_for_map(bar, map_shots)
            if show_kp else None
        )
        carry_lines_data = (
            _get_carry_lines(bar, map_shots)
            if show_kp else []
        )
        fig        = _shot_map_fig(map_shots, kp_for_map, carry_lines_data)

        zone_src = ''
        if not map_shots.empty and 'x' in map_shots.columns:
            xs = map_shots['x'].dropna().tolist()
            ys = map_shots['y'].dropna().tolist()
            if len(xs) >= 2:
                zone_src = render_lsc_heatmap_img(
                    xs, ys, HOME_COLOR, half=True, show_zone_pcts=True, vertical=True,
                )

        scors = _scorers_table_children(kpi_shots)
        assts = _assisters_table_children(kp_stats)

        return kpi, fig, zone_src, scors, assts
