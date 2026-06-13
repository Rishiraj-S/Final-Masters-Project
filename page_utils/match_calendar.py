"""
Shared match-calendar scaffolding for the Barça IQ and Opposition Analysis pages.

Both pages render a monthly calendar of clickable match buttons and wire an
identical set of month-navigation / multi-select callbacks.  The only real
differences are cosmetic (logo + font sizes, paddings), the per-match field
names (Barça uses ``barca_goals``/``opponent_goals`` + ``competition``; the
opposition page uses ``gf``/``ga`` + ``competition_key``), and the element-id
prefix (``ta`` vs ``oa``).

`build_calendar_grid` defaults reproduce the Barça IQ styling exactly; the
opposition page passes the handful of overrides it needs.  `register_calendar_callbacks`
wires the three shared callbacks (month nav, selection toggle, selection
indicator) for a given id prefix.
"""

from __future__ import annotations

import calendar
from datetime import datetime
from typing import Callable

from dash import html, ctx
from dash.dependencies import Input, Output, State, ALL

from utils.config import COLORS
from utils.logos import get_team_logo_path
from page_utils.visualizations import GOLD

# Shared by both pages.
RESULT_COLORS = {
    'W': '#28a745',
    'D': '#ffc107',
    'L': '#dc3545',
}

_DAYS_OF_WEEK = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']


# ── Calendar grid ────────────────────────────────────────────────────────────

