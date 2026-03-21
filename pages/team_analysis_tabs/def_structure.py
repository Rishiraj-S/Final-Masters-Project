"""
Team Analysis — Tab 3: Defensive Structure

Answers: Where and how aggressively do we defend?

Sections:
  Pressing (high block)
    - PPDA trend              (pressing intensity per match)
    - Press triggers          (defensive action heatmap — tackle/intercept)
    - High recoveries         (final-third and mid-third regains bar)
  Mid and low block
    - Defensive line height   (avg x of defensive actions over season)
    - Defensive actions map   (tackles / interceptions / clearances scatter)
    - Opp. allowed zones      (where opponents had events — allowed territory)
  Overall shape
    - Compactness             (vertical + horizontal spread of def actions)
    - xGA conceded map        (opponent shot locations with xG proxy)
    - Top defenders table     (tackles / interceptions / clearances / aerials)
"""

from dash import html, dcc
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
import pandas as pd
import numpy as np

from utils.config import COLORS
from utils.data_utils import (
    get_all_events,
    get_match_results,
    exclude_own_goals,
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


_COMP_SHORT = {
    'La Liga': 'Liga',
    'Champions League': 'UCL',
    'Copa del Rey': 'Copa',
    'Spanish Super Cup': 'SC',
}


# ---------------------------------------------------------------------------
# PPDA helpers (reused from former out_of_possession.py)
# ---------------------------------------------------------------------------

def _ppda_value(bar, all_events):
    opp  = all_events[all_events['team_code'] != 'BAR']
    opp_p = opp[(opp['event_type'] == 'Pass') & opp['x'].notna() & (opp['x'] < 40)]
    bar_pr = bar[bar['event_type'].isin(['Tackle', 'Interception']) &
                 bar['x'].notna() & (bar['x'] > 50)]
    return round(len(opp_p) / max(len(bar_pr), 1), 1)


def _ppda_per_match_chart(results, events):
    sorted_r = sorted(results, key=lambda r: r['date'])
    if not sorted_r or events.empty:
        return empty_fig("No PPDA data")

    ppda_vals, labels = [], []
    for r in sorted_r:
        me    = events[events['match_id'] == r['match_id']] if 'match_id' in events.columns else events.head(0)
        if me.empty:
            continue
        b     = me[me['team_code'] == 'BAR']
        o     = me[me['team_code'] != 'BAR']
        opp_p = o[(o['event_type'] == 'Pass') & o['x'].notna() & (o['x'] < 40)]
        bar_pr = b[b['event_type'].isin(['Tackle', 'Interception']) & b['x'].notna() & (b['x'] > 50)]
        ppda   = round(len(opp_p) / max(len(bar_pr), 1), 1)
        ppda_vals.append(ppda)
        labels.append(f"{r['opponent']} · {_COMP_SHORT.get(r['competition'], r['competition'][:4])}")

    if not ppda_vals:
        return empty_fig("No PPDA data")

    colors = [HOME_COLOR if v <= 8 else GOLD if v <= 12 else AWAY_COLOR for v in ppda_vals]
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=list(range(1, len(ppda_vals) + 1)), y=ppda_vals,
        marker_color=colors,
        text=labels,
        hovertemplate='Match %{x}: %{text}<br>PPDA: %{y}<extra></extra>',
    ))
    avg = round(sum(ppda_vals) / len(ppda_vals), 1)
    fig.add_hline(y=avg, line=dict(color='rgba(255,255,255,0.4)', dash='dot'),
                  annotation_text=f'Avg {avg}', annotation_position='right')
    fig.add_hline(y=10, line=dict(color=GOLD, dash='dash', width=1),
                  annotation_text='High press threshold (10)',
                  annotation_position='right')
    fig.update_layout(
        **CHART_LAYOUT_DEFAULTS, height=300,
        xaxis_title='Match',
        yaxis_title='PPDA (lower = more pressing)',
    )
    return fig


# ---------------------------------------------------------------------------
# Pressing
# ---------------------------------------------------------------------------

def _press_triggers_heatmap(bar):
    """Heatmap of all defensive actions (tackling + intercepting) — press triggers."""
    da = bar[bar['event_type'].isin(['Tackle', 'Interception'])].dropna(subset=['x', 'y'])
    if da.empty:
        return None
    return render_heatmap_img(da['x'].values, da['y'].values, cmap='Reds', half=False)


