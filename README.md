# CuléVision - FC Barcelona Game Analysis Tool

**Masters Project in Sports Analytics**
Escuela Universitaria Real Madrid Universidad Europea

---

## Project Overview

CuléVision is a professional football analytics dashboard built specifically for FC Barcelona. The tool processes Opta event data to provide comprehensive match analysis, rival scouting, and tactical insights aligned with Barcelona's positional play philosophy.

---

## Key Features

- **Match Analysis**: Automated post-match breakdown across seven tabs — Overview (with H1/H2 stat splits), Attacking Output, Build-Up & Passing, Defensive Structure (with fouls/offsides overlay), Transitions (Defensive + Attacking sub-tabs, 30 s windows), Goalkeeping, and Player Stats (including xT)
- **Team Analysis**: KPIs defining Barcelona's playing style and game model across all competitions
- **Player Analysis (Barça DNA)**: Season/match-level stats, attribute radar, Positional xT Heatmap (16×12 grid), shooting map, passing, possession, defending, and discipline panels
- **Opposition Analysis**: Scouting dashboard for every team Barcelona faced, covering defence, transitions, set pieces, in-possession patterns, and player profiling
- **xG Model**: Three specialised XGBoost models (open play, direct free kick, penalty) trained on Wyscout data with SHAP feature selection and monotone constraints — an `XGRouter` automatically routes each shot to the correct model. Integrated across all shot visualisations in the app
- **xT Model**: Grid-based Expected Threat model (Bellman equation, 16×12 grid) trained on all Opta event data. `utils/xt_utils.py` → `add_xt_column(passes_df)` is the public bridge. Used in player stats tables and the Positional xT Heatmap
- **Data Pipeline (Barca)**: Fully automated Opta data ingestion for Barcelona (scrape → download → transform → store)
- **Data Pipeline (Opposition)**: Separate pipeline to collect match event data for all teams Barcelona faced, organised by country / team / competition
- **Live Update Overlay**: UI feedback with real-time pipeline progress while databases are being updated

---

## Prerequisites

- Python 3.11 or higher
- Google Chrome (required by Selenium for the data pipeline)
- pip package manager

---

## Installation

1. **Clone or download this repository**

2. **Install all dependencies**:
```bash
pip install -r requirements.txt
```

3. **Run the application**:
```bash
python app.py
```

4. **Access the dashboard**:
   - Open your browser and navigate to: `http://localhost:8050`
   - Log in with `Guest / guest` or `Rishi / admin`

---

## Project Structure

