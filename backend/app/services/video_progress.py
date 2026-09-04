"""Video watch-time accumulation and dashboard KPI helpers."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import FolderMaster, QuizExam, User, UserExam, UserVideoProgress, Video
from app.services.batch_match import find_in_set_sql

# A video counts as "watched" once cumulative play time reaches this threshold.
WATCHED_THRESHOLD_SECONDS = 600
# Reject oversized heartbeat deltas (client sends ~15s; allow small clock skew).
MAX_DELTA_SECONDS = 30


def clamp_delta_seconds(delta: float | int | None) -> int:
    if delta is None:
        return 0
    try:
        value = int(round(float(delta)))
    except (TypeError, ValueError):
        return 0
    if value < 0:
        return 0
    return min(value, MAX_DELTA_SECONDS)


def is_video_watched(watched_seconds: int | None, *, threshold: int = WATCHED_THRESHOLD_SECONDS) -> bool:
    return int(watched_seconds or 0) >= threshold


def hours_from_seconds(total_seconds: int | None) -> float:
    secs = max(0, int(total_seconds or 0))
    return round(secs / 3600.0, 1)


def watched_minutes_from_seconds(seconds: int | None) -> float:
    return round(max(0, int(seconds or 0)) / 60.0, 1)


def folder_remaining(total: int, watched: int) -> int:
    return max(0, int(total) - int(watched))


def _parse_folder_ids(folder_csv: str | None) -> list[int]:
    ids: list[int] = []
    for part in str(folder_csv or "").split(","):
        part = part.strip()
        if not part:
            continue
        try:
            ids.append(int(part))
        except ValueError:
            continue
    return ids


def summarize_admin_video_progress(
    videos: list[dict],
    *,
    threshold: int = WATCHED_THRESHOLD_SECONDS,
) -> dict:
    """Pure summary over per-video progress dicts (each needs watched_seconds)."""
    total_seconds = 0
    with_progress = 0
    watched = 0
    for v in videos:
        secs = int(v.get("watched_seconds") or 0)
        if secs > 0:
            with_progress += 1
        if is_video_watched(secs, threshold=threshold):
            watched += 1
        total_seconds += max(0, secs)
    return {
        "videos_with_progress": with_progress,
        "videos_watched": watched,
        "total_watched_seconds": total_seconds,
        "hours_spent": hours_from_seconds(total_seconds),
        "watched_threshold_seconds": threshold,
    }


def build_admin_user_video_analytics(db: Session, user_id: int) -> dict:
    """Per-student video progress for admin detail (all progress rows, not subscription-filtered)."""
    pairs = (
        db.query(UserVideoProgress, Video)
        .outerjoin(Video, Video.id == UserVideoProgress.video_id)
        .filter(UserVideoProgress.user_id == int(user_id))
        .all()
    )

    folder_ids: set[int] = set()
    for _prog, video in pairs:
        if video is not None:
            folder_ids.update(_parse_folder_ids(video.folder))

    folder_names: dict[int, str] = {}
    if folder_ids:
        for fm in db.query(FolderMaster).filter(FolderMaster.id.in_(list(folder_ids))).all():
            folder_names[int(fm.id)] = (fm.name or "").strip() or f"Folder {fm.id}"

    videos: list[dict] = []
    for prog, video in pairs:
        secs = int(prog.watched_seconds or 0)
        fids = _parse_folder_ids(video.folder if video else None)
        folder_label = ", ".join(
            folder_names.get(fid, str(fid)) for fid in fids
        ) if fids else ""
        videos.append(
            {
                "video_id": int(prog.video_id),
                "title": (video.title if video else None) or f"Video #{prog.video_id}",
                "folder": folder_label or None,
                "batch": (video.batch if video else None) or None,
                "video_status": (video.status if video else None) or None,
                "watched_seconds": secs,
                "watched_minutes": watched_minutes_from_seconds(secs),
                "is_watched": is_video_watched(secs),
                "last_position_seconds": prog.last_position_seconds,
                "updated_at": prog.updated_at.isoformat() if prog.updated_at else None,
            }
        )

    videos.sort(key=lambda v: (not v["is_watched"], -int(v["watched_seconds"]), str(v["title"]).lower()))
    summary = summarize_admin_video_progress(videos)
    return {**summary, "videos": videos}


def upsert_watch_progress(
    db: Session,
    *,
    user_id: int,
    video_id: int,
    delta_seconds: float | int | None,
    position_seconds: float | int | None = None,
) -> UserVideoProgress:
    delta = clamp_delta_seconds(delta_seconds)
    row = (
        db.query(UserVideoProgress)
        .filter(
            UserVideoProgress.user_id == user_id,
            UserVideoProgress.video_id == video_id,
        )
        .first()
    )
    now = datetime.utcnow()
    if row is None:
        row = UserVideoProgress(
            user_id=user_id,
            video_id=video_id,
            watched_seconds=delta,
            last_position_seconds=float(position_seconds) if position_seconds is not None else None,
            created_at=now,
            updated_at=now,
        )
        db.add(row)
    else:
        row.watched_seconds = int(row.watched_seconds or 0) + delta
        if position_seconds is not None:
            try:
                row.last_position_seconds = float(position_seconds)
            except (TypeError, ValueError):
                pass
        row.updated_at = now
    db.commit()
    db.refresh(row)
    return row


def _accessible_video_filters(subscription: str):
    return [
        Video.status == "1",
        find_in_set_sql(Video.batch, subscription),
    ]


def count_videos_watched(
    db: Session,
    *,
    user_id: int,
    subscription: str,
    folder_id: Optional[int] = None,
    threshold: int = WATCHED_THRESHOLD_SECONDS,
) -> int:
    sub = (subscription or "").strip()
    if not sub:
        return 0
    filters = [
        UserVideoProgress.user_id == user_id,
        UserVideoProgress.watched_seconds >= threshold,
        *_accessible_video_filters(sub),
    ]
    if folder_id is not None:
        filters.append(find_in_set_sql(Video.folder, str(folder_id)))
    return (
        db.query(func.count(UserVideoProgress.id))
        .join(Video, Video.id == UserVideoProgress.video_id)
        .filter(*filters)
        .scalar()
        or 0
    )


def sum_watched_seconds(db: Session, *, user_id: int, subscription: str) -> int:
    sub = (subscription or "").strip()
    if not sub:
        return 0
    total = (
        db.query(func.coalesce(func.sum(UserVideoProgress.watched_seconds), 0))
        .join(Video, Video.id == UserVideoProgress.video_id)
        .filter(
            UserVideoProgress.user_id == user_id,
            *_accessible_video_filters(sub),
        )
        .scalar()
    )
    return int(total or 0)


def count_folder_videos(db: Session, *, subscription: str, folder_id: int) -> int:
    sub = (subscription or "").strip()
    if not sub:
        return 0
    return (
        db.query(func.count(Video.id))
        .filter(
            *_accessible_video_filters(sub),
            find_in_set_sql(Video.folder, str(folder_id)),
        )
        .scalar()
        or 0
    )


def quiz_kpi_for_user(db: Session, *, user_id: int) -> tuple[Optional[int], int]:
    """Return (avg_quiz_score_percent or None, tests_done)."""
    rows = (
        db.query(UserExam.marks, QuizExam.total_questions)
        .join(QuizExam, QuizExam.id == UserExam.exam_id)
        .filter(UserExam.user_id == user_id, UserExam.is_finish_exam == "1")
        .all()
    )
    tests_done = len(rows)
    if not tests_done:
        return None, 0
    percents: list[float] = []
    for marks, total_q in rows:
        total = int(total_q or 0)
        if total <= 0:
            continue
        percents.append((float(marks or 0.0) / total) * 100.0)
    if not percents:
        return 0, tests_done
    return int(round(sum(percents) / len(percents))), tests_done


def build_dashboard_stats(
    db: Session,
    user: User,
    *,
    folder_id: Optional[int] = None,
) -> dict:
    subscription = (user.subscription or "").strip()
    videos_watched = count_videos_watched(
        db, user_id=user.id, subscription=subscription, folder_id=None
    )
    total_seconds = sum_watched_seconds(db, user_id=user.id, subscription=subscription)
    avg_score, tests_done = quiz_kpi_for_user(db, user_id=user.id)

    folder_name: Optional[str] = None
    folder_total = 0
    folder_watched = 0
    remaining = 0
    if folder_id is not None:
        fm = db.query(FolderMaster).filter(FolderMaster.id == folder_id).first()
        folder_name = fm.name if fm else None
        folder_total = count_folder_videos(db, subscription=subscription, folder_id=folder_id)
        folder_watched = count_videos_watched(
            db, user_id=user.id, subscription=subscription, folder_id=folder_id
        )
        remaining = folder_remaining(folder_total, folder_watched)

    return {
        "videos_watched": int(videos_watched),
        "hours_spent": hours_from_seconds(total_seconds),
        "avg_quiz_score": avg_score,
        "tests_done": int(tests_done),
        "folder_id": folder_id,
        "folder_name": folder_name,
        "folder_total_videos": int(folder_total) if folder_id is not None else None,
        "folder_watched_videos": int(folder_watched) if folder_id is not None else None,
        "folder_remaining": int(remaining) if folder_id is not None else None,
    }
