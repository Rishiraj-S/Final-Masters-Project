"""
Opposition analysis tab builders package.

Each module provides a single public build_* function that returns a Dash
layout component for that tab.

    from pages.opposition_analysis_tabs import (
        build_scouting,
        build_in_possession,
        build_defence,
        build_transitions,
        build_set_pieces,
        build_exploit,
    )
"""

from .scouting       import build_scouting
from .in_possession  import build_in_possession
from .defence        import build_defence
from .transitions    import build_transitions
from .set_pieces     import build_set_pieces
from .exploit        import build_exploit

__all__ = [
    "build_scouting",
    "build_in_possession",
    "build_defence",
    "build_transitions",
    "build_set_pieces",
    "build_exploit",
]
