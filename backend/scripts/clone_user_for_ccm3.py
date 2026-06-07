"""
Clone a users row (profile + payment flags) to a new email on CCM Batch 3 with correct package/fees.

Usage (from mock_test/backend):
  python scripts/clone_user_for_ccm3.py --source anjuthottam90@gmail.com --target 2anjuthottam90@gmail.com
  python scripts/clone_user_for_ccm3.py --source anjuthottam90@gmail.com --target 2anjuthottam90@gmail.com --apply
  python scripts/clone_user_for_ccm3.py --source anjuthottam90@gmail.com --extract-only -o exports/anju.json
"""
from __future__ import annotations

import argparse
import json
import secrets
import sys
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

_BACKEND = Path(__file__).resolve().parents[1]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

import pymysql
from app.core.config import get_settings
from app.services.access import batch_slug
from app.services.registration import _resolve_package_line_amounts


def _ser(obj: object) -> object:
    if obj is None:
        return None
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, bytes):
        return obj.hex()
    return obj


def _row_dict(row: dict) -> dict:
    return {k: _ser(v) for k, v in row.items()}


def _connect() -> pymysql.connections.Connection:
    s = get_settings()
    return pymysql.connect(
        host=s.db_host,
        port=s.db_port,
        user=s.db_user,
        password=s.db_password,
        database=s.db_name,
        charset="utf8mb4",
    )


def _pick_ccm3_package(cur: pymysql.cursors.DictCursor, category: str, today: date) -> dict:
    cur.execute(
        "SELECT * FROM package WHERE subscription = %s AND category_name = %s AND status = '1' "
        "ORDER BY start_date ASC, id ASC",
        ("CCM Batch 3", category),
    )
    rows = cur.fetchall()
    if not rows:
        raise SystemExit(f"No CCM Batch 3 packages for {category!r}")

    active: list[dict] = []
    for p in rows:
        start = p.get("start_date")
        end = p.get("end_date")
        if start and start > today:
            continue
        if end and end < today:
            continue
        active.append(p)
    if not active:
        raise SystemExit("No currently active CCM Batch 3 tier for today.")
    return active[-1]


class _Pkg:
    """Minimal object for _resolve_package_line_amounts."""

    def __init__(self, row: dict) -> None:
        for k, v in row.items():
            setattr(self, k, v)


def extract_user(cur: pymysql.cursors.DictCursor, email: str) -> dict:
    cur.execute("SELECT * FROM users WHERE email = %s", (email,))
    user = cur.fetchone()
    if not user:
        raise SystemExit(f"User not found: {email}")
    out: dict = {"user": _row_dict(user)}
    uid = user["id"]
    cur.execute("SELECT * FROM user_subscriptions WHERE user_id = %s", (uid,))
    out["user_subscriptions"] = [_row_dict(r) for r in cur.fetchall()]
    if user.get("package_id"):
        cur.execute("SELECT * FROM package WHERE id = %s", (user["package_id"],))
        out["package"] = _row_dict(cur.fetchone())
    return out


