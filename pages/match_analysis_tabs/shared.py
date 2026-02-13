"""
Shared constants, helpers, and pitch-drawing utilities used across all
match analysis tabs.

Pitch backgrounds are generated using the mplsoccer library (same approach
as utils/interactive_pitch_visualization.py) and cached for performance.
"""

import matplotlib
matplotlib.use('Agg')  # non-interactive backend for server use
import matplotlib.pyplot as plt
from mplsoccer import Pitch
import io
import base64

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

_PITCH_CACHE: dict[str, str] = {}


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
               showticklabels=False, fixedrange=True),
    yaxis=dict(range=[-2, 102], showgrid=False, zeroline=False,
               showticklabels=False, scaleanchor='x', fixedrange=True),
)

PITCH_AXIS_HALF = dict(
    xaxis=dict(range=[48, 105], showgrid=False, zeroline=False,
               showticklabels=False, fixedrange=True),
    yaxis=dict(range=[-2, 102], showgrid=False, zeroline=False,
               showticklabels=False, scaleanchor='x', fixedrange=True),
)
