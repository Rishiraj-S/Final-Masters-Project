#!/usr/bin/env python3
"""
Opta Match Data Pipeline - Multi-Competition Support
Downloads matchevent → Splits into match + match_event parquets
Iterates through all configured competitions
"""

import os
import sys
import yaml
import argparse
from pathlib import Path

from modules import (
    MatchScraper,
    MatchDownloader,
    MatchTransformer,
    MatchEventTransformer,
    setup_logging,
    ensure_directories
)
from modules.utils import get_organized_path_reversed


def load_config(config_path: str = None) -> dict:
    """Load configuration from YAML file"""
    if config_path is None:
        # Default to config.yaml in the same directory as this script
        script_dir = Path(__file__).parent
        config_path = script_dir / "config.yaml"
    else:
        script_dir = Path(__file__).parent

    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)

    # Resolve all paths relative to script location if they are relative paths
    paths_to_resolve = ['data_dir', 'mappings_dir', 'target_dir', 'result_dir', 'logs_dir']
    for path_key in paths_to_resolve:
        path_value = config.get('paths', {}).get(path_key)
        if path_value and not Path(path_value).is_absolute():
            config['paths'][path_key] = str(script_dir / path_value)

    return config


def process_competition(config: dict, competition_info: dict, args, logger) -> dict:
    """
    Process a single competition through the full pipeline.

    Args:
        config: Base configuration dictionary
        competition_info: Competition-specific info (id, league_name, season, results_url)
        args: Command line arguments
        logger: Logger instance

    Returns:
        dict with processing results
    """
    import pandas as pd

    # Update config with current competition info
    config['competition'] = {
        'id': competition_info['id'],
        'league_name': competition_info['league_name'],
        'season': competition_info['season']
    }

    league_name = competition_info['league_name']
    season = competition_info['season']
    competition_id = competition_info['id']
    results_url = competition_info.get('results_url', config.get('team', {}).get('results_url'))

    results = {
        'league': league_name,
        'season': season,
        'scraped': 0,
        'downloaded': 0,
        'skipped': 0,
        'match_transformed': 0,
        'event_transformed': 0,
        'status': 'success'
    }

    try:
        # ============================================================
        # TRANSFORM ONLY MODE
        # ============================================================
        if args.transform_only:
            logger.info("🔄 TRANSFORMING EXISTING DATA")

            # Transform match info
            logger.info("📋 Transforming Match Info...")
            match_transformer = MatchTransformer(config, logger)
            results['match_transformed'] = match_transformer.transform_all()

            # Transform match events
            logger.info("⚽ Transforming Match Events...")
            event_transformer = MatchEventTransformer(config, logger)
            results['event_transformed'] = event_transformer.transform_all()

            return results

        # ============================================================
        # FULL PIPELINE
        # ============================================================

        # Step 1: Scraping
        if not args.skip_scraping:
            logger.info("🔍 Scraping match URLs...")

            scraper = MatchScraper(config, logger)

            try:
                matches_df = scraper.scrape_matches(
                    results_url,
                    config['team']['name']
                )

                if not matches_df.empty:
                    matches_csv_path = get_organized_path_reversed(
                        config['paths']['result_dir'],
                        league_name,
                        season,
                        'matches_urls.csv'
                    )
                    matches_df.to_csv(matches_csv_path, index=False)
                    results['scraped'] = len(matches_df)
                    logger.info(f"💾 Saved {len(matches_df)} matches to: {matches_csv_path}")

            except Exception as e:
                logger.error(f"❌ Scraping failed: {e}")
                logger.info("💡 Continuing with existing data...")

        # Step 2: Downloading
        if not args.skip_download:
            logger.info("⬇️  Downloading match data...")

            matches_csv_path = get_organized_path_reversed(
                config['paths']['result_dir'],
                league_name,
                season,
                'matches_urls.csv'
            )

            if os.path.exists(matches_csv_path):
                matches_df = pd.read_csv(matches_csv_path)

                downloader = MatchDownloader(config, logger)

                total = len(matches_df)
                downloaded = 0
                skipped = 0

                for idx, row in matches_df.iterrows():
                    match_id = row['match_id']
                    match_url = row['url_match']

                    logger.info(f"[{idx + 1}/{total}] Match: {match_id}")

                    success, result_path = downloader.download_match(match_id, match_url, competition_id)

                    if success:
                        downloaded += 1
                    else:
                        skipped += 1

                results['downloaded'] = downloaded
                results['skipped'] = skipped
                logger.info(f"📊 Downloaded: {downloaded}, Skipped: {skipped}")
            else:
                logger.warning(f"No matches CSV found at: {matches_csv_path}")

        # Step 3: Transformation
        logger.info("🔄 Transforming data to parquet...")

        # Transform match info
        logger.info("📋 Transforming Match Info...")
        match_transformer = MatchTransformer(config, logger)
        results['match_transformed'] = match_transformer.transform_all()

        # Transform match events
        logger.info("⚽ Transforming Match Events...")
        event_transformer = MatchEventTransformer(config, logger)
        results['event_transformed'] = event_transformer.transform_all()

    except Exception as e:
        logger.error(f"❌ Error processing {league_name}: {e}")
        results['status'] = 'failed'
        import traceback
        logger.error(traceback.format_exc())

    return results


