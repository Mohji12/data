"""
DEPRECATED — breaks PHP website login. Do not run on production.

PHP `my_simple_crypt` stores an OUTER base64 (~32 chars). This script strips to INNER (~24 chars).
After that, PHP still hashes the typed password to OUTER, so compare fails → "invalid password".

To fix inner-only rows, run instead:
    python -m scripts.sync_passwords_to_php_outer

---

(Legacy description) Normalize accidental double wrap — NOT compatible with main CodeIgniter site.
"""

from __future__ import annotations

import argparse
import base64
import binascii
import re
import string
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sqlalchemy.orm import Session  # noqa: E402

from app.db import SessionLocal  # noqa: E402
from app.models import User  # noqa: E402

_B64_CHARS = frozenset(string.ascii_letters + string.digits + "+/=")
_INNER_BYTE_FIX: dict[int, int] = {0x96: ord("V")}


def _inner_candidate_from_outer_raw(raw: bytes) -> str | None:
    """If outer decodes to an ASCII base64 *string*, return it when it decodes to valid AES blocks."""
    if len(raw) % 16 == 0:
        return None
    fixed = bytes(_INNER_BYTE_FIX.get(b, b) for b in raw)
    try:
        inner = fixed.decode("ascii")
    except UnicodeDecodeError:
        inner = fixed.decode("latin-1").translate(str.maketrans({"\x96": "V"}))
        inner = "".join(c for c in inner if c in _B64_CHARS)
    if not inner or not re.fullmatch(r"[A-Za-z0-9+/]+=*", inner):
        return None
    try:
        ct = base64.b64decode(inner, validate=True)
    except (ValueError, binascii.Error):
        try:
            ct = base64.b64decode(inner)
        except binascii.Error:
            return None
    if len(ct) == 0 or len(ct) % 16 != 0:
        return None
    return inner


def normalize_if_double_wrapped(stored: str) -> str | None:
    """Return canonical single-layer string, or None if nothing to do."""
    stored = (stored or "").strip()
    if len(stored) < 20 or len(stored) % 4 != 0:
        return None
    if not re.fullmatch(r"[A-Za-z0-9+/]+=*", stored):
        return None
    try:
        raw = base64.b64decode(stored, validate=True)
    except (ValueError, binascii.Error):
        return None
    inner = _inner_candidate_from_outer_raw(raw)
    if inner is None or inner == stored:
        return None
    return inner


def looks_like_failed_double_wrap(stored: str) -> bool:
    """Heuristic: outer base64 ok, but not raw cipher — and inner not recoverable."""
    stored = (stored or "").strip()
    if len(stored) < 28 or len(stored) % 4 != 0:
        return False
    if not re.fullmatch(r"[A-Za-z0-9+/]+=*", stored):
        return False
    try:
        raw = base64.b64decode(stored, validate=True)
    except (ValueError, binascii.Error):
        return False
    if len(raw) % 16 == 0:
        return False
    return _inner_candidate_from_outer_raw(raw) is None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--force-deprecated",
        action="store_true",
        help="This script strips the outer base64 PHP expects; main site login will fail. "
        "Use scripts.sync_passwords_to_php_outer instead.",
    )
    args = parser.parse_args()

    if not args.force_deprecated:
        print(
            "Refusing to run: normalize_double_base64_passwords breaks PHP website login.\n"
            "Use:  python -m scripts.sync_passwords_to_php_outer --dry-run\n"
            "Then: python -m scripts.sync_passwords_to_php_outer\n"
            "Re-run with --force-deprecated only if you understand the risk."
        )
        sys.exit(1)

    db: Session = SessionLocal()
    updated = 0
    corrupt: list[tuple[int, str]] = []
    try:
        for user in db.query(User).all():
            pwd = (user.password or "").strip()
            if not pwd:
                continue
            new_pwd = normalize_if_double_wrapped(pwd)
            if new_pwd:
                print(f"OK id={user.id} email={user.email!r} -> single layer ({len(pwd)} -> {len(new_pwd)} chars)")
                if not args.dry_run:
                    user.password = new_pwd
                updated += 1
            elif looks_like_failed_double_wrap(pwd):
                corrupt.append((user.id, user.email or ""))
        if not args.dry_run:
            db.commit()
        print(f"\nUpdated: {updated}  dry_run={args.dry_run}")
        if corrupt:
            print(f"\nLikely corrupt (reset password in admin / SQL): {len(corrupt)} users")
            for uid, em in corrupt[:80]:
                print(f"  id={uid}  email={em!r}")
            if len(corrupt) > 80:
                print(f"  ... and {len(corrupt) - 80} more")
    finally:
        db.close()


if __name__ == "__main__":
    main()
