"""
CuléVision Utils Package
Contains configuration, data utilities, match data adapter, and login functionality
"""

from .config import COLORS, APP_CONFIG, NAV_LINKS, LOGO_CONFIG, FEATURES
from .data_utils import (
    get_match_results, get_player_stats, get_season_summary, get_top_scorers,
    get_match_stats, get_match_events_timeline, get_all_barcelona_players,
    get_player_match_stats, get_all_events, get_all_matches, get_match_events,
    get_recent_matches, calculate_match_result, COMPETITIONS, COMPETITION_NAMES,
    CURRENT_SEASON
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
    # Config exports
    'COLORS', 'APP_CONFIG', 'NAV_LINKS', 'LOGO_CONFIG', 'FEATURES',
    # Data utils exports
    'get_match_results', 'get_player_stats', 'get_season_summary', 'get_top_scorers',
    'get_match_stats', 'get_match_events_timeline', 'get_all_barcelona_players',
    'get_player_match_stats', 'get_all_events', 'get_all_matches', 'get_match_events',
    'get_recent_matches', 'calculate_match_result', 'COMPETITIONS', 'COMPETITION_NAMES',
    'CURRENT_SEASON',
    # Match data adapter exports
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