```
CuléVision/
├── app.py                          # Main Dash application entry point
├── requirements.txt                # Python dependencies
├── STYLING.md                      # UI/UX style guide
├── LICENSE
│
├── pages/                          # One module per dashboard page
│   ├── home.py
│   ├── match_report.py             # /match-report
│   ├── barca_dna.py                # /barca-dna  (Player Analysis)
│   ├── barca_iq.py                 # /barca-iq   (Team Analysis)
│   ├── opposition_analysis.py      # /opposition-analysis
│   ├── match_analysis_tabs/        # Sub-tabs for Match Report page
│   │   ├── shared.py
│   │   ├── overview.py
│   │   ├── attacking_output.py
│   │   ├── build_up_passing.py
│   │   ├── defensive_structure.py
│   │   ├── transitions_counterpressing.py
│   │   ├── goalkeeping.py
│   │   └── player_stats.py
│   ├── team_analysis_tabs/         # Sub-tabs for Team Analysis page
│   │   ├── overview.py
│   │   ├── buildup.py
│   │   ├── chance_creation.py
│   │   ├── def_structure.py
│   │   ├── transitions.py
│   │   └── set_pieces.py
│   └── opposition_analysis_tabs/   # Sub-tabs for Opposition Analysis page
│       ├── defence.py
│       ├── exploit.py
│       ├── in_possession.py
│       ├── scouting.py
│       ├── set_pieces.py
│       └── transitions.py
│
├── xT_model/                       # Grid-based Expected Threat model
│   ├── train.py                    # Bellman-equation training script — writes xt_grid.npy
│   ├── predictor.py                # Lazy-singleton inference — predict_xt(), add_xt_column()
│   └── xt_grid.npy                 # Trained artifact — (16, 12) xT grid
│
├── xg_model/                       # Custom XGBoost expected goals model (3 sub-models)
│   ├── predictor.py                # Inference classes — XGPredictor, XGDFKPredictor, XGPenaltyPredictor, XGRouter
│   ├── xg_model_final.json         # Open-play model weights
│   ├── xg_scaler.pkl               # Open-play MinMaxScaler
│   ├── xg_zone_bounds.pkl          # Open-play shot zone bounds
│   ├── xg_selected_features.txt    # SHAP-selected feature list (open play)
│   ├── xg_monotone_constraints.json
│   ├── xg_dfk_model_final.json     # Direct free kick model weights
│   ├── xg_dfk_scaler.pkl
│   ├── xg_dfk_zone_bounds.pkl
│   ├── xg_dfk_selected_features.txt
│   ├── xg_dfk_monotone_constraints.json
│   ├── xg_penalty_model_final.json # Penalty model weights
│   ├── xg_penalty_scaler.pkl
│   ├── xg_penalty_zone_bounds.pkl
│   ├── xg_penalty_selected_features.txt
│   ├── xg_penalty_monotone_constraints.json
│   └── README.md                   # Model documentation
│
├── utils/                          # Shared utility modules
│   ├── config.py
│   ├── data_utils.py
│   ├── opposition_data_utils.py
│   ├── xg_utils.py                 # Opta → xG model bridge (add_xg_column)
│   ├── xt_utils.py                 # Opta → xT model bridge (add_xt_column)
│   ├── pdf_report.py
│   └── player_analysis/
│
├── page_utils/                     # Analytical helper modules shared across tabs
│   ├── pitch_zones.py
│   ├── possession_utils.py
│   └── time_utils.py
│
├── opta_pipeline/                  # Barcelona data ingestion pipeline
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
│       └── pipeline.log
│
├── opposition_pipeline/            # Opposition scouting data pipeline
│   ├── main.py
│   ├── config.yaml
│   └── logs/
│
├── mappings/                       # Opta reference data (shared by both pipelines)
│   ├── opta_event_types.csv
│   └── opta_qualifier_types.csv
│
├── data/                           # All processed Parquet data (not in repo — share separately)
│   ├── barcelona/
│   │   └── result/
│   │       └── {League}/{Season}/
│   │           ├── match/
│   │           ├── match_event/
│   │           └── lineup/
│   └── opposition/
│       └── {Country}/{Team}/{Competition}/{Season}/
│           ├── match/
│           ├── match_event/
│           └── lineup/
│
├── tests/                          # Unit tests for page_utils modules
│
└── assets/                         # Static assets served by Dash
    ├── style.css
    ├── fonts/
    ├── logos/
    │   ├── team/
    │   └── tournament/
    └── players/
```

---

## Root Files

### `app.py`
The main entry point for the entire application.

- **App initialisation**: Bootstraps the Plotly Dash app with Bootstrap theme and a custom dark-theme HTML template injected via `app.index_string`
- **Authentication system**: Session-based login/logout using `dcc.Store`. Two roles — `guest` and `admin`. Admins see the "Update Databases" button on the Home page
- **URL routing**: A single master callback (`update_main_container`) inspects the URL path and renders the correct page layout and navbar
- **Database update flow**:
  - Admin clicks "Update Databases" → spawns `opta_pipeline/main.py` as a background subprocess via `threading.Thread`
  - A `dcc.Interval` polls every 2 seconds; reads `opta_pipeline/logs/progress.json` to display live stage/competition/match progress in a full-screen overlay
  - On completion, clears the in-process data cache (`clear_events_cache`) and forces a full page reload so fresh parquet data is served
- **Navbar**: Sticky top bar with brand gradient, nav links (Home, Match Analysis, Player Analysis, Team Analysis), and a logout button
- **Page callbacks**: Registers all page-level Dash callbacks by calling each page module's `register_*_callbacks(app)` function

### `requirements.txt`
Python dependencies for the entire project (Dash, Plotly, pandas, mplsoccer, dash-bootstrap-components, selenium, selenium-wire, etc.).

