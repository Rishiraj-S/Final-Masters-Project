"""
Unified visualisations library for CuléVision.

Contains shared charting configuration, base layouts, Plotly layout configurations,
mplsoccer pitch background rendering tools (with performance caching), KDE heatmaps, 
pass map visualisers, and complex composite figures (such as 5D radar charts).
"""

import matplotlib
matplotlib.use('Agg')  # non-interactive backend for server use
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap, to_rgba
from matplotlib.patches import FancyArrowPatch
from matplotlib.lines import Line2D
from mplsoccer import Pitch, VerticalPitch
import io
import base64
import functools
import operator
import numpy as np
import pandas as pd
from dataclasses import dataclass
from dash import html, dcc
import dash_bootstrap_components as dbc
import plotly.graph_objects as go

from utils.config import COLORS

# =============================================================================
# Core Colors & Constants
# =============================================================================

# Reference Style Colors (from image)
PITCH_BG = '#151932'
PITCH_LINE_COLOR = '#8899CC'
BARCA_BLUE = COLORS['primary_blue']

HOME_COLOR = BARCA_BLUE
AWAY_COLOR = COLORS['garnet']
GOLD = COLORS['gold']


# =============================================================================
# Chart theming
# =============================================================================

CHART_LAYOUT_DEFAULTS = dict(
    paper_bgcolor='rgba(0,0,0,0)',
    plot_bgcolor='rgba(0,0,0,0)',
    font=dict(color='#E8E9ED', size=12),
    margin=dict(l=40, r=40, t=50, b=40),
    legend=dict(
        orientation='h', yanchor='bottom', y=1.02, xanchor='center', x=0.5,
        font=dict(color='#E8E9ED')
    ),
)

_BASE_LAYOUT = dict(
    paper_bgcolor='rgba(0,0,0,0)',
    plot_bgcolor='rgba(0,0,0,0)',
    font=dict(color='#E8E9ED', size=12, family='Arial, sans-serif'),
)

def layout_config(**overrides) -> dict:
    """
    Return a layout dict starting from the base theme, merged with caller overrides.
    Use instead of ``**CHART_LAYOUT_DEFAULTS, margin=..., legend=...`` to avoid
    the 'multiple values for keyword argument' TypeError.
    """
    result = dict(_BASE_LAYOUT)
    result.update(overrides)
    return result

CHART_CONFIG = {'displayModeBar': False}

# =============================================================================
# Placeholder figure
# =============================================================================

def empty_fig(message: str = "No data available") -> go.Figure:
    """Return a styled empty placeholder figure."""
    fig = go.Figure()
    fig.update_layout(
        **CHART_LAYOUT_DEFAULTS,
        height=250,
        annotations=[dict(text=message, x=0.5, y=0.5, showarrow=False,
                          font=dict(size=14, color=COLORS['text_secondary']))]
    )
    return fig


# =============================================================================
# mplsoccer grass pitch background (cached)
# =============================================================================

_PITCH_CACHE = {}  # type: dict[str, str]

def _generate_pitch_image(half: bool = False) -> str:
    """Generate a grass pitch PNG via mplsoccer and return as base64 string."""
    key = 'half' if half else 'full'
    if key in _PITCH_CACHE:
        return _PITCH_CACHE[key]

    pitch_kwargs = dict(
        pitch_type='opta',
        pitch_color=PITCH_BG,
        line_color=PITCH_LINE_COLOR,
        linewidth=2.5,
        stripe=False,
        goal_type='box',
        goal_alpha=0.8,
        pad_top=2,
        pad_bottom=2,
    )
    if half:
        pitch_kwargs.update(half=True, pad_left=2, pad_right=5)
    else:
        pitch_kwargs.update(pad_left=5, pad_right=5)

    pitch = Pitch(**pitch_kwargs)
    fig_mpl, _ = pitch.draw(figsize=(12, 8))

    buf = io.BytesIO()
    fig_mpl.savefig(buf, format='png', dpi=100, bbox_inches='tight', pad_inches=0)
    buf.seek(0)
    _PITCH_CACHE[key] = base64.b64encode(buf.read()).decode()
    plt.close(fig_mpl)

    return _PITCH_CACHE[key]


def add_pitch_background(fig: go.Figure, half: bool = False) -> None:
    """
    Add a mplsoccer grass pitch as a background image to a Plotly figure.
    Coordinate system matches Opta (0-100 for both axes). The image includes
    padding for goal posts.
    """
    img = _generate_pitch_image(half=half)

    if half:
        # Half pitch covers x: 48..105, y: -2..102
        fig.add_layout_image(dict(
            source=f'data:image/png;base64,{img}',
            xref='x', yref='y',
            x=48, y=102, sizex=57, sizey=104,
            sizing='stretch', opacity=1, layer='below',
        ))
    else:
        # Full pitch covers x: -5..105, y: -2..102
        fig.add_layout_image(dict(
            source=f'data:image/png;base64,{img}',
            xref='x', yref='y',
            x=-5, y=102, sizex=110, sizey=104,
            sizing='stretch', opacity=1, layer='below',
        ))


# Pre-built axis dicts that match the pitch background dimensions
PITCH_AXIS_FULL = dict(
    xaxis=dict(range=[-5, 105], showgrid=False, zeroline=False,
               showticklabels=False, fixedrange=True, visible=False),
    yaxis=dict(range=[-2, 102], showgrid=False, zeroline=False,
               showticklabels=False, fixedrange=True, visible=False),
)

