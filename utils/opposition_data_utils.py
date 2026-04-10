"""
CuléVision - Opposition Data Utilities
Data access layer for the opposition pipeline output.

Output structure:
    data/opposition/{country_folder}/{team_folder}/{competition_key}/{season}/
        match/          *.parquet   (one row per match)
        match_event/    *.parquet   (one row per event, both teams)

Column note: the matchevent_transformer saves ``event_type_id``; this module
renames it to ``type_id`` on load so all opposition tab modules can use the
short name consistently.
"""

from __future__ import annotations

import unicodedata
from functools import lru_cache
from pathlib import Path

import pandas as pd
import yaml

from utils.data_utils import count_goals

# ── Paths ──────────────────────────────────────────────────────────────────

SCRIPT_DIR    = Path(__file__).parent.parent
OPP_DATA_ROOT = SCRIPT_DIR / "data" / "opposition"
OPP_CONFIG    = SCRIPT_DIR / "opposition_pipeline" / "config.yaml"
SEASON        = "2025-2026"

# ── Opta type-ID constants ──────────────────────────────────────────────────

SETUP_TYPE_ID        = 34
PASS_TYPE_ID         = 1
SHOT_TYPE_IDS        = {13, 14, 15, 16}   # miss, post, saved, goal
SAVED_TYPE_ID        = 15
GOAL_TYPE_ID         = 16
FOUL_TYPE_ID         = 4
TACKLE_TYPE_ID       = 7
INTERCEPTION_TYPE_ID = 8

# ── Folder-name sanitisation (mirrors opposition_pipeline/main.py) ──────────

_MANUAL_SUBS = {
    'ø': 'o', 'Ø': 'O',
    'æ': 'ae', 'Æ': 'AE',
    'å': 'a', 'Å': 'A',
    'ß': 'ss',
    'ð': 'd', 'Ð': 'D',
    'þ': 'th', 'Þ': 'Th',
}


def sanitize_folder(name: str) -> str:
    """Return a filesystem-safe folder name (mirrors opposition_pipeline)."""
    for ch, rep in _MANUAL_SUBS.items():
        name = name.replace(ch, rep)
    nfd = unicodedata.normalize('NFD', name)
    ascii_name = nfd.encode('ascii', 'ignore').decode('ascii')
    return (ascii_name
            .replace(' ', '_').replace('/', '_')
            .replace('\\', '_').replace('.', '')
            .strip('_'))


def _season_clean(season: str) -> str:
    return season.replace(' ', '_').replace('/', '-')


def _comp_clean(comp_key: str) -> str:
    return comp_key.replace(' ', '_').replace('/', '-')


def _normalize(text: str) -> str:
    """Lower-case + ASCII-normalize for fuzzy matching."""
    for ch, rep in {'ø': 'o', 'Ø': 'O', 'æ': 'ae', 'å': 'a'}.items():
        text = text.replace(ch, rep)
    nfd = unicodedata.normalize('NFD', text.lower())
    return nfd.encode('ascii', 'ignore').decode('ascii')


# ── Config loader ───────────────────────────────────────────────────────────

@lru_cache(maxsize=1)
def _load_opp_config() -> dict:
    if not OPP_CONFIG.exists():
        return {'opponents': [], 'competitions': {}}
    with open(OPP_CONFIG) as f:
        return yaml.safe_load(f) or {}


def list_available_opponents() -> list[dict]:
    """Return the opponents list from config.yaml."""
    return _load_opp_config().get('opponents', [])


def get_team_competitions(team_name: str) -> list[str]:
    """Return competition keys configured for a given team."""
    for opp in list_available_opponents():
        if opp['team_name'] == team_name:
            return opp.get('competitions', [])
    return []


def get_team_country(team_name: str) -> str:
    """Return the country string for a given team."""
    for opp in list_available_opponents():
        if opp['team_name'] == team_name:
            return opp.get('country', '')
    return ''


# ── Path construction ───────────────────────────────────────────────────────