### `STYLING.md`
UI/UX style guide documenting the design system: colour tokens, typography, component patterns, and spacing conventions used across the dashboard.

---

## Pages (`pages/`)

Each page module exports two functions: `create_*_layout()` which returns the Dash layout tree, and `register_*_callbacks(app)` which registers all reactive callbacks for that page.

### `pages/home.py`
**Season Overview / Home Page**

- Displays key season KPI cards: matches played, wins, draws, losses, goals for/against, goal difference, win rate, and points
- Shows a per-competition summary table (La Liga, Champions League, Copa del Rey, Spanish Super Cup) with W/D/L, goals, possession, pass accuracy, shot accuracy, and top scorer
- Renders a scrollable results table of all matches with result badges (W/D/L), date, competition, opponent, and score
- Includes a rolling cumulative points trendline chart across the season
- Admin-only: "Update Databases" button triggers the Barcelona data pipeline (see `app.py`)

### `pages/match_report.py`
**Match Report Page** (`/match-report`)

- Two dropdowns at the top: competition selector and match selector (filtered by competition)
- Score headline rendered via a dedicated callback
- On match selection, renders a tabbed layout with seven analysis tabs (see `match_analysis_tabs/` below)
- Passes the selected `match_id` to each tab's layout builder so all tabs read from the same match's event data

### `pages/barca_dna.py`
**Barça DNA — Player Analysis Page** (`/barca-dna`)

- Player, competition, and match filters with Total/Per 90 toggle
- Profile card: player photo, bio, and season headline stats
- Attribute radar chart (ATT/TEC/TAC/DEF/CRE) scored against squad peers
- Positional xT Heatmap — 16×12 grid coloured by cumulative xT from passes, with marginal bar plots
- Shooting panel: shot map, outcome donut, shot stats
- Passing panel: stats table + accurate/inaccurate donut
- Possession panel: dribbles, duels, touches, touch-zone donut
- Defending panel: tackles, interceptions, recoveries, clearances + donut
- Discipline panel: yellow/red card visual

### `pages/barca_iq.py`
**Barça IQ — Team Analysis Page** (`/barca-iq`)

- Season and competition filters
- Aggregate Barcelona team KPIs across six sub-tabs: Overview, Build-Up, Chance Creation, Defensive Structure, Transitions, Set Pieces

---

## Match Report Tabs (`pages/match_analysis_tabs/`)

These sub-modules are loaded on demand when a match is selected in Match Report. All tabs share common constants and pitch-drawing utilities from `shared.py`.

### `shared.py`
Shared constants, colour tokens (`HOME_COLOR`, `AWAY_COLOR`, `GOLD`), and reusable pitch-drawing helpers used by every other tab. Configures Matplotlib to use the `Agg` (non-interactive server-side) backend. Provides functions to render `mplsoccer` pitches as base64-encoded PNG images embedded in Dash `html.Img` elements via Plotly `layout_image`.

### `overview.py`
**Tab 1 — Match Overview**

- Renders a horizontal `mplsoccer` pitch with both starting XIs positioned according to their formation and slot using `pitch.scatter()` for circular markers; home team on the left, away team on the right
- Overlays jersey numbers and player names with path-effect outlines for readability; captain badge displayed next to the captain
- Substitutes panels flank the pitch on either side, showing player name, jersey number, and the minute of substitution
- TV-style horizontal bar comparisons below the pitch for key stats: possession, shots, shots on target, passes, pass accuracy, corners, fouls, yellow/red cards — each bar now shows H1/H2 half-breakdown in brackets

### `attacking_output.py`
**Tab 2 — Attacking Output**

- Shot map on an mplsoccer pitch: goals, saved shots, off-target, and blocked shots plotted by pitch coordinates with xG values
- Shot event table with player, minute, body part, shot zone, xG, and outcome
- KPIs: total shots, shots on target, shot accuracy, goals, xG, big chances created/converted

### `build_up_passing.py`
**Tab 3 — Build-Up & Passing**

- Pass maps showing progressive passing sequences and build-up patterns
- Possession-phase KPIs: pass accuracy by zone, progressive passes, PPDA, ball recoveries, and chance creation metrics

