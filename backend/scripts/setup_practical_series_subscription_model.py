#!/usr/bin/env python3
"""
Enable video/mock folders for PRACTICAL SERIES-SUBSCRIPTION MODEL users.

Usage (from mock_test/backend):
  python scripts/setup_practical_series_subscription_model.py
  python scripts/setup_practical_series_subscription_model.py --dry-run
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from sqlalchemy import func, text  # noqa: E402

from app.db import SessionLocal  # noqa: E402
from app.models import FolderMaster, Option, User  # noqa: E402
from app.services.access import (  # noqa: E402
    can_access_mock_test,
    can_access_video_library,
    get_option_value,
    subscription_allowed,
)

BATCH_NAME = "PRACTICAL SERIES-SUBSCRIPTION MODEL"
PS3_FOLDER_MIN = 513
PS3_FOLDER_MAX = 537


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


def _ensure_folders_for_batch(db, *, dry_run: bool) -> int:
    folders = (
        db.query(FolderMaster)
        .filter(
            FolderMaster.status == "1",
            FolderMaster.id >= PS3_FOLDER_MIN,
            FolderMaster.id <= PS3_FOLDER_MAX,
            func.find_in_set("PRACTICAL SERIES BATCH 3", func.coalesce(FolderMaster.batch, "")) > 0,
        )
        .order_by(FolderMaster.id.asc())
        .all()
    )
    updated = 0
    for folder in folders:
        parts = _split_csv(folder.batch)
        if any(p.lower() == BATCH_NAME.lower() for p in parts):
            continue
        new_batch = _join_csv(parts + [BATCH_NAME])
        if dry_run:
            print(f"  would set folder_master.id={folder.id} batch -> {new_batch!r}")
        else:
            folder.batch = new_batch
        updated += 1
    return updated


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Enable video library folders for PRACTICAL SERIES-SUBSCRIPTION MODEL."
    )
    parser.add_argument("--dry-run", action="store_true", help="Print changes without committing")
    args = parser.parse_args()

    db = SessionLocal()
    changed: list[str] = []
    try:
        if _ensure_batch_in_option(db, "access_video_library_link", BATCH_NAME, dry_run=args.dry_run):
            changed.append("access_video_library_link")
        if _ensure_batch_in_option(db, "access_quiz_link", BATCH_NAME, dry_run=args.dry_run):
            changed.append("access_quiz_link")

        folder_updates = _ensure_folders_for_batch(db, dry_run=args.dry_run)
        if folder_updates:
            changed.append(f"folder_master({folder_updates})")

        if args.dry_run:
            print(f"Dry run: {len(changed)} change group(s) would apply.")
            return 0

        if changed:
            db.commit()
            # Clear option cache after commit.
            from app.services import access as access_mod

            access_mod._option_cache.clear()
            print(f"Updated: {', '.join(changed)}")
        else:
            print("No changes needed (already configured).")

        folder_count = db.execute(
            text(
                "SELECT COUNT(*) FROM folder_master "
                "WHERE status='1' AND FIND_IN_SET(:batch, COALESCE(batch,'')) > 0"
            ),
            {"batch": BATCH_NAME},
        ).scalar()
        print(f"Folders for {BATCH_NAME}: {folder_count}")

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
            print(f"Sample {sample.email}: video={video}, mock={mock}")
        if not samples:
            print("No approved paid users found for sample verification.")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
