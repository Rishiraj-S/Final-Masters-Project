"""
team_analysis_tabs
==================
Tab-level UI builders for the Team Analysis page.

Each ``build_*_tab`` function receives (season, competitions, match_ids)
and returns a Dash layout component for its respective tab.
"""

from .identity          import build_identity_tab
from .in_possession     import build_in_possession_tab
from .out_of_possession import build_out_of_possession_tab
from .def_transition    import build_def_transition_tab
from .att_transition    import build_att_transition_tab
from .goalkeeping       import build_goalkeeping_tab

__all__ = [
    "build_identity_tab",
    "build_in_possession_tab",
    "build_out_of_possession_tab",
    "build_def_transition_tab",
    "build_att_transition_tab",
    "build_goalkeeping_tab",
]
