#!/usr/bin/env python3
"""
WELS Pastor Call Report Scraper
Extracts pastor call information from https://data.wels.net/CallReport/Archive
Uses Selenium for JavaScript-rendered Blazor content
"""

import requests
import json
import logging
import time
import sys
from typing import List, Dict, Optional, Set
from bs4 import BeautifulSoup
from pathlib import Path
import re

try:
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.chrome.options import Options
    from webdriver_manager.chrome import ChromeDriverManager
    from selenium.webdriver.chrome.service import Service
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class PastorCallScraper:
    """Scraper for WELS Call Report Archive"""
    
    BASE_URL = "https://data.wels.net/CallReport"
    ARCHIVE_URL = f"{BASE_URL}/Archive"
    DELAY_SECONDS = 1
    
    def __init__(self, output_dir: str = "data", use_selenium: bool = False):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        self.all_calls = []
        self.use_selenium = use_selenium and SELENIUM_AVAILABLE
        
        if use_selenium and not SELENIUM_AVAILABLE:
            logger.warning("Selenium requested but not available. Install with: pip install selenium webdriver-manager")
        
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (compatible; WELSCallScraper/1.0)',
            'Accept': 'application/json,text/html,application/xhtml+xml'
        })
        self.driver = None
    
    def save_report_list(self, reports: List[Dict[str, str]], filename: str = "report_list.json") -> tuple:
        """Merge new reports into the existing report list file, deduplicating by id."""
        filepath = self.output_dir / filename
        existing = []
        if filepath.exists():
            try:
                with open(filepath, encoding='utf-8') as f:
                    existing = json.load(f)
            except Exception as e:
                logger.error(f"Could not read {filename} ({e}) — starting fresh")

        existing_ids = {r['id'] for r in existing}
        new_entries = [r for r in reports if r['id'] not in existing_ids]
        merged = existing + new_entries
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(merged, f, indent=2, ensure_ascii=False)
        logger.info(f"Saved {len(merged)} reports to {filepath} ({len(new_entries)} new)")
        return filepath, len(new_entries), len(merged)

    def load_existing_dates(self) -> Set[str]:
        """Get report_date strings already in pastor_calls.json to avoid re-scraping."""
        filepath = self.output_dir / "pastor_calls.json"
        if not filepath.exists():
            return set()
        try:
            with open(filepath, encoding='utf-8') as f:
                data = json.load(f)
            return {r.get('report_date', '') for r in data if r.get('report_date')}
        except Exception as e:
            logger.error(f"Could not read pastor_calls.json ({e}) — will re-scrape all")
            return set()

    def get_driver(self):
        """Initialize Selenium WebDriver"""
        if self.driver:
            return self.driver
        
        try:
            chrome_options = Options()
            chrome_options.add_argument("--headless")
            chrome_options.add_argument("--disable-blink-features=AutomationControlled")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
            
            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            return self.driver
        except Exception as e:
            logger.error(f"Failed to initialize Selenium WebDriver: {e}")
            return None
    
    def fetch_with_selenium(self, url: str) -> Optional[str]:
        """Fetch page using Selenium to render JavaScript"""
        driver = self.get_driver()
        if not driver:
            return None
        
        try:
            logger.info(f"Fetching with Selenium: {url}")
            driver.get(url)
            
            # Wait for content to load
            WebDriverWait(driver, 10).until(
                lambda d: d.execute_script("return document.readyState") == "complete"
            )
            
            # Additional wait for Blazor to render
            time.sleep(2)
            return driver.page_source
        except Exception as e:
            logger.error(f"Selenium fetch failed: {e}")
            return None
    
    def fetch_page(self, url: str) -> Optional[str]:
        """Fetch page content"""
        if self.use_selenium:
            return self.fetch_with_selenium(url)
        
        try:
            logger.info(f"Fetching: {url}")
            response = self.session.get(url, timeout=15)
            response.raise_for_status()
            return response.text
        except requests.RequestException as e:
            logger.error(f"Failed to fetch {url}: {e}")
            return None
    
    def get_report_list(self) -> List[Dict[str, str]]:
        """Extract all call report IDs and dates from archive, paginating through all pages"""
        driver = self.get_driver()
        if not driver:
            logger.error("Selenium is required to scrape the archive (Blazor app). Run with --selenium.")
            return []

        logger.info(f"Loading archive: {self.ARCHIVE_URL}")
        driver.get(self.ARCHIVE_URL)
        time.sleep(4)  # Wait for Blazor to render

        reports = []
        page = 1

        while True:
            soup = BeautifulSoup(driver.page_source, 'html.parser')

            # Collect links on this page
            for link in soup.find_all('a', {'href': re.compile(r'/CallReport/History/\d+')}):
                url = link.get('href', '')
                text = link.text.strip()
                match = re.search(r'/History/(\d+)', url)
                if match and text:
                    report_id = match.group(1)
                    full_url = url if url.startswith('http') else f"{self.BASE_URL}{url}"
                    reports.append({'id': report_id, 'date': text, 'url': full_url})

            logger.info(f"Archive page {page}: collected {len(reports)} reports so far")

            # Try to click the Syncfusion "next page" div (role="button", not <button>)
            try:
                next_btn = driver.find_element(
                    By.XPATH,
                    "//div[@title='Go to next page' and not(contains(@class,'e-disable'))]"
                )
                driver.execute_script("arguments[0].click();", next_btn)
                time.sleep(2)
                page += 1
            except Exception:
                break

        # Remove duplicates
        seen = set()
        unique_reports = []
        for r in reports:
            if r['id'] not in seen:
                seen.add(r['id'])
                unique_reports.append(r)

        logger.info(f"Found {len(unique_reports)} reports across {page} pages")
        return unique_reports
    
    def parse_call_data(self, html: str, report_date: str) -> List[Dict]:
        """Extract pastor call data from report HTML"""
        calls = []
        soup = BeautifulSoup(html, 'html.parser')
        
        try:
            # Find all tables and detect their section heading to determine call_status.
            # Each report page has three tables preceded by headings like
            # "Calls Issued", "Calls Accepted", "Calls Returned".
            tables = soup.find_all('table')
            logger.debug(f"Found {len(tables)} tables on page")

            for table_idx, table in enumerate(tables):
                # Walk backwards through siblings to find the nearest heading
                call_status = 'unknown'
                for sibling in table.find_all_previous(['h1', 'h2', 'h3', 'h4', 'h5', 'p', 'div']):
                    text = sibling.get_text(separator=' ', strip=True).lower()
                    if 'issued' in text:
                        call_status = 'issued'
                        break
                    elif 'accepted' in text:
                        call_status = 'accepted'
                        break
                    elif 'returned' in text:
                        call_status = 'returned'
                        break

                rows = table.find_all('tr')
                logger.debug(f"Table {table_idx} ({call_status}): {len(rows)} rows")

                if len(rows) > 0:
                    # Check if first row uses <th> tags (real headers)
                    first_row = rows[0]
                    th_cells = first_row.find_all('th')
                    if th_cells:
                        headers = [th.get_text(strip=True) for th in th_cells]
                        data_rows = rows[1:]
                    else:
                        # No header row — use fixed column names by position
                        headers = ['person_name', 'current_call', 'new_call', 'date_effective']
                        data_rows = rows

                    logger.debug(f"Headers: {headers}")

                    # Process data rows
                    for row_idx, row in enumerate(data_rows):
                        cells = row.find_all('td')

                        if len(cells) > 0:
                            cell_texts = [' '.join(cell.get_text(separator=' ', strip=True).split()) for cell in cells]

                            # Skip navigation and empty rows
                            if any(cell_texts) and not any(kw in str(cell_texts) for kw in ['<<<', '>>>', '«', '»', 'Page']):
                                call_data = {}
                                for i, header in enumerate(headers):
                                    if i < len(cell_texts):
                                        call_data[header] = cell_texts[i]

                                # Only keep pastor entries (Rev or Dr title)
                                person = call_data.get('person_name', '')
                                if not (person.startswith('Rev ') or person.startswith('Dr ')):
                                    continue

                                call_data['report_date'] = report_date
                                call_data['call_status'] = call_status

                                calls.append(call_data)
                                logger.debug(f"Extracted row {row_idx}: {cell_texts[:3]}")
        except Exception as e:
            logger.warning(f"Error parsing call data: {e}")
        
        return calls
    
    def scrape_all_reports(self, reports: List[Dict[str, str]], limit: Optional[int] = None) -> None:
        """Scrape only new call reports not yet in pastor_calls.json."""
        if not reports:
            logger.error("No reports found!")
            return

        existing_dates = self.load_existing_dates()
        new_reports = [r for r in reports if r['date'] not in existing_dates]

        logger.info(
            f"Archive: {len(reports)} total, {len(existing_dates)} dates already in data, "
            f"{len(new_reports)} new to scrape"
        )

        if not new_reports:
            logger.info("Nothing new to scrape.")
            return

        if limit:
            new_reports = new_reports[:limit]
            logger.info(f"Limited to {limit} new reports")

        for idx, report in enumerate(new_reports, 1):
            logger.info(f"Processing report {idx}/{len(new_reports)}: {report['date']}")

            html = self.fetch_with_selenium(report['url'])
            if html:
                calls = self.parse_call_data(html, report['date'])
                self.all_calls.extend(calls)
                logger.info(f"Extracted {len(calls)} rows from {report['date']}")
            else:
                logger.warning(f"Failed to fetch {report['date']} — will retry next run")

            if idx < len(new_reports):
                time.sleep(self.DELAY_SECONDS)

        logger.info(f"New rows extracted this run: {len(self.all_calls)}")
    
    def save_json(self, filename: str = "pastor_calls.json") -> tuple:
        """Merge new calls with existing JSON file and rewrite."""
        filepath = self.output_dir / filename
        existing_calls = []
        if filepath.exists():
            try:
                with open(filepath, encoding='utf-8') as f:
                    existing_calls = json.load(f)
                logger.info(f"Loaded {len(existing_calls)} existing records from {filepath}")
            except Exception as e:
                logger.error(f"Could not read existing JSON ({e}) — starting fresh")

        merged = existing_calls + self.all_calls
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(merged, f, indent=2, ensure_ascii=False)
        logger.info(f"Saved {len(merged)} total records to {filepath} ({len(self.all_calls)} new)")
        return filepath, len(self.all_calls), len(merged)

    def print_summary(self, report_list_stats: tuple = None, call_stats: tuple = None):
        """Print summary of what was appended this run."""
        print("\n" + "="*70)
        print("WELS PASTOR CALL REPORT — RUN SUMMARY")
        print("="*70)

        if report_list_stats:
            _, new_reports, total_reports = report_list_stats
            print(f"  Report list:   +{new_reports} new  (total: {total_reports})  → {self.output_dir}/report_list.json")

        if call_stats:
            _, new_calls, total_calls = call_stats
            print(f"  Call records:  +{new_calls} new  (total: {total_calls})  → {self.output_dir}/pastor_calls.json")
        elif not self.all_calls:
            print("  Call records:  nothing new to append")

        if self.all_calls:
            by_date = {}
            for call in self.all_calls:
                date = call.get('report_date', 'Unknown')
                by_date[date] = by_date.get(date, 0) + 1
            print(f"\n  New records by report date:")
            for date, count in sorted(by_date.items(), reverse=True)[:15]:
                print(f"    {date}: {count} rows")

        if not self.use_selenium and not self.all_calls and not report_list_stats:
            print("\n  Tip: Run with --selenium to render JavaScript content:")
            print("    python scraper.py --selenium")

        print("="*70 + "\n")
    
    def cleanup(self):
        """Clean up resources"""
        if self.driver:
            try:
                self.driver.quit()
            except:
                pass


