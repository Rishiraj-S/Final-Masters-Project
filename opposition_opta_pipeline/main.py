#!/usr/bin/env python3
"""
Opposition Opta Pipeline — Multi-Competition Support

Processes 46 European leagues/competitions already stored in opposition_data/.

Stages per competition:
  1. Scrape   — Update matches_ids.csv with newly played matches (Scoresway)
  2. Download — Download partidos/*.json for any matches not yet captured
  3. Transform— Convert partidos/*.json → Parquet in data/result/

All partidos JSONs are kept permanently (no cleanup step).
"""

import os
import sys
import json
import yaml
import argparse
from pathlib import Path

import pandas as pd

from modules import (
    MatchScraper,
    OppositionDownloader,
    MatchTransformer,
    MatchEventTransformer,
    LineupTransformer,
    setup_logging,
    ensure_directories,
)


# ── Progress file (for UI polling) ───────────────────────────────────────────
PROGRESS_FILE = Path(__file__).parent / "logs" / "progress.json"


def write_progress(
    competition: str = "",
    stage: str = "",
    detail: str = "",
    current_competition: int = 0,
    total_competitions: int = 0,
    current_match: int = 0,
    total_matches: int = 0,
    status: str = "running",
):
    progress = {
        "competition": competition,
        "stage": stage,
        "detail": detail,
        "status": status,
        "current_competition": current_competition,
        "total_competitions": total_competitions,
        "current_match": current_match,
        "total_matches": total_matches,
    }
    try:
        PROGRESS_FILE.parent.mkdir(parents=True, exist_ok=True)
        tmp = PROGRESS_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(progress), encoding="utf-8")
        tmp.rename(PROGRESS_FILE)
    except Exception as e:
        import logging as _log
        _log.getLogger(__name__).warning(f"Could not write progress.json: {e}")


# ── Config loading ────────────────────────────────────────────────────────────

def load_config(config_path: str = None) -> dict:
    """Load YAML config, resolving relative paths relative to script directory."""
    script_dir = Path(__file__).parent
    if config_path is None:
        config_path = script_dir / "config.yaml"

    with open(config_path, "r") as f:
        config = yaml.safe_load(f)

    paths_to_resolve = ["opposition_data_dir", "result_dir", "mappings_dir", "logs_dir"]
    for key in paths_to_resolve:
        val = config.get("paths", {}).get(key)
        if val and not Path(val).is_absolute():
            config["paths"][key] = str(script_dir / val)

    return config


# ── results_url discovery ─────────────────────────────────────────────────────

def discover_results_url(opposition_data_dir: str, league_name: str, season: str) -> str:
    """
    Auto-derive the Scoresway results URL from the existing matches_ids.csv.
    Extracts base URL from the first link_partido entry:
      https://www.scoresway.com/.../match/view/{id}
      → https://www.scoresway.com/.../results
    Returns empty string if not derivable.
    """
    csv_path = Path(opposition_data_dir) / league_name / season / "matches_ids.csv"
    if not csv_path.exists():
        return ""
    try:
        df = pd.read_csv(csv_path)
        if df.empty or "link_partido" not in df.columns:
            return ""
        sample = df["link_partido"].dropna().iloc[0]
        if "/match/view/" in sample:
            base = sample.split("/match/view/")[0]
            return base.rstrip("/") + "/results"
        # fallback: try trimming last two path segments
        parts = sample.rstrip("/").rsplit("/", 2)
        if len(parts) >= 3:
            return parts[0].rstrip("/") + "/results"
    except Exception:
        pass
    return ""


# ── Core competition processor ────────────────────────────────────────────────