### `defensive_structure.py`
**Tab 4 — Defensive Structure**

- Defensive action maps: tackles, interceptions, clearances, and blocks plotted by pitch zone
- Fouls and offsides overlaid on the same pitch map
- KPIs: defensive actions by zone, defensive duels won, fouls conceded, clean sheet metrics

### `transitions_counterpressing.py`
**Tab 5 — Transitions**

- Two sub-tabs: **Defensive Transition** (30 s windows after possession loss) and **Attacking Transition** (30 s windows after possession gain)
- Both home and away teams shown side-by-side in each sub-tab
- Transition event maps on pitch + per-phase KPIs
- Heatmaps showing where transitions originate

### `goalkeeping.py`
**Tab 6 — Goalkeeping**

- Goalkeeper save map plotted on a goal-frame pitch view, with shot origin overlay
- KPIs: saves, goals conceded, save percentage, xG faced vs goals conceded, distribution stats

### `player_stats.py`
**Tab 7 — Player Stats**

- Per-player match statistics table for both teams
- Stats columns: minutes played, goals, assists, shots, shots on target, passes, pass accuracy, key passes, xT, tackles, interceptions, fouls, cards

---

## Opposition Analysis Tabs (`pages/opposition_analysis_tabs/`)

Sub-modules for the Opposition Analysis page, allowing scouting of any team Barcelona faced using the opposition pipeline data.

| Module | Description |
|---|---|
| `helpers.py` | Shared data loaders and formatting utilities for opposition tabs |
| `scouting.py` | Season summary dashboard: W/D/L, goals, and headline KPIs for the selected opponent |
| `in_possession.py` | Opposition in-possession patterns: pass maps, progressive carries, chance creation |
| `defence.py` | Opposition defensive organisation: block shape, defensive actions, duels |
| `transitions.py` | Opposition transition behaviour: counter-attacks, pressing, ball recoveries |
| `set_pieces.py` | Opposition set piece analysis: corners, free kicks, throw-ins |
| `exploit.py` | Exploitable weaknesses: zones to attack, vulnerable opponents, high-xG areas |

---

## Page Utils (`page_utils/`)

Analytical helper modules shared across multiple tab files. Coordinate convention: `x=0` is the performing team's own goal, `x=100` is the opponent's goal.

### `pitch_zones.py`
Pitch zone classification utilities. Divides the pitch into named zones (defensive third, middle third, final third; left/central/right channels) and provides functions to assign each event's x/y coordinates to a zone label.

### `possession_utils.py`
Possession sequence analysis. Chains consecutive same-team events into possession sequences, classifies each sequence by phase (build-up, positional play, finishing), and computes sequence-level metrics (length, progression, outcome).

### `time_utils.py`
Match time helpers. Normalises Opta minute/period fields, splits matches into halves, and provides binned time-window aggregators (e.g. events per 15-minute block).

---

## Utils (`utils/`)

### `config.py`
Central configuration constants for the Dash app layer.

- `COLORS` dict: all colour tokens used throughout the UI (primary blue `#004D98`, garnet `#A50044`, gold `#EDBB00`, dark theme backgrounds and borders, text colours)
- `APP_CONFIG` dict: app title, debug flag, host `0.0.0.0`, port `8050`
- `NAV_LINKS` list: ordered navigation links for the navbar

### `data_utils.py`
Primary data access layer — all pages and tabs load data exclusively through these functions. Reads Parquet files from `data/barcelona/result/`.

**Key responsibilities:**
- `COMPETITIONS` dict maps short keys (`laliga`, `ucl`, `copa`, `supercup`) to folder names on disk
- `COMPETITION_NAMES` maps folder names to display names (`La Liga`, `Champions League`, etc.)
- **In-process cache** (`_events_cache`): `get_all_events()` caches loaded DataFrames in memory keyed by season string, avoiding repeated disk reads across callbacks. Cleared via `clear_events_cache()` after the pipeline updates data
- **Own-goal helpers**: `is_own_goal(row)` and `filter_own_goals(df)` handle Opta's own-goal convention (tagged with `own goal == 'Si'`, attributed to the scoring team)

