"""
Opposition Analysis — Build-Up (Pass Map)

Skeleton + callback pattern. All data loaded via load_opp_events() in the callback.
ID prefix: obu-

Public API:
  build_buildup(team, comp_key)  → html.Div  (skeleton, immediate return)
  register_buildup_callbacks(app)            (wires obu- controls)
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
from page_utils import PassMap, GOLD, HOME_COLOR, AWAY_COLOR
from page_utils.visualizations import render_xt_heatmap_img, PITCH_BG, CHART_CONFIG


# =============================================================================
# Constants
# =============================================================================

PITCH_LINE_COLOR = '#8899CC'
_SKEL_SRC        = 'data:image/png;base64,'

# Local PITCH_AXIS_FULL intentionally includes scaleanchor/scaleratio for correct
# pass-map aspect ratio — differs from page_utils.visualizations.PITCH_AXIS_FULL.
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

_PITCH_CACHE: dict = {}
_ZONE_IMG_CACHE: dict = {}


# =============================================================================
# Pitch helpers
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
# Data helpers
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


# =============================================================================
# Chart builders
# =============================================================================

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
            if not mask.any():
                return
            idx = np.where(mask)[0]
            x_seg, y_seg = [], []
            for i in idx:
                x_seg += [float(xs[i]), float(xe[i]), None]
                y_seg += [float(ys[i]), float(ye[i]), None]
            fig.add_trace(go.Scatter(
                x=x_seg, y=y_seg, mode='lines',
                line=dict(color=color, width=1.5), opacity=op_lines,
                showlegend=False, hoverinfo='skip',
            ))
            fig.add_trace(go.Scatter(
                x=xs[mask], y=ys[mask], mode='markers',
                marker=dict(color=color, size=4, opacity=0.5),
                showlegend=False, hoverinfo='skip',
            ))
            fig.add_trace(go.Scatter(
                x=xe[mask], y=ye[mask], mode='markers',
                marker=dict(color=color, size=6, line=dict(color='white', width=0.5)),
                opacity=op_dots, showlegend=False, hoverinfo='skip',
            ))

        _add_lines(mask_fail, COLORS['garnet'], 0.45, 0.65)
        _add_lines(mask_suc,  COLORS['gold'],   0.75, 0.95)

    _add_attack_direction(fig)
    for x_pos, label in ((100/3, 'Def Third'), (200/3, 'Att Third')):
        fig.add_shape(type='line', x0=x_pos, x1=x_pos, y0=-2, y1=102,
                      xref='x', yref='y',
                      line=dict(color='rgba(255,255,255,0.20)', width=1.5, dash='dash'))
        fig.add_annotation(
            x=x_pos, y=103, xref='x', yref='y', text=f'<b>{label}</b>',
            showarrow=False,
            font=dict(size=8, color='rgba(255,255,255,0.40)', family='Arial, sans-serif'),
            xanchor='center', yanchor='bottom',
        )
    fig.update_layout(
        **PITCH_AXIS_FULL,
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
        font=dict(color='#E8E9ED', size=12, family='Arial, sans-serif'),
        margin=dict(l=0, r=0, t=36, b=0), showlegend=False, height=520,
        uirevision='obu-pass-map',
    )
    return fig


def _zone_pitch_image(passes: pd.DataFrame, n_total: int) -> str:
    if passes.empty:
        return ''
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
            ax.add_patch(Rectangle(
                (x0, y0), x1 - x0, y1 - y0,
                facecolor=COLORS['gold'], alpha=alpha, linewidth=0, zorder=1,
            ))
            cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
            ax.text(cx, cy + 5.5, f'S  {sent_pct:.0f}%',
                    ha='center', va='center', fontsize=6.5,
                    color=COLORS['gold'], fontweight='bold', zorder=2)
            ax.text(cx, cy - 5.5, f'R  {recv_pct:.0f}%',
                    ha='center', va='center', fontsize=6.5,
                    color='white', fontweight='bold', zorder=2)

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
        mask_suc = (passes['outcome'].eq(1) if 'outcome' in passes.columns
                    else pd.Series(True, index=passes.index))
        n_prog   = int((mask_suc & ((passes['Pass End X'] - passes['x']) >= 25)).sum())

    def _card(value, label, color):
        return html.Div([
            html.Div(str(value), style={
                'color': color, 'fontWeight': '800',
                'fontSize': '1.5rem', 'lineHeight': '1.1',
            }),
            html.Div(label, style={
                'color': COLORS['text_secondary'], 'fontSize': '0.63rem',
                'fontWeight': '600', 'letterSpacing': '0.6px',
                'textTransform': 'uppercase', 'marginTop': '3px',
            }),
        ], style={
            'backgroundColor': COLORS['dark_secondary'],
            'border': f'1px solid {COLORS["dark_border"]}',
            'borderRadius': '6px', 'padding': '10px 12px', 'flex': '1',
        })

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
    mask_suc  = (passes['outcome'].eq(1) if 'outcome' in passes.columns
                 else pd.Series(True, index=passes.index))
    mask_prog = (passes['Pass End X'] - passes['x']) >= 25
    prog      = passes[mask_suc & mask_prog]
    if prog.empty or 'player_name' not in prog.columns:
        return [html.P("No data", style={'color': COLORS['text_secondary'], 'fontSize': '0.75rem'})]
    top5 = (prog.groupby('player_name').size()
            .sort_values(ascending=False).head(5).reset_index(name='count'))
    rows = []
    for rank, row in enumerate(top5.itertuples(), start=1):
        rows.append(html.Div([
            html.Span(f"{rank}", style={
                'color': GOLD, 'fontWeight': '800',
                'fontSize': '0.85rem', 'minWidth': '18px',
            }),
            html.Span(row.player_name, style={
                'color': 'white', 'fontSize': '0.72rem',
                'flex': '1', 'overflow': 'hidden',
                'textOverflow': 'ellipsis', 'whiteSpace': 'nowrap',
            }),
            html.Span(str(row.count), style={
                'color': GOLD, 'fontWeight': '700',
                'fontSize': '0.75rem', 'marginLeft': '6px',
            }),
        ], style={
            'display': 'flex', 'alignItems': 'center', 'gap': '8px',
            'padding': '6px 0',
            'borderBottom': f'1px solid {COLORS["dark_border"]}',
        }))
    return [
        html.Div("Top Progressive Passers", style={
            **_SECTION_TITLE,
            'borderBottom': f'1px solid {COLORS["dark_border"]}',
            'marginBottom': '4px',
        }),
        html.Div("(Successful passes advancing ≥ 25% of pitch)", style={
            'color': COLORS['text_secondary'], 'fontSize': '0.58rem',
            'fontStyle': 'italic', 'marginBottom': '8px',
        }),
        *rows,
    ]


def _count_pass_pairs(opp_ev: pd.DataFrame) -> dict:
    if opp_ev.empty:
        return {}
    cols = ['player_name', 'event_type', 'outcome', 'period_id', 'time_min', 'time_sec']
    ev   = opp_ev[[c for c in cols if c in opp_ev.columns]].copy()
    ev   = ev.dropna(subset=['player_name'])
    ev   = ev.sort_values(['period_id', 'time_min', 'time_sec']).reset_index(drop=True)
    if ev.empty:
        return {}
    is_pass = ev['event_type'] == 'Pass'
    is_suc  = (ev['outcome'] == 1) if 'outcome' in ev.columns else pd.Series(True, index=ev.index)
    next_pl = ev['player_name'].shift(-1)
    valid   = is_pass & is_suc & next_pl.notna() & (ev['player_name'] != next_pl)
    if not valid.any():
        return {}
    pairs  = pd.DataFrame({'passer': ev.loc[valid, 'player_name'].values,
                           'receiver': next_pl.loc[valid].values})
    result = pairs.groupby(['passer', 'receiver'], sort=False).size()
    return {(a, b): int(c) for (a, b), c in result.items()}


def _network_fig(opp_ev: pd.DataFrame) -> go.Figure:
    pairs   = _count_pass_pairs(opp_ev)
    edges   = {k: v for k, v in pairs.items() if v >= 2}
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
        nodes['label'] = nodes['player_name'].apply(
            lambda n: n.split()[-1] if isinstance(n, str) else n)

        if edges:
            max_cnt = max(edges.values())
            for (a, b), cnt in edges.items():
                an = nodes[nodes['player_name'] == a]
                bn = nodes[nodes['player_name'] == b]
                if an.empty or bn.empty:
                    continue
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
        **PITCH_AXIS_FULL,
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
        font=dict(color='#E8E9ED', size=12, family='Arial, sans-serif'),
        margin=dict(l=0, r=0, t=36, b=0), showlegend=False, height=520,
        uirevision='obu-network', hovermode='closest',
    )
    return fig


# =============================================================================
# Public builder
# =============================================================================

def build_buildup(team: str | None = None, comp_key: str | None = None) -> html.Div:
    """Return the Build-Up tab skeleton. Callback populates all charts."""
    player_opts = []
    if team and comp_key:
        opp_ev, _ = load_opp_events(team, comp_key, 'all', None, None, SEASON)
        if not opp_ev.empty and 'event_type' in opp_ev.columns:
            passes = opp_ev[opp_ev['event_type'] == 'Pass']
            if 'player_name' in passes.columns:
                names       = passes['player_name'].dropna().unique()
                player_opts = sorted([{'label': n, 'value': n} for n in names],
                                     key=lambda d: d['label'])

    filter_panel = html.Div([
        html.Div("Filters", style=_SECTION_TITLE),
        html.Div("Player", style=_LABEL_STYLE),
        dcc.Dropdown(
            id='obu-player-filter', options=player_opts, value=None, multi=True,
            placeholder="All players…", style={'fontSize': '0.75rem'},
        ),
        *PassMap.dash_controls(
            show=['outcome', 'start_third', 'end_third', 'bands', 'h1_time', 'h2_time'],
            id_prefix='obu',
        ),
    ], style=_PANEL_STYLE)

    pass_map_col = [
        html.Div([
            html.Div("Pass Map", style={
                **_SECTION_TITLE, 'borderBottom': 'none',
                'paddingBottom': '0', 'flex': '1',
            }),
            dcc.Checklist(
                id='obu-prog-only',
                options=[{'label': ' Progressive only', 'value': 'prog'}], value=[],
                inputStyle={'cursor': 'pointer', 'accentColor': COLORS['gold']},
                labelStyle={'color': COLORS['text_secondary'],
                            'fontSize': '0.60rem', 'cursor': 'pointer'},
            ),
        ], style={
            'display': 'flex', 'alignItems': 'center', 'gap': '6px',
            'marginBottom': '6px',
            'borderBottom': f'1px solid {COLORS["dark_border"]}',
            'paddingBottom': '8px',
        }),
        html.Div(style={'marginBottom': '10px'}),
        dcc.Loading(
            type='circle', color=COLORS['gold'],
            children=dcc.Graph(
                id='obu-pitch-graph', figure=_skel_fig(520),
                config=CHART_CONFIG, style={'width': '100%'},
            ),
        ),
        html.Hr(style={'borderColor': COLORS['dark_border'], 'margin': '16px 0 12px'}),
        html.Div("Possession Touch Map", style=_SECTION_TITLE),
        html.Div(style={'marginBottom': '8px'}),
        dcc.Loading(
            type='circle', color=COLORS['gold'],
            children=html.Img(
                id='obu-touch-map-img', src=_SKEL_SRC,
                style={'width': '100%', 'borderRadius': '6px'},
            ),
        ),
    ]

    stats_col = html.Div([
        html.Div("Pass Stats", style=_SECTION_TITLE),
        html.Div(style={'marginTop': '10px'}),
        html.Div(id='obu-stats-numbers', children=[]),
        html.Hr(style={'borderColor': COLORS['dark_border'], 'margin': '12px 0 8px'}),
        html.Div([
            html.Div("Pass Distribution", style={
                **_SECTION_TITLE, 'borderBottom': 'none',
                'paddingBottom': '0', 'flex': '1',
            }),
            dcc.Checklist(
                id='obu-dist-total',
                options=[{'label': ' All passes', 'value': 'total'}], value=[],
                inputStyle={'cursor': 'pointer', 'accentColor': COLORS['gold']},
                labelStyle={'color': COLORS['text_secondary'],
                            'fontSize': '0.60rem', 'cursor': 'pointer'},
            ),
        ], style={'display': 'flex', 'alignItems': 'center', 'gap': '6px', 'marginBottom': '6px'}),
        html.Img(
            id='obu-zone-pitch-img', src=_SKEL_SRC,
            style={'width': '100%', 'borderRadius': '4px'},
        ),
        html.Hr(style={'borderColor': COLORS['dark_border'], 'margin': '12px 0 8px'}),
        html.Div(id='obu-top5-prog', children=[]),
    ], style=_PANEL_STYLE)

    combined = html.Div([
        dbc.Row([
            dbc.Col(pass_map_col, md=8),
            dbc.Col(stats_col, md=4, style={
                'borderLeft': f'1px solid {COLORS["dark_border"]}',
                'paddingLeft': '16px',
            }),
        ], align='start', className='g-0'),
        html.Hr(style={'borderColor': COLORS['dark_border'], 'margin': '16px 0 12px'}),
        html.Div("Pass Network", style=_SECTION_TITLE),
        html.Div(style={'marginBottom': '8px'}),
        dcc.Loading(
            type='circle', color=COLORS['gold'],
            children=dcc.Graph(
                id='obu-network-fig', figure=_skel_fig(520),
                config=CHART_CONFIG, style={'width': '100%'},
            ),
        ),
    ], style=_PANEL_STYLE)

    return html.Div(
        dbc.Row([
            dbc.Col(filter_panel, md=2),
            dbc.Col(combined,     md=10),
        ], align='start', className='g-3'),
    )


# =============================================================================
# Callbacks
# =============================================================================

def register_buildup_callbacks(app) -> None:
    """Wire obu- filter controls to pass map, stats, zone pitch, and network."""

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
        Input('oa-team-select',      'value'),
        Input('oa-comp-select',      'value'),
        Input('oa-venue-filter',     'value'),
        Input('oa-selected-matches', 'data'),
        Input('oa-date-filter',      'date'),
    )
    def _update_buildup(outcomes, start_thirds, end_thirds, bands,
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

        passes = _get_passes(opp_ev)
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
            _suc        = (filtered['outcome'].eq(1) if 'outcome' in filtered.columns
                           else pd.Series(True, index=filtered.index))
            plot_passes = filtered[_suc & ((filtered['Pass End X'] - filtered['x']) >= 25)]
        else:
            plot_passes = filtered

        use_total  = bool(dist_total)
        n_for_zone = n_all if use_total else len(filtered)

        _zone_key = (
            tuple(sorted(match_ids or [])),
            tuple(sorted(outcomes or [])),
            tuple(sorted(start_thirds or [])),
            tuple(sorted(end_thirds or [])),
            tuple(sorted(bands or [])),
            _h1, _h2,
            tuple(sorted(players or [])),
            use_total,
        )
        if _zone_key in _ZONE_IMG_CACHE:
            zone_src = _ZONE_IMG_CACHE[_zone_key]
        else:
            _img     = _zone_pitch_image(filtered, n_for_zone)
            zone_src = f'data:image/png;base64,{_img}' if _img else _SKEL_SRC
            _ZONE_IMG_CACHE[_zone_key] = zone_src

        # Touch heatmap: all opp events, player-filtered
        touches = opp_ev.dropna(subset=['x', 'y'])
        if players and 'player_name' in touches.columns:
            touches = touches[touches['player_name'].isin(players)]
        touch_src = (
            render_xt_heatmap_img(
                touches['x'].tolist(), touches['y'].tolist(),
                [1.0] * len(touches),
            )
            if not touches.empty else _SKEL_SRC
        )

        net_fig   = _network_fig(opp_ev)
        top5_prog = _top5_progressive(filtered)

        return (
            _build_pass_fig(plot_passes),
            _stats_numbers_children(filtered),
            zone_src, touch_src, net_fig, top5_prog,
        )
