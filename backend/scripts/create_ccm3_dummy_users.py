#!/usr/bin/env python3
"""Create or update dummy CCM Batch 3 test accounts."""
from __future__ import annotations

import argparse
import sys
import uuid
from datetime import datetime
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from app.db import SessionLocal  # noqa: E402
from app.models import Package, User, UserPackagePayment  # noqa: E402
from app.services.access import (  # noqa: E402
    admin_subscription_summary,
    can_access_mock_test,
    can_access_video_library,
    get_option_value,
    subscription_allowed,
)
from app.services.password_crypto import php_password_for_db  # noqa: E402

BATCH = "CCM Batch 3"
PACKAGE_ID = 213
DEFAULT_PASSWORD = "Ccm31234"


def _apply_user(db, user: User, pkg: Package, *, request_id: str, payment_date: datetime) -> None:
    user.subscription = BATCH
    user.package_id = PACKAGE_ID
    user.currency_name = "INR"
    user.gross_amount = float(pkg.gross_amount or 0)
    user.gst_percentage = float(pkg.gst_percentage or 0)
    user.gst_amount = float(pkg.gst_amount or 0)
    user.total_amount = float(pkg.total_amount or 0)
    user.payment_request_id = request_id
    user.payment_id = None
    user.payment_status = "Credit"
    user.payment_type = "Offline"
    user.payment_date = payment_date
    user.payment_signature = None
    user.payment_details = "Dummy CCM Batch 3 test account"
    user.document_file_status = 1
    user.approve = "1"
    user.verify = "Yes"
    user.updated_at = datetime.utcnow()


def _add_payment(db, user_id: int, request_id: str, payment_date: datetime) -> None:
    db.add(
        UserPackagePayment(
            user_id=user_id,
            package_id=PACKAGE_ID,
            subscription=BATCH,
            package_type="Topup",
            currency_name="INR",
            payment_request_id=request_id,
            payment_id=None,
            payment_status="Credit",
            payment_type="Offline",
            payment_date=payment_date,
            payment_details="Dummy CCM Batch 3 test account",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
    )


def _create_fields_for_email(email: str) -> dict | None:
    profiles: dict[str, dict] = {
        "abhijeetanandccm@gmail.com": {
            "title": "Dr.",
            "name": "ABHIJEET ANAND",
            "contact_number": "9876543210",
            "hospital": "Dummy Hospital",
            "qualification": "MD",
            "speciality": "Critical Care",
            "country_id": 243,
            "state": "Delhi",
            "city": "New Delhi",
            "pin_code": "110001",
        },
        "akshaysingadwar99@gmail.com": {
            "title": "Dr.",
            "name": "AKSHAY SINGADWAR",
            "contact_number": "9876500001",
            "hospital": "Dummy Hospital",
            "qualification": "MD",
            "speciality": "Critical Care",
            "country_id": 243,
            "state": "Maharashtra",
            "city": "Nagpur",
            "pin_code": "440001",
        },
        "sandeep.anesth@aiimsbhopal.edu.in": {
            "title": "Dr.",
            "name": "SANDEEP",
            "contact_number": "9876500002",
            "hospital": "AIIMS Bhopal",
            "qualification": "MD",
            "speciality": "Anaesthesia",
            "country_id": 243,
            "state": "Madhya Pradesh",
            "city": "Bhopal",
            "pin_code": "462020",
        },
    }
    return profiles.get(email)


def upsert_dummy_user(
    db,
    email: str,
    *,
    password: str,
    payment_date: datetime,
    create_fields: dict | None = None,
    update_existing: bool = True,
) -> tuple[str, User]:
    email = email.strip().lower()
    pkg = db.query(Package).filter(Package.id == PACKAGE_ID).first()
    if not pkg:
        raise RuntimeError(f"Package {PACKAGE_ID} not found")

    user = db.query(User).filter(User.email == email).first()
    request_id = f"order_dummy_{uuid.uuid4().hex[:16]}"
    enc_pwd = php_password_for_db(password)

    if user:
        if not update_existing:
            raise RuntimeError(f"{email} already exists; use --update to modify")
        user.password = enc_pwd
        _apply_user(db, user, pkg, request_id=request_id, payment_date=payment_date)
        db.add(user)
        action = "updated"
    else:
        fields = create_fields or {}
        user = User(
            registration_type="Indian Delegates",
            subscription=BATCH,
            title=fields.get("title", "Dr."),
            name=fields.get("name", "Dummy User"),
            email=email,
            password=enc_pwd,
            contact_number=fields.get("contact_number", "9876543210"),
            hospital=fields.get("hospital", "Dummy Hospital"),
            qualification=fields.get("qualification", "MD"),
            speciality=fields.get("speciality", "Critical Care"),
            country_id=int(fields.get("country_id", 243)),
            state=fields.get("state", "Delhi"),
            city=fields.get("city", "New Delhi"),
            pin_code=fields.get("pin_code", "110001"),
            document_file="",
            document_file_2="",
            document_file_status=1,
            package_id=PACKAGE_ID,
            coupon_code="",
            approve="1",
            verify="Yes",
            is_login="0",
            login_token="",
            password_hash="",
            role="user",
            created_at=datetime.utcnow(),
        )
        _apply_user(db, user, pkg, request_id=request_id, payment_date=payment_date)
        db.add(user)
        db.flush()
        action = "created"

    _add_payment(db, user.id, request_id, payment_date)
    db.commit()
    db.refresh(user)
    return action, user


def main() -> int:
    parser = argparse.ArgumentParser(description="Create dummy CCM Batch 3 accounts.")
    parser.add_argument("emails", nargs="+", help="User email addresses")
    parser.add_argument("--password", default=DEFAULT_PASSWORD, help="8-char login password")
    parser.add_argument("--update", action="store_true", help="Update existing users")
    args = parser.parse_args()

    if len(args.password) != 8:
        print("Error: password must be exactly 8 characters.", file=sys.stderr)
        return 1

    payment_date = datetime.utcnow()
    db = SessionLocal()
    try:
        for raw_email in args.emails:
            email = raw_email.strip().lower()
            create_fields = _create_fields_for_email(email)

            try:
                action, user = upsert_dummy_user(
                    db,
                    email,
                    password=args.password,
                    payment_date=payment_date,
                    create_fields=create_fields,
                    update_existing=args.update or db.query(User).filter(User.email == email).first() is not None,
                )
            except RuntimeError as exc:
                print(f"SKIP {email}: {exc}", file=sys.stderr)
                continue

            pkg = db.query(Package).filter(Package.id == user.package_id).first()
            summary = admin_subscription_summary(user, pkg=pkg, subs=[])
            v_ok, _ = can_access_video_library(db, user)
            q_ok, _ = can_access_mock_test(db, user)
            print(f"{action.upper()} {email} (id={user.id})")
            print(f"  status={summary.get('status')} until={summary.get('end_date')}")
            print(f"  video={v_ok} quiz={q_ok} password={args.password}")

        for opt in ("access_video_library_link", "access_quiz_link"):
            val = get_option_value(db, opt)
            print(f"{opt}: CCM Batch 3 allowed={subscription_allowed(val, BATCH)}")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
