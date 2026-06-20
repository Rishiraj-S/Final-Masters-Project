"""
CuléVision — Canonical event-level helpers.

All functions are **pure**: they accept a DataFrame and return either a
filtered DataFrame or a scalar.  They never load data from disk — that is
``utils/data_utils.py``'s job.

Naming conventions
------------------
``get_*``   → filtered DataFrame  (original index preserved unless noted)
``count_*`` → int
``pct_*``   → float, percentage in 0-100 range

Data-encoding facts (confirmed from parquet inspection)
--------------------------------------------------------
Boolean qualifier flags  : ``'Si'`` (present)  /  ``'N/A'`` (absent)
``Assist`` qualifier on passes (numeric string):
    ``'13'`` → assisted a Miss       → key pass
    ``'14'`` → assisted a Post       → key pass
    ``'15'`` → assisted a Saved Shot → key pass
    ``'16'`` → assisted a Goal       → goal assist
``outcome`` column       : ``1`` (success) / ``0`` (failure), stored as int
``own goal`` qualifier   : always ``'N/A'`` in practice — own goals are
    identified by the scoring player's ``team_code`` differing from the
    team under analysis, NOT by this qualifier.
``Ball recovery``        : lowercase ``r`` — ``'Ball recovery'``
``Leading to attempt`` / ``Leading to goal`` on passes: always ``'N/A'``;
    these qualifiers appear on **Error** events (type 51) as related event IDs.
"""

from __future__ import annotations

import pandas as pd


# ---------------------------------------------------------------------------
# Internal qualifier helpers
# ---------------------------------------------------------------------------

def _flag(series: pd.Series) -> pd.Series:
    """Boolean mask: True where qualifier value is ``'Si'``.

    Cast to ``str`` first so the check is robust against schema drift — if a
    qualifier column is ever stored as bool/int rather than the canonical
    ``'Si'``/``'N/A'`` strings, a raw ``== 'Si'`` would silently return all-False.
    """
    return series.astype(str) == "Si"


def _numeric(series: pd.Series) -> pd.Series:
    """Convert a qualifier column to numeric, coercing ``'N/A'`` to NaN."""
    return pd.to_numeric(series, errors="coerce")


# ---------------------------------------------------------------------------
# Event-type selectors
# ---------------------------------------------------------------------------

# Event types present in data (full list in CLAUDE.md).
SHOT_TYPES: frozenset[str] = frozenset({"Miss", "Saved Shot", "Goal", "Post"})
SHOT_TYPES_WITH_BLOCKED: frozenset[str] = frozenset(SHOT_TYPES | {"Blocked Shot"})
ON_TARGET_TYPES: frozenset[str] = frozenset({"Saved Shot", "Goal"})


def get_passes(events: pd.DataFrame) -> pd.DataFrame:
    """All pass events (event_type == 'Pass')."""
    return events[events["event_type"] == "Pass"]


def get_shots(events: pd.DataFrame, *, include_blocked: bool = False) -> pd.DataFrame:
    """Shot events: Miss, Saved Shot, Goal, Post — and optionally Blocked Shot.

    Does NOT exclude own goals; call ``exclude_own_goals`` first if needed.
    """
    types = SHOT_TYPES_WITH_BLOCKED if include_blocked else SHOT_TYPES
    return events[events["event_type"].isin(types)]


def get_shots_on_target(events: pd.DataFrame) -> pd.DataFrame:
    """Shots on target: Saved Shot + Goal."""
    return events[events["event_type"].isin(ON_TARGET_TYPES)]


def get_goals(events: pd.DataFrame) -> pd.DataFrame:
    """All Goal events regardless of team.

    To get Barcelona goals only: filter ``team_code == 'BAR'`` beforehand.
    To exclude opponent goals: filter by team_code before calling.
    """
    return events[events["event_type"] == "Goal"]


def get_tackles(events: pd.DataFrame) -> pd.DataFrame:
    """All Tackle events."""
    return events[events["event_type"] == "Tackle"]


