"""
CuléVision — Match Report analysis tabs (combined single module).

Merged from the former match_analysis_tabs/ package. Behaviour is identical;
private helpers that collided across the original files were given
per-section prefixes (e.g. _ao_compute / _gk_compute).
"""
from __future__ import annotations

# ============================================================================
# ===== shared.py =====
# ============================================================================
"""
shared.py — UI primitives shared across all match analysis tabs.
"""

import plotly.graph_objects as go
from dash import html, dcc
import dash_bootstrap_components as dbc

from utils.config import COLORS
from page_utils.visualizations import GOLD, CHART_CONFIG

BARCA_LOGO = '/assets/logos/team/barcelona.svg'


def page_header(title: str) -> dbc.Row:
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
    if color is None:
        color = GOLD
    return dbc.Card([
        dbc.CardBody([
            html.Div(str(value), className="stat-value", style={'color': color}),
            html.Div(label, className="stat-label")
        ], className="stat-card")
    ], className="h-100")


def section_card(title, children, footer=None):
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
    if colors is None:
        colors = {}
    n = len(columns)
    width = max(2, 12 // n)
    return dbc.Row([
        dbc.Col(stat_card(kpis.get(key, 0), label, colors.get(key, GOLD)), width=width)
        for key, label in columns
    ], className="mb-3")


def build_legend_box(items: list) -> html.Div:
    legend_items = []
    for symbol, label, color in items:
        legend_items.append(
            html.Span([
                html.Span(symbol, style={
                    'color': color, 'fontSize': '1rem', 'marginRight': '5px',
                    'fontWeight': '700', 'textShadow': f'0 0 4px {color}40',
                }),
                html.Span(label, style={
                    'color': COLORS['text_primary'], 'fontSize': '0.75rem', 'fontWeight': '500',
                }),
            ], className='culevision-legend-item')
        )
    return html.Div(legend_items, className='culevision-legend-box')


def build_info_box(text: str) -> html.Div:
    return html.Div([
        html.Span('ℹ', style={
            'color': GOLD, 'fontSize': '0.85rem', 'marginRight': '8px',
            'fontWeight': '700', 'flexShrink': '0',
        }),
        html.Span(text, style={
            'color': COLORS['text_secondary'], 'fontSize': '0.75rem', 'lineHeight': '1.4',
        }),
    ], className='culevision-info-box')


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

CARD_STYLE = {
    'backgroundColor': COLORS['dark_secondary'],
    'border': f'1px solid {COLORS["dark_border"]}',
    'borderRadius': '8px',
    'padding': '16px',
}
_CARD_STYLE = CARD_STYLE


def section_header(title: str, subtitle: str = '') -> html.Div:
    children = [
        html.H5(title, style={
            'color': GOLD, 'fontWeight': '700',
            'marginBottom': '2px', 'fontSize': '1rem',
            'letterSpacing': '0.03em', 'textAlign': 'center',
        }),
    ]
    if subtitle:
        children.append(html.Span(subtitle, style={
            'color': COLORS['text_secondary'], 'fontSize': '0.75rem',
            'display': 'block', 'marginBottom': '4px', 'textAlign': 'center',
        }))
    children.append(html.Hr(style={
        'borderColor': COLORS['dark_border'],
        'marginTop': '0', 'marginBottom': '16px',
    }))
    return html.Div(children, style={'textAlign': 'center'})


def build_team_stats_table(
    team_name: str,
    color: str,
    metrics: list,
    full: dict,
    h1: dict,
    h2: dict,
) -> html.Div:
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

# ============================================================================
# ===== overview.py =====
# ============================================================================
import io, base64, math
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import matplotlib.pyplot as plt
import matplotlib.patheffects as mpe
from mplsoccer import VerticalPitch
from sklearn.preprocessing import MinMaxScaler
from dash import html, dcc
import dash_bootstrap_components as dbc
from utils.config import COLORS
from utils.data_utils import get_match_lineup, exclude_own_goals, count_goals
from utils.match_data_adapter import get_match_metadata, compute_team_kpis, get_starting_lineups, get_substitutions
from utils.xg_utils import add_xg_column
from page_utils.visualizations import HOME_COLOR, AWAY_COLOR, GOLD, CHART_CONFIG, layout_config, add_pitch_background, PITCH_AXIS_FULL, render_xt_heatmap_img
from page_utils.event_filters import SHOT_TYPES

_COORDS: dict = {
    "433": {
        1:  (4,  50),   2:  (22, 13),   5:  (18, 33),   6:  (18, 67),   3:  (22, 87),
        7:  (37, 23),   4:  (37, 50),   8:  (37, 77),  10:  (47, 17),   9:  (47, 50),
        11: (47, 83),
    },
    "4231": {
        1:  (4,  50),   2:  (22, 13),   5:  (18, 33),   6:  (18, 67),   3:  (22, 87),
        4:  (32, 37),   8:  (32, 63),   7:  (43, 17),  10:  (43, 50),  11:  (43, 83),
        9:  (48, 50),
    },
    "442": {
        1:  (4,  50),   2:  (22, 13),   5:  (18, 33),   6:  (18, 67),   3:  (22, 87),
        7:  (38, 12),   4:  (37, 37),   8:  (37, 63),  11:  (38, 88),   9:  (47, 35),
        10: (47, 65),
    },
    "4141": {
        1:  (4,  50),   2:  (22, 13),   5:  (18, 33),   6:  (18, 67),   3:  (22, 87),
        4:  (31, 50),   7:  (40, 13),   8:  (40, 37),  10:  (40, 63),  11:  (40, 87),
        9:  (48, 50),
    },
    "4321": {
        1:  (4,  50),   2:  (22, 13),   5:  (18, 33),   6:  (18, 67),   3:  (22, 87),
        4:  (34, 27),   7:  (34, 50),   8:  (34, 73),   9:  (44, 30),  10:  (47, 50),
        11: (44, 70),
    },
    "352": {
        1:  (4,  50),   5:  (17, 23),   6:  (17, 50),  11:  (17, 77),   2:  (30, 10),
        4:  (36, 30),   7:  (36, 50),   8:  (36, 70),   3:  (30, 90),   9:  (47, 35),
        10: (47, 65),
    },
    "451": {
        1:  (4,  50),   2:  (22, 13),   5:  (18, 33),   6:  (18, 67),   3:  (22, 87),
        7:  (37, 12),   4:  (37, 30),   8:  (37, 50),  10:  (37, 70),  11:  (37, 88),
        9:  (47, 50),
    },
    "3421": {
        1:  (4,  50),   5:  (18, 25),   6:  (18, 50),   8:  (18, 75),   2:  (33, 12),
        4:  (38, 36),   7:  (38, 64),   3:  (33, 88),   9:  (45, 35),  10:  (47, 50),
        11: (45, 65),
    },
    "343": {
        1:  (4,  50),   5:  (18, 25),   6:  (18, 50),  11:  (18, 75),   2:  (36, 20),
        3:  (36, 40),   4:  (36, 60),  10:  (36, 80),   7:  (47, 20),   8:  (47, 50),
        9:  (47, 80),
    },
    "4132": {
        1:  (4,  50),   2:  (22, 13),   5:  (18, 33),   6:  (18, 67),   3:  (22, 87),
        4:  (31, 50),   7:  (39, 23),   8:  (39, 77),  11:  (43, 50),   9:  (47, 35),
        10: (47, 65),
    },
    "4312": {
        1:  (4,  50),   2:  (22, 13),   5:  (18, 33),   6:  (18, 67),   3:  (22, 87),
        7:  (33, 23),   4:  (33, 50),  11:  (33, 77),   8:  (42, 50),   9:  (47, 33),
        10: (47, 67),
    },
    "3142": {
        1:  (4,  50),   5:  (17, 25),   6:  (17, 50),  11:  (17, 75),   8:  (29, 50),
        2:  (37, 15),   7:  (37, 35),   4:  (37, 65),   3:  (37, 85),   9:  (47, 35),
        10: (47, 65),
    },
}


def _get_slot_coords(formation: str, slot: int, is_home: bool):
    coords_home = _COORDS.get(formation, {})
    if slot in coords_home:
        x, y = coords_home[slot]
        return (x, y) if is_home else (100 - x, 100 - y)
    lines = [int(d) for d in formation if d.isdigit()]
    if not lines:
        lines = [4, 3, 3]
    if slot == 1:
        x, y = 4, 50
    else:
        x_steps = [20, 32, 40, 47]
        idx = slot - 2
        cum = 0
        x, y = 37, 50
        for li, count in enumerate(lines):
            if idx < cum + count:
                x = x_steps[min(li, len(x_steps) - 1)]
                pos_in_line = idx - cum
                y = 10 + (80 / max(count - 1, 1)) * pos_in_line if count > 1 else 50
                break
            cum += count
    return (x, y) if is_home else (100 - x, 100 - y)


def _shorten_name(name) -> str:
    if not name or not isinstance(name, str):
        return ''
    name = name.strip()
    if not name:
        return ''
    parts = name.split()
    if len(parts) == 1 or len(name) <= 14:
        return name
    return f"{parts[0][0]}. {' '.join(parts[1:])}"


def _format_formation(formation_str: str) -> str:
    if not formation_str or len(formation_str) < 2:
        return formation_str or ''
    return '-'.join(formation_str)


def _generate_team_lineup_image(starters, formation: str, color: str):
    if starters is None or starters.empty:
        return None
    fig, ax_p = plt.subplots(figsize=(5, 8), facecolor='#0A0E27')
    fig.subplots_adjust(left=0.01, right=0.99, top=0.92, bottom=0.02)
    ax_p.set_facecolor('#0A0E27')
    pitch = VerticalPitch(
        pitch_type='opta', pitch_color='#3a7d44', line_color='white',
        stripe=True, stripe_color='#2e6b39', goal_type='box', goal_alpha=0.85,
        pad_top=10, pad_bottom=5, pad_left=3, pad_right=3,
    )
    pitch.draw(ax=ax_p)
    fmt_label = _format_formation(formation)
    if fmt_label:
        ax_p.text(50, 108, fmt_label,
                  ha='center', va='bottom', fontsize=12, color=color, fontweight='bold',
                  path_effects=[mpe.withStroke(linewidth=2.5, foreground='#0A0E27')])
    sc_xs, sc_ys, tx_xs, tx_ys, jerseys, names, caps = [], [], [], [], [], [], []
    for _, row in starters.iterrows():
        slot = int(row['formation_slot'])
        name = str(row.get('player_name', '') or '').strip()
        try:
            jersey = int(row['jersey_number'])
        except (ValueError, TypeError):
            jersey = ''
        is_cap = bool(row.get('is_captain', False))
        opta_x, opta_y = _get_slot_coords(formation, slot, True)
        depth   = float(opta_x) * 2.0
        lateral = float(opta_y)
        sc_xs.append(depth); sc_ys.append(lateral)
        tx_xs.append(lateral); tx_ys.append(depth)
        jerseys.append(str(jersey)); names.append(name); caps.append(is_cap)
    if not sc_xs:
        plt.close(fig)
        return None
    pitch.scatter(sc_xs, sc_ys, s=700, c=color, ax=ax_p, zorder=4, alpha=0.22, edgecolors='none')
    pitch.scatter(sc_xs, sc_ys, s=500, c=color, ax=ax_p, zorder=5, alpha=0.95, edgecolors='white', linewidths=1.4)
    for i in range(len(sc_xs)):
        lat = tx_xs[i]; dep = tx_ys[i]
        ax_p.text(lat, dep, jerseys[i], ha='center', va='center',
                  fontsize=8, fontweight='bold', color='white', zorder=7)
        short = _shorten_name(names[i])
        ax_p.text(lat, dep - 5.5, short, ha='center', va='top',
                  fontsize=7, color='white', zorder=7,
                  path_effects=[mpe.withStroke(linewidth=2, foreground='#0A0E27')])
        if caps[i]:
            pitch.scatter([dep + 4.0], [lat + 5.0], s=120, c=GOLD, ax=ax_p, zorder=8, edgecolors='none')
            ax_p.text(lat + 5.0, dep + 4.0, 'C', ha='center', va='center',
                      fontsize=4.5, fontweight='bold', color='#0A0E27', zorder=9)
    buf = io.BytesIO()
    fig.savefig(buf, format='png', dpi=130, facecolor=fig.get_facecolor(),
                edgecolor='none', bbox_inches='tight')
    buf.seek(0)
    img_b64 = base64.b64encode(buf.read()).decode()
    plt.close(fig)
    return img_b64


def _build_lineup_html_panel(subs_list: list, color: str, align: str = 'left') -> html.Div:
    is_right = align == 'right'
    text_align = 'right' if is_right else 'left'
    sub_rows = []
    for s in subs_list:
        minute = s.get('minute', 0) or 0
        p_off  = _shorten_name(s.get('player_off') or '')
        p_on   = _shorten_name(s.get('player_on')  or '')
        is_inj = s.get('reason', '') == 'Injury'
        if not p_off and not p_on:
            continue
        inj_icon = html.Span(' ⚕', style={'color': '#ff6b6b', 'fontSize': '0.72rem'}) if is_inj else html.Span()
        sub_rows.append(html.Div([
            html.Div([html.Span(f"{minute}' ", style={'color': GOLD, 'fontWeight': '700', 'fontSize': '0.8rem'}),
                      html.Span('↓ ', style={'color': '#ff6b6b', 'fontWeight': '700', 'fontSize': '0.9rem'}),
                      html.Span(p_off or '—', style={'color': COLORS['text_secondary'], 'fontSize': '0.85rem'}),
                      inj_icon], style={'textAlign': 'left'}),
            html.Div([html.Span('↑ ', style={'color': '#51cf66', 'fontWeight': '700', 'fontSize': '0.9rem',
                                              'marginLeft': '20px'}),
                      html.Span(p_on or '—', style={'color': '#E8E9ED', 'fontSize': '0.85rem', 'fontWeight': '500'})],
                     style={'textAlign': 'left'}),
        ], style={'width': '50%', 'boxSizing': 'border-box',
                  'padding': '5px 12px 5px 0',
                  'borderBottom': f"1px solid {COLORS['dark_border']}"}))
    header = html.Div('Substitutions', style={
        'color': color, 'fontSize': '0.78rem', 'fontWeight': '700',
        'textTransform': 'uppercase', 'letterSpacing': '0.05em',
        'marginBottom': '8px', 'textAlign': text_align,
    })
    rows_grid = html.Div(sub_rows, style={'display': 'flex', 'flexWrap': 'wrap'}) if sub_rows else \
        html.Div('No substitutions', style={'color': COLORS['text_secondary'],
                                             'fontSize': '0.82rem', 'textAlign': text_align})
    return html.Div([header, rows_grid], style={
        'padding': '14px 16px', 'backgroundColor': COLORS['dark_secondary'],
        'borderRadius': '8px', 'border': f"1px solid {COLORS['dark_border']}", 'height': '100%',
    })


_POS_LABEL_COLOR = {
    'GK': '#ffc107',
    'RB': '#4dabf7', 'CB': '#4dabf7', 'LB': '#4dabf7',
    'CDM': '#51cf66', 'CM': '#51cf66', 'MC': '#51cf66', 'CAM': '#51cf66',
    'RM': '#ff922b', 'RW': '#ff922b', 'LM': '#ff922b', 'LW': '#ff922b',
    'CF': '#ff6b6b',
}


def _build_lineup_card(team_name, lineup_data, color, align='start'):
    formation = lineup_data.get('formation', '')
    players = lineup_data.get('players', [])
    text_align = 'left' if align == 'start' else 'right'
    player_rows = []
    for p in players[:11]:
        pos = p.get('position', '')
        jersey = p.get('jersey', '')
        name = p.get('name', '')
        pos_color = _POS_LABEL_COLOR.get(pos, COLORS['text_secondary'])
        pos_badge = html.Span(pos or '—', style={
            'display': 'inline-block', 'width': '36px', 'textAlign': 'center',
            'fontSize': '0.7rem', 'fontWeight': '700', 'color': '#0A0E27',
            'backgroundColor': pos_color, 'borderRadius': '3px', 'padding': '1px 0',
            'marginRight': '8px' if align == 'start' else '0',
            'marginLeft': '8px' if align == 'end' else '0', 'flexShrink': '0',
        })
        jersey_el = html.Span(jersey, style={
            'fontWeight': '700', 'color': color, 'fontSize': '0.9rem',
            'width': '28px', 'textAlign': 'center', 'flexShrink': '0',
        })
        name_el = html.Span(name, style={
            'color': COLORS['text_primary'], 'fontSize': '0.85rem', 'flex': '1',
            'overflow': 'hidden', 'textOverflow': 'ellipsis', 'whiteSpace': 'nowrap',
        })
        row_children = [pos_badge, jersey_el, name_el] if align == 'start' else [name_el, jersey_el, pos_badge]
        player_rows.append(html.Div(row_children, style={
            'display': 'flex', 'alignItems': 'center', 'padding': '3px 0',
            'direction': 'ltr' if align == 'start' else 'rtl',
        }))
    formation_display = _format_formation(formation)
    return html.Div([
        html.Div(formation_display, style={
            'textAlign': text_align, 'color': GOLD, 'fontSize': '0.95rem',
            'fontWeight': '700', 'marginBottom': '8px', 'letterSpacing': '0.05em',
        }) if formation_display else html.Div(),
        *player_rows,
    ], style={
        'padding': '12px 16px', 'backgroundColor': COLORS['dark_secondary'],
        'borderRadius': '8px', 'border': f"1px solid {COLORS['dark_border']}",
    })


def _build_sub_row(sub, color):
    minute  = sub.get('minute', 0)
    p_off   = sub.get('player_off', '')
    p_on    = sub.get('player_on', '')
    j_off   = sub.get('jersey_off', '')
    j_on    = sub.get('jersey_on', '')
    reason  = sub.get('reason', '')
    reason_icon = html.I(
        className="fas fa-band-aid",
        style={'color': '#ff6b6b', 'fontSize': '0.65rem', 'marginLeft': '4px'},
    ) if reason == 'Injury' else html.Span()
    return html.Div([
        html.Span(f"{minute}'", style={
            'color': GOLD, 'fontWeight': '700', 'fontSize': '0.8rem',
            'width': '32px', 'textAlign': 'right', 'flexShrink': '0', 'marginRight': '10px',
        }),
        html.I(className="fas fa-arrow-down", style={'color': '#ff6b6b', 'fontSize': '0.65rem', 'marginRight': '4px'}),
        html.Span(f"{j_off} ", style={'color': COLORS['text_secondary'], 'fontSize': '0.75rem', 'fontWeight': '600'}),
        html.Span(p_off, style={'color': COLORS['text_secondary'], 'fontSize': '0.8rem'}),
        reason_icon,
        html.Span(" ", style={'width': '12px', 'flexShrink': '0'}),
        html.I(className="fas fa-arrow-up", style={'color': '#51cf66', 'fontSize': '0.65rem', 'marginRight': '4px'}),
        html.Span(f"{j_on} ", style={'color': COLORS['text_primary'], 'fontSize': '0.75rem', 'fontWeight': '600'}),
        html.Span(p_on, style={'color': COLORS['text_primary'], 'fontSize': '0.8rem', 'fontWeight': '500'}),
    ], style={'display': 'flex', 'alignItems': 'center', 'padding': '4px 0'})


def _build_subs_section(team_name, subs_list, color):
    if not subs_list:
        return html.Div()
    return html.Div([
        html.Div("Substitutions", style={
            'color': color, 'fontSize': '0.8rem', 'fontWeight': '700',
            'marginBottom': '6px', 'textTransform': 'uppercase', 'letterSpacing': '0.05em',
        }),
        *[_build_sub_row(s, color) for s in subs_list],
    ], style={
        'padding': '12px 16px', 'backgroundColor': COLORS['dark_secondary'],
        'borderRadius': '8px', 'border': f"1px solid {COLORS['dark_border']}", 'marginTop': '8px',
    })


def _tv_stat_bar(label, home_val, away_val,
                 home_h1=None, away_h1=None, home_h2=None, away_h2=None,
                 suffix='', is_percentage=False, decimals=0, tooltip=None):
    hv = float(home_val) if home_val else 0
    av = float(away_val) if away_val else 0
    max_val = max(hv, av, 1)
    home_pct = (hv / max_val) * 100
    away_pct = (av / max_val) * 100

    def _fmt(v):
        if v is None:
            return None
        fv = float(v) if v else 0
        if is_percentage:
            return f"{fv:.1f}{suffix}"
        elif decimals > 0:
            return f"{fv:.{decimals}f}{suffix}"
        else:
            return f"{int(fv)}{suffix}"

    h_display = _fmt(hv); a_display = _fmt(av)
    hh1 = _fmt(home_h1); hh2 = _fmt(home_h2)
    ah1 = _fmt(away_h1); ah2 = _fmt(away_h2)
    h_weight = 'bold' if hv >= av else 'normal'
    a_weight = 'bold' if av >= hv else 'normal'
    bar_track = {
        'height': '14px', 'borderRadius': '7px', 'backgroundColor': COLORS['dark_tertiary'],
        'overflow': 'hidden', 'display': 'flex',
    }
    label_style = {
        'textAlign': 'center', 'color': COLORS['text_secondary'],
        'fontSize': '0.85rem', 'marginBottom': '4px',
    }
    if tooltip:
        label_style['cursor'] = 'help'
        label_style['borderBottom'] = f"1px dashed {COLORS['text_secondary']}"
        label_style['display'] = 'inline-block'
    label_el = html.Div(
        html.Span(label, title=tooltip, style=label_style) if tooltip else label,
        style={'textAlign': 'center', 'marginBottom': '4px'} if tooltip else label_style,
    )

    def _val_block(main, h1, h2, color, weight, align):
        children = [html.Span(main, style={'fontWeight': weight, 'fontSize': '1.0rem', 'color': color})]
        if h1 is not None and h2 is not None:
            children.append(html.Span(
                f" ({h1}/{h2})",
                style={'fontSize': '0.7rem', 'color': COLORS['text_secondary'], 'fontWeight': 'normal', 'opacity': '0.8'},
            ))
        return html.Div(children, style={
            'minWidth': '110px', 'textAlign': align,
            'paddingRight': '10px' if align == 'right' else '0',
            'paddingLeft': '10px' if align == 'left' else '0',
            'whiteSpace': 'nowrap', 'flexShrink': '0',
        })

    return html.Div([
        label_el,
        html.Div([
            _val_block(h_display, hh1, hh2, HOME_COLOR, h_weight, 'right'),
            html.Div([
                html.Div([
                    html.Div(style={
                        'width': f'{home_pct}%', 'height': '100%', 'backgroundColor': HOME_COLOR,
                        'borderRadius': '7px 0 0 7px', 'marginLeft': 'auto', 'transition': 'width 0.4s ease',
                    })
                ], style={**bar_track, 'width': '50%', 'justifyContent': 'flex-end', 'borderRadius': '7px 0 0 7px'}),
                html.Div(style={'width': '2px', 'height': '14px', 'backgroundColor': COLORS['text_secondary'], 'flexShrink': '0'}),
                html.Div([
                    html.Div(style={
                        'width': f'{away_pct}%', 'height': '100%', 'backgroundColor': AWAY_COLOR,
                        'borderRadius': '0 7px 7px 0', 'transition': 'width 0.4s ease',
                    })
                ], style={**bar_track, 'width': '50%', 'borderRadius': '0 7px 7px 0'}),
            ], style={'display': 'flex', 'alignItems': 'center', 'flex': '1'}),
            _val_block(a_display, ah1, ah2, AWAY_COLOR, a_weight, 'left'),
        ], style={'display': 'flex', 'alignItems': 'center'}),
    ], style={'marginBottom': '14px'})


def _build_stat_bars(home_kpis: dict, away_kpis: dict,
                     home_h1=None, away_h1=None, home_h2=None, away_h2=None) -> html.Div:
    h1h = home_h1 or {}; a1h = away_h1 or {}; h2h = home_h2 or {}; a2h = away_h2 or {}
    has_halves = bool(h1h or h2h)
    legend = html.Div([
        html.Span("Full  ", style={'color': COLORS['text_secondary'], 'fontSize': '0.75rem'}),
        html.Span("(1st Half / 2nd Half)", style={'color': COLORS['text_secondary'], 'fontSize': '0.72rem', 'opacity': '0.65'}),
    ], style={
        'textAlign': 'center', 'marginBottom': '16px', 'paddingBottom': '12px',
        'borderBottom': f"1px solid {COLORS['dark_border']}",
    }) if has_halves else html.Div()
    return html.Div([
        legend,
        _tv_stat_bar('Possession', home_kpis.get('possession', 50), away_kpis.get('possession', 50),
                     h1h.get('possession'), a1h.get('possession'), h2h.get('possession'), a2h.get('possession'),
                     '%', is_percentage=True),
        _tv_stat_bar('Shots', home_kpis.get('shots', 0), away_kpis.get('shots', 0),
                     h1h.get('shots'), a1h.get('shots'), h2h.get('shots'), a2h.get('shots')),
        _tv_stat_bar('Shots on Target', home_kpis.get('shots_on_target', 0), away_kpis.get('shots_on_target', 0),
                     h1h.get('shots_on_target'), a1h.get('shots_on_target'), h2h.get('shots_on_target'), a2h.get('shots_on_target')),
        _tv_stat_bar('Shots from Box', home_kpis.get('box_shots', 0), away_kpis.get('box_shots', 0),
                     h1h.get('box_shots'), a1h.get('box_shots'), h2h.get('box_shots'), a2h.get('box_shots')),
        _tv_stat_bar('xG', home_kpis.get('xg', 0.0), away_kpis.get('xg', 0.0),
                     h1h.get('xg'), a1h.get('xg'), h2h.get('xg'), a2h.get('xg'), decimals=2,
                     tooltip='Expected goals (xG) — how many goals a team should have scored on average based on the number and quality of shots taken.'),
        _tv_stat_bar('Assists', home_kpis.get('assists', 0), away_kpis.get('assists', 0),
                     h1h.get('assists'), a1h.get('assists'), h2h.get('assists'), a2h.get('assists')),
        _tv_stat_bar('Blocked Shots', home_kpis.get('blocked_shots', 0), away_kpis.get('blocked_shots', 0),
                     h1h.get('blocked_shots'), a1h.get('blocked_shots'), h2h.get('blocked_shots'), a2h.get('blocked_shots')),
        _tv_stat_bar('Passes', home_kpis.get('passes', 0), away_kpis.get('passes', 0),
                     h1h.get('passes'), a1h.get('passes'), h2h.get('passes'), a2h.get('passes')),
        _tv_stat_bar('Pass Accuracy', home_kpis.get('pass_accuracy', 0), away_kpis.get('pass_accuracy', 0),
                     h1h.get('pass_accuracy'), a1h.get('pass_accuracy'), h2h.get('pass_accuracy'), a2h.get('pass_accuracy'),
                     '%', is_percentage=True),
        _tv_stat_bar('Fouls Committed', home_kpis.get('fouls', 0), away_kpis.get('fouls', 0),
                     h1h.get('fouls'), a1h.get('fouls'), h2h.get('fouls'), a2h.get('fouls')),
        _tv_stat_bar('Corners', home_kpis.get('corners', 0), away_kpis.get('corners', 0),
                     h1h.get('corners'), a1h.get('corners'), h2h.get('corners'), a2h.get('corners')),
        _tv_stat_bar('Offsides', home_kpis.get('offsides', 0), away_kpis.get('offsides', 0),
                     h1h.get('offsides'), a1h.get('offsides'), h2h.get('offsides'), a2h.get('offsides')),
        _tv_stat_bar('Interceptions', home_kpis.get('interceptions', 0), away_kpis.get('interceptions', 0),
                     h1h.get('interceptions'), a1h.get('interceptions'), h2h.get('interceptions'), a2h.get('interceptions')),
        _tv_stat_bar('Yellow Cards', home_kpis.get('yellow_cards', 0), away_kpis.get('yellow_cards', 0),
                     h1h.get('yellow_cards'), a1h.get('yellow_cards'), h2h.get('yellow_cards'), a2h.get('yellow_cards')),
        _tv_stat_bar('Red Cards', home_kpis.get('red_cards', 0), away_kpis.get('red_cards', 0),
                     h1h.get('red_cards'), a1h.get('red_cards'), h2h.get('red_cards'), a2h.get('red_cards')),
    ], style={
        'padding': '24px', 'backgroundColor': COLORS['dark_secondary'],
        'borderRadius': '8px', 'border': f"1px solid {COLORS['dark_border']}",
        'maxWidth': '700px', 'margin': '0 auto',
    })


def build_overview_tab(events):
    meta      = get_match_metadata(events)
    home_kpis = compute_team_kpis(events, 'home')
    away_kpis = compute_team_kpis(events, 'away')
    home_team = meta.get('home_team', 'Home')
    away_team = meta.get('away_team', 'Away')
    match_id  = str(meta.get('match_id', ''))
    lineup_df = get_match_lineup(match_id) if match_id else pd.DataFrame()
    subs      = get_substitutions(events)
    if 'period_id' in events.columns:
        h1_evts = events[events['period_id'] == 1]
        h2_evts = events[events['period_id'] == 2]
        home_h1_kpis = compute_team_kpis(h1_evts, 'home')
        away_h1_kpis = compute_team_kpis(h1_evts, 'away')
        home_h2_kpis = compute_team_kpis(h2_evts, 'home')
        away_h2_kpis = compute_team_kpis(h2_evts, 'away')
    else:
        home_h1_kpis = away_h1_kpis = home_h2_kpis = away_h2_kpis = {}
    center_col = html.Div(
        _build_stat_bars(home_kpis, away_kpis, home_h1_kpis, away_h1_kpis, home_h2_kpis, away_h2_kpis)
    )
    if not lineup_df.empty:
        home_df    = lineup_df[lineup_df['team_position'] == 'home']
        away_df    = lineup_df[lineup_df['team_position'] == 'away']
        home_start = home_df[home_df['role'] == 'Start'].copy()
        away_start = away_df[away_df['role'] == 'Start'].copy()
        home_fmt   = home_start['formation'].iloc[0] if not home_start.empty else ''
        away_fmt   = away_start['formation'].iloc[0] if not away_start.empty else ''
        home_img = away_img = None
        try:
            home_img = _generate_team_lineup_image(home_start, home_fmt, HOME_COLOR)
        except Exception:
            pass
        try:
            away_img = _generate_team_lineup_image(away_start, away_fmt, AWAY_COLOR)
        except Exception:
            pass

        def _xi_img_card(img_b64):
            if not img_b64:
                return html.Div()
            return html.Div(
                html.Img(src=f'data:image/png;base64,{img_b64}',
                         style={'width': '100%', 'display': 'block', 'borderRadius': '6px'}),
                style={'backgroundColor': COLORS['dark_secondary'], 'borderRadius': '8px',
                       'border': f"1px solid {COLORS['dark_border']}", 'padding': '6px'},
            )

        home_lineup = _xi_img_card(home_img)
        away_lineup = _xi_img_card(away_img)
        home_subs   = _build_lineup_html_panel(subs.get('home', []), HOME_COLOR, align='left')
        away_subs   = _build_lineup_html_panel(subs.get('away', []), AWAY_COLOR, align='right')
    else:
        lineups = get_starting_lineups(events)
        home_lineup = _build_lineup_card(home_team, lineups.get('home', {}), HOME_COLOR, align='start')
        away_lineup = _build_lineup_card(away_team, lineups.get('away', {}), AWAY_COLOR, align='end')
        home_subs   = _build_subs_section(home_team, subs.get('home', []), HOME_COLOR)
        away_subs   = _build_subs_section(away_team, subs.get('away', []), AWAY_COLOR)
    # Substitutions stacked under the lineup (2-column subs panel to cut rows).
    # Lineup pitch spans the full column (bigger).
    home_side = html.Div([home_lineup, html.Div(home_subs, style={'marginTop': '10px'})])
    away_side = html.Div([away_lineup, html.Div(away_subs, style={'marginTop': '10px'})])
    return html.Div([
        section_header('Line-Ups & Match Stats'),
        dbc.Row([
            dbc.Col(home_side,  lg=4, md=6, xs=12, className='mb-3'),
            dbc.Col(center_col, lg=4, md=12, xs=12, className='mb-3'),
            dbc.Col(away_side,  lg=4, md=6, xs=12, className='mb-3'),
        ], align='start'),
    ])


def register_overview_callbacks(app) -> None:
    pass

# ============================================================================
# ===== attacking_output.py =====
# ============================================================================
import math
import pandas as pd
import plotly.graph_objects as go
from dash import html, dcc
import dash_bootstrap_components as dbc
from utils.config import COLORS
from utils.data_utils import exclude_own_goals
from utils.xg_utils import add_xg_column
from utils.match_data_adapter import get_match_metadata, compute_team_kpis
from utils.data_utils import get_match_results, get_match_events
from page_utils.visualizations import HOME_COLOR, AWAY_COLOR, GOLD, CHART_CONFIG, layout_config, add_pitch_background, add_vertical_half_pitch_background, PITCH_AXIS_FULL, VPITCH_AXIS_HALF, render_xt_heatmap_img
from page_utils.event_filters import SHOT_TYPES
from page_utils.pitch_zones import BOX_X_MIN, BOX_Y_MIN, BOX_Y_MAX

_AO_OUTCOME_COLOR = {
    'Goal':         '#51cf66',
    'Saved Shot':   '#339af0',
    'Miss':         '#ff6b6b',
    'Post':         '#ffd43b',
    'Blocked Shot': '#cc5de8',
}
_AO_OUTCOME_SYMBOL = {
    'Goal':         'star',
    'Saved Shot':   'circle',
    'Miss':         'x',
    'Post':         'diamond',
    'Blocked Shot': 'square',
}

_SI = ('N/A', '', 'nan', None)


def _count_from_box(shots: pd.DataFrame) -> int:
    if not {'x', 'y'}.issubset(shots.columns) or shots.empty:
        return 0
    x = pd.to_numeric(shots['x'], errors='coerce')
    y = pd.to_numeric(shots['y'], errors='coerce')
    return int(((x >= BOX_X_MIN) & (y >= BOX_Y_MIN) & (y <= BOX_Y_MAX)).sum())


def _get_shot_type(row) -> str:
    def _present(col):
        return str(row.get(col, 'N/A')) not in _SI
    if _present('Penalty'):        return 'Penalty'
    if _present('Diving Header'):  return 'Diving Header'
    if _present('Head'):           return 'Header'
    if _present('Overhead'):       return 'Overhead / Bicycle'
    if _present('Volley'):         return 'Volley'
    if _present('Half Volley'):    return 'Half Volley'
    if _present('Left footed'):    return 'Left foot'
    if _present('Right footed'):   return 'Right foot'
    return 'Shot'


def _ao_compute(events: pd.DataFrame) -> dict:
    home_team = events['home_team'].iloc[0]
    away_team = events['away_team'].iloc[0]
    out = {}

    for pos, team in (('home', home_team), ('away', away_team)):
        te = events[events['team_position'] == pos]
        sorted_te = te.sort_values(['period_id', 'time_min']).reset_index(drop=True)
        prev_acts = [''] * len(sorted_te)
        for i in range(1, len(sorted_te)):
            pr        = sorted_te.iloc[i - 1]
            prev_type = str(pr.get('event_type', '') or '')
            prev_plr  = str(pr.get('player_name', '') or '').strip()
            if prev_type == 'Pass' and prev_plr:
                prev_acts[i] = f'Pass ({prev_plr})'
            elif prev_type in ('Take On', 'Carry') and prev_plr:
                prev_acts[i] = f'{prev_type} ({prev_plr})'
            else:
                prev_acts[i] = prev_type
        sorted_te['prev_action'] = prev_acts

        shots = exclude_own_goals(sorted_te[sorted_te['event_type'].isin(SHOT_TYPES)].copy())
        shots = add_xg_column(shots)
        goals = shots[shots['event_type'] == 'Goal']
        shots['shot_type'] = shots.apply(_get_shot_type, axis=1)

        if 'Assist' in sorted_te.columns:
            key_passes = sorted_te[
                (sorted_te['event_type'] == 'Pass') &
                pd.to_numeric(sorted_te['Assist'], errors='coerce').isin([13, 14, 15, 16])
            ].copy()
        else:
            key_passes = pd.DataFrame()

        carry_lines: list = []
        if not key_passes.empty:
            _carry_types = {'Take On', 'Carry', 'Ball touch'}
            for ki in key_passes.index:
                kp   = sorted_te.iloc[ki]
                pe_x = pd.to_numeric(kp.get('Pass End X'), errors='coerce')
                pe_y = pd.to_numeric(kp.get('Pass End Y'), errors='coerce')
                if pd.isna(pe_x) or pd.isna(pe_y):
                    continue
                shot_pos, shot_row = None, None
                for j in range(ki + 1, min(ki + 8, len(sorted_te))):
                    if sorted_te.iloc[j]['event_type'] in SHOT_TYPES:
                        shot_pos, shot_row = j, sorted_te.iloc[j]
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
                mid_pts: list = []
                for k in range(ki + 1, shot_pos):
                    ev = sorted_te.iloc[k]
                    if ev['event_type'] in _carry_types and ev.get('player_name') == shooter:
                        mx = pd.to_numeric(ev.get('x'), errors='coerce')
                        my = pd.to_numeric(ev.get('y'), errors='coerce')
                        if pd.notna(mx) and pd.notna(my):
                            mid_pts.append((float(mx), float(my)))
                pts = [(float(pe_x), float(pe_y))] + mid_pts + [(float(sx), float(sy))]
                carry_lines.append({'points': pts, 'is_goal': shot_row['event_type'] == 'Goal'})

        shooter_counts = shots['player_name'].dropna().value_counts().head(5).reset_index()
        shooter_counts.columns = ['Player', 'S']
        goal_counts = goals['player_name'].dropna().value_counts()
        shooter_counts['G'] = (
            shooter_counts['Player'].map(goal_counts).fillna(0).astype(int)
        )
        if 'xg' in shots.columns:
            xg_per_player = shots.groupby('player_name')['xg'].sum().round(2)
            shooter_counts['xG'] = (
                shooter_counts['Player'].map(xg_per_player).fillna(0.0).round(2)
            )

        out[pos] = {
            'team':         team,
            'shots':        shots,
            'key_passes':   key_passes,
            'goals':        len(goals),
            'total_shots':  len(shots),
            'total_xg':     round(shots['xg'].sum(), 2) if 'xg' in shots.columns else None,
            'on_target':    len(te[te['event_type'] == 'Saved Shot']) + len(goals),
            'from_box':     _count_from_box(shots),
            'top_shooters': shooter_counts,
            'carry_lines':  carry_lines,
        }
    return out


def _ao_shot_map_fig(shots: pd.DataFrame, key_passes: pd.DataFrame,
                  team_color: str, team_name: str,
                  carry_lines: list | None = None) -> go.Figure:
    fig = go.Figure()
    add_vertical_half_pitch_background(fig)

    _common = dict(
        **VPITCH_AXIS_HALF,
        height=500, margin=dict(l=10, r=10, t=44, b=20),
        title=dict(text=f'<b>{team_name}</b>', x=0.5,
                   font=dict(color=team_color, size=13)),
        annotations=[dict(x=0.98, y=0.97, xref='paper', yref='paper',
                          text='▲ Attacking Direction', showarrow=False,
                          font=dict(color='black', size=16, family='Arial'),
                          xanchor='right', yanchor='top',
                          bgcolor='rgba(255,255,255,0.7)', borderpad=3)],
    )
    if shots.empty or 'x' not in shots.columns or 'y' not in shots.columns:
        fig.update_layout(**layout_config(**_common))
        return fig

    if not key_passes.empty and 'Pass End X' in key_passes.columns:
        kp = key_passes.copy()
        kp['Pass End X'] = pd.to_numeric(kp['Pass End X'], errors='coerce')
        kp['Pass End Y'] = pd.to_numeric(kp['Pass End Y'], errors='coerce')
        kp['x']         = pd.to_numeric(kp['x'],           errors='coerce')
        kp['y']         = pd.to_numeric(kp['y'],           errors='coerce')
        kp = kp.dropna(subset=['x', 'y', 'Pass End X', 'Pass End Y'])
        if not kp.empty:
            is_goal_assist = (
                pd.to_numeric(kp['Assist'], errors='coerce') == 16
                if 'Assist' in kp.columns
                else pd.Series(False, index=kp.index)
            )
            for is_goal, grp in kp.groupby(is_goal_assist):
                clr     = GOLD if is_goal else 'rgba(220,220,220,0.55)'
                width   = 3.0  if is_goal else 2.0
                opacity = 0.95 if is_goal else 0.65
                label   = 'Goal Assist' if is_goal else 'Key Pass'
                xs_l, ys_l = [], []
                for _, row in grp.iterrows():
                    xs_l.extend([100 - float(row['y']), 100 - float(row['Pass End Y']), None])
                    ys_l.extend([float(row['x']),       float(row['Pass End X']),        None])
                fig.add_trace(go.Scatter(
                    x=xs_l, y=ys_l, mode='lines',
                    line=dict(color=clr, width=width),
                    opacity=opacity, showlegend=False, hoverinfo='skip',
                ))
                fig.add_trace(go.Scatter(
                    x=(100 - grp['Pass End Y']).tolist(),
                    y=grp['Pass End X'].tolist(),
                    mode='markers', name=label,
                    marker=dict(color=clr, size=9 if is_goal else 7,
                                symbol='circle', opacity=opacity,
                                line=dict(color='white', width=1.5 if is_goal else 1)),
                    showlegend=True, hoverinfo='skip',
                ))

    if carry_lines:
        _legend_added: dict = {'goal': False, 'other': False}
        for cl in carry_lines:
            is_goal = cl['is_goal']
            clr     = GOLD if is_goal else 'rgba(220,220,220,0.55)'
            opacity = 0.85 if is_goal else 0.55
            pts     = cl['points']
            fig_xs  = [100 - p[1] for p in pts]
            fig_ys  = [p[0]       for p in pts]
            key_    = 'goal' if is_goal else 'other'
            show_lg = not _legend_added[key_]
            fig.add_trace(go.Scatter(
                x=fig_xs, y=fig_ys, mode='lines',
                line=dict(color=clr, width=2, dash='dot'),
                opacity=opacity,
                name=('Carry (goal)' if is_goal else 'Carry') if show_lg else '',
                showlegend=show_lg, hoverinfo='skip',
            ))
            _legend_added[key_] = True

    for outcome, group in shots.groupby('event_type'):
        valid    = group[group['x'].notna() & group['y'].notna()].copy()
        fig_x    = (100 - valid['y']).tolist()
        fig_y    = valid['x'].tolist()
        if not fig_x:
            continue
        player_names = valid['player_name'].fillna('Unknown').tolist()
        times        = valid['time_min'].fillna(0).astype(int).tolist()
        prev_acts    = (valid['prev_action'].fillna('—').tolist()
                        if 'prev_action' in valid.columns else ['—'] * len(valid))
        shot_types   = (valid['shot_type'].fillna('Shot').tolist()
                        if 'shot_type' in valid.columns else ['Shot'] * len(valid))
        og_flags     = (
            [' (own goal)' if v == 'Si' else '' for v in valid['own goal'].fillna('')]
            if 'own goal' in valid.columns else [''] * len(valid)
        )
        xg_vals = (valid['xg'].fillna(0).tolist() if 'xg' in valid.columns else [0] * len(valid))
        if outcome == 'Goal':
            sizes = [16] * len(valid)
        else:
            sizes = [max(8, min(18, int(v * 60 + 8))) for v in xg_vals]
        fig.add_trace(go.Scatter(
            x=fig_x, y=fig_y, mode='markers', name=outcome,
            marker=dict(color=_AO_OUTCOME_COLOR.get(outcome, team_color),
                        symbol=_AO_OUTCOME_SYMBOL.get(outcome, 'circle'),
                        size=sizes, opacity=0.88, line=dict(color='white', width=1)),
            customdata=[[p, t, a, st, og, xg] for p, t, a, st, og, xg
                        in zip(player_names, times, prev_acts, shot_types, og_flags, xg_vals)],
            hovertemplate=(
                '<b>%{customdata[0]}%{customdata[4]}</b><br>'
                "%{customdata[1]}' | %{customdata[3]}<br>"
                'xG: %{customdata[5]:.2f}<br>'
                'Preceding: %{customdata[2]}<extra></extra>'
            ),
        ))

    fig.update_layout(**layout_config(
        **_common,
        hoverlabel=dict(bgcolor='#1A1D2E', font_color='white', font_size=12),
        legend=dict(
            x=0.01, y=0.01, xanchor='left', yanchor='bottom', orientation='v',
            font=dict(color=COLORS['text_primary'], size=10),
            bgcolor='rgba(26,29,46,0.80)',
            bordercolor=COLORS.get('dark_border', 'rgba(255,255,255,0.15)'),
            borderwidth=1,
        ),
    ))
    return fig


def _player_table(df: pd.DataFrame, color: str) -> html.Div:
    if df.empty:
        return html.Div("No data", style={'color': COLORS['text_secondary'], 'fontSize': '0.8rem'})
    header_cells = [
        html.Th(col, style={
            'color': COLORS['text_secondary'], 'fontSize': '0.7rem',
            'fontWeight': '600', 'padding': '6px 10px',
            'borderBottom': f'1px solid {COLORS["dark_border"]}',
            'textTransform': 'none' if col.startswith('x') else 'uppercase',
            'letterSpacing': '0' if col.startswith('x') else '0.04em',
        }) for col in df.columns
    ]
    rows = []
    for i, (_, row) in enumerate(df.iterrows()):
        bg = COLORS['dark_tertiary'] if i % 2 == 0 else 'transparent'
        cells = [
            html.Td(str(val), style={
                'color': color if j == 0 else COLORS['text_primary'],
                'fontSize': '0.82rem', 'padding': '5px 10px',
                'fontWeight': '600' if j == 0 else 'normal',
            }) for j, val in enumerate(row)
        ]
        rows.append(html.Tr(cells, style={'backgroundColor': bg}))
    return html.Table([html.Thead(html.Tr(header_cells)), html.Tbody(rows)],
                      style={'width': '100%', 'borderCollapse': 'collapse'})


def build_attacking_output_tab(events: pd.DataFrame, **_) -> html.Div:
    if events.empty:
        return html.P("No event data.", style={"color": COLORS["text_secondary"]})

    _shot_mask = events['event_type'].isin(SHOT_TYPES)
    if 'xg' not in events.columns and _shot_mask.any():
        events = events.copy()
        _shots_enriched = add_xg_column(events.loc[_shot_mask].copy())
        if 'xg' in _shots_enriched.columns:
            events.loc[_shot_mask, 'xg'] = _shots_enriched['xg'].values

    d = _ao_compute(events)
    hs, as_ = d['home'], d['away']

    def _shooter_card(data, color):
        return html.Div([
            html.Div('Top Performers', style={
                'color': color, 'fontWeight': '700', 'fontSize': '0.78rem',
                'textTransform': 'uppercase', 'letterSpacing': '0.04em',
                'marginBottom': '8px',
            }),
            _player_table(data['top_shooters'], color),
        ])

    def _team_block(data, color):
        return dbc.Col(dbc.Row([
            dbc.Col(dcc.Graph(
                figure=_ao_shot_map_fig(data['shots'], data.get('key_passes', pd.DataFrame()),
                                     color, data['team'], data.get('carry_lines', [])),
                config=CHART_CONFIG), md=9),
            dbc.Col(_shooter_card(data, color), md=3,
                    style={'overflowY': 'auto', 'maxHeight': '500px'}),
        ], className='g-2', align='start'), md=6, className='mb-3')

    shot_map_section = html.Div([
        section_header('Shot Map'),
        build_legend_box([
            ('★', 'Goal',    '#51cf66'),
            ('●', 'Saved',   '#339af0'),
            ('✕', 'Miss',    '#ff6b6b'),
            ('◆', 'Post',    '#ffd43b'),
            ('■', 'Blocked', '#cc5de8'),
        ]),
        dbc.Row([
            _team_block(hs, HOME_COLOR),
            _team_block(as_, AWAY_COLOR),
        ], className='g-3'),
    ], style={'marginBottom': '36px'})

    return html.Div([shot_map_section], style={'marginTop': '16px'})


_ATK_RADAR_KEYS = [
    ('Goals',            'goals'),
    ('Shots',            'shots'),
    ('Shots on Target',  'shots_on_target'),
    ('xG',               'xg'),
    ('Assists',          'assists'),
    ('Shots from Box',   'box_shots'),
    ('Crosses',          'crosses'),
    ('Passes in Zone 3', 'final_third_passes'),
]

_atk_league_avg_cache: dict = {}


def _compute_atk_league_avg(events: pd.DataFrame) -> dict:
    global _atk_league_avg_cache

    competition = ''
    if 'competition' in events.columns and not events.empty:
        competition = str(events['competition'].iloc[0])
    if not competition:
        try:
            competition = get_match_metadata(events).get('competition', '')
        except Exception:
            pass
    if not competition:
        return {}
    if competition in _atk_league_avg_cache:
        return _atk_league_avg_cache[competition]

    try:
        keys = [k for _, k in _ATK_RADAR_KEYS]
        accumulated: dict = {k: [] for k in keys}
        for r in get_match_results():
            if r.get('competition') != competition:
                continue
            try:
                ev = get_match_events(r['match_id'])
                if ev.empty:
                    continue
                for pos in ('home', 'away'):
                    s = compute_team_kpis(ev, pos)
                    for k in keys:
                        v = s.get(k, 0)
                        if isinstance(v, (int, float)) and not math.isnan(float(v)):
                            accumulated[k].append(float(v))
            except Exception:
                continue
        avg = {k: round(sum(v) / len(v), 2) if v else 0.0 for k, v in accumulated.items()}
        _atk_league_avg_cache[competition] = avg
        return avg
    except Exception:
        return {}


def _hex_to_rgba_atk(hex_color: str, alpha: float = 0.12) -> str:
    h = hex_color.lstrip('#')
    if len(h) == 3:
        h = ''.join(c * 2 for c in h)
    try:
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        return f'rgba({r},{g},{b},{alpha})'
    except (ValueError, IndexError):
        return f'rgba(128,128,128,{alpha})'


def _build_atk_radar_fig(home_stats, away_stats, league_avg, home_team, away_team):
    labels = [lbl for lbl, _ in _ATK_RADAR_KEYS]
    keys   = [k   for _,   k in _ATK_RADAR_KEYS]

    def _raw(stats):
        return [float(stats.get(k, 0) or 0) for k in keys]

    hv = _raw(home_stats); av = _raw(away_stats)
    lv = _raw(league_avg) if league_avg else None
    norm_h, norm_a, norm_l = [], [], []
    for i in range(len(keys)):
        candidates = [hv[i], av[i]] + ([lv[i]] if lv else [])
        max_v = max(candidates) if max(candidates) > 0 else 1.0
        norm_h.append(round(hv[i] / max_v * 100, 1))
        norm_a.append(round(av[i] / max_v * 100, 1))
        if lv:
            norm_l.append(round(lv[i] / max_v * 100, 1))

    labels_c = labels + [labels[0]]
    norm_h_c = norm_h + [norm_h[0]]; norm_a_c = norm_a + [norm_a[0]]
    hv_c = hv + [hv[0]]; av_c = av + [av[0]]
    if lv:
        norm_l_c = norm_l + [norm_l[0]]; lv_c = lv + [lv[0]]

    def _fmt(v):
        return f'{v:.2f}' if isinstance(v, float) and v != int(v) else str(int(v))

    fig = go.Figure()
    if lv:
        fig.add_trace(go.Scatterpolar(
            r=norm_l_c, theta=labels_c, mode='lines', name='League Avg',
            line=dict(color=GOLD, width=1.5, dash='dot'), opacity=0.85,
            customdata=[[_fmt(lv_c[i])] for i in range(len(labels_c))],
            hovertemplate='<b>League Avg</b><br>%{theta}: %{customdata[0]}<extra></extra>',
        ))
    fig.add_trace(go.Scatterpolar(
        r=norm_a_c, theta=labels_c, mode='lines+markers+text', name=away_team,
        fill='toself', fillcolor=_hex_to_rgba_atk(AWAY_COLOR, 0.12),
        line=dict(color=AWAY_COLOR, width=2), marker=dict(size=5, color=AWAY_COLOR),
        text=[_fmt(av_c[i]) for i in range(len(labels_c))],
        textposition='bottom center', textfont=dict(size=10, color='#FFFFFF'),
        customdata=[[_fmt(av_c[i])] for i in range(len(labels_c))],
        hovertemplate=f'<b>{away_team}</b><br>%{{theta}}: %{{customdata[0]}}<extra></extra>',
    ))
    fig.add_trace(go.Scatterpolar(
        r=norm_h_c, theta=labels_c, mode='lines+markers+text', name=home_team,
        fill='toself', fillcolor=_hex_to_rgba_atk(HOME_COLOR, 0.12),
        line=dict(color=HOME_COLOR, width=2), marker=dict(size=5, color=HOME_COLOR),
        text=[_fmt(hv_c[i]) for i in range(len(labels_c))],
        textposition='top center', textfont=dict(size=10, color='#FFFFFF'),
        customdata=[[_fmt(hv_c[i])] for i in range(len(labels_c))],
        hovertemplate=f'<b>{home_team}</b><br>%{{theta}}: %{{customdata[0]}}<extra></extra>',
    ))
    fig.update_layout(
        polar=dict(
            bgcolor='rgba(26,29,46,0.6)',
            radialaxis=dict(visible=True, range=[0, 105], showticklabels=False,
                            gridcolor='rgba(255,255,255,0.08)', linecolor='rgba(255,255,255,0.08)'),
            angularaxis=dict(tickfont=dict(size=10, color=COLORS['text_primary']),
                             gridcolor='rgba(255,255,255,0.08)', linecolor='rgba(255,255,255,0.08)'),
        ),
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', showlegend=True,
        legend=dict(x=0.5, y=-0.06, xanchor='center', yanchor='top', orientation='h',
                    font=dict(color=COLORS['text_primary'], size=11), bgcolor='rgba(0,0,0,0)'),
        height=540, margin=dict(l=80, r=80, t=30, b=80),
        hoverlabel=dict(bgcolor='#1A1D2E', font_color='white', font_size=12),
    )
    return fig


def build_attack_radar(events: pd.DataFrame):
    if events.empty:
        return None
    home_team  = str(events['home_team'].iloc[0]) if 'home_team' in events.columns else 'Home'
    away_team  = str(events['away_team'].iloc[0]) if 'away_team' in events.columns else 'Away'
    home_stats = compute_team_kpis(events, 'home')
    away_stats = compute_team_kpis(events, 'away')
    league_avg = _compute_atk_league_avg(events)
    return _build_atk_radar_fig(home_stats, away_stats, league_avg, home_team, away_team)


def register_attacking_output_callbacks(app) -> None:
    pass

# ============================================================================
# ===== build_up_passing.py =====
# ============================================================================
import io, base64
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import matplotlib.pyplot as plt
from sklearn.preprocessing import MinMaxScaler
from dash import html, dcc
import dash_bootstrap_components as dbc
from utils.config import COLORS
from utils.data_utils import get_match_events, exclude_own_goals
from utils.xt_utils import add_xt_column
from page_utils.visualizations import HOME_COLOR, AWAY_COLOR, GOLD, CHART_CONFIG, layout_config, add_pitch_background, PITCH_AXIS_FULL, render_xt_heatmap_img, render_lsc_heatmap_img
from page_utils.event_filters import SHOT_TYPES

_ZONE_RANGES  = {'Def. Third': (0, 33.33), 'Mid Third': (33.33, 66.67), 'Fin. Third': (66.67, 100)}
_FLANK_RANGES = {'Left': (0, 33.33), 'Centre': (33.33, 66.67), 'Right': (66.67, 100)}


def _apply_filters(events: pd.DataFrame, half: str, zones: list, flanks: list) -> pd.DataFrame:
    ev = events.copy()
    for col in ('x', 'y', 'Pass End X', 'Pass End Y'):
        if col in ev.columns:
            ev[col] = pd.to_numeric(ev[col], errors='coerce')
    if half == '1':
        ev = ev[ev['period_id'] == 1]
    elif half == '2':
        ev = ev[ev['period_id'] == 2]
    if zones and set(zones) != set(_ZONE_RANGES):
        masks = []
        for z in zones:
            lo, hi = _ZONE_RANGES[z]
            masks.append((ev['x'] >= lo) & (ev['x'] <= hi))
        ev = ev[pd.concat(masks, axis=1).any(axis=1)]
    if flanks and set(flanks) != set(_FLANK_RANGES):
        masks = []
        for f in flanks:
            lo, hi = _FLANK_RANGES[f]
            masks.append((ev['y'] >= lo) & (ev['y'] <= hi))
        ev = ev[pd.concat(masks, axis=1).any(axis=1)]
    return ev


def _count_si(df: pd.DataFrame, col: str) -> int:
    if col not in df.columns:
        return 0
    return int((df[col] == 'Si').sum())


def _build_network(te: pd.DataFrame):
    cols = ['player_name', 'event_type', 'outcome', 'x', 'y', 'period_id', 'time_min', 'time_sec']
    ev = te[[c for c in cols if c in te.columns]].copy()
    ev = ev.dropna(subset=['player_name', 'x', 'y'])
    ev = ev.sort_values(['period_id', 'time_min', 'time_sec']).reset_index(drop=True)
    edges: dict = {}
    for i in range(len(ev) - 1):
        row = ev.iloc[i]
        nxt = ev.iloc[i + 1]
        if (row['event_type'] == 'Pass' and row.get('outcome') == 1
                and pd.notna(nxt.get('player_name'))):
            a, b = str(row['player_name']), str(nxt['player_name'])
            if a != b:
                edges[(a, b)] = edges.get((a, b), 0) + 1
    edges = {k: v for k, v in edges.items() if v >= 2}
    pass_ev = ev[ev['event_type'] == 'Pass']
    if pass_ev.empty:
        return pd.DataFrame(), {}
    nodes = (
        pass_ev.groupby('player_name')
        .agg(x=('x', 'mean'), y=('y', 'mean'))
        .reset_index()
    )
    inv: dict = {}
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
    return nodes, edges


def _build_combos(te: pd.DataFrame) -> pd.DataFrame:
    ev = te[['player_name', 'event_type', 'outcome', 'period_id', 'time_min', 'time_sec']].copy()
    ev = ev.dropna(subset=['player_name'])
    ev = ev.sort_values(['period_id', 'time_min', 'time_sec']).reset_index(drop=True)
    combos: dict = {}; combos_h1: dict = {}; combos_h2: dict = {}
    for i in range(len(ev) - 1):
        row = ev.iloc[i]; nxt = ev.iloc[i + 1]
        if (row['event_type'] == 'Pass' and row.get('outcome') == 1 and pd.notna(nxt.get('player_name'))):
            a = str(row['player_name']).split()[-1]
            b = str(nxt['player_name']).split()[-1]
            if a != b:
                key = (a, b)
                combos[key] = combos.get(key, 0) + 1
                if row['period_id'] == 1:   combos_h1[key] = combos_h1.get(key, 0) + 1
                elif row['period_id'] == 2: combos_h2[key] = combos_h2.get(key, 0) + 1
    if not combos:
        return pd.DataFrame(columns=['Combo', 'Total', 'H1', 'H2'])
    rows = [{'Combo': f'{a} -> {b}', 'Total': cnt,
             'H1': combos_h1.get((a, b), 0), 'H2': combos_h2.get((a, b), 0)}
            for (a, b), cnt in combos.items()]
    return pd.DataFrame(rows).sort_values('Total', ascending=False).head(8).reset_index(drop=True)


def _build_3player_combos(te: pd.DataFrame) -> pd.DataFrame:
    ev = te[['player_name', 'event_type', 'outcome', 'period_id', 'time_min', 'time_sec']].copy()
    ev = ev.dropna(subset=['player_name'])
    ev = ev.sort_values(['period_id', 'time_min', 'time_sec']).reset_index(drop=True)
    combos: dict = {}; combos_h1: dict = {}; combos_h2: dict = {}
    for i in range(len(ev) - 2):
        r1 = ev.iloc[i]; r2 = ev.iloc[i + 1]; r3 = ev.iloc[i + 2]
        if (r1['event_type'] == 'Pass' and r1.get('outcome') == 1
                and r2['event_type'] == 'Pass' and r2.get('outcome') == 1
                and pd.notna(r2.get('player_name')) and pd.notna(r3.get('player_name'))):
            a = str(r1['player_name']).split()[-1]
            b = str(r2['player_name']).split()[-1]
            c = str(r3['player_name']).split()[-1]
            if a != b and b != c:
                key = (a, b, c)
                combos[key] = combos.get(key, 0) + 1
                if r1['period_id'] == 1:   combos_h1[key] = combos_h1.get(key, 0) + 1
                elif r1['period_id'] == 2: combos_h2[key] = combos_h2.get(key, 0) + 1
    if not combos:
        return pd.DataFrame(columns=['Combo', 'Total', 'H1', 'H2'])
    rows = [{'Combo': f'{a} -> {b} -> {c}', 'Total': cnt,
             'H1': combos_h1.get((a, b, c), 0), 'H2': combos_h2.get((a, b, c), 0)}
            for (a, b, c), cnt in combos.items()]
    return pd.DataFrame(rows).sort_values('Total', ascending=False).head(8).reset_index(drop=True)


def _build_4player_combos(te: pd.DataFrame) -> pd.DataFrame:
    ev = te[['player_name', 'event_type', 'outcome', 'period_id', 'time_min', 'time_sec']].copy()
    ev = ev.dropna(subset=['player_name'])
    ev = ev.sort_values(['period_id', 'time_min', 'time_sec']).reset_index(drop=True)
    combos: dict = {}; combos_h1: dict = {}; combos_h2: dict = {}
    for i in range(len(ev) - 3):
        r1 = ev.iloc[i]; r2 = ev.iloc[i+1]; r3 = ev.iloc[i+2]; r4 = ev.iloc[i+3]
        if (r1['event_type'] == 'Pass' and r1.get('outcome') == 1
                and r2['event_type'] == 'Pass' and r2.get('outcome') == 1
                and r3['event_type'] == 'Pass' and r3.get('outcome') == 1
                and pd.notna(r2.get('player_name')) and pd.notna(r3.get('player_name'))
                and pd.notna(r4.get('player_name'))):
            a = str(r1['player_name']).split()[-1]; b = str(r2['player_name']).split()[-1]
            c = str(r3['player_name']).split()[-1]; d = str(r4['player_name']).split()[-1]
            if a != b and b != c and c != d:
                key = (a, b, c, d)
                combos[key] = combos.get(key, 0) + 1
                if r1['period_id'] == 1:   combos_h1[key] = combos_h1.get(key, 0) + 1
                elif r1['period_id'] == 2: combos_h2[key] = combos_h2.get(key, 0) + 1
    if not combos:
        return pd.DataFrame(columns=['Combo', 'Total', 'H1', 'H2'])
    rows = [{'Combo': f'{a} -> {b} -> {c} -> {d}', 'Total': cnt,
             'H1': combos_h1.get((a, b, c, d), 0), 'H2': combos_h2.get((a, b, c, d), 0)}
            for (a, b, c, d), cnt in combos.items()]
    return pd.DataFrame(rows).sort_values('Total', ascending=False).head(8).reset_index(drop=True)


_league_avg_cache: dict = {}

_RADAR_KEYS = [
    ('Total Passes',     'passes'),
    ('Pass Accuracy',    'pass_acc'),
    ('Field Tilt',       'field_tilt'),
    ('Avg Passes/Poss',  'avg_passes_per_poss'),
    ('Positional xT',    'total_xt'),
    ('Into Final Third', 'into_ft'),
    ('Long Balls',       'long_balls'),
    ('Through Balls',    'thru_balls'),
    ('Ball Carries',     'carries'),
    ('Dribble Attempts', 'dribbles'),
    ('Dribbles Won',     'drib_succ'),
    ('Dribble Success',  'drib_acc'),
]


def _compute_league_avg(events: pd.DataFrame) -> dict:
    from utils.data_utils import get_match_results
    global _league_avg_cache
    competition = ''
    if 'competition' in events.columns and not events.empty:
        competition = str(events['competition'].iloc[0])
    if not competition:
        try:
            from utils.match_data_adapter import get_match_metadata
            competition = get_match_metadata(events).get('competition', '')
        except Exception:
            pass
    if not competition:
        return {}
    if competition in _league_avg_cache:
        return _league_avg_cache[competition]
    try:
        keys = [k for _, k in _RADAR_KEYS]
        accumulated: dict = {k: [] for k in keys}
        for r in get_match_results():
            if r.get('competition') != competition:
                continue
            try:
                ev = get_match_events(r['match_id'])
                if ev.empty:
                    continue
                for pos in ('home', 'away'):
                    s = _bup_compute_half_stats(ev, pos)
                    for k in keys:
                        v = s.get(k, 0)
                        if isinstance(v, (int, float)) and not np.isnan(float(v)):
                            accumulated[k].append(float(v))
            except Exception:
                continue
        avg = {k: round(sum(v) / len(v), 2) if v else 0.0 for k, v in accumulated.items()}
        _league_avg_cache[competition] = avg
        return avg
    except Exception:
        return {}


def _build_entries(te: pd.DataFrame, zone: str = 'final_third') -> pd.DataFrame:
    te_full = te.sort_values(['period_id', 'time_min', 'time_sec']).reset_index(drop=True)
    relevant_types = ['Pass', 'Take On', 'Ball touch']
    ev = (te_full[te_full['event_type'].isin(relevant_types)]
          .dropna(subset=['x', 'y'])
          .reset_index())
    entries = []
    for i in range(len(ev)):
        row = ev.iloc[i]
        etype = row['event_type']
        start_x = float(row['x'])
        if etype == 'Pass':
            if pd.notna(row.get('Pass End X')):
                end_x = float(row['Pass End X'])
                end_y = float(row['Pass End Y'])
            else:
                continue
        else:
            if i + 1 < len(ev):
                nxt = ev.iloc[i + 1]
                end_x = float(nxt['x'])
                end_y = float(nxt['y'])
            else:
                continue
        start_y = float(row['y'])
        dest_zone = None
        region = None
        if zone == 'final_third':
            if not (start_x < 66.67 and end_x >= 66.67):
                continue
            dest_zone = ('Left Band'   if end_y > 66.67
                         else 'Right Band' if end_y < 33.33
                         else 'Centre Band')
        elif zone == 'zone14':
            in_z14 = (66.67 <= end_x <= 83.33) and (37 <= end_y <= 63)
            in_lhs = (end_x > 66.67) and (63 < end_y <= 79)
            in_rhs = (end_x > 66.67) and (21 <= end_y < 37)
            if not (in_z14 or in_lhs or in_rhs):
                continue
            dest_zone = ('Left Band'   if end_y > 66.67
                         else 'Right Band' if end_y < 33.33
                         else 'Centre Band')
            region = 'Zone 14' if in_z14 else ('Left HS' if in_lhs else 'Right HS')
        label_map = {'Pass': 'Pass', 'Take On': 'Dribble', 'Ball touch': 'Carry'}
        outcome  = row.get('outcome', None)
        time_min = row.get('time_min', 0)
        time_sec = row.get('time_sec', 0)
        te_idx   = int(row['index'])
        next_5   = te_full.iloc[te_idx + 1 : te_idx + 6]
        led_to_shot = bool(next_5['event_type'].isin(SHOT_TYPES).any()) if not next_5.empty else False
        led_to_goal = bool((next_5['event_type'] == 'Goal').any())      if not next_5.empty else False
        receiver_name = ''
        if etype == 'Pass' and outcome == 1 and te_idx + 1 < len(te_full):
            nxt_full = te_full.iloc[te_idx + 1]
            if pd.notna(nxt_full.get('player_name')):
                receiver_name = str(nxt_full['player_name'])
        entries.append({
            'player_name':   row.get('player_name', ''),
            'event_label':   label_map.get(etype, etype),
            'x': start_x, 'y': start_y, 'end_x': end_x, 'end_y': end_y,
            'outcome': outcome, 'time_min': time_min, 'time_sec': time_sec,
            'period_id':     row.get('period_id', 0),
            'dest_zone':     dest_zone,
            'region':        region,
            'led_to_shot':   led_to_shot,
            'led_to_goal':   led_to_goal,
            'receiver_name': receiver_name,
        })
    if not entries:
        return pd.DataFrame(columns=[
            'player_name', 'event_label', 'x', 'y', 'end_x', 'end_y',
            'outcome', 'time_min', 'time_sec', 'period_id', 'dest_zone', 'region',
            'led_to_shot', 'led_to_goal', 'receiver_name',
        ])
    return pd.DataFrame(entries)


def _bup_compute(events: pd.DataFrame) -> dict:
    home_team = events['home_team'].iloc[0]
    away_team = events['away_team'].iloc[0]
    out = {}
    for pos, team in (('home', home_team), ('away', away_team)):
        te = events[events['team_position'] == pos].copy().reset_index(drop=True)
        for col in ('x', 'y', 'Pass End X', 'Pass End Y'):
            if col in te.columns:
                te[col] = pd.to_numeric(te[col], errors='coerce')
        passes   = te[te['event_type'] == 'Pass']
        succ_p   = passes[passes['outcome'] == 1]
        carries  = te[te['event_type'] == 'Ball touch']
        dribbles = te[te['event_type'] == 'Take On']
        succ_d   = dribbles[dribbles['outcome'] == 1]
        total_p = len(passes); total_d = len(dribbles)
        into_ft = 0
        if 'Pass End X' in passes.columns:
            into_ft = int((passes['Pass End X'].dropna() > 66.67).sum())
        nodes, edges = _build_network(te)
        combos  = _build_combos(te)
        combos3 = _build_3player_combos(te)
        combos4 = _build_4player_combos(te)
        entries_ft  = _build_entries(te, zone='final_third')
        entries_z14 = _build_entries(te, zone='zone14')
        if not dribbles.empty and 'player_name' in dribbles.columns:
            _drib_grp = (
                dribbles.groupby('player_name', as_index=False)
                .agg(attempts=('outcome', 'count'),
                     successful=('outcome', lambda s: int((s == 1).sum())))
            )
            _drib_grp['success_rate'] = (_drib_grp['successful'] / _drib_grp['attempts'] * 100).round(1)
            player_drib_stats = _drib_grp.sort_values('attempts', ascending=False).head(8).reset_index(drop=True)
        else:
            player_drib_stats = pd.DataFrame(columns=['player_name', 'attempts', 'successful', 'success_rate'])
        touches = te.dropna(subset=['x', 'y'])
        touch_x = touches['x'].tolist()
        touch_y = touches['y'].tolist()
        if not touches.empty and 'player_name' in touches.columns:
            total_t = max(len(touches), 1)
            t_h1 = touches[touches['period_id'] == 1] if 'period_id' in touches.columns else pd.DataFrame()
            t_h2 = touches[touches['period_id'] == 2] if 'period_id' in touches.columns else pd.DataFrame()
            total_h1 = max(len(t_h1), 1); total_h2 = max(len(t_h2), 1)
            g_tot = touches.groupby('player_name').size().rename('total')
            g_h1  = (t_h1.groupby('player_name').size().rename('h1')
                     if not t_h1.empty else pd.Series(dtype=float, name='h1'))
            g_h2  = (t_h2.groupby('player_name').size().rename('h2')
                     if not t_h2.empty else pd.Series(dtype=float, name='h2'))
            poss_df = pd.concat([g_tot, g_h1, g_h2], axis=1).fillna(0).reset_index()
            poss_df.columns = ['player_name', 'total', 'h1', 'h2']
            poss_df['pct']    = (poss_df['total'] / total_t  * 100).round(1)
            poss_df['pct_h1'] = (poss_df['h1']    / total_h1 * 100).round(1)
            poss_df['pct_h2'] = (poss_df['h2']    / total_h2 * 100).round(1)
            poss_df = poss_df.sort_values('pct', ascending=False).head(12).reset_index(drop=True)
        else:
            poss_df = pd.DataFrame(columns=['player_name', 'total', 'h1', 'h2', 'pct', 'pct_h1', 'pct_h2'])
        out[pos] = {
            'team': team, 'passes': total_p,
            'pass_acc': round(len(succ_p) / total_p * 100, 1) if total_p else 0.0,
            'long_balls': _count_si(passes, 'Long ball'),
            'crosses':    _count_si(passes, 'Cross'),
            'thru_balls': _count_si(passes, 'Through ball'),
            'into_ft': into_ft, 'carries': len(carries),
            'dribbles': total_d, 'drib_succ': len(succ_d),
            'drib_acc': round(len(succ_d) / total_d * 100, 1) if total_d else 0.0,
            'player_drib_stats': player_drib_stats,
            'nodes': nodes, 'edges': edges,
            'combos': combos, 'combos3': combos3, 'combos4': combos4,
            'entries_ft': entries_ft, 'entries_z14': entries_z14,
            'touch_x': touch_x, 'touch_y': touch_y,
            'player_poss_df': poss_df,
        }
    return out


def _bup_compute_half_stats(events: pd.DataFrame, pos: str, period: int | None = None) -> dict:
    home_team = events['home_team'].iloc[0]
    away_team = events['away_team'].iloc[0]
    team = home_team if pos == 'home' else away_team
    te = events[events['team_position'] == pos].copy()
    if period is not None:
        te = te[te['period_id'] == period]
    for col in ('x', 'y', 'Pass End X', 'Pass End Y'):
        if col in te.columns:
            te[col] = pd.to_numeric(te[col], errors='coerce')
    passes   = te[te['event_type'] == 'Pass']
    succ_p   = passes[passes['outcome'] == 1]
    carries  = te[te['event_type'] == 'Ball touch']
    dribbles = te[te['event_type'] == 'Take On']
    succ_d   = dribbles[dribbles['outcome'] == 1]
    total_p = len(passes); total_d = len(dribbles)
    into_ft = 0
    if 'Pass End X' in passes.columns:
        into_ft = int((passes['Pass End X'].dropna() > 66.67).sum())
    total_xt = round(float(add_xt_column(passes)['xT'].sum()), 3) if total_p > 0 else 0.0
    _ev_f = events.copy()
    _sc_f = [c for c in ['period_id', 'time_min', 'time_sec'] if c in _ev_f.columns]
    if _sc_f:
        _ev_f = _ev_f.sort_values(_sc_f).reset_index(drop=True)
    if period is not None and 'period_id' in _ev_f.columns:
        _ev_f = _ev_f[_ev_f['period_id'] == period]
    if 'team_position' in _ev_f.columns and not _ev_f.empty:
        _is_t  = _ev_f['team_position'] == pos
        _n_poss = int((_is_t & ~_is_t.shift(1, fill_value=False)).sum())
    else:
        _n_poss = 0
    avg_passes_per_poss = round(total_p / _n_poss, 1) if _n_poss > 0 else 0.0
    _all_p = events[events['event_type'] == 'Pass'].copy()
    if period is not None and 'period_id' in _all_p.columns:
        _all_p = _all_p[_all_p['period_id'] == period]
    _all_p['x'] = pd.to_numeric(_all_p['x'], errors='coerce')
    _all_ft  = int((_all_p['x'].dropna() > 66.67).sum()) if not _all_p.empty else 0
    _team_ft = int((passes['x'].dropna() > 66.67).sum()) if total_p > 0 else 0
    field_tilt = round(_team_ft / _all_ft * 100, 1) if _all_ft > 0 else 0.0
    return {
        'team': team, 'passes': total_p,
        'pass_acc':            round(len(succ_p) / total_p * 100, 1) if total_p else 0.0,
        'avg_passes_per_poss': avg_passes_per_poss,
        'field_tilt':          field_tilt,
        'long_balls':          _count_si(passes, 'Long ball'),
        'crosses':             _count_si(passes, 'Cross'),
        'thru_balls':          _count_si(passes, 'Through ball'),
        'into_ft':             into_ft,
        'total_xt':            total_xt,
        'carries':             len(carries),
        'dribbles':            total_d,
        'drib_succ':           len(succ_d),
        'drib_acc':            round(len(succ_d) / total_d * 100, 1) if total_d else 0.0,
    }


_BUP_PITCH_HEIGHT = 480

_ENTRY_COLORS = {
    'Pass':    '#32cd32',
    'Dribble': '#ffa500',
    'Carry':   '#00bfff',
}

_BAND_COLORS = {
    'Left Band':   '#00ffff',
    'Centre Band': '#ff1493',
    'Right Band':  '#ffd700',
}


def _hex_to_rgba(hex_color: str, alpha: float = 0.12) -> str:
    h = hex_color.lstrip('#')
    if len(h) == 3:
        h = ''.join(c * 2 for c in h)
    try:
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        return f'rgba({r},{g},{b},{alpha})'
    except (ValueError, IndexError):
        return f'rgba(128,128,128,{alpha})'


def _build_radar_fig(home_stats, away_stats, league_avg, home_team, away_team) -> go.Figure:
    labels = [lbl for lbl, _ in _RADAR_KEYS]
    keys   = [k   for _,   k in _RADAR_KEYS]

    def _raw(stats):
        return [float(stats.get(k, 0) or 0) for k in keys]

    hv = _raw(home_stats); av = _raw(away_stats)
    lv = _raw(league_avg) if league_avg else None
    norm_h, norm_a, norm_l = [], [], []
    for i in range(len(keys)):
        candidates = [hv[i], av[i]] + ([lv[i]] if lv else [])
        max_v = max(candidates) if max(candidates) > 0 else 1.0
        norm_h.append(round(hv[i] / max_v * 100, 1))
        norm_a.append(round(av[i] / max_v * 100, 1))
        if lv:
            norm_l.append(round(lv[i] / max_v * 100, 1))
    labels_c = labels + [labels[0]]; norm_h_c = norm_h + [norm_h[0]]; norm_a_c = norm_a + [norm_a[0]]
    hv_c = hv + [hv[0]]; av_c = av + [av[0]]
    if lv:
        norm_l_c = norm_l + [norm_l[0]]; lv_c = lv + [lv[0]]

    def _fmt(v):
        return f'{v:.1f}' if v != int(v) else str(int(v))

    fig = go.Figure()
    if lv:
        fig.add_trace(go.Scatterpolar(
            r=norm_l_c, theta=labels_c, mode='lines', name='League Avg',
            line=dict(color=GOLD, width=1.5, dash='dot'), opacity=0.85,
            customdata=[[_fmt(lv_c[i])] for i in range(len(labels_c))],
            hovertemplate='<b>League Avg</b><br>%{theta}: %{customdata[0]}<extra></extra>',
        ))
    fig.add_trace(go.Scatterpolar(
        r=norm_a_c, theta=labels_c, mode='lines+markers+text', name=away_team,
        fill='toself', fillcolor=_hex_to_rgba(AWAY_COLOR, 0.12),
        line=dict(color=AWAY_COLOR, width=2), marker=dict(size=5, color=AWAY_COLOR),
        text=[_fmt(av_c[i]) for i in range(len(labels_c))],
        textposition='bottom center', textfont=dict(size=10, color='#FFFFFF'),
        customdata=[[_fmt(av_c[i])] for i in range(len(labels_c))],
        hovertemplate=f'<b>{away_team}</b><br>%{{theta}}: %{{customdata[0]}}<extra></extra>',
    ))
    fig.add_trace(go.Scatterpolar(
        r=norm_h_c, theta=labels_c, mode='lines+markers+text', name=home_team,
        fill='toself', fillcolor=_hex_to_rgba(HOME_COLOR, 0.12),
        line=dict(color=HOME_COLOR, width=2), marker=dict(size=5, color=HOME_COLOR),
        text=[_fmt(hv_c[i]) for i in range(len(labels_c))],
        textposition='top center', textfont=dict(size=10, color='#FFFFFF'),
        customdata=[[_fmt(hv_c[i])] for i in range(len(labels_c))],
        hovertemplate=f'<b>{home_team}</b><br>%{{theta}}: %{{customdata[0]}}<extra></extra>',
    ))
    fig.update_layout(
        polar=dict(
            bgcolor='rgba(26,29,46,0.6)',
            radialaxis=dict(visible=True, range=[0, 105], showticklabels=False,
                            gridcolor='rgba(255,255,255,0.08)', linecolor='rgba(255,255,255,0.08)'),
            angularaxis=dict(tickfont=dict(size=10, color=COLORS['text_primary']),
                             gridcolor='rgba(255,255,255,0.08)', linecolor='rgba(255,255,255,0.08)'),
        ),
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', showlegend=True,
        legend=dict(x=0.5, y=-0.06, xanchor='center', yanchor='top', orientation='h',
                    font=dict(color=COLORS['text_primary'], size=11), bgcolor='rgba(0,0,0,0)'),
        height=540, margin=dict(l=80, r=80, t=30, b=80),
        hoverlabel=dict(bgcolor='#1A1D2E', font_color='white', font_size=12),
    )
    return fig


def _bup_add_attack_direction(fig: go.Figure, **_) -> None:
    fig.add_annotation(
        x=0.5, y=1.0, xref='paper', yref='paper',
        xanchor='center', yanchor='bottom',
        text='➡ Direction of Attack', showarrow=False,
        font=dict(color='black', size=16, family='Arial'),
        align='center', bgcolor='rgba(255,255,255,0.7)', borderpad=3,
    )


def _network_fig(nodes: pd.DataFrame, edges: dict, color: str, is_home: bool = True) -> go.Figure:
    fig = go.Figure()
    add_pitch_background(fig)
    if edges:
        max_cnt = max(edges.values())
        for (a, b), cnt in edges.items():
            an = nodes[nodes['player_name'] == a]
            bn = nodes[nodes['player_name'] == b]
            if an.empty or bn.empty:
                continue
            x0, y0 = float(an.iloc[0]['x']), float(an.iloc[0]['y'])
            x1, y1 = float(bn.iloc[0]['x']), float(bn.iloc[0]['y'])
            width = 1.0 + (cnt / max_cnt) * 5.0
            if (b, a) in edges:
                dx, dy = x1 - x0, y1 - y0
                length = (dx**2 + dy**2) ** 0.5 or 1.0
                ox, oy = -dy / length * 2.5, dx / length * 2.5
                xm, ym = (x0 + x1) / 2 + ox, (y0 + y1) / 2 + oy
                t = np.linspace(0, 1, 25)
                cx = (1-t)**2 * x0 + 2*(1-t)*t * xm + t**2 * x1
                cy = (1-t)**2 * y0 + 2*(1-t)*t * ym + t**2 * y1
            else:
                cx, cy = [x0, x1], [y0, y1]
                xm, ym = (x0 + x1) / 2, (y0 + y1) / 2
            fig.add_trace(go.Scatter(
                x=cx, y=cy, mode='lines',
                line=dict(color=color, width=width),
                opacity=0.55, hoverinfo='skip', showlegend=False,
            ))
            short_a = str(a).split()[-1]; short_b = str(b).split()[-1]
            fig.add_trace(go.Scatter(
                x=[xm], y=[ym], mode='markers',
                marker=dict(size=14, color='rgba(0,0,0,0)', opacity=0),
                customdata=[[short_a, short_b, cnt]],
                hovertemplate='<b>%{customdata[0]} → %{customdata[1]}</b><br>Passes: %{customdata[2]}<extra></extra>',
                showlegend=False,
            ))
    if not nodes.empty:
        fig.add_trace(go.Scatter(
            x=nodes['x'], y=nodes['y'],
            mode='markers+text',
            marker=dict(size=nodes['size'], color=color, line=dict(width=2, color='white')),
            text=nodes['label'],
            textposition='middle center',
            textfont=dict(size=8, color='white', family='Arial Black'),
            customdata=nodes[['player_name', 'involvement']].values,
            hovertemplate='<b>%{customdata[0]}</b><br>Pass involvement: %{customdata[1]:.0f} connections<extra></extra>',
            showlegend=False,
        ))
    for size, label in ((34, 'High involvement'), (22, 'Medium'), (14, 'Low')):
        fig.add_trace(go.Scatter(
            x=[None], y=[None], mode='markers',
            marker=dict(size=size, color=color, line=dict(width=2, color='white')),
            name=label, showlegend=True, legendgroup='nodes',
        ))
    for width, label in ((6.0, 'Frequent (≥8)'), (3.5, 'Moderate (4–7)'), (1.0, 'Occasional (2–3)')):
        fig.add_trace(go.Scatter(
            x=[None], y=[None], mode='lines',
            line=dict(color=color, width=width),
            name=label, showlegend=True, legendgroup='edges',
        ))
    _bup_add_attack_direction(fig, is_home=is_home)
    fig.update_layout(
        **PITCH_AXIS_FULL,
        **layout_config(
            height=_BUP_PITCH_HEIGHT, margin=dict(l=0, r=0, t=48, b=0),
            legend=dict(
                orientation='v', x=0.01, xanchor='left', y=0.99, yanchor='top',
                bgcolor='rgba(0,0,0,0.55)',
                font=dict(color=COLORS['text_primary'], size=9),
                itemsizing='trace',
            ),
        ),
        hovermode='closest',
    )
    return fig


def _entries_fig(entries_df: pd.DataFrame, zone: str,
                 color: str, is_home: bool = True) -> go.Figure:
    fig = go.Figure()
    add_pitch_background(fig)
    if not entries_df.empty:
        entries_df = entries_df.copy()
        entries_df['time_display'] = entries_df.apply(
            lambda r: f"{int(r['time_min'])}:{int(r['time_sec']):02d}", axis=1)
        entries_df['outcome_label'] = entries_df['outcome'].map(
            {1: '✓ Successful', 0: '✗ Unsuccessful'}).fillna('—')
        entries_df['shot_label'] = entries_df.apply(
            lambda r: '<br>⚽ Led to Goal' if r.get('led_to_goal', False)
                      else ('<br>🎯 Led to Shot' if r.get('led_to_shot', False) else ''),
            axis=1,
        )
        if 'receiver_name' not in entries_df.columns:
            entries_df['receiver_name'] = ''
        if zone == 'zone14':
            groups = [('Entries', color, entries_df)]
        elif 'dest_zone' in entries_df.columns and entries_df['dest_zone'].notna().any():
            groups = [(g, c, entries_df[entries_df['dest_zone'] == g]) for g, c in _BAND_COLORS.items()]
        else:
            groups = [(g, c, entries_df[entries_df['event_label'] == g]) for g, c in _ENTRY_COLORS.items()]
        for group_name, ecolor, subset in groups:
            if subset.empty:
                continue
            passes_sub    = subset[subset['event_label'] == 'Pass']
            nonpasses_sub = subset[subset['event_label'] != 'Pass']
            if zone == 'zone14':
                for _, row in passes_sub.iterrows():
                    fig.add_annotation(
                        x=row['end_x'], y=row['end_y'], ax=row['x'], ay=row['y'],
                        xref='x', yref='y', axref='x', ayref='y',
                        showarrow=True, arrowhead=2, arrowsize=1.5,
                        arrowwidth=2, arrowcolor=ecolor, opacity=0.65,
                    )
                if not nonpasses_sub.empty:
                    xs, ys = [], []
                    for _, row in nonpasses_sub.iterrows():
                        xs.extend([row['x'], row['end_x'], None])
                        ys.extend([row['y'], row['end_y'], None])
                    fig.add_trace(go.Scatter(
                        x=xs, y=ys, mode='lines',
                        line=dict(color=ecolor, width=2, dash='dash'),
                        showlegend=False, hoverinfo='skip',
                    ))
            else:
                for _, row in subset.iterrows():
                    fig.add_annotation(
                        x=row['end_x'], y=row['end_y'], ax=row['x'], ay=row['y'],
                        xref='x', yref='y', axref='x', ayref='y',
                        showarrow=True, arrowhead=2, arrowsize=1.5,
                        arrowwidth=2, arrowcolor=ecolor, opacity=0.65,
                    )
            legend_name = f'{group_name} ({len(subset)})'
            legend_shown = False
            if not passes_sub.empty:
                if zone == 'zone14':
                    cd = passes_sub[['player_name', 'receiver_name', 'event_label',
                                     'time_display', 'outcome_label', 'shot_label']].values
                    ht = (f'<b>{group_name}</b><br>Pass: %{{customdata[0]}} → %{{customdata[1]}}<br>'
                          'Time: %{customdata[3]}<br>%{customdata[4]}%{customdata[5]}<extra></extra>')
                else:
                    cd = passes_sub[['player_name', 'receiver_name',
                                     'time_display', 'outcome_label', 'shot_label']].values
                    ht = (f'<b>{group_name}</b><br>%{{customdata[0]}} → %{{customdata[1]}}<br>'
                          'Time: %{customdata[2]}<br>%{customdata[3]}%{customdata[4]}<extra></extra>')
                fig.add_trace(go.Scatter(
                    x=passes_sub['end_x'], y=passes_sub['end_y'], mode='markers',
                    marker=dict(size=8, color=ecolor, line=dict(width=1.5, color='white')),
                    customdata=cd, hovertemplate=ht,
                    name=legend_name, showlegend=True, legendgroup=group_name,
                ))
                legend_shown = True
            if not nonpasses_sub.empty:
                if zone == 'zone14':
                    cd = nonpasses_sub[['player_name', 'event_label',
                                        'time_display', 'outcome_label', 'shot_label']].values
                    ht = (f'<b>{group_name}</b><br>%{{customdata[1]}}: %{{customdata[0]}}<br>'
                          'Time: %{customdata[2]}<br>%{customdata[3]}%{customdata[4]}<extra></extra>')
                else:
                    cd = nonpasses_sub[['player_name', 'time_display', 'outcome_label', 'shot_label']].values
                    ht = (f'<b>{group_name}</b><br>%{{customdata[0]}}<br>'
                          'Time: %{customdata[1]}<br>%{customdata[2]}%{customdata[3]}<extra></extra>')
                fig.add_trace(go.Scatter(
                    x=nonpasses_sub['end_x'], y=nonpasses_sub['end_y'], mode='markers',
                    marker=dict(size=8, color=ecolor, line=dict(width=1.5, color='white')),
                    customdata=cd, hovertemplate=ht,
                    name=legend_name if not legend_shown else '',
                    showlegend=not legend_shown, legendgroup=group_name,
                ))
    if zone == 'final_third':
        fig.add_shape(type='line', x0=66.67, y0=0, x1=66.67, y1=100,
                      line=dict(color='yellow', width=2, dash='dash'))
        for y_val in (66.67, 33.33):
            fig.add_shape(type='line', x0=0, y0=y_val, x1=100, y1=y_val,
                          line=dict(color='white', width=1.5, dash='dot'))
        for y_val, lbl, clr in ((83, 'Left Band', '#00ffff'), (50, 'Centre Band', '#ff1493'), (17, 'Right Band', '#ffd700')):
            fig.add_annotation(x=4, y=y_val, text=lbl, showarrow=False,
                               font=dict(color=clr, size=9, family='Arial Black'),
                               bgcolor='rgba(0,0,0,0.5)', borderpad=2)
    elif zone == 'zone14':
        fig.add_shape(type='rect', x0=66.67, y0=37, x1=83.33, y1=63,
                      line=dict(color='rgba(255,255,255,0.25)', width=1, dash='dash'),
                      fillcolor='rgba(255,255,255,0.03)')
        for y0, y1 in ((63, 79), (21, 37)):
            fig.add_shape(type='rect', x0=66.67, y0=y0, x1=100, y1=y1,
                          line=dict(color='rgba(255,255,255,0.25)', width=1, dash='dash'),
                          fillcolor='rgba(255,255,255,0.03)')
        for y_pos, lbl in ((50, 'Zone 14'), (71, 'Left HS'), (29, 'Right HS')):
            fig.add_annotation(x=75, y=y_pos, text=lbl, showarrow=False,
                               font=dict(color='rgba(255,255,255,0.45)', size=8, family='Arial'),
                               bgcolor='rgba(0,0,0,0)', borderpad=2)
    _bup_add_attack_direction(fig, is_home=is_home)
    fig.update_layout(
        **PITCH_AXIS_FULL,
        **layout_config(
            height=_BUP_PITCH_HEIGHT, margin=dict(l=0, r=0, t=48, b=0),
            legend=dict(orientation='v', x=0.99, xanchor='right', y=0.99, yanchor='top',
                        bgcolor='rgba(0,0,0,0.55)',
                        font=dict(color=COLORS['text_primary'], size=9)),
        ),
        hovermode='closest',
    )
    return fig


_REGION_ORDER = ['Zone 14', 'Left HS', 'Right HS']


def _zone14_bar_fig(entries_df: pd.DataFrame, color: str) -> go.Figure:
    """Stacked bar of Zone 14 / half-space entries split by successful vs unsuccessful."""
    succ, unsucc = [], []
    for reg in _REGION_ORDER:
        if entries_df.empty or 'region' not in entries_df.columns:
            succ.append(0); unsucc.append(0); continue
        sub = entries_df[entries_df['region'] == reg]
        s = int((sub['outcome'] == 1).sum())
        succ.append(s)
        unsucc.append(len(sub) - s)
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=_REGION_ORDER, y=succ, name='Successful', marker_color='#32cd32',
        text=[str(v) if v else '' for v in succ], textposition='inside',
        textfont=dict(color='white', size=11),
        hovertemplate='%{x}<br>Successful: %{y}<extra></extra>',
    ))
    fig.add_trace(go.Bar(
        x=_REGION_ORDER, y=unsucc, name='Unsuccessful', marker_color='#dc3545',
        text=[str(v) if v else '' for v in unsucc], textposition='inside',
        textfont=dict(color='white', size=11),
        hovertemplate='%{x}<br>Unsuccessful: %{y}<extra></extra>',
    ))
    for reg, s, u in zip(_REGION_ORDER, succ, unsucc):
        if s + u:
            fig.add_annotation(x=reg, y=s + u, text=str(s + u), showarrow=False,
                               yshift=10, font=dict(color=color, size=12, family='Arial Black'))
    fig.update_layout(
        barmode='stack', height=_BUP_PITCH_HEIGHT,
        margin=dict(l=8, r=8, t=40, b=70),
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
        title=dict(text='Entries by Region', x=0.5, xanchor='center',
                   font=dict(color=color, size=12)),
        legend=dict(orientation='h', x=0.5, xanchor='center', y=-0.1, yanchor='top',
                    font=dict(color=COLORS['text_primary'], size=9), bgcolor='rgba(0,0,0,0)'),
        xaxis=dict(tickfont=dict(color=COLORS['text_primary'], size=9), showgrid=False),
        yaxis=dict(tickfont=dict(color=COLORS['text_secondary'], size=9),
                   gridcolor='rgba(255,255,255,0.08)', zeroline=False),
        bargap=0.35,
    )
    return fig


