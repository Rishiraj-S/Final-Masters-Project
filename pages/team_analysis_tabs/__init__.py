"""
team_analysis_tabs
==================
Tab-level UI builders for the Team Analysis page.

Each ``build_*_tab`` function receives (season, competitions, match_ids)
and returns a Dash layout component for its respective tab.

Tabs (matching the game model flowchart):
  Tab 0 — Overview          build_overview_tab
  Tab 1 — Build-up          build_buildup_tab
  Tab 2 — Chance Creation   build_chance_creation_tab
  Tab 3 — Def. Structure    build_def_structure_tab
  Tab 4 — Transitions       build_transitions_tab
  Tab 5 — Set Pieces        build_set_pieces_tab
"""

from .overview        import build_overview_tab
from .buildup         import build_buildup_tab
from .chance_creation import build_chance_creation_tab
from .def_structure   import build_def_structure_tab
from .transitions     import build_transitions_tab
from .set_pieces      import build_set_pieces_tab

__all__ = [
    "build_overview_tab",
    "build_buildup_tab",
    "build_chance_creation_tab",
    "build_def_structure_tab",
    "build_transitions_tab",
    "build_set_pieces_tab",
]
