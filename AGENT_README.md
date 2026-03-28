# CuléVision — Agent Onboarding Guide

This file is the single source of truth for any AI agent working on this codebase.
Read it in full before making any changes.

---

## 1. Project Overview

**CuléVision** is an FC Barcelona tactical analytics dashboard built with Python Dash.
It ingests Opta event-level football data via a custom scraping pipeline and presents
interactive visualisations across four analysis pages:

| Page | URL | Purpose |
|---|---|---|
| Home | `/` | Season overview, recent results, tournament cards |
| Match Analysis | `/match-analysis` | Per-match deep-dive (7 tabs) |
| Player Analysis | `/player-analysis` | Individual player profile & radar |
| Team Analysis | `/team-analysis` | Season-level tactical dashboard (6 tabs) |
| Opposition Analysis | `/opposition-analysis` | Opponent scouting across multiple seasons |

**Tech stack:** Python 3.12+, Dash, Dash Bootstrap Components, Plotly, mplsoccer,
pandas, matplotlib, scikit-learn, Selenium / Selenium Wire.

App entry point: `app.py` — starts on `http://0.0.0.0:8050`.

---

## 2. Repository Structure

```
project_root/
├── app.py                        # Dash app factory, login, pipeline overlay
├── AGENT_README.md               # ← this file
├── STYLING.md                    # CSS / design-system reference
├── requirements.txt
│
├── pages/                        # Page layout + callback modules
│   ├── home.py
│   ├── match_analysis.py         # Calendar selector, score headline
│   ├── team_analysis.py          # Competition/match filters, tab routing
│   ├── player_analysis.py        # Player profile, heatmaps, radar
│   ├── opposition_analysis.py    # Opponent selector, global filters
│   │
│   ├── match_analysis_tabs/      # 7 tab modules + shared utilities
│   │   ├── shared.py             # Shared UI components (headers, stat cards)
│   │   ├── overview.py           # Lineup, average positions, stat bars
│   │   ├── attacking_output.py   # Shot maps, xG
│   │   ├── build_up_passing.py   # Pass network, zone entries
│   │   ├── defensive_structure.py
│   │   ├── transitions_counterpressing.py
│   │   ├── goalkeeping.py
│   │   └── player_stats.py
│   │
│   ├── team_analysis_tabs/       # 6 tab modules
│   │   ├── overview.py, buildup.py, chance_creation.py
│   │   ├── def_structure.py, transitions.py, set_pieces.py
│   │
│   └── opposition_analysis_tabs/ # 6 tab modules + helpers.py
│       ├── helpers.py            # Minimal shared helpers for opp tabs
│       ├── scouting.py, in_possession.py, defence.py
│       ├── transitions.py, set_pieces.py, exploit.py
│
├── page_utils/                   # Shared pure-Python utilities for all page/tab modules
│   ├── __init__.py
│   ├── pitch_zones.py            # Zone/half detection, penalty-box check
│   ├── possession_utils.py       # Possession annotation, turnover detection
│   ├── time_utils.py             # Time arithmetic, rolling windows
│   ├── competitions.py           # ALL_COMPETITIONS, COMP_SHORT, normalize_competitions()
│   ├── event_filters.py          # SHOT_TYPES, DEF_ACTION_TYPES/COLORS, filter_by_period()
│   └── visualizations.py         # Unified Plotly/mplsoccer plot configs & tools
│
├── utils/                        # App-level utilities
│   ├── config.py                 # COLORS, APP_CONFIG, NAV_LINKS
│   ├── data_utils.py             # All data loading functions (main API)
│   ├── logos.py                  # Team/tournament logo path helpers
│   ├── match_data_adapter.py     # get_match_metadata(), compute_team_kpis()
│   ├── opposition_data_utils.py  # Opposition-specific data loading
│   ├── player_analysis.py        # compute_player_stats(), compute_5d_scores()
│   ├── xg_utils.py               # add_xg_column()
│   └── pdf_report.py             # Match PDF generation (Flask route)
│
├── opta_pipeline/                # Data download pipeline (Barcelona matches only)
│   ├── main.py                   # Multi-competition orchestrator
│   ├── config.yaml               # 4 competitions configured
│   └── modules/
│       ├── scraper.py            # Scoresway HTML scraper (Selenium)
│       ├── downloader.py         # Opta JSON downloader (Selenium Wire)
│       └── transformers/         # JSON → Parquet transformers
│           ├── base_transformer.py
│           ├── match_transformer.py
│           ├── matchevent_transformer.py
│           └── lineup_transformer.py
│
├── opposition_pipeline/          # Separate pipeline for scouting opponent data
│
├── data/barcelona/result/        # All processed Parquet data
│   ├── Spain_Primera_Division/
│   ├── UEFA_Champions_League/
│   ├── Spain_Copa_del_Rey/
│   └── Spain_Super_Cup/
│       └── {season}/             # e.g. 2025-2026
│           ├── match/            # One parquet per match (metadata)
│           ├── match_event/      # One parquet per match (all events, ~250 cols)
│           └── lineup/           # One parquet per match (starting XI + subs)
│
├── mappings/
│   ├── opta_event_types.csv      # Event type ID ↔ name reference
│   └── opta_qualifier_types.csv  # Qualifier ID ↔ name reference
│
├── assets/                       # Static files (CSS, logos, player images)
│   ├── logos/team/               # SVG team crests
│   ├── logos/tournament/         # SVG tournament logos
│   └── players/                  # Player images (jersey-number prefix)
│
├── xg_model/                     # Trained xG model files
└── tests/                        # pytest unit tests
```

