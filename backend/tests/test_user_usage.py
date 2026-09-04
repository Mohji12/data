"""Unit tests for consolidated student usage helpers."""

from app.services.user_usage import max_activity_at


def test_max_activity_at_empty():
    assert max_activity_at() is None
    assert max_activity_at(None, "", None) is None


def test_max_activity_at_picks_latest():
    assert max_activity_at(
        "2026-01-01T10:00:00",
        "2026-03-15T12:00:00",
        "2026-02-01T08:00:00",
    ) == "2026-03-15T12:00:00"


def test_max_activity_at_ignores_invalid():
    result = max_activity_at("not-a-date", "2026-05-01T00:00:00")
    assert result == "2026-05-01T00:00:00"
