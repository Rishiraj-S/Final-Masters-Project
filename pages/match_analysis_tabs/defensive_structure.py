"""
defensive_structure.py
======================
Defensive Structure & Pressing tab: where and how aggressively did they defend?
Sections:
  1. Defensive Stats (two per-team tables with Full/1H/2H)
     + Pressing Radar Chart
  2. Defensive Action Map + Player Defensive Stats Table
  3. Defensive Intensity Heatmap
  4. Fouls & Offsides Interactive Pitch Plot
"""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
from dash import html, dcc
import dash_bootstrap_components as dbc

from utils.config import COLORS
from page_utils.pitch_zones import get_zone, PitchZone

from .shared import (
    build_legend_box,
    build_info_box,
    build_team_stats_table,
    CARD_STYLE,
    section_header,
)
from page_utils.visualizations import (
    HOME_COLOR,
    AWAY_COLOR,
    GOLD,
    CHART_CONFIG,
    layout_config,
    add_pitch_background,
    PITCH_AXIS_FULL,
    render_lsc_heatmap_img,
)
from page_utils.event_filters import DEF_ACTION_TYPES as _DEF_ACTION_TYPES
_PITCH_HEIGHT = 480

_DEF_COLORS = {
    'Tackle':        '#4dabf7',
    'Interception':  '#51cf66',
    'Ball recovery': '#ffd43b',
    'Clearance':     '#ff922b',
    'Blocked Shot':  '#cc5de8',
}


# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------

def _compute_half_stats(events: pd.DataFrame, pos: str, period: int | None = None) -> dict:
    """Compute defensive stats for a single team, optionally per-half."""
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
    aerials         = te[te['event_type'] == 'Aerial']
    aerials_won     = aerials[aerials['outcome'] == 1]

    # PPDA: opponent passes ÷ our defensive actions
    opp_passes  = len(opp[opp['event_type'] == 'Pass'])
    def_actions = len(tackles) + len(interceptions) + len(fouls_committed)
    ppda = round(opp_passes / def_actions, 1) if def_actions > 0 else 0.0

    return {
        'team':            team,
        'tackles':         len(tackles),
        'tackles_won':     len(tackles_won),
        'tackles_str':     f'{len(tackles_won)}/{len(tackles)}',
        'interceptions':   len(interceptions),
        'clearances':      len(clearances),
        'ball_recoveries': len(ball_recoveries),
        'blocked_shots':   len(blocked_shots),
        'fouls_committed': len(fouls_committed),
        'aerials':         len(aerials),
        'aerials_won':     len(aerials_won),
        'aerials_str':     f'{len(aerials_won)}/{len(aerials)}',
        'ppda':            ppda,
    }


def _compute(events: pd.DataFrame) -> dict:
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

        # All defensive events combined (for heatmap)
        all_def = pd.concat([tackles, interceptions, ball_recoveries])

        # Zone breakdown (high press = x ≥ 66, mid = 33-66, low = x < 33)
        high_count = mid_count = low_count = 0
        if 'x' in all_def.columns:
            for x_val in all_def['x'].dropna():
                z = get_zone(float(x_val))
                if z == PitchZone.FINAL_THIRD:
                    high_count += 1
                elif z == PitchZone.MIDDLE_THIRD:
                    mid_count += 1
                else:
                    low_count += 1

        heatmap_x = all_def['x'].dropna().tolist() if 'x' in all_def.columns else []
        heatmap_y = all_def['y'].dropna().tolist() if 'y' in all_def.columns else []

        # Per-player defensive stats table (Full / 1H / 2H)
        all_actions = pd.concat([tackles, interceptions, ball_recoveries,
                                  clearances, blocked_shots])

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
                .head(8)
                .reset_index(drop=True)
            )

        player_full = _player_stats(all_actions)
        h1_acts = all_actions[all_actions['period_id'] == 1] if 'period_id' in all_actions.columns else pd.DataFrame()
        h2_acts = all_actions[all_actions['period_id'] == 2] if 'period_id' in all_actions.columns else pd.DataFrame()
        player_h1 = _player_stats(h1_acts)
        player_h2 = _player_stats(h2_acts)

        # Defensive action rows for scatter map
        def_events_df = te[te['event_type'].isin(_DEF_ACTION_TYPES)].copy()

        # Fouls & offsides data
        fouls_df = te[te['event_type'] == 'Foul'].copy()
        if 'outcome' in fouls_df.columns:
            fouls_df = fouls_df[fouls_df['outcome'] == 1]
        # Offsides caught = opponent played the ball and their player was offside
        offsides_df = opp[opp['event_type'] == 'Offside Pass'].copy()

        out[pos] = {
            'team':            team,
            'high_press':      high_count,
            'mid_press':       mid_count,
            'low_press':       low_count,
            'heatmap_x':       heatmap_x,
            'heatmap_y':       heatmap_y,
            'player_full':     player_full,
            'player_h1':       player_h1,
            'player_h2':       player_h2,
            'def_events_df':   def_events_df,
            'fouls_df':        fouls_df,
            'offsides_df':     offsides_df,
        }

    return out


