#!/usr/bin/env python3
"""
Opposition Data Pipeline
========================
Downloads ALL match event data for every team Barcelona faced in 2025-2026,
across all competitions those teams participated in.

Output structure:
    data/opposition/{country}/{team_name}/{competition}/2025-2026/
        match/          *.parquet   (basic match info)
        match_event/    *.parquet   (full event data)
        lineup/         *.parquet   (lineups)

Design principles:
    - Each competition page is scraped ONCE and the result cached locally as a CSV.
      All team-specific filtering happens on that cached DataFrame — no redundant
      Scoresway requests per team.
    - Reuses all modules from opta_pipeline/ with zero duplication.
    - Per-team+competition config dicts are built dynamically so existing
      transformers write to the correct country/team/competition folder.

Usage:
    python main.py                          # full pipeline, all opponents
    python main.py --team "Chelsea"         # single team
    python main.py --competition "England_Premier_League"   # single competition
    python main.py --transform-only         # re-transform existing JSONs
    python main.py --force-rescrape         # ignore scrape cache, re-scrape pages
    python main.py --skip-download          # scrape + transform only, no browser
"""

import os
import sys
import json
import yaml
import argparse
import unicodedata
from pathlib import Path

try:
    from tqdm import tqdm as _tqdm
except ImportError:
    def _tqdm(it, **kw):  # type: ignore[misc]
        return it

import pandas as pd

# ── Reuse opta_pipeline modules (no code duplication) ─────────────────────────
sys.path.insert(0, str(Path(__file__).parent.parent / 'opta_pipeline'))
from modules import (
    MatchScraper,
    MatchDownloader,
    MatchTransformer,
    MatchEventTransformer,
    LineupTransformer,
    setup_logging,
    ensure_directories,
)
from modules.utils import get_organized_path_reversed

# ── Constants ──────────────────────────────────────────────────────────────────
PROGRESS_FILE  = Path(__file__).parent / "logs" / "progress.json"
SCRAPE_CACHE   = Path(__file__).parent / "logs" / "scrape_cache"


# ── Progress helper ────────────────────────────────────────────────────────────

def write_progress(team: str = "", competition: str = "", stage: str = "",
                   detail: str = "", current_team: int = 0, total_teams: int = 0,
                   current_match: int = 0, total_matches: int = 0,
                   status: str = "running") -> None:
    payload = {
        "team": team,
        "competition": competition,
        "stage": stage,
        "detail": detail,
        "status": status,
        "current_team": current_team,
        "total_teams": total_teams,
        "current_match": current_match,
        "total_matches": total_matches,
    }
    try:
        PROGRESS_FILE.parent.mkdir(parents=True, exist_ok=True)
        tmp = PROGRESS_FILE.with_suffix('.tmp')
        tmp.write_text(json.dumps(payload), encoding="utf-8")
        tmp.rename(PROGRESS_FILE)
    except Exception:
        pass


# ── Config helpers ─────────────────────────────────────────────────────────────

def load_config(config_path: str = None) -> dict:
    if config_path is None:
        config_path = Path(__file__).parent / "config.yaml"
    config_path = Path(config_path)
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)

    # Resolve relative paths against the pipeline directory
    pipeline_dir = config_path.parent
    for key in ('result_dir', 'target_dir', 'mappings_dir', 'logs_dir'):
        val = config.get('paths', {}).get(key)
        if val and not Path(val).is_absolute():
            config['paths'][key] = str(pipeline_dir / val)

    return config


def sanitize_folder(name: str) -> str:
    """Return a cross-platform filesystem-safe folder name.

    Converts accented characters to their ASCII equivalents and replaces
    spaces/slashes with underscores.
    """
    # Manual replacements for chars that don't decompose cleanly under NFD
    _manual = {
        'ø': 'o', 'Ø': 'O',
        'æ': 'ae', 'Æ': 'AE',
        'å': 'a', 'Å': 'A',
        'ß': 'ss',
        'ð': 'd', 'Ð': 'D',
        'þ': 'th', 'Þ': 'Th',
    }
    for ch, rep in _manual.items():
        name = name.replace(ch, rep)

    # NFD decompose + drop combining diacritical marks
    nfd = unicodedata.normalize('NFD', name)
    ascii_name = nfd.encode('ascii', 'ignore').decode('ascii')

    return (ascii_name
            .replace(' ', '_')
            .replace('/', '_')
            .replace('\\', '_')
            .replace('.', '')
            .strip('_'))


