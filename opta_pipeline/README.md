# Opta Pipeline — Unified Match Data Ingestion

A single automated pipeline for scraping, downloading, and transforming Opta football match data from Scoresway into analysis-ready Parquet files. Handles **FC Barcelona and all configured opponents** in one run.

---

## Overview

The pipeline automates the complete workflow for collecting and processing Opta match event data:

1. **Scrape** — Fetches match URLs from Scoresway competition results pages once per competition and caches them as CSV files
2. **Download** — For each team × competition, intercepts PerformFeeds API responses via Selenium Wire and saves raw JSON files
3. **Transform** — Converts JSON files into structured Parquet files with comprehensive event-level data (~250 columns)

All output goes to: `data/2025-26/{Country}/{Competition}/{subdir}/*.parquet`

---

## Architecture

```
┌───────────────────────────┐
│      Scoresway.com        │
└─────────────┬─────────────┘
              │  Phase 1 — Scrape each competition ONCE
              ▼
┌───────────────────────────┐
│    MatchScraper           │──► logs/scrape_cache/{comp}_matches.csv
└─────────────┬─────────────┘
              │
              │  Phase 2 — For each team × competition
              ▼
┌───────────────────────────┐
│    MatchDownloader        │──► data/target/{comp}/matchdata/*.json
│    (Selenium Wire)        │
└─────────────┬─────────────┘
              │
              ▼
┌───────────────────────────┐       data/2025-26/{Country}/{Competition}/
│    Transformers           │──►    ├── match/
│    MatchTransformer       │       ├── match_event/
│    MatchEventTransformer  │       └── lineup/
│    LineupTransformer      │
└───────────────────────────┘
```

### Key design decisions

- **Scrape once, filter many**: Each competition page is scraped once and cached. All teams in that competition share the cached result — no repeated Selenium scraping for the same URL.
- **Files stored once**: Match parquet files cover both teams' events. A Chelsea vs Villarreal UCL match is stored once under `Europe/UEFA_Champions_League/` and serves both Chelsea's and Villarreal's data — filtered at read time by the Opta 3-letter team code in the filename.
- **Atomic writes**: All Parquet and JSON saves use a `.tmp` → rename pattern to prevent corrupt files on crash.
- **Incremental by default**: `skip_existing: true` in config means the pipeline only downloads matches not already on disk.

---

## Configuration (`config.yaml`)

```yaml
season: "2025-2026"

competitions:
  Spain_Primera_Division:
    results_url: "https://www.scoresway.com/..."
  UEFA_Champions_League:
    results_url: "https://www.scoresway.com/..."
  # ... 21 competitions total

teams:
  - team_name: "Barcelona"
    team_code: "BAR"
    country: "Spain"
    competitions:
      - Spain_Primera_Division
      - UEFA_Champions_League
      - Spain_Copa_del_Rey
      - Spain_Super_Cup

  - team_name: "Paris Saint-Germain"
    team_code: "PSG"              # PSG only — do NOT add PAR (that is Paris FC, a different club)
    search_name: "Paris"
    country: "France"
    competitions:
      - France_Ligue_1
      - UEFA_Champions_League

  # ... 31 teams total (Barcelona + 30 opponents)

paths:
  result_dir: "../data/2025-26"
  target_dir: "../data/target"
  mappings_dir: "../mappings"
  logs_dir: "logs"
```

**Fields per team:**

| Field | Required | Notes |
|-------|----------|-------|
| `team_name` | Yes | Canonical display name |
| `team_code` | Yes | Opta 3-letter code used in parquet filenames |
| `team_code_alt` | No | Secondary code for teams that use different Opta codes across feeds. Supported by the data layer but **no team in the current config uses it** (PSG is `PSG`-only — see note below) |
| `search_name` | No | Override for Scoresway match; use when display name differs (e.g. "Betis" for "Real Betis") |
| `country` | Yes | Used for flag assets and log display (not for path construction) |
| `competitions` | Yes | List of competition keys from the competitions block |

---

## Usage