def _high_recoveries_bar(bar):
    """Stacked bar: ball recoveries/regains by zone (own / mid / final third)."""
    gains = bar[
        bar['event_type'].isin(['Ball Recovery', 'Tackle', 'Interception']) &
        bar['x'].notna()
    ]
    if gains.empty:
        return empty_fig("No recovery data")

    types = ['Ball Recovery', 'Tackle', 'Interception']
    zones = ['Own Third', 'Mid Third', 'Final Third']
    colors = [HOME_COLOR, GOLD, AWAY_COLOR]

    fig = go.Figure()
    for etype, color in zip(types, colors):
        ev  = gains[gains['event_type'] == etype]
        own = int(ev[ev['x'] < 33].shape[0])
        mid = int(ev[(ev['x'] >= 33) & (ev['x'] < 66)].shape[0])
        fin = int(ev[ev['x'] >= 66].shape[0])
        fig.add_trace(go.Bar(
            y=zones, x=[own, mid, fin],
            orientation='h',
            name=etype,
            marker_color=color,
            hovertemplate=etype + ' — %{y}: %{x}<extra></extra>',
        ))

    fig.update_layout(
        **CHART_LAYOUT_DEFAULTS,
        height=240,
        barmode='stack',
        xaxis_title='Actions',
    )
    fig.update_layout(legend=dict(orientation='h', y=1.05, x=0.5, xanchor='center'))
    return fig


# ---------------------------------------------------------------------------
# Mid and low block
# ---------------------------------------------------------------------------

def _def_line_height_chart(results, events):
    """Line chart: avg x of defensive actions per match (block height over season)."""
    sorted_r = sorted(results, key=lambda r: r['date'])
    if not sorted_r or events.empty:
        return empty_fig("No defensive line data")

    heights, labels = [], []
    for r in sorted_r:
        me   = events[events['match_id'] == r['match_id']] if 'match_id' in events.columns else events.head(0)
        if me.empty:
            continue
        b    = me[me['team_code'] == 'BAR']
        da   = b[b['event_type'].isin(['Tackle', 'Interception', 'Clearance']) & b['x'].notna()]
        if da.empty:
            continue
        heights.append(round(da['x'].mean(), 1))
        labels.append(f"{r['opponent']} · {_COMP_SHORT.get(r['competition'], r['competition'][:4])}")

    if not heights:
        return empty_fig("No defensive line data")

    avg = round(sum(heights) / len(heights), 1)
    x = list(range(1, len(heights) + 1))

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=x, y=heights,
        mode='lines+markers',
        line=dict(color=HOME_COLOR, width=2),
        marker=dict(size=7, color=GOLD),
        text=labels,
        hovertemplate='Match %{x}: %{text}<br>Def Line: x=%{y:.1f}<extra></extra>',
    ))
    fig.add_hline(y=avg, line=dict(color='rgba(255,255,255,0.3)', dash='dot'),
                  annotation_text=f'Avg {avg}', annotation_position='right')

    # Reference zones
    for y_val, label, col in [(33, 'Own Third', AWAY_COLOR), (66, 'Mid Third end', GOLD)]:
        fig.add_hline(y=y_val, line=dict(color=col, dash='dash', width=1),
                      annotation_text=label, annotation_position='left')

    fig.update_layout(
        **CHART_LAYOUT_DEFAULTS, height=300,
        xaxis_title='Match',
        yaxis_title='Avg Defensive Action x (0=own goal)',
        yaxis=dict(range=[0, 100]),
    )
    return fig


def _defensive_scatter(bar):
    """Full-pitch scatter: tackles (blue), interceptions (red), clearances (gold)."""
    da = bar[bar['event_type'].isin(['Tackle', 'Interception', 'Clearance'])].dropna(subset=['x', 'y'])
    if da.empty:
        return empty_fig("No defensive action data")

    fig = go.Figure()
    add_pitch_background(fig, half=False)

    style_map = {
        'Tackle':       (HOME_COLOR, 'circle'),
        'Interception': (AWAY_COLOR, 'diamond'),
        'Clearance':    (GOLD,       'triangle-up'),
    }
    for etype, (color, symbol) in style_map.items():
        subset = da[da['event_type'] == etype]
        if subset.empty:
            continue
        fig.add_trace(go.Scatter(
            x=subset['x'], y=subset['y'],
            mode='markers', name=etype,
            marker=dict(color=color, size=7, opacity=0.75, symbol=symbol,
                        line=dict(color='white', width=0.5)),
            text=subset['player_name'].fillna('') if 'player_name' in subset.columns else [''] * len(subset),
            hovertemplate='%{text}<extra>' + etype + '</extra>',
        ))

    fig.update_layout(**CHART_LAYOUT_DEFAULTS, height=400, **PITCH_AXIS_FULL)
    fig.update_layout(legend=dict(orientation='h', y=-0.05, x=0.5, xanchor='center'))
    return fig


