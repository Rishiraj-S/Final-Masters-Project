# ⚽ Opta Match Data Pipeline

A comprehensive Python pipeline for scraping, downloading, and transforming Opta football match data from Scoresway into analysis-ready Parquet files.

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

---

## 📋 Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Architecture](#architecture)
- [Installation](#installation)
- [Configuration](#configuration)
- [Usage](#usage)
- [Data Structure](#data-structure)
- [Output Files](#output-files)
- [Troubleshooting](#troubleshooting)
- [Technical Details](#technical-details)

---

## 🎯 Overview

This pipeline automates the complete workflow for collecting and processing Opta football match data:

1. **Scrapes** match URLs from Scoresway competition pages
2. **Downloads** raw JSON data by intercepting PerformFeeds API calls
3. **Transforms** JSON into structured Parquet files with comprehensive event-level and match-level data

Built for **FC Barcelona La Liga 2025-2026** analysis, but easily configurable for any team/league on Scoresway.

---

## ✨ Features

### Data Collection
- ✅ **Automated Scraping**: Selenium-based scraping of match URLs
- ✅ **API Interception**: Captures Opta API responses via Selenium Wire
- ✅ **Smart Downloading**: Skips already downloaded matches
- ✅ **Multi-Endpoint Support**: Captures both `match` and `matchevent` data

### Data Processing
- ✅ **Event-Level Data**: Complete event-by-event match data with 200+ attributes
- ✅ **Match Metadata**: Basic match information (teams, scores, venue, etc.)
- ✅ **Formation Analysis**: Player positions and team formations
- ✅ **Qualifier Mapping**: All Opta qualifiers mapped to human-readable names
- ✅ **Parquet Output**: Efficient columnar storage with Snappy compression

### Flexibility
- ✅ **Configurable Naming**: Customizable filename patterns
- ✅ **Incremental Updates**: Only downloads new matches
- ✅ **Transform-Only Mode**: Re-process existing JSON files
- ✅ **Organized Structure**: League/Season hierarchy

---

## 🏗️ Architecture

```
┌─────────────────┐
│  Scoresway.com  │
└────────┬────────┘
         │ Scrape match URLs
         ▼
┌─────────────────┐
│  Match Scraper  │ ──► matches_urls.csv
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Match Downloader│ ──► Raw JSON files
│ (Selenium Wire) │     (match + matchevent)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Transformers   │ ──► Parquet files
│  - Match        │     (match/ + match_event/ + lineup/)
│  - Match Events │
│  - Lineup       │
└─────────────────┘
```

---

## 📦 Installation

### Prerequisites

- Python 3.11+
- Chrome/Chromium browser
- ChromeDriver (compatible with your Chrome version)

### Setup

```bash
# Clone the repository
git clone <your-repo-url>
cd opta_pipeline

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Dependencies

```
selenium==4.15.2
selenium-wire==5.1.0
pandas==2.1.3
pyarrow==14.0.1
beautifulsoup4==4.12.2
lxml==4.9.3
pyyaml==6.0.1
```

---

## ⚙️ Configuration

### Main Configuration File: `config.yaml`

```yaml
# Team Configuration
team:
  name: "Barcelona"
  results_url: "https://www.scoresway.com/en_GB/soccer/primera-división-2025-2026/YOUR_COMPETITION_ID/results"

# Competition Configuration
competition:
  id: "YOUR_COMPETITION_ID"
  league_name: "Spain_Primera_Division"
  season: "2025-2026"

# Downloader Settings
downloader:
  method: "selenium_wire"
  timeout_per_match: 45
  sleep_between_matches: 1.5
  skip_existing: true
  
  capture:
    matchevent: true      # Event-by-event data
    match: true           # Basic match information

# Output Configuration
output:
  format: "parquet"
  
  extract:
    match_info: true      # Extract basic match data
    match_events: true    # Extract event data
    
  # Filename pattern
  naming:
    pattern: "{date}_{home_code}_vs_{away_code}"
    include_match_id: "suffix"  # suffix, prefix, or none
    clean_names: true
    replace_spaces: "_"
```

### Available Naming Patterns

```yaml
# Date + Team Codes (Recommended)
pattern: "{date}_{home_code}_vs_{away_code}"
# Output: 2025-12-25_BAR_vs_RMA_abc123.parquet

# Full Team Names
pattern: "{home}_vs_{away}_{date}"
# Output: Barcelona_vs_Real_Madrid_2025-12-25_abc123.parquet

# Week-based
pattern: "week{week}_{date}_{home_code}_{away_code}"
# Output: week15_2025-12-25_BAR_vs_RMA_abc123.parquet

# Match ID Only (Simple)
pattern: "{match_id}"
# Output: abc123.parquet
```

---

## 🚀 Usage

### Full Pipeline

```bash
# Run complete pipeline (scrape → download → transform)
python main.py
```

### Incremental Updates

```bash
# Run again to get only new matches
python main.py

# Downloads will skip existing matches
# Transformations will re-process all (fast operation)
```

### Individual Steps

```bash
# Only scraping (get match URLs)
python main.py --skip-download

# Only downloading (skip scraping step)
python main.py --skip-scraping

# Only transforming (process existing JSONs)
python main.py --transform-only
```

---

## 📁 Data Structure

### Directory Layout

```
opta_pipeline/
├── config.yaml
├── main.py
├── modules/
│   ├── __init__.py
│   ├── scraper.py
│   ├── downloader.py
│   ├── utils.py
│   └── transformers/
│       ├── __init__.py
│       ├── base_transformer.py
│       ├── match_transformer.py
│       ├── matchevent_transformer.py
│       └── lineup_transformer.py
│
data/                                    # Lives at project root (../data/ from pipeline)
├── barcelona/
│   ├── target/                          # Raw JSON files
│   │   └── Spain_Primera_Division/
│   │       └── 2025-2026/
│   │           └── matchdata/           # Combined match + matchevent JSON
│   │               ├── match123.json
│   │               └── match456.json
│   │
│   └── result/                          # Processed Parquet files
│       └── Spain_Primera_Division/
│           └── 2025-2026/
│               ├── matches_urls.csv
│               ├── match/               # Match metadata
│               │   ├── 2025-12-25_BAR_vs_RMA_abc123.parquet
│               │   └── 2025-12-28_BAR_vs_ATM_def456.parquet
│               ├── match_event/         # Event-level data
│               │   ├── 2025-12-25_BAR_vs_RMA_abc123.parquet
│               │   └── 2025-12-28_BAR_vs_ATM_def456.parquet
│               └── lineup/              # Per-player lineup rows
│                   ├── 2025-12-25_BAR_vs_RMA_abc123.parquet
│                   └── 2025-12-28_BAR_vs_ATM_def456.parquet
│
logs/
└── pipeline.log
```

---

## 📊 Output Files

### 1. Match Info (`match/*.parquet`)

Basic match metadata and final results.

**Columns:**
- Match identifiers: `match_id`, `league`, `season`
- Match details: `date`, `time`, `week`, `description`
- Venue: `venue_id`, `venue_name`, `venue_short_name`
- Competition: `competition_id`, `competition_name`, `tournament_id`, `tournament_name`
- Teams: `home_team_id`, `home_team_name`, `home_team_code`, `home_score`
- Teams: `away_team_id`, `away_team_name`, `away_code`, `away_score`
- Technical: `period_length`, `number_of_periods`, `coverage_level`

**Example Usage:**
```python
import pandas as pd

# Read match info
match_info = pd.read_parquet('data/barcelona/result/Spain_Primera_Division/2025-2026/match/2025-12-25_BAR_vs_RMA_abc123.parquet')

print(f"Match: {match_info['home_team_name'].iloc[0]} vs {match_info['away_team_name'].iloc[0]}")
print(f"Score: {match_info['home_score'].iloc[0]} - {match_info['away_score'].iloc[0]}")
print(f"Date: {match_info['date'].iloc[0]}")
```

### 2. Match Events (`match_event/*.parquet`)

Comprehensive event-by-event data with 200+ columns.

**Core Columns:**
- Event identifiers: `event_id`, `event_type`, `event_type_id`
- Timing: `period_id`, `time_min`, `time_sec`, `timestamp`
- Location: `x`, `y` (coordinates on pitch)
- Actor: `player_id`, `player_name`, `team_name`
- Outcome: `outcome` (1 = success, 0 = failure)
- Formation: `formation`, `position`, `Team Formation`
- Context: All Opta qualifiers (100+ columns)

**Key Event Types:**
- Pass, Shot, Goal, Tackle, Interception
- Dribble, Cross, Corner, Free Kick
- Offside, Foul, Card, Substitution
- Formation Change, Team Setup

**Example Usage:**
```python
import pandas as pd

# Read match events
events = pd.read_parquet('data/barcelona/result/Spain_Primera_Division/2025-2026/match_event/2025-12-25_BAR_vs_RMA_abc123.parquet')

# Get all goals
goals = events[events['event_type'] == 'Goal']
print(f"Goals: {len(goals)}")
print(goals[['time_min', 'player_name', 'team_name']])

# Get successful passes
passes = events[(events['event_type'] == 'Pass') & (events['outcome'] == 1)]
print(f"\nTotal successful passes: {len(passes)}")

# Pass accuracy by team
pass_accuracy = events[events['event_type'] == 'Pass'].groupby('team_name').agg({
    'outcome': ['sum', 'count']
})
pass_accuracy['accuracy'] = (pass_accuracy[('outcome', 'sum')] / pass_accuracy[('outcome', 'count')] * 100).round(2)
print(f"\nPass Accuracy:\n{pass_accuracy}")

# Shot map data
shots = events[events['event_type'] == 'Shot']
shot_map = shots[['player_name', 'team_name', 'x', 'y', 'outcome', 'time_min']]
print(f"\nShot Map Data:\n{shot_map}")
```

### 3. Match URLs (`matches_urls.csv`)

List of all matches with URLs for reference.

**Columns:**
- `match_id`: Unique match identifier
- `url_match`: Scoresway match URL
- `team_name`: Team being tracked
- `date`: Match date (if available)

---

## 🔧 Advanced Usage

### Analyzing Multiple Matches

```python
import pandas as pd
import glob

# Load all match events
all_events = pd.concat([
    pd.read_parquet(f)
    for f in glob.glob('data/barcelona/result/Spain_Primera_Division/2025-2026/match_event/*.parquet')
], ignore_index=True)

print(f"Total events: {len(all_events):,}")
print(f"Total matches: {all_events['match_id'].nunique()}")
print(f"Date range: {all_events['match_date'].min()} to {all_events['match_date'].max()}")

# Team statistics across all matches
team_stats = all_events[all_events['team_name'] == 'Barcelona'].groupby('event_type').size().sort_values(ascending=False)
print(f"\nBarcelona Event Distribution:\n{team_stats.head(10)}")
```

### Player Analysis

```python
# Find top passers
passes = all_events[all_events['event_type'] == 'Pass']
top_passers = passes.groupby(['player_name', 'team_name']).agg({
    'outcome': ['sum', 'count']
}).reset_index()
top_passers.columns = ['player', 'team', 'successful', 'total']
top_passers['accuracy'] = (top_passers['successful'] / top_passers['total'] * 100).round(2)
top_passers = top_passers.sort_values('total', ascending=False).head(10)

print("Top 10 Passers:")
print(top_passers)
```

### Shot Analysis

```python
# Shot locations and outcomes
shots = all_events[all_events['event_type'] == 'Shot']

import matplotlib.pyplot as plt

fig, ax = plt.subplots(figsize=(12, 8))

# Plot shots
for team in shots['team_name'].unique():
    team_shots = shots[shots['team_name'] == team]
    
    # Successful shots
    successful = team_shots[team_shots['outcome'] == 1]
    ax.scatter(successful['x'], successful['y'], s=100, alpha=0.6, label=f'{team} (On Target)')
    
    # Unsuccessful shots
    unsuccessful = team_shots[team_shots['outcome'] == 0]
    ax.scatter(unsuccessful['x'], unsuccessful['y'], s=100, alpha=0.3, marker='x')

ax.set_xlabel('X Coordinate')
ax.set_ylabel('Y Coordinate')
ax.set_title('Shot Map')
ax.legend()
plt.show()
```

---

## 🐛 Troubleshooting

### Common Issues

#### 1. ChromeDriver Not Found

**Error:** `selenium.common.exceptions.WebDriverException: 'chromedriver' executable needs to be in PATH`

**Solution:**
```bash
# macOS (using Homebrew)
brew install chromedriver

# Or download from: https://chromedriver.chromium.org/
# Then add to PATH or place in project directory
```

#### 2. No Matches Scraped

**Error:** Empty `matches_urls.csv`

**Solutions:**
- Check the `results_url` in `config.yaml` is correct
- Verify the page loads correctly in a normal browser
- Check logs for Selenium errors
- Try increasing `timeout_seconds` in config

#### 3. Download Timeout

**Error:** `Download failed: timeout`

**Solutions:**
- Increase `timeout_per_match` in config (try 60 seconds)
- Check internet connection
- Verify Scoresway is accessible
- Some matches may not have complete data

#### 4. Transformation Fails

**Error:** `Failed to extract team codes`

**Solutions:**
- Check JSON structure with: `cat data/target/.../match/xxx.json`
- Verify JSON is valid (not truncated)
- Re-download the match if JSON is corrupted

#### 5. Memory Issues

**Error:** `MemoryError` when processing many matches

**Solutions:**
- Process matches in batches
- Use `--transform-only` to avoid re-downloading
- Increase system RAM allocation

---

## 🔍 Technical Details

### Opta Event Types

The pipeline maps Opta's numeric event type IDs to human-readable names:

- **1**: Pass
- **2**: Offside
- **3**: Take On (Dribble)
- **4**: Foul
- **5**: Out
- **10**: Save
- **13**: Tackle
- **14**: Interception
- **15**: Shot
- **16**: Goal
- **32**: Formation Setup
- And 50+ more...

Full mapping: `mappings/opta_event_types.csv`

### Opta Qualifiers

Qualifiers provide additional context for events. Examples:

- **Pass Type**: Ground, High, Cross, Through Ball
- **Shot Type**: Right Foot, Left Foot, Head
- **Body Part**: Foot, Head, Chest, Other
- **Zone**: Defensive Third, Middle Third, Attacking Third
- **Assist**: Whether pass led to goal

Full mapping: `mappings/opta_qualifier_types.csv`

### Coordinate System

- **X**: 0-100 (0 = own goal line, 100 = opponent goal line)
- **Y**: 0-100 (0 = left touchline, 100 = right touchline)
- Origin is relative to attacking direction

### Formations

Supported formations include:
- 442, 433, 4231, 352, 343, 532, and 20+ more
- Player positions mapped to: GK, CB, RB, LB, CDM, CM, CAM, RM, LM, RW, LW, CF, ST

---

## 📈 Performance

### Benchmarks (typical match)

- **Scraping**: ~5-10 seconds for full season
- **Downloading**: ~30-45 seconds per match
- **Transformation**: ~2-5 seconds per match

### File Sizes (typical match)

- **Raw JSON**: 
  - `match`: ~50 KB
  - `matchevent`: ~500 KB - 2 MB
- **Parquet output**:
  - `match_info`: ~5 KB
  - `match_events`: ~200 KB - 800 KB (with Snappy compression)

---

## 🤝 Contributing

### Adding Support for New Leagues

1. Update `config.yaml`:
   ```yaml
   competition:
     league_name: "Premier_League"
     season: "2025-2026"
   team:
     results_url: "https://www.scoresway.com/..."
   ```

2. Run pipeline:
   ```bash
   python main.py
   ```

### Adding New Data Types

To add support for additional Opta endpoints (e.g., `matchstats`, `squads`):

1. Update `config.yaml` capture settings
2. Add regex pattern in `modules/downloader.py`
3. Create new transformer in `modules/transformers/`
4. Update `modules/__init__.py` and `main.py`

---

## 📝 License

This project is licensed under the MIT License.

---

## ⚠️ Disclaimer

This tool is for educational and research purposes. Users are responsible for:
- Respecting Scoresway's Terms of Service
- Not overwhelming servers with excessive requests
- Using data in compliance with Opta's licensing terms
- Ensuring appropriate rate limiting

---

## 🙏 Acknowledgments

- **Opta Sports**: For comprehensive football data
- **Scoresway**: For providing accessible match interfaces
- **Selenium Wire**: For API interception capabilities

---

## 📞 Support

For issues, questions, or contributions:
- Open an issue on GitHub
- Check logs in `logs/` directory for detailed error messages
- Review configuration in `config.yaml`

---

**Built with ❤️ for football analytics**