#!/usr/bin/env python3
"""
Hash / encrypt passwords the same way this project stores them in MySQL.

Student users (table: users, column: password)
  - NOT bcrypt/md5 — AES-256-CBC via PHP my_simple_crypt (reversible encryption)
  - Stored value: double base64 (~32 chars), e.g. SUNMallZSHF1Ybm5WUT09
  - Use the "outer (DB)" value when updating users.password

Admin users (table: admin, column: password)
  - MD5 hex digest (32 chars), e.g. 5f4dcc3b5aa765d61d8327deb882cf99

Usage:
  cd mock_test/backend
  python scripts/hash_password.py "MyPassword123"
  python scripts/hash_password.py --admin "MyPassword123"
  python scripts/hash_password.py --both "MyPassword123"
  python scripts/hash_password.py          # prompts for password (hidden)
"""
from __future__ import annotations

import argparse
import getpass
import hashlib
import sys
from pathlib import Path

# Allow: python scripts/hash_password.py from mock_test/backend
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from app.services.password_crypto import (  # noqa: E402
    my_simple_crypt,
    php_password_for_db,
    stored_password_variants,
)


def student_password_values(plain: str) -> dict[str, str]:
    inner, outer = stored_password_variants(plain)
    return {
        "plain": plain,
        "inner_single_base64": inner,
        "outer_db_value": outer,
        "outer_via_my_simple_crypt": my_simple_crypt(plain, "encrypt"),
    }


def admin_password_md5(plain: str) -> str:
    return hashlib.md5(plain.encode("utf-8")).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate password values for users.password (AES) or admin.password (MD5).",
    )
    parser.add_argument(
        "password",
        nargs="?",
        help="Plaintext password (omit to type securely at prompt)",
    )
    parser.add_argument(
        "--admin",
        action="store_true",
        help="Output admin MD5 only",
    )
    parser.add_argument(
        "--student",
        action="store_true",
        help="Output student users.password value only (default if neither flag set)",
    )
    parser.add_argument(
        "--both",
        action="store_true",
        help="Output both student and admin values",
    )
    args = parser.parse_args()

    plain = args.password
    if not plain:
        plain = getpass.getpass("Password: ")
    if not plain:
        print("Error: password is required.", file=sys.stderr)
        return 1

    show_both = args.both
    show_admin = args.admin or show_both
    show_student = args.student or show_both or (not args.admin)

    if show_student:
        vals = student_password_values(plain)
        print("=== Student user (users.password) ===")
        print("Algorithm : AES-256-CBC + double base64 (PHP my_simple_crypt)")
        print(f"Plain     : {vals['plain']}")
        print(f"DB value  : {vals['outer_db_value']}  <-- use this in users.password")
        print(f"Inner b64 : {vals['inner_single_base64']}  (legacy single layer)")
        # Sanity check round-trip
        decrypted = my_simple_crypt(vals["outer_db_value"], "decrypt")
        if decrypted != plain:
            print("Warning: decrypt round-trip mismatch!", file=sys.stderr)
            return 2

    if show_admin:
        if show_student:
            print()
        md5 = admin_password_md5(plain)
        print("=== Admin user (admin.password) ===")
        print("Algorithm : MD5 hex")
        print(f"Plain     : {plain}")
        print(f"DB value  : {md5}  <-- use this in admin.password")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
