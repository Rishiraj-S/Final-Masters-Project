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
