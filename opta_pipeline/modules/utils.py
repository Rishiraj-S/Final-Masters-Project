"""
Utility functions shared across the pipeline
"""
import os
import json
import logging
from pathlib import Path
from typing import Optional, Set
from urllib.parse import urlparse


def setup_logging(log_dir: str, level: str = "INFO") -> logging.Logger:
    """Setup logging configuration"""
    Path(log_dir).mkdir(parents=True, exist_ok=True)
    
    log_file = Path(log_dir) / "pipeline.log"
    
    logging.basicConfig(
        level=getattr(logging, level),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ]
    )
    
    return logging.getLogger("OptaPipeline")


def ensure_directories(paths: dict) -> None:
    """Create all required directories"""
    dirs_to_create = [
        paths.get('data_dir'),
        paths.get('target_dir'),
        paths.get('result_dir'),
        paths.get('logs_dir'),
        paths.get('mappings_dir')
    ]
    
    for dir_path in dirs_to_create:
        if dir_path:
            Path(dir_path).mkdir(parents=True, exist_ok=True)


def load_processed_matches(file_path: str) -> Set[str]:
    """Load set of already processed match IDs"""
    processed = set()
    
    if os.path.exists(file_path):
        with open(file_path, 'r') as f:
            processed = set(line.strip() for line in f if line.strip())
    
    return processed


def save_processed_match(file_path: str, match_id: str) -> None:
    """Add a match ID to the processed list"""
    with open(file_path, 'a') as f:
        f.write(f"{match_id}\n")


def normalize_url(url: str, base: str = "https://www.scoresway.com") -> str:
    """Normalize Scoresway URLs"""
    url = (url or "").strip()
    if not url:
        return ""
    if url.startswith("//"):
        return "https:" + url
    if url.startswith("/"):
        return base + url
    return url


def to_player_stats_url(match_url: str) -> str:
    """Convert match URL to player-stats URL"""
    match_url = normalize_url(match_url)
    if not match_url:
        return ""
    
    match_url = match_url.split("#")[0].split("?")[0]
    
    if match_url.rstrip("/").endswith("/player-stats"):
        return match_url
    
    return match_url.rstrip("/") + "/player-stats"


def extract_match_id_from_url(url: str) -> str:
    """Extract match ID from URL"""
    url = normalize_url(url)
    if not url:
        return ""
    
    if "/match/view/" in url:
        match_id = url.split("/match/view/")[-1].split("?")[0].split("/")[0].strip()
        return match_id
    
    parsed = urlparse(url)
    parts = [x for x in parsed.path.split("/") if x]
    return parts[-1] if parts else ""


def decode_body(body: bytes) -> str:
    """Decode response body to text"""
    return body.decode("utf-8", errors="ignore").lstrip("\ufeff").strip()


def extract_json_from_jsonp(raw: str) -> str:
    """Extract JSON from JSONP callback wrapper"""
    raw = raw.strip()
    if not raw:
        raise ValueError("Empty raw body")
    
    first_char = next((ch for ch in raw if not ch.isspace()), "")
    if first_char in ("{", "["):
        return raw
    
    start_obj = raw.find("{")
    start_arr = raw.find("[")
    candidates = [pos for pos in (start_obj, start_arr) if pos != -1]
    
    if not candidates:
        raise ValueError("No JSON object/array found inside raw")
    
    start = min(candidates)
    opening = raw[start]
    closing = "}" if opening == "{" else "]"
    end = raw.rfind(closing)
    
    if end == -1 or end <= start:
        raise ValueError("No valid closing bracket found")
    
    return raw[start:end + 1]


def get_match_id_from_json(raw: str, fallback_url: str) -> str:
    """Extract match ID from JSON response"""
    try:
        inner = extract_json_from_jsonp(raw)
        obj = json.loads(inner)
        mid = (obj.get("matchInfo", {}) or {}).get("id")
        if mid:
            return str(mid)
    except Exception:
        pass
    
    return extract_match_id_from_url(fallback_url)


def unique_file_path(path: str) -> str:
    """Generate unique file path if file exists"""
    if not os.path.exists(path):
        return path
    
    base, ext = os.path.splitext(path)
    for k in range(2, 200):
        candidate = f"{base}_{k}{ext}"
        if not os.path.exists(candidate):
            return candidate
    
    import time
    return f"{base}_{int(time.time())}{ext}"


def get_organized_path_reversed(
    base_dir: str, 
    league_name: str,
    season: str, 
    filename: str,
    subdirectory: Optional[str] = None
) -> str:
    """
    Create organized path: base_dir/league_name/season/[subdirectory]/filename
    
    Args:
        base_dir: Base directory (e.g., 'data/target' or 'data/result')
        league_name: League name (e.g., 'Liga_F') - FIRST level
        season: Season (e.g., '2024-2025') - SECOND level
        filename: File name (e.g., 'match123.json')
        subdirectory: Optional subdirectory (e.g., 'matches', 'squad')
    
    Returns:
        Full path with organized structure
    
    Example:
        get_organized_path_reversed('data/result', 'Liga_F', '2024-2025', 'players.parquet', 'squad')
        -> 'data/result/Liga_F/2024-2025/squad/players.parquet'
    """
    # Sanitize league name and season
    league_clean = league_name.replace(" ", "_").replace("/", "-")
    season_clean = season.replace(" ", "_").replace("/", "-")
    
    # Build path: base_dir/league/season/[subdirectory]/filename
    if subdirectory:
        organized_dir = Path(base_dir) / league_clean / season_clean / subdirectory
    else:
        organized_dir = Path(base_dir) / league_clean / season_clean
    
    organized_dir.mkdir(parents=True, exist_ok=True)
    
    return str(organized_dir / filename)