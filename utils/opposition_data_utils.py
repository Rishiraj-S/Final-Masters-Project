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

import threading
import unicodedata
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache
from pathlib import Path

import pandas as pd
import yaml

from utils.data_utils import count_goals

# ── Paths ──────────────────────────────────────────────────────────────────

SCRIPT_DIR    = Path(__file__).parent.parent
DATA_ROOT     = SCRIPT_DIR / "data" / "2025-26"
OPP_CONFIG    = SCRIPT_DIR / "opta_pipeline" / "config.yaml"
SEASON        = "2025-2026"

# Keep old name as alias for any external code that imported it directly
OPP_DATA_ROOT = DATA_ROOT

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


# ── Team registry — auto-discovered from the data on disk ───────────────────
#
# Rather than enumerate every team in config.yaml, the registry is built by
# scanning the one-row ``match`` parquets across all competitions.  Every team
# that appears in any downloaded match (home or away) becomes available in
# Opposition Analysis automatically.  config.yaml entries are still consulted
# as overrides (code spelling, alt codes, country/search_name).

# Minimum matches a team needs to appear in Opposition Analysis.
# The data is opponent-centric: ~31 "focus" teams have a full domestic season,
# while incidental teams appear in only 1–2 matches.  1 = expose every team.
MIN_TEAM_MATCHES = 1

# Data folders use ASCII underscore names; map to flag-friendly display names.
_FOLDER_COUNTRY_DISPLAY = {
    'Czech_Republic': 'Czech Republic',
}


def _display_country(folder: str) -> str:
    return _FOLDER_COUNTRY_DISPLAY.get(folder, folder.replace('_', ' '))


def _read_match_teams(match_file: Path):
    """Return [(name, code), …] for the two teams in a one-row match parquet."""
    cols = ['home_team_name', 'home_team_code', 'away_team_name', 'away_team_code']
    try:
        row = pd.read_parquet(match_file, columns=cols).iloc[0]
    except Exception:
        try:
            row = pd.read_parquet(match_file).iloc[0]
        except Exception:
            return []
    out = []
    for name_c, code_c in (('home_team_name', 'home_team_code'),
                           ('away_team_name', 'away_team_code')):
        name = str(row.get(name_c, '')).strip()
        code = str(row.get(code_c, '')).strip()
        if name and name.upper() not in ('N/A', 'NONE'):
            out.append((name, code))
    return out


@lru_cache(maxsize=1)
def _discover_team_registry() -> tuple:
    """Scan every ``match`` parquet and build the full team registry.

    Returns a tuple of dicts (one per team), each with:
        team_name, team_code, team_codes (list), country, competitions (list)

    ``country`` is the team's domestic country (the non-Europe data folder it
    plays in); teams seen only in European competitions fall back to 'Europe'.
    A team may carry several Opta codes across competitions (e.g. PSG / PAR) —
    all are kept so filename filtering matches every match.
    """
    from collections import Counter, defaultdict

    code_counts:    dict[str, Counter] = defaultdict(Counter)
    comp_sets:      dict[str, set]     = defaultdict(set)
    country_counts: dict[str, Counter] = defaultdict(Counter)
    match_counts:   Counter            = Counter()

    if DATA_ROOT.exists():
        for match_file in DATA_ROOT.glob('*/*/match/*.parquet'):
            comp_key       = match_file.parents[1].name
            country_folder = match_file.parents[2].name
            for name, code in _read_match_teams(match_file):
                if code and code.upper() not in ('N/A', 'NONE'):
                    code_counts[name][code] += 1
                comp_sets[name].add(comp_key)
                country_counts[name][country_folder] += 1
                match_counts[name] += 1

    config_by_name = {t['team_name']: t for t in _load_opp_config().get('teams', [])}

    registry = []
    for name in sorted(comp_sets):
        if match_counts[name] < MIN_TEAM_MATCHES:
            continue
        codes_ranked = [c for c, _ in code_counts[name].most_common()]

        non_europe = [f for f, _ in country_counts[name].most_common() if f != 'Europe']
        if non_europe:
            country_folder = non_europe[0]
        elif country_counts[name]:
            country_folder = country_counts[name].most_common(1)[0][0]
        else:
            country_folder = ''
        country = _display_country(country_folder)

        # config.yaml overrides
        cfg = config_by_name.get(name, {})
        if cfg.get('team_code'):
            ranked = [cfg['team_code']]
            if cfg.get('team_code_alt'):
                ranked.append(cfg['team_code_alt'])
            for c in codes_ranked:
                if c not in ranked:
                    ranked.append(c)
            codes_ranked = ranked
        if cfg.get('country'):
            country = cfg['country']

        if not codes_ranked:
            continue

        registry.append({
            'team_name':    name,
            'team_code':    codes_ranked[0],
            'team_codes':   codes_ranked,
            'country':      country,
            'competitions': sorted(comp_sets[name]),
            'search_name':  cfg.get('search_name'),
        })
    return tuple(registry)


