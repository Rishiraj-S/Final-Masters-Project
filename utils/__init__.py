"""
CuléVision Utils Package
Contains configuration, data utilities, and login functionality
"""

from .config import COLORS, APP_CONFIG, NAV_LINKS, LOGO_CONFIG, FEATURES
from .data_utils import (
    get_match_results, get_player_stats, get_season_summary, get_top_scorers,
    get_match_stats, get_match_events_timeline, get_all_barcelona_players,
    get_player_match_stats, get_all_events, get_all_matches, get_match_events,
    get_recent_matches, calculate_match_result, COMPETITIONS, COMPETITION_NAMES,
    CURRENT_SEASON
)

__all__ = [
    # Config exports
    'COLORS', 'APP_CONFIG', 'NAV_LINKS', 'LOGO_CONFIG', 'FEATURES',
    # Data utils exports
    'get_match_results', 'get_player_stats', 'get_season_summary', 'get_top_scorers',
    'get_match_stats', 'get_match_events_timeline', 'get_all_barcelona_players',
    'get_player_match_stats', 'get_all_events', 'get_all_matches', 'get_match_events',
    'get_recent_matches', 'calculate_match_result', 'COMPETITIONS', 'COMPETITION_NAMES',
    'CURRENT_SEASON'
]
