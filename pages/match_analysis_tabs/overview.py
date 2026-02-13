"""
Tab 1 -- Match Overview

TV-style match summary inspired by broadcast stat displays: large scoreline
header with team names, and horizontal comparison bars for each stat growing
outward from a centre divider.
"""

from dash import html, dcc
import dash_bootstrap_components as dbc
import plotly.graph_objects as go

from utils.config import COLORS
from utils.match_data_adapter import (
    get_match_metadata,
    compute_team_kpis,
    compute_shot_quality_summary,
    compute_territory_metrics,
    compute_momentum_timeline,
    get_shot_locations,
)

from .shared import (
    CHART_LAYOUT_DEFAULTS, CHART_CONFIG,
    HOME_COLOR, AWAY_COLOR, GOLD,
    empty_fig, section_card,
    add_pitch_background, PITCH_AXIS_HALF,
)


# =============================================================================
# TV-style stat bar component (Dash dark-theme adaptation)
# =============================================================================

def _tv_stat_bar(label, home_val, away_val, suffix='', is_percentage=False):
    """
    Build a single TV-broadcast-style comparison bar.

    Layout:  home_value  [=====|=====]  away_value
                      stat label

    Bars grow outward from a centre divider. The longer bar fills its half
    proportionally; the shorter bar scales relative to the longer one.
    """
    # Normalise to float
    hv = float(home_val) if home_val else 0
    av = float(away_val) if away_val else 0
    max_val = max(hv, av, 1)

    home_pct = (hv / max_val) * 100
    away_pct = (av / max_val) * 100

    # Display strings
    if is_percentage:
        h_display = f"{hv:.1f}{suffix}"
        a_display = f"{av:.1f}{suffix}"
    else:
        h_display = f"{int(hv)}{suffix}"
        a_display = f"{int(av)}{suffix}"

    # Highlight the winning side
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
        # Stat label centred above the bar
        html.Div(label, style={
            'textAlign': 'center',
            'color': COLORS['text_secondary'],
            'fontSize': '0.85rem',
            'marginBottom': '4px',
        }),
        # Value + bar row
        html.Div([
            # Home value
            html.Div(h_display, style={
                'width': '65px', 'textAlign': 'right', 'fontWeight': h_weight,
                'color': HOME_COLOR, 'fontSize': '1.05rem', 'paddingRight': '10px',
            }),
            # Bar container (two halves + centre line)
            html.Div([
                # Left half (home) -- bar grows right-to-left
                html.Div([
                    html.Div(style={
                        'width': f'{home_pct}%',
                        'height': '100%',
                        'backgroundColor': HOME_COLOR,
                        'borderRadius': '7px 0 0 7px',
                        'marginLeft': 'auto',  # push to right edge
                        'transition': 'width 0.4s ease',
                    })
                ], style={**bar_track, 'width': '50%', 'justifyContent': 'flex-end',
                          'borderRadius': '7px 0 0 7px'}),
                # Centre divider
                html.Div(style={
                    'width': '2px', 'height': '14px',
                    'backgroundColor': COLORS['text_secondary'],
                    'flexShrink': '0',
                }),
                # Right half (away) -- bar grows left-to-right
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
            # Away value
            html.Div(a_display, style={
                'width': '65px', 'textAlign': 'left', 'fontWeight': a_weight,
                'color': AWAY_COLOR, 'fontSize': '1.05rem', 'paddingLeft': '10px',
            }),
        ], style={'display': 'flex', 'alignItems': 'center'}),
    ], style={'marginBottom': '14px'})


# =============================================================================
# Shot map builder (reused from original overview)
# =============================================================================

