"""Tests for ICU-ID Conclave tiered registration fees."""

from __future__ import annotations

from datetime import date

import pytest

from app.services.event_conclave_fees import (
    compute_event_fee_breakdown,
    registration_open_for_date,
    resolve_event_fee_tier,
)


@pytest.mark.parametrize(
    ("on_date", "expected"),
    [
        (date(2026, 7, 8), "early_bird"),
        (date(2026, 6, 1), "early_bird"),
        (date(2026, 6, 27), "early_bird"),
        (date(2026, 7, 9), "regular"),
        (date(2026, 7, 10), "regular"),
        (date(2026, 7, 11), "spot"),
        (date(2026, 7, 12), "spot"),
        (date(2026, 7, 13), None),
        (date(2026, 5, 1), "early_bird"),
    ],
)
def test_resolve_event_fee_tier(on_date: date, expected: str | None) -> None:
    assert resolve_event_fee_tier(on_date) == expected
    assert registration_open_for_date(on_date) == (expected is not None)


@pytest.mark.parametrize(
    ("tier_date", "category", "base", "gst", "total"),
    [
        (date(2026, 6, 10), "student", 2700.0, 486.0, 3186.0),
        (date(2026, 6, 10), "clinician", 3200.0, 576.0, 3776.0),
        (date(2026, 7, 9), "student", 3500.0, 630.0, 4130.0),
        (date(2026, 7, 9), "clinician", 4000.0, 720.0, 4720.0),
        (date(2026, 7, 11), "student", 4000.0, 720.0, 4720.0),
        (date(2026, 7, 11), "clinician", 4500.0, 810.0, 5310.0),
    ],
)
def test_compute_event_fee_totals(
    tier_date: date,
    category: str,
    base: float,
    gst: float,
    total: float,
) -> None:
    row = compute_event_fee_breakdown(category, on_date=tier_date)
    assert row["base_fee_inr"] == base
    assert row["gst_amount_inr"] == gst
    assert row["total_fee_inr"] == total
    assert row["fee_inr"] == total


def test_registration_closed_raises() -> None:
    with pytest.raises(ValueError, match="registration_closed"):
        compute_event_fee_breakdown("student", on_date=date(2026, 7, 13))


def test_invalid_category_raises() -> None:
    with pytest.raises(ValueError, match="Invalid category"):
        compute_event_fee_breakdown("invalid", on_date=date(2026, 6, 10))


def test_promo_zeroes_total(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.services.event_conclave_fees.event_promo_codes",
        lambda: {"TESTFREE"},
    )
    row = compute_event_fee_breakdown("student", on_date=date(2026, 6, 10), promo_code="testfree")
    assert row["promo_applied"] is True
    assert row["total_fee_inr"] == 0.0


def test_invalid_promo_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.services.event_conclave_fees.event_promo_codes",
        lambda: {"TESTFREE"},
    )
    row = compute_event_fee_breakdown("student", on_date=date(2026, 6, 10), promo_code="BAD")
    assert row["promo_invalid"] is True
    assert row["total_fee_inr"] == 3186.0
