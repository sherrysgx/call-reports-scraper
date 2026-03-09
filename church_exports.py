"""
Per-congregation pastor call export utilities.

Can also be run directly to re-export from an existing wels_calls.json:
    python church_exports.py [output_dir]
"""

import json
import logging
import sys
from collections import defaultdict
from datetime import datetime
from typing import Dict, List, Optional
from pathlib import Path

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def _export_church(
    all_calls: List[Dict],
    output_dir: Path,
    name_keywords: List[str],
    destination_label: str,
    output_filename: str,
) -> Optional[Path]:
    """Generic helper: export unique pastors called to a congregation."""
    if not all_calls:
        logger.warning(f"No data available for {destination_label} export")
        return None

    pastors_by_name = defaultdict(list)

    for call in all_calls:
        new_call = call.get('new_call', '').strip()
        person_name = call.get('person_name', '').strip()

        new_call_lower = new_call.lower()
        if all(kw in new_call_lower for kw in name_keywords):
            pastors_by_name[person_name].append({
                "person_name": person_name,
                "call_status": call.get('call_status', ''),
                "from_congregation": call.get('current_call', '').strip(),
                "to_congregation": new_call,
                "effective_date": call.get('date_effective', '').strip()
            })

    deduped = []
    for person_name, calls in sorted(pastors_by_name.items()):
        # Prefer accepted/returned over issued; fall back to issued if that's all there is
        resolved = [c for c in calls if c['call_status'] in ('accepted', 'returned')]
        if not resolved:
            resolved = calls
        calls_sorted = sorted(resolved, key=lambda x: x['effective_date'], reverse=True)
        deduped.append(calls_sorted[0])

    deduped.sort(
        key=lambda x: datetime.strptime(x['effective_date'], '%m/%d/%Y') if x['effective_date'] else datetime.min,
        reverse=True,
    )

    output = {
        "destination": destination_label,
        "total_unique_pastors": len(deduped),
        "pastors": deduped,
    }

    filepath = output_dir / output_filename
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    logger.info(f"Saved {len(deduped)} unique pastors to {filepath}")
    return filepath


def export_living_hope_madison(all_calls: List[Dict], output_dir: Path) -> Optional[Path]:
    """Export unique pastors called to Living Hope LC Madison WI (most recent only)"""
    return _export_church(
        all_calls, output_dir,
        name_keywords=['living hope', 'madison'],
        destination_label="Living Hope LC Madison WI",
        output_filename="living_hope_madison_new_calls.json",
    )


def export_apostles_san_jose(all_calls: List[Dict], output_dir: Path) -> Optional[Path]:
    """Export unique pastors called to Apostles LC San Jose CA (most recent only)"""
    return _export_church(
        all_calls, output_dir,
        name_keywords=['apostles', 'san jose'],
        destination_label="Apostles LC San Jose CA",
        output_filename="apostles_san_jose_new_calls.json",
    )


def export_crossroads_chicago(all_calls: List[Dict], output_dir: Path) -> Optional[Path]:
    """Export unique pastors called to Crossroads LC Chicago IL (most recent only)"""
    return _export_church(
        all_calls, output_dir,
        name_keywords=['crossroad', 'chicago'],
        destination_label="Crossroads LC Chicago IL",
        output_filename="crossroads_chicago_new_calls.json",
    )


def export_good_shepherd_omaha(all_calls: List[Dict], output_dir: Path) -> Optional[Path]:
    """Export unique pastors called to Good Shepherd LC Omaha NE (most recent only)"""
    return _export_church(
        all_calls, output_dir,
        name_keywords=['good shepherd', 'omaha'],
        destination_label="Good Shepherd LC Omaha NE",
        output_filename="good_shepherd_omaha_new_calls.json",
    )


def export_crown_of_life_west_saint_paul(all_calls: List[Dict], output_dir: Path) -> Optional[Path]:
    """Export unique pastors called to Crown of Life LC West Saint Paul MN (most recent only)"""
    return _export_church(
        all_calls, output_dir,
        name_keywords=['crown of life', 'saint paul'],
        destination_label="Crown of Life LC West Saint Paul MN",
        output_filename="crown_of_life_west_saint_paul_new_calls.json",
    )


def main():
    output_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("output")
    data_file = output_dir / "wels_calls.json"

    if not data_file.exists():
        logger.error(f"Data file not found: {data_file}")
        logger.error("Run scraper.py first to generate the data.")
        sys.exit(1)

    with open(data_file, encoding='utf-8') as f:
        all_calls = json.load(f)

    logger.info(f"Loaded {len(all_calls)} calls from {data_file}")

    export_living_hope_madison(all_calls, output_dir)
    export_apostles_san_jose(all_calls, output_dir)
    export_crossroads_chicago(all_calls, output_dir)
    export_good_shepherd_omaha(all_calls, output_dir)
    export_crown_of_life_west_saint_paul(all_calls, output_dir)


if __name__ == "__main__":
    main()
