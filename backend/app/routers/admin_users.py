from __future__ import annotations
import csv
import io
import logging
import mimetypes
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Response
from fastapi.responses import FileResponse, RedirectResponse
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, inspect
from sqlalchemy.orm import Session, load_only

from app.admin_security import get_current_admin
from app.core.config import get_settings
from app.db import SessionLocal, get_db
from app.models import Country, CouponMaster, Package, User, UserPackagePayment
from app.services.registration import apply_batch_subscription_filter_to_users
from app.services.access import admin_subscription_summary, batch_admin_subscription_summaries
from app.services.mailer import send_html_email
from app.services.payments import apply_offline_registration_credit, sync_registration_payment_from_razorpay, try_send_registration_thank_you_email, _package_for_thank_you_email
from app.services.s3_storage import (
    presigned_get_url,
    registration_document_filename,
    resolve_admin_document_url,
    s3_uploads_enabled,
)
from app.services.email_templates import (
    EMAIL_TEMPLATE_TYPE_DOCUMENT_DENIED,
    EMAIL_TEMPLATE_TYPE_DOCUMENT_VERIFIED,
    PASSWORD_MAIL_SUBJECT,
    custom_template,
    document_status_template,
    password_template_for_user,
    paynow_template,
    plaintext_password_for_password_mail,
    resolve_batch_template_email,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/users", tags=["admin-users"], dependencies=[Depends(get_current_admin)])

_REGISTRATION_UPLOADS_DIR = Path(__file__).resolve().parent.parent.parent / "uploads" / "registration"


def _coupon_has_column(db: Session, column_name: str) -> bool:
    bind = db.get_bind()
    cols = inspect(bind).get_columns("coupon_master")
    return any((c.get("name") or "").lower() == column_name.lower() for c in cols)


def _coupon_query(db: Session):
    cols = [CouponMaster.id, CouponMaster.code, CouponMaster.status]
    if _coupon_has_column(db, "discount_amount"):
        cols.append(CouponMaster.discount_amount)
    if _coupon_has_column(db, "discount_percent"):
        cols.append(CouponMaster.discount_percent)
    if _coupon_has_column(db, "subscriptions"):
        cols.append(CouponMaster.subscriptions)
    if _coupon_has_column(db, "assigned_email"):
        cols.append(CouponMaster.assigned_email)
    return db.query(CouponMaster).options(load_only(*cols))


class PagedUsersResponse(BaseModel):
    total: int
    items: list[dict[str, Any]]


def _json_flag_str(v: object, default: str = "0") -> str:
    """MySQL TINYINT columns often arrive as int; JSON must use string flags for React selects (\"0\"/\"1\")."""
    if v is None:
        return default
    s = str(v).strip()
    return s if s else default


def _serialize_user_admin(u: User) -> dict:
    settings = get_settings()
    pw = (u.password or "").strip()
    pw_hash = (u.password_hash or "").strip()
    plain_pw: Optional[str] = None
    if settings.admin_expose_plaintext_password:
        plain_pw = (plaintext_password_for_password_mail(u) or "").strip() or None
    return {
        "id": u.id,
        "registration_type": u.registration_type,
        "subscription": u.subscription,
        "title": u.title,
        "name": u.name,
        "email": u.email,
        "contact_number": u.contact_number,
        "hospital": u.hospital,
        "qualification": u.qualification,
        "speciality": u.speciality,
        "country_id": u.country_id,
        "state": u.state,
        "city": u.city,
        "pin_code": u.pin_code,
        "document_file": u.document_file,
        "document_file_2": u.document_file_2,
        "document_file_status": _json_flag_str(u.document_file_status, "0"),
        "package_id": u.package_id,
        "currency_name": u.currency_name,
        "gross_amount": u.gross_amount,
        "gst_percentage": u.gst_percentage,
        "gst_amount": u.gst_amount,
        "total_amount": u.total_amount,
        "coupon_code": u.coupon_code,
        "payment_request_id": u.payment_request_id,
        "payment_id": u.payment_id,
        "payment_status": u.payment_status,
        "payment_type": u.payment_type,
        "payment_date": u.payment_date.isoformat() if u.payment_date else None,
        "payment_details": u.payment_details,
        "approve": _json_flag_str(u.approve, ""),
        "verify": _json_flag_str(u.verify, ""),
        "has_password": bool(pw),
        # Expose encrypted password fields for admin table visibility.
        "encrypted_password": pw or None,
        "password_encrypted": pw or None,
        "password_hash": pw_hash or None,
        # Local testing only (guarded by ADMIN_EXPOSE_PLAINTEXT_PASSWORD).
        "plaintext_password": plain_pw,
        "created_at": u.created_at.isoformat() if u.created_at else None,
        "updated_at": u.updated_at.isoformat() if u.updated_at else None,
    }


def _attach_document_urls(d: dict[str, Any], user: User, settings: Any) -> None:
    api_base = settings.api_public_base_url
    legacy = settings.legacy_upload_base_url
    d["document_file_url"] = resolve_admin_document_url(
        user.document_file, settings, legacy, api_base=api_base
    )
    d["document_file_2_url"] = resolve_admin_document_url(
        user.document_file_2, settings, legacy, api_base=api_base
    )
    d["document_admin_view_url"] = (
        f"{api_base.rstrip('/')}/admin/users/{user.id}/document?file=1"
        if (user.document_file or "").strip()
        else None
    )
    d["document_admin_view_url_2"] = (
        f"{api_base.rstrip('/')}/admin/users/{user.id}/document?file=2"
        if (user.document_file_2 or "").strip()
        else None
    )


def _country_name_for_user(db: Session, country_id: Optional[int]) -> Optional[str]:
    if not country_id:
        return None
    row = db.query(Country.name).filter(Country.id == country_id).first()
    return row[0] if row else None


@router.get("", response_model=PagedUsersResponse)
def list_users(
    q: Optional[str] = Query(None, description="Search name/email/contact"),
    subscription: Optional[list[str]] = Query(None),
    batch_filter: Optional[str] = Query(
        None,
        description="batch_master.name or package_subscription; expands to all subscription aliases",
    ),
    payment_status: Optional[str] = Query(None),
    approve: Optional[str] = Query(None),
    document_status: Optional[str] = Query(
        None, description="0=pending, 1=approved, 2=denied (document_file_status)"
    ),
    pending_documents_only: bool = Query(
        False, description="Users with uploaded doc awaiting review (status 0)"
    ),
    sort_by: Optional[str] = Query(None, description="Column to sort by (id, name, email, created_at, subscription)"),
    order: str = Query("desc", description="sort order (asc, desc)"),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=1000),
    db: Session = Depends(get_db),
) -> PagedUsersResponse:
    query = db.query(User)
    if q:
        s = f"%{q.strip().lower()}%"
        query = query.filter(
            func.lower(func.coalesce(User.name, "")).like(s)
            | func.lower(func.coalesce(User.email, "")).like(s)
            | func.lower(func.coalesce(User.contact_number, "")).like(s)
        )
    batch_filters = [f.strip() for f in ([batch_filter] if batch_filter else []) if f.strip()]
    if subscription:
        batch_filters.extend(s.strip() for s in subscription if s.strip())
    if batch_filters:
        query = apply_batch_subscription_filter_to_users(query, db, batch_filters)
    if payment_status:
        query = query.filter(func.lower(func.coalesce(User.payment_status, "")) == payment_status.strip().lower())
    if approve is not None and approve != "":
        query = query.filter(func.coalesce(User.approve, "") == approve)
    if document_status is not None and document_status.strip() != "":
        try:
            doc_st = int(document_status.strip())
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="document_status must be 0, 1, or 2") from exc
        if doc_st not in (0, 1, 2):
            raise HTTPException(status_code=422, detail="document_status must be 0, 1, or 2")
        query = query.filter(User.document_file_status == doc_st)
    if pending_documents_only:
        query = query.filter(
            func.coalesce(User.document_file, "") != "",
            User.document_file_status == 0,
        )

    total = query.count()

    # Dynamic sorting
    if sort_by:
        col = getattr(User, sort_by, None)
        if col:
            if order.lower() == "asc":
                query = query.order_by(col.asc())
            else:
                query = query.order_by(col.desc())
        else:
            query = query.order_by(User.id.desc())
    else:
        query = query.order_by(User.id.desc())
    rows = (
        query.outerjoin(Country, User.country_id == Country.id)
        .add_columns(Country.name)
        .offset(offset)
        .limit(limit)
        .all()
    )
    settings = get_settings()
    user_rows = [row[0] for row in rows]
    subscription_summaries = batch_admin_subscription_summaries(db, user_rows)
    from app.services.mock_test_attempts import describe_attempt_limits_for_user

    items = []
    for row in rows:
        u = row[0]
        country_name = row[1]
        d = _serialize_user_admin(u)
        d["country_name"] = country_name
        d["subscription_access"] = subscription_summaries.get(u.id) or admin_subscription_summary(u)
        d["mock_test_attempts"] = describe_attempt_limits_for_user(db, u)
        _attach_document_urls(d, u, settings)
        items.append(d)
    return PagedUsersResponse(total=total, items=items)


