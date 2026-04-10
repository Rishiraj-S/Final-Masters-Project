"""
Team Analysis — Tab 5: Set Pieces

Three sub-tabs:
  • Free-Kicks  — direct and indirect free kick analysis
  • Corners     — corner delivery types and outcomes
  • Penalties   — penalty record and shot placement

Skeleton + callback pattern: skeletons render instantly; data is populated
asynchronously by each sub-tab's own callback.
"""

import pandas as pd
from dash import html, dcc, Input, Output, State
import dash_bootstrap_components as dbc
import plotly.graph_objects as go

from utils.config import COLORS
from utils.data_utils import get_all_events, CURRENT_SEASON
from page_utils import PassMap, GOLD, HOME_COLOR, AWAY_COLOR
from page_utils.competitions import normalize_competitions as _normalize_competitions
from page_utils.visualizations import (
    add_pitch_background,
    add_vertical_half_pitch_background,
    PITCH_AXIS_FULL,
    PITCH_AXIS_HALF,
    VPITCH_AXIS_HALF,
    PITCH_BG,
)
from page_utils.event_filters import SHOT_TYPES as _SHOT_TYPES


# =============================================================================
# Constants
# =============================================================================
_SKEL_SRC = 'data:image/png;base64,'

CHART_CFG = {'displayModeBar': False}

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
_TD = {
    'textAlign': 'center', 'padding': '4px 6px',
    'fontSize': '0.68rem', 'fontWeight': '600',
    'color': COLORS['text_primary'], 'whiteSpace': 'nowrap',
}
_NAME_TD = {
    **_TD, 'textAlign': 'left', 'color': GOLD,
    'maxWidth': '100px', 'overflow': 'hidden', 'textOverflow': 'ellipsis',
}

_BTN_BASE = {
    'display': 'block', 'width': '100%', 'textAlign': 'center',
    'padding': '20px 0', 'fontWeight': '700', 'fontSize': '1rem',
    'letterSpacing': '0.6px', 'textTransform': 'uppercase',
    'backgroundColor': COLORS['dark_secondary'],
    'border': f'1px solid {COLORS["dark_border"]}', 'borderRadius': '0',
}
_BTN_INACTIVE = {**_BTN_BASE, 'color': COLORS['text_secondary']}
_BTN_ACTIVE   = {
    **_BTN_BASE, 'color': GOLD,
    'backgroundColor': 'rgba(237, 187, 0, 0.08)',
    'borderBottom': f'3px solid {GOLD}',
}

# ── Set piece event types & qualifiers ────────────────────────────────────────
_SHOT_COLORS = {
    'Goal':         '#22c55e',
    'Saved Shot':   '#3b82f6',
    'Miss':         '#ef4444',
    'Post':         GOLD,
    'Blocked Shot': '#cc5de8',
}
_SHOT_SYMBOLS = {
    'Goal':         'star',
    'Saved Shot':   'circle',
    'Miss':         'x',
    'Post':         'diamond',
    'Blocked Shot': 'square',
}

_DELIVERY_COLORS = {
    'Inswinger':  '#3b82f6',
    'Outswinger': '#f97316',
    'Short':      '#9ca3af',
}  # kept for _corner_delivery_type label lookups


_ROW_STYLE = {'borderBottom': f'1px solid {COLORS["dark_border"]}'}


# =============================================================================
# Shared helpers
# =============================================================================

def _skel_fig(height: int = 480) -> go.Figure:
    fig = go.Figure()
    fig.update_layout(
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor=PITCH_BG,
        height=height, margin=dict(l=0, r=0, t=36, b=0),
    )
    return fig


def _kpi_card(value, label, color=None) -> html.Div:
    return html.Div([
        html.Div(str(value), style={
            'color': color or COLORS['text_primary'],
            'fontWeight': '800', 'fontSize': '1.35rem', 'lineHeight': '1.1',
        }),
        html.Div(label, style={
            'color': COLORS['text_secondary'],
            'fontSize': '0.60rem', 'fontWeight': '600',
            'letterSpacing': '0.6px', 'textTransform': 'uppercase',
            'marginTop': '3px',
        }),
    ], style={
        'backgroundColor': COLORS['dark_secondary'],
        'border': f'1px solid {COLORS["dark_border"]}',
        'borderRadius': '6px', 'padding': '8px 10px',
        'flex': '1', 'minWidth': '0',
    })


def _kpi_bar(cards: list) -> list:
    return [html.Div(cards, style={
        'display': 'flex', 'gap': '8px', 'flexWrap': 'wrap', 'marginBottom': '4px',
    })]


def _no_data():
    return html.Div("No data", style={
        'color': COLORS['text_secondary'], 'fontSize': '0.7rem', 'padding': '4px',
    })


def _apply_global_filters(events, competition, venue, match_ids, match_data):
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

    return events


def _attack_arrow(fig):
    """Horizontal: right-pointing direction-of-attack annotation."""
    fig.add_annotation(
        text='→  Direction of Attack',
        x=76, y=-1, xref='x', yref='y',
        showarrow=False,
        font=dict(size=9, color='white', family='Arial'),
        bgcolor='#151932', bordercolor='#8899CC', borderwidth=1, borderpad=4,
    )


# =============================================================================
# FREE-KICKS  —  data helpers
# =============================================================================

def _fk_kpi_children(fk_passes: pd.DataFrame, fk_shots: pd.DataFrame) -> list:
    total     = len(fk_passes)
    completed = int((fk_passes['outcome'] == 1).sum()) if not fk_passes.empty else 0
    comp_pct  = f'{completed / total * 100:.0f}%' if total else '-'
    n_shots   = len(fk_shots)
    n_goals   = int((fk_shots['event_type'] == 'Goal').sum()) if not fk_shots.empty else 0
    on_tgt    = int((fk_shots['event_type'] == 'Saved Shot').sum()) if not fk_shots.empty else 0

    return _kpi_bar([
        _kpi_card(total,     'Total FKs',   HOME_COLOR),
        _kpi_card(completed, 'Completed',   HOME_COLOR),
        _kpi_card(comp_pct,  'Completion %', GOLD),
        _kpi_card(n_shots,   'Shots',        HOME_COLOR),
        _kpi_card(on_tgt,    'On Target',    HOME_COLOR),
        _kpi_card(n_goals,   'Goals',        GOLD),
    ])


def _add_receiver_name(bar: pd.DataFrame) -> pd.DataFrame:
    """Add a 'receiver_name' column to BAR events.

    For completed passes, receiver = player_name of the next event in the same
    match (sorted chronologically). Incomplete passes get an empty string.
    """
    bar = bar.copy()
    bar['receiver_name'] = ''
    if bar.empty:
        return bar

    sort_cols = [c for c in ['match_id', 'period_id', 'time_min', 'time_sec']
                 if c in bar.columns]
    te = bar.sort_values(sort_cols).reset_index()   # 'index' = original df index

    same_match = (
        (te['match_id'] == te['match_id'].shift(-1, fill_value=''))
        if 'match_id' in te.columns
        else pd.Series(True, index=te.index)
    )
    suc = (
        pd.to_numeric(te.get('outcome', pd.Series()), errors='coerce').eq(1)
        if 'outcome' in te.columns
        else pd.Series(False, index=te.index)
    )
    suc_pass = (te['event_type'] == 'Pass') & suc & same_match

    if suc_pass.any():
        next_player = te['player_name'].shift(-1, fill_value='') if 'player_name' in te.columns \
                      else pd.Series('', index=te.index)
        orig_idx = te.loc[suc_pass, 'index'].values
        bar.loc[orig_idx, 'receiver_name'] = next_player[suc_pass].fillna('').values

    return bar


