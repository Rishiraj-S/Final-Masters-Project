"""
Season Summary tab — match history table + recent form strip.
"""

from dash import html
import dash_bootstrap_components as dbc

from utils.config import COLORS
from utils.opposition_data_utils import get_opp_team_matches
from pages.match_analysis_tabs.shared import section_card
from .helpers import no_data

CURRENT_SEASON = "2025-2026"

_RESULT_BG   = {"W": "#1a5c2a", "D": "#5c4a1a", "L": "#5c1a1a"}
_BADGE_COLOR = {"W": "success",  "D": "warning",  "L": "danger"}


def _form_strip(results: list[dict], n: int = 10) -> html.Div:
    """Coloured W/D/L badges for the last n matches. Hover shows detail."""
    badges = [
        dbc.Badge(
            r["result"],
            color=_BADGE_COLOR[r["result"]],
            className="me-1",
            title=f"{str(r['date'])[:10]}  vs {r['opponent']}  {r['gf']}–{r['ga']}  ({r['competition']})",
        )
        for r in results[:n]
    ]
    if not badges:
        return html.Span("–", style={"color": COLORS["text_secondary"]})
    return html.Div(badges, style={"fontSize": "1.1rem"})


def _stat_pill(label: str, value: str) -> html.Span:
    return html.Span([
        html.Span(label, style={"color": COLORS["text_secondary"], "fontSize": "0.78rem", "marginRight": "4px"}),
        html.Span(value, style={"color": COLORS["text_primary"], "fontWeight": "bold", "fontSize": "0.9rem"}),
    ], style={
        "background": "#1E2139",
        "border": f"1px solid {COLORS['dark_border']}",
        "borderRadius": "6px",
        "padding": "4px 10px",
        "marginRight": "8px",
        "display": "inline-block",
    })


def _season_stats(results: list[dict]) -> html.Div:
    wins   = sum(1 for r in results if r["result"] == "W")
    draws  = sum(1 for r in results if r["result"] == "D")
    losses = sum(1 for r in results if r["result"] == "L")
    gf     = sum(r["gf"] for r in results)
    ga     = sum(r["ga"] for r in results)
    n      = len(results)
    ppg    = round((wins * 3 + draws) / n, 2) if n else 0

    return html.Div([
        _stat_pill("P", str(n)),
        _stat_pill("W", str(wins)),
        _stat_pill("D", str(draws)),
        _stat_pill("L", str(losses)),
        _stat_pill("GF", str(gf)),
        _stat_pill("GA", str(ga)),
        _stat_pill("GD", f"{gf - ga:+d}"),
        _stat_pill("PPG", str(ppg)),
    ], style={"marginBottom": "0.5rem"})


def build_summary(team: str, country: str, competition: str,
                  date_cutoff: str | None = None) -> html.Div:
    results = get_opp_team_matches(team, country, competition, CURRENT_SEASON)
    if not results:
        return no_data(f"No matches found for {team}.")

    # Apply date filter
    if date_cutoff:
        cutoff = date_cutoff[:10]
        results = [r for r in results if str(r.get("date", ""))[:10] <= cutoff]

    if not results:
        return no_data(f"No matches found for {team} up to {date_cutoff[:10]}.")

    stats_card = section_card("Season Statistics", _season_stats(results))
    form_card  = section_card("Recent Form (last 10)", _form_strip(results))

    rows = []
    for r in results:
        venue      = dbc.Badge("Home" if r["is_home"] else "Away",
                               color="primary" if r["is_home"] else "secondary",
                               className="me-1")
        result_col = dbc.Badge(r["result"], color=_BADGE_COLOR[r["result"]])
        score_str  = f"{r['gf']} – {r['ga']}"
        # Highlight scoreline colour based on result
        score_style = {
            "fontWeight": "bold",
            "textAlign": "center",
            "color": {
                "W": "#4caf50",
                "D": "#ffc107",
                "L": "#ef5350",
            }.get(r["result"], COLORS["text_primary"]),
        }
        rows.append(html.Tr([
            html.Td(str(r["date"])[:10],
                    style={"color": COLORS["text_secondary"], "fontSize": "0.85rem",
                           "whiteSpace": "nowrap"}),
            html.Td(r["competition"],
                    style={"fontSize": "0.78rem", "color": COLORS["text_secondary"]}),
            html.Td(venue),
            html.Td(r["opponent"], style={"fontWeight": "500"}),
            html.Td(score_str, style=score_style),
            html.Td(result_col),
        ], style={"backgroundColor": _RESULT_BG.get(r["result"], "transparent")}))

    table = section_card("Match History", html.Table([
        html.Thead(html.Tr([
            html.Th("Date"), html.Th("Competition"), html.Th("Venue"),
            html.Th("Opponent"),
            html.Th("Score", style={"textAlign": "center"}),
            html.Th("Result"),
        ])),
        html.Tbody(rows),
    ], className="table table-dark table-sm table-hover"))

    return html.Div([stats_card, form_card, table])
