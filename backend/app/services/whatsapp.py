from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from typing import Any, TypeVar
from urllib import error, request

from app.core.config import get_settings

_PHONE_RE = re.compile(r"^\+?[1-9]\d{7,14}$")


def normalize_phone(phone: str) -> str:
    raw = re.sub(r"[^\d+]", "", (phone or "").strip())
    if raw.startswith("00"):
        raw = f"+{raw[2:]}"
    if not raw.startswith("+"):
        if len(raw) == 10:
            raw = f"+91{raw}"
        else:
            raw = f"+{raw}"
    if not _PHONE_RE.match(raw):
        raise ValueError("Invalid phone number format")
    return raw


T = TypeVar("T")


def split_batches(items: list[T], batch_size: int) -> list[list[T]]:
    safe_size = max(1, int(batch_size or 1))
    return [items[i : i + safe_size] for i in range(0, len(items), safe_size)]


@dataclass
class SendResult:
    phone: str
    success: bool
    provider_message_id: str | None = None
    error: str | None = None
    status_code: int | None = None


def _meta_endpoint() -> str:
    settings = get_settings()
    if not settings.whatsapp_api_key or not settings.whatsapp_phone_number_id:
        raise ValueError("WhatsApp API is not configured")
    return f"{settings.whatsapp_api_base}/{settings.whatsapp_phone_number_id}/messages"


def _meta_headers() -> dict[str, str]:
    settings = get_settings()
    return {
        "Authorization": f"Bearer {settings.whatsapp_api_key}",
        "Content-Type": "application/json",
    }


def _meta_payload(phone: str, message: str) -> dict[str, Any]:
    return {
        "messaging_product": "whatsapp",
        "to": phone,
        "type": "text",
        "text": {"preview_url": False, "body": message},
    }


def send_whatsapp_text(phone: str, message: str) -> SendResult:
    settings = get_settings()
    endpoint = _meta_endpoint()
    headers = _meta_headers()
    payload = _meta_payload(phone, message)
    retries = settings.whatsapp_send_max_retries
    timeout = settings.whatsapp_send_timeout_sec

    attempt = 0
    while True:
        attempt += 1
        body = json.dumps(payload).encode("utf-8")
        req = request.Request(endpoint, data=body, headers=headers, method="POST")
        try:
            with request.urlopen(req, timeout=timeout) as resp:
                status_code = getattr(resp, "status", 200)
                data = json.loads(resp.read().decode("utf-8"))
                message_id = None
                contacts = data.get("messages") if isinstance(data, dict) else None
                if isinstance(contacts, list) and contacts:
                    message_id = (contacts[0] or {}).get("id")
                return SendResult(
                    phone=phone,
                    success=True,
                    provider_message_id=message_id,
                    status_code=status_code,
                )
        except error.HTTPError as exc:
            response_body = ""
            try:
                response_body = exc.read().decode("utf-8")
            except Exception:
                response_body = str(exc)
            error_text = response_body or str(exc)
            if attempt <= retries:
                time.sleep(max(0, settings.whatsapp_send_delay_ms) / 1000.0)
                continue
            return SendResult(
                phone=phone,
                success=False,
                error=error_text[:500],
                status_code=getattr(exc, "code", None),
            )
        except Exception as exc:
            if attempt <= retries:
                time.sleep(max(0, settings.whatsapp_send_delay_ms) / 1000.0)
                continue
            return SendResult(phone=phone, success=False, error=str(exc)[:500], status_code=None)


def send_bulk_text(phones: list[str], message: str) -> dict[str, Any]:
    settings = get_settings()
    unique = list(dict.fromkeys(phones))
    batches = split_batches(unique, settings.whatsapp_batch_size)
    results: list[SendResult] = []
    for idx, batch in enumerate(batches):
        for phone in batch:
            results.append(send_whatsapp_text(phone, message))
            if settings.whatsapp_send_delay_ms > 0:
                time.sleep(settings.whatsapp_send_delay_ms / 1000.0)
        if idx < len(batches) - 1 and settings.whatsapp_send_delay_ms > 0:
            time.sleep(settings.whatsapp_send_delay_ms / 1000.0)

    failures = [r for r in results if not r.success]
    return {
        "total": len(unique),
        "sent": len(results) - len(failures),
        "failed": len(failures),
        "results": [
            {
                "phone": r.phone,
                "success": r.success,
                "provider_message_id": r.provider_message_id,
                "error": r.error,
                "status_code": r.status_code,
            }
            for r in results
        ],
    }
