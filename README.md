# CuléVision — FC Barcelona Game Analysis Tool

**Masters Project in Sports Analytics**
Escuela Universitaria Real Madrid Universidad Europea

---

## Project Overview

CuléVision is a professional football analytics dashboard built for FC Barcelona. It processes Opta event data to provide comprehensive match analysis, player profiling, team intelligence, and rival scouting, all aligned with Barcelona's positional play philosophy.

---

## Key Features

- **Match Report**: Post-match breakdown across seven sections — Overview (H1/H2 stat splits, lineup pitch), Attacking Output, Build-Up & Passing, Defensive Structure (fouls/offsides overlay), Transitions & Counterpressing (15 s windows, both teams side-by-side), Goalkeeping, and Player Stats (including Positional xT). Match selection is a monthly calendar; a one-click PDF export is available
- **Team Analysis (Barça IQ)**: KPIs defining Barcelona's playing style and game model across all competitions, six sub-tabs
- **Player Analysis (Barça DNA)**: Season/match-level stats, attribute radar, Positional xT Heatmap (16×12 grid), shooting map, passing, possession, defending, and discipline panels
- **Opposition Analysis**: Scouting dashboard for every team Barcelona faced, covering defence, transitions, set pieces, in-possession patterns, and player profiling
- **xG Model**: Three specialised XGBoost models (open play, direct free kick, penalty) trained on Wyscout data with SHAP feature selection and monotone constraints. An `XGRouter` automatically routes each shot to the correct model. Integrated across all shot visualisations
- **xT Model**: Grid-based Expected Threat model (Bellman equation, 16×12 grid) trained on all Opta event data. Used in player stats tables and the Positional xT Heatmap
- **Unified Data Pipeline**: Single automated pipeline (`opta_pipeline`) handling data ingestion for FC Barcelona and all configured opponents — scrape → download → transform → store. Admin-triggered from the UI with optional team/competition filters

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

## Usage

### Running the App

```bash
python app.py                 # Starts on http://localhost:8050
```

### Running the Data Pipeline

```bash
# Full pipeline — all teams, all competitions
python opta_pipeline/main.py

# Single team or competition
python opta_pipeline/main.py --team "Barcelona"
python opta_pipeline/main.py --team "Chelsea"
python opta_pipeline/main.py --competition Spain_Primera_Division

# Re-transform existing JSONs without re-downloading
python opta_pipeline/main.py --transform-only

# Skip browser download step (scrape + transform only)
python opta_pipeline/main.py --skip-download

# Force re-scrape Scoresway pages (ignore CSV cache)
python opta_pipeline/main.py --force-rescrape
```

### Running Tests

```bash
pytest tests/ -v
```

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
│   ├── home.py                     # Season overview + pipeline trigger
│   ├── match_report.py             # /match-report
│   ├── barca_dna.py                # /barca-dna  (Player Analysis)
│   ├── barca_iq.py                 # /barca-iq   (Team Analysis)
│   ├── opposition_analysis.py      # /opposition-analysis
│   │                               # NOTE: the 7 Match Report sections (Overview, Attacking
│   │                               # Output, Build-Up & Passing, Defensive Structure,
│   │                               # Transitions, Goalkeeping, Player Stats) are inlined
│   │                               # inside match_report.py — there is no match_analysis_tabs/
│   ├── team_analysis_tabs/         # 6 sub-tabs for Team Analysis
│   │   ├── overview.py
│   │   ├── buildup.py
│   │   ├── chance_creation.py
│   │   ├── def_structure.py
│   │   ├── transitions.py
│   │   └── set_pieces.py
│   └── opposition_analysis_tabs/   # 6 sub-tabs for Opposition Analysis
│       ├── helpers.py
│       ├── overview.py
│       ├── buildup.py
│       ├── chance_creation.py
│       ├── defence.py
│       ├── transitions.py
│       └── set_pieces.py
│
├── xT_model/                       # Grid-based Expected Threat model
│   ├── train.py                    # Bellman-equation training script
│   ├── predictor.py                # Lazy-singleton inference
│   └── xt_grid.npy                 # Trained artifact — (16, 12) xT grid
│
├── xg_model/                       # XGBoost expected goals suite
│   ├── predictor.py                # XGPredictor, XGDFKPredictor, XGPenaltyPredictor, XGRouter
│   ├── xg_model_final.json
│   ├── xg_dfk_model_final.json
│   ├── xg_penalty_model_final.json
│   └── ...                         # Scalers, zone bounds, feature lists
│
├── utils/                          # Shared utility modules
│   ├── config.py                   # COLORS, APP_CONFIG, NAV_LINKS
│   ├── data_utils.py               # Barcelona data access layer
│   ├── opposition_data_utils.py    # Opposition data access layer
│   ├── event_utils.py              # Canonical event-extraction helpers
│   ├── match_data_adapter.py       # Phase-tagged match analysis
│   ├── xg_utils.py                 # add_xg_column() bridge
│   ├── xt_utils.py                 # add_xt_column() bridge
│   ├── logos.py                    # Team/tournament logo path helpers
│   ├── pdf_report.py               # PDF export via Flask route
│   └── player_analysis/
│       ├── metrics.py              # compute_player_stats(), get_player_percentiles()
│       └── wyscout_weights.py
│
├── page_utils/                     # Analytical helpers shared across tabs
│   ├── competitions.py
│   ├── event_filters.py
│   ├── visualizations.py
│   ├── pitch_zones.py
│   ├── possession_utils.py
│   └── time_utils.py
│
├── opta_pipeline/                  # Unified data ingestion pipeline
│   ├── main.py                     # Orchestrator — all teams × competitions
│   ├── config.yaml                 # 31 teams, 21 competitions
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
│       ├── progress.json           # Live progress state (polled by app.py)
│       ├── pipeline.log
│       ├── download_manifest.json  # Tracks downloaded match IDs
│       └── scrape_cache/           # Per-competition CSV caches
│
├── mappings/                       # Opta reference data
│   ├── opta_event_types.csv
│   └── opta_qualifier_types.csv
│
├── data/                           # All processed Parquet data (not in repo)
│   └── 2025-26/
│       └── {Country}/
│           └── {Competition}/
│               ├── match/          # One .parquet per match — metadata
│               ├── match_event/    # One .parquet per match — all ~250-col events
│               └── lineup/         # One .parquet per match — per-player rows
│
├── tests/                          # Unit tests for page_utils modules
│   └── test_phase_classifier.py
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