def _opp_allowed_zones(opp):
    """Heatmap of all opponent events — shows which zones Barca concedes territory."""
    coords = opp.dropna(subset=['x', 'y'])
    if coords.empty:
        return None
    return render_heatmap_img(coords['x'].values, coords['y'].values,
                              cmap='Oranges', half=False)


# ---------------------------------------------------------------------------
# Overall shape
# ---------------------------------------------------------------------------

def _compactness_chart(bar):
    """
    Compactness: interquartile range of x (depth) and y (width) for
    defensive actions over the season. Displayed as a scatter with ellipse.
    """
    da = bar[bar['event_type'].isin(['Tackle', 'Interception', 'Clearance'])].dropna(subset=['x', 'y'])
    if len(da) < 10:
        return empty_fig("Not enough defensive action data for compactness")

    x_q25, x_q75 = np.percentile(da['x'], [25, 75])
    y_q25, y_q75 = np.percentile(da['y'], [25, 75])
    x_iqr = round(x_q75 - x_q25, 1)
    y_iqr = round(y_q75 - y_q25, 1)

    fig = go.Figure()
    add_pitch_background(fig, half=False)

    # Shade the IQR rectangle
    fig.add_shape(type='rect',
                  x0=x_q25, x1=x_q75, y0=y_q25, y1=y_q75,
                  fillcolor='rgba(161,120,40,0.25)',
                  line=dict(color=GOLD, width=2, dash='dot'))

    fig.add_trace(go.Scatter(
        x=da['x'], y=da['y'],
        mode='markers',
        marker=dict(color=HOME_COLOR, size=4, opacity=0.3,
                    line=dict(color='white', width=0.2)),
        showlegend=False,
        hovertemplate='(%{x:.0f}, %{y:.0f})<extra></extra>',
    ))

    fig.add_annotation(
        x=(x_q25 + x_q75) / 2, y=y_q25 - 5,
        text=f"Depth IQR: {x_iqr:.0f} | Width IQR: {y_iqr:.0f}",
        showarrow=False,
        font=dict(color=GOLD, size=11),
    )

    fig.update_layout(**CHART_LAYOUT_DEFAULTS, height=380, **PITCH_AXIS_FULL,
                      title_text='Compactness — IQR of Defensive Actions',
                      title_font_color=GOLD, title_font_size=11)
    return fig


def _xga_conceded_map(opp):
    """Shot map of opponent shots — mirrored to show Barca's defensive half."""
    shot_types = ['Goal', 'Saved Shot', 'Miss']
    shots = exclude_own_goals(
        opp[opp['event_type'].isin(shot_types)].copy()
    ).dropna(subset=['x', 'y'])

    if shots.empty:
        return empty_fig("No opponent shot data")

    shots = shots.copy()
    shots['x_mirror'] = 100 - shots['x']

    _style = {
        'Goal':       ('star',   AWAY_COLOR, 18),
        'Saved Shot': ('circle', GOLD,       11),
        'Miss':       ('x',      '#888888',  10),
    }

    fig = go.Figure()
    add_pitch_background(fig, half=True)

    for etype, (symbol, color, size) in _style.items():
        subset = shots[shots['event_type'] == etype]
        if subset.empty:
            continue
        fig.add_trace(go.Scatter(
            x=subset['x_mirror'], y=subset['y'],
            mode='markers', name=etype,
            marker=dict(color=color, size=size, symbol=symbol,
                        line=dict(color='white', width=1.5)),
            text=subset['player_name'].fillna('') if 'player_name' in subset.columns else [''] * len(subset),
            hovertemplate='<b>%{text}</b><extra>' + etype + '</extra>',
        ))

    fig.update_layout(**CHART_LAYOUT_DEFAULTS, height=420, **PITCH_AXIS_HALF)
    fig.update_layout(legend=dict(orientation='h', y=-0.05, x=0.5, xanchor='center'))
    return fig


