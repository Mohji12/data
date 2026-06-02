"""Set batch_start_date for video/mock access (does not change registration tier sale dates)."""
from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db import SessionLocal
from app.services.registration import set_batch_course_access_dates

# subscription name, course start (access end = start + --months)
PRESETS: dict[str, date] = {
    "CP 7": date(2026, 3, 15),
    "CP 8": date(2026, 3, 15),
    "CCM Batch 2": date(2026, 1, 1),
    "Batch 15": date(2026, 1, 15),
    "Batch EDIC 10": date(2026, 4, 15),
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "subscriptions",
        nargs="*",
        help="Package subscription names (e.g. 'CCM Batch 2' 'Batch 15'). Omit to run all presets.",
    )
    parser.add_argument("--start", help="YYYY-MM-DD (overrides preset when one subscription)")
    parser.add_argument("--months", type=int, default=6)
    args = parser.parse_args()

    targets = args.subscriptions or list(PRESETS.keys())
    db = SessionLocal()
    try:
        for sub in targets:
            start_s = args.start
            if not start_s and sub in PRESETS:
                course_start = PRESETS[sub]
            elif start_s:
                course_start = date.fromisoformat(start_s)
            else:
                print(f"Skip {sub}: no --start and not in presets")
                continue
            result = set_batch_course_access_dates(db, sub, course_start, args.months)
            print(result)
    finally:
        db.close()


if __name__ == "__main__":
    main()