---

## 3. Data Structure

### 3.1 Competitions & Folder Mapping

```python
# utils/data_utils.py
COMPETITIONS = {
    'laliga':   'Spain_Primera_Division',
    'ucl':      'UEFA_Champions_League',
    'copa':     'Spain_Copa_del_Rey',
    'supercup': 'Spain_Super_Cup',
}
COMPETITION_NAMES = {
    'Spain_Primera_Division': 'La Liga',
    'UEFA_Champions_League':  'Champions League',
    'Spain_Copa_del_Rey':     'Copa del Rey',
    'Spain_Super_Cup':        'Spanish Super Cup',
}
CURRENT_SEASON = '2025-2026'
DATA_PATH = project_root / "data" / "barcelona" / "result"
```

### 3.2 Match Event Parquet Schema

Each `match_event/*.parquet` file has **~250 columns**. The key columns used throughout the codebase:

| Column | Type | Description |
|---|---|---|
| `match_id` | str | Unique match identifier |
| `match_date` | str | YYYY-MM-DD |
| `match_description` | str | "Home vs Away" |
| `home_team` | str | Home team full name |
| `away_team` | str | Away team full name |
| `competition` | str | Friendly name (added by loader, e.g. `'La Liga'`) |
| `event_id` | int | Unique event row ID |
| `event_type` | str | Human-readable type (see Section 4) |
| `event_type_id` | int | Opta numeric type ID |
| `period_id` | int | 1=H1, 2=H2, 3=ET1, 4=ET2, 5/6=shootout, 16=team setup |
| `time_min` | int | Minute within the period |
| `time_sec` | int | Second within the minute |
| `team_name` | str | Full team name of the performing team |
| `team_code` | str | 3-letter code (Barcelona = `'BAR'`) |
| `team_position` | str | `'home'` or `'away'` |
| `player_id` | str | Opta player ID |
| `player_name` | str | Player full name |
| `x` | float | Event x-coordinate (0–100, see Section 5) |
| `y` | float | Event y-coordinate (0–100, see Section 5) |
| `outcome` | int | `1` = successful, `0` = unsuccessful |
| `own goal` | str | `'Si'` if own goal, else `'N/A'` |
| `Pass End X` | float | End x of a pass |
| `Pass End Y` | float | End y of a pass |
| `Goal Mouth Y Coordinate` | float | Shot goal-mouth y (for GK viz) |
| `Goal Mouth Z Coordinate` | float | Shot goal-mouth z height (for GK viz) |

