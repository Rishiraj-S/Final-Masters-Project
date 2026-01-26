#!/usr/bin/env python3
"""
Opta Match Data Pipeline - FC Barcelona
Downloads matchevent → Splits into match + match_event parquets
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


def load_config(config_path: str = "config.yaml") -> dict:
    """Load configuration from YAML file"""
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)


def main():
    """Main pipeline execution"""
    parser = argparse.ArgumentParser(description='Opta Match Data Pipeline')
    parser.add_argument('--config', default='config.yaml', help='Path to config file')
    parser.add_argument('--skip-scraping', action='store_true', help='Skip scraping step')
    parser.add_argument('--skip-download', action='store_true', help='Skip download step')
    parser.add_argument('--transform-only', action='store_true', help='Only transform existing JSONs')
    
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
    
    logger.info("="*60)
    logger.info("🚀 OPTA PIPELINE - FC BARCELONA")
    logger.info("="*60)
    
    # Ensure directories exist
    ensure_directories(config['paths'])
    
    # Get league and season
    competition = config.get('competition', {})
    league_name = competition.get('league_name', 'Unknown_League')
    season = competition.get('season', 'Unknown_Season')
    
    logger.info(f"📊 League: {league_name}")
    logger.info(f"📅 Season: {season}")
    
    # ============================================================
    # TRANSFORM ONLY MODE
    # ============================================================
    
    if args.transform_only:
        logger.info("\n" + "="*60)
        logger.info("🔄 TRANSFORMING EXISTING DATA")
        logger.info("="*60)
        
        # Transform match info
        logger.info("\n📋 Transforming Match Info...")
        match_transformer = MatchTransformer(config, logger)
        match_count = match_transformer.transform_all()
        
        # Transform match events
        logger.info("\n⚽ Transforming Match Events...")
        event_transformer = MatchEventTransformer(config, logger)
        event_count = event_transformer.transform_all()
        
        logger.info("\n✅ TRANSFORMATION COMPLETE!")
        logger.info(f"   Match: {match_count} files")
        logger.info(f"   Match Events: {event_count} files")
        return
    
    # ============================================================
    # FULL PIPELINE
    # ============================================================
    
    import pandas as pd
    
    # Step 1: Scraping
    if not args.skip_scraping:
        logger.info("\n" + "="*60)
        logger.info("🔍 STEP 1: SCRAPING MATCH URLS")
        logger.info("="*60)
        
        scraper = MatchScraper(config, logger)
        
        try:
            matches_df = scraper.scrape_matches(
                config['team']['results_url'],
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
                logger.info(f"💾 Saved matches to: {matches_csv_path}")
                logger.info(f"   Total matches: {len(matches_df)}")
            
        except Exception as e:
            logger.error(f"❌ Scraping failed: {e}")
            logger.info("💡 Continuing with existing data...")
    
    # Step 2: Downloading
    if not args.skip_download:
        logger.info("\n" + "="*60)
        logger.info("⬇️  STEP 2: DOWNLOADING MATCH DATA")
        logger.info("="*60)
        
        matches_csv_path = get_organized_path_reversed(
            config['paths']['result_dir'],
            league_name,
            season,
            'matches_urls.csv'
        )
        
        if os.path.exists(matches_csv_path):
            matches_df = pd.read_csv(matches_csv_path)
            
            downloader = MatchDownloader(config, logger)
            competition_id = config.get('competition', {}).get('id')
            
            total = len(matches_df)
            downloaded = 0
            skipped = 0
            
            for idx, row in matches_df.iterrows():
                match_id = row['match_id']
                match_url = row['url_match']
                
                logger.info(f"\n[{idx + 1}/{total}] Match: {match_id}")
                
                success, result_path = downloader.download_match(match_id, match_url, competition_id)
                
                if success:
                    downloaded += 1
                else:
                    skipped += 1
            
            logger.info(f"\n" + "="*60)
            logger.info("📊 DOWNLOAD SUMMARY")
            logger.info("="*60)
            logger.info(f"Total matches: {total}")
            logger.info(f"Downloaded: {downloaded}")
            logger.info(f"Skipped: {skipped}")
        else:
            logger.warning(f"No matches CSV found at: {matches_csv_path}")
    
    # Step 3: Transformation
    logger.info("\n" + "="*60)
    logger.info("🔄 STEP 3: TRANSFORMING DATA TO PARQUET")
    logger.info("="*60)
    
    # Transform match info
    logger.info("\n📋 Transforming Match Info...")
    match_transformer = MatchTransformer(config, logger)
    match_count = match_transformer.transform_all()
    
    # Transform match events
    logger.info("\n⚽ Transforming Match Events...")
    event_transformer = MatchEventTransformer(config, logger)
    event_count = event_transformer.transform_all()
    
    # Final summary
    logger.info("\n" + "="*60)
    logger.info("✅ PIPELINE COMPLETE!")
    logger.info("="*60)
    logger.info(f"\n📁 Results: data/result/{league_name}/{season}/")
    logger.info(f"\nTransformation Summary:")
    logger.info(f"  - Match: {match_count} files")
    logger.info(f"  - Match Events: {event_count} files")
    logger.info(f"\n📂 Directory Structure:")
    logger.info(f"  data/target/{league_name}/{season}/")
    logger.info(f"  └── matchdata/          (Raw JSON files)")
    logger.info(f"\n  data/result/{league_name}/{season}/")
    logger.info(f"  ├── matches_urls.csv")
    logger.info(f"  ├── match/              (Match metadata)")
    logger.info(f"  └── match_event/        (Event-level data)")


if __name__ == "__main__":
    main()