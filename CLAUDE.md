# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Run the app
python app.py                        # Starts on http://localhost:8050

# Run tests
pytest tests/test_phase_classifier.py -v     # Unit tests for page_utils layer
pytest tests/ -v                             # All tests

# Run a single test class or method
pytest tests/test_phase_classifier.py::TestPitchZones -v
pytest tests/test_phase_classifier.py::TestPossessionUtils::test_annotate_adds_abs_time_sec -v

# Barcelona data pipeline
python opta_pipeline/main.py                          # Full pipeline
python opta_pipeline/main.py --transform-only         # Re-transform without re-downloading
python opta_pipeline/main.py --competition Spain_Primera_Division

# Opposition scouting pipeline
python opposition_pipeline/main.py                    # All opponents
python opposition_pipeline/main.py --team "Chelsea"
python opposition_pipeline/main.py --transform-only
python opposition_pipeline/main.py --force-rescrape
```

Login credentials: `Guest / guest` (read-only) or `Rishi / admin` (admin, can trigger pipelines).

## Architecture

### App Skeleton

`app.py` is the single entry point. It initialises Dash, wires session-based auth via `dcc.Store`, routes URLs to page modules, and spawns pipeline subprocesses on admin request. Each page module exposes exactly two functions: `create_*_layout()` and `register_*_callbacks(app)`.

```
app.py
└── pages/
    ├── home.py                       ← Season overview + pipeline trigger UI
    ├── match_report.py               ← Match Report (was match_analysis.py)  /match-report
    ├── barca_dna.py                  ← Player analysis                       /barca-dna
    ├── barca_iq.py                   ← Team analysis                         /barca-iq
    ├── opposition_analysis.py                                                 /opposition-analysis
    ├── match_analysis_tabs/          ← 7 sub-tabs, shared constants in shared.py
    ├── team_analysis_tabs/           ← 7 sub-tabs (overview + 6 analytical)
    └── opposition_analysis_tabs/     ← 7 sub-tabs
```

**URL → page file mapping** (configured in `app.py:update_main_container`):

| URL | File | Layout function exported as |
|-----|------|-----------------------------|
| `/` | `home.py` | `create_home_layout` |
| `/match-report` | `match_report.py` | `create_match_analysis_layout` |
| `/barca-dna` | `barca_dna.py` | `create_player_analysis_layout` |
| `/barca-iq` | `barca_iq.py` | `create_team_analysis_layout` |
| `/opposition-analysis` | `opposition_analysis.py` | `create_opposition_analysis_layout` |

> Note: the old `match_analysis.py`, `player_analysis.py`, and `team_analysis.py` files have been removed. Do not reference them.

### Flask Route — PDF Report

`app.py` registers a Flask route at `/download-report/<match_id>` that bypasses Dash callbacks and serves a PDF via `utils/pdf_report.py:generate_match_report_pdf(match_id)`.

### Navigation

`utils/config.py` → `NAV_LINKS` defines the navbar order:

```
Home  |  Barça DNA  |  Barça IQ  |  Match Report  |  Opposition Analysis
```

### Data Layer

All Barcelona data is loaded exclusively through `utils/data_utils.py`. Data lives at `data/barcelona/result/{Competition}/{Season}/{match|match_event|lineup}/`. The module maintains an in-process cache (`_events_cache`) that must be cleared via `clear_events_cache()` after a pipeline run — page reloads alone do not clear it.

Opposition data is accessed through `utils/opposition_data_utils.py`, stored at `data/opposition/{Country}/{Team}/{Competition}/{Season}/`.

### page_utils — Shared Analytical Helpers

`page_utils/` contains canonical definitions that must be imported, never redefined locally:
- `competitions.py` — `ALL_COMPETITIONS`, `COMP_SHORT`, `normalize_competitions()`, `build_match_selector_options()`
- `event_filters.py` — `SHOT_TYPES`, `DEF_ACTION_TYPES`, `DEF_COLORS`, `SHOT_OUTCOME_COLOR`, `SHOT_OUTCOME_SYMBOL`, `filter_by_period()`, `split_by_halves()`
- `visualizations.py` — `HOME_COLOR`, `AWAY_COLOR`, `GOLD`, `CHART_CONFIG`, `CHART_LAYOUT_DEFAULTS`, and all pitch-drawing utilities
- `pitch_zones.py` — `PitchZone`, `ZoneBoundaries`, `get_zone()`, `is_in_penalty_box()`
- `possession_utils.py` — `annotate_possession()`, `compute_vertical_speed()`, `is_stable_possession()`
- `time_utils.py` — `to_seconds()`, `format_seconds()`, `events_within_window()`

### Tab Inventory

**match_analysis_tabs/** (7 tabs, used by `match_report.py`):

| File | Builder | Callbacks |
|------|---------|-----------|
| `overview.py` | `build_overview_tab` | `register_overview_callbacks` |
| `attacking_output.py` | `build_attacking_output_tab` | — |
| `build_up_passing.py` | `build_build_up_passing_tab` | `register_build_up_passing_callbacks` |
| `defensive_structure.py` | `build_defensive_structure_tab` | `register_defensive_structure_callbacks` |
| `transitions_counterpressing.py` | `build_transitions_counterpressing_tab` | `register_transitions_counterpressing_callbacks` |
| `goalkeeping.py` | `build_goalkeeping_tab` | `register_goalkeeping_callbacks` |
| `player_stats.py` | `build_player_stats_tab` | `register_player_stats_callbacks` |

Score headline callback lives in `match_report.py` (not in `overview.py`).

**team_analysis_tabs/** (used by `barca_iq.py`):

`overview`, `buildup`, `chance_creation`, `def_structure`, `transitions` (split across `attacking_transition.py` + `defensive_transition.py`), `set_pieces`

### Pitch Plots

All pitch visualisations use `mplsoccer` rendered server-side to base64 PNG via `page_utils/visualizations.py`. Use `pitch.scatter()` not `mpatches.Circle` — patches distort with axis aspect ratio.

**Coordinate convention**: x=0 is own goal, x=100 is opponent goal, for **both** home and away teams. Opta data is already normalised per team. Do **not** apply `100 - x` to away team coordinates.

Zone boundaries (both teams, no flip needed):
- Final Third: `x > 66.67`
- Zone 14: `y` 37–63
- Half Spaces: `y` 21–37 and 63–79

### xG Model

`xg_model/predictor.py` contains `XGPredictor` (open play), `XGDFKPredictor` (direct free kicks), `XGPenaltyPredictor` (penalties), and `XGRouter` which auto-routes. The bridge to Opta data is `utils/xg_utils.py` → `add_xg_column(shots_df)`. The predictor is a lazy singleton loaded once on first call.

### Pipeline Architecture

Both pipelines (Barcelona and opposition) share the same modules from `opta_pipeline/modules/`. The pipeline stages are Scrape → Download → Transform, each writing Parquet files. `opta_pipeline/main.py` writes `logs/progress.json` after each step; `app.py` polls this every 2 s for live UI updates.

**Typo note**: `"Team setp up"` (typeId=34) exists intentionally in both `mappings/opta_event_types.csv` and `matchevent_transformer.py:156` — they are consistent with each other. Fix both together or neither.

### UI / Styling

Color tokens are in `utils/config.py` (`COLORS` dict — only `COLORS`, `APP_CONFIG`, `NAV_LINKS` remain) and mirrored as CSS variables in `assets/style.css`. Import from `page_utils/visualizations.py` for pitch plot constants (`HOME_COLOR`, `AWAY_COLOR`, `GOLD`). Image paths in `home.py` use the format `'assets/...'` (no leading `/`).
