"""
Team Analysis — Tab 5: Set Pieces

Covers attacking and defending set pieces plus throw-ins.

Sections:
  Attacking set pieces
    - Corner delivery         (inswing / outswing / short corner donut)
    - Free kick threat        (direct vs indirect + shot map)
    - Target zones            (where deliveries land — headed shots from set pieces)
  Defending set pieces
    - xGA from set pieces     (opponent corners + FK shots conceded)
    - Defensive scheme        (zonal vs man-marking proxy from aerial data)
    - Set piece xGA balance   (Atk xG vs Def xGA comparison)
  Throw-ins
    - Throw-in retention      (possession kept % after throw)
    - Throw-in zones          (dangerous long throw areas)
"""

from dash import html, dcc
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
import pandas as pd
import numpy as np

from utils.config import COLORS
from utils.data_utils import (
    get_all_events,
    filter_own_goals,
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

# Opta event types / qualifier names for set pieces
_CORNER_TYPES = ['Corner Awarded', 'Corner']
_FK_TYPES     = ['Free Kick', 'Free kick taken']
_THROW_TYPES  = ['Throw In', 'Throw in']
_SHOT_TYPES   = ['Goal', 'Saved Shot', 'Miss']


# ---------------------------------------------------------------------------
# Helpers: identify set-piece events
# ---------------------------------------------------------------------------

def _bar_sp_shots(bar):
    """BAR shots from set pieces (Set piece qualifier or from corner/FK zone)."""
    shots = exclude_own_goals(bar[bar['event_type'].isin(_SHOT_TYPES)].copy())
    if 'Set piece' in shots.columns:
        return shots[shots['Set piece'] == 'Si']
    # Fallback: shots from typical set-piece start zones
    return shots[shots['x'].notna() & (shots['x'] < 20)]


def _opp_sp_shots(opp):
    """Opponent shots from set pieces."""
    shots = exclude_own_goals(opp[opp['event_type'].isin(_SHOT_TYPES)].copy())
    if 'Set piece' in shots.columns:
        return shots[shots['Set piece'] == 'Si']
    return shots[shots['x'].notna() & (shots['x'] > 80)]


def _xg_proxy(x, y):
    """Simple distance-based xG proxy."""
    gx, gy = 100.0, 50.0
    dx = gx - x
    dy = abs(gy - y)
    dist = np.sqrt(dx**2 + dy**2)
    angle = np.degrees(np.arctan2(7.32 * dx, dx**2 + dy**2 - (7.32/2)**2)) if dx > 0 else 0
    angle = max(angle, 0)
    return max(round(min(0.05 + angle / 180 * 0.8 * (1 - dist / 120), 0.95), 3), 0.01)


# ---------------------------------------------------------------------------
# Attacking set pieces
# ---------------------------------------------------------------------------

def _corner_delivery_donut(bar):
    """
    Donut: corner delivery type — Inswing / Outswing / Short.
    Uses qualifier columns if available, else approximates by y movement.
    """
    # Look for corner-related events
    corners = pd.concat([
        bar[bar['event_type'].isin(_CORNER_TYPES)],
        bar[(bar['event_type'] == 'Pass') & bar.get('Corner taken', pd.Series(dtype=str)).eq('Si')]
        if 'Corner taken' in bar.columns else bar.head(0),
    ]).drop_duplicates()

    if corners.empty:
        # Try: passes from corner positions (x≈0 or x≈100, y≈0 or y≈100)
        corners = bar[
            (bar['event_type'] == 'Pass') &
            bar['x'].notna() & bar['y'].notna() &
            (
                (bar['x'] < 5) | (bar['x'] > 95)
            ) &
            (
                (bar['y'] < 5) | (bar['y'] > 95)
            )
        ]

    if corners.empty:
        return empty_fig("No corner data available")

    inswing  = 0
    outswing = 0
    short    = 0

    if 'Inswinging' in corners.columns:
        inswing  = int(corners[corners['Inswinging'] == 'Si'].shape[0])
        outswing = int(corners[corners.get('Outswinging', pd.Series(dtype=str)) == 'Si'].shape[0])
        short    = int(len(corners) - inswing - outswing)
    elif 'end_y' in corners.columns and 'end_x' in corners.columns:
        # Approximate: short if end_x close to start, else cross delivery
        c        = corners.dropna(subset=['end_x', 'end_y', 'y'])
        for _, row in c.iterrows():
            dist_from_corner = np.sqrt((row['end_x'] - row['x'])**2 + (row['end_y'] - row['y'])**2)
            if dist_from_corner < 20:
                short += 1
            elif row['y'] < 50 and row['end_y'] > row['y']:
                inswing += 1
            else:
                outswing += 1
    else:
        return empty_fig("No corner delivery qualifier data")

    if inswing + outswing + short == 0:
        return empty_fig("No corner delivery data")

    fig = go.Figure(go.Pie(
        labels=['Inswing', 'Outswing', 'Short'],
        values=[inswing, outswing, short],
        marker_colors=[HOME_COLOR, AWAY_COLOR, GOLD],
        hole=0.45,
        textinfo='label+percent',
        textfont=dict(color='white', size=12),
    ))
    fig.update_layout(**CHART_LAYOUT_DEFAULTS, height=280, showlegend=False)
    fig.update_layout(margin=dict(l=0, r=0, t=20, b=0))
    fig.update_layout(title_text='Corner Delivery Types', title_font_color=GOLD, title_font_size=12)
    return fig


def _free_kick_shot_map(bar):
    """Shot map of Barca free kick shots."""
    fk_shots = bar[
        bar['event_type'].isin(_SHOT_TYPES) & bar['x'].notna() & bar['y'].notna()
    ]
    # Filter by set piece qualifier or by typical FK zones
    if 'Free kick' in bar.columns:
        fk_shots = fk_shots[fk_shots['Free kick'] == 'Si']
    elif 'Set piece' in fk_shots.columns:
        fk_shots = fk_shots[fk_shots['Set piece'] == 'Si']

    fk_shots = exclude_own_goals(fk_shots.copy())

    if fk_shots.empty:
        return empty_fig("No free kick shot data")

    fk_shots['xg'] = fk_shots.apply(lambda r: _xg_proxy(r['x'], r['y']), axis=1)

    _style = {
        'Goal':       ('star',   GOLD,       16),
        'Saved Shot': ('circle', HOME_COLOR, 10),
        'Miss':       ('x',      AWAY_COLOR,  9),
    }

    fig = go.Figure()
    add_pitch_background(fig, half=True)

    for etype, (symbol, color, size) in _style.items():
        subset = fk_shots[fk_shots['event_type'] == etype]
        if subset.empty:
            continue
        fig.add_trace(go.Scatter(
            x=subset['x'], y=subset['y'],
            mode='markers', name=etype,
            marker=dict(color=color, size=size, symbol=symbol,
                        line=dict(color='white', width=1.2)),
            customdata=list(zip(
                subset['player_name'].fillna('') if 'player_name' in subset.columns else [''] * len(subset),
                subset['xg'],
            )),
            hovertemplate='<b>%{customdata[0]}</b><br>xG: %{customdata[1]:.2f}'
                          '<extra>' + etype + '</extra>',
        ))

    fig.update_layout(**CHART_LAYOUT_DEFAULTS, height=400, **PITCH_AXIS_HALF)
    fig.update_layout(legend=dict(orientation='h', y=-0.05, x=0.5, xanchor='center'))
    return fig


def _target_zones_map(bar):
    """
    Full-pitch scatter of set-piece shots with headers — target zone delivery map.
    """
    sp_shots = _bar_sp_shots(bar).dropna(subset=['x', 'y'])

    if sp_shots.empty:
        return empty_fig("No set-piece shot data")

    headed = sp_shots[sp_shots.get('Head', pd.Series(dtype=str)) == 'Si'] \
        if 'Head' in sp_shots.columns else sp_shots

    fig = go.Figure()
    add_pitch_background(fig, half=True)

    fig.add_trace(go.Scatter(
        x=headed['x'], y=headed['y'],
        mode='markers',
        name='SP Shot (headed)' if not headed.empty else 'SP Shot',
        marker=dict(
            color=[HOME_COLOR if e == 'Goal' else GOLD if e == 'Saved Shot' else AWAY_COLOR
                   for e in headed['event_type']],
            size=12, opacity=0.85,
            line=dict(color='white', width=1.5),
        ),
        text=headed['player_name'].fillna('') if 'player_name' in headed.columns else [''] * len(headed),
        hovertemplate='<b>%{text}</b><extra>%{marker.color}</extra>',
    ))

    for label, col in [('Goal', HOME_COLOR), ('Saved Shot', GOLD), ('Miss', AWAY_COLOR)]:
        fig.add_trace(go.Scatter(x=[None], y=[None], mode='markers',
                                 marker=dict(color=col, size=8), name=label))

    fig.update_layout(**CHART_LAYOUT_DEFAULTS, height=400, **PITCH_AXIS_HALF)
    fig.update_layout(legend=dict(orientation='h', y=-0.05, x=0.5, xanchor='center'))
    return fig


# ---------------------------------------------------------------------------
# Defending set pieces
# ---------------------------------------------------------------------------

def _xga_from_set_pieces(opp):
    """Bar: opponent shots from set pieces — xGA per shot type."""
    sp_shots = _opp_sp_shots(opp).dropna(subset=['x', 'y'])

    if sp_shots.empty:
        return empty_fig("No opponent set piece shot data")

    sp_shots['xg'] = sp_shots.apply(lambda r: _xg_proxy(100 - r['x'], r['y']), axis=1)
    n_goals  = int(sp_shots[sp_shots['event_type'] == 'Goal'].shape[0])
    total_xg = round(sp_shots['xg'].sum(), 2)

    # Group by shot type
    counts = sp_shots['event_type'].value_counts()
    xg_by  = sp_shots.groupby('event_type')['xg'].sum().round(2)

    fig = go.Figure()
    for etype, color in [('Goal', AWAY_COLOR), ('Saved Shot', GOLD), ('Miss', '#888888')]:
        if etype in counts.index:
            fig.add_trace(go.Bar(
                x=[etype],
                y=[counts[etype]],
                name=etype,
                marker_color=color,
                hovertemplate=f'{etype}: %{{y}} shots · xG {xg_by.get(etype, 0):.2f}<extra></extra>',
            ))

    fig.add_annotation(
        x=0.5, y=1.12,
        xref='paper', yref='paper',
        text=f"Total SP xGA: {total_xg} · Goals conceded: {n_goals}",
        showarrow=False,
        font=dict(color=GOLD, size=12),
    )
    fig.update_layout(
        **CHART_LAYOUT_DEFAULTS, height=280,
        barmode='group',
        yaxis_title='Shots Conceded',
        showlegend=False,
    )
    return fig


def _defensive_scheme_chart(bar, opp):
    """
    Proxy for defensive scheme: aerial duels won in penalty area (x > 83).
    High aerial win rate → zonal-heavy; low → man-marking struggling.
    """
    # BAR aerials in own penalty area (own penalty: x < 17)
    own_box = bar[bar['event_type'] == 'Aerial'].copy()
    if 'x' in own_box.columns:
        own_box = own_box[own_box['x'].notna() & (own_box['x'] < 17)]

    won  = int(own_box[own_box['outcome'] == 1].shape[0]) if not own_box.empty else 0
    lost = int(own_box[own_box['outcome'] != 1].shape[0]) if not own_box.empty else 0

    # Full pitch aerials
    all_aerials = bar[bar['event_type'] == 'Aerial']
    total_won   = int(all_aerials[all_aerials['outcome'] == 1].shape[0])
    total_lost  = int(all_aerials[all_aerials['outcome'] != 1].shape[0])

    labels  = ['Box Aerial Won', 'Box Aerial Lost', 'Total Aerial Won', 'Total Aerial Lost']
    values  = [won, lost, total_won, total_lost]
    colors  = [HOME_COLOR, AWAY_COLOR, HOME_COLOR, AWAY_COLOR]
    opacity = [1.0, 1.0, 0.45, 0.45]

    if sum(values) == 0:
        return empty_fig("No aerial data for defensive scheme")

    fig = go.Figure()
    for lbl, val, col, op in zip(labels[:2], values[:2], colors[:2], opacity[:2]):
        fig.add_trace(go.Bar(
            x=[lbl], y=[val],
            marker_color=col,
            marker_opacity=op,
            name=lbl,
            hovertemplate=f'{lbl}: {val}<extra></extra>',
        ))

    box_rate = round(won / max(won + lost, 1) * 100, 1)
    fig.add_annotation(
        x=0.5, y=1.12,
        xref='paper', yref='paper',
        text=f"Box Aerial Win Rate: {box_rate}%",
        showarrow=False,
        font=dict(color=GOLD, size=12),
    )
    fig.update_layout(
        **CHART_LAYOUT_DEFAULTS, height=260,
        barmode='group',
        yaxis_title='Aerial Duels',
        showlegend=False,
    )
    return fig


def _sp_xg_balance(bar, opp):
    """Horizontal bar: Attacking SP xG vs Defending SP xGA — balance chart."""
    atk_shots = _bar_sp_shots(bar).dropna(subset=['x', 'y'])
    def_shots = _opp_sp_shots(opp).dropna(subset=['x', 'y'])

    atk_xg = round(atk_shots.apply(lambda r: _xg_proxy(r['x'], r['y']), axis=1).sum(), 2) \
        if not atk_shots.empty else 0.0
    def_xga = round(def_shots.apply(lambda r: _xg_proxy(100 - r['x'], r['y']), axis=1).sum(), 2) \
        if not def_shots.empty else 0.0

    atk_goals = int(filter_own_goals(
        bar[bar['event_type'] == 'Goal'].copy()
    ).shape[0]) if not atk_shots.empty else 0

    def_goals = int(exclude_own_goals(
        opp[opp['event_type'] == 'Goal'].copy()
    ).shape[0]) if not def_shots.empty else 0

    fig = go.Figure()
    fig.add_trace(go.Bar(
        y=['Set Piece Attacking', 'Set Piece Defending'],
        x=[atk_xg, -def_xga],
        orientation='h',
        marker_color=[HOME_COLOR if atk_xg > def_xga else GOLD, AWAY_COLOR],
        hovertemplate='%{y}: xG %{x:.2f}<extra></extra>',
    ))

    fig.add_vline(x=0, line=dict(color='rgba(255,255,255,0.4)', width=1))
    fig.add_annotation(
        x=atk_xg / 2, y='Set Piece Attacking',
        text=f"xG {atk_xg}",
        showarrow=False,
        font=dict(color='white', size=11),
    )
    fig.add_annotation(
        x=-def_xga / 2, y='Set Piece Defending',
        text=f"xGA {def_xga}",
        showarrow=False,
        font=dict(color='white', size=11),
    )

    fig.update_layout(
        **CHART_LAYOUT_DEFAULTS, height=200,
        xaxis=dict(title='← Conceded   |   Created →', zeroline=True,
                   zerolinecolor='rgba(255,255,255,0.3)'),
    )
    fig.update_layout(margin=dict(l=10, r=10, t=20, b=30), showlegend=False)
    return fig


# ---------------------------------------------------------------------------
# Throw-ins
# ---------------------------------------------------------------------------

def _throw_in_retention(bar):
    """Bar: throw-in possession outcome — retained vs lost."""
    throws = bar[bar['event_type'].isin(_THROW_TYPES)]
    if throws.empty:
        # Fallback: look for qualifiers
        if 'Throw in' in bar.columns:
            throws = bar[bar['Throw in'] == 'Si']
        elif 'Throw-in' in bar.columns:
            throws = bar[bar['Throw-in'] == 'Si']

    if throws.empty:
        return empty_fig("No throw-in data available")

    retained = int(throws[throws['outcome'] == 1].shape[0])
    lost     = int(throws[throws['outcome'] != 1].shape[0])
    total    = retained + lost
    pct      = round(retained / max(total, 1) * 100, 1)

    fig = go.Figure(go.Pie(
        labels=['Retained', 'Lost'],
        values=[retained, lost],
        marker_colors=[HOME_COLOR, AWAY_COLOR],
        hole=0.45,
        textinfo='label+percent',
        textfont=dict(color='white', size=12),
    ))
    fig.add_annotation(
        x=0.5, y=0.5,
        text=f"{pct}%\nretained",
        font=dict(color=GOLD, size=13, family='Arial Black'),
        showarrow=False,
    )
    fig.update_layout(**CHART_LAYOUT_DEFAULTS, height=260, showlegend=False)
    fig.update_layout(margin=dict(l=0, r=0, t=20, b=0))
    fig.update_layout(title_text='Throw-In Retention', title_font_color=GOLD, title_font_size=12)
    return fig


def _throw_in_zones(bar):
    """Scatter of throw-in locations on full pitch."""
    throws = bar[bar['event_type'].isin(_THROW_TYPES)].dropna(subset=['x', 'y'])
    if throws.empty:
        return empty_fig("No throw-in location data")

    # Classify as dangerous (opponent half) vs safe
    dangerous = throws[throws['x'] >= 50]
    safe      = throws[throws['x'] < 50]

    fig = go.Figure()
    add_pitch_background(fig, half=False)

    fig.add_trace(go.Scatter(
        x=safe['x'], y=safe['y'],
        mode='markers', name='Own Half',
        marker=dict(color=GOLD, size=7, opacity=0.7,
                    line=dict(color='white', width=0.5)),
        hovertemplate='(%{x:.0f}, %{y:.0f})<extra>Own Half Throw</extra>',
    ))
    fig.add_trace(go.Scatter(
        x=dangerous['x'], y=dangerous['y'],
        mode='markers', name='Opp Half (dangerous)',
        marker=dict(color=AWAY_COLOR, size=9, opacity=0.85,
                    line=dict(color='white', width=0.8)),
        hovertemplate='(%{x:.0f}, %{y:.0f})<extra>Dangerous Throw</extra>',
    ))

    fig.update_layout(**CHART_LAYOUT_DEFAULTS, height=360, **PITCH_AXIS_FULL)
    fig.update_layout(legend=dict(orientation='h', y=-0.05, x=0.5, xanchor='center'))
    return fig


# ---------------------------------------------------------------------------
# Public builder
# ---------------------------------------------------------------------------

def build_set_pieces_tab(season, competitions, match_ids=None):
    """Build the Set Pieces tab content."""
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
    atk_sp_shots = _bar_sp_shots(bar)
    def_sp_shots = _opp_sp_shots(opp)

    corners_bar = pd.concat([
        bar[bar['event_type'].isin(_CORNER_TYPES)],
        bar[(bar['event_type'] == 'Pass') &
            bar.get('Corner taken', pd.Series(dtype=str)).eq('Si')]
        if 'Corner taken' in bar.columns else bar.head(0),
    ]).drop_duplicates()

    fk_bar = bar[bar['event_type'].isin(_FK_TYPES)]
    if fk_bar.empty and 'Free kick' in bar.columns:
        fk_bar = bar[bar['Free kick'] == 'Si']

    throws_bar   = bar[bar['event_type'].isin(_THROW_TYPES)]
    throw_ret    = int(throws_bar[throws_bar['outcome'] == 1].shape[0]) if not throws_bar.empty else 0
    throw_total  = len(throws_bar)

    atk_xg = round(
        atk_sp_shots.dropna(subset=['x', 'y']).apply(
            lambda r: _xg_proxy(r['x'], r['y']), axis=1).sum(), 1
    ) if not atk_sp_shots.empty else 0.0

    def_xga = round(
        def_sp_shots.dropna(subset=['x', 'y']).apply(
            lambda r: _xg_proxy(100 - r['x'], r['y']), axis=1).sum(), 1
    ) if not def_sp_shots.empty else 0.0

    atk_goals = int(filter_own_goals(atk_sp_shots[atk_sp_shots['event_type'] == 'Goal'].copy()).shape[0]) \
        if not atk_sp_shots.empty else 0
    def_goals = int(exclude_own_goals(def_sp_shots[def_sp_shots['event_type'] == 'Goal'].copy()).shape[0]) \
        if not def_sp_shots.empty else 0

    kpi = kpi_row(
        {
            'corners':       len(corners_bar),
            'fk':            len(fk_bar),
            'throws':        throw_total,
            'throw_ret':     f"{round(throw_ret / max(throw_total, 1) * 100, 1)}%",
            'atk_shots':     len(atk_sp_shots),
            'atk_xg':        atk_xg,
            'atk_goals':     atk_goals,
            'def_shots':     len(def_sp_shots),
            'def_xga':       def_xga,
            'def_goals_con': def_goals,
        },
        [
            ('corners',       'Corners Won'),
            ('fk',            'Free Kicks'),
            ('throws',        'Throw-ins'),
            ('throw_ret',     'Throw Retention'),
            ('atk_shots',     'SP Shots (Atk)'),
            ('atk_xg',        'SP xG (Atk)'),
            ('atk_goals',     'SP Goals'),
            ('def_shots',     'SP Shots (Def)'),
            ('def_xga',       'SP xGA'),
            ('def_goals_con', 'SP Goals Conceded'),
        ],
        colors={
            'atk_goals': GOLD,
            'atk_xg':    HOME_COLOR,
            'def_xga':   AWAY_COLOR,
            'def_goals_con': AWAY_COLOR,
        },
    )

    # ── Attacking set pieces ──────────────────────────────────────────────────
    corner_card = section_card(
        "Corner Delivery — Inswing / Outswing / Short",
        dcc.Graph(figure=_corner_delivery_donut(bar), config=CHART_CONFIG),
    )
    fk_card = section_card(
        "Free Kick Shots  ★ Goal  ● Saved  ✕ Miss",
        dcc.Graph(figure=_free_kick_shot_map(bar), config=CHART_CONFIG),
    )
    target_card = section_card(
        "Target Zones — Set Piece Delivery Landing Areas",
        dcc.Graph(figure=_target_zones_map(bar), config=CHART_CONFIG),
    )

    # ── Defending set pieces ──────────────────────────────────────────────────
    def_sp_card = section_card(
        "xGA from Set Pieces — Opponent Corners & Free Kicks Conceded",
        dcc.Graph(figure=_xga_from_set_pieces(opp), config=CHART_CONFIG),
    )
    scheme_card = section_card(
        "Defensive Scheme Proxy — Aerial Duel Win Rate in Own Box",
        dcc.Graph(figure=_defensive_scheme_chart(bar, opp), config=CHART_CONFIG),
    )
    balance_card = section_card(
        "Set Piece Balance — Attacking xG vs Defending xGA",
        dcc.Graph(figure=_sp_xg_balance(bar, opp), config=CHART_CONFIG),
    )

    # ── Throw-ins ─────────────────────────────────────────────────────────────
    throw_ret_card = section_card(
        "Throw-In Retention — Possession Kept %",
        dcc.Graph(figure=_throw_in_retention(bar), config=CHART_CONFIG),
    )
    throw_zone_card = section_card(
        "Throw-In Zones — Dangerous Long Throw Locations",
        dcc.Graph(figure=_throw_in_zones(bar), config=CHART_CONFIG),
    )

    return html.Div([
        kpi,
        html.P("Attacking set pieces", style={
            'color': COLORS['text_secondary'], 'fontSize': '0.78rem',
            'fontStyle': 'italic', 'marginTop': '8px', 'marginBottom': '4px',
        }),
        dbc.Row([
            dbc.Col(corner_card, md=4),
            dbc.Col(fk_card,     md=4),
            dbc.Col(target_card, md=4),
        ], className='mb-3'),
        html.P("Defending set pieces", style={
            'color': COLORS['text_secondary'], 'fontSize': '0.78rem',
            'fontStyle': 'italic', 'marginBottom': '4px',
        }),
        dbc.Row([
            dbc.Col(def_sp_card, md=4),
            dbc.Col(scheme_card, md=4),
            dbc.Col(balance_card, md=4),
        ], className='mb-3'),
        html.P("Throw-ins", style={
            'color': COLORS['text_secondary'], 'fontSize': '0.78rem',
            'fontStyle': 'italic', 'marginBottom': '4px',
        }),
        dbc.Row([
            dbc.Col(throw_ret_card,  md=4),
            dbc.Col(throw_zone_card, md=8),
        ], className='mb-3'),
    ])