def get_successful_tackles(events: pd.DataFrame) -> pd.DataFrame:
    """Tackles won (outcome == 1)."""
    tackles = get_tackles(events)
    return tackles[tackles["outcome"] == 1]


def get_interceptions(events: pd.DataFrame) -> pd.DataFrame:
    """Interception events (outcome is always 1)."""
    return events[events["event_type"] == "Interception"]


def get_ball_recoveries(events: pd.DataFrame) -> pd.DataFrame:
    """Ball recovery events (outcome is always 1).

    Note: event_type is ``'Ball recovery'`` with a lowercase ``r``.
    """
    return events[events["event_type"] == "Ball recovery"]


def get_ball_gains(events: pd.DataFrame) -> pd.DataFrame:
    """Possession-winning actions: ball recoveries + interceptions + won tackles.

    Single source of truth for "ball gains" used by transition/possession radar
    metrics. Uses the canonical Opta spellings (``'Ball recovery'`` lowercase r,
    ``'Tackle'`` with ``outcome == 1``) so callers never hardcode event_type
    strings. The three subsets are disjoint by event_type, so a plain concat
    introduces no duplicate rows.
    """
    return pd.concat([
        get_ball_recoveries(events),
        get_interceptions(events),
        get_successful_tackles(events),
    ])


def get_clearances(events: pd.DataFrame) -> pd.DataFrame:
    """Clearance events."""
    return events[events["event_type"] == "Clearance"]


def get_aerials(events: pd.DataFrame) -> pd.DataFrame:
    """Aerial duel events."""
    return events[events["event_type"] == "Aerial"]


def get_aerial_wins(events: pd.DataFrame) -> pd.DataFrame:
    """Aerial duels won (outcome == 1)."""
    return get_aerials(events).pipe(lambda df: df[df["outcome"] == 1])


def get_take_ons(events: pd.DataFrame) -> pd.DataFrame:
    """Take On (dribble attempt) events."""
    return events[events["event_type"] == "Take On"]


def get_successful_take_ons(events: pd.DataFrame) -> pd.DataFrame:
    """Take Ons where the dribble succeeded (outcome == 1)."""
    return get_take_ons(events).pipe(lambda df: df[df["outcome"] == 1])


def get_challenges(events: pd.DataFrame) -> pd.DataFrame:
    """Challenge events (ground duels)."""
    return events[events["event_type"] == "Challenge"]


def get_successful_challenges(events: pd.DataFrame) -> pd.DataFrame:
    """Challenges won (outcome == 1)."""
    return get_challenges(events).pipe(lambda df: df[df["outcome"] == 1])


def get_fouls(events: pd.DataFrame) -> pd.DataFrame:
    """All Foul event rows (both committed and won).

    NOTE: Opta double-logs every foul — one row per team. Use
    ``get_fouls_committed`` / ``get_fouls_won`` for a directional count; raw
    ``len(get_fouls(...))`` over-counts a team's fouls ~2× by including the
    won-side rows.
    """
    return events[events["event_type"] == "Foul"]


def get_fouls_committed(events: pd.DataFrame) -> pd.DataFrame:
    """Fouls committed by the acting player/team (outcome != 1).

    Each foul is double-logged: the committing player's row carries
    ``outcome == 0`` and the fouled (foul-winning) player's row carries
    ``outcome == 1``. This was verified empirically — the ``outcome == 1``
    team always takes the ensuing free kick. ``!= 1`` (rather than ``== 0``)
    keeps single-logged legacy rows whose outcome may be NaN.
    """
    fouls = get_fouls(events)
    if "outcome" not in fouls.columns:
        return fouls
    return fouls[_numeric(fouls["outcome"]) != 1]


def get_fouls_won(events: pd.DataFrame) -> pd.DataFrame:
    """Fouls won (player was fouled / team awarded the free kick; outcome == 1).

    See ``get_fouls_committed`` for the double-logging convention.
    """
    fouls = get_fouls(events)
    if "outcome" not in fouls.columns:
        return fouls.iloc[0:0]
    return fouls[_numeric(fouls["outcome"]) == 1]


