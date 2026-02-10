"""
CuléVision - Post-Match Analysis Page

Phase-based post-match analysis framework for FC Barcelona.
Decomposes a match into five analytical phases:

1. Match Statistics & Overview — High-level KPIs and match summary
2. Organised Possession — Build Up, Progression, Fast Break, Finishing
3. Transitions — Counterattacks and Counter-pressing
4. Set Pieces — Corners, Free Kicks, Throw-ins, Penalties
5. Contested Phases — Duels, Loose Balls, Scrambles

Football Logic:
    This framework provides a structured way for analysts to review a match
    through the lens of distinct game phases, each with its own tactical
    significance.  The phases are NOT traditional football taxonomy — they
    represent a custom analytical framework designed for Barcelona's
    positional play philosophy.

Technical Logic:
    Built as a Dash page module following the existing pattern:
    - create_post_match_analysis_layout() builds the page shell
    - register_post_match_analysis_callbacks(app) wires up interactivity
    All data flows through the match_data_adapter abstraction layer.
"""

from dash import html, dcc
from dash.dependencies import Input, Output
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
import plotly.express as px

from utils.config import COLORS
from utils.data_utils import get_match_results, get_match_events
from utils.match_data_adapter import (
    get_match_metadata,
    compute_team_kpis,
    compute_shot_quality_summary,
    compute_territory_metrics,
    compute_momentum_timeline,
    tag_possession_phases,
    get_build_up_stats,
    get_progression_stats,
    get_fast_break_stats,
    get_finishing_stats,
    get_transition_summary,
    get_counterattack_sequences,
    get_counterpress_sequences,
    get_set_piece_summary,
    get_set_piece_events,
    get_contested_summary,
    get_contested_phase_events,
    get_shot_locations,
    identify_barcelona_events,
    identify_opponent_events,
)


# =============================================================================
# Shared chart theming — consistent with existing app visualisations
# =============================================================================

CHART_LAYOUT_DEFAULTS = dict(
    paper_bgcolor='rgba(0,0,0,0)',
    plot_bgcolor='rgba(0,0,0,0)',
    font=dict(color='#E8E9ED', size=12),
    margin=dict(l=40, r=40, t=50, b=40),
    legend=dict(
        orientation='h', yanchor='bottom', y=1.02, xanchor='center', x=0.5,
        font=dict(color='#E8E9ED')
    ),
)

CHART_CONFIG = {'displayModeBar': False}

# Barcelona theme colours for two-team comparisons
HOME_COLOR = COLORS['primary_blue']
AWAY_COLOR = COLORS['garnet']
GOLD = COLORS['gold']


def _empty_fig(message: str = "No data available") -> go.Figure:
    """Return a styled empty placeholder figure."""
    fig = go.Figure()
    fig.update_layout(
        **CHART_LAYOUT_DEFAULTS,
        height=250,
        annotations=[dict(text=message, x=0.5, y=0.5, showarrow=False,
                          font=dict(size=14, color=COLORS['text_secondary']))]
    )
    return fig


# =============================================================================
# Reusable UI components
# =============================================================================

def _stat_card(value, label, color=None):
    """Create a compact stat card (reuses existing pattern from home.py)."""
    if color is None:
        color = GOLD
    return dbc.Card([
        dbc.CardBody([
            html.Div(str(value), className="stat-value", style={'color': color}),
            html.Div(label, className="stat-label")
        ], className="stat-card")
    ], className="h-100")


def _section_card(title, children, footer=None):
    """Create a themed section card with a gold-accented header."""
    card_children = [
        dbc.CardHeader(html.H5(title, className="mb-0", style={'color': GOLD})),
        dbc.CardBody(children),
    ]
    if footer:
        card_children.append(dbc.CardFooter(footer))
    return dbc.Card(card_children, className="mb-3")


