"""
Shared helpers for opposition analysis tab builders.
"""

from dash import html
from utils.config import COLORS


def no_data(msg: str = "No data available.") -> html.P:
    """Uniform 'no data' placeholder for all tab builders."""
    return html.P(msg, style={"color": COLORS["text_secondary"], "padding": "1rem 0"})