Qualifier columns (e.g. `Long ball`, `Cross`, `Head`, `Penalty`, `Yellow Card`, `Assist`, etc.)
contain `'Si'` if the qualifier applies, `'N/A'` otherwise. Numeric qualifiers (e.g. jersey number,
formation slot) contain the value as a string.

### 3.3 Lineup Parquet Schema

`lineup/*.parquet` — one row per player per match:

| Column | Description |
|---|---|
| `match_id` | Match identifier |
| `team_position` | `'home'` or `'away'` |
| `formation` | E.g. `'4231'` |
| `player_name` | Full name |
| `jersey_number` | Integer |
| `formation_slot` | 1–11 (starters) or 0 (sub) |
| `role` | `'Start'` or `'Sub'` |
| `position` | Opta position code (GK, CB, LB, CM, …) |
| `is_captain` | bool |
| `sub_on_minute` | int or None |

### 3.4 Data Loading API (`utils/data_utils.py`)

All page code should load data via these functions — never read parquet directly.

```python
from utils.data_utils import (
    get_all_events(season)          # → DataFrame, all events, in-process cached
    get_match_events(match_id)      # → DataFrame, single match events
    get_match_results()             # → list[dict] with match metadata + scores
    get_match_lineup(match_id)      # → DataFrame
    get_all_barcelona_players()     # → list[str]
    get_player_events(player_name)  # → DataFrame
    get_team_events(team_name)      # → DataFrame
    get_match_stats(match_id)       # → dict {home: {...}, away: {...}}
    get_season_summary()            # → dict with W/D/L/GF/GA
    get_tournament_summary()        # → dict keyed by competition name
    clear_events_cache()            # Call after pipeline writes new files
    CURRENT_SEASON                  # '2025-2026'
)
```

Key caching note: `get_all_events()` caches results in-process (`_events_cache` dict).
After the pipeline writes new parquet files, call `clear_events_cache()` before reloading.

---

## 4. Opta Event Types

The most commonly used `event_type` values (from `mappings/opta_event_types.csv`):

| event_type | ID | Notes |
|---|---|---|
| `Pass` | 1 | Includes free kicks, corners, throw-ins, goal kicks |
| `Offside Pass` | 2 | Pass to an offside player |
| `Take On` | 3 | Attempted dribble |
| `Foul` | 4 | Foul committed (neutral, does not change possession) |
| `Out` | 5 | Ball out of play |
| `Corner Awarded` | 6 | Ball went out for a corner |
| `Tackle` | 7 | outcome=1: win+retain / outcome=0: win tackle not possession |
| `Interception` | 8 | Intercepts a pass |
| `Save` | 10 | GK save |
| `Claim` | 11 | GK catches a cross |
| `Clearance` | 12 | Defensive clearance |
| `Miss` | 13 | Shot wide or over |
| `Post` | 14 | Ball hits the post |
| `Saved Shot` | 15 | Shot on target, saved |
| `Goal` | 16 | Goal scored (check `own goal == 'Si'` for own goals) |
| `Card` | 17 | Booking (check `Yellow Card`, `Red Card`, `Second yellow` qualifiers) |
| `Player Off` | 18 | Substitution off |
| `Player on` | 19 | Substitution on |
| `End` | 30 | End of a period |
| `Start` | 32 | Start of a period |
| `Team setp up` | 34 | **Typo is intentional** — matches both the CSV and the transformer code |
| `Aerial` | 44 | Aerial duel |
| `Challenge` | 45 | Player fails to win a dribble |
| `Ball Recovery` | 49 | Team wins possession and keeps it ≥2 passes |
| `Blocked Shot` | — | Shot blocked by a defender |
| `Keeper pick-up` | — | GK picks up the ball |
| `Goal kick` | — | Goal kick (tagged as Pass with `Goal Kick` qualifier) |

