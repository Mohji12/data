"""Set CP 7 / CP 8 video+mock access: course start 15 Mar 2026, end +6 months (15 Sep 2026)."""
from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db import SessionLocal
from app.services.registration import set_batch_course_access_dates

COURSE_START = date(2026, 3, 15)
SUBSCRIPTIONS = ("CP 7", "CP 8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", default=COURSE_START.isoformat(), help="YYYY-MM-DD")
    parser.add_argument("--months", type=int, default=6)
    args = parser.parse_args()
    course_start = date.fromisoformat(args.start)

    db = SessionLocal()
    try:
        for sub in SUBSCRIPTIONS:
            result = set_batch_course_access_dates(db, sub, course_start, args.months)
            print(result)
    finally:
        db.close()


if __name__ == "__main__":
    main()