def _kpi_row(kpis: dict, columns: list, colors: dict = None):
    """
    Render a row of stat cards from a KPI dict.

    Args:
        kpis: dict of {key: value}
        columns: list of (key, label) tuples specifying order
        colors: optional dict of {key: color}
    """
    if colors is None:
        colors = {}
    n = len(columns)
    width = max(2, 12 // n)
    return dbc.Row([
        dbc.Col(_stat_card(kpis.get(key, 0), label, colors.get(key, GOLD)), width=width)
        for key, label in columns
    ], className="mb-3")


def _comparison_bar(label, home_val, away_val, suffix='', home_name='Home', away_name='Away'):
    """Render a single comparison row for the stats table."""
    return html.Tr([
        html.Td(f"{home_val}{suffix}", style={'textAlign': 'right', 'fontWeight': 'bold', 'width': '30%'}),
        html.Td(label, style={'textAlign': 'center', 'color': COLORS['text_secondary'], 'width': '40%'}),
        html.Td(f"{away_val}{suffix}", style={'textAlign': 'left', 'fontWeight': 'bold', 'width': '30%'}),
    ])


# =============================================================================
# Page layout
# =============================================================================

def create_post_match_analysis_layout():
    """
    Create the Post-Match Analysis page layout.

    Contains a match selector dropdown and a tabbed interface for the five
    analysis phases.
    """
    results = get_match_results()

    match_options = [
        {'label': f"{r['date']} - {r['description']} ({r['competition']})", 'value': r['match_id']}
        for r in results
    ]

    tabs = dbc.Tabs([
        dbc.Tab(label="Match Overview", tab_id="tab-overview",
                tab_style={'backgroundColor': COLORS['dark_secondary']},
                active_tab_style={'backgroundColor': COLORS['dark_tertiary'],
                                  'borderBottom': f'2px solid {GOLD}'}),
        dbc.Tab(label="Organised Possession", tab_id="tab-possession",
                tab_style={'backgroundColor': COLORS['dark_secondary']},
                active_tab_style={'backgroundColor': COLORS['dark_tertiary'],
                                  'borderBottom': f'2px solid {GOLD}'}),
        dbc.Tab(label="Transitions", tab_id="tab-transitions",
                tab_style={'backgroundColor': COLORS['dark_secondary']},
                active_tab_style={'backgroundColor': COLORS['dark_tertiary'],
                                  'borderBottom': f'2px solid {GOLD}'}),
        dbc.Tab(label="Set Pieces", tab_id="tab-setpieces",
                tab_style={'backgroundColor': COLORS['dark_secondary']},
                active_tab_style={'backgroundColor': COLORS['dark_tertiary'],
                                  'borderBottom': f'2px solid {GOLD}'}),
        dbc.Tab(label="Contested Phases", tab_id="tab-contested",
                tab_style={'backgroundColor': COLORS['dark_secondary']},
                active_tab_style={'backgroundColor': COLORS['dark_tertiary'],
                                  'borderBottom': f'2px solid {GOLD}'}),
    ], id="pma-tabs", active_tab="tab-overview", className="mb-4")

    return dbc.Container([
        html.H2("Post-Match Analysis", style={'color': GOLD}, className="mb-4"),
        html.Hr(),

        dbc.Row([
            dbc.Col([
                html.Label("Select Match:", style={'color': COLORS['text_secondary']}),
                dcc.Dropdown(
                    id='pma-match-selector',
                    options=match_options,
                    value=match_options[0]['value'] if match_options else None,
                    style={'backgroundColor': '#151932', 'color': '#000'}
                )
            ], width=6)
        ], className="mb-4"),

        tabs,

        # Tab content rendered dynamically
        html.Div(id='pma-tab-content')
    ], fluid=True, className="py-4")


# =============================================================================
# Callback registration
# =============================================================================

def register_post_match_analysis_callbacks(app):
    """Register all callbacks for the post-match analysis page."""

    @app.callback(
        Output('pma-tab-content', 'children'),
        Input('pma-match-selector', 'value'),
        Input('pma-tabs', 'active_tab'),
    )
    def update_pma_content(match_id, active_tab):
        """
        Master callback: loads match events and renders the active tab.

        Technical Logic:
            Fetches events once per match selection, then delegates rendering
            to the appropriate tab builder function.
        """
        if not match_id:
            return html.P("Select a match to begin analysis.",
                          style={'color': COLORS['text_secondary']})

        events = get_match_events(match_id)
        if events.empty:
            return html.P("No event data available for this match.",
                          style={'color': COLORS['text_secondary']})

        tab_builders = {
            'tab-overview': _build_overview_tab,
            'tab-possession': _build_possession_tab,
            'tab-transitions': _build_transitions_tab,
            'tab-setpieces': _build_setpieces_tab,
            'tab-contested': _build_contested_tab,
        }

        builder = tab_builders.get(active_tab, _build_overview_tab)
        return builder(events)


# =============================================================================
# Tab 1 — Match Overview
# =============================================================================

def _build_overview_tab(events):
    """
    Render the Match Statistics & Overview tab.

    Football Logic:
        Provides a high-level summary of the match: scoreline, team KPIs,
        possession, territory, shot quality, and momentum timeline.
    """
    meta = get_match_metadata(events)
    home_kpis = compute_team_kpis(events, 'home')
    away_kpis = compute_team_kpis(events, 'away')
    home_shots = compute_shot_quality_summary(events, 'home')
    away_shots = compute_shot_quality_summary(events, 'away')
    territory = compute_territory_metrics(events)
    momentum = compute_momentum_timeline(events)

    home_team = meta.get('home_team', 'Home')
    away_team = meta.get('away_team', 'Away')

    # --- Match header ---
    match_header = dbc.Card([
        dbc.CardBody([
            dbc.Row([
                dbc.Col([
                    html.H4(home_team, className="text-end mb-0"),
                    html.Small("Home", className="text-end d-block",
                               style={'color': COLORS['text_secondary']})
                ], width=4),
                dbc.Col([
                    html.H2(f"{home_kpis['goals']} - {away_kpis['goals']}",
                             className="text-center mb-0", style={'color': GOLD}),
                    html.Small(meta.get('competition', ''), className="text-center d-block",
                               style={'color': COLORS['text_secondary']})
                ], width=4),
                dbc.Col([
                    html.H4(away_team, className="text-start mb-0"),
                    html.Small("Away", className="text-start d-block",
                               style={'color': COLORS['text_secondary']})
                ], width=4),
            ], align="center")
        ])
    ], className="mb-4")

    # --- Stats comparison table ---
    stat_pairs = [
        ('Possession', 'possession', '%'),
        ('Shots', 'shots', ''),
        ('Shots on Target', 'shots_on_target', ''),
        ('Passes', 'passes', ''),
        ('Pass Accuracy', 'pass_accuracy', '%'),
        ('Fouls', 'fouls', ''),
        ('Corners', 'corners', ''),
        ('Yellow Cards', 'yellow_cards', ''),
        ('Red Cards', 'red_cards', ''),
    ]
    stats_rows = [
        _comparison_bar(label, home_kpis.get(key, 0), away_kpis.get(key, 0),
                        suffix, home_team, away_team)
        for label, key, suffix in stat_pairs
    ]

    stats_card = _section_card("Match Statistics", [
        html.Table([html.Tbody(stats_rows)],
                    className="table table-dark", style={'width': '100%'})
    ])

    # --- Possession bar ---
    possession_fig = go.Figure(data=[
        go.Bar(y=['Possession'], x=[home_kpis.get('possession', 50)],
               orientation='h', name=home_team, marker_color=HOME_COLOR,
               text=[f"{home_kpis.get('possession', 50)}%"], textposition='inside'),
        go.Bar(y=['Possession'], x=[away_kpis.get('possession', 50)],
               orientation='h', name=away_team, marker_color=AWAY_COLOR,
               text=[f"{away_kpis.get('possession', 50)}%"], textposition='inside'),
    ])
    possession_fig.update_layout(**CHART_LAYOUT_DEFAULTS, barmode='stack', height=100)

    # --- Territory chart ---
    territory_fig = go.Figure()
    zones = ['Def Third', 'Mid Third', 'Att Third']
    home_terr = territory.get('home', {})
    away_terr = territory.get('away', {})
    territory_fig.add_trace(go.Bar(
        x=zones,
        y=[home_terr.get('def_third', 0), home_terr.get('mid_third', 0), home_terr.get('att_third', 0)],
        name=home_team, marker_color=HOME_COLOR
    ))
    territory_fig.add_trace(go.Bar(
        x=zones,
        y=[away_terr.get('def_third', 0), away_terr.get('mid_third', 0), away_terr.get('att_third', 0)],
        name=away_team, marker_color=AWAY_COLOR
    ))
    territory_fig.update_layout(**CHART_LAYOUT_DEFAULTS, barmode='group', height=300,
                                 yaxis_title='% of Actions')

    # --- Shot quality comparison ---
    shot_fig = go.Figure()
    shot_cats = ['Total Shots', 'Inside Box', 'Outside Box', 'Big Chances']
    shot_fig.add_trace(go.Bar(
        x=shot_cats,
        y=[home_shots['total_shots'], home_shots['inside_box'],
           home_shots['outside_box'], home_shots['big_chances']],
        name=home_team, marker_color=HOME_COLOR
    ))
    shot_fig.add_trace(go.Bar(
        x=shot_cats,
        y=[away_shots['total_shots'], away_shots['inside_box'],
           away_shots['outside_box'], away_shots['big_chances']],
        name=away_team, marker_color=AWAY_COLOR
    ))
    shot_fig.update_layout(**CHART_LAYOUT_DEFAULTS, barmode='group', height=300,
                            yaxis_title='Count')

    # --- Momentum timeline ---
    if not momentum.empty:
        momentum_fig = go.Figure()
        momentum_fig.add_trace(go.Scatter(
            x=momentum['minute_bucket'], y=momentum['home_momentum'],
            mode='lines+markers', name=home_team,
            line=dict(color=HOME_COLOR, width=2), marker=dict(size=6)
        ))
        momentum_fig.add_trace(go.Scatter(
            x=momentum['minute_bucket'], y=momentum['away_momentum'],
            mode='lines+markers', name=away_team,
            line=dict(color=AWAY_COLOR, width=2), marker=dict(size=6)
        ))
        momentum_fig.update_layout(**CHART_LAYOUT_DEFAULTS, height=300,
                                    xaxis_title='Minute', yaxis_title='Successful Actions')
    else:
        momentum_fig = _empty_fig("No momentum data available")

    # --- Shot map ---
    shot_map = _build_shot_map(events, home_team, away_team)

    return html.Div([
        match_header,
        dbc.Row([
            dbc.Col(stats_card, width=5),
            dbc.Col([
                _section_card("Possession", [
                    dcc.Graph(figure=possession_fig, config=CHART_CONFIG)
                ]),
                _section_card("Territory", [
                    dcc.Graph(figure=territory_fig, config=CHART_CONFIG)
                ]),
            ], width=7),
        ], className="mb-3"),
        dbc.Row([
            dbc.Col(_section_card("Shot Quality", [
                dcc.Graph(figure=shot_fig, config=CHART_CONFIG)
            ]), width=6),
            dbc.Col(_section_card("Shot Map", [
                dcc.Graph(figure=shot_map, config=CHART_CONFIG)
            ]), width=6),
        ], className="mb-3"),
        dbc.Row([
            dbc.Col(_section_card("Match Momentum", [
                dcc.Graph(figure=momentum_fig, config=CHART_CONFIG)
            ]), width=12),
        ]),
    ])


def _build_shot_map(events, home_team, away_team):
    """
    Build a pitch-based shot map using Plotly.

    Football Logic:
        Shows where shots were taken from, colour-coded by team and sized/
        shaped by outcome (goal vs miss vs saved).

    Technical Logic:
        Uses a half-pitch approximation (x: 50-100, y: 0-100) with
        rectangular pitch markings drawn as shapes. Degrades to empty
        figure if no coordinate data is available.
    """
    home_shots = get_shot_locations(events, team_code=None)
    if home_shots.empty:
        return _empty_fig("No shot coordinate data available")

    # Separate by team
    all_shots_df = events[events['event_type'].isin(['Miss', 'Saved Shot', 'Goal'])].copy()
    if all_shots_df.empty or 'x' not in all_shots_df.columns:
        return _empty_fig("No shot coordinate data available")

    fig = go.Figure()

    # Draw half-pitch outline
    _add_pitch_shapes(fig)

    # Plot shots for each team
    for team_pos, color, name in [('home', HOME_COLOR, home_team), ('away', AWAY_COLOR, away_team)]:
        team_shots = all_shots_df[all_shots_df['team_position'] == team_pos]
        if team_shots.empty:
            continue

        for evt_type, symbol, size in [('Goal', 'star', 18), ('Saved Shot', 'circle', 10), ('Miss', 'x', 10)]:
            subset = team_shots[team_shots['event_type'] == evt_type]
            if subset.empty:
                continue
            fig.add_trace(go.Scatter(
                x=subset['x'], y=subset['y'],
                mode='markers', name=f"{name} - {evt_type}",
                marker=dict(color=color, size=size, symbol=symbol,
                            line=dict(width=1, color='white')),
                text=[f"{r.get('player_name', '')} {r.get('time_min', '')}''"
                      for _, r in subset.iterrows()],
                hovertemplate='%{text}<extra></extra>'
            ))

    fig.update_layout(
        **CHART_LAYOUT_DEFAULTS,
        height=400,
        xaxis=dict(range=[49, 101], showgrid=False, zeroline=False,
                   showticklabels=False, fixedrange=True),
        yaxis=dict(range=[-1, 101], showgrid=False, zeroline=False,
                   showticklabels=False, scaleanchor='x', fixedrange=True),
        showlegend=True,
    )
    return fig


def _add_pitch_shapes(fig):
    """Add half-pitch markings as Plotly shapes."""
    line_color = 'rgba(255,255,255,0.3)'
    lw = 1

    shapes = [
        # Pitch outline (right half)
        dict(type='rect', x0=50, y0=0, x1=100, y1=100,
             line=dict(color=line_color, width=lw)),
        # Penalty area
        dict(type='rect', x0=83, y0=21.1, x1=100, y1=78.9,
             line=dict(color=line_color, width=lw)),
        # 6-yard box
        dict(type='rect', x0=94.2, y0=36.8, x1=100, y1=63.2,
             line=dict(color=line_color, width=lw)),
        # Penalty spot
        dict(type='circle', x0=87.5, y0=49, x1=88.5, y1=51,
             line=dict(color=line_color, width=lw)),
        # Centre circle (half)
        dict(type='circle', x0=40, y0=40, x1=60, y1=60,
             line=dict(color=line_color, width=lw)),
    ]

    for s in shapes:
        s['fillcolor'] = 'rgba(0,0,0,0)'
        fig.add_shape(**s)


# =============================================================================
# Tab 2 — Organised Possession
# =============================================================================

def _build_possession_tab(events):
    """
    Render the Organised Possession tab.

    Football Logic:
        Decomposes Barcelona's possession into four sub-phases:
        1. Build Up — constructing from the back
        2. Progression — advancing into the final third
        3. Fast Break — rapid vertical attacks
        4. Finishing — shot-producing actions

        Each sub-phase has its own KPI summary and visualisation.
    """
    tagged = tag_possession_phases(events)
    bu_stats = get_build_up_stats(tagged)
    prog_stats = get_progression_stats(tagged)
    fb_stats = get_fast_break_stats(tagged)
    fin_stats = get_finishing_stats(tagged)

    # Phase distribution pie chart
    phase_counts = tagged['possession_phase'].value_counts() if 'possession_phase' in tagged.columns else {}
    phase_labels = {
        'build_up': 'Build Up',
        'progression': 'Progression',
        'fast_break': 'Fast Break',
        'finishing': 'Finishing',
        'unclassified': 'Other',
    }
    phase_colors = {
        'build_up': '#004D98',
        'progression': '#1a75d1',
        'fast_break': '#EDBB00',
        'finishing': '#A50044',
        'unclassified': '#2A2F4A',
    }

    if not phase_counts.empty:
        dist_fig = go.Figure(data=[go.Pie(
            labels=[phase_labels.get(k, k) for k in phase_counts.index],
            values=phase_counts.values,
            marker_colors=[phase_colors.get(k, '#555') for k in phase_counts.index],
            hole=0.4,
            textinfo='label+percent',
            textfont=dict(color='white'),
        )])
        dist_fig.update_layout(**CHART_LAYOUT_DEFAULTS, height=300, showlegend=False)
    else:
        dist_fig = _empty_fig("No phase data")

    # Build-up pass map
    bu_map = _build_phase_action_map(tagged, 'build_up', 'Build Up Actions')

    # Progression map
    prog_map = _build_phase_action_map(tagged, 'progression', 'Progression Actions')

    # Finishing shot map
    fin_map = _build_finishing_map(tagged)

    return html.Div([
        html.H4("Organised Possession Analysis", style={'color': GOLD}, className="mb-3"),
        html.P("Barcelona's possession decomposed into four analytical sub-phases.",
               style={'color': COLORS['text_secondary']}),

        dbc.Row([
            dbc.Col(_section_card("Phase Distribution", [
                dcc.Graph(figure=dist_fig, config=CHART_CONFIG)
            ]), width=4),
            dbc.Col(_section_card("Build Up", [
                _kpi_row(bu_stats, [
                    ('total_passes', 'Passes'), ('pass_accuracy', 'Accuracy %'),
                    ('progressive_passes', 'Progressive'), ('total_actions', 'Actions'),
                ]),
                dcc.Graph(figure=bu_map, config=CHART_CONFIG),
            ]), width=8),
        ], className="mb-3"),

        dbc.Row([
            dbc.Col(_section_card("Progression", [
                _kpi_row(prog_stats, [
                    ('through_balls', 'Through Balls'), ('long_balls', 'Long Balls'),
                    ('crosses', 'Crosses'), ('switches_of_play', 'Switches'),
                    ('take_ons_successful', 'Take Ons Won'),
                ]),
                dcc.Graph(figure=prog_map, config=CHART_CONFIG),
            ]), width=6),
            dbc.Col(html.Div([
                _section_card("Fast Break", [
                    _kpi_row(fb_stats, [
                        ('total_actions', 'Actions'), ('shots', 'Shots'), ('goals', 'Goals'),
                    ], colors={'goals': '#28a745'}),
                ]),
                _section_card("Finishing", [
                    _kpi_row(fin_stats, [
                        ('total_shots', 'Shots'), ('on_target', 'On Target'),
                        ('goals', 'Goals'), ('headed', 'Headers'),
                        ('right_foot', 'Right Foot'), ('left_foot', 'Left Foot'),
                    ], colors={'goals': '#28a745'}),
                    dcc.Graph(figure=fin_map, config=CHART_CONFIG),
                ]),
            ]), width=6),
        ]),
    ])


def _build_phase_action_map(tagged_events, phase, title):
    """
    Build a heatmap of actions for a specific possession phase.

    Technical Logic:
        Uses 2D histogram for density visualisation on the pitch.
    """
    phase_df = tagged_events[tagged_events.get('possession_phase', '') == phase] \
        if 'possession_phase' in tagged_events.columns else tagged_events.iloc[0:0]

    if phase_df.empty or 'x' not in phase_df.columns or 'y' not in phase_df.columns:
        return _empty_fig(f"No spatial data for {title}")

    fig = go.Figure(data=go.Histogram2d(
        x=phase_df['x'].dropna(),
        y=phase_df['y'].dropna(),
        nbinsx=20, nbinsy=15,
        colorscale=[[0, 'rgba(0,0,0,0)'], [0.5, 'rgba(0,77,152,0.5)'], [1, 'rgba(237,187,0,0.9)']],
        showscale=False,
    ))

    _add_pitch_shapes_full(fig)

    fig.update_layout(
        **CHART_LAYOUT_DEFAULTS,
        height=300,
        title=dict(text=title, font=dict(size=13, color=GOLD)),
        xaxis=dict(range=[-1, 101], showgrid=False, zeroline=False,
                   showticklabels=False, fixedrange=True),
        yaxis=dict(range=[-1, 101], showgrid=False, zeroline=False,
                   showticklabels=False, scaleanchor='x', fixedrange=True),
    )
    return fig


def _add_pitch_shapes_full(fig):
    """Add full pitch markings as Plotly shapes."""
    line_color = 'rgba(255,255,255,0.3)'
    lw = 1

    shapes = [
        # Full pitch
        dict(type='rect', x0=0, y0=0, x1=100, y1=100),
        # Centre line
        dict(type='line', x0=50, y0=0, x1=50, y1=100),
        # Centre circle
        dict(type='circle', x0=40, y0=40, x1=60, y1=60),
        # Left penalty area
        dict(type='rect', x0=0, y0=21.1, x1=17, y1=78.9),
        # Right penalty area
        dict(type='rect', x0=83, y0=21.1, x1=100, y1=78.9),
        # Left 6-yard box
        dict(type='rect', x0=0, y0=36.8, x1=5.8, y1=63.2),
        # Right 6-yard box
        dict(type='rect', x0=94.2, y0=36.8, x1=100, y1=63.2),
    ]

    for s in shapes:
        s['line'] = dict(color=line_color, width=lw)
        s['fillcolor'] = 'rgba(0,0,0,0)'
        fig.add_shape(**s)


def _build_finishing_map(tagged_events):
    """Build a shot map for the finishing phase."""
    fin = tagged_events[tagged_events.get('possession_phase', '') == 'finishing'] \
        if 'possession_phase' in tagged_events.columns else tagged_events.iloc[0:0]

    if fin.empty or 'x' not in fin.columns or 'y' not in fin.columns:
        return _empty_fig("No shot location data")

    fig = go.Figure()
    _add_pitch_shapes(fig)

    for evt_type, symbol, color, size in [
        ('Goal', 'star', '#28a745', 18),
        ('Saved Shot', 'circle', GOLD, 12),
        ('Miss', 'x', COLORS['garnet'], 10)
    ]:
        subset = fin[fin['event_type'] == evt_type]
        if subset.empty:
            continue
        fig.add_trace(go.Scatter(
            x=subset['x'], y=subset['y'],
            mode='markers', name=evt_type,
            marker=dict(color=color, size=size, symbol=symbol,
                        line=dict(width=1, color='white')),
            text=[f"{r.get('player_name', '')} {r.get('time_min', '')}''"
                  for _, r in subset.iterrows()],
            hovertemplate='%{text}<extra></extra>'
        ))

    fig.update_layout(
        **CHART_LAYOUT_DEFAULTS,
        height=300,
        xaxis=dict(range=[49, 101], showgrid=False, zeroline=False,
                   showticklabels=False, fixedrange=True),
        yaxis=dict(range=[-1, 101], showgrid=False, zeroline=False,
                   showticklabels=False, scaleanchor='x', fixedrange=True),
    )
    return fig


# =============================================================================
# Tab 3 — Transitions
# =============================================================================

def _build_transitions_tab(events):
    """
    Render the Transitions tab.

    Football Logic:
        Analyses the moments immediately after a change of possession:
        - Counterattacks: rapid attacks after winning the ball
        - Counter-pressing: immediate pressure after losing the ball

        Both are time-window-based analyses using configurable durations.
    """
    summary = get_transition_summary(events)
    ca_sequences = get_counterattack_sequences(events)
    cp_sequences = get_counterpress_sequences(events)

    # Summary KPIs
    ca_kpis = _kpi_row(summary, [
        ('counterattacks', 'Counter Attacks'),
        ('counterattack_shots', 'CA Shots'),
        ('counterattack_goals', 'CA Goals'),
    ], colors={'counterattack_goals': '#28a745'})

    cp_kpis = _kpi_row(summary, [
        ('counterpresses', 'Counter Presses'),
        ('counterpress_recoveries', 'Recoveries'),
    ])

    # Counterattack map
    ca_map = _build_transition_map(ca_sequences, 'Counterattack Origins')

    # Counter-press map
    cp_map = _build_transition_map(cp_sequences, 'Counter-Press Locations')

    # Counterattack detail table
    ca_table_rows = []
    for i, seq in enumerate(ca_sequences[:10]):
        start_event = seq.iloc[0]
        shot_events = seq[seq['event_type'].isin(['Miss', 'Saved Shot', 'Goal'])]
        outcome = shot_events.iloc[-1]['event_type'] if not shot_events.empty else 'No shot'
        duration = (seq.iloc[-1]['time_min'] * 60 + seq.iloc[-1]['time_sec']) - \
                   (seq.iloc[0]['time_min'] * 60 + seq.iloc[0]['time_sec'])
        ca_table_rows.append(html.Tr([
            html.Td(f"{int(start_event.get('time_min', 0))}'"),
            html.Td(str(start_event.get('player_name', ''))),
            html.Td(str(start_event.get('event_type', ''))),
            html.Td(f"{len(seq)} events"),
            html.Td(f"{duration}s"),
            html.Td(outcome, style={'color': '#28a745' if outcome == 'Goal' else COLORS['text_primary']}),
        ]))

    ca_table = html.Table([
        html.Thead(html.Tr([
            html.Th("Min"), html.Th("Player"), html.Th("Trigger"),
            html.Th("Events"), html.Th("Duration"), html.Th("Outcome"),
        ])),
        html.Tbody(ca_table_rows if ca_table_rows else [
            html.Tr([html.Td("No counterattacks detected", colSpan=6,
                              style={'color': COLORS['text_secondary']})])
        ])
    ], className="table table-dark table-striped")

    return html.Div([
        html.H4("Transition Analysis", style={'color': GOLD}, className="mb-3"),
        html.P("Analysis of moments immediately after possession changes.",
               style={'color': COLORS['text_secondary']}),

        dbc.Row([
            dbc.Col(_section_card("Counterattacks (15s window)", [
                ca_kpis,
                dcc.Graph(figure=ca_map, config=CHART_CONFIG),
            ]), width=6),
            dbc.Col(_section_card("Counter-Pressing (5s window)", [
                cp_kpis,
                dcc.Graph(figure=cp_map, config=CHART_CONFIG),
            ]), width=6),
        ], className="mb-3"),

        dbc.Row([
            dbc.Col(_section_card("Counterattack Details", [ca_table]), width=12),
        ]),
    ])


def _build_transition_map(sequences, title):
    """
    Build a pitch map showing transition starting points.

    Technical Logic:
        Plots the origin (x, y) of each transition sequence as scatter
        markers on a full pitch.
    """
    if not sequences:
        return _empty_fig(f"No {title.lower()} data")

    origins = []
    for seq in sequences:
        if not seq.empty and 'x' in seq.columns and 'y' in seq.columns:
            first = seq.iloc[0]
            origins.append({'x': first['x'], 'y': first['y'],
                           'minute': first.get('time_min', 0),
                           'player': first.get('player_name', '')})

    if not origins:
        return _empty_fig(f"No coordinate data for {title.lower()}")

    import pandas as pd
    origins_df = pd.DataFrame(origins)

    fig = go.Figure()
    _add_pitch_shapes_full(fig)

    fig.add_trace(go.Scatter(
        x=origins_df['x'], y=origins_df['y'],
        mode='markers',
        marker=dict(color=GOLD, size=12, symbol='circle',
                    line=dict(width=1, color='white')),
        text=[f"{r['player']} {int(r['minute'])}'" for _, r in origins_df.iterrows()],
        hovertemplate='%{text}<extra></extra>',
        showlegend=False,
    ))

    fig.update_layout(
        **CHART_LAYOUT_DEFAULTS,
        height=350,
        title=dict(text=title, font=dict(size=13, color=GOLD)),
        xaxis=dict(range=[-1, 101], showgrid=False, zeroline=False,
                   showticklabels=False, fixedrange=True),
        yaxis=dict(range=[-1, 101], showgrid=False, zeroline=False,
                   showticklabels=False, scaleanchor='x', fixedrange=True),
    )
    return fig


# =============================================================================
# Tab 4 — Set Pieces
# =============================================================================

def _build_setpieces_tab(events):
    """
    Render the Set Pieces tab.

    Football Logic:
        Set pieces are dead-ball situations: corners, free kicks, throw-ins,
        and penalties. Each can be analysed from an attacking and defending
        perspective, with spatial data if coordinates are available.
    """
    sp_summary = get_set_piece_summary(events)
    att = sp_summary.get('attacking', {})
    defe = sp_summary.get('defending', {})

    barca_sp = get_set_piece_events(events, 'BAR')

    # Summary table
    sp_types = ['corners', 'free_kicks', 'throw_ins', 'penalties']
    sp_labels = {'corners': 'Corners', 'free_kicks': 'Free Kicks',
                 'throw_ins': 'Throw-Ins', 'penalties': 'Penalties'}

    att_rows = []
    def_rows = []
    for sp_type in sp_types:
        a = att.get(sp_type, {'count': 0, 'shots': 0, 'goals': 0})
        d = defe.get(sp_type, {'count': 0, 'shots': 0, 'goals': 0})
        att_rows.append(html.Tr([
            html.Td(sp_labels[sp_type]),
            html.Td(str(a['count']), style={'fontWeight': 'bold', 'color': GOLD}),
            html.Td(str(a['shots'])),
            html.Td(str(a['goals']), style={'color': '#28a745' if a['goals'] > 0 else COLORS['text_primary']}),
        ]))
        def_rows.append(html.Tr([
            html.Td(sp_labels[sp_type]),
            html.Td(str(d['count']), style={'fontWeight': 'bold', 'color': GOLD}),
            html.Td(str(d['shots'])),
            html.Td(str(d['goals']), style={'color': '#dc3545' if d['goals'] > 0 else COLORS['text_primary']}),
        ]))

    att_table = html.Table([
        html.Thead(html.Tr([
            html.Th("Type"), html.Th("Count"), html.Th("Shots"), html.Th("Goals")
        ])),
        html.Tbody(att_rows)
    ], className="table table-dark table-striped")

    def_table = html.Table([
        html.Thead(html.Tr([
            html.Th("Type"), html.Th("Count"), html.Th("Shots Conceded"), html.Th("Goals Conceded")
        ])),
        html.Tbody(def_rows)
    ], className="table table-dark table-striped")

    # Corner map
    corner_map = _build_set_piece_map(barca_sp.get('corners', None), 'Corner Delivery Locations')

    # Free kick map
    fk_map = _build_set_piece_map(barca_sp.get('free_kicks', None), 'Free Kick Locations')

    # Set piece outcome chart
    sp_chart = go.Figure()
    sp_names = [sp_labels[t] for t in sp_types]
    att_counts = [att.get(t, {}).get('count', 0) for t in sp_types]
    def_counts = [defe.get(t, {}).get('count', 0) for t in sp_types]

    sp_chart.add_trace(go.Bar(x=sp_names, y=att_counts, name='Attacking (Barcelona)',
                               marker_color=HOME_COLOR))
    sp_chart.add_trace(go.Bar(x=sp_names, y=def_counts, name='Defending',
                               marker_color=AWAY_COLOR))
    sp_chart.update_layout(**CHART_LAYOUT_DEFAULTS, barmode='group', height=300,
                            yaxis_title='Count')

    return html.Div([
        html.H4("Set Piece Analysis", style={'color': GOLD}, className="mb-3"),
        html.P("Breakdown of dead-ball situations for attacking and defending phases.",
               style={'color': COLORS['text_secondary']}),

        dbc.Row([
            dbc.Col(_section_card("Attacking Set Pieces (Barcelona)", [att_table]), width=6),
            dbc.Col(_section_card("Defending Set Pieces (Opponent)", [def_table]), width=6),
        ], className="mb-3"),

        dbc.Row([
            dbc.Col(_section_card("Set Piece Overview", [
                dcc.Graph(figure=sp_chart, config=CHART_CONFIG)
            ]), width=12),
        ], className="mb-3"),

        dbc.Row([
            dbc.Col(_section_card("Corner Locations", [
                dcc.Graph(figure=corner_map, config=CHART_CONFIG)
            ]), width=6),
            dbc.Col(_section_card("Free Kick Locations", [
                dcc.Graph(figure=fk_map, config=CHART_CONFIG)
            ]), width=6),
        ]),
    ])


def _build_set_piece_map(sp_events, title):
    """Build a pitch map for set piece locations."""
    if sp_events is None or sp_events.empty:
        return _empty_fig(f"No spatial data for {title.lower()}")

    if 'x' not in sp_events.columns or 'y' not in sp_events.columns:
        return _empty_fig(f"No coordinates for {title.lower()}")

    valid = sp_events.dropna(subset=['x', 'y'])
    if valid.empty:
        return _empty_fig(f"No valid coordinates for {title.lower()}")

    fig = go.Figure()
    _add_pitch_shapes_full(fig)

    fig.add_trace(go.Scatter(
        x=valid['x'], y=valid['y'],
        mode='markers',
        marker=dict(color=GOLD, size=10, symbol='diamond',
                    line=dict(width=1, color='white')),
        text=[f"{r.get('player_name', '')} {int(r.get('time_min', 0))}'"
              for _, r in valid.iterrows()],
        hovertemplate='%{text}<extra></extra>',
        showlegend=False,
    ))

    fig.update_layout(
        **CHART_LAYOUT_DEFAULTS,
        height=350,
        title=dict(text=title, font=dict(size=13, color=GOLD)),
        xaxis=dict(range=[-1, 101], showgrid=False, zeroline=False,
                   showticklabels=False, fixedrange=True),
        yaxis=dict(range=[-1, 101], showgrid=False, zeroline=False,
                   showticklabels=False, scaleanchor='x', fixedrange=True),
    )
    return fig


# =============================================================================
# Tab 5 — Contested Phases
# =============================================================================

def _build_contested_tab(events):
    """
    Render the Contested Phases tab.

    Football Logic:
        Contested phases are moments when neither team has clear possession:
        aerial duels, ground duels, loose balls, and scrambles. These are
        often decisive micro-moments that determine control of the match.

        Some of these (especially loose balls and scrambles) may require
        inference if not explicitly tagged. The logic is designed to be
        overridable with explicit tags when data supports them.
    """
    summary = get_contested_summary(events)
    contested = get_contested_phase_events(events)

    meta = get_match_metadata(events)
    opp_name = meta.get('away_team', 'Opponent') if meta.get('barca_is_home') else meta.get('home_team', 'Opponent')

    # Duels summary
    barca_duels = summary.get('duels', {}).get('barcelona', {})
    opp_duels = summary.get('duels', {}).get('opponent', {})

    duel_fig = go.Figure()
    duel_cats = ['Total', 'Won', 'Lost']
    duel_fig.add_trace(go.Bar(
        x=duel_cats,
        y=[barca_duels.get('total', 0), barca_duels.get('won', 0), barca_duels.get('lost', 0)],
        name='Barcelona', marker_color=HOME_COLOR
    ))
    duel_fig.add_trace(go.Bar(
        x=duel_cats,
        y=[opp_duels.get('total', 0), opp_duels.get('won', 0), opp_duels.get('lost', 0)],
        name=opp_name, marker_color=AWAY_COLOR
    ))
    duel_fig.update_layout(**CHART_LAYOUT_DEFAULTS, barmode='group', height=300,
                            yaxis_title='Count')

    # Duel map
    duel_map = _build_contested_map(contested.get('duels', None), 'Duel Locations')

    # Loose balls summary
    lb_summary = summary.get('loose_balls', {})
    lb_barca = lb_summary.get('barcelona', {})
    lb_opp = lb_summary.get('opponent', {})

    # Scrambles summary
    scr_summary = summary.get('scrambles', {})

    # Contested events location heatmap
    all_contested = []
    for key in ['duels', 'scrambles', 'loose_balls']:
        df = contested.get(key)
        if df is not None and not df.empty:
            all_contested.append(df)

    if all_contested:
        import pandas as pd_inner
        all_df = pd_inner.concat(all_contested, ignore_index=True)
        contested_heatmap = _build_contested_heatmap(all_df, 'Contested Phase Heatmap')
    else:
        contested_heatmap = _empty_fig("No contested phase data")

    return html.Div([
        html.H4("Contested Phases Analysis", style={'color': GOLD}, className="mb-3"),
        html.P("Analysis of moments when possession is disputed: duels, loose balls, and scrambles.",
               style={'color': COLORS['text_secondary']}),

        dbc.Row([
            dbc.Col(_section_card("Duels", [
                dcc.Graph(figure=duel_fig, config=CHART_CONFIG),
            ]), width=6),
            dbc.Col(_section_card("Duel Locations", [
                dcc.Graph(figure=duel_map, config=CHART_CONFIG),
            ]), width=6),
        ], className="mb-3"),

        dbc.Row([
            dbc.Col(_section_card("Loose Balls", [
                dbc.Row([
                    dbc.Col([
                        html.H6("Barcelona", style={'color': HOME_COLOR}),
                        _kpi_row(lb_barca, [
                            ('total', 'Total'), ('won', 'Won'), ('lost', 'Lost'),
                        ]),
                    ], width=6),
                    dbc.Col([
                        html.H6(opp_name, style={'color': AWAY_COLOR}),
                        _kpi_row(lb_opp, [
                            ('total', 'Total'), ('won', 'Won'), ('lost', 'Lost'),
                        ]),
                    ], width=6),
                ]),
            ]), width=6),
            dbc.Col(_section_card("Scrambles", [
                _kpi_row(scr_summary, [
                    ('total', 'Total Scramble Events'),
                ]),
                html.P("Scramble events are tagged via Opta qualifier. If no explicit tags "
                       "exist in the data, this section will show zero — override logic can "
                       "be added when richer data becomes available.",
                       style={'color': COLORS['text_secondary'], 'fontSize': '0.85rem'}),
            ]), width=6),
        ], className="mb-3"),

        dbc.Row([
            dbc.Col(_section_card("Contested Phase Heatmap", [
                dcc.Graph(figure=contested_heatmap, config=CHART_CONFIG),
            ]), width=12),
        ]),
    ])


def _build_contested_map(contested_df, title):
    """Build a pitch scatter map for contested events."""
    if contested_df is None or contested_df.empty:
        return _empty_fig(f"No data for {title.lower()}")

    if 'x' not in contested_df.columns or 'y' not in contested_df.columns:
        return _empty_fig(f"No coordinates for {title.lower()}")

    fig = go.Figure()
    _add_pitch_shapes_full(fig)

    for team_code, color, name in [('BAR', HOME_COLOR, 'Barcelona')]:
        team = contested_df[contested_df['team_code'] == team_code] if 'team_code' in contested_df.columns else contested_df
        won = team[team['outcome'] == 1] if 'outcome' in team.columns else team.iloc[0:0]
        lost = team[team['outcome'] == 0] if 'outcome' in team.columns else team.iloc[0:0]

        if not won.empty:
            fig.add_trace(go.Scatter(
                x=won['x'], y=won['y'], mode='markers', name=f'{name} Won',
                marker=dict(color='#28a745', size=8, symbol='circle',
                            line=dict(width=1, color='white')),
            ))
        if not lost.empty:
            fig.add_trace(go.Scatter(
                x=lost['x'], y=lost['y'], mode='markers', name=f'{name} Lost',
                marker=dict(color='#dc3545', size=8, symbol='x',
                            line=dict(width=1, color='white')),
            ))

    fig.update_layout(
        **CHART_LAYOUT_DEFAULTS,
        height=350,
        title=dict(text=title, font=dict(size=13, color=GOLD)),
        xaxis=dict(range=[-1, 101], showgrid=False, zeroline=False,
                   showticklabels=False, fixedrange=True),
        yaxis=dict(range=[-1, 101], showgrid=False, zeroline=False,
                   showticklabels=False, scaleanchor='x', fixedrange=True),
    )
    return fig


def _build_contested_heatmap(events_df, title):
    """Build a heatmap of all contested phase events."""
    if events_df.empty or 'x' not in events_df.columns or 'y' not in events_df.columns:
        return _empty_fig("No spatial data for contested phases")

    fig = go.Figure(data=go.Histogram2d(
        x=events_df['x'].dropna(),
        y=events_df['y'].dropna(),
        nbinsx=20, nbinsy=15,
        colorscale=[[0, 'rgba(0,0,0,0)'], [0.3, 'rgba(165,0,68,0.4)'],
                     [0.7, 'rgba(237,187,0,0.6)'], [1, 'rgba(237,187,0,0.9)']],
        showscale=False,
    ))

    _add_pitch_shapes_full(fig)

    fig.update_layout(
        **CHART_LAYOUT_DEFAULTS,
        height=400,
        title=dict(text=title, font=dict(size=13, color=GOLD)),
        xaxis=dict(range=[-1, 101], showgrid=False, zeroline=False,
                   showticklabels=False, fixedrange=True),
        yaxis=dict(range=[-1, 101], showgrid=False, zeroline=False,
                   showticklabels=False, scaleanchor='x', fixedrange=True),
    )
    return fig
