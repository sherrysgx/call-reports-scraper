#!/usr/bin/env python3
"""Convert congregation export JSON files to CSV or plain text."""

import csv
import json
import sys
from pathlib import Path


def normalize(r: dict) -> dict:
    """Normalize old-style fields to new-style field names."""
    return {
        'person_name': r.get('person_name', ''),
        'call_status': r.get('call_status', ''),
        'current_call': r.get('current_call') or r.get('from_congregation', ''),
        'new_call': r.get('new_call') or r.get('to_congregation', ''),
        'date_effective': r.get('date_effective') or r.get('effective_date', ''),
        'report_date': r.get('report_date', ''),
    }


def json_to_csv(json_path: str, csv_path: str = None):
    json_path = Path(json_path)
    csv_path = Path(csv_path) if csv_path else json_path.with_suffix('.csv')

    with open(json_path, encoding='utf-8') as f:
        data = json.load(f)

    records = data if isinstance(data, list) else data.get('pastors', [])
    if not records:
        print(f"No records found in {json_path}")
        return

    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['person_name', 'call_status', 'current_call', 'new_call', 'date_effective', 'report_date'], extrasaction='ignore')
        writer.writeheader()
        writer.writerows([normalize(r) for r in records])

    print(f"Wrote {len(records)} rows to {csv_path}")


def json_to_text(json_path: str, txt_path: str = None):
    json_path = Path(json_path)
    txt_path = Path(txt_path) if txt_path else json_path.with_suffix('.txt')

    with open(json_path, encoding='utf-8') as f:
        data = json.load(f)

    records = data if isinstance(data, list) else data.get('pastors', [])

    lines = [
        f"Call Report",
        f"({len(records)} total)",
        "",
    ]

    for i, p in enumerate(records, 1):
        p = normalize(p)
        lines.append(f"{i}. {p['person_name']}  [{p['call_status']}]")
        lines.append(f"   From:      {p['current_call']}")
        lines.append(f"   To:        {p['new_call']}")
        lines.append(f"   Effective: {p['date_effective']}")
        if p['report_date']:
            lines.append(f"   Reported:  {p['report_date']}")
        lines.append("")

    text = "\n".join(lines)

    with open(txt_path, 'w', encoding='utf-8') as f:
        f.write(text)

    print(text)
    print(f"Saved to {txt_path}")


if __name__ == "__main__":
    if len(sys.argv) < 3 or sys.argv[1] not in ("csv", "text"):
        print("Usage:")
        print("  python json_to_csv.py csv  <input.json> [output.csv]")
        print("  python json_to_csv.py text <input.json> [output.txt]")
        sys.exit(1)

    mode = sys.argv[1]
    args = sys.argv[2:]
    if mode == "csv":
        json_to_csv(*args)
    else:
        json_to_text(*args)
