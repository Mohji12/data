#!/usr/bin/env python3
"""
Assign videos from one folder to another (CLI wrapper).

Usage (from mock_test/backend):
  python scripts/copy_videos_to_folder.py --source-folder-id 368 --target-folder-id 493 --dry-run
  python scripts/copy_videos_to_folder.py --source-folder-id 368 --target-folder-id 493 --add-batch "BATCH 16-MCCM"
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from app.db import SessionLocal  # noqa: E402
from app.services.folder_video_copy import copy_videos_between_folders  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Copy folder assignment from source folder to target folder.")
    parser.add_argument("--source-folder-id", type=int, required=True)
    parser.add_argument("--target-folder-id", type=int, required=True)
    parser.add_argument(
        "--add-batch",
        action="append",
        default=[],
        help="Batch/subscription name to append on each matched video (repeatable)",
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        result = copy_videos_between_folders(
            db,
            source_folder_id=args.source_folder_id,
            target_folder_id=args.target_folder_id,
            add_batch_names=args.add_batch or None,
            dry_run=args.dry_run,
        )
        print(json.dumps(result, indent=2))
        return 0
    except ValueError as e:
        print(str(e), file=sys.stderr)
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
