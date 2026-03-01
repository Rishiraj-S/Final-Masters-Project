"""
set_pieces.py
=============
Set Pieces tab: corners, free kicks, throw-ins, and penalties.
Sections: Corners | Free Kicks | Throw-ins | Penalties
"""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
from dash import html, dcc
import dash_bootstrap_components as dbc

from utils.config import COLORS
from page_utils.pitch_zones import get_zone, PitchZone, is_in_penalty_box

GOLD = COLORS['gold']
_CARD = {
    'backgroundColor': COLORS['dark_secondary'],
    'border': f'1px solid {COLORS["dark_border"]}',
    'borderRadius': '8px',
    'padding': '16px',
}


# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------

def _compute(events: pd.DataFrame) -> dict:
    home_team = events['home_team'].iloc[0]
    away_team = events['away_team'].iloc[0]
    result = {'home_team': home_team, 'away_team': away_team, 'teams': {}}

    for pos, team in (('home', home_team), ('away', away_team)):
        te  = events[events['team_position'] == pos]
        opp = events[events['team_position'] != pos]

        # ── Corners ───────────────────────────────────────────────────────
        corners = len(te[te['event_type'] == 'Corner Awarded'])

        # Aerials won inside penalty box (set-piece aerial threat)
        aerials_won_all = te[(te['event_type'] == 'Aerial') & (te['outcome'] == 1)]
        box_aerials_won = 0
        if 'x' in aerials_won_all.columns and 'y' in aerials_won_all.columns:
            for _, r in aerials_won_all.iterrows():
                x, y = r.get('x'), r.get('y')
                if pd.notna(x) and pd.notna(y) and is_in_penalty_box(float(x), float(y)):
                    box_aerials_won += 1

        # Goals from penalty box (proxy for set-piece finishes)
        goals = te[te['event_type'] == 'Goal']
        box_goals = 0
        if 'x' in goals.columns and 'y' in goals.columns:
            for _, r in goals.iterrows():
                x, y = r.get('x'), r.get('y')
                if pd.notna(x) and pd.notna(y) and is_in_penalty_box(float(x), float(y)):
                    box_goals += 1

        # ── Free Kicks ────────────────────────────────────────────────────
        # Fouls received = opponent fouls → free kick awarded to this team
        fouls_received = opp[opp['event_type'] == 'Foul']
        total_fk = len(fouls_received)
        dangerous_fk = 0
        fk_final_third = 0
        fk_mid_third   = 0
        fk_def_third   = 0
        if 'x' in fouls_received.columns:
            for x_val in fouls_received['x'].dropna():
                zone = get_zone(float(x_val))
                if zone == PitchZone.FINAL_THIRD:
                    dangerous_fk   += 1
                    fk_final_third += 1
                elif zone == PitchZone.MIDDLE_THIRD:
                    fk_mid_third   += 1
                else:
                    fk_def_third   += 1

        # ── Throw-ins ─────────────────────────────────────────────────────
        throw_ins = te[te['event_type'].str.lower().str.contains('throw', na=False)]
        throw_in_zones = {'Defensive Third': 0, 'Middle Third': 0, 'Final Third': 0}
        if 'x' in throw_ins.columns:
            for x_val in throw_ins['x'].dropna():
                zone = get_zone(float(x_val))
                if zone == PitchZone.DEFENSIVE_THIRD:
                    throw_in_zones['Defensive Third'] += 1
                elif zone == PitchZone.MIDDLE_THIRD:
                    throw_in_zones['Middle Third'] += 1
                else:
                    throw_in_zones['Final Third'] += 1

        # ── Penalties ─────────────────────────────────────────────────────
        # Penalties won = opponent concedes penalty (look for 'Penalty Conceded' in opp events)
        penalties_won       = len(opp[opp['event_type'].str.lower().str.contains('penalty conceded', na=False)])
        penalties_conceded  = len(te[te['event_type'].str.lower().str.contains('penalty conceded', na=False)])
        # Penalty kicks taken (look for 'Penalty' shots)
        penalty_shots       = te[te['event_type'].str.lower().str.contains('^penalty$', na=False, regex=True)]
        penalty_goals       = len(penalty_shots[penalty_shots['outcome'] == 1]) if len(penalty_shots) > 0 else 0

        result['teams'][pos] = {
            'team':            team,
            # Corners
            'corners':         corners,
            'box_aerials_won': box_aerials_won,
            'box_goals':       box_goals,
            # Free kicks
            'fouls_received':  total_fk,
            'dangerous_fk':    dangerous_fk,
            'fk_final_third':  fk_final_third,
            'fk_mid_third':    fk_mid_third,
            'fk_def_third':    fk_def_third,
            # Throw-ins
            'throw_ins':       len(throw_ins),
            'throw_in_zones':  throw_in_zones,
            # Penalties
            'penalties_won':      penalties_won,
            'penalties_conceded': penalties_conceded,
            'penalty_goals':      penalty_goals,
        }

    return result


