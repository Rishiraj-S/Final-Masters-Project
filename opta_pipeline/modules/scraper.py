"""
Match URL scraper from Scoresway results pages
"""
import time
import logging
import pandas as pd
from typing import List, Dict, Optional
from bs4 import BeautifulSoup

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    NoSuchElementException, TimeoutException,
    ElementClickInterceptedException, StaleElementReferenceException,
)

from .utils import normalize_url


class MatchScraper:
    """Scrapes match URLs from Scoresway results pages"""

    # Common pagination selectors found in Opta widgets
    PAGINATION_SELECTORS = [
        # "Previous" style buttons (navigate to older results)
        "#Opta_0 .Opta-Previous",
        "#Opta_0 .Opta-Prev",
        "#Opta_0 button.Opta-Prev",
        "#Opta_0 [class*='Opta'][class*='revious']",
        "#Opta_0 [class*='Opta'][class*='rev']",
        # "Load More" / "Show More" style buttons
        "#Opta_0 .Opta-Load-More",
        "#Opta_0 .Opta-Show-More",
        "#Opta_0 [class*='Opta'][class*='More']",
        "#Opta_0 [class*='Opta'][class*='Load']",
        # Generic nav controls
        "#Opta_0 .Opta-Nav .Opta-Previous",
        "#Opta_0 .Opta-Controls button",
        "#Opta_0 .Opta-Navigation button",
    ]

    def __init__(self, config: dict, logger: logging.Logger):
        self.config = config
        self.logger = logger
        self.timeout = config.get('scraper', {}).get('timeout_seconds', 60)
        self.cookie_wait = config.get('scraper', {}).get('cookie_wait_seconds', 3)
        self.scroll_delay = config.get('scraper', {}).get('scroll_delay', 0.9)
        self.max_pagination_clicks = config.get('scraper', {}).get('max_pagination_clicks', 50)

    def create_driver(self, headless: bool = False) -> webdriver.Chrome:
        """Create Selenium Chrome driver with anti-detection measures."""
        opts = Options()
        opts.add_argument("--start-maximized")
        opts.add_argument("--lang=en-GB")
        opts.add_argument("--disable-notifications")
        opts.add_argument("--disable-gpu")
        opts.add_argument("--no-sandbox")
        opts.add_argument("--disable-dev-shm-usage")

        # Anti-detection: realistic user-agent to avoid Access Denied blocks
        opts.add_argument(
            "--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
        )
        # Disable automation flags that sites use to detect bots
        opts.add_argument("--disable-blink-features=AutomationControlled")
        opts.add_experimental_option("excludeSwitches", ["enable-automation"])
        opts.add_experimental_option("useAutomationExtension", False)

        if headless:
            opts.add_argument("--headless=new")
            # Extra: set a realistic window size in headless mode
            opts.add_argument("--window-size=1920,1080")

        driver = webdriver.Chrome(options=opts)
        driver.set_page_load_timeout(90)

        # Remove navigator.webdriver flag that reveals automation
        driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
            "source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        })

        return driver

    def try_click_cookies(self, driver: webdriver.Chrome) -> bool:
        """Attempt to click cookie consent banner"""
        candidates = [
            "//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'accept')]",
            "//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'agree')]",
            "//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'consent')]",
        ]

        for xpath in candidates:
            try:
                element = WebDriverWait(driver, self.cookie_wait).until(
                    EC.element_to_be_clickable((By.XPATH, xpath))
                )
                element.click()
                time.sleep(1)
                self.logger.info("✓ Cookie banner accepted")
                return True
            except Exception:
                pass

        return False

    def warmup_scroll(self, driver: webdriver.Chrome) -> None:
        """Scroll page to trigger lazy-loading"""
        try:
            driver.execute_script("window.scrollTo(0, 0);")
            time.sleep(0.4)

            for frac in [0.25, 0.55, 0.85, 1.0]:
                driver.execute_script(
                    "window.scrollTo(0, document.body.scrollHeight * arguments[0]);",
                    frac
                )
                time.sleep(self.scroll_delay)

            self.logger.debug("✓ Page scrolled to trigger lazy-loading")
        except Exception as e:
            self.logger.warning(f"Scroll failed: {e}")

    def wait_for_opta_widget(self, driver: webdriver.Chrome) -> None:
        """Wait for Opta widget to load"""
        # Wait for #Opta_0 to exist
        WebDriverWait(driver, self.timeout).until(
            EC.presence_of_element_located((By.ID, "Opta_0"))
        )

        # Wait for match links to appear
        WebDriverWait(driver, self.timeout).until(
            lambda d: len(d.find_elements(By.CSS_SELECTOR, "#Opta_0 a.Opta-MatchLink")) > 0
        )

        self.logger.info("✓ Opta widget loaded")

    def _detect_pagination(self, driver: webdriver.Chrome) -> dict:
        """Detect what pagination controls exist inside the Opta widget.

        Returns a dict with info about discovered controls for diagnostics.
        """
        info = {'buttons': [], 'all_buttons_in_widget': []}

        # Check all known selectors
        for selector in self.PAGINATION_SELECTORS:
            try:
                elements = driver.find_elements(By.CSS_SELECTOR, selector)
                for elem in elements:
                    try:
                        info['buttons'].append({
                            'selector': selector,
                            'class': elem.get_attribute('class') or '',
                            'text': elem.text.strip(),
                            'visible': elem.is_displayed(),
                            'enabled': elem.is_enabled(),
                            'tag': elem.tag_name,
                        })
                    except StaleElementReferenceException:
                        pass
            except Exception:
                pass

        # Also scan for ANY clickable elements (buttons, anchors) inside the widget
        # that might be pagination controls
        try:
            all_btns = driver.find_elements(By.CSS_SELECTOR, "#Opta_0 button, #Opta_0 a[role='button']")
            for btn in all_btns:
                try:
                    cls = btn.get_attribute('class') or ''
                    txt = btn.text.strip()
                    info['all_buttons_in_widget'].append({
                        'class': cls,
                        'text': txt,
                        'visible': btn.is_displayed(),
                        'tag': btn.tag_name,
                    })
                except StaleElementReferenceException:
                    pass
        except Exception:
            pass

        return info

    def _find_pagination_button(self, driver: webdriver.Chrome):
        """Find the clickable pagination button (Previous/Load More) in the widget.

        Returns the WebElement if found, or None.
        """
        for selector in self.PAGINATION_SELECTORS:
            try:
                elements = driver.find_elements(By.CSS_SELECTOR, selector)
                for elem in elements:
                    try:
                        if elem.is_displayed() and elem.is_enabled():
                            return elem
                    except StaleElementReferenceException:
                        continue
            except Exception:
                continue

        # Fallback: look for any button inside #Opta_0 whose text
        # contains "previous", "older", "more", "load", "earlier"
        try:
            all_btns = driver.find_elements(By.CSS_SELECTOR, "#Opta_0 button")
            for btn in all_btns:
                try:
                    txt = (btn.text or '').strip().lower()
                    cls = (btn.get_attribute('class') or '').lower()
                    if any(kw in txt or kw in cls for kw in
                           ['previous', 'prev', 'older', 'more', 'load', 'earlier']):
                        if btn.is_displayed() and btn.is_enabled():
                            return btn
                except StaleElementReferenceException:
                    continue
        except Exception:
            pass

        return None

    def _get_match_count(self, driver: webdriver.Chrome) -> int:
        """Count current match links visible in the Opta widget."""
        try:
            return len(driver.find_elements(By.CSS_SELECTOR, "#Opta_0 a.Opta-MatchLink"))
        except Exception:
            return 0

    def _load_all_pages(self, driver: webdriver.Chrome) -> None:
        """Repeatedly click pagination to load all available results.

        Handles both "Load More" (accumulative) and "Previous" (page-swap) patterns.
        Collects match IDs across pages so we can merge later.
        """
        # First, detect and log pagination info
        pag_info = self._detect_pagination(driver)

        if pag_info['buttons']:
            self.logger.info(f"📄 Found {len(pag_info['buttons'])} pagination control(s):")
            for b in pag_info['buttons']:
                self.logger.info(f"   → {b['tag']}.{b['class']} text=\"{b['text']}\" "
                                 f"visible={b['visible']} enabled={b['enabled']}")
        else:
            self.logger.info("📄 No known pagination selectors found")
            if pag_info['all_buttons_in_widget']:
                self.logger.info(f"   (Found {len(pag_info['all_buttons_in_widget'])} "
                                 f"generic buttons in widget)")
                for b in pag_info['all_buttons_in_widget']:
                    self.logger.debug(f"   → {b['tag']}.{b['class']} text=\"{b['text']}\"")
            return

        # Click the pagination button repeatedly until:
        #  - Button disappears or becomes disabled
        #  - Match count stops growing (for "Load More")
        #  - Max clicks reached
        clicks = 0
        prev_match_count = self._get_match_count(driver)

        while clicks < self.max_pagination_clicks:
            btn = self._find_pagination_button(driver)
            if not btn:
                self.logger.info("📄 Pagination: no more clickable buttons found")
                break

            try:
                # Scroll button into view
                driver.execute_script(
                    "arguments[0].scrollIntoView({block: 'center'});", btn
                )
                time.sleep(0.3)

                btn.click()
                clicks += 1

                # Wait for content to update
                time.sleep(1.5)

                new_count = self._get_match_count(driver)
                self.logger.info(f"   📄 Page click #{clicks}: "
                                 f"{new_count} matches visible (was {prev_match_count})")

                # For "Load More" pattern: if count didn't grow, we're done
                if new_count == prev_match_count:
                    # Give it one more chance (sometimes loading is slow)
                    time.sleep(2)
                    new_count = self._get_match_count(driver)
                    if new_count == prev_match_count:
                        self.logger.info("📄 Match count unchanged — all results loaded")
                        break

                prev_match_count = new_count

            except (ElementClickInterceptedException, StaleElementReferenceException) as e:
                self.logger.warning(f"   ⚠️  Click failed ({type(e).__name__}), retrying...")
                time.sleep(1)
                continue
            except Exception as e:
                self.logger.warning(f"   ⚠️  Pagination error: {e}")
                break

        if clicks >= self.max_pagination_clicks:
            self.logger.warning(f"⚠️  Hit max pagination clicks ({self.max_pagination_clicks})")
        elif clicks > 0:
            self.logger.info(f"✅ Pagination complete after {clicks} click(s), "
                             f"{self._get_match_count(driver)} matches visible")

    def _collect_all_pages_html(self, driver: webdriver.Chrome) -> List[str]:
        """For page-swap style pagination (Previous/Next), collect HTML from each page.

        Returns list of innerHTML strings from each page.
        """
        pages_html = []

        # Collect current page first
        opta_el = driver.find_element(By.ID, "Opta_0")
        pages_html.append(opta_el.get_attribute("innerHTML") or "")

        seen_match_ids = set()
        # Extract match IDs from current page
        current_matches = driver.find_elements(By.CSS_SELECTOR,
                                                "#Opta_0 tbody.Opta-fixture")
        for m in current_matches:
            try:
                mid = m.get_attribute("data-match") or ""
                if mid:
                    seen_match_ids.add(mid)
            except StaleElementReferenceException:
                pass

        clicks = 0
        while clicks < self.max_pagination_clicks:
            btn = self._find_pagination_button(driver)
            if not btn:
                break

            try:
                driver.execute_script(
                    "arguments[0].scrollIntoView({block: 'center'});", btn
                )
                time.sleep(0.3)
                btn.click()
                clicks += 1
                time.sleep(2)

                # Wait for widget to update
                WebDriverWait(driver, 10).until(
                    lambda d: len(d.find_elements(
                        By.CSS_SELECTOR, "#Opta_0 a.Opta-MatchLink")) > 0
                )

                # Check if we got new matches
                new_matches = driver.find_elements(By.CSS_SELECTOR,
                                                    "#Opta_0 tbody.Opta-fixture")
                new_ids = set()
                for m in new_matches:
                    try:
                        mid = m.get_attribute("data-match") or ""
                        if mid:
                            new_ids.add(mid)
                    except StaleElementReferenceException:
                        pass

                # If all matches were already seen, we've looped
                if new_ids and new_ids.issubset(seen_match_ids):
                    self.logger.info("📄 All matches already collected — pagination complete")
                    break

                seen_match_ids.update(new_ids)

                opta_el = driver.find_element(By.ID, "Opta_0")
                pages_html.append(opta_el.get_attribute("innerHTML") or "")
                self.logger.info(f"   📄 Collected page {clicks + 1} "
                                 f"({len(new_ids)} matches, {len(seen_match_ids)} total)")

            except (ElementClickInterceptedException, StaleElementReferenceException):
                time.sleep(1)
                continue
            except TimeoutException:
                self.logger.info("📄 Timed out waiting for next page — done")
                break
            except Exception as e:
                self.logger.warning(f"   ⚠️  Page collection error: {e}")
                break

        return pages_html

    def parse_opta_html(self, opta_html: str, team_filter: Optional[str] = None) -> List[Dict]:
        """Parse Opta widget HTML and extract match data"""
        soup = BeautifulSoup(opta_html, "lxml")
        rows = []
        current_date = None

        for table in soup.select("table.Opta-Crested"):
            for tbody in table.select("tbody"):
                # Check for date separator
                title_td = tbody.select_one("td.Opta-title h4 span")
                if title_td:
                    current_date = title_td.get_text(strip=True)
                    continue

                # Check if it's a fixture row
                classes = tbody.get("class", []) or []
                if "Opta-fixture" not in classes:
                    continue

                # Extract match URL
                link = tbody.select_one("a.Opta-MatchLink")
                url = (link.get("href") or "").strip() if link else ""
                if not url:
                    continue

                # Extract match ID
                match_id = (tbody.get("data-match") or "").strip()
                if not match_id and "/match/view/" in url:
                    match_id = url.split("/match/view/")[-1].split("?")[0].strip()
                if not match_id:
                    match_id = url.rstrip("/").split("/")[-1]

                # Extract teams
                home_link = tbody.select_one("tr.Opta-Scoreline td.Opta-Team.Opta-Home a.Opta-TeamLink")
                away_link = tbody.select_one("tr.Opta-Scoreline td.Opta-Team.Opta-Away a.Opta-TeamLink")

                home = home_link.get_text(strip=True) if home_link else ""
                away = away_link.get_text(strip=True) if away_link else ""

                # Apply team filter if specified
                if team_filter:
                    team_lower = team_filter.lower()
                    if team_lower not in home.lower() and team_lower not in away.lower():
                        continue

                # Extract scores
                home_score_elem = tbody.select_one("td.Opta-Score.Opta-Home span.Opta-Team-Score")
                away_score_elem = tbody.select_one("td.Opta-Score.Opta-Away span.Opta-Team-Score")

                home_score = home_score_elem.get_text(strip=True) if home_score_elem else ""
                away_score = away_score_elem.get_text(strip=True) if away_score_elem else ""

                rows.append({
                    "date": current_date or "",
                    "match_id": match_id,
                    "url_match": url,
                    "home": home,
                    "away": away,
                    "home_score": home_score,
                    "away_score": away_score,
                })

        return rows

    def diagnose_widget(self, results_url: str) -> dict:
        """Diagnostic tool: open a results page and report the widget structure.

        Run this to understand the pagination controls before scraping:
            scraper.diagnose_widget("https://www.scoresway.com/en_GB/soccer/...")
        """
        self.logger.info(f"🔍 Diagnosing Opta widget at: {results_url}")
        driver = self.create_driver(headless=True)

        try:
            driver.get(results_url)
            self.try_click_cookies(driver)
            self.warmup_scroll(driver)
            self.wait_for_opta_widget(driver)

            match_count = self._get_match_count(driver)
            pag_info = self._detect_pagination(driver)

            report = {
                'url': results_url,
                'initial_match_count': match_count,
                'pagination': pag_info,
            }

            self.logger.info(f"📊 Widget Report:")
            self.logger.info(f"   Matches visible: {match_count}")
            self.logger.info(f"   Pagination buttons: {len(pag_info['buttons'])}")
            self.logger.info(f"   All widget buttons: {len(pag_info['all_buttons_in_widget'])}")

            for b in pag_info['buttons']:
                self.logger.info(f"   → [{b['tag']}] class=\"{b['class']}\" "
                                 f"text=\"{b['text']}\" visible={b['visible']}")

            for b in pag_info['all_buttons_in_widget']:
                self.logger.info(f"   ⊙ [{b['tag']}] class=\"{b['class']}\" "
                                 f"text=\"{b['text']}\" visible={b['visible']}")

            return report

        except Exception as e:
            self.logger.error(f"❌ Diagnosis failed: {e}", exc_info=True)
            return {'error': str(e)}
        finally:
            driver.quit()

    def scrape_matches(self, results_url: str, team_name: Optional[str] = None) -> pd.DataFrame:
        """
        Scrape match URLs from Scoresway results page.

        Handles Opta widget pagination by detecting and clicking through
        Previous/Load More buttons to collect all available results.

        Args:
            results_url: URL of the Scoresway results page
            team_name: Optional team name to filter matches

        Returns:
            DataFrame with match information
        """
        self.logger.info(f"🔍 Scraping matches from: {results_url}")
        if team_name:
            self.logger.info(f"   Filtering for team: {team_name}")

        driver = self.create_driver(headless=True)

        try:
            driver.get(results_url)

            # Handle cookie consent
            self.try_click_cookies(driver)

            # Scroll to trigger lazy loading
            self.warmup_scroll(driver)

            # Wait for Opta widget
            self.wait_for_opta_widget(driver)

            initial_count = self._get_match_count(driver)
            self.logger.info(f"📊 Initial matches visible: {initial_count}")

            # Try to load all pages via pagination
            # First attempt: "Load More" style (accumulative — all matches stay in DOM)
            self._load_all_pages(driver)

            final_count = self._get_match_count(driver)

            if final_count > initial_count:
                # "Load More" style worked — all matches are in the DOM now
                self.logger.info(f"📊 After pagination: {final_count} matches "
                                 f"(+{final_count - initial_count} new)")
                opta_element = driver.find_element(By.ID, "Opta_0")
                opta_html = opta_element.get_attribute("innerHTML") or ""
                matches = self.parse_opta_html(opta_html, team_filter=team_name)

            elif final_count == initial_count and initial_count > 0:
                # Either no pagination exists, or it's page-swap style
                # (Previous/Next replaces content rather than appending).
                # Check if pagination button exists but content swapped:
                btn = self._find_pagination_button(driver)
                if btn:
                    # Page-swap style: need to re-load and collect each page separately
                    self.logger.info("📄 Detected page-swap pagination — "
                                     "collecting each page separately")
                    driver.get(results_url)
                    self.try_click_cookies(driver)
                    self.warmup_scroll(driver)
                    self.wait_for_opta_widget(driver)

                    pages_html = self._collect_all_pages_html(driver)
                    self.logger.info(f"📊 Collected {len(pages_html)} page(s)")

                    # Parse all pages and merge
                    all_matches = []
                    for html_page in pages_html:
                        page_matches = self.parse_opta_html(html_page, team_filter=team_name)
                        all_matches.extend(page_matches)
                    matches = all_matches
                else:
                    # No pagination at all — single page with all results
                    opta_element = driver.find_element(By.ID, "Opta_0")
                    opta_html = opta_element.get_attribute("innerHTML") or ""
                    matches = self.parse_opta_html(opta_html, team_filter=team_name)
            else:
                # Fallback
                opta_element = driver.find_element(By.ID, "Opta_0")
                opta_html = opta_element.get_attribute("innerHTML") or ""
                matches = self.parse_opta_html(opta_html, team_filter=team_name)

            if not matches:
                self.logger.warning("❌ No matches extracted from Opta widget")
                return pd.DataFrame()

            df = pd.DataFrame(matches)

            # Remove duplicates (important when merging multiple pages)
            if "match_id" in df.columns:
                df = df.drop_duplicates(subset=["match_id"], keep="first")
            df = df.drop_duplicates(subset=["url_match"], keep="first")

            self.logger.info(f"✅ Scraped {len(df)} unique matches")

            return df

        except Exception as e:
            self.logger.error(f"❌ Scraping failed: {e}", exc_info=True)
            raise

        finally:
            driver.quit()
