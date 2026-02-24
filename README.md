# CuléVision - FC Barcelona Game Analysis Tool

**Masters Project in Sports Analytics**
Escuela Universitaria Real Madrid Universidad Europea

---

## Project Overview

CuléVision is a professional football analytics dashboard built specifically for FC Barcelona. The tool processes Opta event data to provide comprehensive match analysis, rival scouting, and tactical insights aligned with Barcelona's positional play philosophy.

---

## Key Features

- **Match Analysis**: Automated post-match breakdown across six tactical phases — Overview, Attack, Defence, Attacking Transition, Defensive Transition, and Set Pieces
- **Rival Analysis**: Comprehensive opposition scouting and SWOT analysis
- **Team Analysis**: KPIs defining Barcelona's playing style and game model across all competitions
- **Player Analysis**: Match-by-match individual statistics and performance metrics
- **Data Pipeline**: Fully automated Opta data ingestion (scrape → download → transform → store)
- **Live Update Overlay**: UI feedback with real-time pipeline progress while databases are being updated

---

## Prerequisites

- Python 3.9 or higher
- Google Chrome (required by Selenium for the data pipeline)
- pip package manager

---

## Installation

1. **Clone or download this repository**

2. **Install app dependencies**:
```bash
pip install -r requirements.txt
```

3. **Install pipeline dependencies** (if running the data pipeline):
```bash
pip install -r opta_pipeline/requirements.txt
```

4. **Run the application**:
```bash
python app.py
```

5. **Access the dashboard**:
   - Open your browser and navigate to: `http://localhost:8050`
   - Log in with `Guest / guest` or `Rishi / admin`

---

## Project Structure

