"""
player_stats.py
===============
Player Stats tab (per-match).
Provides a side-by-side view of all players grouped by team, displaying
their attacking and defensive KPIs combined with heatmaps.
The full player comparison table remains at the bottom.
"""
from __future__ import annotations

import pandas as pd
from dash import html, dcc
import dash_bootstrap_components as dbc

from utils.config import COLORS
from utils.data_utils import get_match_events, exclude_own_goals
from utils.xg_utils import add_xg_column

from .shared import (
    CARD_STYLE,
    section_header,
)
from page_utils.visualizations import (
    HOME_COLOR,
    AWAY_COLOR,
    GOLD,
    render_lsc_heatmap_img,
)
from page_utils.event_filters import SHOT_TYPES as _SHOT_TYPES

_DEF_TYPES  = {'Tackle', 'Interception', 'Ball Recovery', 'Clearance'}

# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------

def _compute_player_stats(events: pd.DataFrame, player_name: str) -> dict:
    """Compute all stats for a given player."""
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
    except:
        jersey = ''

    passes     = pe[pe['event_type'] == 'Pass']
    succ_pass  = passes[passes['outcome'] == 1]
    shots      = add_xg_column(exclude_own_goals(pe[pe['event_type'].isin(_SHOT_TYPES)].copy()))
    goals      = shots[shots['event_type'] == 'Goal']
    goal_assists = int((pd.to_numeric(passes['Assist'], errors='coerce') == 16).sum()) if 'Assist' in passes.columns else 0
    key_passes_n = int((passes['Intentional Assist'] == 'Si').sum()) if 'Intentional Assist' in passes.columns else 0
    tackles    = pe[pe['event_type'] == 'Tackle']
    tackles_w  = tackles[tackles['outcome'] == 1]
    ints       = pe[pe['event_type'] == 'Interception']
    recoveries = pe[pe['event_type'] == 'Ball Recovery']
    clearances = pe[pe['event_type'] == 'Clearance']
    aerials    = pe[pe['event_type'] == 'Aerial']
    aerials_w  = aerials[aerials['outcome'] == 1]
    fouls_c    = pe[pe['event_type'] == 'Foul']
    dribbles   = pe[pe['event_type'] == 'Take On']
    dribbles_s = dribbles[dribbles['outcome'] == 1]

    touch_x = pe['x'].dropna().tolist() if 'x' in pe.columns else []
    touch_y = pe['y'].dropna().tolist() if 'y' in pe.columns else []
    def_df  = pe[pe['event_type'].isin(_DEF_TYPES)].copy()
    def_x = def_df['x'].dropna().tolist() if 'x' in def_df.columns else []
    def_y = def_df['y'].dropna().tolist() if 'y' in def_df.columns else []

    pass_acc = round(len(succ_pass) / len(passes) * 100, 1) if len(passes) > 0 else 0
    tackle_w = round(len(tackles_w) / len(tackles) * 100, 1) if len(tackles) > 0 else 0
    aerial_w = round(len(aerials_w) / len(aerials) * 100, 1) if len(aerials) > 0 else 0

    return {
        'player_name': player_name,
        'jersey':      jersey,
        'team':        team,
        'team_position': pos,
        'display_position': display_pos,
        'color':       color,
        'touch_x':     touch_x,
        'touch_y':     touch_y,
        'def_x':       def_x,
        'def_y':       def_y,
        'touches':     len(pe),
        'passes':      len(passes),
        'pass_acc':    pass_acc,
        'shots':       len(shots),
        'goals':       len(goals),
        'xg':          round(shots['xg'].sum(), 2) if 'xg' in shots.columns else 0.0,
        'assists':     goal_assists,
        'key_passes':  key_passes_n,
        'tackles':     len(tackles),
        'tackle_w':    tackle_w,
        'ints':        len(ints),
        'recoveries':  len(recoveries),
        'clearances':  len(clearances),
        'aerials':     len(aerials),
        'aerial_w':    aerial_w,
        'fouls':       len(fouls_c),
        'dribbles':    len(dribbles),
        'dribbles_s':  len(dribbles_s),
    }


def _build_all_player_stats(events: pd.DataFrame) -> tuple[list[dict], list[dict]]:
    """Return (home_players_stats, away_players_stats), sorted by touches desc.

    Uses groupby so each player's events are extracted once (O(n_events) total)
    rather than running a full-DataFrame filter per player (O(n_players × n_events)).
    """
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


# ---------------------------------------------------------------------------
# UI helpers — player cards
# ---------------------------------------------------------------------------

def _kpi_stat_box(label: str, value, color: str) -> html.Div:
    """A compact KPI box for the side-by-side layout."""
    return html.Div([
        html.Div(str(value), style={'fontSize': '1.1rem', 'fontWeight': 'bold', 'color': color, 'lineHeight': '1'}),
        html.Div(label, style={'fontSize': '0.65rem', 'textTransform': 'none' if label.startswith('x') else 'uppercase', 'color': COLORS['text_secondary'], 'letterSpacing': '0' if label.startswith('x') else '0.04em'})
    ], style={
        'backgroundColor': COLORS['dark_tertiary'],
        'padding': '6px 8px',
        'borderRadius': '6px',
        'textAlign': 'center',
        'border': f'1px solid {COLORS["dark_border"]}'
    })

