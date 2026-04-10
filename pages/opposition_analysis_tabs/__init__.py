"""
Opposition analysis tab builders package.

Each module provides:
  • build_*()           — skeleton layout (called from render_tab)
  • register_*_callbacks(app) — wires filter inputs to chart outputs

    from pages.opposition_analysis_tabs import (
        build_overview,
        build_buildup,
        build_chance_creation,
        build_transitions,
        build_defence,
        build_set_pieces,
        register_buildup_callbacks,
        register_chance_creation_callbacks,
        register_transitions_callbacks,
        register_defence_callbacks,
        register_set_pieces_callbacks,
    )
"""

from .overview        import build_overview
from .buildup         import build_buildup,         register_buildup_callbacks
from .chance_creation import build_chance_creation, register_chance_creation_callbacks
from .transitions     import build_transitions,     register_transitions_callbacks
from .defence         import build_defence,         register_defence_callbacks
from .set_pieces      import build_set_pieces,      register_set_pieces_callbacks

__all__ = [
    'build_overview',
    'build_buildup',
    'build_chance_creation',
    'build_transitions',
    'build_defence',
    'build_set_pieces',
    'register_buildup_callbacks',
    'register_chance_creation_callbacks',
    'register_transitions_callbacks',
    'register_defence_callbacks',
    'register_set_pieces_callbacks',
]
