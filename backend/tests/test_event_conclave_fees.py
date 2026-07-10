"""Tests for ICU-ID Conclave registration fees."""

from __future__ import annotations

from datetime import date

import pytest

from app.services.event_conclave_fees import (
    compute_event_fee_breakdown,
    early_bird_period_label,
    registration_open_for_date,
)


@pytest.mark.parametrize(
    ("on_date", "expected"),
    [
        (date(2026, 7, 8), True),
        (date(2026, 6, 1), True),
        (date(2026, 7, 9), True),
        (date(2026, 7, 10), True),
        (date(2026, 7, 11), True),
        (date(2026, 7, 12), True),
        (date(2026, 7, 13), False),
        (date(2026, 5, 1), True),
    ],
)
def test_registration_open_for_date(on_date: date, expected: bool) -> None:
    assert registration_open_for_date(on_date) is expected


@pytest.mark.parametrize(
    ("on_date", "category", "base", "gst", "total"),
    [
        (date(2026, 6, 10), "student", 2700.0, 486.0, 3186.0),
        (date(2026, 6, 10), "clinician", 3200.0, 576.0, 3776.0),
        (date(2026, 7, 9), "student", 2700.0, 486.0, 3186.0),
        (date(2026, 7, 9), "clinician", 3200.0, 576.0, 3776.0),
        (date(2026, 7, 11), "student", 2700.0, 486.0, 3186.0),
        (date(2026, 7, 11), "clinician", 3200.0, 576.0, 3776.0),
        (date(2026, 7, 12), "student", 2700.0, 486.0, 3186.0),
        (date(2026, 7, 12), "clinician", 3200.0, 576.0, 3776.0),
    ],
)
def test_compute_event_fee_totals(
    on_date: date,
    category: str,
    base: float,
    gst: float,
    total: float,
) -> None:
    row = compute_event_fee_breakdown(category, on_date=on_date)
    assert row["base_fee_inr"] == base
    assert row["gst_amount_inr"] == gst
    assert row["total_fee_inr"] == total
    assert row["fee_inr"] == total
    assert row["fee_label"] == early_bird_period_label()
    assert "tier" not in row
    assert "tier_label" not in row


def test_early_bird_period_label() -> None:
    assert early_bird_period_label() == "Early Bird (up to 12 Jul 2026)"


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
