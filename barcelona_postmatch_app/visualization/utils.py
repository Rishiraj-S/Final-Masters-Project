"""Shared visualization utilities: pitch drawing, colors, heatmaps."""
from __future__ import annotations

import numpy as np
import plotly.graph_objects as go

from barcelona_postmatch_app.config import (
    BARCELONA_DARK,
    BARCELONA_GOLD,
    BARCELONA_PRIMARY,
    BARCELONA_SECONDARY,
    HEATMAP_BINS_X,
    HEATMAP_BINS_Y,
    HEATMAP_COLORSCALE,
    OPPOSITION_PRIMARY,
    PITCH_BG_COLOR,
    PITCH_LINE_COLOR,
    PITCH_LINE_WIDTH,
    PITCH_LENGTH,
    PITCH_WIDTH,
    TEAM_COLORS,
)


def draw_pitch(
    fig: go.Figure | None = None,
    pitch_color: str = PITCH_BG_COLOR,
    line_color: str = PITCH_LINE_COLOR,
    line_width: float = PITCH_LINE_WIDTH,
    opta_coords: bool = True,
) -> go.Figure:
    """Draw a football pitch using Plotly shapes.

    If opta_coords=True, x-axis is 0-100 and y-axis is 0-100 (Opta system).
    Otherwise uses meters (0-105 x 0-68).
    """
    if fig is None:
        fig = go.Figure()

    if opta_coords:
        x_max, y_max = 100, 100
        # Penalty area proportions in Opta coords
        pa_width = 16.5 / PITCH_LENGTH * 100    # ~15.7
        pa_height = 40.3 / PITCH_WIDTH * 100     # ~59.3
        ga_width = 5.5 / PITCH_LENGTH * 100       # ~5.2
        ga_height = 18.3 / PITCH_WIDTH * 100       # ~26.9
        penalty_spot = 11 / PITCH_LENGTH * 100     # ~10.5
        center_circle_r = 9.15 / max(PITCH_LENGTH, PITCH_WIDTH) * 100  # ~8.7
    else:
        x_max, y_max = PITCH_LENGTH, PITCH_WIDTH
        pa_width, pa_height = 16.5, 40.3
        ga_width, ga_height = 5.5, 18.3
        penalty_spot = 11
        center_circle_r = 9.15

    pa_y_start = (y_max - pa_height) / 2
    ga_y_start = (y_max - ga_height) / 2

    shapes = []

    def _rect(x0, y0, x1, y1):
        shapes.append(dict(
            type="rect", x0=x0, y0=y0, x1=x1, y1=y1,
            line=dict(color=line_color, width=line_width),
            fillcolor="rgba(0,0,0,0)",
        ))

    def _line(x0, y0, x1, y1):
        shapes.append(dict(
            type="line", x0=x0, y0=y0, x1=x1, y1=y1,
            line=dict(color=line_color, width=line_width),
        ))

    def _circle(xc, yc, r):
        shapes.append(dict(
            type="circle",
            x0=xc - r, y0=yc - r, x1=xc + r, y1=yc + r,
            line=dict(color=line_color, width=line_width),
            fillcolor="rgba(0,0,0,0)",
        ))

    # Pitch outline
    _rect(0, 0, x_max, y_max)

    # Halfway line
    _line(x_max / 2, 0, x_max / 2, y_max)

    # Center circle
    _circle(x_max / 2, y_max / 2, center_circle_r)

    # Center spot
    shapes.append(dict(
        type="circle",
        x0=x_max / 2 - 0.5, y0=y_max / 2 - 0.5,
        x1=x_max / 2 + 0.5, y1=y_max / 2 + 0.5,
        fillcolor=line_color,
        line=dict(color=line_color, width=0),
    ))

    # Left penalty area
    _rect(0, pa_y_start, pa_width, pa_y_start + pa_height)
    # Left goal area
    _rect(0, ga_y_start, ga_width, ga_y_start + ga_height)
    # Left penalty spot
    shapes.append(dict(
        type="circle",
        x0=penalty_spot - 0.4, y0=y_max / 2 - 0.4,
        x1=penalty_spot + 0.4, y1=y_max / 2 + 0.4,
        fillcolor=line_color,
        line=dict(color=line_color, width=0),
    ))

    # Right penalty area
    _rect(x_max - pa_width, pa_y_start, x_max, pa_y_start + pa_height)
    # Right goal area
    _rect(x_max - ga_width, ga_y_start, x_max, ga_y_start + ga_height)
    # Right penalty spot
    shapes.append(dict(
        type="circle",
        x0=x_max - penalty_spot - 0.4, y0=y_max / 2 - 0.4,
        x1=x_max - penalty_spot + 0.4, y1=y_max / 2 + 0.4,
        fillcolor=line_color,
        line=dict(color=line_color, width=0),
    ))

    fig.update_layout(
        shapes=shapes,
        plot_bgcolor=pitch_color,
        xaxis=dict(
            range=[-2, x_max + 2],
            showgrid=False, zeroline=False, showticklabels=False,
            constrain="domain",
        ),
        yaxis=dict(
            range=[-2, y_max + 2],
            showgrid=False, zeroline=False, showticklabels=False,
            scaleanchor="x", scaleratio=1,
        ),
        margin=dict(l=10, r=10, t=30, b=10),
        height=500,
    )

    return fig


