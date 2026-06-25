#!/usr/bin/env python3
"""Reset all mock test attempts for users by email (fresh retake).

Usage (from mock_test/backend):
  python scripts/reset_user_mock_tests.py email1@example.com email2@example.com
  python scripts/reset_user_mock_tests.py --dry-run email@example.com
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from sqlalchemy import func  # noqa: E402

from app.db import SessionLocal  # noqa: E402
from app.models import User, UserAnswer, UserExam  # noqa: E402
from app.services.exam_batch_copy import enable_mock_test_access  # noqa: E402


def reset_user(db, email: str, *, dry_run: bool) -> dict:
    row = db.query(User).filter(func.lower(User.email) == email.strip().lower()).first()
    if not row:
        return {"email": email, "found": False}

    ue_count = db.query(UserExam).filter(UserExam.user_id == row.id).count()
    ua_count = db.query(UserAnswer).filter(UserAnswer.user_id == row.id).count()

    access = None
    batch = (row.subscription or "").strip()
    if batch:
        access = enable_mock_test_access(db, batch, dry_run=dry_run)

    if not dry_run:
        db.query(UserAnswer).filter(UserAnswer.user_id == row.id).delete(
            synchronize_session=False
        )
        db.query(UserExam).filter(UserExam.user_id == row.id).delete(
            synchronize_session=False
        )
        db.commit()

    return {
        "email": email,
        "found": True,
        "user_id": row.id,
        "subscription": batch,
        "deleted_user_exam": ue_count,
        "deleted_user_answer": ua_count,
        "mock_test_access": access,
        "dry_run": dry_run,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Reset mock test attempts for users.")
    parser.add_argument("emails", nargs="+", help="User email addresses")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        for email in args.emails:
            result = reset_user(db, email, dry_run=args.dry_run)
            print(result)
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
