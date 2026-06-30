"""WhatsApp 24-hour customer care window helpers (inbound webhook history)."""

from __future__ import annotations

import re
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.models import WhatsAppWebhookEvent
from app.services.whatsapp import normalize_phone

FREE_TEXT_WINDOW_HOURS = 24


def phone_match_variants(phone: str) -> set[str]:
    """Digits-only variants used to match webhook `from` and user contact_number."""
    try:
        normalized = normalize_phone(phone)
    except ValueError:
        normalized = re.sub(r"[^\d+]", "", (phone or "").strip())
    digits = normalized.lstrip("+")
    last10 = digits[-10:] if len(digits) >= 10 else digits
    return {v for v in {normalized, digits, f"+{digits}", last10} if v}


def last_inbound_message_at(db: Session, phone: str) -> datetime | None:
    """When the user last sent a message to the business (from webhook)."""
    keys = phone_match_variants(phone)
    if not keys:
        return None
    rows = (
        db.query(WhatsAppWebhookEvent.created_at)
        .filter(
            WhatsAppWebhookEvent.event_kind.like("message:%"),
            WhatsAppWebhookEvent.phone.in_(list(keys)),
        )
        .order_by(WhatsAppWebhookEvent.created_at.desc())
        .limit(1)
        .all()
    )
    if not rows:
        return None
    return rows[0][0]


def is_within_free_text_window(db: Session, phone: str, *, hours: int = FREE_TEXT_WINDOW_HOURS) -> bool:
    """True if user messaged the business within the last N hours (Meta free-text window)."""
    last = last_inbound_message_at(db, phone)
    if not last:
        return False
    return last >= datetime.utcnow() - timedelta(hours=hours)


def split_phones_by_free_text_window(db: Session, phones: list[str]) -> tuple[list[str], list[str]]:
    """Return (free_text_ok, template_required) phone lists."""
    warm: list[str] = []
    cold: list[str] = []
    for phone in phones:
        if is_within_free_text_window(db, phone):
            warm.append(phone)
        else:
            cold.append(phone)
    return warm, cold
