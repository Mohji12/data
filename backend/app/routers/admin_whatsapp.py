from __future__ import annotations
import re
from datetime import datetime

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session
from pydantic import BaseModel, field_validator, model_validator

from app.admin_security import get_current_admin, require_admin_type
from app.core.config import get_settings
from app.db import get_db
from app.models import Admin, Audit, Option
from typing import Any, Literal

from app.services.access import get_option_value
from app.services.uploads import save_whatsapp_image, whatsapp_image_path
from app.services.whatsapp_session import split_phones_by_free_text_window
from app.services.whatsapp import (
    normalize_phone,
    send_bulk_image,
    send_bulk_template,
    send_bulk_text,
    upload_image_to_meta,
)

router = APIRouter(prefix="/admin/whatsapp", tags=["admin-whatsapp"], dependencies=[Depends(get_current_admin)])


class WhatsAppLogPayload(BaseModel):
    user_id: int
    message: str


@router.post("/log")
def log_whatsapp_message(
    payload: WhatsAppLogPayload,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
):
    """Logs that an admin attempted to send a WhatsApp message to a user."""
    audit = Audit(
        user_id=current_admin.id,
        file_id=payload.user_id,
        file_type="user",
        activity="whatsapp_send_attempt",
        activity_details=f"Manual WhatsApp attempt: {payload.message[:200]}...",
        activity_datetime=datetime.utcnow(),
    )
    db.add(audit)
    db.commit()
    return {"status": "ok"}


class WhatsAppTemplatePayload(BaseModel):
    template: str
    auto_reply_on_inbound: bool | None = None


@router.get("/template")
def get_whatsapp_template(db: Session = Depends(get_db)):
    """Fetches the global WhatsApp message template from options."""
    settings = get_settings()
    opt = db.query(Option).filter(Option.option_name == "whatsapp_default_template").first()
    auto_reply = get_option_value(db, "whatsapp_auto_reply_on_inbound")
    auto_reply_enabled = True
    if auto_reply is not None and str(auto_reply).strip() != "":
        auto_reply_enabled = auto_reply in {"1", "true", "yes", "on"}
    return {
        "template": opt.option_value if opt else "Hello! This is from Harish Critical Care Classes.",
        "default_template_name": settings.whatsapp_default_template_name,
        "default_template_language": settings.whatsapp_default_template_language,
        "custom_message_template_name": settings.whatsapp_custom_message_template_name,
        "custom_message_template_language": settings.whatsapp_custom_message_template_language,
        "auto_reply_on_inbound": auto_reply_enabled,
    }


@router.post("/template")
def save_whatsapp_template(payload: WhatsAppTemplatePayload, db: Session = Depends(get_db)):
    """Saves the global WhatsApp message template to options."""
    opt = db.query(Option).filter(Option.option_name == "whatsapp_default_template").first()
    if not opt:
        opt = Option(option_name="whatsapp_default_template", option_value=payload.template)
        db.add(opt)
    else:
        opt.option_value = payload.template
    if payload.auto_reply_on_inbound is not None:
        ar_name = "whatsapp_auto_reply_on_inbound"
        ar = db.query(Option).filter(Option.option_name == ar_name).first()
        val = "1" if payload.auto_reply_on_inbound else "0"
        if ar:
            ar.option_value = val
        else:
            db.add(Option(option_name=ar_name, option_value=val))
    db.commit()
    return {"status": "ok"}


@router.post("/upload-image")
async def upload_whatsapp_image(file: UploadFile = File(...)) -> dict:
    """Store an image on the server for WhatsApp campaigns (max 5MB, JPG/PNG/WEBP)."""
    filename = save_whatsapp_image(file)
    settings = get_settings()
    base = (settings.api_public_base_url or "").strip().rstrip("/")
    relative_path = f"/upload/whatsapp/{filename}"
    public_url = f"{base}{relative_path}" if base else None
    return {
        "filename": filename,
        "relative_path": relative_path,
        "public_url": public_url,
    }


class BulkRecipient(BaseModel):
    user_id: int | None = None
    phone: str
    name: str | None = None

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        return normalize_phone(v)


