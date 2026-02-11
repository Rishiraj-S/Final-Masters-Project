"""
Shared constants, helpers, and pitch-drawing utilities used across all
match analysis tabs.
"""

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
# Pitch drawing helpers
# =============================================================================

def add_pitch_shapes_half(fig):
    """Add half-pitch markings as Plotly shapes."""
    line_color = 'rgba(255,255,255,0.3)'
    lw = 1

    shapes = [
        dict(type='rect', x0=50, y0=0, x1=100, y1=100,
             line=dict(color=line_color, width=lw)),
        dict(type='rect', x0=83, y0=21.1, x1=100, y1=78.9,
             line=dict(color=line_color, width=lw)),
        dict(type='rect', x0=94.2, y0=36.8, x1=100, y1=63.2,
             line=dict(color=line_color, width=lw)),
        dict(type='circle', x0=87.5, y0=49, x1=88.5, y1=51,
             line=dict(color=line_color, width=lw)),
        dict(type='circle', x0=40, y0=40, x1=60, y1=60,
             line=dict(color=line_color, width=lw)),
    ]

    for s in shapes:
        s['fillcolor'] = 'rgba(0,0,0,0)'
        fig.add_shape(**s)


def add_pitch_shapes_full(fig):
    """Add full pitch markings as Plotly shapes."""
    line_color = 'rgba(255,255,255,0.3)'
    lw = 1

    shapes = [
        dict(type='rect', x0=0, y0=0, x1=100, y1=100),
        dict(type='line', x0=50, y0=0, x1=50, y1=100),
        dict(type='circle', x0=40, y0=40, x1=60, y1=60),
        dict(type='rect', x0=0, y0=21.1, x1=17, y1=78.9),
        dict(type='rect', x0=83, y0=21.1, x1=100, y1=78.9),
        dict(type='rect', x0=0, y0=36.8, x1=5.8, y1=63.2),
        dict(type='rect', x0=94.2, y0=36.8, x1=100, y1=63.2),
    ]

    for s in shapes:
        s['line'] = dict(color=line_color, width=lw)
        s['fillcolor'] = 'rgba(0,0,0,0)'
        fig.add_shape(**s)
