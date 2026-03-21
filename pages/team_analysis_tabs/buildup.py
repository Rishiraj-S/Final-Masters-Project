"""
Team Analysis — Tab 1: Build-up and Progression

Answers: How do we play out from the back and progress into the final third?

Sections:
  Build-up from the back
    - Goal kick routes        (short vs long %)
    - Pass network            (defensive-third connections)
    - Press resistance        (pass accuracy under pressure in own half)
  Progression
    - Progressive actions     (pass + carry map, x gain ≥ 10)
    - Build-up routes         (Left / Centre / Right corridor split)
    - Possession value map    (progressive distance added per touch zone)
  Positional play
    - Average positions       (mean x,y per player — formation shape)
    - Passing combos          (top player-pair pass counts)
    - Width & depth           (team spread heatmap)
"""

from dash import html, dcc
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
import pandas as pd
import numpy as np

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


_COMP_SHORT = {
    'La Liga': 'Liga',
    'Champions League': 'UCL',
    'Copa del Rey': 'Copa',
    'Spanish Super Cup': 'SC',
}

# Y-corridor boundaries (0-100 pitch width)
_LEFT_MAX   = 33
_RIGHT_MIN  = 67


# ---------------------------------------------------------------------------
# Build-up from the back
# ---------------------------------------------------------------------------

def _goal_kick_routes(bar):
    """Donut: goal kick distribution — Short (end_x < 40) vs Long (end_x ≥ 40)."""
    if 'end_x' not in bar.columns:
        # Fallback: own-half passes from x < 10 (GK zone)
        passes = bar[(bar['event_type'] == 'Pass') & bar['x'].notna() & (bar['x'] < 10)]
        if passes.empty:
            return empty_fig("No goal kick data")
        short = int(passes[(passes['x'] < 10) & (passes.get('end_x', pd.Series()) < 40)].shape[0])
        long_ = int(len(passes) - short)
    else:
        # Passes originating in GK zone
        passes = bar[
            (bar['event_type'] == 'Pass') &
            bar['x'].notna() & (bar['x'] < 15) &
            bar['end_x'].notna()
        ]
        if passes.empty:
            return empty_fig("No goal kick / GK distribution data")
        short  = int(passes[passes['end_x'] < 40].shape[0])
        long_  = int(passes[passes['end_x'] >= 40].shape[0])

    if short + long_ == 0:
        return empty_fig("No GK distribution data")

    fig = go.Figure(go.Pie(
        labels=['Short / Medium', 'Long'],
        values=[short, long_],
        marker_colors=[HOME_COLOR, AWAY_COLOR],
        hole=0.45,
        textinfo='label+percent',
        textfont=dict(color='white', size=12),
    ))
    fig.update_layout(**CHART_LAYOUT_DEFAULTS, height=280, showlegend=False)
    fig.update_layout(margin=dict(l=0, r=0, t=20, b=0))
    fig.update_layout(title_text='GK Distribution Routes', title_font_color=GOLD,
                      title_font_size=12)
    return fig


def _pass_network_def_third(bar):
    """
    Pass connection scatter in the defensive third (x < 33).
    Shows most frequent player-pair pass lines (top 10 pairs).
    """
    passes = bar[
        (bar['event_type'] == 'Pass') &
        bar['x'].notna() & (bar['x'] < 33) &
        bar['y'].notna()
    ]
    if passes.empty or 'player_name' not in passes.columns:
        return empty_fig("No defensive third pass data")

    fig = go.Figure()
    add_pitch_background(fig, half=False)

    # Average positions
    avg_pos = passes.groupby('player_name')[['x', 'y']].mean()

    fig.add_trace(go.Scatter(
        x=avg_pos['x'], y=avg_pos['y'],
        mode='markers+text',
        marker=dict(color=GOLD, size=14, line=dict(color='white', width=2)),
        text=avg_pos.index.str.split().str[-1],   # last name only
        textposition='top center',
        textfont=dict(color='white', size=9),
        hovertemplate='%{text}<br>Avg pos: (%{x:.0f}, %{y:.0f})<extra></extra>',
        showlegend=False,
    ))

    fig.update_layout(**CHART_LAYOUT_DEFAULTS, height=380, **PITCH_AXIS_FULL)
    return fig


