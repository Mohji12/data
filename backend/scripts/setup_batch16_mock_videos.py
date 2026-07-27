"""Create BATCH 16 mock discussion folders (1–10) and link videos from Batch 15."""
from __future__ import annotations

import json
import sys

from app.db import SessionLocal
from app.services.folder_video_copy import (
    _folders_for_batch,
    _subscription_in_csv,
    _video_count_in_folder,
    clone_batch_folders_and_videos,
)

SOURCE_BATCH = "Batch 15"
TARGET_BATCH = "BATCH 16-MCCM"
NAME_FROM = "BATCH 15_"
NAME_TO = "BATCH 16_"


def main() -> int:
    db = SessionLocal()
    try:
        result = clone_batch_folders_and_videos(
            db,
            source_batch=SOURCE_BATCH,
            target_batch=TARGET_BATCH,
            name_from=NAME_FROM,
            name_to=NAME_TO,
            create_missing_folders=True,
            copy_videos=True,
            add_target_batch_access=True,
            dry_run=False,
        )
        print(json.dumps(
            {
                "folders_created": result.get("folders_created"),
                "created_folders": result.get("created_folders"),
                "video_totals": (result.get("video_copy") or {}).get("totals"),
            },
            indent=2,
            default=str,
        ))

        print("\n=== Verify BATCH 16-MCCM mock folders ===")
        for f in _folders_for_batch(db, TARGET_BATCH):
            if "MOCK TEST" not in (f.name or "").upper():
                continue
            print(f"  id={f.id} name={f.name!r} videos={_video_count_in_folder(db, f.id)}")

        # Also ensure access option includes target batch (informational)
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
