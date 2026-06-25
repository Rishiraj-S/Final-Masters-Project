"""
Opposition Analysis — Player Analysis tab.

Mirrors the Barça DNA player page (profile, attribute radar, xT heatmap,
shooting / passing / possession / defending / discipline panels) but scoped to
the **selected opposition team** instead of Barcelona, and with **no player
image** (opposition players have no image assets).

Data is loaded via ``load_opp_events`` (team events + opponents' events), so the
tab honours the page-level Competition / Venue / Date / Calendar filters exactly
like every other opposition tab. The radar compares the player against a peer
pool drawn from the team's competition (its domestic league when "All
Competitions" is selected).

  build_player(team, comp_key)        → skeleton layout (called from render_tab)
  register_player_callbacks(app)      → wires the player selector + filters to
                                        every panel
"""

from __future__ import annotations

import json
import logging
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pandas as pd
from dash import html, dcc, Input, Output, no_update
import dash_bootstrap_components as dbc

from utils.config import COLORS
from utils.data_utils import exclude_own_goals
from utils.opposition_data_utils import (
    SEASON,
    load_opp_events,
    get_team_country,
    get_team_competitions,
    get_opp_team_matches,
    competition_match_event_paths,
)
from utils.event_utils import (
    compute_event_stats,
    get_long_balls, get_crosses,
    get_successful_tackles, get_interceptions, get_ball_recoveries,
)
from utils.xg_utils import add_xg_column
from utils.xt_utils import add_xt_column
from utils.player_analysis.metrics import compute_player_stats, compute_5d_scores
from utils.player_analysis.wyscout_weights import DIMENSION_INFO
from page_utils.event_filters import SHOT_TYPES as _SHOT_TYPES
from page_utils.visualizations import render_xt_heatmap_img, HOME_COLOR

# Reuse Barça DNA's pure visual / formatting helpers so the panels render
# identically — only the data source (opposition team vs BAR) differs.
from pages.barca_dna import (
    _radar_figure, _empty_radar,
    _stat_card, _radar_info_row, _bio_row,
    _empty_shot_map, _player_shot_map, _shot_donut, _shot_stat_row,
    _fmt, _scale,
    _passing_donut, _possession_donut, _defending_donut,
    _role_for_position, _roles_for_positions, _mean_stats,
    _RADAR_DIMS, _DIM_TO_5D, _LEAGUE_METRIC_KEYS,
    _card_style, _section_title_style, _label_style, _GOLD,
)

logger = logging.getLogger(__name__)
CURRENT_SEASON = SEASON


# ---------------------------------------------------------------------------
# Competition peer pool (mirrors barca_dna._laliga_player_pool, per competition)
# ---------------------------------------------------------------------------

_CACHE_DIR = Path(__file__).resolve().parent.parent.parent / "logs"
_pool_cache: dict[str, list[dict]] = {}


def _safe_read(path) -> pd.DataFrame | None:
    try:
        return pd.read_parquet(path)
    except Exception:
        return None


def _competition_player_pool(comp_key: str) -> list[dict]:
    """Season-wide players in a competition as ``[{"roles", "stats"}]``.

    Built once per competition (read every match_event parquet → per-player
    stats + Wyscout roles), memoised in-process and persisted to ``logs/`` keyed
    by the file count so a pipeline run that adds matches triggers a rebuild.
    Returns ``[]`` when the competition has no data.
    """
    if not comp_key or comp_key == 'all':
        return []
    if comp_key in _pool_cache:
        return _pool_cache[comp_key]
    try:
        paths = competition_match_event_paths(comp_key)
        if not paths:
            _pool_cache[comp_key] = []
            return []

        sig = f"{CURRENT_SEASON}:v1:{len(paths)}"
        cache_file = _CACHE_DIR / f"opp_player_pool_{comp_key}.json"
        if cache_file.exists():
            try:
                blob = json.loads(cache_file.read_text())
                if blob.get("sig") == sig and blob.get("players"):
                    _pool_cache[comp_key] = blob["players"]
                    return _pool_cache[comp_key]
            except Exception:
                pass

        if len(paths) > 4:
            with ThreadPoolExecutor(max_workers=min(8, len(paths))) as ex:
                frames = list(ex.map(_safe_read, paths))
        else:
            frames = [_safe_read(p) for p in paths]
        frames = [f for f in frames if f is not None and not f.empty]
        if not frames:
            _pool_cache[comp_key] = []
            return []

        ev = pd.concat(frames, ignore_index=True)
        players: list[dict] = []
        for _name, grp in ev.groupby("player_name"):
            s = compute_player_stats(grp)
            if not s:
                continue
            players.append({
                "roles": _roles_for_positions(grp["position"]),
                "stats": {k: s.get(k, 0) for k in _LEAGUE_METRIC_KEYS},
            })

        try:
            _CACHE_DIR.mkdir(exist_ok=True)
            cache_file.write_text(json.dumps({"sig": sig, "players": players}))
        except Exception:
            logger.warning("Could not persist opposition player pool cache", exc_info=True)

        _pool_cache[comp_key] = players
        return players
    except Exception:
        logger.exception("_competition_player_pool failed for %s", comp_key)
        _pool_cache[comp_key] = []
        return []