def create_heatmap_data(
    x_values: list[float],
    y_values: list[float],
    bins_x: int = HEATMAP_BINS_X,
    bins_y: int = HEATMAP_BINS_Y,
    x_range: tuple = (0, 100),
    y_range: tuple = (0, 100),
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Convert scatter points to a 2D histogram for heatmap overlay.

    Returns (z_matrix, x_edges, y_edges).
    """
    x_arr = np.array([v for v in x_values if not np.isnan(v)])
    y_arr = np.array([v for v in y_values if not np.isnan(v)])

    if len(x_arr) == 0:
        return np.zeros((bins_y, bins_x)), np.linspace(*x_range, bins_x + 1), np.linspace(*y_range, bins_y + 1)

    min_len = min(len(x_arr), len(y_arr))
    x_arr = x_arr[:min_len]
    y_arr = y_arr[:min_len]

    z, x_edges, y_edges = np.histogram2d(
        x_arr, y_arr,
        bins=[bins_x, bins_y],
        range=[list(x_range), list(y_range)],
    )

    return z.T, x_edges, y_edges


def plot_heatmap_on_pitch(
    x_values: list[float],
    y_values: list[float],
    title: str = "",
    colorscale: str = HEATMAP_COLORSCALE,
    bins_x: int = HEATMAP_BINS_X,
    bins_y: int = HEATMAP_BINS_Y,
    opacity: float = 0.6,
) -> go.Figure:
    """Create a heatmap overlay on a football pitch."""
    fig = draw_pitch()

    z, x_edges, y_edges = create_heatmap_data(
        x_values, y_values, bins_x, bins_y
    )

    x_centers = (x_edges[:-1] + x_edges[1:]) / 2
    y_centers = (y_edges[:-1] + y_edges[1:]) / 2

    fig.add_trace(go.Heatmap(
        z=z,
        x=x_centers,
        y=y_centers,
        colorscale=colorscale,
        opacity=opacity,
        showscale=True,
        colorbar=dict(title="Count", len=0.5),
    ))

    fig.update_layout(title=title)
    return fig


def get_barcelona_colors() -> dict:
    """Return Barcelona color palette."""
    return {
        "primary": BARCELONA_PRIMARY,
        "secondary": BARCELONA_SECONDARY,
        "gold": BARCELONA_GOLD,
        "dark": BARCELONA_DARK,
    }


def get_team_colors(team_name: str) -> tuple[str, str]:
    """Return (primary, secondary) color tuple for a team."""
    for name, colors in TEAM_COLORS.items():
        if name.lower() in team_name.lower() or team_name.lower() in name.lower():
            return colors
    return (OPPOSITION_PRIMARY, "#FFFFFF")


def get_color_by_performance(value: float, min_val: float = 0, max_val: float = 100) -> str:
    """Return a color from red (poor) to green (good) based on value."""
    if max_val == min_val:
        norm = 0.5
    else:
        norm = max(0, min(1, (value - min_val) / (max_val - min_val)))

    r = int(255 * (1 - norm))
    g = int(255 * norm)
    return f"rgb({r},{g},80)"


def format_metric_card(value, label: str, unit: str = "", delta: str = "") -> str:
    """Format a metric for display in Streamlit metric card."""
    if isinstance(value, float):
        formatted = f"{value:.1f}"
    else:
        formatted = str(value)
    return formatted


def plot_passing_network_on_pitch(
    nodes: dict,
    edges: dict,
    title: str = "Passing Network",
    min_passes: int = 2,
) -> go.Figure:
    """Draw a passing network on the pitch.

    nodes: {player_id: {"name": str, "avg_x": float, "avg_y": float, "pass_count": int}}
    edges: {(from_id, to_id): count}
    """
    fig = draw_pitch()

    if not nodes or not edges:
        fig.update_layout(title=title)
        return fig

    max_passes = max(edges.values()) if edges else 1
    max_node_passes = max(n["pass_count"] for n in nodes.values()) if nodes else 1

    # Draw edges
    for (from_id, to_id), count in edges.items():
        if count < min_passes:
            continue
        if from_id not in nodes or to_id not in nodes:
            continue

        width = max(1, count / max_passes * 8)
        opacity = max(0.2, min(0.9, count / max_passes))

        fig.add_trace(go.Scatter(
            x=[nodes[from_id]["avg_x"], nodes[to_id]["avg_x"]],
            y=[nodes[from_id]["avg_y"], nodes[to_id]["avg_y"]],
            mode="lines",
            line=dict(width=width, color=f"rgba(255,255,255,{opacity})"),
            hoverinfo="text",
            text=f"{nodes[from_id]['name']} -> {nodes[to_id]['name']}: {count}",
            showlegend=False,
        ))

    # Draw nodes
    for pid, data in nodes.items():
        size = max(10, data["pass_count"] / max_node_passes * 35)
        fig.add_trace(go.Scatter(
            x=[data["avg_x"]],
            y=[data["avg_y"]],
            mode="markers+text",
            marker=dict(
                size=size,
                color=BARCELONA_PRIMARY,
                line=dict(width=2, color=BARCELONA_GOLD),
            ),
            text=data["name"].split()[-1] if data["name"] else "",
            textposition="top center",
            textfont=dict(color="white", size=10),
            hoverinfo="text",
            hovertext=f"{data['name']}: {data['pass_count']} passes",
            showlegend=False,
        ))

    fig.update_layout(title=title)
    return fig
