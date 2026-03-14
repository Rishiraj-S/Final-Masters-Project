"""
CuléVision - Match Data Adapter for Post-Match Analysis

Provides a schema-agnostic interface layer between raw Opta event data and the
post-match analysis visualisation modules. Each function documents its football
logic and technical approach, and degrades gracefully when expected columns are
missing from the data.

Football Logic:
    Post-match analysis decomposes a game into phases: organised possession,
    transitions, set pieces, and contested phases. This adapter extracts and
    tags events into those phases using Opta qualifier flags where available,
    or infers them from event sequences when explicit tags are absent.

Technical Logic:
    All functions accept a pandas DataFrame of match events (as produced by
    the Opta pipeline's MatchEventTransformer) and return filtered/enriched
    DataFrames or summary dictionaries. Column names are discovered at
    runtime so the adapter works even if qualifier columns are renamed or
    absent.
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Any, Tuple

from utils.data_utils import count_goals


# ---------------------------------------------------------------------------
# Column discovery helpers
# ---------------------------------------------------------------------------

def _has_col(df: pd.DataFrame, col: str) -> bool:
    """Check if a column exists in the DataFrame."""
    return col in df.columns


def _safe_col(df: pd.DataFrame, col: str, default=None) -> pd.Series:
    """Return a column if it exists, otherwise a Series of *default* values."""
    if col in df.columns:
        return df[col]
    return pd.Series(default, index=df.index)


def _flag_is_set(df: pd.DataFrame, col: str) -> pd.Series:
    """
    Return a boolean Series that is True where the Opta qualifier flag *col*
    is set (i.e. the value is not 'N/A', not NaN, and not empty).

    Opta qualifiers are stored as 'Si' when present and 'N/A' when absent.
    """
    if col not in df.columns:
        return pd.Series(False, index=df.index)
    return df[col].fillna('N/A').astype(str).ne('N/A') & df[col].astype(str).ne('')


# ---------------------------------------------------------------------------
# Core team identification
# ---------------------------------------------------------------------------

def identify_barcelona_events(events: pd.DataFrame) -> pd.DataFrame:
    """
    Filter events to only Barcelona actions.

    Football Logic:
        Isolating the team of interest is the first step in any phase-based
        analysis.  Barcelona is identified via the ``team_code`` column.

    Technical Logic:
        Falls back to matching 'Barcelona' in ``team_name`` if ``team_code``
        is unavailable.
    """
    if _has_col(events, 'team_code'):
        return events[events['team_code'] == 'BAR'].copy()
    if _has_col(events, 'team_name'):
        return events[events['team_name'].str.contains('Barcelona', case=False, na=False)].copy()
    # ASSUMPTION: cannot identify team — return empty
    return events.iloc[0:0].copy()


def identify_opponent_events(events: pd.DataFrame) -> pd.DataFrame:
    """Filter events to only opponent actions."""
    if _has_col(events, 'team_code'):
        return events[events['team_code'] != 'BAR'].copy()
    if _has_col(events, 'team_name'):
        return events[~events['team_name'].str.contains('Barcelona', case=False, na=False)].copy()
    return events.iloc[0:0].copy()


# ---------------------------------------------------------------------------
# Match metadata helpers
# ---------------------------------------------------------------------------

def get_match_metadata(events: pd.DataFrame) -> Dict[str, Any]:
    """
    Extract high-level match metadata from the events DataFrame.

    Returns dict with keys: match_id, date, description, home_team, away_team,
    home_score, away_score, venue, competition, and barca_is_home.
    """
    if events.empty:
        return {}

    row = events.iloc[0]
    home_team = str(row.get('home_team', ''))
    away_team = str(row.get('away_team', ''))

    return {
        'match_id': row.get('match_id', ''),
        'date': row.get('match_date', ''),
        'time': row.get('match_time', ''),
        'description': row.get('match_description', ''),
        'home_team': home_team,
        'away_team': away_team,
        'home_score': row.get('home_score', ''),
        'away_score': row.get('away_score', ''),
        'venue': row.get('venue_name', ''),
        'competition': row.get('competition', row.get('competition_name', '')),
        'barca_is_home': 'Barcelona' in home_team or home_team == 'BAR',
    }


# ---------------------------------------------------------------------------
# Tab 1 — Match Statistics & Overview
# ---------------------------------------------------------------------------

def compute_team_kpis(events: pd.DataFrame, team_position: str) -> Dict[str, Any]:
    """
    Compute KPIs for one side of the match (home or away).

    Football Logic:
        Standard KPIs: goals, shots, shots on target, passes, pass accuracy,
        fouls, corners, cards, possession (estimated from pass share).

    Technical Logic:
        Uses ``event_type`` values known from the Opta pipeline:
        Goal, Miss, Saved Shot, Pass, Foul, Corner Awarded, Card.
        Possession is approximated as the ratio of successful passes.
    """
    team = events[events['team_position'] == team_position] if _has_col(events, 'team_position') else events.iloc[0:0]

    passes = team[team['event_type'] == 'Pass'] if not team.empty else team
    total_passes = len(passes)
    successful_passes = len(passes[passes['outcome'] == 1]) if _has_col(passes, 'outcome') and not passes.empty else 0

    # Post (type_id=14) = ball hits frame, still counts as a shot attempt
    shot_types = ['Miss', 'Post', 'Saved Shot', 'Goal']

    # Own-goal-aware goal counting
    all_goals = events[events['event_type'] == 'Goal'] if not events.empty else events.iloc[0:0]
    home_goal_count, away_goal_count = count_goals(all_goals)
    goals = home_goal_count if team_position == 'home' else away_goal_count
    shots = len(team[team['event_type'].isin(shot_types)]) if not team.empty else 0

    # Shots on target: GK saves (Saved Shot WITHOUT 'Blocked' qualifier) + goals.
    # 'Saved Shot' with Blocked='Si' means blocked by outfield player, not on target.
    saved_shots_df = team[team['event_type'] == 'Saved Shot'] if not team.empty else team.iloc[0:0]
    if not saved_shots_df.empty:
        blocked_mask = _flag_is_set(saved_shots_df, 'Blocked')
        gk_saves = int((~blocked_mask).sum())
        blocked_shots = int(blocked_mask.sum())
    else:
        gk_saves = 0
        blocked_shots = 0
    shots_on_target = gk_saves + goals

    # Fouls: each foul produces two paired rows (committer outcome=1, receiver outcome=0).
    # Count only outcome=1 to get fouls committed by this team.
    if not team.empty and _has_col(team, 'outcome'):
        fouls = len(team[(team['event_type'] == 'Foul') & (team['outcome'] == 1)])
    else:
        fouls = len(team[team['event_type'] == 'Foul']) if not team.empty else 0

    # Corners: same paired-row structure. outcome=1 = team that won the corner kick.
    if not team.empty and _has_col(team, 'outcome'):
        corners = len(team[(team['event_type'] == 'Corner Awarded') & (team['outcome'] == 1)])
    else:
        corners = len(team[team['event_type'] == 'Corner Awarded']) if not team.empty else 0

    cards = team[team['event_type'] == 'Card'] if not team.empty else team
    yellow = int(_flag_is_set(cards, 'Yellow Card').sum()) if not cards.empty else 0
    red = int(_flag_is_set(cards, 'Red Card').sum()) if not cards.empty else 0

    # Possession: ratio of (successful passes + take-ons) between teams.
    # This matches the standard broadcast method and avoids counting lost-ball passes.
    def _poss_score(evts, pos):
        t = evts[evts['team_position'] == pos] if _has_col(evts, 'team_position') else evts.iloc[0:0]
        if t.empty:
            return 0
        succ = len(t[(t['event_type'] == 'Pass') & (t['outcome'] == 1)]) if _has_col(t, 'outcome') else 0
        take_ons = len(t[t['event_type'] == 'Take On'])
        return succ + take_ons

    home_poss_score = _poss_score(events, 'home')
    away_poss_score = _poss_score(events, 'away')
    total_poss_score = home_poss_score + away_poss_score
    if total_poss_score > 0:
        this_poss_score = home_poss_score if team_position == 'home' else away_poss_score
        possession = round(this_poss_score / total_poss_score * 100, 1)
    else:
        possession = 50.0

    # Pass accuracy
    pass_acc = round(successful_passes / total_passes * 100, 1) if total_passes > 0 else 0.0

    # Offsides: 'Offside Pass' = team caught offside (not paired, no outcome filter needed)
    offsides = len(team[team['event_type'] == 'Offside Pass']) if not team.empty else 0

    # Interceptions: attributed to the intercepting team (not paired)
    interceptions = len(team[team['event_type'] == 'Interception']) if not team.empty else 0

    # Goal assists: passes with Assist qualifier == 16
    assists = 0
    if not passes.empty and 'Assist' in passes.columns:
        import pandas as _pd
        assists = int((_pd.to_numeric(passes['Assist'], errors='coerce') == 16).sum())

    return {
        'goals': goals,
        'assists': assists,
        'shots': shots,
        'shots_on_target': shots_on_target,
        'blocked_shots': blocked_shots,
        'passes': total_passes,
        'pass_accuracy': pass_acc,
        'possession': possession,
        'fouls': fouls,
        'corners': corners,
        'yellow_cards': yellow,
        'red_cards': red,
        'offsides': offsides,
        'interceptions': interceptions,
    }


def compute_shot_quality_summary(events: pd.DataFrame, team_position: str) -> Dict[str, Any]:
    """
    Summarise shot quality for a given team side.

    Football Logic:
        xG is not natively in Opta event data; instead we report shot zones
        (inside box / outside box), big chances, and conversion rate.

    Technical Logic:
        Checks qualifier flags ``Big Chance``, ``Box-centre``, ``Box-right``,
        ``Box-left``, ``Box-deep right``, ``Box-deep left``, ``Small box-*``,
        ``Out of box-*``.
    """
    team = events[events['team_position'] == team_position] if _has_col(events, 'team_position') else events.iloc[0:0]
    shot_types = ['Miss', 'Saved Shot', 'Goal']
    shots = team[team['event_type'].isin(shot_types)] if not team.empty else team

    if shots.empty:
        return {'total_shots': 0, 'inside_box': 0, 'outside_box': 0,
                'big_chances': 0, 'conversion_rate': 0.0}

    # Inside box qualifiers
    box_cols = ['Box-centre', 'Box-right', 'Box-left', 'Box-deep right',
                'Box-deep left', 'Small box-centre', 'Small box-right', 'Small box-left']
    inside_box = pd.Series(False, index=shots.index)
    for col in box_cols:
        inside_box = inside_box | _flag_is_set(shots, col)

    outside_box_cols = ['Out of box-centre', 'Out of box-right', 'Out of box-left',
                        'Out of box-deep right', 'Out of box-deep left',
                        '35+ centre', '35+ right', '35+ left']
    outside_box = pd.Series(False, index=shots.index)
    for col in outside_box_cols:
        outside_box = outside_box | _flag_is_set(shots, col)

    goals = len(shots[shots['event_type'] == 'Goal'])
    total = len(shots)

    return {
        'total_shots': total,
        'inside_box': int(inside_box.sum()),
        'outside_box': int(outside_box.sum()),
        'big_chances': int(_flag_is_set(shots, 'Big Chance').sum()),
        'conversion_rate': round(goals / total * 100, 1) if total > 0 else 0.0,
    }


def compute_territory_metrics(events: pd.DataFrame) -> Dict[str, Dict[str, float]]:
    """
    Compute territory metrics per team side.

    Football Logic:
        Territory = where on the pitch a team's actions occur.
        Defensive third: x < 33.3, Middle third: 33.3-66.6, Attacking third: > 66.6.
        Coordinates are 0-100 based (Opta standard).

    Technical Logic:
        Uses ``x`` coordinate column.  Flips for away team (Opta normalises
        home team attacking left-to-right in first half but events are stored
        with consistent orientation per team).
    """
    result = {}
    if not _has_col(events, 'x'):
        return {'home': {'def_third': 0, 'mid_third': 0, 'att_third': 0},
                'away': {'def_third': 0, 'mid_third': 0, 'att_third': 0}}

    for pos in ['home', 'away']:
        team = events[events['team_position'] == pos] if _has_col(events, 'team_position') else events.iloc[0:0]
        if team.empty:
            result[pos] = {'def_third': 0, 'mid_third': 0, 'att_third': 0}
            continue
        x = team['x'].dropna()
        total = len(x)
        if total == 0:
            result[pos] = {'def_third': 0, 'mid_third': 0, 'att_third': 0}
            continue
        result[pos] = {
            'def_third': round(len(x[x < 33.3]) / total * 100, 1),
            'mid_third': round(len(x[(x >= 33.3) & (x <= 66.6)]) / total * 100, 1),
            'att_third': round(len(x[x > 66.6]) / total * 100, 1),
        }
    return result


def compute_momentum_timeline(events: pd.DataFrame, window_minutes: int = 5) -> pd.DataFrame:
    """
    Compute a momentum timeline in N-minute windows.

    Football Logic:
        Momentum approximated by net successful actions per window:
        passes completed + shots + tackles won for each team.

    Technical Logic:
        Groups events by time_min buckets and counts positive actions per side.
        Returns a DataFrame with columns: minute_bucket, home_momentum,
        away_momentum.
    """
    if events.empty or not _has_col(events, 'time_min'):
        return pd.DataFrame(columns=['minute_bucket', 'home_momentum', 'away_momentum'])

    df = events.copy()
    df['minute_bucket'] = (df['time_min'] // window_minutes) * window_minutes

    positive_types = ['Pass', 'Goal', 'Saved Shot', 'Miss', 'Tackle', 'Interception', 'Take On']
    positive = df[df['event_type'].isin(positive_types)]
    if _has_col(positive, 'outcome'):
        positive = positive[positive['outcome'] == 1]

    rows = []
    for bucket in sorted(df['minute_bucket'].unique()):
        bucket_events = positive[positive['minute_bucket'] == bucket]
        home_count = len(bucket_events[bucket_events['team_position'] == 'home']) if _has_col(bucket_events, 'team_position') else 0
        away_count = len(bucket_events[bucket_events['team_position'] == 'away']) if _has_col(bucket_events, 'team_position') else 0
        rows.append({
            'minute_bucket': int(bucket),
            'home_momentum': home_count,
            'away_momentum': away_count,
        })

    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Tab 2 — Organised Possession Phase
# ---------------------------------------------------------------------------

# Phase tagging framework
# The Opta data provides qualifier flags that map to our custom phases:
#   - 'Regular play' qualifier  → Build Up / Progression
#   - 'Fast break' qualifier    → Fast Break
#   - Shot events               → Finishing
# Where explicit tags are absent, we infer from event sequences.

POSSESSION_PHASE_MAP = {
    'build_up': {
        'description': 'Structured play in the defensive and middle thirds',
        'x_range': (0, 50),
        'event_types': ['Pass', 'Ball recovery', 'Ball touch'],
    },
    'progression': {
        'description': 'Advancing play from middle to attacking third',
        'x_range': (33, 80),
        'event_types': ['Pass', 'Take On', 'Ball touch'],
    },
    'fast_break': {
        'description': 'Rapid vertical progression after possession gain',
        'qualifier_flag': 'Fast break',
    },
    'finishing': {
        'description': 'Actions in and around the penalty area leading to shots',
        'event_types': ['Miss', 'Saved Shot', 'Goal'],
    },
}


def tag_possession_phases(events: pd.DataFrame) -> pd.DataFrame:
    """
    Tag Barcelona events with a custom possession phase label.

    Football Logic:
        Our framework defines four sub-phases of organised possession:
        1. Build Up   — structured passing in own half (x < 50)
        2. Progression — advancing ball into attacking areas (x 33-80)
        3. Fast Break  — rapid transition attacks (Opta 'Fast break' flag)
        4. Finishing   — shot-producing actions (shots, goals)

        These are NOT mutually exclusive timestamps but overlapping zones.
        Priority: Fast Break > Finishing > Progression > Build Up.

    Technical Logic:
        First checks the Opta 'Fast break' qualifier, then event type for
        finishing, then x-coordinate for progression vs build-up.
        Returns a copy of the input with a new ``possession_phase`` column.
    """
    barca = identify_barcelona_events(events)
    if barca.empty:
        barca['possession_phase'] = pd.Series(dtype=str)
        return barca

    barca = barca.copy()
    barca['possession_phase'] = 'unclassified'

    # Layer 1: Build up (passes in own half)
    has_x = _has_col(barca, 'x')
    if has_x:
        mask_buildup = (
            barca['event_type'].isin(['Pass', 'Ball recovery', 'Ball touch']) &
            (barca['x'] < 50)
        )
        barca.loc[mask_buildup, 'possession_phase'] = 'build_up'

    # Layer 2: Progression (passes/take-ons in middle-to-attacking zone)
    if has_x:
        mask_progression = (
            barca['event_type'].isin(['Pass', 'Take On', 'Ball touch']) &
            (barca['x'] >= 33) & (barca['x'] <= 80)
        )
        barca.loc[mask_progression, 'possession_phase'] = 'progression'

    # Layer 3: Finishing (shots and goals)
    mask_finishing = barca['event_type'].isin(['Miss', 'Saved Shot', 'Goal'])
    barca.loc[mask_finishing, 'possession_phase'] = 'finishing'

    # Layer 4: Fast break (explicit Opta qualifier — highest priority)
    if _has_col(barca, 'Fast break'):
        mask_fastbreak = _flag_is_set(barca, 'Fast break')
        barca.loc[mask_fastbreak, 'possession_phase'] = 'fast_break'

    return barca


def get_build_up_stats(tagged_events: pd.DataFrame) -> Dict[str, Any]:
    """
    Compute build-up phase statistics.

    Football Logic:
        Build-up measures how the team constructs play from the back:
        pass count, pass accuracy, progressive passes (end x > start x + 10).
    """
    bu = tagged_events[tagged_events.get('possession_phase', pd.Series()) == 'build_up'] \
        if 'possession_phase' in tagged_events.columns else tagged_events.iloc[0:0]

    passes = bu[bu['event_type'] == 'Pass'] if not bu.empty else bu
    total = len(passes)
    successful = len(passes[passes['outcome'] == 1]) if _has_col(passes, 'outcome') and not passes.empty else 0

    # Progressive passes: end_x > x + 10
    progressive = 0
    if not passes.empty and _has_col(passes, 'Pass End X') and _has_col(passes, 'x'):
        end_x = pd.to_numeric(passes['Pass End X'], errors='coerce')
        start_x = passes['x']
        progressive = int(((end_x - start_x) > 10).sum())

    return {
        'total_passes': total,
        'successful_passes': successful,
        'pass_accuracy': round(successful / total * 100, 1) if total > 0 else 0.0,
        'progressive_passes': progressive,
        'total_actions': len(bu),
    }


def get_progression_stats(tagged_events: pd.DataFrame) -> Dict[str, Any]:
    """
    Compute progression phase statistics.

    Football Logic:
        Progression measures how the team advances into dangerous areas:
        carries into final third, through balls, switches of play.
    """
    prog = tagged_events[tagged_events.get('possession_phase', pd.Series()) == 'progression'] \
        if 'possession_phase' in tagged_events.columns else tagged_events.iloc[0:0]

    passes = prog[prog['event_type'] == 'Pass'] if not prog.empty else prog
    take_ons = prog[prog['event_type'] == 'Take On'] if not prog.empty else prog

    through_balls = int(_flag_is_set(passes, 'Through ball').sum()) if not passes.empty else 0
    long_balls = int(_flag_is_set(passes, 'Long ball').sum()) if not passes.empty else 0
    crosses = int(_flag_is_set(passes, 'Cross').sum()) if not passes.empty else 0
    switches = int(_flag_is_set(passes, 'Switch of play').sum()) if not passes.empty else 0

    successful_take_ons = len(take_ons[take_ons['outcome'] == 1]) if _has_col(take_ons, 'outcome') and not take_ons.empty else 0

    return {
        'total_passes': len(passes),
        'through_balls': through_balls,
        'long_balls': long_balls,
        'crosses': crosses,
        'switches_of_play': switches,
        'take_ons_attempted': len(take_ons),
        'take_ons_successful': successful_take_ons,
        'total_actions': len(prog),
    }


def get_fast_break_stats(tagged_events: pd.DataFrame) -> Dict[str, Any]:
    """
    Compute fast break statistics.

    Football Logic:
        Fast breaks are rapid counter-attacking moves tagged by Opta's
        'Fast break' qualifier. We count events, shots produced, and goals.
    """
    fb = tagged_events[tagged_events.get('possession_phase', pd.Series()) == 'fast_break'] \
        if 'possession_phase' in tagged_events.columns else tagged_events.iloc[0:0]

    shots = fb[fb['event_type'].isin(['Miss', 'Saved Shot', 'Goal'])] if not fb.empty else fb
    goals = fb[fb['event_type'] == 'Goal'] if not fb.empty else fb

    return {
        'total_actions': len(fb),
        'shots': len(shots),
        'goals': len(goals),
    }


def get_finishing_stats(tagged_events: pd.DataFrame) -> Dict[str, Any]:
    """
    Compute finishing phase statistics.

    Football Logic:
        All shot-related events: shot locations, body part, whether assisted.
    """
    fin = tagged_events[tagged_events.get('possession_phase', pd.Series()) == 'finishing'] \
        if 'possession_phase' in tagged_events.columns else tagged_events.iloc[0:0]

    if fin.empty:
        return {'total_shots': 0, 'on_target': 0, 'goals': 0,
                'headed': 0, 'right_foot': 0, 'left_foot': 0, 'assisted': 0}

    on_target = len(fin[fin['event_type'].isin(['Saved Shot', 'Goal'])])
    goals = len(fin[fin['event_type'] == 'Goal'])

    return {
        'total_shots': len(fin),
        'on_target': on_target,
        'goals': goals,
        'headed': int(_flag_is_set(fin, 'Head').sum()),
        'right_foot': int(_flag_is_set(fin, 'Right footed').sum()),
        'left_foot': int(_flag_is_set(fin, 'Left footed').sum()),
        'assisted': int(_flag_is_set(fin, 'Assisted').sum()),
    }


# ---------------------------------------------------------------------------
# Tab 3 — Transitions
# ---------------------------------------------------------------------------

def detect_possession_changes(events: pd.DataFrame) -> pd.DataFrame:
    """
    Detect moments where possession changes between teams.

    Football Logic:
        A transition occurs when the acting team changes between consecutive
        events. Key transition triggers: Ball recovery, Interception, Tackle
        (won), Dispossessed (opponent's perspective).

    Technical Logic:
        Compares team_position of consecutive events. Marks the first event
        by the gaining team as a transition start.
    """
    if events.empty or not _has_col(events, 'team_position'):
        return events.iloc[0:0].copy()

    df = events.sort_values(['period_id', 'time_min', 'time_sec']).copy()
    df['prev_team_position'] = df['team_position'].shift(1)
    df['is_transition'] = df['team_position'] != df['prev_team_position']

    # Only keep real possession gains (not first event or set pieces restarts)
    df.loc[df.index[0], 'is_transition'] = False
    return df


def get_counterattack_sequences(events: pd.DataFrame, window_seconds: int = 15) -> List[pd.DataFrame]:
    """
    Extract counterattack sequences.

    Football Logic:
        A counterattack is a rapid transition-to-attack sequence that produces
        a shot within *window_seconds* of a possession gain. The gain event
        must be a Ball recovery, Interception, or Tackle (won).

    Technical Logic:
        For each Barcelona possession gain, collect subsequent Barcelona events
        within the time window. Keep sequences that include at least one shot.

    Args:
        events: Full match events DataFrame.
        window_seconds: Maximum duration of a counterattack from gain to shot.

    Returns:
        List of DataFrames, each representing one counterattack sequence.
    """
    transitions = detect_possession_changes(events)
    if transitions.empty:
        return []

    barca_gains = transitions[
        (transitions['is_transition']) &
        (transitions['team_code'] == 'BAR') &
        (transitions['event_type'].isin(['Ball recovery', 'Interception', 'Tackle']))
    ] if _has_col(transitions, 'team_code') else transitions.iloc[0:0]

    sequences = []
    for idx, gain in barca_gains.iterrows():
        start_min = gain['time_min']
        start_sec = gain['time_sec']
        start_total = start_min * 60 + start_sec
        end_total = start_total + window_seconds
        period = gain['period_id']

        # Get subsequent Barcelona events in the time window
        mask = (
            (transitions['period_id'] == period) &
            (transitions['team_code'] == 'BAR') &
            ((transitions['time_min'] * 60 + transitions['time_sec']) >= start_total) &
            ((transitions['time_min'] * 60 + transitions['time_sec']) <= end_total)
        )
        seq = transitions.loc[mask].copy()

        # Check if sequence includes a shot
        shot_types = ['Miss', 'Saved Shot', 'Goal']
        if seq['event_type'].isin(shot_types).any():
            sequences.append(seq)

    return sequences


def get_counterpress_sequences(events: pd.DataFrame, window_seconds: int = 5) -> List[pd.DataFrame]:
    """
    Extract counter-pressing sequences.

    Football Logic:
        Counter-pressing (gegenpressing) is the immediate attempt to win the
        ball back after losing possession. We detect Barcelona losing the ball
        then performing pressing actions (Tackle, Foul, Ball recovery) within
        *window_seconds*.

    Technical Logic:
        For each possession loss by Barcelona, collect subsequent Barcelona
        defensive actions within the time window.
    """
    transitions = detect_possession_changes(events)
    if transitions.empty:
        return []

    # Barcelona losses = opponent gains
    opp_gains = transitions[
        (transitions['is_transition']) &
        (transitions['team_code'] != 'BAR')
    ] if _has_col(transitions, 'team_code') else transitions.iloc[0:0]

    press_types = ['Tackle', 'Foul', 'Ball recovery', 'Interception', 'Challenge']
    sequences = []

    for idx, loss in opp_gains.iterrows():
        start_total = loss['time_min'] * 60 + loss['time_sec']
        end_total = start_total + window_seconds
        period = loss['period_id']

        mask = (
            (transitions['period_id'] == period) &
            (transitions['team_code'] == 'BAR') &
            (transitions['event_type'].isin(press_types)) &
            ((transitions['time_min'] * 60 + transitions['time_sec']) > start_total) &
            ((transitions['time_min'] * 60 + transitions['time_sec']) <= end_total)
        )
        press_events = transitions.loc[mask].copy()

        if not press_events.empty:
            # Include the original loss event for context
            seq = pd.concat([loss.to_frame().T, press_events]).sort_values(['time_min', 'time_sec'])
            sequences.append(seq)

    return sequences


def get_transition_summary(events: pd.DataFrame) -> Dict[str, Any]:
    """
    Compute summary statistics for transitions.

    Returns counts of counterattacks, counter-presses, and their outcomes.
    """
    ca_sequences = get_counterattack_sequences(events)
    cp_sequences = get_counterpress_sequences(events)

    ca_goals = sum(
        1 for seq in ca_sequences if (seq['event_type'] == 'Goal').any()
    )
    ca_shots = sum(
        len(seq[seq['event_type'].isin(['Miss', 'Saved Shot', 'Goal'])])
        for seq in ca_sequences
    )

    cp_recoveries = sum(
        1 for seq in cp_sequences
        if (seq[seq['team_code'] == 'BAR']['event_type'] == 'Ball recovery').any()
    ) if cp_sequences else 0

    return {
        'counterattacks': len(ca_sequences),
        'counterattack_shots': ca_shots,
        'counterattack_goals': ca_goals,
        'counterpresses': len(cp_sequences),
        'counterpress_recoveries': cp_recoveries,
    }


# ---------------------------------------------------------------------------
# Tab 4 — Set Pieces
# ---------------------------------------------------------------------------

def get_set_piece_events(events: pd.DataFrame, team_code: str = 'BAR') -> Dict[str, pd.DataFrame]:
    """
    Extract set piece events grouped by type.

    Football Logic:
        Set pieces include corners, free kicks, throw-ins, and penalties.
        Opta tags these with specific event types and qualifier flags.

    Technical Logic:
        - Corners: event_type 'Corner Awarded' or qualifier 'From corner'/'Corner taken'
        - Free kicks: qualifier 'Free kick taken' or 'Free kick'/'Direct free'
        - Throw-ins: qualifier 'Throw In' or 'Throw In set piece'
        - Penalties: qualifier 'Penalty'
    """
    if _has_col(events, 'team_code'):
        team = events[events['team_code'] == team_code].copy()
    else:
        team = events.copy()

    result = {}

    # Corners
    corner_mask = (team['event_type'] == 'Corner Awarded') if not team.empty else pd.Series(dtype=bool)
    corner_taken = _flag_is_set(team, 'Corner taken') | _flag_is_set(team, 'From corner')
    result['corners'] = team[corner_mask | corner_taken].copy() if not team.empty else team.iloc[0:0]

    # Free kicks
    fk_mask = (
        _flag_is_set(team, 'Free kick taken') |
        _flag_is_set(team, 'Free kick') |
        _flag_is_set(team, 'Direct free')
    )
    result['free_kicks'] = team[fk_mask].copy() if not team.empty else team.iloc[0:0]

    # Throw-ins
    ti_mask = _flag_is_set(team, 'Throw In') | _flag_is_set(team, 'Throw In set piece')
    result['throw_ins'] = team[ti_mask].copy() if not team.empty else team.iloc[0:0]

    # Penalties
    pen_mask = _flag_is_set(team, 'Penalty')
    result['penalties'] = team[pen_mask].copy() if not team.empty else team.iloc[0:0]

    return result


def get_set_piece_summary(events: pd.DataFrame) -> Dict[str, Dict[str, Any]]:
    """
    Compute set piece summary for both Barcelona and opponent.

    Returns a dict with 'attacking' and 'defending' keys.
    """
    barca_sp = get_set_piece_events(events, 'BAR')
    opp_code = _get_opponent_code(events)
    opp_sp = get_set_piece_events(events, opp_code) if opp_code else {}

    def _summarise(sp_dict):
        summary = {}
        for sp_type, sp_df in sp_dict.items():
            shot_types = ['Miss', 'Saved Shot', 'Goal']
            shots = sp_df[sp_df['event_type'].isin(shot_types)] if not sp_df.empty else sp_df
            goals = sp_df[sp_df['event_type'] == 'Goal'] if not sp_df.empty else sp_df
            summary[sp_type] = {
                'count': len(sp_df),
                'shots': len(shots),
                'goals': len(goals),
            }
        return summary

    return {
        'attacking': _summarise(barca_sp),
        'defending': _summarise(opp_sp),
    }


def _get_opponent_code(events: pd.DataFrame) -> Optional[str]:
    """Get the opponent's team code from match events."""
    if not _has_col(events, 'team_code') or events.empty:
        return None
    codes = events['team_code'].dropna().unique()
    for code in codes:
        if code != 'BAR':
            return code
    return None


# ---------------------------------------------------------------------------
# Tab 5 — Contested Phases
# ---------------------------------------------------------------------------

def get_contested_phase_events(events: pd.DataFrame) -> Dict[str, pd.DataFrame]:
    """
    Extract events belonging to contested phases.

    Football Logic:
        Contested phases occur when neither team has clear possession:
        - Loose balls: Ball touch events not in clear possession sequences
        - Duels: Aerial duels, tackles, challenges
        - Scrambles: Events tagged with the 'Scramble' qualifier

    Technical Logic:
        Uses event types (Aerial, Tackle, Challenge) and the 'Scramble'
        qualifier flag. Loose balls are inferred from Ball touch / Ball
        recovery events that are not part of a passing sequence.

        ASSUMPTION: These classifications are extensible — if better tags
        become available in future data versions, they can override the
        inference logic here.
    """
    result = {}

    # Duels
    duel_types = ['Aerial', 'Tackle', 'Challenge']
    result['duels'] = events[events['event_type'].isin(duel_types)].copy() if not events.empty else events.iloc[0:0]

    # Scrambles (explicit Opta qualifier)
    scramble_mask = _flag_is_set(events, 'Scramble')
    result['scrambles'] = events[scramble_mask].copy() if not events.empty else events.iloc[0:0]

    # Loose balls (inferred: Ball touch / Ball recovery not directly preceding a pass)
    loose_types = ['Ball touch', 'Ball recovery']
    loose_candidates = events[events['event_type'].isin(loose_types)].copy() if not events.empty else events.iloc[0:0]

    if not loose_candidates.empty and _has_col(events, 'team_position'):
        # A "loose ball" is a ball touch where the previous event was by the other team
        # or the event doesn't lead to a controlled pass
        prev_team = events['team_position'].shift(1)
        loose_mask = events.index.isin(loose_candidates.index) & (events['team_position'] != prev_team)
        result['loose_balls'] = events[loose_mask].copy()
    else:
        result['loose_balls'] = loose_candidates

    return result


def get_contested_summary(events: pd.DataFrame) -> Dict[str, Dict[str, Any]]:
    """
    Summarise contested phase events for Barcelona and opponent.
    """
    contested = get_contested_phase_events(events)

    def _team_summary(df, team_code):
        if df.empty or not _has_col(df, 'team_code'):
            return {'total': 0, 'won': 0, 'lost': 0}
        team = df[df['team_code'] == team_code]
        won = len(team[team['outcome'] == 1]) if _has_col(team, 'outcome') and not team.empty else 0
        lost = len(team[team['outcome'] == 0]) if _has_col(team, 'outcome') and not team.empty else 0
        return {'total': len(team), 'won': won, 'lost': lost}

    opp_code = _get_opponent_code(events) or 'OPP'

    return {
        'duels': {
            'barcelona': _team_summary(contested['duels'], 'BAR'),
            'opponent': _team_summary(contested['duels'], opp_code),
        },
        'scrambles': {
            'total': len(contested['scrambles']),
            'barcelona': _team_summary(contested['scrambles'], 'BAR'),
            'opponent': _team_summary(contested['scrambles'], opp_code),
        },
        'loose_balls': {
            'total': len(contested['loose_balls']),
            'barcelona': _team_summary(contested['loose_balls'], 'BAR'),
            'opponent': _team_summary(contested['loose_balls'], opp_code),
        },
    }


# ---------------------------------------------------------------------------
# Pitch coordinate helpers for spatial visualisations
# ---------------------------------------------------------------------------

def get_shot_locations(events: pd.DataFrame, team_code: str = 'BAR') -> pd.DataFrame:
    """
    Extract shot locations with coordinates for pitch plotting.

    Returns DataFrame with columns: x, y, event_type, player_name, time_min,
    outcome.  Only includes events with valid x/y coordinates.
    """
    shot_types = ['Miss', 'Saved Shot', 'Goal']
    if _has_col(events, 'team_code'):
        team = events[events['team_code'] == team_code]
    else:
        team = events

    shots = team[team['event_type'].isin(shot_types)].copy() if not team.empty else team.iloc[0:0]

    if shots.empty or not _has_col(shots, 'x') or not _has_col(shots, 'y'):
        return pd.DataFrame(columns=['x', 'y', 'event_type', 'player_name', 'time_min', 'outcome'])

    return shots[['x', 'y', 'event_type', 'player_name', 'time_min', 'outcome']].dropna(subset=['x', 'y'])


def get_pass_network_data(events: pd.DataFrame, team_code: str = 'BAR') -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Extract data for pass network visualisation.

    Football Logic:
        A pass network shows average positions of players and the volume of
        passes between them, indicating team shape and connectivity.

    Returns:
        - nodes: DataFrame with player_name, avg_x, avg_y, pass_count
        - edges: DataFrame with passer, receiver, count
    """
    if _has_col(events, 'team_code'):
        team = events[events['team_code'] == team_code]
    else:
        team = events

    passes = team[team['event_type'] == 'Pass'].copy() if not team.empty else team.iloc[0:0]

    if passes.empty or not _has_col(passes, 'x') or not _has_col(passes, 'y'):
        return (
            pd.DataFrame(columns=['player_name', 'avg_x', 'avg_y', 'pass_count']),
            pd.DataFrame(columns=['passer', 'receiver', 'count'])
        )

    # Nodes: average position per player
    nodes = passes.groupby('player_name').agg(
        avg_x=('x', 'mean'),
        avg_y=('y', 'mean'),
        pass_count=('event_type', 'count')
    ).reset_index()

    # Edges: pass connections
    # Receiver is identified by looking at the next event's player
    passes_sorted = passes.sort_values(['period_id', 'time_min', 'time_sec'])
    passes_sorted['receiver'] = passes_sorted['player_name'].shift(-1)

    # Only keep passes where the next event is also by the same team
    passes_sorted['next_team'] = team.sort_values(['period_id', 'time_min', 'time_sec'])['team_code'].shift(-1).values[:len(passes_sorted)] if len(passes_sorted) <= len(team) else None

    if passes_sorted is not None and _has_col(passes_sorted, 'next_team'):
        valid = passes_sorted[passes_sorted['next_team'] == team_code]
    else:
        valid = passes_sorted

    if not valid.empty:
        edges = valid.groupby(['player_name', 'receiver']).size().reset_index(name='count')
        edges.columns = ['passer', 'receiver', 'count']
    else:
        edges = pd.DataFrame(columns=['passer', 'receiver', 'count'])

    return nodes, edges


# ---------------------------------------------------------------------------
# Lineups & Substitutions
# ---------------------------------------------------------------------------

# Position sort order: GK first, then defenders, midfielders, attackers
_POSITION_ORDER = {
    'GK': 0,
    'RB': 1, 'CB': 2, 'LB': 3,
    'CDM': 4, 'CM': 5, 'MC': 5, 'CAM': 6,
    'RM': 7, 'RW': 7, 'LM': 8, 'LW': 8,
    'CF': 9,
}


def get_starting_lineups(events: pd.DataFrame) -> Dict[str, Any]:
    """
    Extract starting lineups and formation for both teams.

    Football Logic:
        Starters are identified as players with on-ball events in period 1
        who are NOT listed as 'Player on' substitutes.  Formation comes from
        the 'Team setp up' event (note Opta typo).

    Returns dict with 'home' and 'away' keys, each containing:
        - formation: str (e.g. '433')
        - players: list of dicts with name, jersey, position
    """
    result = {}

    for pos_label in ['home', 'away']:
        # Get formation from Team setp up event
        setup = events[
            (events['event_type'] == 'Team setp up') &
            (events['team_position'] == pos_label)
        ]
        formation = ''
        if not setup.empty:
            formation = str(setup.iloc[0].get('formation', ''))
            if formation == 'N/A' or formation == 'nan':
                formation = ''

        # Get players who were subbed on (not starters)
        subs_on = set()
        player_on_events = events[
            (events['event_type'] == 'Player on') &
            (events['team_position'] == pos_label)
        ]
        if not player_on_events.empty:
            subs_on = set(player_on_events['player_name'].dropna().tolist())

        # Get starters: players with events in period 1 (excluding sub events
        # and setup events), minus anyone who came on as a sub
        p1 = events[
            (events['period_id'] == 1) &
            (events['team_position'] == pos_label) &
            (events['player_name'].notna()) &
            (~events['event_type'].isin([
                'Player on', 'Player Off', 'Team setp up',
                'Start', 'End', 'Collection End',
            ]))
        ]

        players = []
        seen = set()
        for _, row in p1.iterrows():
            name = row['player_name']
            if name in seen or name in subs_on:
                continue
            seen.add(name)
            jersey = str(row.get('Jersey Number', '')).replace('N/A', '').strip()
            position = str(row.get('position', '')).replace('N/A', '').strip()
            players.append({
                'name': name,
                'jersey': jersey,
                'position': position,
            })

        # Sort by position order (GK → DEF → MID → FWD)
        players.sort(key=lambda p: _POSITION_ORDER.get(p['position'], 99))

        result[pos_label] = {
            'formation': formation,
            'players': players,
        }

    return result


def get_substitutions(events: pd.DataFrame) -> Dict[str, list]:
    """
    Extract substitutions for both teams.

    Returns dict with 'home' and 'away' keys, each a list of dicts:
        - minute: int
        - player_off: str
        - player_on: str
        - jersey_off: str
        - jersey_on: str
        - reason: str ('Tactical' or 'Injury')

    Matching strategy (in order):
      1. off['Related event ID'] == on['event_id']  (primary Opta linkage)
      2. on['Related event ID'] == off['event_id']  (reverse linkage)
      3. Sequential same-minute pairing (handles multiple subs at same minute)
    """
    result = {'home': [], 'away': []}

    def _clean_str(val) -> str:
        s = str(val).strip()
        return '' if s in ('N/A', 'nan', 'None', '') else s

    def _clean_name(val) -> str:
        return str(val).strip() if val and str(val).strip() not in ('N/A', 'nan', 'None') else ''

    for pos_label in ['home', 'away']:
        off_events = events[
            (events['event_type'] == 'Player Off') &
            (events['team_position'] == pos_label)
        ].sort_values('time_min').copy()

        on_events = events[
            (events['event_type'] == 'Player on') &
            (events['team_position'] == pos_label)
        ].copy()

        # Pre-build lookup dicts for O(1) access
        on_by_event_id   = {}   # event_id   → row index
        on_by_related_id = {}   # Related event ID → row index
        for idx, row in on_events.iterrows():
            eid = _clean_str(row.get('event_id', ''))
            rid = _clean_str(row.get('Related event ID', ''))
            if eid:
                on_by_event_id[eid] = idx
            if rid:
                on_by_related_id[rid] = idx

        matched_on_indices = set()

        for _, off_row in off_events.iterrows():
            minute     = int(off_row['time_min']) if pd.notna(off_row['time_min']) else 0
            player_off = _clean_name(off_row.get('player_name', ''))
            jersey_off = _clean_str(off_row.get('Jersey Number', ''))
            player_on  = ''
            jersey_on  = ''
            on_idx     = None

            # Strategy 1: off's Related event ID → on's event_id
            related = _clean_str(off_row.get('Related event ID', ''))
            if related and related in on_by_event_id:
                on_idx = on_by_event_id[related]

            # Strategy 2: on's Related event ID → off's event_id
            if on_idx is None:
                off_eid = _clean_str(off_row.get('event_id', ''))
                if off_eid and off_eid in on_by_related_id:
                    on_idx = on_by_related_id[off_eid]

            # Strategy 3: sequential same-minute pairing
            if on_idx is None:
                same_min = on_events[
                    (on_events['time_min'] == off_row['time_min']) &
                    (~on_events.index.isin(matched_on_indices))
                ]
                if not same_min.empty:
                    on_idx = same_min.index[0]

            if on_idx is not None and on_idx not in matched_on_indices:
                matched_on_indices.add(on_idx)
                on_row    = on_events.loc[on_idx]
                player_on = _clean_name(on_row.get('player_name', ''))
                jersey_on = _clean_str(on_row.get('Jersey Number', ''))

            reason = 'Injury' if _flag_is_set(
                off_row.to_frame().T, 'Injury'
            ).any() else 'Tactical'

            result[pos_label].append({
                'minute':     minute,
                'player_off': player_off,
                'player_on':  player_on,
                'jersey_off': jersey_off,
                'jersey_on':  jersey_on,
                'reason':     reason,
            })

    return result
