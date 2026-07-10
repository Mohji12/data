"""ICU-ID Conclave 2026 registration fees (early bird, category + registration window)."""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from typing import Any, Literal

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import Option

# India Standard Time (UTC+5:30, no DST). Fixed offset avoids ZoneInfo/tzdata on Windows.
IST = timezone(timedelta(hours=5, minutes=30))

EventCategory = Literal["student", "clinician"]

VALID_CATEGORIES = frozenset({"student", "clinician"})

REGISTRATION_LAST_DAY = date(2026, 7, 12)
EARLY_BIRD_LABEL = "Early Bird"

# Default early-bird base fees (INR, before GST).
DEFAULT_EARLY_BIRD_BASE: dict[EventCategory, float] = {"student": 2700.0, "clinician": 3200.0}


def early_bird_period_label() -> str:
    """Human-readable early-bird window (same rate through on-spot registration day)."""
    return f"Early Bird (up to {REGISTRATION_LAST_DAY.strftime('%d %b %Y')})"


def event_fees_option_key(event_slug: str | None = None) -> str:
    slug = (event_slug or get_settings().event_icu_d_conclave_slug or "icu-id-conclave-2026").strip().casefold()
    return f"event_fees::{slug}"


def default_early_bird_fee_config() -> dict[str, Any]:
    settings = get_settings()
    return {
        "label": early_bird_period_label(),
        "student": float(getattr(settings, "event_icu_d_conclave_fee_student_inr", 2700) or 2700),
        "clinician": float(
            getattr(settings, "event_icu_d_conclave_fee_clinician_inr", None)
            or settings.event_icu_d_conclave_fee_inr
            or 3200
        ),
    }


def resolve_early_bird_fee_config(db: Session | None = None) -> dict[str, Any]:
    """Load early-bird fee amounts from DB options, then env, then code defaults."""
    defaults = default_early_bird_fee_config()
    if db is None:
        return defaults
    row = db.query(Option).filter(Option.option_name == event_fees_option_key()).first()
    if not row or not (row.option_value or "").strip():
        return defaults
    try:
        data = json.loads(row.option_value)
        if not isinstance(data, dict):
            return defaults
        return {
            "label": str(data.get("label") or defaults["label"]).strip() or early_bird_period_label(),
            "student": float(data.get("student", defaults["student"])),
            "clinician": float(data.get("clinician", defaults["clinician"])),
        }
    except (TypeError, ValueError, json.JSONDecodeError):
        return defaults


def ensure_early_bird_fees_in_db(db: Session) -> dict[str, Any]:
    """Persist early-bird fees in options (kept in sync with code defaults)."""
    key = event_fees_option_key()
    config = default_early_bird_fee_config()
    payload = json.dumps(config)
    row = db.query(Option).filter(Option.option_name == key).first()
    if not row:
        db.add(Option(option_name=key, option_value=payload))
    else:
        row.option_value = payload
        db.add(row)
    db.commit()
    return config


def early_bird_base_inr(category: str, db: Session | None = None) -> float:
    cat = (category or "").strip().lower()
    if cat not in VALID_CATEGORIES:
        raise ValueError("Invalid category")
    config = resolve_early_bird_fee_config(db)
    return float(config[cat])  # type: ignore[index]


def event_today_ist(on_date: date | None = None) -> date:
    if on_date is not None:
        return on_date
    return datetime.now(IST).date()


def registration_open_for_date(on_date: date | None = None) -> bool:
    return event_today_ist(on_date) <= REGISTRATION_LAST_DAY


def _gst_percent() -> float:
    return float(get_settings().event_icu_d_conclave_gst_percent or 18)


def _breakdown_from_base(
    base: float,
    *,
    gst_percent: float,
    category: EventCategory,
    fee_label: str,
) -> dict[str, Any]:
    gst_amount = round(base * gst_percent / 100, 2)
    total = round(base + gst_amount, 2)
    return {
        "category": category,
        "fee_label": fee_label,
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
    db: Session | None = None,
) -> dict[str, Any]:
    """
    Compute payable amounts for a category on a given day.
    Raises ValueError for invalid category or closed registration window.
    """
    cat = (category or "").strip().lower()
    if cat not in VALID_CATEGORIES:
        raise ValueError("Invalid category")

    if not registration_open_for_date(on_date):
        raise ValueError("registration_closed")

    config = resolve_early_bird_fee_config(db)
    base = float(config[cat])  # type: ignore[index]
    fee_label = str(config.get("label") or early_bird_period_label())
    fees = _breakdown_from_base(
        base,
        gst_percent=_gst_percent(),
        category=cat,  # type: ignore[arg-type]
        fee_label=fee_label,
    )
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


def build_fee_table(db: Session | None = None) -> dict[str, dict[str, float | str]]:
    """Per-category early-bird fee breakdown for public config UI."""
    gst_percent = _gst_percent()
    config = resolve_early_bird_fee_config(db)
    fee_label = str(config.get("label") or early_bird_period_label())
    out: dict[str, dict[str, float | str]] = {}
    for cat in ("student", "clinician"):
        row = _breakdown_from_base(
            float(config[cat]),  # type: ignore[index]
            gst_percent=gst_percent,
            category=cat,  # type: ignore[arg-type]
            fee_label=fee_label,
        )
        out[cat] = {
            "fee_label": fee_label,
            "base_fee_inr": row["base_fee_inr"],
            "gst_percent": row["gst_percent"],
            "gst_amount_inr": row["gst_amount_inr"],
            "total_fee_inr": row["total_fee_inr"],
        }
    return out