```bash
# Full pipeline — all 31 teams across their configured competitions
python opta_pipeline/main.py

# Single team
python opta_pipeline/main.py --team "Barcelona"
python opta_pipeline/main.py --team "Chelsea"

# Single competition (all teams that have it configured)
python opta_pipeline/main.py --competition Spain_Primera_Division

# Combine filters
python opta_pipeline/main.py --team "Real Madrid" --competition UEFA_Champions_League

# Re-transform existing JSONs without re-downloading (fast)
python opta_pipeline/main.py --transform-only

# Skip browser download; scrape + transform only
python opta_pipeline/main.py --skip-download

# Force re-scrape Scoresway pages (ignore cached CSVs)
python opta_pipeline/main.py --force-rescrape

# Process every match in a competition (no team filter)
python opta_pipeline/main.py --competition Spain_Primera_Division --full-competitions
```

---

## Output Structure

```
data/2025-26/
├── Spain/
│   ├── Spain_Primera_Division/
│   │   ├── match/
│   │   │   └── 2025-09-24_BAR_vs_RMA_abc123.parquet
│   │   ├── match_event/
│   │   │   └── 2025-09-24_BAR_vs_RMA_abc123.parquet
│   │   └── lineup/
│   │       └── 2025-09-24_BAR_vs_RMA_abc123.parquet
│   ├── Spain_Copa_del_Rey/
│   └── Spain_Super_Cup/
├── Europe/
│   └── UEFA_Champions_League/
├── England/
│   └── England_Premier_League/
├── Germany/
│   └── Germany_Bundesliga/
├── Belgium/
│   └── Belgium_First_Division_A/
├── France/
│   └── France_Ligue_1/
├── Greece/
│   └── Greece_Super_League/
├── Denmark/
│   └── Denmark_Superliga/
└── Czech_Republic/
    └── Czech_First_League/
```

Filename pattern: `{date}_{HOME_CODE}_vs_{AWAY_CODE}_{match_id}.parquet`

---

## Modules

### `modules/scraper.py` — `MatchScraper`

Scrapes match URLs from Scoresway using headless Chrome:
- Handles cookie consent banners automatically
- Paginates through all results using the widget's navigation
- Parses each row to extract: `match_id`, `date`, `home`, `away`, `url_match`
- Caches results to `logs/scrape_cache/{competition}_matches.csv` with configurable TTL (default 1 day)
- Merges new results with the cached CSV on re-scrape (new data wins on duplicates)

### `modules/downloader.py` — `MatchDownloader`

Downloads raw Opta JSON via Selenium Wire API interception:
- Opens headless Chrome instrumented with Selenium Wire
- Navigates to match centre URL; captures `api.performfeeds.com/soccerdata/matchevent/` responses
- Validates each JSON before saving; retries up to 3× with backoff on failure
- Saves to `data/target/{comp}/matchdata/{match_id}.json`
- Skips matches where a valid JSON already exists

### `modules/transformers/base_transformer.py` — `BaseTransformer`

Abstract base for all transformers:
- Config and logger injection
- JSON/JSONP file reading helpers (`extract_json_from_jsonp`)
- Atomic Parquet save via temp-file-then-rename
- Skip logic: checks whether output parquet already exists before reprocessing

### `modules/transformers/match_transformer.py` — `MatchTransformer`

Extracts match metadata into `match/*.parquet`:
- One row per match
- Columns: `match_id`, `match_date`, `match_time`, `home_team_name`, `away_team_name`, `home_score`, `away_score`, `venue`, `competition`, `season`, `week`

### `modules/transformers/matchevent_transformer.py` — `MatchEventTransformer`

Core transformer — produces `match_event/*.parquet` (~250 columns):
- Parses every event: core fields, player/team metadata, x/y pitch coordinates
- Qualifier columns pivoted from nested `{typeId, value}` objects into named columns (e.g. `Long ball`, `Cross`, `Big Chance`, `Pass End X`, `Assist`)
- Event type and qualifier names looked up from `mappings/opta_event_types.csv` and `mappings/opta_qualifier_types.csv`
- Both teams' events in each file