def _add_shot_goal_lookahead(bar: pd.DataFrame) -> pd.DataFrame:
    """Add led_to_shot and led_to_goal boolean columns to BAR events.

    Uses a 5-event forward window within the same match, identical to the
    approach in buildup._build_entries_bar.
    """
    bar = bar.copy()
    bar['led_to_shot'] = False
    bar['led_to_goal'] = False
    if bar.empty:
        return bar

    sort_cols = [c for c in ['match_id', 'period_id', 'time_min', 'time_sec']
                 if c in bar.columns]
    te = bar.sort_values(sort_cols).reset_index()   # 'index' = original df index

    is_shot = te['event_type'].isin(_SHOT_TYPES)
    is_goal = te['event_type'] == 'Goal'

    led_shot = pd.Series(False, index=te.index)
    led_goal = pd.Series(False, index=te.index)
    for _off in range(1, 6):
        same_match = (
            (te['match_id'] == te['match_id'].shift(-_off, fill_value=''))
            if 'match_id' in te.columns
            else pd.Series(True, index=te.index)
        )
        led_shot |= is_shot.shift(-_off, fill_value=False) & same_match
        led_goal |= is_goal.shift(-_off, fill_value=False) & same_match

    orig_idx = te['index'].values
    bar.loc[orig_idx, 'led_to_shot'] = led_shot.values
    bar.loc[orig_idx, 'led_to_goal'] = led_goal.values
    return bar


def _fk_shot_map_fig(fk_shots: pd.DataFrame) -> go.Figure:
    """FK direct shots on a vertical half-pitch (goal at top).

    Coordinate swap for vertical pitch:
        plot x = Opta y  (left–right)
        plot y = Opta x  (depth, 50=centre → 100=goal)
    """
    fig = go.Figure()
    add_vertical_half_pitch_background(fig)

    if not fk_shots.empty:
        has_player = 'player_name' in fk_shots.columns
        has_time   = 'time_min' in fk_shots.columns

        for etype in _SHOT_TYPES:
            grp = fk_shots[fk_shots['event_type'] == etype]
            if grp.empty:
                continue

            customdata = None
            hover_tmpl = None
            if has_player and has_time:
                customdata = grp[['player_name', 'time_min']].values
                hover_tmpl = (
                    '<b>%{customdata[0]}</b><br>'
                    f'{etype} · %{{customdata[1]}}\''
                    '<extra></extra>'
                )

            fig.add_trace(go.Scatter(
                x=(100 - grp['y']).tolist(),  # Opta y → horizontal axis (flipped to match chance_creation)
                y=grp['x'].tolist(),          # Opta x → vertical axis (goal at top)
                mode='markers',
                marker=dict(
                    color=_SHOT_COLORS.get(etype, '#999'),
                    size=14 if etype == 'Goal' else 10,
                    symbol=_SHOT_SYMBOLS.get(etype, 'circle'),
                    line=dict(color='white', width=0.8),
                    opacity=0.9,
                ),
                name=etype,
                customdata=customdata,
                hovertemplate=hover_tmpl,
            ))

    fig.update_layout(
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor=PITCH_BG,
        height=520, margin=dict(l=0, r=0, t=8, b=0),
        legend=dict(
            font=dict(color='white', size=9), bgcolor='rgba(0,0,0,0)',
            orientation='h', yanchor='bottom', y=1.01, xanchor='right', x=1,
        ),
        uirevision='sp-fk-shot-map',
        **VPITCH_AXIS_HALF,
    )
    return fig


# =============================================================================
# FREE-KICKS  —  Zone 3 entry helpers
# =============================================================================

def _fk_zone3_entries_df(fk_passes: pd.DataFrame, zone: str) -> pd.DataFrame:
    """Filter FK passes that enter the specified zone.

    zone: 'final_third' — passes whose endpoint crosses x=66.67
          'penalty_box' — passes whose endpoint lands inside the penalty area
                          (x >= 83.1, y 21.1–78.9)
    """
    if fk_passes.empty:
        return pd.DataFrame()
    if 'Pass End X' not in fk_passes.columns or 'Pass End Y' not in fk_passes.columns:
        return pd.DataFrame()

    ev = fk_passes.copy()
    ev['end_x'] = pd.to_numeric(ev['Pass End X'], errors='coerce')
    ev['end_y'] = pd.to_numeric(ev['Pass End Y'], errors='coerce')
    ev['x']     = pd.to_numeric(ev['x'], errors='coerce')
    ev['y']     = pd.to_numeric(ev['y'], errors='coerce')
    ev = ev.dropna(subset=['x', 'y', 'end_x', 'end_y'])
    if ev.empty:
        return pd.DataFrame()

    sx = ev['x']
    ex = ev['end_x']
    ey = ev['end_y']

    if zone == 'final_third':
        ev = ev[(sx < 66.67) & (ex >= 66.67)].copy()
    elif zone == 'penalty_box':
        in_box = (ex >= 83.1) & (ey >= 21.1) & (ey <= 78.9)
        ev = ev[in_box].copy()

    return ev.reset_index(drop=True)


def _fk_zone3_fig(entries_df: pd.DataFrame, zone: str) -> go.Figure:
    """FK pass entries into final third or penalty box on a full horizontal pitch.

    Green arrows = completed passes, red arrows = incomplete.
    """
    fig = go.Figure()
    add_pitch_background(fig, half=False)

    if not entries_df.empty:
        new_annotations: list = []
        for outcome_val, color, label in [(1, '#22c55e', 'Completed'), (0, '#ef4444', 'Incomplete')]:
            if 'outcome' not in entries_df.columns:
                grp = entries_df if outcome_val == 1 else pd.DataFrame()
            else:
                grp = entries_df[entries_df['outcome'] == outcome_val]
            if grp.empty:
                continue

            _ann = dict(
                xref='x', yref='y', axref='x', ayref='y',
                showarrow=True, arrowhead=2, arrowsize=1.5,
                arrowwidth=2, arrowcolor=color, opacity=0.65,
            )
            for _, r in grp.iterrows():
                new_annotations.append({**_ann,
                    'x': r['end_x'], 'y': r['end_y'],
                    'ax': r['x'],    'ay': r['y']})

            has_player   = 'player_name'   in grp.columns
            has_receiver = 'receiver_name' in grp.columns
            has_time     = 'time_min'      in grp.columns

            if has_player and has_receiver and has_time:
                cd = grp[['player_name', 'receiver_name', 'time_min']].values
                if outcome_val == 1:
                    ht = (
                        '<b>From:</b> %{customdata[0]}<br>'
                        '<b>To:</b> %{customdata[1]}<br>'
                        '<b>Outcome:</b> ✓ Completed<br>'
                        "%{customdata[2]}'"
                        '<extra></extra>'
                    )
                else:
                    ht = (
                        '<b>From:</b> %{customdata[0]}<br>'
                        '<b>Outcome:</b> ✗ Incomplete<br>'
                        "%{customdata[2]}'"
                        '<extra></extra>'
                    )
            elif has_player and has_time:
                cd = grp[['player_name', 'time_min']].values
                ht = (
                    '<b>From:</b> %{customdata[0]}<br>'
                    f'<b>Outcome:</b> {"✓ Completed" if outcome_val == 1 else "✗ Incomplete"}<br>'
                    "%{customdata[1]}'"
                    '<extra></extra>'
                )
            else:
                cd = None
                ht = None

            fig.add_trace(go.Scatter(
                x=grp['end_x'].tolist(), y=grp['end_y'].tolist(),
                mode='markers',
                marker=dict(size=7, color=color,
                            line=dict(width=1.5, color='white'), opacity=0.88),
                name=f'{label} ({len(grp)})',
                customdata=cd,
                hovertemplate=ht,
                showlegend=True,
            ))

        if new_annotations:
            fig.update_layout(annotations=list(fig.layout.annotations) + new_annotations)

    # Zone boundary
    if zone == 'final_third':
        fig.add_shape(type='line', x0=66.67, y0=0, x1=66.67, y1=100,
                      line=dict(color='yellow', width=3, dash='dash'))
        fig.add_annotation(x=83, y=96, text='Final Third', showarrow=False,
                           font=dict(color='yellow', size=11, family='Arial Black'),
                           bgcolor='rgba(0,0,0,0.5)', borderpad=4)
    elif zone == 'penalty_box':
        fig.add_shape(type='rect', x0=83.1, y0=21.1, x1=100, y1=78.9,
                      line=dict(color='#00bfff', width=2, dash='dash'),
                      fillcolor='rgba(0,191,255,0.06)')
        fig.add_annotation(x=91.5, y=83, text='Penalty Box', showarrow=False,
                           font=dict(color='#00bfff', size=11, family='Arial Black'),
                           bgcolor='rgba(0,0,0,0.5)', borderpad=4)

    _attack_arrow(fig)
    fig.update_layout(
        **PITCH_AXIS_FULL,
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor=PITCH_BG,
        height=480, margin=dict(l=0, r=0, t=36, b=0),
        uirevision=f'sp-fk-zone3-{zone}',
        hovermode='closest',
        legend=dict(
            font=dict(color='white', size=9), bgcolor='rgba(0,0,0,0.55)',
            orientation='v', x=0.01, xanchor='left', y=0.99, yanchor='top',
        ),
    )
    return fig


