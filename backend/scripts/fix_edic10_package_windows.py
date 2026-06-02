"""Align Batch EDIC 10 one_time tier sale windows with tier labels (Indian + Foreign rows)."""
from __future__ import annotations

import argparse
from datetime import date, datetime

from app.db import SessionLocal
from app.models import Package

TIER_WINDOWS: dict[str, tuple[date, date]] = {
    "20% EARLY BIRD TILL 31ST MAY 2026": (date(2025, 10, 25), date(2026, 5, 31)),
    "10% EXTENDED EARLY BIRD-1ST JUNE TO 15TH JUNE 2026": (date(2026, 6, 1), date(2026, 6, 15)),
    "REGULAR- 16TH JUNE 2026 ONWARDS": (date(2026, 6, 16), date(2026, 12, 31)),
    "REGULAR 16TH JUNE ONWARDS": (date(2026, 6, 16), date(2026, 12, 31)),
}


def main(*, apply: bool) -> None:
    db = SessionLocal()
    try:
        rows = (
            db.query(Package)
            .filter(
                Package.subscription == "Batch EDIC 10",
                Package.status == "1",
                Package.plan_type == "one_time",
            )
            .all()
        )
        for row in rows:
            name = (row.name or "").strip()
            window = TIER_WINDOWS.get(name)
            if not window:
                print(f"skip id={row.id} unknown tier name: {name!r}")
                continue
            start, end = window
            print(
                f"id={row.id} {name[:40]}: "
                f"{row.start_date}..{row.end_date} -> {start}..{end}"
            )
            if apply:
                row.start_date = datetime.combine(start, datetime.min.time())
                row.end_date = datetime.combine(end, datetime.min.time())
                row.discount_start_date = None
                row.discount_end_date = None
                db.add(row)
        if apply:
            db.commit()
            print("Committed EDIC 10 tier windows.")
        else:
            print("Dry run — pass --apply to update.")
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="Persist changes")
    args = parser.parse_args()
    main(apply=args.apply)
