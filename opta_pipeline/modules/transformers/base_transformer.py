"""
Base transformer with common functionality
"""
import json
import logging
from pathlib import Path
from typing import Optional
import pandas as pd
import re

from ..utils import extract_json_from_jsonp, get_organized_path_reversed


class BaseTransformer:
    """Base class for all transformers"""
    
    def __init__(self, config: dict, logger: logging.Logger):
        self.config = config
        self.logger = logger
        
        self.base_target_dir = config.get('paths', {}).get('target_dir', 'data/target')
        self.base_result_dir = config.get('paths', {}).get('result_dir', 'data/result')
        
        competition = config.get('competition', {})
        self.league_name = competition.get('league_name') or 'Unknown_League'
        self.season = competition.get('season', 'Unknown_Season'  )
        
        self.output_format = config.get('output', {}).get('format', 'parquet')
    
    def load_json_file(self, json_path: Path) -> dict:
        """Load JSON or JSONP file"""
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
    
    def _clean_filename(self, text: str, config: dict) -> str:
        """Clean text for filename"""
        if not text or text == "N/A":
            return "unknown"
        
        text = str(text)
        
        if config.get('clean_names', True):
            text = re.sub(r'[<>:"/\\|?*]', '', text)
            text = re.sub(r'[^\w\s-]', '', text)
        
        if config.get('replace_spaces'):
            text = text.replace(' ', config['replace_spaces'])
        
        if config.get('lowercase', False):
            text = text.lower()
        
        max_length = config.get('max_length', 100)
        if len(text) > max_length:
            text = text[:max_length]
        
        return text.strip()
    
    def _output_exists(self, match_id: str, subdirectory: str) -> bool:
        """Return True if a result parquet for match_id already exists."""
        result_dir = Path(get_organized_path_reversed(
            self.base_result_dir, self.league_name, self.season, '',
            subdirectory=subdirectory,
        ))
        if not result_dir.exists():
            return False
        # Match the trailing id segment, not a loose substring: match_id '123'
        # must not be considered "already transformed" because a file ending
        # '..._1234.parquet' exists. Filenames end with '_{match_id}.{ext}'.
        mid = str(match_id)
        return any(
            f.stem == mid or f.stem.endswith(f"_{mid}")
            for f in result_dir.glob("*")
        )

    def save_dataframe(self, df: pd.DataFrame, output_path: str) -> None:
        """Save DataFrame to parquet or CSV, writing atomically via a temp file."""
        output_path = Path(output_path)
        tmp_path = output_path.with_suffix('.tmp')
        try:
            if self.output_format == 'parquet':
                df.to_parquet(str(tmp_path), index=False, engine='pyarrow', compression='snappy')
            else:
                df.to_csv(str(tmp_path), index=False, encoding="utf-8-sig")
            tmp_path.rename(output_path)
        except Exception:
            tmp_path.unlink(missing_ok=True)
            raise