def normalize_for_search(text: str) -> str:
    """Lower-case + ASCII-normalize a string for fuzzy team-name matching."""
    for ch, rep in {'ø': 'o', 'Ø': 'O', 'æ': 'ae', 'å': 'a'}.items():
        text = text.replace(ch, rep)
    nfd = unicodedata.normalize('NFD', text.lower())
    return nfd.encode('ascii', 'ignore').decode('ascii')


def build_team_comp_config(base_config: dict, country: str,
                           team_name: str, comp_name: str) -> dict:
    """Build a self-contained config dict for one team × competition.

    The transformers and downloader use:
        target_dir / league_name / season / matchdata / *.json
        result_dir / league_name / season / {match,match_event,lineup} / *.parquet

    By pointing target_dir and result_dir at the team-specific folder, and
    setting league_name = comp_name, we get the desired output path:
        data/opposition/{country}/{team}/{competition}/2025-2026/...
    """
    country_folder = sanitize_folder(country)
    team_folder    = sanitize_folder(team_name)

    base_result = Path(base_config['paths']['result_dir'])
    base_target = Path(base_config['paths']['target_dir'])

    return {
        'competition': {
            'id': '',
            'league_name': comp_name,
            'season': base_config['season'],
        },
        'paths': {
            'result_dir':   str(base_result / country_folder / team_folder),
            'target_dir':   str(base_target / country_folder / team_folder),
            'mappings_dir': base_config['paths']['mappings_dir'],
            'logs_dir':     base_config['paths']['logs_dir'],
        },
        'output':     base_config.get('output', {}),
        'downloader': base_config.get('downloader', {}),
        'logging':    base_config.get('logging', {}),
        'scraper':    base_config.get('scraper', {}),
    }


# ── Scraping helpers ───────────────────────────────────────────────────────────

def get_scraped_matches(comp_name: str, results_url: str,
                        base_config: dict, logger,
                        force_rescrape: bool = False) -> pd.DataFrame:
    """Scrape a competition results page once; cache result as CSV.

    On subsequent runs the cached CSV is returned immediately unless
    --force-rescrape is passed.

    Returns a DataFrame with columns: date, match_id, url_match, home, away,
    home_score, away_score.
    """
    SCRAPE_CACHE.mkdir(parents=True, exist_ok=True)
    cache_file = SCRAPE_CACHE / f"{comp_name}_matches.csv"

    if not force_rescrape and cache_file.exists():
        logger.info(f"📋 [{comp_name}] Using cached scrape ({cache_file.name})")
        print(f"   📋 Using cached scrape: {comp_name}")
        return pd.read_csv(cache_file)

    logger.info(f"🔍 Scraping {comp_name} ...")
    print(f"\n   🔍 Scraping: {comp_name}")

    # Build a minimal config the scraper needs (timeout / scroll settings)
    scraper_config = {
        'scraper': base_config.get('scraper', {}),
        'competition': {'league_name': comp_name, 'season': base_config['season']},
        'paths': base_config['paths'],
    }
    scraper = MatchScraper(scraper_config, logger)

    try:
        df = scraper.scrape_matches(results_url, team_name=None)  # no filter → all matches
    except Exception as e:
        logger.error(f"❌ Scraping {comp_name} failed: {e}")
        print(f"   ❌ Scraping failed for {comp_name}: {e}")
        return pd.DataFrame()

    if not df.empty:
        df.to_csv(cache_file, index=False)
        logger.info(f"💾 Cached {len(df)} matches → {cache_file.name}")
        print(f"   ✅ Scraped {len(df)} matches → cached")
    else:
        logger.warning(f"⚠️  No matches scraped for {comp_name}")
        print(f"   ⚠️  No matches found for {comp_name}")

    return df


def filter_matches_for_team(all_df: pd.DataFrame, team_name: str,
                             search_name: str = None) -> pd.DataFrame:
    """Return rows where the given team appears as home or away.

    Matching is case-insensitive and accent-insensitive.  search_name
    overrides team_name if you need to match a different display string
    (e.g. 'Atl' for 'Atlético de Madrid').
    """
    if all_df.empty:
        return pd.DataFrame()

    needle = normalize_for_search(search_name or team_name)

    home_norm = all_df['home'].fillna('').apply(normalize_for_search)
    away_norm = all_df['away'].fillna('').apply(normalize_for_search)

    mask = (home_norm.str.contains(needle, regex=False) |
            away_norm.str.contains(needle, regex=False))
    return all_df[mask].copy()


# ── Cleanup helper ─────────────────────────────────────────────────────────────