def get_penalty_fouls(events: pd.DataFrame) -> pd.DataFrame:
    """Foul events with Penalty qualifier == 'Si'.

    Note: penalty incidents are double-logged — one row for each team.
    The caller is responsible for pre-filtering to the team of interest.
    """
    fouls = get_fouls(events)
    if "Penalty" not in fouls.columns:
        return fouls.iloc[0:0]
    return fouls[_flag(fouls["Penalty"])]


def get_cards(events: pd.DataFrame) -> pd.DataFrame:
    """All Card events."""
    return events[events["event_type"] == "Card"]


def get_yellow_cards(events: pd.DataFrame) -> pd.DataFrame:
    """Yellow card events (Yellow Card == 'Si', excludes second yellows)."""
    cards = get_cards(events)
    if "Yellow Card" not in cards.columns:
        return cards.iloc[0:0]
    return cards[_flag(cards["Yellow Card"])]


def get_second_yellow_cards(events: pd.DataFrame) -> pd.DataFrame:
    """Second yellow card events."""
    cards = get_cards(events)
    if "Second yellow" not in cards.columns:
        return cards.iloc[0:0]
    return cards[_flag(cards["Second yellow"])]


def get_red_cards(events: pd.DataFrame) -> pd.DataFrame:
    """Straight red card events (Red Card == 'Si')."""
    cards = get_cards(events)
    if "Red Card" not in cards.columns:
        return cards.iloc[0:0]
    return cards[_flag(cards["Red Card"])]


def get_errors(events: pd.DataFrame) -> pd.DataFrame:
    """Error events (type 51).

    The ``Leading to attempt`` and ``Leading to goal`` columns on these rows
    contain the related shot event ID (a number string), not a boolean.
    """
    return events[events["event_type"] == "Error"]


def get_dispossessions(events: pd.DataFrame) -> pd.DataFrame:
    """Dispossessed events — ball lost under pressure."""
    return events[events["event_type"] == "Dispossessed"]


def get_touches(events: pd.DataFrame) -> pd.DataFrame:
    """Approximate 'touches' — all events except non-touch administrative types."""
    exclude = frozenset({
        "Card", "Offside Pass", "Offside provoked", "Deleted event",
        "Start", "End", "Start delay", "End delay", "Team setp up",
        "Formation change", "Player Off", "Player on",
        "Injury Time Announcement", "Corner Awarded",
        "Referee Drop Ball", "Contentious referee decision",
        "Delayed Start", "Post match complete",
    })
    return events[~events["event_type"].isin(exclude)]


def get_corners(events: pd.DataFrame) -> pd.DataFrame:
    """Corner Awarded events."""
    return events[events["event_type"] == "Corner Awarded"]


def get_saves(events: pd.DataFrame) -> pd.DataFrame:
    """Goalkeeper Save events (event_type == 'Save')."""
    return events[events["event_type"] == "Save"]


# ---------------------------------------------------------------------------
# Pass sub-type selectors (all accept a passes DataFrame or full events)
# ---------------------------------------------------------------------------

def get_accurate_passes(events: pd.DataFrame) -> pd.DataFrame:
    """Accurate passes (event_type == 'Pass', outcome == 1)."""
    passes = get_passes(events)
    return passes[passes["outcome"] == 1]


def get_goal_assists(events: pd.DataFrame) -> pd.DataFrame:
    """Passes that directly assisted a goal (Assist qualifier == '16' / 16).

    These passes always have outcome == 1.
    """
    passes = get_passes(events)
    if "Assist" not in passes.columns:
        return passes.iloc[0:0]
    return passes[_numeric(passes["Assist"]) == 16]


def get_key_passes(events: pd.DataFrame) -> pd.DataFrame:
    """Passes that assisted a non-goal shot (Assist in [13, 14, 15]).

    13 = assisted Miss, 14 = assisted Post, 15 = assisted Saved Shot.
    These are key passes (created a chance but no goal).
    """
    passes = get_passes(events)
    if "Assist" not in passes.columns:
        return passes.iloc[0:0]
    return passes[_numeric(passes["Assist"]).isin([13, 14, 15])]


