from __future__ import annotations

import json
import secrets
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.admin_security import get_current_admin, require_admin_type
from app.core.config import get_settings
from app.core.job_queue import enqueue_mail_send
from app.db import get_db
from app.models import (
    Admin,
    BatchMaster,
    MailCampaign,
    MailCampaignRecipient,
    MailCampaignTemplate,
    MailClickEvent,
    MailSuppression,
)
from app.services.mail_campaign_audience import parse_audience_json, parse_pasted_list, resolve_audience
from app.services.mail_suppression import (
    REASONS,
    is_permanent_smtp_error,
    serialize_suppression,
    upsert_suppression,
)
from app.services.mail_campaign_render import parse_cta_list, render_campaign_email, render_campaign_html
from app.services.mail_campaign_time import parse_ist_to_naive_utc
from app.services.mailer import send_html_email
from app.services.uploads import campaign_image_public_url, save_campaign_image

router = APIRouter(
    prefix="/admin/mail",
    tags=["admin-mail"],
    dependencies=[Depends(get_current_admin)],
)

SAMPLE_VARS = {"name": "Dr. Sample", "email": "doctor@example.com", "batch": "Batch 15"}


def _cta_payload(items: list[dict[str, str]] | None) -> str:
    cleaned = []
    for item in items or []:
        label = str(item.get("label") or "").strip()
        url = str(item.get("url") or "").strip()
        if label and url:
            cleaned.append({"label": label, "url": url})
    return json.dumps(cleaned)


