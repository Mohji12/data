"""Unit tests for admin exam/mock-test analytics helpers."""

from types import SimpleNamespace

from app.services.exam_analytics import (
    attempt_no_map,
    rollup_exams,
    score_percent,
    summarize_exam_attempts,
)


def test_score_percent():
    assert score_percent(0, 100) == 0
    assert score_percent(50, 100) == 50
    assert score_percent(75.4, 100) == 75
    assert score_percent(1, 0) is None
    assert score_percent(None, 10) == 0


def test_summarize_exam_attempts_empty():
    assert summarize_exam_attempts([]) == {
        "exams_attempted": 0,
        "tests_done": 0,
        "mock_tests_completed": 0,
        "in_progress_count": 0,
        "avg_score_percent": None,
        "best_score_percent": None,
    }


def test_summarize_exam_attempts_mixed():
    attempts = [
        {"exam_id": 1, "is_finished": True, "score_percent": 80},
        {"exam_id": 1, "is_finished": False, "score_percent": None},
        {"exam_id": 2, "is_finished": True, "score_percent": 60},
        {"exam_id": 3, "is_finished": False, "score_percent": None},
    ]
    summary = summarize_exam_attempts(attempts)
    assert summary["exams_attempted"] == 3
    assert summary["tests_done"] == 2
    assert summary["mock_tests_completed"] == 2
    assert summary["in_progress_count"] == 2
    assert summary["avg_score_percent"] == 70
    assert summary["best_score_percent"] == 80


def test_attempt_no_map():
    rows = [
        SimpleNamespace(id=10, user_id=1, exam_id=5),
        SimpleNamespace(id=11, user_id=1, exam_id=5),
        SimpleNamespace(id=12, user_id=1, exam_id=7),
    ]
    m = attempt_no_map(rows)  # type: ignore[arg-type]
    assert m[10] == 1
    assert m[11] == 2
    assert m[12] == 1


def test_rollup_exams_multi_attempt():
    attempts = [
        {
            "user_exam_id": 1,
            "exam_id": 5,
            "exam_title": "Mock A",
            "is_finished": True,
            "score_percent": 40,
            "marks": 40,
        },
        {
            "user_exam_id": 2,
            "exam_id": 5,
            "exam_title": "Mock A",
            "is_finished": True,
            "score_percent": 70,
            "marks": 70,
        },
        {
            "user_exam_id": 3,
            "exam_id": 5,
            "exam_title": "Mock A",
            "is_finished": False,
            "score_percent": None,
            "marks": 0,
        },
        {
            "user_exam_id": 4,
            "exam_id": 9,
            "exam_title": "Mock B",
            "is_finished": True,
            "score_percent": 90,
            "marks": 90,
        },
    ]
    exams = rollup_exams(attempts)
    by_id = {e["exam_id"]: e for e in exams}
    assert by_id[5]["attempts_count"] == 3
    assert by_id[5]["completed_count"] == 2
    assert by_id[5]["best_score_percent"] == 70
    assert by_id[5]["latest_score_percent"] == 70
    assert by_id[9]["best_score_percent"] == 90
    assert by_id[9]["latest_score_percent"] == 90
