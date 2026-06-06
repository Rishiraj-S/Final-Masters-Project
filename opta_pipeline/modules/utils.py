"""
Utility functions shared across the pipeline
"""
import os
import json
import logging
from pathlib import Path
from typing import Optional
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


def to_formations_url(match_url: str) -> str:
    """Convert match URL to formations URL"""
    match_url = normalize_url(match_url)
    if not match_url:
        return ""

    match_url = match_url.split("#")[0].split("?")[0].rstrip("/")

    # Strip any existing tab suffix so we can append /formations cleanly
    for suffix in ("/player-stats", "/formations", "/timeline", "/match-centre", "/match-timeline"):
        if match_url.endswith(suffix):
            match_url = match_url[: -len(suffix)]
            break

    return match_url.rstrip("/") + "/formations"


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


# Competition-name prefix → country folder mapping
_COMPETITION_COUNTRY: dict[str, str] = {
    'Spain':    'Spain',
    'England':  'England',
    'Germany':  'Germany',
    'France':   'France',
    'Belgium':  'Belgium',
    'Greece':   'Greece',
    'Denmark':  'Denmark',
    'Czech':    'Czech_Republic',
    'UEFA':     'Europe',
}


def get_competition_country(league_name: str) -> str:
    """Derive the country/region folder from a competition key.

    E.g. 'Spain_Primera_Division' → 'Spain', 'UEFA_Champions_League' → 'Europe'.
    Returns 'Other' for unrecognised prefixes.
    """
    for prefix, country in _COMPETITION_COUNTRY.items():
        if league_name.startswith(prefix):
            return country
    return 'Other'


def get_organized_path_reversed(
    base_dir: str,
    league_name: str,
    season: str,
    filename: str,
    subdirectory: Optional[str] = None
) -> str:
    """
    Create organized path: base_dir/{country}/{league_name}/[subdirectory]/filename

    The season is encoded in base_dir (e.g. data/2025-26/) so it is accepted
    as a parameter for API compatibility but is not added to the path.

    Example:
        get_organized_path_reversed('data/2025-26', 'Spain_Primera_Division', '2025-2026',
                                    'file.parquet', 'match_event')
        -> 'data/2025-26/Spain/Spain_Primera_Division/match_event/file.parquet'
    """
    country     = get_competition_country(league_name)
    league_clean = league_name.replace(' ', '_').replace('/', '-')

    if subdirectory:
        organized_dir = Path(base_dir) / country / league_clean / subdirectory
    else:
        organized_dir = Path(base_dir) / country / league_clean

    organized_dir.mkdir(parents=True, exist_ok=True)
    return str(organized_dir / filename)