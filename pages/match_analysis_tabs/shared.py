"""
Shared constants, helpers, and pitch-drawing utilities used across all
match analysis tabs.

Pitch backgrounds are generated using the mplsoccer library (same approach
as utils/interactive_pitch_visualization.py) and cached for performance.
"""



from dash import html, dcc
import dash_bootstrap_components as dbc
import plotly.graph_objects as go

from utils.config import COLORS


# =============================================================================
# Imports for components that still rely on constants moved to visualizations
# =============================================================================
from page_utils.visualizations import CHART_CONFIG, GOLD

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
