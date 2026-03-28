"""
Tab 1 -- Match Overview

Horizontal mplsoccer pitch showing both starting XIs with formation dots,
jersey numbers, player names, and captain badge. Substitutes panels flank
the pitch. TV-style stat comparison bars are displayed below.
"""

import io
import base64
import matplotlib.pyplot as plt
import matplotlib.patheffects as mpe
from mplsoccer import Pitch
import pandas as pd
import plotly.graph_objects as go

from dash import html, dcc, ctx
from dash.dependencies import Input, Output, State
import dash_bootstrap_components as dbc

from utils.config import COLORS
from utils.data_utils import get_match_lineup, get_match_events
from utils.match_data_adapter import (
    get_match_metadata,
    compute_team_kpis,
    get_starting_lineups,
    get_substitutions,
)


from .shared import section_header
from page_utils.visualizations import (
    HOME_COLOR,
    AWAY_COLOR,
    GOLD,
    add_vertical_pitch_background,
    VPITCH_AXIS,
)


# =============================================================================
# Period filter helpers (stat bars only)
# =============================================================================

_OV_PERIOD_OPTIONS = [
    ('Full Match', 'full'),
    ('1st Half',   '1'),
    ('2nd Half',   '2'),
]


def _ov_period_btn_style(active: bool) -> dict:
    if active:
        return {
            'backgroundColor': GOLD, 'color': '#1A1D2E',
            'border': f'1px solid {GOLD}',
            'borderRadius': '6px', 'padding': '5px 14px',
            'cursor': 'pointer', 'fontSize': '0.85rem', 'fontWeight': '600',
        }
    return {
        'backgroundColor': COLORS['dark_secondary'], 'color': COLORS['text_primary'],
        'border': f'1px solid {COLORS["dark_border"]}',
        'borderRadius': '6px', 'padding': '5px 14px',
        'cursor': 'pointer', 'fontSize': '0.85rem',
    }


def _build_controls_bar() -> html.Div:
    """Period toggle + subs checkbox arranged in one neat horizontal row."""
    return html.Div([
        html.Span("Period:", style={
            'color': COLORS['text_secondary'], 'fontSize': '0.85rem',
            'marginRight': '10px', 'alignSelf': 'center',
            'whiteSpace': 'nowrap',
        }),
        html.Div([
            html.Button(label,
                        id=f'pma-ov-period-btn-{val}',
                        n_clicks=0,
                        style=_ov_period_btn_style(active=(val == 'full')))
            for label, val in _OV_PERIOD_OPTIONS
        ], style={'display': 'flex', 'gap': '6px', 'alignItems': 'center'}),
        # Vertical divider
        html.Div(style={
            'width': '1px', 'height': '22px',
            'backgroundColor': COLORS['dark_border'],
            'margin': '0 16px', 'alignSelf': 'center', 'flexShrink': '0',
        }),
        dcc.Checklist(
            id='pma-ov-subs-toggle',
            options=[{'label': '  Show substitutes', 'value': 'subs'}],
            value=[],
            labelStyle={
                'color': COLORS['text_secondary'], 'fontSize': '0.85rem',
                'cursor': 'pointer', 'userSelect': 'none',
                'alignSelf': 'center', 'whiteSpace': 'nowrap',
            },
            inputStyle={
                'marginRight': '6px', 'accentColor': GOLD,
                'cursor': 'pointer', 'width': '14px', 'height': '14px',
            },
        ),
    ], style={
        'display': 'flex', 'alignItems': 'center',
        'flexWrap': 'wrap', 'gap': '4px',
        'marginBottom': '16px',
    })


# =============================================================================
# Formation → slot → (x, y) coordinate tables
# =============================================================================
# Coordinates are for the HOME team (attacking left → right).
# x ∈ [2, 48]: distance from home goal (GK ≈ 4, forward line ≈ 48).
# y ∈ [5, 95]: lateral position (0 = right touchline, 100 = left).
# Away team mirrors via x_away = 100 − x_home.

