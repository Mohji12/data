"""Unit tests for video watch progress helpers and KPI math."""

from app.services.video_progress import (
    MAX_DELTA_SECONDS,
    WATCHED_THRESHOLD_SECONDS,
    clamp_delta_seconds,
    folder_remaining,
    hours_from_seconds,
    is_video_watched,
    summarize_admin_video_progress,
    watched_minutes_from_seconds,
)


def test_clamp_delta_rejects_negative_and_huge():
    assert clamp_delta_seconds(-5) == 0
    assert clamp_delta_seconds(None) == 0
    assert clamp_delta_seconds("x") == 0  # type: ignore[arg-type]
    assert clamp_delta_seconds(15) == 15
    assert clamp_delta_seconds(100) == MAX_DELTA_SECONDS


def test_is_video_watched_threshold():
    assert is_video_watched(0) is False
    assert is_video_watched(599) is False
    assert is_video_watched(600) is True
    assert is_video_watched(900) is True
    assert WATCHED_THRESHOLD_SECONDS == 600


def test_hours_from_seconds():
    assert hours_from_seconds(0) == 0.0
    assert hours_from_seconds(1800) == 0.5
    assert hours_from_seconds(3600) == 1.0
    assert hours_from_seconds(5400) == 1.5


def test_watched_minutes_from_seconds():
    assert watched_minutes_from_seconds(0) == 0.0
    assert watched_minutes_from_seconds(30) == 0.5
    assert watched_minutes_from_seconds(90) == 1.5
    assert watched_minutes_from_seconds(600) == 10.0


def test_folder_remaining():
    assert folder_remaining(5, 4) == 1
    assert folder_remaining(5, 5) == 0
    assert folder_remaining(5, 0) == 5
    assert folder_remaining(3, 10) == 0


def test_summarize_admin_video_progress_empty():
    summary = summarize_admin_video_progress([])
    assert summary == {
        "videos_with_progress": 0,
        "videos_watched": 0,
        "total_watched_seconds": 0,
        "hours_spent": 0.0,
        "watched_threshold_seconds": 600,
    }


def test_summarize_admin_video_progress_mixed():
    videos = [
        {"watched_seconds": 0},
        {"watched_seconds": 120},
        {"watched_seconds": 599},
        {"watched_seconds": 600},
        {"watched_seconds": 3600},
    ]
    summary = summarize_admin_video_progress(videos)
    assert summary["videos_with_progress"] == 4  # excludes 0
    assert summary["videos_watched"] == 2  # 600 and 3600
    assert summary["total_watched_seconds"] == 0 + 120 + 599 + 600 + 3600
    assert summary["hours_spent"] == hours_from_seconds(summary["total_watched_seconds"])
    assert summary["watched_threshold_seconds"] == 600