# ---------------------------------------------------------------------------
# Stats metrics for the per-team tables
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# UI helpers
# ---------------------------------------------------------------------------




def _add_attack_direction(fig: go.Figure) -> None:
    fig.add_annotation(
        x=0.5, y=1.0, xref='paper', yref='paper',
        xanchor='center', yanchor='bottom',
        text='➡ Direction of Attack',
        showarrow=False,
        font=dict(color='black', size=16, family='Arial'),
        align='center',
        bgcolor='rgba(255,255,255,0.7)',
        borderpad=3,
    )


def _def_action_map(def_events_df: pd.DataFrame, team_color: str,
                    fouls_df: pd.DataFrame | None = None,
                    offsides_df: pd.DataFrame | None = None) -> dcc.Graph:
    """Scatter plot of defensive actions, fouls and offsides on a full pitch."""
    fig = go.Figure()
    add_pitch_background(fig)

    if not def_events_df.empty and 'x' in def_events_df.columns:
        for action_type, group in def_events_df.groupby('event_type'):
            valid = group.dropna(subset=['x', 'y'])
            if valid.empty:
                continue
            customdata = [
                [name, t, action_type]
                for name, t in zip(
                    valid['player_name'].fillna('Unknown').tolist(),
                    valid['time_min'].fillna(0).astype(int).tolist(),
                )
            ]
            fig.add_trace(go.Scatter(
                x=valid['x'].tolist(), y=valid['y'].tolist(),
                mode='markers',
                name=action_type,
                marker=dict(
                    color=_DEF_COLORS.get(action_type, team_color),
                    size=8, opacity=0.75,
                    line=dict(color='rgba(0,0,0,0.3)', width=0.5),
                ),
                customdata=customdata,
                hovertemplate=(
                    '<b>%{customdata[0]}</b><br>'
                    "Minute: %{customdata[1]}'<br>"
                    'Action: %{customdata[2]}'
                    '<extra></extra>'
                ),
            ))

    if fouls_df is not None and not fouls_df.empty and 'x' in fouls_df.columns:
        valid = fouls_df.dropna(subset=['x', 'y'])
        if not valid.empty:
            zones = (valid['Zone'].fillna('—').where(valid['Zone'] != 'N/A', '—').tolist()
                     if 'Zone' in valid.columns else ['—'] * len(valid))
            customdata = [
                [name, t, 'Foul', z]
                for name, t, z in zip(
                    valid['player_name'].fillna('Unknown').tolist(),
                    valid['time_min'].fillna(0).astype(int).tolist(),
                    zones,
                )
            ]
            fig.add_trace(go.Scatter(
                x=valid['x'].tolist(), y=valid['y'].tolist(),
                mode='markers', name='Foul',
                marker=dict(color='#ff6b6b', size=10, symbol='x',
                            opacity=0.85, line=dict(color='white', width=1)),
                customdata=customdata,
                hovertemplate=(
                    '<b>%{customdata[0]}</b><br>'
                    "Minute: %{customdata[1]}'<br>"
                    'Event: %{customdata[2]}<br>'
                    'Zone: %{customdata[3]}'
                    '<extra></extra>'
                ),
            ))

    if offsides_df is not None and not offsides_df.empty and 'x' in offsides_df.columns:
        valid = offsides_df.dropna(subset=['x', 'y'])
        if not valid.empty:
            customdata = [
                [name, t, 'Offside Pass']
                for name, t in zip(
                    valid['player_name'].fillna('Unknown').tolist(),
                    valid['time_min'].fillna(0).astype(int).tolist(),
                )
            ]
            fig.add_trace(go.Scatter(
                x=valid['x'].tolist(), y=valid['y'].tolist(),
                mode='markers', name='Offside',
                marker=dict(color='#ffd43b', size=10, symbol='triangle-up',
                            opacity=0.85, line=dict(color='white', width=1)),
                customdata=customdata,
                hovertemplate=(
                    '<b>%{customdata[0]}</b><br>'
                    "Minute: %{customdata[1]}'<br>"
                    'Event: %{customdata[2]}'
                    '<extra></extra>'
                ),
            ))

    _add_attack_direction(fig)
    fig.update_layout(**layout_config(
        **PITCH_AXIS_FULL,
        height=_PITCH_HEIGHT,
        margin=dict(l=0, r=0, t=48, b=0),
        legend=dict(
            orientation='v', x=0.01, xanchor='left', y=0.99, yanchor='top',
            bgcolor='rgba(0,0,0,0.55)',
            font=dict(color=COLORS['text_primary'], size=9),
        ),
    ))
    return dcc.Graph(figure=fig, config=CHART_CONFIG)


