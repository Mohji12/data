from __future__ import annotations

import csv
import io
from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.admin_security import get_current_admin
from app.db import get_db
from app.models import EventPaymentTxn, EventRegistration
from app.services.event_registration import icu_d_conclave_slug

router = APIRouter(
    prefix="/admin/events",
    tags=["admin-events"],
    dependencies=[Depends(get_current_admin)],
)

_EVENT_SLUG = icu_d_conclave_slug()


class PagedEventRegistrationsResponse(BaseModel):
    total: int
    items: list[dict[str, Any]]


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
        "payment_id": row.payment_id,
        "payment_type": row.payment_type,
        "payment_date": row.payment_date.isoformat() if row.payment_date else None,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def _base_query(db: Session):
    return db.query(EventRegistration).filter(EventRegistration.event_slug == _EVENT_SLUG)


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


@router.get("/registrations/export.csv")
def export_event_registrations_csv(
    payment_status: Optional[str] = Query(None),
    db: Session = Depends(get_db),
) -> Response:
    query = _base_query(db)
    if payment_status:
        query = query.filter(
            func.lower(func.trim(EventRegistration.payment_status))
            == payment_status.strip().lower()
        )
    rows = query.order_by(EventRegistration.id.desc()).all()

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(
        [
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
            "payment_id",
            "payment_date",
            "created_at",
        ]
    )
    for r in rows:
        writer.writerow(
            [
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
                r.payment_id,
                r.payment_date.isoformat() if r.payment_date else "",
                r.created_at.isoformat() if r.created_at else "",
            ]
        )
    filename = f"event-registrations-{_EVENT_SLUG}-{datetime.utcnow().strftime('%Y%m%d')}.csv"
    return Response(
        content=buf.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