**Data loading functions:**
| Function | Description |
|---|---|
| `get_all_matches(season)` | All match metadata across all competitions for a season |
| `get_all_events(season)` | All match event rows for a season (cached) |
| `get_match_events(match_id)` | Event rows for a single match |
| `get_match_lineup(match_id)` | Lineup parquet for a single match (scans all dirs) |
| `get_recent_matches(n)` | Most recent N matches |
| `get_match_results()` | All match results with goals computed from event data |
| `get_player_stats(season)` | Per-player aggregated stats (goals, appearances, passes, shots, tackles, interceptions) |
| `get_player_events(player_name, season)` | All events for a specific player |
| `get_team_events(team_name, season)` | All events for a specific team |
| `get_team_season_stats(season, competition)` | Aggregate Barcelona team KPIs |
| `get_tournament_summary(season)` | Per-competition summary stats |
| `get_season_summary()` | Overall season W/D/L, GF, GA, points, win rate |
| `get_form_timeline()` | Cumulative points over time for trendline chart |
| `get_available_seasons(competition)` | Seasons present on disk |
| `get_all_teams(season, competition)` | All non-Barcelona teams in the dataset |

### `logos.py`
Maps team and competition names (as they appear in Opta data) to SVG asset filenames.

- `TEAM_LOGOS` dict: ~60 team name → SVG filename mappings covering La Liga, Champions League, Copa del Rey, and Super Cup opponents
- `TOURNAMENT_LOGOS` dict: competition display name → SVG filename
- `get_team_logo_path(team_name)` / `get_tournament_logo_path(competition)`: return Dash-relative `assets/...` paths
- `team_logo_img(team_name, size)` / `tournament_logo_img(competition, size)`: return `html.Img` elements ready to embed in layouts

### `match_data_adapter.py`
Schema-agnostic interface layer between raw Opta event DataFrames and the match analysis tab modules.

- Decomposes match events into tactical phases: organised possession, attacking/defensive transitions, set pieces, and contested phases
- Uses Opta qualifier flags (e.g. `Fast break`, `Set piece`, `From corner`) where available; falls back to event sequence inference when columns are absent
- All functions accept a pandas DataFrame of match events and return filtered/enriched DataFrames or summary dicts
- **Key exported functions**: `get_match_metadata()`, `compute_team_kpis()`, `get_starting_lineups()`, `get_substitutions()`, and phase-specific event extractors
- Designed to degrade gracefully — if a qualifier column is missing from the data, functions return empty results rather than raising errors

### `xt_utils.py`
Public bridge between Opta pass data and the xT model.

- `add_xt_column(passes_df)` — accepts any Opta pass DataFrame with `x`, `y`, `Pass End X`, `Pass End Y` columns and returns a copy with an `xT` column added (rows with missing coordinates get xT = 0)
- Lazy-loads the grid singleton on first call via `xT_model/predictor.py`

**Note**: Ball carries are not Opta events. xT accrues only to the passer, not to a player who carries the ball before passing. Any per-player xT ranking should be caveated accordingly.

---

## xT Model (`xT_model/`)

Grid-based Expected Threat model following the Soccermatics/Bellman-equation approach.

### Architecture

- **16 × 12 grid** divides the pitch into equal cells along x (length) and y (width)
- Each cell stores the expected threat from controlling the ball there, solved via Bellman iteration:

  ```
  xT[i,j] = P(shoot | i,j) × P(goal | shoot, i,j)
           + P(move  | i,j) × Σ T[i,j,k,l] × xT[k,l]
  ```

- `T` is the transition matrix — probability that a pass from cell (i,j) ends in cell (k,l)

### Files

| File | Purpose |
|------|---------|
| `train.py` | Training script — loads all Opta parquets (Barcelona + opposition), iterates to convergence, saves `xt_grid.npy`. Run: `python xT_model/train.py` |
| `predictor.py` | Lazy-singleton inference — `predict_xt(x1,y1,x2,y2)` returns non-negative xT gained; `add_xt_column(passes_df)` adds the column |
| `xt_grid.npy` | Trained artifact — shape `(16, 12)` |

---

## Opta Pipeline (`opta_pipeline/`)