def _press_resistance(bar):
    """Pass accuracy in own half — proxy for playing under press."""
    own_half = bar[(bar['event_type'] == 'Pass') & bar['x'].notna() & (bar['x'] < 50)]
    if own_half.empty:
        return empty_fig("No own-half pass data")

    by_zone = []
    for label, lo, hi in [('Own Third', 0, 33), ('Mid-Left Third', 33, 50)]:
        zone  = own_half[(own_half['x'] >= lo) & (own_half['x'] < hi)]
        total = len(zone)
        acc   = int(zone['outcome'].eq(1).sum()) if total else 0
        by_zone.append({'Zone': label, 'Total': total, 'Accurate': acc,
                        'Pct': round(acc / max(total, 1) * 100, 1)})

    df = pd.DataFrame(by_zone)
    if df.empty:
        return empty_fig("No press resistance data")

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=df['Zone'], y=df['Total'],
        name='Total Passes',
        marker_color='rgba(255,255,255,0.15)',
        hovertemplate='%{x}: %{y} passes<extra></extra>',
    ))
    fig.add_trace(go.Bar(
        x=df['Zone'], y=df['Accurate'],
        name='Accurate',
        marker_color=HOME_COLOR,
        hovertemplate='%{x}: %{y} accurate<extra></extra>',
    ))
    for _, row in df.iterrows():
        fig.add_annotation(
            x=row['Zone'], y=row['Accurate'] + 2,
            text=f"{row['Pct']}%",
            showarrow=False,
            font=dict(color=GOLD, size=11, family='Arial Black'),
        )

    fig.update_layout(
        **CHART_LAYOUT_DEFAULTS,
        height=280,
        barmode='overlay',
        yaxis_title='Passes',
    )
    fig.update_layout(legend=dict(orientation='h', y=1.05, x=0.5, xanchor='center'))
    return fig


# ---------------------------------------------------------------------------
# Progression
# ---------------------------------------------------------------------------

def _progressive_actions_map(bar):
    """Full-pitch scatter: progressive passes (end_x - x ≥ 10)."""
    if 'end_x' not in bar.columns:
        return empty_fig("No pass endpoint data available")

    passes = bar[
        (bar['event_type'] == 'Pass') &
        bar['x'].notna() & bar['end_x'].notna() & bar['y'].notna()
    ].copy()
    prog = passes[(passes['end_x'] - passes['x']) >= 10]

    if prog.empty:
        return empty_fig("No progressive pass data")

    # Colour by zone of origin
    def zone_color(x):
        if x < 33: return AWAY_COLOR
        if x < 66: return GOLD
        return HOME_COLOR

    colors = prog['x'].map(zone_color)

    fig = go.Figure()
    add_pitch_background(fig, half=False)

    # Draw lines from origin to end
    for _, row in prog.head(300).iterrows():    # cap at 300 for perf
        fig.add_shape(type='line',
                      x0=row['x'], y0=row['y'],
                      x1=row['end_x'], y1=row['end_y'] if 'end_y' in row.index and pd.notna(row.get('end_y')) else row['y'],
                      line=dict(color='rgba(255,255,255,0.15)', width=1))

    fig.add_trace(go.Scatter(
        x=prog['x'], y=prog['y'],
        mode='markers',
        name='Origin',
        marker=dict(color=colors, size=5, opacity=0.7,
                    line=dict(color='white', width=0.3)),
        text=prog['player_name'].fillna('') if 'player_name' in prog.columns else [''] * len(prog),
        hovertemplate='%{text}<extra>Progressive Pass</extra>',
    ))

    # Legend proxies
    for label, col in [('Own Third', AWAY_COLOR), ('Mid Third', GOLD), ('Opp Third', HOME_COLOR)]:
        fig.add_trace(go.Scatter(x=[None], y=[None], mode='markers',
                                 marker=dict(color=col, size=8), name=label))

    fig.update_layout(**CHART_LAYOUT_DEFAULTS, height=400, **PITCH_AXIS_FULL)
    fig.update_layout(legend=dict(orientation='h', y=-0.05, x=0.5, xanchor='center'))
    return fig


