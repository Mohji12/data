from __future__ import annotations
import csv
import io
from datetime import date as date_type, datetime
from typing import Any, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile
from pydantic import BaseModel
from sqlalchemy import func, inspect, or_
from sqlalchemy.orm import Session, load_only

from app.admin_security import get_current_admin, require_admin_type
from app.db import get_db
from app.models import BatchMaster, EmailTemplateMaster, LoginActivity, Option, Testimonial, User, Video, VideoQuestion
from app.services.batch_rename import rename_batch_references
from app.services.registration import build_registration_catalog
from app.services.uploads import save_batch_brochure, save_batch_video

router = APIRouter(prefix="/admin/misc", tags=["admin-misc"], dependencies=[Depends(get_current_admin)])


def _batch_has_column(db: Session, column_name: str) -> bool:
    bind = db.get_bind()
    cols = inspect(bind).get_columns("batch_master")
    return any((c.get("name") or "").lower() == column_name.lower() for c in cols)


def _batch_load_only(db: Session):
    fields = [
        BatchMaster.id,
        BatchMaster.name,
        BatchMaster.status,
        BatchMaster.display_order,
        BatchMaster.registration_fee_structure,
        BatchMaster.description,
        BatchMaster.video_url,
        BatchMaster.video_file,
        BatchMaster.brochure_file,
    ]
    if _batch_has_column(db, "package_subscription"):
        fields.append(BatchMaster.package_subscription)
    return load_only(*fields)


def _batch_package_subscription_value(db: Session, row: BatchMaster) -> str | None:
    if _batch_has_column(db, "package_subscription"):
        val = getattr(row, "package_subscription", None)
        if val is not None and str(val).strip():
            return str(val).strip()
    return None


def _brochure_option_key(batch_name: str) -> str:
    return f"batch_brochure::{(batch_name or '').strip().casefold()}"


def _upsert_option(db: Session, option_name: str, option_value: str) -> None:
    row = db.query(Option).filter(Option.option_name == option_name).first()
    if not row:
        row = Option(option_name=option_name, option_value=option_value)
    else:
        row.option_value = option_value
    db.add(row)


@router.get("/summary")
def admin_dashboard_summary(db: Session = Depends(get_db)) -> dict:
    """Counts + recent users for React admin home (parity with legacy dashboard widgets)."""
    total_users = db.query(func.count(User.id)).scalar() or 0
    active_users = (
        db.query(func.count(User.id))
        .filter(func.lower(func.coalesce(User.payment_status, "")) == "credit")
        .scalar()
        or 0
    )
    revenue = (
        db.query(func.coalesce(func.sum(User.total_amount), 0.0))
        .filter(func.lower(func.coalesce(User.payment_status, "")) == "credit")
        .scalar()
        or 0.0
    )
    total_videos = db.query(func.count(Video.id)).scalar() or 0
    pending_video_questions = db.query(func.count(VideoQuestion.id)).scalar() or 0

    recent = (
        db.query(User)
        .order_by(User.id.desc())
        .limit(12)
        .all()
    )
    recent_users = [
        {
            "id": u.id,
            "name": u.name,
            "email": u.email,
            "subscription": u.subscription,
            "approve": u.approve or "0",
        }
        for u in recent
    ]
    return {
        "total_users": int(total_users),
        "active_users": int(active_users),
        "revenue_estimated": float(revenue),
        "total_videos": int(total_videos),
        "pending_video_questions": int(pending_video_questions),
        "recent_users": recent_users,
    }


