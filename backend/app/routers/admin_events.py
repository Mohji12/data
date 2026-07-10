from __future__ import annotations

import csv
import io
from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response, UploadFile, File
from openpyxl import Workbook
from pydantic import BaseModel, Field
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.admin_security import get_current_admin, require_admin_type
from app.db import get_db
from app.models import EventPaymentTxn, EventRegistration, Option
from app.services.event_payments import admin_approve_event_registration
from app.services.event_registration import (
    event_brochure_option_key,
    event_brochure_public_url,
    event_registration_slugs,
    icu_d_conclave_slug,
    resolve_event_brochure_filename,
)
from app.services.uploads import save_batch_brochure

router = APIRouter(
    prefix="/admin/events",
    tags=["admin-events"],
    dependencies=[Depends(get_current_admin)],
)

_EVENT_SLUG = icu_d_conclave_slug()


class PagedEventRegistrationsResponse(BaseModel):
    total: int
    items: list[dict[str, Any]]


class AdminApproveEventRegistrationRequest(BaseModel):
    force_manual: bool = False
    resend_email: bool = False
    payment_id: Optional[str] = Field(default=None, max_length=255)
    admin_note: Optional[str] = Field(default=None, max_length=500)


_EVENT_EXPORT_COLUMNS = [
    "id",
    "registration_number",
    "full_name",
    "designation",
    "category",
    "specialty",
    "email",
    "phone",
    "country_name",
    "hospital",
    "city",
    "state",
    "council_state",
    "council_registration_number",
    "payment_status",
    "amount_inr",
    "base_fee_inr",
    "gst_percent",
    "gst_amount_inr",
    "fee_label",
    "payment_id",
    "payment_type",
    "payment_date",
    "created_at",
]


def _export_row_values(r: EventRegistration) -> list[Any]:
    return [
        r.id,
        r.registration_number,
        r.full_name,
        r.designation,
        r.category,
        r.specialty,
        r.email,
        r.phone,
        r.country_name,
        r.hospital,
        r.city,
        r.state,
        r.council_state,
        r.council_registration_number,
        r.payment_status,
        r.amount_inr,
        r.base_fee_inr,
        r.gst_percent,
        r.gst_amount_inr,
        r.fee_label,
        r.payment_id,
        r.payment_type,
        r.payment_date.isoformat() if r.payment_date else "",
        r.created_at.isoformat() if r.created_at else "",
    ]


