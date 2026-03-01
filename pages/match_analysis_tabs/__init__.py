"""
match_analysis_tabs
===================
Tab-level UI builders for the Match Analysis page.

Each ``build_*_tab`` function receives the match events DataFrame and returns
a Dash layout component for its respective tab.
"""

from .overview   import build_overview_tab
from .possession import build_possession_tab
from .transition import build_transition_tab
from .recovery   import build_recovery_tab
from .set_pieces import build_setpieces_tab

__all__ = [
    "build_overview_tab",
    "build_possession_tab",
    "build_transition_tab",
    "build_recovery_tab",
    "build_setpieces_tab",
]
