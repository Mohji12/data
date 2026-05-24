#!/usr/bin/env python3
"""
Cascade-update DB references after a batch rename (one-off fix or dry-run preview).

Usage (from mock_test/backend):
  python scripts/rename_batch_references.py "Batch 15" "CCM Batch 15" --dry-run
  python scripts/rename_batch_references.py "Batch 15" "CCM Batch 15" --batch-id 42
  python scripts/rename_batch_references.py "Batch 15" "CCM Batch 15" --register-alias-only
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from app.db import SessionLocal  # noqa: E402
from app.models import BatchMaster  # noqa: E402
from app.services.batch_rename import rename_batch_references  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Cascade batch name references across the database.")
    parser.add_argument("old_name", help='Previous batch name, e.g. "Batch 15"')
    parser.add_argument("new_name", help='Current/canonical batch name, e.g. "CCM Batch 15"')
    parser.add_argument(
        "--batch-id",
        type=int,
        default=None,
        help="batch_master.id (required unless --register-alias-only with known id)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print counts only; do not commit changes",
    )
    parser.add_argument(
        "--register-alias-only",
        action="store_true",
        help="Only register old URL slug alias; skip other table updates",
    )
    args = parser.parse_args()

    old_name = (args.old_name or "").strip()
    new_name = (args.new_name or "").strip()
    if not old_name or not new_name:
        print("old_name and new_name are required.", file=sys.stderr)
        return 1

    db = SessionLocal()
    try:
        batch_id = args.batch_id
        if batch_id is None:
            row = (
                db.query(BatchMaster)
                .filter(BatchMaster.name.ilike(new_name))
                .order_by(BatchMaster.id.desc())
                .first()
            )
            if not row:
                print(
                    f"No batch_master row named {new_name!r}. Pass --batch-id explicitly.",
                    file=sys.stderr,
                )
                return 1
            batch_id = row.id
            print(f"Resolved batch_id={batch_id} from batch_master.name={new_name!r}")
        else:
            row = db.query(BatchMaster).filter(BatchMaster.id == batch_id).first()
            if not row:
                print(f"batch_master id={batch_id} not found.", file=sys.stderr)
                return 1
            if (row.name or "").strip().casefold() != new_name.casefold():
                print(
                    f"Warning: batch_master id={batch_id} name is {row.name!r}, not {new_name!r}.",
                    file=sys.stderr,
                )

        counts = rename_batch_references(
            db,
            old_name,
            new_name,
            batch_id,
            dry_run=args.dry_run,
            register_alias_only=args.register_alias_only,
        )
        if args.dry_run:
            db.rollback()
            print("DRY RUN — no changes committed.")
        else:
            db.commit()
            print("Committed.")

        print(json.dumps(counts, indent=2))
        return 0
    except Exception as exc:
        db.rollback()
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
