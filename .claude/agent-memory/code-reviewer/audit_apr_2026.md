---
name: Codebase Audit April 2026
description: Full sweep findings from April 2026 review — recurring anti-patterns, fragility points, confirmed conventions
type: project
---

Comprehensive audit of CuléVision codebase (April 2026).

**Why:** Full code review requested by user across app.py, pages/, page_utils/, utils/.

**How to apply:** Use as reference when reviewing any of the flagged files or patterns.

## Confirmed Architectural Conventions
- Coordinate system: Opta data is per-team normalised — x=0 own goal, x=100 opponent goal for BOTH teams. No `100-x` flip should ever be applied to Opta pitch event coordinates.
- EXCEPTION: The `100-x` transform IS correct and intentional when rotating coordinates for a VERTICAL half-pitch display (mapping Opta x→fig_y, Opta y→fig_x via `100-y`). This is a display axis rotation, not a team coordinate flip. Seen in attacking_output.py and opposition_analysis_tabs.
- The `_COORDS` dict in `overview.py` uses HOME-perspective x values (0-48 range). The `is_home=False` `100-x, 100-y` flip in `_get_slot_coords()` IS correct and intentional — these are not Opta event coordinates but rendering coordinates for the lineup pitch image.

## Recurring Anti-Patterns Found

### 1. Local re-definition of shared constants (Medium severity, widespread)
Files that locally redefine `_SHOT_TYPES` instead of importing from `page_utils.event_filters.SHOT_TYPES`:
- `pages/match_analysis_tabs/build_up_passing.py:230`
- `pages/match_analysis_tabs/attacking_output.py:35`
- `pages/match_analysis_tabs/goalkeeping.py:55`
- `pages/match_analysis_tabs/player_stats.py:30`
- `pages/match_analysis_tabs/transitions_counterpressing.py:44`
- `pages/match_analysis_tabs/defensive_structure.py:44` (also redefines `_DEF_ACTION_TYPES`)
- `pages/opposition_analysis_tabs/set_pieces.py:105` (ALSO missing 'Blocked Shot')
- `pages/opposition_analysis_tabs/overview.py:192` (defined inside a function)
- `pages/opposition_analysis_tabs/chance_creation.py:36`
- `pages/opposition_analysis_tabs/buildup_attack.py:108`
- `pages/opposition_analysis_tabs/defence.py:59`

`_COMP_SHORT` is still locally defined in:
- `pages/team_analysis_tabs/overview.py:60` (not imported from page_utils.competitions)

### 2. PITCH_AXIS_FULL and CHART_CONFIG re-defined locally
These are re-defined in `pages/team_analysis_tabs/buildup.py` and `pages/opposition_analysis_tabs/buildup.py` / `buildup_attack.py` instead of importing from `page_utils.visualizations`.
PITCH_BG = '#151932' is also copy-pasted into ~10 files.

### 3. `_build_entries` docstring has stale comment
`pages/match_analysis_tabs/build_up_passing.py:237`: docstring says "coords already flipped for away teams" — this is incorrect/misleading. No flip is applied; Opta data is already normalised. The comment should be removed.

### 4. `is_in_penalty_box` called with hardcoded y=50
`pages/match_analysis_tabs/attacking_output.py:142,165`: `is_in_penalty_box(float(x), 50)` — passes a fixed y=50 instead of the shot's actual y coordinate. This underestimates box shots significantly. A shot at x=85, y=10 (near the byline but wide of the box) would incorrectly be counted as a box shot.

### 5. `get_all_teams()` iterrows anti-pattern
`utils/data_utils.py:659`: Uses `iterrows()` over parquet files to extract team names. Should use vectorised `df['team_name'].unique()` / `df[['team_name','team_code']].drop_duplicates()` on the aggregated frame.

### 6. `get_team_season_stats()` season filter is fragile
`utils/data_utils.py:757-761`: Filters results by checking if the 4-char year string of `r['date']` is in a list. This breaks for multi-year seasons that span Jan-Dec of year+1 for non-calendar seasons, and depends on `r['date']` being a string/datetime whose str representation starts with 4-digit year. The events are already filtered by season, but results (from `get_match_results()`) are not season-filtered — this filter is an approximation.

### 7. Opposition pipeline `print()` in production code
`opposition_pipeline/main.py` has extensive `print()` statements alongside `logger.*` calls. Acceptable for a CLI tool that runs in a subprocess, but inconsistent — some messages only go to logger, some only to print, some to both.

### 8. `app.py` debug=True in production
`utils/config.py:31`: `'debug': True` — Dash debug mode should be False in production to avoid the debug toolbar and hot-reload overhead. Low priority for a local tool, but worth noting.

