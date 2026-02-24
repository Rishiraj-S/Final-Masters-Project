"""
Match data downloader - Downloads matchevent + lineup (matchcentre) data
in a single browser session per match.
"""
import os
import re
import time
import json
import logging
from typing import Optional, Tuple, Dict
from pathlib import Path

from seleniumwire import webdriver
from selenium.webdriver.chrome.options import Options

from .utils import (
    decode_body,
    get_match_id_from_json,
    unique_file_path,
    to_player_stats_url,
    to_formations_url,
    get_organized_path_reversed,
    extract_json_from_jsonp
)


class MatchDownloader:
    """Downloads matchevent + lineup data from PerformFeeds API"""

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

        # PerformFeeds API patterns
        # matchevent  → /soccerdata/matchevent/
        # match feed  → /soccerdata/match/  (lineup + basic match info)
        self.matchevent_pattern = re.compile(
            r"https://api\.performfeeds\.com/soccerdata/matchevent/",
            re.IGNORECASE
        )
        # "match" endpoint – any soccerdata/match/ call that is NOT matchevent
        # (matchstats, matchfacts, etc. are excluded so we only grab the lineup feed)
        self.match_lineup_pattern = re.compile(
            r"https://api\.performfeeds\.com/soccerdata/match/(?!event)",
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

    def _validate_lineup_json(self, json_obj: dict) -> bool:
        """Validate that the JSON has lineup data (liveData.lineUp array)."""
        if not isinstance(json_obj, dict):
            return False
        live_data = json_obj.get("liveData")
        if not live_data:
            return False
        lineup = live_data.get("lineUp")
        return bool(lineup and isinstance(lineup, list) and len(lineup) > 0)

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
    # Core download – single driver session, two page navigations
    # ------------------------------------------------------------------

    def download_match_data(
        self,
        match_url: str,
        match_id: str,
        need_matchevent: bool = True,
        need_lineup: bool = True,
    ) -> Dict[str, Optional[str]]:
        """
        Download matchevent and/or lineup data for a match.

        Navigates to:
          1. /formations  → captures PerformFeeds match feed (lineup)
          2. /player-stats → captures PerformFeeds matchevent feed

        Returns:
            dict with 'matchevent_path' and 'lineup_path' (None if not captured)
        """
        result: Dict[str, Optional[str]] = {
            "matchevent_path": None,
            "lineup_path": None,
        }

        driver = self.create_selenium_wire_driver(headless=True)

        try:
            # --------------------------------------------------------
            # PHASE 1 – Formations page (lineup / match-centre data)
            # --------------------------------------------------------
            if need_lineup:
                formations_url = to_formations_url(match_url)
                self.logger.debug(f"   [lineup] Opening: {formations_url}")
                driver.get(formations_url)
                self._scroll_page(driver)

                # Active polling loop – same pattern as matchevent capture.
                # The formations page sometimes takes 15-20 s to fire its API
                # call, so a static sleep is not reliable.
                lineup_candidates: list = []
                seen_lineup_urls: set = set()
                start = time.time()

                while time.time() - start < self.timeout:
                    for req in driver.requests:
                        if not req.url or req.url in seen_lineup_urls:
                            continue
                        if req.response is None or req.response.body is None:
                            continue
                        seen_lineup_urls.add(req.url)
                        if (
                            self.match_lineup_pattern.search(req.url)
                            and len(req.response.body) > 200
                        ):
                            lineup_candidates.append({
                                "url": req.url,
                                "body": req.response.body,
                                "size": len(req.response.body),
                            })
                            self.logger.debug(
                                f"   [lineup] Captured: {req.url} "
                                f"({len(req.response.body)} bytes)"
                            )
                    # Stop early once we have at least one response
                    if lineup_candidates:
                        break
                    time.sleep(0.5)

                if lineup_candidates:
                    largest = max(lineup_candidates, key=lambda x: x["size"])
                    raw_text = decode_body(largest["body"])
                    if raw_text:
                        try:
                            clean_json_str = extract_json_from_jsonp(raw_text)
                            json_obj = json.loads(clean_json_str)
                        except Exception as e:
                            self.logger.error(
                                f"   ❌ Invalid lineup JSON for {match_id}: {e}"
                            )
                            json_obj = None

                        if json_obj and isinstance(json_obj, dict) and (
                            json_obj.get("matchInfo") or json_obj.get("liveData")
                        ):
                            # Log the actual liveData keys so we can inspect structure
                            live_keys = list(
                                (json_obj.get("liveData") or {}).keys()
                            )
                            self.logger.info(
                                f"   [lineup] liveData keys: {live_keys}"
                            )
                            out_path = get_organized_path_reversed(
                                self.base_target_dir,
                                self.league_name,
                                self.season,
                                f"{match_id}.json",
                                subdirectory="matchcentre",
                            )
                            out_path = unique_file_path(out_path)
                            with open(out_path, "w", encoding="utf-8") as f:
                                f.write(
                                    json.dumps(json_obj, indent=2, ensure_ascii=False)
                                )
                            self.logger.info(
                                f"   ✅ matchcentre: {Path(out_path).name} "
                                f"({len(raw_text)} bytes)"
                            )
                            result["lineup_path"] = out_path
                        elif json_obj:
                            self.logger.warning(
                                f"   ⚠️  matchcentre JSON has no matchInfo/liveData "
                                f"for {match_id}"
                            )
                            print(f"   ⚠️  [lineup] JSON structure invalid for {match_id}")
                else:
                    self.logger.warning(
                        f"   ⚠️  No match-centre feed captured for {match_id} "
                        f"(formations page)"
                    )
                    print(f"   ⚠️  [lineup] No API response captured for {match_id}")

                # Clear captured requests before navigating to the next page
                del driver.requests

            # --------------------------------------------------------
            # PHASE 2 – Player-stats page (matchevent data)
            # --------------------------------------------------------
            if need_matchevent:
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

                if captured:
                    largest = max(captured, key=lambda x: x["size"])
                    raw_text = decode_body(largest["body"])
                    if raw_text:
                        try:
                            clean_json_str = extract_json_from_jsonp(raw_text)
                            json_obj = json.loads(clean_json_str)
                        except Exception as e:
                            self.logger.error(
                                f"   ❌ Invalid matchevent JSON for {match_id}: {e}"
                            )
                            json_obj = None

                        if json_obj and self._validate_match_json(json_obj):
                            try:
                                final_match_id = get_match_id_from_json(
                                    raw_text, largest["url"]
                                )
                                if not final_match_id or final_match_id == "unknown_match":
                                    final_match_id = match_id
                            except Exception:
                                final_match_id = match_id

                            clean_json_str = json.dumps(
                                json_obj, indent=2, ensure_ascii=False
                            )
                            out_path = get_organized_path_reversed(
                                self.base_target_dir,
                                self.league_name,
                                self.season,
                                f"{final_match_id}.json",
                                subdirectory="matchdata",
                            )
                            out_path = unique_file_path(out_path)
                            with open(out_path, "w", encoding="utf-8") as f:
                                f.write(clean_json_str)
                            self.logger.info(
                                f"   ✅ matchevent: {Path(out_path).name} ({len(clean_json_str)} bytes)"
                            )
                            result["matchevent_path"] = out_path
                        elif json_obj:
                            self.logger.error(
                                f"   ❌ matchevent JSON missing matchInfo/liveData for {match_id}"
                            )
                else:
                    self.logger.warning(
                        f"   ⚠️  No matchevent data captured for {match_id}"
                    )
                    print(f"   ⚠️  [matchevent] No API response captured for {match_id}")

        except Exception as e:
            self.logger.error(f"   ❌ Download failed for {match_id}: {e}")

        finally:
            driver.quit()

        return result

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
        Download matchevent + lineup data for a match, with incremental skip logic.

        A match is only fully skipped when BOTH files already exist.
        Missing files are (re-)downloaded on the next pipeline run.

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
        matchcentre_path = Path(
            get_organized_path_reversed(
                self.base_target_dir,
                self.league_name,
                self.season,
                f"{match_id}.json",
                subdirectory="matchcentre",
            )
        )

        matchevent_exists = (
            matchdata_path.exists()
            or self._parquet_exists_for_match(match_id, 'match_event')
        )
        lineup_exists = (
            matchcentre_path.exists()
            or self._parquet_exists_for_match(match_id, 'lineup')
        )

        if matchevent_exists and lineup_exists:
            self.logger.info(f"   ⏭️  Already exists (matchevent + lineup): {match_id}")
            print(f"   ⏭️  SKIP   {match_id}  (both files exist)")
            return True, str(matchdata_path)

        if matchevent_exists:
            self.logger.info(f"   ⏭️  matchevent exists, fetching lineup only: {match_id}")
            print(f"   📥  {match_id}  — lineup missing, will download")
        elif lineup_exists:
            self.logger.info(f"   ⏭️  lineup exists, fetching matchevent only: {match_id}")
            print(f"   📥  {match_id}  — matchevent missing, will download")
        else:
            print(f"   📥  {match_id}  — downloading matchevent + lineup")

        # Download with retries
        for attempt in range(1, max_retries + 1):
            if attempt > 1:
                wait = 3 * attempt
                self.logger.info(
                    f"   🔄 Retry {attempt}/{max_retries} for {match_id} (waiting {wait}s)..."
                )
                print(f"   🔄 Retry {attempt}/{max_retries} for {match_id} (waiting {wait}s)...")
                time.sleep(wait)

            result = self.download_match_data(
                match_url,
                match_id,
                need_matchevent=not matchevent_exists,
                need_lineup=not lineup_exists,
            )

            new_matchevent = result.get("matchevent_path")
            new_lineup = result.get("lineup_path")

            # Update flags for retry decisions
            if new_matchevent:
                matchevent_exists = True
                print(f"   ✅ matchevent saved: {Path(new_matchevent).name}")
            if new_lineup:
                lineup_exists = True
                print(f"   ✅ lineup saved:     {Path(new_lineup).name}")

            if matchevent_exists:
                # Core data present – success even if lineup capture failed
                if not new_lineup and not lineup_exists:
                    print(f"   ⚠️  lineup not captured for {match_id} (continuing)")
                time.sleep(self.sleep_between)
                return True, new_matchevent or str(matchdata_path)

        self.logger.error(f"   ❌ Failed after {max_retries} attempts: {match_id}")
        print(f"   ❌ FAILED after {max_retries} attempts: {match_id}")
        return False, None
