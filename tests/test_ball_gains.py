"""
test_ball_gains.py
==================
Regression tests for ball-gain detection.

These guard against the case-sensitivity bug where modules filtered on the
non-existent event_type ``'Ball Recovery'`` (capital R) and the pseudo-string
``'Tackle Won'``. The canonical Opta event_type is ``'Ball recovery'`` (lowercase
r) and a won tackle is ``event_type == 'Tackle'`` with ``outcome == 1`` — so the
buggy literals silently matched zero rows and dropped real possession gains from
the radar/transition/defence analytics.

Run with::

    pytest tests/test_ball_gains.py -v
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pandas as pd

from utils.event_utils import (
    get_ball_gains,
    get_ball_recoveries,
    get_interceptions,
    get_successful_tackles,
)
from page_utils.possession_utils import POSSESSION_TAKING_EVENT_TYPES


def _events() -> pd.DataFrame:
    """A mixed events frame covering every gain type plus non-gains."""
    return pd.DataFrame(
        [
            {"event_type": "Ball recovery", "outcome": 1, "x": 40.0},  # gain
            {"event_type": "Ball recovery", "outcome": 1, "x": 60.0},  # gain (high)
            {"event_type": "Interception",  "outcome": 1, "x": 55.0},  # gain (high)
            {"event_type": "Tackle",        "outcome": 1, "x": 30.0},  # gain (won)
            {"event_type": "Tackle",        "outcome": 0, "x": 30.0},  # NOT a gain (lost)
            {"event_type": "Pass",          "outcome": 1, "x": 50.0},  # NOT a gain
            {"event_type": "Ball Recovery", "outcome": 1, "x": 50.0},  # bogus capital-R — must NOT count
        ]
    )


class TestGetBallGains:
    def test_includes_recoveries_interceptions_and_won_tackles(self):
        gains = get_ball_gains(_events())
        # 2 recoveries + 1 interception + 1 won tackle = 4. Lost tackle, Pass,
        # and the bogus capital-R row are excluded.
        assert len(gains) == 4
        counts = gains["event_type"].value_counts().to_dict()
        assert counts.get("Ball recovery") == 2
        assert counts.get("Interception") == 1
        assert counts.get("Tackle") == 1  # the won one only

    def test_excludes_lost_tackles(self):
        gains = get_ball_gains(_events())
        assert ((gains["event_type"] == "Tackle") & (gains["outcome"] == 0)).sum() == 0

    def test_capital_r_recovery_is_never_matched(self):
        # The historical bug: 'Ball Recovery' (capital R) does not exist in Opta data.
        gains = get_ball_gains(_events())
        assert (gains["event_type"] == "Ball Recovery").sum() == 0

    def test_high_gains_subset_uses_real_recoveries(self):
        gains = get_ball_gains(_events())
        gx = pd.to_numeric(gains["x"], errors="coerce")
        # x >= 50: one recovery (60) + one interception (55) = 2
        assert int((gx >= 50).sum()) == 2

    def test_empty_input_returns_empty(self):
        empty = pd.DataFrame({"event_type": [], "outcome": [], "x": []})
        assert len(get_ball_gains(empty)) == 0

    def test_components_are_disjoint(self):
        ev = _events()
        total = (
            len(get_ball_recoveries(ev))
            + len(get_interceptions(ev))
            + len(get_successful_tackles(ev))
        )
        assert total == len(get_ball_gains(ev))


class TestCanonicalSpelling:
    def test_possession_taking_uses_lowercase_recovery(self):
        assert "Ball recovery" in POSSESSION_TAKING_EVENT_TYPES
        assert "Ball Recovery" not in POSSESSION_TAKING_EVENT_TYPES

    def test_recovery_helper_matches_only_lowercase(self):
        ev = pd.DataFrame(
            [
                {"event_type": "Ball recovery", "outcome": 1},
                {"event_type": "Ball Recovery", "outcome": 1},  # bogus
            ]
        )
        assert len(get_ball_recoveries(ev)) == 1
