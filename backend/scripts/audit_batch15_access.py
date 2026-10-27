#!/usr/bin/env python3
"""One-off audit: Batch 15 access as of run time."""
from __future__ import annotations

import sys
from datetime import date, datetime
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from sqlalchemy import text

from app.db import SessionLocal
from app.models import User
from app.services.access import (
    _user_has_extension_payment,
    ensure_one_time_batch_access,
    get_extension_batch_settings,
    get_option_value,
    has_active_subscription,
)


def main() -> int:
    db = SessionLocal()
    try:
        opts = [
            "batch_access_closed::batch-15",
            "extension_base_date::batch-15",
            "extension_end_date::batch-15",
            "extension_enabled::batch-15",
        ]
        print("=== Batch 15 options ===")
        for k in opts:
            print(f"  {k} = {get_option_value(db, k)!r}")
        manual = get_extension_batch_settings(db, "Batch 15")
        print("  extension settings:", manual)
        print(f"UTC now: {datetime.utcnow()}")
        print(f"date.today(): {date.today()}")

        users = db.query(User).filter(User.subscription.ilike("%batch%15%")).all()
        print(f"\nBatch 15 users: {len(users)}")

        ext_paid = active_ext_video = blocked = still_ok = 0
        for u in users:
            has_ext = _user_has_extension_payment(db, u)
            ok, _reason = ensure_one_time_batch_access(db, u)
            if has_ext:
                ext_paid += 1
                if ok and has_active_subscription(db, u, u.subscription):
                    active_ext_video += 1
            if ok:
                still_ok += 1
            else:
                blocked += 1

        print(f"  extension payment (Credit): {ext_paid}")
        print(f"  extension + active sub + video access OK: {active_ext_video}")
        print(f"  ensure_one_time_batch_access blocked: {blocked}")
        print(f"  ensure_one_time_batch_access allowed: {still_ok}")

        active_subs = db.execute(
            text(
                """
                SELECT COUNT(*) FROM user_subscription us
                JOIN user u ON u.id = us.user_id
                WHERE us.status = 'active' AND us.end_at >= UTC_TIMESTAMP()
                AND (
                  LOWER(us.batch_slug) LIKE '%batch%15%'
                  OR LOWER(u.subscription) LIKE '%batch%15%'
                )
                """
            )
        ).scalar()
        print(f"\nActive user_subscription rows (end_at >= UTC now): {active_subs}")

        sample = db.execute(
            text(
                """
                SELECT us.user_id, us.end_at, us.batch_slug, u.subscription
                FROM user_subscription us
                JOIN user u ON u.id = us.user_id
                WHERE us.status = 'active' AND us.end_at >= UTC_TIMESTAMP()
                AND (
                  LOWER(us.batch_slug) LIKE '%batch%15%'
                  OR LOWER(u.subscription) LIKE '%batch%15%'
                )
                ORDER BY us.end_at DESC LIMIT 8
                """
            )
        ).fetchall()
        print("Sample still-active subscriptions:")
        for row in sample:
            print(f"  {row}")
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