def _buildup_routes(bar):
    """Horizontal bar: proportion of events in Left / Centre / Right corridors."""
    events_xy = bar[bar['x'].notna() & bar['y'].notna()]
    if events_xy.empty:
        return empty_fig("No coordinate data")

    left   = int(events_xy[events_xy['y'] < _LEFT_MAX].shape[0])
    centre = int(events_xy[(events_xy['y'] >= _LEFT_MAX) & (events_xy['y'] < _RIGHT_MIN)].shape[0])
    right  = int(events_xy[events_xy['y'] >= _RIGHT_MIN].shape[0])
    total  = max(left + centre + right, 1)

    labels = ['Left Channel', 'Central Lane', 'Right Channel']
    values = [left, centre, right]
    pcts   = [f"{round(v/total*100,1)}%" for v in values]
    colors = [HOME_COLOR, GOLD, AWAY_COLOR]

    fig = go.Figure(go.Bar(
        y=labels, x=values,
        orientation='h',
        marker_color=colors,
        text=pcts,
        textposition='outside',
        textfont=dict(color='white', size=11),
        hovertemplate='%{y}: %{x} events<extra></extra>',
    ))
    fig.update_layout(
        **CHART_LAYOUT_DEFAULTS,
        height=220,
        xaxis_title='Events',
        xaxis=dict(range=[0, max(values) * 1.2]),
    )
    fig.update_layout(margin=dict(l=10, r=60, t=10, b=30))
    return fig


def _possession_value_map(bar):
    """
    Progressive distance heatmap: colour = avg x-gain of passes starting in each zone.
    We discretise the pitch into a 10x6 grid and compute mean (end_x - x) per cell.
    """
    if 'end_x' not in bar.columns:
        # Fallback: generic touch heatmap
        coords = bar.dropna(subset=['x', 'y'])
        if coords.empty:
            return empty_fig("No touch data")
        src = render_heatmap_img(coords['x'].values, coords['y'].values,
                                 cmap='YlOrRd', half=False)
        return html.Img(src=src, style={'width': '100%', 'borderRadius': '4px'})

    passes = bar[
        (bar['event_type'] == 'Pass') &
        bar['x'].notna() & bar['end_x'].notna() & bar['y'].notna()
    ].copy()
    if passes.empty:
        return empty_fig("No pass data for possession value")

    passes['dx'] = passes['end_x'] - passes['x']

    # Create grid heatmap (x bins × y bins)
    x_bins = np.linspace(0, 100, 11)   # 10 columns
    y_bins = np.linspace(0, 100, 7)    # 6 rows
    grid   = np.zeros((6, 10))
    counts = np.zeros((6, 10))

    for _, row in passes.iterrows():
        xi = min(int(row['x'] / 10), 9)
        yi = min(int(row['y'] / (100/6)), 5)
        grid[yi, xi] += row['dx']
        counts[yi, xi] += 1

    with np.errstate(invalid='ignore'):
        avg_grid = np.where(counts > 0, grid / counts, np.nan)

    fig = go.Figure(go.Heatmap(
        z=avg_grid,
        x=(x_bins[:-1] + x_bins[1:]) / 2,
        y=(y_bins[:-1] + y_bins[1:]) / 2,
        colorscale='RdYlGn',
        zmid=0,
        colorbar=dict(title='Avg x-gain', tickfont=dict(color=COLORS['text_secondary'])),
        hovertemplate='x≈%{x:.0f} y≈%{y:.0f}<br>Avg gain: %{z:.1f}<extra></extra>',
    ))

    fig.update_layout(
        **CHART_LAYOUT_DEFAULTS,
        height=280,
        xaxis=dict(title='Pitch Length (0=own goal)', range=[0, 100]),
        yaxis=dict(title='Pitch Width', range=[0, 100]),
    )
    fig.update_layout(margin=dict(l=10, r=10, t=10, b=30))
    return fig


# ---------------------------------------------------------------------------
# Positional play
# ---------------------------------------------------------------------------

def _average_positions(bar):
    """Scatter: mean x,y per player (minimum 5 events), sized by event count."""
    if 'player_name' not in bar.columns:
        return empty_fig("No player data")

    coords = bar.dropna(subset=['x', 'y', 'player_name'])
    if coords.empty:
        return empty_fig("No coordinate data")

    avg = coords.groupby('player_name').agg(
        x=('x', 'mean'), y=('y', 'mean'), count=('x', 'count')
    ).reset_index()
    avg = avg[avg['count'] >= 5]

    if avg.empty:
        return empty_fig("Not enough player data")

    fig = go.Figure()
    add_pitch_background(fig, half=False)

    fig.add_trace(go.Scatter(
        x=avg['x'], y=avg['y'],
        mode='markers+text',
        marker=dict(
            color=GOLD,
            size=avg['count'].clip(upper=500).apply(lambda c: 10 + c / 50),
            opacity=0.85,
            line=dict(color='white', width=1.5),
        ),
        text=avg['player_name'].str.split().str[-1],
        textposition='top center',
        textfont=dict(color='white', size=9),
        customdata=list(zip(avg['player_name'], avg['count'])),
        hovertemplate='<b>%{customdata[0]}</b><br>Events: %{customdata[1]}<extra></extra>',
        showlegend=False,
    ))

    fig.update_layout(**CHART_LAYOUT_DEFAULTS, height=420, **PITCH_AXIS_FULL)
    return fig