def _fk_zone3_table_children(entries_df: pd.DataFrame, top_n: int = 8) -> list:
    """Per-player outcome table for FK Zone 3 entries.

    Columns: Player | # | Comp | Comp% | Shots | Shot% | Goals | Goal%

    Comp%  — completion rate of the FK delivery.
    Shot%  — % of entries followed by a shot within 5 events.
    Goal%  — % of entries followed by a goal within 5 events (≈ assist rate).
    """
    if entries_df.empty or 'player_name' not in entries_df.columns:
        return [_no_data()]

    rows_data = []
    for player, grp in entries_df.groupby('player_name'):
        total    = len(grp)
        comp     = int(grp['outcome'].eq(1).sum()) if 'outcome' in grp.columns else 0
        comp_pct = round(comp / max(total, 1) * 100)
        shot_n   = int(grp['led_to_shot'].fillna(False).sum()) if 'led_to_shot' in grp.columns else 0
        goal_n   = int(grp['led_to_goal'].fillna(False).sum()) if 'led_to_goal' in grp.columns else 0
        shot_pct = round(shot_n / max(total, 1) * 100)
        goal_pct = round(goal_n / max(total, 1) * 100)
        rows_data.append({
            'player': player, 'total': total,
            'comp': comp, 'comp_pct': comp_pct,
            'shot_n': shot_n, 'shot_pct': shot_pct,
            'goal_n': goal_n, 'goal_pct': goal_pct,
        })

    rows_data.sort(key=lambda r: r['total'], reverse=True)
    rows_data = rows_data[:top_n]

    header = html.Thead(html.Tr([
        html.Th('Player', style={**_TH, 'textAlign': 'left'}),
        html.Th('#',      style=_TH),
        html.Th('Comp',   style=_TH),
        html.Th('Comp%',  style=_TH),
        html.Th('Shots',  style=_TH),
        html.Th('Shot%',  style=_TH),
        html.Th('Goals',  style=_TH),
        html.Th('Goal%',  style=_TH),
    ]))

    table_rows = []
    for i, s in enumerate(rows_data):
        bg = 'rgba(255,255,255,0.03)' if i % 2 == 0 else 'transparent'
        comp_c = GOLD if s['comp_pct'] >= 70 else (AWAY_COLOR if s['comp_pct'] < 40 else COLORS['text_primary'])
        shot_c = GOLD if s['shot_pct'] >= 40 else COLORS['text_primary']
        goal_c = '#22c55e' if s['goal_n'] > 0 else COLORS['text_primary']
        table_rows.append(html.Tr([
            html.Td(s['player'],         style={**_NAME_TD, 'maxWidth': '110px'}),
            html.Td(str(s['total']),     style=_TD),
            html.Td(str(s['comp']),      style=_TD),
            html.Td(f"{s['comp_pct']}%", style={**_TD, 'color': comp_c, 'fontWeight': '700'}),
            html.Td(str(s['shot_n']),    style=_TD),
            html.Td(f"{s['shot_pct']}%", style={**_TD, 'color': shot_c, 'fontWeight': '700'}),
            html.Td(str(s['goal_n']),    style={**_TD, 'color': goal_c}),
            html.Td(f"{s['goal_pct']}%", style={**_TD, 'color': goal_c, 'fontWeight': '700'}),
        ], style={'backgroundColor': bg}))

    return [
        html.Div(
            'Shot% = led to shot within 5 events  ·  Goal% = led to goal (assist)',
            style={'color': COLORS['text_secondary'], 'fontSize': '0.55rem',
                   'fontStyle': 'italic', 'marginBottom': '4px'},
        ),
        html.Table([header, html.Tbody(table_rows)],
                   style={'width': '100%', 'borderCollapse': 'collapse'}),
    ]


def _fk_table_children(fk_passes: pd.DataFrame, top_n: int = 12) -> list:
    """FK passes by player — Total, Completed, Comp%, Crosses, Long Balls."""
    if fk_passes.empty or 'player_name' not in fk_passes.columns:
        return [_no_data()]

    stats = []
    for player, g in fk_passes.groupby('player_name'):
        total     = len(g)
        completed = int((g['outcome'] == 1).sum())
        comp_pct  = f'{completed / total * 100:.0f}' if total else '0'
        crosses   = int((g['Cross'] == 'Si').sum())   if 'Cross'     in g.columns else 0
        long_b    = int((g['Long ball'] == 'Si').sum()) if 'Long ball' in g.columns else 0
        stats.append((player, total, completed, comp_pct, crosses, long_b))

    stats.sort(key=lambda r: r[1], reverse=True)

    header = html.Thead(html.Tr([
        html.Th('Player',   style={**_TH, 'textAlign': 'left'}),
        html.Th('Tot',      style=_TH),
        html.Th('Comp',     style=_TH),
        html.Th('Comp%',    style=_TH),
        html.Th('Crosses',  style=_TH),
        html.Th('Long',     style=_TH),
    ]))
    rows = []
    for player, total, completed, comp_pct, crosses, long_b in stats[:top_n]:
        rows.append(html.Tr([
            html.Td(player,          style={**_NAME_TD, 'maxWidth': '120px'}),
            html.Td(str(total),      style=_TD),
            html.Td(str(completed),  style=_TD),
            html.Td(f'{comp_pct}%',  style={**_TD, 'color': GOLD}),
            html.Td(str(crosses),    style=_TD),
            html.Td(str(long_b),     style=_TD),
        ], style=_ROW_STYLE))

    return [html.Table([header, html.Tbody(rows)],
                       style={'width': '100%', 'borderCollapse': 'collapse'})]


# =============================================================================
# CORNERS  —  data helpers
# =============================================================================

def _corner_kpi_children(corner: pd.DataFrame) -> list:
    total     = len(corner)
    completed = int((corner['outcome'] == 1).sum()) if not corner.empty else 0
    comp_pct  = f'{completed / total * 100:.0f}%' if total else '-'
    right_n   = int((pd.to_numeric(corner['y'], errors='coerce') < 50).sum()) if not corner.empty else 0
    left_n    = total - right_n
    inswing   = int((corner['Inswinger'] == 'Si').sum())  if not corner.empty and 'Inswinger'  in corner.columns else 0
    outswing  = int((corner['Outswinger'] == 'Si').sum()) if not corner.empty and 'Outswinger' in corner.columns else 0

    return _kpi_bar([
        _kpi_card(total,     'Total',       HOME_COLOR),
        _kpi_card(right_n,   'Right Side',  HOME_COLOR),
        _kpi_card(left_n,    'Left Side',   HOME_COLOR),
        _kpi_card(inswing,   'Inswingers',  HOME_COLOR),
        _kpi_card(outswing,  'Outswingers', HOME_COLOR),
        _kpi_card(completed, 'Connected',   GOLD),
        _kpi_card(comp_pct,  'Connect %',   GOLD),
    ])


def _corner_delivery_type(row) -> str:
    if row.get('Inswinger') == 'Si':
        return 'Inswinger'
    if row.get('Outswinger') == 'Si':
        return 'Outswinger'
    return 'Short'


# Gold = connected (completed), Garnet = not connected (incomplete)
_CORNER_CONNECTED_COLOR    = GOLD
_CORNER_UNCONNECTED_COLOR  = '#ba4f45'


