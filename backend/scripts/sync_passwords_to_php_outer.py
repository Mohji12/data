"""
Rewrite users.password to the exact value PHP `my_simple_crypt($plain)` produces.

PHP stores: base64_encode( openssl_encrypt(...) )  where openssl_encrypt(..., 0) already
returns base64 — so the column is typically ~32 chars for an 8-char password.

If you ran `normalize_double_base64_passwords` (inner-only / ~24 chars), the **main website**
login breaks because PHP still compares using the **outer** hash. Run this script to fix.

Safe for users already on correct outer format: decrypt + re-encode yields the same string.

Usage (from mock_test/backend, DB backup first):
    python -m scripts.sync_passwords_to_php_outer --dry-run
    python -m scripts.sync_passwords_to_php_outer
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sqlalchemy.orm import Session  # noqa: E402

from app.db import SessionLocal  # noqa: E402
from app.models import User  # noqa: E402
from app.routers.auth import _php_password_for_db, my_simple_crypt  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    db: Session = SessionLocal()
    updated = 0
    failed = 0
    try:
        for user in db.query(User).all():
            p = (user.password or "").strip()
            if not p:
                continue
            try:
                plain = my_simple_crypt(p, "decrypt")
            except Exception:
                failed += 1
                continue
            if plain is None or plain == "":
                failed += 1
                continue
            outer = _php_password_for_db(plain)
            if p != outer:
                print(
                    f"id={user.id} email={user.email!r} len {len(p)} -> {len(outer)}"
                )
                if not args.dry_run:
                    user.password = outer
                updated += 1
        if not args.dry_run:
            db.commit()
        print(f"\nUpdated: {updated}  decrypt_skipped: {failed}  dry_run={args.dry_run}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
