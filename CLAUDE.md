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

# Unified data pipeline (handles Barcelona + all opponents)
python opta_pipeline/main.py                                    # All teams, all competitions
python opta_pipeline/main.py --team "Barcelona"                 # Single team
python opta_pipeline/main.py --team "Chelsea"
python opta_pipeline/main.py --competition Spain_Primera_Division
python opta_pipeline/main.py --transform-only                   # Re-transform without re-downloading
python opta_pipeline/main.py --skip-download                    # Scrape + transform only, no browser
python opta_pipeline/main.py --force-rescrape                   # Ignore CSV cache, re-scrape pages
```

Login credentials: `Guest / guest` (read-only) or `Rishi / admin` (admin, can trigger pipelines).

## Architecture

### App Skeleton

`app.py` is the single entry point. It initialises Dash, wires session-based auth via `dcc.Store`, routes URLs to page modules, and spawns pipeline subprocesses on admin request. Each page module exposes exactly two functions: `create_*_layout()` and `register_*_callbacks(app)`.

```
app.py
└── pages/
    ├── home.py                       ← Season overview + pipeline trigger UI
    ├── match_report.py               ← Match Report (phase-based post-match)  /match-report
    ├── barca_dna.py                  ← Player analysis                        /barca-dna
    ├── barca_iq.py                   ← Team analysis                          /barca-iq
    ├── opposition_analysis.py                                                  /opposition-analysis
    ├── match_analysis_tabs/          ← 7 sub-tabs, shared constants in shared.py
    ├── team_analysis_tabs/           ← 6 sub-tabs (overview + 5 analytical)
    └── opposition_analysis_tabs/     ← 6 sub-tabs