@router.get("/login-activity")
def list_login_activity(
    q: Optional[str] = Query(None, description="Search name, email, or phone"),
    on_date: Optional[date_type] = Query(None, description="Filter rows on this calendar date (activity time)"),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=1000),
    sort_by: str = Query("id"),
    order: str = Query("desc"),
    db: Session = Depends(get_db),
) -> dict:
    """Rows from `login_activity` joined with `users` (same source as PHP admin LoginActivity)."""
    query = db.query(LoginActivity, User).join(User, User.id == LoginActivity.users_id)
    if q:
        s = f"%{q.strip().lower()}%"
        query = query.filter(
            or_(
                func.lower(func.coalesce(User.email, "")).like(s),
                func.lower(func.coalesce(User.name, "")).like(s),
                func.lower(func.coalesce(User.contact_number, "")).like(s),
            )
        )
    if on_date is not None:
        query = query.filter(func.date(LoginActivity.activity_datetime) == on_date)

    total = (
        db.query(func.count(LoginActivity.id))
        .select_from(LoginActivity)
        .join(User, User.id == LoginActivity.users_id)
    )
    if q:
        s = f"%{q.strip().lower()}%"
        total = total.filter(
            or_(
                func.lower(func.coalesce(User.email, "")).like(s),
                func.lower(func.coalesce(User.name, "")).like(s),
                func.lower(func.coalesce(User.contact_number, "")).like(s),
            )
        )
    if on_date is not None:
        total = total.filter(func.date(LoginActivity.activity_datetime) == on_date)
    total_n = total.scalar() or 0

    if sort_by == "user_name":
        sort_attr = User.name
    elif sort_by == "email":
        sort_attr = User.email
    elif sort_by == "contact_number":
        sort_attr = User.contact_number
    elif sort_by == "activity":
        sort_attr = LoginActivity.activity
    elif sort_by == "activity_datetime":
        sort_attr = LoginActivity.activity_datetime
    else:
        sort_attr = getattr(LoginActivity, sort_by, LoginActivity.id)

    if order.lower() == "asc":
        query = query.order_by(sort_attr.asc())
    else:
        query = query.order_by(sort_attr.desc())

    rows = query.offset(offset).limit(limit).all()
    items = []
    for la, u in rows:
        parts = [p for p in [(u.title or "").strip(), (u.name or "").strip()] if p]
        display_name = " ".join(parts) if parts else (u.email or f"User #{u.id}")
        items.append(
            {
                "id": la.id,
                "user_id": la.users_id,
                "user_name": display_name,
                "email": u.email,
                "contact_number": u.contact_number,
                "activity": la.activity,
                "activity_datetime": la.activity_datetime.isoformat() if la.activity_datetime else None,
            }
        )
    return {"total": total_n, "items": items}