_COORDS: dict = {
    "433": {
        1:  (4,  50),   # GK
        2:  (22, 13),   # RB
        5:  (18, 33),   # CB-R
        6:  (18, 67),   # CB-L
        3:  (22, 87),   # LB
        7:  (37, 23),   # MC-R
        4:  (37, 50),   # MC-C
        8:  (37, 77),   # MC-L
        10: (47, 17),   # RW (Opta slot 10 = right forward in 4-3-3)
        9:  (47, 50),   # CF
        11: (47, 83),   # LW (Opta slot 11 = left forward in 4-3-3)
    },
    "4231": {
        1:  (4,  50),   # GK
        2:  (22, 13),   # RB
        5:  (18, 33),   # CB-R
        6:  (18, 67),   # CB-L
        3:  (22, 87),   # LB
        4:  (32, 37),   # CDM-R
        8:  (32, 63),   # CDM-L
        7:  (43, 17),   # RW
        10: (43, 50),   # CAM
        11: (43, 83),   # LW
        9:  (48, 50),   # CF
    },
    "442": {
        1:  (4,  50),
        2:  (22, 13),   # RB
        5:  (18, 33),   # CB-R
        6:  (18, 67),   # CB-L
        3:  (22, 87),   # LB
        7:  (38, 12),   # RM
        4:  (37, 37),   # CM-R
        8:  (37, 63),   # CM-L
        11: (38, 88),   # LM
        9:  (47, 35),   # RS
        10: (47, 65),   # LS
    },
    "4141": {
        1:  (4,  50),
        2:  (22, 13),   # RB
        5:  (18, 33),   # CB-R
        6:  (18, 67),   # CB-L
        3:  (22, 87),   # LB
        4:  (31, 50),   # CDM
        7:  (40, 13),   # RM
        8:  (40, 37),   # CM-R
        10: (40, 63),   # CM-L
        11: (40, 87),   # LM
        9:  (48, 50),   # ST
    },
    "4321": {
        1:  (4,  50),
        2:  (22, 13),   # RB
        5:  (18, 33),   # CB-R
        6:  (18, 67),   # CB-L
        3:  (22, 87),   # LB
        4:  (34, 27),   # MC-R
        7:  (34, 50),   # MC-C
        8:  (34, 73),   # MC-L
        9:  (44, 30),   # SS-R
        10: (47, 50),   # CF
        11: (44, 70),   # SS-L
    },
    "352": {
        1:  (4,  50),
        5:  (17, 23),   # CB-R
        6:  (17, 50),   # CB-C
        11: (17, 77),   # CB-L
        2:  (30, 10),   # RWB
        4:  (36, 30),   # CM-R
        7:  (36, 50),   # CM-C
        8:  (36, 70),   # CM-L
        3:  (30, 90),   # LWB
        9:  (47, 35),   # RS
        10: (47, 65),   # LS
    },
    "451": {
        1:  (4,  50),
        2:  (22, 13),   # RB
        5:  (18, 33),   # CB-R
        6:  (18, 67),   # CB-L
        3:  (22, 87),   # LB
        7:  (37, 12),   # RM
        4:  (37, 30),   # CM-R
        8:  (37, 50),   # CM-C
        10: (37, 70),   # CM-L
        11: (37, 88),   # LM
        9:  (47, 50),   # CF
    },
    "3421": {
        1:  (4,  50),
        5:  (18, 25),   # CB-R
        6:  (18, 50),   # CB-C
        8:  (18, 75),   # CB-L
        2:  (33, 12),   # RM
        4:  (38, 36),   # AM-R
        7:  (38, 64),   # AM-L
        3:  (33, 88),   # LM
        9:  (45, 35),   # SS-R
        10: (47, 50),   # CF
        11: (45, 65),   # SS-L
    },
    "343": {
        1:  (4,  50),
        5:  (18, 25),   # CB-R
        6:  (18, 50),   # CB-C
        11: (18, 75),   # CB-L
        2:  (36, 20),   # CM-R
        3:  (36, 40),   # CM-CL
        4:  (36, 60),   # CM-CR
        10: (36, 80),   # CM-L
        7:  (47, 20),   # RW/LW
        8:  (47, 50),   # CF
        9:  (47, 80),   # LW/RW
    },
    "4132": {
        1:  (4,  50),
        2:  (22, 13),   # RB
        5:  (18, 33),   # CB-R
        6:  (18, 67),   # CB-L
        3:  (22, 87),   # LB
        4:  (31, 50),   # CDM
        7:  (39, 23),   # CM-R
        8:  (39, 77),   # CM-L
        11: (43, 50),   # CAM
        9:  (47, 35),   # SS-R
        10: (47, 65),   # SS-L
    },
    "4312": {
        1:  (4,  50),
        2:  (22, 13),   # RB
        5:  (18, 33),   # CB-R
        6:  (18, 67),   # CB-L
        3:  (22, 87),   # LB
        7:  (33, 23),   # MC-R
        4:  (33, 50),   # MC-C
        11: (33, 77),   # MC-L
        8:  (42, 50),   # CAM
        9:  (47, 33),   # SS-R
        10: (47, 67),   # SS-L
    },
    "3142": {
        1:  (4,  50),
        5:  (17, 25),   # CB-R
        6:  (17, 50),   # CB-C
        11: (17, 75),   # CB-L
        8:  (29, 50),   # CDM
        2:  (37, 15),   # RM
        7:  (37, 35),   # CM-R
        4:  (37, 65),   # CM-L
        3:  (37, 85),   # LM
        9:  (47, 35),   # RS
        10: (47, 65),   # LS
    },
}


# =============================================================================
# Helper functions
# =============================================================================

def _get_slot_coords(formation: str, slot: int, is_home: bool):
    """Return Opta (x, y) pitch coordinates for a formation slot."""
    coords_home = _COORDS.get(formation, {})
    if slot in coords_home:
        x, y = coords_home[slot]
        return (x, y) if is_home else (100 - x, 100 - y)

    # Generic fallback: parse formation string and distribute evenly
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
    """Abbreviate long names: 'Roberto Lewandowski' → 'R. Lewandowski'."""
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
    """Format '433' → '4-3-3'."""
    if not formation_str or len(formation_str) < 2:
        return formation_str or ''
    return '-'.join(formation_str)


# =============================================================================
# Lineup pitch image generator (pitch only — side panels are HTML)
# =============================================================================

