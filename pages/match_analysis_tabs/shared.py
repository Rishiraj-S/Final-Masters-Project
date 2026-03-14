"""
Shared constants, helpers, and pitch-drawing utilities used across all
match analysis tabs.

Pitch backgrounds are generated using the mplsoccer library (same approach
as utils/interactive_pitch_visualization.py) and cached for performance.
"""

import matplotlib
matplotlib.use('Agg')  # non-interactive backend for server use
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
from mplsoccer import Pitch, VerticalPitch
import io
import base64
import numpy as np

from dash import html, dcc
import dash_bootstrap_components as dbc
import plotly.graph_objects as go

from utils.config import COLORS


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
    font=dict(color='#E8E9ED', size=12),
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

HOME_COLOR = COLORS['primary_blue']
AWAY_COLOR = COLORS['garnet']
GOLD = COLORS['gold']


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
# Reusable UI components
# =============================================================================

BARCA_LOGO = '/assets/logos/team/FC-Barcelona-v2002.svg'


def page_header(title: str) -> dbc.Row:
    """Render a page heading with the Barça crest on the left."""
    return dbc.Row([
        dbc.Col(
            html.Img(src=BARCA_LOGO, style={'height': '48px', 'objectFit': 'contain'}),
            width='auto',
        ),
        dbc.Col(
            html.H2(title, style={'color': GOLD, 'marginBottom': 0, 'alignSelf': 'center'}),
            width='auto',
        ),
    ], align='center', className='mb-2')


def stat_card(value, label, color=None):
    """Create a compact stat card."""
    if color is None:
        color = GOLD
    return dbc.Card([
        dbc.CardBody([
            html.Div(str(value), className="stat-value", style={'color': color}),
            html.Div(label, className="stat-label")
        ], className="stat-card")
    ], className="h-100")


def section_card(title, children, footer=None):
    """Create a themed section card with a gold-accented header."""
    # Auto-wrap bare go.Figure objects so callers don't have to
    if isinstance(children, go.Figure):
        children = dcc.Graph(figure=children, config=CHART_CONFIG)
    card_children = [
        dbc.CardHeader(html.H5(title, className="mb-0", style={'color': GOLD})),
        dbc.CardBody(children),
    ]
    if footer:
        card_children.append(dbc.CardFooter(footer))
    return dbc.Card(card_children, className="mb-3")


