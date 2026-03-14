"""
Team Analysis — Tab 2: In Possession (Build-Up & Creation Model)

Answers: How do we attack structurally?

Shows:
- KPIs: passes, pass accuracy, possession %, final third entries, progressive passes
- Touch density heatmap (attacking half)
- Pass direction breakdown (forward / sideways / backward)
- Final third entry zones (horizontal bar)
- Shot map (BAR shots)
- Top scorers & top passers tables
- Common pass zones (touch heatmap by zone)
"""

from dash import html, dcc
import dash_bootstrap_components as dbc
import plotly.graph_objects as go

from utils.config import COLORS
from utils.data_utils import (
    get_all_events,
    get_match_results,
    get_player_stats,
    get_player_stats_by_competition,
    filter_own_goals,
    exclude_own_goals,
    CURRENT_SEASON,
)
from pages.match_analysis_tabs.shared import (
    CHART_LAYOUT_DEFAULTS,
    CHART_CONFIG,
    add_pitch_background,
    PITCH_AXIS_HALF,
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

_SHOT_STYLE = {
    'Goal':       ('star',   GOLD,       18),
    'Saved Shot': ('circle', HOME_COLOR, 11),
    'Miss':       ('x',      AWAY_COLOR, 10),
}


def _pass_direction_chart(bar_events):
    """Donut: forward / sideways / backward passes."""
    passes = bar_events[
        (bar_events['event_type'] == 'Pass') &
        bar_events['x'].notna() &
        bar_events['end_x'].notna()
    ] if 'end_x' in bar_events.columns else bar_events[bar_events['event_type'] == 'Pass'].head(0)

    if passes.empty or 'end_x' not in passes.columns:
        # Fallback: use outcome to approximate
        all_passes = bar_events[bar_events['event_type'] == 'Pass']
        if all_passes.empty:
            return empty_fig("No pass data")
        # Can't compute direction without end_x — show pass accuracy instead
        acc  = int(all_passes['outcome'].eq(1).sum())
        fail = int(all_passes['outcome'].ne(1).sum())
        fig = go.Figure(go.Pie(
            labels=['Successful', 'Unsuccessful'],
            values=[acc, fail],
            marker_colors=[HOME_COLOR, AWAY_COLOR],
            hole=0.45,
            textinfo='label+value',
            textfont=dict(color='white', size=11),
        ))
        fig.update_layout(**CHART_LAYOUT_DEFAULTS, height=240, showlegend=False,
                          title_text='Pass Outcomes', title_font_color=GOLD)
        fig.update_layout(margin=dict(l=0, r=0, t=30, b=0))
        return fig

    dx = passes['end_x'] - passes['x']
    forward   = int((dx >  5).sum())
    backward  = int((dx < -5).sum())
    sideways  = int(passes.shape[0] - forward - backward)

    fig = go.Figure(go.Pie(
        labels=['Forward', 'Sideways', 'Backward'],
        values=[forward, sideways, backward],
        marker_colors=[HOME_COLOR, GOLD, AWAY_COLOR],
        hole=0.45,
        textinfo='label+value',
        textfont=dict(color='white', size=11),
    ))
    fig.update_layout(**CHART_LAYOUT_DEFAULTS, height=240, showlegend=False,
                      margin=dict(l=0, r=0, t=10, b=0))
    return fig


def _final_third_entry_zones(bar_events):
    """Horizontal bar: entries into final third by lateral zone."""
    ft = bar_events[
        bar_events['x'].notna() & (bar_events['x'] >= 66)
    ] if not bar_events.empty else bar_events

    if ft.empty:
        return empty_fig("No final third data")

    # Split by y (0-33 = left channel, 33-66 = central, 66-100 = right channel)
    left    = int(ft[ft['y'] <  33].shape[0])
    central = int(ft[(ft['y'] >= 33) & (ft['y'] < 67)].shape[0])
    right   = int(ft[ft['y'] >= 67].shape[0])

    zones  = ['Left Channel', 'Central', 'Right Channel']
    counts = [left, central, right]
    colors = [HOME_COLOR, GOLD, AWAY_COLOR]

    fig = go.Figure(go.Bar(
        y=zones, x=counts, orientation='h',
        marker_color=colors,
        hovertemplate='%{y}: %{x} entries<extra></extra>',
    ))
    fig.update_layout(
        **CHART_LAYOUT_DEFAULTS,
        height=200,
        xaxis_title='Events in Final Third',
        margin=dict(l=10, r=10, t=10, b=30),
    )
    return fig


def _shot_map(bar_events):
    """Full shot map — star = goal, circle = saved, x = miss."""
    shot_types = ['Goal', 'Saved Shot', 'Miss']
    shots = exclude_own_goals(
        bar_events[bar_events['event_type'].isin(shot_types)].copy()
    ).dropna(subset=['x', 'y'])

    if shots.empty:
        return empty_fig("No shot data")

    fig = go.Figure()
    add_pitch_background(fig, half=True)

    for etype, (symbol, color, size) in _SHOT_STYLE.items():
        subset = shots[shots['event_type'] == etype]
        if subset.empty:
            continue
        body = subset.apply(
            lambda r: ('Header'     if r.get('Head') == 'Si'
                       else 'Right Foot' if r.get('Right footed') == 'Si'
                       else 'Left Foot'),
            axis=1,
        )
        fig.add_trace(go.Scatter(
            x=subset['x'], y=subset['y'],
            mode='markers', name=etype,
            marker=dict(color=color, size=size, symbol=symbol,
                        line=dict(color='white', width=1.5)),
            customdata=list(zip(
                subset.get('player_name', subset.index).fillna('Unknown'),
                body,
            )),
            hovertemplate='<b>%{customdata[0]}</b><br>%{customdata[1]}'
                          '<extra>' + etype + '</extra>',
        ))

    fig.update_layout(**CHART_LAYOUT_DEFAULTS, height=420, **PITCH_AXIS_HALF)
    fig.update_layout(legend=dict(orientation='h', y=-0.05, x=0.5, xanchor='center'))
    return fig


def _top_scorers_chart(bar_events, competitions, match_ids, season):
    """Top 10 scorers bar chart."""
    if match_ids:
        goal_ev = filter_own_goals(bar_events[bar_events['event_type'] == 'Goal'].copy())
        series  = goal_ev.groupby('player_name').size().sort_values(ascending=False).head(10)
    else:
        ps = get_player_stats(season)
        if not ps.empty and competitions and len(competitions) == 1:
            comp_ps = get_player_stats_by_competition(competitions[0], season)
            if not comp_ps.empty:
                ps = comp_ps
        if ps.empty:
            return empty_fig("No scorer data")
        top10 = ps[ps['goals'] > 0].head(10)
        series = top10.set_index('player')['goals']

    if series.empty:
        return empty_fig("No goals in selection")

    fig = go.Figure(go.Bar(
        x=series.values, y=series.index,
        orientation='h',
        marker_color=GOLD,
        hovertemplate='%{y}: %{x} goals<extra></extra>',
    ))
    fig.update_layout(
        **CHART_LAYOUT_DEFAULTS, height=350,
        xaxis_title='Goals',
        yaxis=dict(autorange='reversed'),
        margin=dict(l=10, r=10, t=10, b=30),
    )
    return fig


def _top_passers_chart(bar_events):
    """Top 10 players by pass count."""
    passes = bar_events[bar_events['event_type'] == 'Pass']
    if passes.empty:
        return empty_fig("No pass data")

    series = passes.groupby('player_name').size().sort_values(ascending=False).head(10)
    fig = go.Figure(go.Bar(
        x=series.values, y=series.index,
        orientation='h',
        marker_color=HOME_COLOR,
        hovertemplate='%{y}: %{x} passes<extra></extra>',
    ))
    fig.update_layout(
        **CHART_LAYOUT_DEFAULTS, height=350,
        xaxis_title='Passes',
        yaxis=dict(autorange='reversed'),
        margin=dict(l=10, r=10, t=10, b=30),
    )
    return fig


def _progressive_passes_chart(bar_events):
    """Scatter: progressive passes (x gain ≥ 10) on half pitch."""
    if 'end_x' not in bar_events.columns:
        return empty_fig("No pass endpoint data")

    passes = bar_events[
        (bar_events['event_type'] == 'Pass') &
        bar_events['x'].notna() & bar_events['end_x'].notna() &
        bar_events['y'].notna()
    ].copy()
    prog = passes[(passes['end_x'] - passes['x']) >= 10]

    if prog.empty:
        return empty_fig("No progressive pass data")

    fig = go.Figure()
    add_pitch_background(fig, half=False)
    fig.add_trace(go.Scatter(
        x=prog['x'], y=prog['y'],
        mode='markers',
        name='Progressive Pass Origin',
        marker=dict(color=HOME_COLOR, size=5, opacity=0.6,
                    line=dict(color='white', width=0.3)),
        text=prog['player_name'].fillna(''),
        hovertemplate='%{text}<extra>Progressive Pass</extra>',
    ))
    fig.update_layout(**CHART_LAYOUT_DEFAULTS, height=360, **PITCH_AXIS_FULL)
    return fig


# ---------------------------------------------------------------------------
# Public builder
# ---------------------------------------------------------------------------

def build_in_possession_tab(season, competitions, match_ids=None):
    """Build the In Possession tab content."""
    events = get_all_events(season)
    if events.empty:
        return html.P("No data available.", style={'color': COLORS['text_secondary']})

    if competitions and 'competition' in events.columns:
        events = events[events['competition'].isin(competitions)]
    if match_ids:
        events = events[events['match_id'].isin(match_ids)]

    bar = events[events['team_code'] == 'BAR']

    if bar.empty:
        return html.P("No Barcelona event data for this selection.",
                      style={'color': COLORS['text_secondary']})

    # ── KPI metrics ─────────────────────────────────────────────────────────
    passes_all = events[events['event_type'] == 'Pass']
    bar_passes = bar[bar['event_type'] == 'Pass']
    possession = round(len(bar_passes) / max(len(passes_all), 1) * 100, 1)
    pass_acc   = round(
        bar_passes['outcome'].eq(1).sum() / max(len(bar_passes), 1) * 100, 1
    )
    shot_types = ['Miss', 'Saved Shot', 'Goal']
    shots      = int(bar[bar['event_type'].isin(shot_types)].shape[0])
    shots_ot   = int(bar[bar['event_type'].isin(['Saved Shot', 'Goal'])].shape[0])
    ft_entries = int(bar[bar['x'].notna() & (bar['x'] >= 66)].shape[0]) if not bar.empty else 0
    goals      = int(filter_own_goals(bar[bar['event_type'] == 'Goal'].copy()).shape[0])

    kpi = kpi_row(
        {
            'possession':  f"{possession}%",
            'pass_acc':    f"{pass_acc}%",
            'passes':      int(len(bar_passes)),
            'ft_entries':  ft_entries,
            'shots':       shots,
            'shots_ot':    shots_ot,
            'goals':       goals,
        },
        [
            ('possession',  'Possession'),
            ('pass_acc',    'Pass Accuracy'),
            ('passes',      'Passes'),
            ('ft_entries',  'Final Third Entries'),
            ('shots',       'Shots'),
            ('shots_ot',    'Shots on Target'),
            ('goals',       'Goals'),
        ],
        colors={'possession': HOME_COLOR, 'goals': GOLD, 'shots_ot': GOLD},
    )

    # ── Touch heatmap (attacking half) ──────────────────────────────────────
    bar_xy = bar.dropna(subset=['x', 'y'])
    if not bar_xy.empty:
        heatmap_src = render_heatmap_img(bar_xy['x'].values, bar_xy['y'].values,
                                         cmap='Blues', half=False)
        heatmap_content = html.Img(
            src=heatmap_src,
            style={'width': '100%', 'borderRadius': '4px'},
        )
    else:
        heatmap_content = html.P("No touch data", style={'color': COLORS['text_secondary']})

    # ── Section cards ────────────────────────────────────────────────────────
    heatmap_card  = section_card("Touch Density",         heatmap_content)
    direction_card = section_card("Pass Direction",       dcc.Graph(figure=_pass_direction_chart(bar), config=CHART_CONFIG))
    ft_entry_card  = section_card("Final Third Entries",  dcc.Graph(figure=_final_third_entry_zones(bar), config=CHART_CONFIG))
    shot_card      = section_card("Shot Map  ★ Goal  ● Saved  ✕ Miss",
                                  dcc.Graph(figure=_shot_map(bar), config=CHART_CONFIG))
    scorers_card   = section_card("Top Scorers",
                                  dcc.Graph(figure=_top_scorers_chart(bar, competitions, match_ids, season), config=CHART_CONFIG))
    passers_card   = section_card("Top Passers",
                                  dcc.Graph(figure=_top_passers_chart(bar), config=CHART_CONFIG))

    # Progressive passes (if end_x available)
    if 'end_x' in bar.columns:
        prog_card = section_card("Progressive Pass Origins",
                                 dcc.Graph(figure=_progressive_passes_chart(bar), config=CHART_CONFIG))
    else:
        prog_card = html.Div()

    return html.Div([
        kpi,
        dbc.Row([
            dbc.Col(shot_card, md=7),
            dbc.Col([direction_card, ft_entry_card], md=5),
        ], className="mb-3"),
        dbc.Row([
            dbc.Col(scorers_card,  md=6),
            dbc.Col(passers_card,  md=6),
        ], className="mb-3"),
        dbc.Row([
            dbc.Col(heatmap_card, md=6),
            dbc.Col(prog_card,    md=6),
        ]),
    ])
