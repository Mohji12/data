#!/usr/bin/env python3
"""
Close Batch 15 video/mock for standard users and enable completion certificates.

Extension users (2-month Topup Extension with active user_subscriptions) keep
video and mock test access until their extended window ends; certificates are
issued only after that.

Usage (from mock_test/backend):
  python scripts/setup_batch_15_post_course.py
  python scripts/setup_batch_15_post_course.py --dry-run
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from app.db import SessionLocal  # noqa: E402
from app.models import Option, User  # noqa: E402
from app.services.access import (  # noqa: E402
    batch_closure_option_key,
    can_access_certificate,
    can_access_mock_test,
    can_access_video_library,
    certificate_option_key,
    get_certificate_batch_settings,
    get_option_value,
    subscription_allowed,
)

BATCH_NAME = "Batch 15"
OFFICIAL_END = "2026-07-15"
CERT_LABEL = "Batch 15"
COURSE_LINE = "Online Master Classes in Critical Care Medicine"
PROGRAM_LINE = "Dr Harish's Master Classes in Critical Care Medicine"


def _split_csv(raw: str) -> list[str]:
    return [p.strip() for p in (raw or "").split(",") if p.strip()]


def _join_csv(parts: list[str]) -> str:
    return ",".join(parts)


def _upsert_option(db, option_name: str, option_value: str, *, dry_run: bool) -> bool:
    row = db.query(Option).filter(Option.option_name == option_name).first()
    current = (row.option_value or "").strip() if row else ""
    if current == option_value:
        return False
    if dry_run:
        print(f"  would set {option_name} = {option_value!r}")
        return True
    if row:
        row.option_value = option_value
    else:
        db.add(Option(option_name=option_name, option_value=option_value))
    return True


def _ensure_batch_in_option(db, option_name: str, batch_name: str, *, dry_run: bool) -> bool:
    current = get_option_value(db, option_name)
    if subscription_allowed(current, batch_name):
        return False
    parts = _split_csv(current)
    parts.append(batch_name)
    return _upsert_option(db, option_name, _join_csv(parts), dry_run=dry_run)


def main() -> int:
    parser = argparse.ArgumentParser(description="Configure Batch 15 post-course access rules.")
    parser.add_argument("--dry-run", action="store_true", help="Print changes without committing")
    args = parser.parse_args()

    db = SessionLocal()
    changed: list[str] = []
    try:
        closed_key = batch_closure_option_key("access_closed", BATCH_NAME)
        if closed_key and _upsert_option(db, closed_key, "1", dry_run=args.dry_run):
            changed.append(closed_key)

        base_key = f"extension_base_date::{BATCH_NAME.lower().replace(' ', '-')}"
        if _upsert_option(db, base_key, OFFICIAL_END, dry_run=args.dry_run):
            changed.append(base_key)

        cert_pairs = {
            certificate_option_key("enabled", BATCH_NAME): "1",
            certificate_option_key("batch_label", BATCH_NAME): CERT_LABEL,
            certificate_option_key("fixed_date", BATCH_NAME): OFFICIAL_END,
            certificate_option_key("course_line", BATCH_NAME): COURSE_LINE,
            certificate_option_key("program_line", BATCH_NAME): PROGRAM_LINE,
            certificate_option_key("show_date", BATCH_NAME): "1",
        }
        for key, value in cert_pairs.items():
            if key and _upsert_option(db, key, value, dry_run=args.dry_run):
                changed.append(key)

        if _upsert_option(db, "display_download_certificate", "1", dry_run=args.dry_run):
            changed.append("display_download_certificate")
        if _ensure_batch_in_option(db, "access_download_certificate", BATCH_NAME, dry_run=args.dry_run):
            changed.append("access_download_certificate")

        # Keep Batch 15 in allowlists; access.py gates video/mock via closure + extension logic.
        if _ensure_batch_in_option(db, "access_video_library_link", BATCH_NAME, dry_run=args.dry_run):
            changed.append("access_video_library_link")
        if _ensure_batch_in_option(db, "access_quiz_link", BATCH_NAME, dry_run=args.dry_run):
            changed.append("access_quiz_link")

        if args.dry_run:
            print(f"Dry run: {len(changed)} option(s) would change.")
            return 0

        if changed:
            db.commit()
            print(f"Updated {len(changed)} option(s): {', '.join(changed)}")
        else:
            print("No option changes needed (already configured).")

        print("Certificate settings:", get_certificate_batch_settings(db, BATCH_NAME))

        samples = (
            db.query(User)
            .filter(
                User.subscription == BATCH_NAME,
                User.payment_status == "Credit",
                User.approve == "1",
            )
            .limit(3)
            .all()
        )
        for sample in samples:
            video = can_access_video_library(db, sample)
            mock = can_access_mock_test(db, sample)
            cert = can_access_certificate(db, sample)
            print(
                f"Sample {sample.email}: video={video[0]}, mock={mock[0]}, certificate={cert[0]}"
            )
        if not samples:
            print("No approved paid Batch 15 users found for sample verification.")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
