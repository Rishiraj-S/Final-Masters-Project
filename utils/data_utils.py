"""
CuléVision - Data Utilities
Functions for loading and processing Opta pipeline data
"""

import os
import pandas as pd
from pathlib import Path

# Data paths
SCRIPT_DIR = Path(__file__).parent.parent  # Go up one level from utils/ to project root
DATA_PATH = SCRIPT_DIR / "data" / "barcelona" / "result"

COMPETITIONS = {
    'laliga': 'Spain_Primera_Division',
    'ucl': 'UEFA_Champions_League',
    'copa': 'Spain_Copa_del_Rey',
    'supercup': 'Spain_Super_Cup'
}

COMPETITION_NAMES = {
    'Spain_Primera_Division': 'La Liga',
    'UEFA_Champions_League': 'Champions League',
    'Spain_Copa_del_Rey': 'Copa del Rey',
    'Spain_Super_Cup': 'Spanish Super Cup'
}

CURRENT_SEASON = '2025-2026'

# Module-level event cache — keyed by season string.
# Populated lazily on first call.
# Must be explicitly cleared (via clear_events_cache()) after the pipeline
# writes new parquet files — dcc.Location page reloads do NOT restart the
# Python server process, so the cache would otherwise serve stale data.
_events_cache: dict = {}

# Cached result of get_match_results() — same lifetime as _events_cache.
# get_match_results() runs a full groupby over the entire events DataFrame;
# caching it avoids repeating that work on every tab build.
_results_cache: list | None = None


def clear_events_cache() -> None:
    """Clear the in-process events and results caches.

    Call this after the data pipeline finishes so the next request reads
    fresh parquet files from disk instead of returning cached data.
    """
    global _results_cache
    _events_cache.clear()
    _results_cache = None


# ── Centralised own-goal helpers ─────────────────────────────────────────────
# In Opta data, own goals are tagged with the ``own goal`` column == ``'Si'``.
# They are attributed to the player/team that scored them, so an own goal by
# the home team counts as a goal for the away team and vice-versa.

def is_own_goal(row):
    """Check if a single event row is an own goal."""
    return str(row.get('own goal', '')).strip() == 'Si'


def filter_own_goals(goals_df):
    """Remove own goals from a goals DataFrame.

    Useful when counting a player's "real" goals — own goals should not be
    credited to the scoring player.
    """
    if goals_df.empty or 'own goal' not in goals_df.columns:
        return goals_df
    return goals_df[goals_df['own goal'] != 'Si']


def exclude_own_goals(events_df):
    """Remove own-goal rows from a mixed event DataFrame.

    Unlike ``filter_own_goals`` (which expects a goals-only DataFrame), this
    works on any event DataFrame that may contain multiple event types.  Only
    Goal rows flagged as own goals are dropped; all other event types are kept.

    Use this when building shot maps or attacking stats so that own goals — which
    are credited to the opposing team — do not appear in the acting team's plots.
    """
    if events_df.empty or 'own goal' not in events_df.columns:
        return events_df
    og_mask = (events_df['event_type'] == 'Goal') & (events_df['own goal'] == 'Si')
    return events_df[~og_mask]


def get_all_matches(season=CURRENT_SEASON):
    """Load all match data for a given season across all competitions."""
    all_matches = []

    for comp_key, comp_folder in COMPETITIONS.items():
        match_path = DATA_PATH / comp_folder / season / "match"
        if match_path.exists():
            for file in sorted(match_path.glob("*.parquet")):
                df = pd.read_parquet(file)
                df['competition'] = COMPETITION_NAMES.get(comp_folder, comp_folder)
                all_matches.append(df)

    if all_matches:
        return pd.concat(all_matches, ignore_index=True).sort_values('date', ascending=False)
    return pd.DataFrame()