def _build_player_card(stats: dict) -> html.Div:
    """Builds a single player's vertical dashboard card."""
    color = stats['color']
    name = stats['player_name']
    jersey_val = stats.get('jersey')
    jersey = f" #{jersey_val}" if jersey_val else ""

    raw_pos = stats.get('display_position', stats['team_position'])
    if str(raw_pos).lower() in ['home', 'away']:
        display_pos = str(raw_pos).capitalize()
    elif len(str(raw_pos)) <= 3:
        display_pos = str(raw_pos).upper()
    else:
        display_pos = str(raw_pos).title()
        
    pos_label = f" ({display_pos})" if display_pos else ""

    # Hero/Header Section
    header = html.Div([
        html.H4(f"{name}{jersey}{pos_label}", style={'color': color, 'fontWeight': 'bold', 'margin': 0}),
    ], style={'textAlign': 'center', 'marginBottom': '16px', 'borderBottom': f'1px solid {color}40', 'paddingBottom': '10px'})
    
    def _kpi_col(kpis, title):
        kpi_boxes = []
        for label, val, c in kpis:
            kpi_boxes.append(html.Div([
                _kpi_stat_box(label, val, c)
            ], style={'marginBottom': '6px'}))
        
        return html.Div([
            html.Div(title, style={'color': color, 'fontWeight': '600', 'fontSize': '0.85rem', 'marginBottom': '10px', 'textAlign': 'center'}),
            html.Div(kpi_boxes, style={'display': 'flex', 'flexDirection': 'column'})
        ])

    pos_kpis = [
        ('Touches', stats['touches'], color),
        ('Passes', stats['passes'], color),
        ('Pass Acc', f"{stats['pass_acc']}%", color),
        ('Dribbles', stats['dribbles'], color)
    ]
    
    att_kpis = [
        ('Shots',      stats['shots'],                        color),
        ('Goals',      stats['goals'],                        '#51cf66' if stats['goals'] > 0 else color),
        ('xG',         stats.get('xg', 0.0),                  color),
        ('Assists',    stats['assists'],                       GOLD if stats['assists'] > 0 else color),
        ('Key Passes', stats['key_passes'],                    color),
    ]
    
    def_kpis = [
        ('Tackles', stats['tackles'], color),
        ('Interceptions', stats['ints'], color),
        ('Recoveries', stats['recoveries'], color),
        ('Clearances', stats['clearances'], color)
    ]
    
    # Heatmaps
    if len(stats['touch_x']) >= 2:
        img_src = render_lsc_heatmap_img(stats['touch_x'], stats['touch_y'], color, half=False)
        touch_heatmap = html.Img(src=img_src, style={'width': '100%', 'borderRadius': '8px', 'border': f'1px solid {COLORS["dark_border"]}'})
    else:
        touch_heatmap = html.Div("Not enough touches.", style={'color': COLORS['text_secondary'], 'padding': '10px', 'textAlign': 'center', 'fontSize': '0.8rem'})

    def_x = stats.get('def_x', [])
    def_y = stats.get('def_y', [])
    if len(def_x) >= 2:
        img_src_def = render_lsc_heatmap_img(def_x, def_y, color, half=False)
        def_heatmap = html.Img(src=img_src_def, style={'width': '100%', 'borderRadius': '8px', 'border': f'1px solid {COLORS["dark_border"]}'})
    else:
        def_heatmap = html.Div("Not enough defensive actions.", style={'color': COLORS['text_secondary'], 'padding': '10px', 'textAlign': 'center', 'fontSize': '0.8rem'})

    return html.Div([
        header,
        
        dbc.Row([
            # Attacking Section
            dbc.Col(
                dbc.Row([
                    dbc.Col([
                        _kpi_col(att_kpis, "Attacking Stats"),
                        html.Div(style={'height': '15px'}),
                        _kpi_col(pos_kpis, "Possession")
                    ], width=4, xl=3),
                    dbc.Col(html.Div([
                        html.Div("Attacking & On-Ball Heatmap", style={'textAlign': 'center', 'color': color, 'fontWeight': 'bold', 'marginBottom': '6px', 'fontSize': '0.8rem'}),
                        touch_heatmap
                    ]), width=8, xl=9)
                ], className="h-100", style={'backgroundColor': 'rgba(255,255,255,0.02)', 'padding': '12px', 'borderRadius': '8px', 'border': f'1px solid {COLORS["dark_border"]}'}),
                md=6, className="mb-3 mb-md-0"
            ),
            
            # Defensive Section
            dbc.Col(
                dbc.Row([
                    dbc.Col(_kpi_col(def_kpis, "Defensive Stats"), width=4, xl=3),
                    dbc.Col(html.Div([
                        html.Div("Defensive Actions Heatmap", style={'textAlign': 'center', 'color': color, 'fontWeight': 'bold', 'marginBottom': '6px', 'fontSize': '0.8rem'}),
                        def_heatmap
                    ]), width=8, xl=9)
                ], className="h-100", style={'backgroundColor': 'rgba(255,255,255,0.02)', 'padding': '12px', 'borderRadius': '8px', 'border': f'1px solid {COLORS["dark_border"]}'}),
                md=6
            )
        ], className="align-items-stretch")
        
    ], style={**CARD_STYLE, 'borderTop': f'4px solid {color}'})