# ---------------------------------------------------------------------------
# UI helpers
# ---------------------------------------------------------------------------

def _section_header(title: str, subtitle: str = '') -> html.Div:
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


def _stat_row(label: str, home_val: int, away_val: int) -> html.Div:
    total = (home_val + away_val) or 1
    home_pct = home_val / total * 100
    return html.Div([
        html.Div([
            html.Span(str(home_val), style={
                'color': GOLD, 'fontWeight': 'bold', 'minWidth': '30px',
            }),
            html.Span(label, style={
                'color': COLORS['text_secondary'], 'fontSize': '0.8rem',
                'flex': '1', 'textAlign': 'center',
            }),
            html.Span(str(away_val), style={
                'color': COLORS['text_primary'], 'fontWeight': 'bold',
                'minWidth': '30px', 'textAlign': 'right',
            }),
        ], style={'display': 'flex', 'marginBottom': '4px'}),
        html.Div([
            html.Div(style={
                'width': f'{home_pct:.1f}%', 'height': '5px',
                'backgroundColor': GOLD,
                'borderRadius': '3px 0 0 3px' if home_pct < 100 else '3px',
            }),
            html.Div(style={
                'width': f'{100 - home_pct:.1f}%', 'height': '5px',
                'backgroundColor': COLORS['dark_border'],
                'borderRadius': '0 3px 3px 0' if home_pct > 0 else '3px',
            }),
        ], style={'display': 'flex', 'marginBottom': '10px'}),
    ])


def _metric_card(label: str, home_val, away_val, note: str = '', md: int = 3) -> dbc.Col:
    return dbc.Col(html.Div([
        html.Div(label, style={
            'color': COLORS['text_secondary'], 'fontSize': '0.72rem',
            'marginBottom': '6px', 'textAlign': 'center',
        }),
        html.Div([
            html.Span(str(home_val), style={
                'color': GOLD, 'fontWeight': 'bold', 'fontSize': '1.2rem',
            }),
            html.Span(" / ", style={'color': COLORS['dark_border'], 'margin': '0 4px'}),
            html.Span(str(away_val), style={
                'color': COLORS['text_primary'], 'fontWeight': 'bold', 'fontSize': '1.2rem',
            }),
        ], style={'textAlign': 'center'}),
        *([html.Div(note, style={
            'color': COLORS['dark_border'], 'fontSize': '0.65rem',
            'textAlign': 'center', 'marginTop': '4px',
        })] if note else []),
    ], style=_CARD), md=md)


def _bar_chart(hs: dict, as_: dict, categories: list,
               home_vals: list, away_vals: list) -> dcc.Graph:
    fig = go.Figure([
        go.Bar(name=hs['team'], x=categories, y=home_vals,
               marker_color=GOLD, opacity=0.85),
        go.Bar(name=as_['team'], x=categories, y=away_vals,
               marker_color=COLORS['text_secondary'], opacity=0.85),
    ])
    fig.update_layout(
        barmode='group',
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font={'color': COLORS['text_primary'], 'size': 11},
        margin={'l': 40, 'r': 10, 't': 10, 'b': 40},
        height=200,
        legend={'orientation': 'h', 'y': -0.35, 'font': {'size': 10}},
        xaxis={'gridcolor': COLORS['dark_border']},
        yaxis={'gridcolor': COLORS['dark_border']},
    )
    return dcc.Graph(figure=fig, config={'displayModeBar': False})


def _team_labels(hs: dict, as_: dict) -> html.Div:
    return html.Div([
        html.Span(hs['team'], style={
            'color': COLORS['text_secondary'], 'fontSize': '0.72rem', 'fontWeight': 'bold',
        }),
        html.Span(as_['team'], style={
            'color': COLORS['text_secondary'], 'fontSize': '0.72rem', 'fontWeight': 'bold',
        }),
    ], style={'display': 'flex', 'justifyContent': 'space-between', 'marginBottom': '14px'})


# ---------------------------------------------------------------------------
# Tab builder
# ---------------------------------------------------------------------------

