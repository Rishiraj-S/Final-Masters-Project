#!/usr/bin/env python3
"""
CuléVision Opta Pipeline — Combined Data Extraction
====================================================
Single entry point for all match data: FC Barcelona and every configured opponent.

Two-phase design:
  Phase 1 — Scrape each competition results page ONCE, cache as CSV with TTL.
  Phase 2 — For each team × competition, download missing matches + transform.

All output goes to: data/2025-26/{country}/{competition}/{subdir}/*.parquet

Usage:
    python opta_pipeline/main.py                              # all teams
    python opta_pipeline/main.py --team "Barcelona"           # single team
    python opta_pipeline/main.py --team "Real Madrid"
    python opta_pipeline/main.py --competition Spain_Primera_Division
    python opta_pipeline/main.py --transform-only
    python opta_pipeline/main.py --skip-download
    python opta_pipeline/main.py --force-rescrape
"""

import os
import sys
import json
import time
import yaml
import argparse
import unicodedata
from pathlib import Path

try:
    from tqdm import tqdm as _tqdm
except ImportError:
    def _tqdm(it, **kw):       # type: ignore[misc]
        return it

import pandas as pd

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

# ── Constants ─────────────────────────────────────────────────────────────────

PROGRESS_FILE = Path(__file__).parent / "logs" / "progress.json"
SCRAPE_CACHE  = Path(__file__).parent / "logs" / "scrape_cache"
MANIFEST_FILE = Path(__file__).parent / "logs" / "download_manifest.json"


# ── Progress ──────────────────────────────────────────────────────────────────

def write_progress(team: str = "", competition: str = "", stage: str = "",
                   detail: str = "", current_team: int = 0, total_teams: int = 0,
                   current_match: int = 0, total_matches: int = 0,
                   status: str = "running") -> None:
    payload = {
        "team": team, "competition": competition,
        "stage": stage, "detail": detail, "status": status,
        "current_team": current_team, "total_teams": total_teams,
        "current_match": current_match, "total_matches": total_matches,
    }
    try:
        PROGRESS_FILE.parent.mkdir(parents=True, exist_ok=True)
        tmp = PROGRESS_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload), encoding="utf-8")
        tmp.rename(PROGRESS_FILE)
    except Exception:
        pass


# ── Manifest ──────────────────────────────────────────────────────────────────

def _bootstrap_manifest_from_fs(base_result_dir: Path) -> set:
    """Scan existing match_event parquets and extract match IDs from filenames."""
    ids: set = set()
    if not base_result_dir.exists():
        return ids
    for pq in base_result_dir.glob("**/match_event/*.parquet"):
        parts = pq.stem.split("_")
        if parts and len(parts[-1]) > 3:
            ids.add(parts[-1])
    return ids


def load_manifest(base_result_dir: Path) -> set:
    if MANIFEST_FILE.exists():
        try:
            data = json.loads(MANIFEST_FILE.read_text(encoding="utf-8"))
            return set(data.get("downloaded", []))
        except Exception:
            return set()
    ids = _bootstrap_manifest_from_fs(base_result_dir)
    if ids:
        save_manifest(ids)
        print(f"   📋 Bootstrapped manifest with {len(ids)} existing match ID(s)")
    return ids


def save_manifest(manifest: set) -> None:
    try:
        MANIFEST_FILE.parent.mkdir(parents=True, exist_ok=True)
        tmp = MANIFEST_FILE.with_suffix(".tmp")
        tmp.write_text(
            json.dumps({"downloaded": sorted(manifest)}, indent=2),
            encoding="utf-8",
        )
        tmp.rename(MANIFEST_FILE)
    except Exception:
        pass


# ── Config ────────────────────────────────────────────────────────────────────

def load_config(config_path=None) -> dict:
    if config_path is None:
        config_path = Path(__file__).parent / "config.yaml"
    config_path = Path(config_path)
    with open(config_path) as f:
        config = yaml.safe_load(f)
    pipeline_dir = config_path.parent
    for key in ("result_dir", "target_dir", "mappings_dir", "logs_dir"):
        val = config.get("paths", {}).get(key)
        if val and not Path(val).is_absolute():
            config["paths"][key] = str(pipeline_dir / val)
    return config