```
CuléVision/
├── app.py                          # Main Dash application entry point
├── requirements.txt                # App Python dependencies
├── STYLING.md                      # UI/UX style guide
├── LICENSE
│
├── pages/                          # One module per dashboard page
│   ├── home.py
│   ├── match_analysis.py
│   ├── player_analysis.py
│   ├── team_analysis.py
│   ├── opposition_analysis.py
│   └── match_analysis_tabs/        # Sub-tabs for Match Analysis page
│       ├── shared.py
│       ├── overview.py
│       ├── attack.py
│       ├── defence.py
│       ├── attacking_transition.py
│       ├── defensive_transition.py
│       └── set_pieces.py
│
├── utils/                          # Shared utility modules
│   ├── config.py
│   ├── data_utils.py
│   ├── logos.py
│   └── match_data_adapter.py
│
├── opta_pipeline/                  # Standalone data ingestion pipeline
│   ├── main.py
│   ├── config.yaml
│   ├── requirements.txt
│   ├── modules/
│   │   ├── scraper.py
│   │   ├── downloader.py
│   │   ├── utils.py
│   │   └── transformers/
│   │       ├── base_transformer.py
│   │       ├── match_transformer.py
│   │       ├── matchevent_transformer.py
│   │       └── lineup_transformer.py
│   ├── mappings/
│   │   ├── opta_event_types.csv
│   │   └── opta_qualifier_types.csv
│   ├── data/
│   │   └── result/
│   │       └── {League}/{Season}/
│   │           ├── match/
│   │           ├── match_event/
│   │           └── lineup/
│   └── logs/
│       ├── pipeline.log
│       └── progress.json
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
- **Navbar**: Sticky top bar with brand gradient, nav links (Home, Match Analysis, Player Analysis, Team Analysis, Opposition Analysis), and a logout button
- **Page callbacks**: Registers all page-level Dash callbacks by calling each page module's `register_*_callbacks(app)` function

### `requirements.txt`
Python dependencies for the Dash application layer (Dash, Plotly, pandas, mplsoccer, dash-bootstrap-components, etc.).

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
- Admin-only: "Update Databases" button triggers the data pipeline (see `app.py`)

### `pages/match_analysis.py`
**Post-Match Analysis Page**

- Two dropdowns at the top: competition selector and match selector (filtered by competition)
- On match selection, renders a tabbed layout with six analysis tabs (see `match_analysis_tabs/` below)
- Passes the selected `match_id` to each tab's layout builder so all tabs read from the same match's event data

### `pages/player_analysis.py`
**Player Analysis Page**

- Season and competition filter dropdowns
- Player selector populated from all Barcelona players who appeared in the selected season
- Displays match-by-match stat table: appearances, goals, passes, shots, tackles
- Visualisations for individual player performance trends

### `pages/team_analysis.py`
**Team Analysis Page**

- Season and competition filters
- Aggregate Barcelona team KPIs: shots, shots on target, passes, pass accuracy, possession, corners, fouls, cards, tackles, interceptions, clean sheets
- Comparison views across competitions

### `pages/opposition_analysis.py`
**Opposition / Rival Analysis Page**

- Opponent selector (all non-Barcelona teams in the dataset)
- Season and competition filters
- Displays the opponent's match events and aggregated stats from their games involving Barcelona
- Designed for pre-match scouting reports

---

## Match Analysis Tabs (`pages/match_analysis_tabs/`)

These sub-modules are loaded on demand when a match is selected in Match Analysis. All tabs share common constants and pitch-drawing utilities from `shared.py`.

### `shared.py`
Shared constants, colour tokens (`HOME_COLOR`, `AWAY_COLOR`, `GOLD`), and reusable pitch-drawing helpers used by every other tab. Configures Matplotlib to use the `Agg` (non-interactive server-side) backend. Provides functions to render `mplsoccer` pitches as base64-encoded PNG images embedded in Dash `html.Img` elements.

### `overview.py`
**Tab 1 — Match Overview**

- Renders a horizontal `mplsoccer` pitch with both starting XIs positioned according to their formation and formation slot
- Uses `pitch.scatter()` to draw circular player markers; home team on the left, away team on the right
- Overlays jersey numbers and player names using Matplotlib text with path-effect outlines for readability
- Captain badge displayed next to the captain's name
- Substitutes panels flank the pitch on either side, showing player name, jersey number, and the minute of substitution
- TV-style horizontal bar comparisons below the pitch for key stats: possession, shots, shots on target, passes, pass accuracy, corners, fouls, yellow/red cards

### `attack.py`
**Tab 2 — Attack Phase**

- Shot map on an mplsoccer pitch: goals, saved shots, and misses plotted by pitch coordinates (x, y)
- Shot event table with player, minute, shot type (head/foot), zone, and outcome
- Barcelona attacking KPIs: total shots, shots on target, shot accuracy, goals, big chances

### `defence.py`
**Tab 3 — Defence Phase**

- Defensive action map: tackles, interceptions, clearances, and blocks plotted on pitch
- Defensive KPIs: tackles won, interceptions, blocks, clearances, fouls conceded, cards

### `attacking_transition.py`
**Tab 4 — Attacking Transition**

- Counter-attack and fast-break event map
- Identifies transitions using Opta qualifier `Fast break` and sequence analysis (defensive recovery → rapid forward progression)
- KPIs: number of counter-attacks initiated, counters resulting in shots, counters resulting in goals

### `defensive_transition.py`
**Tab 5 — Defensive Transition**

- Tracks pressing actions and ball recoveries immediately after possession loss
- PPDA (passes allowed per defensive action) as a pressing intensity metric
- Recovery map showing where Barcelona won the ball back after losing it

### `set_pieces.py`
**Tab 6 — Set Pieces**

- Corners, free kicks, and throw-ins plotted on pitch with delivery endpoints
- Separates attacking and defensive set piece phases
- Outcome breakdown: goals, shots, clearances from set pieces

---

## Utils (`utils/`)

### `config.py`
Central configuration constants for the Dash app layer.

- `COLORS` dict: all colour tokens used throughout the UI (primary blue `#004D98`, garnet `#A50044`, gold `#EDBB00`, dark theme backgrounds and borders, text colours)
- `APP_CONFIG` dict: app title, debug flag, host `0.0.0.0`, port `8050`
- `NAV_LINKS` list: ordered navigation links for the navbar
- `FEATURES` list: feature card definitions shown on the home page

### `data_utils.py`
Primary data access layer — all pages and tabs load data exclusively through these functions. Reads Parquet files from `opta_pipeline/data/result/`.

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
- `get_team_logo_path(team_name)` / `get_tournament_logo_path(competition)`: return Dash-relative `/assets/logos/...` paths
- `team_logo_img(team_name, size)` / `tournament_logo_img(competition, size)`: return `html.Img` elements ready to embed in layouts

### `match_data_adapter.py`
Schema-agnostic interface layer between raw Opta event DataFrames and the six match analysis tab modules.