A standalone automated pipeline for collecting and processing Opta match data for **FC Barcelona**. Can be run independently via CLI or triggered from the app UI by an admin user.

### `main.py`
Multi-competition pipeline orchestrator.

- Loads `config.yaml` and iterates over all configured competitions
- For each competition, runs three sequential steps: **Scrape → Download → Transform**
- Accepts CLI flags: `--skip-scraping`, `--skip-download`, `--transform-only`, `--competition <name>`
- Writes `logs/progress.json` after each step so `app.py` can poll for live UI updates
- Deletes `progress.json` on startup (clears stale state from crashed runs) and on successful completion
- Prints a final summary table: competitions processed, files scraped/downloaded/transformed

### `config.yaml`
Pipeline configuration file.

- **Competitions**: four competitions, each with `league_name` (folder name), season string, and Scoresway results URL
  - `Spain_Primera_Division`
  - `Spain_Copa_del_Rey`
  - `Spain_Super_Cup`
  - `UEFA_Champions_League`
- **Scraper settings**: page load timeout, cookie wait, scroll delay
- **Downloader settings**: Selenium Wire method, per-match timeout (45 s), sleep between matches (1.5 s), `skip_existing: true` to avoid re-downloading
- **Paths**: relative paths pointing to `../data/barcelona/target/`, `../data/barcelona/result/`, `../mappings/`, `logs/`
- **Output**: Parquet format, Snappy compression, PyArrow engine; filename pattern `{date}_{home_code}_vs_{away_code}_{match_id}`

### `modules/scraper.py` — `MatchScraper`
Scrapes match URLs from Scoresway results pages using Selenium.

- Launches a headless Chrome browser and navigates to the competition results URL
- Handles cookie consent banners automatically
- Paginates through all results using the Opta widget's "Previous" buttons
- Parses each row with BeautifulSoup to extract: `match_id`, `date`, `home`, `away`, `url_match`
- Returns a DataFrame of match records; new results are merged with the cached `matches_urls.csv` (new data wins on duplicates)

### `modules/downloader.py` — `MatchDownloader`
Downloads raw Opta JSON data for each match using Selenium Wire.

- Opens a headless Chrome browser instrumented with Selenium Wire to intercept XHR traffic
- Navigates to the match centre URL; captures PerformFeeds API responses for `matcheventfeed` and `lineups` payloads
- Validates each JSON before saving; retries up to 3 times with backoff on failure
- Saves raw JSON files to `data/barcelona/target/{league}/{season}/matchdata/`
- Skips matches where a valid JSON already exists (`skip_existing: true`)

### `modules/utils.py`
Shared utility functions used by both the scraper and downloader:

- URL normalisation and deduplication
- JSONP unwrapping (`extract_json_from_jsonp`)
- Match ID extraction from JSON payloads and URLs
- Path helpers: `get_organized_path_reversed(base_dir, league, season, filename, subdirectory)`
- Unique file path generation to avoid collisions

### `modules/transformers/`

All transformers inherit from `BaseTransformer` and implement a `transform_all()` method that iterates over raw JSON files and writes Parquet outputs.

#### `base_transformer.py` — `BaseTransformer`
Abstract base class providing:
- Config and logger injection
- JSON/JSONP file reading helpers
- Atomic Parquet/CSV save via temp-file-then-rename
- Skip logic: `_output_exists(match_id, subdirectory)` checks whether a result parquet already exists before reprocessing

#### `match_transformer.py` — `MatchTransformer`
Transforms raw match JSON into `match/` Parquet files.

- Extracts match metadata: `match_id`, `match_date`, `match_time`, `home_team`, `away_team`, `venue`, `competition`, `season`, `week`
- One row per match; output: `data/barcelona/result/{league}/{season}/match/{filename}.parquet`

#### `matchevent_transformer.py` — `MatchEventTransformer`
Transforms raw matchevent JSON into `match_event/` Parquet files — the primary data source for all analysis.

