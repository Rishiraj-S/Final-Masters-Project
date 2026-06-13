# CuléVision — Technical Documentation

**A bespoke Game-Analysis platform for FC Barcelona**

Masters Project in Sports Analytics
Escuela Universitaria Real Madrid — Universidad Europea
Author: Rishiraj Sinharay

> This document is the master technical reference for CuléVision. It is written to be detailed enough to (a) explain every moving part of the system to an engineer or analyst, (b) demonstrate the football-data expertise behind the tool, and (c) serve directly as the source prompt for a full project presentation. The final section ([Presentation Blueprint](#22-presentation-blueprint)) maps this content onto a slide-by-slide narrative.

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [What Problem This Tool Solves — The Analyst's Workflow](#2-what-problem-this-tool-solves--the-analysts-workflow)
3. [FC Barcelona's Game Model — The Analytical Lens](#3-fc-barcelonas-game-model--the-analytical-lens)
4. [KPIs That Define Each Phase of Play](#4-kpis-that-define-each-phase-of-play)
5. [Personalization to FC Barcelona](#5-personalization-to-fc-barcelona)
6. [Technology Stack](#6-technology-stack)
7. [Repository Structure](#7-repository-structure)
8. [Application Architecture](#8-application-architecture)
9. [Data Pipeline](#9-data-pipeline)
10. [Data Storage](#10-data-storage)
11. [Event Data Schema](#11-event-data-schema)
12. [Data Access Layer](#12-data-access-layer)
13. [Analytical Utilities & Phase Engine](#13-analytical-utilities--phase-engine)
14. [Machine-Learning Models — xG and xT](#14-machine-learning-models--xg-and-xt)
15. [Dashboard: Home](#15-dashboard-home)
16. [Dashboard: Match Report (Post-Match Automation)](#16-dashboard-match-report-post-match-automation)
17. [Dashboard: Barça DNA (Player Analysis)](#17-dashboard-barça-dna-player-analysis)
18. [Dashboard: Barça IQ (Own-Team Game Model)](#18-dashboard-barça-iq-own-team-game-model)
19. [Dashboard: Opposition Analysis (Rival Scouting)](#19-dashboard-opposition-analysis-rival-scouting)
20. [Answering the Coach's Questions](#20-answering-the-coachs-questions)
21. [UI, Styling, Auth, CI/CD, Setup](#21-ui-styling-auth-cicd-setup)
22. [Presentation Blueprint](#22-presentation-blueprint)
23. [Known Gotchas & Data Caveats](#23-known-gotchas--data-caveats)

---

## 1. Executive Summary

**CuléVision** is a full-stack, single-club football analytics platform built for **FC Barcelona**. It ingests raw Opta event data, enriches it with two custom machine-learning models (Expected Goals and Expected Threat), and serves an interactive five-page web dashboard that decomposes every match into the phases of play that define Barcelona's positional game.

The platform does three jobs an FC Barcelona analyst would otherwise do by hand:

1. **It automates the data plumbing.** A single command (or one admin button-click in the UI) scrapes fixture lists, downloads Opta JSON feeds, and transforms them into ~250-column analysis-ready Parquet tables — for Barcelona **and** 30 scouted opponents across 21 competitions.
2. **It analyses both Barcelona and its rivals through the same tactical framework.** The own-team view (*Barça IQ*), the player view (*Barça DNA*), the post-match view (*Match Report*), and the rival-scouting view (*Opposition Analysis*) all measure the same phases of play with the same KPI definitions, so a like-for-like comparison between "how we play" and "how they play" is always one click away.
3. **It answers the questions a coaching staff actually asks** — "where do we lose the ball and what happens next?", "how does this opponent build out from the back?", "which of our full-backs creates more from the half-space?", "is this striker's xG outperforming his finishing?" — and packages the answers as on-screen dashboards and a downloadable PDF match report.

The whole system is **personalised to FC Barcelona**: the data layer is hard-wired around the `BAR` team code, the branding uses the club's blaugrana palette and official typeface, the analytical phases are tuned to *juego de posición*, and the player radar is weighted with position-specific Wyscout importance coefficients.

| At a glance | |
|---|---|
| Pages | 5 (Home, Match Report, Barça DNA, Barça IQ, Opposition Analysis) |
| Analytical tabs / sections | 7 (Match Report) + 6 (Barça IQ) + 6 (Opposition) + 9 panels (Barça DNA) |
| Teams ingested | 31 (Barcelona + 30 opponents) |
| Competitions configured | 21 across 9 countries + 3 UEFA tournaments |
| Event columns per match | 250 |
| Custom ML models | 4 (xG open-play, xG direct-free-kick, xG penalty, xT grid) |
| Transition analysis window | 15 seconds after every possession change |
| Pitch-zone grid for xT | 16 × 12 |

---

## 2. What Problem This Tool Solves — The Analyst's Workflow

A club performance-analysis department repeats the same manual cycle for every fixture: pull the data feed, clean it, compute the team and player metrics, draw the pitch maps, write the post-match report, and re-do all of it for the next opponent's scouting dossier. CuléVision collapses that cycle into automated stages.

### 2.1 Automating the data work

| Manual analyst task | CuléVision automation |
|---|---|
| Find the fixture / match ID for each game | `MatchScraper` scrapes the competition results page once and caches the fixture list as CSV (Phase 1 of the pipeline) |
| Download the Opta feed for each match | `MatchDownloader` intercepts the PerformFeeds API response via Selenium-Wire, validates it, retries on failure, and saves raw JSON |
| Parse JSON → tidy event table | `MatchEventTransformer` pivots nested qualifier objects into a flat 250-column Parquet; `MatchTransformer` extracts match metadata; `LineupTransformer` extracts formations — **no extra download needed**, formations live inside the same feed |
| Re-key team identity across feeds | Files are stored once per match and filtered at read time by the Opta 3-letter `team_code` embedded in the filename — one Chelsea-vs-Villarreal file serves both teams' analyses |
| Recompute season aggregates | `data_utils` / `opposition_data_utils` maintain in-process caches and recompute KPIs on demand |
| Build the post-match report | The **Match Report** page renders a 7-section report and exposes a one-click **PDF export** via a Flask route |
| Benchmark a player vs peers | Barça DNA builds a season-wide LaLiga player pool, persists it to disk, and computes percentile-ranked radar scores automatically |

The pipeline is **incremental** (already-downloaded matches are skipped via a manifest) and **idempotent** (atomic temp-file-then-rename writes; deduplicated events), so the analyst can re-run it daily without re-doing work.

### 2.2 Analysing own team and rivals through one framework

The same phase definitions, the same KPI formulas, and the same pitch-zone boundaries are applied to Barcelona (*Barça IQ*) and to every scouted opponent (*Opposition Analysis*). This is deliberate: a scouting report is only actionable if it is measured on the same axes as the self-assessment. Both pages expose an identical **Game Model Radar** (Build-up, Chance Creation, Transitions, Defensive Structure, Set Pieces) with dashed league-average overlays, so "us vs them vs the league" is a single visual.

### 2.3 Answering coaches' questions

Section [20](#20-answering-the-coachs-questions) walks through concrete coaching questions and shows exactly which dashboard, tab, and metric answers each one. The design principle throughout: **every number on screen traces back to a documented event-level definition**, so an analyst can defend any figure in a coaches' meeting.

---

## 3. FC Barcelona's Game Model — The Analytical Lens

CuléVision is not a generic analytics tool with a Barça skin. Its analytical decomposition is built around the way FC Barcelona plays — *juego de posición* (positional play). Every dashboard tab maps to a phase of that model.

### 3.1 The principles encoded

1. **Dominate possession to control the game.** Possession share, pass volume, and pass accuracy are first-class KPIs on every team view. Where true possession time is unavailable from the feed, it is approximated by **pass-count share** (and, in the match adapter, by **successful pass + take-on share**).
2. **Build from the back and progress through structure.** The build-up phase is measured by progressive passing, field tilt, average passes per possession, and positional xT — i.e. *how cleanly and how threateningly we move the ball forward*, not just how much we have it.
3. **Attack the high-value zones.** Final-third entries, **Zone 14** (central pocket in front of the box), and the **half-spaces** are explicitly modelled as separate entry channels. Chance quality is judged by xG, big chances, and box shots rather than raw shot counts.
4. **Win the ball back immediately — the 15-second counterpress.** Barcelona's defensive identity is built on regaining possession quickly after losing it. The transition engine tags a **15-second window** after every possession change and classifies the outcome.
5. **Defend high and compact.** Pressing intensity is measured with **PPDA** (passes allowed per defensive action) and pressing height (where on the pitch the ball is regained).
6. **Be ruthless on set pieces.** Corners (in/out-swinger, side, connection rate), free kicks, and penalties are modelled separately.

### 3.2 The phase taxonomy in code

Two complementary phase models coexist:

**(a) Event-level possession phases** — `utils/match_data_adapter.py:tag_possession_phases()` labels every Barcelona on-ball event with one of four phases, applied as layered overwrites (later wins), so the priority is **Fast Break > Finishing > Progression > Build-Up**:

| Phase | Rule |
|---|---|
| `build_up` | event ∈ {Pass, Ball recovery, Ball touch} **and** `x < 50` |
| `progression` | event ∈ {Pass, Take On, Ball touch} **and** `33 ≤ x ≤ 80` |
| `finishing` | event ∈ {Miss, Saved Shot, Goal} |
| `fast_break` | Opta `Fast break` qualifier set (highest priority) |

**(b) Five-phase Game Model scorecard** — the team pages (`team_analysis_tabs/overview.py`, `opposition_analysis_tabs/overview.py`) compute a 0–100 score for each of five phases and plot them on a radar against per-competition league averages:

| Phase | Score formula (as implemented) |
|---|---|
| Build-up | possession % = team passes ÷ all passes × 100 |
| Chance Creation | `min(goals_per_match / 3.0 × 100, 100)`; falls back to `min(shots-on-target % × 1.3, 100)` for small samples |
| Transitions | opposition-half gains ÷ total gains × 100, gains ∈ {Ball Recovery, Interception}, opp-half = `x ≥ 50` |
| Defensive Structure | `max(0, min(100, 100 − goals-against-per-match × 25))` |
| Set Pieces | connected set-piece passes ÷ all set-piece passes × 100 |

This dual model is intentional: (a) drives the pitch-level visualisations and per-event filtering; (b) drives the high-level "are we true to our game model?" radar.

---

## 4. KPIs That Define Each Phase of Play

This is the analytical core of the platform. Every KPI below is computed from event-level data with the exact definition shown, and every pitch-zone threshold is shared across all pages.

### 4.1 Shared spatial conventions

| Concept | Definition |
|---|---|
| Coordinate frame | `x` 0→100 own-goal→opponent-goal, `y` 0→100 left→right touchline. **Per-team normalised** — both teams attack left→right; never flip away-team coordinates. |
| Defensive Third | `x < 33.33` |
| Middle Third | `33.33 ≤ x ≤ 66.67` |
| Final Third | `x > 66.67` |
| Zone 14 | `x ∈ [66.67, 83.33]` and `y ∈ [37, 63]` (central pocket) |
| Left Half-Space | `x > 66.67` and `y ∈ (63, 79]` |
| Right Half-Space | `x > 66.67` and `y ∈ [21, 37)` |
| Penalty Box | `x ≥ 83` and `y ∈ [21.1, 78.9]` |
| Progressive Pass | successful pass with `(Pass End X − x) ≥ 25` (team views); `> 10` in the per-player Match-Report leaderboard |
| Box Shot | shot with `x ≥ 83` |

> Minor note for accuracy: `page_utils/pitch_zones.py` uses third boundaries of `33.3 / 66.7`, while the match adapter and tab modules use `33.33 / 66.67`. Treat the third cutoff as "~2/3 of the pitch"; the ~0.03-unit difference is immaterial to any count.

### 4.2 Phase 1 — Build-Up (playing out from the back)

| KPI | Definition |
|---|---|
| Possession % | team pass count ÷ both-teams pass count |
| Pass Accuracy % | `outcome == 1` passes ÷ all passes |
| Progressive Passes | successful, `(Pass End X − x) ≥ 25` |
| Field Tilt % | team's final-third (`x > 66.67`) pass share of both teams' final-third passes |
| Avg Passes / Possession | passes ÷ number of possession sequences (a possession starts on the first team event following an opponent event) |
| Positional xT | `add_xt_column(passes)['xT'].sum()` — total Expected Threat generated by passing |
| Into Final Third | passes with `Pass End X > 66.67` |
| Pass Network | edge = a successful pass immediately followed by a teammate's next event; edges with count < 2 dropped; node size ∝ involvement (MinMaxScaler 14→36); node position = mean pass-origin |

### 4.3 Phase 2 — Progression (moving through the thirds)

| KPI | Definition |
|---|---|
| Final-Third Entries | a pass/carry/touch crossing from `x < 66.67` to `x ≥ 66.67` |
| Zone 14 Entries | end coordinate inside Zone 14 or either half-space |
| Entry channel split | by end-`y`: Left `> 66.67`, Right `< 33.33`, else Centre |
| Led to Shot / Goal | entry followed by a shot/goal within the next 5 events |
| Ball Carries / Dribbles | Take On attempts and successes; dribble success % |

### 4.4 Phase 3 — Chance Creation & Finishing

| KPI | Definition |
|---|---|
| Shots | event ∈ {Miss, Saved Shot, Goal, Post} |
| Shots on Target | Saved Shot + Goal |
| xG | per-shot Expected Goals from the xG model (see §14.1) |
| Non-Penalty Goals | goals excluding penalties, own goals excluded |
| Big Chances | shot with `Big Chance == 'Si'` |
| Box Shots | `x ≥ 83` |
| Assists | pass with `Assist == 16` |
| Key Passes | pass with `Assist ∈ {13,14,15}` (or `2nd assist == 'Si'`) |
| xA (Expected Assists) | xG of the shot immediately following a player's pass |
| Goal Conversion | goals ÷ shots |
| Set-Piece Goals | goals flagged by set-piece qualifier or preceded by a set-piece pass |

### 4.5 Phase 4 — Attacking Transition (regain → attack, 15 s)

| KPI | Definition |
|---|---|
| Possession Gains | Ball Recovery, Interception, or successful Tackle |
| 15-second outcome | priority `Goal Scored > Shot Taken > Quick Turnover > Possession Held` within `(t₀, t₀+15s]` |
| Own-/Opp-Half Gains | `x < 50` / `x ≥ 50` |
| Final-Third Gains | `x ≥ 66.67` |
| Led to Shot / Goal | gain whose 15 s window contains a shot / goal |
| Quick Turnovers | possession lost again inside the window |

### 4.6 Phase 5 — Defensive Transition (loss → defend, 15 s)

| KPI | Definition |
|---|---|
| Possession Losses | Failed Pass, Lost Duel, Lost Aerial, Miscontrol, Dispossessed, Offside Pass, Error |
| 15-second outcome | priority `Goal Conceded > Shot Conceded > Recovered > No Clear Threat` |
| Recovered (counterpress success) | a Tackle / Interception / Ball Recovery by the losing team inside the window |
| Loss zone | Def Third `x < 33.33`, Att Third `x ≥ 66.67` |
| Led to Shot / Goal conceded | loss whose window contains an opponent shot / goal |

### 4.7 Phase 6 — Defensive Structure & Pressing

| KPI | Definition |
|---|---|
| Tackles Won % | successful tackles ÷ tackle attempts |
| Interceptions / Clearances / Ball Recoveries | event counts |
| Blocked Shots | `Blocked Pass` / block events |
| Defensive Duels Won % | (Tackle + Challenge) success rate |
| Aerial Win % | won aerials ÷ aerial duels |
| **PPDA** | Match Report: opponent passes ÷ (tackles + interceptions + fouls committed), whole pitch. Barça IQ / Opposition: opponent passes in `x < 40` ÷ team (tackles + interceptions) in `x > 50`. |
| Pressing Height | share of ball-regains in Def / Mid / Att third |
| Clean Sheets | matches with 0 goals conceded |

> Two PPDA implementations exist by design: the Match-Report version is a single-match whole-pitch ratio; the season views use the classic high-press definition (opponent build-up passes vs defensive actions in the opponent's territory). Both are documented so a coach knows which is on screen.

### 4.8 Phase 7 — Set Pieces

| KPI | Definition |
|---|---|
| Corners | `Corner taken == 'Si'`; side by `y` (right `< 50`, left `≥ 50`); delivery = Inswinger / Outswinger / Short; connection % = `outcome == 1` |
| Free Kicks | `Free kick taken == 'Si'` (passes); `Free kick == 'Si'` (shots); completion %, shots, goals |
| Penalties | shot with `Penalty == 'Si'`; scored %, saved, missed; goal-mouth placement plot |
| Set-Piece Zone-3 Entries | final-third / penalty-box entries originating from a set piece |

### 4.9 Goalkeeping KPIs

| KPI | Definition |
|---|---|
| Shots Faced / On Target Faced | shots against the GK's team |
| Saves / Goals Conceded | `Saved Shot` / `Goal` against |
| Save % | saves ÷ (saves + goals conceded) |
| xGA (Expected Goals Against) | pre-shot xG summed over faced shots |
| GSAvE | xGA − goals conceded (a simple shot-stopping over/under-performance proxy) |
| Distribution | GK pass map split by success |

---

## 5. Personalization to FC Barcelona

CuléVision is engineered as a club-specific product, not a configurable generic tool. The Barça-specific choices:

### 5.1 Data layer hard-wired to Barcelona
- `utils/data_utils.py` defines `BAR_CODE = 'BAR'` and a fixed four-competition map `_BARCA_COMPS` — **La Liga** (`Spain_Primera_Division`), **Champions League** (`UEFA_Champions_League`), **Copa del Rey** (`Spain_Copa_del_Rey`), **Spanish Super Cup** (`Spain_Super_Cup`).
- Every Barcelona query filters match files by the `_BAR_vs_` / `_vs_BAR_` filename pattern, so the entire Barça-facing dashboard is centred on the club without per-query configuration.
- Own-goal handling, top-scorer logic, and season summaries are all Barcelona-relative.

### 5.2 Brand identity
- The blaugrana palette is a first-class design token set: Primary Blue `#004D98`, Garnet `#A50044`, Gold `#EDBB00`, on a dark `#0A0E27` background.
- The club's official typeface (`assets/fonts/Barcelona FC 23-24 Tipografstore.otf`) is injected via `@font-face` for headings.
- Pages are named in the club's voice — **Barça DNA** (player identity) and **Barça IQ** (team intelligence).
- Team and tournament logos and country flags are resolved through `utils/logos.py`.

### 5.3 Tactical personalization
- The phase taxonomy (§3) encodes positional-play principles.
- The transition window is set to **15 seconds** — tuned to Barcelona's immediate-counterpress identity (the project history shows this was reduced from 30 s to 15 s to better isolate the gegenpress moment).
- The player radar uses **Wyscout position weights** (`assets/wyscout_weights/*.xlsx`): each role (GK, CB, FB, DM, CM, AM, Winger, ST) weights its attacking and defensive metrics by position-specific importance, so a full-back and a striker are judged on what matters for their role.

### 5.4 Scouting personalization
- The 30 configured opponents are exactly the teams Barcelona faced or could face across its four competitions plus the European opponents' domestic leagues — so the opposition database is the real Barça fixture/scouting universe, not an arbitrary set.

---

## 6. Technology Stack

| Layer | Technology |
|-------|-----------|
| Web framework | Plotly Dash (Flask-backed) |
| UI components | Dash Bootstrap Components (dark theme) |
| Charting | Plotly (interactive) + mplsoccer (server-side Matplotlib → base64 PNG pitch backgrounds) |
| Data | pandas, pyarrow, Parquet (snappy compression) |
| ML | XGBoost, scikit-learn, numpy, scipy |
| Pipeline | Selenium, Selenium-Wire, BeautifulSoup |
| Config | YAML |
| PDF | server-side report generation via a Flask route |
| Tests | pytest |
| CI | GitHub Actions |

**Rendering pattern.** Every pitch visualisation is drawn server-side with mplsoccer (`pitch_type='opta'`) to a base64 PNG, then used as a Plotly `layout_image` background with interactive markers/lines/arrows drawn on top in Plotly. Point markers always use `pitch.scatter()` (never `mpatches.Circle`, which distorts under non-square aspect ratios).

---

## 7. Repository Structure

```
CuléVision/
├── app.py                          # Single entry point (Dash + Flask)
├── requirements.txt
├── CLAUDE.md                       # AI coding-assistant guidance
├── STYLING.md                      # Design-system reference
│
├── pages/                          # One module per URL route
│   ├── home.py                     # /                Season overview + pipeline trigger
│   ├── match_report.py             # /match-report    7 sections + calendar + radars + PDF link
│   ├── barca_dna.py                # /barca-dna       Player analysis (9 panels)
│   ├── barca_iq.py                 # /barca-iq        Team analysis (6 tabs)
│   ├── opposition_analysis.py      # /opposition-analysis  Rival scouting (6 tabs)
│   ├── team_analysis_tabs/         # 6 tabs for Barça IQ
│   │   ├── overview.py  buildup.py  chance_creation.py
│   │   ├── def_structure.py  set_pieces.py
│   │   └── transitions.py → attacking_transition.py + defensive_transition.py
│   └── opposition_analysis_tabs/   # 6 tabs for Opposition Analysis
│       ├── helpers.py  overview.py  buildup.py  chance_creation.py
│       ├── transitions.py  defence.py  set_pieces.py
│
├── utils/                          # Backend utilities
│   ├── config.py                   # COLORS, APP_CONFIG, NAV_LINKS
│   ├── data_utils.py               # Barcelona data access
│   ├── opposition_data_utils.py    # Opposition data access (disk-discovered registry)
│   ├── event_utils.py              # Canonical event-extraction helpers
│   ├── match_data_adapter.py       # Phase-tagged match analysis
│   ├── xg_utils.py                 # add_xg_column() bridge
│   ├── xt_utils.py                 # add_xt_column() bridge
│   ├── logos.py                    # Team/tournament/flag path helpers
│   ├── pdf_report.py               # PDF export
│   └── player_analysis/
│       ├── metrics.py              # compute_player_stats, compute_5d_scores, percentiles, ratings
│       └── wyscout_weights.py      # position-weight loader
│
├── page_utils/                     # Shared analytical helpers (import, never redefine)
│   ├── competitions.py  event_filters.py  visualizations.py
│   ├── pitch_zones.py  possession_utils.py  time_utils.py
│
├── opta_pipeline/                  # Unified data ingestion
│   ├── main.py                     # Orchestrator — all teams × competitions
│   ├── config.yaml                 # 31 teams, 21 competitions
│   ├── modules/
│   │   ├── scraper.py  downloader.py  utils.py
│   │   └── transformers/
│   │       ├── base_transformer.py  match_transformer.py
│   │       ├── matchevent_transformer.py  lineup_transformer.py
│   └── logs/
│       ├── progress.json  pipeline.log  download_manifest.json  scrape_cache/
│
├── xT_model/
│   ├── train.py  predictor.py  xt_grid.npy  xT_model_analysis.ipynb
│
├── xg_model/
│   ├── predictor.py  README.md
│   ├── xg_model_final.json  xg_dfk_model_final.json  xg_penalty_model_final.json
│   ├── *_scaler.pkl  *_zone_bounds.pkl  *_selected_features.txt  *_monotone_constraints.json
│
├── mappings/                       # Opta reference data
│   ├── opta_event_types.csv  opta_qualifier_types.csv
│
├── data/                           # NOT in repo — distributed separately
│   └── 2025-26/{Country}/{Competition}/{match|match_event|lineup}/*.parquet
│
├── tests/  └── test_phase_classifier.py
└── assets/  ├── style.css  fonts/  logos/{team,tournament}/  players/  wyscout_weights/
```

> **Structural note:** The former `pages/match_analysis_tabs/` package has been **merged into the single module `pages/match_report.py`** (~5,970 lines). The seven tabs now live as labelled sections inside that file, with per-section private prefixes (e.g. `_ao_*` for Attacking Output, `_gk_*` for Goalkeeping). Behaviour is unchanged; only the file layout differs from earlier versions. The `team_analysis_tabs/` and `opposition_analysis_tabs/` packages remain split into separate files.

---

## 8. Application Architecture

### 8.1 Entry point — `app.py`

`app.py` is the only file executed directly. It:

1. Instantiates Dash with a custom `index_string` injecting the Barcelona typeface and dark theme.
2. Registers every page module's callbacks via `register_*_callbacks(app)`.
3. Defines the master routing callback `update_main_container`, which inspects `dcc.Location.pathname` and renders the correct `create_*_layout()`.
4. Registers the Flask route `/download-report/<match_id>` for PDF export.
5. Manages the database-update flow (admin pipeline trigger + progress polling).

### 8.2 URL → page map

| URL | Module | Layout function |
|-----|--------|-----------------|
| `/` | `pages/home.py` | `create_home_layout` |
| `/match-report` | `pages/match_report.py` | `create_match_analysis_layout` |
| `/barca-dna` | `pages/barca_dna.py` | `create_player_analysis_layout` |
| `/barca-iq` | `pages/barca_iq.py` | `create_team_analysis_layout` |
| `/opposition-analysis` | `pages/opposition_analysis.py` | `create_opposition_analysis_layout` |

Navbar order (`utils/config.py:NAV_LINKS`): **Home · Barça DNA · Barça IQ · Opposition Analysis · Match Report**.

### 8.3 Callback model

Dash callbacks are pure functions decorated with `@app.callback`. Side effects (file I/O, subprocess spawning) are confined to `app.py` and the `utils/` data layer. Each page registers its callbacks once at startup; sub-tab callbacks are registered transitively. No callbacks are defined at import time (avoids import-time side effects). Heavy sections render lazily — the Match Report renders each of its seven sections in its own callback keyed on the selected match, and a clientside callback drives a determinate progress bar that reveals the content only when all sections finish loading.

### 8.4 Database-update flow (admin)

```
Admin clicks "Update Databases"  (home.py modal)
  └─ selects optional team / competition filters
       └─ app.py spawns:  python opta_pipeline/main.py [--team X] [--competition Y]
            └─ dcc.Interval polls opta_pipeline/logs/progress.json every 2 s
                 └─ full-screen overlay: current team / competition / stage / match counts
                      └─ pipeline exits (progress.json deleted)
                           └─ app.py clears _events_cache + _opp_events_cache
                                └─ dcc.Location refresh=True → full page reload
```

### 8.5 PDF export

`/download-report/<match_id>` is a Flask route (bypassing Dash callbacks). It calls `utils/pdf_report.py:generate_match_report_pdf(match_id)` and returns the PDF via `Flask.send_file`. The Match Report page links to it with a "Download Match Report" button whose `href` is set to `/download-report/<selected match id>`.

---

## 9. Data Pipeline

`opta_pipeline/main.py` is the single entry point for all data collection — Barcelona and all 30 opponents in one run, via a two-phase design that minimises redundant scraping.

### 9.1 Phase 1 — Scrape (per competition, once)

For each competition in `config.yaml`:
1. Check `logs/scrape_cache/{competition}_matches.csv` age vs `cache_ttl_days` (default 1 day).
2. If fresh, reuse the cached CSV.
3. If stale or `--force-rescrape`, launch `MatchScraper`:
   - Headless Chrome with anti-detection (custom UA, removed `navigator.webdriver`), targeting the Opta widget.
   - Auto-dismiss cookie consent.
   - Handle both "Load More" and Previous/Next pagination (up to `max_pagination_clicks = 50`).
   - Parse each result row → `match_id, date, home, away, home_score, away_score, url_match`.
   - Dedupe on `match_id`/`url_match`, merge with the existing CSV (new rows win), save.

### 9.2 Phase 2 — Filter & Process (per team × competition)

For each `(team, competition)` pair:
1. Load the competition's cached match CSV.
2. Filter by team name with accent-insensitive matching (strips diacritics, ø/æ/å).
3. Cross-reference `logs/download_manifest.json` to skip already-downloaded match IDs.
4. Launch `MatchDownloader` for missing matches:
   - Selenium-Wire intercepts the `api.performfeeds.com/soccerdata/matchevent/` response on the match `/player-stats` page.
   - Picks the largest captured response, strips JSONP, validates structure (`ok / no_coverage / empty_events / bad_type`), retries up to 3× with backoff.
   - Atomic save (`.tmp` → rename) to `data/target/{competition}/matchdata/{match_id}.json`.
   - Permanent-skip markers (`.no_coverage`, `.no_data`) prevent re-attempting dead feeds.
5. Run all three transformers, then clean up the target JSONs.
6. Update the manifest; write `logs/progress.json`.

### 9.3 Transformers

**`MatchEventTransformer`** → `match_event/*.parquet` (**exactly 250 columns** = 37 fixed + 2 derived + 211 qualifier):
- Reads `matchdata/{match_id}.json` (or JSONP variant).
- Core fields: `event_id, event_type, event_type_id, period_id, time_min, time_sec, x, y, outcome, player_id, player_name, team_name, team_code, position, …`.
- Qualifier pivot: each `{typeId, value}` becomes a named column (looked up from `mappings/opta_qualifier_types.csv`); booleans stored as `'Si'` / `'N/A'`; valueless qualifiers become `'Si'`.
- Formation/lineup handling: `typeId=34` ("Team setp up" — intentional Opta typo) and Formation-change events seed a per-player formation/jersey/position map propagated onto subsequent events.
- Deduplication enabled; dtype optimisation on save.

**`MatchTransformer`** → `match/*.parquet` (one metadata row: teams, scores, venue, competition, season, week).

**`LineupTransformer`** → `lineup/*.parquet` (one row per player: `formation_slot` 1–11 for starters / 0 for subs, `role`, `position`, `is_captain`, `sub_on_minute`) — read from the same JSON, no extra download.

### 9.4 Competition → Country mapping (path construction)

| Prefix | Country folder |
|---|---|
| `Spain_*` | Spain |
| `England_*` | England |
| `Germany_*` | Germany |
| `France_*` | France |
| `Belgium_*` | Belgium |
| `Greece_*` | Greece |
| `Denmark_*` | Denmark |
| `Czech_*` | Czech_Republic |
| `UEFA_*` | Europe |

### 9.5 CLI reference

```
python opta_pipeline/main.py [OPTIONS]

  --team TEXT            Run for a single team (config.yaml name)
  --competition TEXT     Run for a single competition key
  --transform-only       Skip scrape+download; re-transform existing JSONs
  --skip-download        Scrape+transform only; no browser download
  --force-rescrape       Ignore cached CSVs; re-scrape all pages
  --full-competitions    Process every match in a competition (no team filter)
  --config PATH          Path to config.yaml
```

### 9.6 Configuration counts

`config.yaml` holds the season (`2025-2026`), **21 competition keys**, and **31 team entries** (Barcelona + 30 opponents). Each team has `team_name`, `team_code`, optional `search_name`, `country`, and a `competitions` list. Scraper/downloader/output settings (timeouts, snappy compression, pyarrow, dedupe, naming pattern) are all in the same file.

> **PSG note:** Paris Saint-Germain is configured with code `PSG` only; a config comment explicitly forbids adding `PAR` (which is Paris FC, a different club). The data layer's `team_code_alt` mechanism still exists and is read defensively by `opposition_data_utils.py`, but no team in the current config uses it.

### 9.7 Progress tracking & manifest

`logs/progress.json` (atomically written after each step; polled by the app every 2 s) carries `team, competition, stage, detail, status, current_team, total_teams, current_match, total_matches`. It is deleted on startup (clears stale state) and on success. `logs/download_manifest.json` tracks downloaded match IDs and is bootstrapped from existing Parquet filenames if absent.

---

## 10. Data Storage

### 10.1 Directory layout

```
data/2025-26/{Country}/{Competition}/
  ├── match/          one .parquet per match — metadata
  ├── match_event/    one .parquet per match — 250-col event table (both teams)
  └── lineup/         one .parquet per match — per-player rows
```

### 10.2 Filename convention & shared files

`{date}_{HOME_CODE}_vs_{AWAY_CODE}_{match_id}.parquet`
e.g. `2025-10-19_BAR_vs_BVB_8abc1234.parquet`.

Each match file contains **both teams' events**. A Chelsea-vs-Villarreal UCL file is stored once and read by both `data_utils` (Chelsea's analysis filters to `CHE`) and `opposition_data_utils` (Villarreal's filters to `VIL`). Team identity is encoded only in the filename and the `team_code` column — never in the directory tree.

### 10.3 Parquet config & caching

Snappy compression, PyArrow engine, dtype optimisation, deduplication. `data_utils._events_cache` (keyed by season) and `opposition_data_utils._opp_events_cache` (LRU, keyed by `(team, comp_key, season)`) are both cleared after pipeline runs via `clear_events_cache()` / `clear_opp_events_cache()`. Opposition reads parallelise across files with a thread pool when there are more than four.

---

## 11. Event Data Schema

### 11.1 Core columns (always present)

| Column | Type | Notes |
|--------|------|-------|
| `event_type` / `event_type_id` | str / int | human name + Opta numeric ID |
| `period_id` | int | 1 = H1, 2 = H2, 5 = penalties |
| `time_min` / `time_sec` | int | clock |
| `x` / `y` | float | 0–100 pitch coords (per-team normalised) |
| `outcome` | int | 1 = success, 0 = failure |
| `player_name` / `player_id` | str | |
| `team_name` / `team_code` | str | `BAR` = Barcelona; **filter by code, never name** |
| `position` | str | Opta position or `'N/A'` |
| `Pass End X` / `Pass End Y` | float | pass destination |
| `Length` / `Angle` | float | pass distance / angle |

### 11.2 Pass qualifiers (`'Si'` present / `'N/A'` absent)

`Long ball, Cross, Head pass, Through ball, Chipped, Launch, Lay-off, Flick-on, Pull Back, Switch of play, Free kick taken, Corner taken, Throw In, Goal Kick, Keeper Throw, Right/Left footed, High, From corner, Fast break, Intentional Assist, Inswinger/Outswinger/Straight, 2nd assist.`

**`Assist` column (numeric, the resulting shot's event-type ID):** `'13'`→Miss, `'14'`→Post, `'15'`→Saved Shot (key passes); `'16'`→Goal (assist); `'N/A'`→none.
```python
goal_assists = pass_rows['Assist'] == '16'
key_passes   = pass_rows['Assist'].isin(['13','14','15']) | (pass_rows.get('2nd assist','N/A') == 'Si')
```
**Do not** use `Leading to attempt` / `Leading to goal` for assists — those are on **Error (type 51)** events and carry a related event ID, not a flag.

### 11.3 Shot qualifiers

`Head, Right/Left footed, Big Chance, Assisted (on the shot, not the pass), Direct free, Regular play / Fast break / From corner / Set piece, Box-centre / Box-left / …, Goal Mouth Y/Z Coordinate.` The `own goal` qualifier is **always `'N/A'`** — own goals are identified programmatically by a Goal event whose scorer's `team_code` is the opponent.

### 11.4 Defensive outcomes & cards

`Tackle` outcome 1/0 = won/lost; `Interception`/`Ball recovery` always 1; `Take On`/`Aerial`/`Challenge` 1/0; `Pass` 1/0 = accurate/inaccurate. Fouls are stored as two rows (one per team); the committing team's row carries `Penalty == 'Si'` for penalty fouls. Cards: `Yellow Card / Second yellow / Red Card == 'Si'`.

> **`'Ball recovery'` has a lowercase r** — `events['event_type'] == 'Ball recovery'`.

---

## 12. Data Access Layer

### 12.1 Barcelona — `utils/data_utils.py`

Centred on `BAR_CODE = 'BAR'`, `CURRENT_SEASON = '2025-2026'`, and the four-competition `_BARCA_COMPS` map. Selected functions:

| Function | Returns |
|----------|---------|
| `get_all_events(season)` | all Barcelona `match_event` rows (cached) |
| `get_match_events(match_id)` | one match's events |
| `get_all_matches(season)` / `get_match_results()` | match metadata / results with computed scores |
| `get_player_events(player, season, comp)` / `get_team_events(team, …)` | filtered subsets |
| `get_season_summary()` | W/D/L, GF, GA, GD, points, win rate |
| `get_tournament_summary()` | per-competition aggregates (incl. top scorer, possession, pass accuracy) |
| `get_form_timeline()` | cumulative points / PPG trendline |
| `get_match_lineup(match_id)` | lineup parquet |
| `get_match_stats(match_id)` | home/away match stat dict |
| `clear_events_cache()` | reset caches |

Possession everywhere in this module = **pass-count share** (true possession time is not in the feed).

### 12.2 Opposition — `utils/opposition_data_utils.py`

- **Renames `event_type_id` → `type_id` on load.** Opposition tab modules must use `type_id`.
- **Filters strictly by `team_code`** (via `get_team_codes(team)`), never by `team_name` substring — Opta's stored names often differ from display names (e.g. `'Olympiakos FC'` vs `'Olympiakos Piraeus'`).
- **The opponent registry is auto-discovered from disk**, not from config: `_discover_team_registry()` scans every `match/*.parquet`, reads home/away name+code, and exposes every team with ≥ 1 match (≈ 212 teams). `config.yaml` is consulted only as an override for code spelling / country / search name. `list_available_opponents()` returns the registry minus `BAR`.
- Key functions: `load_opp_events(team, comp_key, venue, match_ids, date_cutoff)` → `(opp_ev, bar_ev)` split tuple; `get_opp_team_events`, `get_opp_team_matches`, `get_opp_possession`, `competition_match_event_paths` (for league averages), `clear_opp_events_cache()`.

### 12.3 Canonical event helpers — `utils/event_utils.py`

**Always import from here; never filter events inline.** These encode the qualifier conventions (the `'Si'`/`'N/A'` strings, lowercase `'Ball recovery'`, the numeric `Assist` codes). They return filtered DataFrames; rate helpers return `float 0–100`, count helpers return `int`. The composite `compute_event_stats(events_df)` returns a full per-player/per-team stat dict (apps, minutes, touches, goals, assists, shots, shot accuracy, conversion, key passes, passes, pass accuracy by half, long-ball/cross accuracy, tackles, interceptions, recoveries, clearances, aerials, take-ons, duels, fouls, cards, dispossessions).

---

## 13. Analytical Utilities & Phase Engine

### 13.1 `utils/match_data_adapter.py` — the phase engine

Schema-agnostic layer that decomposes a raw match into tactical phases. Key functions: `get_match_metadata`, `compute_team_kpis`, `tag_possession_phases` (§3.2a), `get_build_up_stats / get_progression_stats / get_fast_break_stats / get_finishing_stats`, `detect_possession_changes`, `get_counterattack_sequences`, `get_counterpress_sequences`, `get_set_piece_summary`, `get_pass_network_data`, `get_starting_lineups`, `get_substitutions`.

Time windows (function defaults):
- **Counter-attack:** 15 s from a Barça gain (Ball recovery / Interception / Tackle) to a shot.
- **Counter-press:** 5 s after a Barça loss; press actions = Tackle, Foul, Ball recovery, Interception, Challenge.
- **Momentum timeline:** 5-minute buckets.

`compute_team_kpis` possession = (successful passes + take-ons) share; final-third pass threshold `Pass End X > 66.67`.

### 13.2 `page_utils/` shared helpers

| Module | Provides |
|---|---|
| `competitions.py` | `ALL_COMPETITIONS` (La Liga, Champions League, Copa del Rey, Spanish Super Cup), `COMP_SHORT` (Liga/UCL/Copa/SC), `normalize_competitions`, `build_match_selector_options` |
| `event_filters.py` | `SHOT_TYPES = {Miss, Saved Shot, Goal, Post}`, `DEF_ACTION_TYPES = {Tackle, Interception, Ball recovery, Clearance}`, outcome colour/symbol maps, `filter_by_period`, `split_by_halves` |
| `pitch_zones.py` | `PitchZone` enum, `get_zone(x)`, `is_in_penalty_box(x,y)` (box `x≥83`, `y∈[21.1,78.9]`), third boundaries 33.3/66.7 |
| `possession_utils.py` | `annotate_possession` (adds `possession_id`, `possession_team`, `abs_time_sec`), `compute_vertical_speed`, `is_stable_possession(min_events=3)`; period offsets `{1:0, 2:2700, 3:5400, 4:6300}` s |
| `time_utils.py` | `to_seconds`, `format_seconds`, `events_within_window(direction='forward'/'backward')`, `rolling_event_windows`, `compute_match_duration` |
| `visualizations.py` | `HOME_COLOR`, `AWAY_COLOR`, `GOLD`, chart defaults, `render_lsc_heatmap_img` (KDE positional heatmap), `render_xt_heatmap_img` (16×12 gold xT heatmap) |

---

## 14. Machine-Learning Models — xG and xT

### 14.1 Expected Goals (xG) — three specialised XGBoost models

`xg_model/predictor.py` provides three classes plus a router. All share preprocessing; they differ only in the artifacts loaded.

| Class | Situation | Features | Trees (final / best-iter) |
|---|---|---|---|
| `XGPredictor` | open play | 21 | 1000 / 999 |
| `XGDFKPredictor` | direct free kicks | 15 | 535 / 484 |
| `XGPenaltyPredictor` | penalties | 12 | 186 / 135 |

**Routing (`XGRouter._route`), priority order:**
```python
if shot['is_own_goal'] == 1: return 'own_goal'   # → xG = None
if shot['is_penalty'] == 1:  return 'penalty'
if shot['pattern_direct_free_kick'] == 1: return 'dfk'
return 'open_play'
```

**Shared preprocessing:** map `period_id`→`period_name`; impute `shot_zone` from `(x,y)` against per-model zone-bounds tables (17 zones open play, 16 DFK, 3 penalty); one-hot encode `shot_zone` + `period_name`; MinMax-scale the five numeric columns `[x, y, distance_to_goal, angle_to_goal, time_min]`; align to the model's exact ordered feature list.

**Feature engineering** (computed in the bridge, not read from data):
- `distance_to_goal = √((100−x)² + (50−y)²)` (goal at `x=100, y=50`).
- `angle_to_goal = |atan2(55.38−y, dx) − atan2(44.62−y, dx)|` (posts at `y = 44.62 / 55.38`), `0` if `dx ≤ 0`.

**Model design:** XGBoost binary classifiers, `binary:logistic`. **Monotone constraints** `distance_to_goal: −1` and `angle_to_goal: −1` force xG to fall as distance grows / angle narrows. **SHAP-based feature selection** (per the model README) cut ~35 → 21 features at a 99.5 % cumulative-importance threshold. Tuning was RandomizedSearchCV (5-fold stratified) with early stopping on validation logloss. **Training data:** Wyscout historical shots (own goals excluded; each model trained on its own shot subset). The training scripts and Wyscout data are not shipped in the repo — only the inference `predictor.py` and the persisted artifacts.

**Artifacts per model:** `xg_*_model_final.json` (XGBoost native JSON), `xg_*_scaler.pkl` (MinMaxScaler), `xg_*_zone_bounds.pkl` (zone DataFrame), `xg_*_selected_features.txt` (ordered feature list), `xg_*_monotone_constraints.json`.

**Public bridge — `utils/xg_utils.py:add_xg_column(shots_df)`:** maps Opta qualifier columns → the feature dict, runs the router, and returns the frame with an `xg` column (float 0–1). Edge cases: empty frame → empty `xg` column; an existing `xg` column → returned unchanged; own goals → `NaN`; per-row mapping errors → `NaN`; lazy-singleton predictor. The model is loaded once on first call.

### 14.2 Expected Threat (xT) — grid Bellman model

`xT_model/train.py` builds a **16 × 12** grid (16 along `x`, 12 along `y`); `xt_grid.npy` is shape `(16, 12)`.

**Cell mapping:** `i = clip(int(x/100·16), 0, 15)`, `j = clip(int(y/100·12), 0, 11)`.

**Per-cell probabilities (Laplace +1 smoothing):**
```
shot_prob = (shot_count + 1) / (action_count + 2)        # P(shoot | cell)
move_prob = (pass_count + 1) / (action_count + 2)        # P(move  | cell)
goal_prob = (goal_count + 1) / (shot_count + 2)          # P(goal  | shoot, cell)
```
`action_count = shot_count + pass_count`. The **transition tensor** `T[i,j,k,l]` is built from pass origin→end cell counts, row-normalised.

**Bellman iteration (to convergence):**
```python
xT = shot_prob * goal_prob
for _ in range(n_iter):                                  # n_iter default 10
    xT_new = shot_prob*goal_prob + move_prob * einsum("ijkl,kl->ij", T, xT)
    if max|xT_new − xT| < 1e-6: break                    # converged
    xT = xT_new
xT = clip(gaussian_filter(xT, sigma=1.0), 0, None)       # smooth + non-negative
```

**Inference — `xT_model/predictor.py`:**
- `predict_xt(x1,y1,x2,y2) = max(grid[cell(x2,y2)] − grid[cell(x1,y1)], 0)` — destination-minus-origin threat, **clamped at 0** (threat-decreasing moves score 0). Accepts scalars or arrays.
- `add_xt_column(passes_df)` adds an `xT` column; rows with any missing coordinate get `xT = 0`.
- Public bridge: `utils/xt_utils.py:add_xt_column`.

**Known limitation:** Opta has no ball-carry events, so all "moves" are passes — ball-carrying wingers / progressive midfielders are systematically under-credited in per-player xT rankings. xT is a zone property, not action-level causation.

> **Retraining caveat:** `train.py` currently globs the legacy paths `data/barcelona/result/**/match_event/*.parquet` and `data/opposition/**/match_event/*.parquet`. The live data now lives at `data/2025-26/{Country}/{Competition}/match_event/`. To retrain on current data the glob in `train.py` must be pointed at the new root, otherwise it loads zero files. The shipped `xt_grid.npy` artifact remains valid for inference regardless.

---

## 15. Dashboard: Home

`pages/home.py` — `/`.

- **Season KPI cards:** matches, wins, draws, losses, GF, GA, GD, win rate, points.
- **Per-competition summary table:** W/D/L, goals, possession, pass accuracy, top scorer.
- **Match results table:** scrollable, W/D/L badges.
- **Cumulative points trendline.**
- **Admin only:** "Update Databases" button → modal with team/competition dropdowns → spawns the pipeline (see §8.4). Tournament/opponent logos and player images are resolved locally (`assets/...`, no leading slash).

---

## 16. Dashboard: Match Report (Post-Match Automation)

`pages/match_report.py` — `/match-report`. This is the analyst's automated post-match deliverable.

### 16.1 Match selection & headline
- A **monthly calendar** (not a dropdown) shows each fixture as a clickable button coloured by result (W green / D amber / L red), with opponent and tournament logos. A **tournament filter** (`pma-tournament-selector`, default *All Tournaments*) and **month navigator** scope it. The latest match is selected by default.
- The **score headline** card renders the tournament crest in a gold circle, both team logos, the scoreline (gold `H1`), kickoff time, and venue — built by a dedicated callback in `match_report.py` (not in the Overview section).
- A **"Download Match Report"** button links to the PDF Flask route for the selected match.
- Sections render lazily; a determinate progress bar (driven by a clientside callback counting still-loading sections) reveals the report only when all are ready.

### 16.2 The seven sections

| # | Section | Content |
|---|---|---|
| 1 | **Overview** | Both XIs on an mplsoccer vertical pitch (formation-positioned via a `(formation, slot) → (x,y)` map covering 13 formations), substitution panels, and TV-style stat bars. Each bar shows the full-match value with the **H1 / H2 split in brackets**: Possession, Shots, Shots on Target, Shots from Box, xG, Assists, Blocked Shots, Passes, Pass Accuracy, Fouls, Corners, Offsides, Interceptions, Yellow/Red Cards. |
| 2 | **Attacking Output** | Shot map on a vertical half-pitch (markers sized by xG, coloured/shaped by outcome: Goal ★, Saved ●, Miss ✕, Post ◆, Blocked ■), with goal-assist + key-pass + carry lines; a Top-Performers table (Shots / Goals / xG); and an Attack radar (Goals, Shots, SoT, xG, Assists, Box Shots, Crosses, Zone-3 Passes) vs league average. |
| 3 | **Build-Up & Passing** | Match-flow possession line (±5-min rolling); positional touch heatmap; **pass network** (edges ≥ 2, node size ∝ involvement); Zone 14 entries map + region breakdown; KPIs Total Passes, Pass Accuracy, **Field Tilt**, Avg Passes/Possession, **Positional xT**, Into Final Third, Long Balls, Crosses, Through Balls, Ball Carries, Dribble success. |
| 4 | **Defensive Structure** | Defensive action map (Tackle / Interception / Ball recovery / Clearance / Blocked Shot) **with fouls (✕) and offsides (▲) overlays**; Actions-by-Zone bars (this match vs league avg); per-player defensive table; KPIs incl. **PPDA** = opp passes ÷ (tackles + interceptions + fouls). |
| 5 | **Transitions & Counterpressing** | Both teams side-by-side. For each: losses-by-zone and gains-by-player tables, and **15-second** transition-outcome donuts. Defensive outcomes: No Threat / Recovered / Shot / Goal. Attacking outcomes: Held / Turnover / Shot / Goal. "Recovered" = a successful counterpress regain inside the window. |
| 6 | **Goalkeeping** | GK selector per team (live callback); Save-rate and Shots-Faced donuts; Full/H1/H2 stat table (Shots Faced, SoT, Saves, Conceded, **xGA** = pre-shot xG summed, Save %); GK distribution pass map. |
| 7 | **Player Stats** | Full per-player table (GKs excluded): Touches, Passes, Pass %, **Positional xT**, Shots, Goals, Assists, Key Passes, Tackles, Tackle Win %, Interceptions, Recoveries, Clearances, Aerials, Aerial Win %, Fouls, Dribbles — top-5 per column highlighted. **Progressive passes** here = `(Pass End X − x) > 10`. |

Plus a **Performance Radars** strip (Attack / Defence / Possession & Build-Up) rendered above the sections.

---

## 17. Dashboard: Barça DNA (Player Analysis)

`pages/barca_dna.py` — `/barca-dna`. The player-identity view.

### 17.1 Controls
Player dropdown (Barcelona squad), Competition filter, Match filter, and a **Total / Per 90** toggle (per-90 scaling `value × 90 / minutes`; percentages are never scaled).

### 17.2 The nine panels

1. **Profile + Season Stats** — photo (matched by jersey), bio, season cards (Matches, Minutes, Yellow, Red, Goals, Assists).
2. **Attribute Radar** — a 5-axis polar chart on the dimensions **ATT, DEF, TEC, PHY, OVR** (Attack, Defense, Technical, Physical, Overall), with a dotted LaLiga positional-average overlay.
3. **Positional xT Heatmap** — 16×12 gold grid via `render_xt_heatmap_img`.
4. **Shooting** — shot map (xG-sized markers) + outcome donut.
5. **Passing** — stats + accurate/inaccurate donut, including **xA** (xG of the next shot after each pass) and **Big Chances Created**.
6. **Possession** — dribbles, duels, touches, touch-zone donut (def/mid/att thirds), Touches in Opp Box (`x ≥ 83`), Fouls Won.
7. **Defending** — tackles, interceptions, recoveries, clearances, "Possession Won in Final Third" (successful defensive actions with `x > 66.67`), clean sheets / goals conceded / xGA in the player's matches.
8. **Discipline** — yellow/red card graphics.

### 17.3 The radar algorithm (`compute_5d_scores`)
- A player can hold **multiple Wyscout roles** — the modal position plus any position with ≥ 15 % of the player's events.
- The peer pool is every LaLiga player whose role overlaps the selected player's roles. The pool is built by reading every LaLiga `match_event` parquet, computing `compute_player_stats` per player, caching in-process **and** persisting to `logs/laliga_player_pool.json` (keyed by a season + file-count signature).
- Each dimension's score = a percentile rank (`scipy.stats.percentileofscore`) of a **weighted** metric score against the pool. Attack and Defense use **Wyscout position weights** (`assets/wyscout_weights/*.xlsx`, loaded by `wyscout_weights.py`, Spanish metric names mapped to internal keys); Technical and Physical use equal weights. Overall = mean of the four.

> The module also defines a separate 3-dimension A/B/C/D letter-grade rating (`get_player_ratings`, bands **A > 75, B > 50, C > 25, D ≤ 25**) and per-role pizza-metric dictionaries (`POSITION_PIZZA_ATT/DEF`). These are available in code but **not** rendered by the current Barça DNA page, which uses the 5-D Wyscout radar.

---

## 18. Dashboard: Barça IQ (Own-Team Game Model)

`pages/barca_iq.py` — `/barca-iq`. The own-team intelligence view: are we true to our game model?

**Filters:** Competition (multi-select), Venue (All / Home / Away), and a **multi-select match calendar**. Season is fixed to the current season. Six tabs:

| Tab | Key content & KPIs |
|---|---|
| **Overview** | Season banner (W/D/L, GD, Points, Pts/Game, Possession, PPDA); the **Game Model Radar** (Build-up / Chance Creation / Transitions / Def. Structure / Set Pieces, each 0–100, vs per-competition league averages); five phase cards; a toggleable form trendline (PPG, GF, GA, Possession, Pass Accuracy, PPDA, Passes/Possession). |
| **Build-up** | Interactive pass map (successful gold / failed garnet, "progressive only" toggle); positional touch heatmap; 3×3 pass-distribution (sent/received %); **pass network** & **pass matrix** (top-11 passer×receiver); Final-Third & Zone-14 entry maps + Top-5 entry tables; Top Progressive Passers / Possession. KPIs: Total, Accuracy, Progressive (`≥25`), Key Passes, Avg Passes/Poss, Field Tilt. |
| **Chance Creation** | Shot map (xG-sized, key-pass + carry lines); **Shooting & Threat Zones** (16×12 buildup-xT layer + shot-zone overlay; pre-shot xT uses a **30-second** look-back window); animated goal-sequence modal. KPIs: Shots, On Target, NP Goals, Set-Piece Goals, xG, Assists, Key Passes, xA, Box Shots, Big Chances; Top Scorers / Assisters. |
| **Transitions** | Two sub-tabs — **Attacking Transition** and **Defensive Transition** — each with a **15-second** window. Gain/Loss maps (shape = 15 s outcome), heatmaps, outcome donuts, by-player tables, by-zone bars. Outcomes as in §4.5–4.6. |
| **Def. Structure** | Defensive action map & heatmap; **Pressing Height** donut ("where we win the ball back"); Vulnerable Flanks bar; Offsides-provoked map; discipline table; opposition entries & shot map / shooting zones; GK statistics (Saves, Conceded, Save %, xGA, **GSAvE**, Box Saves) and action counts. |
| **Set Pieces** | Free-Kicks (shot map, zone-3 entry maps, takers table), Corners (trajectory maps + 8-zone landing grid, in/out-swinger split, connection %), Penalties (goal-mouth placement, scored %). |

---

## 19. Dashboard: Opposition Analysis (Rival Scouting)

`pages/opposition_analysis.py` — `/opposition-analysis`. The rival-scouting view, measured on the **same axes** as Barça IQ.

**Filters:** Country (flag-decorated) → Club (logo-decorated, cascades) → Competition → date cutoff ("show matches up to") → Venue (All / Home / Away) → multi-select match calendar. The team list is the **disk-discovered registry** (≈ 212 teams). Data is loaded via `load_opp_events(...)` → `(opp_ev, bar_ev)` and filtered by `team_code`/`type_id`.

| Tab | Content |
|---|---|
| **Overview** | Stat pills (Matches, Points, Pts/Game, GF, GA, Clean Sheets, Possession, Pass Acc.), record + GD, the **same Game Model Radar** vs league averages, five phase cards, form trendline, competition & contributor cards. |
| **Build-Up** | Pass map, positional touch heatmap, 3×3 pass distribution, pass network, Final-Third & Zone-14 entries; Top Progressive Passers. |
| **Chance Creation** | Shot map (xG-sized, key-pass + carry lines), 16×12 Shooting & Threat zones (30 s pre-shot xT), goal-sequence modal; Top Scorers / Assisters. |
| **Transitions** | Attacking + Defensive sub-tabs, **15-second** window, gain/loss maps + outcome donuts. |
| **Defence** | Defensive action map & heatmap, pressing-height donut, vulnerable/attacking flanks, offsides-provoked map, opposition entries, opponent shot map, shooting zones, GK block. |
| **Set Pieces** | Free-Kicks / Corners / Penalties, same definitions as Barça IQ. |

`helpers.py:no_data(msg)` provides the uniform empty-state placeholder used when a query returns nothing.

---

## 20. Answering the Coach's Questions

The platform is designed so that a coaching staff's natural-language questions map directly to a tab and a metric. Worked examples:

| Coach's question | Where it's answered | The metric / view |
|---|---|---|
| "Did we deserve to win, or were we lucky?" | Match Report → Attacking Output + Overview | xG for/against vs actual goals; shot quality map |
| "Where are we losing the ball, and does it hurt us?" | Match Report → Transitions / Barça IQ → Defensive Transition | Loss zones + 15 s outcome donut (Goal/Shot conceded vs Recovered) |
| "Is our counterpress working?" | Transitions tabs | "Recovered" share inside the 15 s window = counterpress success rate |
| "Are we pressing high enough?" | Barça IQ → Def. Structure | Pressing-height donut + PPDA |
| "How do we progress the ball — through the middle or the channels?" | Build-Up tabs | Final-Third / Zone-14 / half-space entry maps + region split |
| "Who actually creates our chances?" | Chance Creation / Player Stats | Key passes, xA, Big Chances Created per player |
| "Is this striker finishing well or just getting chances?" | Barça DNA → Shooting | Goals vs xG, conversion %, shot map |
| "How does next week's opponent build out from the back?" | Opposition Analysis → Build-Up | Their pass network, field tilt, progressive passes, zone entries |
| "What's their set-piece threat?" | Opposition Analysis → Set Pieces | Corner side/swinger split + connection %, FK shots, penalty record |
| "Where is this opponent vulnerable defensively?" | Opposition Analysis → Defence | Vulnerable-flanks bar, pressing height, shooting zones conceded |
| "Give me a one-pager for the staff meeting." | Match Report → Download Match Report | PDF export of the full 7-section report |

Because Barça IQ and Opposition Analysis share the Game Model Radar, the staff can place "us" and "them" on the same five-axis chart and instantly see where the tactical mismatch lies.

---

## 21. UI, Styling, Auth, CI/CD, Setup

### 21.1 Colour tokens (`utils/config.py:COLORS`, mirrored in `assets/style.css`)

| Token | Hex | Usage |
|-------|-----|-------|
| `primary` | `#004D98` | navbar, primary buttons |
| `garnet` | `#A50044` | accents, active states |
| `gold` | `#EDBB00` | KPI values, badges, active nav |
| `dark_bg` | `#0A0E27` | page background |
| `dark_secondary` | `#151932` | cards/panels |
| `dark_tertiary` | `#1E2139` | inputs, table rows |
| `dark_border` | `#2A2F4A` | borders |
| `text_primary` / `text_secondary` | `#E8E9ED` / `#A5A8B8` | body / labels |

Pitch constants (`HOME_COLOR`, `AWAY_COLOR`, `GOLD`) are imported from `page_utils/visualizations.py` — never hardcoded in page modules. Logo/image paths use the Dash-relative `'assets/...'` format (no leading slash).

### 21.2 Authentication

Session-based, in `app.py` via `dcc.Store(storage_type='session')`. Two roles: **Guest** (`Guest`/`guest`, read-only) and **Admin** (`Rishi`/`admin`, full access + pipeline trigger). Credentials are compared against a dict; passwords are not hashed — this is an academic project, not a public deployment.

### 21.3 CI/CD

GitHub Actions (`.github/workflows/ci.yml`) runs on PRs and pushes to `main`: Python 3.11, install requirements, `pytest tests/ -v`. Tests cover the `page_utils` layer (pitch zones, possession, time utilities) — pure unit tests, no Selenium / Parquet I/O / pipeline invocation.

### 21.4 Setup & commands

```bash
pip install -r requirements.txt
python app.py                       # http://localhost:8050  (Guest/guest or Rishi/admin)

# Pipeline
python opta_pipeline/main.py                       # all teams, all comps
python opta_pipeline/main.py --team "Barcelona"
python opta_pipeline/main.py --competition Spain_Primera_Division
python opta_pipeline/main.py --transform-only      # fast, no browser

# Retrain xT (see retraining caveat in §14.2)
python xT_model/train.py

# Tests
pytest tests/ -v
```

**Adding a team:** add a `teams:` entry in `config.yaml` (`team_name`, `team_code`, optional `search_name`, `country`, `competitions`), add the competition URL if new, run `--team "<name>"`.
**Adding a competition:** add it to `competitions:` with its results URL, add its prefix to `_COMPETITION_COUNTRY` (`opta_pipeline/modules/utils.py`) and `_COMP_COUNTRY` (`utils/opposition_data_utils.py`), run `--competition <key>`.

---

## 22. Presentation Blueprint

This document is structured so it can be turned directly into a slide deck. Suggested narrative:

1. **Title** — CuléVision: a bespoke Game-Analysis platform for FC Barcelona. (From §1.)
2. **The problem** — the manual analyst cycle, repeated every fixture. (§2.)
3. **The thesis** — one tool that automates the data, analyses us and our rivals on the same axes, and answers the coach. (§2.)
4. **Barça's game model** — the principles, the phase taxonomy. (§3.)
5. **KPIs per phase** — one slide per phase (Build-up, Progression, Chance Creation, Att/Def Transition, Defensive Structure, Set Pieces) with the exact definitions. (§4.)
6. **Personalization** — data layer on `BAR`, blaugrana branding, 15 s counterpress window, Wyscout role weights. (§5.)
7. **Architecture** — the five-page Dash app, callback model, PDF route. (§6–8.)
8. **The data pipeline** — scrape → download → transform, two-phase design, 31 teams / 21 comps, 250-column tables. (§9–10.)
9. **The event schema** — what Opta gives us and the qualifier conventions. (§11.)
10. **The ML edge** — xG (3 XGBoost models, monotone constraints, SHAP) and xT (16×12 Bellman grid). One algorithm slide each. (§14.)
11. **Walkthrough: Match Report** — the automated post-match deliverable, the 7 sections, the PDF. (§16.)
12. **Walkthrough: Barça DNA** — player identity, the Wyscout-weighted radar. (§17.)
13. **Walkthrough: Barça IQ** — the Game Model Radar, are we true to our model? (§18.)
14. **Walkthrough: Opposition Analysis** — rival scouting on the same axes. (§19.)
15. **Answering the coach** — the question→tab→metric mapping table. (§20.)
16. **Engineering quality** — caching, atomic writes, incremental pipeline, CI, tests. (§8–10, §21.)
17. **Limitations & roadmap** — xT carry limitation, PPDA dual definition, planned Bayesian opponent-tendency model. (§14, §23.)
18. **Close** — what this demonstrates about working in the football-data industry: domain fluency + production engineering + bespoke club personalization.

---

## 23. Known Gotchas & Data Caveats

- **`'Ball recovery'` lowercase r** — `events['event_type'] == 'Ball recovery'`.
- **`'Team setp up'` typo** is intentional and consistent across `mappings/opta_event_types.csv` and `matchevent_transformer.py`. Fix both or neither.
- **No coordinate flipping** — Opta normalises per-team; both teams attack left→right. Never apply `100 − x`.
- **Own goals** — the `own goal` qualifier is always `'N/A'`; identify by team-code mismatch on a Goal event.
- **`'Si'` / `'N/A'`** — boolean qualifiers are strings, not Python booleans.
- **`event_type_id` vs `type_id`** — Barcelona parquets use `event_type_id`; the opposition module renames it to `type_id` on load. Use `type_id` in opposition tabs only.
- **Filter by `team_code`, never `team_name`** — Opta's stored names differ from display names. Use `get_team_codes(name)` + `df['team_code'].isin(codes)`.
- **Two caches** — clear both `clear_events_cache()` and `clear_opp_events_cache()` after a pipeline run (app.py does this). Page reloads don't clear them.
- **Two PPDA definitions** — Match Report uses a whole-pitch ratio; the season views use the high-press (opponent-territory) definition. Know which is on screen.
- **xT under-credits carriers** — no ball-carry events in Opta.
- **xT retraining glob is stale** — `train.py` points at the legacy `data/barcelona/result/**` & `data/opposition/**` paths, not the current `data/2025-26/**` layout (§14.2).
- **PSG code** — `PSG` only; do **not** add `PAR` (that's Paris FC).
- **Opposition registry is disk-discovered** (≈ 212 teams), not config-driven; `config.yaml` only overrides code/country/search-name.
- **`SHOT_TYPES` / `DEF_ACTION_TYPES`** — import from `page_utils/event_filters.py`. There is no `'Blocked Shot'` event type; `'Ball recovery'` is lowercase-r.

---

*CuléVision — academic project, Masters in Sports Analytics, Escuela Universitaria Real Madrid · Universidad Europea. Author: Rishiraj Sinharay.*