def _serialize_registration(row: EventRegistration) -> dict[str, Any]:
    return {
        "id": row.id,
        "event_slug": row.event_slug,
        "registration_number": row.registration_number,
        "full_name": row.full_name,
        "designation": row.designation,
        "category": row.category,
        "specialty": row.specialty,
        "email": row.email,
        "phone": row.phone,
        "country_id": row.country_id,
        "country_name": row.country_name,
        "hospital": row.hospital,
        "city": row.city,
        "state": row.state,
        "council_state": row.council_state,
        "council_registration_number": row.council_registration_number,
        "payment_status": row.payment_status,
        "amount_inr": float(row.amount_inr or 0),
        "base_fee_inr": float(row.base_fee_inr or 0),
        "gst_percent": float(row.gst_percent or 18),
        "gst_amount_inr": float(row.gst_amount_inr or 0),
        "fee_label": row.fee_label,
        "payment_id": row.payment_id,
        "payment_type": row.payment_type,
        "payment_date": row.payment_date.isoformat() if row.payment_date else None,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def _base_query(db: Session):
    return db.query(EventRegistration).filter(
        EventRegistration.event_slug.in_(event_registration_slugs())
    )


@router.get("/registrations", response_model=PagedEventRegistrationsResponse)
def list_event_registrations(
    q: Optional[str] = Query(None),
    payment_status: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=200),
    db: Session = Depends(get_db),
) -> PagedEventRegistrationsResponse:
    query = _base_query(db)
    if payment_status:
        query = query.filter(
            func.lower(func.trim(EventRegistration.payment_status))
            == payment_status.strip().lower()
        )
    if category:
        query = query.filter(
            func.lower(EventRegistration.category) == category.strip().lower()
        )
    if q:
        term = f"%{q.strip()}%"
        query = query.filter(
            or_(
                EventRegistration.full_name.like(term),
                EventRegistration.email.like(term),
                EventRegistration.registration_number.like(term),
                EventRegistration.phone.like(term),
            )
        )
    total = query.count()
    rows = (
        query.order_by(EventRegistration.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return PagedEventRegistrationsResponse(
        total=total,
        items=[_serialize_registration(r) for r in rows],
    )


def _filtered_export_rows(db: Session, payment_status: Optional[str]) -> list[EventRegistration]:
    query = _base_query(db)
    if payment_status:
        query = query.filter(
            func.lower(func.trim(EventRegistration.payment_status))
            == payment_status.strip().lower()
        )
    return query.order_by(EventRegistration.id.desc()).all()


# Static paths must be registered before /registrations/{registration_id} or FastAPI
# treats "export.xlsx" as registration_id and returns 422.
@router.get("/registrations/export.csv")
def export_event_registrations_csv(
    payment_status: Optional[str] = Query(None),
    db: Session = Depends(get_db),
) -> Response:
    rows = _filtered_export_rows(db, payment_status)

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(_EVENT_EXPORT_COLUMNS)
    for r in rows:
        writer.writerow(_export_row_values(r))
    filename = f"event-registrations-{_EVENT_SLUG}-{datetime.utcnow().strftime('%Y%m%d')}.csv"
    return Response(
        content=buf.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/registrations/export.xlsx")
def export_event_registrations_xlsx(
    payment_status: Optional[str] = Query(None),
    db: Session = Depends(get_db),
) -> Response:
    rows = _filtered_export_rows(db, payment_status)

    wb = Workbook()
    ws = wb.active
    ws.title = "Registrations"
    ws.append(_EVENT_EXPORT_COLUMNS)
    for r in rows:
        ws.append(_export_row_values(r))

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    filename = f"event-registrations-{_EVENT_SLUG}-{datetime.utcnow().strftime('%Y%m%d')}.xlsx"
    return Response(
        content=buf.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/registrations/{registration_id}")
def get_event_registration(
    registration_id: int,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    row = (
        _base_query(db)
        .filter(EventRegistration.id == registration_id)
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Registration not found")
    data = _serialize_registration(row)
    txn = (
        db.query(EventPaymentTxn)
        .filter(EventPaymentTxn.event_registration_id == row.id)
        .order_by(EventPaymentTxn.id.desc())
        .first()
    )
    if txn:
        data["payment_txn"] = {
            "request_id": txn.request_id,
            "gateway_order_id": txn.gateway_order_id,
            "gateway_payment_id": txn.gateway_payment_id,
            "gateway_status": txn.gateway_status,
            "is_finalized": txn.is_finalized,
            "amount": float(txn.amount or 0),
            "currency": txn.currency,
        }
    return data


@router.post("/registrations/{registration_id}/approve")
def approve_event_registration(
    registration_id: int,
    body: AdminApproveEventRegistrationRequest,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Verify Razorpay payment (or manually approve) and send confirmation email."""
    return admin_approve_event_registration(
        db,
        registration_id,
        force_manual=body.force_manual,
        resend_email=body.resend_email,
        payment_id=body.payment_id,
        admin_note=body.admin_note,
    )


def _upsert_option(db: Session, option_name: str, option_value: str) -> None:
    row = db.query(Option).filter(Option.option_name == option_name).first()
    if not row:
        row = Option(option_name=option_name, option_value=option_value)
    else:
        row.option_value = option_value
    db.add(row)


@router.get(f"/{_EVENT_SLUG}/brochure")
def get_event_brochure(db: Session = Depends(get_db)) -> dict[str, str | None]:
    filename = resolve_event_brochure_filename(db)
    return {
        "brochure_file": filename,
        "brochure_url": event_brochure_public_url(filename),
    }


@router.post(
    f"/{_EVENT_SLUG}/upload-brochure",
    dependencies=[Depends(require_admin_type("techadmin"))],
)
def upload_event_brochure(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    filename = save_batch_brochure(file)
    _upsert_option(db, event_brochure_option_key(), filename)
    db.commit()
    return {
        "file_name": filename,
        "brochure_url": event_brochure_public_url(filename) or "",
    }


@router.delete(
    f"/{_EVENT_SLUG}/brochure",
    dependencies=[Depends(require_admin_type("techadmin"))],
)
def remove_event_brochure(db: Session = Depends(get_db)) -> dict[str, str]:
    _upsert_option(db, event_brochure_option_key(), "")
    db.commit()
    return {"status": "ok"}