def _corner_trajectory_fig(corner: pd.DataFrame, side: str, uirev: str) -> go.Figure:
    """Draw corner trajectories (origin → landing) on an attacking half-pitch.

    side: 'right'  — corners taken from the right flag (Opta y < 50)
          'left'   — corners taken from the left flag  (Opta y ≥ 50)

    Gold lines   = connected (outcome == 1)
    Garnet lines = not connected (outcome == 0 or missing)

    Each trajectory is an annotation arrow so the line itself is interactive-free
    and fast. An invisible scatter trace carries the hover tooltip at the landing
    spot.
    """
    fig = go.Figure()
    add_pitch_background(fig, half=True)

    if not corner.empty and 'Pass End X' in corner.columns:
        df = corner.copy()
        df['_y'] = pd.to_numeric(df['y'], errors='coerce')
        df['_ex'] = pd.to_numeric(df['Pass End X'], errors='coerce')
        df['_ey'] = pd.to_numeric(df['Pass End Y'], errors='coerce')
        df = df.dropna(subset=['_y', '_ex', '_ey'])

        # Side filter
        if side == 'right':
            df = df[df['_y'] < 50]
        else:
            df = df[df['_y'] >= 50]

        if not df.empty:
            has_player = 'player_name' in df.columns
            has_time   = 'time_min'    in df.columns

            new_annotations: list = []

            for connected, color, label in [
                (True,  _CORNER_CONNECTED_COLOR,   'Connected'),
                (False, _CORNER_UNCONNECTED_COLOR,  'Not Connected'),
            ]:
                if 'outcome' in df.columns:
                    grp = df[df['outcome'].eq(1) == connected]
                else:
                    grp = df if connected else pd.DataFrame()
                if grp.empty:
                    continue

                # Arrow annotations: origin (x, y) → landing (_ex, _ey)
                for _, r in grp.iterrows():
                    new_annotations.append(dict(
                        xref='x', yref='y', axref='x', ayref='y',
                        x=r['_ex'], y=r['_ey'],
                        ax=r['x'],  ay=r['_y'],
                        showarrow=True, arrowhead=2, arrowsize=1.4,
                        arrowwidth=1.8, arrowcolor=color, opacity=0.70,
                    ))

                # Hover scatter at the landing point
                dtype_vals = grp.apply(_corner_delivery_type, axis=1).tolist()
                _conn_label = '✓ Connected' if connected else '✗ Not Connected'
                if has_player and has_time:
                    cd = list(zip(
                        grp['player_name'].fillna('').tolist(),
                        grp['time_min'].fillna(0).astype(int).tolist(),
                        dtype_vals,
                    ))
                    ht = (
                        '<b>%{customdata[0]}</b><br>'
                        '<b>Type:</b> %{customdata[2]}<br>'
                        "<b>Min:</b> %{customdata[1]}'"
                        f'<br><b>{_conn_label}</b>'
                        '<extra></extra>'
                    )
                else:
                    cd = None
                    ht = f'<b>{_conn_label}</b><extra></extra>'

                fig.add_trace(go.Scatter(
                    x=grp['_ex'].tolist(), y=grp['_ey'].tolist(),
                    mode='markers',
                    marker=dict(
                        color=color, size=9, opacity=0.88,
                        line=dict(color='white', width=1),
                    ),
                    name=f'{label} ({len(grp)})',
                    customdata=cd,
                    hovertemplate=ht,
                    showlegend=True,
                ))

            if new_annotations:
                fig.update_layout(annotations=list(fig.layout.annotations) + new_annotations)

        # ── Zone grid: 8 zones (2 x-bands × 4 y-bands) ───────────────────────
        # x_edges = [50, 83, 100]  y_edges = [0, 21.1, 50, 78.9, 100]
        _x_edges = [50, 83, 100]
        _y_edges = [0, 21.1, 50, 78.9, 100]

        # Count landing points per zone (using full df, already side-filtered)
        _landing_df = df.dropna(subset=['_ex', '_ey']) if not df.empty else pd.DataFrame(columns=['_ex', '_ey'])
        _total_land = len(_landing_df)

        zone_counts = [[0] * (len(_x_edges) - 1) for _ in range(len(_y_edges) - 1)]
        for _, _r in _landing_df.iterrows():
            _xi = min(len(_x_edges) - 2,
                      sum(1 for _xb in _x_edges[1:] if _r['_ex'] >= _xb))
            _yi = min(len(_y_edges) - 2,
                      sum(1 for _yb in _y_edges[1:] if _r['_ey'] >= _yb))
            zone_counts[_yi][_xi] += 1

        grid_shapes   = []
        grid_annots   = []

        # Dashed zone boundary lines
        for _xv in [83]:
            grid_shapes.append(dict(
                type='line', xref='x', yref='y',
                x0=_xv, x1=_xv, y0=0, y1=100,
                line=dict(color='rgba(255,255,255,0.45)', width=1, dash='dash'),
                layer='above',
            ))
        for _yv in [21.1, 50, 78.9]:
            grid_shapes.append(dict(
                type='line', xref='x', yref='y',
                x0=50, x1=100, y0=_yv, y1=_yv,
                line=dict(color='rgba(255,255,255,0.45)', width=1, dash='dash'),
                layer='above',
            ))

        # Percentage label in each zone centre
        for _row in range(len(_y_edges) - 1):
            for _col in range(len(_x_edges) - 1):
                _cx = (_x_edges[_col] + _x_edges[_col + 1]) / 2
                _cy = (_y_edges[_row] + _y_edges[_row + 1]) / 2
                _cnt = zone_counts[_row][_col]
                _pct = _cnt / _total_land * 100 if _total_land else 0
                grid_annots.append(dict(
                    xref='x', yref='y', x=_cx, y=_cy,
                    text=f'<b>{_pct:.1f}%</b>',
                    showarrow=False,
                    font=dict(color='rgba(255,255,255,0.92)', size=14),
                    bgcolor='rgba(0,0,0,0)',
                ))

        existing_shapes = list(fig.layout.shapes) if fig.layout.shapes else []
        existing_annots = list(fig.layout.annotations) if fig.layout.annotations else []
        fig.update_layout(
            shapes=existing_shapes + grid_shapes,
            annotations=existing_annots + grid_annots,
        )

    _attack_arrow(fig)
    side_label = 'Right Side' if side == 'right' else 'Left Side'
    # PITCH_AXIS_HALF: x ∈ [48, 105]  →  width  = 57 data units
    #                  y ∈ [-2, 102]  →  height = 104 data units
    # To preserve a real football-field aspect ratio the figure pixel height
    # must be ≈ (104 / 57) × pixel_width.  We fix height=680 so the pitch
    # feels tall and narrow like an attacking half of a real pitch.
    fig.update_layout(
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor=PITCH_BG,
        height=680,
        margin=dict(l=0, r=0, t=36, b=0),
        legend=dict(
            font=dict(color='white', size=9), bgcolor='rgba(0,0,0,0.55)',
            orientation='v', x=0.01, xanchor='left', y=0.99, yanchor='top',
        ),
        uirevision=uirev,
        hovermode='closest',
        title=dict(
            text=f'<b>{side_label}</b>',
            font=dict(color=GOLD, size=11),
            x=0.5, xanchor='center', y=0.98,
        ),
        xaxis=dict(
            range=[48, 105], showgrid=False, zeroline=False,
            showticklabels=False, fixedrange=True, visible=False,
            scaleanchor='y', scaleratio=1,   # enforce 1:1 data-unit aspect ratio
        ),
        yaxis=dict(
            range=[-2, 102], showgrid=False, zeroline=False,
            showticklabels=False, fixedrange=True, visible=False,
        ),
    )
    return fig


