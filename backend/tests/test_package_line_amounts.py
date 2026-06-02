"""Tests for tier package payable amount resolution."""
from datetime import date
from types import SimpleNamespace

from app.services.registration import _resolve_package_line_amounts


def _pkg(**kwargs):
    defaults = {
        "gross_amount": 15000.0,
        "gst_percentage": 18.0,
        "gst_amount": 2700.0,
        "total_amount": 17700.0,
        "discounted_amount": 0.0,
        "discount_percentage": 0.0,
        "discount_start_date": None,
        "discount_end_date": None,
        "plan_type": "one_time",
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def test_cp_tier_uses_gross_plus_gst():
    pkg = _pkg(total_amount=17700.0, gst_amount=2700.0)
    _, _, _, total = _resolve_package_line_amounts(pkg, today=date(2026, 6, 2))
    assert total == 17700.0


def test_edic_tier_uses_stored_total_even_when_discount_window_expired():
    """EDIC 20%% early bird: stored 14160 must not revert to 17700 after discount_end."""
    pkg = _pkg(
        total_amount=14160.0,
        gst_amount=2430.0,
        discounted_amount=3000.0,
        discount_percentage=20.0,
        discount_start_date=date(2026, 5, 26),
        discount_end_date=date(2026, 5, 31),
    )
    _, _, _, total = _resolve_package_line_amounts(pkg, today=date(2026, 6, 2))
    assert total == 14160.0


def test_edic_extended_tier_stored_total():
    pkg = _pkg(
        total_amount=15930.0,
        gst_amount=2430.0,
        discounted_amount=1500.0,
        discount_percentage=10.0,
        discount_start_date=date(2026, 6, 1),
        discount_end_date=date(2026, 6, 15),
    )
    _, _, _, total = _resolve_package_line_amounts(pkg, today=date(2026, 6, 2))
    assert total == 15930.0


def test_subscription_promo_still_applies():
    pkg = _pkg(
        plan_type="subscription",
        total_amount=9000.0,
        gst_amount=1370.0,
        discounted_amount=1000.0,
        discount_percentage=10.0,
        discount_start_date=date(2026, 6, 1),
        discount_end_date=date(2026, 6, 30),
    )
    _, _, _, total = _resolve_package_line_amounts(pkg, today=date(2026, 6, 2))
    assert total == 9000.0