def _combo_table(combos: pd.DataFrame, color: str) -> html.Div:
    if combos.empty:
        return html.Div('No data', style={'color': COLORS['text_secondary'], 'fontSize': '0.8rem',
                                          'textAlign': 'center', 'marginTop': '12px'})
    _th = {'color': COLORS['text_secondary'], 'fontSize': '0.65rem', 'fontWeight': '600',
           'padding': '5px 8px', 'borderBottom': f'1px solid {COLORS["dark_border"]}',
           'textTransform': 'uppercase'}
    header = html.Tr([html.Th('Combination', style=_th),
                      html.Th('N (1H / 2H)', style={**_th, 'textAlign': 'right'})])
    rows = []
    for i, row in combos.iterrows():
        bg = COLORS.get('dark_tertiary', 'rgba(255,255,255,0.03)') if i % 2 == 0 else 'transparent'
        count_str = f"{int(row['Total'])} ({int(row['H1'])} / {int(row['H2'])})"
        rows.append(html.Tr([
            html.Td(row['Combo'], style={'color': color, 'fontSize': '0.78rem',
                                        'padding': '4px 8px', 'fontWeight': '500'}),
            html.Td(count_str, style={'color': COLORS['text_primary'], 'fontSize': '0.78rem',
                                      'padding': '4px 8px', 'textAlign': 'right', 'fontWeight': '600'}),
        ], style={'backgroundColor': bg}))
    return html.Div(html.Table([html.Thead(header), html.Tbody(rows)],
                               style={'width': '100%', 'borderCollapse': 'collapse'}),
                    style={'overflowX': 'auto'})