def _generate_lineup_pitch_image(
    lineup_df: pd.DataFrame,
    home_team: str,
    away_team: str,
    home_color: str,
    away_color: str,
) -> str | None:
    """
    Render a compact horizontal mplsoccer pitch with both starting XIs.

    Side panels (starters list + subs) are handled as HTML components,
    so this function draws only the pitch itself.
    Returns a base64-encoded PNG string, or None on failure.
    """
    if lineup_df is None or lineup_df.empty:
        return None

    home = lineup_df[lineup_df['team_position'] == 'home']
    away = lineup_df[lineup_df['team_position'] == 'away']

    home_start = home[home['role'] == 'Start'].copy()
    away_start = away[away['role'] == 'Start'].copy()

    home_fmt = home_start['formation'].iloc[0] if not home_start.empty else ''
    away_fmt = away_start['formation'].iloc[0] if not away_start.empty else ''

    # ── Figure — pitch only ───────────────────────────────────────────────────
    fig, ax_p = plt.subplots(figsize=(15, 7.5), facecolor='#0A0E27')
    fig.subplots_adjust(left=0.01, right=0.99, top=0.90, bottom=0.02)
    ax_p.set_facecolor('#0A0E27')

    # ── Draw pitch ────────────────────────────────────────────────────────────
    pitch = Pitch(
        pitch_type='opta',
        pitch_color='#3a7d44',
        line_color='white',
        stripe=True,
        stripe_color='#2e6b39',
        goal_type='box',
        goal_alpha=0.85,
        pad_top=5, pad_bottom=5, pad_left=3, pad_right=3,
    )
    pitch.draw(ax=ax_p)

    # ── "Starting XI" title above the pitch ───────────────────────────────────
    fig.text(0.5, 0.97, 'Starting XI',
             ha='center', va='top',
             fontsize=16, color='white', fontweight='bold',
             path_effects=[mpe.withStroke(linewidth=3, foreground='#0A0E27')])

    # ── Player dots renderer ──────────────────────────────────────────────────
    def _draw_players(starters, formation, is_home, dot_color):
        xs, ys, jerseys, names, caps = [], [], [], [], []

        for _, row in starters.iterrows():
            slot = int(row['formation_slot'])
            name = str(row.get('player_name', '') or '').strip()
            try:
                jersey = int(row['jersey_number'])
            except (ValueError, TypeError):
                jersey = ''
            is_cap = bool(row.get('is_captain', False))
            x, y = _get_slot_coords(formation, slot, is_home)
            xs.append(x); ys.append(y)
            jerseys.append(str(jersey)); names.append(name); caps.append(is_cap)

        if not xs:
            return

        # Glow rings
        pitch.scatter(xs, ys, s=900, c=dot_color, ax=ax_p,
                      zorder=4, alpha=0.22, edgecolors='none')
        # Main filled circles
        pitch.scatter(xs, ys, s=650, c=dot_color, ax=ax_p,
                      zorder=5, alpha=0.95, edgecolors='white', linewidths=1.6)

        # Jersey numbers, names, and captain badges
        for i, (x, y) in enumerate(zip(xs, ys)):
            # Jersey number inside dot
            ax_p.text(x, y, jerseys[i],
                      ha='center', va='center',
                      fontsize=9, fontweight='bold', color='white', zorder=7)
            # Player name below dot — larger, readable
            short = _shorten_name(names[i])
            ax_p.text(x, y - 5.2, short,
                      ha='center', va='top',
                      fontsize=8.5, color='white', zorder=7,
                      path_effects=[mpe.withStroke(linewidth=2.5,
                                                    foreground='#0A0E27')])
            # Captain badge
            if caps[i]:
                bx = x + (3.0 if is_home else -3.0)
                by = y + 3.0
                pitch.scatter([bx], [by], s=160, c=GOLD, ax=ax_p,
                              zorder=8, edgecolors='none')
                ax_p.text(bx, by, 'C',
                          ha='center', va='center',
                          fontsize=5.5, fontweight='bold', color='#0A0E27', zorder=9)

    _draw_players(home_start, home_fmt, True,  home_color)
    _draw_players(away_start, away_fmt, False, away_color)

    # ── Formation labels ──────────────────────────────────────────────────────
    for tx, fmt, col in [
        (14,  _format_formation(home_fmt),  home_color),
        (86,  _format_formation(away_fmt),  away_color),
    ]:
        ax_p.text(tx, 107, fmt,
                  ha='center', va='bottom',
                  fontsize=13, color=col, fontweight='bold',
                  path_effects=[mpe.withStroke(linewidth=2.5, foreground='#0A0E27')])

    # ── Export ────────────────────────────────────────────────────────────────
    buf = io.BytesIO()
    fig.savefig(buf, format='png', dpi=130,
                facecolor=fig.get_facecolor(), edgecolor='none',
                bbox_inches='tight')
    buf.seek(0)
    img_b64 = base64.b64encode(buf.read()).decode()
    plt.close(fig)
    return img_b64


# =============================================================================
# HTML lineup side panel (starters list + substitution pairs)
# =============================================================================

