"""
Team Analysis — Tab 1: Team Identity (Macro Profile)

Answers: What kind of team are we fundamentally?

Shows:
- Season record, points, PPG
- Avg possession, pass accuracy, pressing intensity (PPDA proxy)
- Shot volume & conversion
- Form trendline
- Radar profile vs season benchmarks
- Per-competition breakdown table
"""

from dash import html, dcc
import dash_bootstrap_components as dbc
import plotly.graph_objects as go

from utils.config import COLORS
from utils.data_utils import (
    get_all_events,
    get_match_results,
    get_team_season_stats,
    CURRENT_SEASON,
)
from pages.match_analysis_tabs.shared import (
    CHART_LAYOUT_DEFAULTS,
    CHART_CONFIG,
    section_card,
    kpi_row,
    stat_card,
    empty_fig,
    GOLD,
    HOME_COLOR,
    AWAY_COLOR,
)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _compute_identity_stats(results, bar_events, all_events):
    """Compute all macro stats from filtered results + events."""
    matches = len(results)
    wins    = sum(1 for r in results if r['result'] == 'W')
    draws   = sum(1 for r in results if r['result'] == 'D')
    losses  = sum(1 for r in results if r['result'] == 'L')
    gf      = sum(r['barca_goals']    for r in results)
    ga      = sum(r['opponent_goals'] for r in results)
    cs      = sum(1 for r in results if r['opponent_goals'] == 0)
    pts     = wins * 3 + draws
    ppg     = round(pts / matches, 2) if matches else 0.0

    # Possession (pass-share)
    bar_passes = bar_events[bar_events['event_type'] == 'Pass']
    all_passes = all_events[all_events['event_type'] == 'Pass']
    possession = round(len(bar_passes) / max(len(all_passes), 1) * 100, 1)

    # Pass accuracy
    pass_acc = round(
        bar_passes['outcome'].eq(1).sum() / max(len(bar_passes), 1) * 100, 1
    )

    # Shots & conversion
    shot_types = ['Miss', 'Saved Shot', 'Goal']
    shots     = int(bar_events[bar_events['event_type'].isin(shot_types)].shape[0])
    shots_ot  = int(bar_events[bar_events['event_type'].isin(['Saved Shot', 'Goal'])].shape[0])
    conversion = round(gf / max(shots, 1) * 100, 1)

    # Defensive actions (tackles + interceptions)
    def_actions = bar_events[bar_events['event_type'].isin(['Tackle', 'Interception'])]

    # PPDA proxy: opp passes in defending zone (x < 40) / BAR def actions in opp half (x > 50)
    opp_events   = all_events[all_events['team_code'] != 'BAR']
    opp_passes_def = opp_events[
        (opp_events['event_type'] == 'Pass') &
        (opp_events['x'].notna()) & (opp_events['x'] < 40)
    ]
    bar_press_actions = def_actions[def_actions['x'].notna() & (def_actions['x'] > 50)]
    ppda = round(
        len(opp_passes_def) / max(len(bar_press_actions), 1), 1
    )

    # Field tilt: BAR touches in final third / all touches in final third
    final_third = all_events[all_events['x'].notna() & (all_events['x'] > 66)]
    bar_ft      = final_third[final_third['team_code'] == 'BAR']
    field_tilt  = round(len(bar_ft) / max(len(final_third), 1) * 100, 1)

    # Press height: avg x of BAR defensive actions
    press_height = round(
        def_actions['x'].dropna().mean(), 1
    ) if not def_actions.empty else 0.0

    return {
        'matches':      matches,
        'wins':         wins,
        'draws':        draws,
        'losses':       losses,
        'gf':           gf,
        'ga':           ga,
        'cs':           cs,
        'pts':          pts,
        'ppg':          ppg,
        'possession':   possession,
        'pass_acc':     pass_acc,
        'shots':        shots,
        'shots_ot':     shots_ot,
        'conversion':   conversion,
        'ppda':         ppda,
        'field_tilt':   field_tilt,
        'press_height': press_height,
    }