def _player_defensive_table(player_full: pd.DataFrame,
                            player_h1: pd.DataFrame,
                            player_h2: pd.DataFrame,
                            color: str, team_name: str) -> html.Div:
    """Enhanced player defensive stats table with Full/1H/2H breakdowns."""
    if player_full.empty:
        return html.Div("No data", style={'color': COLORS['text_secondary']})

    # For each player in the full table, get their 1H/2H actions count
    _hdr = {
        'fontSize': '0.65rem', 'fontWeight': '700', 'padding': '5px 8px',
        'color': COLORS['text_secondary'], 'textTransform': 'uppercase',
        'letterSpacing': '0.04em',
        'borderBottom': f'1px solid {COLORS["dark_border"]}',
    }
    _val = {
        'fontSize': '0.78rem', 'padding': '4px 8px',
        'color': COLORS['text_primary'], 'textAlign': 'center',
    }

    cols = ['Player', 'Actions', 'Tackles', 'Int.', 'Rec.', 'Clr.', 'Blk.', '1H', '2H']
    header = html.Tr([html.Th(c, style=_hdr) for c in cols])

    rows = []
    for i, (_, row) in enumerate(player_full.iterrows()):
        bg = COLORS['dark_tertiary'] if i % 2 == 0 else 'transparent'
        pname = row.get('Player', '')
        # Lookup h1/h2 totals for this player
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
        html.Div(team_name, style={
            'color': color, 'fontWeight': '700',
            'fontSize': '0.95rem', 'marginBottom': '10px',
            'borderBottom': f'2px solid {color}',
            'paddingBottom': '6px',
        }),
        html.Div(
            html.Table([html.Thead(header), html.Tbody(rows)],
                       style={'width': '100%', 'borderCollapse': 'collapse'}),
            style={'overflowX': 'auto'},
        ),
    ], style=CARD_STYLE)



def _def_action_heatmap(x_vals: list, y_vals: list,
                        team: str, color: str) -> html.Div:
    """LinearSegmentedColormap heatmap with marginal distribution curves."""
    label = html.Div(f"Defensive Actions — {team}", style={
        'color': color, 'fontWeight': '600',
        'fontSize': '0.85rem', 'marginBottom': '8px', 'textAlign': 'center',
    })
    if len(x_vals) < 2:
        return html.Div([label, html.Div("Not enough data", style={
            'color': COLORS['text_secondary'], 'textAlign': 'center', 'fontSize': '0.8rem',
        })], style=CARD_STYLE)
    img_src = render_lsc_heatmap_img(x_vals, y_vals, color, show_zone_pcts=True)
    return html.Div([
        label,
        html.Img(src=img_src, style={'width': '100%', 'borderRadius': '6px'}),
    ], style=CARD_STYLE)