PITCH_AXIS_HALF = dict(
    xaxis=dict(range=[48, 105], showgrid=False, zeroline=False,
               showticklabels=False, fixedrange=True, visible=False),
    yaxis=dict(range=[-2, 102], showgrid=False, zeroline=False,
               showticklabels=False, fixedrange=True, visible=False),
)

def _generate_vertical_pitch_image() -> str:
    """Generate a vertical grass pitch PNG via mplsoccer and return as base64."""
    key = 'vertical'
    if key in _PITCH_CACHE:
        return _PITCH_CACHE[key]

    pitch = VerticalPitch(
        pitch_type='opta',
        pitch_color=PITCH_BG,
        line_color=PITCH_LINE_COLOR,
        linewidth=2.5,
        stripe=False,
        goal_type='box',
        goal_alpha=0.8,
        pad_left=2,
        pad_right=2,
        pad_bottom=5,
        pad_top=5,
    )
    fig_mpl, _ = pitch.draw(figsize=(7, 10.5))

    buf = io.BytesIO()
    fig_mpl.savefig(buf, format='png', dpi=100, bbox_inches='tight', pad_inches=0)
    buf.seek(0)
    _PITCH_CACHE[key] = base64.b64encode(buf.read()).decode()
    plt.close(fig_mpl)

    return _PITCH_CACHE[key]


def add_vertical_pitch_background(fig: go.Figure) -> None:
    """
    Add a vertical mplsoccer grass pitch as a background image to a Plotly figure.
    Coordinate convention (matches overview.py average-position chart):
        x : Opta y  (side-to-side, 0 = left touchline, 100 = right touchline)
        y : Opta x  (goal-to-goal, 0 = home goal at bottom, 100 = away goal at top)
    """
    img = _generate_vertical_pitch_image()
    # Vertical pitch: x covers [-2, 102] (width=104), y covers [-5, 105] (height=110)
    fig.add_layout_image(dict(
        source=f'data:image/png;base64,{img}',
        xref='x', yref='y',
        x=-2, y=105, sizex=104, sizey=110,
        sizing='stretch', opacity=1, layer='below',
    ))


# Pre-built axis dict that matches the vertical pitch background dimensions
VPITCH_AXIS = dict(
    xaxis=dict(range=[-2, 102], showgrid=False, zeroline=False,
               showticklabels=False, fixedrange=True, visible=False),
    yaxis=dict(range=[-5, 105], showgrid=False, zeroline=False,
               showticklabels=False, fixedrange=True, visible=False),
)


# =============================================================================
# Direction-of-attack annotations (always left→right / bottom→top)
# =============================================================================

def add_attack_direction(fig: go.Figure) -> None:
    """
    Add a '➡ Direction of Attack' label above a horizontal Plotly pitch figure.
    Style matches the LSC heatmap: rounded box, PITCH_BG fill, PITCH_LINE_COLOR
    border, bold white text.  Uses paper coordinates.
    """
    fig.add_annotation(
        x=0.5, y=1.02,
        xref='paper', yref='paper',
        text='<b>➡  Direction of Attack</b>',
        showarrow=False,
        font=dict(size=10, color='white', family='Arial, sans-serif'),
        xanchor='center', yanchor='bottom',
        bgcolor=f'rgba(21,25,50,0.8)',   # PITCH_BG at 80% opacity
        bordercolor=PITCH_LINE_COLOR,
        borderwidth=1,
        borderpad=4,
    )


def add_vertical_attack_direction(fig: go.Figure) -> None:
    """
    Add a '⬆ Direction of Attack' label beside a vertical Plotly pitch figure.
    Style matches the LSC heatmap: rounded box, PITCH_BG fill, PITCH_LINE_COLOR
    border, bold white text.  Text is rotated 90° so it reads bottom-to-top.
    """
    fig.add_annotation(
        x=1.015, y=0.5,
        xref='paper', yref='paper',
        text='<b>⬆  Direction of Attack</b>',
        showarrow=False,
        font=dict(size=10, color='white', family='Arial, sans-serif'),
        xanchor='left', yanchor='middle',
        textangle=-90,
        bgcolor=f'rgba(21,25,50,0.8)',
        bordercolor=PITCH_LINE_COLOR,
        borderwidth=1,
        borderpad=4,
    )

def _generate_vertical_half_pitch_image() -> str:
    """Generate a vertical attacking-half pitch PNG via mplsoccer (half=True)."""
    key = 'vertical_half'
    if key in _PITCH_CACHE:
        return _PITCH_CACHE[key]

    pitch = VerticalPitch(
        pitch_type='opta',
        pitch_color=PITCH_BG,
        line_color=PITCH_LINE_COLOR,
        linewidth=2.5,
        stripe=False,
        goal_type='box',
        goal_alpha=0.8,
        half=True,
        pad_left=2,
        pad_right=2,
        pad_bottom=2,
        pad_top=5,
    )
    fig_mpl, _ = pitch.draw(figsize=(7, 4.5))

    buf = io.BytesIO()
    fig_mpl.savefig(buf, format='png', dpi=100, bbox_inches='tight', pad_inches=0)
    buf.seek(0)
    _PITCH_CACHE[key] = base64.b64encode(buf.read()).decode()
    plt.close(fig_mpl)

    return _PITCH_CACHE[key]


