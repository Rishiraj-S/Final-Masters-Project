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
from dash import html
import dash_bootstrap_components as dbc

from utils.config import COLORS
from utils.data_utils import exclude_own_goals
from utils.xg_utils import add_xg_column
from utils.xt_utils import add_xt_column

from .shared import (
    CARD_STYLE,
    section_header,
)
from page_utils.visualizations import (
    HOME_COLOR,
    AWAY_COLOR,
    GOLD,
)
from page_utils.event_filters import SHOT_TYPES as _SHOT_TYPES

_DEF_TYPES  = {'Tackle', 'Interception', 'Ball recovery', 'Clearance'}

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
    xT_val     = round(add_xt_column(passes)['xT'].sum(), 3) if not passes.empty else 0.0
    shots      = add_xg_column(exclude_own_goals(pe[pe['event_type'].isin(_SHOT_TYPES)].copy()))
    goals      = shots[shots['event_type'] == 'Goal']
    goal_assists = int((pd.to_numeric(passes['Assist'], errors='coerce') == 16).sum()) if 'Assist' in passes.columns else 0
    key_passes_n = int((passes['Intentional Assist'] == 'Si').sum()) if 'Intentional Assist' in passes.columns else 0
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
        'xT':          xT_val,
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
# Top-5 data computation
# ---------------------------------------------------------------------------

def _compute_top5(events: pd.DataFrame) -> dict:
    out = {}
    for pos in ('home', 'away'):
        te = events[events['team_position'] == pos].copy()
        if 'position' in te.columns:
            te = te[te['position'] != 'GK']

        # Shots & shots on target
        shots_df = te[te['event_type'].isin(_SHOT_TYPES)].copy()
        if not shots_df.empty and 'player_name' in shots_df.columns:
            shots_df['sot'] = shots_df['event_type'].isin(['Saved Shot', 'Goal']).astype(int)
            shot_grp = (
                shots_df.groupby('player_name')
                .agg(shots=('event_type', 'count'), sot=('sot', 'sum'))
                .reset_index()
            )
        else:
            shot_grp = pd.DataFrame(columns=['player_name', 'shots', 'sot'])

        # Progressive passes & key passes
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

        # Recoveries & tackles won
        rec_df  = te[te['event_type'] == 'Ball recovery']
        tkl_df  = te[(te['event_type'] == 'Tackle') & (te['outcome'] == 1)]
        rec_grp = (rec_df.groupby('player_name').size().rename('rec')
                   if not rec_df.empty else pd.Series(dtype=int, name='rec'))
        tkl_grp = (tkl_df.groupby('player_name').size().rename('tw')
                   if not tkl_df.empty else pd.Series(dtype=int, name='tw'))
        def_grp = pd.concat([rec_grp, tkl_grp], axis=1).fillna(0).astype(int).reset_index()

        out[pos] = {'shots': shot_grp, 'passes': pass_grp, 'defensive': def_grp}
    return out


# ---------------------------------------------------------------------------
# Top-5 UI helpers
# ---------------------------------------------------------------------------

def _top5_card(metric_title: str, team_name: str, df: pd.DataFrame,
               col: str, color: str) -> html.Div:
    """Standalone top-5 card with its own heading."""
    header = html.Div([
        html.Div(metric_title, style={
            'color': GOLD, 'fontSize': '0.68rem', 'fontWeight': '700',
            'textTransform': 'uppercase', 'letterSpacing': '0.06em',
        }),
        html.Div(team_name, style={
            'color': color, 'fontSize': '0.70rem', 'fontWeight': '700',
            'marginTop': '2px',
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

    # Each row: (data_key, [(metric_title, col, team, pos_key, color), ...])
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
        ('Positional xT', 'xT'),
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

    return html.Div([
        _build_top5_section(events),
        section_header("Full Player Stats", subtitle="All outfield players sorted by total touches"),
        html.Div(_full_stats_table(home_stats, away_stats), style=CARD_STYLE),
    ], style={'marginTop': '16px'})


# ---------------------------------------------------------------------------
# Callbacks
# ---------------------------------------------------------------------------

def register_player_stats_callbacks(app) -> None:
    """No callbacks needed for the static side-by-side layout."""
    pass