def _top_defenders_table(bar):
    """Table: top 10 players by defensive action totals."""
    types = ['Tackle', 'Interception', 'Clearance', 'Aerial']
    da    = bar[bar['event_type'].isin(types)]
    if da.empty:
        return html.P("No defensive data", style={'color': COLORS['text_secondary']})

    aerial_won = da[(da['event_type'] == 'Aerial') & (da['outcome'] == 1)]
    non_aerial = da[da['event_type'] != 'Aerial']

    counts   = non_aerial.groupby('player_name')['event_type'].value_counts().unstack(fill_value=0)
    aw_count = aerial_won.groupby('player_name').size().rename('Aerial Won')
    counts   = counts.join(aw_count, how='outer').fillna(0)
    for c in ['Tackle', 'Interception', 'Clearance', 'Aerial Won']:
        if c not in counts.columns:
            counts[c] = 0
    counts['Total'] = counts[['Tackle', 'Interception', 'Clearance', 'Aerial Won']].sum(axis=1)
    counts = counts.sort_values('Total', ascending=False).head(10).reset_index()

    _th = {'color': GOLD, 'borderBottom': f'1px solid {GOLD}',
            'padding': '6px 8px', 'fontSize': '0.78rem', 'textAlign': 'center'}
    _td = {'padding': '5px 8px', 'fontSize': '0.82rem', 'textAlign': 'center'}
    _td_name = {'padding': '5px 8px', 'fontSize': '0.82rem'}

    hdrs = ['Player', 'Tackles', 'Intercepts', 'Clearances', 'Aerials Won', 'Total']
    cols = ['player_name', 'Tackle', 'Interception', 'Clearance', 'Aerial Won', 'Total']

    header = html.Tr([html.Th(h, style=_th) for h in hdrs])
    rows   = []
    for i, (_, row) in enumerate(counts.iterrows()):
        bg = 'rgba(255,255,255,0.03)' if i % 2 else 'transparent'
        cells = [
            html.Td(
                int(row.get(c, 0)) if c != 'player_name' else row.get(c, ''),
                style=_td_name if c == 'player_name' else
                      ({**_td, 'color': GOLD, 'fontWeight': 600} if c == 'Total' else _td),
            ) for c in cols
        ]
        rows.append(html.Tr(cells, style={'backgroundColor': bg}))

    return html.Table(
        [html.Thead(header), html.Tbody(rows)],
        style={'width': '100%', 'borderCollapse': 'collapse', 'color': COLORS['text_primary']},
    )


# ---------------------------------------------------------------------------
# Public builder
# ---------------------------------------------------------------------------

