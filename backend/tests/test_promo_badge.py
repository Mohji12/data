"""Unit tests for site promo badge days_left / active logic."""

from datetime import date, datetime, timedelta, timezone

from app.services.promo_badge import (
    build_promo_badge_payload,
    days_remaining_for_valid_till,
)

IST = timezone(timedelta(hours=5, minutes=30))


def test_days_remaining_on_valid_till_day_before_eod():
    valid = date(2026, 9, 16)
    now = datetime(2026, 9, 16, 10, 0, 0, tzinfo=IST)
    assert days_remaining_for_valid_till(valid, now=now) == 1


def test_days_remaining_multi_day():
    valid = date(2026, 9, 16)
    now = datetime(2026, 9, 13, 12, 0, 0, tzinfo=IST)
    # End of Sept 16 IST from midday Sept 13 => ceil ~ 3.5 days => 4
    assert days_remaining_for_valid_till(valid, now=now) == 4


def test_days_remaining_expired():
    valid = date(2026, 9, 16)
    now = datetime(2026, 9, 17, 0, 0, 1, tzinfo=IST)
    assert days_remaining_for_valid_till(valid, now=now) == 0


def test_payload_active_with_defaults_style():
    now = datetime(2026, 9, 4, 12, 0, 0, tzinfo=IST)
    payload = build_promo_badge_payload(
        pct_raw="25",
        description_raw="discount",
        valid_till_raw="2026-09-16",
        now=now,
    )
    assert payload["active"] is True
    assert payload["discount_pct"] == 25
    assert payload["description"] == "discount"
    assert payload["valid_till"] == "2026-09-16"
    assert payload["days_left"] > 0


def test_payload_inactive_when_pct_zero():
    payload = build_promo_badge_payload(
        pct_raw="0",
        description_raw="discount",
        valid_till_raw="2026-09-16",
        now=datetime(2026, 9, 4, 12, 0, 0, tzinfo=IST),
    )
    assert payload["active"] is False
    assert payload["days_left"] == 0


def test_payload_inactive_when_expired():
    payload = build_promo_badge_payload(
        pct_raw="25",
        description_raw="Early bird",
        valid_till_raw="2026-09-16",
        now=datetime(2026, 9, 17, 1, 0, 0, tzinfo=IST),
    )
    assert payload["active"] is False
    assert payload["days_left"] == 0
    assert payload["description"] == "Early bird"


def test_payload_inactive_when_invalid_date():
    payload = build_promo_badge_payload(
        pct_raw="25",
        description_raw="discount",
        valid_till_raw="not-a-date",
        now=datetime(2026, 9, 4, 12, 0, 0, tzinfo=IST),
    )
    assert payload["active"] is False
    assert payload["valid_till"] is None
