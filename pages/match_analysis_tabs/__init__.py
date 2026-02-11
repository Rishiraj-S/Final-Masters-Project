"""
Match Analysis Tabs Package
Each tab of the match analysis page lives in its own module.
"""

from .overview import build_overview_tab
from .possession import build_possession_tab
from .transitions import build_transitions_tab
from .set_pieces import build_setpieces_tab
from .contested import build_contested_tab

__all__ = [
    'build_overview_tab',
    'build_possession_tab',
    'build_transitions_tab',
    'build_setpieces_tab',
    'build_contested_tab',
]