def get_all_events(season=CURRENT_SEASON):
    """Load all match event data for a given season across all competitions.

    Results are cached in-process so repeated calls within the same request
    (or across callbacks) hit memory instead of re-reading Parquet files.
    The cache is keyed by season string and cleared on app restart.
    """
    if season in _events_cache:
        return _events_cache[season]

    all_events = []
    for comp_key, comp_folder in COMPETITIONS.items():
        event_path = DATA_PATH / comp_folder / season / "match_event"
        if event_path.exists():
            for file in sorted(event_path.glob("*.parquet")):
                df = pd.read_parquet(file)
                df['competition'] = COMPETITION_NAMES.get(comp_folder, comp_folder)
                all_events.append(df)

    result = pd.concat(all_events, ignore_index=True) if all_events else pd.DataFrame()
    # Only cache non-empty results — an empty result could mean the pipeline
    # hasn't run yet, and we don't want to permanently cache that state.
    if not result.empty:
        _events_cache[season] = result
    return result


def get_match_events(match_id, season=CURRENT_SEASON):
    """Load event data for a specific match.

    Uses the season-level cache populated by get_all_events() to avoid
    repeated parquet reads for every tab switch or callback fire.
    """
    events = get_all_events(season)
    if events.empty:
        return pd.DataFrame()
    match_events = events[events['match_id'] == match_id]
    if match_events.empty:
        return pd.DataFrame()
    return match_events.reset_index(drop=True)


def get_recent_matches(n=5):
    """Get the most recent N Barcelona matches across all competitions."""
    matches = get_all_matches()
    if matches.empty:
        return pd.DataFrame()

    # Sort by date descending and get top N
    matches = matches.sort_values('date', ascending=False).head(n)
    return matches


def count_goals(goals_df):
    """Count home and away goals, accounting for own goals.

    Vectorised: no iterrows. An own goal by the home team counts as an away
    goal and vice-versa.
    """
    if goals_df.empty:
        return 0, 0

    home_mask = goals_df['team_position'] == 'home'

    if 'own goal' not in goals_df.columns:
        return int(home_mask.sum()), int((~home_mask).sum())

    og_mask = goals_df['own goal'] == 'Si'

    home_goals = int((home_mask  & ~og_mask).sum()) + int((~home_mask & og_mask).sum())
    away_goals = int((~home_mask & ~og_mask).sum()) + int((home_mask  & og_mask).sum())

    return home_goals, away_goals


def calculate_match_result(events_df):
    """Calculate match result from event data (goals)."""
    if events_df.empty:
        return {'home_team': '', 'away_team': '', 'home_goals': 0, 'away_goals': 0}

    goals = events_df[events_df['event_type'] == 'Goal']

    home_team = events_df['home_team'].iloc[0]
    away_team = events_df['away_team'].iloc[0]

    home_goals, away_goals = count_goals(goals)

    return {
        'home_team': home_team,
        'away_team': away_team,
        'home_goals': home_goals,
        'away_goals': away_goals
    }


def get_match_results():
    """Get all match results with scores calculated from events.

    Results are cached for the lifetime of the events cache so that
    multiple tab builders don't each re-run the same groupby over 100k+ rows.
    """
    global _results_cache
    if _results_cache is not None:
        return _results_cache

    events = get_all_events()
    if events.empty:
        return []

    has_venue = 'venue_name' in events.columns
    results = []

    for match_id, match_events in events.groupby('match_id', sort=False):
        first = match_events.iloc[0]
        match_info = {
            'match_id': match_id,
            'date':        first['match_date'],
            'description': first['match_description'],
            'competition': first['competition'],
            'home_team':   first['home_team'],
            'away_team':   first['away_team'],
            'venue':       first['venue_name'] if has_venue else '',
        }

        goals = match_events[match_events['event_type'] == 'Goal']
        home_goals, away_goals = count_goals(goals)
        match_info['home_goals'] = home_goals
        match_info['away_goals'] = away_goals

        if 'Barcelona' in match_info['home_team']:
            match_info['barca_goals']    = home_goals
            match_info['opponent_goals'] = away_goals
            match_info['opponent']       = match_info['away_team']
            match_info['is_home']        = True
        else:
            match_info['barca_goals']    = away_goals
            match_info['opponent_goals'] = home_goals
            match_info['opponent']       = match_info['home_team']
            match_info['is_home']        = False

        bg, og = match_info['barca_goals'], match_info['opponent_goals']
        match_info['result'] = 'W' if bg > og else ('L' if bg < og else 'D')

        results.append(match_info)

    _results_cache = sorted(results, key=lambda x: x['date'], reverse=True)
    return _results_cache