def process_competition(config: dict, competition_info: dict, args, logger) -> dict:
    """
    Run the full pipeline (scrape → download → transform) for one competition.
    Returns a results dict.
    """
    config["competition"] = {
        "league_name": competition_info["league_name"],
        "season": competition_info["season"],
    }

    league_name = competition_info["league_name"]
    season = competition_info["season"]
    opposition_data_dir = config["paths"]["opposition_data_dir"]
    comp_idx = competition_info.get("_idx", 0)
    comp_total = competition_info.get("_total", 0)
    display_name = league_name.replace("_", " ")

    results = {
        "league": league_name,
        "season": season,
        "scraped": 0,
        "downloaded": 0,
        "skipped": 0,
        "match_transformed": 0,
        "event_transformed": 0,
        "lineup_transformed": 0,
        "status": "success",
    }

    try:
        # ── Path to existing matches_ids.csv ──────────────────────────────
        matches_csv_path = Path(opposition_data_dir) / league_name / season / "matches_ids.csv"

        # ============================================================
        # TRANSFORM ONLY MODE
        # ============================================================
        if args.transform_only:
            logger.info("🔄 TRANSFORMING EXISTING DATA")

            write_progress(display_name, "Transforming", "Match info", comp_idx, comp_total)
            results["match_transformed"] = MatchTransformer(config, logger).transform_all()

            write_progress(display_name, "Transforming", "Match events", comp_idx, comp_total)
            results["event_transformed"] = MatchEventTransformer(config, logger).transform_all()

            write_progress(display_name, "Transforming", "Lineups", comp_idx, comp_total)
            results["lineup_transformed"] = LineupTransformer(config, logger).transform_all()

            return results

        # ============================================================
        # FULL PIPELINE
        # ============================================================

        # ── Step 1: Scraping ──────────────────────────────────────────
        if not args.skip_scraping:
            logger.info("🔍 Scraping match URLs...")
            write_progress(display_name, "Scraping", "Fetching match URLs", comp_idx, comp_total)

            results_url = competition_info.get("results_url") or discover_results_url(
                opposition_data_dir, league_name, season
            )

            if not results_url:
                logger.warning(f"⚠️  No results_url found for {league_name} — skipping scraping")
            else:
                scraper = MatchScraper(config, logger)
                try:
                    # Scrape with no team filter → all league matches
                    new_df = scraper.scrape_matches(results_url, team_name=None)

                    if not new_df.empty:
                        # Rename columns to match matches_ids.csv convention
                        rename_map = {
                            "match_id":  "id",
                            "url_match": "link_partido",
                            "home":      "equipo_local",
                            "away":      "equipo_visitante",
                        }
                        new_df = new_df.rename(columns=rename_map)
                        new_df["season"] = season
                        new_df["liga"]   = league_name
                        new_df["source"] = "results"

                        if matches_csv_path.exists():
                            existing_df = pd.read_csv(matches_csv_path)
                            merged_df = pd.concat([existing_df, new_df], ignore_index=True)
                            merged_df = merged_df.drop_duplicates(subset=["id"], keep="last")
                            new_count = len(merged_df) - len(existing_df)
                            if new_count > 0:
                                logger.info(f"🆕 Found {new_count} new match(es)")
                            matches_df = merged_df
                        else:
                            matches_df = new_df

                        matches_df.to_csv(matches_csv_path, index=False)
                        results["scraped"] = len(matches_df)
                        logger.info(f"💾 Saved {len(matches_df)} total matches to: {matches_csv_path}")

                except Exception as e:
                    logger.error(f"❌ Scraping failed: {e}")
                    logger.info("💡 Continuing with existing data...")
                    write_progress(display_name, "Scraping failed – using existing data",
                                   str(e)[:120], comp_idx, comp_total, status="warning")

        # ── Step 2: Downloading ───────────────────────────────────────
        if not args.skip_download:
            logger.info("⬇️  Downloading match data...")

            if not matches_csv_path.exists():
                logger.warning(f"No matches_ids.csv found at: {matches_csv_path}")
            else:
                matches_df = pd.read_csv(matches_csv_path)
                downloader = OppositionDownloader(config, logger)

                total = len(matches_df)
                downloaded = skipped = 0
                failed_matches = []

                for idx, row in matches_df.iterrows():
                    match_id  = str(row.get("id", "")).strip()
                    match_url = str(row.get("link_partido", "")).strip()

                    if not match_id or not match_url:
                        continue

                    home  = str(row.get("equipo_local", ""))
                    away  = str(row.get("equipo_visitante", ""))
                    label = f"{home} vs {away}" if home and away else match_id

                    write_progress(display_name, "Downloading", label,
                                   comp_idx, comp_total, idx + 1, total)
                    logger.info(f"[{idx + 1}/{total}] Match: {match_id}")

                    success, _ = downloader.download_match(match_id, match_url)

                    if success:
                        downloaded += 1
                    else:
                        skipped += 1
                        failed_matches.append(label)

                results["downloaded"] = downloaded
                results["skipped"]    = skipped
                if failed_matches:
                    logger.warning(f"⚠️  Failed downloads: {', '.join(failed_matches)}")
                logger.info(f"📊 Downloaded: {downloaded}, Failed: {skipped}")

        # ── Step 3: Transformation ────────────────────────────────────
        logger.info("🔄 Transforming data to Parquet...")

        write_progress(display_name, "Transforming", "Match info", comp_idx, comp_total)
        logger.info("📋 Transforming Match Info...")
        results["match_transformed"] = MatchTransformer(config, logger).transform_all()

        write_progress(display_name, "Transforming", "Match events", comp_idx, comp_total)
        logger.info("⚽ Transforming Match Events...")
        results["event_transformed"] = MatchEventTransformer(config, logger).transform_all()

        write_progress(display_name, "Transforming", "Lineups", comp_idx, comp_total)
        logger.info("👥 Transforming Lineups...")
        results["lineup_transformed"] = LineupTransformer(config, logger).transform_all()

    except Exception as e:
        logger.error(f"❌ Error processing {league_name}: {e}")
        results["status"] = "failed"
        import traceback
        logger.error(traceback.format_exc())

    return results


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    """Main pipeline — iterates all configured competitions."""
    parser = argparse.ArgumentParser(
        description="Opposition Opta Pipeline — Multi-Competition"
    )
    parser.add_argument("--config", default=None, help="Path to config file")
    parser.add_argument("--skip-scraping", action="store_true", help="Skip scraping step")
    parser.add_argument("--skip-download", action="store_true", help="Skip download step")
    parser.add_argument("--transform-only", action="store_true", help="Only transform existing JSONs")
    parser.add_argument("--competition", type=str, help="Process only a specific league_name")
    args = parser.parse_args()

    # Load config
    try:
        config = load_config(args.config)
    except Exception as e:
        print(f"❌ Failed to load config: {e}")
        sys.exit(1)

    # Setup logging
    logger = setup_logging(config["paths"]["logs_dir"], config["logging"]["level"])

    # Ensure output directories exist
    ensure_directories({
        "result_dir": config["paths"]["result_dir"],
        "logs_dir":   config["paths"]["logs_dir"],
    })

    # Get competitions
    competitions = config.get("competitions", [])
    if not competitions:
        print("❌ No competitions configured")
        sys.exit(1)

    # Filter to single competition if requested
    if args.competition:
        competitions = [c for c in competitions if c["league_name"] == args.competition]
        if not competitions:
            print(f"❌ Competition '{args.competition}' not found in config")
            sys.exit(1)

    # Clean up any stale progress file
    try:
        PROGRESS_FILE.unlink(missing_ok=True)
    except Exception:
        pass

    # Header
    total_competitions = len(competitions)
    print("\n" + "=" * 80)
    print("🚀 OPPOSITION PIPELINE — MULTI-COMPETITION MODE")
    print("=" * 80)
    print(f"\n📊 Processing {total_competitions} competition(s):")
    for comp in competitions:
        print(f"   • {comp['league_name']} ({comp['season']})")
    print()

    logger.info("=" * 80)
    logger.info("🚀 OPPOSITION PIPELINE — MULTI-COMPETITION MODE")
    logger.info("=" * 80)
    logger.info(f"📊 Processing {total_competitions} competition(s)")

    all_results = []

    for idx, competition_info in enumerate(competitions, 1):
        league_name = competition_info["league_name"]
        season = competition_info["season"]
        competition_info["_idx"]   = idx
        competition_info["_total"] = total_competitions

        print("\n" + "=" * 80)
        print(f"🏆 COMPETITION {idx}/{total_competitions}: {league_name}")
        print(f"📅 Season: {season}")
        print("=" * 80)
        logger.info(f"🏆 COMPETITION {idx}/{total_competitions}: {league_name}")

        results = process_competition(config, competition_info, args, logger)
        all_results.append(results)

        if results["status"] == "success":
            print(f"\n✅ {league_name} completed successfully")
            if not args.transform_only:
                print(f"   Scraped:    {results['scraped']}")
                print(f"   Downloaded: {results['downloaded']}")
            print(f"   Match files:  {results['match_transformed']}")
            print(f"   Event files:  {results['event_transformed']}")
            print(f"   Lineup files: {results['lineup_transformed']}")
        else:
            print(f"\n❌ {league_name} failed")

    # Final summary
    print("\n" + "=" * 80)
    print("📈 FINAL SUMMARY — ALL COMPETITIONS")
    print("=" * 80)

    successful = [r for r in all_results if r["status"] == "success"]
    failed     = [r for r in all_results if r["status"] == "failed"]

    print(f"\n✅ Successful: {len(successful)}/{total_competitions}")
    print(f"❌ Failed:     {len(failed)}/{total_competitions}")

    if not args.transform_only:
        print(f"\n📊 Scraping & Download:")
        print(f"   Total scraped:    {sum(r['scraped'] for r in all_results)}")
        print(f"   Total downloaded: {sum(r['downloaded'] for r in all_results)}")

    total_match   = sum(r["match_transformed"]   for r in all_results)
    total_event   = sum(r["event_transformed"]   for r in all_results)
    total_lineup  = sum(r["lineup_transformed"]  for r in all_results)
    print(f"\n🔄 Transformation:")
    print(f"   Match parquets:  {total_match}")
    print(f"   Event parquets:  {total_event}")
    print(f"   Lineup parquets: {total_lineup}")

    print("\n📁 Output directory:")
    print(f"   {config['paths']['result_dir']}/{{league}}/{{season}}/")
    print("=" * 80 + "\n")

    logger.info(f"✅ Successful: {len(successful)}/{total_competitions}")
    logger.info(f"❌ Failed: {len(failed)}/{total_competitions}")
    logger.info(f"Match parquets:  {total_match}")
    logger.info(f"Event parquets:  {total_event}")
    logger.info(f"Lineup parquets: {total_lineup}")

    # Clean up progress file
    try:
        PROGRESS_FILE.unlink(missing_ok=True)
    except Exception:
        pass


if __name__ == "__main__":
    main()