def add_vertical_half_pitch_background(fig: go.Figure) -> None:
    """
    Add a vertical attacking-half pitch as a Plotly background image.
    Coordinate system:
        x-axis : Opta y  (side-to-side, 0 = left touchline, 100 = right)
        y-axis : Opta x  (depth,        50 = halfway line, 100 = goal)
    """
    img = _generate_vertical_half_pitch_image()
    # half=True with pad_bottom=2, pad_top=5 → y ∈ [48, 105], x ∈ [-2, 102]
    fig.add_layout_image(dict(
        source=f'data:image/png;base64,{img}',
        xref='x', yref='y',
        x=-2, y=105, sizex=104, sizey=57,
        sizing='stretch', opacity=1, layer='below',
    ))

# Pre-built axis dict matching the vertical half-pitch background
VPITCH_AXIS_HALF = dict(
    xaxis=dict(range=[-2, 102], showgrid=False, zeroline=False,
               showticklabels=False, fixedrange=True, visible=False),
    yaxis=dict(range=[48, 105], showgrid=False, zeroline=False,
               showticklabels=False, fixedrange=True, visible=False),
)


# =============================================================================
# Images & Matplotlib standalone exports (Heatmaps)
# =============================================================================

import hashlib as _hashlib

_heatmap_cache: dict[tuple, str] = {}


