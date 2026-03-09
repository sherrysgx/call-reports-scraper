# WELS Pastor Call Report Scraper

Scrapes pastor call data from the [WELS Call Report Archive](https://data.wels.net/CallReport/Archive) and stores it incrementally so historical data is preserved even as old reports roll off the archive.

## How It Works

The WELS archive is a rolling window of ~110 weekly reports. Each run:

1. Fetches the archive index (Selenium required — the site uses Blazor/JavaScript)
2. Compares report IDs against `output/scraped_ids.json` to find only new reports
3. Scrapes and parses each new report — **pastor entries only** (names starting with `Rev` or `Dr`)
4. Detects which table each row came from (`issued`, `accepted`, or `returned`)
5. Appends new records to `output/wels_calls.json` and `output/wels_calls.csv`
6. Updates `output/scraped_ids.json` so those reports are skipped on the next run

## Project Structure

```
scraper.py          Core scraper — fetches, parses, and saves incrementally
church_exports.py   Per-congregation exports — can run standalone or via scraper.py
pastor_calls.py     Pastor call CSV export utility
json_to_csv.py      Converts per-congregation JSON exports to CSV or plain text
```

## Installation

Requires Python 3.8+ and Chrome/Chromium.

```bash
pip install -r requirements.txt
```

## Usage

### Full scrape (first run or weekly update)

```bash
python scraper.py --selenium
```

On first run this scrapes all ~110 available reports. On subsequent runs it only scrapes reports not yet in `output/scraped_ids.json`.

### Test with a limited number of reports

```bash
python scraper.py 5 --selenium
```

Scrapes at most 5 new reports (does not re-scrape already-tracked ones).

### Re-export congregation files from existing data

If you already have `output/wels_calls.json` and just want to regenerate the per-congregation JSON files:

```bash
python church_exports.py
# or with a custom output directory:
python church_exports.py path/to/output
```

### Convert a congregation JSON export to CSV or plain text

```bash
python json_to_csv.py csv  output/living_hope_madison_new_calls.json
python json_to_csv.py text output/living_hope_madison_new_calls.json
```

## Output Files

| File | Description |
|---|---|
| `output/wels_calls.json` | All pastor call records (cumulative, appended each run) |
| `output/wels_calls.csv` | Same data in CSV format |
| `output/scraped_ids.json` | Tracks which report IDs have been scraped |
| `output/pastors_calls_issued.csv` | Pastor-only CSV (from `pastor_calls.py`) |
| `output/*_new_calls.json` | Per-congregation exports |

## Record Format

Each record in `wels_calls.json` / `wels_calls.csv`:

| Field | Description |
|---|---|
| `report_date` | Publication date of the report (e.g. `March 2, 2026`) |
| `call_status` | `issued`, `accepted`, `returned`, or `unknown` |
| `person_name` | Pastor name including title (e.g. `Rev John Smith`) |
| `current_call` | Congregation the pastor is coming from |
| `new_call` | Congregation the pastor is called to |
| `date_effective` | Effective date of the call (e.g. `1/19/2026`) |

Example record:
```json
{
  "report_date": "March 2, 2026",
  "call_status": "accepted",
  "person_name": "Rev John Smith",
  "current_call": "St Paul LC Hillsboro WI",
  "new_call": "Grace LC Dalton WI",
  "date_effective": "1/19/2026"
}
```

## Congregation Exports

`church_exports.py` exports a deduplicated list of pastors called to specific congregations. For each pastor, if both an `issued` and `accepted`/`returned` record exist for that congregation, the resolved status is used. Currently configured congregations:

- Living Hope LC Madison WI
- Apostles LC San Jose CA
- Crossroads LC Chicago IL
- Good Shepherd LC Omaha NE
- Crown of Life LC West Saint Paul MN

Each export is saved as `output/<congregation>_new_calls.json`.

To add a new congregation, add a function to `church_exports.py` following the existing pattern and call it in `main()`.

## Scraped ID Tracking

`output/scraped_ids.json` records which report IDs have been successfully scraped:

```json
{
  "scraped_ids": ["108", "109", "110"],
  "last_run": "2026-03-09T17:31:00+00:00",
  "total_records": 1547
}
```

- IDs are only written after both `wels_calls.json` and `wels_calls.csv` are saved
- A failed fetch is not tracked, so that report will be retried next run
- To force a re-scrape of a specific report, remove its ID from this file by hand

## Technical Notes

The WELS site runs on Blazor (.NET WebAssembly), so all content is rendered via JavaScript. Selenium launches a headless Chrome browser to render each page before parsing. Each report page has three tables (Calls Issued, Calls Accepted, Calls Returned) — the scraper detects which section each table belongs to and sets `call_status` accordingly.

## Troubleshooting

**"No tracking file found — first run"** — expected on first run, all reports will be scraped.

**"Nothing new to scrape"** — all reports in the archive are already in `scraped_ids.json`.

**ChromeDriver errors** — ensure Chrome/Chromium is installed. Try `pip install --upgrade webdriver-manager`.

**Slow or timed-out fetches** — the scraper waits 1 second between requests and 2 seconds for Blazor to render. If reports fail, they will be retried on the next run automatically.