## Application Architecture

### `app.py`

Main entry point for the Dash application.

- **App initialisation**: Bootstraps Plotly Dash with Bootstrap dark theme and a custom HTML template injected via `app.index_string`
- **Authentication**: Session-based login/logout via `dcc.Store`. Two roles — `guest` and `admin`. Admins see the "Update Databases" button
- **URL routing**: Master callback `update_main_container` renders the correct page layout per URL path
- **Database update flow**: Admin clicks "Update Databases" → optional team/competition filter → spawns `opta_pipeline/main.py` as a background subprocess. A `dcc.Interval` polls every 2 seconds, reads `opta_pipeline/logs/progress.json`, and displays a full-screen live progress overlay. On completion, clears the in-process data cache and forces a page reload
- **PDF export**: Flask route at `/download-report/<match_id>` serves PDFs via `utils/pdf_report.py`

### Page Modules

| URL | File | Layout function |
|-----|------|-----------------|
| `/` | `pages/home.py` | `create_home_layout` |
| `/match-report` | `pages/match_report.py` | `create_match_analysis_layout` |
| `/barca-dna` | `pages/barca_dna.py` | `create_player_analysis_layout` |
| `/barca-iq` | `pages/barca_iq.py` | `create_team_analysis_layout` |
| `/opposition-analysis` | `pages/opposition_analysis.py` | `create_opposition_analysis_layout` |

Each page module exports exactly two functions: `create_*_layout()` and `register_*_callbacks(app)`.

---

## Data Pipeline (`opta_pipeline/`)

A unified automated pipeline collecting and processing Opta match data for FC Barcelona and all 30 configured opponents across 21 competitions.

### Two-Phase Design

**Phase 1 — Scrape (once per competition)**: Scrapes each competition's Scoresway results page, caches the match list as a CSV with a configurable TTL (default 1 day). Multiple teams in the same competition share one cached scrape.

**Phase 2 — Filter & Process (per team × competition)**: Filters the cached match list by team name, downloads missing match JSONs via Selenium Wire API interception, then transforms them into Parquet files. Files are stored once per match regardless of which team's pipeline downloaded them — cross-team match files are shared by filename pattern.

### Output Structure

```
data/2025-26/
├── Spain/
│   ├── Spain_Primera_Division/
│   │   ├── match/          2025-09-24_BAR_vs_RMA_abc123.parquet
│   │   ├── match_event/    2025-09-24_BAR_vs_RMA_abc123.parquet
│   │   └── lineup/         2025-09-24_BAR_vs_RMA_abc123.parquet
│   └── Spain_Copa_del_Rey/
├── Europe/
│   └── UEFA_Champions_League/
├── England/
│   └── England_Premier_League/
└── ...
```

Each match file covers **both teams' events**. Team filtering at read time uses the Opta 3-letter code embedded in filenames (`_BAR_vs_` or `_vs_BAR_`).

### Configuration (`opta_pipeline/config.yaml`)

- **31 teams**: Barcelona + 30 opponents, each with `team_code`, optional `team_code_alt` (for teams like PSG that use different codes across feeds), `search_name` for Scoresway matching, and a list of competition keys
- **21 competitions**: Each with a Scoresway results URL, spanning Spain, England, Germany, Belgium, France, Greece, Denmark, Czech Republic, and three UEFA competitions
- **Paths, scraper, downloader, and output settings**: Fully configurable