def get_any_assist_passes(events: pd.DataFrame) -> pd.DataFrame:
    """Passes that assisted any shot (goal assists + key passes, Assist in [13-16])."""
    passes = get_passes(events)
    if "Assist" not in passes.columns:
        return passes.iloc[0:0]
    return passes[_numeric(passes["Assist"]).isin([13, 14, 15, 16])]


def get_long_balls(events: pd.DataFrame) -> pd.DataFrame:
    """Long ball passes (Long ball == 'Si')."""
    passes = get_passes(events)
    if "Long ball" not in passes.columns:
        return passes.iloc[0:0]
    return passes[_flag(passes["Long ball"])]


def get_crosses(events: pd.DataFrame) -> pd.DataFrame:
    """Crossing passes (Cross == 'Si')."""
    passes = get_passes(events)
    if "Cross" not in passes.columns:
        return passes.iloc[0:0]
    return passes[_flag(passes["Cross"])]


def get_through_balls(events: pd.DataFrame) -> pd.DataFrame:
    """Through-ball passes (Through ball == 'Si')."""
    passes = get_passes(events)
    if "Through ball" not in passes.columns:
        return passes.iloc[0:0]
    return passes[_flag(passes["Through ball"])]


def get_head_passes(events: pd.DataFrame) -> pd.DataFrame:
    """Headed passes (Head pass == 'Si')."""
    passes = get_passes(events)
    if "Head pass" not in passes.columns:
        return passes.iloc[0:0]
    return passes[_flag(passes["Head pass"])]


def get_chipped_passes(events: pd.DataFrame) -> pd.DataFrame:
    """Chipped / lofted passes (Chipped == 'Si')."""
    passes = get_passes(events)
    if "Chipped" not in passes.columns:
        return passes.iloc[0:0]
    return passes[_flag(passes["Chipped"])]


def get_switch_passes(events: pd.DataFrame) -> pd.DataFrame:
    """Switches of play (Switch of play == 'Si')."""
    passes = get_passes(events)
    if "Switch of play" not in passes.columns:
        return passes.iloc[0:0]
    return passes[_flag(passes["Switch of play"])]


def get_free_kick_passes(events: pd.DataFrame) -> pd.DataFrame:
    """Passes taken from free kicks (Free kick taken == 'Si')."""
    passes = get_passes(events)
    if "Free kick taken" not in passes.columns:
        return passes.iloc[0:0]
    return passes[_flag(passes["Free kick taken"])]


def get_corner_passes(events: pd.DataFrame) -> pd.DataFrame:
    """Passes taken from corners (Corner taken == 'Si')."""
    passes = get_passes(events)
    if "Corner taken" not in passes.columns:
        return passes.iloc[0:0]
    return passes[_flag(passes["Corner taken"])]


def get_own_half_passes(events: pd.DataFrame) -> pd.DataFrame:
    """Passes originating in the own half (x < 50)."""
    passes = get_passes(events)
    return passes[pd.to_numeric(passes["x"], errors="coerce") < 50]


def get_opposition_half_passes(events: pd.DataFrame) -> pd.DataFrame:
    """Passes originating in the opposition half (x >= 50)."""
    passes = get_passes(events)
    return passes[pd.to_numeric(passes["x"], errors="coerce") >= 50]


def get_progressive_passes(events: pd.DataFrame) -> pd.DataFrame:
    """Passes that advance the ball at least 10 units forward (Pass End X - x > 10).

    'Progressive' is defined as advancing at least 10 opta units towards the
    opponent's goal — excluding short forward passes.
    """
    passes = get_passes(events)
    x     = pd.to_numeric(passes["x"],         errors="coerce")
    end_x = pd.to_numeric(passes["Pass End X"], errors="coerce")
    return passes[(end_x - x) > 10]


def get_second_assists(events: pd.DataFrame) -> pd.DataFrame:
    """Passes tagged as a 2nd assist (2nd assist qualifier == 'Si')."""
    passes = get_passes(events)
    if "2nd assist" not in passes.columns:
        return passes.iloc[0:0]
    return passes[_flag(passes["2nd assist"])]