def _serialize_template(row: MailCampaignTemplate) -> dict[str, Any]:
    return {
        "id": row.id,
        "name": row.name,
        "subject": row.subject,
        "preview_text": row.preview_text or "",
        "hero_image": row.hero_image or "",
        "hero_image_url": campaign_image_public_url(row.hero_image) if row.hero_image else "",
        "body_html": row.body_html or "",
        "footer_html": row.footer_html or "",
        "cta": parse_cta_list(row.cta_json),
        "status": row.status,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def _clamp_batch_size(value: Any) -> int:
    try:
        n = int(value)
    except (TypeError, ValueError):
        n = 100
    return max(1, min(n, 5000))


def _clamp_pause_seconds(*, seconds: Any = None, minutes: Any = None) -> int:
    raw = seconds
    if raw is None and minutes is not None:
        try:
            raw = int(minutes) * 60
        except (TypeError, ValueError):
            raw = 300
    try:
        n = int(raw) if raw is not None else 300
    except (TypeError, ValueError):
        n = 300
    return max(0, min(n, 86400))


def _maybe_poll_due() -> None:
    try:
        from app.jobs.mail_campaign import poll_due_campaigns

        poll_due_campaigns(requeue=False)
    except Exception:
        pass


def _serialize_campaign(row: MailCampaign) -> dict[str, Any]:
    pause_sec = int(row.send_pause_seconds or 0)
    return {
        "id": row.id,
        "name": row.name,
        "template_id": row.template_id,
        "subject_override": row.subject_override,
        "preview_text_override": row.preview_text_override,
        "audience_type": row.audience_type,
        "audience": parse_audience_json(row.audience_json),
        "status": row.status,
        "scheduled_at": row.scheduled_at.isoformat() + "Z" if row.scheduled_at else None,
        "sent_at": row.sent_at.isoformat() + "Z" if row.sent_at else None,
        "queued_count": row.queued_count or 0,
        "accepted_count": row.accepted_count or 0,
        "failed_count": row.failed_count or 0,
        "suppressed_count": row.suppressed_count or 0,
        "send_batch_size": int(row.send_batch_size or 100),
        "send_pause_seconds": pause_sec,
        "send_pause_minutes": pause_sec // 60,
        "next_wave_at": row.next_wave_at.isoformat() + "Z" if row.next_wave_at else None,
        "skip_previously_bounced": bool(getattr(row, "skip_previously_bounced", True)),
        "audience_snapshot": parse_audience_json(getattr(row, "audience_snapshot_json", None)),
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


class CtaItem(BaseModel):
    label: str
    url: str


class TemplatePayload(BaseModel):
    name: str
    subject: str
    preview_text: str = ""
    hero_image: str = ""
    body_html: str = ""
    footer_html: str = ""
    cta: list[CtaItem] = Field(default_factory=list)
    status: str = "1"


class PreviewPayload(BaseModel):
    subject: str = ""
    preview_text: str = ""
    hero_image: str = ""
    body_html: str = ""
    footer_html: str = ""
    cta: list[CtaItem] = Field(default_factory=list)
    name: str = SAMPLE_VARS["name"]
    email: str = SAMPLE_VARS["email"]
    batch: str = SAMPLE_VARS["batch"]


class TestSendPayload(BaseModel):
    to_email: Optional[str] = None
    subject: Optional[str] = None
    preview_text: Optional[str] = None
    hero_image: Optional[str] = None
    body_html: Optional[str] = None
    footer_html: Optional[str] = None
    cta: Optional[list[CtaItem]] = None


class AudiencePreviewPayload(BaseModel):
    audience_type: str
    audience: dict[str, Any] = Field(default_factory=dict)
    skip_previously_bounced: bool = True
    exclude_emails: list[str] = Field(default_factory=list)
    check_dns: bool = True


class CampaignCreatePayload(BaseModel):
    name: str
    template_id: int
    subject_override: Optional[str] = None
    preview_text_override: Optional[str] = None
    audience_type: str
    audience: dict[str, Any] = Field(default_factory=dict)
    send_mode: str = "now"
    scheduled_at_ist: Optional[str] = None
    send_batch_size: int = 100
    send_pause_minutes: Optional[int] = 5
    send_pause_seconds: Optional[int] = None
    skip_previously_bounced: bool = True
    exclude_emails: list[str] = Field(default_factory=list)


class SuppressionCreatePayload(BaseModel):
    pasted: str = ""
    reason: str = "manual_block"


class CampaignConfirmPayload(BaseModel):
    confirm: bool = True


@router.post("/templates/image")
def upload_template_image(
    request: Request,
    file: UploadFile = File(...),
    _admin: Admin = Depends(require_admin_type("techadmin")),
):
    filename = save_campaign_image(file)
    origin = str(request.base_url).rstrip("/")
    return {
        "filename": filename,
        "url": f"{origin}/upload/campaigns/{filename}",
        "public_url": campaign_image_public_url(filename),
    }


@router.get("/templates")
def list_templates(include_archived: bool = Query(False), db: Session = Depends(get_db)):
    q = db.query(MailCampaignTemplate)
    if not include_archived:
        q = q.filter(MailCampaignTemplate.status == "1")
    rows = q.order_by(MailCampaignTemplate.id.desc()).all()
    return [_serialize_template(r) for r in rows]


@router.post("/templates", dependencies=[Depends(require_admin_type("techadmin"))])
def create_template(payload: TemplatePayload, db: Session = Depends(get_db)):
    name = payload.name.strip()
    subject = payload.subject.strip()
    if not name or not subject:
        raise HTTPException(status_code=422, detail="name and subject are required")
    row = MailCampaignTemplate(
        name=name,
        subject=subject,
        preview_text=(payload.preview_text or "").strip(),
        hero_image=(payload.hero_image or "").strip(),
        body_html=payload.body_html or "",
        footer_html=payload.footer_html or "",
        cta_json=_cta_payload([c.model_dump() for c in payload.cta]),
        status="1" if payload.status != "0" else "0",
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _serialize_template(row)


@router.get("/templates/{template_id}")
def get_template(template_id: int, db: Session = Depends(get_db)):
    row = db.query(MailCampaignTemplate).filter(MailCampaignTemplate.id == template_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Template not found")
    return _serialize_template(row)


@router.put("/templates/{template_id}", dependencies=[Depends(require_admin_type("techadmin"))])
def update_template(template_id: int, payload: TemplatePayload, db: Session = Depends(get_db)):
    row = db.query(MailCampaignTemplate).filter(MailCampaignTemplate.id == template_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Template not found")
    row.name = payload.name.strip()
    row.subject = payload.subject.strip()
    row.preview_text = (payload.preview_text or "").strip()
    row.hero_image = (payload.hero_image or "").strip()
    row.body_html = payload.body_html or ""
    row.footer_html = payload.footer_html or ""
    row.cta_json = _cta_payload([c.model_dump() for c in payload.cta])
    row.status = "1" if payload.status != "0" else "0"
    db.commit()
    db.refresh(row)
    return _serialize_template(row)


@router.post("/templates/{template_id}/duplicate", dependencies=[Depends(require_admin_type("techadmin"))])
def duplicate_template(template_id: int, db: Session = Depends(get_db)):
    row = db.query(MailCampaignTemplate).filter(MailCampaignTemplate.id == template_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Template not found")
    copy = MailCampaignTemplate(
        name=f"{row.name} (copy)",
        subject=row.subject,
        preview_text=row.preview_text,
        hero_image=row.hero_image,
        body_html=row.body_html,
        footer_html=row.footer_html,
        cta_json=row.cta_json,
        status="1",
    )
    db.add(copy)
    db.commit()
    db.refresh(copy)
    return _serialize_template(copy)


@router.post("/templates/{template_id}/archive", dependencies=[Depends(require_admin_type("techadmin"))])
def archive_template(template_id: int, db: Session = Depends(get_db)):
    row = db.query(MailCampaignTemplate).filter(MailCampaignTemplate.id == template_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Template not found")
    row.status = "0"
    db.commit()
    return {"status": "ok"}


@router.delete("/templates/{template_id}", dependencies=[Depends(require_admin_type("techadmin"))])
def delete_template(template_id: int, db: Session = Depends(get_db)):
    used = db.query(MailCampaign.id).filter(MailCampaign.template_id == template_id).first()
    if used:
        raise HTTPException(status_code=409, detail="Template is used by a campaign. Archive it instead.")
    row = db.query(MailCampaignTemplate).filter(MailCampaignTemplate.id == template_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Template not found")
    db.delete(row)
    db.commit()
    return {"status": "ok"}


@router.post("/templates/preview")
def preview_template(payload: PreviewPayload, request: Request):
    hero = (payload.hero_image or "").strip()
    if hero and not hero.lower().startswith(("http://", "https://")):
        origin = str(request.base_url).rstrip("/")
        hero = f"{origin}/upload/campaigns/{Path(hero).name}"
    subj, html = render_campaign_html(
        subject=payload.subject,
        preview_text=payload.preview_text,
        hero_image=hero,
        body_html=payload.body_html,
        footer_html=payload.footer_html,
        cta=[c.model_dump() for c in payload.cta],
        values={
            "name": SAMPLE_VARS["name"],
            "email": SAMPLE_VARS["email"],
            "batch": SAMPLE_VARS["batch"],
        },
        tracking_token=None,
    )
    return {"subject": subj, "html": html, "preview_text": payload.preview_text}


@router.post("/templates/{template_id}/test-send", dependencies=[Depends(require_admin_type("techadmin"))])
def test_send_template(template_id: int, payload: TestSendPayload, db: Session = Depends(get_db)):
    row = db.query(MailCampaignTemplate).filter(MailCampaignTemplate.id == template_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Template not found")
    to_email = (payload.to_email or "").strip()
    if "@" not in to_email:
        raise HTTPException(status_code=422, detail="Enter a valid test email address")
    subject = payload.subject if payload.subject is not None else row.subject
    preview = payload.preview_text if payload.preview_text is not None else row.preview_text
    hero = payload.hero_image if payload.hero_image is not None else row.hero_image
    body = payload.body_html if payload.body_html is not None else row.body_html
    footer = payload.footer_html if payload.footer_html is not None else row.footer_html
    cta = [c.model_dump() for c in payload.cta] if payload.cta is not None else parse_cta_list(row.cta_json)
    subj, html, inline = render_campaign_email(
        subject=subject or "",
        preview_text=preview or "",
        hero_image=hero or "",
        body_html=body or "",
        footer_html=footer or "",
        cta=cta,
        values=SAMPLE_VARS,
        tracking_token=None,
    )
    try:
        send_html_email(to_email, f"[TEST] {subj}", html, inline_images=inline)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {"status": "sent", "to": to_email}


@router.post("/audience/preview")
def audience_preview(payload: AudiencePreviewPayload, db: Session = Depends(get_db)):
    try:
        result = resolve_audience(
            db,
            payload.audience_type,
            payload.audience,
            skip_previously_bounced=payload.skip_previously_bounced,
            exclude_emails=payload.exclude_emails,
            check_dns=payload.check_dns,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {
        "count": result["count"],
        "preview": result["preview"],
        "invalid": result["invalid"],
        "invalid_count": result["invalid_count"],
        "duplicate_count": result["duplicate_count"],
        "duplicate_address_count": result.get("duplicate_address_count") or 0,
        "duplicate_emails": result.get("duplicate_emails") or [],
        "unverified": result.get("unverified") or [],
        "unverified_count": result.get("unverified_count") or 0,
        "previously_bounced_count": result.get("previously_bounced_count") or 0,
        "disposable_count": result.get("disposable_count") or 0,
        "unsubscribed_count": result.get("unsubscribed_count") or 0,
        "complaints_count": result.get("complaints_count") or 0,
        "role_warning_count": result.get("role_warning_count") or 0,
        "flagged": result.get("flagged") or [],
        "snapshot": result.get("snapshot") or {},
        "eligible": result["count"],
    }


@router.get("/batches")
def mail_batches(db: Session = Depends(get_db)):
    rows = (
        db.query(BatchMaster.id, BatchMaster.name)
        .order_by(BatchMaster.display_order.desc(), BatchMaster.id.desc())
        .all()
    )
    return [{"id": r.id, "name": r.name} for r in rows if (r.name or "").strip()]


@router.get("/campaigns")
def list_campaigns(db: Session = Depends(get_db)):
    _maybe_poll_due()
    rows = db.query(MailCampaign).order_by(MailCampaign.id.desc()).limit(200).all()
    return [_serialize_campaign(r) for r in rows]


@router.get("/dashboard")
def mail_dashboard(db: Session = Depends(get_db)):
    _maybe_poll_due()
    total = db.query(func.count(MailCampaign.id)).scalar() or 0
    sent = db.query(func.count(MailCampaign.id)).filter(MailCampaign.status == "sent").scalar() or 0
    scheduled = (
        db.query(func.count(MailCampaign.id)).filter(MailCampaign.status == "scheduled").scalar() or 0
    )
    templates = (
        db.query(func.count(MailCampaignTemplate.id)).filter(MailCampaignTemplate.status == "1").scalar() or 0
    )
    recent = db.query(MailCampaign).order_by(MailCampaign.id.desc()).limit(8).all()
    settings = get_settings()
    return {
        "campaigns": total,
        "sent": sent,
        "scheduled": scheduled,
        "templates": templates,
        "default_test_to": (settings.smtp_from or settings.smtp_username or "").strip(),
        "recent": [_serialize_campaign(r) for r in recent],
    }


@router.post("/campaigns", dependencies=[Depends(require_admin_type("techadmin"))])
def create_campaign(
    payload: CampaignCreatePayload,
    db: Session = Depends(get_db),
    admin: Admin = Depends(get_current_admin),
):
    tpl = db.query(MailCampaignTemplate).filter(MailCampaignTemplate.id == payload.template_id).first()
    if not tpl or tpl.status != "1":
        raise HTTPException(status_code=404, detail="Active template not found")
    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=422, detail="Campaign name is required")
    send_mode = (payload.send_mode or "now").strip().lower()
    scheduled_at = None
    status = "draft"
    if send_mode == "later":
        scheduled_at = parse_ist_to_naive_utc(payload.scheduled_at_ist)
        if not scheduled_at:
            raise HTTPException(status_code=422, detail="scheduled_at_ist is required")
        status = "draft"
    audience = dict(payload.audience or {})
    if payload.exclude_emails:
        audience["exclude_emails"] = [e.strip().lower() for e in payload.exclude_emails if e.strip()]
    row = MailCampaign(
        name=name,
        template_id=tpl.id,
        subject_override=(payload.subject_override or "").strip() or None,
        preview_text_override=(payload.preview_text_override or "").strip() or None,
        audience_type=(payload.audience_type or "").strip().lower(),
        audience_json=json.dumps(audience),
        status=status,
        scheduled_at=scheduled_at,
        send_batch_size=_clamp_batch_size(payload.send_batch_size),
        send_pause_seconds=_clamp_pause_seconds(
            seconds=payload.send_pause_seconds,
            minutes=payload.send_pause_minutes,
        ),
        skip_previously_bounced=bool(payload.skip_previously_bounced),
        audience_snapshot_json=json.dumps(
            {
                "skip_previously_bounced": bool(payload.skip_previously_bounced),
                "exclude_emails": [e.strip().lower() for e in payload.exclude_emails if e.strip()],
            }
        ),
        created_by_admin_id=admin.id,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _serialize_campaign(row)


@router.get("/campaigns/{campaign_id}")
def get_campaign(campaign_id: int, db: Session = Depends(get_db)):
    row = db.query(MailCampaign).filter(MailCampaign.id == campaign_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Campaign not found")
    data = _serialize_campaign(row)
    tpl = db.query(MailCampaignTemplate).filter(MailCampaignTemplate.id == row.template_id).first()
    data["template"] = _serialize_template(tpl) if tpl else None
    return data


@router.post("/campaigns/{campaign_id}/confirm", dependencies=[Depends(require_admin_type("techadmin"))])
def confirm_campaign(campaign_id: int, payload: CampaignConfirmPayload, db: Session = Depends(get_db)):
    if not payload.confirm:
        raise HTTPException(status_code=422, detail="Confirmation required")
    camp = db.query(MailCampaign).filter(MailCampaign.id == campaign_id).first()
    if not camp:
        raise HTTPException(status_code=404, detail="Campaign not found")
    if camp.status not in {"draft"}:
        raise HTTPException(status_code=409, detail="Campaign already confirmed")
    audience = parse_audience_json(camp.audience_json)
    snapshot = parse_audience_json(getattr(camp, "audience_snapshot_json", None))
    skip_bounced = bool(getattr(camp, "skip_previously_bounced", True))
    exclude = snapshot.get("exclude_emails") or audience.get("exclude_emails") or []
    try:
        resolved = resolve_audience(
            db,
            camp.audience_type,
            audience,
            skip_previously_bounced=skip_bounced,
            exclude_emails=list(exclude),
            check_dns=True,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if resolved["count"] < 1:
        raise HTTPException(status_code=422, detail="No eligible recipients")
    existing = db.query(MailCampaignRecipient.id).filter(MailCampaignRecipient.campaign_id == camp.id).first()
    if existing:
        raise HTTPException(status_code=409, detail="Recipients already created")
    for rec in resolved["recipients"]:
        db.add(
            MailCampaignRecipient(
                campaign_id=camp.id,
                user_id=rec.get("user_id"),
                email=rec["email"],
                name=rec.get("name") or "",
                batch=rec.get("batch") or "",
                status="pending",
                tracking_token=secrets.token_urlsafe(24),
            )
        )
    camp.queued_count = resolved["count"]
    camp.audience_snapshot_json = json.dumps(resolved.get("snapshot") or snapshot)
    if camp.scheduled_at and camp.scheduled_at > datetime.utcnow():
        camp.status = "scheduled"
    else:
        camp.status = "queued"
    db.commit()
    from app.jobs.mail_campaign import send_campaign

    if camp.status == "queued":
        enqueue_mail_send(camp.id)
        send_campaign(camp.id)
        db.refresh(camp)
    elif camp.status == "scheduled" and camp.scheduled_at:
        delay = max(1, int((camp.scheduled_at - datetime.utcnow()).total_seconds()))
        enqueue_mail_send(camp.id, delay_seconds=delay)
    return _serialize_campaign(camp)


@router.post("/campaigns/{campaign_id}/cancel", dependencies=[Depends(require_admin_type("techadmin"))])
def cancel_campaign(campaign_id: int, db: Session = Depends(get_db)):
    camp = db.query(MailCampaign).filter(MailCampaign.id == campaign_id).first()
    if not camp:
        raise HTTPException(status_code=404, detail="Campaign not found")
    if camp.status in {"sent", "failed"}:
        raise HTTPException(status_code=409, detail="Cannot cancel a finished campaign")
    camp.status = "cancelled"
    db.commit()
    return _serialize_campaign(camp)


@router.get("/campaigns/{campaign_id}/analytics")
def campaign_analytics(campaign_id: int, db: Session = Depends(get_db)):
    _maybe_poll_due()
    camp = db.query(MailCampaign).filter(MailCampaign.id == campaign_id).first()
    if not camp:
        raise HTTPException(status_code=404, detail="Campaign not found")
    accepted = (
        db.query(func.count(MailCampaignRecipient.id))
        .filter(MailCampaignRecipient.campaign_id == campaign_id, MailCampaignRecipient.status == "accepted")
        .scalar()
        or 0
    )
    failed = (
        db.query(func.count(MailCampaignRecipient.id))
        .filter(MailCampaignRecipient.campaign_id == campaign_id, MailCampaignRecipient.status == "failed")
        .scalar()
        or 0
    )
    suppressed = (
        db.query(func.count(MailCampaignRecipient.id))
        .filter(MailCampaignRecipient.campaign_id == campaign_id, MailCampaignRecipient.status == "suppressed")
        .scalar()
        or 0
    )
    bounced = (
        db.query(func.count(MailCampaignRecipient.id))
        .filter(
            MailCampaignRecipient.campaign_id == campaign_id,
            MailCampaignRecipient.delivery_status.in_(["hard_bounce", "soft_bounce"]),
        )
        .scalar()
        or 0
    )
    delivered = (
        db.query(func.count(MailCampaignRecipient.id))
        .filter(MailCampaignRecipient.campaign_id == campaign_id, MailCampaignRecipient.delivery_status == "delivered")
        .scalar()
        or 0
    )
    unique_opens = (
        db.query(func.count(func.distinct(MailClickEvent.recipient_id)))
        .filter(MailClickEvent.campaign_id == campaign_id)
        .scalar()
        or 0
    )
    total_clicks = (
        db.query(func.count(MailClickEvent.id)).filter(MailClickEvent.campaign_id == campaign_id).scalar() or 0
    )
    recent = (
        db.query(MailClickEvent, MailCampaignRecipient.email)
        .join(MailCampaignRecipient, MailCampaignRecipient.id == MailClickEvent.recipient_id)
        .filter(MailClickEvent.campaign_id == campaign_id)
        .order_by(MailClickEvent.id.desc())
        .limit(30)
        .all()
    )
    rate = round((unique_opens / accepted) * 100, 1) if accepted else 0.0
    return {
        "campaign": _serialize_campaign(camp),
        "sent": accepted,
        "accepted": accepted,
        "delivered": delivered,
        "bounced": bounced,
        "failed": failed,
        "suppressed": suppressed,
        "unique_opens": unique_opens,
        "total_clicks": total_clicks,
        "open_rate": rate,
        "recent_clicks": [
            {
                "email": email,
                "dest_url": ev.dest_url,
                "at": ev.created_at.isoformat() + "Z" if ev.created_at else None,
            }
            for ev, email in recent
        ],
    }


@router.get("/suppressions")
def list_suppressions(
    q: str = Query(""),
    reason: str = Query(""),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    db: Session = Depends(get_db),
):
    query = db.query(MailSuppression)
    needle = (q or "").strip().lower()
    if needle:
        query = query.filter(MailSuppression.email.contains(needle))
    reason_key = (reason or "").strip().lower()
    if reason_key and reason_key in REASONS:
        query = query.filter(MailSuppression.reason == reason_key)
    total = query.count()
    rows = (
        query.order_by(MailSuppression.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "reasons": list(REASONS),
        "items": [serialize_suppression(r) for r in rows],
    }


@router.post("/suppressions", dependencies=[Depends(require_admin_type("techadmin"))])
def create_suppressions(
    payload: SuppressionCreatePayload,
    db: Session = Depends(get_db),
    admin: Admin = Depends(get_current_admin),
):
    reason = (payload.reason or "manual_block").strip().lower()
    if reason not in REASONS:
        reason = "manual_block"
    accepted, invalid, _dupes = parse_pasted_list(payload.pasted)
    added = 0
    for rec in accepted:
        row = upsert_suppression(
            db,
            rec["email"],
            reason,
            source="admin",
            admin_id=admin.id,
        )
        if row:
            added += 1
    db.commit()
    return {"added": added, "invalid": invalid, "invalid_count": len(invalid)}


@router.delete("/suppressions/{suppression_id}", dependencies=[Depends(require_admin_type("techadmin"))])
def delete_suppression(suppression_id: int, db: Session = Depends(get_db)):
    row = db.query(MailSuppression).filter(MailSuppression.id == suppression_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Suppression not found")
    db.delete(row)
    db.commit()
    return {"status": "ok"}


@router.post("/campaigns/{campaign_id}/suppress-smtp-failures", dependencies=[Depends(require_admin_type("techadmin"))])
def suppress_smtp_failures(
    campaign_id: int,
    db: Session = Depends(get_db),
    admin: Admin = Depends(get_current_admin),
):
    camp = db.query(MailCampaign).filter(MailCampaign.id == campaign_id).first()
    if not camp:
        raise HTTPException(status_code=404, detail="Campaign not found")
    rows = (
        db.query(MailCampaignRecipient)
        .filter(MailCampaignRecipient.campaign_id == campaign_id, MailCampaignRecipient.status == "failed")
        .all()
    )
    added = 0
    for rec in rows:
        if not is_permanent_smtp_error(rec.last_error or ""):
            continue
        upsert_suppression(
            db,
            rec.email,
            "hard_bounce",
            source="smtp_5xx",
            diagnostic=(rec.last_error or "")[:2000],
            admin_id=admin.id,
        )
        added += 1
    db.commit()
    return {"added": added, "reviewed": len(rows)}
