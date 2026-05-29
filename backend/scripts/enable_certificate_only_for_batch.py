#!/usr/bin/env python3
"""
Enable certificate-only access for a batch (login + download certificate only).

Usage (from mock_test/backend):
  python scripts/enable_certificate_only_for_batch.py "Batch 14"
  python scripts/enable_certificate_only_for_batch.py "Batch 14" --certificate-date 2025-12-15
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from app.db import SessionLocal  # noqa: E402
from app.models import Option  # noqa: E402
from app.services.access import (  # noqa: E402
    certificate_option_key,
    get_certificate_batch_settings,
    get_option_value,
    is_certificate_only_user,
    can_access_certificate,
    subscription_allowed,
)
from app.models import User  # noqa: E402


def _split_csv(raw: str) -> list[str]:
    return [p.strip() for p in (raw or "").split(",") if p.strip()]


def _join_csv(parts: list[str]) -> str:
    return ",".join(parts)


def _remove_batch(parts: list[str], batch_name: str) -> list[str]:
    target = batch_name.strip().lower()
    return [p for p in parts if p.strip().lower() != target]


def _upsert_option(db, option_name: str, option_value: str) -> None:
    row = db.query(Option).filter(Option.option_name == option_name).first()
    if row:
        row.option_value = option_value
    else:
        db.add(Option(option_name=option_name, option_value=option_value))


def _ensure_batch_in_option(db, option_name: str, batch_name: str) -> bool:
    current = get_option_value(db, option_name)
    parts = _split_csv(current)
    if subscription_allowed(current, batch_name):
        return False
    parts.append(batch_name)
    _upsert_option(db, option_name, _join_csv(parts))
    return True


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Enable certificate-only access for a batch (login + certificate download)."
    )
    parser.add_argument("batch_name", help='Exact subscription name, e.g. "Batch 14"')
    parser.add_argument(
        "--certificate-date",
        default="",
        help="Optional fixed certificate date (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--certificate-label",
        default="",
        help="Optional certificate batch label (defaults to batch name)",
    )
    args = parser.parse_args()
    batch_name = args.batch_name.strip()
    if not batch_name:
        print("Error: batch_name is required.", file=sys.stderr)
        return 1

    db = SessionLocal()
    try:
        changed: list[str] = []

        if _ensure_batch_in_option(db, "access_download_certificate", batch_name):
            changed.append("access_download_certificate")
        _upsert_option(db, "display_download_certificate", "1")
        changed.append("display_download_certificate=1")

        if _ensure_batch_in_option(db, "certificate_only_access", batch_name):
            changed.append("certificate_only_access")

        for opt in ("access_video_library_link", "access_quiz_link"):
            current = get_option_value(db, opt)
            parts = _remove_batch(_split_csv(current), batch_name)
            if len(parts) != len(_split_csv(current)):
                _upsert_option(db, opt, _join_csv(parts))
                changed.append(f"removed from {opt}")

        enabled_key = certificate_option_key("enabled", batch_name)
        label_key = certificate_option_key("batch_label", batch_name)
        date_key = certificate_option_key("fixed_date", batch_name)
        label = (args.certificate_label or batch_name).strip()
        date_val = (args.certificate_date or "").strip()
        if enabled_key and label_key and date_key:
            _upsert_option(db, enabled_key, "1")
            _upsert_option(db, label_key, label)
            if date_val:
                _upsert_option(db, date_key, date_val)
            changed.append("per-batch certificate settings")

        db.commit()

        sample = (
            db.query(User)
            .filter(User.subscription == batch_name, User.payment_status == "Credit", User.approve == "1")
            .first()
        )
        print(f"Configured certificate-only access for {batch_name!r}.")
        if changed:
            print("Updates:", ", ".join(changed))
        print("Batch certificate settings:", get_certificate_batch_settings(db, batch_name))
        if sample:
            print(
                f"Sample user {sample.email}: certificate_only={is_certificate_only_user(db, sample)}, "
                f"can_download={can_access_certificate(db, sample)}"
            )
        else:
            print("No approved paid user found for verification sample.")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
