"""
Create or update a user registration for a target batch (profile copied from source or same row).

Usage (from mock_test/backend):
  python scripts/create_batch_entry.py --email shivam_danger@rediffmail.com --batch "Batch EDIC 10" --apply
  python scripts/create_batch_entry.py --source a@x.com --target 2a@x.com --batch "Batch EDIC 10" --apply
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
from app.services.password_crypto import php_password_for_db
from app.services.access import batch_slug
from app.services.registration import (
    BATCH_COURSE_MONTHS_DEFAULT,
    _resolve_package_line_amounts,
    course_end_from_batch_start,
)


def _ser(obj: object) -> object:
    if obj is None:
        return None
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if isinstance(obj, Decimal):
        return float(obj)
    return obj


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


class _Pkg:
    def __init__(self, row: dict) -> None:
        for k, v in row.items():
            setattr(self, k, v)


def _pick_active_package(cur: pymysql.cursors.DictCursor, subscription: str, category: str, today: date) -> dict:
    cur.execute(
        "SELECT * FROM package WHERE subscription = %s AND category_name = %s AND status = '1' "
        "ORDER BY start_date ASC, id ASC",
        (subscription, category),
    )
    rows = cur.fetchall()
    if not rows:
        raise SystemExit(f"No active packages for {subscription!r} / {category!r}")
    active = [
        p
        for p in rows
        if (not p.get("start_date") or p["start_date"] <= today)
        and (not p.get("end_date") or p["end_date"] >= today)
    ]
    if not active:
        raise SystemExit(f"No pricing tier open today for {subscription!r}.")
    return active[-1]


def _as_dt(val: object) -> datetime:
    if isinstance(val, datetime):
        return val
    if isinstance(val, date):
        return datetime.combine(val, datetime.min.time())
    return datetime.utcnow()


def create_entry(
    *,
    email: str,
    batch_subscription: str,
    source_email: str | None,
    apply: bool,
    plain_password: str | None = None,
    name: str | None = None,
    phone: str | None = None,
) -> dict:
    today = date.today()
    conn = _connect()
    try:
        conn.autocommit = False
        cur = conn.cursor(pymysql.cursors.DictCursor)

        profile_email = source_email or email
        cur.execute("SELECT * FROM users WHERE email = %s", (profile_email,))
        source = cur.fetchone()

        cur.execute("SELECT * FROM users WHERE email = %s", (email,))
        existing_target = cur.fetchone()

        if not source and not existing_target:
            if not plain_password:
                raise SystemExit(
                    f"No existing user for {profile_email!r}. Pass --password to create a new account."
                )
            local = email.split("@")[0].replace(".", " ").replace("_", " ").strip()
            source = {
                "registration_type": "Indian Delegates",
                "title": "Dr.",
                "name": (name or local.title() or "Student").strip(),
                "email": email,
                "password": php_password_for_db(plain_password),
                "contact_number": (phone or "9999999999").strip(),
                "hospital": "",
                "qualification": "",
                "speciality": "",
                "country_id": 101,
                "state": "",
                "city": "",
                "pin_code": "",
                "document_file": "1",
                "document_file_2": "",
                "document_file_status": 1,
                "currency_name": "INR",
            }
        elif not source:
            source = existing_target
        elif plain_password:
            source = dict(source)
            source["password"] = php_password_for_db(plain_password)
            if name:
                source["name"] = name.strip()
            if phone:
                source["contact_number"] = phone.strip()

        category = (source.get("registration_type") or "Indian Delegates").strip()
        pkg_row = _pick_active_package(cur, batch_subscription, category, today)
        gross, gst_pct, gst_amt, total = _resolve_package_line_amounts(_Pkg(pkg_row), today=today)
        slug = batch_slug(batch_subscription) or batch_subscription.lower().replace(" ", "-")

        batch_start = pkg_row.get("batch_start_date") or today
        start_dt = _as_dt(batch_start)
        end_dt = datetime.combine(
            course_end_from_batch_start(
                start_dt.date() if isinstance(start_dt, datetime) else start_dt,
                BATCH_COURSE_MONTHS_DEFAULT,
            ),
            datetime.max.time(),
        ).replace(microsecond=0)

        plan = {
            "email": email,
            "batch_subscription": batch_subscription,
            "package_id": pkg_row["id"],
            "package_name": pkg_row["name"],
            "fees": {"gross": gross, "gst_pct": gst_pct, "gst_amt": gst_amt, "total": total},
            "course_access": {"batch_slug": slug, "start_at": _ser(start_dt), "end_at": _ser(end_dt)},
            "mode": "update" if existing_target and existing_target["email"] == email else "insert",
        }

        if existing_target and email != profile_email:
            raise SystemExit(f"Target email already exists: {email}")

        if not apply:
            plan["source_profile"] = {k: _ser(v) for k, v in source.items()}
            print(json.dumps(plan, indent=2))
            print("\nDry run — pass --apply to save.")
            return plan

        if existing_target:
            user_id = existing_target["id"]
            cur.execute(
                """
                UPDATE users SET
                  registration_type = %s,
                  subscription = %s,
                  title = %s,
                  name = %s,
                  contact_number = %s,
                  hospital = %s,
                  qualification = %s,
                  speciality = %s,
                  country_id = %s,
                  state = %s,
                  city = %s,
                  pin_code = %s,
                  document_file = %s,
                  document_file_2 = COALESCE(%s, document_file_2, ''),
                  document_file_status = %s,
                  package_id = %s,
                  currency_name = %s,
                  gross_amount = %s,
                  gst_percentage = %s,
                  gst_amount = %s,
                  total_amount = %s,
                  coupon_code = NULL,
                  payment_request_id = %s,
                  payment_id = %s,
                  payment_status = 'Credit',
                  payment_type = 'Online',
                  payment_date = UTC_TIMESTAMP(),
                  payment_details = NULL,
                  payment_signature = NULL,
                  approve = '1',
                  verify = 'Yes',
                  password = %s,
                  updated_at = UTC_TIMESTAMP()
                WHERE id = %s
                """,
                (
                    category,
                    batch_subscription,
                    source.get("title"),
                    source.get("name"),
                    source.get("contact_number"),
                    source.get("hospital"),
                    source.get("qualification"),
                    source.get("speciality"),
                    source.get("country_id"),
                    source.get("state"),
                    source.get("city"),
                    source.get("pin_code"),
                    source.get("document_file"),
                    source.get("document_file_2"),
                    source.get("document_file_status") or 1,
                    pkg_row["id"],
                    source.get("currency_name") or "INR",
                    gross,
                    gst_pct,
                    gst_amt,
                    total,
                    f"admin_{secrets.token_hex(8)}",
                    f"admin_{secrets.token_hex(8)}",
                    source.get("password"),
                    user_id,
                ),
            )
            plan["mode"] = "updated"
        else:
            cur.execute(
                """
                INSERT INTO users (
                  registration_type, subscription, title, name, email, password,
                  contact_number, hospital, qualification, speciality,
                  country_id, state, city, pin_code,
                  document_file, document_file_2, document_file_status,
                  package_id, currency_name, gross_amount, gst_percentage, gst_amount, total_amount,
                  payment_request_id, payment_id, payment_status, payment_type, payment_date,
                  approve, verify, is_login, login_token, password_hash, role,
                  created_at, updated_at
                ) VALUES (
                  %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,
                  'Credit','Online',UTC_TIMESTAMP(),'1','Yes','0',%s,'','user',UTC_TIMESTAMP(),UTC_TIMESTAMP()
                )
                """,
                (
                    category,
                    batch_subscription,
                    source.get("title"),
                    source.get("name"),
                    email,
                    source.get("password"),
                    source.get("contact_number"),
                    source.get("hospital"),
                    source.get("qualification"),
                    source.get("speciality"),
                    source.get("country_id"),
                    source.get("state"),
                    source.get("city"),
                    source.get("pin_code"),
                    source.get("document_file"),
                    source.get("document_file_2") or "",
                    source.get("document_file_status") or 1,
                    pkg_row["id"],
                    source.get("currency_name") or "INR",
                    gross,
                    gst_pct,
                    gst_amt,
                    total,
                    f"admin_{secrets.token_hex(8)}",
                    f"admin_{secrets.token_hex(8)}",
                    secrets.token_urlsafe(32),
                ),
            )
            user_id = cur.lastrowid
            plan["mode"] = "inserted"

        cur.execute(
            "SELECT id FROM user_subscriptions WHERE user_id = %s AND batch_slug = %s AND status = 'active'",
            (user_id, slug),
        )
        if not cur.fetchone():
            cur.execute(
                """
                INSERT INTO user_subscriptions
                (user_id, batch_slug, package_id, duration_months, start_at, end_at, status, auto_renew, created_at, updated_at)
                VALUES (%s, %s, %s, NULL, %s, %s, 'active', '0', UTC_TIMESTAMP(), UTC_TIMESTAMP())
                """,
                (user_id, slug, pkg_row["id"], start_dt, end_dt),
            )

        conn.commit()
        plan["user_id"] = user_id
        print(json.dumps(plan, indent=2))
        print(f"\nDone ({plan['mode']}): user id={user_id} email={email} -> {batch_subscription}")
        return plan
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Create/update batch registration from existing profile.")
    parser.add_argument("--email", required=True, help="Target login email")
    parser.add_argument("--batch", default="Batch EDIC 10", help="package.subscription value")
    parser.add_argument("--source", help="Copy profile from this email (default: same as --email)")
    parser.add_argument("--password", help="Login password for new user or to reset on update")
    parser.add_argument("--name", help="Full name when creating a new user")
    parser.add_argument("--phone", help="Contact number when creating a new user")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    create_entry(
        email=args.email.strip(),
        batch_subscription=args.batch.strip(),
        source_email=(args.source or args.email).strip() if args.source or args.password is None else None,
        apply=args.apply,
        plain_password=args.password,
        name=args.name,
        phone=args.phone,
    )


if __name__ == "__main__":
    main()
