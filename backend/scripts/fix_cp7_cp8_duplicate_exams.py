#!/usr/bin/env python3
"""
Remove CP 7 / CP 8 from Batch 14 mock tests that were incorrectly tagged.

Those exams (MOCK TEST _1 … _10) should be Batch 14 only; CP 7/CP 8 have their own
Mock_test_1 … Mock_test_10 series (batch = CP 7,CP 8).

Usage (from mock_test/backend):
  python scripts/fix_cp7_cp8_duplicate_exams.py
  python scripts/fix_cp7_cp8_duplicate_exams.py --dry-run
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from app.db import SessionLocal  # noqa: E402
from app.models import QuizExam  # noqa: E402
from app.services.batch_match import subscription_in_batch_csv  # noqa: E402


def _normalize_batch_tokens(batch_csv: str | None) -> list[str]:
    return [p.strip() for p in (batch_csv or "").split(",") if p.strip()]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        rows = (
            db.query(QuizExam)
            .filter(
                QuizExam.status == "1",
                QuizExam.batch.ilike("%Batch 14%"),
                QuizExam.batch.ilike("%CP 7%"),
            )
            .order_by(QuizExam.id)
            .all()
        )
        if not rows:
            print("No Batch 14 + CP 7 overlap exams found — already fixed?")
            return 0

        print(f"Found {len(rows)} exam(s) to retag (Batch 14 only):")
        for e in rows:
            tokens = _normalize_batch_tokens(e.batch)
            new_tokens = [t for t in tokens if t.lower() not in {"cp 7", "cp 8"}]
            new_batch = ",".join(new_tokens) if new_tokens else "Batch 14"
            print(f"  id={e.id} {e.title!r}: {e.batch!r} -> {new_batch!r}")
            if not args.dry_run:
                e.batch = new_batch

        if not args.dry_run:
            db.commit()
            print("Committed.")

        for sub in ("CP 7", "CP 8", "Batch 14"):
            exams = db.query(QuizExam).filter(QuizExam.status == "1").order_by(QuizExam.id).all()
            matched = [e for e in exams if subscription_in_batch_csv(sub, e.batch)]
            print(f"{sub}: {len(matched)} mock test(s)")

        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
