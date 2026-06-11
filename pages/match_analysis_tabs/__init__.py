from __future__ import annotations

from .overview import build_overview_tab, register_overview_callbacks
from .attacking_output import build_attacking_output_tab, register_attacking_output_callbacks, build_attack_radar
from .build_up_passing import build_build_up_passing_tab, register_build_up_passing_callbacks, build_bup_radar
from .defensive_structure import build_defensive_structure_tab, register_defensive_structure_callbacks, build_def_radar
from .transitions_counterpressing import build_transitions_counterpressing_tab, register_transitions_counterpressing_callbacks
from .goalkeeping import build_goalkeeping_tab, register_goalkeeping_callbacks
from .player_stats import build_player_stats_tab, register_player_stats_callbacks

__all__ = [
    'build_overview_tab', 'register_overview_callbacks',
    'build_attacking_output_tab', 'register_attacking_output_callbacks',
    'build_build_up_passing_tab', 'register_build_up_passing_callbacks',
    'build_defensive_structure_tab', 'register_defensive_structure_callbacks',
    'build_transitions_counterpressing_tab', 'register_transitions_counterpressing_callbacks',
    'build_goalkeeping_tab', 'register_goalkeeping_callbacks',
    'build_player_stats_tab', 'register_player_stats_callbacks',
    'build_attack_radar', 'build_bup_radar', 'build_def_radar',
]
