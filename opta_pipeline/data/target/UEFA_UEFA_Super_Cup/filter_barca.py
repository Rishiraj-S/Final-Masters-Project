import os
import json
import shutil
import re
from pathlib import Path

def strip_jsonp_wrapper(content):
    """Remove JSONP wrapper if present and return clean JSON string."""
    jsonp_pattern = r'^[a-zA-Z0-9_]+\((.*)\)$'
    match = re.match(jsonp_pattern, content.strip(), re.DOTALL)
    
    if match:
        return match.group(1)
    return content

def filter_barcelona_matches(base_dir, output_base_dir, competition_name="Unknown"):
    """
    Filter and copy Barcelona match event data files from season directories.
    Handles both pure JSON and JSONP-wrapped formats.
    
    Args:
        base_dir: Path to the directory containing season folders
        output_base_dir: Path to the output directory
        competition_name: Name of the competition for display purposes
    """
    base_path = Path(base_dir)
    output_path = Path(output_base_dir)
    
    # Get all season directories (e.g., 2008-2009, 2009-2010)
    season_dirs = [d for d in base_path.iterdir() if d.is_dir() and '-' in d.name]
    season_dirs.sort()
    
    print(f"=" * 70)
    print(f"Processing {competition_name}")
    print(f"=" * 70)
    print(f"Found {len(season_dirs)} season directories\n")
    
    total_files = 0
    
    for season_dir in season_dirs:
        season_name = season_dir.name
        partidos_dir = season_dir / "partidos"
        
        if not partidos_dir.exists():
            print(f"⚠️  {season_name}: 'partidos' directory not found")
            continue
        
        # Find all JSON files with "Barcelona" in the name
        barcelona_files = [
            f for f in partidos_dir.glob("*.json") 
            if "barcelona" in f.name.lower()
        ]
        
        if barcelona_files:
            # Create output directory structure
            output_season_dir = output_path / season_name / "match_data"
            output_season_dir.mkdir(parents=True, exist_ok=True)
            
            print(f"📅 {season_name}: Found {len(barcelona_files)} Barcelona matches")
            
            # Process each Barcelona file
            for file in barcelona_files:
                try:
                    # Read the file content
                    with open(file, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    # Strip JSONP wrapper if present
                    clean_json = strip_jsonp_wrapper(content)
                    
                    # Validate JSON
                    json.loads(clean_json)
                    
                    # Write clean JSON to destination
                    destination = output_season_dir / file.name
                    with open(destination, 'w', encoding='utf-8') as f:
                        f.write(clean_json)
                    
                    total_files += 1
                    print(f"   ✓ {file.name}")
                    
                except json.JSONDecodeError as e:
                    print(f"   ✗ Error parsing {file.name}: {e}")
                except Exception as e:
                    print(f"   ✗ Error processing {file.name}: {e}")
        else:
            print(f"📅 {season_name}: No Barcelona matches found")
    
    print(f"\n{'=' * 70}")
    print(f"✅ Done! Processed {total_files} Barcelona matches")
    print(f"📁 Output location: {output_path}")
    print(f"{'=' * 70}\n")

if __name__ == "__main__":
    # Configuration for UEFA Super Cup
    BASE_DIR = "."  # Current directory (where season folders are)
    OUTPUT_DIR = "UEFA_Super_Cup"
    COMPETITION_NAME = "UEFA Super Cup"
    
    filter_barcelona_matches(BASE_DIR, OUTPUT_DIR, COMPETITION_NAME)