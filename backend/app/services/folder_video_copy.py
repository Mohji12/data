from __future__ import annotations

from typing import Any, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import FolderMaster, Video


def _add_csv_token(csv_val: str | None, token: str) -> tuple[str, bool]:
    token = (token or "").strip()
    if not token:
        return (csv_val or "").strip(), False
    parts = [p.strip() for p in (csv_val or "").split(",") if p.strip()]
    if any(p == token for p in parts):
        return ",".join(parts), False
    parts.append(token)
    return ",".join(parts), True


def _subscription_in_csv(subscription: str | None, csv_column: str | None) -> bool:
    sub = (subscription or "").strip()
    if not sub:
        return False
    parts = [p.strip() for p in (csv_column or "").split(",") if p.strip()]
    sub_l = sub.lower()
    return any(p.lower() == sub_l for p in parts)


def _parse_batch_names(csv_column: str | None) -> list[str]:
    return [p.strip() for p in (csv_column or "").split(",") if p.strip()]


def _folders_for_batch(db: Session, batch_name: str) -> list[FolderMaster]:
    batch_name = (batch_name or "").strip()
    if not batch_name:
        return []
    rows = db.query(FolderMaster).order_by(FolderMaster.display_order.asc(), FolderMaster.id.asc()).all()
    return [f for f in rows if _subscription_in_csv(batch_name, f.batch)]


def _transform_folder_name(name: str, name_from: str, name_to: str, *, target_name_prefix: str = "") -> str:
    n = name or ""
    prefix = (target_name_prefix or "").strip()
    if prefix:
        return f"{prefix}{n}"
    if not name_from:
        return n
    return n.replace(name_from, name_to)


def _video_count_in_folder(db: Session, folder_id: int) -> int:
    return (
        db.query(func.count(Video.id))
        .filter(func.find_in_set(str(folder_id), func.coalesce(Video.folder, "")) > 0)
        .scalar()
        or 0
    )


def _videos_in_folder(db: Session, folder_id: int) -> list[Video]:
    return (
        db.query(Video)
        .filter(func.find_in_set(str(folder_id), func.coalesce(Video.folder, "")) > 0)
        .all()
    )


