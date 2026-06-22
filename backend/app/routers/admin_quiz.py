from __future__ import annotations
import csv
import io
from datetime import date, datetime
from typing import Any, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.admin_security import get_current_admin, require_admin_type
from app.db import get_db
from app.models import MarkingType, Question, QuizExam, QuizSection, User, UserAnswer, UserExam
from app.services.pdfs import quiz_result_pdf
from app.services.uploads import remove_question_image_file, save_question_image

router = APIRouter(prefix="/admin/quiz", tags=["admin-quiz"], dependencies=[Depends(get_current_admin)])

_QUESTION_COLS = {c.key for c in Question.__table__.columns}


def _iso_date_only(value: date | datetime | None) -> str | None:
    """Serialize DB date/datetime columns as YYYY-MM-DD."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date().isoformat()
    return value.isoformat()


def _attempt_no_map(rows: list[UserExam]) -> dict[int, int]:
    tracker: dict[tuple[int, int], int] = {}
    out: dict[int, int] = {}
    for ue in sorted(rows, key=lambda r: (r.user_id, r.exam_id, r.id)):
        key = (ue.user_id, ue.exam_id)
        tracker[key] = tracker.get(key, 0) + 1
        out[ue.id] = tracker[key]
    return out


def _section_names_for_exam(db: Session, section_id_csv: str | None) -> str:
    """PHP datatable: GROUP_CONCAT quiz_section.name for ids in quiz_exam.section_id."""
    raw = (section_id_csv or "").strip()
    if not raw:
        return ""
    ids: list[int] = []
    for p in raw.split(","):
        t = p.strip()
        if t.isdigit():
            ids.append(int(t))
    if not ids:
        return ""
    rows = db.query(QuizSection).filter(QuizSection.id.in_(ids), QuizSection.status == "1").all()
    by_id = {r.id: (r.name or "") for r in rows}
    return ", ".join(by_id.get(i, "") for i in ids if by_id.get(i))


def _count_filled_options(payload: dict[str, Any]) -> int:
    n = 0
    for k in ("option_a", "option_b", "option_c", "option_d", "option_e"):
        v = payload.get(k)
        if v is not None and str(v).strip():
            n += 1
    return n


def _validate_question_options(answer_type: str, payload: dict[str, Any]) -> None:
    at = (answer_type or "").strip().upper()
    if at in ("R", "C"):
        if _count_filled_options(payload) == 0:
            raise HTTPException(status_code=422, detail="At least one option (A–E) is required for Radio/Checkbox questions.")
    if at == "K":
        n = _count_filled_options(payload)
        total = int(payload.get("total_option") or 0) or n
        if total < 4:
            raise HTTPException(status_code=422, detail="K-type questions require 4 statements (options A–D).")


class SectionPayload(BaseModel):
    name: str
    display_order: int = 0
    status: str = "1"


@router.get("/sections")
def list_sections(db: Session = Depends(get_db)) -> list[dict]:
    rows = db.query(QuizSection).order_by(QuizSection.display_order.asc(), QuizSection.id.asc()).all()
    return [{"id": s.id, "name": s.name, "display_order": s.display_order, "status": s.status} for s in rows]


@router.post("/sections")
def create_section(payload: SectionPayload, db: Session = Depends(get_db)) -> dict:
    if not (payload.name or "").strip():
        raise HTTPException(status_code=422, detail="Name is required.")
    s = QuizSection(name=payload.name.strip(), display_order=payload.display_order, status=payload.status)
    db.add(s)
    db.commit()
    db.refresh(s)
    return {"id": s.id}


@router.put("/sections/{section_id}")
def update_section(section_id: int, payload: SectionPayload, db: Session = Depends(get_db)) -> dict:
    s = db.query(QuizSection).filter(QuizSection.id == section_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="Section not found")
    s.name = payload.name.strip()
    s.display_order = payload.display_order
    s.status = payload.status
    db.add(s)
    db.commit()
    return {"status": "ok"}


@router.delete("/sections/{section_id}")
def delete_section(section_id: int, db: Session = Depends(get_db)) -> dict:
    s = db.query(QuizSection).filter(QuizSection.id == section_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="Section not found")
    db.delete(s)
    db.commit()
    return {"status": "ok"}


@router.get("/marking-types")
def list_marking_types(db: Session = Depends(get_db)) -> list[dict]:
    rows = db.query(MarkingType).order_by(MarkingType.id.asc()).all()
    return [
        {
            "id": m.id,
            "name": m.name,
            "description": m.description,
            "negative_mark": m.negative_mark,
            "status": m.status,
            "total_correct_answer": m.total_correct_answer,
            "minimum_correct_answer": m.minimum_correct_answer,
        }
        for m in rows
    ]


class MarkingPayload(BaseModel):
    name: str
    description: Optional[str] = None
    negative_mark: float = 0.0
    status: str = "1"


@router.post("/marking-types")
def create_marking(payload: MarkingPayload, db: Session = Depends(get_db)) -> dict:
    m = MarkingType(name=payload.name, description=payload.description, negative_mark=payload.negative_mark, status=payload.status)
    db.add(m)
    db.commit()
    db.refresh(m)
    return {"id": m.id}


@router.put("/marking-types/{marking_id}")
def update_marking(marking_id: int, payload: MarkingPayload, db: Session = Depends(get_db)) -> dict:
    m = db.query(MarkingType).filter(MarkingType.id == marking_id).first()
    if not m:
        raise HTTPException(status_code=404, detail="Marking type not found")
    m.name = payload.name
    m.description = payload.description
    m.negative_mark = payload.negative_mark
    m.status = payload.status
    db.add(m)
    db.commit()
    return {"status": "ok"}


@router.delete("/marking-types/{marking_id}")
def delete_marking(marking_id: int, db: Session = Depends(get_db)) -> dict:
    m = db.query(MarkingType).filter(MarkingType.id == marking_id).first()
    if not m:
        raise HTTPException(status_code=404, detail="Marking type not found")
    db.delete(m)
    db.commit()
    return {"status": "ok"}


def _answer_type_label(at: str | None) -> str:
    x = (at or "").strip().upper()
    if x == "R":
        return "Radio Button"
    if x == "C":
        return "Checkbox"
    if x == "MTF":
        return "Multiple True False"
    if x == "K":
        return "K-type (True/False)"
    return "Free Format"


@router.get("/questions")
def list_questions(
    section_id: Optional[int] = Query(None),
    q: Optional[str] = Query(None),
    sort_by: Optional[str] = Query(None, description="id, question"),
    order: str = Query("desc"),
    db: Session = Depends(get_db),
) -> list[dict]:
    query = (
        db.query(Question, QuizSection.name.label("section_name"), MarkingType.name.label("marking_type_name"))
        .outerjoin(QuizSection, QuizSection.id == Question.section_id)
        .outerjoin(MarkingType, MarkingType.id == Question.marking_type_id)
    )
    if section_id:
        query = query.filter(Question.section_id == section_id)
    if q:
        s = f"%{q.strip().lower()}%"
        query = query.filter(func.lower(func.coalesce(Question.question, "")).like(s))

    # Dynamic sorting
    if sort_by:
        col = getattr(Question, sort_by, None)
        if col:
            if order.lower() == "asc":
                query = query.order_by(col.asc())
            else:
                query = query.order_by(col.desc())
        else:
            query = query.order_by(Question.id.desc())
    else:
        query = query.order_by(Question.id.desc())

    rows = query.all()
    out = []
    for row, section_name, marking_name in rows:
        out.append(
            {
                "id": row.id,
                "section_id": row.section_id,
                "section_name": section_name or "",
                "marking_type_id": row.marking_type_id,
                "marking_type_name": marking_name or "",
                "question": row.question,
                "question_image": row.question_image,
                "answer": row.answer,
                "answer_type": row.answer_type,
                "answer_type_label": _answer_type_label(row.answer_type),
                "option_a": row.option_a,
                "option_b": row.option_b,
                "option_c": row.option_c,
                "option_d": row.option_d,
                "option_e": row.option_e,
                "total_option": row.total_option,
                "is_mandatory_question": row.is_mandatory_question,
                "marks": row.marks,
                "negative_marks": row.negative_marks,
                "status": row.status,
            }
        )
    return out


@router.get("/questions/{question_id}")
def get_question(question_id: int, db: Session = Depends(get_db)) -> dict:
    row = db.query(Question).filter(Question.id == question_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Question not found")
    return {
        "id": row.id,
        "section_id": row.section_id,
        "marking_type_id": row.marking_type_id,
        "question": row.question or "",
        "question_image": row.question_image,
        "answer": row.answer or "",
        "answer_type": row.answer_type or "R",
        "option_a": row.option_a,
        "option_b": row.option_b,
        "option_c": row.option_c,
        "option_d": row.option_d,
        "option_e": row.option_e,
        "total_option": row.total_option or 0,
        "is_mandatory_question": row.is_mandatory_question or "0",
        "marks": row.marks,
        "negative_marks": row.negative_marks,
        "status": row.status or "1",
    }


class AdminQuestionPayload(BaseModel):
    section_id: int
    marking_type_id: int
    question: str
    answer: str = ""
    answer_type: str = "R"
    option_a: Optional[str] = None
    option_b: Optional[str] = None
    option_c: Optional[str] = None
    option_d: Optional[str] = None
    option_e: Optional[str] = None
    question_image: Optional[str] = None
    marks: Optional[int] = None
    negative_marks: Optional[int] = None
    is_mandatory_question: str = "0"
    status: str = "1"


@router.post("/questions")
def create_question(payload: AdminQuestionPayload, db: Session = Depends(get_db)) -> dict:
    if not (payload.question or "").strip():
        raise HTTPException(status_code=422, detail="Question text is required.")
    if not payload.marking_type_id:
        raise HTTPException(status_code=422, detail="Marking type is required.")
    if not (payload.answer or "").strip():
        raise HTTPException(status_code=422, detail="Answer is required.")
    data = payload.model_dump()
    _validate_question_options(payload.answer_type, data)
    data["total_option"] = _count_filled_options(data)
    q = Question(**{k: v for k, v in data.items() if k in _QUESTION_COLS})
    db.add(q)
    db.commit()
    db.refresh(q)
    return {"id": q.id}


@router.post("/questions/upload-image")
def upload_question_image(file: UploadFile = File(...)) -> dict:
    filename = save_question_image(file)
    return {"filename": filename}


@router.put("/questions/{question_id}")
def update_question(question_id: int, payload: AdminQuestionPayload, db: Session = Depends(get_db)) -> dict:
    q = db.query(Question).filter(Question.id == question_id).first()
    if not q:
        raise HTTPException(status_code=404, detail="Question not found")
    data = payload.model_dump()
    _validate_question_options(payload.answer_type, data)
    new_img = (payload.question_image or "").strip() or None
    old_img = (q.question_image or "").strip() or None
    if new_img and old_img and new_img != old_img:
        remove_question_image_file(old_img)
    data["total_option"] = _count_filled_options(data)
    for k, v in data.items():
        if k in _QUESTION_COLS and k != "id":
            setattr(q, k, v)
    db.add(q)
    db.commit()
    return {"status": "ok"}


@router.delete("/questions/{question_id}")
def delete_question(question_id: int, db: Session = Depends(get_db)) -> dict:
    q = db.query(Question).filter(Question.id == question_id).first()
    if not q:
        raise HTTPException(status_code=404, detail="Question not found")
    remove_question_image_file(q.question_image)
    db.delete(q)
    db.commit()
    return {"status": "ok"}


class ExamPayload(BaseModel):
    title: str
    description: Optional[str] = None
    section_id: str = Field(..., description="Comma-separated quiz_section ids")
    batch: str = Field(..., description="Comma-separated batch names from batch_master")
    total_questions: int
    start_date: datetime
    end_date: datetime
    timer_time: int
    status: str = "1"
    is_display_result: str = "1"
    is_display_correct_answer: str = "0"


def _validate_exam_payload(p: ExamPayload) -> None:
    if not (p.title or "").strip():
        raise HTTPException(status_code=422, detail="Exam title is required.")
    if not (p.section_id or "").strip():
        raise HTTPException(status_code=422, detail="At least one section is required.")
    if not (p.batch or "").strip():
        raise HTTPException(status_code=422, detail="At least one batch is required.")
    if p.total_questions is None or int(p.total_questions) < 1:
        raise HTTPException(status_code=422, detail="Total questions is required.")
    if p.timer_time is None or int(p.timer_time) < 1:
        raise HTTPException(status_code=422, detail="Timer time is required.")


@router.get("/exams")
def list_exams(
    q: Optional[str] = Query(None),
    sort_by: Optional[str] = Query(None, description="id, title, start_date"),
    order: str = Query("desc"),
    db: Session = Depends(get_db),
) -> list[dict]:
    query = db.query(QuizExam)
    if q:
        s = f"%{q.strip().lower()}%"
        query = query.filter(func.lower(func.coalesce(QuizExam.title, "")).like(s))

    # Dynamic sorting
    if sort_by:
        col = getattr(QuizExam, sort_by, None)
        if col:
            if order.lower() == "asc":
                query = query.order_by(col.asc())
            else:
                query = query.order_by(col.desc())
        else:
            query = query.order_by(QuizExam.id.desc())
    else:
        query = query.order_by(QuizExam.id.desc())

    rows = query.all()
    out = []
    for e in rows:
        out.append(
            {
                "id": e.id,
                "title": e.title,
                "description": e.description,
                "section_id": e.section_id,
                "section_names": _section_names_for_exam(db, e.section_id),
                "batch": e.batch,
                "total_questions": e.total_questions,
                "timer_time": e.timer_time,
                "start_date": _iso_date_only(e.start_date),
                "end_date": _iso_date_only(e.end_date),
                "status": e.status,
                "is_display_result": e.is_display_result,
                "is_display_correct_answer": e.is_display_correct_answer,
            }
        )
    return out


@router.get("/exams/{exam_id}")
def get_exam(exam_id: int, db: Session = Depends(get_db)) -> dict:
    e = db.query(QuizExam).filter(QuizExam.id == exam_id).first()
    if not e:
        raise HTTPException(status_code=404, detail="Exam not found")
    return {
        "id": e.id,
        "title": e.title or "",
        "description": e.description or "",
        "section_id": e.section_id,
        "section_names": _section_names_for_exam(db, e.section_id),
        "batch": e.batch or "",
        "total_questions": e.total_questions,
        "timer_time": e.timer_time,
        "start_date": _iso_date_only(e.start_date),
        "end_date": _iso_date_only(e.end_date),
        "status": e.status or "1",
        "is_display_result": e.is_display_result or "1",
        "is_display_correct_answer": e.is_display_correct_answer or "0",
    }


@router.post("/exams")
def create_exam(payload: ExamPayload, db: Session = Depends(get_db)) -> dict:
    _validate_exam_payload(payload)
    e = QuizExam(**payload.model_dump())
    db.add(e)
    db.commit()
    db.refresh(e)
    return {"id": e.id}


@router.put("/exams/{exam_id}")
def update_exam(exam_id: int, payload: ExamPayload, db: Session = Depends(get_db)) -> dict:
    e = db.query(QuizExam).filter(QuizExam.id == exam_id).first()
    if not e:
        raise HTTPException(status_code=404, detail="Exam not found")
    _validate_exam_payload(payload)
    for k, v in payload.model_dump().items():
        setattr(e, k, v)
    db.add(e)
    db.commit()
    return {"status": "ok"}


@router.delete("/exams/{exam_id}")
def delete_exam(exam_id: int, db: Session = Depends(get_db)) -> dict:
    e = db.query(QuizExam).filter(QuizExam.id == exam_id).first()
    if not e:
        raise HTTPException(status_code=404, detail="Exam not found")
    db.delete(e)
    db.commit()
    return {"status": "ok"}


class CloneBatchExamsPayload(BaseModel):
    source_batch: str
    target_batch: str
    enable_mock_test_access: bool = True
    dry_run: bool = False


def _validate_clone_batch_exams_payload(payload: CloneBatchExamsPayload) -> None:
    if not (payload.source_batch or "").strip() or not (payload.target_batch or "").strip():
        raise HTTPException(status_code=422, detail="source_batch and target_batch are required.")
    if payload.source_batch.strip().casefold() == payload.target_batch.strip().casefold():
        raise HTTPException(
            status_code=422,
            detail="Copy from and Copy to batch must be different.",
        )


@router.post(
    "/exams/clone-batch/preview",
    dependencies=[Depends(require_admin_type("techadmin"))],
)
def preview_clone_batch_exams_route(
    payload: CloneBatchExamsPayload,
    db: Session = Depends(get_db),
) -> dict:
    """Preview duplicating quiz_exam rows from source batch to target batch."""
    from app.services.exam_batch_copy import preview_clone_batch_exams

    _validate_clone_batch_exams_payload(payload)
    return preview_clone_batch_exams(
        db,
        source_batch=payload.source_batch.strip(),
        target_batch=payload.target_batch.strip(),
    )


@router.post(
    "/exams/clone-batch",
    dependencies=[Depends(require_admin_type("techadmin"))],
)
def clone_batch_exams_route(payload: CloneBatchExamsPayload, db: Session = Depends(get_db)) -> dict:
    """Duplicate Batch 15 mock tests for Batch 16 MCCM (same question sections)."""
    from app.services.exam_batch_copy import clone_batch_exams

    _validate_clone_batch_exams_payload(payload)
    return clone_batch_exams(
        db,
        source_batch=payload.source_batch.strip(),
        target_batch=payload.target_batch.strip(),
        enable_mock_test_access_flag=payload.enable_mock_test_access,
        dry_run=payload.dry_run,
    )


@router.get("/exams/{exam_id}/pool-questions")
def list_exam_pool_questions(exam_id: int, db: Session = Depends(get_db)) -> list[dict]:
    """PHP `Quiz_exam::questions` — questions whose section is included in the exam's section_id list."""
    exam = db.query(QuizExam).filter(QuizExam.id == exam_id).first()
    if not exam or (exam.status or "") != "1":
        raise HTTPException(status_code=404, detail="Exam not found")
    raw = (exam.section_id or "").strip()
    if not raw:
        return []
    ids = [int(x.strip()) for x in raw.split(",") if x.strip().isdigit()]
    if not ids:
        return []
    rows = (
        db.query(Question, QuizSection.display_order, QuizSection.name.label("section_name"))
        .join(QuizSection, QuizSection.id == Question.section_id)
        .filter(Question.section_id.in_(ids), Question.status == "1")
        .order_by(QuizSection.display_order.asc(), Question.id.asc())
        .all()
    )
    out = []
    for q, _disp, sec_name in rows:
        out.append(
            {
                "id": q.id,
                "section_id": q.section_id,
                "section_name": sec_name or "",
                "question": q.question,
                "answer_type": q.answer_type,
                "answer_type_label": _answer_type_label(q.answer_type),
                "status": q.status,
            }
        )
    return out