def _pitch_card(title: str, fig: go.Figure, color: str) -> dbc.Col:
    return dbc.Col(
        html.Div([
            html.Div(title, style={'color': color, 'fontWeight': '600',
                                   'fontSize': '0.85rem', 'marginBottom': '8px', 'textAlign': 'center'}),
            dcc.Graph(figure=fig, config=CHART_CONFIG),
        ], style=CARD_STYLE),
        md=6, className='mb-3',
    )


def _build_player_entries_table(entries_ft: pd.DataFrame, entries_z14: pd.DataFrame) -> pd.DataFrame:
    def _counts(df: pd.DataFrame, zone_filter=None) -> pd.DataFrame:
        if df.empty:
            return pd.DataFrame(columns=['player_name', 'total', 'h1', 'h2'])
        d = df.copy()
        if zone_filter is not None:
            d = d[d['dest_zone'] == zone_filter]
        if d.empty:
            return pd.DataFrame(columns=['player_name', 'total', 'h1', 'h2'])
        grp = d.groupby('player_name')
        total = grp.size().rename('total')
        h1 = grp.apply(lambda g: (g['period_id'] == 1).sum()).rename('h1')
        h2 = grp.apply(lambda g: (g['period_id'] == 2).sum()).rename('h2')
        return pd.concat([total, h1, h2], axis=1).reset_index()
    ft = _counts(entries_ft)
    lb = _counts(entries_z14, 'Left Band')
    cb = _counts(entries_z14, 'Centre Band')
    rb = _counts(entries_z14, 'Right Band')
    all_players: set = set()
    for df in [ft, lb, cb, rb]:
        if not df.empty:
            all_players.update(df['player_name'].tolist())
    if not all_players:
        return pd.DataFrame()
    result = pd.DataFrame({'player_name': sorted(all_players)})
    for prefix, df in [('ft', ft), ('lb', lb), ('cb', cb), ('rb', rb)]:
        if df.empty:
            result[f'{prefix}_total'] = 0; result[f'{prefix}_h1'] = 0; result[f'{prefix}_h2'] = 0
        else:
            merged = result.merge(df.rename(columns={'total': f'{prefix}_total',
                                                      'h1': f'{prefix}_h1',
                                                      'h2': f'{prefix}_h2'}),
                                  on='player_name', how='left')
            result = merged.fillna(0)
            for c in [f'{prefix}_total', f'{prefix}_h1', f'{prefix}_h2']:
                result[c] = result[c].astype(int)
    result['_grand_total'] = (result['ft_total'] + result['lb_total']
                               + result['cb_total'] + result['rb_total'])
    result = (result[result['_grand_total'] > 0]
              .sort_values('_grand_total', ascending=False)
              .drop(columns='_grand_total').reset_index(drop=True))
    return result


def _player_entries_table(df: pd.DataFrame, color: str) -> html.Div:
    _hdr = {'textAlign': 'center', 'padding': '6px 8px', 'fontSize': '0.63rem', 'fontWeight': '700',
            'color': COLORS['text_secondary'], 'textTransform': 'uppercase', 'letterSpacing': '0.06em',
            'borderBottom': f'1px solid {COLORS["dark_border"]}', 'whiteSpace': 'nowrap'}
    _lbl = {'padding': '5px 8px', 'fontSize': '0.77rem', 'color': COLORS['text_primary'],
            'whiteSpace': 'nowrap', 'maxWidth': '150px', 'overflow': 'hidden', 'textOverflow': 'ellipsis'}
    _val = {'textAlign': 'center', 'padding': '5px 8px', 'fontSize': '0.76rem', 'fontWeight': '600',
            'color': COLORS['text_primary'], 'whiteSpace': 'nowrap'}
    if df.empty:
        return html.Div('No entry data', style={'color': COLORS['text_secondary'], 'fontSize': '0.8rem',
                                                'textAlign': 'center', 'marginTop': '8px'})
    def _fmt(total, h1, h2):
        return f"{int(total)}({int(h1)}/{int(h2)})"
    header = html.Tr([
        html.Th('Player', style={**_hdr, 'textAlign': 'left'}),
        html.Th('Final Third', style=_hdr), html.Th('Left Band', style=_hdr),
        html.Th('Centre Band', style=_hdr), html.Th('Right Band', style=_hdr),
    ])
    rows = []
    for i, row in df.iterrows():
        bg = COLORS.get('dark_tertiary', 'rgba(255,255,255,0.03)') if i % 2 == 0 else 'transparent'
        short_name = str(row['player_name']).split()[-1] if pd.notna(row['player_name']) else '—'
        rows.append(html.Tr([
            html.Td(short_name, style={**_lbl, 'color': color}),
            html.Td(_fmt(row['ft_total'], row['ft_h1'], row['ft_h2']), style=_val),
            html.Td(_fmt(row['lb_total'], row['lb_h1'], row['lb_h2']), style=_val),
            html.Td(_fmt(row['cb_total'], row['cb_h1'], row['cb_h2']), style=_val),
            html.Td(_fmt(row['rb_total'], row['rb_h1'], row['rb_h2']), style=_val),
        ], style={'backgroundColor': bg}))
    return html.Div(html.Table([html.Thead(header), html.Tbody(rows)],
                               style={'width': '100%', 'borderCollapse': 'collapse'}),
                    style={'overflowX': 'auto'})


def _short_name(name) -> str:
    """'Marcus Rashford' -> 'M Rashford'; single-token names returned as-is."""
    if not isinstance(name, str) or not name.strip():
        return '—'
    parts = name.split()
    if len(parts) == 1:
        return parts[0]
    return f'{parts[0][0]} {parts[-1]}'


def _connections_table(edges: dict, color: str) -> html.Div:
    if not edges:
        return html.Div('No data', style={'color': COLORS['text_secondary'], 'fontSize': '0.8rem',
                                          'textAlign': 'center', 'marginTop': '12px'})
    top = sorted(edges.items(), key=lambda kv: kv[1], reverse=True)[:5]
    _hdr = {'fontSize': '0.63rem', 'fontWeight': '700', 'padding': '5px 8px',
            'color': COLORS['text_secondary'], 'textTransform': 'uppercase', 'letterSpacing': '0.04em',
            'borderBottom': f'1px solid {COLORS["dark_border"]}', 'whiteSpace': 'nowrap'}
    _lbl = {'padding': '4px 8px', 'fontSize': '0.76rem', 'whiteSpace': 'nowrap'}
    _val = {'textAlign': 'right', 'padding': '4px 8px', 'fontSize': '0.76rem', 'fontWeight': '600',
            'color': COLORS['text_primary'], 'whiteSpace': 'nowrap'}
    header = html.Tr([html.Th('Connection', style={**_hdr, 'textAlign': 'left'}),
                      html.Th('Passes', style={**_hdr, 'textAlign': 'right'})])
    rows = []
    for i, ((a, b), cnt) in enumerate(top):
        bg = COLORS.get('dark_tertiary', 'rgba(255,255,255,0.03)') if i % 2 == 0 else 'transparent'
        combo = f'{_short_name(a)} → {_short_name(b)}'
        rows.append(html.Tr([
            html.Td(combo, style={**_lbl, 'color': color}),
            html.Td(str(int(cnt)), style=_val),
        ], style={'backgroundColor': bg}))
    return html.Div([
        html.Div('Top Connections', style={'color': color, 'fontWeight': '700', 'fontSize': '0.7rem',
                 'textTransform': 'uppercase', 'letterSpacing': '0.04em', 'marginBottom': '6px'}),
        html.Table([html.Thead(header), html.Tbody(rows)],
                   style={'width': '100%', 'borderCollapse': 'collapse'}),
    ], style={'overflowX': 'auto'})