def build_def_structure_tab(season, competitions, match_ids=None):
    """Build the Defensive Structure tab content."""
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

    # ── KPIs ─────────────────────────────────────────────────────────────────
    def_actions  = bar[bar['event_type'].isin(['Tackle', 'Interception'])]
    tackles      = int(bar[bar['event_type'] == 'Tackle'].shape[0])
    intercepts   = int(bar[bar['event_type'] == 'Interception'].shape[0])
    clearances   = int(bar[bar['event_type'] == 'Clearance'].shape[0])
    aerials      = bar[bar['event_type'] == 'Aerial']
    aerial_wins  = int(aerials[aerials['outcome'] == 1].shape[0])
    high_press   = int(def_actions[def_actions['x'].notna() & (def_actions['x'] > 50)].shape[0])
    press_pct    = round(high_press / max(len(def_actions), 1) * 100, 1)
    ppda_val     = _ppda_value(bar, events)

    fouls = int(bar[bar['event_type'] == 'Foul'].shape[0])
    if 'Yellow Card' in bar.columns:
        yellow = int(bar[bar['Yellow Card'] == 'Si'].shape[0])
    else:
        yellow = int(bar[bar['event_type'] == 'Yellow Card'].shape[0])

    kpi = kpi_row(
        {
            'ppda':        ppda_val,
            'tackles':     tackles,
            'intercepts':  intercepts,
            'clearances':  clearances,
            'aerial_wins': aerial_wins,
            'high_press':  f"{press_pct}%",
            'fouls':       fouls,
            'yellow':      yellow,
        },
        [
            ('ppda',        'PPDA'),
            ('tackles',     'Tackles'),
            ('intercepts',  'Interceptions'),
            ('clearances',  'Clearances'),
            ('aerial_wins', 'Aerial Wins'),
            ('high_press',  'High Press %'),
            ('fouls',       'Fouls'),
            ('yellow',      'Yellow Cards'),
        ],
        colors={
            'ppda':        AWAY_COLOR,
            'high_press':  HOME_COLOR,
            'aerial_wins': GOLD,
        },
    )

    # ── Results for trend charts ──────────────────────────────────────────────
    all_results = get_match_results()
    results = [r for r in all_results
               if str(r['date'])[:4] in [season.split('-')[0], season.split('-')[1]]]
    if competitions:
        results = [r for r in results if r['competition'] in competitions]
    if match_ids:
        id_set = set(match_ids)
        results = [r for r in results if r['match_id'] in id_set]

    # ── Pressing cards ────────────────────────────────────────────────────────
    ppda_card = section_card(
        "PPDA per Match — Pressing Intensity Trend",
        dcc.Graph(figure=_ppda_per_match_chart(results, events), config=CHART_CONFIG),
    )
    triggers_src = _press_triggers_heatmap(bar)
    triggers_card = section_card(
        "Press Triggers Heatmap — Tackle & Interception Locations",
        html.Img(src=triggers_src, style={'width': '100%', 'borderRadius': '4px'}),
    ) if triggers_src else html.Div()

    recovery_card = section_card(
        "Ball Recoveries by Zone — High / Mid / Low Regains",
        dcc.Graph(figure=_high_recoveries_bar(bar), config=CHART_CONFIG),
    )

    # ── Mid/low block cards ───────────────────────────────────────────────────
    line_height_card = section_card(
        "Defensive Line Height — Avg. Action x per Match",
        dcc.Graph(figure=_def_line_height_chart(results, events), config=CHART_CONFIG),
    )
    scatter_card = section_card(
        "Defensive Actions Map  ● Tackle  ◆ Interception  ▲ Clearance",
        dcc.Graph(figure=_defensive_scatter(bar), config=CHART_CONFIG),
    )
    opp_zones_src = _opp_allowed_zones(opp)
    opp_zones_card = section_card(
        "Opponent Allowed Zones — Where Opponents Operated",
        html.Img(src=opp_zones_src, style={'width': '100%', 'borderRadius': '4px'}),
    ) if opp_zones_src else html.Div()

    # ── Overall shape cards ───────────────────────────────────────────────────
    compact_card = section_card(
        "Compactness — IQR Rectangle of Defensive Actions",
        dcc.Graph(figure=_compactness_chart(bar), config=CHART_CONFIG),
    )
    xga_map_card = section_card(
        "xGA Conceded Map — Opponent Shot Locations  ★ Goal  ● Saved  ✕ Miss",
        dcc.Graph(figure=_xga_conceded_map(opp), config=CHART_CONFIG),
    )
    defenders_card = section_card(
        "Top Defensive Players — Season Breakdown",
        _top_defenders_table(bar),
    )

    return html.Div([
        kpi,
        html.P("Pressing (high block)", style={
            'color': COLORS['text_secondary'], 'fontSize': '0.78rem',
            'fontStyle': 'italic', 'marginTop': '8px', 'marginBottom': '4px',
        }),
        dbc.Row([
            dbc.Col(ppda_card,     md=5),
            dbc.Col([triggers_card, recovery_card], md=7),
        ], className='mb-3'),
        html.P("Mid and low block", style={
            'color': COLORS['text_secondary'], 'fontSize': '0.78rem',
            'fontStyle': 'italic', 'marginBottom': '4px',
        }),
        dbc.Row([
            dbc.Col(line_height_card, md=5),
            dbc.Col(scatter_card,     md=7),
        ], className='mb-3'),
        dbc.Row([
            dbc.Col(opp_zones_card, md=12),
        ], className='mb-3'),
        html.P("Overall shape", style={
            'color': COLORS['text_secondary'], 'fontSize': '0.78rem',
            'fontStyle': 'italic', 'marginBottom': '4px',
        }),
        dbc.Row([
            dbc.Col(compact_card, md=6),
            dbc.Col(xga_map_card, md=6),
        ], className='mb-3'),
        dbc.Row([
            dbc.Col(defenders_card, md=12),
        ], className='mb-3'),
    ])