- Decomposes match events into tactical phases: organised possession, attacking/defensive transitions, set pieces, and contested phases
- Uses Opta qualifier flags (e.g. `Fast break`, `Set piece`, `From corner`) where available; falls back to event sequence inference when columns are absent
- All functions accept a pandas DataFrame of match events and return filtered/enriched DataFrames or summary dicts
- **Key exported functions**: `get_match_metadata()`, `compute_team_kpis()`, `get_starting_lineups()`, `get_substitutions()`, and phase-specific event extractors
- Designed to degrade gracefully — if a qualifier column is missing from the data, functions return empty results rather than raising errors

---

## Opta Pipeline (`opta_pipeline/`)

A standalone automated pipeline for collecting and processing Opta match data. Can be run independently via CLI or triggered from the app UI.

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

- **Team**: target team name (`Barcelona`) and default results URL
- **Competitions**: list of four competitions, each with Opta competition ID, `league_name` (folder name), season string, and Scoresway results URL
  - `Spain_Copa_del_Rey`
  - `Spain_Primera_Division`
  - `Spain_Super_Cup`
  - `UEFA_Champions_League`
- **Scraper settings**: page load timeout, cookie wait, scroll delay
- **Downloader settings**: Selenium Wire method, per-match timeout (45 s), sleep between matches (1.5 s), `skip_existing: true` to avoid re-downloading
- **Paths**: relative paths for `data/`, `mappings/`, `data/target/`, `data/result/`, `logs/`
- **Output**: Parquet format, Snappy compression, PyArrow engine; filename pattern `{date}_{home_code}_vs_{away_code}_{match_id}`
- **Logging**: level `INFO`

### `modules/scraper.py` — `MatchScraper`
Scrapes match URLs from Scoresway results pages using Selenium.

- Launches a headless Chrome browser and navigates to the competition results URL
- Handles cookie consent banners by clicking accept buttons
- Paginates through all results pages using the Opta widget's "Previous" pagination buttons
- Parses each results row with BeautifulSoup to extract: `match_id`, `date`, `home`, `away`, `url_match`
- Returns a DataFrame of match URL records; new results are merged with the existing `matches_urls.csv` (new data wins on duplicates)

### `modules/downloader.py` — `MatchDownloader`
Downloads raw Opta JSON data for each match using Selenium Wire.

- Opens a headless Chrome browser instrumented with Selenium Wire to intercept network traffic
- Navigates to the match centre URL; captures XHR responses from the PerformFeeds API containing `matcheventfeed` and `lineups` JSON payloads
- Validates each captured JSON before saving (checks for non-empty, parseable content); retries up to 3 times on failure
- Saves raw JSON files to `data/target/{league}/{season}/matchdata/` with organised filenames
- Skips matches where a valid JSON file already exists (`skip_existing: true`)

### `modules/utils.py`
Shared utility functions used by both the scraper and downloader:

- URL normalisation and deduplication
- JSON body decoding (handles gzip, brotli, identity encodings)
- JSONP unwrapping (`extract_json_from_jsonp`)
- Match ID extraction from JSON payloads
- Path helpers: `get_organized_path_reversed(result_dir, league, season, filename)`
- Unique file path generation to avoid collisions

### `modules/transformers/`

All transformers inherit from `BaseTransformer` and implement a `transform_all()` method that iterates over raw JSON files and writes Parquet outputs.

#### `base_transformer.py` — `BaseTransformer`
Abstract base class providing:
- Config and logger injection
- Common file-reading helpers (`read_json`, JSON/JSONP detection)
- Path resolution utilities shared by all concrete transformers

#### `match_transformer.py` — `MatchTransformer`
Transforms raw match JSON into `match/` Parquet files.

- Extracts match metadata: `match_id`, `match_date`, `match_time`, `home_team`, `away_team`, `venue`, `competition`, `season`, `week`
- One row per match; output schema is flat with all match-level fields
- Output path: `data/result/{league}/{season}/match/{filename}.parquet`

#### `matchevent_transformer.py` — `MatchEventTransformer`
Transforms raw matchevent JSON into `match_event/` Parquet files — the primary data source for all analysis.