def _player_possession_table(poss_df: pd.DataFrame, color: str) -> html.Div:
    if poss_df.empty:
        return html.Div('No data', style={'color': COLORS['text_secondary'], 'fontSize': '0.8rem',
                                          'textAlign': 'center', 'marginTop': '12px'})
    _hdr = {'fontSize': '0.65rem', 'fontWeight': '700', 'padding': '5px 8px',
            'color': COLORS['text_secondary'], 'textTransform': 'uppercase', 'letterSpacing': '0.04em',
            'borderBottom': f'1px solid {COLORS["dark_border"]}'}
    _lbl = {'padding': '4px 8px', 'fontSize': '0.77rem', 'color': COLORS['text_primary'], 'whiteSpace': 'nowrap'}
    _val = {'textAlign': 'right', 'padding': '4px 8px', 'fontSize': '0.76rem', 'fontWeight': '600',
            'color': COLORS['text_primary'], 'whiteSpace': 'nowrap'}
    header = html.Tr([html.Th('Player', style={**_hdr, 'textAlign': 'left'}),
                      html.Th('Touch %', style={**_hdr, 'textAlign': 'right'})])
    rows = []
    for i, row in poss_df.iterrows():
        bg = COLORS.get('dark_tertiary', 'rgba(255,255,255,0.03)') if i % 2 == 0 else 'transparent'
        short_name = _short_name(row['player_name'])
        pct_str = f"{row['pct']}% ({row['pct_h1']}%/{row['pct_h2']}%)"
        rows.append(html.Tr([
            html.Td(short_name, style={**_lbl, 'color': color}),
            html.Td(pct_str, style=_val),
        ], style={'backgroundColor': bg}))
    return html.Div(html.Table([html.Thead(header), html.Tbody(rows)],
                               style={'width': '100%', 'borderCollapse': 'collapse'}),
                    style={'overflowX': 'auto'})


_BUP_METRICS = [
    ('Total Passes',     'passes',              False),
    ('Pass Accuracy',    'pass_acc',            True),
    ('Field Tilt',       'field_tilt',          True),
    ('Avg Passes/Poss',  'avg_passes_per_poss', False),
    ('Positional xT',    'total_xt',            False),
    ('Into Final Third', 'into_ft',    False),
    ('Long Balls',       'long_balls', False),
    ('Crosses',          'crosses',    False),
    ('Through Balls',    'thru_balls', False),
    ('Ball Carries',     'carries',    False),
    ('Dribble Attempts', 'dribbles',   False),
    ('Dribbles Won',     'drib_succ',  False),
    ('Dribble Success',  'drib_acc',   True),
]


def _render_radar(events: pd.DataFrame) -> html.Div:
    if events.empty:
        return html.Div()
    home_team  = str(events['home_team'].iloc[0]) if 'home_team' in events.columns else 'Home'
    away_team  = str(events['away_team'].iloc[0]) if 'away_team' in events.columns else 'Away'
    home_stats = _bup_compute_half_stats(events, 'home')
    away_stats = _bup_compute_half_stats(events, 'away')
    league_avg = _compute_league_avg(events)
    fig = _build_radar_fig(home_stats, away_stats, league_avg, home_team, away_team)
    return html.Div([
        section_header('Build-Up Radar'),
        build_info_box('Each axis scaled 0–100 relative to the highest value among home, away, and league average. '
                       'Hover a point for the actual value.'),
        dcc.Graph(figure=fig, config=CHART_CONFIG),
    ], style={'marginBottom': '36px'})


def _render_stats(events: pd.DataFrame) -> html.Div:
    if events.empty:
        return html.P('No event data.', style={'color': COLORS['text_secondary']})
    h_full = _bup_compute_half_stats(events, 'home')
    h_h1   = _bup_compute_half_stats(events, 'home', 1)
    h_h2   = _bup_compute_half_stats(events, 'home', 2)
    a_full = _bup_compute_half_stats(events, 'away')
    a_h1   = _bup_compute_half_stats(events, 'away', 1)
    a_h2   = _bup_compute_half_stats(events, 'away', 2)
    return html.Div([
        section_header('Pass / Carry / Dribble Stats'),
        build_info_box('Performance breakdown by half — Passing, Carries & Dribbles'),
        dbc.Row([
            dbc.Col(build_team_stats_table(h_full['team'], HOME_COLOR, _BUP_METRICS, h_full, h_h1, h_h2),
                    md=6, className='mb-3'),
            dbc.Col(build_team_stats_table(a_full['team'], AWAY_COLOR, _BUP_METRICS, a_full, a_h1, a_h2),
                    md=6, className='mb-3'),
        ], className='g-3'),
    ], style={'marginBottom': '8px'})


def _render_possession(events: pd.DataFrame) -> html.Div:
    if events.empty:
        return html.P('No event data.', style={'color': COLORS['text_secondary']})
    d   = _bup_compute(events)
    hs  = d['home']
    as_ = d['away']

    def _heatmap_card(team, color, touch_x, touch_y, poss_df):
        img_src = render_lsc_heatmap_img(touch_x, touch_y, GOLD)
        return html.Div([
            html.Div(team, style={'color': color, 'fontWeight': '700',
                                  'fontSize': '0.85rem', 'marginBottom': '8px', 'textAlign': 'center'}),
            dbc.Row([
                dbc.Col(html.Img(src=img_src, style={'width': '100%', 'borderRadius': '6px'}), md=8),
                dbc.Col(html.Div(_player_possession_table(poss_df, color),
                                 style={'overflowY': 'auto', 'maxHeight': '420px'}), md=4),
            ], className='g-2', align='start'),
        ], style=CARD_STYLE)

    heatmap_row = dbc.Row([
        dbc.Col(_heatmap_card(hs['team'], HOME_COLOR, hs['touch_x'], hs['touch_y'], hs['player_poss_df']),
                md=6, className='mb-3'),
        dbc.Col(_heatmap_card(as_['team'], AWAY_COLOR, as_['touch_x'], as_['touch_y'], as_['player_poss_df']),
                md=6, className='mb-3'),
    ], className='g-3')
    return html.Div([
        section_header('Possession Touch Map'),
        build_info_box('Touch density across the pitch — darker = more activity. '
                       'Player touch share (% of team touches) shown alongside · format: total% (1H%/2H%).'),
        heatmap_row,
    ], style={'marginBottom': '36px'})


def _render_network(events: pd.DataFrame) -> html.Div:
    if events.empty:
        return html.P('No event data.', style={'color': COLORS['text_secondary']})
    d   = _bup_compute(events)
    hs  = d['home']
    as_ = d['away']

    def _team_block(team, color, nodes, edges, is_home):
        return dbc.Col([
            html.Div(team, style={'color': color, 'fontWeight': '700',
                                  'fontSize': '0.85rem', 'marginBottom': '8px', 'textAlign': 'center'}),
            dbc.Row([
                dbc.Col(dcc.Graph(figure=_network_fig(nodes, edges, color, is_home=is_home),
                                  config=CHART_CONFIG), md=9),
                dbc.Col(html.Div(_connections_table(edges, color),
                                 style={'overflowY': 'auto', 'maxHeight': '420px'}), md=3),
            ], className='g-2', align='start'),
        ], md=6, className='mb-3', style=CARD_STYLE)

    return html.Div([
        section_header('Pass Network'),
        build_info_box('Node size = pass involvement · Edge width = connection frequency · '
                       'Hover nodes/edges for details · Top 5 passer → receiver connections shown alongside'),
        dbc.Row([
            _team_block(hs['team'], HOME_COLOR, hs['nodes'], hs['edges'], is_home=True),
            _team_block(as_['team'], AWAY_COLOR, as_['nodes'], as_['edges'], is_home=False),
        ], className='g-3'),
    ], style={'marginBottom': '36px'})


def _render_combos(events: pd.DataFrame) -> html.Div:
    if events.empty:
        return html.P('No event data.', style={'color': COLORS['text_secondary']})
    d   = _bup_compute(events)
    hs  = d['home']
    as_ = d['away']

    def _combo_section(title, info, combo_key):
        return html.Div([
            section_header(title),
            build_info_box(info),
            dbc.Row([
                dbc.Col(html.Div([
                    html.Div(hs['team'], style={'color': HOME_COLOR, 'fontWeight': '700',
                                               'fontSize': '0.85rem', 'marginBottom': '8px'}),
                    _combo_table(hs[combo_key], HOME_COLOR),
                ], style=CARD_STYLE), md=6, className='mb-3'),
                dbc.Col(html.Div([
                    html.Div(as_['team'], style={'color': AWAY_COLOR, 'fontWeight': '700',
                                                'fontSize': '0.85rem', 'marginBottom': '8px'}),
                    _combo_table(as_[combo_key], AWAY_COLOR),
                ], style=CARD_STYLE), md=6, className='mb-3'),
            ], className='g-3'),
        ], style={'marginBottom': '24px'})

    return html.Div([
        _combo_section('Top Combinations', 'Most frequent passer → receiver combinations · N (1H / 2H)', 'combos'),
        _combo_section('Top 3-Player Combinations', 'Most frequent three-player passing chains (A → B → C) · N (1H / 2H)', 'combos3'),
        _combo_section('Top 4-Player Combinations', 'Most frequent four-player passing chains (A → B → C → D) · N (1H / 2H)', 'combos4'),
    ])


def _render_entries(events: pd.DataFrame) -> html.Div:
    if events.empty:
        return html.P('No event data.', style={'color': COLORS['text_secondary']})
    d   = _bup_compute(events)
    hs  = d['home']
    as_ = d['away']
    def _entry_card(team, entries_df, color, is_home):
        total = len(entries_df)
        return dbc.Col(html.Div([
            html.Div(f"{team} ({total} entries)", style={'color': color, 'fontWeight': '600',
                     'fontSize': '0.85rem', 'marginBottom': '8px', 'textAlign': 'center'}),
            dbc.Row([
                dbc.Col(dcc.Graph(figure=_entries_fig(entries_df, 'zone14', color, is_home=is_home),
                                  config=CHART_CONFIG), md=9),
                dbc.Col(dcc.Graph(figure=_zone14_bar_fig(entries_df, color),
                                  config=CHART_CONFIG), md=3),
            ], className='g-2', align='start'),
        ], style=CARD_STYLE), md=6, className='mb-3')

    return html.Div([
        section_header('Zone 14 Entries'),
        build_info_box('Passes (solid arrows), dribbles and carries (dashed lines) ending in Zone 14, '
                       'Left Half Space (y 63–79) or Right Half Space (y 21–37). '
                       'Bars show entry counts per region, split successful (green) vs unsuccessful (red).'),
        dbc.Row([
            _entry_card(hs['team'], hs['entries_z14'], HOME_COLOR, is_home=True),
            _entry_card(as_['team'], as_['entries_z14'], AWAY_COLOR, is_home=False),
        ], className='g-3'),
    ], style={'marginBottom': '36px'})


def _render_tables(events: pd.DataFrame) -> html.Div:
    if events.empty:
        return html.P('No event data.', style={'color': COLORS['text_secondary']})
    d   = _bup_compute(events)
    hs  = d['home']
    as_ = d['away']
    home_df = _build_player_entries_table(hs['entries_ft'], hs['entries_z14'])
    away_df = _build_player_entries_table(as_['entries_ft'], as_['entries_z14'])
    return html.Div([
        section_header('Player Zone Entries'),
        build_info_box('Final Third entries per player broken down by band — format: total(1H/2H)'),
        dbc.Row([
            dbc.Col(html.Div([
                html.Div(hs['team'], style={'color': HOME_COLOR, 'fontWeight': '700',
                                           'fontSize': '0.85rem', 'marginBottom': '8px'}),
                _player_entries_table(home_df, HOME_COLOR),
            ], style=CARD_STYLE), md=6, className='mb-3'),
            dbc.Col(html.Div([
                html.Div(as_['team'], style={'color': AWAY_COLOR, 'fontWeight': '700',
                                            'fontSize': '0.85rem', 'marginBottom': '8px'}),
                _player_entries_table(away_df, AWAY_COLOR),
            ], style=CARD_STYLE), md=6, className='mb-3'),
        ], className='g-3'),
    ])


def build_build_up_passing_tab(events: pd.DataFrame, **_) -> html.Div:
    if events.empty:
        return html.P('No event data.', style={'color': COLORS['text_secondary']})
    return html.Div([
        _render_possession(events),
        _render_network(events),
        _render_entries(events),
    ], style={'marginTop': '16px'})


def build_bup_radar(events: pd.DataFrame):
    if events.empty:
        return None
    home_team  = str(events['home_team'].iloc[0]) if 'home_team' in events.columns else 'Home'
    away_team  = str(events['away_team'].iloc[0]) if 'away_team' in events.columns else 'Away'
    home_stats = _bup_compute_half_stats(events, 'home')
    away_stats = _bup_compute_half_stats(events, 'away')
    league_avg = _compute_league_avg(events)
    return _build_radar_fig(home_stats, away_stats, league_avg, home_team, away_team)


def register_build_up_passing_callbacks(app) -> None:
    # Half filter removed — entries render statically inside build_build_up_passing_tab.
    return None

# ============================================================================
# ===== defensive_structure.py =====
# ============================================================================
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from dash import html, dcc
import dash_bootstrap_components as dbc

from utils.config import COLORS
from utils.data_utils import get_match_events, get_match_results
from page_utils.visualizations import (
    HOME_COLOR, AWAY_COLOR, GOLD, CHART_CONFIG,
    layout_config, add_pitch_background,
    PITCH_AXIS_FULL, render_xt_heatmap_img,
)
from page_utils.event_filters import DEF_ACTION_TYPES
from page_utils.pitch_zones import get_zone, PitchZone

_DEF_PITCH_HEIGHT = 480

_DEF_COLORS = {
    'Tackle':        '#4dabf7',
    'Interception':  '#51cf66',
    'Ball recovery': '#ffd43b',
    'Clearance':     '#ff922b',
    'Blocked Shot':  '#cc5de8',
}

_DEF_METRICS = [
    ('Tackles Won',      'tackles_str',     False),
    ('Interceptions',    'interceptions',   False),
    ('Clearances',       'clearances',      False),
    ('Ball Recoveries',  'ball_recoveries', False),
    ('Blocked Shots',    'blocked_shots',   False),
    ('Fouls Committed',  'fouls_committed', False),
    ('Aerial Duels',     'aerials_str',     False),
    ('PPDA',             'ppda',            False),
]

_DEF_RADAR_KEYS = [
    ('Tackles Won',     'tackles_won',     False),
    ('Interceptions',   'interceptions',   False),
    ('Clearances',      'clearances',      False),
    ('Ball Recoveries', 'ball_recoveries', False),
    ('Fouls Committed', 'fouls_committed', False),
    ('Aerials Won',     'aerials_won',     False),
    ('PPDA',            'ppda',            True),
]

_def_league_avg_cache: dict = {}
_def_zone_league_cache: dict = {}

_ZONE_LABELS = ['Z1', 'Z2', 'Z3']  # Z1 = own def third, Z2 = middle, Z3 = final third


def _zone_counts(df: pd.DataFrame) -> list:
    """Count rows by pitch third → [Z1, Z2, Z3]."""
    z1 = z2 = z3 = 0
    if 'x' in df.columns:
        for x_val in pd.to_numeric(df['x'], errors='coerce').dropna():
            z = get_zone(float(x_val))
            if z == PitchZone.FINAL_THIRD:    z3 += 1
            elif z == PitchZone.MIDDLE_THIRD: z2 += 1
            else:                             z1 += 1
    return [z1, z2, z3]


def _def_compute_half_stats(events: pd.DataFrame, pos: str, period: int | None = None) -> dict:
    home_team = events['home_team'].iloc[0]
    away_team = events['away_team'].iloc[0]
    team = home_team if pos == 'home' else away_team
    te  = events[events['team_position'] == pos]
    opp = events[events['team_position'] != pos]
    if period is not None:
        te  = te[te['period_id'] == period]
        opp = opp[opp['period_id'] == period]
    tackles         = te[te['event_type'] == 'Tackle']
    tackles_won     = tackles[tackles['outcome'] == 1]
    interceptions   = te[te['event_type'] == 'Interception']
    clearances      = te[te['event_type'] == 'Clearance']
    ball_recoveries = te[te['event_type'] == 'Ball recovery']
    blocked_shots   = te[te['event_type'] == 'Blocked Shot']
    fouls_committed = te[te['event_type'] == 'Foul']
    if 'outcome' in te.columns:
        fouls_committed = fouls_committed[fouls_committed['outcome'] == 1]
    aerials     = te[te['event_type'] == 'Aerial']
    aerials_won = aerials[aerials['outcome'] == 1]
    opp_passes  = len(opp[opp['event_type'] == 'Pass'])
    def_actions = len(tackles) + len(interceptions) + len(fouls_committed)
    ppda = round(opp_passes / def_actions, 1) if def_actions > 0 else 0.0
    return {
        'team': team,
        'tackles':         len(tackles),     'tackles_won':     len(tackles_won),
        'tackles_str':     f'{len(tackles_won)}/{len(tackles)}',
        'interceptions':   len(interceptions),
        'clearances':      len(clearances),
        'ball_recoveries': len(ball_recoveries),
        'blocked_shots':   len(blocked_shots),
        'fouls_committed': len(fouls_committed),
        'aerials':         len(aerials),     'aerials_won': len(aerials_won),
        'aerials_str':     f'{len(aerials_won)}/{len(aerials)}',
        'ppda':            ppda,
    }


def _def_compute(events: pd.DataFrame) -> dict:
    home_team = events['home_team'].iloc[0]
    away_team = events['away_team'].iloc[0]
    out = {}
    for pos, team in (('home', home_team), ('away', away_team)):
        te  = events[events['team_position'] == pos]
        opp = events[events['team_position'] != pos]
        tackles         = te[te['event_type'] == 'Tackle']
        interceptions   = te[te['event_type'] == 'Interception']
        clearances      = te[te['event_type'] == 'Clearance']
        ball_recoveries = te[te['event_type'] == 'Ball recovery']
        blocked_shots   = te[te['event_type'] == 'Blocked Shot']
        all_def = pd.concat([tackles, interceptions, ball_recoveries])
        high_count = mid_count = low_count = 0
        if 'x' in all_def.columns:
            for x_val in all_def['x'].dropna():
                z = get_zone(float(x_val))
                if z == PitchZone.FINAL_THIRD:     high_count += 1
                elif z == PitchZone.MIDDLE_THIRD:  mid_count  += 1
                else:                              low_count  += 1
        heatmap_x = all_def['x'].dropna().tolist() if 'x' in all_def.columns else []
        heatmap_y = all_def['y'].dropna().tolist() if 'y' in all_def.columns else []
        all_actions = pd.concat([tackles, interceptions, ball_recoveries, clearances, blocked_shots])

        def _player_stats(df):
            if df.empty:
                return pd.DataFrame(columns=['Player', 'Actions', 'Tackles', 'Interceptions',
                                             'Recoveries', 'Clearances', 'Blocks'])
            return (
                df.groupby('player_name')
                .agg(
                    Actions=('event_type', 'count'),
                    Tackles=('event_type', lambda s: (s == 'Tackle').sum()),
                    Interceptions=('event_type', lambda s: (s == 'Interception').sum()),
                    Recoveries=('event_type', lambda s: (s == 'Ball recovery').sum()),
                    Clearances=('event_type', lambda s: (s == 'Clearance').sum()),
                    Blocks=('event_type', lambda s: (s == 'Blocked Shot').sum()),
                )
                .reset_index()
                .rename(columns={'player_name': 'Player'})
                .sort_values('Actions', ascending=False)
                .head(8).reset_index(drop=True)
            )

        player_full = _player_stats(all_actions)
        h1_acts = all_actions[all_actions['period_id'] == 1] if 'period_id' in all_actions.columns else pd.DataFrame()
        h2_acts = all_actions[all_actions['period_id'] == 2] if 'period_id' in all_actions.columns else pd.DataFrame()
        player_h1 = _player_stats(h1_acts)
        player_h2 = _player_stats(h2_acts)
        def_events_df = te[te['event_type'].isin(DEF_ACTION_TYPES)].copy()
        fouls_df = te[te['event_type'] == 'Foul'].copy()
        if 'outcome' in fouls_df.columns:
            fouls_df = fouls_df[fouls_df['outcome'] == 1]
        offsides_df = opp[opp['event_type'] == 'Offside Pass'].copy()
        out[pos] = {
            'team': team,
            'high_press': high_count, 'mid_press': mid_count, 'low_press': low_count,
            'zone_counts': _zone_counts(def_events_df),
            'heatmap_x': heatmap_x, 'heatmap_y': heatmap_y,
            'player_full': player_full, 'player_h1': player_h1, 'player_h2': player_h2,
            'def_events_df': def_events_df, 'fouls_df': fouls_df, 'offsides_df': offsides_df,
        }
    return out


def _compute_def_league_avg(events: pd.DataFrame) -> dict:
    global _def_league_avg_cache
    competition = ''
    if 'competition' in events.columns and not events.empty:
        competition = str(events['competition'].iloc[0])
    if not competition:
        try:
            from utils.match_data_adapter import get_match_metadata
            competition = get_match_metadata(events).get('competition', '')
        except Exception:
            pass
    if not competition:
        return {}
    if competition in _def_league_avg_cache:
        return _def_league_avg_cache[competition]
    try:
        keys = [k for _, k, _ in _DEF_RADAR_KEYS]
        accumulated: dict = {k: [] for k in keys}
        for r in get_match_results():
            if r.get('competition') != competition:
                continue
            try:
                ev = get_match_events(r['match_id'])
                if ev.empty:
                    continue
                for pos in ('home', 'away'):
                    s = _def_compute_half_stats(ev, pos)
                    for k in keys:
                        v = s.get(k, 0)
                        if isinstance(v, (int, float)) and not pd.isna(v):
                            accumulated[k].append(float(v))
            except Exception:
                continue
        avg = {k: round(sum(v) / len(v), 2) if v else 0.0 for k, v in accumulated.items()}
        _def_league_avg_cache[competition] = avg
        return avg
    except Exception:
        return {}


def _compute_def_zone_league_avg(events: pd.DataFrame) -> list:
    """Average defensive-action count per zone [Z1, Z2, Z3] across the competition (per team-match)."""
    global _def_zone_league_cache
    competition = ''
    if 'competition' in events.columns and not events.empty:
        competition = str(events['competition'].iloc[0])
    if not competition:
        try:
            from utils.match_data_adapter import get_match_metadata
            competition = get_match_metadata(events).get('competition', '')
        except Exception:
            pass
    if not competition:
        return [0.0, 0.0, 0.0]
    if competition in _def_zone_league_cache:
        return _def_zone_league_cache[competition]
    try:
        acc = [[], [], []]
        for r in get_match_results():
            if r.get('competition') != competition:
                continue
            try:
                ev = get_match_events(r['match_id'])
                if ev.empty:
                    continue
                for pos in ('home', 'away'):
                    te  = ev[ev['team_position'] == pos]
                    ddf = te[te['event_type'].isin(DEF_ACTION_TYPES)]
                    for i, c in enumerate(_zone_counts(ddf)):
                        acc[i].append(c)
            except Exception:
                continue
        avg = [round(sum(v) / len(v), 1) if v else 0.0 for v in acc]
        _def_zone_league_cache[competition] = avg
        return avg
    except Exception:
        return [0.0, 0.0, 0.0]


def _def_zone_bar_fig(zone_counts: list, league_avg: list, color: str) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=_ZONE_LABELS, y=zone_counts, name='This Match', marker_color=color,
        text=[str(int(v)) for v in zone_counts], textposition='outside',
        textfont=dict(color=COLORS['text_primary'], size=10), cliponaxis=False,
        hovertemplate='%{x}<br>This Match: %{y}<extra></extra>',
    ))
    fig.add_trace(go.Bar(
        x=_ZONE_LABELS, y=league_avg, name='League Avg', marker_color=GOLD, opacity=0.55,
        text=[f'{v:.1f}' for v in league_avg], textposition='outside',
        textfont=dict(color=GOLD, size=10), cliponaxis=False,
        hovertemplate='%{x}<br>League Avg: %{y}<extra></extra>',
    ))
    fig.update_layout(
        barmode='group', height=_DEF_PITCH_HEIGHT,
        margin=dict(l=8, r=8, t=40, b=80),
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
        title=dict(text='Actions by Zone', x=0.5, xanchor='center',
                   font=dict(color=color, size=12)),
        legend=dict(orientation='h', x=0.5, xanchor='center', y=-0.08, yanchor='top',
                    font=dict(color=COLORS['text_primary'], size=9), bgcolor='rgba(0,0,0,0)'),
        xaxis=dict(tickfont=dict(color=COLORS['text_primary'], size=10), showgrid=False),
        yaxis=dict(tickfont=dict(color=COLORS['text_secondary'], size=9),
                   gridcolor='rgba(255,255,255,0.08)', zeroline=False),
        bargap=0.3, bargroupgap=0.12,
    )
    return fig


def _hex_to_rgba_def(hex_color: str, alpha: float = 0.12) -> str:
    h = hex_color.lstrip('#')
    if len(h) == 3:
        h = ''.join(c * 2 for c in h)
    try:
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        return f'rgba({r},{g},{b},{alpha})'
    except (ValueError, IndexError):
        return f'rgba(128,128,128,{alpha})'


def _build_def_radar_fig(home_stats, away_stats, league_avg, home_team, away_team) -> go.Figure:
    labels  = [lbl for lbl, _, _   in _DEF_RADAR_KEYS]
    keys    = [k   for _,   k, _   in _DEF_RADAR_KEYS]
    inverts = [inv for _,   _, inv in _DEF_RADAR_KEYS]

    def _raw(stats):
        return [float(stats.get(k, 0) or 0) for k in keys]

    hv_raw = _raw(home_stats); av_raw = _raw(away_stats)
    lv_raw = _raw(league_avg) if league_avg else None

    def _transform(vals):
        return [1.0 / v if inv and v > 0 else v for v, inv in zip(vals, inverts)]

    hv = _transform(hv_raw); av = _transform(av_raw)
    lv = _transform(lv_raw) if lv_raw is not None else None
    norm_h, norm_a, norm_l = [], [], []
    for i in range(len(keys)):
        candidates = [hv[i], av[i]] + ([lv[i]] if lv else [])
        max_v = max(candidates) if max(candidates) > 0 else 1.0
        norm_h.append(round(hv[i] / max_v * 100, 1))
        norm_a.append(round(av[i] / max_v * 100, 1))
        if lv:
            norm_l.append(round(lv[i] / max_v * 100, 1))
    labels_c = labels + [labels[0]]
    norm_h_c = norm_h + [norm_h[0]]; norm_a_c = norm_a + [norm_a[0]]
    hv_raw_c = hv_raw + [hv_raw[0]]; av_raw_c = av_raw + [av_raw[0]]
    if lv:
        norm_l_c = norm_l + [norm_l[0]]; lv_raw_c = lv_raw + [lv_raw[0]]

    def _fmt(v):
        return f'{v:.1f}' if v != int(v) else str(int(v))

    fig = go.Figure()
    if lv:
        fig.add_trace(go.Scatterpolar(
            r=norm_l_c, theta=labels_c, mode='lines', name='League Avg',
            line=dict(color=GOLD, width=1.5, dash='dot'), opacity=0.85,
            customdata=[[_fmt(lv_raw_c[i])] for i in range(len(labels_c))],
            hovertemplate='<b>League Avg</b><br>%{theta}: %{customdata[0]}<extra></extra>',
        ))
    fig.add_trace(go.Scatterpolar(
        r=norm_a_c, theta=labels_c, mode='lines+markers+text', name=away_team,
        fill='toself', fillcolor=_hex_to_rgba_def(AWAY_COLOR, 0.12),
        line=dict(color=AWAY_COLOR, width=2), marker=dict(size=5, color=AWAY_COLOR),
        text=[_fmt(av_raw_c[i]) for i in range(len(labels_c))],
        textposition='bottom center', textfont=dict(size=10, color='#FFFFFF'),
        customdata=[[_fmt(av_raw_c[i])] for i in range(len(labels_c))],
        hovertemplate=f'<b>{away_team}</b><br>%{{theta}}: %{{customdata[0]}}<extra></extra>',
    ))
    fig.add_trace(go.Scatterpolar(
        r=norm_h_c, theta=labels_c, mode='lines+markers+text', name=home_team,
        fill='toself', fillcolor=_hex_to_rgba_def(HOME_COLOR, 0.12),
        line=dict(color=HOME_COLOR, width=2), marker=dict(size=5, color=HOME_COLOR),
        text=[_fmt(hv_raw_c[i]) for i in range(len(labels_c))],
        textposition='top center', textfont=dict(size=10, color='#FFFFFF'),
        customdata=[[_fmt(hv_raw_c[i])] for i in range(len(labels_c))],
        hovertemplate=f'<b>{home_team}</b><br>%{{theta}}: %{{customdata[0]}}<extra></extra>',
    ))
    fig.update_layout(
        polar=dict(
            bgcolor='rgba(26,29,46,0.6)',
            radialaxis=dict(visible=True, range=[0, 105], showticklabels=False,
                            gridcolor='rgba(255,255,255,0.08)', linecolor='rgba(255,255,255,0.08)'),
            angularaxis=dict(tickfont=dict(size=10, color=COLORS['text_primary']),
                             gridcolor='rgba(255,255,255,0.08)', linecolor='rgba(255,255,255,0.08)'),
        ),
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', showlegend=True,
        legend=dict(x=0.5, y=-0.06, xanchor='center', yanchor='top', orientation='h',
                    font=dict(color=COLORS['text_primary'], size=11), bgcolor='rgba(0,0,0,0)'),
        height=540, margin=dict(l=80, r=80, t=30, b=80),
        hoverlabel=dict(bgcolor='#1A1D2E', font_color='white', font_size=12),
    )
    return fig


def _def_add_attack_direction(fig: go.Figure) -> None:
    fig.add_annotation(
        x=0.5, y=1.0, xref='paper', yref='paper',
        xanchor='center', yanchor='bottom',
        text='➡ Direction of Attack', showarrow=False,
        font=dict(color='black', size=16, family='Arial'),
        align='center', bgcolor='rgba(255,255,255,0.7)', borderpad=3,
    )


def _def_action_map(def_events_df: pd.DataFrame, team_color: str,
                    fouls_df: pd.DataFrame | None = None,
                    offsides_df: pd.DataFrame | None = None) -> dcc.Graph:
    fig = go.Figure()
    add_pitch_background(fig)
    if not def_events_df.empty and 'x' in def_events_df.columns:
        for action_type, group in def_events_df.groupby('event_type'):
            valid = group.dropna(subset=['x', 'y'])
            if valid.empty:
                continue
            customdata = [[name, t, action_type]
                          for name, t in zip(valid['player_name'].fillna('Unknown').tolist(),
                                             valid['time_min'].fillna(0).astype(int).tolist())]
            fig.add_trace(go.Scatter(
                x=valid['x'].tolist(), y=valid['y'].tolist(), mode='markers', name=action_type,
                marker=dict(color=_DEF_COLORS.get(action_type, team_color), size=8, opacity=0.75,
                            line=dict(color='rgba(0,0,0,0.3)', width=0.5)),
                customdata=customdata,
                hovertemplate='<b>%{customdata[0]}</b><br>Minute: %{customdata[1]}\'<br>Action: %{customdata[2]}<extra></extra>',
            ))
    if fouls_df is not None and not fouls_df.empty and 'x' in fouls_df.columns:
        valid = fouls_df.dropna(subset=['x', 'y'])
        if not valid.empty:
            zones = (valid['Zone'].fillna('—').where(valid['Zone'] != 'N/A', '—').tolist()
                     if 'Zone' in valid.columns else ['—'] * len(valid))
            customdata = [[name, t, 'Foul', z]
                          for name, t, z in zip(valid['player_name'].fillna('Unknown').tolist(),
                                                valid['time_min'].fillna(0).astype(int).tolist(), zones)]
            fig.add_trace(go.Scatter(
                x=valid['x'].tolist(), y=valid['y'].tolist(), mode='markers', name='Foul',
                marker=dict(color='#ff6b6b', size=10, symbol='x', opacity=0.85,
                            line=dict(color='white', width=1)),
                customdata=customdata,
                hovertemplate="<b>%{customdata[0]}</b><br>Minute: %{customdata[1]}'<br>Event: %{customdata[2]}<br>Zone: %{customdata[3]}<extra></extra>",
            ))
    if offsides_df is not None and not offsides_df.empty and 'x' in offsides_df.columns:
        valid = offsides_df.dropna(subset=['x', 'y'])
        if not valid.empty:
            customdata = [[name, t, 'Offside Pass']
                          for name, t in zip(valid['player_name'].fillna('Unknown').tolist(),
                                             valid['time_min'].fillna(0).astype(int).tolist())]
            fig.add_trace(go.Scatter(
                x=valid['x'].tolist(), y=valid['y'].tolist(), mode='markers', name='Offside',
                marker=dict(color='#ffd43b', size=10, symbol='triangle-up', opacity=0.85,
                            line=dict(color='white', width=1)),
                customdata=customdata,
                hovertemplate="<b>%{customdata[0]}</b><br>Minute: %{customdata[1]}'<br>Event: %{customdata[2]}<extra></extra>",
            ))
    _def_add_attack_direction(fig)
    fig.update_layout(**layout_config(
        **PITCH_AXIS_FULL, height=_DEF_PITCH_HEIGHT, margin=dict(l=0, r=0, t=48, b=80),
        legend=dict(orientation='h', x=0.5, xanchor='center', y=-0.08, yanchor='top',
                    bgcolor='rgba(0,0,0,0)', font=dict(color=COLORS['text_primary'], size=9)),
    ))
    return dcc.Graph(figure=fig, config=CHART_CONFIG)