def _build_shot_map(events, home_team, away_team):
    """Build a half-pitch shot map colour-coded by team and outcome."""
    all_shots = get_shot_locations(events, team_code=None)
    if all_shots.empty:
        return empty_fig("No shot coordinate data available")

    shot_df = events[events['event_type'].isin(['Miss', 'Saved Shot', 'Goal'])].copy()
    if shot_df.empty or 'x' not in shot_df.columns:
        return empty_fig("No shot coordinate data available")

    fig = go.Figure()
    add_pitch_background(fig, half=True)

    for team_pos, color, name in [('home', HOME_COLOR, home_team),
                                   ('away', AWAY_COLOR, away_team)]:
        team_shots = shot_df[shot_df['team_position'] == team_pos]
        if team_shots.empty:
            continue
        for evt_type, symbol, size in [('Goal', 'star', 18),
                                        ('Saved Shot', 'circle', 10),
                                        ('Miss', 'x', 10)]:
            subset = team_shots[team_shots['event_type'] == evt_type]
            if subset.empty:
                continue
            fig.add_trace(go.Scatter(
                x=subset['x'], y=subset['y'],
                mode='markers', name=f"{name} - {evt_type}",
                marker=dict(color=color, size=size, symbol=symbol,
                            line=dict(width=1, color='white')),
                text=[f"{r.get('player_name', '')} {r.get('time_min', '')}'"
                      for _, r in subset.iterrows()],
                hovertemplate='%{text}<extra></extra>'
            ))

    fig.update_layout(
        **CHART_LAYOUT_DEFAULTS, height=400, showlegend=True,
        **PITCH_AXIS_HALF,
    )
    return fig


# =============================================================================
# Public tab builder
# =============================================================================