**Critical typo:** `"Team setp up"` (not `"Team set up"`) appears in **both**
`mappings/opta_event_types.csv` AND `opta_pipeline/modules/transformers/matchevent_transformer.py:156`.
They are consistent — the code works. Do NOT fix one without fixing both.

### Period IDs

```
1  = First half
2  = Second half
3  = Extra time first half
4  = Extra time second half
5  = Penalty shootout
6  = Penalty shootout continuation
16 = Team setup (pre-match lineup events — always filter these out)
```

---

## 5. Coordinate System

**Opta uses a 0–100 scale for both x and y, already normalised per-team.**

```
x = 0   → own goal line      (defending)
x = 100 → opponent goal line (attacking)
y = 0   → top touchline
y = 100 → bottom touchline
```

**This applies to BOTH home and away teams.** Opta normalises so that each team
always attacks toward x=100. **Never apply a `100 - x` flip for the away team.**

### Key Zone Boundaries

| Zone | x range |
|---|---|
| Defensive Third | 0 – 33.3 |
| Middle Third | 33.3 – 66.7 |
| Final Third | 66.7 – 100 |
| Attacking Penalty Box | x ≥ 83, y ∈ [21.1, 78.9] |
| Zone 14 (central attack) | x ∈ [66.7, 83], y ∈ [37, 63] |
| Half Spaces | y ∈ [21–37] or [63–79] |

These constants are defined in `page_utils/pitch_zones.py`.

---

## 6. page_utils — Shared Utilities

All page and tab modules should import shared utilities from `page_utils/`.
**Never redefine these locally.**

### 6.1 `page_utils/competitions.py`

```python
from page_utils.competitions import (
    ALL_COMPETITIONS,          # list[dict] for dcc.Dropdown — 4 competitions
    COMP_SHORT,                # dict: 'La Liga' → 'Liga', 'Champions League' → 'UCL', etc.
    normalize_competitions,    # (competition_value) → list[str] | None
    build_match_selector_options,  # (results, competitions=None) → list[dict]
)
```

- `normalize_competitions(None)` → `None` (all competitions)
- `normalize_competitions('all')` → `None`
- `normalize_competitions('La Liga')` → `['La Liga']`
- `build_match_selector_options()` builds sorted-newest-first dropdown options with
  competition tags when multiple competitions are in scope.

### 6.2 `page_utils/event_filters.py`

```python
from page_utils.event_filters import (
    SHOT_TYPES,             # frozenset: {'Miss','Saved Shot','Goal','Post','Blocked Shot'}
    DEF_ACTION_TYPES,       # frozenset: {'Tackle','Interception','Ball Recovery','Clearance','Blocked Shot'}
    DEF_COLORS,             # dict: event_type → hex colour (for scatter plots)
    SHOT_OUTCOME_COLOR,     # dict: outcome → hex (attacking perspective: Goal=green, Miss=red)
    SHOT_OUTCOME_SYMBOL,    # dict: outcome → Plotly symbol name
    filter_by_period,       # (events_df, period: int|None) → DataFrame
    split_by_halves,        # (events_df) → (full_df, h1_df, h2_df)
)
```

`filter_by_period(events, None)` returns the full DataFrame unchanged.
`split_by_halves` is safe even if `period_id` is absent (returns empty frames for halves).

Note: `goalkeeping.py` uses its own `_OUTCOME_COLOR` with GK-perspective colours
(Goal = red/bad, Saved = green/good) — do not replace those with `SHOT_OUTCOME_COLOR`.

### 6.3 `page_utils/pitch_zones.py`