def main():
    """Main pipeline execution - iterates through all competitions"""
    parser = argparse.ArgumentParser(description='Opta Match Data Pipeline - Multi-Competition')
    parser.add_argument('--config', default=None, help='Path to config file (defaults to config.yaml in script directory)')
    parser.add_argument('--skip-scraping', action='store_true', help='Skip scraping step')
    parser.add_argument('--skip-download', action='store_true', help='Skip download step')
    parser.add_argument('--transform-only', action='store_true', help='Only transform existing JSONs')
    parser.add_argument('--competition', type=str, help='Process only a specific competition by league_name')

    args = parser.parse_args()

    # Load configuration
    try:
        config = load_config(args.config)
    except Exception as e:
        print(f"❌ Failed to load config: {e}")
        sys.exit(1)

    # Setup logging
    logger = setup_logging(
        config['paths']['logs_dir'],
        config['logging']['level']
    )

    # Ensure directories exist
    ensure_directories(config['paths'])

    # Get competitions list
    competitions = config.get('competitions', [])

    # Fallback to single competition if 'competitions' list is not defined
    if not competitions:
        competition = config.get('competition', {})
        if competition:
            competitions = [{
                'id': competition.get('id'),
                'league_name': competition.get('league_name'),
                'season': competition.get('season'),
                'results_url': config.get('team', {}).get('results_url')
            }]

    # Filter to specific competition if requested
    if args.competition:
        competitions = [c for c in competitions if c['league_name'] == args.competition]
        if not competitions:
            print(f"❌ Competition '{args.competition}' not found in config")
            sys.exit(1)

    if not competitions:
        print("❌ No competitions configured")
        sys.exit(1)

    # Display header
    print("\n" + "="*80)
    print("🚀 OPTA PIPELINE - MULTI-COMPETITION MODE")
    print("="*80)
    logger.info("="*80)
    logger.info("🚀 OPTA PIPELINE - MULTI-COMPETITION MODE")
    logger.info("="*80)

    total_competitions = len(competitions)
    print(f"\n📊 Processing {total_competitions} competition(s):")
    logger.info(f"📊 Processing {total_competitions} competition(s):")

    for comp in competitions:
        print(f"   • {comp['league_name']} ({comp['season']})")
        logger.info(f"   • {comp['league_name']} ({comp['season']})")
    print()

    # Process each competition
    all_results = []

    for idx, competition_info in enumerate(competitions, 1):
        league_name = competition_info['league_name']
        season = competition_info['season']

        print("\n" + "="*80)
        print(f"🏆 COMPETITION {idx}/{total_competitions}: {league_name}")
        print(f"📅 Season: {season}")
        print("="*80)
        logger.info("="*80)
        logger.info(f"🏆 COMPETITION {idx}/{total_competitions}: {league_name}")
        logger.info(f"📅 Season: {season}")
        logger.info("="*80)

        results = process_competition(config, competition_info, args, logger)
        all_results.append(results)

        if results['status'] == 'success':
            print(f"\n✅ {league_name} completed successfully")
            if not args.transform_only:
                print(f"   Scraped: {results['scraped']}")
                print(f"   Downloaded: {results['downloaded']}")
            print(f"   Match files: {results['match_transformed']}")
            print(f"   Event files: {results['event_transformed']}")
        else:
            print(f"\n❌ {league_name} failed")

    # Final summary
    print("\n" + "="*80)
    print("📈 FINAL SUMMARY - ALL COMPETITIONS")
    print("="*80)
    logger.info("="*80)
    logger.info("📈 FINAL SUMMARY - ALL COMPETITIONS")
    logger.info("="*80)

    successful = [r for r in all_results if r['status'] == 'success']
    failed = [r for r in all_results if r['status'] == 'failed']

    print(f"\n✅ Successful: {len(successful)}/{total_competitions}")
    print(f"❌ Failed: {len(failed)}/{total_competitions}")

    if not args.transform_only:
        total_scraped = sum(r['scraped'] for r in all_results)
        total_downloaded = sum(r['downloaded'] for r in all_results)
        print(f"\n📊 Scraping & Download:")
        print(f"   Total scraped: {total_scraped}")
        print(f"   Total downloaded: {total_downloaded}")

    total_match = sum(r['match_transformed'] for r in all_results)
    total_event = sum(r['event_transformed'] for r in all_results)
    print(f"\n🔄 Transformation:")
    print(f"   Match parquets: {total_match}")
    print(f"   Event parquets: {total_event}")

    print("\n📁 Output directories:")
    for comp in competitions:
        print(f"   data/result/{comp['league_name']}/{comp['season']}/")

    print("="*80)
    print()

    logger.info(f"✅ Successful: {len(successful)}/{total_competitions}")
    logger.info(f"❌ Failed: {len(failed)}/{total_competitions}")
    logger.info(f"Match parquets: {total_match}")
    logger.info(f"Event parquets: {total_event}")


if __name__ == "__main__":
    main()