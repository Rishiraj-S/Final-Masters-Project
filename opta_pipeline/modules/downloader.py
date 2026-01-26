"""
Match data downloader - Downloads matchevent only
"""
import os
import re
import time
import json
import logging
from typing import Optional, Tuple
from pathlib import Path

from seleniumwire import webdriver
from selenium.webdriver.chrome.options import Options

from .utils import (
    decode_body, 
    get_match_id_from_json,
    unique_file_path,
    to_player_stats_url,
    get_organized_path_reversed,
    extract_json_from_jsonp
)


class MatchDownloader:
    """Downloads matchevent data from PerformFeeds API"""
    
    def __init__(self, config: dict, logger: logging.Logger):
        self.config = config
        self.logger = logger
        self.timeout = config.get('downloader', {}).get('timeout_per_match', 45)
        self.sleep_between = config.get('downloader', {}).get('sleep_between_matches', 1.5)
        self.base_target_dir = config.get('paths', {}).get('target_dir', 'data/target')
        
        # Get league and season info
        competition = config.get('competition', {})
        self.league_name = competition.get('league_name') or 'Unknown_League'
        self.season = competition.get('season', 'Unknown_Season')
        
        # API regex pattern for matchevent only
        self.matchevent_pattern = re.compile(
            r"https://api\.performfeeds\.com/soccerdata/matchevent/",
            re.IGNORECASE
        )
    
    def create_selenium_wire_driver(self, headless: bool = False) -> webdriver.Chrome:
        """Create Selenium Wire driver"""
        chrome_opts = Options()
        chrome_opts.add_argument("--start-maximized")
        chrome_opts.add_argument("--disable-gpu")
        chrome_opts.add_argument("--no-sandbox")
        chrome_opts.add_argument("--disable-dev-shm-usage")
        chrome_opts.add_argument("--lang=en-GB")
        
        if headless:
            chrome_opts.add_argument("--headless=new")
        
        sw_options = {
            "disable_encoding": True,
            "request_storage": "memory",
        }
        
        driver = webdriver.Chrome(options=chrome_opts, seleniumwire_options=sw_options)
        driver.scopes = [r".*api\.performfeeds\.com/soccerdata/.*"]
        
        return driver
    
    def download_match_data(self, match_url: str, match_id: str) -> Optional[str]:
        """
        Download matchevent data
        
        Returns:
            Path to saved JSON file or None
        """
        driver = self.create_selenium_wire_driver(headless=False)
        
        try:
            player_stats_url = to_player_stats_url(match_url)
            
            self.logger.debug(f"   Opening: {player_stats_url}")
            driver.get(player_stats_url)
            
            # Scroll to trigger loading
            try:
                driver.execute_script("window.scrollTo(0, 0);")
                time.sleep(0.5)
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight * 0.5);")
                time.sleep(0.5)
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(0.5)
            except Exception:
                pass
            
            # Collect matchevent responses only
            captured = []
            seen_urls = set()
            start = time.time()
            
            while time.time() - start < self.timeout:
                for req in driver.requests:
                    if not req.url or req.url in seen_urls:
                        continue
                    
                    if req.response is None or req.response.body is None:
                        continue
                    
                    seen_urls.add(req.url)
                    
                    # Check if matchevent endpoint
                    if self.matchevent_pattern.search(req.url):
                        body_bytes = req.response.body or b""
                        if len(body_bytes) > 100:
                            captured.append({
                                'url': req.url,
                                'body': body_bytes,
                                'size': len(body_bytes)
                            })
                            self.logger.debug(f"   📦 Captured matchevent: {len(body_bytes)} bytes")
                
                time.sleep(0.3)
            
            # Save the largest response
            if captured:
                largest = max(captured, key=lambda x: x['size'])
                raw_text = decode_body(largest['body'])
                
                if raw_text:
                    # Get match ID from response
                    try:
                        final_match_id = get_match_id_from_json(raw_text, largest['url'])
                        if not final_match_id or final_match_id == "unknown_match":
                            final_match_id = match_id
                    except:
                        final_match_id = match_id
                    
                    # Extract clean JSON from JSONP wrapper
                    try:
                        clean_json_str = extract_json_from_jsonp(raw_text)
                        # Validate it's proper JSON
                        json_obj = json.loads(clean_json_str)
                        # Pretty print the JSON
                        clean_json_str = json.dumps(json_obj, indent=2, ensure_ascii=False)
                    except Exception as e:
                        self.logger.warning(f"   ⚠️  Could not clean JSONP wrapper: {e}")
                        # Fall back to raw text if cleaning fails
                        clean_json_str = raw_text
                    
                    # Save to matchdata directory
                    out_path = get_organized_path_reversed(
                        self.base_target_dir,
                        self.league_name,
                        self.season,
                        f"{final_match_id}.json",
                        subdirectory='matchdata'
                    )
                    
                    out_path = unique_file_path(out_path)
                    
                    with open(out_path, "w", encoding="utf-8") as f:
                        f.write(clean_json_str)
                    
                    self.logger.info(f"   ✅ Downloaded: {Path(out_path).name} ({len(clean_json_str)} bytes, clean JSON)")
                    
                    return out_path
            
            self.logger.warning(f"   ⚠️  No matchevent data captured")
            return None
            
        except Exception as e:
            self.logger.error(f"   ❌ Download failed: {e}")
            return None
            
        finally:
            driver.quit()
    
    def download_match(
        self,
        match_id: str,
        match_url: str,
        competition_id: Optional[str] = None
    ) -> Tuple[bool, Optional[str]]:
        """
        Download data for a match
        
        Returns:
            (success, json_path)
        """
        # Check if already exists
        existing_json = Path(get_organized_path_reversed(
            self.base_target_dir,
            self.league_name,
            self.season,
            f"{match_id}.json",
            subdirectory='matchdata'
        ))
        
        if existing_json.exists():
            self.logger.info(f"   ⏭️  Already exists: {match_id}")
            return True, str(existing_json)
        
        # Download
        result = self.download_match_data(match_url, match_id)
        
        if result:
            time.sleep(self.sleep_between)
            return True, result
        
        return False, result