def _pool_for_roles(pool: list[dict], roles) -> list[dict]:
    """Stat dicts for pool players who played ANY of ``roles``."""
    wanted = set(roles)
    return [p["stats"] for p in pool if wanted.intersection(p.get("roles", []))]


def _cohort_comp(team: str, comp_key: str | None) -> str | None:
    """Competition whose players form the radar peer cohort.

    A specific competition is used as-is; for "All Competitions" the team's
    domestic league is approximated as the competition the *team* played the
    most matches in (a league season has far more team matches than a cup or a
    European run — counting competition-wide files would wrongly pick the
    biggest tournament).
    """
    if comp_key and comp_key != 'all':
        return comp_key
    comps = get_team_competitions(team) if team else []
    if not comps:
        return None
    country = get_team_country(team)

    def _team_match_count(ck: str) -> int:
        try:
            return len(get_opp_team_matches(team, country, ck, CURRENT_SEASON))
        except Exception:
            return 0

    return max(comps, key=_team_match_count)


def _league_label(comp_key: str | None, roles) -> str:
    base = (comp_key or '').replace('_', ' ').strip() or 'League'
    role_str = '/'.join(roles) if roles else ''
    return f"{base} {role_str} avg".strip()


# ---------------------------------------------------------------------------
# Data loading helper
# ---------------------------------------------------------------------------

def _load_player_events(team, comp_key, venue, match_ids, date_cutoff, player):
    """Return (team_ev, opp_ev, p_ev) scoped to the page filters.

    team_ev — the selected opposition team's events.
    opp_ev  — their opponents' events (for goals conceded / xGA / clean sheets).
    p_ev    — team_ev filtered to ``player``.
    """
    if not team or not comp_key or not player:
        empty = pd.DataFrame()
        return empty, empty, empty
    team_ev, opp_ev = load_opp_events(
        team, comp_key, venue or 'all', match_ids, date_cutoff, CURRENT_SEASON,
    )
    if team_ev.empty or 'player_name' not in team_ev.columns:
        return team_ev, opp_ev, pd.DataFrame()
    p_ev = team_ev[team_ev['player_name'] == player]
    return team_ev, opp_ev, p_ev


def _team_players(team, comp_key) -> list[str]:
    """Sorted distinct player names for the team across the (possibly 'all') comp."""
    if not team or not comp_key:
        return []
    try:
        team_ev, _ = load_opp_events(team, comp_key, 'all', None, None, CURRENT_SEASON)
        if team_ev.empty or 'player_name' not in team_ev.columns:
            return []
        return sorted(n for n in team_ev['player_name'].dropna().unique() if str(n).strip())
    except Exception:
        logger.exception("_team_players failed for %s / %s", team, comp_key)
        return []


# ---------------------------------------------------------------------------
# Layout
# ---------------------------------------------------------------------------

