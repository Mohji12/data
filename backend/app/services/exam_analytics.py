"""Per-student quiz/mock-test analytics for admin user detail."""

from __future__ import annotations

from typing import Any, Optional

from sqlalchemy.orm import Session

from app.models import QuizExam, UserExam
from app.services.video_progress import quiz_kpi_for_user


def score_percent(marks: float | int | None, total_questions: int | None) -> Optional[int]:
    """Same formula as dashboard: round(marks / total_questions * 100)."""
    total = int(total_questions or 0)
    if total <= 0:
        return None
    return int(round((float(marks or 0.0) / total) * 100.0))


def is_finished_exam(flag: str | None) -> bool:
    return str(flag or "").strip() == "1"


def attempt_no_map(rows: list[UserExam]) -> dict[int, int]:
    """Chronological attempt number per (user_id, exam_id), matching admin_quiz."""
    tracker: dict[tuple[int, int], int] = {}
    out: dict[int, int] = {}
    for ue in sorted(rows, key=lambda r: (int(r.user_id), int(r.exam_id), int(r.id))):
        key = (int(ue.user_id), int(ue.exam_id))
        tracker[key] = tracker.get(key, 0) + 1
        out[int(ue.id)] = tracker[key]
    return out


def summarize_exam_attempts(attempts: list[dict[str, Any]]) -> dict[str, Any]:
    """Pure summary over attempt dicts (needs exam_id, is_finished, score_percent)."""
    exam_ids = {int(a["exam_id"]) for a in attempts if a.get("exam_id") is not None}
    finished = [a for a in attempts if a.get("is_finished")]
    in_progress = [a for a in attempts if not a.get("is_finished")]
    finished_percents = [
        int(a["score_percent"])
        for a in finished
        if a.get("score_percent") is not None
    ]
    avg: Optional[int] = None
    best: Optional[int] = None
    if finished_percents:
        avg = int(round(sum(finished_percents) / len(finished_percents)))
        best = max(finished_percents)
    return {
        "exams_attempted": len(exam_ids),
        "tests_done": len(finished),
        "mock_tests_completed": len(finished),
        "in_progress_count": len(in_progress),
        "avg_score_percent": avg,
        "best_score_percent": best,
    }


def rollup_exams(attempts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Exam-wise rollup from attempt rows (sorted by attempt id ascending for latest)."""
    by_exam: dict[int, list[dict[str, Any]]] = {}
    for a in attempts:
        eid = int(a["exam_id"])
        by_exam.setdefault(eid, []).append(a)

    exams: list[dict[str, Any]] = []
    for eid, rows in by_exam.items():
        rows_sorted = sorted(rows, key=lambda r: int(r.get("user_exam_id") or 0))
        finished = [r for r in rows_sorted if r.get("is_finished")]
        finished_percents = [
            int(r["score_percent"])
            for r in finished
            if r.get("score_percent") is not None
        ]
        latest = rows_sorted[-1]
        latest_finished = finished[-1] if finished else None
        exams.append(
            {
                "exam_id": eid,
                "exam_title": rows_sorted[0].get("exam_title") or f"Exam #{eid}",
                "attempts_count": len(rows_sorted),
                "completed_count": len(finished),
                "best_score_percent": max(finished_percents) if finished_percents else None,
                "latest_score_percent": (
                    latest_finished.get("score_percent") if latest_finished else None
                ),
                "latest_marks": (
                    float(latest_finished["marks"])
                    if latest_finished and latest_finished.get("marks") is not None
                    else (float(latest["marks"]) if latest.get("marks") is not None else None)
                ),
            }
        )

    exams.sort(
        key=lambda e: (
            -(e["completed_count"] or 0),
            -(e["best_score_percent"] if e["best_score_percent"] is not None else -1),
            str(e["exam_title"]).lower(),
        )
    )
    return exams


def build_admin_user_exam_analytics(db: Session, user_id: int) -> dict[str, Any]:
    pairs = (
        db.query(UserExam, QuizExam)
        .outerjoin(QuizExam, QuizExam.id == UserExam.exam_id)
        .filter(UserExam.user_id == int(user_id))
        .order_by(UserExam.id.asc())
        .all()
    )
    ues = [ue for ue, _e in pairs]
    attempt_map = attempt_no_map(ues)

    attempts: list[dict[str, Any]] = []
    for ue, exam in pairs:
        total_q = int(exam.total_questions or 0) if exam else 0
        finished = is_finished_exam(ue.is_finish_exam)
        marks = float(ue.marks or 0.0)
        pct = score_percent(marks, total_q) if finished else None
        attempts.append(
            {
                "user_exam_id": int(ue.id),
                "exam_id": int(ue.exam_id),
                "exam_title": (exam.title if exam else None) or f"Exam #{ue.exam_id}",
                "attempt_no": attempt_map.get(int(ue.id), 1),
                "marks": marks,
                "total_questions": total_q,
                "score_percent": pct,
                "is_finished": finished,
                "start_date": ue.start_date.isoformat() if ue.start_date else None,
                "end_date": ue.end_date.isoformat() if ue.end_date else None,
                "batch": (exam.batch if exam else None) or None,
            }
        )

    # Newest first for attempt table
    attempts_desc = sorted(attempts, key=lambda a: -int(a["user_exam_id"]))
    exams = rollup_exams(attempts)

    avg_from_kpi, tests_done_kpi = quiz_kpi_for_user(db, user_id=int(user_id))
    summary = summarize_exam_attempts(attempts)
    # Prefer dashboard KPI for avg/tests_done consistency
    summary["avg_score_percent"] = avg_from_kpi
    summary["tests_done"] = int(tests_done_kpi)
    summary["mock_tests_completed"] = int(tests_done_kpi)

    return {
        **summary,
        "exams": exams,
        "attempts": attempts_desc,
    }