def _corner_table_children(corner: pd.DataFrame, top_n: int = 12) -> list:
    """Corner deliveries by player — Total, R, L, In, Out, Connected, Connect%."""
    if corner.empty or 'player_name' not in corner.columns:
        return [_no_data()]

    stats = []
    for player, g in corner.groupby('player_name'):
        total     = len(g)
        connected = int((g['outcome'] == 1).sum())
        conn_pct  = f'{connected / total * 100:.0f}' if total else '0'
        right_n   = int((pd.to_numeric(g['y'], errors='coerce') < 50).sum())
        left_n    = total - right_n
        inswing   = int((g['Inswinger'] == 'Si').sum())  if 'Inswinger'  in g.columns else 0
        outswing  = int((g['Outswinger'] == 'Si').sum()) if 'Outswinger' in g.columns else 0
        stats.append((player, total, right_n, left_n, inswing, outswing, connected, conn_pct))

    stats.sort(key=lambda r: r[1], reverse=True)

    header = html.Thead(html.Tr([
        html.Th('Player', style={**_TH, 'textAlign': 'left'}),
        html.Th('Tot',    style=_TH),
        html.Th('R',      style=_TH),
        html.Th('L',      style=_TH),
        html.Th('In',     style=_TH),
        html.Th('Out',    style=_TH),
        html.Th('Conn',   style=_TH),
        html.Th('Conn%',  style=_TH),
    ]))
    rows = []
    for player, total, right_n, left_n, inswing, outswing, connected, conn_pct in stats[:top_n]:
        conn_color = GOLD if int(conn_pct) >= 70 else (AWAY_COLOR if int(conn_pct) < 40 else COLORS['text_primary'])
        rows.append(html.Tr([
            html.Td(player,          style={**_NAME_TD, 'maxWidth': '110px'}),
            html.Td(str(total),      style=_TD),
            html.Td(str(right_n),    style=_TD),
            html.Td(str(left_n),     style=_TD),
            html.Td(str(inswing),    style=_TD),
            html.Td(str(outswing),   style=_TD),
            html.Td(str(connected),  style={**_TD, 'color': GOLD}),
            html.Td(f'{conn_pct}%',  style={**_TD, 'color': conn_color, 'fontWeight': '700'}),
        ], style=_ROW_STYLE))

    return [
        html.Div(
            'R = right-side corners  ·  L = left-side corners  ·  Conn = delivery connected',
            style={'color': COLORS['text_secondary'], 'fontSize': '0.55rem',
                   'fontStyle': 'italic', 'marginBottom': '4px'},
        ),
        html.Table([header, html.Tbody(rows)],
                   style={'width': '100%', 'borderCollapse': 'collapse'}),
    ]


def _corner_side_table_children(corner: pd.DataFrame, side: str, top_n: int = 8) -> list:
    """Per-side corner table (same columns as _corner_table_children, filtered by side)."""
    if corner.empty or 'player_name' not in corner.columns:
        return [_no_data()]

    df = corner.copy()
    df['_y'] = pd.to_numeric(df['y'], errors='coerce')
    if side == 'right':
        df = df[df['_y'] < 50]
    else:
        df = df[df['_y'] >= 50]

    if df.empty:
        return [_no_data()]

    stats = []
    for player, g in df.groupby('player_name'):
        total     = len(g)
        connected = int((g['outcome'] == 1).sum())
        conn_pct  = f'{connected / total * 100:.0f}' if total else '0'
        inswing   = int((g['Inswinger'] == 'Si').sum())  if 'Inswinger'  in g.columns else 0
        outswing  = int((g['Outswinger'] == 'Si').sum()) if 'Outswinger' in g.columns else 0
        stats.append((player, total, inswing, outswing, connected, conn_pct))

    stats.sort(key=lambda r: r[1], reverse=True)

    header = html.Thead(html.Tr([
        html.Th('Player', style={**_TH, 'textAlign': 'left'}),
        html.Th('Tot',    style=_TH),
        html.Th('In',     style=_TH),
        html.Th('Out',    style=_TH),
        html.Th('Conn',   style=_TH),
        html.Th('Conn%',  style=_TH),
    ]))
    rows = []
    for player, total, inswing, outswing, connected, conn_pct in stats[:top_n]:
        conn_color = GOLD if int(conn_pct) >= 70 else (AWAY_COLOR if int(conn_pct) < 40 else COLORS['text_primary'])
        rows.append(html.Tr([
            html.Td(player,          style={**_NAME_TD, 'maxWidth': '110px'}),
            html.Td(str(total),      style=_TD),
            html.Td(str(inswing),    style=_TD),
            html.Td(str(outswing),   style=_TD),
            html.Td(str(connected),  style={**_TD, 'color': GOLD}),
            html.Td(f'{conn_pct}%',  style={**_TD, 'color': conn_color, 'fontWeight': '700'}),
        ], style=_ROW_STYLE))

    return [
        html.Table([header, html.Tbody(rows)],
                   style={'width': '100%', 'borderCollapse': 'collapse'}),
    ]


# =============================================================================
# PENALTIES  —  data helpers
# =============================================================================

# Goal-mouth display constants — match goalkeeping.py approach
_GM_CENTER   = 50.0
_GM_X_SCALE  = 2.5
_GM_GOAL_L   = _GM_CENTER + (44.5 - _GM_CENTER) * _GM_X_SCALE   # 36.25
_GM_GOAL_R   = _GM_CENTER + (55.5 - _GM_CENTER) * _GM_X_SCALE   # 63.75
_GM_CROSSBAR = 38.0
_GM_Y_COL    = 'Goal Mouth Y Coordinate'
_GM_Z_COL    = 'Goal Mouth Z Coordinate'

_PEN_STYLE = [
    ('Goal',       '#22c55e', 'star',    18),
    ('Saved Shot', '#3b82f6', 'circle',  15),
    ('Post',       GOLD,      'diamond', 15),
    ('Miss',       '#ef4444', 'x',       13),
]


def _pen_kpi_children(pen: pd.DataFrame) -> list:
    total      = len(pen)
    goals      = int((pen['event_type'] == 'Goal').sum())       if not pen.empty else 0
    on_tgt     = int((pen['event_type'] == 'Saved Shot').sum()) if not pen.empty else 0
    missed     = int(pen['event_type'].isin(['Miss', 'Post']).sum()) if not pen.empty else 0
    scored_pct = f'{goals / total * 100:.0f}%' if total else '-'

    return _kpi_bar([
        _kpi_card(total,      'Penalties',   HOME_COLOR),
        _kpi_card(goals,      'Goals',       GOLD),
        _kpi_card(scored_pct, 'Scored %',    GOLD),
        _kpi_card(on_tgt,     'Saved',       HOME_COLOR),
        _kpi_card(missed,     'Missed/Post', HOME_COLOR),
    ])


