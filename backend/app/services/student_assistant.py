"""Answers a logged-in student from their own course, progress, and scores.

The client never chooses a user id. Every query is filtered to the authenticated user.
"""

from __future__ import annotations

import time
from datetime import datetime

from sqlalchemy.orm import Session

from app.models import FolderMaster, QuizExam, User, UserExam, UserVideoProgress, Video
from app.services.access import (
    can_access_certificate,
    can_access_mock_test,
    can_access_video_library,
    get_subscription_period_for_profile,
)
from app.services.batch_match import find_in_set_sql
from app.services.course_hierarchy import describe_batch
from app.services.video_progress import WATCHED_THRESHOLD_SECONDS, hours_from_seconds

# Repeat questions in one chat should not wait on the remote database again.
_CACHE_SECONDS = 45.0
_watch_cache: dict[int, tuple[float, dict]] = {}

SUGGESTIONS = [
    "Show my batch hierarchy",
    "What packages are in my batch?",
    "What is my watch progress?",
    "When does my access end?",
]


def _fmt_date(value: datetime | None) -> str:
    if value is None:
        return "not set"
    if isinstance(value, datetime):
        return value.strftime("%d %b %Y")
    return str(value)[:10]


def _minutes(seconds: int | float | None) -> str:
    total = int(seconds or 0)
    if total < 60:
        return f"{total} sec"
    return f"{total // 60} min"


def _folder_has_id(folder_csv: str | None, folder_id: int) -> bool:
    return str(folder_id) in {part.strip() for part in (folder_csv or "").split(",") if part.strip()}


def _base(user: User) -> dict:
    return {
        "name": (user.name or "there").strip() or "there",
        "email": user.email,
        "course": (user.subscription or "").strip() or "not assigned",
        "hospital": (user.hospital or "").strip(),
        "qualification": (user.qualification or "").strip(),
        "speciality": (user.speciality or "").strip(),
        "city": (user.city or "").strip(),
    }


def _watch_bundle(db: Session, user: User) -> dict:
    cached = _watch_cache.get(user.id)
    now = time.monotonic()
    if cached and now - cached[0] < _CACHE_SECONDS:
        return cached[1]

    subscription = (user.subscription or "").strip()
    empty = {
        "stats": {"videos_watched": 0, "hours_spent": 0.0, "avg_quiz_score": None, "tests_done": 0},
        "folders": [],
        "recent_videos": [],
    }
    if not subscription:
        _watch_cache[user.id] = (now, empty)
        return empty

    videos = (
        db.query(Video.id, Video.title, Video.folder)
        .filter(Video.status == "1", find_in_set_sql(Video.batch, subscription))
        .all()
    )
    video_ids = {row.id for row in videos}
    progress_rows = (
        db.query(
            UserVideoProgress.video_id,
            UserVideoProgress.watched_seconds,
            UserVideoProgress.updated_at,
        )
        .filter(UserVideoProgress.user_id == user.id)
        .all()
    )
    progress = {
        video_id: (int(seconds or 0), updated)
        for video_id, seconds, updated in progress_rows
        if video_id in video_ids
    }
    watched_ids = {video_id for video_id, (seconds, _) in progress.items() if seconds >= WATCHED_THRESHOLD_SECONDS}
    total_seconds = sum(seconds for seconds, _ in progress.values())

    folder_rows = (
        db.query(FolderMaster.id, FolderMaster.name)
        .filter(FolderMaster.status == "1", find_in_set_sql(FolderMaster.batch, subscription))
        .order_by(FolderMaster.display_order.asc(), FolderMaster.id.asc())
        .all()
    )
    folders = []
    for folder_id, name in folder_rows:
        ids = [row.id for row in videos if _folder_has_id(row.folder, folder_id)]
        watched = sum(1 for video_id in ids if video_id in watched_ids)
        folders.append(
            {
                "name": name,
                "total": len(ids),
                "watched": watched,
                "remaining": max(len(ids) - watched, 0),
            }
        )

    titles = {row.id: row.title for row in videos}
    recent = sorted(progress.items(), key=lambda item: item[1][1] or datetime.min, reverse=True)[:8]
    recent_videos = [
        {
            "title": titles.get(video_id) or "Untitled",
            "watched_seconds": seconds,
            "completed": seconds >= WATCHED_THRESHOLD_SECONDS,
        }
        for video_id, (seconds, _) in recent
    ]
    bundle = {
        "stats": {
            "videos_watched": len(watched_ids),
            "hours_spent": hours_from_seconds(total_seconds),
            "avg_quiz_score": None,
            "tests_done": 0,
        },
        "folders": folders,
        "recent_videos": recent_videos,
    }
    _watch_cache[user.id] = (now, bundle)
    return bundle


