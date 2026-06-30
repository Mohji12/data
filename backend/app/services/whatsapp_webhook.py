from __future__ import annotations

import hashlib
import hmac
import json
import logging
import re
from datetime import datetime, timedelta
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import User, WhatsAppWebhookEvent, Option
from app.services.access import get_option_value
from app.services.whatsapp import normalize_phone, send_whatsapp_text
from app.services.whatsapp_session import phone_match_variants

logger = logging.getLogger(__name__)


def verify_meta_challenge(*, mode: str, verify_token: str, challenge: str) -> Optional[str]:
    """Meta GET webhook verification. Returns challenge text when valid."""
    settings = get_settings()
    expected = (settings.whatsapp_verify_token or "").strip()
    if not expected:
        logger.warning("WhatsApp webhook verify token is not configured")
        return None
    if (mode or "").strip() != "subscribe":
        logger.warning("WhatsApp webhook verify rejected: hub.mode=%s", mode)
        return None
    if (verify_token or "").strip() != expected:
        logger.warning("WhatsApp webhook verify rejected: token mismatch")
        return None
    return (challenge or "").strip()


def verify_meta_signature(body: bytes, signature_header: str) -> bool:
    """Validate X-Hub-Signature-256 (sha256 HMAC of raw body with app secret)."""
    settings = get_settings()
    secret = (settings.whatsapp_app_secret or "").strip()
    if not secret:
        logger.warning("WHATSAPP_APP_SECRET not set — skipping webhook signature verification")
        return True

    raw = (signature_header or "").strip()
    if not raw.startswith("sha256="):
        return False
    expected = raw[7:]
    digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(digest, expected)


def _find_user_id_by_phone(db: Session, phone: str) -> Optional[int]:
    try:
        normalized = normalize_phone(phone)
    except ValueError:
        normalized = re.sub(r"[^\d+]", "", (phone or "").strip())
    if not normalized:
        return None
    digits = normalized.lstrip("+")
    last10 = digits[-10:] if len(digits) >= 10 else digits
    lookups = {normalized, digits, f"+{digits}", last10}
    try:
        row = db.query(User.id).filter(User.contact_number.in_(list(lookups))).first()
    except Exception:
        logger.debug("User lookup by phone skipped", exc_info=True)
        return None
    return int(row[0]) if row else None


def _send_inbound_auto_reply(db: Session, from_phone: str) -> None:
    """When a user messages the business, reply with free text (opens 24h window)."""
    if get_option_value(db, "whatsapp_auto_reply_on_inbound") in {"0", "false", "no", "off"}:
        return
    row = db.query(Option).filter(Option.option_name == "whatsapp_default_template").first()
    reply = (row.option_value or "").strip() if row else ""
    if not reply:
        return
    keys = phone_match_variants(from_phone) if from_phone else set()
    if keys:
        recent = (
            db.query(WhatsAppWebhookEvent.id)
            .filter(
                WhatsAppWebhookEvent.event_kind == "outbound:auto_reply",
                WhatsAppWebhookEvent.phone.in_(list(keys)),
                WhatsAppWebhookEvent.created_at >= datetime.utcnow() - timedelta(minutes=2),
            )
            .first()
        )
        if recent:
            return
    try:
        phone = normalize_phone(from_phone)
        result = send_whatsapp_text(phone, reply)
        if not result.success:
            logger.warning("WhatsApp auto-reply failed for %s: %s", from_phone, result.error)
            return
        _store_event(
            db,
            event_kind="outbound:auto_reply",
            field="messages",
            phone=from_phone,
            wa_message_id=result.provider_message_id,
            event_status="sent",
            payload={"auto_reply": True, "preview": reply[:200]},
        )
        logger.info("WhatsApp auto-reply sent to %s", from_phone)
    except Exception:
        logger.exception("WhatsApp auto-reply error for %s", from_phone)


def _store_event(
    db: Session,
    *,
    event_kind: str,
    field: Optional[str],
    phone: Optional[str],
    wa_message_id: Optional[str],
    event_status: Optional[str],
    payload: dict[str, Any],
    user_id: Optional[int] = None,
) -> None:
    db.add(
        WhatsAppWebhookEvent(
            event_kind=event_kind,
            field=field,
            phone=phone,
            wa_message_id=wa_message_id,
            event_status=event_status,
            user_id=user_id,
            payload=json.dumps(payload, ensure_ascii=False),
        )
    )


def process_whatsapp_webhook(db: Session, payload: dict[str, Any]) -> dict[str, Any]:
    """
    Parse Meta WhatsApp Cloud API webhook payload and persist inbound events.
    Always returns quickly — Meta retries on non-2xx responses.
    """
    object_type = (payload.get("object") or "").strip()
    if object_type and object_type != "whatsapp_business_account":
        logger.info("Ignoring WhatsApp webhook object=%s", object_type)
        return {"status": "ignored", "object": object_type, "processed": 0}

    processed = 0
    for entry in payload.get("entry") or []:
        if not isinstance(entry, dict):
            continue
        for change in entry.get("changes") or []:
            if not isinstance(change, dict):
                continue
            field = (change.get("field") or "").strip() or None
            value = change.get("value") or {}
            if not isinstance(value, dict):
                continue

            metadata = value.get("metadata") or {}
            display_phone = (metadata.get("display_phone_number") or "").strip() or None

            for msg in value.get("messages") or []:
                if not isinstance(msg, dict):
                    continue
                from_phone = (msg.get("from") or "").strip() or None
                wa_id = (msg.get("id") or "").strip() or None
                msg_type = (msg.get("type") or "message").strip()
                user_id = _find_user_id_by_phone(db, from_phone) if from_phone else None
                _store_event(
                    db,
                    event_kind=f"message:{msg_type}",
                    field=field,
                    phone=from_phone,
                    wa_message_id=wa_id,
                    event_status=None,
                    payload={"message": msg, "metadata": metadata, "display_phone": display_phone},
                    user_id=user_id,
                )
                processed += 1
                logger.info(
                    "WhatsApp inbound message id=%s from=%s type=%s user_id=%s",
                    wa_id,
                    from_phone,
                    msg_type,
                    user_id,
                )
                if from_phone:
                    _send_inbound_auto_reply(db, from_phone)

            for status in value.get("statuses") or []:
                if not isinstance(status, dict):
                    continue
                recipient = (status.get("recipient_id") or "").strip() or None
                wa_id = (status.get("id") or "").strip() or None
                status_label = (status.get("status") or "").strip() or None
                user_id = _find_user_id_by_phone(db, recipient) if recipient else None
                _store_event(
                    db,
                    event_kind="status",
                    field=field,
                    phone=recipient,
                    wa_message_id=wa_id,
                    event_status=status_label,
                    payload={"status": status, "metadata": metadata, "display_phone": display_phone},
                    user_id=user_id,
                )
                processed += 1
                logger.info(
                    "WhatsApp status id=%s recipient=%s status=%s",
                    wa_id,
                    recipient,
                    status_label,
                )

            for err in value.get("errors") or []:
                if not isinstance(err, dict):
                    continue
                _store_event(
                    db,
                    event_kind="error",
                    field=field,
                    phone=display_phone,
                    wa_message_id=None,
                    event_status=(err.get("title") or err.get("code") or "error"),
                    payload={"error": err, "metadata": metadata},
                )
                processed += 1
                logger.warning("WhatsApp webhook error payload: %s", err)

    if processed:
        db.commit()
    else:
        logger.debug("WhatsApp webhook received with no processable changes")

    return {"status": "ok", "processed": processed}