def _form_trendline(results):
    """Cumulative points + PPG trendline."""
    sorted_results = sorted(results, key=lambda x: x['date'])
    cumulative, ppg_vals, labels = [], [], []
    total = 0
    for i, r in enumerate(sorted_results, 1):
        pts = 3 if r['result'] == 'W' else (1 if r['result'] == 'D' else 0)
        total += pts
        cumulative.append(total)
        ppg_vals.append(round(total / i, 2))
        comp_short = {'La Liga': 'Liga', 'Champions League': 'UCL',
                      'Copa del Rey': 'Copa', 'Spanish Super Cup': 'SC'}
        comp = comp_short.get(r['competition'], r['competition'][:4])
        labels.append(f"{r['opponent']} ({r['result']}) · {comp}")

    if not cumulative:
        return empty_fig("No matches to display")

    result_colors = {'W': HOME_COLOR, 'D': GOLD, 'L': AWAY_COLOR}
    marker_colors = [
        result_colors.get(r['result'], GOLD) for r in sorted_results
    ]

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=list(range(1, len(cumulative) + 1)),
        y=cumulative,
        mode='lines+markers',
        name='Cumulative Points',
        line=dict(color=GOLD, width=2),
        marker=dict(size=8, color=marker_colors, line=dict(color='white', width=1)),
        text=labels,
        hovertemplate='Match %{x}: %{text}<br>Points: %{y}<extra></extra>',
    ))
    fig.add_trace(go.Scatter(
        x=list(range(1, len(ppg_vals) + 1)),
        y=ppg_vals,
        mode='lines',
        name='PPG',
        line=dict(color=HOME_COLOR, width=1.5, dash='dot'),
        hovertemplate='Match %{x}<br>PPG: %{y}<extra></extra>',
    ))
    fig.update_layout(
        **CHART_LAYOUT_DEFAULTS,
        height=300,
        xaxis_title='Match number',
        yaxis_title='Points',
    )
    return fig


def _radar_chart(s):
    """Team identity radar — 6 dimensions, normalised 0-100."""
    # Possession: raw %
    # Pass accuracy: raw %
    # Conversion: raw %
    # Field tilt: raw %
    # Press intensity: invert PPDA so higher = more pressing (clamp 0-100)
    # Win rate: raw %
    win_rate   = round(s['wins'] / max(s['matches'], 1) * 100, 1)
    press_int  = max(0, min(100, round(100 - s['ppda'] * 5, 1)))  # lower PPDA = higher intensity

    categories = [
        'Possession %', 'Pass Accuracy', 'Conversion %',
        'Field Tilt %', 'Press Intensity', 'Win Rate %',
    ]
    values = [
        s['possession'], s['pass_acc'], s['conversion'],
        s['field_tilt'], press_int, win_rate,
    ]
    # Close the polygon
    values_closed = values + [values[0]]
    cats_closed   = categories + [categories[0]]

    fig = go.Figure()
    fig.add_trace(go.Scatterpolar(
        r=values_closed,
        theta=cats_closed,
        fill='toself',
        name='Barcelona',
        line=dict(color=GOLD, width=2),
        fillcolor=f'rgba(161,120,40,0.3)',
        hovertemplate='%{theta}: %{r:.1f}<extra></extra>',
    ))
    fig.update_layout(
        **CHART_LAYOUT_DEFAULTS,
        height=360,
        polar=dict(
            bgcolor='rgba(0,0,0,0)',
            radialaxis=dict(
                visible=True, range=[0, 100],
                color=COLORS['text_secondary'],
                gridcolor='rgba(255,255,255,0.15)',
            ),
            angularaxis=dict(
                color=COLORS['text_secondary'],
                gridcolor='rgba(255,255,255,0.15)',
            ),
        ),
        showlegend=False,
    )
    return fig


def _competition_breakdown(results, all_events):
    """One card per competition showing W-D-L, GF/GA, possession, pass acc."""
    comps = {}
    for r in results:
        c = r['competition']
        comps.setdefault(c, {'results': [], 'short': c[:4]})
        comps[c]['results'].append(r)

    comp_short = {
        'La Liga': 'Liga', 'Champions League': 'UCL',
        'Copa del Rey': 'Copa', 'Spanish Super Cup': 'SC',
    }

    cards = []
    for comp, data in comps.items():
        rs  = data['results']
        mp  = len(rs)
        w   = sum(1 for r in rs if r['result'] == 'W')
        d   = sum(1 for r in rs if r['result'] == 'D')
        l   = sum(1 for r in rs if r['result'] == 'L')
        gf  = sum(r['barca_goals']    for r in rs)
        ga  = sum(r['opponent_goals'] for r in rs)
        pts = w * 3 + d
        cs  = sum(1 for r in rs if r['opponent_goals'] == 0)

        # Possession for this competition
        ce  = all_events[all_events['competition'] == comp] if not all_events.empty else all_events
        bar_pass = len(ce[(ce['team_code'] == 'BAR') & (ce['event_type'] == 'Pass')])
        all_pass = len(ce[ce['event_type'] == 'Pass'])
        poss = round(bar_pass / max(all_pass, 1) * 100, 1)

        label = comp_short.get(comp, comp[:4])
        record_color = HOME_COLOR if w > l else (AWAY_COLOR if l > w else GOLD)

        cards.append(
            dbc.Col(dbc.Card([
                dbc.CardHeader(
                    html.Span(comp, style={'color': GOLD, 'fontWeight': 600}),
                ),
                dbc.CardBody([
                    html.Div(f"{w}W – {d}D – {l}L",
                             style={'color': record_color, 'fontSize': '1.1rem', 'fontWeight': 700}),
                    html.Div(f"{pts} pts  ·  GF {gf} / GA {ga}  ·  CS {cs}",
                             style={'color': COLORS['text_secondary'], 'fontSize': '0.82rem', 'marginTop': '4px'}),
                    html.Div(f"Possession: {poss}%  ·  {mp} matches",
                             style={'color': COLORS['text_secondary'], 'fontSize': '0.82rem', 'marginTop': '2px'}),
                ]),
            ], className="h-100"), md=3)
        )

    if not cards:
        return html.Div()
    return dbc.Row(cards, className="mb-3")


