"""
Opposition analysis tab builders package.

Each module provides a single public build_* function that returns a Dash
layout component for that tab.  They are imported here for convenience:

    from pages.opposition_analysis_tabs import (
        build_summary,
        build_tactical,
        build_key_players,
        build_shot_map,
    )
"""

from .summary     import build_summary
from .tactical    import build_tactical
from .key_players import build_key_players
from .shot_map    import build_shot_map

__all__ = [
    "build_summary",
    "build_tactical",
    "build_key_players",
    "build_shot_map",
]