class WhatsAppBulkSendPayload(BaseModel):
    send_mode: Literal["text", "template", "custom", "auto"] = "auto"
    message: str | None = None
    template_name: str | None = None
    template_language: str = "en"
    template_body_params: list[str] = []
    recipients: list[BulkRecipient]
    dedupe: bool = True
    max_recipients: int = 300
    image_filename: str | None = None

    @field_validator("image_filename")
    @classmethod
    def validate_image_filename(cls, v: str | None) -> str | None:
        if v is None:
            return None
        val = (v or "").strip()
        if not val:
            return None
        if ".." in val or "/" in val or "\\" in val:
            raise ValueError("Invalid image filename")
        return val

    @field_validator("message")
    @classmethod
    def validate_message(cls, v: str | None) -> str | None:
        if v is None:
            return None
        val = v.strip()
        if len(val) > 4096:
            raise ValueError("message is too long")
        return val or None

    @field_validator("template_name")
    @classmethod
    def validate_template_name(cls, v: str | None) -> str | None:
        if v is None:
            return None
        val = v.strip()
        if val and not re.match(r"^[a-z0-9_]+$", val):
            raise ValueError("template_name must use lowercase letters, numbers, and underscores")
        return val or None

    @field_validator("template_language")
    @classmethod
    def validate_template_language(cls, v: str) -> str:
        val = (v or "en").strip()
        if not val:
            raise ValueError("template_language is required")
        return val

    @model_validator(mode="after")
    def validate_payload(self) -> "WhatsAppBulkSendPayload":
        if not self.recipients:
            raise ValueError("At least one recipient is required")
        if len(self.recipients) > self.max_recipients:
            raise ValueError(f"Recipient limit exceeded (max {self.max_recipients})")
        if self.send_mode == "text":
            if not (self.message or "").strip() and not self.image_filename:
                raise ValueError("message or image is required for text mode")
        elif self.send_mode == "custom":
            if not (self.message or "").strip():
                raise ValueError("message is required for custom mode")
        elif self.send_mode == "auto":
            if not (self.message or "").strip() and not self.image_filename:
                raise ValueError("message or image is required for auto mode")
        else:
            if not (self.template_name or "").strip():
                raise ValueError("template_name is required for template mode")
        return self


def _resolve_whatsapp_image_assets(image_filename: str | None) -> tuple[str | None, str | None]:
    """Return (meta_media_id, public_https_url) for a stored WhatsApp image."""
    if not image_filename:
        return None, None
    path = whatsapp_image_path(image_filename)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Uploaded image not found on server")

    media_id: str | None = None
    try:
        media_id = upload_image_to_meta(path)
    except Exception:
        media_id = None

    public_url: str | None = None
    settings = get_settings()
    base = (settings.api_public_base_url or "").strip().rstrip("/")
    if base.lower().startswith("https://"):
        public_url = f"{base.rstrip('/')}/upload/whatsapp/{image_filename}"

    if not media_id and not public_url:
        raise HTTPException(
            status_code=422,
            detail=(
                "Could not prepare image for WhatsApp. Set API_PUBLIC_BASE_URL to your public HTTPS API "
                "or ensure Meta media upload is configured."
            ),
        )
    return media_id, public_url


def _merge_send_summaries(*parts: dict[str, Any]) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    for part in parts:
        results.extend(part.get("results") or [])
    failures = [r for r in results if not r.get("success")]
    phones = list(dict.fromkeys(r.get("phone") for r in results if r.get("phone")))
    return {
        "total": len(phones),
        "sent": len(results) - len(failures),
        "failed": len(failures),
        "results": results,
    }


def _resolve_custom_template(
    settings: Any, payload: WhatsAppBulkSendPayload
) -> tuple[str, str, list[str]]:
    tpl = (payload.template_name or settings.whatsapp_custom_message_template_name or "").strip()
    lang = (
        payload.template_language
        or settings.whatsapp_custom_message_template_language
        or "en"
    ).strip()
    if not tpl:
        raise HTTPException(
            status_code=422,
            detail=(
                "Approved template required for first-time recipients. Set WHATSAPP_CUSTOM_MESSAGE_TEMPLATE "
                "in backend .env (Meta template with {{1}} body variable) or enter template name in admin."
            ),
        )
    body_text = (payload.message or "").strip()
    extra_params = [p for p in (payload.template_body_params or []) if (p or "").strip()]
    body_params = [body_text, *extra_params] if body_text else extra_params
    return tpl, lang, body_params


def _template_send_params(template_name: str, body_params: list[str]) -> list[str] | None:
    """Meta hello_world has no {{n}} placeholders — sending params would fail."""
    if (template_name or "").strip().lower() == "hello_world":
        return None
    cleaned = [p for p in body_params if (p or "").strip()]
    return cleaned or None