- Parses every event: ~250 columns including match metadata, event core fields, player/team fields, x/y pitch coordinates, and ~200 qualifier flag columns
- Qualifier columns are pivoted from nested `{typeId, value}` objects into named columns (e.g. `Long ball`, `Cross`, `Big Chance`, `Pass End X`)
- Qualifier and event type names looked up from `mappings/` CSVs
- Output: `data/barcelona/result/{league}/{season}/match_event/{filename}.parquet`

#### `lineup_transformer.py` — `LineupTransformer`
Transforms lineup data (Opta `typeId=34` qualifier blocks) into `lineup/` Parquet files.

- Reads from already-downloaded `matchdata/*.json` files (no additional downloads needed)
- Extracts per-player records: `match_id`, `team_position`, `formation`, `player_name`, `jersey_number`, `formation_slot` (1–11, or 0 for subs), `role` (Start/Sub), `position`, `is_captain`, `sub_on_minute`
- Output: `data/barcelona/result/{league}/{season}/lineup/{filename}.parquet`

---

## Opposition Pipeline (`opposition_pipeline/`)

A separate pipeline that downloads match event data for **every team Barcelona faced in 2025-2026**, covering all competitions those opponents play in. Data is organised by country / team / competition — independent from the Barcelona pipeline.

### `main.py`
Opposition data pipeline orchestrator.

- Loads `config.yaml` to read the full opponent list and competition URLs
- **Phase 1 (Scrape once)**: Scrapes each competition's Scoresway results page once and caches it to `logs/scrape_cache/{competition}_matches.csv`. Multiple opponents in the same competition share the same cached scrape
- **Phase 2 (Filter & process)**: For each `(opponent × competition)` pair, filters the cached DataFrame using accent-insensitive team name matching, then downloads and transforms all matching matches
- Reuses all modules from `opta_pipeline/modules/` directly (no code duplication)
- Builds a per-`(team × competition)` config dict to route output to `data/opposition/{country}/{team}/{competition}/2025-2026/`
- CLI flags: `--team <name>`, `--competition <name>`, `--transform-only`, `--skip-download`, `--force-rescrape`
- Can also be triggered from the app UI by an admin user via the **Scout Opponents** tool on the Home page

**CLI usage:**

```bash
# Full pipeline — all opponents, all competitions
python opposition_pipeline/main.py

# Single team or single competition
python opposition_pipeline/main.py --team "Chelsea"
python opposition_pipeline/main.py --competition "England_Premier_League"

# Force re-scrape the Scoresway pages (otherwise uses cache)
python opposition_pipeline/main.py --force-rescrape

# Re-transform existing JSONs without re-downloading
python opposition_pipeline/main.py --transform-only
```

### `config.yaml`
Opposition pipeline configuration.