def _pen_goal_mouth_fig(pen: pd.DataFrame, team: str | None = None) -> go.Figure:
    """Penalty shot placement on a goal-face frame — matches goalkeeping.py approach."""
    POST_W = 0.7
    shapes = [
        # Goal interior
        dict(type='rect', x0=_GM_GOAL_L, x1=_GM_GOAL_R, y0=0, y1=_GM_CROSSBAR,
             fillcolor='rgba(255,255,255,0.07)', line=dict(width=0)),
        # Left post
        dict(type='rect', x0=_GM_GOAL_L - POST_W, x1=_GM_GOAL_L,
             y0=0, y1=_GM_CROSSBAR + POST_W, fillcolor='white', line=dict(width=0)),
        # Right post
        dict(type='rect', x0=_GM_GOAL_R, x1=_GM_GOAL_R + POST_W,
             y0=0, y1=_GM_CROSSBAR + POST_W, fillcolor='white', line=dict(width=0)),
        # Crossbar
        dict(type='rect', x0=_GM_GOAL_L - POST_W, x1=_GM_GOAL_R + POST_W,
             y0=_GM_CROSSBAR, y1=_GM_CROSSBAR + POST_W, fillcolor='white', line=dict(width=0)),
        # Ground line
        dict(type='line', x0=20, x1=80, y0=0, y1=0,
             line=dict(color='rgba(255,255,255,0.25)', width=1, dash='dot')),
        # Vertical guide lines (thirds of goal)
        *[dict(type='line', x0=v, x1=v, y0=0, y1=_GM_CROSSBAR,
               line=dict(color='rgba(255,255,255,0.07)', width=1))
          for v in [43.0, 46.5, 50.0, 53.5, 57.0]],
        # Horizontal guide lines (low / mid / high)
        *[dict(type='line', x0=_GM_GOAL_L, x1=_GM_GOAL_R, y0=h, y1=h,
               line=dict(color='rgba(255,255,255,0.07)', width=1))
          for h in [13, 25]],
    ]

    fig = go.Figure()

    if (not pen.empty
            and _GM_Y_COL in pen.columns
            and _GM_Z_COL in pen.columns):
        # Derive the opponent team for each row from home/away columns
        if team and 'home_team' in pen.columns and 'away_team' in pen.columns:
            t_lower   = team.lower()
            is_home   = pen['home_team'].fillna('').str.lower().str.contains(t_lower, regex=False)
            opp_series = pen['away_team'].where(is_home, pen['home_team']).fillna('Unknown')
        else:
            opp_series = pd.Series('Unknown', index=pen.index)

        for outcome, color, symbol, size in _PEN_STYLE:
            grp = pen[pen['event_type'] == outcome].copy()
            if grp.empty:
                continue
            grp[_GM_Y_COL] = pd.to_numeric(grp[_GM_Y_COL], errors='coerce')
            grp[_GM_Z_COL] = pd.to_numeric(grp[_GM_Z_COL], errors='coerce')
            grp = grp.dropna(subset=[_GM_Y_COL, _GM_Z_COL])
            if grp.empty:
                continue
            names = grp['player_name'].fillna('Unknown').tolist() if 'player_name' in grp.columns else [''] * len(grp)
            mins  = grp['time_min'].fillna('?').astype(str).tolist() if 'time_min'  in grp.columns else ['?'] * len(grp)
            opps  = opp_series.loc[grp.index].tolist()
            x_raw  = 100 - grp[_GM_Y_COL]
            x_disp = (_GM_CENTER + (x_raw - _GM_CENTER) * _GM_X_SCALE).tolist()
            fig.add_trace(go.Scatter(
                x=x_disp, y=grp[_GM_Z_COL].tolist(),
                mode='markers', name=outcome,
                marker=dict(color=color, symbol=symbol, size=size, opacity=0.92,
                            line=dict(color='white', width=1)),
                customdata=list(zip(names, mins, opps)),
                hovertemplate=(
                    f'<b>{outcome}</b><br>'
                    'Player: %{customdata[0]}<br>'
                    "Min: %{customdata[1]}'<br>"
                    'vs: %{customdata[2]}<extra></extra>'
                ),
            ))

    fig.update_layout(
        shapes=shapes,
        xaxis=dict(range=[20, 80], showgrid=False, zeroline=False, visible=False, fixedrange=True),
        yaxis=dict(range=[-4, 55], showgrid=False, zeroline=False, visible=False, fixedrange=True),
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='#0d1a35',
        margin=dict(l=10, r=10, t=10, b=50), height=400,
        font=dict(color=COLORS['text_primary']),
        legend=dict(orientation='h', y=-0.13, x=0.5, xanchor='center',
                    font=dict(color=COLORS['text_primary'], size=10),
                    bgcolor='rgba(0,0,0,0)'),
        uirevision='sp-pen-map',
    )
    return fig


def _pen_table_children(pen: pd.DataFrame, top_n: int = 15) -> list:
    """Penalty taker table — Pen, G, Saved, Miss, Scored%."""
    if pen.empty or 'player_name' not in pen.columns:
        return [_no_data()]

    stats = []
    for player, g in pen.groupby('player_name'):
        total    = len(g)
        goals    = int((g['event_type'] == 'Goal').sum())
        saved    = int((g['event_type'] == 'Saved Shot').sum())
        missed   = int(g['event_type'].isin(['Miss', 'Post']).sum())
        scr_pct  = f'{goals / total * 100:.0f}' if total else '0'
        stats.append((player, total, goals, saved, missed, scr_pct))

    stats.sort(key=lambda r: r[1], reverse=True)

    header = html.Thead(html.Tr([
        html.Th('Player',   style={**_TH, 'textAlign': 'left'}),
        html.Th('Pen',      style=_TH),
        html.Th('G',        style=_TH),
        html.Th('Saved',    style=_TH),
        html.Th('Miss',     style=_TH),
        html.Th('Scored%',  style=_TH),
    ]))
    rows = []
    for player, total, goals, saved, missed, scr_pct in stats[:top_n]:
        rows.append(html.Tr([
            html.Td(player,          style={**_NAME_TD, 'maxWidth': '120px'}),
            html.Td(str(total),      style=_TD),
            html.Td(str(goals),      style={**_TD, 'color': '#22c55e'}),
            html.Td(str(saved),      style=_TD),
            html.Td(str(missed),     style=_TD),
            html.Td(f'{scr_pct}%',   style={**_TD, 'color': GOLD}),
        ], style=_ROW_STYLE))

    return [html.Table([header, html.Tbody(rows)],
                       style={'width': '100%', 'borderCollapse': 'collapse'})]


# =============================================================================
# FREE-KICKS skeleton
# =============================================================================

def _build_free_kicks_skeleton(player_opts=None) -> html.Div:
    filter_panel = html.Div([
        html.Div("Filters", style=_SECTION_TITLE),
        html.Div("Player", style=_LABEL_STYLE),
        dcc.Dropdown(
            id='sp-fk-player',
            options=player_opts or [],
            value=None, multi=True,
            placeholder="All players…",
            style={'fontSize': '0.75rem'},
        ),
        *PassMap.dash_controls(
            show=['outcome', 'start_third', 'end_third', 'bands', 'h1_time', 'h2_time'],
            id_prefix='sp-fk',
        ),
    ], style=_PANEL_STYLE)

    content = html.Div([
        html.Div(id='sp-fk-kpi', children=[]),
        html.Hr(style={'borderColor': COLORS['dark_border'], 'margin': '10px 0 14px'}),

        dbc.Row([
            dbc.Col([
                html.Div("Free Kick Shot Map", style=_SECTION_TITLE),
                html.Div(
                    "Direct FK shots · star = goal · circle = saved · ✕ = miss",
                    style={'color': COLORS['text_secondary'], 'fontSize': '0.62rem',
                           'fontStyle': 'italic', 'marginBottom': '8px'},
                ),
                dcc.Loading(type='circle', color=GOLD, children=dcc.Graph(
                    id='sp-fk-shot-map', figure=_skel_fig(520), config=CHART_CFG,
                    style={'width': '100%'},
                )),
            ], md=8),

            dbc.Col([
                html.Div("Top FK Takers", style={**_SECTION_TITLE, 'fontSize': '0.75rem'}),
                html.Div(id='sp-fk-table', children=[], style={'marginTop': '6px'}),
            ], md=4, style={
                'borderLeft': f'1px solid {COLORS["dark_border"]}',
                'paddingLeft': '14px',
            }),
        ], align='start', className='g-0'),

        html.Hr(style={'borderColor': COLORS['dark_border'], 'margin': '16px 0 12px'}),
        html.Div("Zone 3 Entries from Free Kicks", style=_SECTION_TITLE),
        html.Div(style={'marginBottom': '8px'}),
        dbc.Row([
            dbc.Col([
                html.Div("Final Third Entries",
                         style={**_SECTION_TITLE, 'borderBottom': 'none',
                                'paddingBottom': '4px', 'fontSize': '0.72rem'}),
                html.Div(
                    "FK passes that cross into the final third",
                    style={'color': COLORS['text_secondary'], 'fontSize': '0.62rem',
                           'fontStyle': 'italic', 'marginBottom': '8px'},
                ),
                dcc.Loading(type='circle', color=GOLD, children=dcc.Graph(
                    id='sp-fk-ft-map', figure=_skel_fig(480), config=CHART_CFG,
                    style={'width': '100%'},
                )),
                html.Div(id='sp-fk-ft-table', children=[], style={'marginTop': '8px'}),
            ], md=6),
            dbc.Col([
                html.Div("Penalty Box Entries",
                         style={**_SECTION_TITLE, 'borderBottom': 'none',
                                'paddingBottom': '4px', 'fontSize': '0.72rem'}),
                html.Div(
                    "FK passes landing inside the penalty area",
                    style={'color': COLORS['text_secondary'], 'fontSize': '0.62rem',
                           'fontStyle': 'italic', 'marginBottom': '8px'},
                ),
                dcc.Loading(type='circle', color=GOLD, children=dcc.Graph(
                    id='sp-fk-pb-map', figure=_skel_fig(480), config=CHART_CFG,
                    style={'width': '100%'},
                )),
                html.Div(id='sp-fk-pb-table', children=[], style={'marginTop': '8px'}),
            ], md=6),
        ], align='start', className='g-3'),
    ], style=_PANEL_STYLE)

    return html.Div(
        dbc.Row([
            dbc.Col(filter_panel, md=2),
            dbc.Col(content,      md=10),
        ], align='start', className='g-3'),
    )


