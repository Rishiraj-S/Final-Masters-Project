"""
CuléVision Utils Package
Contains configuration, data utilities, match data adapter, and event helpers.

Prefer importing from ``utils.event_utils`` directly for event-level helpers
to avoid pulling in the full package (which requires the data pipeline to have
run at least once).
"""

from .config import COLORS, APP_CONFIG, NAV_LINKS
from .data_utils import (
    get_match_results, get_player_stats, get_season_summary, get_top_scorers,
    get_match_stats, get_match_events_timeline, get_all_barcelona_players,
    get_player_match_stats, get_all_events, get_all_matches, get_match_events,
    get_recent_matches, calculate_match_result, COMPETITIONS, COMPETITION_NAMES,
    CURRENT_SEASON, is_own_goal, filter_own_goals, count_goals,
)
from .event_utils import (
    # Event-type selectors
    get_passes, get_shots, get_shots_on_target, get_goals,
    get_tackles, get_successful_tackles,
    get_interceptions, get_ball_recoveries, get_clearances,
    get_aerials, get_aerial_wins,
    get_take_ons, get_successful_take_ons,
    get_challenges, get_successful_challenges,
    get_fouls, get_penalty_fouls,
    get_cards, get_yellow_cards, get_second_yellow_cards, get_red_cards,
    get_errors, get_dispossessions, get_touches, get_corners, get_saves,
    # Pass sub-type selectors
    get_accurate_passes,
    get_goal_assists, get_key_passes, get_any_assist_passes,
    get_long_balls, get_crosses, get_through_balls, get_head_passes,
    get_chipped_passes, get_switch_passes,
    get_free_kick_passes, get_corner_passes,
    get_own_half_passes, get_opposition_half_passes, get_progressive_passes,
    # Shot sub-type selectors
    get_big_chances, get_headed_shots, get_direct_free_kick_shots,
    get_assisted_shots, get_box_shots,
    # Accuracy / rate helpers
    pct_pass_accuracy, pct_aerial_win, pct_take_on,
    pct_shot_on_target, pct_cross_accuracy, pct_long_ball_accuracy,
    pct_tackle_success,
    # Count helpers
    count_appearances, count_goals as count_goal_events,
    count_goal_assists, count_key_passes,
    count_shots, count_shots_on_target, count_total_minutes,
    # Own-goal helpers
    filter_out_opponent_goals,
    # Composite stats
    compute_event_stats,
    # Constants
    SHOT_TYPES, SHOT_TYPES_WITH_BLOCKED, ON_TARGET_TYPES,
)
from .match_data_adapter import (
    get_match_metadata, compute_team_kpis, compute_shot_quality_summary,
    compute_territory_metrics, compute_momentum_timeline,
    tag_possession_phases, get_build_up_stats, get_progression_stats,
    get_fast_break_stats, get_finishing_stats,
    get_transition_summary, get_counterattack_sequences, get_counterpress_sequences,
    get_set_piece_summary, get_set_piece_events,
    get_contested_summary, get_contested_phase_events,
    get_shot_locations, identify_barcelona_events, identify_opponent_events,
    get_pass_network_data,
)

__all__ = [
    # Config
    'COLORS', 'APP_CONFIG', 'NAV_LINKS',
    # Data utils
    'get_match_results', 'get_player_stats', 'get_season_summary', 'get_top_scorers',
    'get_match_stats', 'get_match_events_timeline', 'get_all_barcelona_players',
    'get_player_match_stats', 'get_all_events', 'get_all_matches', 'get_match_events',
    'get_recent_matches', 'calculate_match_result', 'COMPETITIONS', 'COMPETITION_NAMES',
    'CURRENT_SEASON', 'is_own_goal', 'filter_own_goals', 'count_goals',
    # Event utils — selectors
    'get_passes', 'get_shots', 'get_shots_on_target', 'get_goals',
    'get_tackles', 'get_successful_tackles',
    'get_interceptions', 'get_ball_recoveries', 'get_clearances',
    'get_aerials', 'get_aerial_wins',
    'get_take_ons', 'get_successful_take_ons',
    'get_challenges', 'get_successful_challenges',
    'get_fouls', 'get_penalty_fouls',
    'get_cards', 'get_yellow_cards', 'get_second_yellow_cards', 'get_red_cards',
    'get_errors', 'get_dispossessions', 'get_touches', 'get_corners', 'get_saves',
    # Event utils — pass sub-types
    'get_accurate_passes',
    'get_goal_assists', 'get_key_passes', 'get_any_assist_passes',
    'get_long_balls', 'get_crosses', 'get_through_balls', 'get_head_passes',
    'get_chipped_passes', 'get_switch_passes',
    'get_free_kick_passes', 'get_corner_passes',
    'get_own_half_passes', 'get_opposition_half_passes', 'get_progressive_passes',
    # Event utils — shot sub-types
    'get_big_chances', 'get_headed_shots', 'get_direct_free_kick_shots',
    'get_assisted_shots', 'get_box_shots',
    # Event utils — rates
    'pct_pass_accuracy', 'pct_aerial_win', 'pct_take_on',
    'pct_shot_on_target', 'pct_cross_accuracy', 'pct_long_ball_accuracy',
    'pct_tackle_success',
    # Event utils — counts
    'count_appearances', 'count_goal_events', 'count_goal_assists', 'count_key_passes',
    'count_shots', 'count_shots_on_target', 'count_total_minutes',
    # Event utils — own goals
    'filter_out_opponent_goals',
    # Event utils — composite
    'compute_event_stats',
    # Event utils — constants
    'SHOT_TYPES', 'SHOT_TYPES_WITH_BLOCKED', 'ON_TARGET_TYPES',
    # Match data adapter
    'get_match_metadata', 'compute_team_kpis', 'compute_shot_quality_summary',
    'compute_territory_metrics', 'compute_momentum_timeline',
    'tag_possession_phases', 'get_build_up_stats', 'get_progression_stats',
    'get_fast_break_stats', 'get_finishing_stats',
    'get_transition_summary', 'get_counterattack_sequences', 'get_counterpress_sequences',
    'get_set_piece_summary', 'get_set_piece_events',
    'get_contested_summary', 'get_contested_phase_events',
    'get_shot_locations', 'identify_barcelona_events', 'identify_opponent_events',
    'get_pass_network_data',
]