def _player_defensive_table(player_full: pd.DataFrame, player_h1: pd.DataFrame,
                             player_h2: pd.DataFrame, color: str, team_name: str) -> html.Div:
    if player_full.empty:
        return html.Div("No data", style={'color': COLORS['text_secondary']})
    _hdr = {'fontSize': '0.65rem', 'fontWeight': '700', 'padding': '5px 8px',
            'color': COLORS['text_secondary'], 'textTransform': 'uppercase',
            'letterSpacing': '0.04em', 'borderBottom': f'1px solid {COLORS["dark_border"]}'}
    _val = {'fontSize': '0.78rem', 'padding': '4px 8px', 'color': COLORS['text_primary'], 'textAlign': 'center'}
    cols = ['Player', 'Actions', 'Tackles', 'Int.', 'Rec.', 'Clr.', 'Blk.', '1H', '2H']
    header = html.Tr([html.Th(c, style=_hdr) for c in cols])
    rows = []
    for i, (_, row) in enumerate(player_full.iterrows()):
        bg = COLORS['dark_tertiary'] if i % 2 == 0 else 'transparent'
        pname = row.get('Player', '')
        h1_row = player_h1[player_h1['Player'] == pname]
        h2_row = player_h2[player_h2['Player'] == pname]
        h1_total = int(h1_row['Actions'].iloc[0]) if not h1_row.empty else 0
        h2_total = int(h2_row['Actions'].iloc[0]) if not h2_row.empty else 0
        short_name = str(pname).split()[-1] if pname else ''
        cells = [
            html.Td(short_name, style={**_val, 'color': color, 'fontWeight': '600',
                                        'textAlign': 'left', 'whiteSpace': 'nowrap'}),
            html.Td(str(int(row.get('Actions', 0))), style=_val),
            html.Td(str(int(row.get('Tackles', 0))), style=_val),
            html.Td(str(int(row.get('Interceptions', 0))), style=_val),
            html.Td(str(int(row.get('Recoveries', 0))), style=_val),
            html.Td(str(int(row.get('Clearances', 0))), style=_val),
            html.Td(str(int(row.get('Blocks', 0))), style=_val),
            html.Td(str(h1_total), style={**_val, 'color': COLORS['text_secondary']}),
            html.Td(str(h2_total), style={**_val, 'color': COLORS['text_secondary']}),
        ]
        rows.append(html.Tr(cells, style={'backgroundColor': bg}))
    return html.Div([
        html.Div(team_name, style={'color': color, 'fontWeight': '700', 'fontSize': '0.95rem',
                                   'marginBottom': '10px', 'borderBottom': f'2px solid {color}',
                                   'paddingBottom': '6px'}),
        html.Div(html.Table([html.Thead(header), html.Tbody(rows)],
                             style={'width': '100%', 'borderCollapse': 'collapse'}),
                 style={'overflowX': 'auto'}),
    ], style=CARD_STYLE)


def _def_action_heatmap(x_vals: list, y_vals: list, team: str, color: str) -> html.Div:
    label = html.Div(f"Defensive Actions — {team}", style={
        'color': color, 'fontWeight': '600', 'fontSize': '0.85rem',
        'marginBottom': '8px', 'textAlign': 'center',
    })
    if len(x_vals) < 2:
        return html.Div([label, html.Div("Not enough data",
                                          style={'color': COLORS['text_secondary'], 'textAlign': 'center', 'fontSize': '0.8rem'})],
                        style=CARD_STYLE)
    img_src = render_xt_heatmap_img(x_vals, y_vals, [1.0] * len(x_vals))
    return html.Div([label, html.Img(src=img_src, style={'width': '100%', 'borderRadius': '6px'})],
                    style=CARD_STYLE)


def _fouls_offsides_map(fouls_df: pd.DataFrame, offsides_df: pd.DataFrame) -> dcc.Graph:
    fig = go.Figure()
    add_pitch_background(fig)
    if not fouls_df.empty and 'x' in fouls_df.columns:
        valid = fouls_df.dropna(subset=['x', 'y'])
        if not valid.empty:
            zones = (valid['Zone'].fillna('—').astype(str).where(valid['Zone'] != 'N/A', '—').tolist()
                     if 'Zone' in valid.columns else ['—'] * len(valid))
            customdata = [[name, t, 'Foul', z]
                          for name, t, z in zip(valid['player_name'].fillna('Unknown').tolist(),
                                                valid['time_min'].fillna(0).astype(int).tolist(), zones)]
            fig.add_trace(go.Scatter(
                x=valid['x'].tolist(), y=valid['y'].tolist(), mode='markers', name='Foul',
                marker=dict(color='#ff6b6b', size=10, symbol='x', opacity=0.85,
                            line=dict(color='white', width=1)),
                customdata=customdata,
                hovertemplate="<b>%{customdata[0]}</b><br>Minute: %{customdata[1]}'<br>Event: %{customdata[2]}<br>Zone: %{customdata[3]}<extra></extra>",
            ))
    if not offsides_df.empty and 'x' in offsides_df.columns:
        valid = offsides_df.dropna(subset=['x', 'y'])
        if not valid.empty:
            customdata = [[name, t, 'Offside Pass']
                          for name, t in zip(valid['player_name'].fillna('Unknown').tolist(),
                                             valid['time_min'].fillna(0).astype(int).tolist())]
            fig.add_trace(go.Scatter(
                x=valid['x'].tolist(), y=valid['y'].tolist(), mode='markers', name='Offside',
                marker=dict(color='#ffd43b', size=10, symbol='triangle-up', opacity=0.85,
                            line=dict(color='white', width=1)),
                customdata=customdata,
                hovertemplate="<b>%{customdata[0]}</b><br>Minute: %{customdata[1]}'<br>Event: %{customdata[2]}<extra></extra>",
            ))
    _def_add_attack_direction(fig)
    fig.update_layout(**layout_config(
        **PITCH_AXIS_FULL, height=_DEF_PITCH_HEIGHT, margin=dict(l=0, r=0, t=48, b=0),
        legend=dict(orientation='v', x=0.01, xanchor='left', y=0.99, yanchor='top',
                    bgcolor='rgba(0,0,0,0.55)', font=dict(color=COLORS['text_primary'], size=9)),
    ))
    return dcc.Graph(figure=fig, config=CHART_CONFIG)


def _render_def_plots(events: pd.DataFrame) -> html.Div:
    if events.empty:
        return html.P("No event data.", style={"color": COLORS["text_secondary"]})
    d = _def_compute(events)
    hs, as_ = d['home'], d['away']
    zone_league_avg = _compute_def_zone_league_avg(events)

    def _team_card(data, color):
        return dbc.Col(html.Div([
            html.Div(data['team'], style={'color': color, 'fontWeight': '700',
                                          'fontSize': '0.85rem', 'marginBottom': '8px'}),
            dbc.Row([
                dbc.Col(_def_action_map(data['def_events_df'], color,
                                        data['fouls_df'], data['offsides_df']), md=9),
                dbc.Col(dcc.Graph(figure=_def_zone_bar_fig(data['zone_counts'], zone_league_avg, color),
                                  config=CHART_CONFIG), md=3),
            ], className='g-2', align='start'),
            html.Div(_player_defensive_table(data['player_full'], data['player_h1'], data['player_h2'],
                                             color, data['team']), style={'marginTop': '12px'}),
        ], style=CARD_STYLE), md=6, className='mb-3')

    return html.Div([
        section_header("Defensive Action Map"),
        build_legend_box([
            ('●', 'Tackle',       '#4dabf7'), ('●', 'Interception', '#51cf66'),
            ('●', 'Recovery',     '#ffd43b'), ('●', 'Clearance',    '#ff922b'),
            ('●', 'Block',        '#cc5de8'), ('✕', 'Foul',         '#ff6b6b'),
            ('▲', 'Offside',      '#ffd43b'),
        ]),
        dbc.Row([
            _team_card(hs, HOME_COLOR),
            _team_card(as_, AWAY_COLOR),
        ], className='g-3'),
    ], style={'marginBottom': '32px'})


def build_defensive_structure_tab(events: pd.DataFrame, **_) -> html.Div:
    if events.empty:
        return html.P("No event data.", style={"color": COLORS["text_secondary"]})
    return html.Div([_render_def_plots(events)], style={'marginTop': '16px'})


def build_def_radar(events: pd.DataFrame):
    if events.empty:
        return None
    home_team  = str(events['home_team'].iloc[0]) if 'home_team' in events.columns else 'Home'
    away_team  = str(events['away_team'].iloc[0]) if 'away_team' in events.columns else 'Away'
    h_full     = _def_compute_half_stats(events, 'home')
    a_full     = _def_compute_half_stats(events, 'away')
    league_avg = _compute_def_league_avg(events)
    return _build_def_radar_fig(h_full, a_full, league_avg, home_team, away_team)


def register_defensive_structure_callbacks(app) -> None:
    pass

# ============================================================================
# ===== transitions_counterpressing.py =====
# ============================================================================
import pandas as pd
import plotly.graph_objects as go
from dash import html, dcc
import dash_bootstrap_components as dbc

from utils.config import COLORS
from page_utils.visualizations import (
    HOME_COLOR, AWAY_COLOR, GOLD, CHART_CONFIG,
    add_pitch_background, PITCH_AXIS_FULL,
    render_xt_heatmap_img, PITCH_BG,
)

_TRANSITION_WINDOW_SEC = 15

_POSS_LOSS_RAW = ['Miscontrol', 'Dispossessed', 'Offside Pass', 'Error']

_LOSS_COLORS = {
    'Failed Pass':  '#ef4444',
    'Miscontrol':   '#f97316',
    'Dispossessed': '#3b82f6',
    'Lost Duel':    '#06b6d4',
    'Lost Aerial':  '#8b5cf6',
    'Offside Pass': '#eab308',
    'Error':        '#a855f7',
}

_LOSS_OUTCOME_SYMBOLS = {
    'Goal Conceded':   ('star',        14),
    'Shot Conceded':   ('triangle-up', 12),
    'Team Recovered':  ('circle',      11),
    'No Clear Threat': ('square',      10),
}

_GAIN_TYPES_RAW = ['Ball recovery', 'Interception']

_GAIN_COLORS = {
    'Ball recovery': '#22c55e',
    'Interception':  '#3b82f6',
    'Tackle Won':    GOLD,
}

_GAIN_OUTCOME_SYMBOLS = {
    'Goal Scored':     ('star',        14),
    'Shot Taken':      ('triangle-up', 12),
    'Quick Turnover':  ('x',           12),
    'Possession Held': ('circle',      10),
}

_POSS_LOSS_EVENTS = ['Miscontrol', 'Dispossessed', 'Offside Pass', 'Error']
_SHOT_TYPES       = ['Goal', 'Saved Shot', 'Miss']
_RECOVERY_TYPES   = ['Tackle', 'Interception', 'Ball recovery']

_SKEL_SRC = 'data:image/png;base64,'

_BTN_BASE = {
    'display': 'block', 'width': '100%', 'textAlign': 'center',
    'padding': '20px 0', 'fontWeight': '700', 'fontSize': '1rem',
    'letterSpacing': '0.6px', 'textTransform': 'uppercase',
    'backgroundColor': COLORS['dark_secondary'],
    'border': f'1px solid {COLORS["dark_border"]}', 'borderRadius': '0',
}
_BTN_INACTIVE = {**_BTN_BASE, 'color': COLORS['text_secondary']}
_BTN_ACTIVE   = {**_BTN_BASE, 'color': GOLD,
                 'backgroundColor': 'rgba(237,187,0,0.08)',
                 'borderBottom': f'3px solid {GOLD}'}

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
    'maxWidth': '100px', 'overflow': 'hidden', 'textOverflow': 'ellipsis',
}


def _tc_add_attack_direction(fig: go.Figure) -> None:
    fig.add_annotation(
        x=0.5, y=1.02, xref='paper', yref='paper',
        text='<b>➡  Direction of Attack</b>', showarrow=False,
        font=dict(size=10, color='white', family='Arial, sans-serif'),
        xanchor='center', yanchor='bottom',
        bgcolor='rgba(21,25,50,0.8)', bordercolor='#8899CC',
        borderwidth=1, borderpad=4,
    )


def _add_third_dividers(fig: go.Figure) -> None:
    for x_pos, label in ((100 / 3, 'Z1  Def Third'), (200 / 3, 'Z3  Att Third')):
        fig.add_shape(type='line', x0=x_pos, x1=x_pos, y0=-2, y1=102,
                      xref='x', yref='y',
                      line=dict(color='rgba(255,255,255,0.15)', width=1.5, dash='dash'),
                      layer='above')
        fig.add_annotation(x=x_pos, y=103, xref='x', yref='y',
                           text=f'<b>{label}</b>', showarrow=False,
                           font=dict(size=8, color='rgba(255,255,255,0.40)', family='Arial, sans-serif'),
                           xanchor='center', yanchor='bottom')
    for x_centre, zone_name in [(16.67, 'Zone 1'), (50.0, 'Zone 2'), (83.33, 'Zone 3')]:
        fig.add_annotation(x=x_centre, y=2, xref='x', yref='y',
                           text=zone_name, showarrow=False,
                           font=dict(size=9, color='rgba(255,255,255,0.20)', family='Arial Black'),
                           xanchor='center', yanchor='bottom')


def _pitch_layout(uirev: str) -> dict:
    return dict(
        **PITCH_AXIS_FULL,
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
        font=dict(color='#E8E9ED', size=12, family='Arial, sans-serif'),
        height=520, hovermode='closest', uirevision=uirev,
        legend=dict(
            orientation='v', x=1.01, y=1.0, xanchor='left', yanchor='top',
            bgcolor='rgba(21,25,50,0.88)',
            bordercolor=COLORS.get('dark_border', 'rgba(255,255,255,0.15)'),
            borderwidth=1, font=dict(color=COLORS['text_primary'], size=10),
            groupclick='toggleitem',
        ),
        legend2=dict(
            orientation='v', x=1.01, y=0.45, xanchor='left', yanchor='top',
            bgcolor='rgba(21,25,50,0.88)',
            bordercolor=COLORS.get('dark_border', 'rgba(255,255,255,0.15)'),
            borderwidth=1, font=dict(color=COLORS['text_primary'], size=10),
            groupclick='toggleitem',
        ),
        margin=dict(l=0, r=150, t=36, b=0),
    )


def _extract_losses(te: pd.DataFrame, all_events: pd.DataFrame) -> pd.DataFrame:
    has_event_id = 'event_id' in all_events.columns
    has_related  = 'Related event ID' in all_events.columns
    has_team_pos = 'team_position' in all_events.columns
    eid_to_player: dict = {}; eid_to_pos: dict = {}
    if has_event_id:
        eid_to_player = dict(zip(all_events['event_id'].astype(str),
                                  all_events['player_name'].fillna('')))
        if has_team_pos:
            eid_to_pos = dict(zip(all_events['event_id'].astype(str),
                                   all_events['team_position'].fillna('')))
    te_pos = te['team_position'].iloc[0] if (not te.empty and 'team_position' in te.columns) else ''

    def _resolve_opponent(row) -> str:
        if not has_related:
            return ''
        rid = str(row.get('Related event ID', ''))
        if not rid or rid in ('nan', 'None', ''):
            return ''
        player = eid_to_player.get(rid, ''); pos = eid_to_pos.get(rid, '')
        if player and pos and pos != te_pos:
            return player
        return ''

    rows = []
    for _, row in te.iterrows():
        etype = row.get('event_type', ''); outcome = row.get('outcome', 1)
        if etype == 'Pass' and outcome == 0:         loss_type = 'Failed Pass'
        elif etype == 'Challenge' and outcome == 0:  loss_type = 'Lost Duel'
        elif etype == 'Aerial' and outcome == 0:     loss_type = 'Lost Aerial'
        elif etype in _POSS_LOSS_RAW:                loss_type = etype
        else:                                        continue
        x = row.get('x', None); y = row.get('y', None)
        if pd.isna(x) or pd.isna(y):
            continue
        t_min = int(row.get('time_min', 0) or 0); t_sec = int(row.get('time_sec', 0) or 0)
        opp_player = _resolve_opponent(row) if loss_type == 'Dispossessed' else ''
        rows.append({
            'loss_type': loss_type, 'player_name': row.get('player_name', '') or '',
            'time_min': t_min, 'time_sec': t_sec, 'period_id': row.get('period_id', 1),
            'x': float(x), 'y': float(y), 'timestamp': t_min * 60 + t_sec,
            'opponent_player': opp_player,
        })
    return pd.DataFrame(rows) if rows else pd.DataFrame(
        columns=['loss_type', 'player_name', 'time_min', 'time_sec',
                 'period_id', 'x', 'y', 'timestamp', 'opponent_player'])


def _opp_events_in_windows(losses: pd.DataFrame, opp: pd.DataFrame) -> pd.DataFrame:
    if losses.empty or opp.empty:
        return pd.DataFrame()
    opp = opp.copy()
    if 'time_min' not in opp.columns or 'time_sec' not in opp.columns:
        return pd.DataFrame()
    opp['_ts'] = opp['time_min'].fillna(0).astype(int) * 60 + opp['time_sec'].fillna(0).astype(int)
    parts = []
    for period_id, loss_grp in losses.groupby('period_id'):
        opp_sl = opp[opp['period_id'] == period_id]
        if opp_sl.empty:
            continue
        for t_loss in loss_grp['timestamp']:
            window = opp_sl[(opp_sl['_ts'] >= t_loss) & (opp_sl['_ts'] <= t_loss + _TRANSITION_WINDOW_SEC)]
            parts.append(window)
    if not parts:
        return pd.DataFrame()
    return pd.concat(parts, ignore_index=True).drop_duplicates()


def _tag_loss_outcomes(losses: pd.DataFrame, te: pd.DataFrame, opp: pd.DataFrame) -> pd.DataFrame:
    if losses.empty:
        losses = losses.copy()
        losses['window_outcome'] = ''; losses['window_detail'] = ''
        return losses
    te = te.copy(); opp = opp.copy()
    for df in (te, opp):
        df['_ts'] = df['time_min'].fillna(0).astype(int) * 60 + df['time_sec'].fillna(0).astype(int)
    all_outcomes: dict = {}; all_details: dict = {}
    for period_id, grp in losses.groupby('period_id'):
        opp_sl = opp[opp['period_id'] == period_id]
        te_sl  = te[te['period_id']  == period_id]
        for idx, loss_row in grp.iterrows():
            t0 = int(loss_row['timestamp']); t1 = t0 + _TRANSITION_WINDOW_SEC
            opp_win = opp_sl[(opp_sl['_ts'] >= t0) & (opp_sl['_ts'] <= t1)]
            te_win  = te_sl[(te_sl['_ts']   >= t0) & (te_sl['_ts']  <= t1)]
            has_goal    = not opp_win.empty and (opp_win['event_type'] == 'Goal').any()
            has_shot    = not opp_win.empty and opp_win['event_type'].isin(_SHOT_TYPES).any()
            has_recover = not te_win.empty  and te_win['event_type'].isin(_RECOVERY_TYPES).any()
            if has_goal:
                goal_rows = opp_win[opp_win['event_type'] == 'Goal']
                scorer  = goal_rows['player_name'].iloc[0] if not goal_rows.empty else ''
                outcome = 'Goal Conceded'; detail = f'Scorer: {scorer}' if scorer else ''
            elif has_shot:
                shot_rows = opp_win[opp_win['event_type'].isin(_SHOT_TYPES)]
                shooter   = shot_rows['player_name'].iloc[0] if not shot_rows.empty else ''
                shot_type = shot_rows['event_type'].iloc[0]  if not shot_rows.empty else ''
                outcome = 'Shot Conceded'; detail = f'{shot_type} by {shooter}' if shooter else shot_type
            elif has_recover:
                rec_rows  = te_win[te_win['event_type'].isin(_RECOVERY_TYPES)]
                recoverer = rec_rows['player_name'].iloc[0] if not rec_rows.empty else ''
                rec_type  = rec_rows['event_type'].iloc[0]  if not rec_rows.empty else ''
                outcome = 'Team Recovered'; detail = f'{rec_type} — {recoverer}' if recoverer else rec_type
            else:
                outcome = 'No Clear Threat'; detail = ''
            all_outcomes[idx] = outcome; all_details[idx] = detail
    losses = losses.copy()
    losses['window_outcome'] = losses.index.map(lambda i: all_outcomes.get(i, 'No Clear Threat'))
    losses['window_detail']  = losses.index.map(lambda i: all_details.get(i, ''))
    return losses


def _losses_zone_donut_card(losses: pd.DataFrame, opp_in_windows: pd.DataFrame, color: str) -> list:
    z1 = int((losses['x'] < 33.33).sum())                                 if not losses.empty else 0
    z2 = int(((losses['x'] >= 33.33) & (losses['x'] < 66.67)).sum())     if not losses.empty else 0
    z3 = int((losses['x'] >= 66.67).sum())                                if not losses.empty else 0
    total = z1 + z2 + z3
    fig = go.Figure(go.Pie(
        labels=['Def 3rd', 'Mid 3rd', 'Att 3rd'],
        values=[z1, z2, z3] if total > 0 else [1, 1, 1], hole=0.6,
        marker=dict(colors=['#ef4444', '#f97316', '#22c55e'],
                    line=dict(color='rgba(0,0,0,0.2)', width=1.5)),
        textinfo='label+percent', textposition='auto', insidetextorientation='horizontal',
        textfont=dict(color='white', size=12),
        hovertemplate='<b>%{label}</b>: %{value} (%{percent})<extra></extra>', sort=False,
    ))
    fig.add_annotation(text=str(total), x=0.5, y=0.5, showarrow=False,
                       font=dict(color='white', size=18, family='Arial Black'), xref='paper', yref='paper')
    fig.update_layout(
        title=dict(text='<b>Losses by Zone</b>', x=0.5,
                   font=dict(color=COLORS['text_secondary'], size=12)),
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
        showlegend=True,
        legend=dict(orientation='h', x=0.5, xanchor='center', y=-0.08,
                    font=dict(color=COLORS['text_primary'], size=10),
                    bgcolor='rgba(0,0,0,0)', itemsizing='constant'),
        margin=dict(l=5, r=5, t=34, b=34), height=230,
    )
    if not opp_in_windows.empty and 'event_type' in opp_in_windows.columns:
        shots_faced = int(opp_in_windows['event_type'].isin(_SHOT_TYPES).sum())
        goals_faced = int((opp_in_windows['event_type'] == 'Goal').sum())
    else:
        shots_faced = goals_faced = 0
    def _stat_box(lbl, val, c):
        return html.Div([
            html.Div(val, style={'color': c, 'fontWeight': '800', 'fontSize': '1.6rem', 'lineHeight': '1.1'}),
            html.Div(lbl, style={'color': COLORS['text_secondary'], 'fontSize': '0.60rem',
                                  'fontWeight': '600', 'letterSpacing': '0.5px',
                                  'textTransform': 'uppercase', 'marginTop': '3px'}),
        ], style={'backgroundColor': COLORS['dark_secondary'],
                  'border': f'1px solid {COLORS["dark_border"]}',
                  'borderRadius': '6px', 'padding': '10px 12px',
                  'textAlign': 'center', 'marginTop': '10px'})
    return {
        'donut':     dcc.Graph(figure=fig, config=CHART_CONFIG),
        'shot_card': _stat_box('Led to Shot', str(shots_faced), color),
        'goal_card': _stat_box('Led to Goal', str(goals_faced), '#ef4444'),
    }


def _loss_pitch_map(losses: pd.DataFrame, uirev: str) -> go.Figure:
    fig = go.Figure()
    add_pitch_background(fig, half=False)
    has_outcome = 'window_outcome' in losses.columns
    for outcome, (symbol, size) in _LOSS_OUTCOME_SYMBOLS.items():
        for loss_type, clr in _LOSS_COLORS.items():
            subset = (losses[(losses['loss_type'] == loss_type) & (losses['window_outcome'] == outcome)]
                      if has_outcome else losses[losses['loss_type'] == loss_type])
            if subset.empty:
                continue
            custom = []
            for _, row in subset.iterrows():
                player = row['player_name'] or 'Unknown'
                t_str  = f"{int(row['time_min'])}'"
                opp_line   = (f"<br>Caused by: <b>{row['opponent_player']}</b>" if row.get('opponent_player') else '')
                detail      = row.get('window_detail', '')
                detail_line = f'<br>↳ {detail}' if detail else ''
                custom.append([player, t_str, loss_type, opp_line, outcome, detail_line])
            fig.add_trace(go.Scatter(
                x=subset['x'], y=subset['y'], mode='markers',
                name=loss_type, legendgroup=f'loss_{loss_type}', showlegend=False,
                marker=dict(color=clr, symbol=symbol, size=size,
                            opacity=0.90, line=dict(color='white', width=0.8)),
                customdata=custom,
                hovertemplate=('<b>%{customdata[0]}</b><br>Time: %{customdata[1]}<br>'
                               'How: %{customdata[2]}%{customdata[3]}<br>'
                               '<b>Next 15s:</b> %{customdata[4]}%{customdata[5]}<extra></extra>'),
            ))
    for i, (lt, clr) in enumerate(_LOSS_COLORS.items()):
        fig.add_trace(go.Scatter(
            x=[None], y=[None], mode='markers', name=lt, legend='legend',
            legendgroup=f'loss_{lt}', legendgrouptitle_text='Loss Type' if i == 0 else '',
            showlegend=True, marker=dict(color=clr, symbol='circle', size=10,
                                          line=dict(color='white', width=0.8)),
        ))
    for i, (outcome, (symbol, size)) in enumerate(_LOSS_OUTCOME_SYMBOLS.items()):
        fig.add_trace(go.Scatter(
            x=[None], y=[None], mode='markers', name=outcome, legend='legend2',
            legendgroup=f'outcome_{outcome}', legendgrouptitle_text='Next 15s' if i == 0 else '',
            showlegend=True, marker=dict(color='#e2e8f0', symbol=symbol, size=size,
                                          line=dict(color='white', width=0.8)),
        ))
    _add_third_dividers(fig)
    _tc_add_attack_direction(fig)
    fig.update_layout(**_pitch_layout(uirev))
    return fig


def _loss_stats_table(losses: pd.DataFrame, color: str, top_n: int = 10) -> list:
    _no_data = [html.P("No data", style={'color': COLORS['text_secondary'], 'fontSize': '0.75rem',
                                          'textAlign': 'center', 'marginTop': '8px'})]
    if losses.empty or 'player_name' not in losses.columns:
        return _no_data
    rows_data = []
    for player, grp in losses.groupby('player_name'):
        if not player:
            continue
        rows_data.append({
            'player': player, 'total': len(grp),
            'def': int((grp['x'] < 33.33).sum()),
            'mid': int(((grp['x'] >= 33.33) & (grp['x'] < 66.67)).sum()),
            'att': int((grp['x'] >= 66.67).sum()),
            'fp':     int((grp['loss_type'] == 'Failed Pass').sum()),
            'misc':   int((grp['loss_type'] == 'Miscontrol').sum()),
            'disp':   int((grp['loss_type'] == 'Dispossessed').sum()),
            'duel':   int((grp['loss_type'] == 'Lost Duel').sum()),
            'aerial': int((grp['loss_type'] == 'Lost Aerial').sum()),
            'oth':    int((~grp['loss_type'].isin(
                ['Failed Pass', 'Miscontrol', 'Dispossessed', 'Lost Duel', 'Lost Aerial'])).sum()),
        })
    rows_data.sort(key=lambda r: r['total'], reverse=True)
    rows_data = rows_data[:top_n]
    if not rows_data:
        return _no_data
    header = html.Tr([
        html.Th('Player', style={**_TH, 'textAlign': 'left'}),
        html.Th('Tot', style=_TH), html.Th('Z1', style=_TH), html.Th('Z2', style=_TH),
        html.Th('Z3', style=_TH), html.Th('FP', style=_TH), html.Th('Mc', style=_TH),
        html.Th('Dis', style=_TH), html.Th('Duel', style=_TH), html.Th('Air', style=_TH),
        html.Th('Oth', style=_TH),
    ])
    table_rows = []
    for idx, s in enumerate(rows_data):
        bg = COLORS.get('dark_tertiary', 'rgba(255,255,255,0.03)') if idx % 2 == 0 else 'transparent'
        short = s['player'].split()[-1] if s['player'] else '—'
        table_rows.append(html.Tr([
            html.Td(short,           style=_NAME_TD),
            html.Td(str(s['total']), style={**_TD, 'color': color, 'fontWeight': '700'}),
            html.Td(str(s['def']),   style=_TD), html.Td(str(s['mid']),   style=_TD),
            html.Td(str(s['att']),   style={**_TD, 'color': GOLD}),
            html.Td(str(s['fp']),    style={**_TD, 'color': '#ef4444'}),
            html.Td(str(s['misc']),  style={**_TD, 'color': '#f97316'}),
            html.Td(str(s['disp']),  style={**_TD, 'color': '#3b82f6'}),
            html.Td(str(s['duel']),  style={**_TD, 'color': '#06b6d4'}),
            html.Td(str(s['aerial']),style={**_TD, 'color': '#8b5cf6'}),
            html.Td(str(s['oth']),   style={**_TD, 'color': COLORS['text_secondary']}),
        ], style={'backgroundColor': bg}))
    legend = html.Div(
        "Z1=Def Third · Z2=Mid Third · Z3=Att Third · FP=Failed Pass · "
        "Mc=Miscontrol · Dis=Dispossessed · Duel=Lost Duel · Air=Lost Aerial · Oth=Other",
        style={'color': COLORS['text_secondary'], 'fontSize': '0.55rem',
               'fontStyle': 'italic', 'marginBottom': '4px'},
    )
    return [legend, html.Div(html.Table([html.Thead(header), html.Tbody(table_rows)],
                                         style={'width': '100%', 'borderCollapse': 'collapse'}),
                              style={'overflowX': 'auto'})]


def _loss_zone_summary(losses: pd.DataFrame, color: str) -> list:
    if losses.empty:
        return []
    total = max(len(losses), 1)
    z1 = int((losses['x'] < 33.33).sum())
    z2 = int(((losses['x'] >= 33.33) & (losses['x'] < 66.67)).sum())
    z3 = int((losses['x'] >= 66.67).sum())

    def _row(label, count, c):
        pct = round(count / total * 100)
        return html.Div([
            html.Span(label, style={'color': COLORS['text_secondary'], 'fontSize': '0.68rem', 'minWidth': '80px'}),
            html.Div(style={'flex': '1', 'height': '6px', 'backgroundColor': COLORS['dark_border'],
                            'borderRadius': '3px', 'overflow': 'hidden', 'margin': '0 8px'}, children=[
                html.Div(style={'width': f'{pct}%', 'height': '100%', 'backgroundColor': c, 'borderRadius': '3px'}),
            ]),
            html.Span(f'{count}  ({pct}%)', style={'color': c, 'fontSize': '0.68rem',
                                                    'fontWeight': '700', 'minWidth': '60px', 'textAlign': 'right'}),
        ], style={'display': 'flex', 'alignItems': 'center', 'padding': '4px 0'})

    return [
        html.Hr(style={'borderColor': COLORS['dark_border'], 'margin': '10px 0 8px'}),
        html.Div("Losses by Zone", style={**_SECTION_TITLE, 'marginBottom': '6px'}),
        _row('Zone 1 (Def Third)', z1, color),
        _row('Zone 2 (Mid Third)', z2, GOLD),
        _row('Zone 3 (Att Third)', z3, COLORS['text_primary']),
    ]


def _def_outcome_donut(losses: pd.DataFrame, uirev: str) -> go.Figure:
    keys   = ['No Clear Threat', 'Team Recovered', 'Shot Conceded', 'Goal Conceded']
    labels = ['No Threat', 'Recovered', 'Shot', 'Goal']
    colors = ['#6b7280', HOME_COLOR, '#f97316', '#ef4444']
    col    = losses['window_outcome'] if not losses.empty and 'window_outcome' in losses.columns \
             else pd.Series(dtype=str)
    values = [int((col == k).sum()) for k in keys]
    total  = sum(values)
    fig = go.Figure(go.Pie(
        labels=labels, values=values,
        marker=dict(colors=colors, line=dict(color='rgba(0,0,0,0.2)', width=1.5)),
        hole=0.6, textinfo='label+percent', textposition='auto',
        insidetextorientation='horizontal', textfont=dict(color='white', size=12),
        hovertemplate='<b>%{label}</b>: %{value} (%{percent})<extra></extra>', sort=False,
    ))
    fig.add_annotation(text=str(total), x=0.5, y=0.5, showarrow=False,
                       font=dict(color='white', size=18, family='Arial Black'), xref='paper', yref='paper')
    fig.update_layout(
        title=dict(text='<b>Transition Outcomes</b>', x=0.5,
                   font=dict(color=COLORS['text_secondary'], size=12)),
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
        height=230, margin=dict(l=5, r=5, t=34, b=34), showlegend=True,
        legend=dict(orientation='h', x=0.5, xanchor='center', y=-0.08,
                    font=dict(color=COLORS['text_primary'], size=10),
                    bgcolor='rgba(0,0,0,0)', itemsizing='constant'),
        uirevision=uirev,
    )
    return fig