- Parses every event in the Opta feed: ~250 columns including match metadata, event core fields, player/team fields, x/y pitch coordinates, and ~200 qualifier flag columns
- Qualifier columns are pivoted from a nested list of `{typeId, value}` objects into named columns (e.g. `Long ball`, `Cross`, `Big Chance`, `Pass End X`, `Goal Mouth Z Coordinate`)
- Qualifier type names are looked up from `mappings/opta_qualifier_types.csv`
- Event type names are looked up from `mappings/opta_event_types.csv`
- Deduplicates events and converts dtypes for Parquet efficiency
- Output path: `data/result/{league}/{season}/match_event/{filename}.parquet`

#### `lineup_transformer.py` — `LineupTransformer`
Transforms lineup data (Opta `typeId=34` qualifier blocks) from matchevent JSON into `lineup/` Parquet files.

- Reads from already-downloaded `matchdata/*.json` files (no additional downloads needed)
- Extracts per-player lineup records: `match_id`, `team_position` (home/away), `formation`, `player_name`, `jersey_number`, `formation_slot` (1–11, or 0 for subs), `role` (Start/Sub), `position`, `is_captain`, `sub_on_minute`
- One row per player per team per match
- Output path: `data/result/{league}/{season}/lineup/{filename}.parquet`

### `mappings/`

Reference CSV files used by the transformers to decode numeric Opta type IDs into human-readable strings.

| File | Description |
|---|---|
| `opta_event_types.csv` | Maps `event_type_id` integers to event type names (e.g. `1 → Pass`, `16 → Goal`) |
| `opta_qualifier_types.csv` | Maps `qualifier_type_id` integers to qualifier names (e.g. `72 → Cross`, `233 → Big Chance`) |

> **Note**: The string `"Team setp up"` (for `typeId=34`) is intentionally kept as-is in both the CSV and `matchevent_transformer.py` to preserve consistency with the raw Opta data.

### `data/result/`
Output directory for all processed data, organised by league and season:

```
data/result/
└── {League_Name}/
    └── {YYYY-YYYY}/
        ├── match/            # One .parquet per match — match metadata
        ├── match_event/      # One .parquet per match — all ~250-column event rows
        ├── lineup/           # One .parquet per match — per-player lineup rows
        └── matches_urls.csv  # Scraped match URL index for this competition/season
```

Supported leagues: `Spain_Primera_Division` (from 2008–2009), `UEFA_Champions_League`, `Spain_Copa_del_Rey`, `Spain_Super_Cup`.

### `logs/`
- `pipeline.log`: Full pipeline run log with timestamps, stage names, match counts, and error traces
- `progress.json`: Written during pipeline execution; read by `app.py` every 2 seconds to display live progress in the update overlay. Deleted on clean startup and on completion

---

## Assets (`assets/`)

Static files served directly by Dash at `/assets/...`.

### `style.css`
Global CSS overrides and utility classes layered on top of Bootstrap dark theme styles. Defines layout helpers, custom scrollbar styles, and component-specific overrides.

### `fonts/`
- `Barcelona FC 23-24 Tipografstore.otf` — Official FC Barcelona typeface used for brand headings

### `logos/team/`
SVG team badge files (~80 teams) covering all La Liga clubs, Champions League opponents, Copa del Rey, and Super Cup participants. Filenames follow the pattern `{Club-Name}-v{year}.svg`.

### `logos/tournament/`
SVG competition logos for La Liga, UEFA Champions League, Copa del Rey, and Spanish Super Cup.

### `players/`
`.webp` player portrait images for the current Barcelona squad (Hansi Flick coaching staff + 25 first-team players), named `{jersey_number}-{player_name}.webp`.

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

**Version**: 0.1.0

- Data pipeline fully operational across four competitions
- Match Analysis page (all 6 tabs), Home, Player Analysis, Team Analysis, and Opposition Analysis pages implemented

---

## To-Do

- [ ] xG model
- [ ] Bayesian model for opponent analysis

---

## Development Notes

- Built with Plotly Dash for interactive visualisations
- Uses mplsoccer for football-specific pitch plotting (server-side Matplotlib → base64 PNG)
- Bootstrap components for responsive dark-theme UI
- Parquet + Snappy compression for fast columnar data access
- In-process event cache avoids re-reading large Parquet files across page callbacks

---

## Author

Rishiraj Sinharay [LinkedIn](https://www.linkedin.com/in/rishirajsinharay/)
Masters in Sports Analytics
Escuela Universitaria Real Madrid Universidad Europea

---

*This is an academic project developed incrementally as part of the Masters thesis timeline.*
