---
name: audit-match-report-jun2026
description: Deep bug audit of pages/match_report.py (5970 LOC monolith) — Jun 2026. Key bugs, anti-patterns, and confirmed safe patterns.
metadata:
  type: project
---

# match_report.py Deep Audit — Jun 2026

## Confirmed Bugs

### High Severity
1. **Coordinate flip in `_get_slot_coords` (line 296/314)**: Away team lineup dots are flipped with `100-x, 100-y`. Opta coordinates are already normalised — no flip is needed or correct. The mplsoccer VerticalPitch is always drawn from goal-end at bottom; away formation dots end up mirrored.
2. **Assist qualifier type mismatch (lines 819, 915, 5041, 5042)**: Most callsites use `pd.to_numeric(...) == 16` (int) which works, but line 5123 correctly uses string `'13','14','15','16'` for isin(). The inconsistency is not a crash but is fragile — if the column is ever left as string the numeric comparisons silently return 0.
3. **Score headline uses `compute_team_kpis` goals (line 5840)**: `compute_team_kpis` calls `count_goals()` which is own-goal-aware. This is correct. No bug here.
4. **Foul outcome filter in `_def_compute_half_stats` (line 2661)**: `fouls_committed = fouls_committed[fouls_committed['outcome'] == 1]`. Per Opta schema, outcome=1 on a Foul row means the foul was committed (not received). This is correct but fragile without a comment.
5. **`render_lsc_heatmap_img` and `render_xt_heatmap_img`: plt.close() NOT in finally block** (lines 389, 703). If an exception occurs mid-render (e.g. scipy KDE failure) `plt.close()` is never called, leaking a matplotlib figure. The `_generate_team_lineup_image` also lacks a `finally: plt.close(fig)` guard (line 368 closes only on the happy path for the `not sc_xs` branch).
6. **`_section_cb("goalkeeping", build_goalkeeping_tab)`** at line 5953: `build_goalkeeping_tab` populates `html.Div(id='gk-plots-content', ...)`. The GK selector callback then also outputs to `'gk-plots-content'`. But `_section_cb` puts this inside `pma-sec-goalkeeping`, so the `gk-plots-content` div only exists in the DOM when the goalkeeping section has been rendered. If the GK selector fires before goalkeeping section renders, there is no `gk-plots-content` in the DOM and Dash raises a non-fatal callback error. In practice this is unlikely (selector only shown when GK list > 1), but is a latent issue.
7. **`_compute_player_stats` uses `pe` not `events` for `add_xt_column`**: At line 5038, `add_xt_column(passes)` is called where `passes` is already per-player filtered — this is correct. No bug.

### Medium Severity
8. **`2nd assist` column not guaranteed present**: Line 5119-5123 checks `'2nd assist' in passes.columns` before accessing it (correct). But lines 1041-1042 use `pd.to_numeric(passes['Assist'], errors='coerce').isin([13,14,15])` without checking for the `'2nd assist'` qualifier, so pre-assist passes are not counted as key passes in `_compute_player_stats` (lines 5042). Inconsistency with `_compute_top5` (line 5123) which does count 2nd assists.
9. **PPDA denominator includes fouls filtered by outcome==1** (line 2661, 2665): `def_actions = len(tackles) + len(interceptions) + len(fouls_committed)`. The outcome==1 filter on fouls is applied in `_def_compute_half_stats` but NOT in `_def_compute` (line 2734 filters `fouls_df` for the display, but PPDA is computed in `_def_compute_half_stats`). In `_def_compute`, PPDA is not computed — it's only in `_def_compute_half_stats`, so this is fine. But the inconsistency is a maintenance trap.
10. **Extra time events not separated from H1/H2 splits**: All half-split logic (lines 668-673, 4932-4933) only splits on period_id==1 and period_id==2. For knockout matches with extra time (period_id==3,4), those events fall into neither H1 nor H2 but ARE included in the full-match totals, causing H1+H2 != Full for some stats.
11. **`_build_entries` uses `te_idx` from a reset-index view but looks up in `te_full`** (line 1515-1516): `ev` is `te_full[...].reset_index()`, so `ev.iloc[i]['index']` is the original index in `te_full`. Then `te_full.iloc[te_idx + 1: te_idx + 6]` uses `.iloc` with that original position. This is only correct if `te_full` itself has a zero-based integer index (it does, due to `reset_index()` at line 1469). But it's fragile — if the calling path changes, the index mismatch would produce wrong data silently.

### Low Severity
12. **`_atk_league_avg_cache`, `_league_avg_cache`, `_def_league_avg_cache` are module-level dicts** shared across all Dash workers in the same process. This is fine (they're intentionally a hot-path cache) but they are never cleared, so stale data after a pipeline update persists until app restart.
13. **Match flow chart (line 2492)**: goals are counted from raw `play['event_type'] == 'Goal'` including own goals without using `count_goals()`. The score ticker (h_sc, a_sc at lines 2498-2503) correctly assigns to the scoring team's position, but own goals (where the scoring team_position is the team that scored against themselves) would increment the wrong counter.
14. **`_generate_team_lineup_image` applies `is_home=True` for ALL calls** (line 361): Home lineup rendered correctly. Away lineup passed through `_get_slot_coords(formation, slot, True)` — always home. The flip `(100-x, 100-y)` is never applied because `is_home` is always hardcoded to `True`. This avoids the wrong coordinate-flip bug (see #1) by accident, not by design.

## Confirmed Safe Patterns
- PPDA zero-division guard: `if def_actions > 0 else 0.0` (line 2666) — safe.
- `render_lsc_heatmap_img`: handles `len(x) < 2` gracefully (falls through to single-scatter or nothing).
- `render_xt_heatmap_img`: handles `len(_x) < 2` — skips heatmap, still draws pitch and marginals with zero-height bars.
- Calendar month navigation: correct modular arithmetic with year wrap-around (lines 2713-2719).
- Calendar empty-month: `_build_calendar_grid` just shows an empty grid — no crash.
- Zone 14 boundaries: consistently y 37–63 everywhere in this file (lines 1502, 1959).
- No duplicate `pma-sec-*` IDs — `gk-plots-content` is nested inside `pma-sec-goalkeeping`, so no Dash Output collision.
- `exclude_own_goals()` is a no-op (own goal qualifier always 'N/A') — goal counts are owned by `count_goals()` which is used in GK section correctly.
- Transition 15s windows: timestamps computed as `time_min * 60 + time_sec` (seconds) consistently everywhere (lines 3347, 3360, 3381, 3869).

**Why:** Live Jun 2026 audit of the 5970-line monolith.
**How to apply:** Reference when reviewing any changes to match_report.py or when a user asks about GK section bugs, lineup coordinates, or transition window logic.