def _build_lineup_html_panel(
    subs_list: list,
    color: str,
    align: str = 'left',
) -> html.Div:
    """
    Build an HTML side panel showing only substitutions for one team.

    Each sub block shows the minute, who came off (↓ red), and who came on (↑ green).
    """
    is_right = align == 'right'
    text_align = 'right' if is_right else 'left'

    # ── Substitution pairs ────────────────────────────────────────────────────
    sub_rows = []
    for s in subs_list:
        minute = s.get('minute', 0) or 0
        p_off  = _shorten_name(s.get('player_off') or '')
        p_on   = _shorten_name(s.get('player_on')  or '')
        is_inj = s.get('reason', '') == 'Injury'

        # Skip completely blank entries (e.g. injury sub with no paired name)
        if not p_off and not p_on:
            continue

        inj_icon = html.Span(' ⚕', style={
            'color': '#ff6b6b', 'fontSize': '0.72rem',
        }) if is_inj else html.Span()

        sub_rows.append(html.Div([
            # Minute
            html.Div(
                html.Span(f"{minute}'", style={
                    'color': GOLD, 'fontWeight': '700', 'fontSize': '0.82rem',
                }),
                style={'textAlign': text_align, 'marginBottom': '1px'},
            ),
            # Player off
            html.Div([
                html.Span('↓ ', style={'color': '#ff6b6b', 'fontWeight': '700',
                                        'fontSize': '0.95rem'}),
                html.Span(p_off or '—', style={'color': COLORS['text_secondary'],
                                                'fontSize': '0.88rem'}),
                inj_icon,
            ], style={'textAlign': text_align}),
            # Player on
            html.Div([
                html.Span('↑ ', style={'color': '#51cf66', 'fontWeight': '700',
                                        'fontSize': '0.95rem'}),
                html.Span(p_on or '—', style={'color': '#E8E9ED', 'fontSize': '0.88rem',
                                               'fontWeight': '500'}),
            ], style={'textAlign': text_align}),
        ], style={
            'padding': '6px 0',
            'borderBottom': f"1px solid {COLORS['dark_border']}",
        }))

    header = html.Div('Substitutions', style={
        'color': color, 'fontSize': '0.78rem', 'fontWeight': '700',
        'textTransform': 'uppercase', 'letterSpacing': '0.05em',
        'marginBottom': '8px', 'textAlign': text_align,
    })

    content = [header, *sub_rows] if sub_rows else [
        header,
        html.Div('No substitutions', style={
            'color': COLORS['text_secondary'], 'fontSize': '0.82rem',
            'textAlign': text_align,
        }),
    ]

    return html.Div(content, style={
        'padding': '14px 16px',
        'backgroundColor': COLORS['dark_secondary'],
        'borderRadius': '8px',
        'border': f"1px solid {COLORS['dark_border']}",
        'height': '100%',
    })


# =============================================================================
# TV-style stat bar component
# =============================================================================

def _tv_stat_bar(label, home_val, away_val, suffix='', is_percentage=False, decimals=0, tooltip=None):
    """
    Build a single TV-broadcast-style comparison bar.

    Layout:  home_value  [=====|=====]  away_value
                      stat label

    Parameters
    ----------
    decimals : int
        Decimal places for display. 0 = integer (default). Use 2 for xG.
    tooltip : str | None
        If provided, shown on hover over the label (native browser title attribute).
    """
    hv = float(home_val) if home_val else 0
    av = float(away_val) if away_val else 0
    max_val = max(hv, av, 1)

    home_pct = (hv / max_val) * 100
    away_pct = (av / max_val) * 100

    if is_percentage:
        h_display = f"{hv:.1f}{suffix}"
        a_display = f"{av:.1f}{suffix}"
    elif decimals > 0:
        h_display = f"{hv:.{decimals}f}{suffix}"
        a_display = f"{av:.{decimals}f}{suffix}"
    else:
        h_display = f"{int(hv)}{suffix}"
        a_display = f"{int(av)}{suffix}"

    h_weight = 'bold' if hv >= av else 'normal'
    a_weight = 'bold' if av >= hv else 'normal'

    bar_track = {
        'height': '14px',
        'borderRadius': '7px',
        'backgroundColor': COLORS['dark_tertiary'],
        'overflow': 'hidden',
        'display': 'flex',
    }

    label_style = {
        'textAlign': 'center',
        'color': COLORS['text_secondary'],
        'fontSize': '0.85rem',
        'marginBottom': '4px',
    }
    if tooltip:
        label_style['cursor'] = 'help'
        label_style['borderBottom'] = f"1px dashed {COLORS['text_secondary']}"
        label_style['display'] = 'inline-block'

    label_el = html.Div(
        html.Span(label, title=tooltip, style=label_style) if tooltip
        else label,
        style={'textAlign': 'center', 'marginBottom': '4px'} if tooltip else label_style,
    )

    return html.Div([
        label_el,
        html.Div([
            html.Div(h_display, style={
                'width': '65px', 'textAlign': 'right', 'fontWeight': h_weight,
                'color': HOME_COLOR, 'fontSize': '1.05rem', 'paddingRight': '10px',
            }),
            html.Div([
                html.Div([
                    html.Div(style={
                        'width': f'{home_pct}%',
                        'height': '100%',
                        'backgroundColor': HOME_COLOR,
                        'borderRadius': '7px 0 0 7px',
                        'marginLeft': 'auto',
                        'transition': 'width 0.4s ease',
                    })
                ], style={**bar_track, 'width': '50%', 'justifyContent': 'flex-end',
                          'borderRadius': '7px 0 0 7px'}),
                html.Div(style={
                    'width': '2px', 'height': '14px',
                    'backgroundColor': COLORS['text_secondary'],
                    'flexShrink': '0',
                }),
                html.Div([
                    html.Div(style={
                        'width': f'{away_pct}%',
                        'height': '100%',
                        'backgroundColor': AWAY_COLOR,
                        'borderRadius': '0 7px 7px 0',
                        'transition': 'width 0.4s ease',
                    })
                ], style={**bar_track, 'width': '50%', 'borderRadius': '0 7px 7px 0'}),
            ], style={'display': 'flex', 'alignItems': 'center', 'flex': '1'}),
            html.Div(a_display, style={
                'width': '65px', 'textAlign': 'left', 'fontWeight': a_weight,
                'color': AWAY_COLOR, 'fontSize': '1.05rem', 'paddingLeft': '10px',
            }),
        ], style={'display': 'flex', 'alignItems': 'center'}),
    ], style={'marginBottom': '14px'})


