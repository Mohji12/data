from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Question, QuizExam, UserAnswer, UserExam, MarkingType, User
from app.security import get_current_user
from app.services.access import can_access_mock_test
from app.services.batch_match import find_in_set_sql
from app.schemas import (
    AnswerSubmitRequest,
    AnswerSubmitResponse,
    AttemptState,
    ExamDetail,
    ExamSummary,
    QuestionOption,
    QuestionPayload,
    ResultSummary,
    QuestionReview,
    AllQuestionsResponse,
    AttemptSummary,
)
from app.services.exam_flow import (
    build_exam_question_list,
    calculate_marks,
    get_question_id_by_display,
    get_remaining_seconds,
    parse_id_list,
)
from app.services.pdfs import build_quiz_review_pdf


router = APIRouter(prefix="/exams", tags=["exams"])
MAX_EXAM_ATTEMPTS = 2


def _ensure_exam_access(db: Session, user: User) -> None:
    allowed, reason = can_access_mock_test(db, user)
    if not allowed:
        raise HTTPException(status_code=403, detail=reason or "Mock test access denied.")


def _get_exam_or_404(db: Session, exam_id: int) -> QuizExam:
    exam = db.query(QuizExam).filter(
        QuizExam.id == exam_id,
        QuizExam.status == "1",
    ).first()
    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found")
    return exam


def _create_user_exam_attempt(
    db: Session,
    exam: QuizExam,
    user_id: int,
) -> UserExam:
    start_date = datetime.utcnow()
    minutes = exam.timer_time or 180
    end_date = start_date + timedelta(minutes=minutes)
    question_ids = build_exam_question_list(db, exam)
    exam_question_id = ",".join(str(qid) for qid in question_ids)

    ue = UserExam(
        user_id=user_id,
        exam_id=exam.id,
        exam_question_id=exam_question_id,
        start_date=start_date,
        end_date=end_date,
        is_finish_exam="0",
    )
    db.add(ue)
    db.commit()
    db.refresh(ue)
    return ue


def _list_user_exam_attempts(
    db: Session,
    exam_id: int,
    user_id: int,
) -> List[UserExam]:
    return (
        db.query(UserExam)
        .filter(UserExam.user_id == user_id, UserExam.exam_id == exam_id)
        .order_by(UserExam.id.asc())
        .all()
    )


def _find_active_attempt(attempts: List[UserExam]) -> Optional[UserExam]:
    for ue in reversed(attempts):
        if ue.is_finish_exam != "1":
            return ue
    return None


def _attempt_number(attempts: List[UserExam], attempt: UserExam) -> int:
    for idx, item in enumerate(attempts, start=1):
        if item.id == attempt.id:
            return idx
    return len(attempts) or 1


def _answer_filter_for_attempt(user_id: int, exam_id: int, user_exam_id: int):
    return (
        UserAnswer.user_id == user_id,
        UserAnswer.exam_id == exam_id,
        UserAnswer.user_exam_id == user_exam_id,
    )


def _build_attempt_state(
    exam: QuizExam,
    ue: UserExam,
    question_ids: List[int],
    current_display_no: int,
    user_id: int,
    attempt_no: int,
    attempts_used: int,
) -> AttemptState:
    total_questions = len(question_ids)
    remaining_seconds = get_remaining_seconds(ue)
    return AttemptState(
        exam_id=exam.id,
        user_id=user_id,
        total_questions=total_questions,
        current_question_no=current_display_no,
        is_first_question=current_display_no <= 1,
        is_last_question=current_display_no >= total_questions,
        remaining_seconds=remaining_seconds,
        attempt_no=attempt_no,
        attempts_used=attempts_used,
        max_attempts=MAX_EXAM_ATTEMPTS,
        remaining_attempts=max(0, MAX_EXAM_ATTEMPTS - attempts_used),
    )


def _question_to_payload(
    question: Question,
    user_answer_value: Optional[str],
) -> QuestionPayload:
    options: List[QuestionOption] = []
    for key in ["A", "B", "C", "D", "E"]:
        field_name = f"option_{key.lower()}"
        text = getattr(question, field_name)
        if text:
            options.append(QuestionOption(key=key, text=text))

    user_answer_list: Optional[List[str]] = None
    if user_answer_value:
        user_answer_list = [v.strip().upper() for v in user_answer_value.split(",") if v.strip()]

    return QuestionPayload(
        id=question.id,
        text=question.question,
        image_url=question.question_image or None,
        marking_description=None,
        answer_type=question.answer_type,
        options=options,
        user_answer=user_answer_list,
    )


