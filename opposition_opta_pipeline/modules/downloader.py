"""
Opposition pipeline downloader.

Downloads match event JSON directly into opposition_data/{league}/{season}/partidos/
using the same Selenium Wire interception as opta_pipeline, but:
  - Skip check: any file in partidos/ whose name contains the match_id
  - Filename derived from downloaded JSON content:
      {week}_{home_short}_{away_short}_{match_id}.json
  - No cleanup step — partidos JSONs are kept permanently
"""
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
    extract_json_from_jsonp,
)


def _clean_name(text: str) -> str:
    """Clean a team name for use in a filename (remove special chars, spaces → _)."""
    text = (text or "").strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"\s+", "_", text)
    return text[:30].strip("_") or "Unknown"


class OppositionDownloader:
    """Downloads match event JSON into opposition_data/{league}/{season}/partidos/"""

    def __init__(self, config: dict, logger: logging.Logger):
        self.config = config
        self.logger = logger
        self.timeout = config.get("downloader", {}).get("timeout_per_match", 45)
        self.sleep_between = config.get("downloader", {}).get("sleep_between_matches", 1.5)

        script_dir = Path(__file__).parent.parent
        opposition_data_dir = config.get("paths", {}).get("opposition_data_dir", "opposition_data")
        if not Path(opposition_data_dir).is_absolute():
            opposition_data_dir = str(script_dir / opposition_data_dir)
        self.opposition_data_dir = opposition_data_dir

        competition = config.get("competition", {})
        self.league_name = competition.get("league_name") or "Unknown_League"
        self.season = competition.get("season", "Unknown_Season")

        self.matchevent_pattern = re.compile(
            r"https://api\.performfeeds\.com/soccerdata/matchevent/",
            re.IGNORECASE,
        )

    # ------------------------------------------------------------------
    # Paths
    # ------------------------------------------------------------------

    def _get_partidos_dir(self) -> Path:
        return Path(self.opposition_data_dir) / self.league_name / self.season / "partidos"

    def _skip_match(self, match_id: str) -> bool:
        """Return True if a partidos file already exists for this match_id."""
        partidos_dir = self._get_partidos_dir()
        if not partidos_dir.exists():
            return False
        return any(partidos_dir.glob(f"*{match_id}*"))

    # ------------------------------------------------------------------
    # Driver factory
    # ------------------------------------------------------------------

    def create_driver(self, headless: bool = True) -> webdriver.Chrome:
        """Create Selenium Wire driver with anti-detection measures."""
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

        sw_options = {"disable_encoding": True, "request_storage": "memory"}
        driver = webdriver.Chrome(options=chrome_opts, seleniumwire_options=sw_options)
        driver.scopes = [r".*api\.performfeeds\.com/soccerdata/.*"]
        driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
            "source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        })
        return driver

    # ------------------------------------------------------------------
    # Validators / helpers
    # ------------------------------------------------------------------

    def _validate_match_json(self, obj: dict) -> bool:
        if not isinstance(obj, dict):
            return False
        match_info = obj.get("matchInfo")
        live_data = obj.get("liveData")
        if not match_info or not live_data:
            return False
        events = live_data.get("event")
        return bool(events and isinstance(events, list) and len(events) > 0)

    def _scroll_page(self, driver) -> None:
        try:
            driver.execute_script("window.scrollTo(0, 0);")
            time.sleep(0.4)
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight * 0.5);")
            time.sleep(0.4)
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(0.4)
        except Exception:
            pass

    def _build_filename(self, json_obj: dict, fallback_match_id: str) -> str:
        """Derive filename from JSON content: {week}_{home}_{away}_{match_id}.json"""
        match_info = json_obj.get("matchInfo", {})
        week = str(match_info.get("week", "0")).strip()
        match_id = match_info.get("id") or fallback_match_id

        home_name = away_name = "Unknown"
        for c in match_info.get("contestant", []) or []:
            short = c.get("shortName") or c.get("name", "")
            if c.get("position") == "home":
                home_name = short
            elif c.get("position") == "away":
                away_name = short

        return f"{_clean_name(week)}_{_clean_name(home_name)}_{_clean_name(away_name)}_{match_id}.json"

    # ------------------------------------------------------------------
    # Core download
    # ------------------------------------------------------------------

    def download_match_data(self, match_url: str, match_id: str) -> Optional[str]:
        """
        Navigate to the player-stats page, capture the PerformFeeds matchevent API
        response, and save to partidos/.
        Returns path to saved file or None on failure.
        """
        driver = self.create_driver(headless=True)

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
                            captured.append({"url": req.url, "body": body_bytes, "size": len(body_bytes)})
                            self.logger.debug(f"   [matchevent] Captured: {len(body_bytes)} bytes")
                time.sleep(0.3)

            if not captured:
                self.logger.warning(f"   ⚠️  No matchevent data captured for {match_id}")
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
                self.logger.error(f"   ❌ matchevent JSON missing matchInfo/liveData for {match_id}")
                return None

            filename = self._build_filename(json_obj, match_id)
            partidos_dir = self._get_partidos_dir()
            partidos_dir.mkdir(parents=True, exist_ok=True)

            out_path = Path(unique_file_path(str(partidos_dir / filename)))
            tmp_path = out_path.with_suffix(".tmp")
            clean_json_str = json.dumps(json_obj, indent=2, ensure_ascii=False)
            try:
                tmp_path.write_text(clean_json_str, encoding="utf-8")
                tmp_path.rename(out_path)
            except Exception as write_err:
                tmp_path.unlink(missing_ok=True)
                raise write_err

            self.logger.info(f"   ✅ matchevent: {out_path.name} ({len(clean_json_str)} bytes)")
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
        max_retries: int = 3,
    ) -> Tuple[bool, Optional[str]]:
        """
        Download matchevent data for one match with skip and retry logic.
        Returns (success, path_or_None).
        """
        if self._skip_match(match_id):
            self.logger.info(f"   ⏭️  Already exists: {match_id}")
            print(f"   ⏭️  SKIP   {match_id}  (already in partidos/)")
            return True, None

        print(f"   📥  {match_id}  — downloading matchevent")

        for attempt in range(1, max_retries + 1):
            if attempt > 1:
                wait = 3 * attempt
                self.logger.info(f"   🔄 Retry {attempt}/{max_retries} for {match_id} (waiting {wait}s)...")
                print(f"   🔄 Retry {attempt}/{max_retries} for {match_id} (waiting {wait}s)...")
                time.sleep(wait)

            result_path = self.download_match_data(match_url, match_id)

            if result_path:
                print(f"   ✅ saved: {Path(result_path).name}")
                time.sleep(self.sleep_between)
                return True, result_path

        self.logger.error(f"   ❌ Failed after {max_retries} attempts: {match_id}")
        print(f"   ❌ FAILED after {max_retries} attempts: {match_id}")
        return False, None
