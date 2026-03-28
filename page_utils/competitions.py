"""
page_utils.competitions
=======================
Competition constants and helpers shared across all page modules.

Previously each page (team_analysis.py, player_analysis.py) and every tab
module under team_analysis_tabs/ defined their own copy of _ALL_COMPETITIONS,
_COMP_SHORT, and _normalize_competitions.  All of those should now import from
here instead.
"""

from __future__ import annotations

from typing import Optional

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Full list of tracked competitions, ready for use in dcc.Dropdown options.
ALL_COMPETITIONS: list[dict] = [
    {'label': 'La Liga',          'value': 'La Liga'},
    {'label': 'Champions League', 'value': 'Champions League'},
    {'label': 'Copa del Rey',     'value': 'Copa del Rey'},
    {'label': 'Spanish Super Cup','value': 'Spanish Super Cup'},
]

#: Abbreviated competition labels used on chart axes and match selector rows.
COMP_SHORT: dict[str, str] = {
    'La Liga':           'Liga',
    'Champions League':  'UCL',
    'Copa del Rey':      'Copa',
    'Spanish Super Cup': 'SC',
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def normalize_competitions(competition) -> Optional[list[str]]:
    """
    Normalise a competition value from a dcc.Dropdown to a list or None.

    - None / empty   → None  (means "all competitions")
    - 'all'          → None
    - 'La Liga'      → ['La Liga']
    - ['La Liga', …] → ['La Liga', …]
    """
    if not competition:
        return None
    if isinstance(competition, str):
        return None if competition == 'all' else [competition]
    return list(competition) or None


def build_match_selector_options(
    results: list[dict],
    competitions: Optional[list[str]] = None,
) -> list[dict]:
    """
    Build dcc.Dropdown option dicts for a match selector.

    Args:
        results:      List of match result dicts from get_match_results().
        competitions: Optional list of competition names to filter to.
                      If None, all results are included.

    Returns:
        List of {'label': ..., 'value': match_id} dicts sorted newest first.
    """
    if competitions:
        results = [r for r in results if r['competition'] in competitions]

    results = sorted(results, key=lambda x: x['date'], reverse=True)

    show_tag = not competitions or len(competitions) > 1
    options: list[dict] = []
    for r in results:
        comp_tag = COMP_SHORT.get(r['competition'], r['competition'][:4])
        label = (
            f"{str(r['date'])[:10]}  vs  {r['opponent']}  ({r['result']})"
            + (f"  · {comp_tag}" if show_tag else '')
        )
        options.append({'label': label, 'value': r['match_id']})

    return options