def kpi_row(kpis: dict, columns: list, colors: dict = None):
    """Render a row of stat cards from a KPI dict."""
    if colors is None:
        colors = {}
    n = len(columns)
    width = max(2, 12 // n)
    return dbc.Row([
        dbc.Col(stat_card(kpis.get(key, 0), label, colors.get(key, GOLD)), width=width)
        for key, label in columns
    ], className="mb-3")


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
        pitch_color='grass',
        line_color='white',
        stripe=True,
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
    fig_mpl, _ = pitch.draw(figsize=(15, 10))

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
        pitch_color='grass',
        line_color='white',
        stripe=True,
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

    The image covers x ∈ [-2, 102] and y ∈ [-5, 105] to include the goal areas.
    Use VPITCH_AXIS to set matching axis ranges on the Plotly figure.
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


def _generate_vertical_half_pitch_image() -> str:
    """Generate a vertical attacking-half pitch PNG via mplsoccer (half=True)."""
    key = 'vertical_half'
    if key in _PITCH_CACHE:
        return _PITCH_CACHE[key]

    pitch = VerticalPitch(
        pitch_type='opta',
        pitch_color='grass',
        line_color='white',
        stripe=True,
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

    Coordinate system (same as add_vertical_pitch_background):
        x-axis : Opta y  (side-to-side, 0 = left touchline, 100 = right)
        y-axis : Opta x  (depth,        50 = halfway line, 100 = goal)

    Goal is rendered at the top (y=100). Use VPITCH_AXIS_HALF for matching axes.
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
# Pass map image utility
# =============================================================================

def render_pass_map_img(x_start, y_start, x_end, y_end,
                        outcomes=None) -> str:
    """
    Render a pass map with directional arrows on a grass pitch via mplsoccer.

    Successful passes are drawn in blue, unsuccessful in red.
    Returns a base64 PNG data-URI string suitable for use in html.Img(src=...).

    Args:
        x_start:  iterable of pass start x coords (Opta 0-100)
        y_start:  iterable of pass start y coords (Opta 0-100)
        x_end:    iterable of pass end x coords (Opta 0-100)
        y_end:    iterable of pass end y coords (Opta 0-100)
        outcomes: optional iterable of outcome values (1=successful, 0=failed)
    """
    pitch = Pitch(
        pitch_type='opta', pitch_color='grass',
        line_color='white', stripe=True,
        goal_type='box', goal_alpha=0.8,
    )
    fig_mpl, ax = pitch.draw(figsize=(12, 8))

    xs = np.asarray(x_start, dtype=float)
    ys = np.asarray(y_start, dtype=float)
    xe = np.asarray(x_end,   dtype=float)
    ye = np.asarray(y_end,   dtype=float)

    if len(xs) > 0:
        if outcomes is not None:
            oc = np.asarray(outcomes)
            mask_suc  = oc == 1
            mask_fail = ~mask_suc
            if mask_suc.any():
                pitch.arrows(xs[mask_suc], ys[mask_suc], xe[mask_suc], ye[mask_suc],
                             ax=ax, color='#4fc3f7', width=1.5, headwidth=4,
                             alpha=0.65, label='Successful')
            if mask_fail.any():
                pitch.arrows(xs[mask_fail], ys[mask_fail], xe[mask_fail], ye[mask_fail],
                             ax=ax, color='#ef5350', width=1.5, headwidth=4,
                             alpha=0.55, label='Unsuccessful')
            ax.legend(facecolor='#1a1a2e', labelcolor='white',
                      fontsize=9, loc='upper left')
        else:
            pitch.arrows(xs, ys, xe, ye,
                         ax=ax, color='#4fc3f7', width=1.5, headwidth=4, alpha=0.65)

    buf = io.BytesIO()
    fig_mpl.savefig(buf, format='png', dpi=80, bbox_inches='tight', pad_inches=0)
    buf.seek(0)
    img_str = base64.b64encode(buf.read()).decode()
    plt.close(fig_mpl)
    return f'data:image/png;base64,{img_str}'


# =============================================================================
# Heatmap image utility (shared across Player, Team, Opposition Analysis)
# =============================================================================

def render_heatmap_img(x_vals, y_vals, cmap: str = 'YlOrRd',
                       fallback_color: str = None, half: bool = False) -> str:
    """
    Render a KDE touch heatmap on a grass pitch via mplsoccer.

    Returns a base64 PNG data-URI string suitable for use in html.Img(src=...).

    Args:
        x_vals: iterable of x coordinates (Opta 0-100 scale)
        y_vals: iterable of y coordinates (Opta 0-100 scale)
        cmap: matplotlib colormap name for KDE plot (default 'YlOrRd')
        fallback_color: dot colour when fewer than 5 points (default: GOLD)
        half: if True, draw attacking half only
    """
    if fallback_color is None:
        fallback_color = GOLD

    pitch_kwargs = dict(
        pitch_type='opta', pitch_color='grass',
        line_color='white', stripe=True,
        goal_type='box', goal_alpha=0.8,
    )
    if half:
        pitch_kwargs['half'] = True

    pitch = Pitch(**pitch_kwargs)
    fig_mpl, ax = pitch.draw(figsize=(10, 7))

    if len(x_vals) >= 5:
        pitch.kdeplot(x_vals, y_vals, ax=ax, cmap=cmap,
                      fill=True, alpha=0.7, levels=100)
    else:
        pitch.scatter(x_vals, y_vals, ax=ax,
                      color=fallback_color, s=80,
                      edgecolors='white', linewidth=0.5)

    buf = io.BytesIO()
    fig_mpl.savefig(buf, format='png', dpi=80, bbox_inches='tight', pad_inches=0)
    buf.seek(0)
    img_str = base64.b64encode(buf.read()).decode()
    plt.close(fig_mpl)
    return f'data:image/png;base64,{img_str}'


def render_lsc_heatmap_img(x_vals, y_vals, color_hex: str, half: bool = False,
                           show_zone_pcts: bool = False) -> str:
    """
    Render a LinearSegmentedColormap KDE heatmap with marginal distribution
    curves (top = x-distribution, right = y-distribution) around the pitch.

    Returns a base64 PNG data URI string suitable for html.Img(src=...).

    Args:
        x_vals:         iterable of x coordinates (Opta 0-100 scale)
        y_vals:         iterable of y coordinates (Opta 0-100 scale)
        color_hex:      team colour as hex string, e.g. '#1a73e8'
        half:           if True, draw attacking half only
        show_zone_pcts: if True, overlay % of events in each pitch third
    """
    r_c = int(color_hex[1:3], 16) / 255
    g_c = int(color_hex[3:5], 16) / 255
    b_c = int(color_hex[5:7], 16) / 255

    # Colormap varies BOTH luminance and alpha so density differences are
    # visible even before alpha blending is considered.  The previous version
    # used a constant-RGB / alpha-only ramp, but passing alpha=0.88 to
    # heatmap_positional overrides per-patch alpha → uniform flat colour.
    cmap = LinearSegmentedColormap.from_list(
        'team_cmap',
        [
            (0.07, 0.07, 0.14, 0.0),                                        # transparent – empty cells show pitch grass
            (r_c * 0.35, g_c * 0.35, b_c * 0.35, 0.55),                    # dark dim team colour – low density
            (r_c,        g_c,        b_c,        0.85),                     # full team colour – medium density
            (min(r_c * 1.25, 1.0), min(g_c * 1.25, 1.0),
             min(b_c * 1.25, 1.0), 1.0),                                    # bright – peak density
        ],
    )

    x = np.asarray(x_vals, dtype=float)
    y = np.asarray(y_vals, dtype=float)

    bg = '#1a1a2e'
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
        pitch_type='opta', pitch_color='grass', line_color='white',
        stripe=True, goal_type='box', goal_alpha=0.8,
        pad_top=2, pad_bottom=2,
    )
    if half:
        pitch_kwargs.update(half=True, pad_left=2, pad_right=5)
    else:
        pitch_kwargs.update(pad_left=5, pad_right=5)

    pitch = Pitch(**pitch_kwargs)
    pitch.draw(ax=ax_main)

    # Sync marginal limits with the actual pitch axis extents
    ax_xlim = ax_main.get_xlim()
    ax_ylim = ax_main.get_ylim()
    ax_top.set_xlim(*ax_xlim)
    ax_right.set_ylim(*ax_ylim)

    if len(x) >= 2:
        bin_stat = pitch.bin_statistic_positional(
            x, y, statistic='count', positional='full', normalize=False,
        )
        # Do NOT pass alpha= here — it would override the per-patch alpha
        # values that the colormap encodes, producing a flat uniform colour.
        pitch.heatmap_positional(
            bin_stat, ax=ax_main, cmap=cmap,
            edgecolors='#1a1a2e', linewidth=0.8,
        )
    elif len(x) == 1:
        pitch.scatter(x, y, ax=ax_main, color=color_hex, s=60,
                      edgecolors='white', linewidth=0.5)

    # ── Optional zone percentage overlays ────────────────────────────────
    if show_zone_pcts and len(x) > 0:
        total = len(x)
        x_range_lo = 50 if half else 0
        thirds = [
            ('Def', x_range_lo,       33.33,  (x_range_lo + 33.33) / 2),
            ('Mid', 33.33,            66.67,  50.0),
            ('Att', 66.67,            100.0,  83.33),
        ]
        # Draw dashed third-dividers and overlay percentage labels
        for label, lo, hi, cx in thirds:
            if half and hi <= 50:
                continue  # skip zones entirely outside the half pitch view
            mask = (x >= lo) & (x < hi)
            pct  = mask.sum() / total * 100
            # Vertical divider lines (skip pitch boundaries)
            if lo > x_range_lo:
                ax_main.axvline(lo, color='white', linestyle='--',
                                linewidth=0.9, alpha=0.45, zorder=3)
            ax_main.text(
                cx, 93, f'{pct:.0f}%',
                ha='center', va='top', fontsize=10, fontweight='bold',
                color='white', zorder=5,
                bbox=dict(boxstyle='round,pad=0.28', facecolor='#000000',
                          alpha=0.55, edgecolor='none'),
            )
            ax_main.text(
                cx, 85, label,
                ha='center', va='top', fontsize=7, fontweight='600',
                color='#cccccc', zorder=5,
            )

    # ── Direction-of-attack label ─────────────────────────────────────────
    ax_main.text(
        0.5, 1.012, '➡  Direction of Attack',
        transform=ax_main.transAxes,
        ha='center', va='bottom',
        fontsize=9.5, fontweight='bold', color='black',
        bbox=dict(boxstyle='round,pad=0.3', facecolor='white', alpha=0.72,
                  edgecolor='none'),
        zorder=10,
    )

    # Gaussian smoothing kernel
    _s = 1.5
    _k = max(3, int(6 * _s + 1))
    if _k % 2 == 0:
        _k += 1
    _kern = np.exp(-0.5 * ((np.arange(_k) - _k // 2) / _s) ** 2)
    _kern /= _kern.sum()

    N = 20
    x_range = (50, 100) if half else (0, 100)

    # ── Top marginal: x distribution ─────────────────────────────────────
    x_counts, x_edges = np.histogram(x, bins=N, range=x_range)
    x_mids = (x_edges[:-1] + x_edges[1:]) / 2
    x_smooth = np.convolve(x_counts.astype(float), _kern, mode='same')
    bw = (x_edges[1] - x_edges[0]) * 0.85
    ax_top.bar(x_mids, x_counts, width=bw,
               color=(r_c, g_c, b_c, 0.40), align='center')
    ax_top.plot(x_mids, x_smooth, color=(r_c, g_c, b_c), linewidth=2)
    ax_top.fill_between(x_mids, x_smooth, alpha=0.15, color=(r_c, g_c, b_c))
    ax_top.set_ylim(bottom=0)

    # ── Right marginal: y distribution ───────────────────────────────────
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
    return f'data:image/png;base64,{img_str}'


# =============================================================================
# Legend / Info Box UI components
# =============================================================================

def build_legend_box(items: list[tuple[str, str, str]]) -> html.Div:
    """
    Build a styled legend box with colored symbols and labels.

    Args:
        items: list of (symbol_char, label, css_color) tuples.
               e.g. [('★', 'Goal', '#51cf66'), ('●', 'Saved', '#339af0')]
    """
    legend_items = []
    for symbol, label, color in items:
        legend_items.append(
            html.Span([
                html.Span(symbol, style={
                    'color': color,
                    'fontSize': '1rem',
                    'marginRight': '5px',
                    'fontWeight': '700',
                    'textShadow': f'0 0 4px {color}40',
                }),
                html.Span(label, style={
                    'color': COLORS['text_primary'],
                    'fontSize': '0.75rem',
                    'fontWeight': '500',
                }),
            ], className='culevision-legend-item')
        )

    return html.Div(
        legend_items,
        className='culevision-legend-box',
    )


def build_info_box(text: str) -> html.Div:
    """
    Build a styled info box for plain-text section descriptions.

    Args:
        text: the descriptive text to display.
    """
    return html.Div([
        html.Span('ℹ', style={
            'color': GOLD,
            'fontSize': '0.85rem',
            'marginRight': '8px',
            'fontWeight': '700',
            'flexShrink': '0',
        }),
        html.Span(text, style={
            'color': COLORS['text_secondary'],
            'fontSize': '0.75rem',
            'lineHeight': '1.4',
        }),
    ], className='culevision-info-box')


# =============================================================================
# Half-filter button styles (shared by build_up_passing, defensive_structure,
# transitions_counterpressing).  goalkeeping.py uses its own slight variant.
# =============================================================================

_HALF_BTN_BASE = {
    'border': f'1px solid {COLORS["dark_border"]}',
    'borderRadius': '6px', 'padding': '5px 14px',
    'cursor': 'pointer', 'fontSize': '0.82rem',
}
HALF_BTN_ACTIVE = {**_HALF_BTN_BASE,
                   'backgroundColor': GOLD, 'color': '#1A1D2E', 'fontWeight': '600'}
HALF_BTN_IDLE   = {**_HALF_BTN_BASE,
                   'backgroundColor': COLORS['dark_secondary'],
                   'color': COLORS['text_primary']}


# ── Reusable card style & section header ──────────────────────────────────

CARD_STYLE = {
    'backgroundColor': COLORS['dark_secondary'],
    'border': f'1px solid {COLORS["dark_border"]}',
    'borderRadius': '8px',
    'padding': '16px',
}

# Keep old alias for backward compat inside this file
_CARD_STYLE = CARD_STYLE


def section_header(title: str, subtitle: str = '') -> html.Div:
    """Gold-accented section header with optional subtitle and divider.

    Canonical implementation — all tabs should import from shared.
    """
    children = [
        html.H5(title, style={
            'color': GOLD, 'fontWeight': '700',
            'marginBottom': '2px', 'fontSize': '1rem',
            'letterSpacing': '0.03em',
        }),
    ]
    if subtitle:
        children.append(html.Span(subtitle, style={
            'color': COLORS['text_secondary'], 'fontSize': '0.75rem',
            'display': 'block', 'marginBottom': '4px',
        }))
    children.append(html.Hr(style={
        'borderColor': COLORS['dark_border'],
        'marginTop': '0', 'marginBottom': '16px',
    }))
    return html.Div(children)


def build_team_stats_table(
    team_name: str,
    color: str,
    metrics: list[tuple[str, str, bool]],
    full: dict,
    h1: dict,
    h2: dict,
) -> html.Div:
    """Single-team stats table with Full / 1st Half / 2nd Half columns.

    Args:
        team_name: display name.
        color: team accent colour.
        metrics: list of (label, dict_key, is_pct) tuples.
        full / h1 / h2: stat dicts for full match / 1st half / 2nd half.
    """
    _hdr = {
        'textAlign': 'center', 'padding': '6px 12px',
        'fontSize': '0.68rem', 'fontWeight': '700',
        'color': COLORS['text_secondary'],
        'textTransform': 'uppercase', 'letterSpacing': '0.06em',
        'borderBottom': f'1px solid {COLORS["dark_border"]}',
    }
    _lbl = {
        'padding': '6px 12px', 'fontSize': '0.8rem',
        'color': COLORS['text_secondary'], 'whiteSpace': 'nowrap',
    }
    _val = {
        'textAlign': 'center', 'padding': '6px 12px',
        'fontSize': '0.82rem', 'fontWeight': '600',
        'color': COLORS['text_primary'],
    }

    def _fmt(d, key, is_pct):
        v = d.get(key, 0)
        if is_pct:
            try:
                return f'{float(v):.1f}%'
            except (TypeError, ValueError):
                return '—'
        if isinstance(v, float):
            return f'{v:.1f}' if v != int(v) else str(int(v))
        return str(v)

    header = html.Tr([
        html.Th('', style=_hdr),
        html.Th('Full', style=_hdr),
        html.Th('1st Half', style=_hdr),
        html.Th('2nd Half', style=_hdr),
    ])
    rows = []
    for i, (label, key, is_pct) in enumerate(metrics):
        bg = COLORS.get('dark_tertiary', 'rgba(255,255,255,0.03)') if i % 2 == 0 else 'transparent'
        rows.append(html.Tr([
            html.Td(label, style=_lbl),
            html.Td(_fmt(full, key, is_pct), style=_val),
            html.Td(_fmt(h1, key, is_pct),   style=_val),
            html.Td(_fmt(h2, key, is_pct),   style=_val),
        ], style={'backgroundColor': bg}))

    return html.Div([
        html.Div(team_name, style={
            'color': color, 'fontWeight': '700', 'fontSize': '0.95rem',
            'marginBottom': '10px',
            'borderBottom': f'2px solid {color}',
            'paddingBottom': '6px',
        }),
        html.Table(
            [html.Thead(header), html.Tbody(rows)],
            style={'width': '100%', 'borderCollapse': 'collapse'},
        ),
    ], style=_CARD_STYLE)
