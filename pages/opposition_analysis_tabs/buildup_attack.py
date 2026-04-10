"""
Opposition Analysis — Tab 2: Build Up & Attack

Two sub-tabs (skeleton + callback pattern):
  • Pass Map     — pass map, zone distribution, pass network, final-third entries
  • Shot Map     — shot map with xG, pre-shot heatmap, scorer/assister tables

ID prefix: obu-  (pass map sub-tab)
           occ-  (chance creation / shot map sub-tab)

All data is loaded inside the registered callbacks via load_opp_events().
The build functions return skeletons that are filled asynchronously.
"""

from __future__ import annotations

import io
import base64

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
from mplsoccer import Pitch

import numpy as np
import pandas as pd
from sklearn.preprocessing import MinMaxScaler
import plotly.graph_objects as go
from dash import html, dcc, Input, Output, State
import dash_bootstrap_components as dbc

from utils.config import COLORS
from utils.opposition_data_utils import load_opp_events, SEASON
from utils.xg_utils import add_xg_column
from page_utils import PassMap, GOLD, HOME_COLOR, AWAY_COLOR
from page_utils.visualizations import (
    add_vertical_half_pitch_background,
    VPITCH_AXIS_HALF,
    render_lsc_heatmap_img,
)


# =============================================================================
# Shared constants
# =============================================================================

PITCH_BG         = '#151932'
PITCH_LINE_COLOR = '#8899CC'
_SKEL_SRC        = 'data:image/png;base64,'
CHART_CONFIG     = {'displayModeBar': False}

PITCH_AXIS_FULL = dict(
    xaxis=dict(range=[-5, 105], showgrid=False, zeroline=False,
               showticklabels=False, fixedrange=True, visible=False),
    yaxis=dict(range=[-2, 102], showgrid=False, zeroline=False,
               showticklabels=False, fixedrange=True, visible=False,
               scaleanchor='x', scaleratio=0.68),
)