class ApproveUpdate(BaseModel):
    approve: str

    @field_validator("approve", mode="before")
    @classmethod
    def _coerce_approve(cls, v: object) -> str:
        return str(v).strip()


@router.post("/{user_id}/approve")
def update_approve(user_id: int, payload: ApproveUpdate, db: Session = Depends(get_db)) -> dict:
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    ap = str(payload.approve).strip()
    if ap not in ("0", "1"):
        raise HTTPException(status_code=422, detail="approve must be 0 or 1")
    user.approve = ap
    if ap == "1":
        user.verify = "Yes"
    db.add(user)
    db.commit()
    return {"status": "ok"}


class OfflineCreditPayload(BaseModel):
    payment_details: Optional[str] = None


@router.post("/{user_id}/offline-credit")
def offline_credit(user_id: int, payload: OfflineCreditPayload, db: Session = Depends(get_db)) -> dict:
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    apply_offline_registration_credit(db, user, payment_details=payload.payment_details)
    return {"status": "ok", "payment_status": user.payment_status or "Credit"}


@router.post("/{user_id}/sync-razorpay-payment")
def sync_razorpay_payment(user_id: int, db: Session = Depends(get_db)) -> dict:
    """Finalize registration when Razorpay captured payment but /payment/callback never ran."""
    result = sync_registration_payment_from_razorpay(db, user_id)
    return {
        "status": result.status,
        "payment_status": result.payment_status,
        "message": result.message,
        "user_id": result.user_id,
    }


