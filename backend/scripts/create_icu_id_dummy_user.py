#!/usr/bin/env python3
"""Create or update a dummy ICU-ID Certification Course test account."""
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

BATCH = "ICU-ID Certification Course"
DEFAULT_EMAIL = "icu-id.dummy@harishcriticalcare.test"
DEFAULT_PASSWORD = "IcuId123"
INDIAN_PACKAGE_NAME = "ICU-ID Certification Course — Indian Delegates"


def _find_indian_package(db) -> Package:
    pkg = (
        db.query(Package)
        .filter(
            Package.subscription == BATCH,
            Package.category_name == "Indian Delegates",
            Package.status == "1",
        )
        .order_by(Package.id.desc())
        .first()
    )
    if pkg:
        return pkg
    pkg = (
        db.query(Package)
        .filter(Package.subscription == BATCH, Package.status == "1")
        .order_by(Package.id.desc())
        .first()
    )
    if not pkg:
        raise RuntimeError(
            f"No package for {BATCH!r}. Run: python scripts/seed_icu_id_certification_course.py"
        )
    return pkg


def _apply_user(db, user: User, pkg: Package, *, request_id: str, payment_date: datetime) -> None:
    user.subscription = BATCH
    user.package_id = pkg.id
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
    user.payment_details = "Dummy ICU-ID Certification Course test account"
    user.document_file_status = 1
    user.approve = "1"
    user.verify = "Yes"
    user.updated_at = datetime.utcnow()


def _add_payment(db, user_id: int, pkg: Package, request_id: str, payment_date: datetime) -> None:
    db.add(
        UserPackagePayment(
            user_id=user_id,
            package_id=pkg.id,
            subscription=BATCH,
            package_type="Topup",
            currency_name="INR",
            payment_request_id=request_id,
            payment_id=None,
            payment_status="Credit",
            payment_type="Offline",
            payment_date=payment_date,
            payment_details="Dummy ICU-ID Certification Course test account",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
    )


def upsert_dummy_user(
    db,
    email: str,
    *,
    password: str,
    name: str,
    payment_date: datetime,
    update_existing: bool,
) -> tuple[str, User]:
    email = email.strip().lower()
    pkg = _find_indian_package(db)
    user = db.query(User).filter(User.email == email).first()
    request_id = f"order_icuid_{uuid.uuid4().hex[:16]}"
    enc_pwd = php_password_for_db(password)

    if user:
        if not update_existing:
            raise RuntimeError(f"{email} already exists; pass --update to reset password and batch")
        user.password = enc_pwd
        user.name = name
        _apply_user(db, user, pkg, request_id=request_id, payment_date=payment_date)
        db.add(user)
        action = "updated"
    else:
        user = User(
            registration_type="Indian Delegates",
            subscription=BATCH,
            title="Dr.",
            name=name,
            email=email,
            password=enc_pwd,
            contact_number="9876501234",
            hospital="Dummy Hospital",
            qualification="MD",
            speciality="Critical Care",
            country_id=243,
            state="Delhi",
            city="New Delhi",
            pin_code="110001",
            document_file="",
            document_file_2="",
            document_file_status=1,
            package_id=pkg.id,
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

    _add_payment(db, user.id, pkg, request_id, payment_date)
    db.commit()
    db.refresh(user)
    return action, user


def main() -> int:
    parser = argparse.ArgumentParser(description="Create dummy ICU-ID Certification Course login.")
    parser.add_argument("--email", default=DEFAULT_EMAIL, help="Login email")
    parser.add_argument("--password", default=DEFAULT_PASSWORD, help="8-character password")
    parser.add_argument("--name", default="ICU-ID Dummy Student", help="Display name")
    parser.add_argument("--update", action="store_true", help="Update existing user with same email")
    args = parser.parse_args()

    if len(args.password) != 8:
        print("Error: password must be exactly 8 characters.", file=sys.stderr)
        return 1

    db = SessionLocal()
    try:
        exists = db.query(User).filter(User.email == args.email.strip().lower()).first() is not None
        action, user = upsert_dummy_user(
            db,
            args.email,
            password=args.password,
            name=args.name,
            payment_date=datetime.utcnow(),
            update_existing=args.update or exists,
        )
        pkg = db.query(Package).filter(Package.id == user.package_id).first()
        summary = admin_subscription_summary(user, pkg=pkg, subs=[])
        v_ok, _ = can_access_video_library(db, user)
        q_ok, _ = can_access_mock_test(db, user)

        print(f"{action.upper()} user id={user.id}")
        print(f"  email:    {user.email}")
        print(f"  password: {args.password}")
        print(f"  batch:    {user.subscription}")
        print(f"  package:  {pkg.name if pkg else user.package_id} (id={user.package_id})")
        print(f"  access:   status={summary.get('status')} until={summary.get('end_date')}")
        print(f"  video={v_ok} quiz={q_ok}")
        for opt in ("access_video_library_link", "access_quiz_link"):
            val = get_option_value(db, opt)
            print(f"  {opt}: allowed={subscription_allowed(val, BATCH)}")
        return 0
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
