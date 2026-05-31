#!/usr/bin/env python3
"""
Enable Batch 15 subscription extension (pay now; access extends from official batch end).

Usage (from mock_test/backend):
  python scripts/setup_batch15_extension.py
  python scripts/setup_batch15_extension.py --batch-name "Batch 15"
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from app.db import SessionLocal  # noqa: E402
from app.models import Option  # noqa: E402
from app.services.access import extension_option_key, get_extension_batch_settings  # noqa: E402

# Batch 15 ends 15 Jul 2026; extension adds 2 months until 15 Sep 2026.
DEFAULT_BATCH = "Batch 15"
DEFAULT_BASE_DATE = "2026-07-15"
DEFAULT_PAYMENT_START = "2026-05-28"
DEFAULT_PAYMENT_END = "2026-09-15"
DEFAULT_GROSS = 6500.0
DEFAULT_GST_PCT = 18.0
DEFAULT_GST_AMT = 1170.0
DEFAULT_TOTAL = 7670.0
DEFAULT_MONTHS = 2


def _upsert_option(db, option_name: str, option_value: str) -> None:
    row = db.query(Option).filter(Option.option_name == option_name).first()
    if row:
        row.option_value = option_value
    else:
        db.add(Option(option_name=option_name, option_value=option_value))


def main() -> int:
    parser = argparse.ArgumentParser(description="Configure batch extension offer in options table.")
    parser.add_argument("--batch-name", default=DEFAULT_BATCH)
    parser.add_argument("--base-date", default=DEFAULT_BASE_DATE, help="Official batch end / extension start")
    parser.add_argument("--payment-start", default=DEFAULT_PAYMENT_START, help="First day students can pay")
    parser.add_argument("--payment-end", default=DEFAULT_PAYMENT_END, help="Last day students can pay")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    batch_name = args.batch_name.strip()
    if not batch_name:
        print("batch-name is required", file=sys.stderr)
        return 1

    values = {
        "enabled": "1",
        "gross_amount": str(DEFAULT_GROSS),
        "gst_percentage": str(DEFAULT_GST_PCT),
        "gst_amount": str(DEFAULT_GST_AMT),
        "total_amount": str(DEFAULT_TOTAL),
        "months": str(DEFAULT_MONTHS),
        "start_date": args.payment_start.strip(),
        "end_date": args.payment_end.strip(),
        "base_date": args.base_date.strip(),
    }

    print(f"Batch extension settings for {batch_name!r}:")
    for k, v in values.items():
        print(f"  {k}: {v}")

    if args.dry_run:
        print("(dry run — no DB changes)")
        return 0

    db = SessionLocal()
    try:
        for kind, val in values.items():
            key = extension_option_key(kind, batch_name)
            if key:
                _upsert_option(db, key, val)
        db.commit()
        saved = get_extension_batch_settings(db, batch_name)
        print("Saved:", saved)
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