def build_comp_config(base_config: dict, comp_name: str) -> dict:
    """Build a self-contained config dict for one competition."""
    return {
        "competition": {
            "id": "",
            "league_name": comp_name,
            "season": base_config["season"],
        },
        "paths": {
            "result_dir":   base_config["paths"]["result_dir"],
            "target_dir":   base_config["paths"]["target_dir"],
            "mappings_dir": base_config["paths"]["mappings_dir"],
            "logs_dir":     base_config["paths"]["logs_dir"],
        },
        "output":     base_config.get("output", {}),
        "downloader": base_config.get("downloader", {}),
        "logging":    base_config.get("logging", {}),
        "scraper":    base_config.get("scraper", {}),
    }


# ── Name helpers ──────────────────────────────────────────────────────────────

def normalize_for_search(text: str) -> str:
    for ch, rep in {"ø": "o", "Ø": "O", "æ": "ae", "å": "a"}.items():
        text = text.replace(ch, rep)
    nfd = unicodedata.normalize("NFD", text.lower())
    return nfd.encode("ascii", "ignore").decode("ascii")


# ── Scraping ──────────────────────────────────────────────────────────────────

def get_scraped_matches(comp_name: str, results_url: str, base_config: dict,
                        logger, force_rescrape: bool = False) -> pd.DataFrame:
    """Scrape a competition results page once; return (and cache) the result."""
    SCRAPE_CACHE.mkdir(parents=True, exist_ok=True)
    cache_file = SCRAPE_CACHE / f"{comp_name}_matches.csv"

    cache_ttl  = base_config.get("scraper", {}).get("cache_ttl_days", 1)
    cache_age  = (
        (time.time() - cache_file.stat().st_mtime) / 86400
        if cache_file.exists() else float("inf")
    )
    cache_ok = cache_file.exists() and cache_age < cache_ttl

    if not force_rescrape and cache_ok:
        logger.info(f"📋 [{comp_name}] Using cached scrape ({cache_age:.1f}d old)")
        print(f"   📋 Cached scrape: {comp_name}  ({cache_age:.1f}d old)")
        return pd.read_csv(cache_file)

    if not force_rescrape and cache_file.exists() and not cache_ok:
        logger.info(f"🔄 [{comp_name}] Cache expired — re-scraping")
        print(f"   🔄 Cache expired for {comp_name} — re-scraping")

    print(f"\n   🔍 Scraping: {comp_name}")
    scraper_config = {
        "scraper":     base_config.get("scraper", {}),
        "competition": {"league_name": comp_name, "season": base_config["season"]},
        "paths":       base_config["paths"],
    }
    scraper = MatchScraper(scraper_config, logger)

    try:
        df = scraper.scrape_matches(results_url, team_name=None)
    except Exception as e:
        logger.error(f"❌ Scraping {comp_name} failed: {e}")
        print(f"   ❌ Scraping failed for {comp_name}: {e}")
        return pd.DataFrame()

    if not df.empty:
        df.to_csv(cache_file, index=False)
        logger.info(f"💾 Cached {len(df)} matches → {cache_file.name}")
        print(f"   ✅ Scraped {len(df)} matches — cached")
    else:
        logger.warning(f"⚠️  No matches scraped for {comp_name}")
        print(f"   ⚠️  No matches found for {comp_name}")

    return df


def filter_matches_for_team(all_df: pd.DataFrame, team_name: str,
                             search_name: str = None) -> pd.DataFrame:
    """Return rows where the given team appears as home or away."""
    if all_df.empty:
        return pd.DataFrame()
    needle    = normalize_for_search(search_name or team_name)
    home_norm = all_df["home"].fillna("").apply(normalize_for_search)
    away_norm = all_df["away"].fillna("").apply(normalize_for_search)
    mask = (home_norm.str.contains(needle, regex=False) |
            away_norm.str.contains(needle, regex=False))
    return all_df[mask].copy()


# ── Cleanup ───────────────────────────────────────────────────────────────────

def cleanup_target_jsons(comp_config: dict, comp_name: str,
                         season: str, logger) -> int:
    target_dir = comp_config["paths"]["target_dir"]
    dir_path   = Path(get_organized_path_reversed(
        target_dir, comp_name, season, "", subdirectory="matchdata"
    ))
    if not dir_path.exists():
        return 0
    deleted = 0
    for f in dir_path.glob("*.json"):
        try:
            f.unlink()
            deleted += 1
        except Exception as e:
            logger.warning(f"Could not delete {f.name}: {e}")
    if deleted:
        logger.info(f"🗑️  Deleted {deleted} temporary JSON(s)")
    return deleted