```python
from page_utils.pitch_zones import (
    PitchZone,          # Enum: DEFENSIVE_THIRD, MIDDLE_THIRD, FINAL_THIRD, UNKNOWN
    PitchHalf,          # Enum: OWN_HALF, OPPONENT_HALF
    ZoneBoundaries,     # dataclass with defensive_end=33.3, middle_end=66.7
    get_zone,           # (x, boundaries=default) → PitchZone
    get_half,           # (x) → PitchHalf
    is_in_penalty_box,  # (x, y) → bool
    zone_from_series,   # (x_series) → PitchZone (uses mean x)
    pitch_third_label,  # (PitchZone) → str
)
```

### 6.4 `page_utils/possession_utils.py`

```python
from page_utils.possession_utils import (
    POSSESSION_TAKING_EVENT_TYPES,   # frozenset — events that always hand possession
    CONDITIONAL_POSSESSION_TAKING,   # frozenset — only on outcome==1
    CONTESTED_EVENT_TYPES,           # frozenset — aerials, 50/50
    NEUTRAL_EVENT_TYPES,             # frozenset — fouls, cards, admin (forward-fill through)
    IGNORE_PERIOD_IDS,               # {16, 5, 6} — non-play periods
    annotate_possession,             # (events_df) → annotated DataFrame
    compute_absolute_time,           # (row) → int (seconds from kick-off)
    compute_vertical_speed,          # (events_subset) → float
    detect_turnovers,                # (events_df, focus_team) → DataFrame
)
```

`annotate_possession()` adds columns: `abs_time_sec`, `possession_team`, `is_contested`.
It also strips non-play periods and sorts chronologically.

### 6.5 `page_utils/time_utils.py`

```python
from page_utils.time_utils import (
    to_seconds,              # (time_min, time_sec) → int
    format_seconds,          # (total_seconds) → 'MM:SS'
    time_diff_seconds,       # (row_a, row_b) → float (requires abs_time_sec)
    events_within_window,    # (events_df, anchor_time, window_secs, direction) → DataFrame
    rolling_event_windows,   # (events_df, window_size, step=1) → list[DataFrame]
    compute_match_duration,  # (events_df) → int seconds
)
```

---

## 7. pages/match_analysis_tabs/shared.py — UI & Pitch Components

This is the most-imported file in the project. All visual building blocks live here.
Import path: `from pages.match_analysis_tabs.shared import ...` (or `.shared import ...`
inside the same package).

### 7.1 Theme Constants

```python
HOME_COLOR = '#004D98'   # Barcelona blue
AWAY_COLOR = '#A50044'   # Garnet/red
GOLD       = '#EDBB00'   # Gold accent

CHART_LAYOUT_DEFAULTS   # dict — base Plotly layout (transparent bg, gold font, etc.)
CHART_CONFIG            # {'displayModeBar': False}
CARD_STYLE              # dict — dark secondary card CSS
HALF_BTN_ACTIVE         # dict — gold button style
HALF_BTN_IDLE           # dict — muted button style
```

### 7.2 Pitch Background Functions

mplsoccer pitches are generated once and cached as base64 PNGs.

```python
add_pitch_background(fig, half=False)         # Full or half horizontal pitch
add_vertical_pitch_background(fig)            # Vertical full pitch
add_vertical_half_pitch_background(fig)       # Vertical attacking half only

# Matching axis ranges for each background:
PITCH_AXIS_FULL   # xaxis [-5,105], yaxis [-2,102]
PITCH_AXIS_HALF   # xaxis [48,105], yaxis [-2,102]
VPITCH_AXIS       # xaxis [-2,102], yaxis [-5,105]
VPITCH_AXIS_HALF  # xaxis [-2,102], yaxis [48,105]
```

**Usage pattern:**

```python
fig = go.Figure()
add_pitch_background(fig)
fig.update_layout(**PITCH_AXIS_FULL, **layout_config(height=400))
```

### 7.3 Heatmap Image Utilities

Both return a `data:image/png;base64,...` URI for use in `html.Img(src=...)`.

```python
render_heatmap_img(x_vals, y_vals, cmap='YlOrRd', fallback_color=None, half=False)
# → KDE heatmap; falls back to scatter dots if < 5 points

render_lsc_heatmap_img(x_vals, y_vals, color_hex, half=False, show_zone_pcts=False)
# → Team-coloured LinearSegmentedColormap heatmap with marginal distributions
#   and optional zone percentage labels
```