@router.post("/{user_id}/resend-thank-you-email")
def resend_thank_you_email(user_id: int, db: Session = Depends(get_db)) -> dict:
    """Resend registration thank-you email (e.g. after fixing SMTP_FROM)."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if (user.payment_status or "").strip().lower() != "credit":
        raise HTTPException(status_code=400, detail="User payment is not Credit")
    pkg = _package_for_thank_you_email(db, user)
    sent = try_send_registration_thank_you_email(db, user, pkg, force=True)
    if not sent:
        raise HTTPException(
            status_code=502,
            detail="Email could not be sent. Check API logs and SMTP_FROM (must be verified in ZeptoMail Mail Agents).",
        )
    return {"status": "ok", "email_sent": True, "email": user.email}


@router.post("/{user_id}/refund")
def refund(user_id: int, db: Session = Depends(get_db)) -> dict:
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.payment_status = "Refund"
    user.approve = "0"
    db.add(user)

    upp = (
        db.query(UserPackagePayment)
        .filter(UserPackagePayment.user_id == user.id)
        .order_by(UserPackagePayment.id.desc())
        .first()
    )
    if upp:
        upp.payment_status = "Refund"
        db.add(upp)

    db.commit()
    return {"status": "ok"}


def _smtp_configured() -> bool:
    settings = get_settings()
    return bool((settings.smtp_host or "").strip())


def _send_document_status_email(to_email: str, subject: str, html: str) -> bool:
    settings = get_settings()
    if not _smtp_configured():
        logger.warning("document status email skipped: SMTP_HOST is empty")
        return False
    if not (to_email or "").strip():
        logger.warning("document status email skipped: user has no email")
        return False
    try:
        send_html_email(
            to_email=to_email.strip(),
            subject=subject,
            html=html,
            cc=settings.smtp_cc or None,
            bcc=settings.smtp_bcc or None,
        )
        return True
    except Exception as exc:
        logger.warning("document status email failed to=%s: %s", to_email, exc)
        return False


def _background_document_status_emails(
    user_id: int,
    status: str,
    subject: str,
    html: str,
) -> None:
    """Fresh DB session — request-scoped Session must not be used after the response."""
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return
        if status in ("1", "2"):
            _send_document_status_email((user.email or "").strip(), subject, html)
        if status == "1" and (user.payment_status or "").strip().lower() == "credit":
            pkg = _package_for_thank_you_email(db, user)
            try_send_registration_thank_you_email(db, user, pkg)
    finally:
        db.close()


class DocumentStatusPayload(BaseModel):
    document_file_status: str

    @field_validator("document_file_status", mode="before")
    @classmethod
    def _coerce_doc_status(cls, v: object) -> str:
        return str(v).strip()


@router.post("/{user_id}/document-status")
def update_document_status(
    user_id: int,
    payload: DocumentStatusPayload,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> dict:
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    status = payload.document_file_status
    if status not in ("0", "1", "2"):
        raise HTTPException(status_code=422, detail="document_file_status must be 0, 1, or 2")
    user.document_file_status = int(status)
    if status == "1":
        user.approve = "1"
    db.add(user)
    db.commit()

    smtp_ok = _smtp_configured()
    email_queued = False
    if status in ("1", "2"):
        default_subject = "Document status update"
        default_html = document_status_template(user.name or "Learner", user.subscription or "", status)
        template_type = (
            EMAIL_TEMPLATE_TYPE_DOCUMENT_VERIFIED
            if status == "1"
            else EMAIL_TEMPLATE_TYPE_DOCUMENT_DENIED
        )
        try:
            subject, html = resolve_batch_template_email(
                db,
                user,
                template_type,
                default_subject=default_subject,
                default_html=default_html,
                status_label="Approved" if status == "1" else "Denied",
            )
            if smtp_ok and (user.email or "").strip():
                background_tasks.add_task(
                    _background_document_status_emails,
                    user.id,
                    status,
                    subject,
                    html,
                )
                email_queued = True
        except Exception as exc:
            logger.warning(
                "document status email skipped for user_id=%s (status saved): %s",
                user.id,
                exc,
            )

    return {
        "status": "ok",
        "document_file_status": status,
        "smtp_configured": smtp_ok,
        "email_queued": email_queued,
        "message": (
            "Document approved; notification email queued."
            if email_queued and status == "1"
            else "Document denied; notification email queued."
            if email_queued and status == "2"
            else "Status saved. Configure SMTP_HOST on the API server to send notification emails."
            if status in ("1", "2") and not smtp_ok
            else "Status saved."
            if status in ("1", "2")
            else "Status saved (no email for pending)."
        ),
    }


class PayNowMailPayload(BaseModel):
    subscription: Optional[str] = None
    limit: int = 100


@router.post("/mail/paynow")
def send_paynow_mail(payload: PayNowMailPayload, db: Session = Depends(get_db)) -> dict:
    query = db.query(User).filter(func.lower(func.coalesce(User.payment_status, "")) != "credit")
    if payload.subscription:
        query = query.filter(func.lower(func.coalesce(User.subscription, "")) == payload.subscription.strip().lower())
    rows = query.order_by(User.id.desc()).limit(payload.limit).all()
    sent = 0
    for u in rows:
        send_html_email(u.email, "Complete your payment", paynow_template(u.name or "Learner", u.subscription or ""))
        sent += 1
    return {"status": "ok", "sent": sent}


class PasswordMailPayload(BaseModel):
    user_id: int
    plain_password: Optional[str] = None


@router.post("/mail/password")
def send_password_mail(payload: PasswordMailPayload, db: Session = Depends(get_db)) -> dict:
    u = db.query(User).filter(User.id == payload.user_id).first()
    if not u:
        raise HTTPException(status_code=404, detail="User not found")
    if (u.email or "").strip() == "":
        raise HTTPException(status_code=400, detail="User has no email address.")
    pay = (u.payment_status or "").strip().lower()
    if pay != "credit":
        raise HTTPException(status_code=400, detail="User payment must be Credit to send login mail.")
    if (u.approve or "").strip() != "1":
        raise HTTPException(status_code=400, detail="User must be approved to send login mail.")

    if not (u.password or "").strip():
        raise HTTPException(
            status_code=422,
            detail="User has no password stored. Complete registration or set password before sending login mail.",
        )

    settings = get_settings()
    if not (settings.smtp_host or "").strip():
        raise HTTPException(status_code=503, detail="SMTP is not configured")

    try:
        send_html_email(
            (u.email or "").strip(),
            PASSWORD_MAIL_SUBJECT,
            password_template_for_user(u),
            cc=settings.smtp_cc or None,
            bcc=settings.smtp_bcc or None,
        )
    except Exception as exc:
        logger.warning("password mail failed for user_id=%s: %s", payload.user_id, exc)
        raise HTTPException(status_code=503, detail="Email could not be sent. Check SMTP settings.") from exc

    return {"status": "ok"}


class CustomMailPayload(BaseModel):
    subject: str
    body_html: str
    subscription: Optional[str] = None
    limit: int = 100


@router.post("/mail/custom")
def send_custom_mail(payload: CustomMailPayload, db: Session = Depends(get_db)) -> dict:
    query = db.query(User).filter(func.lower(func.coalesce(User.payment_status, "")) == "credit")
    if payload.subscription:
        query = query.filter(func.lower(func.coalesce(User.subscription, "")) == payload.subscription.strip().lower())
    rows = query.order_by(User.id.desc()).limit(payload.limit).all()
    sent = 0
    html = custom_template(payload.subject, payload.body_html)
    for u in rows:
        send_html_email(u.email, payload.subject, html)
        sent += 1
    return {"status": "ok", "sent": sent}


@router.get("/export.csv")
def export_users_csv(
    subscription: Optional[str] = Query(None),
    batch_filter: Optional[str] = Query(None),
    payment_status: Optional[str] = Query(None),
    approve: Optional[str] = Query(None),
    db: Session = Depends(get_db),
) -> Response:
    query = db.query(User)
    batch_filters = [f.strip() for f in ([batch_filter] if batch_filter else []) if f.strip()]
    if subscription:
        batch_filters.append(subscription.strip())
    if batch_filters:
        query = apply_batch_subscription_filter_to_users(query, db, batch_filters)
    if payment_status:
        query = query.filter(func.lower(func.coalesce(User.payment_status, "")) == payment_status.strip().lower())
    if approve is not None and approve != "":
        query = query.filter(func.coalesce(User.approve, "") == approve)
    rows = query.order_by(User.id.desc()).all()
    packages: dict[int, Package] = {}
    pkg_ids = {u.package_id for u in rows if u.package_id}
    if pkg_ids:
        packages = {p.id: p for p in db.query(Package).filter(Package.id.in_(pkg_ids)).all()}
    subs_map = batch_admin_subscription_summaries(db, rows)

    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(
        [
            "id",
            "name",
            "email",
            "contact_number",
            "subscription",
            "plan_type",
            "package_name",
            "course_start_at",
            "course_end_at",
            "access_status",
            "payment_status",
            "payment_type",
            "payment_date",
            "approve",
            "package_id",
            "currency_name",
            "total_amount",
            "created_at",
        ]
    )
    for u in rows:
        acc = subs_map.get(u.id) or admin_subscription_summary(u, pkg=packages.get(u.package_id) if u.package_id else None)
        w.writerow(
            [
                u.id,
                u.name or "",
                u.email or "",
                u.contact_number or "",
                u.subscription or "",
                acc.get("plan_type_label") or "",
                acc.get("package_name") or "",
                acc.get("course_start_at") or "",
                acc.get("course_end_at") or "",
                acc.get("access_status") or "",
                u.payment_status or "",
                u.payment_type or "",
                u.payment_date.isoformat() if u.payment_date else "",
                u.approve or "",
                u.package_id or "",
                u.currency_name or "",
                u.total_amount or "",
                u.created_at.isoformat() if u.created_at else "",
            ]
        )

    return Response(
        content=buf.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=users.csv"},
    )


@router.get("/{user_id}/document", response_model=None)
def admin_download_document(
    user_id: int,
    file: int = Query(1, ge=1, le=2, description="1=primary registration doc, 2=secondary"),
    db: Session = Depends(get_db),
):
    """Serve registration document for admin review (local disk or S3 presigned redirect)."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    stored = (user.document_file if file == 1 else user.document_file_2) or ""
    v = stored.strip()
    if not v:
        raise HTTPException(status_code=404, detail="No document on file for this user")

    settings = get_settings()
    plain = registration_document_filename(v)
    if plain:
        v = plain

    low = v.lower()
    if low.startswith("http://") or low.startswith("https://"):
        return RedirectResponse(url=v)

    if s3_uploads_enabled(settings) and "/" in v:
        url = presigned_get_url(v, settings)
        if url:
            return RedirectResponse(url=url)
        raise HTTPException(status_code=404, detail="Could not resolve S3 document URL")

    path = _REGISTRATION_UPLOADS_DIR / v
    if not path.is_file():
        raise HTTPException(
            status_code=404,
            detail="Document file not found on server. Check uploads/registration or S3 configuration.",
        )

    media_type = mimetypes.guess_type(v)[0] or "application/octet-stream"
    return FileResponse(path, media_type=media_type, filename=Path(v).name)