def _exam_bundle(db: Session, user: User) -> dict:
    exam_rows = (
        db.query(QuizExam.title, UserExam.marks, QuizExam.total_questions, UserExam.end_date)
        .join(QuizExam, QuizExam.id == UserExam.exam_id)
        .filter(UserExam.user_id == user.id, UserExam.is_finish_exam == "1")
        .order_by(UserExam.id.desc())
        .limit(8)
        .all()
    )
    exams = []
    percents: list[float] = []
    for title, marks, total_q, end_date in exam_rows:
        total = int(total_q or 0)
        score = float(marks or 0)
        percent = round((score / total) * 100) if total > 0 else None
        if percent is not None:
            percents.append(float(percent))
        exams.append(
            {
                "title": title or "Mock test",
                "marks": score,
                "total": total,
                "percent": percent,
                "finished": _fmt_date(end_date),
            }
        )
    avg = int(round(sum(percents) / len(percents))) if percents else None
    return {"exams": exams, "tests_done": len(exam_rows), "avg_quiz_score": avg}


def _access_bundle(db: Session, user: User) -> dict:
    video_ok, video_reason = can_access_video_library(db, user)
    mock_ok, mock_reason = can_access_mock_test(db, user)
    cert_ok, cert_reason = can_access_certificate(db, user)
    return {
        "period": get_subscription_period_for_profile(db, user) or {},
        "video_ok": video_ok,
        "video_reason": video_reason,
        "mock_ok": mock_ok,
        "mock_reason": mock_reason,
        "cert_ok": cert_ok,
        "cert_reason": cert_reason,
    }


def _overview(data: dict) -> str:
    period = data["period"]
    stats = data["stats"]
    end = _fmt_date(period.get("end_at"))
    days = period.get("days_remaining")
    days_text = f"{days} days remaining" if isinstance(days, int) else "days remaining not available"
    lines = [
        f"Hello {data['name']}. This is your account only.",
        f"Course / batch: {data['course']}.",
        f"Access until {end} ({days_text}).",
        f"Videos watched: {stats['videos_watched']}. Hours spent: {stats['hours_spent']}.",
        f"Mock tests finished: {stats['tests_done']}. Average score: "
        + (f"{stats['avg_quiz_score']}%" if stats["avg_quiz_score"] is not None else "no finished tests yet")
        + ".",
    ]
    if data["folders"]:
        lines.append("Modules:")
        for folder in data["folders"]:
            lines.append(
                f"- {folder['name']}: {folder['watched']} of {folder['total']} watched, {folder['remaining']} remaining."
            )
    else:
        lines.append("No course modules are assigned to this batch yet.")
    lines.append(
        "Video library: " + ("open." if data["video_ok"] else f"closed. {data['video_reason'] or ''}".strip())
    )
    lines.append(
        "Mock tests: " + ("open." if data["mock_ok"] else f"closed. {data['mock_reason'] or ''}".strip())
    )
    lines.append(
        "Certificate: " + ("available." if data["cert_ok"] else f"not available. {data['cert_reason'] or ''}".strip())
    )
    return "\n".join(lines)


def _progress(data: dict) -> str:
    stats = data["stats"]
    lines = [
        f"Watch progress for {data['name']} on {data['course']}:",
        f"{stats['videos_watched']} videos counted as watched.",
        f"{stats['hours_spent']} hours of watch time recorded.",
    ]
    if data["folders"]:
        for folder in data["folders"]:
            lines.append(
                f"{folder['name']}: {folder['watched']}/{folder['total']} watched, {folder['remaining']} left."
            )
    if data["recent_videos"]:
        lines.append("Latest videos you opened:")
        for video in data["recent_videos"]:
            state = "watched" if video["completed"] else "in progress"
            lines.append(f"- {video['title']}: {_minutes(video['watched_seconds'])} ({state}).")
    else:
        lines.append("No watch time is stored for your account yet.")
    return "\n".join(lines)


