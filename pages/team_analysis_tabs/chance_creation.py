"""
Team Analysis — Tab 2: Chance Creation and Finishing

Answers: How do we create and convert chances?

Sections:
  Creation
    - Key passes map          (origin + end zones of key passes)
    - Box entries             (pass vs carry vs cross into penalty area)
    - Crossing patterns       (zones + success rate)
  Finishing
    - Shot map                (xG proxy by location, sized by danger)
    - Shot types              (open play vs set piece donut)
    - Pre-shot sequences      (last event type before each shot)
  Performance
    - xG timeline             (cumulative goals per match)
    - Goals vs xG             (over / under performance bar)
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
    filter_own_goals,
    exclude_own_goals,
    CURRENT_SEASON,
)
from utils.xg_utils import add_xg_column
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

_SHOT_STYLE = {
    'Goal':       ('star',   GOLD,       18),
    'Saved Shot': ('circle', HOME_COLOR, 11),
    'Miss':       ('x',      AWAY_COLOR, 10),
}


# ---------------------------------------------------------------------------
# Creation
# ---------------------------------------------------------------------------

def _key_passes_map(bar):
    """Full-pitch scatter: origin of key passes (Assist qualifier), coloured by outcome."""
    if 'Assist' not in bar.columns:
        return empty_fig("No key pass qualifier (Assist) in data")

    kp = bar[
        (bar['event_type'] == 'Pass') &
        (bar['Assist'] == 'Si')
    ].dropna(subset=['x', 'y'])

    if kp.empty:
        return empty_fig("No key passes found")

    # Colour by outcome: accurate (1) vs inaccurate (0)
    colors = kp['outcome'].map(lambda o: HOME_COLOR if o == 1 else AWAY_COLOR)

    fig = go.Figure()
    add_pitch_background(fig, half=False)

    # Draw arrow lines if end_x/end_y available
    if 'end_x' in kp.columns and 'end_y' in kp.columns:
        for _, row in kp.head(200).iterrows():
            if pd.notna(row.get('end_x')) and pd.notna(row.get('end_y')):
                fig.add_annotation(
                    x=row['end_x'], y=row['end_y'],
                    ax=row['x'], ay=row['y'],
                    axref='x', ayref='y',
                    arrowhead=2, arrowwidth=1.5,
                    arrowcolor='rgba(255,255,255,0.25)',
                    showarrow=True,
                )

    fig.add_trace(go.Scatter(
        x=kp['x'], y=kp['y'],
        mode='markers',
        name='Key Pass Origin',
        marker=dict(color=colors, size=8, opacity=0.85,
                    line=dict(color='white', width=1)),
        text=kp['player_name'].fillna('') if 'player_name' in kp.columns else [''] * len(kp),
        hovertemplate='<b>%{text}</b><extra>Key Pass</extra>',
    ))

    for label, col in [('Accurate', HOME_COLOR), ('Inaccurate', AWAY_COLOR)]:
        fig.add_trace(go.Scatter(x=[None], y=[None], mode='markers',
                                 marker=dict(color=col, size=8), name=label))

    fig.update_layout(**CHART_LAYOUT_DEFAULTS, height=400, **PITCH_AXIS_FULL)
    fig.update_layout(legend=dict(orientation='h', y=-0.05, x=0.5, xanchor='center'))
    return fig


def _box_entries(bar):
    """Grouped bar: how does Barca enter the penalty area (pass / carry / cross)?"""
    # Box = x ≥ 83, y between 21.1 and 78.9
    box = bar[bar['x'].notna() & (bar['x'] >= 83) & bar['y'].notna() &
              (bar['y'] >= 21) & (bar['y'] <= 79)]

    if box.empty:
        return empty_fig("No penalty-area entries")

    crosses = int(box[box['event_type'].isin(['Cross', 'Crossed Ball'])].shape[0])
    carries = int(box[box['event_type'] == 'Take On'].shape[0])   # dribble into box
    passes_ = int(box[box['event_type'] == 'Pass'].shape[0])
    other   = int(box.shape[0] - crosses - carries - passes_)

    labels = ['Pass', 'Cross/Crossed Ball', 'Take On / Carry', 'Other']
    values = [passes_, crosses, carries, other]
    colors = [HOME_COLOR, GOLD, AWAY_COLOR, '#888888']

    fig = go.Figure(go.Pie(
        labels=labels, values=values,
        marker_colors=colors,
        hole=0.45,
        textinfo='label+percent',
        textfont=dict(color='white', size=11),
        hovertemplate='%{label}: %{value} entries<extra></extra>',
    ))
    fig.update_layout(**CHART_LAYOUT_DEFAULTS, height=280, showlegend=False)
    fig.update_layout(margin=dict(l=0, r=0, t=20, b=0))
    fig.update_layout(title_text='Box Entry Types', title_font_color=GOLD,
                      title_font_size=12)
    return fig


def _crossing_patterns(bar):
    """Bar: cross attempts by zone (left flank / right flank) + accuracy rate."""
    cross_types = ['Cross', 'Crossed Ball']
    crosses = bar[bar['event_type'].isin(cross_types) & bar['y'].notna()]

    if crosses.empty:
        return empty_fig("No cross data")

    left_crosses  = crosses[crosses['y'] < 33]
    right_crosses = crosses[crosses['y'] > 67]

    def _acc(df):
        if df.empty:
            return 0.0, 0
        return round(df['outcome'].eq(1).sum() / max(len(df), 1) * 100, 1), len(df)

    la, ln = _acc(left_crosses)
    ra, rn = _acc(right_crosses)

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=['Left Flank', 'Right Flank'],
        y=[ln, rn],
        name='Total Crosses',
        marker_color='rgba(255,255,255,0.15)',
    ))
    fig.add_trace(go.Bar(
        x=['Left Flank', 'Right Flank'],
        y=[int(left_crosses['outcome'].eq(1).sum()), int(right_crosses['outcome'].eq(1).sum())],
        name='Accurate',
        marker_color=HOME_COLOR,
    ))

    for x_pos, acc in [('Left Flank', la), ('Right Flank', ra)]:
        fig.add_annotation(
            x=x_pos, y=max(ln, rn) + 2,
            text=f"{acc}% acc.",
            showarrow=False,
            font=dict(color=GOLD, size=11, family='Arial Black'),
        )

    fig.update_layout(
        **CHART_LAYOUT_DEFAULTS,
        height=280,
        barmode='overlay',
        yaxis_title='Crosses',
    )
    fig.update_layout(legend=dict(orientation='h', y=1.05, x=0.5, xanchor='center'))
    return fig


# ---------------------------------------------------------------------------
# Finishing
# ---------------------------------------------------------------------------

def _shot_map_xg(bar):
    """Half-pitch shot map with xG (bubble size = xG)."""
    shot_types = ['Goal', 'Saved Shot', 'Miss']
    shots = exclude_own_goals(
        bar[bar['event_type'].isin(shot_types)].copy()
    ).dropna(subset=['x', 'y'])

    if shots.empty:
        return empty_fig("No shot data")

    shots = add_xg_column(shots)

    fig = go.Figure()
    add_pitch_background(fig, half=True)

    for etype, (symbol, color, base_size) in _SHOT_STYLE.items():
        subset = shots[shots['event_type'] == etype]
        if subset.empty:
            continue
        fig.add_trace(go.Scatter(
            x=subset['x'], y=subset['y'],
            mode='markers',
            name=etype,
            marker=dict(
                color=color,
                size=(subset['xg'] * 40 + 8).clip(upper=28),
                symbol=symbol,
                opacity=0.85,
                line=dict(color='white', width=1.2),
            ),
            customdata=list(zip(
                subset['player_name'].fillna('') if 'player_name' in subset.columns else [''] * len(subset),
                subset['xg'],
            )),
            hovertemplate='<b>%{customdata[0]}</b><br>xG: %{customdata[1]:.2f}'
                          '<extra>' + etype + '</extra>',
        ))

    fig.update_layout(**CHART_LAYOUT_DEFAULTS, height=440, **PITCH_AXIS_HALF)
    fig.update_layout(legend=dict(orientation='h', y=-0.05, x=0.5, xanchor='center'))
    return fig


def _shot_types_donut(bar):
    """Donut: open play vs set piece shots."""
    shot_types = ['Goal', 'Saved Shot', 'Miss']
    shots = exclude_own_goals(bar[bar['event_type'].isin(shot_types)].copy())

    if shots.empty:
        return empty_fig("No shot data")

    sp = int(shots[shots.get('Set piece', pd.Series(dtype=str)) == 'Si'].shape[0]) \
        if 'Set piece' in shots.columns else 0
    op = int(len(shots) - sp)

    fig = go.Figure(go.Pie(
        labels=['Open Play', 'Set Piece'],
        values=[op, sp],
        marker_colors=[HOME_COLOR, GOLD],
        hole=0.45,
        textinfo='label+percent',
        textfont=dict(color='white', size=12),
    ))
    fig.update_layout(**CHART_LAYOUT_DEFAULTS, height=260, showlegend=False)
    fig.update_layout(margin=dict(l=0, r=0, t=20, b=0))
    fig.update_layout(title_text='Shot Origin', title_font_color=GOLD, title_font_size=12)
    return fig


def _pre_shot_sequences(bar):
    """Bar: most common event type immediately preceding a shot."""
    shot_types = ['Goal', 'Saved Shot', 'Miss']
    shots = exclude_own_goals(bar[bar['event_type'].isin(shot_types)].copy())

    if shots.empty or 'match_id' not in bar.columns:
        return empty_fig("No pre-shot sequence data")

    pre_events = []
    shots_sorted = shots.sort_values(['match_id', 'period_id', 'time_min', 'time_sec']
                                     if all(c in shots.columns for c in ['period_id', 'time_sec'])
                                     else ['match_id', 'time_min']) if 'time_min' in shots.columns else shots

    bar_sorted = bar.sort_values(['match_id', 'time_min']
                                 if 'time_min' in bar.columns else ['match_id'])

    for _, shot in shots_sorted.iterrows():
        match_ev = bar_sorted[bar_sorted['match_id'] == shot['match_id']] \
            if 'match_id' in bar_sorted.columns else bar_sorted
        if 'time_min' in shot.index and 'time_min' in match_ev.columns:
            prior = match_ev[match_ev['time_min'] < shot['time_min']]
            if not prior.empty:
                pre_events.append(prior.iloc[-1]['event_type'])

    if not pre_events:
        return empty_fig("Could not extract pre-shot sequences")

    counts = pd.Series(pre_events).value_counts().head(8)
    fig = go.Figure(go.Bar(
        y=counts.index, x=counts.values,
        orientation='h',
        marker_color=GOLD,
        hovertemplate='%{y}: %{x} times<extra></extra>',
    ))
    fig.update_layout(
        **CHART_LAYOUT_DEFAULTS, height=300,
        xaxis_title='Count',
        yaxis=dict(autorange='reversed'),
    )
    fig.update_layout(margin=dict(l=10, r=10, t=10, b=30))
    return fig


# ---------------------------------------------------------------------------
# Performance
# ---------------------------------------------------------------------------

def _xg_timeline(results, bar, events):
    """Cumulative actual goals vs xG proxy per match."""
    sorted_r = sorted(results, key=lambda r: r['date'])
    if not sorted_r:
        return empty_fig("No match data")

    cum_goals, cum_xg, labels = [], [], []
    g_total = xg_total = 0.0

    for r in sorted_r:
        me = bar[bar['match_id'] == r['match_id']] if 'match_id' in bar.columns else bar.head(0)
        goals = int(filter_own_goals(me[me['event_type'] == 'Goal'].copy()).shape[0]) \
            if not me.empty else r['barca_goals']
        shots = exclude_own_goals(
            me[me['event_type'].isin(['Goal', 'Saved Shot', 'Miss'])].copy()
        ).dropna(subset=['x', 'y'])
        xg = add_xg_column(shots)['xg'].sum() if not shots.empty else 0.0

        g_total  += goals
        xg_total += xg
        cum_goals.append(g_total)
        cum_xg.append(round(xg_total, 2))

        comp = _COMP_SHORT.get(r['competition'], r['competition'][:4])
        labels.append(f"{r['opponent']} · {comp}")

    x = list(range(1, len(cum_goals) + 1))
    result_colors = {'W': HOME_COLOR, 'D': GOLD, 'L': AWAY_COLOR}
    marker_colors = [result_colors.get(r['result'], GOLD) for r in sorted_r]

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=x, y=cum_goals, name='Goals Scored',
        mode='lines+markers',
        line=dict(color=GOLD, width=2),
        marker=dict(size=8, color=marker_colors, line=dict(color='white', width=1)),
        text=labels,
        hovertemplate='Match %{x}: %{text}<br>Goals: %{y}<extra></extra>',
    ))
    fig.add_trace(go.Scatter(
        x=x, y=cum_xg, name='xG',
        mode='lines',
        line=dict(color=HOME_COLOR, width=1.5, dash='dot'),
        hovertemplate='Match %{x}<br>xG: %{y:.2f}<extra></extra>',
    ))
    fig.update_layout(
        **CHART_LAYOUT_DEFAULTS,
        height=300,
        xaxis_title='Match',
        yaxis_title='Cumulative',
    )
    fig.update_layout(legend=dict(orientation='h', y=1.05, x=0.5, xanchor='center'))
    return fig


def _goals_vs_xg_bar(results, bar):
    """Per-match Goals scored vs xG proxy — deviation bars."""
    sorted_r = sorted(results, key=lambda r: r['date'])
    if not sorted_r:
        return empty_fig("No match data")

    labels, goals_list, xg_list, diff_list = [], [], [], []

    for r in sorted_r:
        me = bar[bar['match_id'] == r['match_id']] if 'match_id' in bar.columns else bar.head(0)
        goals = r['barca_goals']
        shots = exclude_own_goals(
            me[me['event_type'].isin(['Goal', 'Saved Shot', 'Miss'])].copy()
        ).dropna(subset=['x', 'y']) if not me.empty else me
        xg = round(add_xg_column(shots)['xg'].sum(), 2) if not shots.empty else 0.0
        diff = round(goals - xg, 2)

        comp = _COMP_SHORT.get(r['competition'], r['competition'][:4])
        labels.append(f"{r['opponent'][:12]} · {comp}")
        goals_list.append(goals)
        xg_list.append(xg)
        diff_list.append(diff)

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=labels, y=xg_list,
        name='xG',
        marker_color='rgba(255,255,255,0.2)',
        hovertemplate='%{x}<br>xG: %{y:.2f}<extra></extra>',
    ))
    fig.add_trace(go.Scatter(
        x=labels, y=goals_list,
        name='Goals Scored',
        mode='lines+markers',
        line=dict(color=GOLD, width=2),
        marker=dict(
            size=9,
            color=[HOME_COLOR if d >= 0 else AWAY_COLOR for d in diff_list],
            line=dict(color='white', width=1),
        ),
        hovertemplate='%{x}<br>Goals: %{y}<extra></extra>',
    ))

    fig.update_layout(
        **CHART_LAYOUT_DEFAULTS,
        height=320,
        barmode='overlay',
        xaxis_tickangle=-45,
        yaxis_title='Goals / xG',
    )
    fig.update_layout(legend=dict(orientation='h', y=1.05, x=0.5, xanchor='center'))
    return fig


# ---------------------------------------------------------------------------
# Public builder
# ---------------------------------------------------------------------------

def build_chance_creation_tab(season, competitions, match_ids=None):
    """Build the Chance Creation and Finishing tab content."""
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
    shot_types  = ['Goal', 'Saved Shot', 'Miss']
    shots       = exclude_own_goals(bar[bar['event_type'].isin(shot_types)].copy())
    shots_ot    = int(bar[bar['event_type'].isin(['Saved Shot', 'Goal'])].shape[0])
    goals       = int(filter_own_goals(bar[bar['event_type'] == 'Goal'].copy()).shape[0])
    key_passes  = int(bar[(bar['event_type'] == 'Pass') &
                          (bar.get('Assist', pd.Series(dtype=str)) == 'Si')].shape[0]) \
        if 'Assist' in bar.columns else 0
    crosses_n   = int(bar[bar['event_type'].isin(['Cross', 'Crossed Ball'])].shape[0])
    box_events  = int(bar[bar['x'].notna() & (bar['x'] >= 83)].shape[0])
    big_chances = int(bar[bar.get('Big Chance', pd.Series(dtype=str)) == 'Si'].shape[0]) \
        if 'Big Chance' in bar.columns else 0
    xg_total    = round(add_xg_column(shots.dropna(subset=['x', 'y']))['xg'].sum(), 1) if not shots.empty else 0.0
    conversion  = round(goals / max(len(shots), 1) * 100, 1)

    kpi = kpi_row(
        {
            'goals':       goals,
            'xg':          xg_total,
            'shots':       len(shots),
            'shots_ot':    shots_ot,
            'conversion':  f"{conversion}%",
            'key_passes':  key_passes,
            'big_chances': big_chances,
            'crosses':     crosses_n,
            'box_events':  box_events,
        },
        [
            ('goals',       'Goals'),
            ('xg',          'xG'),
            ('shots',       'Shots'),
            ('shots_ot',    'On Target'),
            ('conversion',  'Conversion'),
            ('key_passes',  'Key Passes'),
            ('big_chances', 'Big Chances'),
            ('crosses',     'Crosses'),
            ('box_events',  'Box Entries'),
        ],
        colors={
            'goals':       GOLD,
            'xg':          HOME_COLOR,
            'shots_ot':    HOME_COLOR,
            'conversion':  GOLD,
            'big_chances': HOME_COLOR,
        },
    )

    # ── Results for timeline ──────────────────────────────────────────────────
    all_results = get_match_results()
    results = [r for r in all_results
               if str(r['date'])[:4] in [season.split('-')[0], season.split('-')[1]]]
    if competitions:
        results = [r for r in results if r['competition'] in competitions]
    if match_ids:
        id_set  = set(match_ids)
        results = [r for r in results if r['match_id'] in id_set]

    # ── Creation cards ────────────────────────────────────────────────────────
    kp_map_card = section_card(
        "Key Passes Map — Origin & Direction",
        dcc.Graph(figure=_key_passes_map(bar), config=CHART_CONFIG),
    )
    box_card = section_card(
        "Box Entries — Pass vs Cross vs Take-On",
        dcc.Graph(figure=_box_entries(bar), config=CHART_CONFIG),
    )
    cross_card = section_card(
        "Crossing Patterns — Zone & Accuracy",
        dcc.Graph(figure=_crossing_patterns(bar), config=CHART_CONFIG),
    )

    # ── Finishing cards ───────────────────────────────────────────────────────
    shot_map_card = section_card(
        "Shot Map — xG (bubble size = danger)",
        dcc.Graph(figure=_shot_map_xg(bar), config=CHART_CONFIG),
    )
    shot_type_card = section_card(
        "Shot Origin — Open Play vs Set Piece",
        dcc.Graph(figure=_shot_types_donut(bar), config=CHART_CONFIG),
    )
    preshot_card = section_card(
        "Pre-Shot Sequences — Last Event Before Shot",
        dcc.Graph(figure=_pre_shot_sequences(bar), config=CHART_CONFIG),
    )

    # ── Performance cards ─────────────────────────────────────────────────────
    timeline_card = section_card(
        "xG Timeline — Cumulative Goals vs xG",
        dcc.Graph(figure=_xg_timeline(results, bar, events), config=CHART_CONFIG),
    )
    gvxg_card = section_card(
        "Goals vs xG per Match — Over / Under Performance",
        dcc.Graph(figure=_goals_vs_xg_bar(results, bar), config=CHART_CONFIG),
    )

    return html.Div([
        kpi,
        html.P("Creation", style={
            'color': COLORS['text_secondary'], 'fontSize': '0.78rem',
            'fontStyle': 'italic', 'marginTop': '8px', 'marginBottom': '4px',
        }),
        dbc.Row([
            dbc.Col(kp_map_card, md=6),
            dbc.Col([box_card, cross_card], md=6),
        ], className='mb-3'),
        html.P("Finishing", style={
            'color': COLORS['text_secondary'], 'fontSize': '0.78rem',
            'fontStyle': 'italic', 'marginBottom': '4px',
        }),
        dbc.Row([
            dbc.Col(shot_map_card,  md=6),
            dbc.Col([shot_type_card, preshot_card], md=6),
        ], className='mb-3'),
        html.P("Performance", style={
            'color': COLORS['text_secondary'], 'fontSize': '0.78rem',
            'fontStyle': 'italic', 'marginBottom': '4px',
        }),
        dbc.Row([
            dbc.Col(timeline_card, md=6),
            dbc.Col(gvxg_card,     md=6),
        ], className='mb-3'),
    ])
