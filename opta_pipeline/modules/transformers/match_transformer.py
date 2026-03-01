"""
Transform match info from matchevent JSON (reads from matchdata directory)
"""
import pandas as pd
from pathlib import Path
from typing import Optional

from .base_transformer import BaseTransformer
from ..utils import get_organized_path_reversed


class MatchTransformer(BaseTransformer):
    """Extracts match info from matchevent JSON in matchdata directory"""
    
    def _extract_match_info_for_naming(self, match_info_obj: dict, match_id: str) -> dict:
        """Extract match info for filename generation"""
        contestants = match_info_obj.get("contestant", []) or []
        home_team = away_team = home_code = away_code = "unknown"
        
        for contestant in contestants:
            position = contestant.get("position", "")
            
            if position == "home":
                home_team = contestant.get("officialName") or contestant.get("name", "unknown")
                home_code = contestant.get("code", "UNK")
            elif position == "away":
                away_team = contestant.get("officialName") or contestant.get("name", "unknown")
                away_code = contestant.get("code", "UNK")
        
        date = match_info_obj.get("localDate") or match_info_obj.get("date", "unknown")
        week = match_info_obj.get("week", "unknown")
        venue_obj = match_info_obj.get("venue", {}) or {}
        venue = venue_obj.get("shortName") or venue_obj.get("longName", "unknown")
        
        return {
            'home_team': home_team,
            'away_team': away_team,
            'home_code': home_code,
            'away_code': away_code,
            'date': date,
            'week': week,
            'score': '',
            'venue': venue,
        }
    
    def _build_filename(self, match_id: str, match_info: dict, naming_config: dict) -> str:
        """Build filename based on pattern"""
        pattern = naming_config.get('pattern', '{match_id}')
        
        placeholders = {
            'match_id': match_id,
            'date': self._clean_filename(match_info.get('date', 'unknown'), naming_config),
            'home': self._clean_filename(match_info.get('home_team', 'unknown'), naming_config),
            'away': self._clean_filename(match_info.get('away_team', 'unknown'), naming_config),
            'home_code': self._clean_filename(match_info.get('home_code', 'UNK'), naming_config),
            'away_code': self._clean_filename(match_info.get('away_code', 'UNK'), naming_config),
            'week': self._clean_filename(match_info.get('week', 'unknown'), naming_config),
            'score': self._clean_filename(match_info.get('score', ''), naming_config),
            'venue': self._clean_filename(match_info.get('venue', 'unknown'), naming_config),
        }
        
        filename = pattern
        for key, value in placeholders.items():
            filename = filename.replace(f'{{{key}}}', str(value))
        
        include_match_id = naming_config.get('include_match_id', 'none')
        if include_match_id == 'prefix' and '{match_id}' not in pattern:
            filename = f"{match_id}_{filename}"
        elif include_match_id == 'suffix' and '{match_id}' not in pattern:
            filename = f"{filename}_{match_id}"
        
        return filename
    
    def transform_match(self, match_id: str) -> Optional[str]:
        """Transform match info from matchevent JSON"""
        if self._output_exists(match_id, 'match'):
            self.logger.debug(f"   ⏭️  match parquet exists, skipping: {match_id}")
            return 'skipped'

        # Load from matchdata directory
        json_path = Path(get_organized_path_reversed(
            self.base_target_dir,
            self.league_name,
            self.season,
            f"{match_id}.json",
            subdirectory='matchdata'
        ))
        
        if not json_path.exists():
            self.logger.warning(f"   ⚠️  JSON not found: {match_id}")
            return None
        
        try:
            data = self.load_json_file(json_path)
            match_info_obj = data.get('matchInfo', {})
            
            if not match_info_obj:
                self.logger.error(f"   ❌ No matchInfo found: {match_id}")
                return None
            
            # Extract match info for naming
            match_info_for_naming = self._extract_match_info_for_naming(match_info_obj, match_id)
            naming_config = self.config.get('output', {}).get('naming', {})
            
            # Build filename
            match_filename = self._build_filename(match_id, match_info_for_naming, naming_config)
            match_filename = f"{match_filename}.{self.output_format}"
            
            # Extract detailed match information
            record = {
                'match_id': match_info_obj.get('id', match_id),
                'league': self.league_name,
                'season': self.season,
                'date': match_info_obj.get('localDate') or match_info_obj.get('date', 'N/A'),
                'time': match_info_obj.get('localTime') or match_info_obj.get('time', 'N/A'),
                'description': match_info_obj.get('description', 'N/A'),
                'week': match_info_obj.get('week', 'N/A'),
                'period_length': match_info_obj.get('periodLength', 45),
                'number_of_periods': match_info_obj.get('numberOfPeriods', 2),
                'coverage_level': match_info_obj.get('coverageLevel', 'N/A'),
                'last_updated': match_info_obj.get('lastUpdated', 'N/A'),
            }
            
            # Venue
            venue = match_info_obj.get('venue', {}) or {}
            record['venue_id'] = venue.get('id', 'N/A')
            record['venue_name'] = venue.get('longName', 'N/A')
            record['venue_short_name'] = venue.get('shortName', 'N/A')
            
            # Competition
            competition = match_info_obj.get('competition', {}) or {}
            record['competition_id'] = competition.get('id', 'N/A')
            record['competition_name'] = competition.get('name', 'N/A')
            
            # Tournament
            tournament = match_info_obj.get('tournamentCalendar', {}) or {}
            record['tournament_id'] = tournament.get('id', 'N/A')
            record['tournament_name'] = tournament.get('name', 'N/A')
            
            # Teams
            contestants = match_info_obj.get('contestant', []) or []
            for contestant in contestants:
                position = contestant.get('position', '')
                prefix = 'home' if position == 'home' else 'away'
                
                record[f'{prefix}_team_id'] = contestant.get('id', 'N/A')
                record[f'{prefix}_team_name'] = contestant.get('name', 'N/A')
                record[f'{prefix}_team_code'] = contestant.get('code', 'N/A')
                record[f'{prefix}_team_official_name'] = contestant.get('officialName', 'N/A')
                record[f'{prefix}_score'] = contestant.get('score', 'N/A')
            
            df = pd.DataFrame([record])
            
            # Save to match directory (not match_info)
            output_path = get_organized_path_reversed(
                self.base_result_dir,
                self.league_name,
                self.season,
                match_filename,
                subdirectory='match'
            )
            
            self.save_dataframe(df, output_path)
            self.logger.info(f"   ✅ match: {match_filename}")
            
            return str(output_path)
            
        except Exception as e:
            self.logger.error(f"   ❌ Match transform failed for {match_id}: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            return None
    
    def transform_all(self) -> int:
        """Transform all matchdata files"""
        matchdata_dir = Path(get_organized_path_reversed(
            self.base_target_dir,
            self.league_name,
            self.season,
            '',
            subdirectory='matchdata'
        ))
        
        if not matchdata_dir.exists():
            self.logger.warning(f"Matchdata directory not found: {matchdata_dir}")
            return 0
        
        json_files = list(matchdata_dir.glob("*.json"))
        
        if not json_files:
            self.logger.warning("No matchdata files found")
            return 0
        
        self.logger.info(f"🔄 Found {len(json_files)} matchdata files")
        print(f"   📋 Match info: processing {len(json_files)} file(s)...")

        successful = 0
        failed = 0

        for json_file in sorted(json_files):
            match_id = json_file.stem
            self.logger.info(f"\n[{successful + failed + 1}/{len(json_files)}] Processing: {match_id}")

            result = self.transform_match(match_id)
            if result:
                successful += 1
            else:
                failed += 1

        self.logger.info(f"\n✅ Transformed {successful}/{len(json_files)} match files")
        if failed > 0:
            self.logger.warning(f"⚠️  Failed: {failed}")
        status = f"⚠️  {failed} failed" if failed else "all OK"
        print(f"   ✅ Match info done: {successful}/{len(json_files)} ({status})")

        return successful