## Known Correct Patterns (do not flag)
- `100-x` in `_get_slot_coords(overview.py)` — correct, these are rendering coordinates for the lineup pitch image, not Opta event coordinates
- `100-y` / `100-x` used as axis mapping for vertical pitch displays (attacking_output.py, opposition tabs) — this is a coordinate axis rotation for display purposes, not a team flip
- "Team setp up" typo in both matchevent_transformer.py:156 and opta_event_types.csv — intentional consistency
- `_events_cache` in data_utils.py only caches non-empty results — correct defensive behaviour
- `team_analysis_tabs/` directory is live (not a ghost) — all 8 source files exist (overview, buildup, chance_creation, def_structure, transitions, attacking_transition, defensive_transition, set_pieces)
- `compute_5d_scores` empty pool fallback: barca_dna.py line 1134 does `if not pool: pool = [player_stats]` — always passes at least 1 element, no division risk
- `event_type_id` vs `type_id`: opposition_analysis.py and opposition_analysis_tabs/ do not reference either integer ID column directly — filtering is done via `event_type` string column

## Jun 2026 Pipeline & ML Model Audit — Confirmed Bugs

### 16. xT_model/train.py:49 — glob at wrong path (CRITICAL)
`load_events()` globs `data/barcelona/result/` and `data/opposition/`. Both paths are gone. Current root is `data/2025-26/`. Any retrain produces a model trained on 0 events. Shipped xt_grid.npy is valid for inference. Fix: change both glob strings to `data/2025-26/**/match_event/*.parquet`.

### 17. main.py:471-481 — Phase 1 scraping runs even with --transform-only (HIGH)
`get_scraped_matches()` is called unconditionally in Phase 1. With a cold scrape cache, `--transform-only` still launches a Selenium browser. With a warm cache it's a cheap CSV read, but the intent is violated. Fix: gate Phase 1 inside `if not args.transform_only`.

### 18. base_transformer.py:78 — _output_exists glob matches partial IDs (HIGH)
`glob(f"*{match_id}*")` is a substring match. match_id "123" matches a file for match "1234" in the same dir. This silently skips transforms. Fix: use `glob(f"*_{match_id}.*")` or anchor with full suffix.

### 19. pdf_report.py:331 — temp file leak on PDF generation failure (MEDIUM)
`os.unlink(tmp)` is inside `try`, not `finally`. If `execute_cdp_cmd` raises, the temp HTML file leaks. Fix: move unlink into `finally` block with `if os.path.exists(tmp): os.unlink(tmp)`.

### 20. pdf_report.py — _HTMLReport class is dead code (~250 lines) (LOW)
`_HTMLReport` and `_tab_figures_to_pdf()` are never called by `generate_match_report_pdf()`. The live path uses `_REPORT_SHELL` + `_selenium_html_to_pdf()` directly.

### 21. xg_utils.py:36-42 — xG lazy singleton not thread-safe (LOW)
`_get_predictor()` checks `if _predictor is None` without a lock. Under Dash's threaded mode, concurrent callbacks can both enter the branch and both load XGRouter. Python GIL makes the assignment atomic so only one instance persists, but both model loads run concurrently (3 XGBoost files × 2 threads = 6 file reads). Fix: wrap with `threading.Lock()`.

### 22. pdf_report.py:766 — _logo_b64 uses relative path (LOW)
`open(p.lstrip('/'), 'rb')` strips the leading slash and uses a CWD-relative path. If Flask's CWD is not the project root, logo is silently dropped. Fix: resolve against `Path(__file__).parent.parent`.

## Jun 2026 Page Module Audit — Additional Bugs Found

### 9. Admin security bypass — `handle_database_update` (app.py:751) [HIGH]
The callback does NOT include `State('session-store')` and never checks role. UI elements are admin-only conditional, but callback fires unconditionally. A crafted Dash request can trigger pipeline as guest.
Fix: Add `State('session-store', 'data')` and check `if not session or session.get('role') != 'admin': raise PreventUpdate`.

### 10. App.py callback references IDs that only exist for admin users [MEDIUM]
`handle_database_update` references `Input('update-db-button')`, `State('opp-team-select')`, `State('opp-comp-select')`, `State('opp-pipeline-options')`. These components are only in the DOM when admin user is on the home page. Dash logs callback errors for guest users.

### 11. `fouls_won` always zero in barca_dna.py:1374-1376 [HIGH]
`fouls_total_rows` counts Foul events in `p_ev` (which is already filtered to `team_code == "BAR"` and `player_name == player`). Foul rows are stored per-committing-team — so this counts the player's own committed fouls, identical to `fouls_committed`. The subtraction yields 0 always.

### 12. `touches_box` ignores y-coordinate (barca_dna.py:1372) [MEDIUM]
`(x_num >= 83).sum()` overcounts — includes touches past x=83 but wide of the box (y < 21.1 or y > 78.9). Should use `is_in_penalty_box(x, y)` from `page_utils.pitch_zones`.

### 13. `get_successful_tackles/ball_recoveries/interceptions` called 3× each in `update_defending_panel` (barca_dna.py:1452-1463) [MEDIUM]
Each getter scans the full DataFrame. Cache results before the ternary.

### 14. `render_ta_content` missing `prevent_initial_call` (barca_iq.py:274) [LOW]
Triggers heavy data load on initial page load. Should add `prevent_initial_call=True` or guard with `if not match_data: return html.Div()`.

### 15. `_laliga_player_pool` global cache not thread-safe (barca_dna.py:229) [LOW]
Module-level global written without a lock. Under threaded Dash, two simultaneous requests can both rebuild and write. Low impact (idempotent write, same result) but worth noting.
