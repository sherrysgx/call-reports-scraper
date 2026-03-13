# WELS Pastor Call Report Scraper

Scrapes pastor call data from the [WELS Call Report Archive](https://data.wels.net/CallReport/Archive) and stores it incrementally so historical data is preserved even as old reports roll off the archive.

## How It Works

The WELS archive is a rolling window of ~110 weekly reports. Each run:

1. Fetches the archive index (Selenium required — the site uses Blazor/JavaScript)
2. Compares report dates against `data/pastor_calls.json` to find only new reports
3. Scrapes and parses each new report — **pastor entries only** (names starting with `Rev` or `Dr`)
4. Detects which section each row came from (`issued`, `accepted`, or `returned`)
5. Appends new records to `data/pastor_calls.json`
6. Updates `data/report_list.json` so those reports are skipped on the next run

## Project Structure

```
scraper.py          Core scraper — fetches, parses, and saves incrementally to data/
church_exports.py   Per-congregation exports — reads data/, writes output/
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
python scraper.py
```

On first run this scrapes all ~110 available reports. On subsequent runs it only scrapes reports not yet in `data/pastor_calls.json`.

### Test with a limited number of reports

```bash
python scraper.py 5
```

Scrapes at most 5 new reports (does not re-scrape already-tracked ones).

### Re-export congregation files from existing data

If you already have `data/pastor_calls.json` and just want to regenerate the per-congregation JSON files:

```bash
python church_exports.py
# or with a custom data directory:
python church_exports.py path/to/data
```

### Convert a congregation JSON export to CSV or plain text

```bash
python json_to_csv.py csv  output/living_hope_madison_new_calls.json
python json_to_csv.py text output/living_hope_madison_new_calls.json
```

## Output Files

| File | Description |
|---|---|
| `data/pastor_calls.json` | All pastor call records (cumulative, appended each run) |
| `data/report_list.json` | Archive index — tracks all report IDs and dates |
| `output/*_new_calls.json` | Per-congregation exports (from `church_exports.py`) |

## Record Format

Each record in `data/pastor_calls.json`:

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

`church_exports.py` exports a deduplicated list of pastors called to specific congregations. For each pastor, if both an `issued` and `accepted`/`returned` record exist, the resolved status is used. Currently configured congregations:

- Living Hope LC Madison WI
- Apostles LC San Jose CA
- Crossroads LC Chicago IL
- Good Shepherd LC Omaha NE
- Crown of Life LC West Saint Paul MN

Each export is saved as `output/<congregation>_new_calls.json`.

To add a new congregation, add a function to `church_exports.py` following the existing pattern and call it in `main()`.

## Incremental Tracking

`data/report_list.json` records all report IDs and dates found in the archive:

```json
[
  {"id": "108", "date": "March 2, 2026", "url": "https://data.wels.net/CallReport/History/108"},
  ...
]
```

- A report is skipped on subsequent runs if its `date` is already present in `pastor_calls.json`
- A failed fetch is not recorded, so that report will be retried next run

## Technical Notes

The WELS site runs on Blazor (.NET), so all content is rendered via JavaScript. Selenium launches a headless Chrome browser to render each page before parsing. Each report page has three sections (Calls Issued, Calls Accepted, Calls Returned) rendered as Syncfusion grid tables — the scraper detects which section each table belongs to and sets `call_status` accordingly.

## Troubleshooting

**"Nothing new to scrape"** — all reports in the archive are already in `pastor_calls.json`.

**ChromeDriver errors** — ensure Chrome/Chromium is installed. Try `pip install --upgrade webdriver-manager`.

**Slow or timed-out fetches** — the scraper waits 1 second between requests and 2 seconds for Blazor to render. If a report fails, it will be retried on the next run automatically.
