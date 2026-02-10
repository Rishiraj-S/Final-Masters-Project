"""Data loader for Barcelona match data from Opta Parquet files."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

from barcelona_postmatch_app.config import (
    BARCELONA_CODES,
    BARCELONA_NAMES,
    DATA_BASE_PATH,
    FORMATION_MAP,
)
from barcelona_postmatch_app.utils.helpers import (
    is_barcelona,
    safe_float,
    qualifier_is_set,
)

# Resolve the data directory relative to this file's location
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = _PROJECT_ROOT / DATA_BASE_PATH


def load_available_matches() -> list[dict]:
    """Scan the data directory for all available Barcelona matches.

    Returns a list of dicts with keys:
        match_id, label, match_parquet, event_parquet, league, season, date
    sorted by date descending (most recent first).
    """
    matches = []

    if not DATA_DIR.exists():
        return matches

    for league_dir in sorted(DATA_DIR.iterdir()):
        if not league_dir.is_dir():
            continue
        league = league_dir.name

        for season_dir in sorted(league_dir.iterdir()):
            if not season_dir.is_dir():
                continue
            season = season_dir.name

            match_dir = season_dir / "match"
            event_dir = season_dir / "match_event"

            if not match_dir.exists() or not event_dir.exists():
                continue

            for match_pq in sorted(match_dir.glob("*.parquet")):
                try:
                    mdf = pd.read_parquet(match_pq)
                    if mdf.empty:
                        continue

                    row = mdf.iloc[0]
                    home_name = str(row.get("home_team_name", ""))
                    away_name = str(row.get("away_team_name", ""))
                    home_code = str(row.get("home_team_code", ""))
                    away_code = str(row.get("away_team_code", ""))

                    # Only include matches where Barcelona played
                    if not (is_barcelona(home_name, home_code) or
                            is_barcelona(away_name, away_code)):
                        continue

                    match_id = str(row.get("match_id", match_pq.stem))
                    date = str(row.get("date", ""))
                    description = str(row.get("description", f"{home_name} vs {away_name}"))

                    # Find corresponding event file
                    event_files = list(event_dir.glob(f"*{match_id}*"))
                    if not event_files:
                        # Try matching by date and teams
                        event_files = list(event_dir.glob(f"*{home_code}*{away_code}*"))
                    if not event_files:
                        event_files = list(event_dir.glob("*.parquet"))
                        event_files = [
                            f for f in event_files
                            if match_id in f.stem or (home_code in f.stem and away_code in f.stem)
                        ]

                    event_pq = event_files[0] if event_files else None

                    label = f"{date} | {description} ({league.replace('_', ' ')} {season})"

                    matches.append({
                        "match_id": match_id,
                        "label": label,
                        "match_parquet": str(match_pq),
                        "event_parquet": str(event_pq) if event_pq else None,
                        "league": league,
                        "season": season,
                        "date": date,
                        "description": description,
                        "home_team": home_name,
                        "away_team": away_name,
                    })
                except Exception:
                    continue

    # Sort by date descending
    matches.sort(key=lambda m: m["date"], reverse=True)
    return matches


def load_match_data(match_info: dict) -> tuple[pd.DataFrame, dict]:
    """Load and preprocess a single match's event data plus metadata.

    Args:
        match_info: dict from load_available_matches() with file paths

    Returns:
        events_df: Preprocessed DataFrame of match events
        metadata: dict with match-level information
    """
    match_pq = match_info["match_parquet"]
    event_pq = match_info.get("event_parquet")

    if not event_pq or not os.path.exists(event_pq):
        raise FileNotFoundError(f"Event data not found for match {match_info['match_id']}")

    # Load match metadata
    match_df = pd.read_parquet(match_pq)
    match_row = match_df.iloc[0]

    # Load event data
    events_df = pd.read_parquet(event_pq)

    # Build metadata dict
    metadata = _build_metadata(match_row, events_df)

    # Preprocess events
    events_df = _preprocess_events(events_df, metadata)

    return events_df, metadata


def _build_metadata(match_row: pd.Series, events_df: pd.DataFrame) -> dict:
    """Build match metadata dictionary from parquet data."""
    home_name = str(match_row.get("home_team_name", ""))
    away_name = str(match_row.get("away_team_name", ""))
    home_code = str(match_row.get("home_team_code", ""))
    away_code = str(match_row.get("away_team_code", ""))

    # Determine which team is Barcelona
    barca_is_home = is_barcelona(home_name, home_code)

    barca_team_name = home_name if barca_is_home else away_name
    opp_team_name = away_name if barca_is_home else home_name
    barca_code = home_code if barca_is_home else away_code
    opp_code = away_code if barca_is_home else home_code

    # Get team IDs from events
    barca_team_id = None
    opp_team_id = None
    for _, row in events_df.head(50).iterrows():
        tc = str(row.get("team_code", ""))
        cid = str(row.get("contestant_id", ""))
        if tc == barca_code and barca_team_id is None:
            barca_team_id = cid
        elif tc == opp_code and opp_team_id is None:
            opp_team_id = cid

    # Derive scores from Goal events
    goals = events_df[events_df["event_type_id"] == 16]
    home_goals = len(goals[goals["team_position"] == "home"])
    away_goals = len(goals[goals["team_position"] == "away"])

    # Check for own goals (qualifier 28 = "Own goal")
    for idx, g in goals.iterrows():
        if qualifier_is_set(g.get("Own Goal")):
            if g["team_position"] == "home":
                home_goals -= 1
                away_goals += 1
            else:
                away_goals -= 1
                home_goals += 1

    barca_score = home_goals if barca_is_home else away_goals
    opp_score = away_goals if barca_is_home else home_goals

    # Get formation from team_setup events
    setup_events = events_df[events_df["event_type_id"] == 34]
    barca_formation = "Unknown"
    for _, se in setup_events.iterrows():
        if str(se.get("team_code", "")) == barca_code:
            fm_val = str(se.get("Team Formation", "N/A"))
            if fm_val != "N/A":
                barca_formation = FORMATION_MAP.get(fm_val, fm_val)
            break

    # Extract lineup
    lineup = _extract_lineup(events_df, barca_code)

    return {
        "match_id": str(match_row.get("match_id", "")),
        "date": str(match_row.get("date", "")),
        "time": str(match_row.get("time", "")),
        "description": str(match_row.get("description", "")),
        "venue": str(match_row.get("venue_name", "")),
        "league": str(match_row.get("league", "")),
        "season": str(match_row.get("season", "")),
        "competition": str(match_row.get("competition_name", "")),
        "home_team": home_name,
        "away_team": away_name,
        "home_code": home_code,
        "away_code": away_code,
        "home_score": home_goals,
        "away_score": away_goals,
        "barca_team_name": barca_team_name,
        "barca_code": barca_code,
        "barca_team_id": barca_team_id,
        "opp_team_name": opp_team_name,
        "opp_code": opp_code,
        "opp_team_id": opp_team_id,
        "barca_is_home": barca_is_home,
        "barca_score": barca_score,
        "opp_score": opp_score,
        "barca_formation": barca_formation,
        "lineup": lineup,
    }


def _extract_lineup(events_df: pd.DataFrame, barca_code: str) -> list[dict]:
    """Extract Barcelona's starting lineup from team setup events."""
    lineup = []
    setup = events_df[
        (events_df["event_type_id"] == 34) &
        (events_df["team_code"] == barca_code)
    ]

    if setup.empty:
        return lineup

    # Get all events for Barcelona players in the first period for positions
    period1 = events_df[
        (events_df["period_id"] == 1) &
        (events_df["team_code"] == barca_code) &
        (events_df["player_id"].notna()) &
        (events_df["player_name"].notna())
    ]

    seen = set()
    for _, row in period1.iterrows():
        pid = str(row.get("player_id", ""))
        if pid in seen or pid == "" or pid == "nan":
            continue
        seen.add(pid)

        pos = str(row.get("position", "N/A"))
        jersey = str(row.get("Jersey Number", "N/A"))

        lineup.append({
            "player_id": pid,
            "player_name": str(row.get("player_name", "")),
            "position": pos if pos != "N/A" else "",
            "jersey_number": jersey if jersey != "N/A" else "",
        })

    return lineup


