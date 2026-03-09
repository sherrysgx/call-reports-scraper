#!/usr/bin/env python3
"""Convert congregation export JSON files to CSV or plain text."""

import csv
import json
import sys
from pathlib import Path


def json_to_csv(json_path: str, csv_path: str = None):
    json_path = Path(json_path)
    csv_path = Path(csv_path) if csv_path else json_path.with_suffix('.csv')

    with open(json_path, encoding='utf-8') as f:
        data = json.load(f)

    pastors = data.get('pastors', [])
    if not pastors:
        print(f"No pastors found in {json_path}")
        return

    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['person_name', 'call_status', 'from_congregation', 'to_congregation', 'effective_date'])
        writer.writeheader()
        writer.writerows(pastors)

    print(f"Wrote {len(pastors)} rows to {csv_path}")


def json_to_text(json_path: str, txt_path: str = None):
    json_path = Path(json_path)
    txt_path = Path(txt_path) if txt_path else json_path.with_suffix('.txt')

    with open(json_path, encoding='utf-8') as f:
        data = json.load(f)

    destination = data.get('destination', '')
    pastors = data.get('pastors', [])

    lines = [
        f"Pastors Called to {destination}",
        f"({len(pastors)} total)",
        "",
    ]

    for i, p in enumerate(pastors, 1):
        lines.append(f"{i}. {p['person_name']}")
        lines.append(f"   From:      {p['from_congregation']}")
        lines.append(f"   Effective: {p['effective_date']}")
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