# =============================================================================
# THROW-INS skeleton
# =============================================================================

# =============================================================================
# CORNERS skeleton
# =============================================================================

def _build_corners_skeleton(player_opts=None) -> html.Div:
    filter_panel = html.Div([
        html.Div("Filters", style=_SECTION_TITLE),
        html.Div("Player", style=_LABEL_STYLE),
        dcc.Dropdown(
            id='sp-corner-player',
            options=player_opts or [],
            value=None, multi=True,
            placeholder="All players…",
            style={'fontSize': '0.75rem'},
        ),
        html.Hr(style={'borderColor': COLORS['dark_border'], 'margin': '8px 0'}),
        html.Div('Outcome', style={
            'color': GOLD, 'fontSize': '0.68rem', 'fontWeight': '700',
            'letterSpacing': '0.8px', 'textTransform': 'uppercase',
            'marginBottom': '4px', 'marginTop': '14px',
        }),
        dcc.Checklist(
            id='sp-corner-outcome',
            options=[
                {'label': ' Successful',   'value': 1},
                {'label': ' Unsuccessful', 'value': 0},
                {'label': ' Led to Shot',  'value': 'led_to_shot'},
                {'label': ' Led to Goal',  'value': 'led_to_goal'},
            ],
            value=[1, 0],
            inputStyle={'marginRight': '4px'},
            labelStyle={
                'display': 'block',
                'color': COLORS['text_secondary'],
                'fontSize': '0.75rem',
                'marginBottom': '3px',
            },
        ),
        *PassMap.dash_controls(
            show=['h1_time', 'h2_time'],
            id_prefix='sp-corner',
        ),
    ], style=_PANEL_STYLE)

    _legend_note = html.Div(
        'Gold lines = connected delivery  ·  Red lines = not connected  ·  % = zone share of landings',
        style={'color': COLORS['text_secondary'], 'fontSize': '0.62rem',
               'fontStyle': 'italic', 'marginBottom': '10px'},
    )

    content = html.Div([
        # ── Corner Stats KPI bar ──────────────────────────────────────────────
        html.Div(id='sp-corner-kpi', children=[]),
        html.Hr(style={'borderColor': COLORS['dark_border'], 'margin': '10px 0 14px'}),
        _legend_note,

        # ── Right side: plot | table ──────────────────────────────────────────
        html.Div("Right Side Corners", style=_SECTION_TITLE),
        dbc.Row([
            dbc.Col([
                dcc.Loading(type='circle', color=GOLD, children=dcc.Graph(
                    id='sp-corner-right', figure=_skel_fig(420), config=CHART_CFG,
                    style={'width': '100%'},
                )),
            ], md=7),
            dbc.Col([
                html.Div(id='sp-corner-right-table', children=[], style={'marginTop': '6px'}),
            ], md=5, style={
                'borderLeft': f'1px solid {COLORS["dark_border"]}',
                'paddingLeft': '12px',
            }),
        ], align='start', className='g-2'),

        html.Hr(style={'borderColor': COLORS['dark_border'], 'margin': '14px 0 10px'}),

        # ── Left side: plot | table ───────────────────────────────────────────
        html.Div("Left Side Corners", style=_SECTION_TITLE),
        dbc.Row([
            dbc.Col([
                dcc.Loading(type='circle', color=GOLD, children=dcc.Graph(
                    id='sp-corner-left', figure=_skel_fig(420), config=CHART_CFG,
                    style={'width': '100%'},
                )),
            ], md=7),
            dbc.Col([
                html.Div(id='sp-corner-left-table', children=[], style={'marginTop': '6px'}),
            ], md=5, style={
                'borderLeft': f'1px solid {COLORS["dark_border"]}',
                'paddingLeft': '12px',
            }),
        ], align='start', className='g-2'),

        html.Hr(style={'borderColor': COLORS['dark_border'], 'margin': '14px 0 10px'}),

        # ── All takers summary ────────────────────────────────────────────────
        html.Div("By Taker (All Corners)", style=_SECTION_TITLE),
        html.Div(id='sp-corner-table', children=[], style={'marginTop': '6px'}),
    ], style=_PANEL_STYLE)

    return html.Div(
        dbc.Row([
            dbc.Col(filter_panel, md=2),
            dbc.Col(content,      md=10),
        ], align='start', className='g-3'),
    )


# =============================================================================
# PENALTIES skeleton
# =============================================================================

def _build_penalties_skeleton(player_opts=None) -> html.Div:
    filter_panel = html.Div([
        html.Div("Filters", style=_SECTION_TITLE),
        html.Div("Player", style=_LABEL_STYLE),
        dcc.Dropdown(
            id='sp-pen-player',
            options=player_opts or [],
            value=None, multi=True,
            placeholder="All players…",
            style={'fontSize': '0.75rem'},
        ),
    ], style=_PANEL_STYLE)

    content = html.Div([
        html.Div(id='sp-pen-kpi', children=[]),
        html.Hr(style={'borderColor': COLORS['dark_border'], 'margin': '10px 0 14px'}),

        dbc.Row([
            dbc.Col([
                html.Div("Goal Mouth — Shot Placement", style=_SECTION_TITLE),
                html.Div(
                    "star = goal · circle = saved · ◆ = post · ✕ = miss",
                    style={'color': COLORS['text_secondary'], 'fontSize': '0.62rem',
                           'fontStyle': 'italic', 'marginBottom': '8px'},
                ),
                dcc.Loading(type='circle', color=GOLD, children=dcc.Graph(
                    id='sp-pen-map', figure=_skel_fig(400), config=CHART_CFG,
                    style={'width': '100%'},
                )),
            ], md=7),

            dbc.Col([
                html.Div("By Taker", style={**_SECTION_TITLE, 'fontSize': '0.75rem'}),
                html.Div(id='sp-pen-table', children=[], style={'marginTop': '6px'}),
            ], md=5, style={
                'borderLeft': f'1px solid {COLORS["dark_border"]}',
                'paddingLeft': '14px',
            }),
        ], align='start', className='g-0'),
    ], style=_PANEL_STYLE)

    return html.Div(
        dbc.Row([
            dbc.Col(filter_panel, md=2),
            dbc.Col(content,      md=10),
        ], align='start', className='g-3'),
    )


# =============================================================================
# Public builder
# =============================================================================

def build_set_pieces_tab(season=None, competitions=None, match_ids=None, **_) -> dbc.Tabs:
    events = get_all_events(CURRENT_SEASON)

    fk_player_opts     = []
    corner_player_opts = []
    pen_player_opts    = []

    if not events.empty:
        bar = events[events['team_code'] == 'BAR']

        def _player_opts(df):
            if 'player_name' not in df.columns:
                return []
            names = df['player_name'].dropna().unique()
            return sorted([{'label': n, 'value': n} for n in names],
                          key=lambda d: d['label'])

        fk_player_opts     = _player_opts(
            bar[(bar['event_type'] == 'Pass') & (bar['Free kick taken'] == 'Si')]
        )
        corner_player_opts = _player_opts(
            bar[(bar['event_type'] == 'Pass') & (bar['Corner taken'] == 'Si')]
        )
        pen_player_opts    = _player_opts(
            bar[
                bar['event_type'].isin(['Goal', 'Miss', 'Post', 'Saved Shot']) &
                (bar['Penalty'] == 'Si')
            ]
        )

    return dbc.Tabs(
        active_tab='sp-tab-fk',
        children=[
            dbc.Tab(
                _build_free_kicks_skeleton(fk_player_opts),
                label='Free-Kicks',
                tab_id='sp-tab-fk',
                tab_style={'flex': '1'},
                label_style=_BTN_INACTIVE,
                active_label_style=_BTN_ACTIVE,
            ),
            dbc.Tab(
                _build_corners_skeleton(corner_player_opts),
                label='Corners',
                tab_id='sp-tab-corners',
                tab_style={'flex': '1'},
                label_style=_BTN_INACTIVE,
                active_label_style=_BTN_ACTIVE,
            ),
            dbc.Tab(
                _build_penalties_skeleton(pen_player_opts),
                label='Penalties',
                tab_id='sp-tab-pen',
                tab_style={'flex': '1'},
                label_style=_BTN_INACTIVE,
                active_label_style=_BTN_ACTIVE,
            ),
        ],
        className='mb-3',
    )