# ---------------------------------------------------------------------------
# UI helpers — full stats table
# ---------------------------------------------------------------------------

def _full_stats_table(home_stats: list[dict], away_stats: list[dict]) -> html.Div:
    """Combined player stats table for all players from both teams."""
    all_stats = home_stats + away_stats
    if not all_stats:
        return html.P("No data.", style={'color': COLORS['text_secondary']})

    cols = [
        ('Player',      'player_name'),
        ('Team',        'team'),
        ('TCH',         'touches'),
        ('PAS',         'passes'),
        ('PA%',         'pass_acc'),
        ('SHT',         'shots'),
        ('G',           'goals'),
        ('AST',         'assists'),
        ('KP',          'key_passes'),
        ('TKL',         'tackles'),
        ('TW%',         'tackle_w'),
        ('INT',         'ints'),
        ('REC',         'recoveries'),
        ('CLR',         'clearances'),
        ('AER',         'aerials'),
        ('AW%',         'aerial_w'),
        ('FC',          'fouls'),
        ('DRB',         'dribbles'),
    ]

    header_row = html.Tr([
        html.Th(
            label,
            style={
                'color': GOLD,
                'borderBottom': f'2px solid {GOLD}',
                'padding': '6px 8px',
                'fontSize': '0.72rem',
                'textAlign': 'center' if key not in ('player_name', 'team') else 'left',
                'whiteSpace': 'nowrap',
            }
        )
        for label, key in cols
    ])

    rows = []
    for i, s in enumerate(all_stats):
        bg = 'rgba(255,255,255,0.03)' if i % 2 else 'transparent'
        color = s['color']
        cells = []
        for label, key in cols:
            val = s.get(key, '')
            align = 'left' if key in ('player_name', 'team') else 'center'
            style = {
                'padding': '5px 8px',
                'fontSize': '0.78rem',
                'textAlign': align,
                'whiteSpace': 'nowrap',
            }
            if key == 'player_name':
                style['color'] = color
                style['fontWeight'] = '600'
            elif key == 'goals' and val and int(val) > 0:
                style['color'] = '#51cf66'
                style['fontWeight'] = '700'
            elif key == 'assists' and val and int(val) > 0:
                style['color'] = GOLD
                style['fontWeight'] = '700'
            cells.append(html.Td(str(val), style=style))
        rows.append(html.Tr(cells, style={'backgroundColor': bg}))

    return html.Div(
        html.Table(
            [html.Thead(header_row), html.Tbody(rows)],
            style={'width': '100%', 'borderCollapse': 'collapse',
                   'color': COLORS['text_primary']},
        ),
        style={'overflowX': 'auto'},
    )


# ---------------------------------------------------------------------------
# Tab builder
# ---------------------------------------------------------------------------

def build_player_stats_tab(events: pd.DataFrame, **_) -> html.Div:
    """Build the Player Stats tab: side-by-side all players + full stats table."""
    if events.empty:
        return html.P("No event data.", style={"color": COLORS["text_secondary"]})

    home_stats, away_stats = _build_all_player_stats(events)

    if not home_stats and not away_stats:
        return html.P("No player data available.", style={"color": COLORS["text_secondary"]})

    home_team = home_stats[0]['team'] if home_stats else 'Home'
    away_team = away_stats[0]['team'] if away_stats else 'Away'

    # Render all player cards
    home_cards = [html.Div(_build_player_card(s), className='mb-4') for s in home_stats]
    away_cards = [html.Div(_build_player_card(s), className='mb-4') for s in away_stats]

    # ── Full stats table ─────────────────────────────────────────────────────
    table_section = html.Div([
        section_header("Full Match Player Stats", subtitle="All players sorted by total touches"),
        html.Div(_full_stats_table(home_stats, away_stats), style=CARD_STYLE),
    ])

    return html.Div([
        section_header(f"{home_team} Players", subtitle="Outfield players"),
        html.Div(home_cards),
        
        html.Div(style={'height': '40px'}),
        
        section_header(f"{away_team} Players", subtitle="Outfield players"),
        html.Div(away_cards),
        
        html.Div(style={'height': '40px'}),
        
        table_section,
    ], style={'marginTop': '16px'})


# ---------------------------------------------------------------------------
# Callbacks
# ---------------------------------------------------------------------------

def register_player_stats_callbacks(app) -> None:
    """No callbacks needed for the static side-by-side layout."""
    pass