def count_assists(events_df):
    """Count goal assists (passes with Assist qualifier == 16) per player.

    Returns a Series indexed by player_name.
    """
    if events_df.empty:
        return pd.Series(dtype=int)
    passes = events_df[events_df['event_type'] == 'Pass']
    if passes.empty or 'Assist' not in passes.columns:
        return pd.Series(dtype=int)
    mask = pd.to_numeric(passes['Assist'], errors='coerce') == 16
    return passes[mask].groupby('player_name').size()


def get_player_stats(season=CURRENT_SEASON):
    """Calculate player statistics for the season."""
    events = get_all_events(season)
    if events.empty:
        return pd.DataFrame()

    # Filter Barcelona events
    barca_events = events[events['team_code'] == 'BAR']

    # Get goals (exclude own goals — they shouldn't count as the player's goals)
    barca_goals = filter_own_goals(barca_events[barca_events['event_type'] == 'Goal'])
    goals = barca_goals.groupby('player_name').size()

    # Get goal assists
    assists = count_assists(barca_events)

    # Get appearances (unique matches)
    appearances = barca_events.groupby('player_name')['match_id'].nunique()

    # Get passes
    passes = barca_events[barca_events['event_type'] == 'Pass'].groupby('player_name').size()

    # Get shots (Miss + Saved Shot + Goal)
    shots = barca_events[barca_events['event_type'].isin(['Miss', 'Saved Shot', 'Goal'])].groupby('player_name').size()

    # Get tackles
    tackles = barca_events[barca_events['event_type'] == 'Tackle'].groupby('player_name').size()

    # Get interceptions
    interceptions = barca_events[barca_events['event_type'] == 'Interception'].groupby('player_name').size()

    # Combine all stats
    stats_df = pd.DataFrame({
        'goals': goals,
        'assists': assists,
        'appearances': appearances,
        'passes': passes,
        'shots': shots,
        'tackles': tackles,
        'interceptions': interceptions
    }).fillna(0).astype(int)

    stats_df = stats_df.reset_index()
    stats_df.columns = ['player', 'goals', 'assists', 'appearances', 'passes', 'shots', 'tackles', 'interceptions']

    # Sort by goals + assists then appearances
    stats_df = stats_df.sort_values(['goals', 'assists', 'appearances'], ascending=[False, False, False])

    return stats_df


def get_match_stats(match_id):
    """Get detailed statistics for a specific match."""
    events = get_match_events(match_id)
    if events.empty or 'home_team' not in events.columns:
        return {}

    home_team = events['home_team'].iloc[0]
    away_team = events['away_team'].iloc[0]

    stats = {
        'home_team': home_team,
        'away_team': away_team,
        'home': {},
        'away': {}
    }

    # Calculate goals with own-goal awareness
    all_goals = events[events['event_type'] == 'Goal']
    home_goal_count, away_goal_count = count_goals(all_goals)

    for position, team_stats in [('home', stats['home']), ('away', stats['away'])]:
        team_events = events[events['team_position'] == position]

        # Goals (own-goal-aware)
        team_stats['goals'] = home_goal_count if position == 'home' else away_goal_count

        # Shots
        team_stats['shots'] = len(team_events[team_events['event_type'].isin(['Miss', 'Saved Shot', 'Goal'])])

        # Shots on target
        team_stats['shots_on_target'] = len(team_events[team_events['event_type'].isin(['Saved Shot', 'Goal'])])

        # Passes
        passes = team_events[team_events['event_type'] == 'Pass']
        team_stats['passes'] = len(passes)
        team_stats['pass_accuracy'] = round(len(passes[passes['outcome'] == 1]) / len(passes) * 100, 1) if len(passes) > 0 else 0

        # Fouls
        team_stats['fouls'] = len(team_events[team_events['event_type'] == 'Foul'])

        # Cards
        cards = team_events[team_events['event_type'] == 'Card']
        team_stats['yellow_cards'] = len(cards[cards['Yellow Card'] == 'Si']) if 'Yellow Card' in cards.columns else 0
        team_stats['red_cards'] = len(cards[cards['Red Card'] == 'Si']) if 'Red Card' in cards.columns else 0

        # Corners
        team_stats['corners'] = len(team_events[team_events['event_type'] == 'Corner Awarded'])

        # Possession (simplified - based on pass count ratio)
        all_passes = len(events[events['event_type'] == 'Pass'])
        team_stats['possession'] = round(len(passes) / all_passes * 100, 1) if all_passes > 0 else 50

    return stats


