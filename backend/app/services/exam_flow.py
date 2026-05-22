from __future__ import annotations

from datetime import datetime
from typing import Iterable, List, Sequence, Tuple

from sqlalchemy.orm import Session
from sqlalchemy import text

from app.models import MarkingType, Question, QuizExam, UserAnswer, UserExam


def parse_id_list(id_list: str) -> List[int]:
    if not id_list:
        return []
    return [int(x) for x in id_list.split(",") if x]


def build_exam_question_list(db: Session, exam: QuizExam) -> List[int]:
    """
    Re-implements the PHP query that orders questions by section display_order then id.
    """
    section_ids = exam.section_id
    if not section_ids:
        return []

    sql = """
        SELECT GROUP_CONCAT(q.id ORDER BY qs.display_order, q.id) AS question_id_list
        FROM questions q
        JOIN quiz_section qs ON qs.id = q.section_id
        WHERE q.section_id IN ({section_ids})
          AND q.status = '1'
        ORDER BY qs.display_order ASC
    """.format(
        section_ids=section_ids
    )
    result = db.execute(text(sql))  # type: ignore[arg-type]
    row = result.fetchone()
    if not row or not row.question_id_list:
        return []
    return parse_id_list(row.question_id_list)


def get_question_id_by_display(question_ids: Sequence[int], display_question_id: int) -> int:
    index = display_question_id - 1
    if index < 0 or index >= len(question_ids):
        raise IndexError("display_question_id out of range")
    return question_ids[index]


def calculate_marks(
    question: Question,
    marking_type: MarkingType,
    submitted_answer: str | None,
) -> Tuple[bool, float, float]:
    """
    Port of the PHP marking logic for R, C, and MTF questions.
    Returns (is_correct, marks, negative_mark).
    """
    if submitted_answer is None:
        submitted_answer = ""
    submitted_answer = submitted_answer.strip().upper()
    correct_answer = (question.answer or "").strip().upper()

    is_correct = False
    marks = 0.0
    negative_mark = 0.0

    if question.answer_type == "R":
        if submitted_answer and submitted_answer == correct_answer:
            is_correct = True
            marks = float(marking_type.total_correct_answer_mark or 0.0)
        else:
            negative_mark = float(marking_type.negative_mark or 0.0)

    elif question.answer_type == "C":
        correct_count = 0
        if submitted_answer:
            answers = submitted_answer.split(",")
            for ans in answers:
                ans = ans.strip().upper()
                if ans and ans in correct_answer:
                    correct_count += 1

        if submitted_answer and submitted_answer == correct_answer:
            is_correct = True
            marks = float(marking_type.total_correct_answer_mark or 0.0)
        else:
            if (
                correct_count > 0
                and marking_type.minimum_correct_answer
                and correct_count == marking_type.minimum_correct_answer
            ):
                is_correct = True
                marks = float(marking_type.minimum_correct_answer_mark or 0.0)
            else:
                negative_mark = float(marking_type.negative_mark or 0.0)

    elif question.answer_type == "MTF":
        total_option = question.total_option or 0
        options = ["A", "B", "C", "D", "E"]
        correct_count = 0
        if total_option > 0:
            for i in range(total_option):
                key = options[i]
                if key in correct_answer:
                    if submitted_answer and key in submitted_answer:
                        correct_count += 1
                else:
                    if not submitted_answer or key not in submitted_answer:
                        correct_count += 1

        if correct_count > 0:
            if marking_type.total_correct_answer and correct_count >= marking_type.total_correct_answer:
                is_correct = True
                marks = float(marking_type.total_correct_answer_mark or 0.0)
            elif (
                marking_type.minimum_correct_answer
                and correct_count >= marking_type.minimum_correct_answer
            ):
                is_correct = True
                marks = float(marking_type.minimum_correct_answer_mark or 0.0)
            else:
                negative_mark = float(marking_type.negative_mark or 0.0)
        else:
            negative_mark = float(marking_type.negative_mark or 0.0)

    return is_correct, marks, negative_mark


def get_remaining_seconds(user_exam: UserExam) -> int:
    if not user_exam.end_date:
        return 0
    
    if user_exam.is_paused == '1':
        return user_exam.remaining_seconds or 0

    now = datetime.utcnow()
    delta = (user_exam.end_date - now).total_seconds()
    return max(0, int(delta))