def build_setpieces_tab(events: pd.DataFrame, **_) -> html.Div:
    """Build the Set Pieces tab layout."""
    if events.empty:
        return html.P("No event data.", style={"color": COLORS["text_secondary"]})

    d = _compute(events)
    hs, as_ = d['teams']['home'], d['teams']['away']

    # ── Stats ─────────────────────────────────────────────────────────────
    stats_row = html.Div([
        dbc.Row([
            dbc.Col(html.Div([
                _team_labels(hs, as_),
                _stat_row("Corners Awarded",      hs['corners'],         as_['corners']),
                _stat_row("Fouls Received",        hs['fouls_received'],  as_['fouls_received']),
                _stat_row("Dangerous Free Kicks",  hs['dangerous_fk'],    as_['dangerous_fk']),
                _stat_row("Box Aerials Won",        hs['box_aerials_won'], as_['box_aerials_won']),
                _stat_row("Goals from Penalty Box", hs['box_goals'],       as_['box_goals']),
            ], style=_CARD), md=5),
            dbc.Col(html.Div([
                html.Div("Set Piece Overview", style={
                    'color': COLORS['text_secondary'], 'fontWeight': '500',
                    'marginBottom': '10px', 'fontSize': '0.85rem',
                }),
                _bar_chart(
                    hs, as_,
                    ['Corners', 'Fouls Received', 'Dangerous FK', 'Box Aerials Won'],
                    [hs['corners'], hs['fouls_received'], hs['dangerous_fk'], hs['box_aerials_won']],
                    [as_['corners'], as_['fouls_received'], as_['dangerous_fk'], as_['box_aerials_won']],
                ),
            ], style=_CARD), md=7),
        ], className="g-3"),
    ], style={'marginBottom': '32px'})

    # ── Corners ───────────────────────────────────────────────────────────
    corners_section = html.Div([
        _section_header("Corners"),
        dbc.Row([
            _metric_card("Corners Won",    hs['corners'],         as_['corners'],         md=4),
            _metric_card("Box Aerials Won", hs['box_aerials_won'], as_['box_aerials_won'], md=4),
            _metric_card("Box Goals",       hs['box_goals'],       as_['box_goals'],       md=4),
        ], className="g-3"),
    ], style={'marginBottom': '32px'})

    # ── Free Kicks ────────────────────────────────────────────────────────
    free_kicks_section = html.Div([
        _section_header("Free Kicks"),
        dbc.Row([
            _metric_card("Fouls Received",    hs['fouls_received'],  as_['fouls_received'],  md=3),
            _metric_card("Dangerous FK",      hs['dangerous_fk'],    as_['dangerous_fk'],    md=3),
            _metric_card("FK in Final Third", hs['fk_final_third'],  as_['fk_final_third'],  md=3),
            _metric_card("FK in Mid Third",   hs['fk_mid_third'],    as_['fk_mid_third'],    md=3),
        ], className="g-3", style={'marginBottom': '12px'}),
        html.Div([
            _bar_chart(
                hs, as_,
                ['Def. Third', 'Mid. Third', 'Final Third'],
                [hs['fk_def_third'], hs['fk_mid_third'], hs['fk_final_third']],
                [as_['fk_def_third'], as_['fk_mid_third'], as_['fk_final_third']],
            ),
        ], style=_CARD),
    ], style={'marginBottom': '32px'})

    # ── Throw-ins ─────────────────────────────────────────────────────────
    tz_h = hs['throw_in_zones']
    tz_a = as_['throw_in_zones']
    throw_ins_section = html.Div([
        _section_header("Throw-ins"),
        dbc.Row([
            _metric_card("Total Throw-ins",       hs['throw_ins'],                   as_['throw_ins'],                   md=4),
            _metric_card("In Defensive Third",    tz_h['Defensive Third'],           tz_a['Defensive Third'],            md=4),
            _metric_card("In Final Third",        tz_h['Final Third'],               tz_a['Final Third'],                md=4),
        ], className="g-3", style={'marginBottom': '12px'}),
        html.Div([
            _bar_chart(
                hs, as_,
                ['Defensive Third', 'Middle Third', 'Final Third'],
                [tz_h['Defensive Third'], tz_h['Middle Third'], tz_h['Final Third']],
                [tz_a['Defensive Third'], tz_a['Middle Third'], tz_a['Final Third']],
            ),
        ], style=_CARD),
    ], style={'marginBottom': '32px'})

    # ── Penalties ─────────────────────────────────────────────────────────
    penalties_section = html.Div([
        _section_header("Penalties"),
        dbc.Row([
            _metric_card("Penalties Won",      hs['penalties_won'],      as_['penalties_won'],      md=4),
            _metric_card("Penalties Conceded", hs['penalties_conceded'], as_['penalties_conceded'], md=4),
            _metric_card("Penalty Goals",      hs['penalty_goals'],      as_['penalty_goals'],      md=4),
        ], className="g-3"),
    ])

    return html.Div(
        [stats_row, corners_section, free_kicks_section, throw_ins_section, penalties_section],
        style={'marginTop': '16px'},
    )