# ── Core: process a full competition (every match, no team filter) ───────────

def process_full_competition(
    comp_name: str,
    comp_df: pd.DataFrame,
    base_config: dict,
    logger,
    args,
    comp_idx: int,
    total_comps: int,
    manifest: set,
) -> dict:
    """Download + transform EVERY match in a competition (no per-team filter)."""
    season      = base_config["season"]
    comp_config = build_comp_config(base_config, comp_name)

    if comp_df.empty:
        logger.info(f"   ⚠️  No matches scraped for {comp_name}")
        return {"downloaded": 0, "skipped": 0, "transformed": 0, "status": "empty"}

    total_matches = len(comp_df)
    logger.info(f"   📊 {total_matches} match(es) in {comp_name}")
    stats = {"downloaded": 0, "skipped": 0, "transformed": 0, "status": "success"}

    # ── Download ───────────────────────────────────────────────────────────────
    if not args.transform_only and not args.skip_download:
        downloader = MatchDownloader(comp_config, logger)
        pbar = _tqdm(list(comp_df.iterrows()), total=total_matches,
                     desc=f"⬇  {comp_name[:18]}", unit="match", ncols=90, leave=True)
        for i, (_, row) in enumerate(pbar, 1):
            match_id  = str(row["match_id"])
            match_url = str(row["url_match"])
            home, away = row.get("home", ""), row.get("away", "")
            label = f"{home} vs {away}" if home and away else match_id

            pbar.set_postfix_str(label[:35], refresh=True)
            write_progress(
                team=comp_name, competition=comp_name,
                stage="Downloading", detail=label,
                current_team=comp_idx, total_teams=total_comps,
                current_match=i, total_matches=total_matches,
            )

            # Manifest skip — match already downloaded by a prior team/competition pass
            if match_id in manifest and base_config.get("downloader", {}).get("skip_existing", True):
                stats["skipped"] += 1
                continue

            logger.info(f"   [{i}/{total_matches}] {label}")
            success, _ = downloader.download_match(match_id, match_url)
            if success:
                stats["downloaded"] += 1
                manifest.add(match_id)
                save_manifest(manifest)
            else:
                stats["skipped"] += 1

    # ── Transform ──────────────────────────────────────────────────────────────
    write_progress(
        team=comp_name, competition=comp_name, stage="Transforming",
        current_team=comp_idx, total_teams=total_comps,
    )
    n  = MatchTransformer(comp_config, logger).transform_all()
    n += MatchEventTransformer(comp_config, logger).transform_all()
    LineupTransformer(comp_config, logger).transform_all()
    stats["transformed"] = n

    # ── Cleanup ────────────────────────────────────────────────────────────────
    deleted = cleanup_target_jsons(comp_config, comp_name, season, logger)
    if deleted:
        print(f"      🗑️  Cleaned up {deleted} JSON(s)")

    return stats


# ── Core: process one team × competition ─────────────────────────────────────

