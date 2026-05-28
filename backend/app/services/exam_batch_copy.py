from __future__ import annotations

from typing import Any, Optional

from sqlalchemy.orm import Session

from app.models import Option, QuizExam
from app.services.access import get_option_value, subscription_allowed


def _subscription_in_csv(subscription: str | None, csv_column: str | None) -> bool:
    sub = (subscription or "").strip()
    if not sub:
        return False
    parts = [p.strip() for p in (csv_column or "").split(",") if p.strip()]
    sub_l = sub.lower()
    return any(p.lower() == sub_l for p in parts)


def _exams_for_batch(db: Session, batch_name: str, *, active_only: bool = True) -> list[QuizExam]:
    batch_name = (batch_name or "").strip()
    if not batch_name:
        return []
    rows = db.query(QuizExam).order_by(QuizExam.id.asc()).all()
    out = [e for e in rows if _subscription_in_csv(batch_name, e.batch)]
    if active_only:
        out = [e for e in out if (e.status or "") == "1"]
    return out


def _exam_signature(title: str | None, section_id: str | None) -> tuple[str, str]:
    return ((title or "").strip().casefold(), (section_id or "").strip())


def _find_target_exam(
    db: Session,
    *,
    title: str,
    section_id: str,
    target_batch: str,
) -> QuizExam | None:
    sig = _exam_signature(title, section_id)
    for e in _exams_for_batch(db, target_batch, active_only=False):
        if _exam_signature(e.title, e.section_id) == sig:
            return e
    return None


def enable_mock_test_access(db: Session, batch_name: str, *, dry_run: bool = False) -> dict[str, Any]:
    """Append batch to access_quiz_link option if missing."""
    batch_name = (batch_name or "").strip()
    current = get_option_value(db, "access_quiz_link")
    already = subscription_allowed(current, batch_name)
    if already:
        return {"batch_name": batch_name, "updated": False, "already_enabled": True}
    parts = [p.strip() for p in (current or "").split(",") if p.strip()]
    parts.append(batch_name)
    new_value = ",".join(parts)
    if not dry_run:
        row = db.query(Option).filter(Option.option_name == "access_quiz_link").first()
        if row:
            row.option_value = new_value
        else:
            db.add(Option(option_name="access_quiz_link", option_value=new_value))
        db.commit()
    return {"batch_name": batch_name, "updated": True, "already_enabled": False, "new_value": new_value}


def preview_clone_batch_exams(
    db: Session,
    *,
    source_batch: str,
    target_batch: str,
) -> dict[str, Any]:
    source_batch = (source_batch or "").strip()
    target_batch = (target_batch or "").strip()
    source_exams = _exams_for_batch(db, source_batch)
    exams_to_create: list[dict[str, Any]] = []
    exams_already: list[dict[str, Any]] = []

    for src in source_exams:
        existing = _find_target_exam(
            db,
            title=src.title or "",
            section_id=src.section_id or "",
            target_batch=target_batch,
        )
        row = {
            "source_exam_id": src.id,
            "source_title": src.title,
            "section_id": src.section_id,
            "section_names": None,
            "total_questions": src.total_questions,
            "timer_time": src.timer_time,
        }
        if existing:
            exams_already.append(
                {
                    **row,
                    "target_exam_id": existing.id,
                    "target_title": existing.title,
                }
            )
        else:
            exams_to_create.append(row)

    quiz_access = get_option_value(db, "access_quiz_link")
    return {
        "source_batch": source_batch,
        "target_batch": target_batch,
        "source_exam_count": len(source_exams),
        "exams_to_create": exams_to_create,
        "exams_to_create_count": len(exams_to_create),
        "exams_already": exams_already,
        "exams_already_count": len(exams_already),
        "mock_test_access_enabled": subscription_allowed(quiz_access, target_batch),
    }


def clone_batch_exams(
    db: Session,
    *,
    source_batch: str,
    target_batch: str,
    enable_mock_test_access_flag: bool = True,
    dry_run: bool = False,
) -> dict[str, Any]:
    """
    Copy Batch 15 mock tests to Batch 16 MCCM: duplicate quiz_exam rows (same sections/questions)
    when no matching target exam exists; optionally enable access_quiz_link for target batch.
    """
    preview = preview_clone_batch_exams(db, source_batch=source_batch, target_batch=target_batch)
    created: list[dict[str, Any]] = []

    if not dry_run:
        source_by_id = {e.id: e for e in _exams_for_batch(db, source_batch.strip())}
        for item in preview["exams_to_create"]:
            src = source_by_id.get(item["source_exam_id"])
            if not src:
                continue
            row = QuizExam(
                title=(src.title or "").strip(),
                description=src.description,
                section_id=(src.section_id or "").strip(),
                batch=target_batch.strip(),
                timer_time=src.timer_time,
                total_questions=src.total_questions,
                start_date=src.start_date,
                end_date=src.end_date,
                status=src.status or "1",
                is_display_result=src.is_display_result or "1",
                is_display_correct_answer=src.is_display_correct_answer or "0",
            )
            db.add(row)
            db.flush()
            created.append(
                {
                    "source_exam_id": src.id,
                    "target_exam_id": row.id,
                    "title": row.title,
                }
            )
        if created:
            db.commit()

    access_result: dict[str, Any] | None = None
    if enable_mock_test_access_flag and not dry_run:
        access_result = enable_mock_test_access(db, target_batch.strip(), dry_run=False)
    elif enable_mock_test_access_flag and dry_run:
        access_result = enable_mock_test_access(db, target_batch.strip(), dry_run=True)

    return {
        **preview,
        "dry_run": dry_run,
        "exams_created": len(created),
        "created_exams": created,
        "mock_test_access": access_result,
    }
