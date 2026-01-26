"""
CuléVision - Data Utilities
Functions for loading and processing Opta pipeline data
"""

import os
import pandas as pd
from pathlib import Path

# Data paths
SCRIPT_DIR = Path(__file__).parent
DATA_PATH = SCRIPT_DIR / "opta_pipeline" / "data" / "result"

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
    """Load all match event data for a given season across all competitions."""
    all_events = []

    for comp_key, comp_folder in COMPETITIONS.items():
        event_path = DATA_PATH / comp_folder / season / "match_event"
        if event_path.exists():
            for file in sorted(event_path.glob("*.parquet")):
                df = pd.read_parquet(file)
                df['competition'] = COMPETITION_NAMES.get(comp_folder, comp_folder)
                all_events.append(df)

    if all_events:
        return pd.concat(all_events, ignore_index=True)
    return pd.DataFrame()


def get_match_events(match_id, season=CURRENT_SEASON):
    """Load event data for a specific match."""
    for comp_key, comp_folder in COMPETITIONS.items():
        event_path = DATA_PATH / comp_folder / season / "match_event"
        if event_path.exists():
            for file in event_path.glob("*.parquet"):
                df = pd.read_parquet(file)
                if df['match_id'].iloc[0] == match_id:
                    df['competition'] = COMPETITION_NAMES.get(comp_folder, comp_folder)
                    return df
    return pd.DataFrame()


def get_recent_matches(n=5):
    """Get the most recent N Barcelona matches across all competitions."""
    matches = get_all_matches()
    if matches.empty:
        return pd.DataFrame()

    # Sort by date descending and get top N
    matches = matches.sort_values('date', ascending=False).head(n)
    return matches


def calculate_match_result(events_df):
    """Calculate match result from event data (goals)."""
    goals = events_df[events_df['event_type'] == 'Goal']

    home_team = events_df['home_team'].iloc[0]
    away_team = events_df['away_team'].iloc[0]

    # Count goals by team position
    home_goals = len(goals[goals['team_position'] == 'home'])
    away_goals = len(goals[goals['team_position'] == 'away'])

    return {
        'home_team': home_team,
        'away_team': away_team,
        'home_goals': home_goals,
        'away_goals': away_goals
    }


def get_match_results():
    """Get all match results with scores calculated from events."""
    events = get_all_events()
    if events.empty:
        return []

    results = []
    for match_id in events['match_id'].unique():
        match_events = events[events['match_id'] == match_id]

        # Get match info
        match_info = {
            'match_id': match_id,
            'date': match_events['match_date'].iloc[0],
            'description': match_events['match_description'].iloc[0],
            'competition': match_events['competition'].iloc[0],
            'home_team': match_events['home_team'].iloc[0],
            'away_team': match_events['away_team'].iloc[0],
            'venue': match_events['venue_name'].iloc[0] if 'venue_name' in match_events.columns else ''
        }

        # Calculate score from goals
        goals = match_events[match_events['event_type'] == 'Goal']
        home_goals = len(goals[goals['team_position'] == 'home'])
        away_goals = len(goals[goals['team_position'] == 'away'])

        match_info['home_goals'] = home_goals
        match_info['away_goals'] = away_goals

        # Determine result for Barcelona
        if 'Barcelona' in match_info['home_team']:
            match_info['barca_goals'] = home_goals
            match_info['opponent_goals'] = away_goals
            match_info['opponent'] = match_info['away_team']
            match_info['is_home'] = True
        else:
            match_info['barca_goals'] = away_goals
            match_info['opponent_goals'] = home_goals
            match_info['opponent'] = match_info['home_team']
            match_info['is_home'] = False

        if match_info['barca_goals'] > match_info['opponent_goals']:
            match_info['result'] = 'W'
        elif match_info['barca_goals'] < match_info['opponent_goals']:
            match_info['result'] = 'L'
        else:
            match_info['result'] = 'D'

        results.append(match_info)

    # Sort by date descending
    results = sorted(results, key=lambda x: x['date'], reverse=True)
    return results


def get_player_stats(season=CURRENT_SEASON):
    """Calculate player statistics for the season."""
    events = get_all_events(season)
    if events.empty:
        return pd.DataFrame()

    # Filter Barcelona events
    barca_events = events[events['team_code'] == 'BAR']

    # Get goals
    goals = barca_events[barca_events['event_type'] == 'Goal'].groupby('player_name').size()

    # Get assists (where Assisted == 'Si')
    goals_with_assists = events[(events['event_type'] == 'Goal') & (events['Assisted'] == 'Si')]
    # We need to look at the pass before the goal for the assister - simplified approach
    # Just count participation for now

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
        'appearances': appearances,
        'passes': passes,
        'shots': shots,
        'tackles': tackles,
        'interceptions': interceptions
    }).fillna(0).astype(int)

    stats_df = stats_df.reset_index()
    stats_df.columns = ['player', 'goals', 'appearances', 'passes', 'shots', 'tackles', 'interceptions']

    # Sort by goals then appearances
    stats_df = stats_df.sort_values(['goals', 'appearances'], ascending=[False, False])

    return stats_df


def get_match_stats(match_id):
    """Get detailed statistics for a specific match."""
    events = get_match_events(match_id)
    if events.empty:
        return {}

    home_team = events['home_team'].iloc[0]
    away_team = events['away_team'].iloc[0]

    stats = {
        'home_team': home_team,
        'away_team': away_team,
        'home': {},
        'away': {}
    }

    for position, team_stats in [('home', stats['home']), ('away', stats['away'])]:
        team_events = events[events['team_position'] == position]

        # Goals
        team_stats['goals'] = len(team_events[team_events['event_type'] == 'Goal'])

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
        event = {
            'minute': int(row['time_min']) if pd.notna(row['time_min']) else 0,
            'type': row['event_type'],
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
        player_match_events = player_events[player_events['match_id'] == match_id]

        stats = {
            'match_id': match_id,
            'date': match_events['match_date'].iloc[0],
            'description': match_events['match_description'].iloc[0],
            'competition': match_events['competition'].iloc[0],
            'goals': len(player_match_events[player_match_events['event_type'] == 'Goal']),
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