def build_calendar_grid(
    year: int,
    month: int,
    match_data: list[dict],
    selected_match_ids: list[str] | None,
    *,
    id_type: str,
    score_fn: Callable[[dict], str],
    comp_value_fn: Callable[[dict], str],
    comp_short_fn: Callable[[str], str],
    comp_logo_fn: Callable[[str], str | None],
    opp_logo_size: int = 20,
    opp_logo_margin: int = 4,
    opp_font: str = '0.8rem',
    tourn_logo_size: int = 14,
    tourn_logo_margin: int = 3,
    tourn_font: str = '0.65rem',
    tourn_pad: str = '1px 4px',
    score_font: str = '0.7rem',
    score_margin: int = 6,
    button_padding: str = '4px 6px',
) -> html.Div:
    """Build a monthly calendar grid of clickable match buttons.

    Defaults reproduce the Barça IQ calendar styling; callers override the
    cosmetic kwargs to match a different page.  ``score_fn``/``comp_value_fn``
    abstract the differing per-match field names; ``comp_short_fn``/``comp_logo_fn``
    map a competition value to its short label / logo path.  ``id_type`` is the
    pattern-matching button-id ``type`` (e.g. ``'ta-cal-match-btn'``).
    """
    selected_match_ids = selected_match_ids or []

    cal = calendar.Calendar(firstweekday=0)
    month_days = cal.monthdayscalendar(year, month)

    matches_by_day: dict[int, list] = {}
    for m in match_data:
        m_date = str(m.get('date', ''))[:10]
        if len(m_date) == 10:
            m_year, m_month, m_day = int(m_date[:4]), int(m_date[5:7]), int(m_date[8:10])
            if m_year == year and m_month == month:
                matches_by_day.setdefault(m_day, []).append(m)

    header = html.Div(
        [html.Div(d, style={
            'flex': '1', 'textAlign': 'center', 'padding': '8px 0',
            'color': COLORS['text_secondary'], 'fontWeight': 'bold',
            'fontSize': '0.8rem',
        }) for d in _DAYS_OF_WEEK],
        style={'display': 'flex', 'borderBottom': f'1px solid {COLORS["dark_border"]}'},
    )

    week_rows = []
    for week in month_days:
        day_cells = []
        for day_num in week:
            if day_num == 0:
                day_cells.append(html.Div(style={'flex': '1', 'minHeight': '80px'}))
                continue

            day_matches = matches_by_day.get(day_num, [])
            cell_children = [
                html.Div(str(day_num), style={
                    'fontSize': '0.75rem',
                    'color': COLORS['text_secondary'],
                    'marginBottom': '2px',
                })
            ]

            for m in day_matches:
                match_id = m.get('match_id')
                is_selected = match_id in selected_match_ids
                result_color = RESULT_COLORS.get(m.get('result', ''), COLORS['text_secondary'])
                is_home = m.get('is_home', True)
                opponent = m.get('opponent', '???')
                score = score_fn(m)
                venue_marker = 'H' if is_home else 'A'
                comp_value = comp_value_fn(m)

                opp_logo_path = get_team_logo_path(opponent)
                tourn_logo_path = comp_logo_fn(comp_value)

                logo_children = []
                if opp_logo_path:
                    logo_children.append(html.Img(
                        src=opp_logo_path,
                        style={
                            'height': f'{opp_logo_size}px', 'width': f'{opp_logo_size}px',
                            'objectFit': 'contain', 'marginRight': f'{opp_logo_margin}px',
                            'flexShrink': '0',
                        },
                    ))
                logo_children.append(html.Span(opponent, style={
                    'fontSize': opp_font, 'fontWeight': 'bold', 'color': '#E8E9ED',
                    'lineHeight': '1.2', 'overflow': 'hidden',
                    'textOverflow': 'ellipsis', 'whiteSpace': 'nowrap',
                }))

                tourn_children = []
                if tourn_logo_path:
                    tourn_children.append(html.Img(
                        src=tourn_logo_path,
                        style={
                            'height': f'{tourn_logo_size}px', 'width': f'{tourn_logo_size}px',
                            'objectFit': 'contain', 'marginRight': f'{tourn_logo_margin}px',
                        },
                    ))
                tourn_children.append(html.Span(comp_short_fn(comp_value), style={
                    'fontSize': tourn_font, 'color': COLORS['text_primary'],
                }))

                check_span = html.Span('✓ ', style={
                    'color': GOLD, 'fontSize': '0.7rem',
                    'fontWeight': '700', 'marginRight': '2px',
                }) if is_selected else None

                cell_children.append(
                    html.Button(
                        html.Div([
                            html.Div(
                                ([check_span] if check_span else []) + logo_children,
                                style={'display': 'flex', 'alignItems': 'center', 'overflow': 'hidden'},
                            ),
                            html.Div([
                                html.Span(f"{score} ({venue_marker})", style={
                                    'fontSize': score_font,
                                    'color': GOLD if is_selected else result_color,
                                    'fontWeight': 'bold', 'marginRight': f'{score_margin}px',
                                }),
                                html.Span(tourn_children, style={
                                    'display': 'inline-flex', 'alignItems': 'center',
                                    'backgroundColor': 'rgba(255, 255, 255, 0.08)',
                                    'borderRadius': '3px', 'padding': tourn_pad,
                                }),
                            ], style={'display': 'flex', 'alignItems': 'center', 'marginTop': '2px'}),
                        ]),
                        id={'type': id_type, 'match_id': match_id},
                        n_clicks=0,
                        style={
                            'background': 'rgba(237, 187, 0, 0.15)' if is_selected else 'none',
                            'border': 'none',
                            'borderLeft': f'3px solid {GOLD if is_selected else result_color}',
                            'padding': button_padding, 'cursor': 'pointer',
                            'width': '100%', 'textAlign': 'left',
                            'borderRadius': '0 4px 4px 0',
                            'marginBottom': '2px',
                        },
                    )
                )

            has_match = len(day_matches) > 0
            cell_style = {
                'flex': '1', 'minHeight': '80px', 'padding': '4px',
                'borderRight': f'1px solid {COLORS["dark_border"]}',
                'borderBottom': f'1px solid {COLORS["dark_border"]}',
            }
            if has_match:
                cell_style['backgroundColor'] = '#2A2F4A'
                cell_style['borderBottom'] = f'2px solid {GOLD}'
            today = datetime.now()
            if year == today.year and month == today.month and day_num == today.day:
                cell_style['boxShadow'] = f'inset 0 0 0 1px {GOLD}'

            day_cells.append(html.Div(cell_children, style=cell_style))

        week_rows.append(html.Div(day_cells, style={'display': 'flex'}))

    return html.Div([header] + week_rows, style={
        'border': f'1px solid {COLORS["dark_border"]}',
        'borderRadius': '8px', 'overflow': 'hidden',
        'backgroundColor': COLORS['dark_secondary'],
    })


# ── Shared callbacks ─────────────────────────────────────────────────────────