def build_player(team: str | None = None, comp_key: str | None = None) -> html.Div:
    """Skeleton layout for the Player Analysis tab (no player image)."""
    if not team:
        return html.P(
            "Select a team to view player analysis.",
            style={'color': COLORS['text_secondary'], 'padding': '2rem 0'},
        )

    players     = _team_players(team, comp_key)
    player_opts = [{'label': n, 'value': n} for n in players]
    init_player = players[0] if players else None

    return html.Div([
        # ── Player selector + view mode ───────────────────────────────────────
        dbc.Row([
            dbc.Col([
                html.Label("PLAYER", style=_label_style),
                dcc.Dropdown(
                    id="oap-player",
                    options=player_opts,
                    value=init_player,
                    clearable=False,
                    placeholder="Select player…",
                    style={"backgroundColor": COLORS["dark_secondary"]},
                ),
            ], md=4, xs=12),
            dbc.Col([
                html.Label("VIEW", style=_label_style),
                dbc.RadioItems(
                    id="oap-display-mode",
                    options=[
                        {"label": "Total",  "value": "total"},
                        {"label": "Per 90", "value": "per90"},
                    ],
                    value="total",
                    className="btn-group",
                    inputClassName="btn-check",
                    labelClassName="btn btn-outline-warning btn-sm",
                    labelCheckedClassName="active",
                    style={"display": "flex"},
                ),
            ], md=3, xs=12, style={"display": "flex", "flexDirection": "column",
                                   "justifyContent": "flex-end"}),
        ], className="mb-4"),

        # ── Section 1: Profile (bio + season stats, no photo) ─────────────────
        dbc.Row([
            dbc.Col(
                dbc.Card([dbc.CardBody([
                    dbc.Row([
                        dbc.Col(html.Div(id="oap-bio"), md=4),
                        dbc.Col(
                            html.Div(style={
                                "borderLeft": f"1px solid {COLORS['dark_border']}",
                                "height": "100%", "minHeight": "80px",
                            }),
                            width="auto", className="d-none d-md-block",
                        ),
                        dbc.Col([
                            html.Div("Season Stats",
                                     style={**_section_title_style, "marginBottom": "10px"}),
                            html.Div(id="oap-season-stats"),
                        ]),
                    ], align="center"),
                ], style={"padding": "18px"})], style=_card_style),
                xs=12, className="mb-3",
            ),
        ], className="mb-3"),

        # ── Section 2: Radar + Heatmap ────────────────────────────────────────
        dbc.Row([
            dbc.Col(
                dbc.Card([dbc.CardBody([
                    html.Div("Attribute Overview", style=_section_title_style),
                    dbc.Row([
                        dbc.Col(
                            dcc.Loading(type="circle", color=_GOLD, children=dcc.Graph(
                                id="oap-radar", config={"displayModeBar": False},
                                style={"height": "420px"}, figure=_empty_radar(),
                            )),
                            md=9, xs=12,
                        ),
                        dbc.Col(
                            html.Div([
                                _radar_info_row("ATT", *DIMENSION_INFO["Attack"]),
                                _radar_info_row("DEF", *DIMENSION_INFO["Defense"]),
                                _radar_info_row("TEC", *DIMENSION_INFO["Technical"]),
                                _radar_info_row("PHY", *DIMENSION_INFO["Physical"]),
                                _radar_info_row("OVR", *DIMENSION_INFO["Overall"]),
                            ], style={"paddingLeft": "8px"}),
                            md=3, xs=12, className="d-flex align-items-center",
                        ),
                    ], align="center"),
                ], style={"padding": "18px"})], style=_card_style),
                md=6, xs=12, className="mb-3",
            ),
            dbc.Col(
                dbc.Card([dbc.CardBody([
                    html.Div("Positional xT Heatmap",
                             style={**_section_title_style, "textTransform": "none"}),
                    dcc.Loading(type="circle", color=_GOLD, children=html.Img(
                        id="oap-heatmap",
                        style={"width": "75%", "borderRadius": "6px",
                               "display": "block", "margin": "0 auto"},
                    )),
                ], style={"padding": "18px"})], style=_card_style),
                md=6, xs=12, className="mb-3",
            ),
        ]),

        # ── Section 3: Shooting ───────────────────────────────────────────────
        dbc.Row([
            dbc.Col(
                dbc.Card([dbc.CardBody([
                    html.Div("Shooting", style=_section_title_style),
                    dbc.Row([
                        dbc.Col(html.Div(id="oap-shot-stats"), md=3, xs=12),
                        dbc.Col(
                            dcc.Loading(type="circle", color=_GOLD, children=dcc.Graph(
                                id="oap-shot-donut", config={"displayModeBar": False},
                                figure=_shot_donut(pd.DataFrame()), style={"height": "300px"},
                            )),
                            md=3, xs=12,
                        ),
                        dbc.Col(
                            dcc.Loading(type="circle", color=_GOLD, children=dcc.Graph(
                                id="oap-shot-map", config={"displayModeBar": False},
                                figure=_empty_shot_map(), style={"height": "340px"},
                            )),
                            md=6, xs=12,
                        ),
                    ], align="start", className="g-2"),
                ], style={"padding": "18px"})], style=_card_style),
                xs=12, className="mb-3",
            ),
        ]),

        # ── Section 4: Passing + Possession ───────────────────────────────────
        dbc.Row([
            dbc.Col(
                dbc.Card([dbc.CardBody([
                    html.Div("Passing", style=_section_title_style),
                    dbc.Row([
                        dbc.Col(html.Div(id="oap-pass-stats"), md=5, xs=12),
                        dbc.Col(
                            dcc.Loading(type="circle", color=_GOLD, children=dcc.Graph(
                                id="oap-pass-donut", config={"displayModeBar": False},
                                figure=_passing_donut(0, 0), style={"height": "280px"},
                            )),
                            md=7, xs=12,
                        ),
                    ], align="center", className="g-2"),
                ], style={"padding": "18px"})], style=_card_style),
                md=6, xs=12, className="mb-3",
            ),
            dbc.Col(
                dbc.Card([dbc.CardBody([
                    html.Div("Possession", style=_section_title_style),
                    dbc.Row([
                        dbc.Col(html.Div(id="oap-poss-stats"), md=5, xs=12),
                        dbc.Col(
                            dcc.Loading(type="circle", color=_GOLD, children=dcc.Graph(
                                id="oap-poss-donut", config={"displayModeBar": False},
                                figure=_possession_donut(0, 0, 0), style={"height": "280px"},
                            )),
                            md=7, xs=12,
                        ),
                    ], align="center", className="g-2"),
                ], style={"padding": "18px"})], style=_card_style),
                md=6, xs=12, className="mb-3",
            ),
        ], className="mb-3"),

        # ── Section 5: Defending + Discipline ─────────────────────────────────
        dbc.Row([
            dbc.Col(
                dbc.Card([dbc.CardBody([
                    html.Div("Defending", style=_section_title_style),
                    dbc.Row([
                        dbc.Col(html.Div(id="oap-def-stats"), md=5, xs=12),
                        dbc.Col(
                            dcc.Loading(type="circle", color=_GOLD, children=dcc.Graph(
                                id="oap-def-donut", config={"displayModeBar": False},
                                figure=_defending_donut(0, 0, 0, 0), style={"height": "280px"},
                            )),
                            md=7, xs=12,
                        ),
                    ], align="center", className="g-2"),
                ], style={"padding": "18px"})], style=_card_style),
                md=8, xs=12, className="mb-3",
            ),
            dbc.Col(
                dbc.Card([dbc.CardBody([
                    html.Div("Discipline", style=_section_title_style),
                    html.Div(id="oap-disc-stats"),
                ], style={"padding": "18px"})], style={**_card_style, "height": "100%"}),
                md=4, xs=12, className="mb-3",
            ),
        ], className="mb-3"),
    ])


