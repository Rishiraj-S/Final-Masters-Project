"""
Extract lineup / formation data from matchevent JSON (matchdata directory).

Source:  data/target/{league}/{season}/matchdata/{match_id}.json
Output:  data/result/{league}/{season}/lineup/{date}_{home}_vs_{away}_{match_id}.parquet

The Opta typeId=34 ("Team setp up") event encodes the full matchday squad via
qualifiers:
  qualifierId=30  → comma-sep list of all player IDs (21 in order)
  qualifierId=131 → formation slot per player (1-11 = starter slot, 0 = sub)
  qualifierId=59  → jersey number per player
  qualifierId=44  → broad position code per player
                    (1=GK, 2=DEF, 3=MID, 4=FWD, 5=bench/sub)
  qualifierId=194 → captain's player ID (single value)
  qualifierId=130 → Opta formation code → mapped to formation string

Player names are recovered from the playerName field across all other events.

Each row in the output represents one squad member per team per match.
Columns:
  match_id, league, season, date, home_team, away_team
  team_id, team_name, team_position  ('home' | 'away')
  formation        e.g. "433"
  player_id, player_name
  jersey_number    int
  formation_slot   1-11 for starters, 0 for bench
  role             'Start' | 'Sub'
  position         specific role from formation map e.g. "GK", "CB", "CAM"
  position_broad   'GK' | 'DEF' | 'MID' | 'FWD' | 'Sub'
  is_captain       bool
  sub_on_minute    int | None  (minute subbed on, from Player-on events)
"""

import pandas as pd
from pathlib import Path
from typing import Optional, Dict, List

from .base_transformer import BaseTransformer
from ..utils import get_organized_path_reversed


# ── Opta qualifier IDs inside typeId=34 (Team setp up) ──────────────────────
_Q_PLAYER_IDS      = 30   # comma-sep all 21 player IDs in squad order
_Q_FORMATION_SLOTS = 131  # slot 1-11 = starting position, 0 = bench
_Q_JERSEY_NUMBERS  = 59   # jersey number for each of the 21 players
_Q_POSITION_CODES  = 44   # 1=GK, 2=DEF, 3=MID, 4=FWD, 5=Sub
_Q_CAPTAIN         = 194  # single player ID of the captain
_Q_FORMATION_CODE  = 130  # Opta numeric formation code

# Opta formation code → human-readable string
_FORMATION_MAP: Dict[str, str] = {
    "1": "", "2": "442", "3": "41212", "4": "433", "5": "451",
    "6": "4411", "7": "4141", "8": "4231", "9": "4321", "10": "532",
    "11": "541", "12": "352", "13": "343", "14": "31312", "15": "4222",
    "16": "3511", "17": "3421", "18": "3412", "19": "3142", "20": "",
    "21": "4132", "22": "", "23": "4312",
}

