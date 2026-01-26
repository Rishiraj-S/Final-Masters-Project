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

from .utils import normalize_url


class MatchScraper:
    """Scrapes match URLs from Scoresway results pages"""
    
    def __init__(self, config: dict, logger: logging.Logger):
        self.config = config
        self.logger = logger
        self.timeout = config.get('scraper', {}).get('timeout_seconds', 60)
        self.cookie_wait = config.get('scraper', {}).get('cookie_wait_seconds', 3)
        self.scroll_delay = config.get('scraper', {}).get('scroll_delay', 0.9)
    
    def create_driver(self, headless: bool = False) -> webdriver.Chrome:
        """Create Selenium Chrome driver"""
        opts = Options()
        opts.add_argument("--start-maximized")
        opts.add_argument("--lang=en-GB")
        opts.add_argument("--disable-notifications")
        opts.add_argument("--disable-gpu")
        opts.add_argument("--no-sandbox")
        opts.add_argument("--disable-dev-shm-usage")
        
        if headless:
            opts.add_argument("--headless=new")
        
        driver = webdriver.Chrome(options=opts)
        driver.set_page_load_timeout(90)
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
    
    def scrape_matches(self, results_url: str, team_name: Optional[str] = None) -> pd.DataFrame:
        """
        Scrape match URLs from Scoresway results page
        
        Args:
            results_url: URL of the Scoresway results page
            team_name: Optional team name to filter matches
            
        Returns:
            DataFrame with match information
        """
        self.logger.info(f"🔍 Scraping matches from: {results_url}")
        if team_name:
            self.logger.info(f"   Filtering for team: {team_name}")
        
        driver = self.create_driver(headless=False)
        
        try:
            driver.get(results_url)
            
            # Handle cookie consent
            self.try_click_cookies(driver)
            
            # Scroll to trigger lazy loading
            self.warmup_scroll(driver)
            
            # Wait for Opta widget
            self.wait_for_opta_widget(driver)
            
            # Get Opta widget HTML
            opta_element = driver.find_element(By.ID, "Opta_0")
            opta_html = opta_element.get_attribute("innerHTML") or ""
            
            # Parse matches
            matches = self.parse_opta_html(opta_html, team_filter=team_name)
            
            if not matches:
                self.logger.warning("❌ No matches extracted from Opta widget")
                return pd.DataFrame()
            
            df = pd.DataFrame(matches)
            
            # Remove duplicates
            if "match_id" in df.columns:
                df = df.drop_duplicates(subset=["match_id"], keep="first")
            df = df.drop_duplicates(subset=["url_match"], keep="first")
            
            self.logger.info(f"✅ Scraped {len(df)} matches")
            
            return df
            
        except Exception as e:
            self.logger.error(f"❌ Scraping failed: {e}", exc_info=True)
            raise
            
        finally:
            driver.quit()