# ---------------------------------------------------------------------------
# Callbacks
# ---------------------------------------------------------------------------

def register_player_callbacks(app) -> None:

    # Shared Inputs: player + page-level filters.
    # No active_tab guard needed — oap-player only exists when this tab is
    # rendered, so suppress_callback_exceptions handles cross-tab suppression.
    _COMMON = (
        Input("oap-player",          "value"),
        Input("oa-team-select",      "value"),
        Input("oa-comp-select",      "value"),
        Input("oa-venue-filter",     "value"),
        Input("oa-selected-matches", "data"),
        Input("oa-date-filter",      "date"),
    )

    # ── Profile: bio + season stats ───────────────────────────────────────────
    @app.callback(
        Output("oap-bio",           "children"),
        Output("oap-season-stats",  "children"),
        *_COMMON,
    )
    def update_profile(player, team, comp, venue, match_ids, date_cutoff):
        blank = (html.P("—", style={"color": COLORS["text_secondary"]}),
                 html.P("—", style={"color": COLORS["text_secondary"]}))
        if not player:
            return no_update, no_update
        try:
            _team_ev, _opp_ev, p_ev = _load_player_events(
                team, comp, venue, match_ids, date_cutoff, player)
            if p_ev.empty:
                return blank

            jersey = (
                str(p_ev["Jersey Number"].dropna().iloc[0])
                if "Jersey Number" in p_ev.columns and not p_ev["Jersey Number"].dropna().empty
                else "—"
            )
            position = (
                str(p_ev["position"].dropna().mode().iloc[0])
                if "position" in p_ev.columns and not p_ev["position"].dropna().empty
                else "—"
            )

            bio = html.Div([
                html.Div(player, style={
                    "color": COLORS["text_primary"], "fontSize": "1.4rem",
                    "fontWeight": "700", "marginBottom": "10px", "lineHeight": "1.2",
                }),
                _bio_row("#",      jersey),
                _bio_row("Pos",    position),
                _bio_row("Club",   team),
                _bio_row("Season", CURRENT_SEASON),
            ])

            stats = compute_event_stats(p_ev)
            if not stats:
                return bio, html.P("No stats", style={"color": COLORS["text_secondary"]})

            row1 = html.Div([
                _stat_card("Matches", str(stats.get("apps", 0) or 0)),
                _stat_card("Minutes", str(stats.get("total_minutes", 0) or 0)),
                _stat_card("Yellow",  str(stats.get("yellow_cards", 0) or 0)),
                _stat_card("Red",     str(stats.get("red_cards", 0) or 0)),
            ], style={"display": "flex", "gap": "8px", "marginBottom": "8px", "flexWrap": "wrap"})
            row2 = html.Div([
                _stat_card("Goals",   str(stats.get("goals", 0) or 0)),
                _stat_card("Assists", str(stats.get("assists", 0) or 0)),
            ], style={"display": "flex", "gap": "8px", "flexWrap": "wrap"})

            return bio, html.Div([row1, row2])
        except Exception:
            logger.exception("oap update_profile failed")
            return blank

    # ── Attribute radar ───────────────────────────────────────────────────────
    @app.callback(
        Output("oap-radar", "figure"),
        *_COMMON,
    )
    def update_radar(player, team, comp, venue, match_ids, date_cutoff):
        if not player:
            return no_update
        try:
            _team_ev, _opp_ev, p_ev = _load_player_events(
                team, comp, venue, match_ids, date_cutoff, player)
            if p_ev.empty:
                return _empty_radar()

            player_stats = compute_player_stats(p_ev)
            if not player_stats:
                return _empty_radar()

            roles = _roles_for_positions(p_ev["position"]) if "position" in p_ev.columns else []
            valid_pos = p_ev["position"].dropna() if "position" in p_ev.columns else pd.Series(dtype=object)
            valid_pos = valid_pos[valid_pos != "N/A"]
            primary_role = _role_for_position(
                valid_pos.mode().iloc[0] if not valid_pos.empty else None)

            cohort = _cohort_comp(team, comp)
            pool   = _pool_for_roles(_competition_player_pool(cohort), roles) if cohort else []
            if not pool:
                pool = [player_stats]

            p5     = compute_5d_scores(player_stats, pool, primary_role)
            scores = {dim: p5[_DIM_TO_5D[dim]] for dim in _RADAR_DIMS}

            league_scores = None
            if len(pool) > 1:
                l5 = compute_5d_scores(_mean_stats(pool), pool, primary_role)
                league_scores = {dim: l5[_DIM_TO_5D[dim]] for dim in _RADAR_DIMS}

            return _radar_figure(
                scores, league_scores=league_scores,
                player_label=player, league_label=_league_label(cohort, roles),
            )
        except Exception:
            logger.exception("oap update_radar failed")
            return _empty_radar()

    # ── Positional xT heatmap ─────────────────────────────────────────────────
    @app.callback(
        Output("oap-heatmap", "src"),
        *_COMMON,
    )
    def update_heatmap(player, team, comp, venue, match_ids, date_cutoff):
        if not player:
            return no_update
        try:
            _team_ev, _opp_ev, p_ev = _load_player_events(
                team, comp, venue, match_ids, date_cutoff, player)
            if p_ev.empty:
                return no_update

            passes = p_ev[p_ev["event_type"] == "Pass"].dropna(
                subset=["x", "y", "Pass End X", "Pass End Y"]
            ).copy()
            if len(passes) < 3:
                return no_update

            passes = add_xt_column(passes)
            return render_xt_heatmap_img(
                passes["x"].tolist(), passes["y"].tolist(), passes["xT"].tolist())
        except Exception:
            logger.exception("oap update_heatmap failed")
            return no_update

    # ── Shooting panel ────────────────────────────────────────────────────────
    @app.callback(
        Output("oap-shot-stats", "children"),
        Output("oap-shot-donut", "figure"),
        Output("oap-shot-map",   "figure"),
        *_COMMON,
        Input("oap-display-mode", "value"),
    )
    def update_shooting_panel(player, team, comp, venue, match_ids, date_cutoff,
                              display_mode):
        p90 = display_mode == "per90"
        _empty = (html.P("—", style={"color": COLORS["text_secondary"]}),
                  _shot_donut(pd.DataFrame()), _empty_shot_map())
        if not player:
            return no_update, no_update, no_update
        try:
            _team_ev, _opp_ev, p_ev = _load_player_events(
                team, comp, venue, match_ids, date_cutoff, player)
            if p_ev.empty:
                return _empty

            shots = exclude_own_goals(
                p_ev[p_ev["event_type"].isin(_SHOT_TYPES)].copy()
            ).dropna(subset=["x", "y"])
            if shots.empty:
                return _empty

            shots = add_xg_column(shots)
            stats = compute_event_stats(p_ev)
            mins  = float(stats.get("total_minutes", 1) or 1)

            goals     = int((shots["event_type"] == "Goal").sum())
            xg        = round(shots["xg"].sum(), 2) if "xg" in shots.columns else 0.0
            total     = len(shots)
            on_tgt    = int(shots["event_type"].isin(["Goal", "Saved Shot"]).sum())
            pen_mask  = (shots["Penalty"].eq("Si") if "Penalty" in shots.columns
                         else pd.Series(False, index=shots.index))
            pen_goals = int((shots["event_type"] == "Goal")[pen_mask].sum())
            np_xg     = round(shots.loc[~pen_mask, "xg"].sum(), 2) if "xg" in shots.columns else 0.0

            stats_children = html.Div([
                _shot_stat_row("Goals",           _fmt(_scale(goals,     mins, p90), p90), "#51cf66"),
                _shot_stat_row("xG",              f"{_scale(xg,    mins, p90):.2f}", _GOLD),
                _shot_stat_row("Penalty Goals",   _fmt(_scale(pen_goals, mins, p90), p90)),
                _shot_stat_row("Non-penalty xG",  f"{_scale(np_xg, mins, p90):.2f}", HOME_COLOR),
                _shot_stat_row("Shots",           _fmt(_scale(total,     mins, p90), p90)),
                _shot_stat_row("Shots on Target", _fmt(_scale(on_tgt,    mins, p90), p90), "#339af0"),
            ])
            return stats_children, _shot_donut(shots), _player_shot_map(shots)
        except Exception:
            logger.exception("oap update_shooting_panel failed")
            return _empty

    # ── Passing + Possession panels ───────────────────────────────────────────
    @app.callback(
        Output("oap-pass-stats", "children"),
        Output("oap-pass-donut", "figure"),
        Output("oap-poss-stats", "children"),
        Output("oap-poss-donut", "figure"),
        *_COMMON,
        Input("oap-display-mode", "value"),
    )
    def update_pass_poss_panels(player, team, comp, venue, match_ids, date_cutoff,
                                display_mode):
        p90 = display_mode == "per90"
        _empty_pass = html.P("—", style={"color": COLORS["text_secondary"]})
        _empty_out = (_empty_pass, _passing_donut(0, 0), _empty_pass, _possession_donut(0, 0, 0))
        if not player:
            return no_update, no_update, no_update, no_update
        try:
            team_ev, _opp_ev, p_ev = _load_player_events(
                team, comp, venue, match_ids, date_cutoff, player)
            if p_ev.empty:
                return _empty_out

            stats = compute_event_stats(p_ev)
            if not stats:
                return _empty_out
            mins = float(stats.get("total_minutes", 1) or 1)

            # ── Passing ───────────────────────────────────────────────────────
            passes   = int(stats.get("passes", 0) or 0)
            pass_acc = float(stats.get("pass_acc", 0) or 0)
            accurate   = round(passes * pass_acc / 100)
            inaccurate = passes - accurate

            lb_acc = float(stats.get("long_ball_acc", 0) or 0)
            cr_acc = float(stats.get("cross_acc", 0)   or 0)
            kp     = int(stats.get("key_passes", 0)    or 0)
            ast    = int(stats.get("assists", 0)        or 0)

            # xA — xG of shots immediately following this player's passes, within
            # the team's own event stream (sorted per match).
            sort_cols = [c for c in ["match_id", "period_id", "time_min", "time_sec"]
                         if c in team_ev.columns]
            te = team_ev.sort_values(sort_cols).reset_index(drop=True) if sort_cols else team_ev.reset_index(drop=True)
            _is_shot = te["event_type"].isin(_SHOT_TYPES) & te["x"].notna()
            _xg_col  = pd.Series(0.0, index=te.index)
            if _is_shot.any():
                _shot_xg = add_xg_column(te[_is_shot].copy())
                _xg_col.loc[_shot_xg.index] = _shot_xg["xg"].fillna(0.0)
            _next_type  = te["event_type"].shift(-1)
            _next_xg    = _xg_col.shift(-1, fill_value=0.0)
            _same_match = (
                te["match_id"] == te["match_id"].shift(-1, fill_value=-1)
                if "match_id" in te.columns else pd.Series(True, index=te.index)
            )
            _xa_mask = (
                (te["event_type"] == "Pass") & _next_type.isin(_SHOT_TYPES) &
                _same_match & (te["player_name"] == player)
            )
            xa = round(float(_next_xg[_xa_mask].sum()), 2)

            _is_bc = (
                te["event_type"].isin(_SHOT_TYPES) &
                (te["Big Chance"].eq("Si") if "Big Chance" in te.columns
                 else pd.Series(False, index=te.index))
            )
            _bc_mask = (
                (te["event_type"] == "Pass") & _is_bc.shift(-1, fill_value=False) &
                _same_match & (te["player_name"] == player)
            )
            big_chances_created = int(_bc_mask.sum())

            lb_rows = get_long_balls(p_ev)
            acc_lb  = int(lb_rows["outcome"].eq(1).sum()) if not lb_rows.empty else 0
            cr_rows = get_crosses(p_ev)
            acc_cr  = int(cr_rows["outcome"].eq(1).sum()) if not cr_rows.empty else 0

            pass_stats = html.Div([
                _shot_stat_row("Assists",             _fmt(_scale(ast,                 mins, p90), p90), _GOLD),
                _shot_stat_row("xA",                  f"{_scale(xa, mins, p90):.2f}", HOME_COLOR),
                _shot_stat_row("Successful Passes",   _fmt(_scale(accurate,            mins, p90), p90)),
                _shot_stat_row("Successful Passes %", _fmt(pass_acc, p90, pct=True),              "#51cf66"),
                _shot_stat_row("Accurate Long Balls", _fmt(_scale(acc_lb,              mins, p90), p90)),
                _shot_stat_row("Accurate LB %",       _fmt(lb_acc,  p90, pct=True)),
                _shot_stat_row("Chances Created",     _fmt(_scale(kp,                  mins, p90), p90), _GOLD),
                _shot_stat_row("Big Chances Created", _fmt(_scale(big_chances_created, mins, p90), p90), _GOLD),
                _shot_stat_row("Successful Crosses",  _fmt(_scale(acc_cr,              mins, p90), p90)),
                _shot_stat_row("Successful Cross %",  _fmt(cr_acc,  p90, pct=True)),
            ])

            # ── Possession ────────────────────────────────────────────────────
            take_ons  = int(stats.get("take_ons", 0)        or 0)
            to_pct    = float(stats.get("takeon_pct", 0)    or 0)
            succ_drib = round(take_ons * to_pct / 100)
            duel_pct  = float(stats.get("duel_pct", 0)      or 0)
            aerials   = int(stats.get("aerials", 0)          or 0)
            aer_pct   = float(stats.get("aerial_win_pct", 0) or 0)
            aer_won   = round(aerials * aer_pct / 100)
            duels_won = aer_won + succ_drib
            touches   = int(stats.get("touches", 0)          or 0)
            dispos    = int(stats.get("dispossessions", 0)   or 0)
            pen_fouls = int(stats.get("penalty_fouls", 0)    or 0)

            x_num = pd.to_numeric(p_ev["x"], errors="coerce")
            y_num = pd.to_numeric(p_ev["y"], errors="coerce")
            touches_box = int(((x_num >= 83) & (y_num >= 21.1) & (y_num <= 78.9)).sum())

            # Fouls won = the outcome==1 (fouled) rows of the double-logged foul.
            _foul_rows    = p_ev[p_ev["event_type"] == "Foul"]
            _foul_outcome = pd.to_numeric(_foul_rows["outcome"], errors="coerce")
            fouls_won     = int((_foul_outcome == 1).sum())

            poss_stats = html.Div([
                _shot_stat_row("Successful Dribbles",   _fmt(_scale(succ_drib,   mins, p90), p90), "#51cf66"),
                _shot_stat_row("Successful Dribbles %", _fmt(to_pct,   p90, pct=True),            "#51cf66"),
                _shot_stat_row("Duels Won",             _fmt(_scale(duels_won,   mins, p90), p90)),
                _shot_stat_row("Duels Won %",           _fmt(duel_pct, p90, pct=True)),
                _shot_stat_row("Touches",               _fmt(_scale(touches,     mins, p90), p90)),
                _shot_stat_row("Touches in Opp Box",    _fmt(_scale(touches_box, mins, p90), p90), _GOLD),
                _shot_stat_row("Dispossessed",          _fmt(_scale(dispos,      mins, p90), p90), "#ff6b6b"),
                _shot_stat_row("Fouls Won",             _fmt(_scale(fouls_won,   mins, p90), p90)),
                _shot_stat_row("Penalties Awarded",     _fmt(_scale(pen_fouls,   mins, p90), p90)),
            ])

            x_vals = x_num.dropna()
            def_t = int((x_vals < 33.33).sum())
            mid_t = int(((x_vals >= 33.33) & (x_vals <= 66.67)).sum())
            att_t = int((x_vals > 66.67).sum())

            return (pass_stats, _passing_donut(accurate, inaccurate),
                    poss_stats, _possession_donut(def_t, mid_t, att_t))
        except Exception:
            logger.exception("oap update_pass_poss_panels failed")
            return _empty_out

    # ── Defending panel ───────────────────────────────────────────────────────
    @app.callback(
        Output("oap-def-stats", "children"),
        Output("oap-def-donut", "figure"),
        *_COMMON,
        Input("oap-display-mode", "value"),
    )
    def update_defending_panel(player, team, comp, venue, match_ids, date_cutoff,
                               display_mode):
        p90 = display_mode == "per90"
        _empty = (html.P("—", style={"color": COLORS["text_secondary"]}),
                  _defending_donut(0, 0, 0, 0))
        if not player:
            return no_update, no_update
        try:
            _team_ev, opp_ev, p_ev = _load_player_events(
                team, comp, venue, match_ids, date_cutoff, player)
            if p_ev.empty:
                return _empty

            stats = compute_event_stats(p_ev)
            if not stats:
                return _empty

            apps = int(p_ev["match_id"].nunique()) if "match_id" in p_ev.columns else 1
            apps = apps or 1
            mins = float(stats.get("total_minutes", 1) or 1)

            tackles    = int(stats.get("tackles", 0)        or 0)
            intercepts = round((stats.get("intercepts_app", 0) or 0) * apps)
            recoveries = round((stats.get("recoveries_app", 0) or 0) * apps)
            clearances = round((stats.get("clearances_app", 0) or 0) * apps)
            fouls      = int(stats.get("fouls", 0)           or 0)
            def_contribs = tackles + intercepts + recoveries + clearances

            # Possession won in the final third (x > 66.67).
            x_num = pd.to_numeric(p_ev["x"], errors="coerce")
            _st = get_successful_tackles(p_ev)
            succ_tackles_ft = int((pd.to_numeric(_st["x"], errors="coerce") > 66.67).sum()) if not _st.empty else 0
            _rec = get_ball_recoveries(p_ev)
            recov_ft = int((x_num.reindex(_rec.index) > 66.67).sum()) if not _rec.empty else 0
            _int = get_interceptions(p_ev)
            intcpt_ft = int((x_num.reindex(_int.index) > 66.67).sum()) if not _int.empty else 0
            pwft3 = succ_tackles_ft + recov_ft + intcpt_ft

            # Opponent data over the player's matches → goals conceded / xGA / CS.
            pmids = set(p_ev["match_id"].unique()) if "match_id" in p_ev.columns else set()
            opp_p = (opp_ev[opp_ev["match_id"].isin(pmids)]
                     if not opp_ev.empty and "match_id" in opp_ev.columns else opp_ev)
            opp_goals = int((opp_p["event_type"] == "Goal").sum()) if not opp_p.empty else 0
            clean_sheets = sum(
                1 for mid in pmids
                if not opp_p.empty and int((opp_p[opp_p["match_id"] == mid]["event_type"] == "Goal").sum()) == 0
            )
            opp_shots = opp_p[opp_p["event_type"].isin(_SHOT_TYPES)].copy() if not opp_p.empty else pd.DataFrame()
            if not opp_shots.empty:
                opp_shots = add_xg_column(opp_shots)
                xg_against = round(opp_shots["xg"].sum(), 2) if "xg" in opp_shots.columns else 0.0
            else:
                xg_against = 0.0

            def_stats = html.Div([
                _shot_stat_row("Def. Contributions", _fmt(_scale(def_contribs, mins, p90), p90), _GOLD),
                _shot_stat_row("Tackles",            _fmt(_scale(tackles,      mins, p90), p90)),
                _shot_stat_row("Interceptions",      _fmt(_scale(intercepts,   mins, p90), p90), "#339af0"),
                _shot_stat_row("Fouls Committed",    _fmt(_scale(fouls,        mins, p90), p90)),
                _shot_stat_row("Recoveries",         _fmt(_scale(recoveries,   mins, p90), p90), "#ffd43b"),
                _shot_stat_row("Poss. Won Final 3rd",_fmt(_scale(pwft3,        mins, p90), p90), "#51cf66"),
                _shot_stat_row("Dribbled Past",      "—"),
                _shot_stat_row("Clearances",         _fmt(_scale(clearances,   mins, p90), p90), "#cc5de8"),
                _shot_stat_row("Clean Sheets",       str(clean_sheets),                          "#51cf66"),
                _shot_stat_row("Goals Conceded",     _fmt(_scale(opp_goals,    mins, p90), p90), "#ff6b6b"),
                _shot_stat_row("xG AGAINST",         _fmt(_scale(xg_against,   mins, p90), p90), HOME_COLOR),
            ])
            return def_stats, _defending_donut(tackles, intercepts, recoveries, clearances)
        except Exception:
            logger.exception("oap update_defending_panel failed")
            return _empty

    # ── Discipline panel ──────────────────────────────────────────────────────
    @app.callback(
        Output("oap-disc-stats", "children"),
        *_COMMON,
    )
    def update_discipline_panel(player, team, comp, venue, match_ids, date_cutoff):
        _empty = html.P("—", style={"color": COLORS["text_secondary"]})
        if not player:
            return no_update
        try:
            _team_ev, _opp_ev, p_ev = _load_player_events(
                team, comp, venue, match_ids, date_cutoff, player)
            if p_ev.empty:
                return _empty

            stats = compute_event_stats(p_ev)
            if not stats:
                return _empty

            yellows = int(stats.get("yellow_cards", 0) or 0)
            reds    = int(stats.get("red_cards", 0)    or 0)

            def _draw_card(color, count):
                return html.Div([
                    html.Div(str(count), style={
                        "color": "white" if color == "#E8003D" else "#1a1a1a",
                        "fontWeight": "900", "fontSize": "63px", "lineHeight": "1",
                    }),
                ], style={
                    "width": "120px", "height": "171px", "backgroundColor": color,
                    "borderRadius": "11px", "display": "flex", "alignItems": "center",
                    "justifyContent": "center", "boxShadow": "2px 3px 8px rgba(0,0,0,0.5)",
                    "margin": "0 16px",
                })

            return html.Div([
                html.Div([
                    html.Div([
                        _draw_card("#FFD700", yellows),
                        html.Div("Yellow", style={"color": COLORS["text_secondary"], "fontSize": "11px",
                                                  "marginTop": "6px", "textAlign": "center"}),
                    ], style={"display": "flex", "flexDirection": "column", "alignItems": "center"}),
                    html.Div([
                        _draw_card("#E8003D", reds),
                        html.Div("Red", style={"color": COLORS["text_secondary"], "fontSize": "11px",
                                               "marginTop": "6px", "textAlign": "center"}),
                    ], style={"display": "flex", "flexDirection": "column", "alignItems": "center"}),
                ], style={"display": "flex", "flexDirection": "row", "justifyContent": "center",
                          "alignItems": "flex-start", "paddingTop": "16px"}),
            ])
        except Exception:
            logger.exception("oap update_discipline_panel failed")
            return _empty