def _extract_gains(te: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, row in te.iterrows():
        etype = row.get('event_type', ''); outcome = row.get('outcome', 0)
        if etype in _GAIN_TYPES_RAW:         gain_type = etype
        elif etype == 'Tackle' and outcome == 1: gain_type = 'Tackle Won'
        else:                                    continue
        x = row.get('x', None); y = row.get('y', None)
        if pd.isna(x) or pd.isna(y):
            continue
        t_min = int(row.get('time_min', 0) or 0); t_sec = int(row.get('time_sec', 0) or 0)
        rows.append({
            'gain_type': gain_type, 'player_name': row.get('player_name', '') or '',
            'time_min': t_min, 'time_sec': t_sec, 'period_id': row.get('period_id', 1),
            'x': float(x), 'y': float(y), 'timestamp': t_min * 60 + t_sec,
        })
    return pd.DataFrame(rows) if rows else pd.DataFrame(
        columns=['gain_type', 'player_name', 'time_min', 'time_sec', 'period_id', 'x', 'y', 'timestamp'])


# ---------------------------------------------------------------------------
# Reconciled possession-transfer model (open-play turnovers only).
#
# Possession is tracked as runs of "control" events. A transfer is the moment
# control passes to the other team. Each transfer is recorded ONCE, carrying
# both a loss side (losing team) and a gain side (winning team) — so a home→away
# transfer is simultaneously a home loss and an away gain. This guarantees
#   Team A losses  ==  Team B gains  (and vice-versa).
#
# "Open-play turnovers only": transfers via a shot ending possession, dead-ball
# stoppages (out, offside, foul) or restarts (throw-in, corner, free kick, goal
# kick, keeper distribution) are dropped entirely (both sides), preserving the
# equality.
# ---------------------------------------------------------------------------
_POSSESSOR_EVENTS  = {'Pass', 'Take On', 'Ball touch', 'Ball recovery',
                      'Interception', 'Keeper pick-up', 'Keeper Sweeper'}
_SHOT_ENDED_EVENTS = {'Goal', 'Miss', 'Post', 'Saved Shot'}
_DEADBALL_BETWEEN  = {'Out', 'Corner Awarded', 'Offside Pass', 'Offside provoked',
                      'Foul', 'Card'}
_RESTART_QUALS     = ['Throw In', 'Corner taken', 'Free kick taken',
                      'Goal Kick', 'Keeper Throw', 'Gk kick from hands']

_TRANSFER_COLS = ['period_id', 'loser', 'winner',
                  'loss_type', 'loss_x', 'loss_y', 'loss_min', 'loss_sec', 'loss_ts', 'loss_player',
                  'gain_type', 'gain_x', 'gain_y', 'gain_min', 'gain_sec', 'gain_ts', 'gain_player']


def _possessor(row):
    et = row.get('event_type', '')
    if et in _POSSESSOR_EVENTS or et in _SHOT_ENDED_EVENTS:
        return row.get('team_position', None)
    if et == 'Tackle' and row.get('outcome', 0) == 1:
        return row.get('team_position', None)
    return None


def _is_restart(row) -> bool:
    if row.get('event_type', '') != 'Pass':
        return False
    return any(row.get(q, 'N/A') == 'Si' for q in _RESTART_QUALS)


def _classify_loss(loser_last, loser_neutral):
    """(loss_type, marker_row) from the losing team's boundary events."""
    for r in loser_neutral:
        if r.get('event_type', '') == 'Dispossessed': return 'Dispossessed', r
    for r in loser_neutral:
        if r.get('event_type', '') == 'Miscontrol':   return 'Miscontrol', r
    et = loser_last.get('event_type', '')
    if et == 'Pass' and loser_last.get('outcome', 1) == 0:
        return 'Failed Pass', loser_last
    if et == 'Take On' and loser_last.get('outcome', 1) == 0:
        return 'Dispossessed', loser_last
    for r in loser_neutral:
        if r.get('event_type', '') == 'Aerial' and r.get('outcome', 1) == 0:
            return 'Lost Aerial', r
    for r in loser_neutral:
        if r.get('event_type', '') == 'Challenge' and r.get('outcome', 1) == 0:
            return 'Lost Duel', r
    return 'Other', loser_last


def _classify_gain(winner_event) -> str:
    et = winner_event.get('event_type', '')
    if et == 'Ball recovery': return 'Ball recovery'
    if et == 'Interception':  return 'Interception'
    if et == 'Tackle':        return 'Tackle Won'
    return 'Other'


def _extract_possession_transfers(events: pd.DataFrame) -> pd.DataFrame:
    if events.empty or 'team_position' not in events.columns:
        return pd.DataFrame(columns=_TRANSFER_COLS)
    df = events.copy()
    for c in ('x', 'y'):
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors='coerce')
    df = df.sort_values(['period_id', 'time_min', 'time_sec'], kind='stable').reset_index(drop=True)

    def _ts(r):
        return int(r.get('time_min', 0) or 0) * 60 + int(r.get('time_sec', 0) or 0)

    transfers = []
    cur_team = loser_last = None
    neutral_buf = []
    deadball_flag = False
    cur_period = None

    for _, row in df.iterrows():
        period = row.get('period_id', 1)
        if period != cur_period:
            cur_period, cur_team, loser_last = period, None, None
            neutral_buf, deadball_flag = [], False
        p = _possessor(row)
        if p is None:
            neutral_buf.append(row)
            if row.get('event_type', '') in _DEADBALL_BETWEEN:
                deadball_flag = True
            continue
        if cur_team is None or p == cur_team:
            cur_team, loser_last = p, row
            neutral_buf, deadball_flag = [], False
            continue
        # possession flipped: cur_team -> p
        shot_ended = loser_last.get('event_type', '') in _SHOT_ENDED_EVENTS
        if not (shot_ended or deadball_flag or _is_restart(row)):
            loser_neutral = [r for r in neutral_buf if r.get('team_position', '') == cur_team]
            loss_type, marker = _classify_loss(loser_last, loser_neutral)
            transfers.append({
                'period_id': period, 'loser': cur_team, 'winner': p,
                'loss_type': loss_type,
                'loss_x': marker.get('x'), 'loss_y': marker.get('y'),
                'loss_min': int(marker.get('time_min', 0) or 0),
                'loss_sec': int(marker.get('time_sec', 0) or 0),
                'loss_ts': _ts(marker), 'loss_player': marker.get('player_name', '') or '',
                'gain_type': _classify_gain(row),
                'gain_x': row.get('x'), 'gain_y': row.get('y'),
                'gain_min': int(row.get('time_min', 0) or 0),
                'gain_sec': int(row.get('time_sec', 0) or 0),
                'gain_ts': _ts(row), 'gain_player': row.get('player_name', '') or '',
            })
        cur_team, loser_last = p, row
        neutral_buf, deadball_flag = [], False

    out = pd.DataFrame(transfers, columns=_TRANSFER_COLS)
    out = out.dropna(subset=['loss_x', 'loss_y', 'gain_x', 'gain_y']).reset_index(drop=True)

    # Refine 'Other' gains: when the winning team also logs a recovery-type event
    # at the same second as the transfer (an Opta ordering artifact where a plain
    # pass/touch was listed first), credit the recovery instead. Relabels the gain
    # side only — never adds/removes a transfer, so conservation is preserved.
    if not out.empty:
        rec = df[df['event_type'].isin(['Ball recovery', 'Interception', 'Tackle'])].copy()
        if 'outcome' in rec.columns:
            rec = rec[(rec['event_type'] != 'Tackle') | (rec['outcome'] == 1)]
        if not rec.empty:
            rec['_ts'] = rec['time_min'].fillna(0).astype(int) * 60 + rec['time_sec'].fillna(0).astype(int)
            _prio = {'Ball recovery': 0, 'Interception': 1, 'Tackle': 2}
            rec = rec.assign(_prio=rec['event_type'].map(_prio)).sort_values('_prio')
            recmap = {}
            for _, rr in rec.iterrows():
                k = (rr['period_id'], int(rr['_ts']), rr['team_position'])
                recmap.setdefault(k, rr)

            def _refine(t):
                if t['gain_type'] != 'Other':
                    return t
                rr = recmap.get((t['period_id'], int(t['gain_ts']), t['winner']))
                if rr is None:
                    return t
                t['gain_type']   = 'Tackle Won' if rr['event_type'] == 'Tackle' else rr['event_type']
                t['gain_player'] = rr.get('player_name', '') or t['gain_player']
                if pd.notna(rr.get('x')) and pd.notna(rr.get('y')):
                    t['gain_x'], t['gain_y'] = rr.get('x'), rr.get('y')
                return t

            out = out.apply(_refine, axis=1)
    return out


def _transfer_loss_view(transfers: pd.DataFrame, loser_pos: str) -> pd.DataFrame:
    sub = transfers[transfers['loser'] == loser_pos] if not transfers.empty else transfers
    return pd.DataFrame({
        'loss_type':   sub['loss_type'].values if not sub.empty else [],
        'player_name': sub['loss_player'].values if not sub.empty else [],
        'time_min':    sub['loss_min'].values if not sub.empty else [],
        'time_sec':    sub['loss_sec'].values if not sub.empty else [],
        'period_id':   sub['period_id'].values if not sub.empty else [],
        'x':           sub['loss_x'].values if not sub.empty else [],
        'y':           sub['loss_y'].values if not sub.empty else [],
        'timestamp':   sub['loss_ts'].values if not sub.empty else [],
    })


def _transfer_gain_view(transfers: pd.DataFrame, winner_pos: str) -> pd.DataFrame:
    sub = transfers[transfers['winner'] == winner_pos] if not transfers.empty else transfers
    return pd.DataFrame({
        'gain_type':   sub['gain_type'].values if not sub.empty else [],
        'player_name': sub['gain_player'].values if not sub.empty else [],
        'time_min':    sub['gain_min'].values if not sub.empty else [],
        'time_sec':    sub['gain_sec'].values if not sub.empty else [],
        'period_id':   sub['period_id'].values if not sub.empty else [],
        'x':           sub['gain_x'].values if not sub.empty else [],
        'y':           sub['gain_y'].values if not sub.empty else [],
        'timestamp':   sub['gain_ts'].values if not sub.empty else [],
    })


def _team_events_in_windows(gains: pd.DataFrame, te: pd.DataFrame) -> pd.DataFrame:
    if gains.empty or te.empty:
        return pd.DataFrame()
    te = te.copy()
    te['_ts'] = te['time_min'].fillna(0).astype(int) * 60 + te['time_sec'].fillna(0).astype(int)
    parts = []
    for period_id, grp in gains.groupby('period_id'):
        te_sl = te[te['period_id'] == period_id]
        if te_sl.empty:
            continue
        for t_gain in grp['timestamp']:
            window = te_sl[(te_sl['_ts'] > t_gain) & (te_sl['_ts'] <= t_gain + _TRANSITION_WINDOW_SEC)]
            parts.append(window)
    if not parts:
        return pd.DataFrame()
    return pd.concat(parts, ignore_index=True).drop_duplicates()


def _tag_gain_outcomes(gains: pd.DataFrame, te: pd.DataFrame) -> pd.DataFrame:
    if gains.empty:
        gains = gains.copy()
        gains['window_outcome'] = ''; gains['window_detail'] = ''
        return gains
    te = te.copy()
    te['_ts'] = te['time_min'].fillna(0).astype(int) * 60 + te['time_sec'].fillna(0).astype(int)
    _loss_events = _POSS_LOSS_EVENTS[:]
    all_outcomes: dict = {}; all_details: dict = {}
    for period_id, grp in gains.groupby('period_id'):
        te_sl = te[te['period_id'] == period_id]
        for idx, gain_row in grp.iterrows():
            t0 = int(gain_row['timestamp']); t1 = t0 + _TRANSITION_WINDOW_SEC
            te_win = te_sl[(te_sl['_ts'] > t0) & (te_sl['_ts'] <= t1)]
            has_goal     = not te_win.empty and (te_win['event_type'] == 'Goal').any()
            has_shot     = not te_win.empty and te_win['event_type'].isin(_SHOT_TYPES).any()
            has_turnover = not te_win.empty and (
                te_win['event_type'].isin(_loss_events).any() or
                (not te_win[te_win['event_type'] == 'Pass'].empty and
                 te_win[te_win['event_type'] == 'Pass']['outcome'].eq(0).any()) or
                ((te_win['event_type'] == 'Challenge') & (te_win['outcome'] == 0)).any()
            )
            if has_goal:
                goal_rows = te_win[te_win['event_type'] == 'Goal']
                scorer  = goal_rows['player_name'].iloc[0] if not goal_rows.empty else ''
                outcome = 'Goal Scored'; detail = f'by {scorer}' if scorer else ''
            elif has_shot:
                shot_rows = te_win[te_win['event_type'].isin(_SHOT_TYPES)]
                shooter   = shot_rows['player_name'].iloc[0] if not shot_rows.empty else ''
                shot_type = shot_rows['event_type'].iloc[0]  if not shot_rows.empty else ''
                outcome = 'Shot Taken'; detail = f'{shot_type} — {shooter}' if shooter else shot_type
            elif has_turnover:
                outcome = 'Quick Turnover'; detail = ''
            else:
                outcome = 'Possession Held'; detail = ''
            all_outcomes[idx] = outcome; all_details[idx] = detail
    gains = gains.copy()
    gains['window_outcome'] = gains.index.map(lambda i: all_outcomes.get(i, 'Possession Held'))
    gains['window_detail']  = gains.index.map(lambda i: all_details.get(i, ''))
    return gains


def _gains_zone_donut_card(gains: pd.DataFrame, te_in_windows: pd.DataFrame, color: str) -> list:
    z1 = int((gains['x'] < 33.33).sum())                                if not gains.empty else 0
    z2 = int(((gains['x'] >= 33.33) & (gains['x'] < 66.67)).sum())     if not gains.empty else 0
    z3 = int((gains['x'] >= 66.67).sum())                               if not gains.empty else 0
    total = z1 + z2 + z3
    fig = go.Figure(go.Pie(
        labels=['Def 3rd', 'Mid 3rd', 'Att 3rd'],
        values=[z1, z2, z3] if total > 0 else [1, 1, 1], hole=0.6,
        marker=dict(colors=['#6b7280', '#f97316', '#22c55e'],
                    line=dict(color='rgba(0,0,0,0.2)', width=1.5)),
        textinfo='label+percent', textposition='auto', insidetextorientation='horizontal',
        textfont=dict(color='white', size=12),
        hovertemplate='<b>%{label}</b>: %{value} (%{percent})<extra></extra>', sort=False,
    ))
    fig.add_annotation(text=str(total), x=0.5, y=0.55, showarrow=False,
                       font=dict(color='white', size=18, family='Arial Black'), xref='paper', yref='paper')
    fig.add_annotation(text='Total Gains', x=0.5, y=0.43, showarrow=False,
                       font=dict(color=COLORS['text_secondary'], size=10), xref='paper', yref='paper')
    fig.update_layout(
        paper_bgcolor='rgba(0,0,0,0)', showlegend=True,
        legend=dict(orientation='h', x=0.5, xanchor='center', y=-0.08,
                    font=dict(color=COLORS['text_primary'], size=10),
                    bgcolor='rgba(0,0,0,0)', itemsizing='constant'),
        margin=dict(l=5, r=5, t=34, b=34), height=230,
    )
    if not te_in_windows.empty and 'event_type' in te_in_windows.columns:
        shots_taken  = int(te_in_windows['event_type'].isin(_SHOT_TYPES).sum())
        goals_scored = int((te_in_windows['event_type'] == 'Goal').sum())
    else:
        shots_taken = goals_scored = 0
    col = gains['window_outcome'] if not gains.empty and 'window_outcome' in gains.columns \
          else pd.Series(dtype=str)
    quick_turnovers = int((col == 'Quick Turnover').sum())
    stats = [('Led to Shot', str(shots_taken), GOLD), ('Led to Goal', str(goals_scored), '#22c55e'),
             ('Quick Turnovers', str(quick_turnovers), AWAY_COLOR)]
    stats_panel = html.Div([
        html.Div([
            html.Div(val, style={'color': c, 'fontWeight': '800', 'fontSize': '1.6rem', 'lineHeight': '1.1'}),
            html.Div(lbl, style={'color': COLORS['text_secondary'], 'fontSize': '0.60rem',
                                  'fontWeight': '600', 'letterSpacing': '0.5px',
                                  'textTransform': 'uppercase', 'marginTop': '3px'}),
        ], style={'backgroundColor': COLORS['dark_secondary'],
                  'border': f'1px solid {COLORS["dark_border"]}',
                  'borderRadius': '6px', 'padding': '10px 12px', 'flex': '1'})
        for lbl, val, c in stats
    ], style={'display': 'flex', 'flexDirection': 'row', 'gap': '8px',
              'justifyContent': 'center', 'marginTop': '10px'})
    return [
        dcc.Graph(figure=fig, config=CHART_CONFIG, style={'width': '100%'}),
        stats_panel,
    ]


def _gain_pitch_map(gains: pd.DataFrame, uirev: str) -> go.Figure:
    fig = go.Figure()
    add_pitch_background(fig, half=False)
    has_outcome = 'window_outcome' in gains.columns
    for outcome, (symbol, size) in _GAIN_OUTCOME_SYMBOLS.items():
        for gain_type, clr in _GAIN_COLORS.items():
            subset = (gains[(gains['gain_type'] == gain_type) & (gains['window_outcome'] == outcome)]
                      if has_outcome else gains[gains['gain_type'] == gain_type])
            if subset.empty:
                continue
            custom = []
            for _, row in subset.iterrows():
                player = row['player_name'] or 'Unknown'; t_str = f"{int(row['time_min'])}'"
                detail = row.get('window_detail', ''); detail_line = f'<br>↳ {detail}' if detail else ''
                custom.append([player, t_str, gain_type, outcome, detail_line])
            fig.add_trace(go.Scatter(
                x=subset['x'], y=subset['y'], mode='markers',
                name=gain_type, legendgroup=f'gain_{gain_type}', showlegend=False,
                marker=dict(color=clr, symbol=symbol, size=size,
                            opacity=0.90, line=dict(color='white', width=0.8)),
                customdata=custom,
                hovertemplate=('<b>%{customdata[0]}</b><br>Time: %{customdata[1]}<br>'
                               'How: %{customdata[2]}<br><b>Next 15s:</b> %{customdata[3]}'
                               '%{customdata[4]}<extra></extra>'),
            ))
    for i, (gt, clr) in enumerate(_GAIN_COLORS.items()):
        fig.add_trace(go.Scatter(
            x=[None], y=[None], mode='markers', name=gt, legend='legend',
            legendgroup=f'gain_{gt}', legendgrouptitle_text='Gain Type' if i == 0 else '',
            showlegend=True, marker=dict(color=clr, symbol='circle', size=10,
                                          line=dict(color='white', width=0.8)),
        ))
    for i, (outcome, (symbol, size)) in enumerate(_GAIN_OUTCOME_SYMBOLS.items()):
        fig.add_trace(go.Scatter(
            x=[None], y=[None], mode='markers', name=outcome, legend='legend2',
            legendgroup=f'outcome_{outcome}', legendgrouptitle_text='Next 15s' if i == 0 else '',
            showlegend=True, marker=dict(color='#e2e8f0', symbol=symbol, size=size,
                                          line=dict(color='white', width=0.8)),
        ))
    _add_third_dividers(fig)
    _tc_add_attack_direction(fig)
    fig.update_layout(**_pitch_layout(uirev))
    return fig


def _gain_stats_table(gains: pd.DataFrame, color: str, top_n: int = 10) -> list:
    _no_data = [html.P("No data", style={'color': COLORS['text_secondary'], 'fontSize': '0.75rem',
                                          'textAlign': 'center', 'marginTop': '8px'})]
    if gains.empty or 'player_name' not in gains.columns:
        return _no_data
    rows_data = []
    for player, grp in gains.groupby('player_name'):
        if not player:
            continue
        rows_data.append({
            'player': player, 'total': len(grp),
            'z1': int((grp['x'] < 33.33).sum()),
            'z2': int(((grp['x'] >= 33.33) & (grp['x'] < 66.67)).sum()),
            'z3': int((grp['x'] >= 66.67).sum()),
            'br':  int((grp['gain_type'] == 'Ball recovery').sum()),
            'int': int((grp['gain_type'] == 'Interception').sum()),
            'tkl': int((grp['gain_type'] == 'Tackle Won').sum()),
            'oth': int((~grp['gain_type'].isin(['Ball recovery', 'Interception', 'Tackle Won'])).sum()),
        })
    rows_data.sort(key=lambda r: r['total'], reverse=True)
    rows_data = rows_data[:top_n]
    if not rows_data:
        return _no_data
    header = html.Tr([
        html.Th('Player', style={**_TH, 'textAlign': 'left'}),
        html.Th('Tot', style=_TH), html.Th('Z1', style=_TH), html.Th('Z2', style=_TH),
        html.Th('Z3', style=_TH), html.Th('BR', style=_TH), html.Th('Int', style=_TH),
        html.Th('Tkl', style=_TH), html.Th('Oth', style=_TH),
    ])
    table_rows = []
    for idx, s in enumerate(rows_data):
        bg = COLORS.get('dark_tertiary', 'rgba(255,255,255,0.03)') if idx % 2 == 0 else 'transparent'
        short = s['player'].split()[-1] if s['player'] else '—'
        table_rows.append(html.Tr([
            html.Td(short,           style=_NAME_TD),
            html.Td(str(s['total']), style={**_TD, 'color': color, 'fontWeight': '700'}),
            html.Td(str(s['z1']),    style=_TD), html.Td(str(s['z2']), style=_TD),
            html.Td(str(s['z3']),    style={**_TD, 'color': GOLD}),
            html.Td(str(s['br']),    style={**_TD, 'color': '#22c55e'}),
            html.Td(str(s['int']),   style={**_TD, 'color': '#3b82f6'}),
            html.Td(str(s['tkl']),   style={**_TD, 'color': GOLD}),
            html.Td(str(s['oth']),   style={**_TD, 'color': COLORS['text_secondary']}),
        ], style={'backgroundColor': bg}))
    legend = html.Div(
        "Z1=Def Third · Z2=Mid Third · Z3=Att Third · BR=Ball recovery · Int=Interception · Tkl=Tackle Won · Oth=Other",
        style={'color': COLORS['text_secondary'], 'fontSize': '0.55rem',
               'fontStyle': 'italic', 'marginBottom': '4px'},
    )
    return [legend, html.Div(html.Table([html.Thead(header), html.Tbody(table_rows)],
                                         style={'width': '100%', 'borderCollapse': 'collapse'}),
                              style={'overflowX': 'auto'})]


def _gain_zone_summary(gains: pd.DataFrame, color: str) -> list:
    if gains.empty:
        return []
    total = max(len(gains), 1)
    z1 = int((gains['x'] < 33.33).sum())
    z2 = int(((gains['x'] >= 33.33) & (gains['x'] < 66.67)).sum())
    z3 = int((gains['x'] >= 66.67).sum())

    def _row(label, count, c):
        pct = round(count / total * 100)
        return html.Div([
            html.Span(label, style={'color': COLORS['text_secondary'], 'fontSize': '0.68rem', 'minWidth': '80px'}),
            html.Div(style={'flex': '1', 'height': '6px', 'backgroundColor': COLORS['dark_border'],
                            'borderRadius': '3px', 'overflow': 'hidden', 'margin': '0 8px'}, children=[
                html.Div(style={'width': f'{pct}%', 'height': '100%', 'backgroundColor': c, 'borderRadius': '3px'}),
            ]),
            html.Span(f'{count}  ({pct}%)', style={'color': c, 'fontSize': '0.68rem',
                                                    'fontWeight': '700', 'minWidth': '60px', 'textAlign': 'right'}),
        ], style={'display': 'flex', 'alignItems': 'center', 'padding': '4px 0'})

    return [
        html.Hr(style={'borderColor': COLORS['dark_border'], 'margin': '10px 0 8px'}),
        html.Div("Gains by Zone", style={**_SECTION_TITLE, 'marginBottom': '6px'}),
        _row('Zone 1 (Def Third)', z1, AWAY_COLOR),
        _row('Zone 2 (Mid Third)', z2, GOLD),
        _row('Zone 3 (Att Third)', z3, color),
    ]


def _atk_outcome_donut(gains: pd.DataFrame, uirev: str) -> go.Figure:
    keys   = ['Possession Held', 'Quick Turnover', 'Shot Taken', 'Goal Scored']
    labels = ['Held', 'Turnover', 'Shot', 'Goal']
    colors = ['#6b7280', AWAY_COLOR, GOLD, '#22c55e']
    col    = gains['window_outcome'] if not gains.empty and 'window_outcome' in gains.columns \
             else pd.Series(dtype=str)
    values = [int((col == k).sum()) for k in keys]
    total  = sum(values)
    fig = go.Figure(go.Pie(
        labels=labels, values=values,
        marker=dict(colors=colors, line=dict(color='rgba(0,0,0,0.2)', width=1.5)),
        hole=0.6, textinfo='label+percent', textposition='auto',
        insidetextorientation='horizontal', textfont=dict(color='white', size=12),
        hovertemplate='<b>%{label}</b>: %{value} (%{percent})<extra></extra>', sort=False,
    ))
    fig.add_annotation(text=str(total), x=0.5, y=0.5, showarrow=False,
                       font=dict(color='white', size=18, family='Arial Black'), xref='paper', yref='paper')
    fig.update_layout(
        title=dict(text='<b>Transition Outcomes</b>', x=0.5,
                   font=dict(color=COLORS['text_secondary'], size=12)),
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
        height=230, margin=dict(l=5, r=5, t=34, b=34), showlegend=True,
        legend=dict(orientation='h', x=0.5, xanchor='center', y=-0.08,
                    font=dict(color=COLORS['text_primary'], size=10),
                    bgcolor='rgba(0,0,0,0)', itemsizing='constant'),
        uirevision=uirev,
    )
    return fig


def build_transitions_counterpressing_tab(events: pd.DataFrame, **_) -> html.Div:
    if events.empty:
        return html.P("No event data.", style={"color": COLORS["text_secondary"]})

    home_team = events['home_team'].iloc[0] if 'home_team' in events.columns else 'Home'
    away_team = events['away_team'].iloc[0] if 'away_team' in events.columns else 'Away'
    home_te = events[events['team_position'] == 'home']
    away_te = events[events['team_position'] == 'away']

    # Reconciled possession transfers (open-play only) — each counted once, so
    # home losses == away gains and away losses == home gains by construction.
    transfers   = _extract_possession_transfers(events)
    home_losses = _transfer_loss_view(transfers, 'home')   # == away gains
    away_losses = _transfer_loss_view(transfers, 'away')   # == home gains
    home_gains  = _transfer_gain_view(transfers, 'home')
    away_gains  = _transfer_gain_view(transfers, 'away')

    home_opp_win = _opp_events_in_windows(home_losses, away_te)
    home_losses  = _tag_loss_outcomes(home_losses, home_te, away_te)
    away_opp_win = _opp_events_in_windows(away_losses, home_te)
    away_losses  = _tag_loss_outcomes(away_losses, away_te, home_te)

    home_te_win = _team_events_in_windows(home_gains, home_te)
    home_gains  = _tag_gain_outcomes(home_gains, home_te)
    away_te_win = _team_events_in_windows(away_gains, away_te)
    away_gains  = _tag_gain_outcomes(away_gains, away_te)

    def _hm(df, color):
        valid = df.dropna(subset=['x', 'y'])
        if len(valid) < 2:
            return _SKEL_SRC
        return render_xt_heatmap_img(valid['x'].values, valid['y'].values, [1.0] * len(valid))

    def _name(label, color):
        return html.Div(label, style={'color': color, 'fontWeight': '700',
                                      'fontSize': '0.85rem', 'marginBottom': '8px'})

    _tbl_cap = {'color': COLORS['text_secondary'], 'fontSize': '0.72rem', 'fontWeight': '700',
                'textTransform': 'uppercase', 'letterSpacing': '0.5px', 'margin': '14px 0 6px'}

    def _panel(team, color, losses, opp_win, uirev, gains):
        zc = _losses_zone_donut_card(losses, opp_win, color)
        return dbc.Col(html.Div([
            _name(team, color),
            dbc.Row([
                dbc.Col(html.Div([
                    zc['donut'],
                    zc['shot_card'],
                ]), md=6, className='p-1'),
                dbc.Col(html.Div([
                    dcc.Graph(figure=_def_outcome_donut(losses, uirev),
                              config=CHART_CONFIG),
                    zc['goal_card'],
                ]), md=6, className='p-1'),
            ], className='g-2', align='start'),
            html.Hr(style={'borderColor': COLORS['dark_border'], 'margin': '10px 0 0'}),
            html.Div('Losses by Player', style=_tbl_cap),
            *_loss_stats_table(losses, color),
            html.Div('Gains by Player', style=_tbl_cap),
            *_gain_stats_table(gains, color),
        ], style=CARD_STYLE), md=6, className='mb-3')

    return html.Div([
        section_header('Transitions'),
        build_info_box('Open-play possession transfers — losses by zone with opponent threat and how each 15s '
                       'window resolved, plus per-player loss and gain breakdowns. '
                       'FP=Failed Pass · Mc=Miscontrol · Dis=Dispossessed · Duel=Lost Duel · Air=Lost Aerial · '
                       'BR=Ball recovery · Int=Interception · Tkl=Tackle Won · Oth=Other'),
        dbc.Row([
            _panel(home_team, HOME_COLOR, home_losses, home_opp_win, 'def-donut-home', home_gains),
            _panel(away_team, AWAY_COLOR, away_losses, away_opp_win, 'def-donut-away', away_gains),
        ], className='g-3'),
    ], style={'marginTop': '16px'})


def register_transitions_counterpressing_callbacks(app) -> None:
    pass

# ============================================================================
# ===== goalkeeping.py =====
# ============================================================================
import pandas as pd
import plotly.graph_objects as go
from dash import html, dcc
from dash.dependencies import Input, Output, State
import dash_bootstrap_components as dbc

from utils.config import COLORS
from utils.data_utils import get_match_events, exclude_own_goals, count_goals
from utils.xg_utils import add_xg_column
from page_utils.visualizations import (
    HOME_COLOR, AWAY_COLOR, GOLD, CHART_CONFIG,
    layout_config, add_pitch_background, add_vertical_half_pitch_background,
    PITCH_AXIS_FULL, VPITCH_AXIS_HALF,
)
from page_utils.event_filters import SHOT_TYPES

_SAVE_COLOR = '#51cf66'
_GOAL_COLOR = '#ff6b6b'
_MISS_COLOR = '#868e96'

_GM_CENTER  = 50.0
_GM_X_SCALE = 2.5
_GOAL_LEFT  = _GM_CENTER + (44.5 - _GM_CENTER) * _GM_X_SCALE
_GOAL_RIGHT = _GM_CENTER + (55.5 - _GM_CENTER) * _GM_X_SCALE
_CROSSBAR_Z = 38.0
_GM_Y_COL   = 'Goal Mouth Y Coordinate'
_GM_Z_COL   = 'Goal Mouth Z Coordinate'

_GK_OUTCOME_COLOR = {
    'Goal':         _GOAL_COLOR,
    'Saved Shot':   _SAVE_COLOR,
    'Post':         '#ffd43b',
    'Blocked Shot': '#cc5de8',
    'Miss':         _MISS_COLOR,
}
_GK_OUTCOME_SYMBOL = {
    'Goal':         'star',
    'Saved Shot':   'circle',
    'Post':         'diamond',
    'Blocked Shot': 'square',
    'Miss':         'x',
}

_GK_X_THRESHOLD = 20
_BARCA_BLUE   = '#004D98'
_BARCA_GARNET = '#A50044'


def _identify_gks(te_gk: pd.DataFrame) -> list:
    if 'player_name' not in te_gk.columns or 'x' not in te_gk.columns:
        return []
    avg_x = (
        te_gk.dropna(subset=['player_name', 'x'])
        .groupby('player_name')['x'].mean()
        .sort_values()
    )
    if avg_x.empty:
        return []
    primary    = avg_x.index[0]
    candidates = avg_x[avg_x < _GK_X_THRESHOLD].index.tolist()
    if primary not in candidates:
        candidates = [primary] + candidates
    if 'time_min' in te_gk.columns and len(candidates) > 1:
        first_t: dict = {}
        for n in candidates:
            t = pd.to_numeric(te_gk.loc[te_gk['player_name'] == n, 'time_min'], errors='coerce').dropna()
            first_t[n] = float(t.min()) if not t.empty else 999.0
        candidates.sort(key=lambda n: first_t[n])
    return candidates


def _gk_boundaries(gk_names: list, te_gk: pd.DataFrame) -> list:
    if len(gk_names) <= 1 or 'time_min' not in te_gk.columns:
        return []
    last_t: dict = {}; first_t: dict = {}
    for n in gk_names:
        t = pd.to_numeric(te_gk.loc[te_gk['player_name'] == n, 'time_min'], errors='coerce').dropna()
        if not t.empty:
            first_t[n] = float(t.min()); last_t[n] = float(t.max())
    return [
        (last_t.get(gk_names[i], 45.0) + first_t.get(gk_names[i + 1], 46.0)) / 2
        for i in range(len(gk_names) - 1)
    ]


def _gk_compute(events: pd.DataFrame) -> dict:
    home_team = events['home_team'].iloc[0]
    away_team = events['away_team'].iloc[0]
    all_goals = events[events['event_type'] == 'Goal']
    home_goals_total, away_goals_total = count_goals(all_goals)
    out = {}
    for gk_pos, opp_pos, gk_team in (
        ('home', 'away', home_team),
        ('away', 'home', away_team),
    ):
        te_gk  = events[events['team_position'] == gk_pos]
        te_opp = events[events['team_position'] == opp_pos]
        opp_shots = exclude_own_goals(te_opp[te_opp['event_type'].isin(SHOT_TYPES)].copy())
        gk_goals_df = te_gk[te_gk['event_type'] == 'Goal'].copy()
        if 'own goal' in gk_goals_df.columns:
            own_ogs = gk_goals_df[gk_goals_df['own goal'] == 'Si'].copy()
        else:
            own_ogs = gk_goals_df.iloc[:0]
        if not own_ogs.empty:
            if 'x' in own_ogs.columns:
                own_ogs['x'] = 100 - pd.to_numeric(own_ogs['x'], errors='coerce')
            shots_faced_all = pd.concat([opp_shots, own_ogs], ignore_index=True)
        else:
            shots_faced_all = opp_shots
        saves_total      = len(te_opp[te_opp['event_type'] == 'Saved Shot'])
        goals_conc_total = away_goals_total if gk_pos == 'home' else home_goals_total
        sot_total        = saves_total + goals_conc_total
        save_pct_total   = round(saves_total / sot_total * 100, 1) if sot_total > 0 else 0.0
        gk_names   = _identify_gks(te_gk)
        boundaries = _gk_boundaries(gk_names, te_gk)

        def _in_range(df: pd.DataFrame, t0: float, t1):
            if 'time_min' not in df.columns or not boundaries:
                return df
            t    = pd.to_numeric(df['time_min'], errors='coerce')
            mask = t >= t0
            if t1 is not None:
                mask &= (t < t1)
            return df[mask]

        gk_list: list = []
        for i, name in enumerate(gk_names):
            t0: float = 0.0 if i == 0 else boundaries[i - 1]
            t1        = boundaries[i] if i < len(boundaries) else None
            gk_shots  = _in_range(shots_faced_all, t0, t1)
            saved_in  = _in_range(te_opp[te_opp['event_type'] == 'Saved Shot'], t0, t1)
            goals_evt = _in_range(events[events['event_type'] == 'Goal'], t0, t1)
            hg, ag    = count_goals(goals_evt)
            gk_goals  = ag if gk_pos == 'home' else hg
            gk_saves  = len(saved_in)
            gk_sot    = gk_saves + gk_goals
            gk_sv_pct = round(gk_saves / gk_sot * 100, 1) if gk_sot > 0 else 0.0
            gk_evts   = te_gk[te_gk['player_name'] == name]
            passes    = gk_evts[gk_evts['event_type'] == 'Pass'].copy()
            passes_df = (
                passes if (not passes.empty and 'Pass End X' in passes.columns
                           and 'Pass End Y' in passes.columns) else pd.DataFrame()
            )
            t_label = ''
            if boundaries:
                t_label = f"{int(t0)}'–{int(t1)}'" if t1 is not None else f"{int(t0)}'–FT"
            gk_list.append({
                'name':            name,
                'shots_faced':     gk_shots,
                'gk_passes_df':    passes_df,
                'total_shots':     len(gk_shots),
                'shots_on_target': gk_sot,
                'saves':           gk_saves,
                'goals_conceded':  gk_goals,
                'save_pct':        gk_sv_pct,
                'xg_against':      round(add_xg_column(gk_shots)['xg'].sum(), 2)
                                   if not gk_shots.empty else 0.0,
                'time_label':      t_label,
            })
        xga_total = round(add_xg_column(shots_faced_all)['xg'].sum(), 2) \
            if not shots_faced_all.empty else 0.0
        if not gk_list:
            gk_list = [{
                'name':            '—',
                'shots_faced':     shots_faced_all,
                'gk_passes_df':    pd.DataFrame(),
                'total_shots':     len(shots_faced_all),
                'shots_on_target': sot_total,
                'saves':           saves_total,
                'goals_conceded':  goals_conc_total,
                'save_pct':        save_pct_total,
                'xg_against':      xga_total,
                'time_label':      '',
            }]
        out[gk_pos] = {
            'team':             gk_team,
            'total_shots':      len(shots_faced_all),
            'shots_on_target':  sot_total,
            'saves':            saves_total,
            'goals_conceded':   goals_conc_total,
            'save_pct':         save_pct_total,
            'xg_against':       xga_total,
            'gk_name':          gk_list[0]['name'],
            'opp_shots_df':     shots_faced_all,
            'gk_passes_df':     gk_list[0]['gk_passes_df'],
            'gk_list':          gk_list,
        }
    return out