@router.get("/exams/{exam_id}/download-result")
def download_exam_results_php_csv(exam_id: int, db: Session = Depends(get_db)) -> Response:
    """PHP `Quiz_exam::download_result` columns."""
    exam = db.query(QuizExam).filter(QuizExam.id == exam_id).first()
    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found")
    ues = db.query(UserExam).filter(UserExam.exam_id == exam_id).order_by(UserExam.id.asc()).all()
    if not ues:
        raise HTTPException(status_code=404, detail="No Exam Result Found.")

    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["Sl No", "Attempt No", "Username", "Total question", "Total Answered", "Total Correct Answer", "Total Wrong Answer", "Total Marks"])
    total_q = int(exam.total_questions or 0)
    attempt_map = _attempt_no_map(ues)
    for idx, ue in enumerate(ues):
        u = db.query(User).filter(User.id == ue.user_id).first()
        uname = " ".join(x for x in [(u.title or "").strip(), (u.name or "").strip()] if u and x).strip() if u else ""
        answered = (
            db.query(func.count(UserAnswer.id))
            .filter(UserAnswer.user_id == ue.user_id, UserAnswer.exam_id == exam_id, UserAnswer.user_exam_id == ue.id)
            .scalar()
            or 0
        )
        correct = (
            db.query(func.count(UserAnswer.id))
            .filter(UserAnswer.user_id == ue.user_id, UserAnswer.exam_id == exam_id, UserAnswer.user_exam_id == ue.id, UserAnswer.is_correct_answer == "1")
            .scalar()
            or 0
        )
        wrong = (
            db.query(func.count(UserAnswer.id))
            .filter(UserAnswer.user_id == ue.user_id, UserAnswer.exam_id == exam_id, UserAnswer.user_exam_id == ue.id, UserAnswer.is_correct_answer == "0")
            .scalar()
            or 0
        )
        marks = float(ue.marks or 0.0)
        w.writerow([idx + 1, attempt_map.get(ue.id, 1), uname, total_q, answered, correct, wrong, marks])

    safe = "".join(c for c in (exam.title or "exam") if c.isalnum() or c in " -_")[:80]
    fname = f"{safe}-download-result-{datetime.utcnow().date().isoformat()}.csv"
    return Response(content=buf.getvalue(), media_type="text/csv", headers={"Content-Disposition": f"attachment; filename={fname}"})