def get_match_events_timeline(match_id):
    """Get key events timeline for a match."""
    events = get_match_events(match_id)
    if events.empty:
        return []

    key_event_types = ['Goal', 'Card', 'Player Off', 'Player on']
    key_events = events[events['event_type'].isin(key_event_types)]

    timeline = []
    for _, row in key_events.iterrows():
        og = row['event_type'] == 'Goal' and is_own_goal(row)
        event = {
            'minute': int(row['time_min']) if pd.notna(row['time_min']) else 0,
            'type': 'Own Goal' if og else row['event_type'],
            'player': row['player_name'] if pd.notna(row['player_name']) else '',
            'team': row['team_code'] if pd.notna(row['team_code']) else '',
            'team_position': row['team_position'] if pd.notna(row['team_position']) else ''
        }
        timeline.append(event)

    return sorted(timeline, key=lambda x: x['minute'])


def get_season_summary():
    """Get season summary statistics."""
    results = get_match_results()

    if not results:
        return {}

    total_matches = len(results)
    wins = sum(1 for r in results if r['result'] == 'W')
    draws = sum(1 for r in results if r['result'] == 'D')
    losses = sum(1 for r in results if r['result'] == 'L')
    goals_for = sum(r['barca_goals'] for r in results)
    goals_against = sum(r['opponent_goals'] for r in results)

    return {
        'matches_played': total_matches,
        'wins': wins,
        'draws': draws,
        'losses': losses,
        'goals_for': goals_for,
        'goals_against': goals_against,
        'goal_difference': goals_for - goals_against,
        'points': wins * 3 + draws,
        'win_rate': round(wins / total_matches * 100, 1) if total_matches > 0 else 0
    }


def get_top_scorers(n=10):
    """Get top N scorers for Barcelona this season."""
    stats = get_player_stats()
    if stats.empty:
        return pd.DataFrame()

    return stats[stats['goals'] > 0].head(n)


def get_player_match_stats(player_name, season=CURRENT_SEASON):
    """Get match-by-match stats for a specific player."""
    events = get_all_events(season)
    if events.empty:
        return []

    player_events = events[events['player_name'] == player_name]

    match_stats = []
    for match_id in player_events['match_id'].unique():
        match_events = events[events['match_id'] == match_id]
        if match_events.empty:
            continue
        player_match_events = player_events[player_events['match_id'] == match_id]

        player_goals = filter_own_goals(
            player_match_events[player_match_events['event_type'] == 'Goal']
        )

        stats = {
            'match_id': match_id,
            'date': match_events['match_date'].iloc[0],
            'description': match_events['match_description'].iloc[0],
            'competition': match_events['competition'].iloc[0],
            'goals': len(player_goals),
            'passes': len(player_match_events[player_match_events['event_type'] == 'Pass']),
            'shots': len(player_match_events[player_match_events['event_type'].isin(['Miss', 'Saved Shot', 'Goal'])]),
            'tackles': len(player_match_events[player_match_events['event_type'] == 'Tackle']),
        }
        match_stats.append(stats)

    return sorted(match_stats, key=lambda x: x['date'], reverse=True)


def get_all_barcelona_players(season=CURRENT_SEASON):
    """Get list of all Barcelona players who appeared this season."""
    events = get_all_events(season)
    if events.empty:
        return []

    barca_events = events[events['team_code'] == 'BAR']
    players = barca_events['player_name'].dropna().unique().tolist()
    return sorted(players)


