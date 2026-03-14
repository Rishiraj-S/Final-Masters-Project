"""
Team Analysis — Tab 3: Out of Possession (Defensive Structure)

Answers: Where do we defend and how aggressive are we?

Shows:
- KPIs: PPDA, defensive actions, tackles, interceptions, fouls, press %
- Defensive action heatmap (full pitch)
- Defensive actions scatter map (colour-coded by type)
- Opponent shot map against Barcelona
- Pressure by player (top defensive performers table)
- Fouls by zone (horizontal bar)
"""

from dash import html, dcc
import dash_bootstrap_components as dbc
import plotly.graph_objects as go

from utils.config import COLORS
from utils.data_utils import (
    get_all_events,
    get_match_results,
    CURRENT_SEASON,
)
from pages.match_analysis_tabs.shared import (
    CHART_LAYOUT_DEFAULTS,
    CHART_CONFIG,
    add_pitch_background,
    PITCH_AXIS_FULL,
    PITCH_AXIS_HALF,
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

def _ppda(bar_events, all_events):
    """PPDA: opp passes in defending zone / BAR def actions in opp half."""
    opp_events = all_events[all_events['team_code'] != 'BAR']
    opp_passes_def = opp_events[
        (opp_events['event_type'] == 'Pass') &
        opp_events['x'].notna() & (opp_events['x'] < 40)
    ]
    def_actions = bar_events[
        bar_events['event_type'].isin(['Tackle', 'Interception']) &
        bar_events['x'].notna() & (bar_events['x'] > 50)
    ]
    return round(len(opp_passes_def) / max(len(def_actions), 1), 1)


def _defensive_scatter(bar_events):
    """Full-pitch scatter: tackles (blue) vs interceptions (red)."""
    def_actions = bar_events[
        bar_events['event_type'].isin(['Tackle', 'Interception'])
    ].dropna(subset=['x', 'y'])

    if def_actions.empty:
        return empty_fig("No defensive action data")

    fig = go.Figure()
    add_pitch_background(fig, half=False)

    tackles    = def_actions[def_actions['event_type'] == 'Tackle']
    intercepts = def_actions[def_actions['event_type'] == 'Interception']

    if not tackles.empty:
        fig.add_trace(go.Scatter(
            x=tackles['x'], y=tackles['y'],
            mode='markers', name='Tackle',
            marker=dict(color=HOME_COLOR, size=7, opacity=0.75,
                        line=dict(color='white', width=0.5)),
            text=tackles['player_name'].fillna(''),
            hovertemplate='%{text}<extra>Tackle</extra>',
        ))
    if not intercepts.empty:
        fig.add_trace(go.Scatter(
            x=intercepts['x'], y=intercepts['y'],
            mode='markers', name='Interception',
            marker=dict(color=AWAY_COLOR, size=7, opacity=0.75,
                        symbol='diamond', line=dict(color='white', width=0.5)),
            text=intercepts['player_name'].fillna(''),
            hovertemplate='%{text}<extra>Interception</extra>',
        ))

    fig.update_layout(**CHART_LAYOUT_DEFAULTS, height=400, **PITCH_AXIS_FULL)
    fig.update_layout(legend=dict(orientation='h', y=-0.05, x=0.5, xanchor='center'))
    return fig


def _opponent_shot_map(opp_events):
    """Half-pitch shot map of shots taken AGAINST Barcelona."""
    shot_types = ['Goal', 'Saved Shot', 'Miss']
    shots = opp_events[opp_events['event_type'].isin(shot_types)].dropna(subset=['x', 'y'])

    if shots.empty:
        return empty_fig("No opponent shot data")

    _style = {
        'Goal':       ('star',   AWAY_COLOR, 18),
        'Saved Shot': ('circle', GOLD,       11),
        'Miss':       ('x',      '#888888',  10),
    }

    # Opta coords are from the attacking team's perspective, so opp shots go to x > 50
    # We mirror: opp_x → 100 - opp_x to show on Barcelona's defensive half
    shots = shots.copy()
    shots['x_mirror'] = 100 - shots['x']
    shots['y_mirror'] = shots['y']

    fig = go.Figure()
    add_pitch_background(fig, half=True)

    for etype, (symbol, color, size) in _style.items():
        subset = shots[shots['event_type'] == etype]
        if subset.empty:
            continue
        fig.add_trace(go.Scatter(
            x=subset['x_mirror'], y=subset['y_mirror'],
            mode='markers', name=etype,
            marker=dict(color=color, size=size, symbol=symbol,
                        line=dict(color='white', width=1.5)),
            text=subset['player_name'].fillna(''),
            hovertemplate='<b>%{text}</b><extra>' + etype + '</extra>',
        ))

    fig.update_layout(**CHART_LAYOUT_DEFAULTS, height=400, **PITCH_AXIS_HALF)
    fig.update_layout(legend=dict(orientation='h', y=-0.05, x=0.5, xanchor='center'))
    return fig


def _top_defenders_table(bar_events):
    """Table: top defenders by defensive actions (tackles + interceptions)."""
    def_ev = bar_events[bar_events['event_type'].isin(['Tackle', 'Interception'])]
    if def_ev.empty:
        return html.P("No defensive data", style={'color': COLORS['text_secondary']})

    counts = def_ev.groupby('player_name')['event_type'].value_counts().unstack(fill_value=0)
    counts['Total'] = counts.sum(axis=1)
    counts = counts.sort_values('Total', ascending=False).head(10).reset_index()

    header_cells = ['Player', 'Tackles', 'Interceptions', 'Total']
    col_keys = ['player_name',
                'Tackle' if 'Tackle' in counts.columns else None,
                'Interception' if 'Interception' in counts.columns else None,
                'Total']

    header = html.Tr([html.Th(c, style={'color': GOLD, 'borderBottom': f'1px solid {GOLD}',
                                         'padding': '6px 8px', 'fontSize': '0.8rem'})
                      for c in header_cells])

    rows = []
    for i, (_, row) in enumerate(counts.iterrows()):
        bg = 'rgba(255,255,255,0.03)' if i % 2 else 'transparent'
        cells = [
            html.Td(row['player_name'], style={'padding': '5px 8px', 'fontSize': '0.82rem'}),
            html.Td(int(row.get('Tackle', 0)),       style={'padding': '5px 8px', 'textAlign': 'center'}),
            html.Td(int(row.get('Interception', 0)), style={'padding': '5px 8px', 'textAlign': 'center'}),
            html.Td(int(row['Total']),               style={'padding': '5px 8px', 'textAlign': 'center',
                                                              'color': GOLD, 'fontWeight': 600}),
        ]
        rows.append(html.Tr(cells, style={'backgroundColor': bg}))

    return html.Table(
        [html.Thead(header), html.Tbody(rows)],
        style={'width': '100%', 'borderCollapse': 'collapse', 'color': COLORS['text_primary']},
    )


def _fouls_by_zone(bar_events):
    """Bar: fouls committed by zone."""
    fouls = bar_events[
        (bar_events['event_type'] == 'Foul') & bar_events['x'].notna()
    ]
    if fouls.empty:
        return empty_fig("No foul data")

    own_third  = int(fouls[fouls['x'] < 33].shape[0])
    mid_third  = int(fouls[(fouls['x'] >= 33) & (fouls['x'] < 66)].shape[0])
    opp_third  = int(fouls[fouls['x'] >= 66].shape[0])

    fig = go.Figure(go.Bar(
        y=['Own Third', 'Middle Third', 'Opp Third'],
        x=[own_third, mid_third, opp_third],
        orientation='h',
        marker_color=[AWAY_COLOR, GOLD, HOME_COLOR],
        hovertemplate='%{y}: %{x} fouls<extra></extra>',
    ))
    fig.update_layout(
        **CHART_LAYOUT_DEFAULTS,
        height=180,
        xaxis_title='Fouls',
        margin=dict(l=10, r=10, t=10, b=30),
    )
    return fig


# ---------------------------------------------------------------------------
# Public builder
# ---------------------------------------------------------------------------

def build_out_of_possession_tab(season, competitions, match_ids=None):
    """Build the Out of Possession tab content."""
    events = get_all_events(season)
    if events.empty:
        return html.P("No data available.", style={'color': COLORS['text_secondary']})

    if competitions and 'competition' in events.columns:
        events = events[events['competition'].isin(competitions)]
    if match_ids:
        events = events[events['match_id'].isin(match_ids)]

    bar = events[events['team_code'] == 'BAR']
    opp = events[events['team_code'] != 'BAR']

    if bar.empty:
        return html.P("No Barcelona event data.", style={'color': COLORS['text_secondary']})

    # ── KPIs ────────────────────────────────────────────────────────────────
    def_actions = bar[bar['event_type'].isin(['Tackle', 'Interception'])]
    tackles     = int(bar[bar['event_type'] == 'Tackle'].shape[0])
    intercepts  = int(bar[bar['event_type'] == 'Interception'].shape[0])
    fouls       = int(bar[bar['event_type'] == 'Foul'].shape[0])
    high_press  = int(def_actions[def_actions['x'].notna() & (def_actions['x'] > 50)].shape[0])
    press_pct   = round(high_press / max(len(def_actions), 1) * 100, 1)
    ppda_val    = _ppda(bar, events)

    kpi = kpi_row(
        {
            'ppda':       ppda_val,
            'def_actions': int(len(def_actions)),
            'tackles':    tackles,
            'intercepts': intercepts,
            'high_press': high_press,
            'press_pct':  f"{press_pct}%",
            'fouls':      fouls,
        },
        [
            ('ppda',        'PPDA'),
            ('def_actions', 'Def Actions'),
            ('tackles',     'Tackles'),
            ('intercepts',  'Interceptions'),
            ('high_press',  'High Press'),
            ('press_pct',   'High Press %'),
            ('fouls',       'Fouls Conceded'),
        ],
        colors={'ppda': AWAY_COLOR, 'high_press': GOLD, 'press_pct': HOME_COLOR},
    )

    # ── Defensive action heatmap ─────────────────────────────────────────────
    da_xy = def_actions.dropna(subset=['x', 'y'])
    if not da_xy.empty:
        heatmap_src = render_heatmap_img(da_xy['x'].values, da_xy['y'].values,
                                          cmap='Reds', half=False)
        heatmap_content = html.Img(src=heatmap_src, style={'width': '100%', 'borderRadius': '4px'})
    else:
        heatmap_content = html.P("No data", style={'color': COLORS['text_secondary']})

    heatmap_card  = section_card("Defensive Action Heatmap",  heatmap_content)
    scatter_card  = section_card("Defensive Actions Map",
                                  dcc.Graph(figure=_defensive_scatter(bar), config=CHART_CONFIG))
    opp_shot_card = section_card("Opponent Shots Against",
                                  dcc.Graph(figure=_opponent_shot_map(opp), config=CHART_CONFIG))
    defenders_card = section_card("Top Defenders",             _top_defenders_table(bar))
    fouls_card    = section_card("Fouls Committed by Zone",
                                  dcc.Graph(figure=_fouls_by_zone(bar), config=CHART_CONFIG))

    return html.Div([
        kpi,
        dbc.Row([
            dbc.Col(scatter_card,  md=6),
            dbc.Col(opp_shot_card, md=6),
        ], className="mb-3"),
        dbc.Row([
            dbc.Col(heatmap_card,   md=6),
            dbc.Col([defenders_card, fouls_card], md=6),
        ]),
    ])