def _resolve_user_id(current_user: User, requested_user_id: Optional[int]) -> int:
    if requested_user_id is None:
        return current_user.id
    if requested_user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Cannot access another user's exam data")
    return requested_user_id


@router.get("", response_model=list[ExamSummary])
def list_exams(
    user_id: Optional[int] = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> list[ExamSummary]:
    _ensure_exam_access(db, current_user)
    user_id = _resolve_user_id(current_user, user_id)
    query = db.query(QuizExam).filter(
        QuizExam.status == "1",
    )

    if user_id:
        user = db.query(User).filter(User.id == user_id).first()
        if user and user.subscription:
            # PHP parity: FIND_IN_SET(subscription, quiz_exam.batch) — exact CSV token match
            query = query.filter(find_in_set_sql(QuizExam.batch, user.subscription.strip()))

    # Order by ID to ensure Mock Test 1, 2, etc. appear in order
    exams = query.order_by(QuizExam.id.asc()).all()
    results: list[ExamSummary] = []
    for exam in exams:
        duration_seconds = (exam.timer_time or 180) * 60
        total_questions = exam.total_questions or 0
        if not total_questions and exam.section_id:
            question_ids = build_exam_question_list(db, exam)
            total_questions = len(question_ids)

        is_finished = False
        attempts_used = 0
        has_active_attempt = False
        can_retake = False
        if user_id:
            attempts = _list_user_exam_attempts(db, exam.id, user_id)
            attempts_used = len(attempts)
            active_attempt = _find_active_attempt(attempts)
            has_active_attempt = active_attempt is not None
            can_retake = attempts_used < MAX_EXAM_ATTEMPTS
            is_finished = attempts_used >= MAX_EXAM_ATTEMPTS and active_attempt is None

        results.append(
            ExamSummary(
                id=exam.id,
                title=exam.title,
                description=exam.description,
                total_questions=total_questions,
                duration_seconds=duration_seconds,
                is_finished=is_finished,
                attempts_used=attempts_used,
                max_attempts=MAX_EXAM_ATTEMPTS,
                remaining_attempts=max(0, MAX_EXAM_ATTEMPTS - attempts_used),
                can_retake=can_retake,
                has_active_attempt=has_active_attempt,
            )
        )
    return results


@router.get("/{exam_id}", response_model=ExamDetail)
def get_exam_detail(exam_id: int, db: Session = Depends(get_db)) -> ExamDetail:
    exam = _get_exam_or_404(db, exam_id)
    duration_seconds = (exam.timer_time or 180) * 60
    question_ids = build_exam_question_list(db, exam)
    total_questions = len(question_ids)
    section_ids = parse_id_list(exam.section_id or "")
    return ExamDetail(
        id=exam.id,
        title=exam.title,
        description=exam.description,
        total_questions=total_questions,
        duration_seconds=duration_seconds,
        section_ids=section_ids,
    )


@router.post("/{exam_id}/start", response_model=AnswerSubmitResponse)
def start_exam(
    exam_id: int,
    user_id: int = Query(..., description="Temporary sessionless user id"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AnswerSubmitResponse:
    _ensure_exam_access(db, current_user)
    user_id = _resolve_user_id(current_user, user_id)
    exam = _get_exam_or_404(db, exam_id)
    attempts = _list_user_exam_attempts(db, exam.id, user_id)
    ue = _find_active_attempt(attempts)
    if not ue:
        if len(attempts) >= MAX_EXAM_ATTEMPTS:
            raise HTTPException(status_code=400, detail="Maximum attempts reached for this exam")
        ue = _create_user_exam_attempt(db, exam, user_id)
        attempts = _list_user_exam_attempts(db, exam.id, user_id)

    question_ids = parse_id_list(ue.exam_question_id or "")
    if not question_ids:
        question_ids = build_exam_question_list(db, exam)
        ue.exam_question_id = ",".join(str(qid) for qid in question_ids)
        db.commit()

    first_question_id = question_ids[0]
    question = db.query(Question).filter(Question.id == first_question_id).first()
    if not question:
        raise HTTPException(status_code=404, detail="First question not found")

    attempt_no = _attempt_number(attempts, ue)
    ua = (
        db.query(UserAnswer)
        .filter(
            *_answer_filter_for_attempt(user_id, exam.id, ue.id),
            UserAnswer.question_id == question.id,
        )
        .first()
    )
    user_answer_value = ua.answer if ua else None

    question_payload = _question_to_payload(question, user_answer_value)
    attempt_state = _build_attempt_state(
        exam=exam,
        ue=ue,
        question_ids=question_ids,
        current_display_no=1,
        user_id=user_id,
        attempt_no=attempt_no,
        attempts_used=len(attempts),
    )

    total_marks = (
        db.query(func.coalesce(func.sum(UserAnswer.marks - UserAnswer.negative_mark), 0.0))
        .filter(*_answer_filter_for_attempt(user_id, exam.id, ue.id))
        .scalar()
    )

    return AnswerSubmitResponse(
        finish_exam=False,
        total_user_marks=float(total_marks or 0.0),
        attempt=attempt_state,
        question=question_payload,
    )


@router.get("/{exam_id}/question", response_model=AnswerSubmitResponse)
def get_question(
    exam_id: int,
    user_id: int = Query(...),
    display_question_id: int = Query(..., ge=1),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AnswerSubmitResponse:
    _ensure_exam_access(db, current_user)
    user_id = _resolve_user_id(current_user, user_id)
    exam = _get_exam_or_404(db, exam_id)
    attempts = _list_user_exam_attempts(db, exam.id, user_id)
    ue = _find_active_attempt(attempts)
    if not ue:
        raise HTTPException(status_code=400, detail="No active exam attempt. Please start exam.")
    attempt_no = _attempt_number(attempts, ue)

    question_ids = parse_id_list(ue.exam_question_id or "")
    if not question_ids:
        raise HTTPException(status_code=400, detail="Exam has no questions")

    try:
        question_id = get_question_id_by_display(question_ids, display_question_id)
    except IndexError:
        raise HTTPException(status_code=400, detail="Question number out of range")

    question = db.query(Question).filter(Question.id == question_id).first()
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")

    ua = (
        db.query(UserAnswer)
        .filter(
            *_answer_filter_for_attempt(user_id, exam.id, ue.id),
            UserAnswer.question_id == question.id,
        )
        .first()
    )
    user_answer_value = ua.answer if ua else None

    question_payload = _question_to_payload(question, user_answer_value)
    attempt_state = _build_attempt_state(
        exam=exam,
        ue=ue,
        question_ids=question_ids,
        current_display_no=display_question_id,
        user_id=user_id,
        attempt_no=attempt_no,
        attempts_used=len(attempts),
    )

    total_marks = (
        db.query(func.coalesce(func.sum(UserAnswer.marks - UserAnswer.negative_mark), 0.0))
        .filter(*_answer_filter_for_attempt(user_id, exam.id, ue.id))
        .scalar()
    )

    return AnswerSubmitResponse(
        finish_exam=False,
        total_user_marks=float(total_marks or 0.0),
        attempt=attempt_state,
        question=question_payload,
    )


@router.post("/{exam_id}/pause")
def pause_exam(
    exam_id: int,
    user_id: int = Query(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _ensure_exam_access(db, current_user)
    user_id = _resolve_user_id(current_user, user_id)
    exam = _get_exam_or_404(db, exam_id)
    attempts = _list_user_exam_attempts(db, exam.id, user_id)
    ue = _find_active_attempt(attempts)
    if not ue:
        raise HTTPException(status_code=400, detail="No active exam attempt to pause")
    
    if ue.is_paused == '1':
        return {"status": "already paused", "remaining_seconds": ue.remaining_seconds}
    
    # Calculate remaining time
    rem = get_remaining_seconds(ue)
    ue.remaining_seconds = rem
    ue.is_paused = '1'
    db.commit()
    
    return {"status": "paused", "remaining_seconds": rem}


@router.post("/{exam_id}/resume")
def resume_exam(
    exam_id: int,
    user_id: int = Query(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _ensure_exam_access(db, current_user)
    user_id = _resolve_user_id(current_user, user_id)
    exam = _get_exam_or_404(db, exam_id)
    attempts = _list_user_exam_attempts(db, exam.id, user_id)
    ue = _find_active_attempt(attempts)
    if not ue:
        raise HTTPException(status_code=400, detail="No active exam attempt to resume")
    
    if ue.is_paused == '0':
        return {"status": "already running", "remaining_seconds": get_remaining_seconds(ue)}
    
    # Set new end_date
    rem = ue.remaining_seconds or 0
    ue.end_date = datetime.utcnow() + timedelta(seconds=rem)
    ue.is_paused = '0'
    db.commit()
    
    return {"status": "resumed", "remaining_seconds": rem}


@router.get("/{exam_id}/all-questions", response_model=AllQuestionsResponse)
def get_all_questions(
    exam_id: int,
    user_id: int = Query(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AllQuestionsResponse:
    _ensure_exam_access(db, current_user)
    user_id = _resolve_user_id(current_user, user_id)
    exam = _get_exam_or_404(db, exam_id)
    attempts = _list_user_exam_attempts(db, exam.id, user_id)
    ue = _find_active_attempt(attempts)
    if not ue:
        raise HTTPException(status_code=400, detail="No active exam attempt")
    attempt_no = _attempt_number(attempts, ue)

    question_ids = parse_id_list(ue.exam_question_id or "")
    if not question_ids:
        raise HTTPException(status_code=400, detail="Exam has no questions")

    # Fetch all questions
    questions = db.query(Question).filter(Question.id.in_(question_ids)).all()
    questions_map = {q.id: q for q in questions}
    sorted_questions = [questions_map[qid] for qid in question_ids if qid in questions_map]

    # Fetch user answers
    user_answers = (
        db.query(UserAnswer)
        .filter(*_answer_filter_for_attempt(user_id, exam.id, ue.id))
        .all()
    )
    ua_map = {ua.question_id: ua for ua in user_answers}

    question_payloads = []
    for q in sorted_questions:
        ua = ua_map.get(q.id)
        user_answer_value = ua.answer if ua else None
        question_payloads.append(_question_to_payload(q, user_answer_value))

    return AllQuestionsResponse(
        exam_id=exam.id,
        exam_title=exam.title,
        attempt_no=attempt_no,
        questions=question_payloads,
        remaining_seconds=get_remaining_seconds(ue),
    )


@router.post("/{exam_id}/answer", response_model=AnswerSubmitResponse)
def submit_answer(
    exam_id: int,
    payload: AnswerSubmitRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AnswerSubmitResponse:
    _ensure_exam_access(db, current_user)
    if payload.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Cannot access another user's exam data")
    exam = _get_exam_or_404(db, exam_id)
    attempts = _list_user_exam_attempts(db, exam.id, payload.user_id)
    ue = _find_active_attempt(attempts)
    if not ue:
        raise HTTPException(status_code=400, detail="No active exam attempt")
    attempt_no = _attempt_number(attempts, ue)

    # Time check
    if get_remaining_seconds(ue) <= 0:
        ue.is_finish_exam = "1"
        db.commit()
        raise HTTPException(status_code=400, detail="Exam time is over")

    question_ids = parse_id_list(ue.exam_question_id or "")
    if not question_ids:
        raise HTTPException(status_code=400, detail="Exam has no questions")

    question = db.query(Question).filter(Question.id == payload.question_id).first()
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")

    marking_type = (
        db.query(MarkingType).filter(MarkingType.id == question.marking_type_id).first()
    )
    if not marking_type:
        raise HTTPException(status_code=400, detail="Marking type not configured")

    submitted_answer: Optional[str] = None
    if payload.answers:
        submitted_answer = ",".join(sorted(a.strip().upper() for a in payload.answers if a.strip()))

    is_correct, marks, negative_mark = calculate_marks(
        question=question,
        marking_type=marking_type,
        submitted_answer=submitted_answer,
    )

    ua = (
        db.query(UserAnswer)
        .filter(
            *_answer_filter_for_attempt(payload.user_id, exam.id, ue.id),
            UserAnswer.question_id == question.id,
        )
        .first()
    )
    if ua:
        db.delete(ua)
        db.flush()

    ua = UserAnswer(
        user_id=payload.user_id,
        exam_id=exam.id,
        user_exam_id=ue.id,
        question_id=question.id,
        answer=submitted_answer,
        is_correct_answer="1" if is_correct else "0",
        is_attempt_question="1" if submitted_answer else "0",
        marks=marks,
        negative_mark=negative_mark,
    )
    db.add(ua)
    db.commit()

    # Recalculate total marks
    total_marks = (
        db.query(func.coalesce(func.sum(UserAnswer.marks - UserAnswer.negative_mark), 0.0))
        .filter(*_answer_filter_for_attempt(payload.user_id, exam.id, ue.id))
        .scalar()
    )

    finish_exam = False
    current_display_no = (
        payload.display_question_id
        if payload.display_question_id
        else question_ids.index(question.id) + 1
    )

    next_question_payload: Optional[QuestionPayload] = None

    # Only end the attempt when the client explicitly submits the last question.
    # Saving an answer while viewing the final question must not auto-finish.
    if payload.is_last_question:
        ue.is_finish_exam = "1"
        ue.marks = float(total_marks or 0.0)
        finish_exam = True
        db.commit()
    elif current_display_no < len(question_ids):
        # Move to the next question
        current_display_no += 1
        next_question_id = get_question_id_by_display(question_ids, current_display_no)
        next_question_obj = db.query(Question).filter(Question.id == next_question_id).first()
        if not next_question_obj:
            raise HTTPException(status_code=404, detail="Next question not found")
        
        # Load user's previous answer for the next question, if any
        next_ua = (
            db.query(UserAnswer)
            .filter(
                *_answer_filter_for_attempt(payload.user_id, exam.id, ue.id),
                UserAnswer.question_id == next_question_obj.id,
            )
            .first()
        )
        next_user_answer_value = next_ua.answer if next_ua else None
        next_question_payload = _question_to_payload(next_question_obj, next_user_answer_value)

    attempt_state = _build_attempt_state(
        exam=exam,
        ue=ue,
        question_ids=question_ids,
        current_display_no=current_display_no,
        user_id=payload.user_id,
        attempt_no=attempt_no,
        attempts_used=len(attempts),
    )

    return AnswerSubmitResponse(
        finish_exam=finish_exam,
        total_user_marks=float(total_marks or 0.0),
        attempt=attempt_state,
        question=next_question_payload,
    )


def _build_result_summary_for_attempt(
    db: Session,
    exam: QuizExam,
    ue: UserExam,
    attempt_no: int,
    user_id: int,
) -> ResultSummary:
    total_marks = (
        db.query(func.coalesce(func.sum(UserAnswer.marks - UserAnswer.negative_mark), 0.0))
        .filter(*_answer_filter_for_attempt(user_id, exam.id, ue.id))
        .scalar()
    )
    total_answered = (
        db.query(func.count(UserAnswer.id))
        .filter(*_answer_filter_for_attempt(user_id, exam.id, ue.id))
        .scalar()
    )
    total_correct = (
        db.query(func.count(UserAnswer.id))
        .filter(
            *_answer_filter_for_attempt(user_id, exam.id, ue.id),
            UserAnswer.is_correct_answer == "1",
        )
        .scalar()
    )
    total_wrong = (
        db.query(func.count(UserAnswer.id))
        .filter(
            *_answer_filter_for_attempt(user_id, exam.id, ue.id),
            UserAnswer.is_correct_answer == "0",
            UserAnswer.is_attempt_question == "1",
        )
        .scalar()
    )

    question_ids = parse_id_list(ue.exam_question_id or "")
    if not question_ids:
        question_ids = build_exam_question_list(db, exam)

    questions = db.query(Question).filter(Question.id.in_(question_ids)).all()
    questions_map = {q.id: q for q in questions}
    sorted_questions = [questions_map[qid] for qid in question_ids if qid in questions_map]
    user_answers = db.query(UserAnswer).filter(*_answer_filter_for_attempt(user_id, exam.id, ue.id)).all()
    ua_map = {ua.question_id: ua for ua in user_answers}

    reviews: List[QuestionReview] = []
    for q in sorted_questions:
        ua = ua_map.get(q.id)
        options: List[QuestionOption] = []
        for key in ["A", "B", "C", "D", "E"]:
            field_name = f"option_{key.lower()}"
            text_val = getattr(q, field_name)
            if text_val:
                options.append(QuestionOption(key=key, text=text_val))
        user_answer_list = [v.strip().upper() for v in ua.answer.split(",") if v.strip()] if ua and ua.answer else []
        correct_answer_list = [v.strip().upper() for v in q.answer.split(",") if v.strip()] if q.answer else []
        reviews.append(
            QuestionReview(
                id=q.id,
                text=q.question,
                options=options,
                user_answer=user_answer_list if user_answer_list else None,
                correct_answer=correct_answer_list,
                is_correct=ua.is_correct_answer == "1" if ua else False,
                marks=float(ua.marks or 0.0) if ua else 0.0,
                negative_mark=float(ua.negative_mark or 0.0) if ua else 0.0,
            )
        )

    return ResultSummary(
        exam_id=exam.id,
        user_id=user_id,
        exam_title=exam.title,
        attempt_no=attempt_no,
        total_questions=len(question_ids),
        total_answered=int(total_answered or 0),
        total_correct=int(total_correct or 0),
        total_wrong=int(total_wrong or 0),
        total_marks=float(total_marks or 0.0),
        reviews=reviews,
    )


@router.get("/{exam_id}/results", response_model=list[AttemptSummary])
def list_attempt_results(
    exam_id: int,
    user_id: int = Query(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[AttemptSummary]:
    _ensure_exam_access(db, current_user)
    user_id = _resolve_user_id(current_user, user_id)
    _get_exam_or_404(db, exam_id)
    attempts = _list_user_exam_attempts(db, exam_id, user_id)
    out: list[AttemptSummary] = []
    for idx, ue in enumerate(attempts, start=1):
        total_answered = (
            db.query(func.count(UserAnswer.id))
            .filter(*_answer_filter_for_attempt(user_id, exam_id, ue.id))
            .scalar()
        )
        total_correct = (
            db.query(func.count(UserAnswer.id))
            .filter(
                *_answer_filter_for_attempt(user_id, exam_id, ue.id),
                UserAnswer.is_correct_answer == "1",
            )
            .scalar()
        )
        total_wrong = (
            db.query(func.count(UserAnswer.id))
            .filter(
                *_answer_filter_for_attempt(user_id, exam_id, ue.id),
                UserAnswer.is_correct_answer == "0",
                UserAnswer.is_attempt_question == "1",
            )
            .scalar()
        )
        out.append(
            AttemptSummary(
                attempt_no=idx,
                user_exam_id=ue.id,
                is_finished=ue.is_finish_exam == "1",
                marks=float(ue.marks or 0.0),
                start_date=ue.start_date,
                end_date=ue.end_date,
                total_answered=int(total_answered or 0),
                total_correct=int(total_correct or 0),
                total_wrong=int(total_wrong or 0),
            )
        )
    return out


@router.get("/{exam_id}/result", response_model=ResultSummary)
def get_result(
    exam_id: int,
    user_id: int = Query(...),
    attempt_no: Optional[int] = Query(None, ge=1),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ResultSummary:
    _ensure_exam_access(db, current_user)
    user_id = _resolve_user_id(current_user, user_id)
    exam = _get_exam_or_404(db, exam_id)
    attempts = _list_user_exam_attempts(db, exam.id, user_id)
    if not attempts:
        raise HTTPException(status_code=404, detail="No attempts found for this exam")
    if attempt_no is None:
        target_attempt_no = len(attempts)
    else:
        target_attempt_no = attempt_no
    if target_attempt_no < 1 or target_attempt_no > len(attempts):
        raise HTTPException(status_code=400, detail="Invalid attempt number")
    ue = attempts[target_attempt_no - 1]
    return _build_result_summary_for_attempt(db, exam, ue, target_attempt_no, user_id)


@router.get("/{exam_id}/result/download.pdf")
def download_result_review_pdf(
    exam_id: int,
    user_id: int = Query(...),
    attempt_no: Optional[int] = Query(None, ge=1),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    """Detailed per-question review PDF for the student result page."""
    _ensure_exam_access(db, current_user)
    user_id = _resolve_user_id(current_user, user_id)
    exam = _get_exam_or_404(db, exam_id)
    attempts = _list_user_exam_attempts(db, exam.id, user_id)
    if not attempts:
        raise HTTPException(status_code=404, detail="No attempts found for this exam")
    target_attempt_no = len(attempts) if attempt_no is None else attempt_no
    if target_attempt_no < 1 or target_attempt_no > len(attempts):
        raise HTTPException(status_code=400, detail="Invalid attempt number")
    ue = attempts[target_attempt_no - 1]

    summary = _build_result_summary_for_attempt(db, exam, ue, target_attempt_no, user_id)
    user_row = db.get(User, user_id)
    reviews_payload = [r.model_dump() for r in summary.reviews]

    pdf_bytes = build_quiz_review_pdf(
        user_email=(user_row.email if user_row else "") or current_user.email or "",
        user_name=(user_row.name if user_row else None) or current_user.name,
        exam_title=summary.exam_title,
        attempt_no=summary.attempt_no,
        total_questions=summary.total_questions,
        total_answered=summary.total_answered,
        total_correct=summary.total_correct,
        total_wrong=summary.total_wrong,
        total_marks=summary.total_marks,
        reviews=reviews_payload,
    )

    safe_title = re.sub(r"[^\w\-]+", "_", (summary.exam_title or "exam"))[:40]
    filename = f"exam_review_{exam_id}_attempt{target_attempt_no}_{safe_title}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/{exam_id}/finish", response_model=ResultSummary)
def finish_exam(
    exam_id: int,
    user_id: int = Query(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ResultSummary:
    _ensure_exam_access(db, current_user)
    user_id = _resolve_user_id(current_user, user_id)
    exam = _get_exam_or_404(db, exam_id)
    attempts = _list_user_exam_attempts(db, exam.id, user_id)
    ue = _find_active_attempt(attempts)
    if not ue:
        raise HTTPException(status_code=400, detail="No active exam attempt")
    attempt_no = _attempt_number(attempts, ue)

    ue.is_finish_exam = "1"
    ue.end_date = datetime.utcnow()

    total_marks = (
        db.query(func.coalesce(func.sum(UserAnswer.marks - UserAnswer.negative_mark), 0.0))
        .filter(*_answer_filter_for_attempt(user_id, exam.id, ue.id))
        .scalar()
    )
    ue.marks = float(total_marks or 0.0)
    db.commit()

    total_answered = (
        db.query(func.count(UserAnswer.id))
        .filter(*_answer_filter_for_attempt(user_id, exam.id, ue.id))
        .scalar()
    )
    total_correct = (
        db.query(func.count(UserAnswer.id))
        .filter(
            UserAnswer.user_id == user_id,
            UserAnswer.exam_id == exam.id,
            UserAnswer.user_exam_id == ue.id,
            UserAnswer.is_correct_answer == "1",
        )
        .scalar()
    )
    total_wrong = (
        db.query(func.count(UserAnswer.id))
        .filter(
            UserAnswer.user_id == user_id,
            UserAnswer.exam_id == exam.id,
            UserAnswer.user_exam_id == ue.id,
            UserAnswer.is_correct_answer == "0",
            UserAnswer.is_attempt_question == "1",
        )
        .scalar()
    )

    question_ids = parse_id_list(ue.exam_question_id or "")
    if not question_ids:
        question_ids = build_exam_question_list(db, exam)

    # Fetch all questions for the review
    questions = db.query(Question).filter(Question.id.in_(question_ids)).all()
    # Sort them according to question_ids order
    questions_map = {q.id: q for q in questions}
    sorted_questions = [questions_map[qid] for qid in question_ids if qid in questions_map]

    # Fetch all user answers for this exam
    user_answers = db.query(UserAnswer).filter(
        UserAnswer.user_id == user_id,
        UserAnswer.exam_id == exam.id,
        UserAnswer.user_exam_id == ue.id,
    ).all()
    ua_map = {ua.question_id: ua for ua in user_answers}

    reviews: List[QuestionReview] = []
    for q in sorted_questions:
        ua = ua_map.get(q.id)
        
        # Build options
        options: List[QuestionOption] = []
        for key in ["A", "B", "C", "D", "E"]:
            field_name = f"option_{key.lower()}"
            text_val = getattr(q, field_name)
            if text_val:
                options.append(QuestionOption(key=key, text=text_val))

        user_answer_list = [v.strip().upper() for v in ua.answer.split(",") if v.strip()] if ua and ua.answer else []
        correct_answer_list = [v.strip().upper() for v in q.answer.split(",") if v.strip()] if q.answer else []

        reviews.append(
            QuestionReview(
                id=q.id,
                text=q.question,
                options=options,
                user_answer=user_answer_list if user_answer_list else None,
                correct_answer=correct_answer_list,
                is_correct=ua.is_correct_answer == "1" if ua else False,
                marks=float(ua.marks or 0.0) if ua else 0.0,
                negative_mark=float(ua.negative_mark or 0.0) if ua else 0.0,
            )
        )

    return ResultSummary(
        exam_id=exam.id,
        user_id=user_id,
        exam_title=exam.title,
        attempt_no=attempt_no,
        total_questions=len(question_ids),
        total_answered=int(total_answered or 0),
        total_correct=int(total_correct or 0),
        total_wrong=int(total_wrong or 0),
        total_marks=float(total_marks or 0.0),
        reviews=reviews,
    )

