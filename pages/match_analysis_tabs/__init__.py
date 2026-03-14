"""
match_analysis_tabs
===================
Tab-level UI builders for the Match Analysis page.

Each ``build_*_tab`` function receives the match events DataFrame and returns
a Dash layout component for its respective tab.
"""

from .overview                   import build_overview_tab, register_overview_callbacks
from .attacking_output           import build_attacking_output_tab
from .build_up_passing           import build_build_up_passing_tab, register_build_up_passing_callbacks
from .defensive_structure        import build_defensive_structure_tab, register_defensive_structure_callbacks
from .transitions_counterpressing import build_transitions_counterpressing_tab, register_transitions_counterpressing_callbacks
from .goalkeeping                import build_goalkeeping_tab, register_goalkeeping_callbacks
from .player_analysis            import build_player_analysis_tab, register_player_analysis_callbacks

__all__ = [
    "build_overview_tab",
    "register_overview_callbacks",
    "build_attacking_output_tab",
    "build_build_up_passing_tab",
    "register_build_up_passing_callbacks",
    "build_defensive_structure_tab",
    "register_defensive_structure_callbacks",
    "build_transitions_counterpressing_tab",
    "register_transitions_counterpressing_callbacks",
    "build_goalkeeping_tab",
    "register_goalkeeping_callbacks",
    "build_player_analysis_tab",
    "register_player_analysis_callbacks",
]