def cleanup_target_jsons(comp_config: dict, comp_name: str,
                         season: str, logger) -> int:
    target_dir = comp_config['paths']['target_dir']
    dir_path = Path(get_organized_path_reversed(
        target_dir, comp_name, season, '', subdirectory='matchdata'
    ))
    if not dir_path.exists():
        return 0
    deleted = 0
    for f in dir_path.glob('*.json'):
        try:
            f.unlink()
            deleted += 1
        except Exception as e:
            logger.warning(f"Could not delete {f.name}: {e}")
    if deleted:
        logger.info(f"🗑️  Deleted {deleted} temporary JSON(s)")
    return deleted


# ── Core: process one team × competition ──────────────────────────────────────

def process_team_competition(
    team_name: str,
    country: str,
    search_name: str,
    comp_name: str,
    comp_df: pd.DataFrame,
    base_config: dict,
    logger,
    args,
    team_idx: int,
    total_teams: int,
) -> dict:
    """Download + transform all matches for one team in one competition.

    Returns a dict summarising what happened.
    """
    season      = base_config['season']
    comp_config = build_team_comp_config(base_config, country, team_name, comp_name)

    # Filter the cached competition DataFrame to this team's matches
    team_df = filter_matches_for_team(comp_df, team_name, search_name)

    if team_df.empty:
        logger.info(f"   ⚠️  No matches found for '{team_name}' in {comp_name}")
        return {'downloaded': 0, 'skipped': 0, 'transformed': 0, 'status': 'empty'}

    total_matches = len(team_df)
    logger.info(f"   📊 {total_matches} match(es) for {team_name} in {comp_name}")

    stats = {'downloaded': 0, 'skipped': 0, 'transformed': 0, 'status': 'success'}

    # ── Download phase ─────────────────────────────────────────────────────────
    if not args.transform_only and not args.skip_download:
        downloader = MatchDownloader(comp_config, logger)

        pbar = _tqdm(list(team_df.iterrows()), total=total_matches,
                     desc=f"⬇  {team_name[:18]}", unit="match",
                     ncols=90, leave=True)
        for i, (_, row) in enumerate(pbar, 1):
            match_id  = str(row['match_id'])
            match_url = str(row['url_match'])
            home      = row.get('home', '')
            away      = row.get('away', '')
            label     = f"{home} vs {away}" if home and away else match_id

            pbar.set_postfix_str(label[:35], refresh=True)
            write_progress(
                team=team_name, competition=comp_name,
                stage="Downloading", detail=label,
                current_team=team_idx, total_teams=total_teams,
                current_match=i, total_matches=total_matches,
            )
            logger.info(f"   [{i}/{total_matches}] {label}")

            success, _ = downloader.download_match(match_id, match_url)
            if success:
                stats['downloaded'] += 1
            else:
                stats['skipped'] += 1

    # ── Transform phase ────────────────────────────────────────────────────────
    write_progress(
        team=team_name, competition=comp_name, stage="Transforming",
        current_team=team_idx, total_teams=total_teams,
    )

    n  = MatchTransformer(comp_config, logger).transform_all()
    n += MatchEventTransformer(comp_config, logger).transform_all()
    LineupTransformer(comp_config, logger).transform_all()
    stats['transformed'] = n

    # ── Cleanup raw JSONs ──────────────────────────────────────────────────────
    deleted = cleanup_target_jsons(comp_config, comp_name, season, logger)
    if deleted:
        print(f"      🗑️  Cleaned up {deleted} JSON(s)")

    return stats


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description='Opposition Data Pipeline — all matches for every Barça opponent'
    )
    parser.add_argument('--config',         default=None,
                        help='Path to config.yaml (default: opposition_pipeline/config.yaml)')
    parser.add_argument('--team',           type=str, default=None,
                        help='Process only one team by team_name')
    parser.add_argument('--competition',    type=str, default=None,
                        help='Process only one competition by key (e.g. England_Premier_League)')
    parser.add_argument('--transform-only', action='store_true',
                        help='Skip download; only transform existing JSONs')
    parser.add_argument('--skip-download',  action='store_true',
                        help='Scrape pages and transform but skip browser downloads')
    parser.add_argument('--force-rescrape', action='store_true',
                        help='Ignore scrape cache; re-scrape every competition page')
    args = parser.parse_args()

    # ── Load config + setup ────────────────────────────────────────────────────
    config = load_config(args.config)

    logger = setup_logging(config['paths']['logs_dir'], config['logging']['level'])
    ensure_directories(config['paths'])
    SCRAPE_CACHE.mkdir(parents=True, exist_ok=True)

    # Remove stale progress from a previous run
    try:
        PROGRESS_FILE.unlink(missing_ok=True)
    except Exception:
        pass

    all_opponents  = config['opponents']
    all_comp_urls  = config['competitions']
    season         = config['season']

    # ── Apply CLI filters ──────────────────────────────────────────────────────
    if args.team:
        all_opponents = [o for o in all_opponents if o['team_name'] == args.team]
        if not all_opponents:
            print(f"❌ Team '{args.team}' not found in config")
            sys.exit(1)

    if args.competition:
        if args.competition not in all_comp_urls:
            print(f"❌ Competition '{args.competition}' not found in config")
            sys.exit(1)
        # Keep only opponents that include this competition
        all_opponents = [
            o for o in all_opponents
            if args.competition in o.get('competitions', [])
        ]
        all_comp_urls = {args.competition: all_comp_urls[args.competition]}

    # ── Determine which competitions actually need scraping ────────────────────
    needed_comps = {
        comp
        for opp in all_opponents
        for comp in opp.get('competitions', [])
        if comp in all_comp_urls
    }

    total_teams = len(all_opponents)

    print(f"\n{'='*80}")
    print("🚀 OPPOSITION PIPELINE")
    print(f"{'='*80}")
    print(f"📊 {total_teams} opponent(s) | {len(needed_comps)} competition page(s) to scrape")
    print(f"📅 Season: {season}")
    print()

    # ──────────────────────────────────────────────────────────────────────────
    # PHASE 1 — Scrape each competition page once and cache
    # ──────────────────────────────────────────────────────────────────────────
    print(f"{'='*60}")
    print("PHASE 1 — SCRAPING COMPETITION PAGES")
    print(f"{'='*60}")

    comp_cache: dict[str, pd.DataFrame] = {}
    for comp_name in sorted(needed_comps):
        comp_info = all_comp_urls[comp_name]
        comp_cache[comp_name] = get_scraped_matches(
            comp_name,
            comp_info['results_url'],
            config,
            logger,
            force_rescrape=args.force_rescrape,
        )

    # ──────────────────────────────────────────────────────────────────────────
    # PHASE 2 — Download + transform per opponent × competition
    # ──────────────────────────────────────────────────────────────────────────
    print(f"\n{'='*60}")
    print("PHASE 2 — DOWNLOAD & TRANSFORM")
    print(f"{'='*60}")

    all_stats = []

    team_pbar = _tqdm(all_opponents, total=total_teams,
                      desc="👤 Opponents", unit="team", ncols=90)
    for team_idx, opp in enumerate(team_pbar, 1):
        team_name   = opp['team_name']
        country     = opp['country']
        search_name = opp.get('search_name')
        team_comps  = [c for c in opp.get('competitions', []) if c in comp_cache]

        team_pbar.set_description(f"👤 {team_name[:25]}")

        print(f"\n{'='*60}")
        print(f"👤 [{team_idx}/{total_teams}] {team_name}  ({country})")
        print(f"{'='*60}")

        for comp_name in team_comps:
            comp_df = comp_cache[comp_name]
            print(f"\n  🏆 {comp_name}")

            stats = process_team_competition(
                team_name=team_name,
                country=country,
                search_name=search_name,
                comp_name=comp_name,
                comp_df=comp_df,
                base_config=config,
                logger=logger,
                args=args,
                team_idx=team_idx,
                total_teams=total_teams,
            )
            all_stats.append({'team': team_name, 'competition': comp_name, **stats})

            if stats['status'] == 'empty':
                print(f"     ⚠️  Not in {comp_name} (0 matches found)")
            else:
                print(f"     ✅ Downloaded: {stats['downloaded']} | "
                      f"Skipped: {stats['skipped']} | "
                      f"Parquets: {stats['transformed']}")

    # ──────────────────────────────────────────────────────────────────────────
    # Summary
    # ──────────────────────────────────────────────────────────────────────────
    total_dl  = sum(s['downloaded']  for s in all_stats)
    total_sk  = sum(s['skipped']     for s in all_stats)
    total_tr  = sum(s['transformed'] for s in all_stats)
    empty_cnt = sum(1 for s in all_stats if s['status'] == 'empty')

    print(f"\n{'='*80}")
    print("📈 FINAL SUMMARY")
    print(f"{'='*80}")
    print(f"✅ Matches downloaded : {total_dl}")
    print(f"⏭️  Matches skipped   : {total_sk}  (already existed)")
    print(f"🔄 Parquets written  : {total_tr}")
    print(f"⚠️  Empty results    : {empty_cnt}  (team not found in that competition)")
    print(f"\n📁 Output: data/opposition/{{country}}/{{team}}/{{competition}}/")
    print(f"{'='*80}\n")

    logger.info(f"✅ Downloaded: {total_dl} | Skipped: {total_sk} | Parquets: {total_tr}")

    # Clean up progress file
    try:
        PROGRESS_FILE.unlink(missing_ok=True)
    except Exception:
        pass


if __name__ == "__main__":
    main()
