"""
Pizza plot generation for CuléVision Player Analysis.

Adapted from the standalone player_analysis_engine.py pizza-plot logic
to match the app's dark theme and return base64 data URIs (same pattern
as render_heatmap_img / render_pass_map_img in shared.py).
"""

from __future__ import annotations

import base64
import io

import matplotlib
matplotlib.use("Agg")  # non-interactive backend
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from mplsoccer import PyPizza

from utils.config import COLORS

# ---------------------------------------------------------------------------
# Theme constants  (derived from the app colour palette)
# ---------------------------------------------------------------------------

_BG_COLOR    = COLORS["dark_secondary"]   # '#151932'
_SLICE_COLOR = "#1A78CF"                  # Barça-adjacent blue
_TEXT_COLOR  = COLORS["text_primary"]     # '#E8E9ED'
_GOLD        = COLORS["gold"]             # '#EDBB00'
_GRID_COLOR  = "#2A2F4A"                  # subtle grid lines


def render_pizza_plot(
    labels: list[str],
    percentile_values: list[int | float],
    raw_values: list[float],
    avg_values: list[float],
    player_name: str,
    subtitle: str = "",
) -> str:
    """
    Generate a PyPizza percentile chart and return a base64 PNG data URI.

    Parameters
    ----------
    labels            : metric display names (length N).
    percentile_values : player percentile scores 0-100 (length N).
    raw_values        : player raw stat values used in the legend (length N).
    avg_values        : positional-average raw values for legend (length N).
    player_name       : shown as the plot title.
    subtitle          : shown below the title (e.g. 'Attacking & Possession').

    Returns
    -------
    str  ``data:image/png;base64,...`` or empty string if labels is empty.
    """
    n = len(labels)
    if n == 0:
        return ""

    # Clamp values: PyPizza behaves oddly at exactly 0 or 100
    vals = [max(1, min(99, int(v))) for v in percentile_values]

    fig = plt.figure(figsize=(9, 10), facecolor=_BG_COLOR)
    ax  = fig.add_subplot(111, projection="polar", facecolor=_BG_COLOR)
    fig.subplots_adjust(top=0.82, bottom=0.22)

    baker = PyPizza(
        params=labels,
        background_color=_BG_COLOR,
        straight_line_color=_GRID_COLOR,
        straight_line_lw=1,
        last_circle_lw=1,
        last_circle_color=_GRID_COLOR,
        other_circle_ls="-.",
        other_circle_lw=1,
    )
    baker.make_pizza(
        vals,
        ax=ax,
        color_blank_space="same",
        param_location=112,
        blank_alpha=0.35,
        kwargs_slices=dict(
            facecolor=_SLICE_COLOR,
            edgecolor=_GRID_COLOR,
            zorder=1,
            linewidth=1,
        ),
        kwargs_params=dict(
            color=_TEXT_COLOR,
            fontsize=10,
            zorder=5,
            va="center",
        ),
        kwargs_values=dict(
            color="#000000",
            fontsize=9,
            bbox=dict(
                edgecolor="#000000",
                facecolor=_SLICE_COLOR,
                boxstyle="round,pad=0.2",
                lw=1,
            ),
        ),
    )

    # Legend: one coloured dot per metric showing player value and positional average
    legend_labels = [
        f"{lbl}: {rv:.2f}  (avg {av:.2f})"
        for lbl, rv, av in zip(labels, raw_values, avg_values)
    ]
    handles = [
        Line2D(
            [0], [0],
            marker="o", color="w",
            markerfacecolor=_GOLD,
            markeredgecolor=_TEXT_COLOR,
            markersize=8,
            label=legend_lbl,
        )
        for legend_lbl in legend_labels
    ]
    legend = fig.legend(
        handles=handles,
        loc="lower center",
        fontsize=7.5,
        ncol=2,
        frameon=False,
        bbox_to_anchor=(0.5, 0.01),
    )
    for t in legend.get_texts():
        t.set_color(_TEXT_COLOR)

    # Title block
    fig.text(0.5, 0.94, player_name, size=15, ha="center",
             color=_GOLD, fontweight="bold")
    if subtitle:
        fig.text(0.5, 0.90, subtitle, size=9, ha="center", color=_TEXT_COLOR)

    # Encode to base64
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=140, bbox_inches="tight",
                facecolor=_BG_COLOR)
    plt.close(fig)
    buf.seek(0)
    b64 = base64.b64encode(buf.read()).decode()
    return f"data:image/png;base64,{b64}"
