#!/usr/bin/env python3
"""
Process ALL leagues and seasons in data/target directory
Automatically discovers all tournaments and seasons
"""
import os
import yaml
from pathlib import Path
from modules import (
    MatchTransformer,
    MatchEventTransformer,
    setup_logging,
    ensure_directories
)


def load_config(config_path: str = "config.yaml") -> dict:
    """Load configuration from YAML file"""
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)


def get_all_leagues_and_seasons(target_dir: str = "data/target") -> dict:
    """
    Discover all leagues and seasons in target directory
    
    Returns:
        {
            'Spain_Primera_Division': ['2008-2009', '2009-2010', ...],
            'Liga_F': ['2021-2022', '2022-2023', ...],
            ...
        }
    """
    target_path = Path(target_dir)
    
    if not target_path.exists():
        return {}
    
    leagues = {}
    
    # Iterate through all league directories
    for league_dir in target_path.iterdir():
        if not league_dir.is_dir() or league_dir.name.startswith('.'):
            continue
        
        league_name = league_dir.name
        seasons = []
        
        # Iterate through all season directories
        for season_dir in league_dir.iterdir():
            if not season_dir.is_dir() or season_dir.name.startswith('.'):
                continue
            
            # Check if it has matchdata subdirectory with JSON files
            matchdata_path = season_dir / 'matchdata'
            if matchdata_path.exists():
                json_files = list(matchdata_path.glob('*.json'))
                if json_files:
                    seasons.append(season_dir.name)
        
        if seasons:
            leagues[league_name] = sorted(seasons)
    
    return leagues


def process_season(league_name: str, season: str, config: dict, logger) -> dict:
    """Process a single season"""
    # Update config for this season
    config['competition']['league_name'] = league_name
    config['competition']['season'] = season
    
    # Count JSON files
    matchdata_dir = Path(config['paths']['target_dir']) / league_name / season / 'matchdata'
    json_files = list(matchdata_dir.glob('*.json'))
    
    logger.info(f"   📁 Found {len(json_files)} JSON files")
    
    results = {
        'league': league_name,
        'season': season,
        'total_files': len(json_files),
        'match_success': 0,
        'event_success': 0,
        'status': 'success'
    }
    
    try:
        # Transform match info
        logger.info(f"   📋 Transforming Match Info...")
        match_transformer = MatchTransformer(config, logger)
        results['match_success'] = match_transformer.transform_all()
        
        # Transform match events
        logger.info(f"   ⚽ Transforming Match Events...")
        event_transformer = MatchEventTransformer(config, logger)
        results['event_success'] = event_transformer.transform_all()
        
    except Exception as e:
        logger.error(f"   ❌ Error: {e}")
        results['status'] = 'failed'
    
    return results


