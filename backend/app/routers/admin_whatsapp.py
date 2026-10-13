from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.admin_security import get_current_admin, require_admin_type
from app.core.config import get_settings
from app.core.job_queue import enqueue_whatsapp_bulk, get_job_status
from app.core.redis_client import redis_enabled
from app.db import get_db
from app.models import Admin, Audit, Option
from app.services.access import get_option_value
from app.services.uploads import save_whatsapp_image
from app.services.whatsapp_bulk_dispatch import (
    BulkRecipient,
    WhatsAppBulkSendPayload,
    execute_whatsapp_bulk_send,
)

__all__ = ["BulkRecipient", "WhatsAppBulkSendPayload"]

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
    from app.services.cache import invalidate_option_cache

    invalidate_option_cache("whatsapp_default_template")
    invalidate_option_cache("whatsapp_auto_reply_on_inbound")
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


@router.post("/bulk-send", dependencies=[Depends(require_admin_type("techadmin"))])
def bulk_send_whatsapp(
    payload: WhatsAppBulkSendPayload,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
):
    settings = get_settings()
    if not settings.whatsapp_api_key or not settings.whatsapp_phone_number_id:
        raise HTTPException(status_code=503, detail="WhatsApp API is not configured")

    if redis_enabled():
        job = enqueue_whatsapp_bulk(current_admin.id, payload.model_dump(mode="json"))
        if job is not None:
            return {
                "status": "queued",
                "job_id": job.id,
                "total": len(payload.recipients),
            }

    return execute_whatsapp_bulk_send(db, current_admin, payload)


@router.get("/jobs/{job_id}", dependencies=[Depends(require_admin_type("techadmin"))])
def whatsapp_job_status(job_id: str) -> dict:
    status = get_job_status(job_id)
    if status is None:
        raise HTTPException(status_code=404, detail="Job not found or Redis unavailable")
    return status
