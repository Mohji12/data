from __future__ import annotations
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel, field_validator, model_validator

from app.admin_security import get_current_admin, require_admin_type
from app.core.config import get_settings
from app.db import get_db
from app.models import Admin, Audit, Option
from app.services.whatsapp import normalize_phone, send_bulk_text

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


@router.get("/template")
def get_whatsapp_template(db: Session = Depends(get_db)):
    """Fetches the global WhatsApp message template from options."""
    opt = db.query(Option).filter(Option.option_name == "whatsapp_default_template").first()
    return {"template": opt.option_value if opt else "Hello! This is from Harish Critical Care Classes."}


@router.post("/template")
def save_whatsapp_template(payload: WhatsAppTemplatePayload, db: Session = Depends(get_db)):
    """Saves the global WhatsApp message template to options."""
    opt = db.query(Option).filter(Option.option_name == "whatsapp_default_template").first()
    if not opt:
        opt = Option(option_name="whatsapp_default_template", option_value=payload.template)
        db.add(opt)
    else:
        opt.option_value = payload.template
    db.commit()
    return {"status": "ok"}


class BulkRecipient(BaseModel):
    user_id: int | None = None
    phone: str
    name: str | None = None

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        return normalize_phone(v)


class WhatsAppBulkSendPayload(BaseModel):
    message: str
    recipients: list[BulkRecipient]
    dedupe: bool = True
    max_recipients: int = 300

    @field_validator("message")
    @classmethod
    def validate_message(cls, v: str) -> str:
        val = (v or "").strip()
        if not val:
            raise ValueError("message is required")
        if len(val) > 4096:
            raise ValueError("message is too long")
        return val

    @model_validator(mode="after")
    def validate_recipients(self) -> "WhatsAppBulkSendPayload":
        if not self.recipients:
            raise ValueError("At least one recipient is required")
        if len(self.recipients) > self.max_recipients:
            raise ValueError(f"Recipient limit exceeded (max {self.max_recipients})")
        return self


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

    summary = send_bulk_text(recipient_phones, payload.message)
    audit_time = datetime.utcnow()
    result_map = {r["phone"]: r for r in summary.get("results", [])}

    for rec in payload.recipients:
        res = result_map.get(rec.phone, {})
        status_label = "success" if res.get("success") else "failed"
        err = (res.get("error") or "")[:250]
        msg_id = (res.get("provider_message_id") or "")[:120]
        details = (
            f"WhatsApp bulk {status_label}; phone={rec.phone}; "
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
        "failures": [
            {
                "phone": item.get("phone"),
                "error": item.get("error"),
                "status_code": item.get("status_code"),
            }
            for item in failures[:30]
        ],
    }