def _half_stats(events: pd.DataFrame, gk_pos: str, opp_pos: str) -> dict:
    te_opp = events[events['team_position'] == opp_pos]
    saved  = te_opp[te_opp['event_type'] == 'Saved Shot']
    half_goals = events[events['event_type'] == 'Goal']
    hg, ag     = count_goals(half_goals)
    goals_conc = ag if gk_pos == 'home' else hg
    shots      = exclude_own_goals(te_opp[te_opp['event_type'].isin(SHOT_TYPES)].copy())
    sot = len(saved) + goals_conc
    return {
        'total_shots':      len(shots),
        'shots_on_target':  sot,
        'saves':            len(saved),
        'goals_conceded':   goals_conc,
        'save_pct':         round(len(saved) / sot * 100, 1) if sot > 0 else 0.0,
        'xg_against':       round(add_xg_column(shots)['xg'].sum(), 2) if not shots.empty else 0.0,
    }


def _team_shots(team_data: dict, gk_filter: str) -> pd.DataFrame:
    if gk_filter in ('all', None, ''):
        return team_data['opp_shots_df']
    try:
        idx = int(gk_filter)
        if 0 <= idx < len(team_data['gk_list']):
            return team_data['gk_list'][idx]['shots_faced']
    except (ValueError, IndexError):
        pass
    return team_data['opp_shots_df']


def _team_passes(team_data: dict, gk_filter: str) -> tuple:
    if gk_filter in ('all', None, ''):
        frames = [gk['gk_passes_df'] for gk in team_data['gk_list']
                  if not gk['gk_passes_df'].empty]
        combined = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
        return combined, 'All GKs'
    try:
        idx = int(gk_filter)
        if 0 <= idx < len(team_data['gk_list']):
            gk = team_data['gk_list'][idx]
            return gk['gk_passes_df'], gk['name']
    except (ValueError, IndexError):
        pass
    return team_data['gk_passes_df'], team_data['gk_name']


def _plot_title(team_data: dict, gk_filter: str) -> str:
    if gk_filter in ('all', None, ''):
        return team_data['team']
    try:
        idx = int(gk_filter)
        if 0 <= idx < len(team_data['gk_list']):
            gk = team_data['gk_list'][idx]
            label = f"{team_data['team']}: {gk['name']}"
            if gk['time_label']:
                label += f" ({gk['time_label']})"
            return label
    except (ValueError, IndexError):
        pass
    return team_data['team']


def _make_donut(values: list, labels: list, colors: list,
                center_text: str, title: str) -> go.Figure:
    fig = go.Figure(go.Pie(
        values=values, labels=labels, hole=0.6,
        marker=dict(colors=colors, line=dict(color='rgba(0,0,0,0.2)', width=1.5)),
        textinfo='label+percent', textposition='auto', insidetextorientation='horizontal',
        textfont=dict(color='white', size=12),
        hovertemplate='<b>%{label}</b>: %{value} (%{percent})<extra></extra>',
        sort=False,
    ))
    fig.add_annotation(
        text=center_text, x=0.5, y=0.5, showarrow=False,
        font=dict(color='white', size=18, family='Arial Black'),
        xref='paper', yref='paper',
    )
    fig.update_layout(
        title=dict(text=f'<b>{title}</b>', x=0.5,
                   font=dict(color=COLORS['text_secondary'], size=12)),
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
        showlegend=True,
        legend=dict(
            orientation='h', x=0.5, xanchor='center', y=-0.08,
            font=dict(color=COLORS['text_primary'], size=10),
            bgcolor='rgba(0,0,0,0)', itemsizing='constant',
        ),
        margin=dict(l=5, r=5, t=34, b=34),
        height=230,
    )
    return fig


def _gk_donut_card(team_name: str, color: str, gk_name: str,
                   full: dict, h1: dict, h2: dict) -> html.Div:
    saves  = full.get('saves', 0)
    goals  = full.get('goals_conceded', 0)
    sot    = full.get('shots_on_target', 0)
    total  = full.get('total_shots', 0)
    off_t  = max(total - sot, 0)
    sv_pct = full.get('save_pct', 0.0)
    fig_save = _make_donut(
        values=[saves, goals] if (saves + goals) > 0 else [1, 0],
        labels=['Saves', 'Goals'],
        colors=[_BARCA_BLUE, _BARCA_GARNET],
        center_text=f"{sv_pct:.0f}%",
        title='Save Rate',
    )
    fig_shots = _make_donut(
        values=[sot, off_t] if total > 0 else [0, 1],
        labels=['On Target', 'Off Target'],
        colors=[_BARCA_GARNET, 'rgba(140,140,140,0.35)'],
        center_text=f"{sot}/{total}",
        title='Shots Faced',
    )
    _METRICS_T = [
        ('Shots Faced', 'total_shots',     lambda v: str(int(v))),
        ('SOT',         'shots_on_target', lambda v: str(int(v))),
        ('xGA',         'xg_against',      lambda v: f"{v:.2f}"),
        ('Save %',      'save_pct',        lambda v: f"{v:.1f}%"),
    ]
    _hdr = {
        'textAlign': 'center', 'padding': '4px 10px',
        'fontSize': '0.64rem', 'fontWeight': '700',
        'color': COLORS['text_secondary'],
        'textTransform': 'uppercase', 'letterSpacing': '0.06em',
        'borderBottom': f'1px solid {COLORS["dark_border"]}',
    }
    _col = {'textAlign': 'center', 'padding': '4px 10px',
            'fontSize': '0.78rem', 'fontWeight': '600', 'color': COLORS['text_primary']}
    _lbl = {'padding': '4px 10px', 'fontSize': '0.76rem',
            'color': COLORS['text_secondary'], 'whiteSpace': 'nowrap'}
    header = html.Tr([
        html.Th('', style=_hdr), html.Th('Full', style=_hdr),
        html.Th('1H', style=_hdr), html.Th('2H', style=_hdr),
    ])
    rows = []
    for i, (label, key, fmt) in enumerate(_METRICS_T):
        bg = 'rgba(255,255,255,0.03)' if i % 2 else 'transparent'
        rows.append(html.Tr([
            html.Td(label, style=_lbl),
            html.Td(fmt(full.get(key, 0)), style=_col),
            html.Td(fmt(h1.get(key, 0)),   style=_col),
            html.Td(fmt(h2.get(key, 0)),   style=_col),
        ], style={'backgroundColor': bg}))
    return html.Div([
        html.Div(team_name, style={
            'color': color, 'fontWeight': '700', 'fontSize': '0.95rem',
            'marginBottom': '4px', 'borderBottom': f'2px solid {color}',
            'paddingBottom': '6px',
        }),
        html.Div(f"GK: {gk_name}", style={
            'color': COLORS['text_secondary'], 'fontSize': '0.82rem', 'marginBottom': '8px',
        }),
        dbc.Row([
            dbc.Col(dcc.Graph(figure=fig_save,  config=CHART_CONFIG), width=6, className='p-0'),
            dbc.Col(dcc.Graph(figure=fig_shots, config=CHART_CONFIG), width=6, className='p-0'),
        ], className='g-0 mb-2'),
        html.Table([html.Thead(header), html.Tbody(rows)],
                   style={'width': '100%', 'borderCollapse': 'collapse'}),
    ], style=CARD_STYLE)


def _gk_stats_table_multi(team_name: str, color: str, gk_list: list) -> html.Div:
    _METRICS = [
        ('Shots Faced',     'total_shots'),
        ('Shots on Target', 'shots_on_target'),
        ('Saves',           'saves'),
        ('Goals Conceded',  'goals_conceded'),
        ('xGA',             'xg_against'),
        ('Save %',          'save_pct'),
    ]
    _col = {'textAlign': 'center', 'padding': '6px 12px',
            'fontSize': '0.82rem', 'fontWeight': '600', 'color': COLORS['text_primary']}
    _hdr = {'textAlign': 'center', 'padding': '6px 12px',
            'fontSize': '0.68rem', 'fontWeight': '700',
            'color': COLORS['text_secondary'],
            'textTransform': 'uppercase', 'letterSpacing': '0.06em',
            'borderBottom': f'1px solid {COLORS["dark_border"]}'}
    _lbl = {'padding': '6px 12px', 'fontSize': '0.8rem',
            'color': COLORS['text_secondary'], 'whiteSpace': 'nowrap'}

    def _fmt(key, d):
        v = d.get(key, 0)
        if key == 'save_pct':   return f"{v:.1f}%"
        if key == 'xg_against': return f"{v:.2f}"
        return str(int(v))

    gk_headers = [html.Th('', style=_hdr)]
    for gk in gk_list:
        gk_headers.append(html.Th(
            html.Div([
                html.Div(gk['name'],       style={'fontSize': '0.72rem', 'fontWeight': '700',
                                                   'color': COLORS['text_primary']}),
                html.Div(gk['time_label'], style={'fontSize': '0.62rem',
                                                   'color': COLORS['text_secondary']}),
            ]),
            style=_hdr,
        ))
    rows = []
    for i, (label, key) in enumerate(_METRICS):
        bg = COLORS.get('dark_tertiary', 'rgba(255,255,255,0.03)') if i % 2 == 0 else 'transparent'
        rows.append(html.Tr(
            [html.Td(label, style=_lbl)] + [html.Td(_fmt(key, gk), style=_col) for gk in gk_list],
            style={'backgroundColor': bg},
        ))
    return html.Div([
        html.Div(team_name, style={
            'color': color, 'fontWeight': '700', 'fontSize': '0.95rem',
            'marginBottom': '10px', 'borderBottom': f'2px solid {color}',
            'paddingBottom': '6px',
        }),
        html.Table([html.Thead(html.Tr(gk_headers)), html.Tbody(rows)],
                   style={'width': '100%', 'borderCollapse': 'collapse'}),
    ], style=CARD_STYLE)


def _gk_match_stats_section(hs: dict, as_: dict,
                              h1_hs: dict, h2_hs: dict,
                              h1_as: dict, h2_as: dict) -> html.Div:
    def _block(td: dict, color: str, h1: dict, h2: dict) -> html.Div:
        gk_list = td['gk_list']
        if len(gk_list) == 1:
            full = {k: td[k] for k in ('total_shots', 'shots_on_target',
                                        'saves', 'goals_conceded', 'xg_against', 'save_pct')}
            return _gk_donut_card(td['team'], color, gk_list[0]['name'], full, h1, h2)
        return _gk_stats_table_multi(td['team'], color, gk_list)
    return html.Div([
        section_header('GK Statistics'),
        dbc.Row([
            dbc.Col(_block(hs, HOME_COLOR, h1_hs, h2_hs), md=6, className='mb-3'),
            dbc.Col(_block(as_, AWAY_COLOR, h1_as, h2_as), md=6, className='mb-3'),
        ], className='g-3'),
    ], style={'marginBottom': '36px'})


def _goal_mouth_viz(opp_shots_df: pd.DataFrame,
                    gk_team_color: str, gk_team: str) -> dcc.Graph:
    POST_W = 0.7
    shapes = [
        dict(type='rect', x0=_GOAL_LEFT, x1=_GOAL_RIGHT, y0=0, y1=_CROSSBAR_Z,
             fillcolor='rgba(255,255,255,0.07)', line=dict(width=0)),
        dict(type='rect', x0=_GOAL_LEFT - POST_W, x1=_GOAL_LEFT,
             y0=0, y1=_CROSSBAR_Z + POST_W, fillcolor='white', line=dict(width=0)),
        dict(type='rect', x0=_GOAL_RIGHT, x1=_GOAL_RIGHT + POST_W,
             y0=0, y1=_CROSSBAR_Z + POST_W, fillcolor='white', line=dict(width=0)),
        dict(type='rect', x0=_GOAL_LEFT - POST_W, x1=_GOAL_RIGHT + POST_W,
             y0=_CROSSBAR_Z, y1=_CROSSBAR_Z + POST_W, fillcolor='white', line=dict(width=0)),
        dict(type='line', x0=20, x1=80, y0=0, y1=0,
             line=dict(color='rgba(255,255,255,0.25)', width=1, dash='dot')),
        *[dict(type='line', x0=v, x1=v, y0=0, y1=_CROSSBAR_Z,
               line=dict(color='rgba(255,255,255,0.07)', width=1))
          for v in [43.0, 46.5, 50.0, 53.5, 57.0]],
        *[dict(type='line', x0=_GOAL_LEFT, x1=_GOAL_RIGHT, y0=h, y1=h,
               line=dict(color='rgba(255,255,255,0.07)', width=1))
          for h in [13, 25]],
    ]
    _STYLE = [
        ('Goal',         _GOAL_COLOR, 'star',    18),
        ('Saved Shot',   _SAVE_COLOR, 'circle',  15),
        ('Post',         '#ffd43b',   'diamond', 15),
        ('Blocked Shot', '#cc5de8',   'square',  13),
        ('Miss',         _MISS_COLOR, 'x',       13),
    ]
    fig = go.Figure()
    if (not opp_shots_df.empty
            and _GM_Y_COL in opp_shots_df.columns
            and _GM_Z_COL in opp_shots_df.columns):
        for outcome, color, symbol, size in _STYLE:
            grp = opp_shots_df[opp_shots_df['event_type'] == outcome].copy()
            if grp.empty:
                continue
            grp[_GM_Y_COL] = pd.to_numeric(grp[_GM_Y_COL], errors='coerce')
            grp[_GM_Z_COL] = pd.to_numeric(grp[_GM_Z_COL], errors='coerce')
            grp = grp.dropna(subset=[_GM_Y_COL, _GM_Z_COL])
            if grp.empty:
                continue
            names    = grp['player_name'].fillna('Unknown').tolist() if 'player_name' in grp.columns else [''] * len(grp)
            mins     = grp['time_min'].fillna('?').astype(str).tolist() if 'time_min' in grp.columns else ['?'] * len(grp)
            og_flags = (
                [' (OG)' if v == 'Si' else '' for v in grp['own goal'].fillna('')]
                if 'own goal' in grp.columns else [''] * len(grp)
            )
            x_raw  = 100 - grp[_GM_Y_COL]
            x_disp = (_GM_CENTER + (x_raw - _GM_CENTER) * _GM_X_SCALE).tolist()
            fig.add_trace(go.Scatter(
                x=x_disp, y=grp[_GM_Z_COL].tolist(),
                mode='markers', name=outcome,
                marker=dict(color=color, symbol=symbol, size=size, opacity=0.92,
                            line=dict(color='white', width=1)),
                customdata=list(zip(names, mins, og_flags)),
                hovertemplate=(
                    '<b>' + outcome + '%{customdata[2]}</b><br>'
                    'Player: %{customdata[0]}<br>'
                    "Min: %{customdata[1]}'<extra></extra>"
                ),
            ))
    fig.update_layout(
        shapes=shapes,
        xaxis=dict(range=[20, 80], showgrid=False, zeroline=False, visible=False),
        yaxis=dict(range=[-4, 55], showgrid=False, zeroline=False, visible=False),
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='#0d1a35',
        margin=dict(l=10, r=10, t=40, b=60), height=430,
        font=dict(color=COLORS['text_primary']),
        legend=dict(orientation='h', y=-0.14, x=0.5, xanchor='center',
                    font=dict(color=COLORS['text_primary'], size=10),
                    bgcolor='rgba(0,0,0,0)'),
        title=dict(text=f'<b>Goal Mouth — {gk_team} GK</b>', x=0.5,
                   font=dict(color=gk_team_color, size=12)),
    )
    return dcc.Graph(figure=fig, config=CHART_CONFIG)


def _gk_shot_map_fig(shots: pd.DataFrame, team_color: str, team_name: str) -> go.Figure:
    fig = go.Figure()
    add_vertical_half_pitch_background(fig)
    _common = dict(
        **VPITCH_AXIS_HALF,
        height=520, margin=dict(l=10, r=10, t=44, b=20),
        title=dict(text=f'<b>{team_name}</b>', x=0.5,
                   font=dict(color=team_color, size=13)),
        annotations=[dict(
            x=0.98, y=0.97, xref='paper', yref='paper',
            text='▲ Attacking Direction', showarrow=False,
            font=dict(color='black', size=16, family='Arial'),
            xanchor='right', yanchor='top',
            bgcolor='rgba(255,255,255,0.7)', borderpad=3,
        )],
    )
    if shots.empty or 'x' not in shots.columns:
        fig.update_layout(**layout_config(**_common))
        return fig
    for outcome in ['Goal', 'Saved Shot', 'Post', 'Blocked Shot', 'Miss']:
        grp = shots[shots['event_type'] == outcome].copy()
        if grp.empty:
            continue
        color  = _GK_OUTCOME_COLOR.get(outcome, team_color)
        symbol = _GK_OUTCOME_SYMBOL.get(outcome, 'circle')
        valid  = grp[grp['x'].notna() & grp['y'].notna()].copy()
        if valid.empty:
            continue
        fig_x = (100 - valid['y']).tolist()
        fig_y = valid['x'].tolist()
        names    = valid['player_name'].fillna('Unknown').tolist() if 'player_name' in valid.columns else [''] * len(valid)
        mins     = valid['time_min'].fillna(0).astype(int).tolist() if 'time_min' in valid.columns else [0] * len(valid)
        og_flags = (
            [' (own goal)' if v == 'Si' else '' for v in valid['own goal'].fillna('')]
            if 'own goal' in valid.columns else [''] * len(valid)
        )
        if _GM_Y_COL in valid.columns:
            gm_y = pd.to_numeric(valid[_GM_Y_COL], errors='coerce')
            xs_l, ys_l = [], []
            for sx, sy, gmy in zip(fig_x, fig_y, gm_y):
                if pd.notna(gmy):
                    xs_l.extend([sx, 100 - float(gmy), None])
                    ys_l.extend([sy, 100.0, None])
            if xs_l:
                fig.add_trace(go.Scatter(
                    x=xs_l, y=ys_l, mode='lines',
                    line=dict(color=color, width=2.5),
                    opacity=0.65, showlegend=False, hoverinfo='skip',
                ))
        size = 15 if outcome == 'Goal' else 10
        fig.add_trace(go.Scatter(
            x=fig_x, y=fig_y, mode='markers', name=outcome,
            marker=dict(color=color, symbol=symbol, size=size,
                        opacity=0.88, line=dict(color='white', width=1)),
            customdata=list(zip(names, mins, og_flags)),
            hovertemplate=(
                f'<b>{outcome}%{{customdata[2]}}</b><br>'
                '<b>%{customdata[0]}</b><br>'
                "%{customdata[1]}'<extra></extra>"
            ),
        ))
    fig.update_layout(**layout_config(
        **_common,
        hoverlabel=dict(bgcolor='#1A1D2E', font_color='white', font_size=12),
        legend=dict(
            x=0.01, y=0.01, xanchor='left', yanchor='bottom', orientation='v',
            font=dict(color=COLORS['text_primary'], size=10),
            bgcolor='rgba(26,29,46,0.80)',
            bordercolor=COLORS.get('dark_border', 'rgba(255,255,255,0.15)'),
            borderwidth=1,
        ),
    ))
    return fig


def _gk_pass_map(gk_passes_df: pd.DataFrame, team_color: str, gk_name: str) -> go.Figure:
    fig = go.Figure()
    add_pitch_background(fig)
    if not gk_passes_df.empty and 'Pass End X' in gk_passes_df.columns:
        passes = gk_passes_df.copy()
        passes['Pass End X'] = pd.to_numeric(passes['Pass End X'], errors='coerce')
        passes['Pass End Y'] = pd.to_numeric(passes['Pass End Y'], errors='coerce')
        passes = passes.dropna(subset=['x', 'y', 'Pass End X', 'Pass End Y'])
        for success, (color, label, opacity) in {
            True:  (team_color, 'Successful', 0.75),
            False: ('#ff6b6b',  'Unsuccessful', 0.60),
        }.items():
            if 'outcome' in passes.columns:
                grp = passes[passes['outcome'] == (1 if success else 0)]
            else:
                grp = passes if success else passes.iloc[:0]
            if grp.empty:
                continue
            xs_l, ys_l = [], []
            for _, row in grp.iterrows():
                xs_l.extend([row['x'], row['Pass End X'], None])
                ys_l.extend([row['y'], row['Pass End Y'], None])
            if xs_l:
                fig.add_trace(go.Scatter(
                    x=xs_l, y=ys_l, mode='lines',
                    line=dict(color=color, width=1.5),
                    opacity=opacity * 0.6,
                    showlegend=False, hoverinfo='skip',
                ))
            fig.add_trace(go.Scatter(
                x=grp['Pass End X'].tolist(), y=grp['Pass End Y'].tolist(),
                mode='markers', showlegend=False,
                marker=dict(color=color, size=5, opacity=opacity * 0.7, symbol='circle'),
                hoverinfo='skip',
            ))
            names = grp['player_name'].fillna(gk_name).tolist() if 'player_name' in grp.columns else [gk_name] * len(grp)
            mins  = grp['time_min'].fillna(0).astype(int).tolist() if 'time_min' in grp.columns else [0] * len(grp)
            fig.add_trace(go.Scatter(
                x=grp['x'].tolist(), y=grp['y'].tolist(),
                mode='markers', name=label,
                marker=dict(color=color, size=9, opacity=opacity,
                            symbol='circle', line=dict(color='white', width=1)),
                customdata=list(zip(names, mins)),
                hovertemplate=(
                    f'<b>{label} Pass</b><br>%{{customdata[0]}}<br>'
                    "%{customdata[1]}'<extra></extra>"
                ),
            ))
    fig.update_layout(**layout_config(
        **PITCH_AXIS_FULL,
        height=480, margin=dict(l=0, r=0, t=48, b=0),
        legend=dict(orientation='v', x=0.01, xanchor='left', y=0.99, yanchor='top',
                    bgcolor='rgba(0,0,0,0.55)',
                    font=dict(color=COLORS['text_primary'], size=9)),
        hoverlabel=dict(bgcolor='#1A1D2E', font_color='white', font_size=12),
        annotations=[dict(
            x=0.5, y=1.0, xref='paper', yref='paper',
            text='➡ Direction of Attack', showarrow=False,
            font=dict(color='black', size=16, family='Arial'),
            xanchor='center', yanchor='bottom',
            bgcolor='rgba(255,255,255,0.7)', borderpad=3,
        )],
    ))
    return fig


def _build_gk_selector_row(d: dict) -> html.Div:
    home_gks   = d['home']['gk_list']
    away_gks   = d['away']['gk_list']
    home_multi = len(home_gks) > 1
    away_multi = len(away_gks) > 1

    def _opts(gk_list):
        return [{'label': 'All GKs', 'value': 'all'}] + [
            {'label': gk['name'] + (f" ({gk['time_label']})" if gk['time_label'] else ''),
             'value': str(i)}
            for i, gk in enumerate(gk_list)
        ]

    _lbl_style = {'fontSize': '0.85rem', 'marginRight': '8px',
                  'alignSelf': 'center', 'whiteSpace': 'nowrap'}
    home_block = html.Div([
        html.Span(f"{d['home']['team']} GK:", style={**_lbl_style, 'color': HOME_COLOR}),
        dcc.Dropdown(
            id='gk-home-filter', options=_opts(home_gks), value='all',
            clearable=False, className='culevision-dropdown', style={'minWidth': '220px'},
        ),
    ], style={'display': 'flex' if home_multi else 'none',
              'alignItems': 'center', 'gap': '8px'})
    away_block = html.Div([
        html.Span(f"{d['away']['team']} GK:", style={**_lbl_style, 'color': AWAY_COLOR}),
        dcc.Dropdown(
            id='gk-away-filter', options=_opts(away_gks), value='all',
            clearable=False, className='culevision-dropdown', style={'minWidth': '220px'},
        ),
    ], style={'display': 'flex' if away_multi else 'none',
              'alignItems': 'center', 'gap': '8px'})
    outer = 'flex' if (home_multi or away_multi) else 'none'
    return html.Div(
        [home_block, away_block],
        style={'display': outer, 'gap': '24px', 'alignItems': 'center',
               'marginBottom': '20px', 'flexWrap': 'wrap'},
    )


def _gk_metrics_table(full: dict, h1: dict, h2: dict) -> html.Table:
    _METRICS_T = [
        ('Shots Faced', 'total_shots',     lambda v: str(int(v))),
        ('SOT',         'shots_on_target', lambda v: str(int(v))),
        ('xGA',         'xg_against',      lambda v: f"{v:.2f}"),
        ('Save %',      'save_pct',        lambda v: f"{v:.1f}%"),
    ]
    _hdr = {'textAlign': 'center', 'padding': '4px 10px', 'fontSize': '0.64rem',
            'fontWeight': '700', 'color': COLORS['text_secondary'],
            'textTransform': 'uppercase', 'letterSpacing': '0.06em',
            'borderBottom': f'1px solid {COLORS["dark_border"]}'}
    _col = {'textAlign': 'center', 'padding': '4px 10px', 'fontSize': '0.78rem',
            'fontWeight': '600', 'color': COLORS['text_primary']}
    _lbl = {'padding': '4px 10px', 'fontSize': '0.76rem',
            'color': COLORS['text_secondary'], 'whiteSpace': 'nowrap'}
    header = html.Tr([html.Th('', style=_hdr), html.Th('Full', style=_hdr),
                      html.Th('1H', style=_hdr), html.Th('2H', style=_hdr)])
    rows = []
    for i, (label, key, fmt) in enumerate(_METRICS_T):
        bg = 'rgba(255,255,255,0.03)' if i % 2 else 'transparent'
        rows.append(html.Tr([
            html.Td(label, style=_lbl),
            html.Td(fmt(full.get(key, 0)), style=_col),
            html.Td(fmt(h1.get(key, 0)),   style=_col),
            html.Td(fmt(h2.get(key, 0)),   style=_col),
        ], style={'backgroundColor': bg}))
    return html.Table([html.Thead(header), html.Tbody(rows)],
                      style={'width': '100%', 'borderCollapse': 'collapse'})


def _gk_stats_parts(td: dict, color: str, h1: dict, h2: dict):
    """Return (donuts_row_or_None, table_div) for embedding beside the pass map."""
    gk_list = td['gk_list']
    if len(gk_list) != 1:
        return None, _gk_stats_table_multi(td['team'], color, gk_list)
    full = {k: td[k] for k in ('total_shots', 'shots_on_target',
                               'saves', 'goals_conceded', 'xg_against', 'save_pct')}
    saves = full.get('saves', 0); goals = full.get('goals_conceded', 0)
    sot   = full.get('shots_on_target', 0); total = full.get('total_shots', 0)
    off_t = max(total - sot, 0); sv_pct = full.get('save_pct', 0.0)
    fig_save = _make_donut(
        values=[saves, goals] if (saves + goals) > 0 else [1, 0],
        labels=['Saves', 'Goals'], colors=[_BARCA_BLUE, _BARCA_GARNET],
        center_text=f"{sv_pct:.0f}%", title='Save Rate')
    fig_shots = _make_donut(
        values=[sot, off_t] if total > 0 else [0, 1],
        labels=['On Target', 'Off Target'], colors=[_BARCA_GARNET, 'rgba(140,140,140,0.35)'],
        center_text=f"{sot}/{total}", title='Shots Faced')
    donuts = dbc.Row([
        dbc.Col(dcc.Graph(figure=fig_save,  config=CHART_CONFIG), md=6, className='p-1'),
        dbc.Col(dcc.Graph(figure=fig_shots, config=CHART_CONFIG), md=6, className='p-1'),
    ], className='g-2', align='center')
    return donuts, _gk_metrics_table(full, h1, h2)


def _render_gk_plots(events: pd.DataFrame, home_gk: str = 'all', away_gk: str = 'all') -> html.Div:
    d   = _gk_compute(events)
    hs  = d['home']
    as_ = d['away']
    h1 = events[events['period_id'] == 1] if 'period_id' in events.columns else events.iloc[:0]
    h2 = events[events['period_id'] == 2] if 'period_id' in events.columns else events.iloc[:0]
    h1_hs = _half_stats(h1, 'home', 'away'); h2_hs = _half_stats(h2, 'home', 'away')
    h1_as = _half_stats(h1, 'away', 'home'); h2_as = _half_stats(h2, 'away', 'home')

    h_passes, h_gk_name = _team_passes(hs,  home_gk)
    a_passes, a_gk_name = _team_passes(as_, away_gk)

    def _panel(td, color, passes, gk_name, hh1, hh2):
        donuts, table = _gk_stats_parts(td, color, hh1, hh2)
        children = [html.Div(f"{td['team']} — GK: {gk_name}", style={
            'color': color, 'fontWeight': '600', 'fontSize': '0.85rem',
            'marginBottom': '8px', 'textAlign': 'center'})]
        if donuts is not None:
            children.append(donuts)               # donuts side by side, above the table
        children.append(table)
        children.append(html.Div(style={'height': '12px'}))
        children.append(dcc.Graph(figure=_gk_pass_map(passes, color, gk_name),
                                  config=CHART_CONFIG))   # GK Pass Map, full width below
        return dbc.Col(html.Div(children, style=CARD_STYLE), md=6, className='mb-3')

    return html.Div([
        section_header('GK Pass Map & Statistics'),
        dbc.Row([
            _panel(hs,  HOME_COLOR, h_passes, h_gk_name, h1_hs, h2_hs),
            _panel(as_, AWAY_COLOR, a_passes, a_gk_name, h1_as, h2_as),
        ], className='g-3'),
    ])


def build_goalkeeping_tab(events: pd.DataFrame, **_) -> html.Div:
    if events.empty:
        return html.P("No event data.", style={"color": COLORS["text_secondary"]})
    d = _gk_compute(events)
    return html.Div([
        _build_gk_selector_row(d),
        html.Div(id='gk-plots-content', children=_render_gk_plots(events)),
    ], style={'marginTop': '16px'})


def register_goalkeeping_callbacks(app) -> None:
    @app.callback(
        Output('gk-plots-content', 'children'),
        Input('gk-home-filter', 'value'),
        Input('gk-away-filter', 'value'),
        State('pma-selected-match', 'data'),
        prevent_initial_call=True,
    )
    def _update_gk_plots(home_gk, away_gk, match_id):
        if not match_id:
            return html.P("No match selected.", style={'color': COLORS['text_secondary']})
        events = get_match_events(match_id)
        if events.empty:
            return html.P("No data.", style={'color': COLORS['text_secondary']})
        return _render_gk_plots(events, home_gk or 'all', away_gk or 'all')

# ============================================================================
# ===== player_stats.py =====
# ============================================================================
import pandas as pd
import plotly.graph_objects as go
from dash import html, dcc
import dash_bootstrap_components as dbc

from utils.config import COLORS
from utils.data_utils import exclude_own_goals
from utils.xg_utils import add_xg_column
from utils.xt_utils import add_xt_column
from page_utils.visualizations import HOME_COLOR, AWAY_COLOR, GOLD, CHART_CONFIG
from page_utils.event_filters import SHOT_TYPES

_DEF_TYPES = {'Tackle', 'Interception', 'Ball recovery', 'Clearance'}


def _compute_player_stats(events: pd.DataFrame, player_name: str) -> dict:
    pe = events[events['player_name'] == player_name].copy()
    if pe.empty:
        return {}
    if 'position_name' in pe.columns and (pe['position_name'] == 'Goalkeeper').any():
        return {}
    if 'position' in pe.columns and (pe['position'] == 'GK').any():
        return {}
    pos   = pe['team_position'].iloc[0] if 'team_position' in pe.columns else 'home'
    color = HOME_COLOR if pos == 'home' else AWAY_COLOR
    team  = pe['home_team'].iloc[0] if pos == 'home' else pe['away_team'].iloc[0]
    if 'jersey_number' in pe.columns and not pe['jersey_number'].dropna().empty:
        jersey = pe['jersey_number'].dropna().iloc[0]
    elif 'Jersey Number' in pe.columns and not pe['Jersey Number'].dropna().empty:
        jersey = pe['Jersey Number'].dropna().iloc[0]
    else:
        jersey = ''
    if 'position_name' in pe.columns and not pe['position_name'].dropna().empty:
        display_pos = pe['position_name'].dropna().iloc[0]
    elif 'position' in pe.columns and not pe['position'].dropna().empty:
        display_pos = pe['position'].dropna().iloc[0]
    else:
        display_pos = pos
    try:
        if pd.notna(jersey):
            jersey = int(float(jersey))
        else:
            jersey = ''
    except Exception:
        jersey = ''
    passes      = pe[pe['event_type'] == 'Pass']
    succ_pass   = passes[passes['outcome'] == 1]
    xT_val      = round(add_xt_column(passes)['xT'].sum(), 3) if not passes.empty else 0.0
    shots       = add_xg_column(exclude_own_goals(pe[pe['event_type'].isin(SHOT_TYPES)].copy()))
    goals       = shots[shots['event_type'] == 'Goal']
    goal_assists  = int((pd.to_numeric(passes['Assist'], errors='coerce') == 16).sum()) if 'Assist' in passes.columns else 0
    key_passes_n  = int(pd.to_numeric(passes['Assist'], errors='coerce').isin([13, 14, 15]).sum()) if 'Assist' in passes.columns else 0
    tackles    = pe[pe['event_type'] == 'Tackle']
    tackles_w  = tackles[tackles['outcome'] == 1]
    ints       = pe[pe['event_type'] == 'Interception']
    recoveries = pe[pe['event_type'] == 'Ball recovery']
    clearances = pe[pe['event_type'] == 'Clearance']
    aerials    = pe[pe['event_type'] == 'Aerial']
    aerials_w  = aerials[aerials['outcome'] == 1]
    fouls_c    = pe[pe['event_type'] == 'Foul']
    dribbles   = pe[pe['event_type'] == 'Take On']
    dribbles_s = dribbles[dribbles['outcome'] == 1]
    touch_x = pe['x'].dropna().tolist() if 'x' in pe.columns else []
    touch_y = pe['y'].dropna().tolist() if 'y' in pe.columns else []
    def_df  = pe[pe['event_type'].isin(_DEF_TYPES)].copy()
    def_x   = def_df['x'].dropna().tolist() if 'x' in def_df.columns else []
    def_y   = def_df['y'].dropna().tolist() if 'y' in def_df.columns else []
    pass_acc = round(len(succ_pass) / len(passes) * 100, 1) if len(passes) > 0 else 0
    tackle_w = round(len(tackles_w) / len(tackles) * 100, 1) if len(tackles) > 0 else 0
    aerial_w = round(len(aerials_w) / len(aerials) * 100, 1) if len(aerials) > 0 else 0
    return {
        'player_name': player_name, 'jersey': jersey, 'team': team,
        'team_position': pos, 'display_position': display_pos, 'color': color,
        'touch_x': touch_x, 'touch_y': touch_y, 'def_x': def_x, 'def_y': def_y,
        'touches': len(pe), 'passes': len(passes), 'pass_acc': pass_acc, 'xT': xT_val,
        'shots': len(shots), 'goals': len(goals),
        'xg': round(shots['xg'].sum(), 2) if 'xg' in shots.columns else 0.0,
        'assists': goal_assists, 'key_passes': key_passes_n,
        'tackles': len(tackles), 'tackle_w': tackle_w,
        'ints': len(ints), 'recoveries': len(recoveries), 'clearances': len(clearances),
        'aerials': len(aerials), 'aerial_w': aerial_w,
        'fouls': len(fouls_c), 'dribbles': len(dribbles), 'dribbles_s': len(dribbles_s),
    }