@lru_cache(maxsize=1)
def _registry_by_name() -> dict:
    return {t['team_name']: t for t in _discover_team_registry()}


def list_available_opponents() -> list[dict]:
    """Return every non-Barcelona team discovered in the data on disk."""
    return [t for t in _discover_team_registry() if t.get('team_code') != 'BAR']


def get_team_competitions(team_name: str) -> list[str]:
    """Return competition keys the team appears in."""
    t = _registry_by_name().get(team_name)
    return list(t['competitions']) if t else []


def get_team_country(team_name: str) -> str:
    """Return the (display) country string for a given team."""
    t = _registry_by_name().get(team_name)
    return t['country'] if t else ''


def get_team_codes(team_name: str) -> list[str]:
    """Return all Opta codes for a team (handles codes differing per comp)."""
    t = _registry_by_name().get(team_name)
    return list(t['team_codes']) if t else []


def get_team_code(team_name: str) -> str:
    """Return the primary Opta code for a team."""
    codes = get_team_codes(team_name)
    return codes[0] if codes else ''


# ── Competition → country mapping (mirrors opta_pipeline/modules/utils.py) ──

_COMP_COUNTRY: dict[str, str] = {
    'Spain':    'Spain',
    'England':  'England',
    'Germany':  'Germany',
    'France':   'France',
    'Belgium':  'Belgium',
    'Greece':   'Greece',
    'Denmark':  'Denmark',
    'Czech':    'Czech_Republic',
    'UEFA':     'Europe',
}


def _comp_country(comp_key: str) -> str:
    for prefix, country in _COMP_COUNTRY.items():
        if comp_key.startswith(prefix):
            return country
    return 'Other'


# ── Path construction ───────────────────────────────────────────────────────

def _opp_dir(comp_key: str, subdir: str = 'match_event',
             # country/team/season kept for call-site compatibility but unused
             country: str = '', team: str = '', season: str = SEASON) -> Path:
    """Return the flat competition subdir path.

    New structure: DATA_ROOT / {country} / {comp_key} / {subdir}
    """
    return DATA_ROOT / _comp_country(comp_key) / _comp_clean(comp_key) / subdir


def _team_parquets(team_codes: list[str], comp_key: str,
                   subdir: str = 'match_event') -> list[Path]:
    """Return sorted parquet files for a team in one competition subdir.

    Filters by Opta 3-letter team code(s) embedded in filenames:
        {date}_{HOME_CODE}_vs_{AWAY_CODE}_{match_id}.parquet

    Accepts a list of codes to handle teams that use different codes across
    competitions (e.g. PSG uses 'PSG' in UEFA feeds and 'PAR' in Ligue 1).
    """
    folder = _opp_dir(comp_key, subdir)
    if not folder.exists() or not team_codes:
        return []
    patterns = [(f'_{c}_vs_', f'_vs_{c}_') for c in team_codes]
    return sorted(
        f for f in folder.iterdir()
        if f.suffix == '.parquet'
        and any(h in f.name or a in f.name for h, a in patterns)
    )