@router.get("/results")
def list_results(
    exam_id: Optional[int] = Query(None),
    q: Optional[str] = Query(None, description="Search user name/email"),
    sort_by: Optional[str] = Query(None, description="id, marks, start_date"),
    order: str = Query("desc"),
    db: Session = Depends(get_db),
) -> list[dict]:
    query = db.query(UserExam, User, QuizExam).join(User, User.id == UserExam.user_id).join(QuizExam, QuizExam.id == UserExam.exam_id)
    if exam_id:
        query = query.filter(UserExam.exam_id == exam_id)
    if q:
        s = f"%{q.strip().lower()}%"
        query = query.filter(
            func.lower(func.coalesce(User.name, "")).like(s)
            | func.lower(func.coalesce(User.email, "")).like(s)
        )

    # Dynamic sorting
    if sort_by:
        col = getattr(UserExam, sort_by, None)
        if col:
            if order.lower() == "asc":
                query = query.order_by(col.asc())
            else:
                query = query.order_by(col.desc())
        else:
            query = query.order_by(UserExam.id.desc())
    else:
        query = query.order_by(UserExam.id.desc())

    rows = query.limit(500).all()
    attempt_map = _attempt_no_map([ue for ue, _u, _e in rows])
    return [
        {
            "user_exam_id": ue.id,
            "attempt_no": attempt_map.get(ue.id, 1),
            "user_id": u.id,
            "user_email": u.email,
            "exam_id": e.id,
            "exam_title": e.title,
            "marks": ue.marks,
            "is_finish_exam": ue.is_finish_exam,
            "start_date": ue.start_date.isoformat() if ue.start_date else None,
            "end_date": ue.end_date.isoformat() if ue.end_date else None,
        }
        for ue, u, e in rows
    ]