def get_tournament_summary(season=CURRENT_SEASON):
    """Get per-competition summary stats (W-D-L, GF/GA, top scorer, possession)."""
    results = get_match_results()
    events = get_all_events(season)
    if not results or events.empty:
        return {}

    summaries = {}
    for comp_name in COMPETITION_NAMES.values():
        comp_results = [r for r in results if r['competition'] == comp_name]
        if not comp_results:
            continue

        wins = sum(1 for r in comp_results if r['result'] == 'W')
        draws = sum(1 for r in comp_results if r['result'] == 'D')
        losses = sum(1 for r in comp_results if r['result'] == 'L')
        gf = sum(r['barca_goals'] for r in comp_results)
        ga = sum(r['opponent_goals'] for r in comp_results)
        matches = len(comp_results)

        # Top scorer in this competition (exclude own goals)
        comp_events = events[events['competition'] == comp_name]
        barca_goals = filter_own_goals(comp_events[
            (comp_events['team_code'] == 'BAR') & (comp_events['event_type'] == 'Goal')
        ])
        top_scorer = ''
        top_scorer_goals = 0
        if not barca_goals.empty:
            scorer_counts = barca_goals['player_name'].value_counts()
            top_scorer = scorer_counts.index[0]
            top_scorer_goals = int(scorer_counts.iloc[0])

        # Average possession (pass share)
        comp_barca_passes = len(comp_events[
            (comp_events['team_code'] == 'BAR') & (comp_events['event_type'] == 'Pass')
        ])
        comp_all_passes = len(comp_events[comp_events['event_type'] == 'Pass'])
        avg_possession = round(comp_barca_passes / comp_all_passes * 100, 1) if comp_all_passes > 0 else 50.0

        # Pass accuracy
        barca_passes = comp_events[
            (comp_events['team_code'] == 'BAR') & (comp_events['event_type'] == 'Pass')
        ]
        pass_acc = round(
            len(barca_passes[barca_passes['outcome'] == 1]) / len(barca_passes) * 100, 1
        ) if len(barca_passes) > 0 else 0

        # Shot accuracy
        barca_shots = comp_events[
            (comp_events['team_code'] == 'BAR') &
            (comp_events['event_type'].isin(['Miss', 'Saved Shot', 'Goal']))
        ]
        shots_on_target = len(comp_events[
            (comp_events['team_code'] == 'BAR') &
            (comp_events['event_type'].isin(['Saved Shot', 'Goal']))
        ])
        shot_acc = round(shots_on_target / len(barca_shots) * 100, 1) if len(barca_shots) > 0 else 0

        summaries[comp_name] = {
            'matches': matches,
            'wins': wins,
            'draws': draws,
            'losses': losses,
            'goals_for': gf,
            'goals_against': ga,
            'points': wins * 3 + draws,
            'win_rate': round(wins / matches * 100, 1) if matches > 0 else 0,
            'top_scorer': top_scorer,
            'top_scorer_goals': top_scorer_goals,
            'avg_possession': avg_possession,
            'pass_accuracy': pass_acc,
            'shot_accuracy': shot_acc,
            'goals_per_game': round(gf / matches, 1) if matches > 0 else 0,
        }

    return summaries


def get_tournament_match_results(competition):
    """Get match results filtered by a specific competition."""
    results = get_match_results()
    return [r for r in results if r['competition'] == competition]


def get_player_stats_by_competition(competition, season=CURRENT_SEASON):
    """Get player stats filtered by competition."""
    events = get_all_events(season)
    if events.empty:
        return pd.DataFrame()

    comp_events = events[events['competition'] == competition]
    barca_events = comp_events[comp_events['team_code'] == 'BAR']

    if barca_events.empty:
        return pd.DataFrame()

    comp_barca_goals = filter_own_goals(barca_events[barca_events['event_type'] == 'Goal'])
    goals = comp_barca_goals.groupby('player_name').size()
    assists = count_assists(barca_events)
    appearances = barca_events.groupby('player_name')['match_id'].nunique()
    shots = barca_events[barca_events['event_type'].isin(['Miss', 'Saved Shot', 'Goal'])].groupby('player_name').size()

    stats_df = pd.DataFrame({
        'goals': goals,
        'assists': assists,
        'appearances': appearances,
        'shots': shots,
    }).fillna(0).astype(int)

    stats_df = stats_df.reset_index()
    stats_df.columns = ['player', 'goals', 'assists', 'appearances', 'shots']
    stats_df = stats_df.sort_values(['goals', 'assists', 'appearances'], ascending=[False, False, False])

    return stats_df



