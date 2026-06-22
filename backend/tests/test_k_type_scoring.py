"""K-type / K-prime question scoring (4 statements, partial credit, no negative marks)."""

from app.models import MarkingType, Question
from app.services.exam_flow import (
    calculate_marks,
    count_k_type_correct_judgments,
    score_k_type_marks,
)


def _k_question(*, answer: str = "A,C", total_option: int = 4) -> Question:
    return Question(
        id=1,
        section_id=1,
        question="K-type sample",
        answer=answer,
        answer_type="K",
        total_option=total_option,
        marking_type_id=1,
        status="1",
    )


def _marking() -> MarkingType:
    return MarkingType(
        id=1,
        name="K-type",
        total_correct_answer_mark=1.0,
        minimum_correct_answer_mark=0.5,
        negative_mark=0.25,
    )


def test_k_type_full_marks():
    q = _k_question()
    is_correct, marks, negative = calculate_marks(q, _marking(), "A,C")
    assert is_correct is True
    assert marks == 1.0
    assert negative == 0.0


def test_k_type_partial_marks():
    q = _k_question()
    # Correct T,F,T,F — student T,F,T,T
    is_correct, marks, negative = calculate_marks(q, _marking(), "A,C,D")
    assert is_correct is True
    assert marks == 0.5
    assert negative == 0.0


def test_k_type_two_wrong_zero_marks():
    q = _k_question()
    is_correct, marks, negative = calculate_marks(q, _marking(), "A,B")
    assert is_correct is False
    assert marks == 0.0
    assert negative == 0.0


def test_k_type_unanswered_zero():
    q = _k_question()
    is_correct, marks, negative = calculate_marks(q, _marking(), "")
    assert is_correct is False
    assert marks == 0.0
    assert negative == 0.0


def test_k_type_unanswered_none():
    q = _k_question()
    is_correct, marks, negative = calculate_marks(q, _marking(), None)
    assert marks == 0.0
    assert negative == 0.0


def test_count_k_type_judgments():
    q = _k_question()
    assert count_k_type_correct_judgments(q, "A,C", "A,C") == 4
    assert count_k_type_correct_judgments(q, "A,C,D", "A,C") == 3
    assert count_k_type_correct_judgments(q, "A,B", "A,C") == 2


def test_score_k_type_marks_thresholds():
    assert score_k_type_marks(4, 4) == (True, 1.0)
    assert score_k_type_marks(3, 4) == (True, 0.5)
    assert score_k_type_marks(2, 4) == (False, 0.0)