def clone_user(
    *,
    source_email: str,
    target_email: str,
    apply: bool,
) -> dict:
    today = date.today()
    conn = _connect()
    try:
        conn.autocommit = False
        cur = conn.cursor(pymysql.cursors.DictCursor)

        extracted = extract_user(cur, source_email)
        source = extracted["user"]

        cur.execute("SELECT id FROM users WHERE email = %s", (target_email,))
        if cur.fetchone():
            raise SystemExit(f"Target email already exists: {target_email}")

        category = (source.get("registration_type") or "Indian Delegates").strip()
        pkg_row = _pick_ccm3_package(cur, category, today)
        pkg_obj = _Pkg(pkg_row)
        gross, gst_pct, gst_amt, total = _resolve_package_line_amounts(pkg_obj, today=today)

        slug = batch_slug("CCM Batch 3") or "ccm-batch-3"
        start_at = pkg_row.get("batch_start_date")
        if isinstance(start_at, date) and not isinstance(start_at, datetime):
            start_dt = datetime.combine(start_at, datetime.min.time())
        elif isinstance(start_at, datetime):
            start_dt = start_at
        else:
            start_dt = datetime.utcnow()

        from app.services.access import course_end_from_batch_start
        from app.services.registration import BATCH_COURSE_MONTHS_DEFAULT

        end_date = course_end_from_batch_start(
            start_dt.date() if isinstance(start_dt, datetime) else start_dt,
            BATCH_COURSE_MONTHS_DEFAULT,
        )
        end_dt = datetime.combine(end_date, datetime.max.time()).replace(microsecond=0)

        new_login_token = secrets.token_urlsafe(32)
        insert_cols = [
            "registration_type",
            "subscription",
            "title",
            "name",
            "email",
            "password",
            "contact_number",
            "hospital",
            "qualification",
            "speciality",
            "country_id",
            "state",
            "city",
            "pin_code",
            "document_file",
            "document_file_2",
            "document_file_status",
            "package_id",
            "currency_name",
            "gross_amount",
            "gst_percentage",
            "gst_amount",
            "total_amount",
            "coupon_code",
            "payment_request_id",
            "payment_id",
            "payment_status",
            "payment_type",
            "payment_date",
            "payment_details",
            "payment_signature",
            "approve",
            "email_verify_token",
            "forgot_token",
            "verify",
            "is_login",
            "login_token",
            "password_hash",
            "role",
        ]
        values = {
            "registration_type": category,
            "subscription": "CCM Batch 3",
            "title": source.get("title"),
            "name": source.get("name"),
            "email": target_email,
            "password": source.get("password"),
            "contact_number": source.get("contact_number"),
            "hospital": source.get("hospital"),
            "qualification": source.get("qualification"),
            "speciality": source.get("speciality"),
            "country_id": source.get("country_id"),
            "state": source.get("state"),
            "city": source.get("city"),
            "pin_code": source.get("pin_code"),
            "document_file": source.get("document_file"),
            "document_file_2": source.get("document_file_2") or "",
            "document_file_status": source.get("document_file_status") or 0,
            "package_id": pkg_row["id"],
            "currency_name": source.get("currency_name") or "INR",
            "gross_amount": gross,
            "gst_percentage": gst_pct,
            "gst_amount": gst_amt,
            "total_amount": total,
            "coupon_code": None,
            "payment_request_id": f"cloned_{secrets.token_hex(8)}",
            "payment_id": f"cloned_{secrets.token_hex(8)}",
            "payment_status": source.get("payment_status") or "Credit",
            "payment_type": source.get("payment_type") or "Online",
            "payment_date": source.get("payment_date") or datetime.utcnow(),
            "payment_details": None,
            "payment_signature": None,
            "approve": source.get("approve") or "1",
            "email_verify_token": None,
            "forgot_token": None,
            "verify": source.get("verify") or "Yes",
            "is_login": "0",
            "login_token": new_login_token,
            "password_hash": source.get("password_hash") or "",
            "role": source.get("role") or "user",
        }

        plan = {
            "source_email": source_email,
            "target_email": target_email,
            "extracted_source": extracted,
            "ccm3_package": _row_dict(pkg_row),
            "fees": {
                "gross_amount": gross,
                "gst_percentage": gst_pct,
                "gst_amount": gst_amt,
                "total_amount": total,
            },
            "user_subscriptions_plan": {
                "batch_slug": slug,
                "package_id": pkg_row["id"],
                "start_at": _ser(start_dt),
                "end_at": _ser(end_dt),
                "status": "active",
            },
            "insert_values": {k: _ser(values[k]) for k in insert_cols},
        }

        if not apply:
            print(json.dumps(plan, indent=2))
            print("\nDry run — pass --apply to insert.")
            return plan

        placeholders = ", ".join(f"%({c})s" for c in insert_cols)
        col_names = ", ".join(f"`{c}`" for c in insert_cols)
        cur.execute(
            f"INSERT INTO users ({col_names}, created_at, updated_at) "
            f"VALUES ({placeholders}, UTC_TIMESTAMP(), UTC_TIMESTAMP())",
            values,
        )
        new_id = cur.lastrowid
        cur.execute(
            "INSERT INTO user_subscriptions "
            "(user_id, batch_slug, package_id, duration_months, start_at, end_at, status, auto_renew, created_at, updated_at) "
            "VALUES (%s, %s, %s, NULL, %s, %s, 'active', '0', UTC_TIMESTAMP(), UTC_TIMESTAMP())",
            (new_id, slug, pkg_row["id"], start_dt, end_dt),
        )
        conn.commit()
        plan["created_user_id"] = new_id
        print(json.dumps(plan, indent=2))
        print(f"\nCreated user id={new_id} email={target_email}")
        return plan
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Clone user to new email on CCM Batch 3.")
    parser.add_argument("--source", default="anjuthottam90@gmail.com")
    parser.add_argument("--target", default="2anjuthottam90@gmail.com")
    parser.add_argument("--apply", action="store_true", help="Insert into database")
    parser.add_argument("--extract-only", action="store_true")
    parser.add_argument("-o", "--output", type=Path, help="Save extract JSON")
    args = parser.parse_args()

    if args.extract_only:
        conn = _connect()
        try:
            cur = conn.cursor(pymysql.cursors.DictCursor)
            data = extract_user(cur, args.source)
        finally:
            conn.close()
        text = json.dumps(data, indent=2)
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(text, encoding="utf-8")
            print(f"Wrote {args.output}")
        else:
            print(text)
        return

    clone_user(
        source_email=args.source.strip(),
        target_email=args.target.strip(),
        apply=args.apply,
    )


if __name__ == "__main__":
    main()