# =============================================================================
# Fallback text lineup components (used when no lineup parquet is found)
# =============================================================================

_POS_LABEL_COLOR = {
    'GK': '#ffc107',
    'RB': '#4dabf7', 'CB': '#4dabf7', 'LB': '#4dabf7',
    'CDM': '#51cf66', 'CM': '#51cf66', 'MC': '#51cf66', 'CAM': '#51cf66',
    'RM': '#ff922b', 'RW': '#ff922b', 'LM': '#ff922b', 'LW': '#ff922b',
    'CF': '#ff6b6b',
}


def _build_lineup_card(team_name, lineup_data, color, align='start'):
    """Build a text-based lineup card for one team (fallback)."""
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
    """Build a single substitution row (fallback)."""
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
            'width': '32px', 'textAlign': 'right', 'flexShrink': '0',
            'marginRight': '10px',
        }),
        html.I(className="fas fa-arrow-down",
               style={'color': '#ff6b6b', 'fontSize': '0.65rem', 'marginRight': '4px'}),
        html.Span(f"{j_off} ", style={
            'color': COLORS['text_secondary'], 'fontSize': '0.75rem', 'fontWeight': '600',
        }),
        html.Span(p_off, style={'color': COLORS['text_secondary'], 'fontSize': '0.8rem'}),
        reason_icon,
        html.Span(" ", style={'width': '12px', 'flexShrink': '0'}),
        html.I(className="fas fa-arrow-up",
               style={'color': '#51cf66', 'fontSize': '0.65rem', 'marginRight': '4px'}),
        html.Span(f"{j_on} ", style={
            'color': COLORS['text_primary'], 'fontSize': '0.75rem', 'fontWeight': '600',
        }),
        html.Span(p_on, style={'color': COLORS['text_primary'], 'fontSize': '0.8rem',
                               'fontWeight': '500'}),
    ], style={'display': 'flex', 'alignItems': 'center', 'padding': '4px 0'})


def _build_subs_section(team_name, subs_list, color):
    """Build substitution section (fallback)."""
    if not subs_list:
        return html.Div()
    return html.Div([
        html.Div("Substitutions", style={
            'color': color, 'fontSize': '0.8rem', 'fontWeight': '700',
            'marginBottom': '6px', 'textTransform': 'uppercase',
            'letterSpacing': '0.05em',
        }),
        *[_build_sub_row(s, color) for s in subs_list],
    ], style={
        'padding': '12px 16px', 'backgroundColor': COLORS['dark_secondary'],
        'borderRadius': '8px', 'border': f"1px solid {COLORS['dark_border']}",
        'marginTop': '8px',
    })


# =============================================================================
# Stat bars builder (extracted so the period-filter callback can call it)
# =============================================================================

def _build_stat_bars(home_kpis: dict, away_kpis: dict) -> html.Div:
    """Build the TV-style stat comparison bars for the given KPI dicts."""
    return html.Div([
        _tv_stat_bar('Possession',
                     home_kpis.get('possession', 50), away_kpis.get('possession', 50),
                     '%', is_percentage=True),
        _tv_stat_bar('Shots',
                     home_kpis.get('shots', 0), away_kpis.get('shots', 0)),
        _tv_stat_bar('Shots on Target',
                     home_kpis.get('shots_on_target', 0), away_kpis.get('shots_on_target', 0)),
        _tv_stat_bar('xG',
                     home_kpis.get('xg', 0.0), away_kpis.get('xg', 0.0),
                     decimals=2,
                     tooltip='Expected goals (xG) — how many goals a team should have scored on average based on the number and quality of shots taken.'),
        _tv_stat_bar('Assists',
                     home_kpis.get('assists', 0), away_kpis.get('assists', 0)),
        _tv_stat_bar('Blocked Shots',
                     home_kpis.get('blocked_shots', 0), away_kpis.get('blocked_shots', 0)),
        _tv_stat_bar('Passes',
                     home_kpis.get('passes', 0), away_kpis.get('passes', 0)),
        _tv_stat_bar('Pass Accuracy',
                     home_kpis.get('pass_accuracy', 0), away_kpis.get('pass_accuracy', 0),
                     '%', is_percentage=True),
        _tv_stat_bar('Fouls Committed',
                     home_kpis.get('fouls', 0), away_kpis.get('fouls', 0)),
        _tv_stat_bar('Corners',
                     home_kpis.get('corners', 0), away_kpis.get('corners', 0)),
        _tv_stat_bar('Offsides',
                     home_kpis.get('offsides', 0), away_kpis.get('offsides', 0)),
        _tv_stat_bar('Interceptions',
                     home_kpis.get('interceptions', 0), away_kpis.get('interceptions', 0)),
        _tv_stat_bar('Yellow Cards',
                     home_kpis.get('yellow_cards', 0), away_kpis.get('yellow_cards', 0)),
        _tv_stat_bar('Red Cards',
                     home_kpis.get('red_cards', 0), away_kpis.get('red_cards', 0)),
    ], style={
        'padding': '24px',
        'backgroundColor': COLORS['dark_secondary'],
        'borderRadius': '8px',
        'border': f"1px solid {COLORS['dark_border']}",
        'maxWidth': '640px',
        'margin': '0 auto',
    })


# =============================================================================
# Average position pitch helpers
# =============================================================================