```

**URL → page file mapping** (configured in `app.py:update_main_container`):

| URL | File | Layout function |
|-----|------|-----------------|
| `/` | `home.py` | `create_home_layout` |
| `/match-report` | `match_report.py` | `create_match_analysis_layout` |
| `/barca-dna` | `barca_dna.py` | `create_player_analysis_layout` |
| `/barca-iq` | `barca_iq.py` | `create_team_analysis_layout` |
| `/opposition-analysis` | `opposition_analysis.py` | `create_opposition_analysis_layout` |

### Flask Route — PDF Report

`app.py` registers a Flask route at `/download-report/<match_id>` that bypasses Dash callbacks and serves a PDF via `utils/pdf_report.py:generate_match_report_pdf(match_id)`.

### Navigation

`utils/config.py` → `NAV_LINKS` defines the navbar order:

```
Home  |  Barça DNA  |  Barça IQ  |  Match Report  |  Opposition Analysis
```

### Data Layer

**Barcelona data** — loaded exclusively through `utils/data_utils.py`. Parquet files live at `data/2025-26/{Country}/{Competition}/{subdir}/`. The module filters by `_BAR_vs_` or `_vs_BAR_` in filenames. Maintains an in-process cache (`_events_cache`) cleared via `clear_events_cache()` after pipeline runs.

**Opposition data** — accessed through `utils/opposition_data_utils.py`, same `data/2025-26/` root. Filters by team code in filenames. Important: the module renames `event_type_id` → `type_id` on load, so opposition tab modules use `type_id` not `event_type_id`. All event-filtering functions use the `team_code` column — never `team_name` substring matching — because Opta stored names frequently differ from config display names. Always use `get_team_codes(team_name)` → `df['team_code'].isin(codes)`. After any pipeline run, both `clear_events_cache()` and `clear_opp_events_cache()` must be called (app.py does this automatically).

Both modules read from `data/2025-26/{Country}/{Competition}/{subdir}/` — there is no separate `data/barcelona/` or `data/opposition/` directory.

### Utils Layer

| Module | Purpose |
|--------|---------|
| `utils/event_utils.py` | Canonical event-extraction functions — **always use these, never filter inline** |
| `utils/match_data_adapter.py` | Phase-tagged match analysis: possession, transitions, set pieces, counterpress, pass networks |
| `utils/player_analysis/metrics.py` | `compute_player_stats(events_df)` → stat dict; `get_player_percentiles()`, `get_player_ratings()` → A–D grades; `POSITION_PIZZA_ATT` / `POSITION_PIZZA_DEF` dicts define which metrics appear on the radar per position role |
| `utils/player_analysis/wyscout_weights.py` | Wyscout position weights loaded from `assets/wyscout_weights/*.xlsx` |
| `utils/logos.py` | `get_team_logo_path()`, `get_tournament_logo_path()`, `get_country_flag_path()` — maps data names to asset paths |
| `utils/xg_utils.py` | `add_xg_column(shots_df)` bridge to the xG model |
| `utils/xt_utils.py` | `add_xt_column(passes_df)` bridge to the xT model — adds `xT` column to pass DataFrames |
| `utils/config.py` | `COLORS`, `APP_CONFIG`, `NAV_LINKS` only |

### Event Helpers — `utils/event_utils.py`

**Always import from here instead of filtering inline.** The functions encode the correct qualifier conventions from the parquet schema.

```python
from utils.event_utils import (
    # ── Event type selectors ──────────────────────────────────────────
    get_passes, get_shots, get_shots_on_target, get_goals,
    get_tackles, get_successful_tackles,
    get_interceptions, get_ball_recoveries, get_clearances,
    get_aerials, get_aerial_wins,
    get_take_ons, get_successful_take_ons,
    get_challenges, get_successful_challenges,
    get_fouls, get_penalty_fouls,
    get_cards, get_yellow_cards, get_second_yellow_cards, get_red_cards,
    get_touches, get_corners, get_saves, get_errors, get_dispossessions,

    # ── Pass sub-types ────────────────────────────────────────────────
    get_accurate_passes,
    get_goal_assists,      # Assist == 16  (pass led to a Goal)
    get_key_passes,        # Assist in [13,14,15]  (pass led to a non-goal shot)
    get_any_assist_passes, # Assist in [13-16]
    get_long_balls, get_crosses, get_through_balls, get_head_passes,
    get_chipped_passes, get_switch_passes,
    get_free_kick_passes, get_corner_passes,
    get_own_half_passes, get_opposition_half_passes, get_progressive_passes,

    # ── Shot sub-types ────────────────────────────────────────────────
    get_big_chances, get_headed_shots, get_direct_free_kick_shots,
    get_assisted_shots, get_box_shots,

    # ── Rate helpers (return float 0-100) ─────────────────────────────
    pct_pass_accuracy, pct_aerial_win, pct_take_on,
    pct_shot_on_target, pct_cross_accuracy, pct_long_ball_accuracy,
    pct_tackle_success,

    # ── Count helpers (return int) ────────────────────────────────────
    count_appearances, count_goal_assists, count_key_passes,
    count_shots, count_shots_on_target, count_total_minutes,

    # ── Own goal handling ─────────────────────────────────────────────
    filter_out_opponent_goals,  # drop Goals scored by the other team_code

    # ── Composite stats dict ──────────────────────────────────────────
    compute_event_stats,  # full aggregate dict from any filtered events DF
)
```

Key `compute_event_stats` output keys: `apps`, `total_minutes`, `mins_per_app`, `touches`, `goals`, `goals_app`, `assists`, `assists_app`, `shots`, `shot_acc`, `goal_conv`, `key_passes`, `key_passes_app`, `passes`, `pass_acc`, `own_h_acc`, `opp_h_acc`, `long_ball_acc`, `cross_acc`, `through_balls`, `tackles`, `tackle_pct`, `intercepts_app`, `recoveries_app`, `clearances_app`, `aerials`, `aerial_win_pct`, `take_ons`, `takeon_pct`, `duel_pct`, `fouls`, `penalty_fouls`, `yellow_cards`, `red_cards`, `dispossessions`.

### page_utils — Shared Analytical Helpers

`page_utils/` contains canonical definitions that must be imported, never redefined locally:
- `competitions.py` — `ALL_COMPETITIONS`, `COMP_SHORT`, `normalize_competitions()`, `build_match_selector_options()`
- `event_filters.py` — `SHOT_TYPES`, `DEF_ACTION_TYPES`, `DEF_COLORS`, `SHOT_OUTCOME_COLOR`, `SHOT_OUTCOME_SYMBOL`, `filter_by_period()`, `split_by_halves()`
- `visualizations.py` — `HOME_COLOR`, `AWAY_COLOR`, `GOLD`, `CHART_CONFIG`, `CHART_LAYOUT_DEFAULTS`, and all pitch-drawing utilities. Key renderers: `render_lsc_heatmap_img` (positional KDE heatmap), `render_xt_heatmap_img(x, y, xt)` (16×12 grid xT heatmap, gold colormap)
- `pitch_zones.py` — `PitchZone`, `ZoneBoundaries`, `get_zone()`, `is_in_penalty_box()`
- `possession_utils.py` — `annotate_possession()`, `compute_vertical_speed()`, `is_stable_possession()`
- `time_utils.py` — `to_seconds()`, `format_seconds()`, `events_within_window()`

### Tab Inventory

**match_analysis_tabs/** (7 tabs, used by `match_report.py`):

| File | Builder | Callbacks | Notes |
|------|---------|-----------|-------|
| `overview.py` | `build_overview_tab` | `register_overview_callbacks` | TV stat bars show H1/H2 half splits in brackets |
| `attacking_output.py` | `build_attacking_output_tab` | — | |
| `build_up_passing.py` | `build_build_up_passing_tab` | `register_build_up_passing_callbacks` | |
| `defensive_structure.py` | `build_defensive_structure_tab` | `register_defensive_structure_callbacks` | Defensive action map includes fouls + offsides overlays |
| `transitions_counterpressing.py` | `build_transitions_counterpressing_tab` | `register_transitions_counterpressing_callbacks` | Two sub-tabs: Defensive Transition + Attacking Transition; 30s windows after possession changes; both teams side-by-side |
| `goalkeeping.py` | `build_goalkeeping_tab` | `register_goalkeeping_callbacks` | |
| `player_stats.py` | `build_player_stats_tab` | `register_player_stats_callbacks` | Player table now includes `xT` column per player |

Score headline callback lives in `match_report.py` (not in `overview.py`).

**team_analysis_tabs/** (6 tabs, used by `barca_iq.py`):

`overview`, `buildup`, `chance_creation`, `def_structure`, `transitions` (orchestrates `attacking_transition.py` + `defensive_transition.py`), `set_pieces`

**opposition_analysis_tabs/** (6 tabs, used by `opposition_analysis.py`):

`overview`, `buildup`, `chance_creation`, `transitions`, `defence`, `set_pieces`

`helpers.py` — `no_data(msg)` uniform placeholder used by all six tab builders when a data query returns empty.

### Pitch Plots

All pitch visualisations use `mplsoccer` rendered server-side to base64 PNG via `page_utils/visualizations.py`. Use `pitch.scatter()` not `mpatches.Circle` — patches distort with axis aspect ratio.

**Coordinate convention**: x=0 is own goal, x=100 is opponent goal, for **both** home and away teams. Opta data is already normalised per team. Do **not** apply `100 - x` to away team coordinates.

Zone boundaries (both teams, no flip needed):
- Final Third: `x > 66.67`
- Zone 14: `y` 37–63
- Half Spaces: `y` 21–37 and 63–79

### xG Model

`xg_model/predictor.py` contains `XGPredictor` (open play), `XGDFKPredictor` (direct free kicks), `XGPenaltyPredictor` (penalties), and `XGRouter` which auto-routes. The bridge to Opta data is `utils/xg_utils.py` → `add_xg_column(shots_df)`. The predictor is a lazy singleton loaded once on first call.

### xT Model

Grid-based Expected Threat model following the Soccermatics/Bellman-equation approach.

| File | Purpose |
|------|---------|
| `xT_model/train.py` | Training script — loads all Opta parquets from `data/2025-26/**/match_event/`, builds 16×12 grid via Bellman iteration, saves `xt_grid.npy` |
| `xT_model/predictor.py` | Lazy-singleton inference — `predict_xt(x1,y1,x2,y2)` and `add_xt_column(passes_df)` |
| `xT_model/xt_grid.npy` | Trained artifact — (16, 12) array of xT values |
| `utils/xt_utils.py` | Public bridge — `add_xt_column(passes_df)` adding an `xT` column to any Opta pass DataFrame |

**Retrain**: `python xT_model/train.py` — reads from `data/2025-26/**/match_event/`.

**Known limitation**: Ball carries are not Opta events. Wingers/progressive midfielders are under-credited vs. pure passers in any per-player xT ranking.

### Pipeline Architecture

`opta_pipeline/` is the single unified pipeline for all teams. Stages: Scrape → Download → Transform, each writing Parquet files to `data/2025-26/{Country}/{Competition}/{subdir}/`. `opta_pipeline/main.py` writes `logs/progress.json` after each step; `app.py` polls it every 2 s for live overlay updates.

Two-phase design:
- **Phase 1**: Scrape each competition page once; cache as CSV in `logs/scrape_cache/`
- **Phase 2**: For each team × competition, filter cached CSV by team name, download missing JSONs, transform to parquet

**Typo note**: `"Team setp up"` (typeId=34) exists intentionally in both `mappings/opta_event_types.csv` and `opta_pipeline/modules/transformers/matchevent_transformer.py:156` — they are consistent. Fix both together or neither.

### Event Data Reference (from actual parquet files)

Each parquet in `data/2025-26/{Country}/{Competition}/match_event/` has **250 columns** and covers all events from both teams in the match.

#### Core fields (always present)
| Column | Values / Notes |
|--------|---------------|
| `event_type` | String. See event types below. |
| `event_type_id` | Integer. |
| `outcome` | `1` = success, `0` = failure (integer). Present on Pass, Tackle, Take On, Aerial, Interception, Ball recovery. Interceptions and Ball recoveries are always `1`. |
| `x`, `y` | Float. Pitch coordinates (0–100). x=0 own goal, x=100 opponent goal. |
| `team_code` | `'BAR'` for Barcelona, opponent code otherwise. All events from both teams are in each file. |
| `position` | Opta position string: `GK, CB, LB, RB, LWB, RWB, CDM, CM, MC, CAM, LM, RM, LW, RW, CF`. `'N/A'` when missing. |
| `player_name` | String. |
| `Jersey Number` | String (e.g. `'9'`). |
| `Pass End X`, `Pass End Y` | Float. Destination coordinates for pass events. Always populated on passes. |
| `Length`, `Angle` | Float. Pass distance and angle. Always populated on passes. |
| `Zone` | `'Back'`, `'Center'`, `'Right'`, `'Left'`, `'N/A'`. Pitch zone from the player's perspective. |

#### Event types (full list with IDs)
```
Pass (1)              Ball recovery (49)    Take On (3)
Foul (4)              Aerial (44)           Tackle (7)
Interception (8)      Save (10)             Saved Shot (15)
Miss (13)             Goal (16)             Post (14)
Blocked Pass (74)     Clearance (12)        Dispossessed (50)
Ball touch (61)       Challenge (45)        Out (5)
Corner Awarded (6)    Offside Pass (2)      Offside provoked (55)
Card (17)             Error (51)            Keeper pick-up (52)
Player Off (18)       Player on (19)        Formation change (40)
Punch (41)            Keeper Sweeper (59)   Shield ball opp (56)
Good skill (42)       Chance missed (60)    Deleted event (43)
Start/End/Start delay/End delay (32/30/27/28)
Team setp up (34)     [note: intentional typo]
```

**Important**: `'Ball recovery'` is lowercase-r — `events["event_type"] == "Ball recovery"`.

#### Pass qualifiers (boolean: `'Si'` present, `'N/A'` absent)
| Qualifier | Meaning |
|-----------|---------|
| `Long ball` | Long aerial pass |
| `Cross` | Crossing pass from wide area |
| `Head pass` | Pass played with the head |
| `Through ball` | Ball played through for a run |
| `Chipped` | Chipped/lobbed pass |
| `Launch` | Goal-kick or long hoof launch |
| `Lay-off` | One-touch lay-off |
| `Flick-on` | Flick-on header/touch |
| `Pull Back` | Pull-back from byline |
| `Switch of play` | Ball switched across the pitch |
| `Free kick taken` | Pass taken from a free kick |
| `Corner taken` | Pass taken from a corner |
| `Throw In` | Throw-in |
| `Goal Kick` | Goal kick |
| `Keeper Throw` | Goalkeeper throw |
| `Gk kick from hands` | GK distribution from hands |
| `Right footed` / `Left footed` | Foot used |
| `High` | Ball played in the air |
| `From corner` | Pass originating from a corner |
| `Fast break` | Pass during fast break |
| `Intentional Assist` | Pass was an intentional assist (no deflection) |
| `Inswinger` / `Outswinger` / `Straight` | Corner/cross delivery type |
| `2nd assist` | Pass that led to the assist pass |

#### `Assist` qualifier on passes (numeric)
The `Assist` column contains the **event type ID of the resulting shot**:
- `'13'` → assisted a **Miss** (key pass)
- `'14'` → assisted a **Post** (key pass)
- `'15'` → assisted a **Saved Shot** (key pass)
- `'16'` → assisted a **Goal** (goal assist)
- `'N/A'` → not an assist

All assist passes have `outcome == 1`. Correct formulas:
```python
goal_assists = pass_rows['Assist'] == '16'          # or == 16 after pd.to_numeric
key_passes   = (
    pass_rows['Assist'].isin(['13','14','15'])       # direct key pass (pass leading to shot)
    | (pass_rows.get('2nd assist', 'N/A') == 'Si')  # 2nd assist / pre-assist (pass leading to assist pass)
)
any_assist   = pass_rows['Assist'].isin(['13','14','15','16']) | (pass_rows.get('2nd assist', 'N/A') == 'Si')
```
**Do not use** `Leading to attempt` or `Leading to goal` for assists — those are qualifiers on **Error (type 51)** events containing the related event ID, not pass qualifiers.

#### Shot qualifiers
| Qualifier | Meaning |
|-----------|---------|
| `Head` | Header |
| `Right footed` / `Left footed` | Foot used |
| `Big Chance` | Tagged as a big chance (`'Si'`) |
| `Assisted` | Shot was assisted (`'Si'` on the shot event, not the pass) |
| `Intentional Assist` | Assist was intentional |
| `Direct free` | Direct free kick shot |
| `Regular play` / `Fast break` / `From corner` / `Set piece` | Situation |
| `Small box-centre`, `Box-centre`, `Box-right`, `Box-left`, ... | Shot location zones |
| `Goal Mouth Y Coordinate`, `Goal Mouth Z Coordinate` | Goal mouth position (float strings) |
| `own goal` | **Always `'N/A'`** — own goals are NOT flagged with this qualifier. Own goals are identified by the scoring player's `team_code` not matching the conceding team's code (i.e. an opponent-team player's Goal event). |

#### Defensive event outcomes
| Event | outcome=1 | outcome=0 |
|-------|-----------|-----------|
| `Tackle` | Successful | Unsuccessful |
| `Interception` | Always 1 | — |
| `Ball recovery` | Always 1 | — |
| `Take On` | Dribble succeeded | Dribble failed |
| `Aerial` | Won | Lost |
| `Challenge` | Won | Lost |
| `Pass` | Accurate | Inaccurate |

#### Foul / Card / Penalty
- **Foul**: `Penalty` qualifier (`'Si'`) marks penalty fouls. **Stored as two rows** (one per team) — filter to the committing team's row for analysis.
- **Card**: `Yellow Card`, `Second yellow`, `Red Card` qualifiers are `'Si'` on the relevant row.

#### Own goals
`own goal` qualifier is **always `'N/A'`** in practice. Own goals are identified programmatically: a Goal event where the scoring player's team is the opponent. Use `filter_own_goals()` / `exclude_own_goals()` from `utils/data_utils.py`.

#### Error events (type 51)
The `Leading to attempt` and `Leading to goal` columns on Error events contain the **related event ID** (a number string like `'454'`), not a boolean flag. They link the error to the resulting shot/goal event.

### UI / Styling

Color tokens are in `utils/config.py` (`COLORS` dict) and mirrored as CSS variables in `assets/style.css`. Import from `page_utils/visualizations.py` for pitch plot constants (`HOME_COLOR`, `AWAY_COLOR`, `GOLD`). Image paths use the format `'assets/...'` (no leading `/`).
