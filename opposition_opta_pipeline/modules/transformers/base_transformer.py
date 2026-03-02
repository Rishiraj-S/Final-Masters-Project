"""
Base transformer — reads from opposition_data/{league}/{season}/partidos/
instead of data/target/{league}/{season}/matchdata/.
"""
import json
import logging
import re
from pathlib import Path
from typing import Iterator, Optional, Tuple

import pandas as pd

from ..utils import extract_json_from_jsonp, get_organized_path_reversed


class BaseTransformer:
    """Base class for all opposition-pipeline transformers."""

    def __init__(self, config: dict, logger: logging.Logger):
        self.config = config
        self.logger = logger

        script_dir = Path(__file__).parent.parent.parent  # opposition_opta_pipeline/
        opposition_data_dir = config.get("paths", {}).get("opposition_data_dir", "opposition_data")
        if not Path(opposition_data_dir).is_absolute():
            opposition_data_dir = str(script_dir / opposition_data_dir)
        self.opposition_data_dir = opposition_data_dir

        result_dir = config.get("paths", {}).get("result_dir", "data/result")
        if not Path(result_dir).is_absolute():
            result_dir = str(script_dir / result_dir)
        self.base_result_dir = result_dir

        competition = config.get("competition", {})
        self.league_name = competition.get("league_name") or "Unknown_League"
        self.season = competition.get("season", "Unknown_Season")

        self.output_format = config.get("output", {}).get("format", "parquet")

    # ------------------------------------------------------------------
    # Path helpers
    # ------------------------------------------------------------------

    def _get_partidos_dir(self) -> Path:
        """Return Path to opposition_data/{league}/{season}/partidos/"""
        return Path(self.opposition_data_dir) / self.league_name / self.season / "partidos"

    def _output_exists(self, match_id: str, subdirectory: str) -> bool:
        """Return True if a result Parquet for match_id already exists."""
        result_dir = Path(get_organized_path_reversed(
            self.base_result_dir, self.league_name, self.season, "",
            subdirectory=subdirectory,
        ))
        if not result_dir.exists():
            return False
        return any(result_dir.glob(f"*{match_id}*"))

    # ------------------------------------------------------------------
    # File loading
    # ------------------------------------------------------------------

    def load_json_file(self, json_path: Path) -> dict:
        """Load a JSON or JSONP file."""
        with open(json_path, "r", encoding="utf-8", errors="ignore") as f:
            raw = f.read()

        if not raw or not raw.strip():
            raise ValueError("Empty file")

        raw = raw.lstrip("\ufeff").strip()
        first_char = next((ch for ch in raw if not ch.isspace()), "")

        if first_char in ("{", "["):
            return json.loads(raw)

        json_str = extract_json_from_jsonp(raw)
        return json.loads(json_str)

    # ------------------------------------------------------------------
    # Partidos iterator
    # ------------------------------------------------------------------

    def _load_all_partidos(self) -> Iterator[Tuple[str, dict, Path]]:
        """
        Yield (match_id, data, json_file_path) for every JSON in partidos/.
        match_id is taken from matchInfo.id inside the JSON, not from the filename.
        """
        partidos_dir = self._get_partidos_dir()
        if not partidos_dir.exists():
            self.logger.warning(f"partidos/ dir not found: {partidos_dir}")
            return

        json_files = sorted(partidos_dir.glob("*.json"))
        if not json_files:
            self.logger.warning(f"No JSON files in: {partidos_dir}")
            return

        for json_file in json_files:
            try:
                data = self.load_json_file(json_file)
                match_id = (data.get("matchInfo") or {}).get("id")
                if not match_id:
                    self.logger.warning(f"No matchInfo.id in {json_file.name} — skipping")
                    continue
                yield match_id, data, json_file
            except Exception as e:
                self.logger.warning(f"Could not load {json_file.name}: {e}")

    # ------------------------------------------------------------------
    # Filename helpers
    # ------------------------------------------------------------------

    def _clean_filename(self, text: str, config: dict) -> str:
        if not text or text == "N/A":
            return "unknown"
        text = str(text)
        if config.get("clean_names", True):
            text = re.sub(r'[<>:"/\\|?*]', "", text)
            text = re.sub(r"[^\w\s-]", "", text)
        if config.get("replace_spaces"):
            text = text.replace(" ", config["replace_spaces"])
        if config.get("lowercase", False):
            text = text.lower()
        max_length = config.get("max_length", 100)
        if len(text) > max_length:
            text = text[:max_length]
        return text.strip()

    # ------------------------------------------------------------------
    # Save
    # ------------------------------------------------------------------

    def save_dataframe(self, df: pd.DataFrame, output_path: str) -> None:
        """Save DataFrame atomically via a temp file."""
        output_path = Path(output_path)
        tmp_path = output_path.with_suffix(".tmp")
        try:
            if self.output_format == "parquet":
                df.to_parquet(str(tmp_path), index=False, engine="pyarrow", compression="snappy")
            else:
                df.to_csv(str(tmp_path), index=False, encoding="utf-8-sig")
            tmp_path.rename(output_path)
        except Exception:
            tmp_path.unlink(missing_ok=True)
            raise