- **Season**: `2025-2026`
- **Competitions**: 21 competition entries with Scoresway results URLs spanning Spain, England, Germany, Belgium, France, Greece, Denmark, Czech Republic, and three UEFA competitions (UCL, UEL, UECL)
- **Opponents**: ~30 opponents, each with `team_name`, `country`, optional `search_name` (used when Scoresway's display name differs), and a list of competition keys
- **Paths**: `result_dir: "../data/opposition"`, `target_dir: "../data/opposition/target"`
- Scraper/downloader/output settings mirror the Barcelona pipeline

**Opposition data output structure:**
```
data/opposition/
└── {Country}/
    └── {Team_Name}/
        └── {Competition}/
            └── 2025-2026/
                ├── match_event/   # One .parquet per match
                ├── match/
                └── lineup/
```

---

## Mappings (`mappings/`)

Reference CSV files at the project root, shared by both the Barcelona and opposition pipelines.

| File | Description |
|---|---|
| `opta_event_types.csv` | Maps `event_type_id` integers to event type names (e.g. `1 → Pass`, `16 → Goal`) |
| `opta_qualifier_types.csv` | Maps `qualifier_type_id` integers to qualifier names (e.g. `72 → Cross`, `233 → Big Chance`) |

> **Note**: The string `"Team setp up"` (for `typeId=34`) is intentionally kept as-is in both the CSV and `matchevent_transformer.py` to preserve consistency with the raw Opta feed.

---

## Data (`data/`)

All processed Parquet data lives here, separated by pipeline:

```
data/
├── barcelona/
│   └── result/
│       └── {League}/{Season}/
│           ├── match/            # One .parquet per match — match metadata
│           ├── match_event/      # One .parquet per match — all ~250-column event rows
│           ├── lineup/           # One .parquet per match — per-player lineup rows
│           └── matches_urls.csv  # Scraped match URL index
│
└── opposition/
    └── {Country}/{Team}/{Competition}/{Season}/
        ├── match/
        ├── match_event/
        └── lineup/
```

**Barcelona competitions on disk**: `Spain_Primera_Division`, `UEFA_Champions_League`, `Spain_Copa_del_Rey`, `Spain_Super_Cup`

---

## Assets (`assets/`)

Static files served directly by Dash at `/assets/...`.

### `style.css`
Global CSS overrides and utility classes layered on top of Bootstrap dark theme. Defines layout helpers, custom scrollbar styles, and component-specific overrides.

### `fonts/`
- `Barcelona FC 23-24 Tipografstore.otf` — Official FC Barcelona typeface used for brand headings

### `logos/team/`
SVG team badge files (~80 teams) covering all La Liga clubs, Champions League opponents, Copa del Rey, and Super Cup participants.

### `logos/tournament/`
SVG competition logos for La Liga, UEFA Champions League, Copa del Rey, and Spanish Super Cup.

### `players/`
`.webp` player portrait images for the current Barcelona squad, named `{jersey_number}-{player_name}.webp`.

---

## Brand Colors

The application uses FC Barcelona's official color scheme on a dark background:

| Token | Hex | Usage |
|---|---|---|
| Primary Blue | `#004D98` | Navbar, primary buttons |
| Garnet | `#A50044` | Accent highlights |
| Gold | `#EDBB00` | KPI values, active nav links, alerts |
| Dark Background | `#0A0E27` | Main page background |
| Dark Secondary | `#151932` | Cards and panels |
| Dark Tertiary | `#1E2139` | Inputs and table rows |
| Dark Border | `#2A2F4A` | Card and panel borders |
| Text Primary | `#E8E9ED` | Main body text |
| Text Secondary | `#A5A8B8` | Labels and subtitles |

---

## Current Status

**Version**: 0.5.0

- Barcelona data pipeline fully operational across four competitions (La Liga, UCL, Copa del Rey, Super Cup)
- Opposition data pipeline built and configured for ~30 opponents across 21 competitions
- All five dashboard pages implemented: Home, Match Report (7 tabs), Barça DNA, Barça IQ, and Opposition Analysis
- Three-model xG suite (open play, direct free kick, penalty) with `XGRouter` — predictions displayed across all shot visualisations in the app
- Grid-based xT model (Bellman equation, 16×12) trained on Opta data; integrated in Barça DNA heatmap, player stats table, and player metrics
- Transitions tab fully rewritten — Defensive + Attacking sub-tabs with 30 s windows and side-by-side team view
- Barça DNA Player Analysis page: full tactical profile with xT heatmap, shooting, passing, possession, defending, and discipline panels

---

## To-Do

- [x] Opposition Analysis page
- [x] xG model (XGBoost, SHAP feature selection, monotone constraints)
- [x] xT model (grid-based Bellman equation, 16×12)
- [x] Barça DNA — full player analysis page (xT heatmap, shooting, passing, possession, defending)
- [x] Transitions tab — Defensive + Attacking sub-tabs with 30 s windows
- [ ] Bayesian model for opponent analysis

---

## Development Notes

- Built with Plotly Dash for interactive visualisations
- Uses mplsoccer for football-specific pitch plotting (server-side Matplotlib → base64 PNG → Plotly `layout_image`)
- Bootstrap components for responsive dark-theme UI
- Parquet + Snappy compression for fast columnar data access
- In-process event cache avoids re-reading large Parquet files across page callbacks
- Both pipelines reuse the same `opta_pipeline/modules/` (scraper, downloader, transformers)

---

## Author

Rishiraj Sinharay [LinkedIn](https://www.linkedin.com/in/rishirajsinharay/)
Masters in Sports Analytics
Escuela Universitaria Real Madrid Universidad Europea

---

*This is an academic project developed incrementally as part of the Masters thesis timeline.*