def register_calendar_callbacks(
    app,
    prefix: str,
    *,
    month_allow_duplicate: bool = False,
    selection_allow_duplicate: bool = False,
) -> None:
    """Wire the three shared calendar callbacks for an id ``prefix`` (``ta``/``oa``).

    - month navigation (``{prefix}-prev-month`` / ``{prefix}-next-month``)
    - multi-select toggle (``{prefix}-cal-match-btn`` pattern + clear button)
    - selection indicator text + clear-button visibility

    ``*_allow_duplicate`` flags are set when another page-specific callback also
    writes the same Store (the opposition page writes the month/selection Stores
    from its data-loading and team-reset callbacks).
    """
    def _month_out(prop):
        return Output(f'{prefix}-calendar-month', prop, allow_duplicate=True) if month_allow_duplicate \
            else Output(f'{prefix}-calendar-month', prop)

    def _label_out():
        return Output(f'{prefix}-month-label', 'children', allow_duplicate=True) if month_allow_duplicate \
            else Output(f'{prefix}-month-label', 'children')

    def _selection_out():
        return Output(f'{prefix}-selected-matches', 'data', allow_duplicate=True) if selection_allow_duplicate \
            else Output(f'{prefix}-selected-matches', 'data')

    # ── Month navigation ──────────────────────────────────────────────────────
    @app.callback(
        _month_out('data'),
        _label_out(),
        Input(f'{prefix}-prev-month', 'n_clicks'),
        Input(f'{prefix}-next-month', 'n_clicks'),
        State(f'{prefix}-calendar-month', 'data'),
        prevent_initial_call=True,
    )
    def navigate_month(prev_clicks, next_clicks, current):
        triggered = ctx.triggered_id
        year, month = current['year'], current['month']
        if triggered == f'{prefix}-prev-month':
            month -= 1
            if month < 1:
                month, year = 12, year - 1
        elif triggered == f'{prefix}-next-month':
            month += 1
            if month > 12:
                month, year = 1, year + 1
        return {'year': year, 'month': month}, f"{calendar.month_name[month]} {year}"

    # ── Toggle match selection ────────────────────────────────────────────────
    @app.callback(
        _selection_out(),
        Input({'type': f'{prefix}-cal-match-btn', 'match_id': ALL}, 'n_clicks'),
        Input(f'{prefix}-clear-selection-btn', 'n_clicks'),
        State(f'{prefix}-selected-matches', 'data'),
        prevent_initial_call=True,
    )
    def update_selected_matches(n_clicks_list, clear_n_clicks, current_matches):
        if not ctx.triggered_id:
            return current_matches or []
        if ctx.triggered_id == f'{prefix}-clear-selection-btn':
            return []
        # Ignore the re-render of freshly-built calendar buttons (n_clicks 0/None).
        trigger = ctx.triggered[0]
        if trigger['value'] is None or trigger['value'] == 0:
            return current_matches or []
        match_id = ctx.triggered_id['match_id']
        current = list(current_matches or [])
        if match_id in current:
            current.remove(match_id)
        else:
            current.append(match_id)
        return current

    # ── Selection indicator ───────────────────────────────────────────────────
    @app.callback(
        Output(f'{prefix}-selected-indicator-text', 'children'),
        Output(f'{prefix}-clear-selection-btn', 'style'),
        Input(f'{prefix}-selected-matches', 'data'),
    )
    def update_selected_indicator(match_ids):
        if not match_ids:
            return (
                html.Div("All Matches (Default)",
                         style={'color': COLORS['text_secondary'], 'fontSize': '0.9rem'}),
                {'display': 'none'},
            )
        count = len(match_ids)
        text = html.Span(
            f"{count} Match{'es' if count > 1 else ''} Selected",
            style={'color': GOLD, 'fontWeight': 'bold', 'marginRight': '12px', 'fontSize': '0.95rem'},
        )
        btn_style = {
            'display': 'inline-block', 'background': 'none',
            'border': f'1px solid {COLORS["dark_border"]}',
            'color': COLORS['text_primary'], 'borderRadius': '4px',
            'padding': '4px 10px', 'cursor': 'pointer', 'fontSize': '0.8rem',
        }
        return text, btn_style