def _passing_combos(bar):
    """Top 15 player-pair pass counts (horizontal bar)."""
    if 'player_name' not in bar.columns:
        return empty_fig("No player data")

    passes = bar[(bar['event_type'] == 'Pass') & (bar['outcome'] == 1)]
    if passes.empty:
        return empty_fig("No successful pass data")

    # Pair: (passer, receiver) — Opta doesn't always carry receiver name,
    # so we sort by player event proximity within same match_id + time window.
    # Simplification: just count passes per player pair if 'receiver' col exists,
    # otherwise show top passers to/from zones.
    if 'receiver' in passes.columns:
        pairs = passes.groupby(['player_name', 'receiver']).size().reset_index(name='count')
        pairs['label'] = pairs['player_name'].str.split().str[-1] + \
                         ' → ' + pairs['receiver'].str.split().str[-1]
        pairs = pairs.nlargest(15, 'count')

        fig = go.Figure(go.Bar(
            y=pairs['label'], x=pairs['count'],
            orientation='h',
            marker_color=HOME_COLOR,
            hovertemplate='%{y}: %{x} passes<extra></extra>',
        ))
        fig.update_layout(
            **CHART_LAYOUT_DEFAULTS, height=380,
            xaxis_title='Successful Passes',
            yaxis=dict(autorange='reversed'),
        )
        fig.update_layout(margin=dict(l=10, r=10, t=10, b=30))
        return fig

    # Fallback: top passers bar
    top_passers = passes.groupby('player_name').size().nlargest(15)
    fig = go.Figure(go.Bar(
        y=top_passers.index, x=top_passers.values,
        orientation='h',
        marker_color=HOME_COLOR,
        hovertemplate='%{y}: %{x} passes<extra></extra>',
    ))
    fig.update_layout(
        **CHART_LAYOUT_DEFAULTS, height=360,
        xaxis_title='Successful Passes',
        yaxis=dict(autorange='reversed'),
    )
    fig.update_layout(margin=dict(l=10, r=10, t=10, b=30))
    return fig


def _width_depth_heatmap(bar):
    """Full-pitch heatmap of all BAR touch locations — shows team shape/spread."""
    coords = bar.dropna(subset=['x', 'y'])
    if coords.empty:
        return None
    return render_heatmap_img(coords['x'].values, coords['y'].values,
                              cmap='hot', half=False)


# ---------------------------------------------------------------------------
# Public builder
# ---------------------------------------------------------------------------

