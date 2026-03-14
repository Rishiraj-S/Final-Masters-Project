"""
Team Analysis — Tab 4: Defensive Transition (Counterpressing Model)

Answers: What do we do immediately after losing the ball?

Shows:
- KPIs: turnovers, own-half losses, press regains, high-press actions, gegenpressing %
- Turnover location map (where BAR loses the ball)
- Counterpressing map (defensive actions very close to turnover spots)
- Ball recovery heatmap
- Turnover locations by zone (own / mid / opp third)
- Top counterpressers table (players with most def actions in opponent half)
"""

from dash import html, dcc
import dash_bootstrap_components as dbc
import plotly.graph_objects as go

from utils.config import COLORS
from utils.data_utils import (
    get_all_events,
    CURRENT_SEASON,
)
from pages.match_analysis_tabs.shared import (
    CHART_LAYOUT_DEFAULTS,
    CHART_CONFIG,
    add_pitch_background,
    PITCH_AXIS_FULL,
    section_card,
    kpi_row,
    empty_fig,
    render_heatmap_img,
    GOLD,
    HOME_COLOR,
    AWAY_COLOR,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Event types that signal BAR lost the ball
_TURNOVER_TYPES = [
    'Miscontrol', 'Blocked Pass', 'Ball Recovery',
    'Dispossessed', 'Error', 'Offside Pass',
]


def _turnover_events(bar_events):
    """Return events where BAR loses possession."""
    import pandas as pd
    lost_pass  = bar_events[
        (bar_events['event_type'] == 'Pass') & (bar_events['outcome'] == 0)
    ]
    other_loss = bar_events[bar_events['event_type'].isin(_TURNOVER_TYPES)]
    all_loss   = pd.concat([lost_pass, other_loss], ignore_index=True) if not other_loss.empty else lost_pass
    return all_loss.dropna(subset=['x', 'y'])


def _turnover_map(turnovers):
    """Full-pitch scatter: where BAR lost the ball."""
    if turnovers.empty:
        return empty_fig("No turnover data")

    fig = go.Figure()
    add_pitch_background(fig, half=False)

    # Colour by zone: own third red, mid yellow, opp third blue
    def zone_color(x):
        if x < 33:
            return AWAY_COLOR
        if x < 66:
            return GOLD
        return HOME_COLOR

    colors = turnovers['x'].map(zone_color)

    fig.add_trace(go.Scatter(
        x=turnovers['x'], y=turnovers['y'],
        mode='markers',
        marker=dict(
            color=colors, size=6, opacity=0.70,
            line=dict(color='white', width=0.4),
        ),
        text=turnovers.get('player_name', turnovers['event_type']).fillna(''),
        hovertemplate='%{text}<br>(%{x:.0f}, %{y:.0f})<extra>Turnover</extra>',
        showlegend=False,
    ))

    # Dummy traces for legend
    for label, color in [('Own Third', AWAY_COLOR), ('Mid Third', GOLD), ('Opp Third', HOME_COLOR)]:
        fig.add_trace(go.Scatter(
            x=[None], y=[None], mode='markers',
            marker=dict(color=color, size=8),
            name=label,
        ))

    fig.update_layout(**CHART_LAYOUT_DEFAULTS, height=400, **PITCH_AXIS_FULL)
    fig.update_layout(legend=dict(orientation='h', y=-0.05, x=0.5, xanchor='center'))
    return fig


def _turnover_zone_bar(turnovers):
    """Horizontal bar: turnovers per zone."""
    if turnovers.empty:
        return empty_fig("No turnover data")

    own  = int(turnovers[turnovers['x'] < 33].shape[0])
    mid  = int(turnovers[(turnovers['x'] >= 33) & (turnovers['x'] < 66)].shape[0])
    opp  = int(turnovers[turnovers['x'] >= 66].shape[0])

    fig = go.Figure(go.Bar(
        y=['Own Third', 'Mid Third', 'Opp Third'],
        x=[own, mid, opp],
        orientation='h',
        marker_color=[AWAY_COLOR, GOLD, HOME_COLOR],
        hovertemplate='%{y}: %{x} turnovers<extra></extra>',
    ))
    fig.update_layout(
        **CHART_LAYOUT_DEFAULTS, height=180,
        xaxis_title='Turnovers',
        margin=dict(l=10, r=10, t=10, b=30),
    )
    return fig


def _counterpress_map(bar_events, turnovers):
    """Defensive actions (tackles/interceptions) in opp half — counterpressing."""
    cp = bar_events[
        bar_events['event_type'].isin(['Tackle', 'Interception']) &
        bar_events['x'].notna() & (bar_events['x'] > 50)
    ].dropna(subset=['x', 'y'])

    if cp.empty:
        return empty_fig("No counterpress data")

    fig = go.Figure()
    add_pitch_background(fig, half=False)

    tackles    = cp[cp['event_type'] == 'Tackle']
    intercepts = cp[cp['event_type'] == 'Interception']

    if not tackles.empty:
        fig.add_trace(go.Scatter(
            x=tackles['x'], y=tackles['y'],
            mode='markers', name='Tackle',
            marker=dict(color=GOLD, size=7, opacity=0.8,
                        line=dict(color='white', width=0.5)),
            hovertemplate='Tackle<extra></extra>',
        ))
    if not intercepts.empty:
        fig.add_trace(go.Scatter(
            x=intercepts['x'], y=intercepts['y'],
            mode='markers', name='Interception',
            marker=dict(color=HOME_COLOR, size=7, opacity=0.8,
                        symbol='diamond', line=dict(color='white', width=0.5)),
            hovertemplate='Interception<extra></extra>',
        ))

    fig.update_layout(**CHART_LAYOUT_DEFAULTS, height=400, **PITCH_AXIS_FULL)
    fig.update_layout(legend=dict(orientation='h', y=-0.05, x=0.5, xanchor='center'))
    return fig


def _ball_recovery_heatmap(bar_events):
    """Heatmap of ball recovery locations."""
    rec = bar_events[bar_events['event_type'] == 'Ball Recovery'].dropna(subset=['x', 'y'])
    if rec.empty:
        return None
    return render_heatmap_img(rec['x'].values, rec['y'].values, cmap='YlGn', half=False)


def _top_counterpressers_table(bar_events):
    """Top 10 players by defensive actions in opponent's half (x > 50)."""
    cp = bar_events[
        bar_events['event_type'].isin(['Tackle', 'Interception']) &
        bar_events['x'].notna() & (bar_events['x'] > 50)
    ]
    if cp.empty:
        return html.P("No counterpress data", style={'color': COLORS['text_secondary']})

    counts = cp.groupby('player_name').size().sort_values(ascending=False).head(10).reset_index()
    counts.columns = ['Player', 'High Actions']

    header = html.Tr([
        html.Th(c, style={'color': GOLD, 'borderBottom': f'1px solid {GOLD}',
                           'padding': '6px 8px', 'fontSize': '0.8rem'})
        for c in ['Player', 'High Press Actions']
    ])
    rows = []
    for i, row in counts.iterrows():
        bg = 'rgba(255,255,255,0.03)' if i % 2 else 'transparent'
        rows.append(html.Tr([
            html.Td(row['Player'],       style={'padding': '5px 8px', 'fontSize': '0.82rem'}),
            html.Td(row['High Actions'], style={'padding': '5px 8px', 'textAlign': 'center',
                                                 'color': GOLD, 'fontWeight': 600}),
        ], style={'backgroundColor': bg}))

    return html.Table(
        [html.Thead(header), html.Tbody(rows)],
        style={'width': '100%', 'borderCollapse': 'collapse', 'color': COLORS['text_primary']},
    )


# ---------------------------------------------------------------------------
# Public builder
# ---------------------------------------------------------------------------

def build_def_transition_tab(season, competitions, match_ids=None):
    """Build the Defensive Transition tab content."""
    events = get_all_events(season)
    if events.empty:
        return html.P("No data available.", style={'color': COLORS['text_secondary']})

    if competitions and 'competition' in events.columns:
        events = events[events['competition'].isin(competitions)]
    if match_ids:
        events = events[events['match_id'].isin(match_ids)]

    bar = events[events['team_code'] == 'BAR']

    if bar.empty:
        return html.P("No Barcelona event data.", style={'color': COLORS['text_secondary']})

    turnovers = _turnover_events(bar)

    # ── KPIs ────────────────────────────────────────────────────────────────
    lost_passes  = int(bar[(bar['event_type'] == 'Pass') & (bar['outcome'] == 0)].shape[0])
    n_turnovers  = int(len(turnovers))
    own_half_loss = int(turnovers[turnovers['x'] < 50].shape[0]) if not turnovers.empty else 0
    def_actions   = bar[bar['event_type'].isin(['Tackle', 'Interception'])]
    high_cp       = int(def_actions[def_actions['x'].notna() & (def_actions['x'] > 50)].shape[0])
    cp_pct        = round(high_cp / max(len(def_actions), 1) * 100, 1)
    ball_rec      = int(bar[bar['event_type'] == 'Ball Recovery'].shape[0])

    kpi = kpi_row(
        {
            'turnovers':    n_turnovers,
            'own_half':     own_half_loss,
            'ball_rec':     ball_rec,
            'high_cp':      high_cp,
            'cp_pct':       f"{cp_pct}%",
        },
        [
            ('turnovers', 'Turnovers'),
            ('own_half',  'Own-Half Losses'),
            ('ball_rec',  'Ball Recoveries'),
            ('high_cp',   'High Press Regains'),
            ('cp_pct',    'Gegenpressing %'),
        ],
        colors={'high_cp': GOLD, 'cp_pct': HOME_COLOR, 'own_half': AWAY_COLOR},
    )

    # ── Cards ────────────────────────────────────────────────────────────────
    turnover_map_card  = section_card(
        "Turnover Locations  ● Own Third  ● Mid Third  ● Opp Third",
        dcc.Graph(figure=_turnover_map(turnovers), config=CHART_CONFIG),
    )
    cp_map_card = section_card(
        "Counterpressing Actions (Opponent Half)",
        dcc.Graph(figure=_counterpress_map(bar, turnovers), config=CHART_CONFIG),
    )
    zone_bar_card = section_card(
        "Turnovers by Zone",
        dcc.Graph(figure=_turnover_zone_bar(turnovers), config=CHART_CONFIG),
    )
    cp_table_card = section_card("Top Counterpressers", _top_counterpressers_table(bar))

    # Ball recovery heatmap
    rec_src = _ball_recovery_heatmap(bar)
    if rec_src:
        rec_card = section_card(
            "Ball Recovery Heatmap",
            html.Img(src=rec_src, style={'width': '100%', 'borderRadius': '4px'}),
        )
    else:
        rec_card = html.Div()

    return html.Div([
        kpi,
        dbc.Row([
            dbc.Col(turnover_map_card, md=6),
            dbc.Col(cp_map_card,       md=6),
        ], className="mb-3"),
        dbc.Row([
            dbc.Col([zone_bar_card, cp_table_card], md=5),
            dbc.Col(rec_card,                       md=7),
        ]),
    ])