# Formation string + slot string → specific position label
_POSITION_DETAIL: Dict[str, Dict[str, str]] = {
    "442":   {"1":"GK","2":"RB","3":"LB","4":"MC","5":"CB","6":"CB","7":"RM","8":"CM","9":"CF","10":"CF","11":"LM"},
    "41212": {"1":"GK","2":"RB","3":"LB","4":"CDM","5":"CB","6":"CB","7":"MC","8":"CAM","9":"CF","10":"CF","11":"MC"},
    "433":   {"1":"GK","2":"RB","3":"LB","4":"MC","5":"CB","6":"CB","7":"MC","8":"MC","9":"CF","10":"LW","11":"RW"},
    "451":   {"1":"GK","2":"RB","3":"LB","4":"MC","5":"CB","6":"CB","7":"RM","8":"MC","9":"CAM","10":"CF","11":"LM"},
    "4411":  {"1":"GK","2":"RB","3":"LB","4":"MC","5":"CB","6":"CB","7":"RM","8":"MC","9":"CF","10":"SS","11":"LM"},
    "4141":  {"1":"GK","2":"RB","3":"LB","4":"CDM","5":"CB","6":"CB","7":"RM","8":"MC","9":"CF","10":"MC","11":"LM"},
    "4231":  {"1":"GK","2":"RB","3":"LB","4":"CDM","5":"CB","6":"CB","7":"RW","8":"CDM","9":"CF","10":"CAM","11":"LW"},
    "4321":  {"1":"GK","2":"RB","3":"LB","4":"CDM","5":"CB","6":"CB","7":"MC","8":"MC","9":"CF","10":"CAM","11":"CAM"},
    "532":   {"1":"GK","2":"RWB","3":"LWB","4":"CB","5":"CB","6":"CB","7":"MC","8":"CDM","9":"CF","10":"CF","11":"MC"},
    "541":   {"1":"GK","2":"RWB","3":"LWB","4":"CB","5":"CB","6":"CB","7":"RM","8":"MC","9":"CF","10":"MC","11":"LM"},
    "352":   {"1":"GK","2":"RWB","3":"LWB","4":"CB","5":"CB","6":"CB","7":"MC","8":"MC","9":"CF","10":"CF","11":"CAM"},
    "343":   {"1":"GK","2":"RWB","3":"LWB","4":"CB","5":"CB","6":"CB","7":"MC","8":"MC","9":"CF","10":"RW","11":"LW"},
    "31312": {"1":"GK","2":"RWB","3":"LWB","4":"CDM","5":"CB","6":"CB","7":"CB","8":"MC","9":"CF","10":"CAM","11":"SS"},
    "4222":  {"1":"GK","2":"RB","3":"LB","4":"CDM","5":"CB","6":"CB","7":"CDM","8":"CAM","9":"CF","10":"CF","11":"CAM"},
    "3511":  {"1":"GK","2":"RWB","3":"LWB","4":"CB","5":"CB","6":"CB","7":"MC","8":"MC","9":"CF","10":"SS","11":"CAM"},
    "3421":  {"1":"GK","2":"RWB","3":"LWB","4":"CB","5":"CB","6":"CB","7":"MC","8":"MC","9":"CAM","10":"CAM","11":"CF"},
    "3412":  {"1":"GK","2":"RWB","3":"LWB","4":"CB","5":"CB","6":"CB","7":"MC","8":"MC","9":"CAM","10":"CF","11":"CF"},
    "3142":  {"1":"GK","2":"RWB","3":"LWB","4":"CB","5":"CB","6":"CB","7":"CDM","8":"MC","9":"CF","10":"CF","11":"MC"},
    "4132":  {"1":"GK","2":"RB","3":"LB","4":"CDM","5":"CB","6":"CB","7":"MC","8":"MC","9":"CF","10":"CF","11":"MC"},
    "4312":  {"1":"GK","2":"RB","3":"LB","4":"MC","5":"CB","6":"CB","7":"MC","8":"MC","9":"CAM","10":"CF","11":"CF"},
}

_POSITION_BROAD: Dict[int, str] = {
    1: "GK", 2: "DEF", 3: "MID", 4: "FWD", 5: "Sub",
}


def _get_qual(event: dict, qualifier_id: int) -> str:
    """Return the value of a specific qualifier from a raw Opta event."""
    for q in event.get("qualifier", []):
        if q.get("qualifierId") == qualifier_id:
            return (q.get("value") or "").strip()
    return ""


def _parse_int_list(raw: str) -> List[int]:
    """Parse a comma-separated list of ints, returning 0 for blank/invalid items."""
    result = []
    for item in raw.split(","):
        item = item.strip()
        try:
            result.append(int(item))
        except ValueError:
            result.append(0)
    return result


