"""Unlock module mock tests after all videos in the linked folder are watched."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session

from app.models import FolderMaster, QuizExam, User, Video, UserVideoProgress
from app.services.batch_match import find_in_set_sql
from app.services.video_progress import WATCHED_THRESHOLD_SECONDS

MODULE_EXAM_MAP_OPTION = "icu_id_module_exam_map"


def _load_folder_exam_map(db: Session) -> dict[int, int]:
    from app.services.access import get_option_value

    raw = (get_option_value(db, MODULE_EXAM_MAP_OPTION) or "").strip()
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    if not isinstance(data, dict):
        return {}
    out: dict[int, int] = {}
    for key, value in data.items():
        try:
            folder_id = int(key)
            exam_id = int(value)
        except (TypeError, ValueError):
            continue
        out[folder_id] = exam_id
    return out


def _exam_to_folder_map(db: Session) -> dict[int, int]:
    folder_exam = _load_folder_exam_map(db)
    return {exam_id: folder_id for folder_id, exam_id in folder_exam.items()}


def folder_id_for_exam(db: Session, exam_id: int) -> int | None:
    return _exam_to_folder_map(db).get(int(exam_id))


def exam_id_for_folder(db: Session, folder_id: int) -> int | None:
    return _load_folder_exam_map(db).get(int(folder_id))


def _video_ids_in_folder(db: Session, folder_id: int, subscription: str) -> list[int]:
    sub = (subscription or "").strip()
    if not sub:
        return []
    rows = (
        db.query(Video.id)
        .filter(
            Video.status == "1",
            find_in_set_sql(Video.batch, sub),
            find_in_set_sql(Video.folder, str(folder_id)),
        )
        .all()
    )
    return [int(row[0]) for row in rows]


def folder_video_completion(
    db: Session,
    user_id: int,
    folder_id: int,
    *,
    subscription: str | None = None,
) -> dict[str, Any]:
    """Return counts and whether every video in the folder is watched (10 min threshold)."""
    user = db.query(User).filter(User.id == user_id).first()
    sub = (subscription or (user.subscription if user else "") or "").strip()
    video_ids = _video_ids_in_folder(db, folder_id, sub)
    total = len(video_ids)
    if total == 0:
        return {
            "videos_total": 0,
            "videos_watched": 0,
            "complete": False,
            "reason": "No videos in this module yet.",
        }
    progress_rows = (
        db.query(UserVideoProgress.video_id, UserVideoProgress.watched_seconds)
        .filter(UserVideoProgress.user_id == user_id, UserVideoProgress.video_id.in_(video_ids))
        .all()
    )
    watched_by_id = {int(vid): int(seconds or 0) for vid, seconds in progress_rows}
    watched = sum(
        1 for vid in video_ids if watched_by_id.get(vid, 0) >= WATCHED_THRESHOLD_SECONDS
    )
    complete = watched >= total
    return {
        "videos_total": total,
        "videos_watched": watched,
        "complete": complete,
        "reason": None if complete else f"Watch all videos in this module ({watched}/{total} completed).",
    }


def exam_module_unlocked(db: Session, user: User, exam: QuizExam) -> tuple[bool, str | None, str | None]:
    """
    Returns (unlocked, hint_message, folder_name).
    Exams without a folder mapping stay unlocked (legacy batches).
    """
    folder_id = folder_id_for_exam(db, exam.id)
    if folder_id is None:
        return True, None, None
    folder = db.query(FolderMaster).filter(FolderMaster.id == folder_id).first()
    folder_name = (folder.name if folder else f"Module folder {folder_id}") or f"Module folder {folder_id}"
    stats = folder_video_completion(db, user.id, folder_id, subscription=user.subscription)
    if stats["complete"]:
        return True, None, folder_name
    hint = stats.get("reason") or f"Finish all videos in {folder_name} to unlock this test."
    return False, hint, folder_name