### `modules/transformers/lineup_transformer.py` — `LineupTransformer`

Extracts lineup data from already-downloaded JSONs — no additional downloads:
- Reads `typeId=34` qualifier blocks from `matchdata/*.json`
- Per-player columns: `match_id`, `team_position`, `formation`, `player_name`, `jersey_number`, `formation_slot` (1–11 for starters, 0 for subs), `role`, `position`, `is_captain`, `sub_on_minute`

### `modules/utils.py`

Shared utilities:
- `get_organized_path_reversed(base_dir, league, season, filename, subdir)` — constructs output path as `{base_dir}/{country}/{league}/{subdir}/{filename}`
- `get_competition_country(league_name)` — maps competition name to country folder
- URL normalisation, deduplication, JSONP unwrapping, match ID extraction

---

## Progress Tracking

The pipeline writes `logs/progress.json` after each step — the app polls this every 2 seconds to show a live progress overlay. Format:

```json
{
  "team": "Barcelona",
  "competition": "Spain_Primera_Division",
  "stage": "download",
  "detail": "Downloading match 14/38",
  "current_team": 1,
  "total_teams": 31,
  "current_match": 14,
  "total_matches": 38
}
```

`progress.json` is deleted on startup (clears stale state from crashed runs) and on successful completion.

---

## Download Manifest

`logs/download_manifest.json` tracks which match IDs have been downloaded. On the next run, already-downloaded IDs are skipped even if `skip_existing` in config is changed. Bootstrap-from-filesystem: if the manifest is absent, the pipeline scans existing files and rebuilds it.

---

## Troubleshooting

**Empty scrape result**: Check the `results_url` in `config.yaml`, verify the page loads in a browser, try increasing `timeout_seconds`, or add `--force-rescrape` to bypass cache.

**Download timeout**: Increase `timeout_per_match` (try 60 s). Some matches may have no event data in the Opta feed — these are skipped silently.

**Transform fails — team codes not found**: Check that `home_team_code` / `away_team_code` fields are present in the raw JSON. Re-download if the JSON is truncated or invalid.

**Team data appears blank in the dashboard**: Opta's stored `team_name` column in parquets sometimes differs from the `team_name` in `config.yaml` (e.g. `'Olympiakos FC'` vs `'Olympiakos Piraeus'`). The data layer uses `team_code` (reliable 3-letter identifier) rather than `team_name` substring matching. If a team shows 0 events, verify that `team_code` in `config.yaml` matches the code embedded in the parquet filenames and the `team_code` column in the parquet data.

**Data not refreshing after pipeline run**: The app maintains in-process caches (`_events_cache` for Barcelona, `_opp_events_cache` for opponents). Both are cleared automatically when the pipeline finishes. If stale data persists, restart the app process — `dcc.Location` page refreshes do not clear in-process caches.

**PSG team code**: Paris Saint-Germain is configured with `team_code: PSG` only. Do **not** add `PAR` as a `team_code_alt` — `PAR` is Paris FC, a different club, and would pull the wrong matches. The `team_code_alt` mechanism still exists in the data layer for genuinely dual-coded teams, but no team in the current config needs it.

---

## Supported Teams (2025-26)

**Spain**: Barcelona, Real Madrid, Athletic Club, Atletico de Madrid, Villarreal, Real Sociedad, Real Betis, Sevilla, Girona, Osasuna, Getafe, Celta de Vigo, Rayo Vallecano, Mallorca, Valencia, Alaves, Espanyol, Levante, Real Oviedo, Elche, Albacete, Guadalajara, Racing de Santander

**England**: Chelsea, Newcastle United

**Germany**: Eintracht Frankfurt

**Belgium**: Club Brugge

**France**: Paris Saint-Germain

**Greece**: Olympiakos Piraeus

**Denmark**: FC København

**Czech Republic**: Slavia Praha

---

## Disclaimer

This tool is for educational and research purposes. Users are responsible for respecting Scoresway's Terms of Service, applying appropriate rate limiting, and ensuring compliance with Opta's data licensing terms.
