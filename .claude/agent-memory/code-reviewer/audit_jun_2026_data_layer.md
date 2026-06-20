---
name: audit-jun-2026-data-layer
description: Deep bug audit of the data layer (data_utils, opposition_data_utils, event_utils, xg_utils, xt_utils, match_data_adapter) — Jun 2026
metadata:
  type: project
---

# Data Layer Audit — Jun 2026

## Confirmed bugs (reproduced via code reading)

### data_utils.py
- `_events_cache` / `_results_cache` have NO threading lock. `opposition_data_utils` has a `threading.Lock`; `data_utils` does not. Real race on Dash's threaded Flask server. Fix: add `_cache_lock = threading.Lock()` same pattern as opp utils.
- `get_match_results` guard `if _results_cache:` fails for empty list (evaluates False). Should be `if _results_cache is not None:`.
- `get_match_results` uses `if 'Barcelona' in match_info['home_team']` — fragile. Should use `team_code == 'BAR'`.
- `get_match_lineup` has no try/except around `pd.read_parquet` — partial pipeline writes crash the callback.
- `count_goals` in data_utils (returns `(int, int)`) name-clashes with `count_goals` in event_utils (returns `int`). Rename data_utils version.

### event_utils.py
- `_flag(series)` does raw `== "Si"` with no dtype guard. Boolean/int parquet columns return all-False silently.
- `get_ball_gains` uses `pd.concat` without `ignore_index=True` — duplicate index values in result.
- `pct_shot_on_target` double-filters: calls `get_shots_on_target(events)` on the original full frame instead of the pre-filtered `shots` frame — semantically inconsistent.

### xg_utils.py
- `_get_predictor()` not thread-safe (no lock). Double model load on concurrent cold start.
- Own-goal exclusion checks `own goal == 'Si'` which is NEVER set in the Opta data — own goals get xG predictions instead of NaN.
- `float(row.get('x') or 0)` does not guard against NaN (NaN is truthy, so `or 0` never fires for NaN).

### xt_utils.py / xT_model/predictor.py
- No column presence check before accessing `Pass End X` / `Pass End Y` — raises `KeyError` if caller passes non-pass frame.
- `_load()` singleton not thread-safe (minor — npy is small, double-load is harmless in practice).

### match_data_adapter.py
- `get_pass_network_data` line 983: positional alignment of `next_team` from `team.sort_values(...).shift(-1).values[:N]` is WRONG — aligns by position against all events, not against the pass subset. Produces arbitrary wrong team labels on edges.
- `get_counterattack_sequences` lower bound is `>= start_total` (inclusive), so the gain event itself is included in shot detection — can produce false-positive counter-attacks.
- `detect_possession_changes` sorts on `time_sec` without checking the column exists — `KeyError` if absent.
- `compute_momentum_timeline` filters `outcome == 1` across all positive_types including Goal — goals with NaN outcome are silently dropped from momentum buckets.
- `compute_territory_metrics` docstring says it "flips for away team" but the code does NOT flip (which is CORRECT per project coord convention). Docstring is actively misleading — must be fixed to prevent future spurious `100-x` flip additions.
- `identify_opponent_events` hardcodes `!= 'BAR'` — not reusable for non-Barcelona analysis.
- `_flag_is_set` line 63: double astype with inconsistent fillna — NaN handling is accidentally correct but fragile logic.

## Recurring anti-patterns found
1. Singleton lazy-load without threading lock (`xg_utils._get_predictor`, `xT_model/predictor._load`)
2. `pd.concat` without `ignore_index=True` on sub-filtered frames from a shared index
3. `== "Si"` qualifier checks without dtype coercion guard
4. Positional `.values[:N]` slicing used as a substitute for index-preserving join

**Why:** line (1) causes double model load; (2) causes duplicate index surprises downstream; (3) causes silent all-False on schema drift; (4) is outright wrong data alignment.

**How to apply:** Flag any new `pd.concat` missing `ignore_index`, any new singleton missing a lock, any `== "Si"` on a raw parquet column, and any `.values[:N]` pattern used for alignment.
