"""
CuléVision Pages Package
Contains individual page modules for the multi-page Dash application
"""

from .home import create_home_layout
from .match_analysis import create_match_analysis_layout, register_match_analysis_callbacks
from .team_insights import create_team_insights_layout, register_team_insights_callbacks

__all__ = [
    'create_home_layout',
    'create_match_analysis_layout',
    'register_match_analysis_callbacks',
    'create_team_insights_layout',
    'register_team_insights_callbacks',
]