@router.get("/login-activity/export.csv")
def export_login_activity(db: Session = Depends(get_db)) -> Response:
    rows = db.query(LoginActivity, User).join(User, User.id == LoginActivity.users_id).order_by(LoginActivity.id.desc()).all()
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["id", "user_id", "name", "email", "phone", "activity", "activity_datetime"])
    for la, u in rows:
        parts = [p for p in [(u.title or "").strip(), (u.name or "").strip()] if p]
        display_name = " ".join(parts) if parts else ""
        w.writerow(
            [
                la.id,
                la.users_id,
                display_name,
                u.email or "",
                u.contact_number or "",
                la.activity or "",
                la.activity_datetime.isoformat() if la.activity_datetime else "",
            ]
        )
    return Response(content=buf.getvalue(), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=login_activity.csv"})


class TestimonialPayload(BaseModel):
    text: str
    display_order: int = 0
    status: str = "1"


@router.get("/testimonials")
def list_testimonials(db: Session = Depends(get_db)) -> list[dict]:
    rows = (
        db.query(Testimonial)
        .order_by(Testimonial.display_order.asc(), Testimonial.id.desc())
        .all()
    )
    return [
        {
            "id": t.id,
            "text": t.text or "",
            "display_order": t.display_order if t.display_order is not None else 0,
            "status": t.status,
        }
        for t in rows
    ]


@router.post("/testimonials", dependencies=[Depends(require_admin_type("techadmin"))])
def create_testimonial(payload: TestimonialPayload, db: Session = Depends(get_db)) -> dict:
    body = (payload.text or "").strip()
    if not body:
        raise HTTPException(status_code=422, detail="Text is required.")
    t = Testimonial(
        text=body,
        display_order=max(0, int(payload.display_order or 0)),
        status=payload.status or "1",
    )
    db.add(t)
    db.commit()
    db.refresh(t)
    return {"id": t.id}


@router.put("/testimonials/{testimonial_id}", dependencies=[Depends(require_admin_type("techadmin"))])
def update_testimonial(testimonial_id: int, payload: TestimonialPayload, db: Session = Depends(get_db)) -> dict:
    t = db.query(Testimonial).filter(Testimonial.id == testimonial_id).first()
    if not t:
        raise HTTPException(status_code=404, detail="Testimonial not found")
    body = (payload.text or "").strip()
    if not body:
        raise HTTPException(status_code=422, detail="Text is required.")
    t.text = body
    t.display_order = max(0, int(payload.display_order or 0))
    t.status = payload.status or "1"
    db.add(t)
    db.commit()
    return {"status": "ok"}


@router.delete("/testimonials/{testimonial_id}", dependencies=[Depends(require_admin_type("techadmin"))])
def delete_testimonial(testimonial_id: int, db: Session = Depends(get_db)) -> dict:
    t = db.query(Testimonial).filter(Testimonial.id == testimonial_id).first()
    if not t:
        raise HTTPException(status_code=404, detail="Testimonial not found")
    db.delete(t)
    db.commit()
    return {"status": "ok"}


class BatchPayload(BaseModel):
    name: str
    status: str = "1"
    display_order: int = 0
    registration_fee_structure: Optional[str] = None
    description: Optional[str] = None
    video_url: Optional[str] = None
    video_file: Optional[str] = None
    brochure_file: Optional[str] = None
    package_subscription: Optional[str] = None


ALLOWED_EMAIL_TEMPLATE_TYPES = {
    "registration_thank_you",
    "document_verified",
    "document_denied",
}


class EmailTemplatePayload(BaseModel):
    batch_id: int
    template_type: str
    subject: str
    body_html: str
    status: str = "1"


def _normalize_template_type(raw: str) -> str:
    value = (raw or "").strip().lower()
    if value not in ALLOWED_EMAIL_TEMPLATE_TYPES:
        raise HTTPException(
            status_code=422,
            detail=f"template_type must be one of: {', '.join(sorted(ALLOWED_EMAIL_TEMPLATE_TYPES))}",
        )
    return value


def _validate_email_template_payload(payload: EmailTemplatePayload) -> tuple[str, str, str]:
    template_type = _normalize_template_type(payload.template_type)
    subject = (payload.subject or "").strip()
    body_html = (payload.body_html or "").strip()
    if not subject:
        raise HTTPException(status_code=422, detail="subject is required")
    if not body_html:
        raise HTTPException(status_code=422, detail="body_html is required")
    status = str(payload.status or "1").strip()
    if status not in ("0", "1"):
        raise HTTPException(status_code=422, detail="status must be 0 or 1")
    return template_type, subject, status


def _serialize_email_template(row: EmailTemplateMaster, batch_name: str | None = None) -> dict:
    return {
        "id": row.id,
        "batch_id": row.batch_id,
        "batch_name": batch_name,
        "template_type": row.template_type,
        "subject": row.subject,
        "body_html": row.body_html,
        "status": row.status,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


@router.get("/batches")
def list_batches(
    q: Optional[str] = Query(None),
    sort_by: str = Query("id"),
    order: str = Query("desc"),
    db: Session = Depends(get_db),
) -> list[dict]:
    has_brochure = _batch_has_column(db, "brochure_file")
    query = db.query(BatchMaster).options(_batch_load_only(db))
    
    if q:
        query = query.filter(BatchMaster.name.ilike(f"%{q}%"))

    if order.lower() == "asc":
        query = query.order_by(getattr(BatchMaster, sort_by).asc())
    else:
        query = query.order_by(getattr(BatchMaster, sort_by).desc())

    rows = query.all()
    brochure_map: dict[str, str] = {}
    if not has_brochure:
        keys = [_brochure_option_key((b.name or "").strip()) for b in rows if (b.name or "").strip()]
        if keys:
            opt_rows = db.query(Option).filter(Option.option_name.in_(keys)).all()
            brochure_map = {str(o.option_name): str(o.option_value or "").strip() for o in opt_rows}
    return [
        {
            "id": b.id,
            "name": b.name,
            "status": b.status,
            "display_order": b.display_order if b.display_order is not None else 0,
            "registration_fee_structure": b.registration_fee_structure,
            "description": b.description,
            "video_url": b.video_url,
            "video_file": b.video_file,
            "video_resolved_url": (
                f"/upload/batch_videos/{b.video_file}" if (b.video_file or "").strip() else None
            ),
            "brochure_file": (
                getattr(b, "brochure_file", None)
                if has_brochure
                else brochure_map.get(_brochure_option_key((b.name or "").strip()))
            ),
            "brochure_url": (
                (
                    f"/upload/brochures/{getattr(b, 'brochure_file', None)}"
                    if has_brochure
                    else (
                        f"/upload/brochures/{brochure_map.get(_brochure_option_key((b.name or '').strip()))}"
                        if (brochure_map.get(_brochure_option_key((b.name or '').strip())) or "").strip()
                        else None
                    )
                )
            ),
            "package_subscription": _batch_package_subscription_value(db, b),
        }
        for b in rows
    ]


@router.get("/batches/launch-readiness")
def batch_launch_readiness(db: Session = Depends(get_db)) -> list[dict]:
    items = build_registration_catalog(db, include_inactive=True)
    return [
        {
            "batch_id": i.batch_id,
            "name": i.batch_name,
            "slug": i.batch_slug,
            "status": i.status,
            "launch_ready": i.launch_ready,
            "indian_package_count": i.indian_package_count,
            "foreign_package_count": i.foreign_package_count,
            "issues": i.launch_issues,
        }
        for i in items
    ]


@router.post("/batches", dependencies=[Depends(require_admin_type("techadmin"))])
def create_batch(payload: BatchPayload, db: Session = Depends(get_db)) -> dict:
    name = (payload.name or "").strip()
    b = BatchMaster(
        name=name,
        status=payload.status or "1",
        display_order=max(0, int(payload.display_order or 0)),
        registration_fee_structure=(payload.registration_fee_structure or "").strip() or None,
        description=(payload.description or "").strip() or None,
        video_url=(payload.video_url or "").strip() or None,
        video_file=(payload.video_file or "").strip() or None,
    )
    brochure_file = (payload.brochure_file or "").strip() or None
    has_brochure = _batch_has_column(db, "brochure_file")
    has_pkg_sub = _batch_has_column(db, "package_subscription")
    if has_brochure:
        b.brochure_file = brochure_file
    if has_pkg_sub:
        b.package_subscription = (payload.package_subscription or "").strip() or None
    db.add(b)
    if (not has_brochure) and name:
        _upsert_option(db, _brochure_option_key(name), brochure_file or "")
    db.commit()
    db.refresh(b)
    return {"id": b.id}


@router.put("/batches/{batch_id}", dependencies=[Depends(require_admin_type("techadmin"))])
def update_batch(batch_id: int, payload: BatchPayload, db: Session = Depends(get_db)) -> dict:
    b = (
        db.query(BatchMaster)
        .options(_batch_load_only(db))
        .filter(BatchMaster.id == batch_id)
        .first()
    )
    if not b:
        raise HTTPException(status_code=404, detail="Batch not found")
    old_name = (b.name or "").strip()
    new_name = (payload.name or "").strip()
    rename_counts = None
    if old_name.casefold() != new_name.casefold():
        rename_counts = rename_batch_references(db, old_name, new_name, b.id)
    b.name = new_name
    b.status = payload.status or "1"
    b.display_order = max(0, int(payload.display_order or 0))
    b.registration_fee_structure = (payload.registration_fee_structure or "").strip() or None
    b.description = (payload.description or "").strip() or None
    b.video_url = (payload.video_url or "").strip() or None
    b.video_file = (payload.video_file or "").strip() or None
    brochure_file = (payload.brochure_file or "").strip() or None
    has_brochure = _batch_has_column(db, "brochure_file")
    has_pkg_sub = _batch_has_column(db, "package_subscription")
    if has_brochure:
        b.brochure_file = brochure_file
    elif new_name:
        _upsert_option(db, _brochure_option_key(new_name), brochure_file or "")
    if has_pkg_sub:
        b.package_subscription = (payload.package_subscription or "").strip() or None
    db.add(b)
    db.commit()
    result: dict = {"status": "ok"}
    if rename_counts is not None:
        result["rename"] = rename_counts
    return result


@router.post("/batches/upload-brochure", dependencies=[Depends(require_admin_type("techadmin"))])
def upload_batch_brochure(file: UploadFile = File(...)) -> dict:
    filename = save_batch_brochure(file)
    return {
        "file_name": filename,
        "brochure_url": f"/upload/brochures/{filename}",
    }


@router.post("/batches/upload-video", dependencies=[Depends(require_admin_type("techadmin"))])
def upload_batch_video(file: UploadFile = File(...)) -> dict:
    filename = save_batch_video(file)
    return {
        "file_name": filename,
        "video_url": f"/upload/batch_videos/{filename}",
    }


@router.delete("/batches/{batch_id}", dependencies=[Depends(require_admin_type("techadmin"))])
def delete_batch(batch_id: int, db: Session = Depends(get_db)) -> dict:
    b = (
        db.query(BatchMaster)
        .options(load_only(BatchMaster.id))
        .filter(BatchMaster.id == batch_id)
        .first()
    )
    if not b:
        raise HTTPException(status_code=404, detail="Batch not found")
    db.delete(b)
    db.commit()
    return {"status": "ok"}


@router.get("/email-templates")
def list_email_templates(
    batch_id: Optional[int] = Query(None),
    template_type: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    db: Session = Depends(get_db),
) -> list[dict]:
    query = (
        db.query(EmailTemplateMaster, BatchMaster.name)
        .join(BatchMaster, BatchMaster.id == EmailTemplateMaster.batch_id)
    )
    if batch_id is not None:
        query = query.filter(EmailTemplateMaster.batch_id == batch_id)
    if template_type and template_type.strip():
        query = query.filter(EmailTemplateMaster.template_type == _normalize_template_type(template_type))
    if status is not None and str(status).strip() != "":
        st = str(status).strip()
        if st not in ("0", "1"):
            raise HTTPException(status_code=422, detail="status must be 0 or 1")
        query = query.filter(EmailTemplateMaster.status == st)

    rows = query.order_by(EmailTemplateMaster.id.desc()).all()
    return [_serialize_email_template(row, batch_name=name) for row, name in rows]


@router.get("/email-templates/{template_id}")
def get_email_template(template_id: int, db: Session = Depends(get_db)) -> dict:
    row = (
        db.query(EmailTemplateMaster, BatchMaster.name)
        .join(BatchMaster, BatchMaster.id == EmailTemplateMaster.batch_id)
        .filter(EmailTemplateMaster.id == template_id)
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Email template not found")
    tpl, batch_name = row
    return _serialize_email_template(tpl, batch_name=batch_name)


@router.post("/email-templates", dependencies=[Depends(require_admin_type("techadmin"))])
def create_email_template(payload: EmailTemplatePayload, db: Session = Depends(get_db)) -> dict:
    template_type, subject, status = _validate_email_template_payload(payload)
    batch = db.query(BatchMaster).filter(BatchMaster.id == payload.batch_id).first()
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")
    existing = (
        db.query(EmailTemplateMaster)
        .filter(
            EmailTemplateMaster.batch_id == payload.batch_id,
            EmailTemplateMaster.template_type == template_type,
        )
        .first()
    )
    if existing:
        raise HTTPException(status_code=409, detail="Template already exists for this batch and template type")
    row = EmailTemplateMaster(
        batch_id=payload.batch_id,
        template_type=template_type,
        subject=subject,
        body_html=(payload.body_html or "").strip(),
        status=status,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"id": row.id}


@router.put("/email-templates/{template_id}", dependencies=[Depends(require_admin_type("techadmin"))])
def update_email_template(template_id: int, payload: EmailTemplatePayload, db: Session = Depends(get_db)) -> dict:
    template_type, subject, status = _validate_email_template_payload(payload)
    batch = db.query(BatchMaster).filter(BatchMaster.id == payload.batch_id).first()
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")

    row = db.query(EmailTemplateMaster).filter(EmailTemplateMaster.id == template_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Email template not found")

    duplicate = (
        db.query(EmailTemplateMaster.id)
        .filter(
            EmailTemplateMaster.id != template_id,
            EmailTemplateMaster.batch_id == payload.batch_id,
            EmailTemplateMaster.template_type == template_type,
        )
        .first()
    )
    if duplicate:
        raise HTTPException(status_code=409, detail="Template already exists for this batch and template type")

    row.batch_id = payload.batch_id
    row.template_type = template_type
    row.subject = subject
    row.body_html = (payload.body_html or "").strip()
    row.status = status
    db.add(row)
    db.commit()
    return {"status": "ok"}


@router.delete("/email-templates/{template_id}", dependencies=[Depends(require_admin_type("techadmin"))])
def delete_email_template(template_id: int, db: Session = Depends(get_db)) -> dict:
    row = db.query(EmailTemplateMaster).filter(EmailTemplateMaster.id == template_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Email template not found")
    db.delete(row)
    db.commit()
    return {"status": "ok"}


@router.post("/users/deactivate-before", dependencies=[Depends(require_admin_type("techadmin"))])
def deactivate_users_before(
    before_date: str = Query(..., description="YYYY-MM-DD"),
    db: Session = Depends(get_db),
) -> dict:
    # Mirrors batch deactivate concept: set approve=0 for users created before date.
    dt = datetime.fromisoformat(before_date)
    updated = (
        db.query(User)
        .filter(User.created_at < dt)
        .update({User.approve: "0"})
    )
    db.commit()
    return {"status": "ok", "updated": int(updated or 0)}