### 7.4 Pass Map Image Utility

```python
render_pass_map_img(x_start, y_start, x_end, y_end, outcomes=None)
# → base64 PNG URI; successful passes in blue, unsuccessful in red
```

### 7.5 Reusable UI Components

```python
page_header(title)                    # dbc.Row with Barça crest + title
section_header(title, subtitle='')    # Gold h5 + HR divider
section_card(title, children)         # dbc.Card with gold header
stat_card(value, label, color=None)   # Compact KPI card
kpi_row(kpis, columns, colors=None)   # Row of stat_cards
build_legend_box(items)               # Coloured symbol + label list
build_info_box(text)                  # ℹ info callout
build_team_stats_table(team_name, color, metrics, full, h1, h2)
# Single-team table with Full / 1st Half / 2nd Half columns
empty_fig(message)                    # Placeholder figure
layout_config(**overrides)            # Merge overrides onto base chart layout
```

---

## 8. Own Goal Handling

Own goals in Opta are attributed to the player who scored them (the player of the
team that conceded). The `own goal` qualifier column is `'Si'` for own goals.

```python
from utils.data_utils import is_own_goal, filter_own_goals, exclude_own_goals

# is_own_goal(row) → bool
# filter_own_goals(goals_df)   — remove own goals from a goals-only DataFrame
# exclude_own_goals(events_df) — remove own-goal Goal rows from any event DataFrame
```

Always call `exclude_own_goals()` before building shot maps or attacker stats.
Use `filter_own_goals()` when counting a player's "real" goals.
Use `count_goals(goals_df)` (in data_utils) for own-goal-aware home/away goal counts.

---

## 9. Data Pipeline

### Flow

```
"Update Databases" button
       ↓
app.py spawns subprocess → opta_pipeline/main.py
       ↓
main.py iterates 4 competitions → scraper.py → downloader.py → transformers/
       ↓
Writes Parquet files to data/barcelona/result/
       ↓
Writes progress.json for overlay updates (polled every 2s)
       ↓
On completion, app.py calls clear_events_cache() + triggers page reload
```

### Key pipeline notes

- `downloader.py` has JSON validation before save + retry logic (3 attempts).
- `main.py` cleans stale `progress.json` on startup.
- `app.py` prevents double-start if pipeline is already running.
- The opposition pipeline (`opposition_pipeline/`) is separate and triggered differently.

---

## 10. App Architecture

### Page Registration

Pages are registered in `app.py`. Each page module exports:
- `create_<page>_layout()` — returns the Dash layout tree
- `register_<page>_callbacks(app)` — registers all Dash callbacks

### Callback Conventions

- Match-level callbacks use prefix `pma-` (match analysis).
- Team-level callbacks use prefix `ta-`.
- Player-level callbacks use prefix `pa-`.
- Opposition callbacks use prefix `oa-`.

### Tab Dispatch Pattern

All multi-tab pages use a dispatch dict:

```python
dispatch = {
    'tab-id': build_tab_function,
    ...
}
builder = dispatch.get(active_tab)
if builder:
    return builder(**kwargs)
```

### Match Selector (Team/Player Analysis)

Both `team_analysis.py` and `player_analysis.py` drive a cascading selector:
1. Competition dropdown → filters match list
2. Match dropdown → multi-select for filtering aggregations

Use `page_utils.competitions.normalize_competitions()` to normalise the dropdown
value and `build_match_selector_options()` to build the options list.

---

## 11. UI / Design System

Colours live in `utils/config.py → COLORS`. Always import from there.

