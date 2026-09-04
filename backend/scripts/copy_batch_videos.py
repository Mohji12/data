"""
Copy videos from one batch into another (folders + video.batch/folder links + access options).

Usage:
  python scripts/copy_batch_videos.py "CP 8" "CP 10"
  python scripts/copy_batch_videos.py "CP 10" "COMPREHENSIVE COURSE 2-SUBSCRIPTION MODEL"
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models import FolderMaster, Option, Video
from app.services.folder_video_copy import (
    _add_csv_token,
    _folders_for_batch,
    _subscription_in_csv,
    _video_count_in_folder,
)


def _norm_name(name: str | None) -> str:
    return " ".join((name or "").replace("\r", " ").replace("\n", " ").split()).casefold()


def _ensure_access_option(db: Session, option_name: str, batch: str) -> bool:
    row = db.query(Option).filter(Option.option_name == option_name).first()
    if not row:
        return False
    new_val, changed = _add_csv_token(row.option_value, batch)
    if changed:
        row.option_value = new_val
        db.add(row)
    return changed


def copy_batch(db: Session, source_batch: str, target_batch: str) -> dict:
    source_folders = _folders_for_batch(db, source_batch)
    if not source_folders:
        raise SystemExit(f"No folders found for source batch {source_batch!r}")

    existing_target = _folders_for_batch(db, target_batch)
    name_to_target = {_norm_name(f.name): f for f in existing_target}

    created: list[dict] = []
    source_to_target: dict[int, FolderMaster] = {}

    for src in source_folders:
        key = _norm_name(src.name)
        tgt = name_to_target.get(key)
        if tgt and _subscription_in_csv(target_batch, tgt.batch):
            source_to_target[src.id] = tgt
            continue
        row = FolderMaster(
            name=src.name,
            status=src.status or "1",
            batch=target_batch,
            display_order=src.display_order or 0,
        )
        db.add(row)
        db.flush()
        source_to_target[src.id] = row
        name_to_target[key] = row
        created.append({"source_folder_id": src.id, "target_folder_id": row.id, "name": row.name})

    db.commit()

    all_folders = db.query(FolderMaster).all()
    old_id_to_target: dict[int, FolderMaster] = {}
    for f in all_folders:
        key = _norm_name(f.name)
        tgt = name_to_target.get(key)
        if tgt:
            old_id_to_target[f.id] = tgt
    for sid, tgt in source_to_target.items():
        old_id_to_target[sid] = tgt

    videos = [
        v
        for v in db.query(Video).filter(Video.batch.isnot(None)).all()
        if _subscription_in_csv(source_batch, v.batch)
    ]

    batch_updated = 0
    folder_updated = 0
    for v in videos:
        new_batch, bchg = _add_csv_token(v.batch, target_batch)
        new_folder = v.folder
        fchg = False
        for part in [p.strip() for p in (v.folder or "").split(",") if p.strip()]:
            if not part.isdigit():
                continue
            fid = int(part)
            tgt = old_id_to_target.get(fid) or source_to_target.get(fid)
            if not tgt:
                continue
            new_folder, one = _add_csv_token(new_folder, str(tgt.id))
            fchg = fchg or one
        if bchg:
            batch_updated += 1
        if fchg:
            folder_updated += 1
        if bchg or fchg:
            v.batch = new_batch
            v.folder = new_folder
            db.add(v)

    access_video = _ensure_access_option(db, "access_video_library_link", target_batch)
    access_quiz = _ensure_access_option(db, "access_quiz_link", target_batch)
    db.commit()

    verify = [
        {"id": f.id, "name": f.name, "videos": _video_count_in_folder(db, f.id)}
        for f in _folders_for_batch(db, target_batch)
    ]
    video_count = db.execute(
        text("SELECT COUNT(*) FROM videos WHERE FIND_IN_SET(:b, COALESCE(batch,'')) > 0"),
        {"b": target_batch},
    ).scalar()

    return {
        "source_batch": source_batch,
        "target_batch": target_batch,
        "folders_created": len(created),
        "created_folders": created,
        "source_videos": len(videos),
        "videos_batch_updated": batch_updated,
        "videos_folder_updated": folder_updated,
        "access_video_library_link_updated": access_video,
        "access_quiz_link_updated": access_quiz,
        "target_video_count": video_count,
        "target_folders": verify,
    }


def main() -> int:
    if len(sys.argv) != 3:
        print(__doc__)
        return 1
    source_batch = sys.argv[1].strip()
    target_batch = sys.argv[2].strip()
    db = SessionLocal()
    try:
        result = copy_batch(db, source_batch, target_batch)
        print(json.dumps(result, indent=2, default=str))
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
