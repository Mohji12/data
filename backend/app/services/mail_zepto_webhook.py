"""Parse and apply ZeptoMail / Zoho CPaaS webhook events."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import time
from datetime import datetime
from typing import Any
from urllib.parse import unquote

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import MailCampaignRecipient, MailProviderEvent
from app.services.mail_campaign_audience import normalize_email
from app.services.mail_suppression import upsert_suppression

logger = logging.getLogger(__name__)

HARD_EVENTS = frozenset({"hardbounce", "hard bounce", "hard_bounce"})
SOFT_EVENTS = frozenset({"softbounce", "soft bounce", "soft_bounce"})
COMPLAINT_EVENTS = frozenset({"feedback loop", "feedbackloop", "feedback_loop", "fbl_complaint", "complaint"})
DELIVERED_EVENTS = frozenset({"delivered", "email delivered"})
IGNORED_EVENTS = frozenset({"open", "opens", "click", "clicks", "email opens", "email clicks"})

_TERMINAL_DELIVERY = frozenset({"hard_bounce", "soft_bounce", "complaint"})


def _event_names(raw: Any) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, str):
        return [raw.strip().lower()]
    if isinstance(raw, list):
        out = []
        for item in raw:
            if isinstance(item, str) and item.strip():
                out.append(item.strip().lower())
        return out
    return []


def webhook_auth_configured() -> bool:
    settings = get_settings()
    return bool(settings.zeptomail_webhook_auth_key or settings.zeptomail_webhook_authorization_value)


def is_verify_probe(body: bytes) -> bool:
    """Zepto Verify only checks that POST returns 200; it is not a bounce event."""
    raw = (body or b"").strip()
    if not raw or raw.lower() in {b"{}", b"[]", b"null", b"ok", b'"ok"'}:
        return True
    try:
        data = parse_webhook_body(raw)
    except Exception:
        return len(raw) < 64 and b"event" not in raw.lower()
    if not isinstance(data, dict) or not data:
        return True
    names = _event_names(data.get("event_name"))
    messages = data.get("event_message")
    return not names and not messages and not str(data.get("webhook_request_id") or "").strip()


def verify_zepto_request(body: bytes, headers: dict[str, str]) -> bool:
    settings = get_settings()
    auth_key = settings.zeptomail_webhook_auth_key
    header_name = settings.zeptomail_webhook_authorization_header
    header_value = settings.zeptomail_webhook_authorization_value
    if not auth_key and not header_value:
        return False
    lowered = {str(k).lower(): str(v) for k, v in headers.items()}
    if header_value:
        sent = lowered.get(header_name.lower(), "")
        if not hmac.compare_digest(sent, header_value):
            return False
        if not auth_key:
            return True
    if not auth_key:
        return False
    producer = lowered.get("producer-signature", "")
    if not producer:
        return False
    parts: dict[str, str] = {}
    for chunk in producer.split(";"):
        if "=" not in chunk:
            continue
        key, value = chunk.split("=", 1)
        parts[key.strip()] = value.strip()
    ts = parts.get("ts")
    sig = parts.get("s")
    algo = parts.get("s-algorithm")
    if not ts or not sig or algo != "HmacSHA256":
        return False
    try:
        ts_ms = int(ts)
    except ValueError:
        return False
    skew_ms = abs(int(time.time() * 1000) - ts_ms)
    if skew_ms > settings.zeptomail_webhook_max_skew_sec * 1000:
        return False
    signed = _signed_payload(body)
    try:
        received = base64.b64decode(unquote(sig))
    except Exception:
        return False
    expected = hmac.new(auth_key.encode("utf-8"), signed.encode("utf-8"), hashlib.sha256).digest()
    return hmac.compare_digest(received, expected)


def _signed_payload(body: bytes) -> str:
    raw = body.decode("utf-8", errors="replace")
    stripped = raw.lstrip()
    if stripped.startswith("{") or stripped.startswith("["):
        return raw
    sep = raw.find("=")
    if sep < 0:
        return raw
    return unquote(raw[sep + 1 :])


def parse_webhook_body(body: bytes) -> dict[str, Any]:
    text = _signed_payload(body)
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError("payload must be a JSON object")
    return data


def _parse_time(raw: Any) -> datetime | None:
    if not raw:
        return None
    text = str(raw).strip().replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(text)
        return dt.replace(tzinfo=None)
    except ValueError:
        return None


def _nested_addresses(info: dict[str, Any]) -> list[str]:
    found: list[str] = []
    for bucket in info.get("to") or []:
        if isinstance(bucket, dict):
            addr = (bucket.get("email_address") or {}).get("address") if isinstance(bucket.get("email_address"), dict) else bucket.get("address")
            if addr:
                found.append(str(addr))
    return found


def _detail_maps(event_data: Any) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if not isinstance(event_data, list):
        return out
    for block in event_data:
        if not isinstance(block, dict):
            continue
        details = block.get("details") or []
        if isinstance(details, dict):
            details = [details]
        for item in details:
            if isinstance(item, dict):
                out.append(item)
    return out


def _client_ids(reference: str | None) -> tuple[int | None, int | None]:
    raw = (reference or "").strip()
    if not raw or ":" not in raw:
        return None, None
    left, right = raw.split(":", 1)
    try:
        return int(left), int(right.split(":")[0])
    except ValueError:
        return None, None


def process_zepto_webhook(db: Session, payload: dict[str, Any]) -> dict[str, Any]:
    names = _event_names(payload.get("event_name"))
    webhook_id = str(payload.get("webhook_request_id") or "").strip()
    messages = payload.get("event_message") or []
    if not isinstance(messages, list):
        messages = [messages] if messages else []
    if not webhook_id:
        digest = hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode("utf-8")).hexdigest()[:40]
        webhook_id = f"gen.{digest}"

    processed = 0
    skipped = 0
    for index, message in enumerate(messages or [{}]):
        if not isinstance(message, dict):
            continue
        event_id = webhook_id if index == 0 else f"{webhook_id}.{index}"
        existing = db.query(MailProviderEvent.id).filter(MailProviderEvent.webhook_request_id == event_id).first()
        if existing:
            skipped += 1
            continue
        info = message.get("email_info") if isinstance(message.get("email_info"), dict) else {}
        details = _detail_maps(message.get("event_data"))
        first = details[0] if details else {}
        emails: list[str] = []
        for item in details:
            for key in ("bounced_recipient", "fblFrom", "recipient", "address"):
                val = item.get(key)
                if val:
                    emails.append(str(val))
        emails.extend(_nested_addresses(info))
        email = ""
        for candidate in emails:
            key = normalize_email(candidate)
            if key and "@" in key:
                email = key
                break
        client_ref = str(info.get("client_reference") or "").strip() or None
        campaign_id, recipient_id = _client_ids(client_ref)
        rec = None
        if recipient_id:
            rec = db.query(MailCampaignRecipient).filter(MailCampaignRecipient.id == recipient_id).first()
        if rec is None and email:
            rec = (
                db.query(MailCampaignRecipient)
                .filter(MailCampaignRecipient.email == email, MailCampaignRecipient.status == "accepted")
                .order_by(MailCampaignRecipient.id.desc())
                .first()
            )
        if rec is not None:
            campaign_id = rec.campaign_id
            recipient_id = rec.id
            if not email:
                email = normalize_email(rec.email)
        reason = str(first.get("reason") or "")[:128] or None
        diagnostic = str(first.get("diagnostic_message") or first.get("diagnostic") or "")[:2000] or None
        occurred = _parse_time(first.get("time") or info.get("processed_time"))
        name = names[0] if names else str((message.get("event_data") or [{}])[0].get("object") if isinstance(message.get("event_data"), list) and message.get("event_data") else "")
        name = (name or "").strip().lower()
        event = MailProviderEvent(
            webhook_request_id=event_id[:191],
            event_name=name[:64] or "unknown",
            email=email,
            campaign_id=campaign_id,
            recipient_id=recipient_id,
            request_id=str(message.get("request_id") or payload.get("request_id") or "")[:191] or None,
            client_reference=client_ref,
            reason=reason,
            diagnostic=diagnostic,
            occurred_at=occurred,
            payload_json=json.dumps(payload, default=str)[:8000],
        )
        db.add(event)
        try:
            db.flush()
        except IntegrityError:
            db.rollback()
            skipped += 1
            continue
        _apply_event(db, name, email, rec, diagnostic, reason)
        processed += 1
    db.commit()
    return {"ok": True, "processed": processed, "skipped": skipped}


def _apply_event(
    db: Session,
    name: str,
    email: str,
    rec: MailCampaignRecipient | None,
    diagnostic: str | None,
    reason: str | None,
) -> None:
    settings = get_settings()
    if name in HARD_EVENTS:
        upsert_suppression(
            db,
            email,
            "hard_bounce",
            source="zepto_webhook",
            diagnostic=diagnostic or reason,
        )
        if rec is not None:
            rec.delivery_status = "hard_bounce"
            rec.bounced_at = datetime.utcnow()
            db.add(rec)
        return
    if name in SOFT_EVENTS:
        count = (
            db.query(func.count(MailProviderEvent.id))
            .filter(
                MailProviderEvent.email == email,
                MailProviderEvent.event_name.in_(tuple(SOFT_EVENTS)),
            )
            .scalar()
            or 0
        )
        if rec is not None and rec.delivery_status not in _TERMINAL_DELIVERY:
            rec.delivery_status = "soft_bounce"
            rec.bounced_at = datetime.utcnow()
            db.add(rec)
        if count >= settings.mail_soft_bounce_suppress_after:
            upsert_suppression(
                db,
                email,
                "soft_bounce",
                source="zepto_webhook",
                diagnostic=diagnostic or reason,
                bounce_count=count,
            )
        return
    if name in COMPLAINT_EVENTS:
        upsert_suppression(
            db,
            email,
            "complaint",
            source="zepto_webhook",
            diagnostic=diagnostic or reason,
        )
        if rec is not None:
            rec.delivery_status = "complaint"
            rec.bounced_at = datetime.utcnow()
            db.add(rec)
        return
    if name in DELIVERED_EVENTS and rec is not None:
        if rec.delivery_status not in _TERMINAL_DELIVERY:
            rec.delivery_status = "delivered"
            db.add(rec)
        return
    if name in IGNORED_EVENTS:
        return
    logger.info("zepto webhook ignored event_name=%s email=%s", name, email)
