from __future__ import annotations
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
from .shared import CARD_STYLE, section_header, build_info_box, build_team_stats_table
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
            html.Div(html.Span(f"{minute}'", style={'color': GOLD, 'fontWeight': '700', 'fontSize': '0.82rem'}),
                     style={'textAlign': text_align, 'marginBottom': '1px'}),
            html.Div([html.Span('↓ ', style={'color': '#ff6b6b', 'fontWeight': '700', 'fontSize': '0.95rem'}),
                      html.Span(p_off or '—', style={'color': COLORS['text_secondary'], 'fontSize': '0.88rem'}),
                      inj_icon], style={'textAlign': text_align}),
            html.Div([html.Span('↑ ', style={'color': '#51cf66', 'fontWeight': '700', 'fontSize': '0.95rem'}),
                      html.Span(p_on or '—', style={'color': '#E8E9ED', 'fontSize': '0.88rem', 'fontWeight': '500'})],
                     style={'textAlign': text_align}),
        ], style={'padding': '6px 0', 'borderBottom': f"1px solid {COLORS['dark_border']}"}))
    header = html.Div('Substitutions', style={
        'color': color, 'fontSize': '0.78rem', 'fontWeight': '700',
        'textTransform': 'uppercase', 'letterSpacing': '0.05em',
        'marginBottom': '8px', 'textAlign': text_align,
    })
    content = [header, *sub_rows] if sub_rows else [
        header,
        html.Div('No substitutions', style={'color': COLORS['text_secondary'], 'fontSize': '0.82rem', 'textAlign': text_align}),
    ]
    return html.Div(content, style={
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
    home_side = dbc.Row([
        dbc.Col(home_lineup, xs=9),
        dbc.Col(home_subs,   xs=3),
    ], className='g-2', align='start')
    away_side = dbc.Row([
        dbc.Col(away_subs,   xs=3),
        dbc.Col(away_lineup, xs=9),
    ], className='g-2', align='start')
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