def build_overview_tab(events):
    """Render the Match Overview tab with TV-style stat bars."""
    meta = get_match_metadata(events)
    home_kpis = compute_team_kpis(events, 'home')
    away_kpis = compute_team_kpis(events, 'away')
    home_shots = compute_shot_quality_summary(events, 'home')
    away_shots = compute_shot_quality_summary(events, 'away')
    territory = compute_territory_metrics(events)
    momentum = compute_momentum_timeline(events)

    home_team = meta.get('home_team', 'Home')
    away_team = meta.get('away_team', 'Away')

    # --- Scoreline header ---
    match_header = dbc.Card([
        dbc.CardBody([
            dbc.Row([
                dbc.Col([
                    html.H3(home_team, className="text-end mb-0",
                             style={'fontWeight': '600'}),
                    html.Small("Home", className="text-end d-block",
                               style={'color': COLORS['text_secondary']}),
                ], width=4),
                dbc.Col([
                    html.H1(
                        f"{home_kpis['goals']}  -  {away_kpis['goals']}",
                        className="text-center mb-0",
                        style={'color': GOLD, 'fontWeight': '900',
                               'fontSize': '3.5rem', 'letterSpacing': '0.15em'},
                    ),
                    html.Small(
                        meta.get('competition', ''),
                        className="text-center d-block",
                        style={'color': COLORS['text_secondary']},
                    ),
                ], width=4),
                dbc.Col([
                    html.H3(away_team, className="text-start mb-0",
                             style={'fontWeight': '600'}),
                    html.Small("Away", className="text-start d-block",
                               style={'color': COLORS['text_secondary']}),
                ], width=4),
            ], align="center"),
        ])
    ], className="mb-4")

    # --- TV-style stat bars ---
    stat_bars = html.Div([
        # Team name headers above the bars
        html.Div([
            html.Div(home_team, style={
                'width': '65px', 'textAlign': 'right', 'fontWeight': 'bold',
                'color': HOME_COLOR, 'fontSize': '0.9rem', 'paddingRight': '10px',
            }),
            html.Div(style={'flex': '1'}),
            html.Div(away_team, style={
                'width': '65px', 'textAlign': 'left', 'fontWeight': 'bold',
                'color': AWAY_COLOR, 'fontSize': '0.9rem', 'paddingLeft': '10px',
            }),
        ], style={'display': 'flex', 'alignItems': 'center', 'marginBottom': '16px'}),

        _tv_stat_bar('Possession', home_kpis.get('possession', 50),
                     away_kpis.get('possession', 50), '%', is_percentage=True),
        _tv_stat_bar('Shots', home_kpis.get('shots', 0),
                     away_kpis.get('shots', 0)),
        _tv_stat_bar('Shots on Target', home_kpis.get('shots_on_target', 0),
                     away_kpis.get('shots_on_target', 0)),
        _tv_stat_bar('Passes', home_kpis.get('passes', 0),
                     away_kpis.get('passes', 0)),
        _tv_stat_bar('Pass Accuracy', home_kpis.get('pass_accuracy', 0),
                     away_kpis.get('pass_accuracy', 0), '%', is_percentage=True),
        _tv_stat_bar('Fouls', home_kpis.get('fouls', 0),
                     away_kpis.get('fouls', 0)),
        _tv_stat_bar('Corners', home_kpis.get('corners', 0),
                     away_kpis.get('corners', 0)),
        _tv_stat_bar('Yellow Cards', home_kpis.get('yellow_cards', 0),
                     away_kpis.get('yellow_cards', 0)),
        _tv_stat_bar('Red Cards', home_kpis.get('red_cards', 0),
                     away_kpis.get('red_cards', 0)),
    ], style={
        'padding': '24px',
        'backgroundColor': COLORS['dark_secondary'],
        'borderRadius': '8px',
        'border': f"1px solid {COLORS['dark_border']}",
    })

    # --- Territory chart ---
    territory_fig = go.Figure()
    zones = ['Def Third', 'Mid Third', 'Att Third']
    home_terr = territory.get('home', {})
    away_terr = territory.get('away', {})
    territory_fig.add_trace(go.Bar(
        x=zones,
        y=[home_terr.get('def_third', 0), home_terr.get('mid_third', 0),
           home_terr.get('att_third', 0)],
        name=home_team, marker_color=HOME_COLOR,
    ))
    territory_fig.add_trace(go.Bar(
        x=zones,
        y=[away_terr.get('def_third', 0), away_terr.get('mid_third', 0),
           away_terr.get('att_third', 0)],
        name=away_team, marker_color=AWAY_COLOR,
    ))
    territory_fig.update_layout(**CHART_LAYOUT_DEFAULTS, barmode='group',
                                 height=300, yaxis_title='% of Actions')

    # --- Shot quality comparison ---
    shot_fig = go.Figure()
    shot_cats = ['Total Shots', 'Inside Box', 'Outside Box', 'Big Chances']
    shot_fig.add_trace(go.Bar(
        x=shot_cats,
        y=[home_shots['total_shots'], home_shots['inside_box'],
           home_shots['outside_box'], home_shots['big_chances']],
        name=home_team, marker_color=HOME_COLOR,
    ))
    shot_fig.add_trace(go.Bar(
        x=shot_cats,
        y=[away_shots['total_shots'], away_shots['inside_box'],
           away_shots['outside_box'], away_shots['big_chances']],
        name=away_team, marker_color=AWAY_COLOR,
    ))
    shot_fig.update_layout(**CHART_LAYOUT_DEFAULTS, barmode='group',
                            height=300, yaxis_title='Count')

    # --- Momentum timeline ---
    if not momentum.empty:
        momentum_fig = go.Figure()
        momentum_fig.add_trace(go.Scatter(
            x=momentum['minute_bucket'], y=momentum['home_momentum'],
            mode='lines+markers', name=home_team,
            line=dict(color=HOME_COLOR, width=2), marker=dict(size=6),
        ))
        momentum_fig.add_trace(go.Scatter(
            x=momentum['minute_bucket'], y=momentum['away_momentum'],
            mode='lines+markers', name=away_team,
            line=dict(color=AWAY_COLOR, width=2), marker=dict(size=6),
        ))
        momentum_fig.update_layout(**CHART_LAYOUT_DEFAULTS, height=300,
                                    xaxis_title='Minute',
                                    yaxis_title='Successful Actions')
    else:
        momentum_fig = empty_fig("No momentum data available")

    # --- Shot map ---
    shot_map = _build_shot_map(events, home_team, away_team)

    # --- Assemble layout ---
    return html.Div([
        match_header,

        dbc.Row([
            dbc.Col(stat_bars, width=5),
            dbc.Col([
                section_card("Territory", [
                    dcc.Graph(figure=territory_fig, config=CHART_CONFIG),
                ]),
            ], width=7),
        ], className="mb-3"),

        dbc.Row([
            dbc.Col(section_card("Shot Quality", [
                dcc.Graph(figure=shot_fig, config=CHART_CONFIG),
            ]), width=6),
            dbc.Col(section_card("Shot Map", [
                dcc.Graph(figure=shot_map, config=CHART_CONFIG),
            ]), width=6),
        ], className="mb-3"),

        dbc.Row([
            dbc.Col(section_card("Match Momentum", [
                dcc.Graph(figure=momentum_fig, config=CHART_CONFIG),
            ]), width=12),
        ]),
    ])