def get_available_seasons(competition=None):
    """Return sorted list of season strings present on disk.

    Args:
        competition: Optional folder name, e.g. 'Spain_Primera_Division'.
                     If None, returns the union across all competitions.
    Returns:
        List[str] sorted ascending, e.g. ['2008-2009', ..., '2025-2026'].
    """
    if competition:
        folder = DATA_PATH / competition
        if not folder.exists():
            return []
        return sorted(
            d.name for d in folder.iterdir()
            if d.is_dir() and '-' in d.name
        )

    seasons = set()
    for comp_folder in COMPETITIONS.values():
        folder = DATA_PATH / comp_folder
        if folder.exists():
            for d in folder.iterdir():
                if d.is_dir() and '-' in d.name:
                    seasons.add(d.name)
    return sorted(seasons)


def get_all_teams(season=None, competition=None):
    """Return sorted list of all non-Barcelona team names in the match data.

    Args:
        season: Season string, e.g. '2025-2026'. If None, all seasons.
        competition: Friendly competition name (value from COMPETITION_NAMES),
                     e.g. 'La Liga'. If None, all competitions.
    Returns:
        List[str] of team names, excluding Barcelona.
    """
    teams = set()
    for comp_folder in COMPETITIONS.values():
        comp_display = COMPETITION_NAMES.get(comp_folder, comp_folder)
        if competition and competition != 'all' and comp_display != competition:
            continue

        if season and season != 'all':
            seasons_to_check = [season]
        else:
            season_path = DATA_PATH / comp_folder
            if not season_path.exists():
                continue
            seasons_to_check = [d.name for d in season_path.iterdir() if d.is_dir()]

        for s in seasons_to_check:
            # Read team_name from match_event files so names are consistent
            # with the team_name column used in get_team_events()
            event_path = DATA_PATH / comp_folder / s / 'match_event'
            if not event_path.exists():
                continue
            for f in event_path.glob('*.parquet'):
                df = pd.read_parquet(f, columns=['team_name', 'team_code'])
                valid = df.loc[
                    (df['team_code'] != 'BAR') & df['team_name'].notna(),
                    'team_name'
                ]
                teams.update(valid.unique())

    return sorted(teams)


def get_player_events(player_name, season=CURRENT_SEASON, competition=None):
    """Return all events attributed to a specific player.

    Args:
        player_name: Exact player name as stored in data.
        season: Season string. Defaults to CURRENT_SEASON.
        competition: Friendly competition name. If None, all competitions.
    Returns:
        DataFrame with columns including x, y, event_type, outcome,
        time_min, match_id, competition, match_date.
    """
    events = get_all_events(season)
    if events.empty:
        return pd.DataFrame()

    result = events[events['player_name'] == player_name]

    if competition and competition != 'all' and 'competition' in result.columns:
        result = result[result['competition'] == competition]

    return result.reset_index(drop=True)


def get_team_events(team_name, season=CURRENT_SEASON, competition=None):
    """Return all events for a specific team across their matches in the dataset.

    Args:
        team_name: Team name as stored in data (e.g. 'Real Madrid').
        season: Season string. Defaults to CURRENT_SEASON.
        competition: Friendly competition name. If None, all competitions.
    Returns:
        DataFrame of all event rows where team_name matches.
    """
    events = get_all_events(season)
    if events.empty:
        return pd.DataFrame()

    result = events[events['team_name'] == team_name]

    if competition and competition != 'all' and 'competition' in result.columns:
        result = result[result['competition'] == competition]

    return result.reset_index(drop=True)