# ---------------------------------------------------------------------------
# Shot sub-type selectors
# ---------------------------------------------------------------------------

def get_big_chances(events: pd.DataFrame) -> pd.DataFrame:
    """Shots tagged as big chances (Big Chance == 'Si')."""
    shots = get_shots(events, include_blocked=True)
    if "Big Chance" not in shots.columns:
        return shots.iloc[0:0]
    return shots[_flag(shots["Big Chance"])]


def get_headed_shots(events: pd.DataFrame) -> pd.DataFrame:
    """Shots taken with the head (Head == 'Si')."""
    shots = get_shots(events, include_blocked=True)
    if "Head" not in shots.columns:
        return shots.iloc[0:0]
    return shots[_flag(shots["Head"])]


def get_direct_free_kick_shots(events: pd.DataFrame) -> pd.DataFrame:
    """Shots from direct free kicks (Direct free == 'Si')."""
    shots = get_shots(events, include_blocked=True)
    if "Direct free" not in shots.columns:
        return shots.iloc[0:0]
    return shots[_flag(shots["Direct free"])]


def get_assisted_shots(events: pd.DataFrame) -> pd.DataFrame:
    """Shots that were assisted (Assisted == 'Si' on the shot event)."""
    shots = get_shots(events, include_blocked=True)
    if "Assisted" not in shots.columns:
        return shots.iloc[0:0]
    return shots[_flag(shots["Assisted"])]


def get_box_shots(events: pd.DataFrame) -> pd.DataFrame:
    """Shots from inside the penalty box.

    Box zones in Opta: Small box-*, Box-*, Box-deep-*. Excludes Out-of-box
    and 35+ zones.
    """
    shots = get_shots(events, include_blocked=True)
    box_cols = [
        "Small box-centre", "Small box-right", "Small box-left",
        "Box-centre",       "Box-right",        "Box-left",
        "Box-deep right",   "Box-deep left",
    ]
    available = [c for c in box_cols if c in shots.columns]
    if not available:
        return shots.iloc[0:0]
    mask = pd.Series(False, index=shots.index)
    for col in available:
        mask |= _flag(shots[col])
    return shots[mask]


# ---------------------------------------------------------------------------
# Accuracy / rate helpers
# ---------------------------------------------------------------------------

def pct_pass_accuracy(events: pd.DataFrame) -> float:
    """Pass accuracy as a percentage (0-100). Returns 0.0 if no passes."""
    passes = get_passes(events)
    n = len(passes)
    if n == 0:
        return 0.0
    return round(int((passes["outcome"] == 1).sum()) / n * 100, 1)


def pct_aerial_win(events: pd.DataFrame) -> float:
    """Aerial duel win rate as a percentage. Returns 0.0 if no aerials."""
    aerials = get_aerials(events)
    n = len(aerials)
    if n == 0:
        return 0.0
    return round(int((aerials["outcome"] == 1).sum()) / n * 100, 1)


def pct_take_on(events: pd.DataFrame) -> float:
    """Take-on (dribble) success rate as a percentage. Returns 0.0 if none."""
    take_ons = get_take_ons(events)
    n = len(take_ons)
    if n == 0:
        return 0.0
    return round(int((take_ons["outcome"] == 1).sum()) / n * 100, 1)


def pct_shot_on_target(events: pd.DataFrame) -> float:
    """Shots on target as % of total shots (Miss+Saved Shot+Goal+Post). Returns 0.0 if none."""
    shots = get_shots(events)
    n = len(shots)
    if n == 0:
        return 0.0
    on_target = len(get_shots_on_target(events))
    return round(on_target / n * 100, 1)


def pct_cross_accuracy(events: pd.DataFrame) -> float:
    """Accurate crosses as a percentage of total crosses."""
    crosses = get_crosses(events)
    n = len(crosses)
    if n == 0:
        return 0.0
    return round(int((crosses["outcome"] == 1).sum()) / n * 100, 1)


