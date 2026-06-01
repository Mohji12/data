#!/usr/bin/env python3
"""
Clone video folders from one batch to another (create target folders + link videos).

Usage (from mock_test/backend):
  python scripts/copy_batch_videos.py --dry-run
  python scripts/copy_batch_videos.py --source "CCM Batch 2" --target "PRACTICAL SERIES BATCH 3" --prefix "PS3 - "
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
from app.services.folder_video_copy import clone_batch_folders_and_videos, preview_clone_batch_folders  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Clone folders + videos from source batch to target batch.")
    parser.add_argument("--source", default="CCM Batch 2")
    parser.add_argument("--target", default="PRACTICAL SERIES BATCH 3")
    parser.add_argument("--prefix", default="PS3 - ", help="Prefix for new target folder names")
    parser.add_argument("--name-from", default="", help="Optional substring replace in folder names")
    parser.add_argument("--name-to", default="", help="Replacement for --name-from")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--folders-only", action="store_true", help="Create folders without linking videos")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        if args.dry_run:
            out = preview_clone_batch_folders(
                db,
                source_batch=args.source,
                target_batch=args.target,
                name_from=args.name_from,
                name_to=args.name_to,
                target_name_prefix=args.prefix,
            )
        else:
            out = clone_batch_folders_and_videos(
                db,
                source_batch=args.source,
                target_batch=args.target,
                name_from=args.name_from,
                name_to=args.name_to,
                target_name_prefix=args.prefix,
                create_missing_folders=True,
                copy_videos=not args.folders_only,
                add_target_batch_access=True,
                dry_run=False,
            )
        print(json.dumps(out, indent=2, default=str))
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
