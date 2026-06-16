"""ICU-ID Conclave 2026 tiered registration fees (category + date window)."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any, Literal

from app.core.config import get_settings

# India Standard Time (UTC+5:30, no DST). Fixed offset avoids ZoneInfo/tzdata on Windows.
IST = timezone(timedelta(hours=5, minutes=30))

EventFeeTier = Literal["early_bird", "regular", "spot"]
EventCategory = Literal["student", "clinician"]

VALID_CATEGORIES = frozenset({"student", "clinician"})

EARLY_BIRD_END = date(2026, 6, 26)
REGULAR_START = date(2026, 6, 27)
REGULAR_END = date(2026, 7, 10)
SPOT_START = date(2026, 7, 11)
SPOT_END = date(2026, 7, 12)

# Base fee INR per tier and category (GST applied separately).
FEE_BASE_INR: dict[EventFeeTier, dict[EventCategory, float]] = {
    "early_bird": {"student": 2700.0, "clinician": 3200.0},
    "regular": {"student": 3500.0, "clinician": 4000.0},
    "spot": {"student": 4000.0, "clinician": 4500.0},
}

TIER_LABELS: dict[EventFeeTier, str] = {
    "early_bird": "Early Bird (valid up to 26th June 2026)",
    "regular": "Regular (27th June 2026 to 10th July 2026)",
    "spot": "Spot registration (11th & 12th July 2026)",
}

TIER_WINDOWS: dict[EventFeeTier, str] = {
    "early_bird": "Valid up to 26th June 2026",
    "regular": "27th June 2026 to 10th July 2026",
    "spot": "11th & 12th July 2026",
}


def event_today_ist(on_date: date | None = None) -> date:
    if on_date is not None:
        return on_date
    return datetime.now(IST).date()


def resolve_event_fee_tier(on_date: date | None = None) -> EventFeeTier | None:
    """Return active pricing tier for the given calendar day (IST), or None if registration is closed."""
    d = event_today_ist(on_date)
    if d <= EARLY_BIRD_END:
        return "early_bird"
    if REGULAR_START <= d <= REGULAR_END:
        return "regular"
    if SPOT_START <= d <= SPOT_END:
        return "spot"
    return None


def registration_open_for_date(on_date: date | None = None) -> bool:
    return resolve_event_fee_tier(on_date) is not None


def _gst_percent() -> float:
    return float(get_settings().event_icu_d_conclave_gst_percent or 18)


def _breakdown_from_base(
    base: float,
    *,
    gst_percent: float,
    tier: EventFeeTier,
    category: EventCategory,
) -> dict[str, Any]:
    gst_amount = round(base * gst_percent / 100, 2)
    total = round(base + gst_amount, 2)
    return {
        "tier": tier,
        "tier_label": TIER_LABELS[tier],
        "tier_window": TIER_WINDOWS[tier],
        "category": category,
        "base_fee_inr": base,
        "gst_percent": gst_percent,
        "gst_amount_inr": gst_amount,
        "total_fee_inr": total,
        "fee_inr": total,
    }


def compute_event_fee_breakdown(
    category: str,
    *,
    on_date: date | None = None,
    promo_code: str | None = None,
    promo_codes: set[str] | None = None,
) -> dict[str, Any]:
    """
    Compute payable amounts for a category on a given day.
    Raises ValueError for invalid category or closed registration window.
    """
    cat = (category or "").strip().lower()
    if cat not in VALID_CATEGORIES:
        raise ValueError("Invalid category")

    tier = resolve_event_fee_tier(on_date)
    if tier is None:
        raise ValueError("registration_closed")

    base = FEE_BASE_INR[tier][cat]  # type: ignore[index]
    fees = _breakdown_from_base(base, gst_percent=_gst_percent(), tier=tier, category=cat)  # type: ignore[arg-type]
    return _apply_promo_to_fees(fees, promo_code, promo_codes=promo_codes)


def event_promo_codes() -> set[str]:
    return set(get_settings().event_icu_d_conclave_promo_codes or [])


def is_valid_event_promo(promo_code: str | None, codes: set[str] | None = None) -> bool:
    code = (promo_code or "").strip().upper()
    if not code:
        return False
    allowed = codes if codes is not None else event_promo_codes()
    return code in allowed


def _apply_promo_to_fees(
    fees: dict[str, Any],
    promo_code: str | None,
    *,
    promo_codes: set[str] | None = None,
) -> dict[str, Any]:
    codes = promo_codes if promo_codes is not None else event_promo_codes()
    code = (promo_code or "").strip()
    if not code:
        return {**fees, "promo_applied": False, "promo_code": "", "promo_invalid": False}
    if not is_valid_event_promo(code, codes):
        return {**fees, "promo_applied": False, "promo_code": code, "promo_invalid": True}
    gst_percent = float(fees.get("gst_percent") or 18)
    return {
        **fees,
        "base_fee_inr": 0.0,
        "gst_percent": gst_percent,
        "gst_amount_inr": 0.0,
        "total_fee_inr": 0.0,
        "fee_inr": 0.0,
        "promo_applied": True,
        "promo_code": code.upper(),
        "promo_invalid": False,
    }


def build_fee_schedule_table() -> dict[str, dict[str, dict[str, float]]]:
    """Full fee table for all tiers and categories (for public config UI)."""
    gst_percent = _gst_percent()
    out: dict[str, dict[str, dict[str, float]]] = {}
    for tier in ("early_bird", "regular", "spot"):
        out[tier] = {}
        for cat in ("student", "clinician"):
            row = _breakdown_from_base(
                FEE_BASE_INR[tier][cat],  # type: ignore[index]
                gst_percent=gst_percent,
                tier=tier,  # type: ignore[arg-type]
                category=cat,  # type: ignore[arg-type]
            )
            out[tier][cat] = {
                "base_fee_inr": row["base_fee_inr"],
                "gst_percent": row["gst_percent"],
                "gst_amount_inr": row["gst_amount_inr"],
                "total_fee_inr": row["total_fee_inr"],
            }
    return out


def amounts_for_current_tier(on_date: date | None = None) -> dict[str, dict[str, float]]:
    """Per-category breakdown for the active tier today."""
    tier = resolve_event_fee_tier(on_date)
    if not tier:
        return {}
    gst_percent = _gst_percent()
    result: dict[str, dict[str, float]] = {}
    for cat in ("student", "clinician"):
        row = _breakdown_from_base(
            FEE_BASE_INR[tier][cat],  # type: ignore[index]
            gst_percent=gst_percent,
            tier=tier,
            category=cat,  # type: ignore[arg-type]
        )
        result[cat] = {
            "base_fee_inr": row["base_fee_inr"],
            "gst_percent": row["gst_percent"],
            "gst_amount_inr": row["gst_amount_inr"],
            "total_fee_inr": row["total_fee_inr"],
        }
    return result
