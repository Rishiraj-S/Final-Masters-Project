# CuléVision — Technical Documentation

**Masters Project in Sports Analytics**
Escuela Universitaria Real Madrid Universidad Europea
Author: Rishiraj Sinharay

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [Repository Structure](#2-repository-structure)
3. [Application Architecture](#3-application-architecture)
4. [Data Pipeline](#4-data-pipeline)
5. [Data Storage](#5-data-storage)
6. [Event Data Schema](#6-event-data-schema)
7. [ML Models](#7-ml-models)
8. [Data Access Layer](#8-data-access-layer)
9. [Dashboard Pages and Tabs](#9-dashboard-pages-and-tabs)
10. [Analytical Utilities](#10-analytical-utilities)
11. [UI and Styling](#11-ui-and-styling)
12. [Authentication](#12-authentication)
13. [CI/CD](#13-cicd)
14. [Setup and Development](#14-setup-and-development)

---

## 1. System Overview

CuléVision is a full-stack football analytics platform built for FC Barcelona. It ingests Opta event data for Barcelona and 30 configured opponents, applies custom machine learning models (xG, xT), and serves an interactive Dash dashboard for tactical analysis.

**Technology stack:**

| Layer | Technology |
|-------|-----------|
| Web framework | Plotly Dash 4 (Flask-backed) |
| UI components | Dash Bootstrap Components (dark Bootstrap theme) |
| Charting | Plotly, mplsoccer (server-side Matplotlib → base64 PNG) |
| Data | pandas, pyarrow, Parquet (snappy compression) |
| ML | XGBoost, scikit-learn, numpy |
| Pipeline | Selenium, Selenium Wire, BeautifulSoup |
| Config | YAML |
| Tests | pytest |

---

## 2. Repository Structure

```
CuléVision/
├── app.py                          # Single entry point
├── requirements.txt
├── CLAUDE.md                       # AI coding assistant guidance
├── STYLING.md                      # Design system reference
│
├── pages/                          # One module per URL route
│   ├── home.py
│   ├── match_report.py             # /match-report
│   ├── barca_dna.py                # /barca-dna
│   ├── barca_iq.py                 # /barca-iq
│   ├── opposition_analysis.py      # /opposition-analysis
│   ├── match_analysis_tabs/        # 7 sub-tabs
│   ├── team_analysis_tabs/         # 6 sub-tabs
│   └── opposition_analysis_tabs/   # 6 sub-tabs
│
├── utils/                          # Backend utilities
│   ├── config.py
│   ├── data_utils.py               # Barcelona data access
│   ├── opposition_data_utils.py    # Opposition data access
│   ├── event_utils.py              # Event extraction helpers
│   ├── match_data_adapter.py       # Phase-tagged analysis
│   ├── xg_utils.py
│   ├── xt_utils.py
│   ├── logos.py
│   ├── pdf_report.py
│   └── player_analysis/
│       ├── metrics.py
│       └── wyscout_weights.py
│
├── page_utils/                     # Shared analytical helpers
│   ├── competitions.py
│   ├── event_filters.py
│   ├── visualizations.py
│   ├── pitch_zones.py
│   ├── possession_utils.py
│   └── time_utils.py
│
├── opta_pipeline/                  # Unified data ingestion
│   ├── main.py
│   ├── config.yaml
│   ├── modules/
│   │   ├── scraper.py
│   │   ├── downloader.py
│   │   ├── utils.py
│   │   └── transformers/
│   │       ├── base_transformer.py
│   │       ├── match_transformer.py
│   │       ├── matchevent_transformer.py
│   │       └── lineup_transformer.py
│   └── logs/
│       ├── progress.json
│       ├── pipeline.log
│       ├── download_manifest.json
│       └── scrape_cache/
│
├── xT_model/
│   ├── train.py
│   ├── predictor.py
│   └── xt_grid.npy
│
├── xg_model/
│   ├── predictor.py
│   └── *.json / *.pkl / *.txt
│
├── mappings/
│   ├── opta_event_types.csv
│   └── opta_qualifier_types.csv
│
├── data/                           # NOT in repo — distributed separately
│   └── 2025-26/
│       └── {Country}/{Competition}/{subdir}/*.parquet
│
├── tests/
│   └── test_phase_classifier.py
│
└── assets/
    ├── style.css
    ├── fonts/
    ├── logos/
    └── players/
```

---

## 3. Application Architecture

### Entry Point — `app.py`

`app.py` is the only file executed directly. It:

1. Instantiates the Dash app with a custom `index_string` injecting the Barcelona typeface and dark theme
2. Imports and registers all page module callbacks via `register_*_callbacks(app)`
3. Defines master routing callback `update_main_container` that inspects `dcc.Location.pathname` and calls the appropriate `create_*_layout()` function
4. Registers the Flask route `/download-report/<match_id>` for PDF export
5. Manages the database update flow (see Section 3.3)

### Callback Architecture

Dash uses a reactive callback model. Callbacks are pure functions decorated with `@app.callback`, taking component property inputs and returning outputs. Side-effects (file I/O, subprocess spawning) are confined to:
- `app.py` (pipeline subprocess + progress polling)
- `utils/` modules (data loading with in-process caching)

Each page module calls `register_*_callbacks(app)` once at startup. Callbacks within sub-tabs call `register_*_callbacks(app)` transitively from the page module. No callbacks are defined at module-level — all are inside the registration function to avoid import-time side effects.

### Database Update Flow

```
Admin user
  │
  ▼ clicks "Update Databases"
home.py modal opens
  │
  ▼ selects optional team / competition filters, clicks "Run Pipeline"
app.py handle_database_update callback
  │
  ▼ spawns subprocess: python opta_pipeline/main.py [--team X] [--competition Y]
  │
  ▼ dcc.Interval fires every 2s
app.py poll_pipeline_progress callback
  │  reads opta_pipeline/logs/progress.json
  │
  ▼ full-screen overlay shows current team / competition / stage / match counts
  │
  ▼ pipeline exits (progress.json deleted)
app.py detects completion
  │
  ▼ calls clear_events_cache() + clear_opp_events_cache()
  │
  ▼ dcc.Location refresh=True → full page reload
```

### PDF Export — Flask Route

`app.py` registers `/download-report/<match_id>` as a Flask route (bypassing Dash callbacks). The handler calls `utils/pdf_report.py:generate_match_report_pdf(match_id)` and returns the PDF as a `Flask.send_file` response. This is accessible from a download button in the Match Report page.

---

## 4. Data Pipeline

### Overview

`opta_pipeline/main.py` is the single entry point for all data collection. It handles FC Barcelona and all 30 configured opponents in one run via a two-phase design that minimises redundant Scoresway scraping.

### Phase 1 — Scrape (per competition, once)

For each competition in `config.yaml`:

1. Check `logs/scrape_cache/{competition}_matches.csv` age vs `cache_ttl_days` (default 1 day)
2. If fresh: load cached CSV and skip scraping
3. If stale or `--force-rescrape`: launch `MatchScraper`:
   - Headless Chrome via Selenium
   - Navigate to `results_url` from config
   - Auto-dismiss cookie consent banner
   - Paginate by clicking "Previous" buttons up to `max_pagination_clicks` times
   - Parse each result row with BeautifulSoup: extract `match_id`, `date`, `home`, `away`, `url_match`
   - Merge with existing CSV (new rows win on duplicate `match_id`)
   - Save CSV to `logs/scrape_cache/`

### Phase 2 — Filter & Process (per team × competition)

For each `(team, competition)` pair configured in `config.yaml`:

1. Load the competition's cached match CSV
2. Filter rows by team name using accent-insensitive matching (`_normalize()` strips diacritics)
3. Cross-reference `logs/download_manifest.json` to skip already-downloaded match IDs
4. Launch `MatchDownloader` for missing matches:
   - Headless Chrome instrumented with Selenium Wire
   - Navigate to match centre URL
   - Intercept XHR to `api.performfeeds.com/soccerdata/matchevent/`
   - Validate JSON before saving (retry up to 3× with backoff)
   - Atomic save: write to `.tmp`, then rename
   - Save to `data/target/{competition}/matchdata/{match_id}.json`
5. Run all three transformers on the downloaded JSONs:
   - `MatchTransformer` → `{comp}/match/*.parquet`
   - `MatchEventTransformer` → `{comp}/match_event/*.parquet`
   - `LineupTransformer` → `{comp}/lineup/*.parquet`
6. Update `logs/download_manifest.json`
7. Write `logs/progress.json` (polled by app.py every 2 s)

### Transformer Details

#### `MatchEventTransformer`

The primary transformer producing ~250-column Parquet files:

1. Reads `matchdata/{match_id}.json` (or JSONP-wrapped variant)
2. Extracts match metadata columns: `match_id`, `match_date`, `home_team_name`, `away_team_name`, `home_team_code`, `away_team_code`
3. For each event in `matchInfo.event[]`:
   - Core fields: `event_id`, `event_type`, `event_type_id`, `period_id`, `time_min`, `time_sec`, `x`, `y`, `outcome`, `player_id`, `player_name`, `team_name`, `team_code`
   - Qualifier pivot: for each `{typeId, value}` in `event.qualifier[]`, look up name from `mappings/opta_qualifier_types.csv`, write to column `qualifier_name = value`
   - Boolean qualifiers use `'Si'` (present) / `'N/A'` (absent)
   - Numeric qualifiers (coordinates, angles) stored as float strings
4. Column set is union of all qualifiers encountered across all events in the file — sparse columns filled with `'N/A'`
5. `convert_dtypes=true` in config triggers pandas dtype optimisation on save
6. Deduplication: rows with identical `(event_id, period_id, time_min, team_code)` are dropped

#### `LineupTransformer`

Reads formation data from already-downloaded JSONs — no browser needed:
- Locates `typeId=34` ("Team setp up") event in `matchdata/*.json`
- Parses qualifier blocks to extract `formation_slot` (1–11), `player_name`, `jersey_number`, `position`, `is_captain`
- Detects substitutions from Player On/Off events; attaches `sub_on_minute`
- Schema: one row per player per team per match

### Competition → Country Mapping

Used to construct output paths (`data/2025-26/{Country}/`):

| Competition prefix | Country folder |
|--------------------|---------------|
| `Spain_*` | `Spain` |
| `England_*` | `England` |
| `Germany_*` | `Germany` |
| `France_*` | `France` |
| `Belgium_*` | `Belgium` |
| `Greece_*` | `Greece` |
| `Denmark_*` | `Denmark` |
| `Czech_*` | `Czech_Republic` |
| `UEFA_*` | `Europe` |

### CLI Reference

```
python opta_pipeline/main.py [OPTIONS]

Options:
  --team TEXT            Run for a single team name (from config.yaml)
  --competition TEXT     Run for a single competition key
  --transform-only       Skip scraping and downloading; re-transform existing JSONs
  --skip-download        Scrape and transform only; skip browser download step
  --force-rescrape       Ignore cached CSVs; re-scrape all competition pages
  --config PATH          Path to config.yaml (default: opta_pipeline/config.yaml)
```

---

## 5. Data Storage

### Directory Structure

```
data/2025-26/
├── Spain/
│   ├── Spain_Primera_Division/
│   │   ├── match/            2025-09-24_BAR_vs_RMA_a1b2c3.parquet
│   │   ├── match_event/      2025-09-24_BAR_vs_RMA_a1b2c3.parquet
│   │   └── lineup/           2025-09-24_BAR_vs_RMA_a1b2c3.parquet
│   ├── Spain_Copa_del_Rey/
│   └── Spain_Super_Cup/
├── Europe/
│   └── UEFA_Champions_League/
├── England/
│   ├── England_Premier_League/
│   ├── England_FA_Cup/
│   └── England_EFL_Cup/
├── Germany/
│   ├── Germany_Bundesliga/
│   └── Germany_DFB_Pokal/
├── Belgium/
│   ├── Belgium_First_Division_A/
│   └── Belgium_Cup/
├── France/
│   ├── France_Ligue_1/
│   └── France_Coupe_de_France/
├── Greece/
│   ├── Greece_Super_League/
│   └── Greece_Cup/
├── Denmark/
│   ├── Denmark_Superliga/
│   └── Denmark_DBU_Pokalen/
└── Czech_Republic/
    ├── Czech_First_League/
    └── Czech_Cup/
```

### Filename Convention

`{date}_{HOME_CODE}_vs_{AWAY_CODE}_{match_id}.parquet`

Example: `2025-10-19_BAR_vs_BVB_8abc1234.parquet`

**Team identification at read time**: The data layer scans filenames for `_{TEAM_CODE}_vs_` (home) or `_vs_{TEAM_CODE}_` (away) to filter matches for a given team. No directory hierarchy encodes team identity — one file serves both teams.

### Shared Match Files

A match between Chelsea and Villarreal in the UCL is stored once at:
```
data/2025-26/Europe/UEFA_Champions_League/match_event/2026-02-18_CHE_vs_VIL_xyz.parquet
```

Both `data_utils.py` (when loading Chelsea data) and `opposition_data_utils.py` (when loading Villarreal data) read the same file — they just filter events to the relevant `team_code` after loading.

### Parquet Configuration

- **Compression**: Snappy
- **Engine**: PyArrow
- **Dtype optimisation**: `convert_dtypes=true` (pandas 2.x nullable dtypes)
- **Deduplication**: enabled — duplicate events dropped on transform

### In-Process Cache

`utils/data_utils.py` maintains `_events_cache: dict[str, DataFrame]` keyed by season. `utils/opposition_data_utils.py` maintains `_opp_events_cache: dict[tuple, DataFrame]` keyed by `(team, comp_key, season)`. Both caches are cleared after pipeline runs via `clear_events_cache()` / `clear_opp_events_cache()`.

---

## 6. Event Data Schema

### Coordinate System

- **x**: 0–100, where 0 = own goal line and 100 = opponent goal line
- **y**: 0–100, where 0 = left touchline and 100 = right touchline
- Convention is **per-team**: both home and away teams attack left → right in all stored coordinates. Do **not** flip away-team coordinates.

Zone reference (same for both teams):

| Zone | Condition |
|------|-----------|
| Defensive Third | `x < 33.33` |
| Middle Third | `33.33 ≤ x ≤ 66.67` |
| Final Third | `x > 66.67` |
| Zone 14 | `x > 66.67` and `37 < y < 63` |
| Left Half-Space | `x > 33.33` and `21 < y < 37` |
| Right Half-Space | `x > 33.33` and `63 < y < 79` |
| Penalty Box | `x > 83` and `21.1 < y < 78.9` |

### Core Columns (always present)

| Column | Type | Notes |
|--------|------|-------|
| `event_id` | str | Unique per event within match |
| `event_type` | str | Human-readable event name |
| `event_type_id` | int | Opta numeric ID |
| `period_id` | int | 1 = first half, 2 = second half, 5 = penalties |
| `time_min` | int | Minute of event |
| `time_sec` | int | Second within minute |
| `x` | float | Pitch x-coordinate (0–100) |
| `y` | float | Pitch y-coordinate (0–100) |
| `outcome` | int | 1 = success, 0 = failure |
| `player_id` | str | Opta player ID |
| `player_name` | str | Full player name |
| `team_name` | str | Full team name |
| `team_code` | str | Opta 3-letter code |
| `position` | str | Opta position (`GK`, `CB`, `LB`, ...) or `'N/A'` |
| `match_id` | str | Match identifier |
| `match_date` | str | ISO date string |
| `home_team_name` | str | Home team display name |
| `away_team_name` | str | Away team display name |
| `Jersey Number` | str | Player jersey number as string |

### Pass Columns

| Column | Type | Notes |
|--------|------|-------|
| `Pass End X` | float | Destination x |
| `Pass End Y` | float | Destination y |
| `Length` | float | Pass distance |
| `Angle` | float | Pass angle (degrees) |
| `Assist` | str | `'13'–'16'` = shot type of resulting attempt, `'N/A'` otherwise |
| `2nd assist` | str | `'Si'` if this was the pre-assist pass |
| `Long ball` | str | `'Si'` / `'N/A'` |
| `Cross` | str | `'Si'` / `'N/A'` |
| `Through ball` | str | `'Si'` / `'N/A'` |
| `Head pass` | str | `'Si'` / `'N/A'` |
| `Switch of play` | str | `'Si'` / `'N/A'` |
| `Free kick taken` | str | `'Si'` / `'N/A'` |
| `Corner taken` | str | `'Si'` / `'N/A'` |

### Shot Columns

| Column | Notes |
|--------|-------|
| `Big Chance` | `'Si'` / `'N/A'` |
| `Assisted` | `'Si'` / `'N/A'` — on the Shot event, not the pass |
| `Direct free` | `'Si'` / `'N/A'` |
| `Head` | `'Si'` / `'N/A'` |
| `Goal Mouth Y Coordinate` | Float string; goal-mouth position |
| `Goal Mouth Z Coordinate` | Float string |
| `Box-centre`, `Box-left`, ... | Zone label `'Si'` / `'N/A'` |

### Event Type Reference

```
Pass (1)          Offside Pass (2)    Take On (3)       Foul (4)
Out (5)           Corner Awarded (6)  Tackle (7)        Interception (8)
Save (10)         Clearance (12)      Miss (13)         Post (14)
Saved Shot (15)   Goal (16)           Card (17)         Player Off (18)
Player On (19)    Start (32)          Team setp up (34) [intentional typo]
Formation change (40)  Punch (41)    Good skill (42)   Deleted event (43)
Aerial (44)       Challenge (45)      Ball recovery (49) Dispossessed (50)
Error (51)        Keeper pick-up (52) Offside provoked (55)
Shield ball opp (56) Keeper Sweeper (59) Chance missed (60)
Ball touch (61)   Blocked Pass (74)   End (30)
Start delay (27)  End delay (28)
```

### Own Goals

The `own goal` qualifier is **always `'N/A'`** in the raw Opta feed. Own goals are identified programmatically: a `Goal` event where the `team_code` of the scoring player matches the **opponent** (i.e., the player who accidentally scored is on the defending side). Use `filter_own_goals(df)` from `utils/data_utils.py`.

### Foul / Penalty Encoding

Foul events are stored as **two rows** — one per team involved. The row for the committing team has `Penalty = 'Si'` when a penalty was awarded. Filter to the committing team's row for per-team foul analysis.

---

## 7. ML Models

### 7.1 xG Model (`xg_model/`)

Three specialised XGBoost classifiers for expected goals:

| Class | Situations |
|-------|-----------|
| `XGPredictor` | Open-play shots |
| `XGDFKPredictor` | Direct free kick shots |
| `XGPenaltyPredictor` | Penalty kicks |

`XGRouter` auto-routes each shot event to the correct model by inspecting shot qualifiers (`Direct free`, `Penalty`).

**Training data**: Wyscout historical shot data (not included in repository).

**Feature engineering**:
- Distance and angle to goal
- Shot zone (penalty box, outside box, header, etc.)
- Situational context (fast break, from corner, set piece)
- SHAP-based feature selection (stored in `*_selected_features.txt`)
- Monotone constraints applied to distance and angle features (ensures xG decreases with distance, as enforced by `*_monotone_constraints.json`)

**Artifacts per model**:
- `xg_*_model_final.json` — XGBoost model weights
- `xg_*_scaler.pkl` — MinMaxScaler for feature normalisation
- `xg_*_zone_bounds.pkl` — shot zone boundary definitions
- `xg_*_selected_features.txt` — feature names after SHAP selection

**Public bridge**: `utils/xg_utils.py:add_xg_column(shots_df)` accepts any Opta shot DataFrame and returns a copy with an `xG` column (float 0–1). Calls `XGRouter` internally. Model is a lazy singleton — loaded once on first call.

### 7.2 xT Model (`xT_model/`)

Grid-based Expected Threat model following the Soccermatics/Bellman-equation approach.

**Architecture**:

- Pitch divided into a 16 × 12 grid (16 columns along x-axis, 12 rows along y-axis)
- Each cell `(i, j)` stores the expected threat value `xT[i,j]`
- Solved iteratively via the Bellman equation:

```
xT[i,j] = P(shoot | i,j) × P(goal | shoot, i,j)
         + P(move  | i,j) × Σ_{k,l} T[i,j → k,l] × xT[k,l]
```

Where:
- `P(shoot | i,j)` = probability a team shoots from cell `(i,j)`, computed from event frequency
- `P(goal | shoot, i,j)` = empirical shot conversion rate from cell `(i,j)`
- `P(move | i,j)` = `1 - P(shoot | i,j)`
- `T[i,j → k,l]` = transition probability from cell `(i,j)` to `(k,l)` via a pass, from pass frequency counts

**Training**: `python xT_model/train.py` reads all `match_event` parquets from `data/2025-26/**/match_event/` (Barcelona + all opponents). Iterates Bellman equation to convergence. Saves `xT_model/xt_grid.npy` (shape `(16, 12)`).

**Inference**: `xT_model/predictor.py:predict_xt(x1, y1, x2, y2)` returns non-negative xT gained from a pass between coordinates `(x1,y1)` → `(x2,y2)`. Negative values (passes that move into lower-xT zones) return 0.

**Public bridge**: `utils/xt_utils.py:add_xt_column(passes_df)` accepts any Opta pass DataFrame with `x`, `y`, `Pass End X`, `Pass End Y` columns and returns a copy with `xT` added. Rows with missing coordinates get `xT = 0`.

**Limitation**: Ball carries are not Opta events. xT accrues only to the passer. Per-player xT rankings under-credit progressive dribblers/wingers relative to pure passers.

---

## 8. Data Access Layer

### 8.1 Barcelona Data — `utils/data_utils.py`

All Barcelona-specific analysis reads through this module.

**Path constants**:
```python
DATA_ROOT = SCRIPT_DIR / "data" / "2025-26"
_BARCA_COMPS = {
    'laliga':   ('Spain', 'Spain_Primera_Division'),
    'ucl':      ('Europe', 'UEFA_Champions_League'),
    'copa':     ('Spain', 'Spain_Copa_del_Rey'),
    'supercup': ('Spain', 'Spain_Super_Cup'),
}
```

**Key functions**:

| Function | Returns |
|----------|---------|
| `get_all_events(season)` | All `match_event` rows for Barcelona across all competitions (cached) |
| `get_match_events(match_id)` | Event rows for one match |
| `get_all_matches(season)` | All match metadata |
| `get_match_lineup(match_id)` | Lineup parquet for one match |
| `get_match_results()` | Match results with scores computed from goal events |
| `get_player_events(player_name, season)` | All events for a specific player |
| `get_team_season_stats(season, competition)` | Aggregate Barcelona KPIs |
| `get_season_summary()` | W/D/L, GF, GA, points, win rate |
| `get_form_timeline()` | Cumulative points trendline data |
| `get_available_seasons(competition)` | Seasons present on disk |
| `clear_events_cache()` | Clears in-process event cache |

File filtering: uses `_BAR_vs_` or `_vs_BAR_` in filename to identify Barcelona matches.

**Own goal helpers**: `is_own_goal(row)` — true when a Goal event's `team_code` belongs to the opponent. `filter_own_goals(df)` — removes opponent-team goal events from a Barcelona goals DataFrame.

### 8.2 Opposition Data — `utils/opposition_data_utils.py`

All opposition analysis reads through this module.

**Important**: renames `event_type_id` → `type_id` on load. All opposition tab modules must use `type_id`, not `event_type_id`.

**Path construction**: `DATA_ROOT / {country} / {comp_key} / {subdir}` — country derived from competition key prefix.

**Key functions**:

| Function | Returns |
|----------|---------|
| `list_available_opponents()` | All non-Barcelona teams from `opta_pipeline/config.yaml` |
| `get_team_code(team_name)` | Primary Opta 3-letter code |
| `get_team_codes(team_name)` | All codes (including `team_code_alt`) |
| `get_team_competitions(team_name)` | Competition keys configured for this team |
| `get_opp_all_events(team, country, comp_key)` | All match events for one team × competition (both teams, cached) |
| `get_opp_team_events(team, country, comp_key)` | Only the opposition team's own events |
| `get_opp_team_matches(team, country, comp_key)` | Match result dicts (date, gf, ga, result, opponent) |
| `load_opp_events(team, comp_key, venue, match_ids)` | Returns `(opp_ev, bar_ev)` split tuple |
| `get_opp_possession(team, country, comp_key)` | Approximate possession % from pass share |
| `clear_opp_events_cache()` | Clears opposition event cache |

**Team filtering via `team_code`**: All event-filtering functions (`get_opp_team_events`, `load_opp_events`, `get_opp_possession`, `get_opp_team_matches`) use the `team_code` column in the DataFrame — not `team_name` substring matching. This is necessary because Opta's stored `team_name` value (e.g. `'Olympiakos FC'`) often differs from the config display name (e.g. `'Olympiakos Piraeus'`). Always call `get_team_codes(team_name)` to retrieve the code(s) and filter by `df['team_code'].isin(codes)`.

**PSG dual-code**: `get_team_codes("Paris Saint-Germain")` returns `['PSG', 'PAR']`. `_team_parquets()` accepts a list and checks both codes in filenames. All filtering functions handle multi-code teams transparently.

### 8.3 Event Utils — `utils/event_utils.py`

Canonical event-extraction helpers. **Always import from here — never filter events inline.** Functions encode correct qualifier conventions and handle edge cases (e.g. `outcome` column dtype, `'Si'`/`'N/A'` qualifiers, `'Ball recovery'` lowercase-r).

Import pattern:
```python
from utils.event_utils import get_passes, get_shots, get_goals, get_tackles, ...
```

Returns filtered pandas DataFrames. Rate helpers return `float 0–100`. Count helpers return `int`.

Key composite: `compute_event_stats(events_df)` → full stats dict for a player or team subset.

---

## 9. Dashboard Pages and Tabs

### Home (`pages/home.py`)

- Season KPI cards: matches, wins, draws, losses, GF, GA, GD, win rate, points
- Per-competition summary table with W/D/L, goals, possession, pass accuracy, top scorer
- Scrollable match results table with W/D/L badges
- Cumulative points trendline chart
- Admin: "Update Databases" button → modal with team/competition dropdowns → pipeline run

### Match Report (`pages/match_report.py`, URL `/match-report`)

Competition and match selectors at top. Score headline via dedicated callback in `match_report.py`. Seven sub-tabs:

| Tab | File | Key content |
|-----|------|-------------|
| Overview | `overview.py` | mplsoccer pitch with both XIs (formation-positioned), sub panels, H1/H2 TV stat bars |
| Attacking Output | `attacking_output.py` | Shot map with xG, shot table, KPIs |
| Build-Up & Passing | `build_up_passing.py` | Pass maps, PPDA, progressive passes, chance creation |
| Defensive Structure | `defensive_structure.py` | Defensive action map (tackles, interceptions, clearances, fouls, offsides) |
| Transitions | `transitions_counterpressing.py` | Two sub-tabs: Defensive + Attacking transitions; 30 s windows; both teams side-by-side |
| Goalkeeping | `goalkeeping.py` | Save map on goal-frame view, xG faced vs goals conceded, distribution stats |
| Player Stats | `player_stats.py` | Per-player match stats table including `xT` column |

### Barça DNA (`pages/barca_dna.py`, URL `/barca-dna`)

Player, competition, and match filters with Total/Per 90 toggle. Nine panels:
- Profile card (photo, bio, headline stats)
- Attribute radar (ATT/TEC/TAC/DEF/CRE) vs squad peers
- Positional xT Heatmap (16×12 grid, gold colormap)
- Shooting panel (shot map, outcome donut)
- Passing panel (stats table, accurate/inaccurate donut)
- Possession panel (dribbles, duels, touches, touch-zone donut)
- Defending panel (tackles, interceptions, recoveries, clearances)
- Discipline panel (yellow/red cards)

### Barça IQ (`pages/barca_iq.py`, URL `/barca-iq`)

Season and competition filters. Six sub-tabs:

| Tab | Key content |
|-----|-------------|
| Overview | Season KPIs, goals for/against, xG |
| Build-Up | Build-up pass maps, PPDA, progressive passes |
| Chance Creation | Shot maps, xG, big chances |
| Defensive Structure | Defensive action heatmaps, PPDA allowed |
| Transitions | Transition event maps, 30 s windows |
| Set Pieces | Corner/free kick maps, outcomes |

### Opposition Analysis (`pages/opposition_analysis.py`, URL `/opposition-analysis`)

Team selector, competition selector, venue filter. Six sub-tabs:

| Tab | File | Key content |
|-----|------|-------------|
| Overview | `overview.py` | W/D/L, goals, key KPIs |
| Build-Up | `buildup.py` | In-possession pass patterns |
| Chance Creation | `chance_creation.py` | Shot maps, xG, big chances |
| Transitions | `transitions.py` | Counter-attacks, pressing |
| Defence | `defence.py` | Defensive shape, duels, block zones |
| Set Pieces | `set_pieces.py` | Corners, free kicks, throw-ins |

`helpers.py` provides `no_data(msg)` — a uniform empty-state placeholder used by all six tab builders when data queries return empty.

---

## 10. Analytical Utilities

### `page_utils/pitch_zones.py`

```python
from page_utils.pitch_zones import PitchZone, ZoneBoundaries, get_zone, is_in_penalty_box
```

- `PitchZone` enum: `DEFENSIVE_THIRD`, `MIDDLE_THIRD`, `FINAL_THIRD`, `ZONE_14`, `LEFT_HALF_SPACE`, `RIGHT_HALF_SPACE`, `PENALTY_BOX`
- `get_zone(x, y)` → `PitchZone`
- `is_in_penalty_box(x, y)` → `bool`

### `page_utils/possession_utils.py`

```python
from page_utils.possession_utils import annotate_possession, compute_vertical_speed, is_stable_possession
```

- `annotate_possession(events_df)` → DataFrame with `possession_id`, `possession_team`, `abs_time_sec` columns
- `compute_vertical_speed(events_df)` → float (average vertical progression rate in a possession sequence)
- `is_stable_possession(events_df)` → bool (whether sequence meets minimum pass/touch threshold)

### `page_utils/time_utils.py`

```python
from page_utils.time_utils import to_seconds, format_seconds, events_within_window
```

- `to_seconds(period_id, time_min, time_sec)` → float absolute match time in seconds
- `format_seconds(secs)` → `"MM:SS"` string
- `events_within_window(events_df, start_sec, end_sec)` → filtered DataFrame

### `page_utils/competitions.py`

```python
from page_utils.competitions import ALL_COMPETITIONS, COMP_SHORT, normalize_competitions, build_match_selector_options
```

- `ALL_COMPETITIONS` — list of all competition display names
- `COMP_SHORT` — `{'La Liga': 'LL', 'Champions League': 'UCL', ...}`
- `normalize_competitions(comps)` → deduplicated, sorted list
- `build_match_selector_options(matches_df)` → Dash dropdown options list

### `page_utils/event_filters.py`

```python
from page_utils.event_filters import SHOT_TYPES, DEF_ACTION_TYPES, DEF_COLORS, SHOT_OUTCOME_COLOR, SHOT_OUTCOME_SYMBOL, filter_by_period, split_by_halves
```

- `SHOT_TYPES` — set of shot event type strings
- `DEF_ACTION_TYPES` — set of defensive event type strings
- `filter_by_period(events_df, period)` → filtered DataFrame (`period=1` or `2`)
- `split_by_halves(events_df)` → `(h1_df, h2_df)` tuple

### `page_utils/visualizations.py`

Central pitch visualisation module. All pitch plots rendered server-side via mplsoccer to base64 PNG.

```python
from page_utils.visualizations import (
    HOME_COLOR, AWAY_COLOR, GOLD,
    CHART_CONFIG, CHART_LAYOUT_DEFAULTS,
    render_lsc_heatmap_img,     # KDE positional heatmap
    render_xt_heatmap_img,      # 16×12 xT grid heatmap (gold colormap)
)
```

**Pitch creation pattern**:
```python
from mplsoccer import Pitch
pitch = Pitch(pitch_color='#151932', line_color='#2A2F4A')
fig, ax = pitch.draw(figsize=(10, 6.5))
pitch.scatter(x, y, ax=ax, ...)   # use scatter(), not mpatches.Circle
```

Use `pitch.scatter()` for all point markers — `mpatches.Circle` patches distort under non-square axis aspect ratios.

### `utils/match_data_adapter.py`

Schema-agnostic layer for phase-based match analysis. Accepts raw event DataFrames and decomposes them into tactical phases:

```python
from utils.match_data_adapter import (
    get_match_metadata,
    compute_team_kpis,
    get_starting_lineups,
    get_substitutions,
)
```

Uses Opta qualifier flags (`Fast break`, `Set piece`, `From corner`) where available; falls back to event sequence inference when columns are absent. Returns empty results rather than raising on missing qualifier columns.

---

## 11. UI and Styling

### Color Tokens

Defined in `utils/config.py → COLORS` and mirrored as CSS variables in `assets/style.css`:

| Token | Hex | Usage |
|-------|-----|-------|
| `primary` | `#004D98` | Navbar, primary action buttons |
| `garnet` | `#A50044` | Accent highlights, active states |
| `gold` | `#EDBB00` | KPI values, badges, active nav links |
| `dark_bg` | `#0A0E27` | Main page background |
| `dark_secondary` | `#151932` | Cards and panels |
| `dark_tertiary` | `#1E2139` | Inputs, table rows |
| `dark_border` | `#2A2F4A` | Card and panel borders |
| `text_primary` | `#E8E9ED` | Main body text |
| `text_secondary` | `#A5A8B8` | Labels, subtitles |

Always import pitch constants from `page_utils/visualizations.py`:
```python
from page_utils.visualizations import HOME_COLOR, AWAY_COLOR, GOLD
```

Never hardcode hex values in page or tab modules.

### Asset Conventions

- Logo paths use Dash-relative format: `'assets/logos/team/barcelona.svg'` (no leading `/`)
- Player images: `'assets/players/{jersey_number}-{player_name}.webp'`
- Font: `assets/fonts/Barcelona FC 23-24 Tipografstore.otf` — used for brand headings via CSS `@font-face`

---

## 12. Authentication

Session-based auth implemented entirely in `app.py` using `dcc.Store(id='session-store', storage_type='session')`.

Two roles:

| Role | Username | Password | Capabilities |
|------|----------|----------|-------------|
| Guest | `Guest` | `guest` | Read-only dashboard access |
| Admin | `Rishi` | `admin` | Full access + "Update Databases" pipeline trigger |

**Login flow**: Credentials compared against hardcoded dict in `app.py`. On success, `session-store` is populated with `{'logged_in': True, 'role': 'admin'}`. On logout, store cleared. URL routing callback checks `session-store` before rendering any page — unauthenticated requests are redirected to the login layout.

No passwords are hashed. This is an academic project not intended for public deployment.

---

## 13. CI/CD

### GitHub Actions — `.github/workflows/ci.yml`

Runs on every pull request and push to `main`.

```yaml
name: CI
on:
  pull_request:
  push:
    branches: [main]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
          cache: pip
          cache-dependency-path: requirements.txt
      - run: pip install -r requirements.txt && pip install pytest
      - run: pytest tests/ -v
```

**Scope**: Unit tests in `tests/test_phase_classifier.py` covering the `page_utils` layer (pitch zones, possession utilities, time utilities). Tests are pure unit tests — no Selenium, no Parquet I/O, no pipeline invocation.

### Running Locally

```bash
pytest tests/ -v
pytest tests/test_phase_classifier.py::TestPitchZones -v
pytest tests/test_phase_classifier.py::TestPossessionUtils::test_annotate_adds_abs_time_sec -v
```

---

## 14. Setup and Development

### Prerequisites

- Python 3.11+
- Google Chrome (for data pipeline — Selenium)
- pip

### Installation

```bash
git clone <repo-url>
cd Final-Masters-Project
pip install -r requirements.txt
```

### Running the App

```bash
python app.py
# Open http://localhost:8050
# Login: Guest / guest  (read-only)
#        Rishi / admin  (full access + pipeline)
```

### Running the Data Pipeline

```bash
# Full pipeline — all teams, all competitions (~hours for first run)
python opta_pipeline/main.py

# Single team, useful for incremental updates
python opta_pipeline/main.py --team "Barcelona"

# Re-transform without re-downloading (fast, no browser needed)
python opta_pipeline/main.py --transform-only
```

### Retraining the xT Model

```bash
python xT_model/train.py
# Reads data/2025-26/**/match_event/*.parquet
# Writes xT_model/xt_grid.npy
```

### Adding a New Team

1. Add an entry to `teams:` in `opta_pipeline/config.yaml`:
   ```yaml
   - team_name: "Inter Milan"
     team_code: "INT"
     search_name: "Inter"
     country: "Italy"
     competitions:
       - Italy_Serie_A
       - UEFA_Champions_League
   ```
2. Add the competition URL to `competitions:` if not already present
3. Run the pipeline with `--team "Inter Milan"`

### Adding a New Competition

1. Add the competition to `competitions:` in `opta_pipeline/config.yaml` with its Scoresway `results_url`
2. Add `Italy_Serie_A` prefix to `_COMPETITION_COUNTRY` in `opta_pipeline/modules/utils.py` and `_COMP_COUNTRY` in `utils/opposition_data_utils.py`
3. Run `python opta_pipeline/main.py --competition Italy_Serie_A`

### Known Gotchas

- **`'Ball recovery'` lowercase-r**: `events["event_type"] == "Ball recovery"` — the `r` is lowercase. This is how Opta stores it.
- **`"Team setp up"` typo**: Intentional. Exists in both `mappings/opta_event_types.csv` and `matchevent_transformer.py:156`. Fix both or neither.
- **PSG dual code**: PSG uses `PSG` in UEFA feeds and `PAR` in Ligue 1. Always use `get_team_codes()` (returns both) rather than `get_team_code()` when filtering PSG matches.
- **`event_type_id` vs `type_id`**: Barcelona parquets use `event_type_id`. Opposition module renames it to `type_id` on load. Never use `event_type_id` in opposition tab modules.
- **Coordinate flipping**: Do **not** apply `100 - x` to away team coordinates. Opta normalises per-team — both teams already attack left → right.
- **Own goals**: The `own goal` qualifier is always `'N/A'`. Identify own goals by team code mismatch on Goal events.
- **`'Si'` / `'N/A'`**: Boolean qualifiers are `'Si'` (true) or `'N/A'` (absent/false) — not Python booleans.
- **`_events_cache` and `_opp_events_cache`**: Both caches must be cleared after pipeline runs — `clear_events_cache()` for Barcelona data and `clear_opp_events_cache()` for opposition data. `app.py` calls both on pipeline completion. Page reloads alone do not clear either cache.
- **Team name vs team code**: Never filter opposition events by `team_name` substring matching (`_normalize()` approach). Always use `get_team_codes(team_name)` and filter by `df['team_code'].isin(codes)`. Opta stored `team_name` values frequently differ from config display names (e.g. `'Olympiakos FC'` vs `'Olympiakos Piraeus'`).
- **`SHOT_TYPES` / `DEF_ACTION_TYPES`**: Import from `page_utils/event_filters.py`. `'Blocked Shot'` does not exist in Opta data — it was removed. `'Ball recovery'` uses lowercase-r in both constants and raw data.