def main():
    """Main entry point"""
    limit = None
    use_selenium = False
    
    for arg in sys.argv[1:]:
        if arg == '--selenium':
            use_selenium = True
            logger.info("Using Selenium for JavaScript rendering")
        else:
            try:
                limit = int(arg)
            except ValueError:
                print("Usage: python scraper.py [limit] [--selenium]")
                print("  limit: Number of reports to scrape")
                print("  --selenium: Use Selenium for JavaScript-rendered content")
                sys.exit(1)
    
    scraper = PastorCallScraper(use_selenium=use_selenium)
    try:
        logger.info("Starting WELS Pastor Call Report Scraper")
        reports = scraper.get_report_list()
        report_list_stats = None
        if reports:
            report_list_stats = scraper.save_report_list(reports)
        scraper.scrape_all_reports(reports, limit=limit)

        call_stats = None
        if scraper.all_calls:
            call_stats = scraper.save_json()
        scraper.print_summary(report_list_stats=report_list_stats, call_stats=call_stats)

    except KeyboardInterrupt:
        logger.info("Scraping interrupted by user")
    except Exception as e:
        logger.error(f"Scraping failed: {e}", exc_info=True)
        sys.exit(1)
    finally:
        scraper.cleanup()


if __name__ == "__main__":
    main()
