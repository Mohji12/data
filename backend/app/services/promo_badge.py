"""Site-wide marketing promo badge config (options-backed)."""

from __future__ import annotations

import math
from datetime import date, datetime, timedelta, timezone
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.services.access import get_option_value

OPTION_PCT = "site_promo_discount_pct"
OPTION_DESCRIPTION = "site_promo_discount_description"
OPTION_VALID_TILL = "site_promo_discount_valid_till"

DEFAULT_PCT = "25"
DEFAULT_DESCRIPTION = "discount"
DEFAULT_VALID_TILL = "2026-09-16"

# Asia/Kolkata is fixed UTC+5:30 (no DST).
_IST = timezone(timedelta(hours=5, minutes=30))
_MS_PER_DAY = 24 * 60 * 60 * 1000


def _parse_pct(raw: str) -> float:
    try:
        return float(str(raw or "").strip() or "0")
    except ValueError:
        return 0.0


def _parse_valid_till(raw: str) -> Optional[date]:
    value = str(raw or "").strip()
    if not value:
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def days_remaining_for_valid_till(
    valid_till: date,
    *,
    now: Optional[datetime] = None,
) -> int:
    """
    Days remaining until end of valid_till (Asia/Kolkata), ceil-style.
    Returns 0 when expired.
    """
    current = now if now is not None else datetime.now(tz=_IST)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    current_ist = current.astimezone(_IST)
    deadline = datetime(
        valid_till.year,
        valid_till.month,
        valid_till.day,
        23,
        59,
        59,
        999000,
        tzinfo=_IST,
    )
    ms_left = (deadline - current_ist).total_seconds() * 1000
    if ms_left <= 0:
        return 0
    return int(math.ceil(ms_left / _MS_PER_DAY))


def build_promo_badge_payload(
    *,
    pct_raw: str,
    description_raw: str,
    valid_till_raw: str,
    now: Optional[datetime] = None,
) -> dict[str, Any]:
    pct = _parse_pct(pct_raw)
    description = (description_raw or "").strip() or DEFAULT_DESCRIPTION
    valid_till = _parse_valid_till(valid_till_raw)

    if pct <= 0 or valid_till is None:
        return {
            "active": False,
            "discount_pct": int(pct) if float(pct).is_integer() else pct,
            "description": description,
            "valid_till": valid_till.isoformat() if valid_till else None,
            "days_left": 0,
        }

    days_left = days_remaining_for_valid_till(valid_till, now=now)
    discount_pct: int | float = int(pct) if float(pct).is_integer() else pct
    return {
        "active": days_left > 0,
        "discount_pct": discount_pct,
        "description": description,
        "valid_till": valid_till.isoformat(),
        "days_left": days_left,
    }


def get_promo_badge_config(db: Session, *, now: Optional[datetime] = None) -> dict[str, Any]:
    pct_raw = get_option_value(db, OPTION_PCT) or DEFAULT_PCT
    description_raw = get_option_value(db, OPTION_DESCRIPTION) or DEFAULT_DESCRIPTION
    valid_till_raw = get_option_value(db, OPTION_VALID_TILL) or DEFAULT_VALID_TILL
    return build_promo_badge_payload(
        pct_raw=pct_raw,
        description_raw=description_raw,
        valid_till_raw=valid_till_raw,
        now=now,
    )