def get_team_season_stats(season=CURRENT_SEASON, competition=None):
    """Return aggregate Barcelona team-level stats for a season.

    Args:
        season: Season string.
        competition: Friendly competition name. If None, all competitions.
    Returns:
        dict with keys: shots, shots_on_target, goals_scored, goals_conceded,
        passes, pass_accuracy, possession, corners, fouls, yellow_cards,
        red_cards, tackles, interceptions, clean_sheets,
        matches_played, wins, draws, losses.
    """
    events = get_all_events(season)
    if events.empty:
        return {}

    if competition and competition != 'all' and 'competition' in events.columns:
        events = events[events['competition'] == competition]

    bar_events = events[events['team_code'] == 'BAR']

    passes = bar_events[bar_events['event_type'] == 'Pass']
    pass_acc = round(
        len(passes[passes['outcome'] == 1]) / len(passes) * 100, 1
    ) if len(passes) > 0 else 0.0

    all_passes = len(events[events['event_type'] == 'Pass'])
    possession = round(
        len(passes) / all_passes * 100, 1
    ) if all_passes > 0 else 50.0

    shot_types = ['Miss', 'Saved Shot', 'Goal']
    shots = bar_events[bar_events['event_type'].isin(shot_types)]
    shots_on_target = bar_events[bar_events['event_type'].isin(['Saved Shot', 'Goal'])]

    yellow_col = 'Yellow Card'
    red_col = 'Red Card'
    cards = bar_events[bar_events['event_type'] == 'Card']
    yellow_cards = len(cards[cards[yellow_col] == 'Si']) if yellow_col in cards.columns else 0
    red_cards = len(cards[cards[red_col] == 'Si']) if red_col in cards.columns else 0

    # Match-level stats from results
    # Scope to match_ids already present in the season-scoped events (authoritative)
    match_ids = set(events['match_id'].unique()) if not events.empty else set()
    results = get_match_results()
    if competition and competition != 'all':
        results = [r for r in results if r['competition'] == competition]
    results = [r for r in results if r['match_id'] in match_ids]

    wins = sum(1 for r in results if r['result'] == 'W')
    draws = sum(1 for r in results if r['result'] == 'D')
    losses = sum(1 for r in results if r['result'] == 'L')
    clean_sheets = sum(1 for r in results if r['opponent_goals'] == 0)
    goals_scored = sum(r['barca_goals'] for r in results)
    goals_conceded = sum(r['opponent_goals'] for r in results)

    return {
        'shots': len(shots),
        'shots_on_target': len(shots_on_target),
        'goals_scored': goals_scored,
        'goals_conceded': goals_conceded,
        'passes': len(passes),
        'pass_accuracy': pass_acc,
        'possession': possession,
        'corners': len(bar_events[bar_events['event_type'] == 'Corner Awarded']),
        'fouls': len(bar_events[bar_events['event_type'] == 'Foul']),
        'yellow_cards': yellow_cards,
        'red_cards': red_cards,
        'tackles': len(bar_events[bar_events['event_type'] == 'Tackle']),
        'interceptions': len(bar_events[bar_events['event_type'] == 'Interception']),
        'clean_sheets': clean_sheets,
        'matches_played': len(results),
        'wins': wins,
        'draws': draws,
        'losses': losses,
    }


def get_match_lineup(match_id):
    """Load lineup data for a specific match.

    Scans all lineup/ subdirectories for a file whose stem contains match_id.
    Returns an empty DataFrame if not found.
    """
    if not match_id:
        return pd.DataFrame()

    for comp_folder in COMPETITIONS.values():
        comp_path = DATA_PATH / comp_folder
        if not comp_path.exists():
            continue
        for season_dir in comp_path.iterdir():
            if not season_dir.is_dir():
                continue
            lineup_path = season_dir / 'lineup'
            if not lineup_path.exists():
                continue
            for f in lineup_path.glob('*.parquet'):
                if match_id in f.stem:
                    return pd.read_parquet(f)

    return pd.DataFrame()


def get_form_timeline():
    """Get rolling form data (cumulative points over matches) for trendline chart."""
    results = get_match_results()
    if not results:
        return []

    # Sort chronologically
    sorted_results = sorted(results, key=lambda x: x['date'])

    timeline = []
    cumulative_points = 0
    for i, r in enumerate(sorted_results, 1):
        if r['result'] == 'W':
            points = 3
        elif r['result'] == 'D':
            points = 1
        else:
            points = 0
        cumulative_points += points
        timeline.append({
            'match_num': i,
            'date': r['date'],
            'opponent': r['opponent'],
            'competition': r['competition'],
            'result': r['result'],
            'points': points,
            'cumulative_points': cumulative_points,
            'ppg': round(cumulative_points / i, 2),
            'barca_goals': r['barca_goals'],
            'opponent_goals': r['opponent_goals'],
        })

    return timeline
