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
from utils.logos import team_logo_img, tournament_logo_img

from .shared import HOME_COLOR, AWAY_COLOR, GOLD


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


def _build_period_filter() -> html.Div:
    """Period toggle buttons placed between lineup and stat bars."""
    return html.Div([
        html.Span("Period:", style={
            'color': COLORS['text_secondary'], 'fontSize': '0.85rem',
            'marginRight': '10px', 'alignSelf': 'center',
        }),
        html.Div([
            html.Button(label,
                        id=f'pma-ov-period-btn-{val}',
                        n_clicks=0,
                        style=_ov_period_btn_style(active=(val == 'full')))
            for label, val in _OV_PERIOD_OPTIONS
        ], style={'display': 'flex', 'gap': '6px'}),
    ], style={
        'display': 'flex', 'alignItems': 'center',
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
        11: (47, 17),   # RW
        9:  (47, 50),   # CF
        10: (47, 83),   # LW
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
        return (x, y) if is_home else (100 - x, y)

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

    return (x, y) if is_home else (100 - x, y)


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

def _tv_stat_bar(label, home_val, away_val, suffix='', is_percentage=False):
    """
    Build a single TV-broadcast-style comparison bar.

    Layout:  home_value  [=====|=====]  away_value
                      stat label
    """
    hv = float(home_val) if home_val else 0
    av = float(away_val) if away_val else 0
    max_val = max(hv, av, 1)

    home_pct = (hv / max_val) * 100
    away_pct = (av / max_val) * 100

    if is_percentage:
        h_display = f"{hv:.1f}{suffix}"
        a_display = f"{av:.1f}{suffix}"
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

    return html.Div([
        html.Div(label, style={
            'textAlign': 'center',
            'color': COLORS['text_secondary'],
            'fontSize': '0.85rem',
            'marginBottom': '4px',
        }),
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
# Public tab builder
# =============================================================================

def build_overview_tab(events):
    """Render the Match Overview tab."""
    meta       = get_match_metadata(events)
    home_kpis  = compute_team_kpis(events, 'home')
    away_kpis  = compute_team_kpis(events, 'away')

    home_team  = meta.get('home_team', 'Home')
    away_team  = meta.get('away_team', 'Away')
    competition = meta.get('competition', '')
    match_id   = str(meta.get('match_id', ''))

    # Format kick-off time (HH:MM:SS → HH:MM) and date
    raw_time = str(meta.get('time', '') or '')
    kickoff_str = raw_time[:5] if len(raw_time) >= 5 else raw_time
    raw_date = str(meta.get('date', '') or '')
    venue = str(meta.get('venue', '') or '')

    # ── Scoreline header ──────────────────────────────────────────────────────
    match_header = dbc.Card([
        dbc.CardBody([
            html.Div([
                html.Div([
                    tournament_logo_img(competition, '80px'),
                ], style={
                    'width': '110px', 'height': '110px', 'borderRadius': '50%',
                    'background': GOLD, 'padding': '15px',
                    'display': 'flex', 'alignItems': 'center', 'justifyContent': 'center',
                }),
                html.Div(competition, style={
                    'color': COLORS['text_primary'], 'fontSize': '1rem',
                    'fontWeight': '500', 'marginTop': '6px',
                }),
            ], style={
                'display': 'flex', 'flexDirection': 'column',
                'alignItems': 'center', 'marginBottom': '16px',
            }),

            dbc.Row([
                dbc.Col([
                    html.Div([team_logo_img(home_team, '88px')],
                             style={'textAlign': 'right', 'marginBottom': '6px'}),
                    html.H3(home_team, className="text-end mb-0",
                            style={'fontWeight': '600'}),
                    html.Small("Home", className="text-end d-block",
                               style={'color': COLORS['text_secondary']}),
                ], width=4),

                dbc.Col([
                    html.H1(
                        f"{home_kpis['goals']}  -  {away_kpis['goals']}",
                        className="text-center mb-1",
                        style={'color': GOLD, 'fontWeight': '900',
                               'fontSize': '3.5rem', 'letterSpacing': '0.15em'},
                    ),
                    # Kick-off time
                    html.Div([
                        html.I(className="fas fa-clock",
                               style={'marginRight': '5px', 'fontSize': '0.75rem'}),
                        html.Span(f"KO {kickoff_str}" if kickoff_str else ''),
                    ], style={
                        'textAlign': 'center', 'color': COLORS['text_secondary'],
                        'fontSize': '0.82rem', 'marginBottom': '3px',
                    }),
                    # Venue
                    html.Div([
                        html.I(className="fas fa-map-marker-alt",
                               style={'marginRight': '5px', 'fontSize': '0.75rem'}),
                        html.Span(venue or '—'),
                    ], style={
                        'textAlign': 'center', 'color': COLORS['text_secondary'],
                        'fontSize': '0.82rem',
                    }),
                ], width=4),

                dbc.Col([
                    html.Div([team_logo_img(away_team, '88px')],
                             style={'textAlign': 'left', 'marginBottom': '6px'}),
                    html.H3(away_team, className="text-start mb-0",
                            style={'fontWeight': '600'}),
                    html.Small("Away", className="text-start d-block",
                               style={'color': COLORS['text_secondary']}),
                ], width=4),
            ], align="center"),
        ])
    ], className="mb-4")

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
            html.H5("Line-Ups", style={
                'color': GOLD, 'fontWeight': '700',
                'marginBottom': '12px', 'letterSpacing': '0.04em',
            }),
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
            html.H5("Line-Ups", style={
                'color': GOLD, 'fontWeight': '700',
                'marginBottom': '12px', 'letterSpacing': '0.04em',
            }),
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

    # ── Assemble ──────────────────────────────────────────────────────────────
    return html.Div([
        match_header,
        lineup_section,
        _build_period_filter(),
        html.Div(
            id='pma-ov-stat-bars',
            children=_build_stat_bars(home_kpis, away_kpis),
        ),
    ])


# =============================================================================
# Callback registrar (called from match_analysis.register_match_analysis_callbacks)
# =============================================================================

def register_overview_callbacks(app):
    """Register the period-filter callback for the Match Overview stat bars."""

    @app.callback(
        Output('pma-ov-stat-bars', 'children'),
        Output('pma-ov-period-btn-full', 'style'),
        Output('pma-ov-period-btn-1', 'style'),
        Output('pma-ov-period-btn-2', 'style'),
        Input('pma-ov-period-btn-full', 'n_clicks'),
        Input('pma-ov-period-btn-1', 'n_clicks'),
        Input('pma-ov-period-btn-2', 'n_clicks'),
        State('pma-selected-match', 'data'),
        prevent_initial_call=True,
    )
    def _update_stat_bars(_n_full, _n_1, _n_2, match_id):
        triggered = ctx.triggered_id or 'pma-ov-period-btn-full'
        period = {
            'pma-ov-period-btn-full': 'full',
            'pma-ov-period-btn-1':    '1',
            'pma-ov-period-btn-2':    '2',
        }.get(triggered, 'full')

        button_styles = (
            _ov_period_btn_style(active=(period == 'full')),
            _ov_period_btn_style(active=(period == '1')),
            _ov_period_btn_style(active=(period == '2')),
        )

        if not match_id:
            return _build_stat_bars({}, {}), *button_styles

        events = get_match_events(match_id)
        if events.empty:
            return _build_stat_bars({}, {}), *button_styles

        if period != 'full' and 'period_id' in events.columns:
            events = events[events['period_id'] == int(period)]

        home_kpis = compute_team_kpis(events, 'home')
        away_kpis = compute_team_kpis(events, 'away')
        return _build_stat_bars(home_kpis, away_kpis), *button_styles
