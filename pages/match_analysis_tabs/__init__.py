"""
Match Analysis Tabs Package
Each tab of the match analysis page lives in its own module.
"""

from .overview import build_overview_tab, register_overview_callbacks
from .attack import build_attack_tab
from .attacking_transition import build_attacking_transition_tab
from .defence import build_defence_tab
from .defensive_transition import build_defensive_transition_tab
from .set_pieces import build_setpieces_tab

__all__ = [
    'build_overview_tab',
    'register_overview_callbacks',
    'build_attack_tab',
    'build_attacking_transition_tab',
    'build_defence_tab',
    'build_defensive_transition_tab',
    'build_setpieces_tab',
]
