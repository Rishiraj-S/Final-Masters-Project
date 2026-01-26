"""
Transform match event data (the comprehensive event-by-event data)
"""
import pandas as pd
from pathlib import Path
from typing import Optional
import re

from .base_transformer import BaseTransformer
from ..utils import get_organized_path_reversed


class MatchEventTransformer(BaseTransformer):
    """Transforms match event data to comprehensive parquet"""
    
    def __init__(self, config: dict, logger):
        super().__init__(config, logger)
        
        # Load mappings
        self.mappings_dir = config.get('paths', {}).get('mappings_dir', 'mappings')
        self.event_types = None
        self.qualifier_types = None
        self._load_mappings()
        
        # Formation mappings
        self.formation_mapping = {
            "1": "", "2": "442", "3": "41212", "4": "433", "5": "451",
            "6": "4411", "7": "4141", "8": "4231", "9": "4321", "10": "532",
            "11": "541", "12": "352", "13": "343", "14": "31312", "15": "4222",
            "16": "3511", "17": "3421", "18": "3412", "19": "3142", "20": "",
            "21": "4132", "22": "", "23": "4312",
        }
        
        self.formation_position_mapping = {
            "442": {"1": "GK", "2": "RB", "3": "LB", "4": "MC", "5": "CB", "6": "CB", "7": "RM", "8": "CM", "9": "CF", "10": "CF", "11": "LM"},
            "41212": {"1": "GK", "2": "RB", "3": "LB", "4": "CDM", "5": "CB", "6": "CB", "7": "MC", "8": "CAM", "9": "CF", "10": "CF", "11": "MC"},
            "433": {"1": "GK", "2": "RB", "3": "LB", "4": "MC", "5": "CB", "6": "CB", "7": "MC", "8": "MC", "9": "CF", "10": "LW", "11": "RW"},
            "451": {"1": "GK", "2": "RB", "3": "LB", "4": "MC", "5": "CB", "6": "CB", "7": "RM", "8": "MC", "9": "CAM", "10": "CF", "11": "LM"},
            "4411": {"1": "GK", "2": "RB", "3": "LB", "4": "MC", "5": "CB", "6": "CB", "7": "RM", "8": "MC", "9": "CF", "10": "SS", "11": "LM"},
            "4141": {"1": "GK", "2": "RB", "3": "LB", "4": "CDM", "5": "CB", "6": "CB", "7": "RM", "8": "MC", "9": "CF", "10": "MC", "11": "LM"},
            "4231": {"1": "GK", "2": "RB", "3": "LB", "4": "CDM", "5": "CB", "6": "CB", "7": "RW", "8": "CDM", "9": "CF", "10": "CAM", "11": "LW"},
            "4321": {"1": "GK", "2": "RB", "3": "LB", "4": "CDM", "5": "CB", "6": "CB", "7": "MC", "8": "MC", "9": "CF", "10": "CAM", "11": "CAM"},
            "532": {"1": "GK", "2": "RWB", "3": "LWB", "4": "CB", "5": "CB", "6": "CB", "7": "MC", "8": "CDM", "9": "CF", "10": "CF", "11": "MC"},
            "541": {"1": "GK", "2": "RWB", "3": "LWB", "4": "CB", "5": "CB", "6": "CB", "7": "RM", "8": "MC", "9": "CF", "10": "MC", "11": "LM"},
            "352": {"1": "GK", "2": "RWB", "3": "LWB", "4": "CB", "5": "CB", "6": "CB", "7": "MC", "8": "MC", "9": "CF", "10": "CF", "11": "CAM"},
            "343": {"1": "GK", "2": "RWB", "3": "LWB", "4": "CB", "5": "CB", "6": "CB", "7": "MC", "8": "MC", "9": "CF", "10": "RW", "11": "LW"},
            "31312": {"1": "GK", "2": "RWB", "3": "LWB", "4": "CDM", "5": "CB", "6": "CB", "7": "CB", "8": "MC", "9": "CF", "10": "CAM", "11": "SS"},
            "4222": {"1": "GK", "2": "RB", "3": "LB", "4": "CDM", "5": "CB", "6": "CB", "7": "CDM", "8": "CAM", "9": "CF", "10": "CF", "11": "CAM"},
            "3511": {"1": "GK", "2": "RWB", "3": "LWB", "4": "CB", "5": "CB", "6": "CB", "7": "MC", "8": "MC", "9": "CF", "10": "SS", "11": "CAM"},
            "3421": {"1": "GK", "2": "RWB", "3": "LWB", "4": "CB", "5": "CB", "6": "CB", "7": "MC", "8": "MC", "9": "CAM", "10": "CAM", "11": "CF"},
            "3412": {"1": "GK", "2": "RWB", "3": "LWB", "4": "CB", "5": "CB", "6": "CB", "7": "MC", "8": "MC", "9": "CAM", "10": "CF", "11": "CF"},
        }
    
    def _load_mappings(self):
        """Load event and qualifier mappings"""
        event_types_path = Path(self.mappings_dir) / 'opta_event_types.csv'
        qualifier_types_path = Path(self.mappings_dir) / 'opta_qualifier_types.csv'
        
        if not event_types_path.exists():
            raise FileNotFoundError(f"Missing: {event_types_path}")
        
        if not qualifier_types_path.exists():
            raise FileNotFoundError(f"Missing: {qualifier_types_path}")
        
        self.event_types = pd.read_csv(event_types_path)
        self.qualifier_types = pd.read_csv(qualifier_types_path)
    
    def process_match_json(self, json_data: dict) -> pd.DataFrame:
        """Transform JSON to comprehensive event DataFrame"""
        match_info = json_data.get("matchInfo", {})
        match_id = match_info.get("id", "N/A")
        
        # Extract match metadata
        coverage_level = match_info.get("coverageLevel", "N/A")
        local_date = match_info.get("localDate", "N/A")
        local_time = match_info.get("localTime", "N/A")
        week = match_info.get("week", "N/A")
        description = match_info.get("description", "N/A")
        
        competition = match_info.get("competition", {}) or {}
        competition_id = competition.get("id", "N/A")
        competition_name = competition.get("name", "N/A")
        
        tournament_calendar = match_info.get("tournamentCalendar", {}) or {}
        tournament_id = tournament_calendar.get("id", "N/A")
        tournament_name = tournament_calendar.get("name", "N/A")
        
        venue = match_info.get("venue", {}) or {}
        venue_id = venue.get("id", "N/A")
        venue_name = venue.get("longName", "N/A")
        venue_short_name = venue.get("shortName", "N/A")
        
        # Extract teams
        contestants = match_info.get("contestant", []) or []
        team_info = {}
        home_team = away_team = home_score = away_score = "N/A"
        
        for contestant in contestants:
            team_id = contestant["id"]
            team_info[team_id] = {
                "name": contestant.get("officialName", "N/A"),
                "code": contestant.get("code", "N/A"),
                "position": contestant.get("position", "N/A")
            }
            
            if contestant.get("position") == "home":
                home_team = contestant.get("name", "N/A")
                home_score = contestant.get("score", "N/A")
            elif contestant.get("position") == "away":
                away_team = contestant.get("name", "N/A")
                away_score = contestant.get("score", "N/A")
        
        # Get qualifier types
        qualifier_types = self.qualifier_types["qualifierTypeName"].values
        qualifier_type_ids = self.qualifier_types["qualifierTypeId"].values
        
        # Process events
        events = json_data.get("liveData", {}).get("event", []) or []
        processed_events = []
        
        team_formations = {}
        team_player_mappings = {}
        
        for event in events:
            type_id = event.get("typeId")
            
            # Map event type
            if type_id in self.event_types['eventTypeId'].values:
                event_name = self.event_types.loc[
                    self.event_types['eventTypeId'] == type_id, 'eventTypeName'
                ].values[0]
            else:
                event_name = "Unknown"
            
            contestant_id = event.get("contestantId")
            player_id = event.get("playerId")
            
            team_details = team_info.get(contestant_id, {"name": "N/A", "code": "N/A", "position": "N/A"})
            
            # Process qualifiers
            qualifiers = event.get("qualifier", []) or []
            qualifier_values = {q_name: "N/A" for q_name in qualifier_types}
            
            for qualifier in qualifiers:
                qualifier_id = qualifier.get("qualifierId")
                qualifier_value = qualifier.get("value", None)
                
                if qualifier_id in qualifier_type_ids:
                    qualifier_name = self.qualifier_types.loc[
                        self.qualifier_types["qualifierTypeId"] == qualifier_id, 
                        "qualifierTypeName"
                    ].values[0]
                    qualifier_values[qualifier_name] = qualifier_value if qualifier_value else "Si"
            
            # Handle formations
            if event_name in ["Team setp up", "Formation change"]:
                team_formation_value = qualifier_values.get("Team Formation", None)
                if team_formation_value and team_formation_value != "N/A":
                    team_formations[contestant_id] = team_formation_value
                
                involved = qualifier_values.get("Involved", "").split(", ")
                jersey_numbers = qualifier_values.get("Jersey Number", "").split(", ")
                team_player_formation = qualifier_values.get("Team Player Formation", "").split(", ")
                player_positions = qualifier_values.get("Player Position", "").split(", ")
                
                mapping = {}
                for idx, pid in enumerate(involved):
                    pid = pid.strip()
                    if not pid:
                        continue
                    mapping[pid] = {
                        "Jersey Number": jersey_numbers[idx] if idx < len(jersey_numbers) else "N/A",
                        "Team Player Formation": team_player_formation[idx] if idx < len(team_player_formation) else "N/A",
                        "Player Position": player_positions[idx] if idx < len(player_positions) else "N/A"
                    }
                team_player_mappings[contestant_id] = mapping
            
            # Propagate formation
            qualifier_values["Team Formation"] = team_formations.get(contestant_id, "N/A")
            player_mapping = team_player_mappings.get(contestant_id, {}).get(player_id, {})
            qualifier_values["Jersey Number"] = player_mapping.get("Jersey Number", "N/A")
            qualifier_values["Team Player Formation"] = player_mapping.get("Team Player Formation", "N/A")
            qualifier_values["Player Position"] = player_mapping.get("Player Position", "N/A")
            
            # Build event record
            processed_events.append({
                "match_id": match_id,
                "league": self.league_name,
                "season": self.season,
                "match_date": local_date,
                "match_time": local_time,
                "match_description": description,
                "week": week,
                "home_team": home_team,
                "away_team": away_team,
                "home_score": home_score,
                "away_score": away_score,
                "venue_id": venue_id,
                "venue_name": venue_name,
                "venue_short_name": venue_short_name,
                "competition_id": competition_id,
                "competition_name": competition_name,
                "tournament_id": tournament_id,
                "tournament_name": tournament_name,
                "coverage_level": coverage_level,
                "event_general_id": event.get("id"),
                "event_id": event.get("eventId"),
                "event_type": event_name,
                "event_type_id": type_id,
                "period_id": event.get("periodId"),
                "time_min": event.get("timeMin"),
                "time_sec": event.get("timeSec"),
                "timestamp": event.get("timeStamp"),
                "last_modified": event.get("lastModified"),
                "contestant_id": contestant_id,
                "team_name": team_details["name"],
                "team_code": team_details["code"],
                "team_position": team_details["position"],
                "player_id": player_id,
                "player_name": event.get("playerName"),
                "x": event.get("x"),
                "y": event.get("y"),
                "outcome": event.get("outcome"),
                **qualifier_values,
            })
        
        df = pd.DataFrame(processed_events)
        
        # Add derived columns
        if 'Team Formation' in df.columns:
            df['formation'] = (
                df['Team Formation']
                .astype(str)
                .map(self.formation_mapping)
                .fillna("")
            )
            df["position"] = df.apply(self.get_position, axis=1)
        
        return df
    
    def get_position(self, row: pd.Series) -> str:
        """Get player position based on formation"""
        formation = row.get("formation", "")
        pos_number = str(row.get("Team Player Formation", ""))
        return self.formation_position_mapping.get(formation, {}).get(pos_number, "N/A")
    
    def _extract_match_info(self, json_data: dict) -> dict:
        """Extract match info for filename"""
        match_info_obj = json_data.get("matchInfo", {})
        
        contestants = match_info_obj.get("contestant", []) or []
        home_team = away_team = home_code = away_code = "unknown"
        
        for contestant in contestants:
            if contestant.get("position") == "home":
                home_team = contestant.get("officialName", "unknown")
                home_code = contestant.get("code", "UNK")
            elif contestant.get("position") == "away":
                away_team = contestant.get("officialName", "unknown")
                away_code = contestant.get("code", "UNK")
        
        date = match_info_obj.get("localDate", "unknown")
        week = match_info_obj.get("week", "unknown")
        
        venue_obj = match_info_obj.get("venue", {}) or {}
        venue = venue_obj.get("shortName", venue_obj.get("longName", "unknown"))
        
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
        """Transform match event data"""
        # CHANGED: Read from matchdata instead of matchevent
        json_path = Path(get_organized_path_reversed(
            self.base_target_dir,
            self.league_name,
            self.season,
            f"{match_id}.json",
            subdirectory='matchdata'
        ))
        
        if not json_path.exists():
            self.logger.warning(f"   ⚠️  matchdata JSON not found: {match_id}")
            return None
        
        try:
            json_data = self.load_json_file(json_path)
            events_df = self.process_match_json(json_data)
            
            if events_df.empty:
                self.logger.warning(f"   ⚠️  No events: {match_id}")
                return None
            
            # Build filename
            match_info = self._extract_match_info(json_data)
            naming_config = self.config.get('output', {}).get('naming', {})
            match_filename = self._build_filename(match_id, match_info, naming_config)
            match_filename = f"{match_filename}.{self.output_format}"
            
            # Save to match_event directory
            output_path = get_organized_path_reversed(
                self.base_result_dir,
                self.league_name,
                self.season,
                match_filename,
                subdirectory='match_event'
            )
            
            self.save_dataframe(events_df, output_path)
            self.logger.info(f"   ✅ match_event: {Path(output_path).name} ({len(events_df)} events)")
            
            return str(output_path)
            
        except Exception as e:
            self.logger.error(f"   ❌ Event transform failed for {match_id}: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            return None
    
    def transform_all(self) -> int:
        """Transform all matchdata files"""
        # CHANGED: Read from matchdata instead of matchevent
        matches_dir = Path(get_organized_path_reversed(
            self.base_target_dir,
            self.league_name,
            self.season,
            '',
            subdirectory='matchdata'
        ))
        
        if not matches_dir.exists():
            self.logger.error(f"matchdata directory not found: {matches_dir}")
            return 0
        
        json_files = list(matches_dir.glob("*.json"))
        
        if not json_files:
            self.logger.warning("No matchdata files found")
            return 0
        
        self.logger.info(f"🔄 Found {len(json_files)} matchdata files")
        
        successful = 0
        
        for json_file in sorted(json_files):
            match_id = json_file.stem
            self.logger.info(f"\n[{successful + 1}/{len(json_files)}] Processing: {match_id}")
            
            result = self.transform_match(match_id)
            if result:
                successful += 1
        
        self.logger.info(f"\n✅ Transformed {successful}/{len(json_files)} match events")
        
        return successful