def _quizzes(data: dict) -> str:
    stats = data["stats"]
    if not data["exams"]:
        return (
            f"You have not finished a mock test yet. Tests completed: {stats['tests_done']}. "
            + ("Mock tests are open." if data["mock_ok"] else f"Mock tests are closed. {data['mock_reason'] or ''}".strip())
        )
    lines = [
        f"Finished mock tests: {stats['tests_done']}. Average score: {stats['avg_quiz_score']}%.",
    ]
    for exam in data["exams"]:
        percent = f"{exam['percent']}%" if exam["percent"] is not None else "n/a"
        lines.append(
            f"- {exam['title']}: {exam['marks']} / {exam['total']} ({percent}), finished {exam['finished']}."
        )
    return "\n".join(lines)


def _access(data: dict) -> str:
    period = data["period"]
    extended = " Yes, this end date includes an extension." if period.get("is_extended") else ""
    return (
        f"Your course is {data['course']}. "
        f"Access runs from {_fmt_date(period.get('start_at'))} to {_fmt_date(period.get('end_at'))}. "
        f"Days remaining: {period.get('days_remaining') if period.get('days_remaining') is not None else 'not available'}."
        f"{extended} "
        f"Video library is {'open' if data['video_ok'] else 'closed'}. "
        f"Mock tests are {'open' if data['mock_ok'] else 'closed'}. "
        f"Certificate is {'available' if data['cert_ok'] else 'not available'}."
    )


def _profile(data: dict) -> str:
    parts = [
        f"Name: {data['name']}.",
        f"Email: {data['email']}.",
        f"Course: {data['course']}.",
    ]
    if data["qualification"]:
        parts.append(f"Qualification: {data['qualification']}.")
    if data["speciality"]:
        parts.append(f"Speciality: {data['speciality']}.")
    if data["hospital"]:
        parts.append(f"Hospital: {data['hospital']}.")
    if data["city"]:
        parts.append(f"City: {data['city']}.")
    return " ".join(parts)


def _match_video(data: dict, text: str) -> str | None:
    for video in data["recent_videos"]:
        title = video["title"].strip()
        if len(title) >= 4 and title.lower() in text:
            state = "counted as watched" if video["completed"] else "still in progress"
            return f"{title}: {_minutes(video['watched_seconds'])} recorded, {state}."
    return None


def answer_student(db: Session, user: User, message: str) -> dict:
    text = " ".join((message or "").split()).strip().lower()
    person = _base(user)

    if not text or text in {"hi", "hello", "hey", "help"}:
        reply = (
            f"Hello {person['name']}. I can show your course, watch progress, and mock-test scores. "
            "I only read your login's records."
        )
    elif any(word in text for word in ("quiz", "mock", "score", "test", "marks", "result")):
        exams = _exam_bundle(db, user)
        reply = _quizzes(
            {
                **person,
                "exams": exams["exams"],
                "stats": {
                    "tests_done": exams["tests_done"],
                    "avg_quiz_score": exams["avg_quiz_score"],
                },
                "mock_ok": True,
                "mock_reason": None,
            }
        )
    elif any(word in text for word in ("progress", "watch", "video", "hour", "module", "folder", "remaining")):
        reply = _progress({**person, **_watch_bundle(db, user)})
    elif any(word in text for word in ("access", "end", "expire", "expir", "extend", "certificate")):
        reply = _access({**person, **_access_bundle(db, user)})
    elif any(word in text for word in ("profile", "who am i", "my name", "email", "hospital")):
        reply = _profile(person)
    elif any(
        word in text
        for word in ("course", "detail", "analytics", "overview", "everything", "summary", "status", "batch", "package", "hierarch")
    ):
        if person["course"] == "not assigned":
            reply = f"{person['name']}, no batch is assigned to your account."
        else:
            reply = f"{person['name']}, this is your batch only.\n" + describe_batch(
                db, person["course"], user_id=user.id
            )
    else:
        watch = _watch_bundle(db, user)
        video_hit = _match_video(watch, text)
        reply = video_hit or (
            "I can answer from your account only: course details, module progress, videos watched, "
            "hours spent, mock-test scores, and when your access ends. Try one of the suggestions."
        )

    return {"reply": reply, "suggestions": SUGGESTIONS}