# ── Data loaders ────────────────────────────────────────────────────────────

# Bounded LRU caches (OrderedDict). Keyed by (team/codes, comp_key, season).
# With 212 teams an unbounded cache could pin hundreds of 60k-row DataFrames in
# RAM and thrash; we keep only the most-recently-used selections.
_OPP_EVENTS_CACHE_MAX  = 24
_OPP_MATCHES_CACHE_MAX = 64
_opp_events_cache:  "OrderedDict[tuple, pd.DataFrame]" = OrderedDict()
_opp_matches_cache: "OrderedDict[tuple, list]"         = OrderedDict()
# Flask's dev server is threaded, so callbacks (and their cache access) can run
# concurrently — guard the check-then-act cache ops with a lock.
_cache_lock = threading.Lock()


def _cache_get(cache: OrderedDict, key):
    """LRU read: return the value and mark it most-recently-used, else None."""
    with _cache_lock:
        if key in cache:
            cache.move_to_end(key)
            return cache[key]
    return None


def _cache_put(cache: OrderedDict, key, value, maxsize: int) -> None:
    """LRU write: insert/refresh and evict the oldest entries past ``maxsize``."""
    with _cache_lock:
        cache[key] = value
        cache.move_to_end(key)
        while len(cache) > maxsize:
            cache.popitem(last=False)


def clear_opp_events_cache() -> None:
    """Clear the opposition events cache (call after running the pipeline)."""
    with _cache_lock:
        _opp_events_cache.clear()
        _opp_matches_cache.clear()
    # New matches may introduce new teams — rebuild the discovered registry too.
    _discover_team_registry.cache_clear()
    _registry_by_name.cache_clear()
    _load_opp_config.cache_clear()


def get_opp_all_events(team: str, country: str, comp_key: str,
                       season: str = SEASON) -> pd.DataFrame:
    """Load all match_event parquets for a team × competition (both teams).

    Results are cached in-process so repeated calls within the same session
    hit memory instead of disk.

    Renames ``event_type_id`` → ``type_id`` so tab modules share a
    consistent column name.

    country/season are kept for call-site compatibility; path is now derived
    from comp_key alone.
    """
    cache_key = (team, comp_key, season)
    cached = _cache_get(_opp_events_cache, cache_key)
    if cached is not None:
        return cached

    files = _team_parquets(get_team_codes(team), comp_key, 'match_event')
    if not files:
        return pd.DataFrame()

    # Parquet reads are I/O-bound and pyarrow releases the GIL, so reading the
    # match files concurrently cuts cold-load latency for big seasons.
    if len(files) > 4:
        with ThreadPoolExecutor(max_workers=min(8, len(files))) as ex:
            frames = list(ex.map(pd.read_parquet, files))
    else:
        frames = [pd.read_parquet(f) for f in files]

    df = pd.concat(frames, ignore_index=True)
    if 'event_type_id' in df.columns and 'type_id' not in df.columns:
        df = df.rename(columns={'event_type_id': 'type_id'})
    if not df.empty:
        _cache_put(_opp_events_cache, cache_key, df, _OPP_EVENTS_CACHE_MAX)
    return df


