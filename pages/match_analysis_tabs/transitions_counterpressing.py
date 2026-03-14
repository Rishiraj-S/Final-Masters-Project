"""
transitions_counterpressing.py
===============================
Transitions & Counterpressing tab: how effective were they immediately after
losing the ball?
Sections:
  1. Transition Stats (two per-team tables with Full/1H/2H)
  2. Ball Win Map (with enhanced tooltips)
  3. Player Ball-Win Stats Table (with Full/1H/2H)
"""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
from dash import html, dcc
import dash_bootstrap_components as dbc

from dash.dependencies import Input, Output, State

from utils.config import COLORS
from utils.data_utils import get_match_events
from page_utils.pitch_zones import get_zone, PitchZone

from .shared import (
    HOME_COLOR, AWAY_COLOR, GOLD,
    CHART_CONFIG, layout_config,
    add_pitch_background, PITCH_AXIS_FULL,
    build_info_box,
    build_team_stats_table,
    build_legend_box,
    CARD_STYLE, section_header,
    HALF_BTN_ACTIVE as _BTN_ACTIVE,
    HALF_BTN_IDLE   as _BTN_IDLE,
)

_WIN_TYPES      = {'Ball Recovery', 'Interception', 'Tackle'}
_SHOT_TYPES     = {'Miss', 'Saved Shot', 'Goal', 'Post', 'Blocked Shot'}
_TURNOVER_TYPES = {'Pass', 'Take On'}  # turnovers = failed versions

# Number of events after a ball win to count as a direct transition sequence
_COUNTER_WINDOW = 6
# Seconds after a turnover in which a defensive regain counts as a counterpressing action
_COUNTER_SECS = 5


# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------

def _compute_half_stats(events: pd.DataFrame, pos: str, period: int | None = None) -> dict:
    """Compute transition/counterpressing stats for a single team, optionally per-half."""
    home_team = events['home_team'].iloc[0]
    away_team = events['away_team'].iloc[0]
    team = home_team if pos == 'home' else away_team

    ev = events.copy()
    if period is not None:
        ev = ev[ev['period_id'] == period]

    te  = ev[ev['team_position'] == pos]
    opp = ev[ev['team_position'] != pos]

    # Turnovers (we lose the ball)
    failed_passes  = te[(te['event_type'] == 'Pass')    & (te['outcome'] == 0)]
    failed_takeons = te[(te['event_type'] == 'Take On') & (te['outcome'] == 0)]
    turnovers_df   = pd.concat([failed_passes, failed_takeons])

    # Ball wins by us
    ball_wins     = te[te['event_type'].isin(_WIN_TYPES)]
    ball_wins_df  = ball_wins.copy()

    # Sort for sequence analysis
    sorted_te  = te.sort_values(['period_id', 'time_min']).reset_index(drop=True)
    sorted_opp = opp.sort_values(['period_id', 'time_min']).reset_index(drop=True)

    # Counter-pressing: our defensive actions within 5 seconds after opponent wins the ball
    opp_wins = sorted_opp[sorted_opp['event_type'].isin(_WIN_TYPES)]
    counterpress_events = []
    for _, win_row in opp_wins.iterrows():
        t_win = win_row['time_min']
        t_deadline = t_win + _COUNTER_SECS / 60.0
        our_cp = sorted_te[
            (sorted_te['period_id'] == win_row['period_id']) &
            (sorted_te['time_min'] >= t_win) &
            (sorted_te['time_min'] <= t_deadline) &
            (sorted_te['event_type'].isin(_WIN_TYPES))
        ]
        counterpress_events.append(our_cp)

    cp_df = pd.concat(counterpress_events).drop_duplicates() if counterpress_events else pd.DataFrame()

    # Sequences ending in a shot after ball win (direct transitions)
    counter_shots = sum(
        1 for i in sorted_te.index[sorted_te['event_type'].isin(_WIN_TYPES)]
        if sorted_te.iloc[i:min(i + _COUNTER_WINDOW + 1, len(sorted_te))]['event_type']
           .isin(_SHOT_TYPES).any()
    )

    return {
        'team':          team,
        'ball_wins':     len(ball_wins_df),
        'turnovers':     len(turnovers_df),
        'counter_shots': counter_shots,
        'cp_regains':    len(cp_df),
    }