def _compute_avg_positions(
    events: pd.DataFrame,
    lineup_df: pd.DataFrame,
    team_position: str,
    include_subs: bool = False,
) -> list:
    """
    Compute per-player average x, y positions from event coordinates.

    Opta event x is always from the acting team's perspective (0 = own goal,
    100 = opponent goal), so both home and away player lists can be plotted
    with the same orientation (attack left→right / bottom→top).

    Returns a list of dicts keyed: player_name, jersey_number, avg_x, avg_y,
    role ('Start'/'Sub'), is_captain.
    """
    if events is None or events.empty:
        return []

    team_evts = events[events['team_position'] == team_position].copy()
    # Drop system events that have null coordinates (x=0, y=0 together)
    team_evts = team_evts[~((team_evts['x'] == 0) & (team_evts['y'] == 0))]
    team_evts = team_evts[
        team_evts['player_name'].notna() & (team_evts['player_name'] != '')
    ]
    if team_evts.empty:
        return []

    # Build per-player metadata lookup from lineup
    player_info: dict = {}
    if lineup_df is not None and not lineup_df.empty:
        for _, row in lineup_df[lineup_df['team_position'] == team_position].iterrows():
            name = str(row.get('player_name', '') or '').strip()
            if not name:
                continue
            player_info[name] = {
                'jersey_number': row.get('jersey_number', ''),
                'is_captain':    bool(row.get('is_captain', False)),
                'role':          str(row.get('role', 'Start')),
                'sub_on_minute': row.get('sub_on_minute', None),
            }

    result = []
    for name, grp in team_evts.groupby('player_name'):
        info    = player_info.get(str(name), {})
        role    = info.get('role', 'Start')
        if role == 'Sub' and not include_subs:
            continue

        # For subs, only average events after they came on
        sub_min = info.get('sub_on_minute', None)
        if role == 'Sub' and sub_min is not None and pd.notna(sub_min):
            grp = grp[grp['time_min'] >= float(sub_min)]

        if len(grp) < 3:
            continue

        result.append({
            'player_name':   str(name),
            'jersey_number': info.get('jersey_number', ''),
            'avg_x':         float(grp['x'].mean()),
            'avg_y':         float(grp['y'].mean()),
            'role':          role,
            'is_captain':    info.get('is_captain', False),
        })

    # Sort by avg_x ascending: GK → defenders → midfield → forwards
    result.sort(key=lambda p: p['avg_x'])
    return result


def _build_avg_pos_fig(
    players: list,
    color: str,
    team_name: str = '',
    is_home: bool = True,
) -> go.Figure:
    """
    Build an interactive Plotly figure showing per-player average positions.

    A grass vertical pitch background (via shared.add_vertical_pitch_background)
    is overlaid with Plotly scatter traces so jersey numbers appear as text and
    hovering reveals the full player name.

    Home team attacks upward (pitch_x = 0 at bottom = own goal).
    Away team is flipped so they attack downward (own goal at top).

    Direction of attack is shown as a gradient shadow on the pitch itself —
    darkest near the own-goal end, fading to transparent toward the attack end.

    Coordinate mapping:
      Plotly x = pitch_y (0-100 width)
      Plotly y = pitch_x (0-100 length) for home,  or  100 - pitch_x for away
    """
    fig = go.Figure()

    # ── Pitch background (shared utility from shared.py) ──────────────────────
    add_vertical_pitch_background(fig)

    # ── Direction-of-attack shadow (rendered on the pitch, not outside it) ────
    # Home: shadow darkens toward y_min (bottom = own goal).
    # Away: shadow darkens toward y_max (top = own goal after y-flip).
    x_min, x_max = VPITCH_AXIS['xaxis']['range']
    y_min, y_max = VPITCH_AXIS['yaxis']['range']
    sy = y_max - y_min
    n_bands = 30
    band_h  = sy / n_bands
    for i in range(n_bands):
        alpha = 0.22 * (1.0 - i / n_bands)
        if alpha < 0.005:
            continue
        if is_home:
            y0 = y_min + i * band_h
        else:
            y0 = y_max - (i + 1) * band_h
        fig.add_shape(
            type='rect',
            x0=x_min, x1=x_max,
            y0=y0, y1=y0 + band_h,
            fillcolor=f'rgba(0,0,0,{alpha:.3f})',
            line_width=0, layer='below',
        )

    # ── Direction-of-attack indicator ─────────────────────────────────────────
    # Home attacks upward → label near top goal; away attacks downward → near bottom goal.
    fig.add_annotation(
        x=3, y=96 if is_home else 4,
        xref='x', yref='y',
        xanchor='left',
        text='⬆ Attacking Direction' if is_home else '⬇ Attacking Direction',
        showarrow=False,
        font=dict(color='black', size=16, family='Arial'),
        align='left',
        bgcolor='rgba(255,255,255,0.7)',
        borderpad=3,
    )

    # ── Player dots (starters then subs) ──────────────────────────────────────
    for is_sub in (False, True):
        group = [p for p in players if (p.get('role') == 'Sub') == is_sub]
        if not group:
            continue

        # Home y is from home's attacking perspective (y=0 = their right touchline),
        # which is the mirror of the display's x-axis (x=0 = left touchline), so flip.
        # Away y is already consistent with the absolute display orientation.
        if is_home:
            py_arr = [100.0 - float(p['avg_y']) for p in group]
        else:
            py_arr = [float(p['avg_y']) for p in group]
        px_arr = [float(p['avg_x']) for p in group]   # pitch length
        plot_y = px_arr if is_home else [100.0 - v for v in px_arr]

        jerseys = [str(p.get('jersey_number', '') or '') for p in group]
        names   = [str(p.get('player_name', ''))         for p in group]

        fig.add_trace(go.Scatter(
            x=py_arr, y=plot_y,
            mode='markers+text',
            marker=dict(
                size=20 if not is_sub else 14,
                color=color,
                opacity=0.90 if not is_sub else 0.55,
                line=dict(color='white', width=2 if not is_sub else 1.2),
            ),
            text=jerseys,
            textfont=dict(color='white', size=9 if not is_sub else 7,
                          family='Arial, sans-serif'),
            textposition='middle center',
            customdata=names,
            hovertemplate='<b>%{customdata}</b><extra></extra>',
            showlegend=False,
        ))


    # ── Figure layout ─────────────────────────────────────────────────────────
    fig.update_layout(
        paper_bgcolor='#0A0E27',
        plot_bgcolor='rgba(0,0,0,0)',
        margin=dict(l=0, r=0, t=26 if team_name else 4, b=0),
        height=780,
        **VPITCH_AXIS,
        title=dict(
            text=f'<b>{team_name}</b>',
            x=0.5, y=0.995, xanchor='center', yanchor='top',
            font=dict(size=11, color=color),
        ) if team_name else {},
        hoverlabel=dict(bgcolor='#1A1D2E', font_color='white', font_size=12),
        dragmode=False,
    )
    return fig


