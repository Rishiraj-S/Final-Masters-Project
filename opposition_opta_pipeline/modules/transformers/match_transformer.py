"""
Transform match info from partidos JSON.
Output: data/result/{league}/{season}/match/{date}_{home_code}_vs_{away_code}_{match_id}.parquet
"""
import pandas as pd
from pathlib import Path
from typing import Optional

from .base_transformer import BaseTransformer
from ..utils import get_organized_path_reversed


class MatchTransformer(BaseTransformer):
    """Extracts match metadata from each partidos JSON."""

    def _extract_naming(self, match_info: dict, match_id: str) -> dict:
        contestants = match_info.get("contestant", []) or []
        home_team = away_team = home_code = away_code = "unknown"
        for c in contestants:
            pos = c.get("position", "")
            if pos == "home":
                home_team = c.get("officialName") or c.get("name", "unknown")
                home_code = c.get("code", "UNK")
            elif pos == "away":
                away_team = c.get("officialName") or c.get("name", "unknown")
                away_code = c.get("code", "UNK")
        date = match_info.get("localDate") or match_info.get("date", "unknown")
        return {
            "home_team": home_team, "away_team": away_team,
            "home_code": home_code, "away_code": away_code, "date": date,
        }

    def transform_match(self, match_id: str, data: dict) -> Optional[str]:
        """Transform one match JSON dict → match Parquet. Returns output path or None."""
        if self._output_exists(match_id, "match"):
            self.logger.debug(f"   ⏭️  match parquet exists: {match_id}")
            return "skipped"

        try:
            match_info = data.get("matchInfo", {})
            if not match_info:
                self.logger.error(f"   ❌ No matchInfo: {match_id}")
                return None

            naming = self._extract_naming(match_info, match_id)
            naming_config = self.config.get("output", {}).get("naming", {})

            record = {
                "match_id": match_info.get("id", match_id),
                "league": self.league_name,
                "season": self.season,
                "date": match_info.get("localDate") or match_info.get("date", "N/A"),
                "time": match_info.get("localTime") or match_info.get("time", "N/A"),
                "description": match_info.get("description", "N/A"),
                "week": match_info.get("week", "N/A"),
                "period_length": match_info.get("periodLength", 45),
                "number_of_periods": match_info.get("numberOfPeriods", 2),
                "coverage_level": match_info.get("coverageLevel", "N/A"),
                "last_updated": match_info.get("lastUpdated", "N/A"),
            }

            venue = match_info.get("venue", {}) or {}
            record["venue_id"] = venue.get("id", "N/A")
            record["venue_name"] = venue.get("longName", "N/A")
            record["venue_short_name"] = venue.get("shortName", "N/A")

            competition = match_info.get("competition", {}) or {}
            record["competition_id"] = competition.get("id", "N/A")
            record["competition_name"] = competition.get("name", "N/A")

            tournament = match_info.get("tournamentCalendar", {}) or {}
            record["tournament_id"] = tournament.get("id", "N/A")
            record["tournament_name"] = tournament.get("name", "N/A")

            contestants = match_info.get("contestant", []) or []
            for c in contestants:
                prefix = "home" if c.get("position") == "home" else "away"
                record[f"{prefix}_team_id"] = c.get("id", "N/A")
                record[f"{prefix}_team_name"] = c.get("name", "N/A")
                record[f"{prefix}_team_code"] = c.get("code", "N/A")
                record[f"{prefix}_team_official_name"] = c.get("officialName", "N/A")
                record[f"{prefix}_score"] = c.get("score", "N/A")

            # Add FT scores from liveData if available
            live_data = data.get("liveData", {}) or {}
            match_details = live_data.get("matchDetails", {}) or {}
            scores = match_details.get("scores", {}) or {}
            ft = scores.get("ft", {}) or {}
            if ft:
                record["home_score_ft"] = ft.get("home", "N/A")
                record["away_score_ft"] = ft.get("away", "N/A")
            ht = scores.get("ht", {}) or {}
            if ht:
                record["home_score_ht"] = ht.get("home", "N/A")
                record["away_score_ht"] = ht.get("away", "N/A")

            df = pd.DataFrame([record])

            date_clean = self._clean_filename(naming["date"], naming_config)
            home_code = self._clean_filename(naming["home_code"], naming_config)
            away_code = self._clean_filename(naming["away_code"], naming_config)
            filename = f"{date_clean}_{home_code}_vs_{away_code}_{match_id}.{self.output_format}"

            output_path = get_organized_path_reversed(
                self.base_result_dir, self.league_name, self.season,
                filename, subdirectory="match",
            )
            self.save_dataframe(df, output_path)
            self.logger.info(f"   ✅ match: {filename}")
            return output_path

        except Exception as e:
            self.logger.error(f"   ❌ Match transform failed for {match_id}: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            return None

    def transform_all(self) -> int:
        """Transform all partidos JSONs → match Parquets. Returns count of successes."""
        partidos_dir = self._get_partidos_dir()
        if not partidos_dir.exists():
            self.logger.warning(f"partidos/ not found: {partidos_dir}")
            return 0

        json_files = list(partidos_dir.glob("*.json"))
        if not json_files:
            self.logger.warning("No partidos JSON files found")
            return 0

        self.logger.info(f"🔄 Found {len(json_files)} partidos files")
        print(f"   📋 Match info: processing {len(json_files)} file(s)...")

        successful = failed = 0
        for match_id, data, json_file in self._load_all_partidos():
            result = self.transform_match(match_id, data)
            if result:
                successful += 1
            else:
                failed += 1

        status = f"⚠️  {failed} failed" if failed else "all OK"
        print(f"   ✅ Match info done: {successful}/{len(json_files)} ({status})")
        return successful