def _compute(events: pd.DataFrame) -> dict:
    home_team = events['home_team'].iloc[0]
    away_team = events['away_team'].iloc[0]
    out = {}

    sorted_events = events.sort_values(['period_id', 'time_min']).reset_index(drop=True)

    for pos, team in (('home', home_team), ('away', away_team)):
        te  = events[events['team_position'] == pos]
        opp = events[events['team_position'] != pos]

        # Ball wins by us
        ball_wins_df = te[te['event_type'].isin(_WIN_TYPES)].copy()

        # Counterpressing events: OUR defensive actions within _COUNTER_SECS after
        # the OPPONENT wins the ball.  Only keep events that have coordinates.
        sorted_te  = sorted_events[sorted_events['team_position'] == pos]
        sorted_opp = sorted_events[sorted_events['team_position'] != pos]
        opp_wins = sorted_opp[sorted_opp['event_type'].isin(_WIN_TYPES)]

        # For each opponent ball win, find our actions within _COUNTER_SECS.
        # Keep only the first triggering opponent event per CP action so each
        # marker is plotted once and the tooltip can name what triggered it.
        cp_by_idx: dict = {}
        for _, win_row in opp_wins.iterrows():
            t_win      = win_row['time_min']
            t_deadline = t_win + _COUNTER_SECS / 60.0
            our_cp = sorted_te[
                (sorted_te['period_id'] == win_row['period_id']) &
                (sorted_te['time_min'] >= t_win) &
                (sorted_te['time_min'] <= t_deadline) &
                (sorted_te['event_type'].isin(_WIN_TYPES))
            ]
            for idx, row in our_cp.iterrows():
                if idx not in cp_by_idx:
                    cp_by_idx[idx] = {
                        **row.to_dict(),
                        '_trigger_player': win_row.get('player_name', 'Unknown'),
                        '_trigger_type':   win_row['event_type'],
                        '_trigger_min':    int(win_row['time_min']),
                    }

        cp_events_df = (
            pd.DataFrame(list(cp_by_idx.values()))
            if cp_by_idx
            else pd.DataFrame(columns=list(ball_wins_df.columns) +
                              ['_trigger_player', '_trigger_type', '_trigger_min'])
        )

        # Per-player counterpressing stats (Full / 1H / 2H) — based on cp_events_df
        _CP_COLS = ['Player', 'Actions', 'Recoveries', 'Tackles', 'Interceptions']

        def _cp_player_stats(df):
            if df.empty or 'player_name' not in df.columns:
                return pd.DataFrame(columns=_CP_COLS)
            return (
                df.groupby('player_name')
                .agg(
                    Actions=('event_type', 'count'),
                    Recoveries=('event_type', lambda s: (s == 'Ball Recovery').sum()),
                    Tackles=('event_type', lambda s: (s == 'Tackle').sum()),
                    Interceptions=('event_type', lambda s: (s == 'Interception').sum()),
                )
                .reset_index()
                .rename(columns={'player_name': 'Player'})
                .sort_values('Actions', ascending=False)
                .head(8)
                .reset_index(drop=True)
            )

        cp_player_full = _cp_player_stats(cp_events_df)
        cp_h1 = (cp_events_df[cp_events_df['period_id'] == 1]
                 if 'period_id' in cp_events_df.columns else pd.DataFrame())
        cp_h2 = (cp_events_df[cp_events_df['period_id'] == 2]
                 if 'period_id' in cp_events_df.columns else pd.DataFrame())
        cp_player_h1 = _cp_player_stats(cp_h1)
        cp_player_h2 = _cp_player_stats(cp_h2)

        out[pos] = {
            'team':           team,
            'ball_wins_df':   ball_wins_df,
            'cp_events_df':   cp_events_df,
            'cp_player_full': cp_player_full,
            'cp_player_h1':   cp_player_h1,
            'cp_player_h2':   cp_player_h2,
        }

    return out