def _build_avg_pos_component(
    fig: 'go.Figure | None',
    team_name: str = '',
    color: str = GOLD,
) -> html.Div:
    """Wrap an average-position Plotly figure in a styled card."""
    if fig is None:
        return html.Div('Position data unavailable', style={
            'textAlign': 'center', 'color': COLORS['text_secondary'],
            'fontSize': '0.82rem', 'padding': '20px 0',
        })
    return html.Div([
        html.Div('Average Positions', style={
            'textAlign': 'center',
            'color': COLORS['text_secondary'],
            'fontSize': '0.72rem', 'fontWeight': '600',
            'textTransform': 'uppercase', 'letterSpacing': '0.06em',
            'marginBottom': '4px',
        }),
        dcc.Graph(
            figure=fig,
            config={'displayModeBar': False},
            style={'width': '100%'},
        ),
    ], style={
        'backgroundColor': COLORS['dark_secondary'],
        'borderRadius': '4px',
        'border': f"1px solid {COLORS['dark_border']}",
        'padding': '4px',
        'height': '100%',
    })


# =============================================================================
# Public tab builder
# =============================================================================

def build_overview_tab(events):
    """Render the Match Overview tab."""
    meta       = get_match_metadata(events)
    home_kpis  = compute_team_kpis(events, 'home')
    away_kpis  = compute_team_kpis(events, 'away')

    home_team  = meta.get('home_team', 'Home')
    away_team  = meta.get('away_team', 'Away')
    match_id   = str(meta.get('match_id', ''))

    # ── Lineup section ────────────────────────────────────────────────────────
    lineup_df = get_match_lineup(match_id) if match_id else pd.DataFrame()
    subs      = get_substitutions(events)
    pitch_img = None

    if not lineup_df.empty:
        try:
            pitch_img = _generate_lineup_pitch_image(
                lineup_df, home_team, away_team, HOME_COLOR, AWAY_COLOR
            )
        except Exception:
            pitch_img = None

    if pitch_img:
        home_panel = _build_lineup_html_panel(
            subs.get('home', []), HOME_COLOR, align='left'
        )
        away_panel = _build_lineup_html_panel(
            subs.get('away', []), AWAY_COLOR, align='right'
        )

        lineup_section = html.Div([
            section_header('Line-Ups'),
            dbc.Row([
                dbc.Col(home_panel, lg=3, md=6, xs=12, className='mb-3'),
                dbc.Col(
                    dbc.Card([
                        dbc.CardBody([
                            html.Img(
                                src=f'data:image/png;base64,{pitch_img}',
                                style={
                                    'width': '100%', 'display': 'block',
                                    'borderRadius': '6px',
                                },
                            )
                        ], style={'padding': '8px'})
                    ], style={
                        'backgroundColor': COLORS['dark_secondary'],
                        'border': f"1px solid {COLORS['dark_border']}",
                    }),
                    lg=6, md=12, xs=12, className='mb-3',
                ),
                dbc.Col(away_panel, lg=3, md=6, xs=12, className='mb-3'),
            ], align='start'),
        ], className='mb-4')

    else:
        # Fallback: text-based lineups side by side
        lineups = get_starting_lineups(events)
        lineup_section = html.Div([
            section_header('Line-Ups'),
            dbc.Row([
                dbc.Col([
                    html.H6("Starting XI", style={
                        'color': HOME_COLOR, 'fontWeight': '700', 'marginBottom': '8px',
                        'textTransform': 'uppercase', 'letterSpacing': '0.05em',
                        'fontSize': '0.8rem',
                    }),
                    _build_lineup_card(home_team, lineups.get('home', {}),
                                       HOME_COLOR, align='start'),
                    _build_subs_section(home_team, subs.get('home', []), HOME_COLOR),
                ], lg=6, md=12, className='mb-3'),
                dbc.Col([
                    html.H6("Starting XI", style={
                        'color': AWAY_COLOR, 'fontWeight': '700', 'marginBottom': '8px',
                        'textAlign': 'right', 'textTransform': 'uppercase',
                        'letterSpacing': '0.05em', 'fontSize': '0.8rem',
                    }),
                    _build_lineup_card(away_team, lineups.get('away', {}),
                                       AWAY_COLOR, align='end'),
                    _build_subs_section(away_team, subs.get('away', []), AWAY_COLOR),
                ], lg=6, md=12, className='mb-3'),
            ], className='mb-3'),
        ], className='mb-4')

    # ── Average positions (initial: full match, starters only) ────────────────
    home_avg_players = _compute_avg_positions(events, lineup_df, 'home')
    away_avg_players = _compute_avg_positions(events, lineup_df, 'away')
    home_avg_fig = _build_avg_pos_fig(home_avg_players, HOME_COLOR, home_team, is_home=True)
    away_avg_fig = _build_avg_pos_fig(away_avg_players, AWAY_COLOR, away_team, is_home=False)

    # ── Assemble ──────────────────────────────────────────────────────────────
    return html.Div([
        lineup_section,
        _build_controls_bar(),
        dcc.Store(id='pma-ov-active-period', data='full'),
        dbc.Row([
            dbc.Col(
                html.Div(
                    id='pma-ov-avg-pos-home',
                    children=_build_avg_pos_component(
                        home_avg_fig, home_team, HOME_COLOR
                    ),
                ),
                lg=4, md=6, xs=12, className='mb-3',
            ),
            dbc.Col(
                html.Div(
                    id='pma-ov-stat-bars',
                    children=_build_stat_bars(home_kpis, away_kpis),
                ),
                lg=4, md=12, xs=12, className='mb-3',
            ),
            dbc.Col(
                html.Div(
                    id='pma-ov-avg-pos-away',
                    children=_build_avg_pos_component(
                        away_avg_fig, away_team, AWAY_COLOR
                    ),
                ),
                lg=4, md=6, xs=12, className='mb-3',
            ),
        ], className='g-2'),
    ])