---

## ML Models

### xG Model (`xg_model/`)

Three specialised XGBoost models for expected goals:
- `XGPredictor` — open play shots
- `XGDFKPredictor` — direct free kick shots
- `XGPenaltyPredictor` — penalties
- `XGRouter` — automatically routes each shot to the correct model based on shot context

Trained on Wyscout data with SHAP-based feature selection and monotone constraints. Public bridge: `utils/xg_utils.py → add_xg_column(shots_df)`.

### xT Model (`xT_model/`)

Grid-based Expected Threat model following the Soccermatics/Bellman-equation approach.

- **16 × 12 grid** over the pitch; each cell stores the expected threat from controlling the ball there
- Solved via Bellman iteration: `xT[i,j] = P(shoot|i,j) × P(goal|shoot,i,j) + P(move|i,j) × Σ T[i,j→k,l] × xT[k,l]`
- Trained on all Opta match event data (Barcelona + opponents) via `python xT_model/train.py`. ⚠️ The training glob still points at the legacy `data/barcelona/result/**` and `data/opposition/**` paths — repoint it at `data/2025-26/**/match_event/` before retraining on current data. The shipped `xt_grid.npy` (16×12) is valid for inference as-is.
- Public bridge: `utils/xt_utils.py → add_xt_column(passes_df)`
- `predict_xt(x1,y1,x2,y2)` returns destination-minus-origin threat, clamped at 0 (threat-decreasing moves score 0)

---

## Data Schema

### Coordinate System

- `x`: 0–100 where 0 = own goal line, 100 = opponent goal line
- `y`: 0–100 where 0 = left touchline, 100 = right touchline
- Convention is **per-team**: both Barcelona and opponents attack left→right. Do **not** flip away-team coordinates.

### Core Event Columns

| Column | Notes |
|--------|-------|
| `event_type` | String event name (e.g. `'Pass'`, `'Goal'`, `'Tackle'`) |
| `event_type_id` | Integer type ID |
| `outcome` | `1` = success, `0` = failure |
| `x`, `y` | Pitch coordinates |
| `team_code` | Opta 3-letter code |
| `player_name` | String |
| `Pass End X`, `Pass End Y` | Destination for passes |

Full schema reference: see `CLAUDE.md`.

---

## Brand Colors

| Token | Hex | Usage |
|---|---|---|
| Primary Blue | `#004D98` | Navbar, primary buttons |
| Garnet | `#A50044` | Accent highlights |
| Gold | `#EDBB00` | KPI values, active nav links |
| Dark Background | `#0A0E27` | Main page background |
| Dark Secondary | `#151932` | Cards and panels |
| Dark Tertiary | `#1E2139` | Inputs and table rows |
| Dark Border | `#2A2F4A` | Card and panel borders |
| Text Primary | `#E8E9ED` | Main body text |
| Text Secondary | `#A5A8B8` | Labels and subtitles |

---

## Current Status

**Version**: 0.6.1

- Unified data pipeline: FC Barcelona + 30 opponents across 21 competitions in a single `opta_pipeline`
- Flat data structure: `data/2025-26/{Country}/{Competition}/` — each match file stored once, shared across teams
- All five dashboard pages implemented: Home, Match Report (7 tabs), Barça DNA, Barça IQ, Opposition Analysis
- Three-model xG suite (open play, direct free kick, penalty) with `XGRouter`
- Grid-based xT model (Bellman equation, 16×12) trained on all Opta data
- Transitions: Defensive + Attacking analysis with 15 s windows and side-by-side team view
- Barça DNA: full tactical profile with xT heatmap, shooting, passing, possession, defending, and discipline panels
- Admin UI: single "Update Databases" button with team/competition filter dropdowns
- E2E data fixes: team_code-based event filtering in opposition module (replaces fragile team_name substring matching); both caches (`_events_cache` + `_opp_events_cache`) cleared on pipeline completion; `DEF_ACTION_TYPES` / `SHOT_TYPES` corrected (removed non-existent `'Blocked Shot'`, fixed `'Ball recovery'` casing); xG pkl artifacts re-serialized for current pandas version

---

## To-Do

- [x] Opposition Analysis page
- [x] xG model (XGBoost, SHAP feature selection, monotone constraints)
- [x] xT model (grid-based Bellman equation, 16×12)
- [x] Barça DNA — full player analysis page (xT heatmap, shooting, passing, possession, defending)
- [x] Transitions — Defensive + Attacking analysis with 15 s windows
- [x] Unified pipeline — single `opta_pipeline` handles Barcelona + all opponents
- [ ] Bayesian model for opponent tendency analysis

---

## Author

Rishiraj Sinharay — [LinkedIn](https://www.linkedin.com/in/rishirajsinharay/)
Masters in Sports Analytics, Escuela Universitaria Real Madrid Universidad Europea

*This is an academic project developed as part of the Masters thesis.*
