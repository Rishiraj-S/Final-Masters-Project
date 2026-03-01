"""
recovery.py
===========
Recovery Phase tab: defensive actions by block type.
Sections: High Block | Mid Block | Low Block
"""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
from dash import html, dcc
import dash_bootstrap_components as dbc

from utils.config import COLORS

GOLD = COLORS['gold']
_CARD = {
    'backgroundColor': COLORS['dark_secondary'],
    'border': f'1px solid {COLORS["dark_border"]}',
    'borderRadius': '8px',
    'padding': '16px',
}

# Opta x-axis: 0 (own goal) → 100 (opp goal), from performing team's perspective
_HIGH_BLOCK_X = 66   # opponent's final third
_LOW_BLOCK_X  = 33   # own defensive third


# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------

def _split_by_zone(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Return (high_block, mid_block, low_block) subsets based on x coordinate."""
    if 'x' not in df.columns or df.empty:
        empty = pd.DataFrame(columns=df.columns)
        return empty, empty, empty
    x = df['x'].fillna(50.0).astype(float)
    return df[x >= _HIGH_BLOCK_X], df[(x >= _LOW_BLOCK_X) & (x < _HIGH_BLOCK_X)], df[x < _LOW_BLOCK_X]


def _compute(events: pd.DataFrame) -> dict:
    home_team = events['home_team'].iloc[0]
    away_team = events['away_team'].iloc[0]
    result = {'home_team': home_team, 'away_team': away_team, 'teams': {}}

    for pos, team in (('home', home_team), ('away', away_team)):
        te  = events[events['team_position'] == pos]
        opp = events[events['team_position'] != pos]

        tackles         = te[te['event_type'] == 'Tackle']
        tackles_won     = tackles[tackles['outcome'] == 1]
        interceptions   = te[te['event_type'] == 'Interception']
        clearances      = te[te['event_type'] == 'Clearance']
        ball_recoveries = te[te['event_type'] == 'Ball Recovery']
        aerials         = te[te['event_type'] == 'Aerial']
        aerials_won     = aerials[aerials['outcome'] == 1]

        # PPDA: opponent passes ÷ our defensive actions
        opp_passes  = len(opp[opp['event_type'] == 'Pass'])
        def_actions = len(tackles) + len(interceptions) + len(te[te['event_type'] == 'Foul'])
        ppda = round(opp_passes / def_actions, 1) if def_actions > 0 else 0.0

        # All pressing events for zone split
        all_def = pd.concat([tackles, interceptions, ball_recoveries])
        high_press = int((all_def['x'].dropna() >= _HIGH_BLOCK_X).sum()) if 'x' in all_def.columns else 0

        aerial_pct = round(len(aerials_won) / len(aerials) * 100, 1) if len(aerials) > 0 else 0.0

        # Zone split for each action type
        t_high, t_mid, t_low   = _split_by_zone(tackles)
        i_high, i_mid, i_low   = _split_by_zone(interceptions)
        br_high, br_mid, br_low = _split_by_zone(ball_recoveries)
        _, _, cl_low            = _split_by_zone(clearances)  # clearances mainly in own third

        result['teams'][pos] = {
            'team':            team,
            'tackles':         len(tackles),
            'tackles_won':     len(tackles_won),
            'tackle_pct':      round(len(tackles_won) / len(tackles) * 100, 1) if len(tackles) > 0 else 0.0,
            'interceptions':   len(interceptions),
            'clearances':      len(clearances),
            'ball_recoveries': len(ball_recoveries),
            'aerials':         len(aerials),
            'aerials_won':     len(aerials_won),
            'aerial_pct':      aerial_pct,
            'ppda':            ppda,
            'high_press':      high_press,
            # Zone breakdown
            'high': {
                'tackles':         len(t_high),
                'interceptions':   len(i_high),
                'ball_recoveries': len(br_high),
                'total':           len(t_high) + len(i_high) + len(br_high),
            },
            'mid': {
                'tackles':         len(t_mid),
                'interceptions':   len(i_mid),
                'ball_recoveries': len(br_mid),
                'total':           len(t_mid) + len(i_mid) + len(br_mid),
            },
            'low': {
                'tackles':         len(t_low),
                'interceptions':   len(i_low),
                'ball_recoveries': len(br_low),
                'clearances':      len(cl_low),
                'total':           len(t_low) + len(i_low) + len(br_low) + len(cl_low),
            },
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


def _action_bar_chart(hs: dict, as_: dict,
                      categories: list, home_vals: list, away_vals: list) -> dcc.Graph:
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


def _aerial_panel(hs: dict, as_: dict) -> html.Div:
    def _bar_row(team: str, won: int, total: int, pct: float, color: str) -> html.Div:
        return html.Div([
            html.Div([
                html.Span(team, style={
                    'color': COLORS['text_secondary'], 'fontSize': '0.8rem', 'minWidth': '130px',
                }),
                html.Span(f"{won}/{total} ({pct}%)", style={
                    'color': color, 'fontWeight': 'bold', 'fontSize': '0.9rem', 'marginLeft': '8px',
                }),
            ], style={'display': 'flex', 'alignItems': 'center', 'marginBottom': '6px'}),
            html.Div([
                html.Div(style={
                    'width': f'{pct}%', 'height': '8px',
                    'backgroundColor': color,
                    'borderRadius': '4px 0 0 4px' if pct < 100 else '4px',
                }),
                html.Div(style={
                    'width': f'{100 - pct}%', 'height': '8px',
                    'backgroundColor': COLORS['dark_border'],
                    'borderRadius': '0 4px 4px 0' if pct > 0 else '4px',
                }),
            ], style={'display': 'flex', 'marginBottom': '14px'}),
        ])

    return html.Div([
        _bar_row(hs['team'], hs['aerials_won'], hs['aerials'], hs['aerial_pct'], GOLD),
        _bar_row(as_['team'], as_['aerials_won'], as_['aerials'], as_['aerial_pct'],
                 COLORS['text_secondary']),
    ])


# ---------------------------------------------------------------------------
# Tab builder
# ---------------------------------------------------------------------------

def build_recovery_tab(events: pd.DataFrame, **_) -> html.Div:
    """Build the Recovery Phase tab layout."""
    if events.empty:
        return html.P("No event data.", style={"color": COLORS["text_secondary"]})

    d = _compute(events)
    hs, as_ = d['teams']['home'], d['teams']['away']

    # ── Defensive Stats ────────────────────────────────────────────────────
    stats_row = html.Div([
        dbc.Row([
            _metric_card(
                f"Tackles Won ({hs['team']} / {as_['team']})",
                f"{hs['tackles_won']}/{hs['tackles']}",
                f"{as_['tackles_won']}/{as_['tackles']}",
            ),
            _metric_card("Interceptions",   hs['interceptions'], as_['interceptions']),
            _metric_card("Clearances",      hs['clearances'],    as_['clearances']),
            _metric_card("PPDA", hs['ppda'], as_['ppda'], note="lower = higher press"),
        ], className="g-3"),
    ], style={'marginBottom': '32px'})

    # ── High Block (x ≥ 66) ───────────────────────────────────────────────
    high_block = html.Div([
        _section_header("High Block", "Defensive actions in the opponent's final third (x ≥ 66)"),
        dbc.Row([
            _metric_card("High Press Actions",  hs['high_press'],          as_['high_press'],          md=4),
            _metric_card("PPDA",                hs['ppda'],                as_['ppda'],                note="lower = higher press", md=4),
            _metric_card("Total High Actions",  hs['high']['total'],       as_['high']['total'],       md=4),
        ], className="g-3", style={'marginBottom': '12px'}),
        html.Div([
            _action_bar_chart(
                hs, as_,
                ['Tackles', 'Interceptions', 'Ball Recoveries'],
                [hs['high']['tackles'], hs['high']['interceptions'], hs['high']['ball_recoveries']],
                [as_['high']['tackles'], as_['high']['interceptions'], as_['high']['ball_recoveries']],
            ),
        ], style=_CARD),
    ], style={'marginBottom': '32px'})

    # ── Mid Block (33 ≤ x < 66) ───────────────────────────────────────────
    mid_block = html.Div([
        _section_header("Mid Block", "Defensive actions in the middle third (33 ≤ x < 66)"),
        dbc.Row([
            _metric_card("Tackles",          hs['mid']['tackles'],         as_['mid']['tackles'],         md=4),
            _metric_card("Interceptions",    hs['mid']['interceptions'],   as_['mid']['interceptions'],   md=4),
            _metric_card("Ball Recoveries",  hs['mid']['ball_recoveries'], as_['mid']['ball_recoveries'], md=4),
        ], className="g-3", style={'marginBottom': '12px'}),
        html.Div([
            _action_bar_chart(
                hs, as_,
                ['Tackles', 'Interceptions', 'Ball Recoveries'],
                [hs['mid']['tackles'], hs['mid']['interceptions'], hs['mid']['ball_recoveries']],
                [as_['mid']['tackles'], as_['mid']['interceptions'], as_['mid']['ball_recoveries']],
            ),
        ], style=_CARD),
    ], style={'marginBottom': '32px'})

    # ── Low Block (x < 33) ────────────────────────────────────────────────
    low_block = html.Div([
        _section_header("Low Block", "Defensive actions in the own defensive third (x < 33)"),
        dbc.Row([
            _metric_card("Tackles",         hs['low']['tackles'],         as_['low']['tackles'],         md=3),
            _metric_card("Interceptions",   hs['low']['interceptions'],   as_['low']['interceptions'],   md=3),
            _metric_card("Clearances",      hs['low']['clearances'],      as_['low']['clearances'],      md=3),
            _metric_card("Aerial Duels",    f"{hs['aerials_won']}/{hs['aerials']}",
                                            f"{as_['aerials_won']}/{as_['aerials']}",                    md=3),
        ], className="g-3", style={'marginBottom': '12px'}),
        html.Div([
            html.Div("Aerial Duel Success", style={
                'color': COLORS['text_secondary'], 'fontWeight': '500',
                'marginBottom': '12px', 'fontSize': '0.85rem',
            }),
            _aerial_panel(hs, as_),
        ], style=_CARD),
    ])

    return html.Div([stats_row, high_block, mid_block, low_block], style={'marginTop': '16px'})