@router.post("/bulk-send", dependencies=[Depends(require_admin_type("techadmin"))])
def bulk_send_whatsapp(
    payload: WhatsAppBulkSendPayload,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
):
    settings = get_settings()
    if not settings.whatsapp_api_key or not settings.whatsapp_phone_number_id:
        raise HTTPException(status_code=503, detail="WhatsApp API is not configured")

    recipient_phones = [r.phone for r in payload.recipients]
    if payload.dedupe:
        recipient_phones = list(dict.fromkeys(recipient_phones))

    media_id, public_image_url = _resolve_whatsapp_image_assets(payload.image_filename)
    caption = (payload.message or "").strip() or None
    image_link = public_image_url if payload.image_filename else None
    if payload.image_filename and not image_link and payload.send_mode in {"template", "custom", "auto"}:
        # Template header images need public HTTPS; warm path may still use Meta media upload.
        pass

    warm_phones, cold_phones = split_phones_by_free_text_window(db, recipient_phones)
    dispatch_label = payload.send_mode

    if payload.send_mode == "auto":
        summaries: list[dict[str, Any]] = []
        tpl, lang, body_params = _resolve_custom_template(settings, payload)
        if cold_phones:
            cold_image = image_link
            if payload.image_filename and not cold_image:
                raise HTTPException(
                    status_code=422,
                    detail="First-time sends with image need API_PUBLIC_BASE_URL (HTTPS) and a Meta template with IMAGE header.",
                )
            summaries.append(
                send_bulk_template(
                    cold_phones,
                    tpl,
                    lang,
                    _template_send_params(tpl, body_params),
                    image_header_link=cold_image,
                )
            )
        if warm_phones:
            if payload.image_filename:
                summaries.append(
                    send_bulk_image(
                        warm_phones,
                        media_id=media_id,
                        image_link=public_image_url if not media_id else None,
                        caption=caption,
                    )
                )
            else:
                summaries.append(send_bulk_text(warm_phones, (payload.message or "").strip()))
        if not summaries:
            raise HTTPException(status_code=422, detail="No recipients to send to")
        summary = _merge_send_summaries(*summaries)
        dispatch_label = f"auto template={tpl} cold={len(cold_phones)} warm={len(warm_phones)}"
    elif payload.send_mode == "template":
        image_link = public_image_url if payload.image_filename else None
        if payload.image_filename and not image_link:
            raise HTTPException(
                status_code=422,
                detail="Template + image requires API_PUBLIC_BASE_URL as a public HTTPS URL.",
            )
        summary = send_bulk_template(
            recipient_phones,
            (payload.template_name or "").strip(),
            payload.template_language,
            payload.template_body_params or None,
            image_header_link=image_link,
        )
        dispatch_label = f"template={payload.template_name}"
    elif payload.send_mode == "custom":
        tpl = (payload.template_name or settings.whatsapp_custom_message_template_name or "").strip()
        lang = (
            payload.template_language
            or settings.whatsapp_custom_message_template_language
            or "en"
        ).strip()
        if not tpl:
            raise HTTPException(
                status_code=422,
                detail=(
                    "Custom message template is not configured. Set WHATSAPP_CUSTOM_MESSAGE_TEMPLATE "
                    "in backend .env to an approved Meta template with a {{1}} body variable, "
                    "or enter the template name in the admin form."
                ),
            )
        body_text = (payload.message or "").strip()
        extra_params = [p for p in (payload.template_body_params or []) if (p or "").strip()]
        body_params = [body_text, *extra_params] if body_text else extra_params
        image_link = public_image_url if payload.image_filename else None
        if payload.image_filename and not image_link:
            raise HTTPException(
                status_code=422,
                detail=(
                    "Custom template + image requires an approved Meta template with IMAGE header "
                    "and API_PUBLIC_BASE_URL as public HTTPS."
                ),
            )
        summary = send_bulk_template(
            recipient_phones,
            tpl,
            lang,
            _template_send_params(tpl, body_params),
            image_header_link=image_link,
        )
        dispatch_label = f"custom template={tpl}"
    elif payload.image_filename:
        summary = send_bulk_image(
            recipient_phones,
            media_id=media_id,
            image_link=public_image_url if not media_id else None,
            caption=caption,
        )
        dispatch_label = "image"
    else:
        summary = send_bulk_text(recipient_phones, (payload.message or "").strip())
        dispatch_label = "text"
    audit_time = datetime.utcnow()
    result_map = {r["phone"]: r for r in summary.get("results", [])}

    for rec in payload.recipients:
        res = result_map.get(rec.phone, {})
        status_label = "success" if res.get("success") else "failed"
        err = (res.get("error") or "")[:250]
        msg_id = (res.get("provider_message_id") or "")[:120]
        details = (
            f"WhatsApp bulk {status_label}; mode={dispatch_label}; phone={rec.phone}; "
            f"image={payload.image_filename or 'na'}; "
            f"provider_message_id={msg_id or 'na'}; error={err or 'na'}"
        )
        db.add(
            Audit(
                user_id=current_admin.id,
                file_id=rec.user_id,
                file_type="user" if rec.user_id else "external",
                activity="whatsapp_bulk_send",
                activity_details=details,
                activity_datetime=audit_time,
            )
        )
    db.commit()

    failures = [r for r in summary.get("results", []) if not r.get("success")]
    return {
        "total": summary.get("total", 0),
        "sent": summary.get("sent", 0),
        "failed": summary.get("failed", 0),
        "cold_recipients": len(cold_phones) if payload.send_mode == "auto" else None,
        "warm_recipients": len(warm_phones) if payload.send_mode == "auto" else None,
        "failures": [
            {
                "phone": item.get("phone"),
                "error": item.get("error"),
                "status_code": item.get("status_code"),
            }
            for item in failures[:30]
        ],
    }