def render_lsc_heatmap_img(x_vals, y_vals, color_hex: str, half: bool = False,
                           show_zone_pcts: bool = False,
                           text_color: str | None = None) -> str:
    """
    Render a LinearSegmentedColormap KDE heatmap with marginal distribution
    curves (top = x-distribution, right = y-distribution) around the pitch.
    Returns a base64 PNG data URI string suitable for html.Img(src=...).

    Results are cached by content hash so the same heatmap (same match + same
    half filter) is only rendered once per session.
    """
    _x = np.asarray(x_vals, dtype=float)
    _y = np.asarray(y_vals, dtype=float)
    _cache_key = (
        _hashlib.md5(_x.tobytes()).hexdigest()[:10],
        _hashlib.md5(_y.tobytes()).hexdigest()[:10],
        color_hex, half, show_zone_pcts, text_color,
    )
    if _cache_key in _heatmap_cache:
        return _heatmap_cache[_cache_key]
    r_c = int(color_hex[1:3], 16) / 255
    g_c = int(color_hex[3:5], 16) / 255
    b_c = int(color_hex[5:7], 16) / 255

    cmap = LinearSegmentedColormap.from_list(
        'team_cmap',
        [
            (0.07, 0.07, 0.14, 0.0),
            (r_c * 0.35, g_c * 0.35, b_c * 0.35, 0.55),
            (r_c,        g_c,        b_c,        0.85),
            (min(r_c * 1.25, 1.0), min(g_c * 1.25, 1.0),
             min(b_c * 1.25, 1.0), 1.0),
        ],
    )

    x = np.asarray(x_vals, dtype=float)
    y = np.asarray(y_vals, dtype=float)

    # Map visual constants
    bg = PITCH_BG
    fig = plt.figure(figsize=(11, 8.5), facecolor=bg)
    gs = fig.add_gridspec(
        2, 2,
        width_ratios=[5, 1], height_ratios=[1, 5],
        hspace=0.03, wspace=0.03,
        left=0.01, right=0.99, top=0.97, bottom=0.01,
    )
    ax_main  = fig.add_subplot(gs[1, 0])
    ax_top   = fig.add_subplot(gs[0, 0])
    ax_right = fig.add_subplot(gs[1, 1])

    for ax in (ax_top, ax_right):
        ax.set_facecolor(bg)
        for spine in ax.spines.values():
            spine.set_visible(False)
        ax.tick_params(left=False, bottom=False, labelleft=False, labelbottom=False)

    pitch_kwargs = dict(
        pitch_type='opta', pitch_color=PITCH_BG, line_color=PITCH_LINE_COLOR,
        linewidth=2.5, stripe=False, goal_type='box', goal_alpha=0.8,
        pad_top=2, pad_bottom=2,
    )
    if half:
        pitch_kwargs.update(half=True, pad_left=2, pad_right=5)
    else:
        pitch_kwargs.update(pad_left=5, pad_right=5)

    pitch = Pitch(**pitch_kwargs)
    pitch.draw(ax=ax_main)

    ax_xlim = ax_main.get_xlim()
    ax_ylim = ax_main.get_ylim()
    ax_top.set_xlim(*ax_xlim)
    ax_right.set_ylim(*ax_ylim)

    if len(x) >= 2:
        # Use a muted version of the heatmap or just zones
        bin_stat = pitch.bin_statistic_positional(
            x, y, statistic='count', positional='full', normalize=False,
        )
        # Heatmap colors - subtle orange fade
        pitch.heatmap_positional(
            bin_stat, ax=ax_main, cmap=cmap,
            edgecolors=PITCH_BG, linewidth=0.8, alpha=0.3
        )
    elif len(x) == 1:
        pitch.scatter(x, y, ax=ax_main, color=BARCA_BLUE, s=60,
                      edgecolors='white', linewidth=0.5)

    if show_zone_pcts and len(x) > 0:
        total = len(x)
        x_range_lo = 50 if half else 0
        
        # Positional bins for text placement
        bin_stat = pitch.bin_statistic_positional(
            x, y, statistic='count', positional='full', normalize=False
        )
        
        # bin_stat is a list of dictionaries (one for each major zone)
        for zone in bin_stat:
            stats = zone['statistic'].flatten()
            cxs = zone['cx'].flatten()
            cys = zone['cy'].flatten()
            
            for bin_info, cx, cy in zip(stats, cxs, cys):
                if bin_info > 0:
                    pct = (bin_info / total) * 100
                    
                    _tc = text_color if text_color else BARCA_BLUE
                    # Large Count
                    ax_main.text(
                        cx, cy - 2, f'{int(bin_info)}',
                        ha='center', va='center', fontsize=22, fontweight='bold',
                        color=_tc, zorder=5
                    )
                    # Smaller Percentage
                    ax_main.text(
                        cx, cy + 4, f'({pct:.0f}%)',
                        ha='center', va='center', fontsize=12, fontweight='bold',
                        color=_tc, zorder=5
                    )

    ax_main.text(
        0.5, 1.012, '➡  Direction of Attack',
        transform=ax_main.transAxes,
        ha='center', va='bottom',
        fontsize=9.5, fontweight='bold', color='white',
        bbox=dict(boxstyle='round,pad=0.3', facecolor=PITCH_BG, alpha=0.8,
                  edgecolor=PITCH_LINE_COLOR),
        zorder=10,
    )

    _s = 1.5
    _k = max(3, int(6 * _s + 1))
    if _k % 2 == 0:
        _k += 1
    _kern = np.exp(-0.5 * ((np.arange(_k) - _k // 2) / _s) ** 2)
    _kern /= _kern.sum()

    N = 20
    x_range = (50, 100) if half else (0, 100)

    x_counts, x_edges = np.histogram(x, bins=N, range=x_range)
    x_mids = (x_edges[:-1] + x_edges[1:]) / 2
    x_smooth = np.convolve(x_counts.astype(float), _kern, mode='same')
    bw = (x_edges[1] - x_edges[0]) * 0.85
    ax_top.bar(x_mids, x_counts, width=bw,
               color=(r_c, g_c, b_c, 0.40), align='center')
    ax_top.plot(x_mids, x_smooth, color=(r_c, g_c, b_c), linewidth=2)
    ax_top.fill_between(x_mids, x_smooth, alpha=0.15, color=(r_c, g_c, b_c))
    ax_top.set_ylim(bottom=0)

    y_counts, y_edges = np.histogram(y, bins=N, range=(0, 100))
    y_mids = (y_edges[:-1] + y_edges[1:]) / 2
    y_smooth = np.convolve(y_counts.astype(float), _kern, mode='same')
    bh = (y_edges[1] - y_edges[0]) * 0.85
    ax_right.barh(y_mids, y_counts, height=bh,
                  color=(r_c, g_c, b_c, 0.40), align='center')
    ax_right.plot(y_smooth, y_mids, color=(r_c, g_c, b_c), linewidth=2)
    ax_right.fill_betweenx(y_mids, y_smooth, alpha=0.15, color=(r_c, g_c, b_c))
    ax_right.set_xlim(left=0)

    buf = io.BytesIO()
    fig.savefig(buf, format='png', dpi=80, bbox_inches='tight', pad_inches=0.05,
                facecolor=bg)
    buf.seek(0)
    img_str = base64.b64encode(buf.read()).decode()
    plt.close(fig)
    result = f'data:image/png;base64,{img_str}'
    _heatmap_cache[_cache_key] = result
    return result


# =============================================================================
# 5-Dimension Radar Configuration & Utility
# =============================================================================

RADAR_KEYS   = ['attack', 'defense', 'technical', 'physical', 'overall']
RADAR_LABELS = ['Attack', 'Defense', 'Technical', 'Physical', 'Overall']

RADAR_INFO: dict[str, tuple[str, str]] = {
    'Attack':    (
        'Scoring & Creativity',
        'Goals, shots, shot accuracy, assists and key passes — '
        'weighted by position-specific importance',
    ),
    'Defense':   (
        'Defensive Contribution',
        'Tackles, interceptions, recoveries, clearances and aerial win rate — '
        'weighted by position-specific importance',
    ),
    'Technical': (
        'Technical Quality',
        'Pass accuracy, dribble success rate, key passes and shot on target — '
        'equal weight across positions',
    ),
    'Physical':  (
        'Physical Duels',
        'Aerial duel win rate and defensive duel frequency — '
        'proxy for dominance in physical contests',
    ),
    'Overall':   (
        'Composite Score',
        'Simple average of Attack, Defense, Technical and Physical percentile scores',
    ),
}

RADAR_COLORS: dict[str, str] = {
    'Attack':    GOLD,
    'Defense':   AWAY_COLOR,
    'Technical': HOME_COLOR,
    'Physical':  '#51cf66',
    'Overall':   COLORS['text_primary'],
}

def build_radar_fig(player_name: str, d5: dict, n_peers: int) -> go.Figure:
    """Build a 5-axis Plotly polar radar from 5-dimension percentile scores."""
    r_player = [d5.get(k, 50) for k in RADAR_KEYS]
    r_avg    = [50] * len(RADAR_LABELS)

    fig = go.Figure()

    # Average reference ring (dashed Barça blue)
    fig.add_trace(go.Scatterpolar(
        r=r_avg + [r_avg[0]],
        theta=RADAR_LABELS + [RADAR_LABELS[0]],
        mode='lines',
        name=f'Positional Average ({n_peers} peers)',
        line=dict(color=HOME_COLOR, width=2, dash='dot'),
        fill='toself',
        fillcolor='rgba(0, 77, 152, 0.12)',
        hoverinfo='skip',
    ))

    # Player filled area (gold)
    fig.add_trace(go.Scatterpolar(
        r=r_player + [r_player[0]],
        theta=RADAR_LABELS + [RADAR_LABELS[0]],
        mode='lines+markers',
        name=player_name,
        line=dict(color=GOLD, width=2.5),
        fill='toself',
        fillcolor='rgba(237, 187, 0, 0.22)',
        marker=dict(color=GOLD, size=8, line=dict(color='white', width=1)),
        hovertemplate='<b>%{theta}</b><br>Percentile: <b>%{r}</b><extra></extra>',
    ))

    fig.update_layout(
        polar=dict(
            bgcolor='rgba(0,0,0,0)',
            radialaxis=dict(
                range=[0, 100],
                visible=True,
                tickvals=[25, 50, 75, 100],
                tickfont=dict(size=9, color=COLORS['text_secondary']),
                gridcolor=COLORS['dark_border'],
                linecolor=COLORS['dark_border'],
                tickangle=0,
            ),
            angularaxis=dict(
                tickfont=dict(size=13, color=COLORS['text_primary']),
                gridcolor=COLORS['dark_border'],
                linecolor=COLORS['dark_border'],
            ),
        ),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font=dict(color=COLORS['text_primary'], size=12),
        showlegend=True,
        legend=dict(
            font=dict(color=COLORS['text_primary'], size=10),
            bgcolor='rgba(0,0,0,0)',
            x=0.5, y=-0.10, xanchor='center', orientation='h',
        ),
        height=450,
        margin=dict(l=70, r=70, t=40, b=70),
    )
    return fig


def build_metric_explanation_card(n_peers: int, role_label: str) -> dbc.Card:
    """Card explaining each of the 5 radar dimensions."""
    sections = []
    for dim, (subtitle, desc) in RADAR_INFO.items():
        color = RADAR_COLORS[dim]
        sections.append(html.Div([
            html.Div(dim.upper(), style={
                'color': color, 'fontWeight': '700',
                'fontSize': '0.65rem', 'letterSpacing': '0.8px',
                'textTransform': 'uppercase',
                'marginTop': '12px' if sections else '0',
                'marginBottom': '3px',
            }),
            html.Div(subtitle, style={
                'color': COLORS['text_primary'], 'fontWeight': '600',
                'fontSize': '0.76rem', 'marginBottom': '2px',
                'paddingLeft': '10px', 'borderLeft': f'2px solid {color}',
            }),
            html.Div(desc, style={
                'color': COLORS['text_secondary'], 'fontSize': '0.70rem',
                'lineHeight': '1.4', 'paddingLeft': '10px',
            }),
        ]))

    footer = html.Div([
        html.Hr(style={'borderColor': COLORS['dark_border'], 'margin': '12px 0 8px'}),
        html.Small(
            f'Percentile rank vs {n_peers} positional peers ({role_label}).  '
            '100 = top, 50 = average.  Weights are position-specific.',
            style={'color': COLORS['text_secondary'], 'fontSize': '0.69rem', 'lineHeight': '1.5'},
        ),
    ])

    return dbc.Card([
        dbc.CardHeader(html.H6('Dimension Guide', style={'color': GOLD, 'marginBottom': 0})),
        dbc.CardBody([*sections, footer]),
    ], style={
        'backgroundColor': COLORS['dark_secondary'],
        'border': f'1px solid {COLORS["dark_border"]}',
        'height': '100%',
    })


def build_scatter_pitch_fig(x_vals, y_vals, title: str = None, 
                            color: str = GOLD, name: str = 'Points',
                            half: bool = False) -> go.Figure:
    """Convenience function to build a Plotly pitch with scatter points."""
    fig = go.Figure()
    add_pitch_background(fig, half=half)
    
    fig.add_trace(go.Scatter(
        x=x_vals, y=y_vals, mode='markers',
        marker=dict(
            color=color, 
            size=10, 
            line=dict(color=PITCH_BG, width=1.5)
        ),
        name=name
    ))
    
    axis_opts = PITCH_AXIS_HALF if half else PITCH_AXIS_FULL
    fig.update_layout(
        **axis_opts,
        **layout_config(title=title, height=600)
    )
    add_attack_direction(fig)
    return fig


def hex_to_rgb(hex_str: str):
    """Convert hex string to RGB tuple."""
    hex_str = hex_str.lstrip('#')
    if len(hex_str) == 3:
        hex_str = ''.join([c*2 for c in hex_str])
    return tuple(int(hex_str[i:i+2], 16) for i in (0, 2, 4))


def build_pass_map_fig(x_start, y_start, x_end, y_end, outcomes=None,
                       title: str = "Pass Map", half: bool = False) -> go.Figure:
    """Build an interactive Plotly pass map with gradient lines and end-point circles."""
    fig = go.Figure()
    add_pitch_background(fig, half=half)

    xs = np.asarray(x_start, dtype=float)
    ys = np.asarray(y_start, dtype=float)
    xe = np.asarray(x_end,   dtype=float)
    ye = np.asarray(y_end,   dtype=float)

    if len(xs) == 0:
        return fig

    if outcomes is None:
        outcomes = np.ones(len(xs), dtype=int)
    else:
        outcomes = np.asarray(outcomes)

    mask_suc  = (outcomes == 1)
    mask_fail = ~mask_suc

    N_SEG = 15  # gradient steps per line

    def add_gradient_passes(m, color, name):
        if not m.any():
            return
        indices = np.where(m)[0]

        # Batched gradient: N_SEG traces each covering 1/N_SEG of every line,
        # with linearly increasing opacity (faint at start → full at end).
        for step in range(N_SEG):
            t0 = step / N_SEG
            t1 = (step + 1) / N_SEG
            alpha = (step + 1) / N_SEG

            x_seg, y_seg = [], []
            for i in indices:
                xa = float(xs[i] + t0 * (xe[i] - xs[i]))
                ya = float(ys[i] + t0 * (ye[i] - ys[i]))
                xb = float(xs[i] + t1 * (xe[i] - xs[i]))
                yb = float(ys[i] + t1 * (ye[i] - ys[i]))
                x_seg += [xa, xb, None]
                y_seg += [ya, yb, None]

            fig.add_trace(go.Scatter(
                x=x_seg, y=y_seg,
                mode='lines',
                line=dict(color=color, width=2),
                opacity=alpha,
                showlegend=(step == N_SEG - 1),
                name=name,
                legendgroup=name,
                hoverinfo='skip',
            ))

        # Filled circles at end points
        fig.add_trace(go.Scatter(
            x=xe[m], y=ye[m],
            mode='markers',
            marker=dict(color=color, size=8, line=dict(width=0)),
            name=name,
            legendgroup=name,
            showlegend=False,
            hovertemplate='<b>' + name + ' Pass</b><br>End: (%{x:.1f}, %{y:.1f})<extra></extra>',
        ))

    add_gradient_passes(mask_suc,  BARCA_BLUE,       'Successful')
    add_gradient_passes(mask_fail, COLORS['garnet'], 'Unsuccessful')

    axis_opts = PITCH_AXIS_HALF if half else PITCH_AXIS_FULL
    fig.update_layout(
        **axis_opts,
        **layout_config(title=title, height=600),
        showlegend=True,
    )
    add_attack_direction(fig)
    return fig


# =============================================================================
# PassMap — filterable mplsoccer pass map with integrated Dash filter controls
# =============================================================================

@dataclass
class PassMapConfig:
    """
    Visual appearance settings for a PassMap instance.

    Attributes
    ----------
    color        : Arrow colour when no outcome column is present.
    success_color: Arrow colour for successful passes (outcome == 1).
    fail_color   : Arrow colour for unsuccessful passes (outcome == 0).
    half         : Render only the attacking half of the pitch.
    figsize      : Matplotlib figure size (width, height) in inches.
    n_segments   : Number of gradient segments per arrow.
    arrow_alpha  : Maximum opacity of each arrow.
    """
    color:         str   = HOME_COLOR
    success_color: str   = HOME_COLOR
    fail_color:    str   = AWAY_COLOR
    half:          bool  = False
    figsize:       tuple = (12, 8)
    n_segments:    int   = 20
    arrow_alpha:   float = 0.7


class PassMap:
    """
    Filterable mplsoccer pass map that returns a base64 PNG data URI.

    Filtering (zone, channel, outcome, time) is handled internally via
    PassMap.filter(), so callers can pass a raw pass DataFrame and let the
    class apply the active filter values from the Dash controls.

    The Dash filter controls themselves are generated by PassMap.dash_controls();
    pass ``show=[...]`` to render only the controls relevant to a given page.

    Example
    -------
    pm  = PassMap(PassMapConfig(color=HOME_COLOR))
    src = pm.render(passes_df,
                    end_x_col='Pass End X', end_y_col='Pass End Y',
                    start_thirds=['middle', 'final'], outcomes=[1])
    html.Img(src=src)

    controls = PassMap.dash_controls(
        show=['outcome', 'start_third', 'end_third', 'bands', 'h1_time', 'h2_time'],
        id_prefix='buildup',
    )
    """

    # x-axis thirds — Opta coords, direction of attack left → right
    THIRDS: dict = {
        'defensive': (0.0,   33.33),
        'middle':    (33.33, 66.67),
        'final':     (66.67, 100.0),
    }

    # y-axis bands (OR-logic when multiple selected)
    BANDS: dict = {
        'left':   (66.67, 100.0),
        'centre': (33.33, 66.67),
        'right':  (0.0,   33.33),
    }

    # Ordered list of all available filter control keys
    _ALL_CONTROLS = [
        'start_third', 'end_third', 'bands',
        'outcome', 'h1_time', 'h2_time',
    ]

    def __init__(self, config: PassMapConfig = None):
        self.config = config or PassMapConfig()

    # ------------------------------------------------------------------
    # Filtering
    # ------------------------------------------------------------------

    @classmethod
    def _thirds_range(cls, thirds: list) -> tuple:
        """Collapse a list of third names into a single (x_min, x_max) span."""
        ranges = [cls.THIRDS[t] for t in thirds if t in cls.THIRDS]
        if not ranges:
            return 0.0, 100.0
        return min(r[0] for r in ranges), max(r[1] for r in ranges)

    @classmethod
    def _bands_mask(cls, y_series, bands: list):
        """Return a boolean mask matching any of the selected y-axis bands."""
        conditions = [
            (y_series >= cls.BANDS[b][0]) & (y_series <= cls.BANDS[b][1])
            for b in bands if b in cls.BANDS
        ]
        if not conditions:
            return pd.Series(True, index=y_series.index)
        return functools.reduce(operator.or_, conditions)

    @classmethod
    def filter(cls, df: pd.DataFrame, *,
               start_thirds: list = None,
               end_thirds:   list = None,
               bands:        list = None,
               outcomes:     list = None,
               h1_range:     tuple = None,
               h2_range:     tuple = None,
               end_x_col:    str   = 'end_x') -> pd.DataFrame:
        """
        Apply spatial, channel, outcome, and time filters to a pass DataFrame.

        Parameters
        ----------
        start_thirds : Subset of ['defensive', 'middle', 'final']; None = no filter.
        end_thirds   : Same applied to pass-destination x.
        bands        : Subset of ['left', 'centre', 'right'] (y-axis, OR logic).
        outcomes     : e.g. [1] for successful only, [0, 1] for both; None = all.
        h1_range     : (min_min, max_min) window for first-half passes; None = all.
        h2_range     : Same for second half.  Both ranges are ORed together.
        end_x_col    : Column name for pass-end x coordinate.
        end_y_col    : Column name for pass-end y coordinate (used for bands).
        """
        out = df

        if start_thirds and len(start_thirds) < 3:
            lo, hi = cls._thirds_range(start_thirds)
            out = out[(out['x'] >= lo) & (out['x'] <= hi)]

        if end_thirds and len(end_thirds) < 3 and end_x_col in out.columns:
            lo, hi = cls._thirds_range(end_thirds)
            out = out[(out[end_x_col] >= lo) & (out[end_x_col] <= hi)]

        if bands and len(bands) < 3:
            out = out[cls._bands_mask(out['y'], bands)]

        if outcomes is not None and 'outcome' in out.columns:
            out = out[out['outcome'].isin(outcomes)]

        time_col = next(
            (c for c in ('time_min', 'time_minutes') if c in out.columns), None
        )
        if time_col and (h1_range or h2_range):
            t = pd.to_numeric(out[time_col], errors='coerce')
            masks = []
            if h1_range:
                masks.append((t >= h1_range[0]) & (t <= h1_range[1]))
            if h2_range:
                masks.append((t >= h2_range[0]) & (t <= h2_range[1]))
            out = out[functools.reduce(operator.or_, masks)]

        return out.copy()

    # ------------------------------------------------------------------
    # Drawing
    # ------------------------------------------------------------------

    @staticmethod
    def _draw_gradient_arrows(ax, x_start, y_start, x_end, y_end,
                              color: str, n_segments: int = 20,
                              alpha: float = 0.7) -> None:
        """
        Draw gradient pass lines, each ending in a FancyArrowPatch arrowhead.
        Opacity and brightness increase from origin → destination.
        """
        base = to_rgba(color)
        for x0, y0, x1, y1 in zip(x_start, y_start, x_end, y_end):
            for j in range(n_segments):
                t0, t1    = j / n_segments, (j + 1) / n_segments
                sx0, sy0  = x0 + t0 * (x1 - x0), y0 + t0 * (y1 - y0)
                sx1, sy1  = x0 + t1 * (x1 - x0), y0 + t1 * (y1 - y0)
                seg_alpha = alpha * (0.3 + 0.7 * t1)
                intensity = 0.4 + 0.6 * t1
                seg_color = (
                    base[0] * intensity, base[1] * intensity,
                    base[2] * intensity, seg_alpha,
                )
                if j < n_segments - 1:
                    ax.plot([sx0, sx1], [sy0, sy1],
                            color=seg_color, linewidth=2, zorder=2)
                else:
                    ax.add_patch(FancyArrowPatch(
                        (sx0, sy0), (sx1, sy1),
                        arrowstyle='->', mutation_scale=15,
                        linewidth=2, color=seg_color, zorder=2,
                    ))

    # ------------------------------------------------------------------
    # Render
    # ------------------------------------------------------------------

    def render(self, df: pd.DataFrame, *,
               start_thirds: list  = None,
               end_thirds:   list  = None,
               bands:        list  = None,
               outcomes:     list  = None,
               h1_range:     tuple = None,
               h2_range:     tuple = None,
               end_x_col:    str   = 'end_x',
               end_y_col:    str   = 'end_y') -> str:
        """
        Filter *df*, render the pass map, and return a base64 PNG data URI
        suitable for ``html.Img(src=...)``.

        All keyword arguments are forwarded to PassMap.filter(); see its
        docstring for full parameter details.
        """
        cfg = self.config

        filtered = self.filter(
            df,
            start_thirds=start_thirds, end_thirds=end_thirds,
            bands=bands,               outcomes=outcomes,
            h1_range=h1_range,         h2_range=h2_range,
            end_x_col=end_x_col,
        )

        pitch_kwargs = dict(
            pitch_type='opta',
            pitch_color=PITCH_BG, line_color=PITCH_LINE_COLOR,
            linewidth=2.5, stripe=False,
            goal_type='box', goal_alpha=0.8,
            pad_top=2, pad_bottom=2,
        )
        if cfg.half:
            pitch_kwargs.update(half=True, pad_left=2, pad_right=5)
        else:
            pitch_kwargs.update(pad_left=5, pad_right=5)

        pitch = Pitch(**pitch_kwargs)
        fig_mpl, ax = pitch.draw(figsize=cfg.figsize)

        if len(filtered) > 0 and end_x_col in filtered.columns:
            has_outcome = 'outcome' in filtered.columns
            if has_outcome:
                suc  = filtered[filtered['outcome'] == 1]
                fail = filtered[filtered['outcome'] == 0]
                if len(suc):
                    self._draw_gradient_arrows(
                        ax,
                        suc['x'].values, suc['y'].values,
                        suc[end_x_col].values, suc[end_y_col].values,
                        color=cfg.success_color,
                        n_segments=cfg.n_segments, alpha=cfg.arrow_alpha,
                    )
                if len(fail):
                    self._draw_gradient_arrows(
                        ax,
                        fail['x'].values, fail['y'].values,
                        fail[end_x_col].values, fail[end_y_col].values,
                        color=cfg.fail_color,
                        n_segments=cfg.n_segments, alpha=cfg.arrow_alpha,
                    )
                # Legend
                handles = []
                if len(suc):
                    handles.append(Line2D([0], [0], color=cfg.success_color,
                                          linewidth=2, label='Successful'))
                if len(fail):
                    handles.append(Line2D([0], [0], color=cfg.fail_color,
                                          linewidth=2, label='Unsuccessful'))
                if handles:
                    ax.legend(handles=handles, facecolor=PITCH_BG,
                              labelcolor='white', edgecolor=PITCH_LINE_COLOR,
                              fontsize=9, loc='upper left')
            else:
                self._draw_gradient_arrows(
                    ax,
                    filtered['x'].values,        filtered['y'].values,
                    filtered[end_x_col].values,  filtered[end_y_col].values,
                    color=cfg.color,
                    n_segments=cfg.n_segments, alpha=cfg.arrow_alpha,
                )

        ax.text(
            0.5, 1.012, '➡  Direction of Attack',
            transform=ax.transAxes,
            ha='center', va='bottom',
            fontsize=9.5, fontweight='bold', color='white',
            bbox=dict(boxstyle='round,pad=0.3', facecolor=PITCH_BG,
                      alpha=0.8, edgecolor=PITCH_LINE_COLOR),
            zorder=10,
        )

        buf = io.BytesIO()
        fig_mpl.savefig(buf, format='png', dpi=80,
                        bbox_inches='tight', pad_inches=0)
        buf.seek(0)
        img = base64.b64encode(buf.read()).decode()
        plt.close(fig_mpl)
        return f'data:image/png;base64,{img}'

    # ------------------------------------------------------------------
    # Dash filter controls
    # ------------------------------------------------------------------

    @staticmethod
    def dash_controls(show: list = None, id_prefix: str = 'pm') -> list:
        """
        Return a list of labelled Dash filter-control elements.

        Parameters
        ----------
        show      : Controls to render.  Subset of::

                        ['start_third', 'end_third', 'bands',
                         'outcome', 'h1_time', 'h2_time']

                    ``None`` renders all controls.
        id_prefix : Unique string prefix for component IDs — use a different
                    value per page to avoid ID collisions when multiple pass
                    maps share the same layout.

        Component IDs produced
        ----------------------
        ``{id_prefix}-start-third``   dcc.Checklist
        ``{id_prefix}-end-third``     dcc.Checklist
        ``{id_prefix}-bands``         dcc.Checklist
        ``{id_prefix}-outcome``       dcc.Checklist
        ``{id_prefix}-h1-time``       dcc.RangeSlider  (0 – 50 min)
        ``{id_prefix}-h2-time``       dcc.RangeSlider  (45 – 100 min)
        """
        active = show if show is not None else PassMap._ALL_CONTROLS

        _lbl = {
            'color': GOLD,
            'fontSize': '0.68rem',
            'fontWeight': '700',
            'letterSpacing': '0.8px',
            'textTransform': 'uppercase',
            'marginBottom': '4px',
            'marginTop': '14px',
        }
        _inline = dict(
            inline=True,
            inputStyle={'marginRight': '4px'},
            labelStyle={
                'display': 'inline-block',
                'marginRight': '10px',
                'color': COLORS['text_secondary'],
                'fontSize': '0.75rem',
            },
        )
        _div = html.Hr(style={'borderColor': COLORS['dark_border'],
                               'margin': '8px 0'})

        third_opts = [
            {'label': ' Own Third',   'value': 'defensive'},
            {'label': ' Mid Third',   'value': 'middle'},
            {'label': ' Final Third', 'value': 'final'},
        ]

        out = []

        if 'start_third' in active:
            out += [
                html.Div('Zone of Origin', style=_lbl),
                dcc.Checklist(
                    id=f'{id_prefix}-start-third',
                    options=third_opts,
                    value=['defensive', 'middle', 'final'],
                    **_inline,
                ),
            ]

        if 'end_third' in active:
            out += [
                _div,
                html.Div('Zone of Destination', style=_lbl),
                dcc.Checklist(
                    id=f'{id_prefix}-end-third',
                    options=third_opts,
                    value=['defensive', 'middle', 'final'],
                    **_inline,
                ),
            ]

        if 'bands' in active:
            out += [
                _div,
                html.Div('Band', style=_lbl),
                dcc.Checklist(
                    id=f'{id_prefix}-bands',
                    options=[
                        {'label': ' Left',   'value': 'left'},
                        {'label': ' Centre', 'value': 'centre'},
                        {'label': ' Right',  'value': 'right'},
                    ],
                    value=['left', 'centre', 'right'],
                    **_inline,
                ),
            ]

        if 'outcome' in active:
            out += [
                _div,
                html.Div('Outcome', style=_lbl),
                dcc.Checklist(
                    id=f'{id_prefix}-outcome',
                    options=[
                        {'label': ' Successful',   'value': 1},
                        {'label': ' Unsuccessful', 'value': 0},
                    ],
                    value=[1, 0],
                    **_inline,
                ),
            ]

        if 'h1_time' in active:
            out += [
                _div,
                html.Div('1st Half (min)', style=_lbl),
                dcc.RangeSlider(
                    id=f'{id_prefix}-h1-time',
                    min=0, max=50, step=1, value=[0, 50],
                    marks={0: '0', 15: '15', 30: '30', 45: '45', 50: '50+'},
                    tooltip={'placement': 'bottom', 'always_visible': False},
                ),
            ]

        if 'h2_time' in active:
            out += [
                html.Div('2nd Half (min)', style=_lbl),
                dcc.RangeSlider(
                    id=f'{id_prefix}-h2-time',
                    min=45, max=100, step=1, value=[45, 100],
                    marks={45: '45', 60: '60', 75: '75', 90: '90', 100: '90+'},
                    tooltip={'placement': 'bottom', 'always_visible': False},
                ),
            ]

        return out
