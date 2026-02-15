"""
CuléVision Pages Package
Contains individual page modules for the multi-page Dash application
"""

from .home import create_home_layout, register_home_callbacks
from .match_analysis import create_match_analysis_layout, register_match_analysis_callbacks
from .team_insights import create_team_insights_layout, register_team_insights_callbacks
from .opposition_analysis import create_opposition_analysis_layout, register_opposition_analysis_callbacks

__all__ = [
    'create_home_layout',
    'register_home_callbacks',
    'create_match_analysis_layout',
    'register_match_analysis_callbacks',
    'create_team_insights_layout',
    'register_team_insights_callbacks',
    'create_opposition_analysis_layout',
    'register_opposition_analysis_callbacks',
]