class LineupTransformer(BaseTransformer):
    """
    Extracts per-player lineup rows from existing matchdata JSON files.
    No additional network requests required — all data comes from the
    typeId=34 (Team setp up) qualifier block.
    """

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _contestant_context(self, match_info: dict) -> Dict[str, dict]:
        """Return {contestant_id → {name, team_position, code}} mapping."""
        result: Dict[str, dict] = {}
        for c in match_info.get("contestant", []) or []:
            cid = c.get("id", "")
            if cid:
                result[cid] = {
                    "name": c.get("name", ""),
                    "official_name": c.get("officialName", "") or c.get("name", ""),
                    "code": c.get("code", ""),
                    "team_position": c.get("position", ""),  # 'home' | 'away'
                }
        return result

    def _build_name_lookup(self, events: list) -> Dict[str, str]:
        """Build player_id → player_name from all events that carry a player."""
        lookup: Dict[str, str] = {}
        for ev in events:
            pid = (ev.get("playerId") or ev.get("playerRef") or "").strip()
            name = (ev.get("playerName") or ev.get("matchName") or "").strip()
            if pid and name:
                lookup[pid] = name
        return lookup

    def _build_sub_minute_lookup(self, events: list) -> Dict[str, int]:
        """Return {player_id → minute_subbed_on} from Player-on events (typeId=19)."""
        lookup: Dict[str, int] = {}
        for ev in events:
            if ev.get("typeId") == 19:
                pid = (ev.get("playerId") or "").strip()
                if pid:
                    lookup[pid] = int(ev.get("timeMin") or 0)
        return lookup

    def _extract_match_naming(self, match_info: dict, match_id: str) -> dict:
        """Pull date + team codes for the output filename."""
        contestants = match_info.get("contestant", []) or []
        home_team = away_team = "unknown"
        home_code = away_code = "UNK"
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
            "date": date,
            "home_team": home_team,
            "away_team": away_team,
            "home_code": home_code,
            "away_code": away_code,
        }

    # ------------------------------------------------------------------
    # Core transform
    # ------------------------------------------------------------------

    def transform_lineup(self, match_id: str) -> Optional[str]:
        """
        Parse the matchdata JSON for one match and write a lineup Parquet.
        Returns output path or None on failure.
        """
        json_path = Path(
            get_organized_path_reversed(
                self.base_target_dir,
                self.league_name,
                self.season,
                f"{match_id}.json",
                subdirectory="matchdata",
            )
        )

        if not json_path.exists():
            self.logger.debug(f"   [lineup] No matchdata JSON: {match_id}")
            return None

        try:
            data = self.load_json_file(json_path)
        except Exception as e:
            self.logger.error(f"   ❌ [lineup] Could not load {json_path.name}: {e}")
            return None

        match_info = data.get("matchInfo") or {}
        live_data = data.get("liveData") or {}
        events: List[dict] = live_data.get("event") or []

        if not events:
            self.logger.warning(f"   ⚠️  [lineup] No events in {match_id}")
            return None

        # Context maps
        contestant_ctx = self._contestant_context(match_info)
        name_lookup = self._build_name_lookup(events)
        sub_minute_lookup = self._build_sub_minute_lookup(events)
        naming = self._extract_match_naming(match_info, match_id)

        # Find all Team setp up events (typeId=34)
        setup_events = [ev for ev in events if ev.get("typeId") == 34]
        if not setup_events:
            self.logger.warning(f"   ⚠️  [lineup] No typeId=34 events in {match_id}")
            return None

        rows = []

        for ev in setup_events:
            contestant_id = (ev.get("contestantId") or "").strip()
            ctx = contestant_ctx.get(contestant_id, {})
            team_name = ctx.get("name", contestant_id)
            team_position = ctx.get("team_position", "")

            # ── Qualifier extraction ──────────────────────────────────
            raw_pids = _get_qual(ev, _Q_PLAYER_IDS)
            raw_slots = _get_qual(ev, _Q_FORMATION_SLOTS)
            raw_jerseys = _get_qual(ev, _Q_JERSEY_NUMBERS)
            raw_pos_codes = _get_qual(ev, _Q_POSITION_CODES)
            captain_id = _get_qual(ev, _Q_CAPTAIN)
            formation_code = _get_qual(ev, _Q_FORMATION_CODE)

            if not raw_pids:
                self.logger.warning(
                    f"   ⚠️  [lineup] Missing player IDs in team setup ({team_name})"
                )
                continue

            player_ids = [p.strip() for p in raw_pids.split(",")]
            formation_slots = _parse_int_list(raw_slots) if raw_slots else [0] * len(player_ids)
            jersey_numbers = _parse_int_list(raw_jerseys) if raw_jerseys else [0] * len(player_ids)
            position_codes = _parse_int_list(raw_pos_codes) if raw_pos_codes else [5] * len(player_ids)
            formation_str = _FORMATION_MAP.get(formation_code, formation_code)
            slot_to_pos = _POSITION_DETAIL.get(formation_str, {})

            # Pad lists to match player count
            n = len(player_ids)
            formation_slots = (formation_slots + [0] * n)[:n]
            jersey_numbers = (jersey_numbers + [0] * n)[:n]
            position_codes = (position_codes + [5] * n)[:n]

            for i, pid in enumerate(player_ids):
                slot = formation_slots[i]
                jersey = jersey_numbers[i] or None
                pos_code = position_codes[i]

                role = "Start" if slot > 0 else "Sub"
                position_broad = _POSITION_BROAD.get(pos_code, "Sub")
                position_detail = slot_to_pos.get(str(slot), "") if slot > 0 else ""

                rows.append({
                    "match_id": match_id,
                    "league": self.league_name,
                    "season": self.season,
                    "date": naming["date"],
                    "home_team": naming["home_team"],
                    "away_team": naming["away_team"],
                    "team_id": contestant_id,
                    "team_name": team_name,
                    "team_position": team_position,
                    "formation": formation_str,
                    "player_id": pid,
                    "player_name": name_lookup.get(pid, ""),
                    "jersey_number": jersey,
                    "formation_slot": slot,
                    "role": role,
                    "position": position_detail,
                    "position_broad": position_broad,
                    "is_captain": (pid == captain_id),
                    "sub_on_minute": sub_minute_lookup.get(pid),
                })

        if not rows:
            self.logger.warning(f"   ⚠️  [lineup] No rows extracted for {match_id}")
            return None

        df = pd.DataFrame(rows)

        # Build filename using same naming convention
        naming_config = self.config.get("output", {}).get("naming", {})
        date_clean = self._clean_filename(naming["date"], naming_config)
        home_code = self._clean_filename(naming["home_code"], naming_config)
        away_code = self._clean_filename(naming["away_code"], naming_config)
        filename = f"{date_clean}_{home_code}_vs_{away_code}_{match_id}.{self.output_format}"

        output_path = get_organized_path_reversed(
            self.base_result_dir,
            self.league_name,
            self.season,
            filename,
            subdirectory="lineup",
        )

        self.save_dataframe(df, output_path)
        starters = (df["role"] == "Start").sum()
        self.logger.info(
            f"   ✅ lineup: {filename} "
            f"({len(df)} players, {starters} starters across both teams)"
        )
        return output_path

    # ------------------------------------------------------------------
    # Batch transform
    # ------------------------------------------------------------------

    def transform_all(self) -> int:
        """Transform all matchdata JSON files into lineup Parquets."""
        matchdata_dir = Path(
            get_organized_path_reversed(
                self.base_target_dir,
                self.league_name,
                self.season,
                "",
                subdirectory="matchdata",
            )
        )

        if not matchdata_dir.exists():
            self.logger.info(f"   [lineup] No matchdata directory: {matchdata_dir}")
            return 0

        json_files = sorted(matchdata_dir.glob("*.json"))
        if not json_files:
            self.logger.info("   [lineup] No matchdata JSON files found")
            return 0

        self.logger.info(f"🔄 [lineup] Found {len(json_files)} matchdata file(s)")
        print(f"   👥 Lineups: processing {len(json_files)} file(s)...")
        successful = 0
        failed = 0

        for json_file in json_files:
            match_id = json_file.stem
            result = self.transform_lineup(match_id)
            if result:
                successful += 1
            else:
                failed += 1

        self.logger.info(
            f"✅ Lineup: {successful}/{len(json_files)} transformed"
            + (f"  ⚠️  {failed} failed" if failed else "")
        )
        status = f"⚠️  {failed} failed" if failed else "all OK"
        print(f"   ✅ Lineups done: {successful}/{len(json_files)} ({status})")
        return successful
