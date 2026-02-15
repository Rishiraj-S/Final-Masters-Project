"""
CuléVision - Data Utilities
Functions for loading and processing Opta pipeline data
"""

import os
import pandas as pd
from pathlib import Path

# Data paths
SCRIPT_DIR = Path(__file__).parent.parent  # Go up one level from utils/ to project root
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


def count_goals(goals_df):
    """Count home and away goals, accounting for own goals.

    In Opta data, own goals are tagged with ``own goal`` == ``'Si'`` and
    attributed to the player/team that scored them.  An own goal by the
    home team counts as an away goal and vice-versa.
    """
    has_og_col = 'own goal' in goals_df.columns

    home_goals = 0
    away_goals = 0

    for _, row in goals_df.iterrows():
        is_own_goal = has_og_col and str(row.get('own goal', '')).strip() == 'Si'
        if is_own_goal:
            # Own goal: credit the opposing side
            if row['team_position'] == 'home':
                away_goals += 1
            else:
                home_goals += 1
        else:
            if row['team_position'] == 'home':
                home_goals += 1
            else:
                away_goals += 1

    return home_goals, away_goals


def calculate_match_result(events_df):
    """Calculate match result from event data (goals)."""
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

        # Calculate score from goals (own goals count for the opposing side)
        goals = match_events[match_events['event_type'] == 'Goal']
        home_goals, away_goals = count_goals(goals)

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

    # Get goals (exclude own goals — they shouldn't count as the player's goals)
    barca_goals = barca_events[barca_events['event_type'] == 'Goal']
    if 'own goal' in barca_goals.columns:
        barca_goals = barca_goals[barca_goals['own goal'] != 'Si']
    goals = barca_goals.groupby('player_name').size()

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
        is_own_goal = (
            row['event_type'] == 'Goal'
            and 'own goal' in key_events.columns
            and str(row.get('own goal', '')).strip() == 'Si'
        )
        event = {
            'minute': int(row['time_min']) if pd.notna(row['time_min']) else 0,
            'type': 'Own Goal' if is_own_goal else row['event_type'],
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
            'goals': len(player_match_events[(player_match_events['event_type'] == 'Goal') & (player_match_events['own goal'] != 'Si')]) if 'own goal' in player_match_events.columns else len(player_match_events[player_match_events['event_type'] == 'Goal']),
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
        barca_goals = comp_events[
            (comp_events['team_code'] == 'BAR') & (comp_events['event_type'] == 'Goal')
        ]
        if 'own goal' in barca_goals.columns:
            barca_goals = barca_goals[barca_goals['own goal'] != 'Si']
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

    comp_barca_goals = barca_events[barca_events['event_type'] == 'Goal']
    if 'own goal' in comp_barca_goals.columns:
        comp_barca_goals = comp_barca_goals[comp_barca_goals['own goal'] != 'Si']
    goals = comp_barca_goals.groupby('player_name').size()
    appearances = barca_events.groupby('player_name')['match_id'].nunique()
    shots = barca_events[barca_events['event_type'].isin(['Miss', 'Saved Shot', 'Goal'])].groupby('player_name').size()

    stats_df = pd.DataFrame({
        'goals': goals,
        'appearances': appearances,
        'shots': shots,
    }).fillna(0).astype(int)

    stats_df = stats_df.reset_index()
    stats_df.columns = ['player', 'goals', 'appearances', 'shots']
    stats_df = stats_df.sort_values(['goals', 'appearances'], ascending=[False, False])

    return stats_df


def get_season_highlights():
    """Get notable season highlights: biggest win, toughest match, MVP, breakout star."""
    results = get_match_results()
    stats = get_player_stats()
    if not results or stats.empty:
        return {}

    # Biggest win (largest positive goal difference)
    biggest_win = max(
        [r for r in results if r['result'] == 'W'],
        key=lambda r: r['barca_goals'] - r['opponent_goals'],
        default=None
    )

    # Toughest match (closest loss or draw with most goals)
    tough_candidates = [r for r in results if r['result'] in ('L', 'D')]
    toughest_match = None
    if tough_candidates:
        toughest_match = min(
            tough_candidates,
            key=lambda r: abs(r['barca_goals'] - r['opponent_goals'])
        )

    # MVP (most goals)
    mvp = None
    if not stats.empty:
        top = stats.iloc[0]
        mvp = {'player': top['player'], 'goals': int(top['goals']), 'appearances': int(top['appearances'])}

    # Breakout star (best goals per appearance, min 3 apps)
    breakout = None
    eligible = stats[(stats['appearances'] >= 3) & (stats['goals'] > 0)].copy()
    if not eligible.empty:
        eligible['gpg'] = eligible['goals'] / eligible['appearances']
        eligible = eligible.sort_values('gpg', ascending=False)
        # Exclude the MVP to make it interesting
        if mvp:
            eligible = eligible[eligible['player'] != mvp['player']]
        if not eligible.empty:
            star = eligible.iloc[0]
            breakout = {
                'player': star['player'],
                'goals': int(star['goals']),
                'appearances': int(star['appearances']),
                'gpg': round(float(star['gpg']), 2)
            }

    return {
        'biggest_win': biggest_win,
        'toughest_match': toughest_match,
        'mvp': mvp,
        'breakout_star': breakout
    }


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
