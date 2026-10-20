"""Shared suppression upsert and skip rules for campaign mail."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.models import MailSuppression
from app.services.mail_campaign_audience import normalize_email

REASONS = (
    "unsubscribe",
    "hard_bounce",
    "soft_bounce",
    "complaint",
    "invalid",
    "disposable",
    "manual_block",
)
MANDATORY_SKIP = frozenset(
    {"unsubscribe", "complaint", "invalid", "disposable", "manual_block", "hard_bounce"}
)
BOUNCE_SKIP = frozenset({"soft_bounce"})
PERMANENT_SMTP_TOKENS = (
    "550",
    "551",
    "553",
    "554",
    "5.1.1",
    "5.1.2",
    "5.1.3",
    "5.4.1",
    "user unknown",
    "unknown user",
    "mailbox unavailable",
    "mailbox not found",
    "does not exist",
    "no such user",
    "recipient address rejected",
    "invalid mailbox",
    "invalid recipient",
    "undeliverable",
)
PROTECTED = frozenset({"unsubscribe", "complaint"})
_STRENGTH = {
    "complaint": 100,
    "unsubscribe": 90,
    "hard_bounce": 80,
    "soft_bounce": 50,
    "invalid": 40,
    "disposable": 30,
    "manual_block": 20,
}


def serialize_suppression(row: MailSuppression) -> dict[str, Any]:
    return {
        "id": row.id,
        "email": row.email,
        "reason": row.reason,
        "source": row.source or "",
        "diagnostic": row.diagnostic or "",
        "bounce_count": int(row.bounce_count or 0),
        "last_event_at": row.last_event_at.isoformat() + "Z" if row.last_event_at else None,
        "created_at": row.created_at.isoformat() + "Z" if row.created_at else None,
        "updated_at": row.updated_at.isoformat() + "Z" if row.updated_at else None,
        "created_by_admin_id": row.created_by_admin_id,
    }


def should_skip_send(row: MailSuppression | None, skip_previously_bounced: bool) -> bool:
    if not row:
        return False
    reason = (row.reason or "").strip().lower()
    if reason in MANDATORY_SKIP:
        return True
    if skip_previously_bounced and reason in BOUNCE_SKIP:
        return True
    return False


def is_permanent_smtp_error(text: str) -> bool:
    err = (text or "").lower()
    return any(token in err for token in PERMANENT_SMTP_TOKENS)


def lookup_suppression(db: Session, email: str) -> MailSuppression | None:
    key = normalize_email(email)
    if not key:
        return None
    return db.query(MailSuppression).filter(MailSuppression.email == key).first()


def upsert_suppression(
    db: Session,
    email: str,
    reason: str,
    *,
    source: str,
    diagnostic: str | None = None,
    bounce_count: int | None = None,
    admin_id: Optional[int] = None,
    commit: bool = False,
) -> MailSuppression | None:
    key = normalize_email(email)
    if not key or "@" not in key:
        return None
    reason = (reason or "").strip().lower()
    if reason not in REASONS:
        reason = "manual_block"
    now = datetime.utcnow()
    row = db.query(MailSuppression).filter(MailSuppression.email == key).first()
    if not row:
        row = MailSuppression(
            email=key,
            reason=reason,
            source=source,
            diagnostic=(diagnostic or "")[:2000] or None,
            bounce_count=int(bounce_count or 0),
            last_event_at=now,
            created_by_admin_id=admin_id,
        )
        db.add(row)
        if commit:
            db.commit()
            db.refresh(row)
        return row

    existing = (row.reason or "").strip().lower()
    if bounce_count is not None:
        row.bounce_count = max(int(row.bounce_count or 0), int(bounce_count))
    row.last_event_at = now
    if diagnostic:
        row.diagnostic = diagnostic[:2000]
    if existing in PROTECTED and reason not in PROTECTED:
        if commit:
            db.commit()
            db.refresh(row)
        return row
    if _STRENGTH.get(reason, 0) >= _STRENGTH.get(existing, 0):
        row.reason = reason
        row.source = source or row.source
        if admin_id is not None:
            row.created_by_admin_id = admin_id
    if commit:
        db.commit()
        db.refresh(row)
    return row