# =============================================================================
# Callbacks
# =============================================================================

def register_set_pieces_callbacks(app) -> None:
    """Register all Set Pieces sub-tab callbacks."""

    # ── Free Kicks ────────────────────────────────────────────────────────────
    @app.callback(
        Output('sp-fk-kpi',        'children'),
        Output('sp-fk-shot-map',   'figure'),
        Output('sp-fk-ft-map',     'figure'),
        Output('sp-fk-pb-map',     'figure'),
        Output('sp-fk-ft-table',   'children'),
        Output('sp-fk-pb-table',   'children'),
        Output('sp-fk-table',      'children'),
        Input('sp-fk-player',       'value'),
        Input('sp-fk-outcome',      'value'),
        Input('sp-fk-start-third',  'value'),
        Input('sp-fk-end-third',    'value'),
        Input('sp-fk-bands',        'value'),
        Input('sp-fk-h1-time',      'value'),
        Input('sp-fk-h2-time',      'value'),
        State('ta-competition-selector', 'value'),
        State('ta-venue-selector',       'value'),
        State('ta-selected-matches',     'data'),
        State('ta-match-data',           'data'),
    )
    def _update_fk(players, outcomes, start_thirds, end_thirds, bands,
                   h1_range, h2_range,
                   competition, venue, match_ids, match_data):

        def _empty():
            return [], _skel_fig(520), _skel_fig(480), _skel_fig(480), [], [], []

        events = get_all_events(CURRENT_SEASON)
        if events.empty:
            return _empty()

        events = _apply_global_filters(events, competition, venue, match_ids, match_data)
        bar = _add_receiver_name(events[events['team_code'] == 'BAR'])
        bar = _add_shot_goal_lookahead(bar)

        fk_passes = bar[(bar['event_type'] == 'Pass') & (bar['Free kick taken'] == 'Si')]
        fk_shots  = bar[bar['event_type'].isin(_SHOT_TYPES) & (bar['Free kick'] == 'Si')]

        if fk_passes.empty and fk_shots.empty:
            return _empty()

        _h1 = tuple(h1_range) if h1_range else (0, 50)
        _h2 = tuple(h2_range) if h2_range else (45, 100)

        # Filtered passes — full filter set
        fk_filtered = PassMap.filter(
            fk_passes,
            outcomes=outcomes       or [0, 1],
            start_thirds=start_thirds or None,
            end_thirds=end_thirds   or None,
            bands=bands             or None,
            h1_range=_h1,
            h2_range=_h2,
            end_x_col='Pass End X',
        )
        if players and 'player_name' in fk_filtered.columns:
            fk_filtered = fk_filtered[fk_filtered['player_name'].isin(players)]

        # Shots — player + time only
        fk_shots_f = PassMap.filter(fk_shots, h1_range=_h1, h2_range=_h2)
        if players and 'player_name' in fk_shots_f.columns:
            fk_shots_f = fk_shots_f[fk_shots_f['player_name'].isin(players)]

        ft_entries = _fk_zone3_entries_df(fk_filtered, 'final_third')
        pb_entries = _fk_zone3_entries_df(fk_filtered, 'penalty_box')
        return (
            _fk_kpi_children(fk_filtered, fk_shots_f),
            _fk_shot_map_fig(fk_shots_f),
            _fk_zone3_fig(ft_entries, 'final_third'),
            _fk_zone3_fig(pb_entries, 'penalty_box'),
            _fk_zone3_table_children(ft_entries),
            _fk_zone3_table_children(pb_entries),
            _fk_table_children(fk_filtered),
        )

    # ── Corners ───────────────────────────────────────────────────────────────
    @app.callback(
        Output('sp-corner-kpi',          'children'),
        Output('sp-corner-right',        'figure'),
        Output('sp-corner-left',         'figure'),
        Output('sp-corner-right-table',  'children'),
        Output('sp-corner-left-table',   'children'),
        Output('sp-corner-table',        'children'),
        Input('sp-corner-player',   'value'),
        Input('sp-corner-outcome',  'value'),
        Input('sp-corner-h1-time',  'value'),
        Input('sp-corner-h2-time',  'value'),
        State('ta-competition-selector', 'value'),
        State('ta-venue-selector',       'value'),
        State('ta-selected-matches',     'data'),
        State('ta-match-data',           'data'),
    )
    def _update_corners(players, outcomes, h1_range, h2_range,
                        competition, venue, match_ids, match_data):

        def _empty():
            return [], _skel_fig(420), _skel_fig(420), [], [], []

        events = get_all_events(CURRENT_SEASON)
        if events.empty:
            return _empty()

        events = _apply_global_filters(events, competition, venue, match_ids, match_data)
        bar = _add_shot_goal_lookahead(events[events['team_code'] == 'BAR'])

        corner = bar[(bar['event_type'] == 'Pass') & (bar['Corner taken'] == 'Si')]
        if corner.empty:
            return _empty()

        _h1 = tuple(h1_range) if h1_range else (0, 50)
        _h2 = tuple(h2_range) if h2_range else (45, 100)

        # Split outcome checklist values into standard pass outcomes and sequence flags
        _all_outcomes = outcomes if outcomes is not None else [1, 0]
        std_outcomes = [v for v in _all_outcomes if v in (0, 1)]
        seq_filters  = [v for v in _all_outcomes if v in ('led_to_shot', 'led_to_goal')]
        # Default to both outcomes if user deselected both but picked a seq filter
        if not std_outcomes:
            std_outcomes = [0, 1]

        corner = PassMap.filter(
            corner,
            outcomes=std_outcomes,
            h1_range=_h1, h2_range=_h2,
        )
        if players and 'player_name' in corner.columns:
            corner = corner[corner['player_name'].isin(players)]

        # Apply sequence filters (OR logic across selected flags)
        if seq_filters and not corner.empty:
            mask = pd.Series(False, index=corner.index)
            if 'led_to_shot' in seq_filters:
                mask |= corner['led_to_shot'].fillna(False)
            if 'led_to_goal' in seq_filters:
                mask |= corner['led_to_goal'].fillna(False)
            corner = corner[mask]

        if corner.empty:
            return _empty()

        return (
            _corner_kpi_children(corner),
            _corner_trajectory_fig(corner, 'right', 'sp-corner-right'),
            _corner_trajectory_fig(corner, 'left',  'sp-corner-left'),
            _corner_side_table_children(corner, 'right'),
            _corner_side_table_children(corner, 'left'),
            _corner_table_children(corner),
        )

    # ── Penalties ─────────────────────────────────────────────────────────────
    @app.callback(
        Output('sp-pen-kpi',   'children'),
        Output('sp-pen-map',   'figure'),
        Output('sp-pen-table', 'children'),
        Input('sp-pen-player',           'value'),
        Input('ta-competition-selector', 'value'),
        State('ta-venue-selector',       'value'),
        State('ta-selected-matches',     'data'),
        State('ta-match-data',           'data'),
    )
    def _update_penalties(players, competition, venue, match_ids, match_data):

        def _empty():
            return [], _skel_fig(400), []

        events = get_all_events(CURRENT_SEASON)
        if events.empty:
            return _empty()

        events = _apply_global_filters(events, competition, venue, match_ids, match_data)
        bar = events[events['team_code'] == 'BAR']

        # Barcelona penalty shots (Goal / Miss / Post / Saved Shot taken by BAR players)
        pen = bar[
            bar['event_type'].isin(['Goal', 'Miss', 'Post', 'Saved Shot']) &
            (bar['Penalty'] == 'Si')
        ]

        if pen.empty:
            return _empty()

        if players and 'player_name' in pen.columns:
            pen = pen[pen['player_name'].isin(players)]

        if pen.empty:
            return _empty()

        return (
            _pen_kpi_children(pen),
            _pen_goal_mouth_fig(pen, team='Barcelona'),
            _pen_table_children(pen),
        )
