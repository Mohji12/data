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
OPTION_BATCH_START = "site_promo_batch_start"
OPTION_HEADLINE = "site_promo_headline"
OPTION_BATCH_LABEL = "site_promo_batch_label"
OPTION_CTA_PREFIX = "site_promo_cta_prefix"
OPTION_VALID_PREFIX = "site_promo_valid_prefix"

DEFAULT_PCT = "25"
DEFAULT_DESCRIPTION = "DISCOUNT"
DEFAULT_VALID_TILL = "2026-09-30"
DEFAULT_BATCH_START = "2026-10-01"
DEFAULT_HEADLINE = "OFFER"
DEFAULT_BATCH_LABEL = "NEW BATCHES START FROM"
DEFAULT_CTA_PREFIX = "REGISTER NOW TO AVAIL"
DEFAULT_VALID_PREFIX = "OFFER VALID TILL"

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


def _clean_text(raw: str, default: str, *, max_len: int = 60) -> str:
    value = (raw or "").strip() or default
    return value[:max_len]


def _clean_description(raw: str) -> str:
    """Keep short % label; ignore legacy values that stuffed batch copy here."""
    value = (raw or "").strip()
    if not value or len(value) > 16 or "batch" in value.lower():
        return DEFAULT_DESCRIPTION
    return value.upper()


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
    batch_start_raw: str = "",
    headline_raw: str = "",
    batch_label_raw: str = "",
    cta_prefix_raw: str = "",
    valid_prefix_raw: str = "",
    now: Optional[datetime] = None,
) -> dict[str, Any]:
    pct = _parse_pct(pct_raw)
    description = _clean_description(description_raw)
    valid_till = _parse_valid_till(valid_till_raw)
    batch_start = _parse_valid_till(batch_start_raw)
    headline = _clean_text(headline_raw, DEFAULT_HEADLINE, max_len=24)
    batch_label = _clean_text(batch_label_raw, DEFAULT_BATCH_LABEL, max_len=40)
    cta_prefix = _clean_text(cta_prefix_raw, DEFAULT_CTA_PREFIX, max_len=40)
    valid_prefix = _clean_text(valid_prefix_raw, DEFAULT_VALID_PREFIX, max_len=40)

    base = {
        "discount_pct": int(pct) if float(pct).is_integer() else pct,
        "description": description,
        "valid_till": valid_till.isoformat() if valid_till else None,
        "batch_start": batch_start.isoformat() if batch_start else None,
        "headline": headline,
        "batch_label": batch_label,
        "cta_prefix": cta_prefix,
        "valid_prefix": valid_prefix,
    }

    if pct <= 0 or valid_till is None:
        return {**base, "active": False, "days_left": 0}

    days_left = days_remaining_for_valid_till(valid_till, now=now)
    return {**base, "active": days_left > 0, "days_left": days_left}


def get_promo_badge_config(db: Session, *, now: Optional[datetime] = None) -> dict[str, Any]:
    return build_promo_badge_payload(
        pct_raw=get_option_value(db, OPTION_PCT) or DEFAULT_PCT,
        description_raw=get_option_value(db, OPTION_DESCRIPTION) or DEFAULT_DESCRIPTION,
        valid_till_raw=get_option_value(db, OPTION_VALID_TILL) or DEFAULT_VALID_TILL,
        batch_start_raw=get_option_value(db, OPTION_BATCH_START) or DEFAULT_BATCH_START,
        headline_raw=get_option_value(db, OPTION_HEADLINE) or DEFAULT_HEADLINE,
        batch_label_raw=get_option_value(db, OPTION_BATCH_LABEL) or DEFAULT_BATCH_LABEL,
        cta_prefix_raw=get_option_value(db, OPTION_CTA_PREFIX) or DEFAULT_CTA_PREFIX,
        valid_prefix_raw=get_option_value(db, OPTION_VALID_PREFIX) or DEFAULT_VALID_PREFIX,
        now=now,
    )
