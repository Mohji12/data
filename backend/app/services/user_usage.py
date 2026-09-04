"""Consolidated per-student usage dashboard for admin."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import LoginActivity
from app.services.exam_analytics import build_admin_user_exam_analytics
from app.services.video_progress import build_admin_user_video_analytics


def _parse_iso_dt(value: str | datetime | None) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    raw = str(value).strip()
    if not raw:
        return None
    try:
        # Support trailing Z
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        return None


def max_activity_at(*candidates: str | datetime | None) -> Optional[str]:
    """Return ISO string of the latest non-null timestamp among candidates."""
    parsed = [p for p in (_parse_iso_dt(c) for c in candidates) if p is not None]
    if not parsed:
        return None
    return max(parsed).isoformat()


def build_admin_user_usage(db: Session, user_id: int) -> dict[str, Any]:
    video = build_admin_user_video_analytics(db, user_id)
    exams = build_admin_user_exam_analytics(db, user_id)

    login_count = (
        db.query(func.count(LoginActivity.id))
        .filter(LoginActivity.users_id == int(user_id))
        .scalar()
        or 0
    )
    last_login = (
        db.query(func.max(LoginActivity.activity_datetime))
        .filter(LoginActivity.users_id == int(user_id))
        .scalar()
    )
    last_login_at = last_login.isoformat() if last_login else None

    latest_video_updated = None
    for v in video.get("videos") or []:
        candidate = _parse_iso_dt(v.get("updated_at"))
        if candidate and (latest_video_updated is None or candidate > latest_video_updated):
            latest_video_updated = candidate

    latest_exam_at = None
    for a in exams.get("attempts") or []:
        for key in ("end_date", "start_date"):
            candidate = _parse_iso_dt(a.get(key))
            if candidate and (latest_exam_at is None or candidate > latest_exam_at):
                latest_exam_at = candidate

    last_activity_at = max_activity_at(
        last_login_at,
        latest_video_updated.isoformat() if latest_video_updated else None,
        latest_exam_at.isoformat() if latest_exam_at else None,
    )

    return {
        "videos_watched": int(video.get("videos_watched") or 0),
        "videos_with_progress": int(video.get("videos_with_progress") or 0),
        "hours_spent": float(video.get("hours_spent") or 0.0),
        "total_watched_seconds": int(video.get("total_watched_seconds") or 0),
        "exams_attempted": int(exams.get("exams_attempted") or 0),
        "mock_tests_completed": int(exams.get("mock_tests_completed") or 0),
        "tests_done": int(exams.get("tests_done") or 0),
        "in_progress_count": int(exams.get("in_progress_count") or 0),
        "avg_score_percent": exams.get("avg_score_percent"),
        "best_score_percent": exams.get("best_score_percent"),
        "login_count": int(login_count),
        "last_login_at": last_login_at,
        "last_activity_at": last_activity_at,
        "video": {**video, "user_id": int(user_id)},
        "exams": {**exams, "user_id": int(user_id)},
    }
