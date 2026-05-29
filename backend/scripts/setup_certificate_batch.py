#!/usr/bin/env python3
"""
Initialize batch_master + certificate options so admin can edit certificate content.

Usage (from mock_test/backend):
  python scripts/setup_certificate_batch.py "Batch 14"
  python scripts/setup_certificate_batch.py "Batch 14" --certificate-only
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from app.db import SessionLocal  # noqa: E402
from app.models import BatchMaster, Option  # noqa: E402
from app.services.access import (  # noqa: E402
    certificate_option_key,
    get_certificate_batch_settings,
    get_option_value,
    subscription_allowed,
)

DEFAULT_COURSE = "has completed MASTER CLASSES IN CRITICAL CARE MEDICINE"
DEFAULT_PROGRAM = (
    "An online education & training program offered by Dr. Harish Mallapura Maheshwarappa"
)
DEFAULT_NAME_SIZE = "20"


def _split_csv(raw: str) -> list[str]:
    return [p.strip() for p in (raw or "").split(",") if p.strip()]


def _join_csv(parts: list[str]) -> str:
    return ",".join(parts)


def _upsert_option(db, option_name: str, option_value: str) -> None:
    row = db.query(Option).filter(Option.option_name == option_name).first()
    if row:
        row.option_value = option_value
    else:
        db.add(Option(option_name=option_name, option_value=option_value))


def _ensure_batch_in_option(db, option_name: str, batch_name: str) -> bool:
    current = get_option_value(db, option_name)
    if subscription_allowed(current, batch_name):
        return False
    parts = _split_csv(current)
    parts.append(batch_name)
    _upsert_option(db, option_name, _join_csv(parts))
    return True


def _ensure_batch_master(db, batch_name: str) -> BatchMaster:
    row = db.query(BatchMaster).filter(BatchMaster.name == batch_name).first()
    if row:
        return row
    row = BatchMaster(name=batch_name, status="1", display_order=0)
    db.add(row)
    db.flush()
    return row


def main() -> int:
    parser = argparse.ArgumentParser(description="Set up certificate admin data for a batch.")
    parser.add_argument("batch_name", help='Exact batch name, e.g. "Batch 14"')
    parser.add_argument(
        "--batch-label",
        default="",
        help="Certificate batch line (default: Batch 14 - July to December 2025 for Batch 14)",
    )
    parser.add_argument("--certificate-only", action="store_true", help="Certificate-only login access")
    parser.add_argument("--keep-inactive", action="store_true", help="Do not change batch_master.status")
    args = parser.parse_args()
    batch_name = args.batch_name.strip()
    if not batch_name:
        print("Error: batch_name is required.", file=sys.stderr)
        return 1

    label = (args.batch_label or "").strip()
    if not label and batch_name.lower() == "batch 14":
        label = "Batch 14 - July to December 2025"
    if not label:
        label = batch_name

    db = SessionLocal()
    try:
        batch = _ensure_batch_master(db, batch_name)
        if not args.keep_inactive and str(batch.status or "").strip() != "1":
            batch.status = "1"
            db.add(batch)

        _upsert_option(db, "display_download_certificate", "1")
        _ensure_batch_in_option(db, "access_download_certificate", batch_name)

        if args.certificate_only:
            _ensure_batch_in_option(db, "certificate_only_access", batch_name)

        keys = {
            "enabled": "1",
            "batch_label": label,
            "fixed_date": "",
            "course_line": DEFAULT_COURSE,
            "program_line": DEFAULT_PROGRAM,
            "show_date": "0",
            "name_size": DEFAULT_NAME_SIZE,
        }
        for kind, value in keys.items():
            opt_key = certificate_option_key(kind, batch_name)
            if opt_key:
                _upsert_option(db, opt_key, value)

        db.commit()
        print(f"Certificate admin data ready for {batch_name!r} (batch_master id={batch.id}, status={batch.status}).")
        print("Settings:", get_certificate_batch_settings(db, batch_name))
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