```python
COLORS = {
    'primary_blue':   '#004D98',   # HOME_COLOR
    'garnet':         '#A50044',   # AWAY_COLOR
    'gold':           '#EDBB00',   # GOLD — primary accent
    'dark_bg':        '#0A0E27',   # Main background
    'dark_secondary': '#151932',   # Card / panel backgrounds
    'dark_tertiary':  '#1E2139',   # Active tab, hover states
    'dark_border':    '#2A2F4A',   # All borders
    'text_primary':   '#E8E9ED',
    'text_secondary': '#A5A8B8',
}
```

See `STYLING.md` for CSS classes (`culevision-dropdown`, `culevision-legend-box`, etc.).

---

## 12. Pitch Visualisation Rules

1. **Always use `pitch.scatter()` not `mpatches.Circle`** — patches stretch with axis aspect ratio.
2. **Never flip away team coordinates** — Opta data is already per-team normalised.
3. **Never apply `100 - x`** transforms to any coordinate.
4. **Attack direction is always left → right** in all pitch plots.
5. `_add_attack_direction()` in `overview.py` always draws a right-pointing arrow (no branching).
6. When adding a new interactive pitch plot (Plotly), use:
   - `add_pitch_background(fig)` + `PITCH_AXIS_FULL` for full pitch
   - `add_vertical_half_pitch_background(fig)` + `VPITCH_AXIS_HALF` for shot maps
7. For static (mplsoccer) heatmaps use `render_heatmap_img()` or `render_lsc_heatmap_img()`.

---

## 13. Known Quirks & Gotchas

| Issue | Detail |
|---|---|
| `"Team setp up"` typo | In both `opta_event_types.csv` AND `matchevent_transformer.py:156`. Do not fix one without the other. |
| `period_id == 16` | Team-setup events. Always exclude from analysis. `IGNORE_PERIOD_IDS = {16, 5, 6}`. |
| Own goals | Attributed to the scoring team in Opta. Always call `exclude_own_goals()` for shot/attack data. |
| Events cache | `get_all_events()` caches in-process. After pipeline runs, call `clear_events_cache()`. |
| `dcc.Location refresh=True` | Auto-reload mechanism after pipeline completes — this does NOT restart the Python process, so manual cache clearing is required. |
| Formation mappings | `_COORDS` dict in `match_analysis_tabs/overview.py` maps `(formation, slot) → (x, y)`. Formations 3142, 4132, 4312 are supported. |
| GK outcome colours | `goalkeeping.py` uses inverted colours (Goal=red, Save=green). Do not replace with `SHOT_OUTCOME_COLOR` from `page_utils.event_filters`. |
| `'Si'` qualifier values | All Opta qualifier presence flags use the string `'Si'` (Spanish for "yes"), not `True` or `1`. |
| `outcome` column | Integer `1` = success, `0` = failure. Not a boolean. |

---

## 14. Adding New Features — Checklist

When adding a new visualisation or tab:

- [ ] Import shared pitch utils from `pages/match_analysis_tabs/shared.py`
- [ ] Import competition constants from `page_utils/competitions.py`
- [ ] Import event type sets from `page_utils/event_filters.py`
- [ ] Use `filter_by_period()` / `split_by_halves()` for half filtering
- [ ] Never define a local copy of `_COMP_SHORT`, `_ALL_COMPETITIONS`, `_SHOT_TYPES`, `_DEF_ACTION_TYPES`, or `_DEF_COLORS`
- [ ] Call `exclude_own_goals()` before any shot/goal analysis
- [ ] Do NOT flip coordinates for the away team
- [ ] Use `CHART_CONFIG = {'displayModeBar': False}` on all Plotly graphs
- [ ] Wrap new chart sections in `section_card(title, children)` or `section_header(title)`
- [ ] Register any new callbacks in the page's `register_*_callbacks(app)` function

---

## 15. Testing

Tests live in `tests/`. Run with `pytest` from the project root.

Existing test file: `tests/test_phase_classifier.py`
- `TestPitchZones` — tests `page_utils.pitch_zones`
- `TestPossessionUtils` — tests `page_utils.possession_utils`
- `TestTimeUtils` — tests `page_utils.time_utils`
