"""Multi-select / checkbox scoring: answer order must not affect marks."""

from app.models import MarkingType, Question
from app.services.exam_flow import calculate_marks, normalize_answer_csv


def _c_question(*, answer: str = "B,A,C") -> Question:
    return Question(
        id=1,
        section_id=1,
        question="Multi-correct sample",
        answer=answer,
        answer_type="C",
        total_option=4,
        marking_type_id=1,
        status="1",
    )


def _marking() -> MarkingType:
    return MarkingType(
        id=1,
        name="Checkbox",
        total_correct_answer=3,
        total_correct_answer_mark=1.0,
        minimum_correct_answer=2,
        minimum_correct_answer_mark=0.5,
        negative_mark=0.25,
    )


def test_normalize_answer_csv_sorts():
    assert normalize_answer_csv("B,A,C") == "A,B,C"
    assert normalize_answer_csv("c, a") == "A,C"


def test_c_type_full_marks_regardless_of_order():
    q = _c_question(answer="B,A,C")
    is_correct, marks, negative = calculate_marks(q, _marking(), "A,B,C")
    assert is_correct is True
    assert marks == 1.0
    assert negative == 0.0


def test_c_type_full_marks_when_db_and_submit_same_unsorted():
    q = _c_question(answer="C,A")
    is_correct, marks, negative = calculate_marks(q, _marking(), "A,C")
    assert is_correct is True
    assert marks == 1.0


def test_c_type_partial_when_more_than_minimum():
    """Selecting 2+ correct options (but not the full set) should get partial credit."""
    q = _c_question(answer="A,B,C")
    is_correct, marks, negative = calculate_marks(q, _marking(), "A,B")
    assert is_correct is True
    assert marks == 0.5
    assert negative == 0.0


def test_r_type_exact_letter():
    q = Question(
        id=2,
        section_id=1,
        question="Single",
        answer="B",
        answer_type="R",
        total_option=4,
        marking_type_id=1,
        status="1",
    )
    is_correct, marks, negative = calculate_marks(q, _marking(), "B")
    assert is_correct is True
    assert marks == 1.0
    assert negative == 0.0