def _fouls_offsides_map(fouls_df: pd.DataFrame, offsides_df: pd.DataFrame) -> dcc.Graph:
    """Interactive pitch plot for fouls & offsides."""
    fig = go.Figure()
    add_pitch_background(fig)

    # Fouls
    if not fouls_df.empty and 'x' in fouls_df.columns:
        valid = fouls_df.dropna(subset=['x', 'y'])
        if not valid.empty:
            if 'Zone' in valid.columns:
                zones = valid['Zone'].fillna('—').astype(str)
                zones = zones.where(zones != 'N/A', '—').tolist()
            else:
                zones = ['—'] * len(valid)
            customdata = [
                [name, t, 'Foul', z]
                for name, t, z in zip(
                    valid['player_name'].fillna('Unknown').tolist(),
                    valid['time_min'].fillna(0).astype(int).tolist(),
                    zones,
                )
            ]
            fig.add_trace(go.Scatter(
                x=valid['x'].tolist(), y=valid['y'].tolist(),
                mode='markers', name='Foul',
                marker=dict(color='#ff6b6b', size=10, symbol='x',
                            opacity=0.85, line=dict(color='white', width=1)),
                customdata=customdata,
                hovertemplate=(
                    '<b>%{customdata[0]}</b><br>'
                    "Minute: %{customdata[1]}'<br>"
                    'Event: %{customdata[2]}<br>'
                    'Zone: %{customdata[3]}'
                    '<extra></extra>'
                ),
            ))

    # Offsides
    if not offsides_df.empty and 'x' in offsides_df.columns:
        valid = offsides_df.dropna(subset=['x', 'y'])
        if not valid.empty:
            customdata = [
                [name, t, 'Offside Pass']
                for name, t in zip(
                    valid['player_name'].fillna('Unknown').tolist(),
                    valid['time_min'].fillna(0).astype(int).tolist(),
                )
            ]
            fig.add_trace(go.Scatter(
                x=valid['x'].tolist(), y=valid['y'].tolist(),
                mode='markers', name='Offside',
                marker=dict(color='#ffd43b', size=10, symbol='triangle-up',
                            opacity=0.85, line=dict(color='white', width=1)),
                customdata=customdata,
                hovertemplate=(
                    '<b>%{customdata[0]}</b><br>'
                    "Minute: %{customdata[1]}'<br>"
                    'Event: %{customdata[2]}'
                    '<extra></extra>'
                ),
            ))

    _add_attack_direction(fig)
    fig.update_layout(**layout_config(
        **PITCH_AXIS_FULL,
        height=_PITCH_HEIGHT,
        margin=dict(l=0, r=0, t=48, b=0),
        legend=dict(
            orientation='v', x=0.01, xanchor='left', y=0.99, yanchor='top',
            bgcolor='rgba(0,0,0,0.55)',
            font=dict(color=COLORS['text_primary'], size=9),
        ),
    ))
    return dcc.Graph(figure=fig, config=CHART_CONFIG)


# ---------------------------------------------------------------------------
# Filterable plot renderer
# ---------------------------------------------------------------------------

