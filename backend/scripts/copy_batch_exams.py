#!/usr/bin/env python3
"""
Duplicate quiz_exam rows from one batch to another (same sections/questions).

Usage (from mock_test/backend):
  python scripts/copy_batch_exams.py --dry-run
  python scripts/copy_batch_exams.py --source "Batch 15" --target "BATCH 16-MCCM"
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
from app.services.exam_batch_copy import clone_batch_exams, preview_clone_batch_exams  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Clone mock tests from source batch to target batch.")
    parser.add_argument("--source", default="Batch 15")
    parser.add_argument("--target", default="BATCH 16-MCCM")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--no-enable-access", action="store_true")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        if args.dry_run:
            out = preview_clone_batch_exams(db, source_batch=args.source, target_batch=args.target)
        else:
            out = clone_batch_exams(
                db,
                source_batch=args.source,
                target_batch=args.target,
                enable_mock_test_access_flag=not args.no_enable_access,
                dry_run=False,
            )
        print(json.dumps(out, indent=2, default=str))
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