@router.get("/results/export.csv")
def export_results_csv(
    exam_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
) -> Response:
    query = db.query(UserExam, User, QuizExam).join(User, User.id == UserExam.user_id).join(QuizExam, QuizExam.id == UserExam.exam_id)
    if exam_id:
        query = query.filter(UserExam.exam_id == exam_id)
    rows = query.order_by(UserExam.id.desc()).all()
    attempt_map = _attempt_no_map([ue for ue, _u, _e in rows])

    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["user_exam_id", "attempt_no", "user_id", "email", "exam_id", "exam_title", "marks", "is_finish_exam", "start_date", "end_date"])
    for ue, u, e in rows:
        w.writerow([ue.id, attempt_map.get(ue.id, 1), u.id, u.email or "", e.id, e.title or "", ue.marks or 0, ue.is_finish_exam or "", ue.start_date.isoformat() if ue.start_date else "", ue.end_date.isoformat() if ue.end_date else ""])
    return Response(content=buf.getvalue(), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=quiz_results.csv"})


@router.get("/questions-graph")
def question_graph(exam_id: int, db: Session = Depends(get_db)) -> dict:
    rows = (
        db.query(UserAnswer.question_id, UserAnswer.answer, func.count(UserAnswer.id))
        .filter(UserAnswer.exam_id == exam_id)
        .group_by(UserAnswer.question_id, UserAnswer.answer)
        .all()
    )
    out: dict[str, dict[str, int]] = {}
    for qid, ans, cnt in rows:
        key = str(qid)
        out.setdefault(key, {})
        out[key][ans or ""] = int(cnt)
    return out


@router.get("/questions-graph-detail")
def questions_graph_detail(exam_id: int, question_id: int, db: Session = Depends(get_db)) -> dict:
    """PHP `questions_graph`: counts per option A–E using FIND_IN_SET on user_answer.answer."""
    q = db.query(Question).filter(Question.id == question_id).first()
    if not q:
        raise HTTPException(status_code=404, detail="Question not found")
    n_opt = int(q.total_option or 0)
    if n_opt <= 0:
        n_opt = _count_filled_options(
            {
                "option_a": q.option_a,
                "option_b": q.option_b,
                "option_c": q.option_c,
                "option_d": q.option_d,
                "option_e": q.option_e,
            }
        )
    labels = ["A", "B", "C", "D", "E"][: max(1, n_opt)]
    total_answered = (
        db.query(func.count(UserAnswer.id))
        .filter(UserAnswer.exam_id == exam_id, UserAnswer.question_id == question_id)
        .scalar()
        or 0
    )
    counts: list[int] = []
    percentages: list[int] = []
    option_texts: dict[str, str] = {}
    for i, letter in enumerate(labels):
        opt_attr = f"option_{letter.lower()}"
        option_texts[letter] = str(getattr(q, opt_attr, None) or "")
        cnt = (
            db.query(func.count(UserAnswer.id))
            .filter(
                UserAnswer.exam_id == exam_id,
                UserAnswer.question_id == question_id,
                func.find_in_set(letter, func.coalesce(UserAnswer.answer, "")) > 0,
            )
            .scalar()
            or 0
        )
        counts.append(int(cnt))
        pct = 0
        if total_answered > 0 and cnt > 0:
            pct = round((int(cnt) * 100) / int(total_answered))
        percentages.append(pct)

    mt = db.query(MarkingType).filter(MarkingType.id == q.marking_type_id).first()
    marking_description = (mt.description or "") if mt else ""

    exam_qs = db.query(QuizExam).filter(QuizExam.id == exam_id).first()
    exam_question_ids: list[int] = []
    if exam_qs and (exam_qs.section_id or "").strip():
        ids = [int(x.strip()) for x in exam_qs.section_id.split(",") if x.strip().isdigit()]
        if ids:
            id_rows = (
                db.query(Question.id)
                .filter(Question.section_id.in_(ids), Question.status == "1")
                .order_by(Question.id.asc())
                .all()
            )
            exam_question_ids = [r[0] for r in id_rows]

    return {
        "question_id": question_id,
        "labels": labels,
        "counts": counts,
        "percentages": percentages,
        "option_texts": option_texts,
        "total_answered": int(total_answered),
        "marking_description": marking_description,
        "exam_question_id_array": exam_question_ids,
    }


@router.get("/results/{user_exam_id}/download.pdf")
def download_result_pdf(user_exam_id: int, db: Session = Depends(get_db)) -> Response:
    row = (
        db.query(UserExam, User, QuizExam)
        .join(User, User.id == UserExam.user_id)
        .join(QuizExam, QuizExam.id == UserExam.exam_id)
        .filter(UserExam.id == user_exam_id)
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Result not found")
    ue, u, e = row

    total_answered = (
        db.query(func.count(UserAnswer.id))
        .filter(UserAnswer.user_id == u.id, UserAnswer.exam_id == e.id, UserAnswer.user_exam_id == ue.id, UserAnswer.is_attempt_question == "1")
        .scalar()
        or 0
    )
    total_correct = (
        db.query(func.count(UserAnswer.id))
        .filter(UserAnswer.user_id == u.id, UserAnswer.exam_id == e.id, UserAnswer.user_exam_id == ue.id, UserAnswer.is_correct_answer == "1")
        .scalar()
        or 0
    )
    total_wrong = (
        db.query(func.count(UserAnswer.id))
        .filter(
            UserAnswer.user_id == u.id,
            UserAnswer.exam_id == e.id,
            UserAnswer.user_exam_id == ue.id,
            UserAnswer.is_correct_answer == "0",
            UserAnswer.is_attempt_question == "1",
        )
        .scalar()
        or 0
    )
    total_questions = 0
    try:
        total_questions = int(e.total_questions or 0)
    except Exception:
        total_questions = 0
    if not total_questions and ue.exam_question_id:
        total_questions = len([x for x in (ue.exam_question_id or "").split(",") if x.strip()])

    pdf_bytes = quiz_result_pdf(
        user_email=u.email or "",
        exam_title=e.title or "",
        total_questions=total_questions,
        total_answered=int(total_answered),
        total_correct=int(total_correct),
        total_wrong=int(total_wrong),
        total_marks=float(ue.marks or 0.0),
        user_name=u.name,
    )

    filename = f"quiz_result_{user_exam_id}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