# =============================================================================
# Callback registrar (called from match_analysis.register_match_analysis_callbacks)
# =============================================================================

def register_overview_callbacks(app):
    """Register period-filter and average-position callbacks for Match Overview."""

    @app.callback(
        Output('pma-ov-stat-bars',        'children'),
        Output('pma-ov-period-btn-full',  'style'),
        Output('pma-ov-period-btn-1',     'style'),
        Output('pma-ov-period-btn-2',     'style'),
        Output('pma-ov-avg-pos-home',     'children'),
        Output('pma-ov-avg-pos-away',     'children'),
        Output('pma-ov-active-period',    'data'),
        Input('pma-ov-period-btn-full',   'n_clicks'),
        Input('pma-ov-period-btn-1',      'n_clicks'),
        Input('pma-ov-period-btn-2',      'n_clicks'),
        Input('pma-ov-subs-toggle',       'value'),
        State('pma-selected-match',       'data'),
        State('pma-ov-active-period',     'data'),
        prevent_initial_call=True,
    )
    def _update_overview(_n_full, _n_1, _n_2, subs_value, match_id, current_period):
        triggered = ctx.triggered_id or 'pma-ov-period-btn-full'

        # Only update the active period when a period button was clicked;
        # for all other triggers (e.g. subs toggle) keep the stored period.
        if triggered in ('pma-ov-period-btn-full',
                         'pma-ov-period-btn-1',
                         'pma-ov-period-btn-2'):
            period = {
                'pma-ov-period-btn-full': 'full',
                'pma-ov-period-btn-1':    '1',
                'pma-ov-period-btn-2':    '2',
            }[triggered]
        else:
            period = current_period or 'full'

        include_subs = bool(subs_value and 'subs' in subs_value)

        button_styles = (
            _ov_period_btn_style(active=(period == 'full')),
            _ov_period_btn_style(active=(period == '1')),
            _ov_period_btn_style(active=(period == '2')),
        )

        _empty_home = _build_avg_pos_component(None)
        _empty_away = _build_avg_pos_component(None)

        if not match_id:
            return (
                _build_stat_bars({}, {}),
                *button_styles,
                _empty_home, _empty_away, period,
            )

        events = get_match_events(match_id)
        if events.empty:
            return (
                _build_stat_bars({}, {}),
                *button_styles,
                _empty_home, _empty_away, period,
            )

        # Apply period filter
        if period != 'full' and 'period_id' in events.columns:
            filtered = events[events['period_id'] == int(period)]
        else:
            filtered = events

        home_kpis = compute_team_kpis(filtered, 'home')
        away_kpis = compute_team_kpis(filtered, 'away')

        # Average positions
        lineup_df = get_match_lineup(match_id)
        home_team = str(events['home_team'].iloc[0]) if 'home_team' in events.columns else 'Home'
        away_team = str(events['away_team'].iloc[0]) if 'away_team' in events.columns else 'Away'

        home_players = _compute_avg_positions(filtered, lineup_df, 'home', include_subs)
        away_players = _compute_avg_positions(filtered, lineup_df, 'away', include_subs)

        home_fig = _build_avg_pos_fig(home_players, HOME_COLOR, home_team, is_home=True)
        away_fig = _build_avg_pos_fig(away_players, AWAY_COLOR, away_team, is_home=False)

        return (
            _build_stat_bars(home_kpis, away_kpis),
            *button_styles,
            _build_avg_pos_component(home_fig, home_team, HOME_COLOR),
            _build_avg_pos_component(away_fig, away_team, AWAY_COLOR),
            period,
        )
