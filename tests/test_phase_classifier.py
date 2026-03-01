"""
test_phase_classifier.py
========================
Unit tests for the page_utils layer (pitch zones, possession utils, time utils).

Run with::

    pytest tests/test_phase_classifier.py -v

Note: Tests for the Phases of Play classifier (PhaseClassifier, SubPhase detectors,
etc.) have been removed because the ``pages.match_analysis_pages`` framework they
depended on no longer exists in the codebase. Only the lower-level page_utils
tests are retained here.

Test Data Conventions
---------------------
All synthetic events use the Opta 0-100 coordinate scale.
``period_id=1`` is used throughout to keep absolute-time arithmetic simple.
``outcome=1`` denotes a successful event; ``outcome=0`` denotes failure.
"""

from __future__ import annotations

import sys
import os

# Make the project root importable when running pytest from any directory.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pandas as pd
import pytest

from page_utils.pitch_zones import PitchZone, ZoneBoundaries, get_zone, is_in_penalty_box
from page_utils.possession_utils import (
    annotate_possession,
    compute_vertical_speed,
    is_stable_possession,
)
from page_utils.time_utils import events_within_window, format_seconds, to_seconds


TEAM_A = "FC Barcelona"
TEAM_B = "Real Madrid CF"


# ---------------------------------------------------------------------------
# Shared test fixtures
# ---------------------------------------------------------------------------

def _make_events(rows: list[dict]) -> pd.DataFrame:
    """Create a synthetic events DataFrame from a list of row dicts."""
    defaults = {
        "match_id":   "test_match",
        "event_id":   None,
        "event_type": "Pass",
        "team_name":  TEAM_A,
        "outcome":    1,
        "x":          50.0,
        "y":          50.0,
        "period_id":  1,
        "time_min":   0,
        "time_sec":   0,
    }
    data = []
    for i, row in enumerate(rows):
        merged = {**defaults, **row, "event_id": row.get("event_id", i + 1)}
        data.append(merged)
    return pd.DataFrame(data)


def _annotate(rows: list[dict]) -> pd.DataFrame:
    """Build and annotate a synthetic events DataFrame."""
    return annotate_possession(_make_events(rows))


# ---------------------------------------------------------------------------
# page_utils.pitch_zones
# ---------------------------------------------------------------------------

class TestPitchZones:
    def test_defensive_third(self):
        assert get_zone(10.0) == PitchZone.DEFENSIVE_THIRD

    def test_middle_third(self):
        assert get_zone(50.0) == PitchZone.MIDDLE_THIRD

    def test_final_third(self):
        assert get_zone(90.0) == PitchZone.FINAL_THIRD

    def test_exact_boundary_defensive(self):
        assert get_zone(33.3) == PitchZone.DEFENSIVE_THIRD

    def test_exact_boundary_final(self):
        assert get_zone(66.71) == PitchZone.FINAL_THIRD

    def test_out_of_range_returns_unknown(self):
        assert get_zone(-1.0)  == PitchZone.UNKNOWN
        assert get_zone(101.0) == PitchZone.UNKNOWN

    def test_custom_boundaries(self):
        wide_mid = ZoneBoundaries(defensive_end=20.0, middle_end=80.0)
        assert get_zone(50.0, wide_mid) == PitchZone.MIDDLE_THIRD
        assert get_zone(85.0, wide_mid) == PitchZone.FINAL_THIRD

    def test_penalty_box_inside(self):
        assert is_in_penalty_box(90.0, 50.0) is True

    def test_penalty_box_outside_x(self):
        assert is_in_penalty_box(75.0, 50.0) is False

    def test_penalty_box_outside_y(self):
        assert is_in_penalty_box(90.0, 10.0) is False


# ---------------------------------------------------------------------------
# page_utils.possession_utils
# ---------------------------------------------------------------------------

class TestPossessionUtils:
    def test_annotate_adds_abs_time_sec(self):
        df = _annotate([{"time_min": 5, "time_sec": 30, "period_id": 1}])
        assert "abs_time_sec" in df.columns
        assert df.iloc[0]["abs_time_sec"] == 5 * 60 + 30

    def test_annotate_period2_offset(self):
        df = _annotate([{"time_min": 50, "time_sec": 0, "period_id": 2}])
        expected = 45 * 60 + 50 * 60
        assert df.iloc[0]["abs_time_sec"] == expected

    def test_annotate_strips_team_setup(self):
        df = _annotate([
            {"period_id": 16, "event_type": "Team setp up"},
            {"period_id": 1,  "event_type": "Pass"},
        ])
        assert len(df) == 1
        assert df.iloc[0]["event_type"] == "Pass"

    def test_possession_team_ffill_through_neutral(self):
        df = _annotate([
            {"event_type": "Pass",  "team_name": TEAM_A},
            {"event_type": "Foul",  "team_name": TEAM_B},   # neutral — should not change possession
            {"event_type": "Pass",  "team_name": TEAM_A},
        ])
        assert df.iloc[1]["possession_team"] == TEAM_A

    def test_vertical_speed_positive(self):
        df = _annotate([
            {"x": 20.0, "time_min": 1, "time_sec": 0},
            {"x": 50.0, "time_min": 1, "time_sec": 10},
        ])
        speed = compute_vertical_speed(df)
        assert speed > 0.0

    def test_vertical_speed_zero_for_single_event(self):
        df = _annotate([{"x": 50.0}])
        assert compute_vertical_speed(df) == 0.0

    def test_stable_possession_true(self):
        df = _annotate([{"event_type": "Pass"}] * 5)
        assert is_stable_possession(df, min_events=3) is True

    def test_stable_possession_false_too_few(self):
        df = _annotate([{"event_type": "Pass"}] * 2)
        assert is_stable_possession(df, min_events=3) is False


# ---------------------------------------------------------------------------
# page_utils.time_utils
# ---------------------------------------------------------------------------

class TestTimeUtils:
    def test_to_seconds(self):
        assert to_seconds(2, 30) == 150

    def test_format_seconds(self):
        assert format_seconds(90) == "01:30"
        assert format_seconds(0)  == "00:00"

    def test_events_within_window_forward(self):
        df = _annotate([
            {"time_min": 0, "time_sec": 0},    # abs=0
            {"time_min": 0, "time_sec": 5},    # abs=5
            {"time_min": 0, "time_sec": 15},   # abs=15
        ])
        result = events_within_window(df, anchor_time=0, window_seconds=10)
        assert len(result) == 2

    def test_events_within_window_backward(self):
        df = _annotate([
            {"time_min": 0, "time_sec": 0},
            {"time_min": 0, "time_sec": 5},
            {"time_min": 0, "time_sec": 15},
        ])
        result = events_within_window(df, anchor_time=15, window_seconds=10, direction="backward")
        assert len(result) == 2

    def test_events_within_window_bad_direction(self):
        df = _annotate([{"time_min": 0, "time_sec": 0}])
        with pytest.raises(ValueError):
            events_within_window(df, 0, 10, direction="sideways")