def _opp_dir(country: str, team: str, comp_key: str,
             season: str = SEASON, subdir: str = 'match_event') -> Path:
    return (
        OPP_DATA_ROOT
        / sanitize_folder(country)
        / sanitize_folder(team)
        / _comp_clean(comp_key)
        / _season_clean(season)
        / subdir
    )


# ── Data loaders ────────────────────────────────────────────────────────────

# In-process cache for opposition event DataFrames.  Keyed by (team, country,
# comp_key, season).  Avoids re-reading all parquet files on every tab switch.
_opp_events_cache: dict[tuple, pd.DataFrame] = {}


def clear_opp_events_cache() -> None:
    """Clear the opposition events cache (call after running the pipeline)."""
    _opp_events_cache.clear()


def get_opp_all_events(team: str, country: str, comp_key: str,
                       season: str = SEASON) -> pd.DataFrame:
    """Load all match_event parquets for a team × competition (both teams).

    Results are cached in-process so repeated calls within the same session
    (e.g. switching tabs for the same opponent) hit memory instead of disk.

    Renames ``event_type_id`` → ``type_id`` so tab modules share a
    consistent column name.
    """
    cache_key = (team, country, comp_key, season)
    if cache_key in _opp_events_cache:
        return _opp_events_cache[cache_key]

    ev_dir = _opp_dir(country, team, comp_key, season, 'match_event')
    if not ev_dir.exists():
        return pd.DataFrame()
    frames = [pd.read_parquet(f) for f in sorted(ev_dir.glob('*.parquet'))]
    if not frames:
        return pd.DataFrame()
    df = pd.concat(frames, ignore_index=True)
    if 'event_type_id' in df.columns and 'type_id' not in df.columns:
        df = df.rename(columns={'event_type_id': 'type_id'})
    if not df.empty:
        _opp_events_cache[cache_key] = df
    return df


def get_opp_team_events(team: str, country: str, comp_key: str,
                        season: str = SEASON) -> pd.DataFrame:
    """Return only the events attributed to the opposition team."""
    df = get_opp_all_events(team, country, comp_key, season)
    if df.empty or 'team_name' not in df.columns:
        return df
    needle = _normalize(team)
    mask = df['team_name'].fillna('').apply(lambda s: needle in _normalize(s))
    return df[mask].copy()


def _scores_from_goals(match_ev_path: Path) -> tuple[int, int]:
    """Derive home/away scores from goal events using the shared count_goals helper.

    Delegates to data_utils.count_goals so own-goal handling stays in one place.
    Returns (home_score, away_score), both 0 if data is unavailable.
    """
    if not match_ev_path.exists():
        return 0, 0
    try:
        ev = pd.read_parquet(match_ev_path)
        goals = ev[ev['event_type'] == 'Goal']
        return count_goals(goals)
    except Exception:
        return 0, 0


def get_opp_team_matches(team: str, country: str, comp_key: str,
                         season: str = SEASON) -> list[dict]:
    """Return a list of result dicts from the match parquets.

    Each dict: date, competition, is_home, opponent, gf, ga, result.
    """
    match_dir = _opp_dir(country, team, comp_key, season, 'match')
    if not match_dir.exists():
        return []

    ev_dir = _opp_dir(country, team, comp_key, season, 'match_event')

    results = []
    for f in sorted(match_dir.glob('*.parquet')):
        try:
            row = pd.read_parquet(f).iloc[0]

            # Team names — transformer stores home_team_name / away_team_name
            home = str(row.get('home_team_name', row.get('home_team', ''))).strip()
            away = str(row.get('away_team_name', row.get('away_team', ''))).strip()

            # Scores — the transformer writes 'N/A' when the field is absent in
            # matchInfo.contestant; fall back to counting goal events instead.
            raw_h = str(row.get('home_score', 'N/A')).strip()
            raw_a = str(row.get('away_score', 'N/A')).strip()
            scores_missing = raw_h.upper() in ('N/A', 'NONE', '') or raw_a.upper() in ('N/A', 'NONE', '')
            if scores_missing:
                h_score, a_score = _scores_from_goals(ev_dir / f.name)
            else:
                try:
                    h_score = int(raw_h)
                    a_score = int(raw_a)
                except (ValueError, TypeError):
                    h_score = a_score = 0

            needle = _normalize(team)
            is_home = needle in _normalize(home)
            if is_home:
                gf, ga, opponent = h_score, a_score, away
            else:
                gf, ga, opponent = a_score, h_score, home

            result = 'W' if gf > ga else ('D' if gf == ga else 'L')

            results.append({
                'match_id':    str(row.get('match_id', f.stem)),
                'date':        str(row.get('date', row.get('match_date', '')))[:10],
                'competition': comp_key.replace('_', ' '),
                'is_home':     is_home,
                'opponent':    opponent,
                'gf':          gf,
                'ga':          ga,
                'result':      result,
            })
        except Exception:
            continue

    results.sort(key=lambda r: r['date'])
    return results


