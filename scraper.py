#!/usr/bin/env python3
"""
WELS Pastor Call Report Scraper
Extracts pastor call information from https://data.wels.net/CallReport/Archive
Uses Selenium for JavaScript-rendered Blazor content
"""

import requests
import csv
import json
import logging
import time
import sys
from datetime import datetime, timezone
from typing import List, Dict, Optional, Set
from bs4 import BeautifulSoup
from pathlib import Path
import re

from church_exports import (
    export_living_hope_madison,
    export_apostles_san_jose,
    export_crossroads_chicago,
    export_good_shepherd_omaha,
)

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
    
    def __init__(self, output_dir: str = "output", use_selenium: bool = False):
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
    
    def load_scraped_ids(self) -> Set[str]:
        """Load set of already-scraped report IDs from tracking file"""
        tracking_file = self.output_dir / "scraped_ids.json"
        if not tracking_file.exists():
            logger.info("No tracking file found — first run, all reports will be scraped")
            return set()
        try:
            with open(tracking_file, encoding='utf-8') as f:
                data = json.load(f)
            return set(data.get("scraped_ids", []))
        except Exception as e:
            logger.error(f"Could not read scraped_ids.json ({e}) — will re-scrape all")
            return set()

    def save_scraped_ids(self, ids: Set[str]) -> None:
        """Persist the set of scraped report IDs to tracking file"""
        tracking_file = self.output_dir / "scraped_ids.json"
        data = {
            "scraped_ids": sorted(ids),
            "last_run": datetime.now(timezone.utc).isoformat(),
            "total_records": len(self.all_calls),
        }
        with open(tracking_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
        logger.info(f"Saved {len(ids)} scraped IDs to {tracking_file}")

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
    
    def scrape_all_reports(self, limit: Optional[int] = None) -> Set[str]:
        """Scrape only new call reports not yet in the tracking file.
        Returns the set of report IDs successfully scraped this run."""
        reports = self.get_report_list()

        if not reports:
            logger.error("No reports found!")
            return set()

        existing_ids = self.load_scraped_ids()
        new_reports = [r for r in reports if r['id'] not in existing_ids]

        logger.info(
            f"Archive: {len(reports)} total, {len(existing_ids)} already scraped, "
            f"{len(new_reports)} new to scrape"
        )

        if not new_reports:
            logger.info("Nothing new to scrape.")
            return set()

        if limit:
            new_reports = new_reports[:limit]
            logger.info(f"Limited to {limit} new reports")

        newly_scraped_ids: Set[str] = set()

        for idx, report in enumerate(new_reports, 1):
            logger.info(f"Processing report {idx}/{len(new_reports)}: {report['date']}")

            html = self.fetch_page(report['url'])
            if html:
                calls = self.parse_call_data(html, report['date'])
                self.all_calls.extend(calls)
                newly_scraped_ids.add(report['id'])
                logger.info(f"Extracted {len(calls)} rows from {report['date']}")
            else:
                logger.warning(f"Failed to fetch {report['date']} — will retry next run")

            if idx < len(new_reports):
                time.sleep(self.DELAY_SECONDS)

        logger.info(f"New rows extracted this run: {len(self.all_calls)}")
        return newly_scraped_ids
    
    def save_json(self, filename: str = "wels_calls.json") -> Path:
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
        return filepath

    def save_csv(self, filename: str = "wels_calls.csv") -> Optional[Path]:
        """Append new calls to existing CSV, or create it on first run."""
        if not self.all_calls:
            logger.warning("No new data to append to CSV")
            return None

        fieldnames = ['report_date', 'call_status', 'person_name', 'current_call', 'new_call', 'date_effective']
        filepath = self.output_dir / filename

        try:
            if filepath.exists():
                with open(filepath, 'a', newline='', encoding='utf-8') as f:
                    writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
                    writer.writerows(self.all_calls)
                logger.info(f"Appended {len(self.all_calls)} rows to {filepath}")
            else:
                with open(filepath, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
                    writer.writeheader()
                    writer.writerows(self.all_calls)
                logger.info(f"Created {filepath} with {len(self.all_calls)} rows")
            return filepath
        except Exception as e:
            logger.error(f"Failed to save CSV: {e}")
            return None
    
    def print_summary(self):
        """Print summary statistics"""
        if not self.all_calls:
            print("No data collected")
            if not self.use_selenium:
                print("\nTip: Try with Selenium to render JavaScript:")
                print("  python scraper.py --selenium")
            return
        
        print("\n" + "="*70)
        print("WELS PASTOR CALL REPORT SUMMARY")
        print("="*70)
        print(f"Total data rows extracted: {len(self.all_calls)}")
        
        # Group by report date
        by_date = {}
        for call in self.all_calls:
            date = call.get('report_date', 'Unknown')
            by_date[date] = by_date.get(date, 0) + 1
        
        print(f"\nRows by Report Date:")
        for date, count in sorted(by_date.items(), reverse=True)[:15]:
            print(f"  {date}: {count} rows")
        
        # Show sample data
        if self.all_calls:
            print(f"\nSample row:")
            sample = self.all_calls[0]
            for key, value in list(sample.items())[:5]:
                print(f"  {key}: {value[:80] if isinstance(value, str) else value}")
        
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
        newly_scraped_ids = scraper.scrape_all_reports(limit=limit)

        if scraper.all_calls:
            scraper.save_json()
            scraper.save_csv()
            export_living_hope_madison(scraper.all_calls, scraper.output_dir)
            export_apostles_san_jose(scraper.all_calls, scraper.output_dir)
            export_crossroads_chicago(scraper.all_calls, scraper.output_dir)
            export_good_shepherd_omaha(scraper.all_calls, scraper.output_dir)
            scraper.print_summary()

        # Persist scraped IDs only after data files are safely written
        if newly_scraped_ids:
            existing_ids = scraper.load_scraped_ids()
            scraper.save_scraped_ids(existing_ids | newly_scraped_ids)

    except KeyboardInterrupt:
        logger.info("Scraping interrupted by user")
    except Exception as e:
        logger.error(f"Scraping failed: {e}", exc_info=True)
        sys.exit(1)
    finally:
        scraper.cleanup()


if __name__ == "__main__":
    main()