_LABEL_STYLE = {
    'color': GOLD, 'fontSize': '0.70rem', 'fontWeight': '700',
    'letterSpacing': '0.8px', 'textTransform': 'uppercase',
    'marginBottom': '5px', 'marginTop': '14px',
}
_PANEL_STYLE = {
    'backgroundColor': COLORS['dark_secondary'],
    'border': f'1px solid {COLORS["dark_border"]}',
    'borderRadius': '6px', 'padding': '14px 12px',
    'overflowY': 'auto', 'maxHeight': '80vh',
}
_SECTION_TITLE = {
    'color': GOLD, 'fontWeight': '700', 'fontSize': '0.82rem',
    'letterSpacing': '1px', 'textTransform': 'uppercase',
    'paddingBottom': '8px', 'borderBottom': f'1px solid {COLORS["dark_border"]}',
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
    'maxWidth': '90px', 'overflow': 'hidden', 'textOverflow': 'ellipsis',
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

_SHOT_TYPES = ['Goal', 'Saved Shot', 'Miss', 'Post', 'Blocked Shot']

_PITCH_CACHE: dict = {}


# =============================================================================
# Shared pitch helpers
# =============================================================================

def _skel_fig(height: int = 520) -> go.Figure:
    fig = go.Figure()
    fig.update_layout(
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor=PITCH_BG,
        height=height, margin=dict(l=0, r=0, t=36, b=0),
    )
    return fig


def _generate_pitch_image() -> str:
    if 'full' in _PITCH_CACHE:
        return _PITCH_CACHE['full']
    pitch = Pitch(pitch_type='opta', pitch_color=PITCH_BG, line_color=PITCH_LINE_COLOR,
                  linewidth=2.5, stripe=False, goal_type='box', goal_alpha=0.8,
                  pad_top=1, pad_bottom=1, pad_left=4, pad_right=4)
    fig_mpl, _ = pitch.draw(figsize=(16, 10))
    buf = io.BytesIO()
    fig_mpl.savefig(buf, format='png', dpi=100, bbox_inches='tight', pad_inches=0)
    buf.seek(0)
    _PITCH_CACHE['full'] = base64.b64encode(buf.read()).decode()
    plt.close(fig_mpl)
    return _PITCH_CACHE['full']


def _add_pitch_background(fig: go.Figure) -> None:
    img = _generate_pitch_image()
    fig.add_layout_image(dict(
        source=f'data:image/png;base64,{img}',
        xref='x', yref='y', x=-5, y=102, sizex=110, sizey=104,
        sizing='stretch', opacity=1, layer='below',
    ))


def _add_attack_direction(fig: go.Figure) -> None:
    fig.add_annotation(
        x=0.5, y=1.02, xref='paper', yref='paper',
        text='<b>➡  Direction of Attack</b>', showarrow=False,
        font=dict(size=10, color='white', family='Arial, sans-serif'),
        xanchor='center', yanchor='bottom',
        bgcolor='rgba(21,25,50,0.8)', bordercolor=PITCH_LINE_COLOR,
        borderwidth=1, borderpad=4,
    )


# =============================================================================
# PASS MAP  —  data helpers + chart builders
# =============================================================================

def _get_passes(opp_ev: pd.DataFrame) -> pd.DataFrame:
    passes = opp_ev[
        (opp_ev['event_type'] == 'Pass') &
        opp_ev['x'].notna() & opp_ev['y'].notna()
    ].copy()
    if 'Pass End X' not in passes.columns:
        return passes
    passes['Pass End X'] = pd.to_numeric(passes['Pass End X'], errors='coerce')
    passes['Pass End Y'] = pd.to_numeric(passes['Pass End Y'], errors='coerce')
    return passes[passes['Pass End X'].notna() & passes['Pass End Y'].notna()]


def _apply_pass_filters(passes, *, outcomes, start_thirds, end_thirds,
                        bands, players, h1_range, h2_range) -> pd.DataFrame:
    passes = PassMap.filter(
        passes, outcomes=outcomes, start_thirds=start_thirds,
        end_thirds=end_thirds, bands=bands,
        h1_range=h1_range, h2_range=h2_range, end_x_col='Pass End X',
    )
    if players and 'player_name' in passes.columns:
        passes = passes[passes['player_name'].isin(players)]
    return passes


def _build_pass_fig(passes: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    _add_pitch_background(fig)

    if len(passes) > 0 and 'Pass End X' in passes.columns:
        xs = passes['x'].values.astype(float)
        ys = passes['y'].values.astype(float)
        xe = passes['Pass End X'].values.astype(float)
        ye = passes['Pass End Y'].values.astype(float)
        has_outcome = 'outcome' in passes.columns
        outcomes    = passes['outcome'].values.astype(int) if has_outcome else np.ones(len(xs), dtype=int)
        mask_suc    = (outcomes == 1)
        mask_fail   = ~mask_suc

        def _add_lines(mask, color, op_lines, op_dots):
            if not mask.any(): return
            idx = np.where(mask)[0]
            x_seg, y_seg = [], []
            for i in idx:
                x_seg += [float(xs[i]), float(xe[i]), None]
                y_seg += [float(ys[i]), float(ye[i]), None]
            fig.add_trace(go.Scatter(x=x_seg, y=y_seg, mode='lines',
                                     line=dict(color=color, width=1.5), opacity=op_lines,
                                     showlegend=False, hoverinfo='skip'))
            fig.add_trace(go.Scatter(x=xs[mask], y=ys[mask], mode='markers',
                                     marker=dict(color=color, size=4, opacity=0.5),
                                     showlegend=False, hoverinfo='skip'))
            fig.add_trace(go.Scatter(x=xe[mask], y=ye[mask], mode='markers',
                                     marker=dict(color=color, size=6, line=dict(color='white', width=0.5)),
                                     opacity=op_dots, showlegend=False, hoverinfo='skip'))

        _add_lines(mask_fail, COLORS['garnet'], 0.45, 0.65)
        _add_lines(mask_suc,  COLORS['gold'],   0.75, 0.95)

    fig.update_layout(
        **PITCH_AXIS_FULL,
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
        font=dict(color='#E8E9ED', size=12, family='Arial, sans-serif'),
        margin=dict(l=0, r=0, t=36, b=0), showlegend=False, height=520,
        uirevision='obu-pass-map',
    )
    _add_attack_direction(fig)
    for x_pos, label in ((100/3, 'Def Third'), (200/3, 'Att Third')):
        fig.add_shape(type='line', x0=x_pos, x1=x_pos, y0=-2, y1=102,
                      xref='x', yref='y',
                      line=dict(color='rgba(255,255,255,0.20)', width=1.5, dash='dash'))
        fig.add_annotation(x=x_pos, y=103, xref='x', yref='y', text=f'<b>{label}</b>',
                           showarrow=False,
                           font=dict(size=8, color='rgba(255,255,255,0.40)', family='Arial, sans-serif'),
                           xanchor='center', yanchor='bottom')
    return fig


def _count_pass_pairs(opp_ev: pd.DataFrame) -> dict:
    if opp_ev.empty: return {}
    cols = ['player_name', 'event_type', 'outcome', 'period_id', 'time_min', 'time_sec']
    ev   = opp_ev[[c for c in cols if c in opp_ev.columns]].copy()
    ev   = ev.dropna(subset=['player_name'])
    ev   = ev.sort_values(['period_id', 'time_min', 'time_sec']).reset_index(drop=True)
    if ev.empty: return {}
    is_pass  = ev['event_type'] == 'Pass'
    is_suc   = (ev['outcome'] == 1) if 'outcome' in ev.columns else pd.Series(True, index=ev.index)
    next_pl  = ev['player_name'].shift(-1)
    valid    = is_pass & is_suc & next_pl.notna() & (ev['player_name'] != next_pl)
    if not valid.any(): return {}
    pairs = pd.DataFrame({'passer': ev.loc[valid, 'player_name'].values,
                          'receiver': next_pl.loc[valid].values})
    result = pairs.groupby(['passer', 'receiver'], sort=False).size()
    return {(a, b): int(c) for (a, b), c in result.items()}


def _network_fig(opp_ev: pd.DataFrame) -> go.Figure:
    pairs = _count_pass_pairs(opp_ev)
    edges = {k: v for k, v in pairs.items() if v >= 2}
    pass_ev = opp_ev[opp_ev['event_type'] == 'Pass'].dropna(subset=['player_name', 'x', 'y'])

    fig = go.Figure()
    _add_pitch_background(fig)

    if not pass_ev.empty:
        nodes = (pass_ev.groupby('player_name')
                 .agg(x=('x', 'mean'), y=('y', 'mean')).reset_index())
        inv = {}
        for (a, b), cnt in edges.items():
            inv[a] = inv.get(a, 0) + cnt
            inv[b] = inv.get(b, 0) + cnt
        nodes['involvement'] = nodes['player_name'].map(lambda p: inv.get(p, 1))
        if len(nodes) > 1 and nodes['involvement'].max() > nodes['involvement'].min():
            sc = MinMaxScaler(feature_range=(14, 36))
            nodes['size'] = sc.fit_transform(nodes[['involvement']]).flatten()
        else:
            nodes['size'] = 22.0
        nodes['label'] = nodes['player_name'].apply(lambda n: n.split()[-1] if isinstance(n, str) else n)

        if edges:
            max_cnt = max(edges.values())
            for (a, b), cnt in edges.items():
                an = nodes[nodes['player_name'] == a]
                bn = nodes[nodes['player_name'] == b]
                if an.empty or bn.empty: continue
                x0, y0 = float(an.iloc[0]['x']), float(an.iloc[0]['y'])
                x1, y1 = float(bn.iloc[0]['x']), float(bn.iloc[0]['y'])
                width  = 1.0 + (cnt / max_cnt) * 5.0
                fig.add_trace(go.Scatter(
                    x=[x0, x1], y=[y0, y1], mode='lines',
                    line=dict(color=COLORS['primary_blue'], width=width),
                    opacity=0.55, hoverinfo='skip', showlegend=False,
                ))

        fig.add_trace(go.Scatter(
            x=nodes['x'], y=nodes['y'], mode='markers+text',
            marker=dict(size=nodes['size'], color=COLORS['primary_blue'],
                        line=dict(width=2, color='white')),
            text=nodes['label'], textposition='middle center',
            textfont=dict(size=8, color='white', family='Arial Black'),
            customdata=nodes[['player_name', 'involvement']].values,
            hovertemplate='<b>%{customdata[0]}</b><br>Involvement: %{customdata[1]:.0f}<extra></extra>',
            showlegend=False,
        ))

    _add_attack_direction(fig)
    fig.update_layout(
        **PITCH_AXIS_FULL, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
        font=dict(color='#E8E9ED', size=12, family='Arial, sans-serif'),
        margin=dict(l=0, r=0, t=36, b=0), showlegend=False, height=520,
        uirevision='obu-network', hovermode='closest',
    )
    return fig


def _zone_pitch_image(passes: pd.DataFrame, n_total: int) -> str:
    if passes.empty: return ''
    _X = [0, 100/3, 200/3, 100]
    _Y = [0, 100/3, 200/3, 100]

    pitch = Pitch(pitch_type='opta', pitch_color=PITCH_BG, line_color=PITCH_LINE_COLOR,
                  linewidth=1.5, stripe=False, goal_type='box',
                  pad_top=2, pad_bottom=2, pad_left=2, pad_right=2)
    fig_mpl, ax = pitch.draw(figsize=(4.5, 3.0))
    n_total = max(n_total, 1)
    has_end = 'Pass End X' in passes.columns and 'Pass End Y' in passes.columns

    sent_grid = {}
    for x0, x1 in zip(_X[:-1], _X[1:]):
        for y0, y1 in zip(_Y[:-1], _Y[1:]):
            m = ((passes['x'] >= x0) & (passes['x'] < x1) &
                 (passes['y'] >= y0) & (passes['y'] < y1))
            sent_grid[(x0, y0)] = m.sum() / n_total * 100
    max_sent = max(sent_grid.values()) if sent_grid else 1

    for x0, x1 in zip(_X[:-1], _X[1:]):
        for y0, y1 in zip(_Y[:-1], _Y[1:]):
            sent_pct = sent_grid[(x0, y0)]
            recv_pct = 0.0
            if has_end:
                rm = ((passes['Pass End X'] >= x0) & (passes['Pass End X'] < x1) &
                      (passes['Pass End Y'] >= y0) & (passes['Pass End Y'] < y1))
                recv_pct = rm.sum() / n_total * 100
            alpha = 0.06 + 0.40 * (sent_pct / max(max_sent, 1))
            ax.add_patch(Rectangle((x0, y0), x1-x0, y1-y0,
                                   facecolor=COLORS['gold'], alpha=alpha, linewidth=0, zorder=1))
            cx, cy = (x0+x1)/2, (y0+y1)/2
            ax.text(cx, cy+5.5, f'S  {sent_pct:.0f}%', ha='center', va='center',
                    fontsize=6.5, color=COLORS['gold'], fontweight='bold', zorder=2)
            ax.text(cx, cy-5.5, f'R  {recv_pct:.0f}%', ha='center', va='center',
                    fontsize=6.5, color='white', fontweight='bold', zorder=2)

    for xb in [100/3, 200/3]:
        ax.axvline(xb, color='white', linewidth=0.8, linestyle='--', alpha=0.25, zorder=3)
    for yb in [100/3, 200/3]:
        ax.axhline(yb, color='white', linewidth=0.8, linestyle='--', alpha=0.25, zorder=3)

    buf = io.BytesIO()
    fig_mpl.savefig(buf, format='png', dpi=130, bbox_inches='tight',
                    pad_inches=0.05, facecolor=PITCH_BG)
    buf.seek(0)
    result = base64.b64encode(buf.read()).decode()
    plt.close(fig_mpl)
    return result


def _stats_numbers_children(passes: pd.DataFrame) -> list:
    n_total = len(passes)
    n_suc   = int(passes['outcome'].eq(1).sum()) if 'outcome' in passes.columns else 0
    acc     = round(n_suc / max(n_total, 1) * 100, 1)
    n_prog  = 0
    if 'Pass End X' in passes.columns and 'x' in passes.columns:
        mask_suc = passes['outcome'].eq(1) if 'outcome' in passes.columns else pd.Series(True, index=passes.index)
        n_prog   = int((mask_suc & ((passes['Pass End X'] - passes['x']) >= 25)).sum())

    def _card(value, label, color):
        return html.Div([
            html.Div(str(value), style={'color': color, 'fontWeight': '800', 'fontSize': '1.5rem', 'lineHeight': '1.1'}),
            html.Div(label, style={'color': COLORS['text_secondary'], 'fontSize': '0.63rem', 'fontWeight': '600', 'letterSpacing': '0.6px', 'textTransform': 'uppercase', 'marginTop': '3px'}),
        ], style={'backgroundColor': COLORS['dark_secondary'], 'border': f'1px solid {COLORS["dark_border"]}', 'borderRadius': '6px', 'padding': '10px 12px', 'flex': '1'})

    def _row(*cards):
        return html.Div(list(cards), style={'display': 'flex', 'gap': '6px', 'marginBottom': '6px'})

    return [
        _row(_card(n_total,   'Total',       GOLD),
             _card(f'{acc}%', 'Accuracy',    HOME_COLOR)),
        _row(_card(n_prog,    'Progressive', HOME_COLOR),
             _card('—',       'Key Passes',  AWAY_COLOR)),
    ]


def _top5_progressive(passes: pd.DataFrame) -> list:
    if passes.empty or 'Pass End X' not in passes.columns:
        return [html.P("No data", style={'color': COLORS['text_secondary'], 'fontSize': '0.75rem'})]
    mask_suc  = passes['outcome'].eq(1) if 'outcome' in passes.columns else pd.Series(True, index=passes.index)
    mask_prog = (passes['Pass End X'] - passes['x']) >= 25
    prog      = passes[mask_suc & mask_prog]
    if prog.empty or 'player_name' not in prog.columns:
        return [html.P("No data", style={'color': COLORS['text_secondary'], 'fontSize': '0.75rem'})]
    top5 = prog.groupby('player_name').size().sort_values(ascending=False).head(5).reset_index(name='count')
    rows = []
    for rank, row in enumerate(top5.itertuples(), start=1):
        rows.append(html.Div([
            html.Span(f"{rank}", style={'color': GOLD, 'fontWeight': '800', 'fontSize': '0.85rem', 'minWidth': '18px'}),
            html.Span(row.player_name, style={'color': 'white', 'fontSize': '0.72rem', 'flex': '1', 'overflow': 'hidden', 'textOverflow': 'ellipsis', 'whiteSpace': 'nowrap'}),
            html.Span(str(row.count), style={'color': GOLD, 'fontWeight': '700', 'fontSize': '0.75rem', 'marginLeft': '6px'}),
        ], style={'display': 'flex', 'alignItems': 'center', 'gap': '8px', 'padding': '6px 0', 'borderBottom': f'1px solid {COLORS["dark_border"]}'}))
    return [
        html.Div("Top Progressive Passers", style={**_SECTION_TITLE, 'marginBottom': '4px'}),
        html.Div("(Successful passes advancing ≥ 25% of pitch)", style={'color': COLORS['text_secondary'], 'fontSize': '0.58rem', 'fontStyle': 'italic', 'marginBottom': '8px'}),
        *rows,
    ]


# =============================================================================
# SHOT MAP  —  data helpers + chart builders
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


def _get_shots(opp_ev: pd.DataFrame) -> pd.DataFrame:
    shots = opp_ev[opp_ev['event_type'].isin(_SHOT_TYPES)].copy()
    shots = shots.dropna(subset=['x', 'y'])
    if shots.empty:
        return shots
    return add_xg_column(shots)


def _apply_shot_filters(shots, *, outcomes, bands, players, h1_range, h2_range) -> pd.DataFrame:
    if outcomes:
        shots = shots[shots['event_type'].isin(outcomes)]
    if bands and len(bands) < 3 and 'y' in shots.columns:
        y    = pd.to_numeric(shots['y'], errors='coerce')
        mask = pd.Series(False, index=shots.index)
        if 'left'   in bands: mask |= y > 66.67
        if 'centre' in bands: mask |= (y >= 33.33) & (y <= 66.67)
        if 'right'  in bands: mask |= y < 33.33
        shots = shots[mask]
    if players and 'player_name' in shots.columns:
        shots = shots[shots['player_name'].isin(players)]
    if 'period_id' in shots.columns and 'time_min' in shots.columns:
        h1_lo, h1_hi = h1_range
        h2_lo, h2_hi = h2_range
        m1 = (shots['period_id'] == 1) & (shots['time_min'] >= h1_lo) & (shots['time_min'] <= h1_hi)
        m2 = (shots['period_id'] == 2) & (shots['time_min'] >= h2_lo) & (shots['time_min'] <= h2_hi)
        shots = shots[m1 | m2]
    return shots


def _shot_map_fig(shots: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    add_vertical_half_pitch_background(fig)

    _base = dict(
        **VPITCH_AXIS_HALF,
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor=PITCH_BG,
        height=520, margin=dict(l=0, r=0, t=8, b=0),
        hoverlabel=dict(bgcolor='#1A1D2E', font_color='white', font_size=12),
        legend=dict(x=0.01, y=0.01, xanchor='left', yanchor='bottom',
                    orientation='v', font=dict(color=COLORS['text_primary'], size=10),
                    bgcolor='rgba(26,29,46,0.80)',
                    bordercolor=COLORS.get('dark_border', 'rgba(255,255,255,0.15)'),
                    borderwidth=1),
    )

    if not shots.empty:
        for etype in _SHOT_TYPES:
            grp = shots[shots['event_type'] == etype]
            if grp.empty: continue
            xg_vals = grp['xg'].fillna(0.05) if 'xg' in grp.columns else pd.Series(0.05, index=grp.index)
            sizes   = (xg_vals * 120 + 12).clip(upper=50)
            mins    = grp['time_min'].fillna('?').astype(str) if 'time_min' in grp.columns else pd.Series('?', index=grp.index)
            names   = grp['player_name'].fillna('Unknown') if 'player_name' in grp.columns else pd.Series('Unknown', index=grp.index)
            xg_disp = xg_vals.round(3).astype(str)
            custom  = list(zip(names, mins, xg_disp))

            # Opta: x = distance from own goal (0-100), y = pitch width (0-100)
            # Vertical half-pitch: fig_x = 100-y, fig_y = x
            fig.add_trace(go.Scatter(
                x=(100 - grp['y']).tolist(),
                y=grp['x'].tolist(),
                mode='markers',
                name=etype,
                marker=dict(
                    color=_OUTCOME_COLOR.get(etype, '#888'),
                    symbol=_OUTCOME_SYMBOL.get(etype, 'circle'),
                    size=sizes.tolist(),
                    opacity=0.85,
                    line=dict(color='white', width=1),
                ),
                customdata=custom,
                hovertemplate=(
                    f'<b>{etype}</b><br>'
                    'Player: %{customdata[0]}<br>'
                    "Min: %{customdata[1]}'<br>"
                    'xG: %{customdata[2]}<extra></extra>'
                ),
            ))

    fig.update_layout(**_base, uirevision='occ-shot-map')
    return fig


def _kpi_children(shots: pd.DataFrame) -> list:
    def _card(value, label, color=COLORS['text_primary'], preserve_case=False):
        return html.Div([
            html.Div(str(value), style={'color': color, 'fontWeight': '800', 'fontSize': '1.35rem', 'lineHeight': '1.1'}),
            html.Div(label, style={'color': COLORS['text_secondary'], 'fontSize': '0.60rem', 'fontWeight': '600', 'letterSpacing': '0' if preserve_case else '0.6px', 'textTransform': 'none' if preserve_case else 'uppercase', 'marginTop': '3px'}),
        ], style={'backgroundColor': COLORS['dark_secondary'], 'border': f'1px solid {COLORS["dark_border"]}', 'borderRadius': '6px', 'padding': '8px 10px', 'flex': '1', 'minWidth': '0'})

    total_shots = len(shots)
    shots_ot    = int(shots['event_type'].isin(['Goal', 'Saved Shot']).sum()) if not shots.empty else 0
    goals       = int((shots['event_type'] == 'Goal').sum()) if not shots.empty else 0
    xg_total    = round(shots['xg'].sum(), 2) if not shots.empty and 'xg' in shots.columns else 0.0
    box_shots   = int((shots['x'] >= 83).sum()) if not shots.empty and 'x' in shots.columns else 0

    return [html.Div([
        _card(total_shots,        'Shots',       COLORS['text_primary']),
        _card(shots_ot,           'On Target',   HOME_COLOR),
        _card(goals,              'Goals',        GOLD),
        _card(f'{xg_total:.2f}',  'xG',          HOME_COLOR, preserve_case=True),
        _card(box_shots,          'Box Shots',   COLORS['text_primary']),
    ], style={'display': 'flex', 'gap': '6px', 'flexWrap': 'wrap'})]


def _scorers_table(shots: pd.DataFrame, top_n: int = 10) -> list:
    if shots.empty or 'player_name' not in shots.columns:
        return [html.P("No data", style={'color': COLORS['text_secondary'], 'fontSize': '0.75rem'})]
    goals = shots[shots['event_type'] == 'Goal']
    if goals.empty:
        return [html.P("No goals", style={'color': COLORS['text_secondary'], 'fontSize': '0.75rem'})]

    tbl = goals.groupby('player_name').agg(
        goals=('event_type', 'count'),
        shots=('event_type', 'size'),
        xg=('xg', 'sum'),
    ).reset_index()
    tbl = tbl.nlargest(top_n, 'goals')
    header = html.Tr([
        html.Th('Player', style={**_TH, 'textAlign': 'left'}),
        html.Th('G', style=_TH), html.Th('Sh', style=_TH),
        html.Th('xG', style={**_TH, 'textTransform': 'none'}),
    ])
    rows = [html.Tr([
        html.Td(r.player_name.split()[-1], style=_NAME_TD),
        html.Td(str(r.goals), style={**_TD, 'color': GOLD, 'fontWeight': '800'}),
        html.Td(str(r.shots), style=_TD),
        html.Td(f'{r.xg:.2f}', style=_TD),
    ]) for r in tbl.itertuples()]
    return [html.Table([html.Thead(header), html.Tbody(rows)],
                       style={'width': '100%', 'borderCollapse': 'collapse'})]


# =============================================================================
# Skeleton builders
# =============================================================================

def _build_pass_map_skeleton(player_opts=None) -> html.Div:
    filter_panel = html.Div([
        html.Div("Filters", style=_SECTION_TITLE),
        html.Div("Player", style=_LABEL_STYLE),
        dcc.Dropdown(id='obu-player-filter', options=player_opts or [], value=None, multi=True,
                     placeholder="All players…", style={'fontSize': '0.75rem'}),
        *PassMap.dash_controls(
            show=['outcome', 'start_third', 'end_third', 'bands', 'h1_time', 'h2_time'],
            id_prefix='obu',
        ),
    ], style=_PANEL_STYLE)

    pass_map_col = [
        html.Div([
            html.Div("Pass Map", style={**_SECTION_TITLE, 'borderBottom': 'none', 'paddingBottom': '0', 'flex': '1'}),
            dcc.Checklist(id='obu-prog-only',
                          options=[{'label': ' Progressive only', 'value': 'prog'}], value=[],
                          inputStyle={'cursor': 'pointer', 'accentColor': COLORS['gold']},
                          labelStyle={'color': COLORS['text_secondary'], 'fontSize': '0.60rem', 'cursor': 'pointer'}),
        ], style={'display': 'flex', 'alignItems': 'center', 'gap': '6px', 'marginBottom': '6px',
                  'borderBottom': f'1px solid {COLORS["dark_border"]}', 'paddingBottom': '8px'}),
        html.Div(style={'marginBottom': '10px'}),
        dcc.Loading(type='circle', color=COLORS['gold'], children=dcc.Graph(
            id='obu-pitch-graph', figure=_skel_fig(520), config=CHART_CONFIG, style={'width': '100%'},
        )),
        html.Hr(style={'borderColor': COLORS['dark_border'], 'margin': '16px 0 12px'}),
        html.Div("Possession Touch Map", style=_SECTION_TITLE),
        dcc.Loading(type='circle', color=COLORS['gold'], children=html.Img(
            id='obu-touch-map-img', src=_SKEL_SRC, style={'width': '100%', 'borderRadius': '6px'},
        )),
    ]

    stats_col = html.Div([
        html.Div("Pass Stats", style=_SECTION_TITLE),
        html.Div(style={'marginTop': '10px'}),
        html.Div(id='obu-stats-numbers', children=[]),
        html.Hr(style={'borderColor': COLORS['dark_border'], 'margin': '12px 0 8px'}),
        html.Div([
            html.Div("Pass Distribution", style={**_SECTION_TITLE, 'borderBottom': 'none', 'paddingBottom': '0', 'flex': '1'}),
            dcc.Checklist(id='obu-dist-total',
                          options=[{'label': ' All passes', 'value': 'total'}], value=[],
                          inputStyle={'cursor': 'pointer', 'accentColor': COLORS['gold']},
                          labelStyle={'color': COLORS['text_secondary'], 'fontSize': '0.60rem', 'cursor': 'pointer'}),
        ], style={'display': 'flex', 'alignItems': 'center', 'gap': '6px', 'marginBottom': '6px'}),
        html.Img(id='obu-zone-pitch-img', src=_SKEL_SRC, style={'width': '100%', 'borderRadius': '4px'}),
        html.Hr(style={'borderColor': COLORS['dark_border'], 'margin': '12px 0 8px'}),
        html.Div(id='obu-top5-prog', children=[]),
    ], style=_PANEL_STYLE)

    combined = html.Div([
        dbc.Row([
            dbc.Col(pass_map_col, md=8),
            dbc.Col(stats_col, md=4, style={'borderLeft': f'1px solid {COLORS["dark_border"]}', 'paddingLeft': '16px'}),
        ], align='start', className='g-0'),
        html.Hr(style={'borderColor': COLORS['dark_border'], 'margin': '16px 0 12px'}),
        html.Div("Pass Network", style=_SECTION_TITLE),
        dcc.Loading(type='circle', color=COLORS['gold'], children=dcc.Graph(
            id='obu-network-fig', figure=_skel_fig(520), config=CHART_CONFIG, style={'width': '100%'},
        )),
    ], style=_PANEL_STYLE)

    return html.Div(
        dbc.Row([
            dbc.Col(filter_panel, md=2),
            dbc.Col(combined,     md=10),
        ], align='start', className='g-3'),
    )


def _build_shot_map_skeleton(player_opts=None) -> html.Div:
    filter_panel = html.Div([
        html.Div("Filters", style=_SECTION_TITLE),
        html.Div("Player", style=_LABEL_STYLE),
        dcc.Dropdown(id='occ-player-filter', options=player_opts or [], value=None, multi=True,
                     placeholder="All players…", style={'fontSize': '0.75rem'}),
        html.Hr(style={'borderColor': COLORS['dark_border'], 'margin': '10px 0 4px'}),
        html.Div("Shot Outcome", style=_LABEL_STYLE),
        dcc.Checklist(
            id='occ-shot-outcome',
            options=[{'label': f' {t}', 'value': t} for t in _SHOT_TYPES],
            value=_SHOT_TYPES,
            inputStyle={'cursor': 'pointer', 'accentColor': GOLD},
            labelStyle={'color': COLORS['text_secondary'], 'fontSize': '0.75rem', 'display': 'block', 'marginBottom': '4px'},
        ),
        html.Hr(style={'borderColor': COLORS['dark_border'], 'margin': '10px 0 4px'}),
        html.Div("Band", style=_LABEL_STYLE),
        dcc.Checklist(
            id='occ-bands',
            options=[{'label': ' Left', 'value': 'left'}, {'label': ' Centre', 'value': 'centre'}, {'label': ' Right', 'value': 'right'}],
            value=['left', 'centre', 'right'], inline=True,
            inputStyle={'cursor': 'pointer', 'accentColor': GOLD, 'marginRight': '4px'},
            labelStyle={'color': COLORS['text_secondary'], 'fontSize': '0.75rem', 'marginRight': '10px'},
        ),
        *PassMap.dash_controls(show=['h1_time', 'h2_time'], id_prefix='occ'),
    ], style=_PANEL_STYLE)

    main_content = html.Div([
        html.Div(id='occ-kpi-bar', children=[]),
        html.Hr(style={'borderColor': COLORS['dark_border'], 'margin': '10px 0 14px'}),
        dbc.Row([
            dbc.Col([
                html.Div("Shot Map", style=_SECTION_TITLE),
                html.Div("Dot size proportional to xG · star = goal · circle = saved · ✕ = miss",
                         style={'color': COLORS['text_secondary'], 'fontSize': '0.62rem', 'fontStyle': 'italic', 'marginBottom': '8px'}),
                dcc.Loading(type='circle', color=GOLD, children=dcc.Graph(
                    id='occ-shot-map', figure=_skel_fig(520), config=CHART_CONFIG, style={'width': '100%'},
                )),
            ], md=8),
            dbc.Col([
                html.Div("Top Scorers", style={**_SECTION_TITLE, 'fontSize': '0.75rem'}),
                html.Div(style={'marginBottom': '6px'}),
                html.Div(id='occ-scorers-table', children=[]),
            ], md=4, style={'borderLeft': f'1px solid {COLORS["dark_border"]}', 'paddingLeft': '14px'}),
        ], align='start', className='g-0'),
    ], style=_PANEL_STYLE)

    return html.Div(
        dbc.Row([
            dbc.Col(filter_panel, md=2),
            dbc.Col(main_content,  md=10),
        ], align='start', className='g-3'),
    )


# =============================================================================
# Public builder
# =============================================================================

def build_buildup_attack(team: str | None = None,
                         comp_key: str | None = None) -> dbc.Tabs:
    """Return the Build Up & Attack tab layout (two sub-tabs, skeleton pattern)."""
    pass_player_opts = []
    shot_player_opts = []

    if team and comp_key:
        opp_ev, _ = load_opp_events(team, comp_key, 'all', None, None, SEASON)
        if not opp_ev.empty and 'event_type' in opp_ev.columns:
            def _opts(df_sub):
                if 'player_name' not in df_sub.columns:
                    return []
                names = df_sub['player_name'].dropna().unique()
                return sorted([{'label': n, 'value': n} for n in names], key=lambda d: d['label'])

            pass_player_opts = _opts(opp_ev[opp_ev['event_type'] == 'Pass'])
            shot_player_opts = _opts(opp_ev[opp_ev['event_type'].isin(_SHOT_TYPES)])

    return dbc.Tabs(
        active_tab='oab-tab-pass',
        children=[
            dbc.Tab(
                _build_pass_map_skeleton(pass_player_opts),
                label='Pass Map',
                tab_id='oab-tab-pass',
                tab_style={'flex': '1'},
                label_style=_BTN_INACTIVE,
                active_label_style=_BTN_ACTIVE,
            ),
            dbc.Tab(
                _build_shot_map_skeleton(shot_player_opts),
                label='Shot Map',
                tab_id='oab-tab-shot',
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

def register_buildup_attack_callbacks(app) -> None:
    """Wire all filter controls to the pass map and shot map."""

    # ── Pass Map callback ─────────────────────────────────────────────────────
    @app.callback(
        Output('obu-pitch-graph',    'figure'),
        Output('obu-stats-numbers',  'children'),
        Output('obu-zone-pitch-img', 'src'),
        Output('obu-touch-map-img',  'src'),
        Output('obu-network-fig',    'figure'),
        Output('obu-top5-prog',      'children'),
        Input('obu-outcome',         'value'),
        Input('obu-start-third',     'value'),
        Input('obu-end-third',       'value'),
        Input('obu-bands',           'value'),
        Input('obu-h1-time',         'value'),
        Input('obu-h2-time',         'value'),
        Input('obu-player-filter',   'value'),
        Input('obu-dist-total',      'value'),
        Input('obu-prog-only',       'value'),
        State('oa-team-select',      'value'),
        State('oa-comp-select',      'value'),
        State('oa-venue-filter',     'value'),
        State('oa-selected-matches', 'data'),
        State('oa-date-filter',      'date'),
    )
    def _update_pass_map(outcomes, start_thirds, end_thirds, bands,
                         h1_range, h2_range, players, dist_total, prog_only,
                         team, comp, venue, match_ids, date_cutoff):

        def _empty():
            return (_build_pass_fig(pd.DataFrame()), [], _SKEL_SRC, _SKEL_SRC,
                    _skel_fig(520), [])

        if not team or not comp:
            return _empty()

        opp_ev, _ = load_opp_events(team, comp, venue or 'all',
                                    match_ids or None, date_cutoff, SEASON)
        if opp_ev.empty:
            return _empty()

        passes  = _get_passes(opp_ev)
        if passes.empty:
            return _empty()

        n_all = len(passes)
        _h1   = tuple(h1_range) if h1_range else (0, 50)
        _h2   = tuple(h2_range) if h2_range else (45, 100)

        filtered = _apply_pass_filters(
            passes,
            outcomes=outcomes         or [0, 1],
            start_thirds=start_thirds or None,
            end_thirds=end_thirds     or None,
            bands=bands               or None,
            players=players           or None,
            h1_range=_h1, h2_range=_h2,
        )

        if prog_only and 'Pass End X' in filtered.columns:
            _suc        = filtered['outcome'].eq(1) if 'outcome' in filtered.columns else pd.Series(True, index=filtered.index)
            plot_passes = filtered[_suc & ((filtered['Pass End X'] - filtered['x']) >= 25)]
        else:
            plot_passes = filtered

        use_total  = bool(dist_total)
        n_for_zone = n_all if use_total else len(filtered)

        zone_img = _zone_pitch_image(filtered, n_for_zone)
        zone_src = f'data:image/png;base64,{zone_img}' if zone_img else _SKEL_SRC

        # Touch heatmap
        touches = opp_ev.dropna(subset=['x', 'y'])
        if players and 'player_name' in touches.columns:
            touches = touches[touches['player_name'].isin(players)]
        if not touches.empty:
            touch_src = render_lsc_heatmap_img(
                touches['x'].tolist(), touches['y'].tolist(),
                COLORS['garnet'], show_zone_pcts=True, text_color=COLORS['gold'],
            )
        else:
            touch_src = _SKEL_SRC

        net_fig   = _network_fig(opp_ev)
        top5_prog = _top5_progressive(filtered)

        return (_build_pass_fig(plot_passes), _stats_numbers_children(filtered),
                zone_src, touch_src, net_fig, top5_prog)

    # ── Shot Map callback ─────────────────────────────────────────────────────
    @app.callback(
        Output('occ-kpi-bar',       'children'),
        Output('occ-shot-map',      'figure'),
        Output('occ-scorers-table', 'children'),
        Input('occ-player-filter',  'value'),
        Input('occ-shot-outcome',   'value'),
        Input('occ-bands',          'value'),
        Input('occ-h1-time',        'value'),
        Input('occ-h2-time',        'value'),
        State('oa-team-select',     'value'),
        State('oa-comp-select',     'value'),
        State('oa-venue-filter',    'value'),
        State('oa-selected-matches','data'),
        State('oa-date-filter',     'date'),
    )
    def _update_shot_map(players, outcomes, bands, h1_range, h2_range,
                         team, comp, venue, match_ids, date_cutoff):

        def _empty():
            return [], _skel_fig(520), []

        if not team or not comp:
            return _empty()

        opp_ev, _ = load_opp_events(team, comp, venue or 'all',
                                    match_ids or None, date_cutoff, SEASON)
        if opp_ev.empty:
            return _empty()

        _h1 = tuple(h1_range) if h1_range else (0, 50)
        _h2 = tuple(h2_range) if h2_range else (45, 100)

        all_shots = _get_shots(opp_ev)
        if all_shots.empty:
            return _empty()

        map_shots = _apply_shot_filters(
            all_shots.copy(),
            outcomes=outcomes or _SHOT_TYPES,
            bands=bands       or ['left', 'centre', 'right'],
            players=players   or None,
            h1_range=_h1, h2_range=_h2,
        )

        return (
            _kpi_children(map_shots),
            _shot_map_fig(map_shots),
            _scorers_table(map_shots),
        )