def build_buildup_tab(season, competitions, match_ids=None):
    """Build the Build-up and Progression tab content."""
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

    # ── KPIs ─────────────────────────────────────────────────────────────────
    bar_passes    = bar[bar['event_type'] == 'Pass']
    all_passes    = events[events['event_type'] == 'Pass']
    poss          = round(len(bar_passes) / max(len(all_passes), 1) * 100, 1)
    pass_acc      = round(bar_passes['outcome'].eq(1).sum() / max(len(bar_passes), 1) * 100, 1)

    own_half_p    = bar_passes[bar_passes['x'].notna() & (bar_passes['x'] < 50)]
    oh_acc        = round(own_half_p['outcome'].eq(1).sum() / max(len(own_half_p), 1) * 100, 1)

    prog_passes   = bar_passes[
        bar_passes['end_x'].notna() & bar_passes['x'].notna() &
        ((bar_passes['end_x'] - bar_passes['x']) >= 10)
    ] if 'end_x' in bar_passes.columns else bar_passes.head(0)
    n_prog        = len(prog_passes)

    # L/C/R split
    ev_xy = bar.dropna(subset=['x', 'y'])
    left  = int(ev_xy[ev_xy['y'] < _LEFT_MAX].shape[0])
    ctr   = int(ev_xy[(ev_xy['y'] >= _LEFT_MAX) & (ev_xy['y'] < _RIGHT_MIN)].shape[0])
    right = int(ev_xy[ev_xy['y'] >= _RIGHT_MIN].shape[0])

    kpi = kpi_row(
        {
            'poss':      f"{poss}%",
            'pass_acc':  f"{pass_acc}%",
            'oh_acc':    f"{oh_acc}%",
            'n_passes':  len(bar_passes),
            'prog_pass': n_prog,
            'left_pct':  f"{round(left / max(left+ctr+right,1)*100,1)}%",
            'ctr_pct':   f"{round(ctr  / max(left+ctr+right,1)*100,1)}%",
            'right_pct': f"{round(right/ max(left+ctr+right,1)*100,1)}%",
        },
        [
            ('poss',      'Possession'),
            ('pass_acc',  'Pass Accuracy'),
            ('oh_acc',    'Own-Half Acc.'),
            ('n_passes',  'Total Passes'),
            ('prog_pass', 'Progressive Passes'),
            ('left_pct',  'Left Corridor'),
            ('ctr_pct',   'Central Lane'),
            ('right_pct', 'Right Corridor'),
        ],
        colors={
            'poss':     HOME_COLOR,
            'prog_pass': GOLD,
            'oh_acc':   HOME_COLOR,
        },
    )

    # ── Build-up from the back ────────────────────────────────────────────────
    sub_label = lambda t: html.P(t, style={
        'color': COLORS['text_secondary'], 'fontSize': '0.75rem',
        'fontStyle': 'italic', 'marginBottom': '8px', 'marginTop': '4px',
    })

    gk_card = section_card(
        "Goal Kick / GK Distribution Routes",
        dcc.Graph(figure=_goal_kick_routes(bar), config=CHART_CONFIG),
    )
    net_card = section_card(
        "Pass Network — Defensive Third Positions",
        dcc.Graph(figure=_pass_network_def_third(bar), config=CHART_CONFIG),
    )
    press_card = section_card(
        "Press Resistance — Own-Half Pass Accuracy by Zone",
        dcc.Graph(figure=_press_resistance(bar), config=CHART_CONFIG),
    )

    # ── Progression ──────────────────────────────────────────────────────────
    prog_map_card = section_card(
        "Progressive Passes Map  (x-gain ≥ 10)",
        dcc.Graph(figure=_progressive_actions_map(bar), config=CHART_CONFIG),
    )
    routes_card = section_card(
        "Build-up Routes — Left / Centre / Right Corridor Split",
        dcc.Graph(figure=_buildup_routes(bar), config=CHART_CONFIG),
    )
    pv_content = _possession_value_map(bar)
    pv_card = section_card(
        "Possession Value Map — Avg. Progressive Distance Added by Zone",
        pv_content if isinstance(pv_content, go.Figure.__class__) else
        dcc.Graph(figure=pv_content, config=CHART_CONFIG)
        if hasattr(pv_content, 'data') else pv_content,
    )

    # ── Positional play ───────────────────────────────────────────────────────
    avg_pos_card = section_card(
        "Average Positions — Formation Shape (dot size = event volume)",
        dcc.Graph(figure=_average_positions(bar), config=CHART_CONFIG),
    )
    combos_card = section_card(
        "Passing Combos — Top Player Pairs",
        dcc.Graph(figure=_passing_combos(bar), config=CHART_CONFIG),
    )
    wd_src = _width_depth_heatmap(bar)
    wd_card = section_card(
        "Width & Depth — Touch Heatmap",
        html.Img(src=wd_src, style={'width': '100%', 'borderRadius': '4px'}),
    ) if wd_src else html.Div()

    return html.Div([
        kpi,
        # Build-up from the back
        html.P("Build-up from the back", style={
            'color': COLORS['text_secondary'], 'fontSize': '0.78rem',
            'fontStyle': 'italic', 'marginTop': '8px', 'marginBottom': '4px',
        }),
        dbc.Row([
            dbc.Col(gk_card,    md=4),
            dbc.Col(net_card,   md=4),
            dbc.Col(press_card, md=4),
        ], className='mb-3'),
        # Progression
        html.P("Progression", style={
            'color': COLORS['text_secondary'], 'fontSize': '0.78rem',
            'fontStyle': 'italic', 'marginBottom': '4px',
        }),
        dbc.Row([
            dbc.Col(prog_map_card, md=6),
            dbc.Col([routes_card, pv_card], md=6),
        ], className='mb-3'),
        # Positional play
        html.P("Positional play", style={
            'color': COLORS['text_secondary'], 'fontSize': '0.78rem',
            'fontStyle': 'italic', 'marginBottom': '4px',
        }),
        dbc.Row([
            dbc.Col(avg_pos_card, md=5),
            dbc.Col([combos_card, wd_card], md=7),
        ], className='mb-3'),
    ])