def _render_def_plots(events: pd.DataFrame) -> html.Div:
    """Render the filterable plot sections: action map, heatmap, fouls & offsides."""
    if events.empty:
        return html.P("No event data.", style={"color": COLORS["text_secondary"]})
    d = _compute(events)
    hs, as_ = d['home'], d['away']

    action_maps = html.Div([
        section_header("Defensive Action Map"),
        build_legend_box([
            ('●', 'Tackle',       '#4dabf7'),
            ('●', 'Interception', '#51cf66'),
            ('●', 'Recovery',     '#ffd43b'),
            ('●', 'Clearance',    '#ff922b'),
            ('●', 'Block',        '#cc5de8'),
            ('✕', 'Foul',         '#ff6b6b'),
            ('▲', 'Offside',      '#ffd43b'),
        ]),
        dbc.Row([
            dbc.Col(html.Div([
                html.Div(hs['team'], style={'color': HOME_COLOR, 'fontWeight': '700',
                                            'fontSize': '0.85rem', 'marginBottom': '8px'}),
                _def_action_map(hs['def_events_df'], HOME_COLOR,
                                hs['fouls_df'], hs['offsides_df']),
            ], style=CARD_STYLE), md=6, className='mb-3'),
            dbc.Col(html.Div([
                html.Div(as_['team'], style={'color': AWAY_COLOR, 'fontWeight': '700',
                                             'fontSize': '0.85rem', 'marginBottom': '8px'}),
                _def_action_map(as_['def_events_df'], AWAY_COLOR,
                                as_['fouls_df'], as_['offsides_df']),
            ], style=CARD_STYLE), md=6, className='mb-3'),
        ], className='g-3'),
    ], style={'marginBottom': '32px'})

    heatmaps = html.Div([
        section_header("Defensive Actions Heatmap"),
        build_info_box('Square-bin density of tackles, interceptions & recoveries — marginal curves show x/y distributions'),
        dbc.Row([
            dbc.Col(_def_action_heatmap(hs['heatmap_x'], hs['heatmap_y'], hs['team'], HOME_COLOR),
                    md=6, className='mb-3'),
            dbc.Col(_def_action_heatmap(as_['heatmap_x'], as_['heatmap_y'], as_['team'], AWAY_COLOR),
                    md=6, className='mb-3'),
        ], className='g-3'),
    ], style={'marginBottom': '32px'})

    return html.Div([action_maps, heatmaps])


# ---------------------------------------------------------------------------
# Tab builder
# ---------------------------------------------------------------------------

def build_defensive_structure_tab(events: pd.DataFrame, **_) -> html.Div:
    """Build the Defensive Structure & Pressing tab layout."""
    if events.empty:
        return html.P("No event data.", style={"color": COLORS["text_secondary"]})

    # Per-half stats for tables (always full match — tables are never filtered)
    h_full = _compute_half_stats(events, 'home')
    h_h1   = _compute_half_stats(events, 'home', 1)
    h_h2   = _compute_half_stats(events, 'home', 2)
    a_full = _compute_half_stats(events, 'away')
    a_h1   = _compute_half_stats(events, 'away', 1)
    a_h2   = _compute_half_stats(events, 'away', 2)

    # Player table uses full-match data
    d_full = _compute(events)
    hs, as_ = d_full['home'], d_full['away']

    # ── Defensive Stats Tables (static) ──────────────────────────────────
    stats_section = html.Div([
        section_header('Defensive Statistics'),
        build_info_box('Performance breakdown by half — Tackles, Interceptions, Clearances, Fouls & more'),
        dbc.Row([
            dbc.Col(build_team_stats_table(
                h_full['team'], HOME_COLOR, _DEF_METRICS, h_full, h_h1, h_h2,
            ), md=6, className='mb-3'),
            dbc.Col(build_team_stats_table(
                a_full['team'], AWAY_COLOR, _DEF_METRICS, a_full, a_h1, a_h2,
            ), md=6, className='mb-3'),
        ], className='g-3'),
    ], style={'marginBottom': '32px'})

    # ── Player Defensive Stats Table (static) ─────────────────────────────
    player_table = html.Div([
        section_header("Top Player Defensive Stats"),
        build_info_box('Top 8 players by total defensive actions — 1H/2H columns show action counts per half'),
        dbc.Row([
            dbc.Col(_player_defensive_table(
                hs['player_full'], hs['player_h1'], hs['player_h2'],
                HOME_COLOR, hs['team'],
            ), md=6, className='mb-3'),
            dbc.Col(_player_defensive_table(
                as_['player_full'], as_['player_h1'], as_['player_h2'],
                AWAY_COLOR, as_['team'],
            ), md=6, className='mb-3'),
        ], className='g-3'),
    ], style={'marginBottom': '32px'})

    return html.Div([
        stats_section,
        _render_def_plots(events),
        player_table,
    ], style={'marginTop': '16px'})


# ---------------------------------------------------------------------------
# Callback registration
# ---------------------------------------------------------------------------

def register_defensive_structure_callbacks(app) -> None:
    pass