def load_opp_events(team: str, comp_key: str,
                    venue: str = 'all',
                    match_ids: list | None = None,
                    date_cutoff: str | None = None,
                    season: str = SEASON) -> tuple:
    """Load and split opposition events into (opp_ev, bar_ev).

    Applies venue, match-id selection, and date filters in that order.
    opp_ev — events attributed to ``team``.
    bar_ev — all other events (Barcelona's events in the match files).
    Returns (pd.DataFrame, pd.DataFrame) — both empty on any failure.
    """
    if not team or not comp_key:
        return pd.DataFrame(), pd.DataFrame()

    country   = get_team_country(team)
    all_comps = get_team_competitions(team)

    if comp_key == 'all':
        frames = [get_opp_all_events(team, country, c, season) for c in all_comps]
        non_empty = [f for f in frames if not f.empty]
        all_ev = pd.concat(non_empty, ignore_index=True) if non_empty else pd.DataFrame()
    else:
        all_ev = get_opp_all_events(team, country, comp_key, season)

    if all_ev.empty:
        return pd.DataFrame(), pd.DataFrame()

    # Date filter
    if date_cutoff and 'match_date' in all_ev.columns:
        all_ev = all_ev[all_ev['match_date'].astype(str).str[:10] <= date_cutoff[:10]]

    # Venue filter (uses home_team column written by the match transformer)
    if venue and venue != 'all' and 'home_team' in all_ev.columns:
        needle  = _normalize(team)
        is_home = all_ev['home_team'].fillna('').apply(lambda s: needle in _normalize(s))
        if venue == 'home':
            all_ev = all_ev[is_home].copy()
        elif venue == 'away':
            all_ev = all_ev[~is_home].copy()

    # Match-id selection filter
    if match_ids and 'match_id' in all_ev.columns:
        all_ev = all_ev[all_ev['match_id'].isin(match_ids)]

    if all_ev.empty:
        return pd.DataFrame(), pd.DataFrame()

    # Split into opposition team and Barcelona
    if 'team_name' in all_ev.columns:
        needle  = _normalize(team)
        is_opp  = all_ev['team_name'].fillna('').apply(lambda s: needle in _normalize(s))
        opp_ev  = all_ev[is_opp].copy()
        bar_ev  = all_ev[~is_opp].copy()
    else:
        opp_ev  = all_ev.copy()
        bar_ev  = pd.DataFrame()

    return opp_ev, bar_ev


def get_opp_possession(team: str, country: str, comp_key: str,
                       season: str = SEASON) -> float:
    """Approximate possession % based on the share of pass events.

    Returns 0.0 if no data exists or comp_key is 'all'.
    """
    if comp_key == 'all':
        return 0.0
    df = get_opp_all_events(team, country, comp_key, season)
    if df.empty or 'type_id' not in df.columns or 'team_name' not in df.columns:
        return 0.0
    passes = df[df['type_id'] == PASS_TYPE_ID]
    if passes.empty:
        return 0.0
    needle = _normalize(team)
    team_passes = passes['team_name'].fillna('').apply(
        lambda s: needle in _normalize(s)
    ).sum()
    total = len(passes)
    return round(team_passes / total * 100, 1) if total > 0 else 0.0