def process_team_competition(
    team_name: str,
    search_name: str,
    comp_name: str,
    comp_df: pd.DataFrame,
    base_config: dict,
    logger,
    args,
    team_idx: int,
    total_teams: int,
    manifest: set,
) -> dict:
    """Download + transform all matches for one team in one competition."""
    season      = base_config["season"]
    comp_config = build_comp_config(base_config, comp_name)

    team_df = filter_matches_for_team(comp_df, team_name, search_name)

    if team_df.empty:
        logger.info(f"   ⚠️  No matches found for '{team_name}' in {comp_name}")
        return {"downloaded": 0, "skipped": 0, "transformed": 0, "status": "empty"}

    total_matches = len(team_df)
    logger.info(f"   📊 {total_matches} match(es) for {team_name} in {comp_name}")
    stats = {"downloaded": 0, "skipped": 0, "transformed": 0, "status": "success"}

    # ── Download ───────────────────────────────────────────────────────────────
    if not args.transform_only and not args.skip_download:
        downloader = MatchDownloader(comp_config, logger)
        pbar = _tqdm(list(team_df.iterrows()), total=total_matches,
                     desc=f"⬇  {team_name[:18]}", unit="match", ncols=90, leave=True)
        for i, (_, row) in enumerate(pbar, 1):
            match_id  = str(row["match_id"])
            match_url = str(row["url_match"])
            home, away = row.get("home", ""), row.get("away", "")
            label = f"{home} vs {away}" if home and away else match_id

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
                stats["downloaded"] += 1
                manifest.add(match_id)
                save_manifest(manifest)
            else:
                stats["skipped"] += 1

    # ── Transform ──────────────────────────────────────────────────────────────
    write_progress(
        team=team_name, competition=comp_name, stage="Transforming",
        current_team=team_idx, total_teams=total_teams,
    )
    n  = MatchTransformer(comp_config, logger).transform_all()
    n += MatchEventTransformer(comp_config, logger).transform_all()
    LineupTransformer(comp_config, logger).transform_all()
    stats["transformed"] = n

    # ── Cleanup ────────────────────────────────────────────────────────────────
    deleted = cleanup_target_jsons(comp_config, comp_name, season, logger)
    if deleted:
        print(f"      🗑️  Cleaned up {deleted} JSON(s)")

    return stats


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="CuléVision Opta Pipeline — combined Barcelona + opponents"
    )
    parser.add_argument("--config",         default=None,
                        help="Path to config.yaml")
    parser.add_argument("--team",           type=str, default=None,
                        help="Process only this team (e.g. 'Barcelona', 'Real Madrid')")
    parser.add_argument("--competition",    type=str, default=None,
                        help="Process only this competition key")
    parser.add_argument("--transform-only", action="store_true",
                        help="Skip download; re-transform existing JSONs only")
    parser.add_argument("--skip-download",  action="store_true",
                        help="Scrape + transform but skip browser downloads")
    parser.add_argument("--force-rescrape", action="store_true",
                        help="Ignore scrape cache; re-scrape every competition page")
    parser.add_argument("--full-competitions", action="store_true",
                        help="Download EVERY match in each competition (no per-team "
                             "filter). Use to pull whole-tournament datasets, not just "
                             "Barcelona-opponent games.")
    args = parser.parse_args()

    config = load_config(args.config)
    logger = setup_logging(config["paths"]["logs_dir"], config["logging"]["level"])
    ensure_directories(config["paths"])
    SCRAPE_CACHE.mkdir(parents=True, exist_ok=True)

    try:
        PROGRESS_FILE.unlink(missing_ok=True)
    except Exception:
        pass

    manifest  = load_manifest(Path(config["paths"]["result_dir"]))
    all_teams = config["teams"]
    all_comps = config["competitions"]
    season    = config["season"]

    # ── Apply CLI filters ──────────────────────────────────────────────────────
    if args.team:
        all_teams = [t for t in all_teams if t["team_name"] == args.team]
        if not all_teams:
            print(f"❌ Team '{args.team}' not found in config")
            sys.exit(1)

    if args.competition:
        if args.competition not in all_comps:
            print(f"❌ Competition '{args.competition}' not found in config")
            sys.exit(1)
        all_teams = [
            t for t in all_teams
            if args.competition in t.get("competitions", [])
        ]
        all_comps = {args.competition: all_comps[args.competition]}

    needed_comps = {
        comp
        for team in all_teams
        for comp in team.get("competitions", [])
        if comp in all_comps
    }
    total_teams = len(all_teams)

    print(f"\n{'='*80}")
    print("🚀 OPTA PIPELINE")
    print(f"{'='*80}")
    print(f"📊 {total_teams} team(s) | {len(needed_comps)} competition page(s) to scrape")
    print(f"📅 Season: {season}\n")

    # ─────────────────────────────────────────────────────────────────────────
    # PHASE 1 — Scrape competition pages (once each, with cache)
    # ─────────────────────────────────────────────────────────────────────────
    print(f"{'='*60}\nPHASE 1 — SCRAPING COMPETITION PAGES\n{'='*60}")

    comp_cache: dict[str, pd.DataFrame] = {}
    for comp_name in sorted(needed_comps):
        comp_info = all_comps[comp_name]
        comp_cache[comp_name] = get_scraped_matches(
            comp_name, comp_info["results_url"], config, logger,
            force_rescrape=args.force_rescrape,
        )

    # ─────────────────────────────────────────────────────────────────────────
    # PHASE 2 — Download + transform per team × competition
    # ─────────────────────────────────────────────────────────────────────────
    print(f"\n{'='*60}\nPHASE 2 — DOWNLOAD & TRANSFORM\n{'='*60}")

    all_stats = []

    # ── Full-competition mode: download every match, once per competition ────────
    if args.full_competitions:
        comp_list   = sorted(needed_comps)
        total_comps = len(comp_list)
        print(f"🌍 FULL-COMPETITION MODE — every match in {total_comps} competition(s)\n")
        for comp_idx, comp_name in enumerate(comp_list, 1):
            print(f"\n{'='*60}\n🏆 [{comp_idx}/{total_comps}] {comp_name}\n{'='*60}")
            stats = process_full_competition(
                comp_name=comp_name,
                comp_df=comp_cache[comp_name],
                base_config=config,
                logger=logger,
                args=args,
                comp_idx=comp_idx,
                total_comps=total_comps,
                manifest=manifest,
            )
            all_stats.append({"team": "ALL", "competition": comp_name, **stats})
            if stats["status"] == "empty":
                print(f"     ⚠️  No matches scraped for {comp_name}")
            else:
                print(f"     ✅ Downloaded: {stats['downloaded']} | "
                      f"Skipped: {stats['skipped']} | "
                      f"Parquets: {stats['transformed']}")

        total_dl = sum(s["downloaded"]  for s in all_stats)
        total_sk = sum(s["skipped"]     for s in all_stats)
        total_tr = sum(s["transformed"] for s in all_stats)
        print(f"\n{'='*80}\n📈 FINAL SUMMARY (full-competition mode)\n{'='*80}")
        print(f"✅ Downloaded : {total_dl}")
        print(f"⏭️  Skipped    : {total_sk}")
        print(f"🔄 Parquets   : {total_tr}")
        print(f"\n📁 Output: data/2025-26/{{country}}/{{competition}}/")
        print(f"{'='*80}\n")
        logger.info(f"✅ Downloaded: {total_dl} | Skipped: {total_sk} | Parquets: {total_tr}")
        try:
            PROGRESS_FILE.unlink(missing_ok=True)
        except Exception:
            pass
        return

    team_pbar = _tqdm(all_teams, total=total_teams,
                      desc="👤 Teams", unit="team", ncols=90)

    for team_idx, team in enumerate(team_pbar, 1):
        team_name   = team["team_name"]
        search_name = team.get("search_name")
        team_comps  = [c for c in team.get("competitions", []) if c in comp_cache]

        team_pbar.set_description(f"👤 {team_name[:25]}")
        print(f"\n{'='*60}\n👤 [{team_idx}/{total_teams}] {team_name}\n{'='*60}")

        for comp_name in team_comps:
            print(f"\n  🏆 {comp_name}")
            stats = process_team_competition(
                team_name=team_name,
                search_name=search_name,
                comp_name=comp_name,
                comp_df=comp_cache[comp_name],
                base_config=config,
                logger=logger,
                args=args,
                team_idx=team_idx,
                total_teams=total_teams,
                manifest=manifest,
            )
            all_stats.append({"team": team_name, "competition": comp_name, **stats})

            if stats["status"] == "empty":
                print(f"     ⚠️  Not in {comp_name} (0 matches found)")
            else:
                print(f"     ✅ Downloaded: {stats['downloaded']} | "
                      f"Failed: {stats['skipped']} | "
                      f"Parquets: {stats['transformed']}")

    # ── Summary ────────────────────────────────────────────────────────────────
    total_dl = sum(s["downloaded"]  for s in all_stats)
    total_sk = sum(s["skipped"]     for s in all_stats)
    total_tr = sum(s["transformed"] for s in all_stats)
    empty    = sum(1 for s in all_stats if s["status"] == "empty")

    print(f"\n{'='*80}\n📈 FINAL SUMMARY\n{'='*80}")
    print(f"✅ Downloaded : {total_dl}")
    print(f"❌ Failed     : {total_sk}")
    print(f"🔄 Parquets   : {total_tr}")
    print(f"⚠️  Empty      : {empty}  (team not found in competition)")
    print(f"\n📁 Output: data/2025-26/{{country}}/{{competition}}/")
    print(f"{'='*80}\n")

    logger.info(f"✅ Downloaded: {total_dl} | Skipped: {total_sk} | Parquets: {total_tr}")

    try:
        PROGRESS_FILE.unlink(missing_ok=True)
    except Exception:
        pass


if __name__ == "__main__":
    main()