def pct_long_ball_accuracy(events: pd.DataFrame) -> float:
    """Accurate long balls as a percentage of total long balls."""
    lb = get_long_balls(events)
    n = len(lb)
    if n == 0:
        return 0.0
    return round(int((lb["outcome"] == 1).sum()) / n * 100, 1)


def pct_tackle_success(events: pd.DataFrame) -> float:
    """Tackle success rate as a percentage."""
    tackles = get_tackles(events)
    n = len(tackles)
    if n == 0:
        return 0.0
    return round(int((tackles["outcome"] == 1).sum()) / n * 100, 1)


# ---------------------------------------------------------------------------
# Count helpers
# ---------------------------------------------------------------------------

def count_appearances(events: pd.DataFrame) -> int:
    """Number of distinct matches the player/team appears in."""
    if events.empty or "match_id" not in events.columns:
        return 0
    return int(events["match_id"].nunique())


def count_goals(events: pd.DataFrame) -> int:
    """Count Goal events. Call after filtering to the relevant team_code."""
    return len(get_goals(events))


def count_goal_assists(events: pd.DataFrame) -> int:
    """Count passes that directly assisted a goal (Assist == 16)."""
    return len(get_goal_assists(events))


def count_key_passes(events: pd.DataFrame) -> int:
    """Count key passes (Assist in [13, 14, 15])."""
    return len(get_key_passes(events))


def count_shots(events: pd.DataFrame, *, include_blocked: bool = False) -> int:
    """Count shot events."""
    return len(get_shots(events, include_blocked=include_blocked))


def count_shots_on_target(events: pd.DataFrame) -> int:
    """Count shots on target (Saved Shot + Goal)."""
    return len(get_shots_on_target(events))


def count_total_minutes(events: pd.DataFrame) -> int:
    """Estimate total minutes played from the maximum time_min per match."""
    if events.empty or "time_min" not in events.columns:
        return 0
    grouped = events.groupby("match_id")["time_min"].max()
    return int(grouped.sum())


# ---------------------------------------------------------------------------
# Own-goal helpers
# ---------------------------------------------------------------------------

def is_own_goal_by_team(goal_row: pd.Series, own_team_code: str) -> bool:
    """Return True if this Goal event is an own goal scored by ``own_team_code``.

    Since the ``own goal`` qualifier is never populated in practice, we detect
    own goals by comparing the scorer's ``team_code`` to the team under analysis.
    A Goal event attributed to a player whose ``team_code != own_team_code``
    means the scorer is an opponent — this is NOT an own goal from the
    perspective of ``own_team_code``.

    A true own goal by ``own_team_code`` would be a Goal event where
    ``team_code == own_team_code`` but the goal counts for the opponent.
    Because the ``own goal`` qualifier is always ``'N/A'``, this cannot be
    reliably detected from the qualifier alone. Use ``count_goals_with_own_goal``
    at the match level (which uses team_position context) for goal-line scoring.

    In practice, use ``filter_out_opponent_goals`` to keep only the team's own
    Goal events from a mixed-team events DataFrame.
    """
    return str(goal_row.get("own goal", "")).strip() == "Si"


def filter_out_opponent_goals(events: pd.DataFrame, own_team_code: str) -> pd.DataFrame:
    """Remove Goal events scored by the opposing team from a mixed events DataFrame.

    This is the recommended way to obtain only the goals scored BY ``own_team_code``.
    """
    if events.empty:
        return events
    goal_mask = events["event_type"] == "Goal"
    opponent_goal_mask = goal_mask & (events["team_code"] != own_team_code)
    return events[~opponent_goal_mask]


# ---------------------------------------------------------------------------
# Composite per-player stats dict
# ---------------------------------------------------------------------------