@router.get("/{user_id}")
def get_user(user_id: int, db: Session = Depends(get_db)) -> dict:
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    settings = get_settings()
    udict = _serialize_user_admin(user)
    udict["country_name"] = _country_name_for_user(db, user.country_id)
    pkg = db.query(Package).filter(Package.id == user.package_id).first() if user.package_id else None
    udict["subscription_access"] = admin_subscription_summary(user, pkg=pkg)
    _attach_document_urls(udict, user, settings)
    pay_rows = (
        db.query(UserPackagePayment)
        .filter(UserPackagePayment.user_id == user_id)
        .order_by(UserPackagePayment.id.desc())
        .limit(20)
        .all()
    )
    payments = [
        {
            "id": p.id,
            "package_id": p.package_id,
            "subscription": p.subscription,
            "package_type": p.package_type,
            "payment_status": p.payment_status,
            "payment_type": p.payment_type,
            "payment_date": p.payment_date.isoformat() if p.payment_date else None,
            "currency_name": p.currency_name,
        }
        for p in pay_rows
    ]
    return {"user": udict, "recent_payments": payments}


class UserMockTestAttemptsResponse(BaseModel):
    user_id: int
    subscription: str | None = None
    default_max_attempts: int
    batch_override: int | None = None
    user_override: int | None = None
    effective_max_attempts: int


class UserMockTestAttemptsUpdate(BaseModel):
    max_attempts: int | None = Field(
        default=None,
        description="Per-user override; null clears override",
        ge=1,
        le=50,
    )


@router.get("/{user_id}/mock-test-attempts", response_model=UserMockTestAttemptsResponse)
def get_user_mock_test_attempts(user_id: int, db: Session = Depends(get_db)) -> UserMockTestAttemptsResponse:
    from app.services.mock_test_attempts import describe_attempt_limits_for_user

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    info = describe_attempt_limits_for_user(db, user)
    return UserMockTestAttemptsResponse(**info)


@router.put("/{user_id}/mock-test-attempts", response_model=UserMockTestAttemptsResponse)
def update_user_mock_test_attempts(
    user_id: int,
    payload: UserMockTestAttemptsUpdate,
    db: Session = Depends(get_db),
) -> UserMockTestAttemptsResponse:
    from app.services.mock_test_attempts import describe_attempt_limits_for_user, set_user_max_attempts

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    result = set_user_max_attempts(db, user_id, payload.max_attempts)
    info = result.get("user") or describe_attempt_limits_for_user(db, user)
    return UserMockTestAttemptsResponse(**info)

