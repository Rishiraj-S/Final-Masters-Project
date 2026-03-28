"""
page_utils
==========
Shared utilities for all page and tab modules.

Modules:
    pitch_zones      -- Zone detection from (x, y) coordinates.
    possession_utils -- Possession-change heuristics and vertical speed.
    time_utils       -- Time-window arithmetic and rolling helpers.
    competitions     -- Competition constants, short labels, and normalization.
    event_filters    -- Event-type sets, colour maps, and period-filter helpers.
    visualizations   -- Unified Plotly/mplsoccer plot configs & tools.
"""

from .visualizations import (
    HOME_COLOR, AWAY_COLOR, GOLD,
    CHART_LAYOUT_DEFAULTS, CHART_CONFIG, layout_config, empty_fig,
    add_pitch_background, PITCH_AXIS_FULL, PITCH_AXIS_HALF,
    add_vertical_pitch_background, VPITCH_AXIS,
    add_vertical_half_pitch_background, VPITCH_AXIS_HALF,
    render_lsc_heatmap_img,
    RADAR_KEYS, build_radar_fig, build_metric_explanation_card,
    build_scatter_pitch_fig, build_pass_map_fig,
    PassMapConfig, PassMap,
)
