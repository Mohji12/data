#!/usr/bin/env python3
"""
Add a batch name to the access_quiz_link admin option (and optionally batch_master).

Usage (from mock_test/backend):
  python scripts/enable_mock_tests_for_batch.py "CCM Batch 2"
  python scripts/enable_mock_tests_for_batch.py "CCM Batch 2" --create-batch-row
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from app.db import SessionLocal  # noqa: E402
from app.models import BatchMaster, Option  # noqa: E402
from app.services.access import get_option_value, subscription_allowed  # noqa: E402


def _split_csv(raw: str) -> list[str]:
    return [p.strip() for p in (raw or "").split(",") if p.strip()]


def _join_csv(parts: list[str]) -> str:
    return ",".join(parts)


def main() -> int:
    parser = argparse.ArgumentParser(description="Enable mock tests for a subscription/batch name.")
    parser.add_argument("batch_name", help='Exact subscription name, e.g. "CCM Batch 2"')
    parser.add_argument(
        "--create-batch-row",
        action="store_true",
        help="Insert batch_master row if missing (status=1)",
    )
    args = parser.parse_args()
    batch_name = args.batch_name.strip()
    if not batch_name:
        print("Error: batch_name is required.", file=sys.stderr)
        return 1

    db = SessionLocal()
    try:
        current = get_option_value(db, "access_quiz_link")
        parts = _split_csv(current)
        if not subscription_allowed(current, batch_name):
            parts.append(batch_name)
            new_value = _join_csv(parts)
            row = db.query(Option).filter(Option.option_name == "access_quiz_link").first()
            if row:
                row.option_value = new_value
            else:
                db.add(Option(option_name="access_quiz_link", option_value=new_value))
            db.commit()
            print(f"Updated access_quiz_link: added {batch_name!r}")
        else:
            print(f"access_quiz_link already includes {batch_name!r}")

        if args.create_batch_row:
            existing = db.query(BatchMaster).filter(BatchMaster.name == batch_name).first()
            if existing:
                print(f"batch_master already has {batch_name!r} (id={existing.id}, status={existing.status})")
            else:
                db.add(BatchMaster(name=batch_name, status="1", display_order=0))
                db.commit()
                print(f"Created batch_master row: {batch_name!r}")

        ok = subscription_allowed(get_option_value(db, "access_quiz_link"), batch_name)
        print(f"Mock test access for {batch_name!r}: {'enabled' if ok else 'still blocked'}")
        return 0 if ok else 2
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