# ---------------------------------------------------------------------------
# Stats metrics definition
# ---------------------------------------------------------------------------

_TRANS_METRICS = [
    ('Ball Wins',          'ball_wins',     False),
    ('Turnovers',          'turnovers',     False),
    ('Transitions → Shot', 'counter_shots', False),
    ('Quick Regains',      'cp_regains',    False),
]


# ---------------------------------------------------------------------------
# UI helpers
# ---------------------------------------------------------------------------




_WIN_COLORS = {
    'Tackle':        '#4dabf7',
    'Interception':  '#51cf66',
    'Ball Recovery': '#ffd43b',
}


def _counterpress_map(cp_events_df: pd.DataFrame, team_color: str) -> dcc.Graph:
    """Scatter of counterpressing locations (ball wins within 5 s of opponent ball win)."""
    fig = go.Figure()
    add_pitch_background(fig)

    if not cp_events_df.empty and 'x' in cp_events_df.columns:
        for win_type, group in cp_events_df.groupby('event_type'):
            valid = group.dropna(subset=['x', 'y'])
            if valid.empty:
                continue

            customdata = [
                [
                    r.get('player_name', 'Unknown'),
                    win_type,
                    int(r.get('time_min', 0)),
                    'Successful' if r.get('outcome', 1) == 1 else 'Unsuccessful',
                    r.get('_trigger_player', 'Unknown'),
                    r.get('_trigger_type', '—'),
                    int(r.get('_trigger_min', 0)),
                ]
                for _, r in valid.iterrows()
            ]

            fig.add_trace(go.Scatter(
                x=valid['x'].tolist(), y=valid['y'].tolist(),
                mode='markers',
                name=win_type,
                marker=dict(
                    color=_WIN_COLORS.get(win_type, team_color),
                    size=8, opacity=0.75,
                    line=dict(color='rgba(0,0,0,0.3)', width=0.5),
                ),
                customdata=customdata,
                hovertemplate=(
                    '<b>%{customdata[0]}</b><br>'
                    'Action: %{customdata[1]}<br>'
                    "Minute: %{customdata[2]}'<br>"
                    'Outcome: %{customdata[3]}<br>'
                    '<i>After: %{customdata[4]} (%{customdata[5]}, '
                    "%{customdata[6]}')</i>"
                    '<extra></extra>'
                ),
            ))

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

    fig.update_layout(**layout_config(
        **PITCH_AXIS_FULL,
        height=480,
        margin=dict(l=0, r=0, t=48, b=0),
        legend=dict(
            orientation='v', x=0.01, xanchor='left', y=0.99, yanchor='top',
            bgcolor='rgba(0,0,0,0.55)',
            font=dict(color=COLORS['text_primary'], size=9),
        ),
    ))
    return dcc.Graph(figure=fig, config=CHART_CONFIG)


