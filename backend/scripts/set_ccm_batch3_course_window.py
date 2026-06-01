"""Set CCM Batch 3 batch_start_date to today and course end to start + 6 months."""
from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db import SessionLocal
from app.services.registration import apply_batch_course_window

SUBSCRIPTION = "CCM Batch 3"


def main() -> None:
    parser = argparse.ArgumentParser(description="Apply 6-month course window for CCM Batch 3 packages.")
    parser.add_argument(
        "--start",
        type=str,
        default=None,
        help="Batch start date YYYY-MM-DD (default: today)",
    )
    parser.add_argument("--months", type=int, default=6, help="Course length in months (default: 6)")
    args = parser.parse_args()
    batch_start = date.fromisoformat(args.start) if args.start else date.today()

    db = SessionLocal()
    try:
        result = apply_batch_course_window(db, SUBSCRIPTION, batch_start, args.months)
        print(result)
    finally:
        db.close()


if __name__ == "__main__":
    main()
