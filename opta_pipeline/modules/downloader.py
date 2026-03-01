"""
Match data downloader - Downloads matchevent data in a single browser session per match.

Lineup and formation data is embedded in the matchevent JSON as typeId=34 events
and is extracted by the LineupTransformer directly from matchdata/*.json.
No separate download is required.
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
        self.base_result_dir = config.get('paths', {}).get('result_dir', 'data/result')

        competition = config.get('competition', {})
        self.league_name = competition.get('league_name') or 'Unknown_League'
        self.season = competition.get('season', 'Unknown_Season')

        # PerformFeeds API pattern for matchevent feed
        self.matchevent_pattern = re.compile(
            r"https://api\.performfeeds\.com/soccerdata/matchevent/",
            re.IGNORECASE
        )

    # ------------------------------------------------------------------
    # Skip helpers
    # ------------------------------------------------------------------

    def _parquet_exists_for_match(self, match_id: str, subdirectory: str) -> bool:
        """Return True if a parquet output file for match_id already exists in result dir."""
        result_dir = Path(get_organized_path_reversed(
            self.base_result_dir,
            self.league_name,
            self.season,
            '',
            subdirectory=subdirectory,
        ))
        if not result_dir.exists():
            return False
        return any(result_dir.glob(f"*{match_id}*"))

    # ------------------------------------------------------------------
    # Driver factory
    # ------------------------------------------------------------------

    def create_selenium_wire_driver(self, headless: bool = True) -> webdriver.Chrome:
        """Create Selenium Wire driver with anti-detection measures"""
        chrome_opts = Options()
        chrome_opts.add_argument("--start-maximized")
        chrome_opts.add_argument("--disable-gpu")
        chrome_opts.add_argument("--no-sandbox")
        chrome_opts.add_argument("--disable-dev-shm-usage")
        chrome_opts.add_argument("--lang=en-GB")
        chrome_opts.add_argument(
            "--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
        )
        chrome_opts.add_argument("--disable-blink-features=AutomationControlled")
        chrome_opts.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_opts.add_experimental_option("useAutomationExtension", False)

        if headless:
            chrome_opts.add_argument("--headless=new")
            chrome_opts.add_argument("--window-size=1920,1080")

        sw_options = {
            "disable_encoding": True,
            "request_storage": "memory",
        }

        driver = webdriver.Chrome(options=chrome_opts, seleniumwire_options=sw_options)
        driver.scopes = [r".*api\.performfeeds\.com/soccerdata/.*"]

        driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
            "source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        })

        return driver

    # ------------------------------------------------------------------
    # Validators
    # ------------------------------------------------------------------

    def _validate_match_json(self, json_obj: dict) -> bool:
        """Validate that the JSON has the expected Opta matchevent structure."""
        if not isinstance(json_obj, dict):
            return False
        match_info = json_obj.get("matchInfo")
        live_data = json_obj.get("liveData")
        if not match_info or not live_data:
            return False
        events = live_data.get("event")
        if not events or not isinstance(events, list) or len(events) == 0:
            return False
        return True

    # ------------------------------------------------------------------
    # Scroll helper
    # ------------------------------------------------------------------

    def _scroll_page(self, driver) -> None:
        """Scroll to trigger lazy-loaded data"""
        try:
            driver.execute_script("window.scrollTo(0, 0);")
            time.sleep(0.4)
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight * 0.5);")
            time.sleep(0.4)
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(0.4)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Core download – single driver session, single page navigation
    # ------------------------------------------------------------------

    def download_match_data(self, match_url: str, match_id: str) -> Optional[str]:
        """
        Download matchevent data for a match.

        Navigates to the player-stats page and captures the PerformFeeds
        matchevent feed. The matchevent JSON contains all events including
        typeId=34 (Team Setup) which holds lineup and formation data.

        Returns:
            Path to the saved JSON file, or None if capture failed.
        """
        driver = self.create_selenium_wire_driver(headless=True)

        try:
            player_stats_url = to_player_stats_url(match_url)
            self.logger.debug(f"   [matchevent] Opening: {player_stats_url}")
            driver.get(player_stats_url)
            self._scroll_page(driver)

            captured = []
            seen_urls: set = set()
            start = time.time()

            while time.time() - start < self.timeout:
                for req in driver.requests:
                    if not req.url or req.url in seen_urls:
                        continue
                    if req.response is None or req.response.body is None:
                        continue
                    seen_urls.add(req.url)
                    if self.matchevent_pattern.search(req.url):
                        body_bytes = req.response.body or b""
                        if len(body_bytes) > 100:
                            captured.append({
                                "url": req.url,
                                "body": body_bytes,
                                "size": len(body_bytes),
                            })
                            self.logger.debug(
                                f"   [matchevent] Captured: {len(body_bytes)} bytes"
                            )
                time.sleep(0.3)

            if not captured:
                self.logger.warning(f"   ⚠️  No matchevent data captured for {match_id}")
                print(f"   ⚠️  [matchevent] No API response captured for {match_id}")
                return None

            largest = max(captured, key=lambda x: x["size"])
            raw_text = decode_body(largest["body"])
            if not raw_text:
                return None

            try:
                clean_json_str = extract_json_from_jsonp(raw_text)
                json_obj = json.loads(clean_json_str)
            except Exception as e:
                self.logger.error(f"   ❌ Invalid matchevent JSON for {match_id}: {e}")
                return None

            if not self._validate_match_json(json_obj):
                self.logger.error(
                    f"   ❌ matchevent JSON missing matchInfo/liveData for {match_id}"
                )
                return None

            try:
                final_match_id = get_match_id_from_json(raw_text, largest["url"])
                if not final_match_id or final_match_id == "unknown_match":
                    final_match_id = match_id
            except Exception:
                final_match_id = match_id

            clean_json_str = json.dumps(json_obj, indent=2, ensure_ascii=False)
            out_path = Path(get_organized_path_reversed(
                self.base_target_dir,
                self.league_name,
                self.season,
                f"{final_match_id}.json",
                subdirectory="matchdata",
            ))
            out_path = Path(unique_file_path(str(out_path)))
            tmp_path = out_path.with_suffix('.tmp')
            try:
                tmp_path.write_text(clean_json_str, encoding="utf-8")
                tmp_path.rename(out_path)
            except Exception as write_err:
                tmp_path.unlink(missing_ok=True)
                raise write_err

            self.logger.info(
                f"   ✅ matchevent: {out_path.name} ({len(clean_json_str)} bytes)"
            )
            return str(out_path)

        except Exception as e:
            self.logger.error(f"   ❌ Download failed for {match_id}: {e}")
            return None

        finally:
            driver.quit()

    # ------------------------------------------------------------------
    # Public entry point (with skip + retry logic)
    # ------------------------------------------------------------------

    def download_match(
        self,
        match_id: str,
        match_url: str,
        competition_id: Optional[str] = None,
        max_retries: int = 3,
    ) -> Tuple[bool, Optional[str]]:
        """
        Download matchevent data for a match, with skip and retry logic.

        Skips if matchdata JSON or match_event parquet already exists.

        Returns:
            (success, matchevent_json_path)
        """
        matchdata_path = Path(
            get_organized_path_reversed(
                self.base_target_dir,
                self.league_name,
                self.season,
                f"{match_id}.json",
                subdirectory="matchdata",
            )
        )

        already_exists = (
            matchdata_path.exists()
            or self._parquet_exists_for_match(match_id, 'match_event')
        )

        if already_exists:
            self.logger.info(f"   ⏭️  Already exists: {match_id}")
            print(f"   ⏭️  SKIP   {match_id}  (already exists)")
            return True, str(matchdata_path)

        print(f"   📥  {match_id}  — downloading matchevent")

        for attempt in range(1, max_retries + 1):
            if attempt > 1:
                wait = 3 * attempt
                self.logger.info(
                    f"   🔄 Retry {attempt}/{max_retries} for {match_id} (waiting {wait}s)..."
                )
                print(f"   🔄 Retry {attempt}/{max_retries} for {match_id} (waiting {wait}s)...")
                # Remove any stale/partial file from the previous attempt so it
                # does not cause the next run to skip a corrupt download.
                matchdata_path.unlink(missing_ok=True)
                time.sleep(wait)

            result_path = self.download_match_data(match_url, match_id)

            if result_path:
                print(f"   ✅ matchevent saved: {Path(result_path).name}")
                time.sleep(self.sleep_between)
                return True, result_path

        self.logger.error(f"   ❌ Failed after {max_retries} attempts: {match_id}")
        print(f"   ❌ FAILED after {max_retries} attempts: {match_id}")
        return False, None