def compute_event_stats(events: pd.DataFrame) -> dict:
    """Compute a comprehensive stat dict for a player/team from their events.

    All values are raw counts unless stated otherwise.  Percentage fields
    are 0-100 floats.  ``_app`` suffix = per appearance (per match).

    Parameters
    ----------
    events : DataFrame
        Events attributed to one player or team (pre-filtered by caller).

    Returns
    -------
    dict with the keys listed below, or an empty dict if ``events`` is empty.
    """
    if events is None or events.empty:
        return {}

    apps = count_appearances(events)
    if apps == 0:
        return {}

    def _per_app(n: int | float) -> float:
        return round(n / apps, 3)

    # ── Passing ──────────────────────────────────────────────────────────────
    passes          = get_passes(events)
    n_passes        = len(passes)
    n_acc_passes    = int((passes["outcome"] == 1).sum()) if n_passes else 0
    pass_acc        = round(n_acc_passes / max(n_passes, 1) * 100, 1)

    own_h_passes    = get_own_half_passes(events)
    opp_h_passes    = get_opposition_half_passes(events)
    long_balls      = get_long_balls(events)
    crosses         = get_crosses(events)
    through_balls   = get_through_balls(events)
    chipped_passes  = get_chipped_passes(events)
    prog_passes     = get_progressive_passes(events)
    switch_passes   = get_switch_passes(events)
    second_assists  = get_second_assists(events)

    n_crosses       = len(crosses)
    n_long          = len(long_balls)
    n_own_h         = len(own_h_passes)
    n_opp_h         = len(opp_h_passes)

    cross_acc       = pct_cross_accuracy(events)
    long_ball_acc   = pct_long_ball_accuracy(events)
    own_h_acc       = round(int((own_h_passes["outcome"] == 1).sum()) / max(n_own_h, 1) * 100, 1)
    opp_h_acc       = round(int((opp_h_passes["outcome"] == 1).sum()) / max(n_opp_h, 1) * 100, 1)

    # ── Attacking ────────────────────────────────────────────────────────────
    goals           = count_goals(events)
    assists         = count_goal_assists(events)
    key_passes      = count_key_passes(events)
    shots           = get_shots(events)
    n_shots         = len(shots)
    n_sot           = count_shots_on_target(events)
    big_chances     = len(get_big_chances(events))
    direct_fk_shots = get_direct_free_kick_shots(events)
    fk_goals        = len(direct_fk_shots[direct_fk_shots["event_type"] == "Goal"])
    box_shots       = get_box_shots(events)
    headed_shots    = get_headed_shots(events)

    shot_acc        = pct_shot_on_target(events)
    goal_conv       = round(goals / max(n_shots, 1) * 100, 1)

    # ── Defensive ────────────────────────────────────────────────────────────
    tackles         = get_tackles(events)
    n_tackles       = len(tackles)
    n_tackle_succ   = int((tackles["outcome"] == 1).sum()) if n_tackles else 0
    tackle_pct      = round(n_tackle_succ / max(n_tackles, 1) * 100, 1)

    interceptions   = get_interceptions(events)
    ball_recoveries = get_ball_recoveries(events)
    clearances      = get_clearances(events)
    blocked_passes  = events[events["event_type"] == "Blocked Pass"]

    # ── Duels ────────────────────────────────────────────────────────────────
    aerials         = get_aerials(events)
    n_aerials       = len(aerials)
    n_aerial_won    = int((aerials["outcome"] == 1).sum()) if n_aerials else 0
    aerial_win_pct  = round(n_aerial_won / max(n_aerials, 1) * 100, 1)

    take_ons        = get_take_ons(events)
    n_take_ons      = len(take_ons)
    n_take_succ     = int((take_ons["outcome"] == 1).sum()) if n_take_ons else 0
    takeon_pct      = round(n_take_succ / max(n_take_ons, 1) * 100, 1)

    challenges      = get_challenges(events)
    n_challs        = len(challenges)
    n_chall_won     = int((challenges["outcome"] == 1).sum()) if n_challs else 0

    n_ground_won    = n_take_succ + n_chall_won
    n_ground_tot    = n_take_ons + n_challs
    ground_duel_pct = round(n_ground_won / max(n_ground_tot, 1) * 100, 1)

    n_duels_won     = n_ground_won + n_aerial_won
    n_duels_tot     = n_ground_tot + n_aerials
    duel_pct        = round(n_duels_won / max(n_duels_tot, 1) * 100, 1)

    # ── Miscellaneous ────────────────────────────────────────────────────────
    offside_prov    = events[events["event_type"] == "Offside provoked"]

    # ── Discipline ───────────────────────────────────────────────────────────
    # "fouls" here means fouls *committed* — get_fouls() returns both the
    # committed and won rows of each double-logged foul, so use the committed
    # selector to avoid ~2× inflation.
    fouls           = get_fouls_committed(events)
    pen_fouls       = get_penalty_fouls(events)
    yellows         = len(get_yellow_cards(events))
    second_yellows  = len(get_second_yellow_cards(events))
    reds            = len(get_red_cards(events))
    dispossessions  = len(get_dispossessions(events))

    # ── Playing time ─────────────────────────────────────────────────────────
    total_minutes   = count_total_minutes(events)
    mins_per_app    = int(total_minutes / apps) if apps > 0 else 0
    touches         = len(get_touches(events))

    return {
        # Identity
        "apps":              apps,
        "total_minutes":     total_minutes,
        "mins_per_app":      mins_per_app,
        "touches":           touches,
        "touches_app":       _per_app(touches),

        # Attacking
        "goals":             goals,
        "goals_app":         _per_app(goals),
        "assists":           assists,
        "assists_app":       _per_app(assists),
        "shots":             n_shots,
        "shots_app":         _per_app(n_shots),
        "shots_on_target":   n_sot,
        "sot_app":           _per_app(n_sot),
        "shot_acc":          shot_acc,           # % shots on target
        "goal_conv":         goal_conv,           # % shots that were goals
        "big_chances":       big_chances,
        "box_shots":         len(box_shots),
        "headed_shots":      len(headed_shots),
        "fk_shots":          len(direct_fk_shots),
        "fk_goals":          fk_goals,

        # Creativity
        "key_passes":        key_passes,
        "key_passes_app":    _per_app(key_passes),

        # Passing
        "passes":            n_passes,
        "passes_app":        _per_app(n_passes),
        "acc_passes":        n_acc_passes,
        "pass_acc":          pass_acc,
        "own_h_passes":      n_own_h,
        "own_h_acc":         own_h_acc,
        "opp_h_passes":      n_opp_h,
        "opp_h_acc":         opp_h_acc,
        "long_balls":        n_long,
        "long_ball_acc":     long_ball_acc,
        "crosses":           n_crosses,
        "cross_acc":         cross_acc,
        "through_balls":     len(through_balls),
        "chipped_passes":    len(chipped_passes),
        "progressive_passes": len(prog_passes),
        "switch_passes":     len(switch_passes),
        "second_assists":    len(second_assists),

        # Defending
        "tackles":           n_tackles,
        "tackles_app":       _per_app(n_tackles),
        "tackle_succ":       n_tackle_succ,
        "tackle_pct":        tackle_pct,
        "interceptions":     len(interceptions),
        "intercepts_app":    _per_app(len(interceptions)),
        "recoveries":        len(ball_recoveries),
        "recoveries_app":    _per_app(len(ball_recoveries)),
        "clearances":        len(clearances),
        "clearances_app":    _per_app(len(clearances)),
        "blocked_passes":    len(blocked_passes),
        "offside_provoked":  len(offside_prov),

        # Duels
        "aerials":           n_aerials,
        "aerial_won":        n_aerial_won,
        "aerial_win_pct":    aerial_win_pct,
        "take_ons":          n_take_ons,
        "take_on_succ":      n_take_succ,
        "takeon_pct":        takeon_pct,
        "ground_duels_won":  n_ground_won,
        "ground_duel_pct":   ground_duel_pct,
        "duels_won":         n_duels_won,
        "duels_total":       n_duels_tot,
        "duel_pct":          duel_pct,

        # Discipline
        "fouls":             len(fouls),
        "fouls_app":         _per_app(len(fouls)),
        "penalty_fouls":     len(pen_fouls),
        "yellow_cards":      yellows,
        "second_yellows":    second_yellows,
        "red_cards":         reds,
        "dispossessions":    dispossessions,
        "disp_app":          _per_app(dispossessions),
    }
