from __future__ import annotations

import json
import mimetypes
import re
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, TypeVar
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


def _to_wa_id(phone: str) -> str:
    """Meta expects E.164 digits without the leading +."""
    return phone.lstrip("+")


def _meta_payload(phone: str, message: str) -> dict[str, Any]:
    return {
        "messaging_product": "whatsapp",
        "to": _to_wa_id(phone),
        "type": "text",
        "text": {"preview_url": False, "body": message},
    }


def _meta_template_payload(
    phone: str,
    template_name: str,
    language_code: str,
    body_params: list[str] | None = None,
    image_header_link: str | None = None,
) -> dict[str, Any]:
    template: dict[str, Any] = {
        "name": template_name,
        "language": {"code": language_code},
    }
    components: list[dict[str, Any]] = []
    link = (image_header_link or "").strip()
    if link:
        components.append(
            {
                "type": "header",
                "parameters": [{"type": "image", "image": {"link": link}}],
            }
        )
    params = [p for p in (body_params or []) if (p or "").strip()]
    if params:
        components.append(
            {
                "type": "body",
                "parameters": [{"type": "text", "text": p} for p in params],
            }
        )
    if components:
        template["components"] = components
    return {
        "messaging_product": "whatsapp",
        "to": _to_wa_id(phone),
        "type": "template",
        "template": template,
    }


def _meta_image_payload(
    phone: str,
    *,
    media_id: str | None = None,
    image_link: str | None = None,
    caption: str | None = None,
) -> dict[str, Any]:
    image: dict[str, Any] = {}
    if media_id:
        image["id"] = media_id
    elif image_link:
        image["link"] = image_link
    else:
        raise ValueError("media_id or image_link is required for image messages")
    cap = (caption or "").strip()
    if cap:
        image["caption"] = cap[:1024]
    return {
        "messaging_product": "whatsapp",
        "to": _to_wa_id(phone),
        "type": "image",
        "image": image,
    }


def _post_meta_message(payload: dict[str, Any], phone: str) -> SendResult:
    settings = get_settings()
    endpoint = _meta_endpoint()
    headers = _meta_headers()
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


def send_whatsapp_text(phone: str, message: str) -> SendResult:
    return _post_meta_message(_meta_payload(phone, message), phone)


def send_whatsapp_template(
    phone: str,
    template_name: str,
    language_code: str,
    body_params: list[str] | None = None,
    image_header_link: str | None = None,
) -> SendResult:
    return _post_meta_message(
        _meta_template_payload(
            phone,
            template_name,
            language_code,
            body_params,
            image_header_link=image_header_link,
        ),
        phone,
    )


def upload_image_to_meta(file_path: Path) -> str:
    """Upload a local image to Meta; returns media id for outbound image messages."""
    settings = get_settings()
    if not settings.whatsapp_api_key or not settings.whatsapp_phone_number_id:
        raise ValueError("WhatsApp API is not configured")
    if not file_path.is_file():
        raise ValueError("Image file not found")

    mime = mimetypes.guess_type(file_path.name)[0] or "image/jpeg"
    file_data = file_path.read_bytes()
    boundary = f"----WhatsAppBoundary{uuid.uuid4().hex}"
    parts: list[bytes] = []

    def _field(name: str, value: str) -> None:
        parts.append(f"--{boundary}\r\n".encode())
        parts.append(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode())
        parts.append(f"{value}\r\n".encode())

    _field("messaging_product", "whatsapp")
    _field("type", mime)
    parts.append(f"--{boundary}\r\n".encode())
    parts.append(
        f'Content-Disposition: form-data; name="file"; filename="{file_path.name}"\r\n'.encode()
    )
    parts.append(f"Content-Type: {mime}\r\n\r\n".encode())
    parts.append(file_data)
    parts.append(f"\r\n--{boundary}--\r\n".encode())
    body = b"".join(parts)

    endpoint = f"{settings.whatsapp_api_base}/{settings.whatsapp_phone_number_id}/media"
    req = request.Request(
        endpoint,
        data=body,
        headers={
            "Authorization": f"Bearer {settings.whatsapp_api_key}",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        },
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=settings.whatsapp_send_timeout_sec) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            media_id = data.get("id") if isinstance(data, dict) else None
            if not media_id:
                raise ValueError(f"Meta media upload failed: {data}")
            return str(media_id)
    except error.HTTPError as exc:
        raw = exc.read().decode("utf-8") if exc.fp else str(exc)
        raise ValueError(raw[:500]) from exc


def send_whatsapp_image(
    phone: str,
    *,
    media_id: str | None = None,
    image_link: str | None = None,
    caption: str | None = None,
) -> SendResult:
    return _post_meta_message(
        _meta_image_payload(phone, media_id=media_id, image_link=image_link, caption=caption),
        phone,
    )


def _send_bulk(
    phones: list[str],
    send_one: Callable[[str], SendResult],
) -> dict[str, Any]:
    settings = get_settings()
    unique = list(dict.fromkeys(phones))
    batches = split_batches(unique, settings.whatsapp_batch_size)
    results: list[SendResult] = []
    for idx, batch in enumerate(batches):
        for phone in batch:
            results.append(send_one(phone))
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


def send_bulk_text(phones: list[str], message: str) -> dict[str, Any]:
    return _send_bulk(phones, lambda phone: send_whatsapp_text(phone, message))


def send_bulk_template(
    phones: list[str],
    template_name: str,
    language_code: str,
    body_params: list[str] | None = None,
    image_header_link: str | None = None,
) -> dict[str, Any]:
    return _send_bulk(
        phones,
        lambda phone: send_whatsapp_template(
            phone,
            template_name,
            language_code,
            body_params,
            image_header_link=image_header_link,
        ),
    )


def send_bulk_image(
    phones: list[str],
    *,
    media_id: str | None = None,
    image_link: str | None = None,
    caption: str | None = None,
) -> dict[str, Any]:
    return _send_bulk(
        phones,
        lambda phone: send_whatsapp_image(
            phone,
            media_id=media_id,
            image_link=image_link,
            caption=caption,
        ),
    )