def _player_cp_table(cp_player_full: pd.DataFrame,
                     cp_player_h1: pd.DataFrame,
                     cp_player_h2: pd.DataFrame,
                     color: str, team_name: str) -> html.Div:
    """Per-player counterpressing stats: actions within 5 s of an opponent ball win."""
    if cp_player_full.empty:
        return html.Div("No counterpressing data", style={'color': COLORS['text_secondary']})

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

    cols = ['Player', 'Actions', 'Recoveries', 'Tackles', 'Interceptions', '1st Half', '2nd Half']
    header = html.Tr([html.Th(c, style=_hdr) for c in cols])

    rows = []
    for i, (_, row) in enumerate(cp_player_full.iterrows()):
        bg = COLORS['dark_tertiary'] if i % 2 == 0 else 'transparent'
        pname = row.get('Player', '')
        h1_row = cp_player_h1[cp_player_h1['Player'] == pname]
        h2_row = cp_player_h2[cp_player_h2['Player'] == pname]
        h1_total = int(h1_row['Actions'].iloc[0]) if not h1_row.empty else 0
        h2_total = int(h2_row['Actions'].iloc[0]) if not h2_row.empty else 0

        short_name = str(pname).split()[-1] if pname else ''
        cells = [
            html.Td(short_name, style={**_val, 'color': color, 'fontWeight': '600',
                                        'textAlign': 'left', 'whiteSpace': 'nowrap'}),
            html.Td(str(int(row.get('Actions', 0))), style=_val),
            html.Td(str(int(row.get('Recoveries', 0))), style=_val),
            html.Td(str(int(row.get('Tackles', 0))), style=_val),
            html.Td(str(int(row.get('Interceptions', 0))), style=_val),
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


# ---------------------------------------------------------------------------
# Filter bar
# ---------------------------------------------------------------------------

def _filter_bar_tcp() -> html.Div:
    lbl_style = {'color': COLORS['text_secondary'], 'fontSize': '0.72rem',
                 'fontWeight': '600', 'textTransform': 'uppercase',
                 'letterSpacing': '0.06em', 'marginRight': '6px',
                 'whiteSpace': 'nowrap'}
    return html.Div([
        html.Div([
            html.Span('Half', style=lbl_style),
            html.Div(style={'display': 'flex', 'gap': '6px'}, children=[
                html.Button('Full',     id='tcp-half-full', n_clicks=0, style=_BTN_ACTIVE),
                html.Button('1st Half', id='tcp-half-1',    n_clicks=0, style=_BTN_IDLE),
                html.Button('2nd Half', id='tcp-half-2',    n_clicks=0, style=_BTN_IDLE),
            ]),
            dcc.Store(id='tcp-half-store', data='all'),
        ], style={'display': 'flex', 'alignItems': 'center'}),
    ], style={
        **CARD_STYLE,
        'display': 'flex', 'alignItems': 'center',
        'flexWrap': 'wrap', 'gap': '8px',
        'marginBottom': '20px', 'marginTop': '8px', 'padding': '12px 16px',
    })


# ---------------------------------------------------------------------------
# Filterable plot renderer
# ---------------------------------------------------------------------------

def _render_cp_maps(events: pd.DataFrame) -> html.Div:
    """Render the counterpressing locations map (re-rendered on half filter change)."""
    if events.empty:
        return html.P("No event data.", style={"color": COLORS["text_secondary"]})
    d = _compute(events)
    hs, as_ = d['home'], d['away']
    return html.Div([
        section_header("Counterpressing Locations"),
        build_legend_box([
            ('●', 'Tackle',       '#4dabf7'),
            ('●', 'Interception', '#51cf66'),
            ('●', 'Recovery',     '#ffd43b'),
        ]),
        dbc.Row([
            dbc.Col(html.Div([
                html.Div(hs['team'], style={'color': HOME_COLOR, 'fontWeight': '700',
                                           'fontSize': '0.85rem', 'marginBottom': '8px'}),
                _counterpress_map(hs['cp_events_df'], HOME_COLOR),
            ], style=CARD_STYLE), md=6, className='mb-3'),
            dbc.Col(html.Div([
                html.Div(as_['team'], style={'color': AWAY_COLOR, 'fontWeight': '700',
                                            'fontSize': '0.85rem', 'marginBottom': '8px'}),
                _counterpress_map(as_['cp_events_df'], AWAY_COLOR),
            ], style=CARD_STYLE), md=6, className='mb-3'),
        ], className='g-3'),
    ], style={'marginBottom': '16px'})


# ---------------------------------------------------------------------------
# Tab builder
# ---------------------------------------------------------------------------

def build_transitions_counterpressing_tab(events: pd.DataFrame, **_) -> html.Div:
    """Build the Transitions & Counterpressing tab layout."""
    if events.empty:
        return html.P("No event data.", style={"color": COLORS["text_secondary"]})

    # Per-half stats (always full match — tables are never filtered)
    h_full = _compute_half_stats(events, 'home')
    h_h1   = _compute_half_stats(events, 'home', 1)
    h_h2   = _compute_half_stats(events, 'home', 2)
    a_full = _compute_half_stats(events, 'away')
    a_h1   = _compute_half_stats(events, 'away', 1)
    a_h2   = _compute_half_stats(events, 'away', 2)

    # Player table uses full-match CP data
    d_full = _compute(events)
    hs, as_ = d_full['home'], d_full['away']

    # ── Summary Stats Tables (static) ────────────────────────────────────
    stats_section = html.Div([
        section_header('Transition Statistics'),
        build_info_box('Ball wins, turnovers & counterpressing — broken down by half'),
        dbc.Row([
            dbc.Col(build_team_stats_table(
                h_full['team'], HOME_COLOR, _TRANS_METRICS, h_full, h_h1, h_h2,
            ), md=6, className='mb-3'),
            dbc.Col(build_team_stats_table(
                a_full['team'], AWAY_COLOR, _TRANS_METRICS, a_full, a_h1, a_h2,
            ), md=6, className='mb-3'),
        ], className='g-3'),
    ], style={'marginBottom': '32px'})

    # ── Player Counterpressing Stats (static) ─────────────────────────────
    player_table = html.Div([
        section_header("Top Player Counterpressing Stats"),
        dbc.Row([
            dbc.Col(_player_cp_table(
                hs['cp_player_full'], hs['cp_player_h1'], hs['cp_player_h2'],
                HOME_COLOR, hs['team'],
            ), md=6, className='mb-3'),
            dbc.Col(_player_cp_table(
                as_['cp_player_full'], as_['cp_player_h1'], as_['cp_player_h2'],
                AWAY_COLOR, as_['team'],
            ), md=6, className='mb-3'),
        ], className='g-3'),
    ])

    return html.Div([
        stats_section,
        _filter_bar_tcp(),
        html.Div(id='tcp-plots-content', children=_render_cp_maps(events)),
        player_table,
    ], style={'marginTop': '16px'})


# ---------------------------------------------------------------------------
# Callback registration
# ---------------------------------------------------------------------------

def register_transitions_counterpressing_callbacks(app) -> None:
    """Register the half-filter callback for the Transitions & Counterpressing tab."""

    @app.callback(
        [
            Output('tcp-half-store', 'data'),
            Output('tcp-half-full', 'style'),
            Output('tcp-half-1',    'style'),
            Output('tcp-half-2',    'style'),
        ],
        [
            Input('tcp-half-full', 'n_clicks'),
            Input('tcp-half-1',    'n_clicks'),
            Input('tcp-half-2',    'n_clicks'),
        ],
        prevent_initial_call=True,
    )
    def _toggle_half(nc_full, nc_1, nc_2):
        from dash import ctx as _ctx
        mapping = {'tcp-half-full': 'all', 'tcp-half-1': '1', 'tcp-half-2': '2'}
        val = mapping.get(_ctx.triggered_id, 'all')
        return (
            val,
            _BTN_ACTIVE if val == 'all' else _BTN_IDLE,
            _BTN_ACTIVE if val == '1'   else _BTN_IDLE,
            _BTN_ACTIVE if val == '2'   else _BTN_IDLE,
        )

    @app.callback(
        Output('tcp-plots-content', 'children'),
        Input('tcp-half-store', 'data'),
        State('pma-selected-match', 'data'),
        prevent_initial_call=True,
    )
    def _update_plots(half, match_id):
        if not match_id:
            return html.P('No match selected.', style={'color': COLORS['text_secondary']})
        events = get_match_events(match_id)
        if events.empty:
            return html.P('No event data.', style={'color': COLORS['text_secondary']})
        if half == '1':
            events = events[events['period_id'] == 1]
        elif half == '2':
            events = events[events['period_id'] == 2]
        return _render_cp_maps(events)