def _preprocess_events(events_df: pd.DataFrame, metadata: dict) -> pd.DataFrame:
    """Preprocess event DataFrame for analysis."""
    df = events_df.copy()

    # Convert coordinate columns to numeric
    df["x"] = pd.to_numeric(df["x"], errors="coerce")
    df["y"] = pd.to_numeric(df["y"], errors="coerce")

    # Parse pass end coordinates from qualifier columns
    df["x_end"] = df["Pass End X"].apply(safe_float)
    df["y_end"] = df["Pass End Y"].apply(safe_float)

    # Parse other numeric qualifiers
    df["pass_length"] = df["Length"].apply(safe_float)
    df["pass_angle"] = df["Angle"].apply(safe_float)

    # Add match minute (absolute)
    df["minute"] = df.apply(
        lambda r: r["time_min"] + (45 if r["period_id"] == 2 else 0), axis=1
    )

    # Add is_barcelona flag
    barca_code = metadata["barca_code"]
    df["is_barca"] = df["team_code"] == barca_code

    # Determine attacking direction for Barcelona
    # In Opta data, home team attacks from left to right in period 1
    # If Barcelona is home, they attack left->right (increasing x) in period 1
    # If Barcelona is away, they attack right->left (decreasing x) in period 1
    # Periods alternate direction
    barca_is_home = metadata["barca_is_home"]
    df["barca_attacks_right"] = df["period_id"].apply(
        lambda p: (barca_is_home and p in (1, 3)) or (not barca_is_home and p in (2, 4))
    )

    # Normalize coordinates so Barcelona always attacks left to right
    # This makes analysis consistent regardless of home/away
    df["x_norm"] = df.apply(
        lambda r: r["x"] if r["barca_attacks_right"] else (100.0 - r["x"])
        if r["is_barca"] else
        (100.0 - r["x"]) if r["barca_attacks_right"] else r["x"],
        axis=1,
    )
    df["y_norm"] = df.apply(
        lambda r: r["y"] if r["barca_attacks_right"] else (100.0 - r["y"])
        if r["is_barca"] else
        (100.0 - r["y"]) if r["barca_attacks_right"] else r["y"],
        axis=1,
    )

    # Normalize end coordinates for passes
    df["x_end_norm"] = df.apply(
        lambda r: r["x_end"] if r["barca_attacks_right"] else (100.0 - r["x_end"])
        if r["is_barca"] and pd.notna(r["x_end"]) else
        ((100.0 - r["x_end"]) if r["barca_attacks_right"] else r["x_end"])
        if pd.notna(r["x_end"]) else np.nan,
        axis=1,
    )
    df["y_end_norm"] = df.apply(
        lambda r: r["y_end"] if r["barca_attacks_right"] else (100.0 - r["y_end"])
        if r["is_barca"] and pd.notna(r["y_end"]) else
        ((100.0 - r["y_end"]) if r["barca_attacks_right"] else r["y_end"])
        if pd.notna(r["y_end"]) else np.nan,
        axis=1,
    )

    # Sort by period and event sequence
    df = df.sort_values(["period_id", "time_min", "time_sec", "event_id"]).reset_index(drop=True)

    # Add timestamp in seconds for time-based calculations
    df["time_seconds"] = df["time_min"] * 60 + df["time_sec"]

    # Add cumulative match seconds (accounting for periods)
    def _cumulative_seconds(row):
        base = 0
        if row["period_id"] == 2:
            base = 45 * 60
        elif row["period_id"] == 3:
            base = 90 * 60
        elif row["period_id"] == 4:
            base = 105 * 60
        return base + row["time_seconds"]

    df["match_seconds"] = df.apply(_cumulative_seconds, axis=1)

    return df