def main():
    """Main batch processing function"""
    # Load base configuration
    config = load_config("config.yaml")
    
    # Setup logging
    logger = setup_logging(
        config['paths']['logs_dir'],
        config['logging']['level']
    )
    
    # Ensure directories exist
    ensure_directories(config['paths'])
    
    print("\n" + "="*80)
    print("🚀 BATCH PROCESSING - ALL TOURNAMENTS & SEASONS")
    print("="*80)
    logger.info("="*80)
    logger.info("🚀 BATCH PROCESSING - ALL TOURNAMENTS & SEASONS")
    logger.info("="*80)
    
    # Discover all leagues and seasons
    leagues_and_seasons = get_all_leagues_and_seasons(config['paths']['target_dir'])
    
    if not leagues_and_seasons:
        print("\n❌ No tournaments/seasons found in data/target/")
        print("\n💡 Expected structure:")
        print("   data/target/Spain_Primera_Division/2008-2009/matchdata/*.json")
        print("   data/target/Liga_F/2021-2022/matchdata/*.json")
        print("   data/target/Champions_League/2024-2025/matchdata/*.json")
        logger.error("No tournaments/seasons found in data/target/")
        return
    
    # Calculate totals
    total_leagues = len(leagues_and_seasons)
    total_seasons = sum(len(seasons) for seasons in leagues_and_seasons.values())
    
    print(f"\n✅ Discovered:")
    print(f"   • {total_leagues} tournament(s)")
    print(f"   • {total_seasons} season(s) total")
    print()
    logger.info(f"\n✅ Discovered {total_leagues} tournament(s), {total_seasons} season(s) total\n")
    
    # Show what will be processed
    for league, seasons in sorted(leagues_and_seasons.items()):
        print(f"📊 {league}:")
        for season in seasons:
            matchdata_dir = Path(config['paths']['target_dir']) / league / season / 'matchdata'
            json_count = len(list(matchdata_dir.glob('*.json')))
            print(f"   • {season} ({json_count} matches)")
        print()
        
        logger.info(f"📊 {league}:")
        for season in seasons:
            matchdata_dir = Path(config['paths']['target_dir']) / league / season / 'matchdata'
            json_count = len(list(matchdata_dir.glob('*.json')))
            logger.info(f"   • {season} ({json_count} matches)")
    
    # Confirm before processing
    print("-"*80)
    response = input("\n▶️  Press ENTER to start processing (or Ctrl+C to cancel): ")
    print()
    
    # Process all leagues and seasons
    all_results = []
    league_counter = 0
    season_counter = 0
    
    for league, seasons in sorted(leagues_and_seasons.items()):
        league_counter += 1
        
        print("\n" + "="*80)
        print(f"🏆 TOURNAMENT {league_counter}/{total_leagues}: {league}")
        print("="*80)
        logger.info("\n" + "="*80)
        logger.info(f"🏆 TOURNAMENT {league_counter}/{total_leagues}: {league}")
        logger.info("="*80)
        
        for season in seasons:
            season_counter += 1
            
            print(f"\n📅 Season {season_counter}/{total_seasons}: {league} / {season}")
            print("-"*80)
            logger.info(f"\n📅 Season {season_counter}/{total_seasons}: {league} / {season}")
            logger.info("-"*80)
            
            try:
                results = process_season(league, season, config, logger)
                all_results.append(results)
                
                if results['status'] == 'success':
                    print(f"   ✅ Match: {results['match_success']}/{results['total_files']}")
                    print(f"   ✅ Events: {results['event_success']}/{results['total_files']}")
                    logger.info(f"   ✅ Match: {results['match_success']}/{results['total_files']}")
                    logger.info(f"   ✅ Events: {results['event_success']}/{results['total_files']}")
                else:
                    print(f"   ❌ Failed to process")
                    logger.error(f"   ❌ Failed to process")
                    
            except Exception as e:
                print(f"   ❌ Error: {e}")
                logger.error(f"   ❌ Error: {e}")
                import traceback
                logger.error(traceback.format_exc())
                continue
    
    # Final summary
    print("\n" + "="*80)
    print("✅ BATCH PROCESSING COMPLETE!")
    print("="*80)
    logger.info("\n" + "="*80)
    logger.info("✅ BATCH PROCESSING COMPLETE!")
    logger.info("="*80)
    
    # Summary by league
    print("\n📊 SUMMARY BY TOURNAMENT:")
    print("="*80)
    logger.info("\n📊 SUMMARY BY TOURNAMENT:")
    logger.info("="*80)
    
    for league in sorted(leagues_and_seasons.keys()):
        league_results = [r for r in all_results if r['league'] == league]
        
        if not league_results:
            continue
        
        total_json = sum(r['total_files'] for r in league_results)
        total_match = sum(r['match_success'] for r in league_results)
        total_events = sum(r['event_success'] for r in league_results)
        seasons_processed = len(league_results)
        
        print(f"\n🏆 {league}")
        print(f"   Seasons: {seasons_processed}")
        print(f"   Matches: {total_json}")
        print(f"   Match Parquets: {total_match}")
        print(f"   Event Parquets: {total_events}")
        
        logger.info(f"\n🏆 {league}")
        logger.info(f"   Seasons: {seasons_processed}")
        logger.info(f"   Matches: {total_json}")
        logger.info(f"   Match Parquets: {total_match}")
        logger.info(f"   Event Parquets: {total_events}")
    
    # Grand totals
    print("\n" + "="*80)
    print("📈 GRAND TOTALS:")
    print("="*80)
    
    grand_total_json = sum(r['total_files'] for r in all_results)
    grand_total_match = sum(r['match_success'] for r in all_results)
    grand_total_events = sum(r['event_success'] for r in all_results)
    
    print(f"   Tournaments: {total_leagues}")
    print(f"   Seasons: {total_seasons}")
    print(f"   Total Matches: {grand_total_json}")
    print(f"   Match Parquets: {grand_total_match}")
    print(f"   Event Parquets: {grand_total_events}")
    
    logger.info("\n" + "="*80)
    logger.info("📈 GRAND TOTALS:")
    logger.info("="*80)
    logger.info(f"   Tournaments: {total_leagues}")
    logger.info(f"   Seasons: {total_seasons}")
    logger.info(f"   Total Matches: {grand_total_json}")
    logger.info(f"   Match Parquets: {grand_total_match}")
    logger.info(f"   Event Parquets: {grand_total_events}")
    
    print("\n📁 Output directory: data/result/")
    print("="*80)
    print()
    logger.info("\n📁 Output directory: data/result/")
    logger.info("="*80)


if __name__ == "__main__":
    main()