def get_opp_team_events(team: str, country: str, comp_key: str,
                        season: str = SEASON) -> pd.DataFrame:
    """Return only the events attributed to the opposition team."""
    df = get_opp_all_events(team, country, comp_key, season)
    if df.empty or 'team_code' not in df.columns:
        return df
    codes = get_team_codes(team)
    return df[df['team_code'].isin(codes)].copy()


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
    codes = get_team_codes(team)
    cache_key = (tuple(codes), comp_key, season)
    cached = _cache_get(_opp_matches_cache, cache_key)
    if cached is not None:
        # Shallow copy so callers can sort/filter the list without touching cache.
        return list(cached)

    match_files = _team_parquets(codes, comp_key, 'match')
    if not match_files:
        return []

    ev_dir = _opp_dir(comp_key, 'match_event')

    # Match parquets are one tiny row each; read them concurrently.
    def _read_first_row(f: Path):
        try:
            return f, pd.read_parquet(f).iloc[0]
        except Exception:
            return f, None

    if len(match_files) > 4:
        with ThreadPoolExecutor(max_workers=min(8, len(match_files))) as ex:
            rows = list(ex.map(_read_first_row, match_files))
    else:
        rows = [_read_first_row(f) for f in match_files]

    results = []
    for f, row in rows:
        if row is None:
            continue
        try:
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

            is_home = any(f'_{c}_vs_' in f.name for c in codes)
            if is_home:
                gf, ga, opponent = h_score, a_score, away
            else:
                gf, ga, opponent = a_score, h_score, home

            result = 'W' if gf > ga else ('D' if gf == ga else 'L')

            results.append({
                'match_id':       str(row.get('match_id', f.stem)),
                'date':           str(row.get('date', row.get('match_date', '')))[:10],
                'competition':    comp_key.replace('_', ' '),
                'competition_key': comp_key,
                'is_home':        is_home,
                'opponent':    opponent,
                'gf':          gf,
                'ga':          ga,
                'result':      result,
            })
        except Exception:
            continue

    results.sort(key=lambda r: r['date'])
    _cache_put(_opp_matches_cache, cache_key, results, _OPP_MATCHES_CACHE_MAX)
    return list(results)


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

    # Venue filter — use team_code in home_team_code column if available,
    # else fall back to matching team_code against the first event per match.
    if venue and venue != 'all' and 'team_code' in all_ev.columns:
        codes = get_team_codes(team)
        # home_team_code column written by match_transformer; fall back to
        # checking whether the team's code matches the home_team_code per row.
        if 'home_team_code' in all_ev.columns:
            is_home = all_ev['home_team_code'].isin(codes)
        else:
            # Derive home/away from team_position column (always present)
            is_home = (
                all_ev['team_position'].eq('home') &
                all_ev['team_code'].isin(codes)
            )
            # Broadcast per match_id: if any row for this match has team home, all rows for that match are "home"
            home_match_ids = set(all_ev[is_home]['match_id'].unique()) if 'match_id' in all_ev.columns else set()
            is_home = all_ev['match_id'].isin(home_match_ids)
        if venue == 'home':
            all_ev = all_ev[is_home].copy()
        elif venue == 'away':
            all_ev = all_ev[~is_home].copy()

    # Match-id selection filter
    if match_ids and 'match_id' in all_ev.columns:
        all_ev = all_ev[all_ev['match_id'].isin(match_ids)]

    if all_ev.empty:
        return pd.DataFrame(), pd.DataFrame()

    # Split into opposition team and Barcelona using team_code (reliable across all teams)
    if 'team_code' in all_ev.columns:
        codes  = get_team_codes(team)
        is_opp = all_ev['team_code'].isin(codes)
        opp_ev = all_ev[is_opp].copy()
        bar_ev = all_ev[~is_opp].copy()
    else:
        opp_ev = all_ev.copy()
        bar_ev = pd.DataFrame()

    return opp_ev, bar_ev


def get_opp_possession(team: str, country: str, comp_key: str,
                       season: str = SEASON) -> float:
    """Approximate possession % based on the share of pass events.

    Returns 0.0 if no data exists or comp_key is 'all'.
    """
    if comp_key == 'all':
        return 0.0
    df = get_opp_all_events(team, country, comp_key, season)
    if df.empty or 'type_id' not in df.columns or 'team_code' not in df.columns:
        return 0.0
    passes = df[df['type_id'] == PASS_TYPE_ID]
    if passes.empty:
        return 0.0
    codes = get_team_codes(team)
    team_passes = passes['team_code'].isin(codes).sum()
    total = len(passes)
    return round(team_passes / total * 100, 1) if total > 0 else 0.0