def _build_all_player_stats(events: pd.DataFrame) -> tuple:
    if 'player_name' not in events.columns or 'team_position' not in events.columns:
        return [], []
    home_stats, away_stats = [], []
    for player_name, pe in events.dropna(subset=['player_name']).groupby('player_name', sort=False):
        s = _compute_player_stats(pe, str(player_name).strip())
        if not s:
            continue
        if s['team_position'] == 'home':
            home_stats.append(s)
        else:
            away_stats.append(s)
    home_stats.sort(key=lambda x: x['touches'], reverse=True)
    away_stats.sort(key=lambda x: x['touches'], reverse=True)
    return home_stats, away_stats


def _compute_top5(events: pd.DataFrame) -> dict:
    out = {}
    for pos in ('home', 'away'):
        te = events[events['team_position'] == pos].copy()
        if 'position' in te.columns:
            te = te[te['position'] != 'GK']
        shots_df = te[te['event_type'].isin(SHOT_TYPES)].copy()
        if not shots_df.empty and 'player_name' in shots_df.columns:
            shots_df['sot'] = shots_df['event_type'].isin(['Saved Shot', 'Goal']).astype(int)
            shot_grp = (
                shots_df.groupby('player_name')
                .agg(shots=('event_type', 'count'), sot=('sot', 'sum'))
                .reset_index()
            )
        else:
            shot_grp = pd.DataFrame(columns=['player_name', 'shots', 'sot'])
        passes = te[te['event_type'] == 'Pass'].copy()
        if not passes.empty and 'player_name' in passes.columns:
            passes['x'] = pd.to_numeric(passes['x'], errors='coerce')
            if 'Pass End X' in passes.columns:
                passes['Pass End X'] = pd.to_numeric(passes['Pass End X'], errors='coerce')
                passes['is_prog'] = ((passes['Pass End X'] - passes['x']) > 10).astype(int)
            else:
                passes['is_prog'] = 0
            if 'Assist' in passes.columns:
                second_assist = (
                    passes['2nd assist'] if '2nd assist' in passes.columns
                    else pd.Series('N/A', index=passes.index)
                )
                passes['is_kp'] = (
                    passes['Assist'].isin(['13', '14', '15', '16']) | (second_assist == 'Si')
                ).astype(int)
            else:
                passes['is_kp'] = 0
            pass_grp = (
                passes.groupby('player_name')
                .agg(prog=('is_prog', 'sum'), kp=('is_kp', 'sum'))
                .reset_index()
            )
            pass_grp[['prog', 'kp']] = pass_grp[['prog', 'kp']].astype(int)
        else:
            pass_grp = pd.DataFrame(columns=['player_name', 'prog', 'kp'])
        rec_df  = te[te['event_type'] == 'Ball recovery']
        tkl_df  = te[(te['event_type'] == 'Tackle') & (te['outcome'] == 1)]
        rec_grp = (rec_df.groupby('player_name').size().rename('rec')
                   if not rec_df.empty else pd.Series(dtype=int, name='rec'))
        tkl_grp = (tkl_df.groupby('player_name').size().rename('tw')
                   if not tkl_df.empty else pd.Series(dtype=int, name='tw'))
        def_grp = pd.concat([rec_grp, tkl_grp], axis=1).fillna(0).astype(int).reset_index()
        out[pos] = {'shots': shot_grp, 'passes': pass_grp, 'defensive': def_grp}
    return out


def _top5_card(metric_title: str, team_name: str, df: pd.DataFrame,
               col: str, color: str) -> html.Div:
    header = html.Div([
        html.Div(metric_title, style={
            'color': GOLD, 'fontSize': '0.68rem', 'fontWeight': '700',
            'textTransform': 'uppercase', 'letterSpacing': '0.06em',
        }),
        html.Div(team_name, style={
            'color': color, 'fontSize': '0.70rem', 'fontWeight': '700', 'marginTop': '2px',
        }),
    ], style={
        'marginBottom': '8px', 'paddingBottom': '8px',
        'borderBottom': f'2px solid {color}40',
    })
    if df.empty or col not in df.columns:
        return html.Div([header, html.Div('No data', style={
            'color': COLORS['text_secondary'], 'fontSize': '0.78rem',
        })], style=CARD_STYLE)
    top5 = df.sort_values(col, ascending=False).head(5).reset_index(drop=True)
    rows = [header]
    for i, row in top5.iterrows():
        short = str(row['player_name']).split()[-1]
        val = int(row[col])
        is_last = i == len(top5) - 1
        rows.append(html.Div([
            html.Span(f"{i + 1}. {short}", style={
                'color': color, 'fontSize': '0.80rem', 'fontWeight': '600', 'flex': '1',
                'overflow': 'hidden', 'textOverflow': 'ellipsis', 'whiteSpace': 'nowrap',
            }),
            html.Span(str(val), style={
                'color': COLORS['text_primary'], 'fontSize': '0.80rem', 'fontWeight': '700',
            }),
        ], style={
            'display': 'flex', 'alignItems': 'center', 'padding': '3px 0',
            'borderBottom': 'none' if is_last else f'1px solid {COLORS["dark_border"]}',
        }))
    return html.Div(rows, style=CARD_STYLE)


def _build_top5_section(events: pd.DataFrame) -> html.Div:
    d = _compute_top5(events)
    home_team = events['home_team'].iloc[0]
    away_team = events['away_team'].iloc[0]
    rows_def = [
        ('shots', [
            ('Shots',           'shots', home_team, 'home', HOME_COLOR),
            ('Shots on Target', 'sot',   home_team, 'home', HOME_COLOR),
            ('Shots',           'shots', away_team, 'away', AWAY_COLOR),
            ('Shots on Target', 'sot',   away_team, 'away', AWAY_COLOR),
        ]),
        ('passes', [
            ('Progressive Passes', 'prog', home_team, 'home', HOME_COLOR),
            ('Key Passes',         'kp',   home_team, 'home', HOME_COLOR),
            ('Progressive Passes', 'prog', away_team, 'away', AWAY_COLOR),
            ('Key Passes',         'kp',   away_team, 'away', AWAY_COLOR),
        ]),
        ('defensive', [
            ('Ball Recoveries', 'rec', home_team, 'home', HOME_COLOR),
            ('Tackles Won',     'tw',  home_team, 'home', HOME_COLOR),
            ('Ball Recoveries', 'rec', away_team, 'away', AWAY_COLOR),
            ('Tackles Won',     'tw',  away_team, 'away', AWAY_COLOR),
        ]),
    ]
    blocks = []
    for key, cards in rows_def:
        blocks.append(
            dbc.Row([
                dbc.Col(
                    _top5_card(title, team, d[pos][key], col, color),
                    md=3, className='mb-3',
                )
                for title, col, team, pos, color in cards
            ], className='g-3 mb-4')
        )
    return html.Div(blocks, style={'marginBottom': '36px'})


def _full_stats_table(home_stats: list, away_stats: list) -> html.Div:
    all_stats = home_stats + away_stats
    if not all_stats:
        return html.P("No data.", style={'color': COLORS['text_secondary']})
    cols = [
        ('Player',        'player_name'),
        ('Team',          'team'),
        ('TCH',           'touches'),
        ('PAS',           'passes'),
        ('PA%',           'pass_acc'),
        ('Positional xT', 'xT'),
        ('SHT',           'shots'),
        ('G',             'goals'),
        ('AST',           'assists'),
        ('KP',            'key_passes'),
        ('TKL',           'tackles'),
        ('TW%',           'tackle_w'),
        ('INT',           'ints'),
        ('REC',           'recoveries'),
        ('CLR',           'clearances'),
        ('AER',           'aerials'),
        ('AW%',           'aerial_w'),
        ('FC',            'fouls'),
        ('DRB',           'dribbles'),
    ]
    header_row = html.Tr([
        html.Th(label, style={
            'color': GOLD, 'borderBottom': f'2px solid {GOLD}',
            'padding': '6px 8px', 'fontSize': '0.72rem',
            'textAlign': 'center' if key not in ('player_name', 'team') else 'left',
            'whiteSpace': 'nowrap',
        })
        for label, key in cols
    ])
    # Per numeric column: indices of the top-5 values (value > 0) — highlighted gold.
    top5_idx: dict = {}
    for _, key in cols:
        if key in ('player_name', 'team'):
            continue
        scored = []
        for idx, s in enumerate(all_stats):
            try:
                v = float(s.get(key, 0) or 0)
            except (TypeError, ValueError):
                v = 0.0
            scored.append((idx, v))
        chosen = set()
        for idx, v in sorted(scored, key=lambda t: t[1], reverse=True):
            if v <= 0 or len(chosen) >= 5:
                break
            chosen.add(idx)
        top5_idx[key] = chosen

    rows = []
    for i, s in enumerate(all_stats):
        bg = 'rgba(255,255,255,0.03)' if i % 2 else 'transparent'
        color = s['color']
        cells = []
        for label, key in cols:
            val = s.get(key, '')
            align = 'left' if key in ('player_name', 'team') else 'center'
            style = {'padding': '5px 8px', 'fontSize': '0.78rem',
                     'textAlign': align, 'whiteSpace': 'nowrap'}
            if key == 'player_name':
                style['color'] = color; style['fontWeight'] = '600'
            elif i in top5_idx.get(key, ()):
                style['color'] = GOLD; style['fontWeight'] = '700'
            cells.append(html.Td(str(val), style=style))
        rows.append(html.Tr(cells, style={'backgroundColor': bg}))
    return html.Div(
        html.Table([html.Thead(header_row), html.Tbody(rows)],
                   style={'width': '100%', 'borderCollapse': 'collapse',
                          'color': COLORS['text_primary']}),
        style={'overflowX': 'auto'},
    )


def build_player_stats_tab(events: pd.DataFrame, **_) -> html.Div:
    if events.empty:
        return html.P("No event data.", style={"color": COLORS["text_secondary"]})
    home_stats, away_stats = _build_all_player_stats(events)
    if not home_stats and not away_stats:
        return html.P("No player data available.", style={"color": COLORS["text_secondary"]})
    return html.Div([
        html.Div(_full_stats_table(home_stats, away_stats), style=CARD_STYLE),
    ], style={'marginTop': '16px'})


def register_player_stats_callbacks(app) -> None:
    pass

__all__ = [
    'page_header',
    'build_overview_tab', 'register_overview_callbacks',
    'build_attacking_output_tab', 'register_attacking_output_callbacks',
    'build_build_up_passing_tab', 'register_build_up_passing_callbacks',
    'build_defensive_structure_tab', 'register_defensive_structure_callbacks',
    'build_transitions_counterpressing_tab', 'register_transitions_counterpressing_callbacks',
    'build_goalkeeping_tab', 'register_goalkeeping_callbacks',
    'build_player_stats_tab', 'register_player_stats_callbacks',
    'build_attack_radar', 'build_bup_radar', 'build_def_radar',
]


# ============================================================================
# ===== Match Report page (calendar, score headline, section orchestration) =====
# ============================================================================

"""
CuléVision - Match Report Page

Orchestrates the calendar selector, score headline, and a single scrolling
page of all match-analysis sections, delegating rendering to the modules
inside ``match_analysis_tabs/``.
"""

import calendar
import logging
from datetime import datetime

from dash import html, dcc, ctx, ALL
from dash.dependencies import Input, Output, State
import dash_bootstrap_components as dbc

from utils.config import COLORS
from utils.data_utils import get_match_results, get_match_events
from utils.logos import (
    get_team_logo_path, get_tournament_logo_path,
    team_logo_img, tournament_logo_img,
)
from utils.match_data_adapter import get_match_metadata, compute_team_kpis

from page_utils.visualizations import GOLD, CHART_CONFIG


log = logging.getLogger(__name__)

RESULT_COLORS = {'W': '#28a745', 'D': '#ffc107', 'L': '#dc3545'}


# =============================================================================
# Calendar builder
# =============================================================================

def _build_calendar_grid(year, month, matches, selected_match_id=None):
    matches_by_day = {}
    for m in matches:
        try:
            d = datetime.strptime(str(m['date'])[:10], '%Y-%m-%d')
            if d.year == year and d.month == month:
                matches_by_day.setdefault(d.day, []).append(m)
        except (ValueError, TypeError):
            continue

    cal = calendar.Calendar(firstweekday=0)
    weeks = cal.monthdayscalendar(year, month)

    day_names = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
    header = html.Div(
        [html.Div(d, style={
            'flex': '1', 'textAlign': 'center', 'padding': '8px 0',
            'color': COLORS['text_secondary'], 'fontWeight': 'bold', 'fontSize': '0.8rem',
        }) for d in day_names],
        style={'display': 'flex', 'borderBottom': f'1px solid {COLORS["dark_border"]}'}
    )

    week_rows = []
    for week in weeks:
        day_cells = []
        for day_num in week:
            if day_num == 0:
                day_cells.append(html.Div(style={'flex': '1', 'minHeight': '80px'}))
            else:
                day_matches = matches_by_day.get(day_num, [])
                cell_children = [
                    html.Div(str(day_num), style={
                        'fontSize': '0.75rem', 'color': COLORS['text_secondary'],
                        'marginBottom': '2px',
                    })
                ]
                for m in day_matches:
                    match_id = m.get('match_id')
                    is_selected = str(match_id) == str(selected_match_id) if selected_match_id else False
                    result_color = RESULT_COLORS.get(m.get('result', ''), COLORS['text_secondary'])
                    is_home = m.get('is_home', True)
                    opponent = m.get('opponent', '???')
                    score = f"{m.get('barca_goals', 0)}-{m.get('opponent_goals', 0)}"
                    venue_marker = 'H' if is_home else 'A'
                    competition = m.get('competition', '')
                    opp_logo_path   = get_team_logo_path(opponent)
                    tourn_logo_path = get_tournament_logo_path(competition)

                    logo_children = []
                    if opp_logo_path:
                        logo_children.append(html.Img(
                            src=opp_logo_path,
                            style={'height': '20px', 'width': '20px', 'objectFit': 'contain',
                                   'marginRight': '4px', 'flexShrink': '0'},
                        ))
                    logo_children.append(html.Span(opponent, style={
                        'fontSize': '0.8rem', 'fontWeight': 'bold', 'color': '#E8E9ED',
                        'lineHeight': '1.2', 'overflow': 'hidden',
                        'textOverflow': 'ellipsis', 'whiteSpace': 'nowrap',
                    }))

                    tourn_children = []
                    if tourn_logo_path:
                        tourn_children.append(html.Img(
                            src=tourn_logo_path,
                            style={'height': '14px', 'width': '14px',
                                   'objectFit': 'contain', 'marginRight': '3px'},
                        ))
                    comp_short = {
                        'La Liga': 'Liga', 'Champions League': 'UCL',
                        'Copa del Rey': 'Copa', 'Spanish Super Cup': 'Super Cup',
                    }.get(competition, competition[:6])
                    tourn_children.append(html.Span(comp_short, style={
                        'fontSize': '0.65rem', 'color': COLORS['text_primary'],
                    }))

                    check_span = html.Span(
                        '✓ ', style={'color': GOLD, 'fontSize': '0.7rem',
                                     'fontWeight': '700', 'marginRight': '2px'},
                    ) if is_selected else None

                    cell_children.append(
                        html.Button(
                            html.Div([
                                html.Div(([check_span] if check_span else []) + logo_children, style={
                                    'display': 'flex', 'alignItems': 'center', 'overflow': 'hidden',
                                }),
                                html.Div([
                                    html.Span(f"{score} ({venue_marker})", style={
                                        'fontSize': '0.7rem',
                                        'color': GOLD if is_selected else result_color,
                                        'fontWeight': 'bold', 'marginRight': '6px',
                                    }),
                                    html.Span(tourn_children, style={
                                        'display': 'inline-flex', 'alignItems': 'center',
                                        'backgroundColor': 'rgba(255,255,255,0.08)',
                                        'borderRadius': '3px', 'padding': '1px 4px',
                                    }),
                                ], style={'display': 'flex', 'alignItems': 'center',
                                          'marginTop': '2px'}),
                            ]),
                            id={'type': 'cal-match-btn', 'match_id': m['match_id']},
                            n_clicks=0,
                            style={
                                'background': 'rgba(237,187,0,0.15)' if is_selected else 'none',
                                'border': 'none',
                                'borderLeft': f'3px solid {GOLD if is_selected else result_color}',
                                'padding': '4px 6px', 'cursor': 'pointer',
                                'width': '100%', 'textAlign': 'left',
                                'borderRadius': '0 4px 4px 0', 'marginBottom': '2px',
                            },
                        )
                    )

                cell_style = {
                    'flex': '1', 'minHeight': '90px', 'padding': '4px',
                    'borderRight': f'1px solid {COLORS["dark_border"]}',
                    'borderBottom': f'1px solid {COLORS["dark_border"]}',
                }
                today = datetime.now()
                if year == today.year and month == today.month and day_num == today.day:
                    cell_style['boxShadow'] = f'inset 0 0 0 1px {GOLD}'
                day_cells.append(html.Div(cell_children, style=cell_style))
        week_rows.append(html.Div(day_cells, style={'display': 'flex'}))

    return html.Div([header] + week_rows, style={
        'border': f'1px solid {COLORS["dark_border"]}',
        'borderRadius': '8px', 'overflow': 'hidden',
        'backgroundColor': COLORS['dark_secondary'],
    })


# =============================================================================
# Section shell — static skeleton; each section loaded by its own callback
# =============================================================================

_SECTIONS = [
    ("overview",    "Overview"),
    ("attack",      "Attack"),
    ("buildup",     "Build-Up & Passing"),
    ("defense",     "Defense"),
    ("transitions", "Transitions & Counterpressing"),
    ("goalkeeping", "Goalkeeping"),
    ("playerstats", "Player Stats"),
]


def _section_divider(title):
    return html.Div(title, style={
        'color': GOLD, 'fontWeight': '800', 'fontSize': '1.1rem',
        'letterSpacing': '1px', 'textTransform': 'uppercase',
        'paddingTop': '32px', 'paddingBottom': '10px',
        'borderBottom': f'2px solid {GOLD}', 'marginBottom': '20px',
        'textAlign': 'center',
    })


def _sections_shell():
    children = []
    for key, title in _SECTIONS:
        if key == 'attack':
            children.append(
                dcc.Loading(
                    type='circle', color=GOLD,
                    children=html.Div(id='pma-radars'),
                )
            )
        children.append(_section_divider(title))
        children.append(
            dcc.Loading(
                type='circle', color=GOLD,
                children=html.Div(id=f'pma-sec-{key}'),
            )
        )
    return html.Div(children)


# =============================================================================
# Page layout
# =============================================================================

def create_match_analysis_layout():
    results = get_match_results()
    results = sorted(results, key=lambda r: str(r['date']))
    competitions = sorted(set(r['competition'] for r in results))
    tournament_options = [{'label': 'All Tournaments', 'value': 'all'}] + [
        {'label': comp, 'value': comp} for comp in competitions
    ]
    match_data = []
    for r in results:
        match_data.append({
            'match_id':       r['match_id'],
            'date':           str(r['date'])[:10],
            'competition':    r['competition'],
            'description':    r['description'],
            'home_team':      r['home_team'],
            'away_team':      r['away_team'],
            'opponent':       r.get('opponent', ''),
            'is_home':        r.get('is_home', True),
            'barca_goals':    r.get('barca_goals', 0),
            'opponent_goals': r.get('opponent_goals', 0),
            'result':         r.get('result', ''),
        })
    if match_data:
        latest_match    = max(match_data, key=lambda m: str(m['date']))
        default_match_id = latest_match['match_id']
        latest          = latest_match['date']
        init_year       = int(latest[:4])
        init_month      = int(latest[5:7])
    else:
        now = datetime.now()
        init_year, init_month = now.year, now.month
        default_match_id = None

    month_name = calendar.month_name[init_month]
    return dbc.Container([
        dcc.Store(id='pma-match-data',      data=match_data),
        dcc.Store(id='pma-calendar-month',  data={'year': init_year, 'month': init_month}),
        dcc.Store(id='pma-selected-match',  data=default_match_id),
        html.H2("Match Report", style={'color': COLORS['text_primary'], 'fontWeight': 'bold',
                                        'textAlign': 'center'}),
        html.Hr(),
        dbc.Row([
            dbc.Col([
                html.Label("Filter by Tournament:",
                           style={'color': COLORS['text_secondary'], 'fontSize': '0.85rem'}),
                dcc.Dropdown(
                    id='pma-tournament-selector',
                    options=tournament_options, value='all',
                    clearable=False, className="culevision-dropdown mb-2",
                ),
            ], md=3),
            dbc.Col([
                html.Div([
                    html.Button("◀", id='pma-prev-month', n_clicks=0, style={
                        'background': 'none', 'border': f'1px solid {COLORS["dark_border"]}',
                        'color': COLORS['text_primary'], 'borderRadius': '6px',
                        'padding': '6px 14px', 'cursor': 'pointer', 'fontSize': '1rem',
                    }),
                    html.H4(id='pma-month-label', children=f"{month_name} {init_year}",
                            className="mb-0 mx-4",
                            style={'color': COLORS['text_primary'], 'display': 'inline'}),
                    html.Button("▶", id='pma-next-month', n_clicks=0, style={
                        'background': 'none', 'border': f'1px solid {COLORS["dark_border"]}',
                        'color': COLORS['text_primary'], 'borderRadius': '6px',
                        'padding': '6px 14px', 'cursor': 'pointer', 'fontSize': '1rem',
                    }),
                ], style={'display': 'flex', 'alignItems': 'center',
                          'justifyContent': 'center', 'paddingTop': '22px'}),
            ], md=5),
            dbc.Col([html.Div(id='pma-selected-indicator', style={'paddingTop': '10px'})], md=4),
        ], className="mb-3"),
        html.Div(id='pma-calendar-container', className="mb-4"),
        html.Div(
            html.A(
                [html.I(className="fas fa-file-pdf", style={'marginRight': '8px'}),
                 "Download Match Report"],
                id='pma-report-link', href='#', target='_blank', className='report-btn',
                style={
                    'display': 'inline-block', 'backgroundColor': GOLD, 'color': '#1A1D2E',
                    'border': 'none', 'borderRadius': '8px', 'padding': '10px 22px',
                    'cursor': 'pointer', 'fontWeight': '700', 'fontSize': '0.88rem',
                    'letterSpacing': '0.03em', 'textDecoration': 'none',
                },
            ),
            className="mb-3",
        ),
        html.Div(id='pma-score-headline', className="mb-3"),
        _sections_shell(),
    ], fluid=True, className="py-4")


# =============================================================================
# Callbacks
# =============================================================================

def register_match_analysis_callbacks(app):

    @app.callback(
        Output('pma-calendar-month', 'data'),
        Output('pma-month-label', 'children'),
        Input('pma-prev-month', 'n_clicks'),
        Input('pma-next-month', 'n_clicks'),
        State('pma-calendar-month', 'data'),
        prevent_initial_call=True,
    )
    def navigate_month(prev_clicks, next_clicks, current):
        triggered = ctx.triggered_id
        year, month = current['year'], current['month']
        if triggered == 'pma-prev-month':
            month -= 1
            if month < 1:
                month, year = 12, year - 1
        elif triggered == 'pma-next-month':
            month += 1
            if month > 12:
                month, year = 1, year + 1
        return {'year': year, 'month': month}, f"{calendar.month_name[month]} {year}"

    @app.callback(
        Output('pma-calendar-container', 'children'),
        Input('pma-calendar-month', 'data'),
        Input('pma-tournament-selector', 'value'),
        Input('pma-match-data', 'data'),
        Input('pma-selected-match', 'data'),
    )
    def render_calendar(cal_month, tournament, match_data, selected_match_id):
        if not match_data:
            return html.P("No match data available.", style={'color': COLORS['text_secondary']})
        year, month = cal_month['year'], cal_month['month']
        filtered = ([m for m in match_data if m['competition'] == tournament]
                    if tournament and tournament != 'all' else match_data)
        return _build_calendar_grid(year, month, filtered, selected_match_id)

    @app.callback(
        Output('pma-selected-match', 'data'),
        Input({'type': 'cal-match-btn', 'match_id': ALL}, 'n_clicks'),
        State('pma-selected-match', 'data'),
        prevent_initial_call=True,
    )
    def select_match_from_calendar(n_clicks_list, current_match):
        if not ctx.triggered_id or not any(n_clicks_list):
            return current_match
        return ctx.triggered_id['match_id']

    @app.callback(
        Output('pma-selected-indicator', 'children'),
        Input('pma-selected-match', 'data'),
        Input('pma-match-data', 'data'),
    )
    def update_selected_indicator(match_id, match_data):
        if not match_id or not match_data:
            return html.Span("No match selected",
                             style={'color': COLORS['text_secondary'], 'fontSize': '0.85rem'})
        match = next((m for m in match_data if m['match_id'] == match_id), None)
        if not match:
            return html.Span("No match selected",
                             style={'color': COLORS['text_secondary'], 'fontSize': '0.85rem'})
        home_team   = match['home_team']
        away_team   = match['away_team']
        competition = match.get('competition', '')
        match_date  = match.get('date', '')
        venue       = 'Home' if match.get('is_home') else 'Away'
        try:
            dt = datetime.strptime(match_date, '%Y-%m-%d')
            formatted_date = dt.strftime('%d %b %Y')
        except (ValueError, TypeError):
            formatted_date = match_date
        return html.Div([
            html.Div("Selected Match", style={
                'color': GOLD, 'fontSize': '0.8rem', 'fontWeight': 'bold',
                'marginBottom': '8px', 'letterSpacing': '0.03em',
            }),
            html.Div([
                tournament_logo_img(competition, '16px'),
                html.Span(competition, style={'color': COLORS['text_secondary'],
                                              'fontSize': '0.7rem', 'marginLeft': '4px'}),
                html.Span(f" · {venue}", style={'color': GOLD, 'fontSize': '0.7rem',
                                                'fontWeight': 'bold'}),
            ], style={'display': 'flex', 'alignItems': 'center', 'marginBottom': '6px'}),
            html.Div([
                team_logo_img(home_team, '28px'),
                html.Span(home_team, style={'color': COLORS['text_primary'], 'fontWeight': 'bold',
                                            'fontSize': '0.85rem', 'marginLeft': '6px'}),
                html.Span("vs", style={'color': COLORS['text_secondary'], 'fontSize': '0.75rem',
                                       'margin': '0 8px'}),
                team_logo_img(away_team, '28px'),
                html.Span(away_team, style={'color': COLORS['text_primary'], 'fontWeight': 'bold',
                                            'fontSize': '0.85rem', 'marginLeft': '6px'}),
            ], style={'display': 'flex', 'alignItems': 'center', 'marginBottom': '4px'}),
            html.Div(formatted_date, style={'color': COLORS['text_secondary'],
                                            'fontSize': '0.75rem'}),
        ], style={
            'backgroundColor': COLORS['dark_secondary'],
            'border': f'1px solid {COLORS["dark_border"]}',
            'borderRadius': '8px', 'padding': '10px 14px',
        })

    @app.callback(
        Output('pma-score-headline', 'children'),
        Input('pma-selected-match', 'data'),
    )
    def update_score_headline(match_id):
        if not match_id:
            return None
        events = get_match_events(match_id)
        if events.empty:
            return None
        meta        = get_match_metadata(events)
        home_kpis   = compute_team_kpis(events, 'home')
        away_kpis   = compute_team_kpis(events, 'away')
        home_team   = meta.get('home_team', 'Home')
        away_team   = meta.get('away_team', 'Away')
        competition = meta.get('competition', '')
        raw_time    = str(meta.get('time', '') or '')
        kickoff_str = raw_time[:5] if len(raw_time) >= 5 else raw_time
        venue       = str(meta.get('venue', '') or '')
        return dbc.Card([dbc.CardBody([
            html.Div([
                html.Div([tournament_logo_img(competition, '80px')], style={
                    'width': '110px', 'height': '110px', 'borderRadius': '50%',
                    'background': GOLD, 'padding': '15px',
                    'display': 'flex', 'alignItems': 'center', 'justifyContent': 'center',
                }),
                html.Div(competition, style={'color': COLORS['text_primary'], 'fontSize': '1rem',
                                             'fontWeight': '500', 'marginTop': '6px'}),
            ], style={'display': 'flex', 'flexDirection': 'column',
                      'alignItems': 'center', 'marginBottom': '16px'}),
            dbc.Row([
                dbc.Col([
                    html.Div([team_logo_img(home_team, '88px')],
                             style={'textAlign': 'right', 'marginBottom': '6px'}),
                    html.H3(home_team, className="text-end mb-0", style={'fontWeight': '600'}),
                    html.Small("Home", className="text-end d-block",
                               style={'color': COLORS['text_secondary']}),
                ], width=4),
                dbc.Col([
                    html.H1(f"{home_kpis['goals']}  -  {away_kpis['goals']}",
                            className="text-center mb-1",
                            style={'color': GOLD, 'fontWeight': '900',
                                   'fontSize': '3.5rem', 'letterSpacing': '0.15em',
                                   # override the global gradient-text h1 rule so the score is gold
                                   'background': 'none', 'WebkitTextFillColor': GOLD,
                                   'WebkitBackgroundClip': 'border-box'}),
                    html.Div([
                        html.I(className="fas fa-clock",
                               style={'marginRight': '5px', 'fontSize': '0.75rem'}),
                        html.Span(f"KO {kickoff_str}" if kickoff_str else ''),
                    ], style={'textAlign': 'center', 'color': COLORS['text_secondary'],
                              'fontSize': '0.82rem', 'marginBottom': '3px'}),
                    html.Div([
                        html.I(className="fas fa-map-marker-alt",
                               style={'marginRight': '5px', 'fontSize': '0.75rem'}),
                        html.Span(venue or '—'),
                    ], style={'textAlign': 'center', 'color': COLORS['text_secondary'],
                              'fontSize': '0.82rem'}),
                ], width=4),
                dbc.Col([
                    html.Div([team_logo_img(away_team, '88px')],
                             style={'textAlign': 'left', 'marginBottom': '6px'}),
                    html.H3(away_team, className="text-start mb-0", style={'fontWeight': '600'}),
                    html.Small("Away", className="text-start d-block",
                               style={'color': COLORS['text_secondary']}),
                ], width=4),
            ], align="center"),
        ])])

    @app.callback(
        Output('pma-radars', 'children'),
        Input('pma-selected-match', 'data'),
    )
    def update_radars(match_id):
        import traceback
        if not match_id:
            return None
        try:
            events = get_match_events(match_id)
            if events.empty:
                return None
            atk_fig = build_attack_radar(events)
            def_fig = build_def_radar(events)
            bup_fig = build_bup_radar(events)
        except Exception as e:
            log.error("Radar section failed: %s\n%s", e, traceback.format_exc())
            return html.P(f"Error rendering radars: {e}",
                          style={'color': '#dc3545', 'fontSize': '0.85rem'})
        for fig in (atk_fig, def_fig, bup_fig):
            if fig is not None:
                fig.update_layout(height=420, margin=dict(l=50, r=50, t=20, b=60))

        _card_style = {
            'backgroundColor': COLORS['dark_secondary'],
            'border': f'1px solid {COLORS["dark_border"]}',
            'borderRadius': '8px', 'padding': '12px 8px',
        }
        _title_style = {
            'color': GOLD, 'fontWeight': '700', 'fontSize': '0.82rem',
            'textAlign': 'center', 'marginBottom': '2px',
            'textTransform': 'uppercase', 'letterSpacing': '0.06em',
        }

        def _radar_col(title, fig):
            body = (
                dcc.Graph(figure=fig, config=CHART_CONFIG)
                if fig is not None
                else html.Div("No data", style={'color': COLORS['text_secondary'],
                                                'textAlign': 'center', 'padding': '40px 0'})
            )
            return dbc.Col(
                html.Div([html.Div(title, style=_title_style), body], style=_card_style),
                lg=4, md=12, className='mb-3',
            )

        return html.Div([
            _section_divider("Performance Radars"),
            dbc.Row([
                _radar_col("Attack", atk_fig),
                _radar_col("Defence", def_fig),
                _radar_col("Possession & Build-Up", bup_fig),
            ], className='g-3'),
        ])

    def _section_cb(sec_id, builder_fn):
        """Register one section callback."""
        import traceback

        @app.callback(
            Output(f'pma-sec-{sec_id}', 'children'),
            Input('pma-selected-match', 'data'),
        )
        def _cb(match_id, _fn=builder_fn, _key=sec_id):
            if not match_id:
                return html.P("Select a match from the calendar.",
                              style={'color': COLORS['text_secondary']})
            events = get_match_events(match_id)
            if events.empty:
                return html.P("No event data available.",
                              style={'color': COLORS['text_secondary']})
            try:
                return _fn(events)
            except Exception as e:
                log.error("Section '%s' failed: %s\n%s", _key, e, traceback.format_exc())
                return html.P(f"Error rendering section: {e}",
                              style={'color': '#dc3545', 'fontSize': '0.85rem'})

    _section_cb("overview",    build_overview_tab)
    _section_cb("attack",      build_attacking_output_tab)
    _section_cb("buildup",     build_build_up_passing_tab)
    _section_cb("defense",     build_defensive_structure_tab)
    _section_cb("transitions", build_transitions_counterpressing_tab)
    _section_cb("goalkeeping", build_goalkeeping_tab)
    _section_cb("playerstats", build_player_stats_tab)

    @app.callback(
        Output('pma-report-link', 'href'),
        Input('pma-selected-match', 'data'),
    )
    def update_report_link(match_id):
        if not match_id:
            return '#'
        return f'/download-report/{match_id}'

    register_overview_callbacks(app)
    register_build_up_passing_callbacks(app)
    register_defensive_structure_callbacks(app)
    register_transitions_counterpressing_callbacks(app)
    register_goalkeeping_callbacks(app)
    register_player_stats_callbacks(app)