def copy_videos_between_folders(
    db: Session,
    *,
    source_folder_id: int,
    target_folder_id: int,
    add_batch_names: Optional[list[str]] = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    src = db.query(FolderMaster).filter(FolderMaster.id == source_folder_id).first()
    tgt = db.query(FolderMaster).filter(FolderMaster.id == target_folder_id).first()
    if not src:
        raise ValueError(f"Source folder id={source_folder_id} not found.")
    if not tgt:
        raise ValueError(f"Target folder id={target_folder_id} not found.")
    if src.id == tgt.id:
        raise ValueError("Source and target folder must be different.")

    batches = [b for b in (add_batch_names or []) if (b or "").strip()]
    videos = _videos_in_folder(db, source_folder_id)
    folder_updated = 0
    batch_updated = 0
    for v in videos:
        new_folder, fc = _add_csv_token(v.folder, str(target_folder_id))
        new_batch = v.batch
        bc = False
        for batch_name in batches:
            new_batch, b_one = _add_csv_token(new_batch, batch_name)
            bc = bc or b_one
        if fc:
            folder_updated += 1
        if bc:
            batch_updated += 1
        if not dry_run and (fc or bc):
            v.folder = new_folder
            v.batch = new_batch
            db.add(v)

    if not dry_run and (folder_updated or batch_updated):
        db.commit()

    return {
        "source_folder_id": src.id,
        "source_folder_name": src.name,
        "target_folder_id": tgt.id,
        "target_folder_name": tgt.name,
        "videos_matched": len(videos),
        "folder_updated": folder_updated,
        "batch_updated": batch_updated,
        "dry_run": dry_run,
    }


def preview_bulk_copy_by_batch(
    db: Session,
    *,
    source_batch: str,
    target_batch: str,
    name_from: str = "B15_",
    name_to: str = "B16_",
    target_name_prefix: str = "",
) -> dict[str, Any]:
    source_batch = (source_batch or "").strip()
    target_batch = (target_batch or "").strip()
    source_folders = _folders_for_batch(db, source_batch)
    target_folders = _folders_for_batch(db, target_batch)
    target_by_name = {(f.name or "").strip().casefold(): f for f in target_folders}

    def _resolve_target(expected_name: str) -> FolderMaster | None:
        key = expected_name.strip().casefold()
        if not key:
            return None
        hit = target_by_name.get(key)
        if hit:
            return hit
        return _find_folder_by_name_ci(db, expected_name)

    pairs: list[dict[str, Any]] = []
    unmatched_sources: list[dict[str, Any]] = []
    skipped_same_folder: list[dict[str, Any]] = []

    for src in source_folders:
        expected_name = _transform_folder_name(
            src.name or "", name_from, name_to, target_name_prefix=target_name_prefix
        ).strip()
        tgt = _resolve_target(expected_name)
        video_count = _video_count_in_folder(db, src.id)
        if tgt and tgt.id == src.id:
            skipped_same_folder.append(
                {
                    "folder_id": src.id,
                    "folder_name": src.name,
                    "expected_target_name": expected_name,
                    "reason": (
                        "Source and target are the same folder. Use separate B16 folders "
                        "(do not add both batches on one B15-named folder), or fix batch/replace settings."
                    ),
                }
            )
        elif tgt:
            already = _video_count_in_folder(db, tgt.id)
            pairs.append(
                {
                    "source_folder_id": src.id,
                    "source_folder_name": src.name,
                    "target_folder_id": tgt.id,
                    "target_folder_name": tgt.name,
                    "expected_target_name": expected_name,
                    "source_video_count": video_count,
                    "target_video_count_before": already,
                }
            )
        else:
            unmatched_sources.append(
                {
                    "source_folder_id": src.id,
                    "source_folder_name": src.name,
                    "expected_target_name": expected_name,
                    "source_video_count": video_count,
                }
            )

    matched_target_ids = {p["target_folder_id"] for p in pairs}
    unmatched_targets = [
        {"target_folder_id": f.id, "target_folder_name": f.name}
        for f in target_folders
        if f.id not in matched_target_ids
    ]

    return {
        "source_batch": source_batch,
        "target_batch": target_batch,
        "name_from": name_from,
        "name_to": name_to,
        "target_name_prefix": target_name_prefix,
        "pairs": pairs,
        "unmatched_sources": unmatched_sources,
        "unmatched_targets": unmatched_targets,
        "skipped_same_folder": skipped_same_folder,
        "pair_count": len(pairs),
    }


def bulk_copy_videos_by_batch(
    db: Session,
    *,
    source_batch: str,
    target_batch: str,
    name_from: str = "B15_",
    name_to: str = "B16_",
    target_name_prefix: str = "",
    add_target_batch_access: bool = True,
    dry_run: bool = False,
) -> dict[str, Any]:
    preview = preview_bulk_copy_by_batch(
        db,
        source_batch=source_batch,
        target_batch=target_batch,
        name_from=name_from,
        name_to=name_to,
        target_name_prefix=target_name_prefix,
    )
    tgt_folder = {f.id: f for f in _folders_for_batch(db, target_batch)}

    pair_results: list[dict[str, Any]] = []
    total_folder_updated = 0
    total_batch_updated = 0
    total_videos = 0

    skipped_results: list[dict[str, Any]] = []

    for pair in preview["pairs"]:
        if pair["source_folder_id"] == pair["target_folder_id"]:
            skipped_results.append({**pair, "skipped": True, "reason": "same_folder"})
            continue
        batch_names: list[str] = []
        if add_target_batch_access:
            tgt = tgt_folder.get(pair["target_folder_id"])
            if tgt:
                batch_names = _parse_batch_names(tgt.batch)
        try:
            result = copy_videos_between_folders(
                db,
                source_folder_id=pair["source_folder_id"],
                target_folder_id=pair["target_folder_id"],
                add_batch_names=batch_names,
                dry_run=dry_run,
            )
        except ValueError as e:
            skipped_results.append({**pair, "skipped": True, "reason": str(e)})
            continue
        pair_results.append(result)
        total_folder_updated += result["folder_updated"]
        total_batch_updated += result["batch_updated"]
        total_videos += result["videos_matched"]

    return {
        **preview,
        "dry_run": dry_run,
        "add_target_batch_access": add_target_batch_access,
        "results": pair_results,
        "skipped_results": skipped_results,
        "totals": {
            "pairs_processed": len(pair_results),
            "pairs_skipped": len(skipped_results) + len(preview.get("skipped_same_folder") or []),
            "videos_matched": total_videos,
            "folder_updated": total_folder_updated,
            "batch_updated": total_batch_updated,
        },
    }


def _find_folder_by_name_ci(db: Session, name: str) -> FolderMaster | None:
    key = (name or "").strip().casefold()
    if not key:
        return None
    for row in db.query(FolderMaster).all():
        if (row.name or "").strip().casefold() == key:
            return row
    return None


def preview_clone_batch_folders(
    db: Session,
    *,
    source_batch: str,
    target_batch: str,
    name_from: str = "B15_",
    name_to: str = "B16_",
    target_name_prefix: str = "",
) -> dict[str, Any]:
    """Preview creating missing target folders + linking videos from source batch."""
    base = preview_bulk_copy_by_batch(
        db,
        source_batch=source_batch,
        target_batch=target_batch,
        name_from=name_from,
        name_to=name_to,
        target_name_prefix=target_name_prefix,
    )
    source_by_id = {f.id: f for f in _folders_for_batch(db, source_batch)}
    folders_to_create: list[dict[str, Any]] = []
    name_collisions: list[dict[str, Any]] = []

    for item in base["unmatched_sources"]:
        expected = (item.get("expected_target_name") or "").strip()
        src = source_by_id.get(item["source_folder_id"])
        if not expected or not src:
            continue
        existing = _find_folder_by_name_ci(db, expected)
        if existing:
            if not _subscription_in_csv(target_batch, existing.batch):
                existing.batch, _ = _add_csv_token(existing.batch, target_batch)
                db.add(existing)
                name_collisions.append(
                    {
                        "folder_id": existing.id,
                        "folder_name": existing.name,
                        "expected_target_name": expected,
                        "batch_assigned": target_batch,
                        "reason": f"Existing folder updated with batch {target_batch!r}.",
                    }
                )
            continue
        folders_to_create.append(
            {
                "source_folder_id": src.id,
                "source_folder_name": src.name,
                "target_folder_name": expected,
                "display_order": src.display_order or 0,
                "source_video_count": item.get("source_video_count", 0),
            }
        )

    return {
        **base,
        "folders_to_create": folders_to_create,
        "folders_to_create_count": len(folders_to_create),
        "name_collisions": name_collisions,
    }


def clone_batch_folders_and_videos(
    db: Session,
    *,
    source_batch: str,
    target_batch: str,
    name_from: str = "B15_",
    name_to: str = "B16_",
    target_name_prefix: str = "",
    create_missing_folders: bool = True,
    copy_videos: bool = True,
    add_target_batch_access: bool = True,
    dry_run: bool = False,
) -> dict[str, Any]:
    """
    Clone source batch folders into target batch, then link all videos.
    """
    preview = preview_clone_batch_folders(
        db,
        source_batch=source_batch,
        target_batch=target_batch,
        name_from=name_from,
        name_to=name_to,
        target_name_prefix=target_name_prefix,
    )
    created_folders: list[dict[str, Any]] = []

    if create_missing_folders:
        source_by_id = {f.id: f for f in _folders_for_batch(db, source_batch)}
        for item in preview["folders_to_create"]:
            expected = item["target_folder_name"]
            src = source_by_id.get(item["source_folder_id"])
            if not src:
                continue
            if dry_run:
                created_folders.append({**item, "dry_run": True})
                continue
            row = FolderMaster(
                name=expected,
                status=src.status or "1",
                batch=target_batch.strip(),
                display_order=src.display_order or 0,
            )
            db.add(row)
            db.flush()
            created_folders.append(
                {
                    "source_folder_id": src.id,
                    "source_folder_name": src.name,
                    "target_folder_id": row.id,
                    "target_folder_name": row.name,
                }
            )
        if not dry_run and (created_folders or preview.get("name_collisions")):
            db.commit()

    video_result: dict[str, Any] | None = None
    if copy_videos:
        video_result = bulk_copy_videos_by_batch(
            db,
            source_batch=source_batch,
            target_batch=target_batch,
            name_from=name_from,
            name_to=name_to,
            target_name_prefix=target_name_prefix,
            add_target_batch_access=add_target_batch_access,
            dry_run=dry_run,
        )

    return {
        "source_batch": source_batch,
        "target_batch": target_batch,
        "name_from": name_from,
        "name_to": name_to,
        "target_name_prefix": target_name_prefix,
        "dry_run": dry_run,
        "folders_created": len(created_folders),
        "created_folders": created_folders,
        "folders_to_create_count": preview["folders_to_create_count"],
        "name_collisions": preview.get("name_collisions") or [],
        "video_copy": video_result,
    }