# ---------------------------------------------------------------------------
# Public builder
# ---------------------------------------------------------------------------

def build_identity_tab(season, competitions, match_ids=None):
    """Build the Team Identity tab content."""
    all_results = get_match_results()
    results = [
        r for r in all_results
        if str(r['date'])[:4] in [season.split('-')[0], season.split('-')[1]]
    ]
    if competitions:
        results = [r for r in results if r['competition'] in competitions]
    if match_ids:
        id_set = set(match_ids)
        results = [r for r in results if r['match_id'] in id_set]

    if not results:
        return html.P("No data available for the selected filters.",
                      style={'color': COLORS['text_secondary']})

    all_events = get_all_events(season)
    if not all_events.empty:
        if competitions and 'competition' in all_events.columns:
            all_events = all_events[all_events['competition'].isin(competitions)]
        if match_ids:
            all_events = all_events[all_events['match_id'].isin(match_ids)]

    bar_events = all_events[all_events['team_code'] == 'BAR'] if not all_events.empty else all_events

    s = _compute_identity_stats(results, bar_events, all_events)

    # ── KPI rows ────────────────────────────────────────────────────────────
    row1 = kpi_row(
        {
            'matches': s['matches'],
            'wins':    s['wins'],
            'draws':   s['draws'],
            'losses':  s['losses'],
            'pts':     s['pts'],
            'ppg':     s['ppg'],
        },
        [
            ('matches', 'Played'),
            ('wins',    'Wins'),
            ('draws',   'Draws'),
            ('losses',  'Losses'),
            ('pts',     'Points'),
            ('ppg',     'PPG'),
        ],
        colors={'wins': HOME_COLOR, 'losses': AWAY_COLOR, 'pts': GOLD, 'ppg': GOLD},
    )

    row2 = kpi_row(
        {
            'possession':  f"{s['possession']}%",
            'pass_acc':    f"{s['pass_acc']}%",
            'shots':       s['shots'],
            'shots_ot':    s['shots_ot'],
            'conversion':  f"{s['conversion']}%",
            'ppda':        s['ppda'],
            'field_tilt':  f"{s['field_tilt']}%",
            'cs':          s['cs'],
        },
        [
            ('possession',  'Possession'),
            ('pass_acc',    'Pass Accuracy'),
            ('shots',       'Shots'),
            ('shots_ot',    'Shots on Target'),
            ('conversion',  'Conversion'),
            ('ppda',        'PPDA'),
            ('field_tilt',  'Field Tilt'),
            ('cs',          'Clean Sheets'),
        ],
        colors={'possession': HOME_COLOR, 'conversion': GOLD, 'cs': GOLD, 'ppda': AWAY_COLOR},
    )

    # ── Radar + form trendline side by side ─────────────────────────────────
    radar_card = section_card(
        "Identity Radar",
        dcc.Graph(figure=_radar_chart(s), config=CHART_CONFIG),
    )
    form_card = section_card(
        "Form Trendline  ● W  ● D  ● L",
        dcc.Graph(figure=_form_trendline(results), config=CHART_CONFIG),
    )

    # ── Per-competition breakdown ────────────────────────────────────────────
    breakdown = _competition_breakdown(results, all_events)
    breakdown_section = section_card("Competition Breakdown", breakdown) if breakdown.children else html.Div()

    return html.Div([
        row1,
        row2,
        dbc.Row([
            dbc.Col(radar_card, md=5),
            dbc.Col(form_card,  md=7),
        ], className="mb-3"),
        breakdown_section,
    ])
