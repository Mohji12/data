from __future__ import annotations
import csv
import io
from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.admin_security import get_current_admin
from app.db import get_db
from app.models import User, UserPackagePayment

# React tabs send slugs; legacy PHP stores human-readable package_type values.
_PACKAGE_TYPE_SLUG_TO_DB_VALUES: dict[str, list[str]] = {
    "topup": ["Topup"],
    "topup_extension": ["Topup Extension"],
    "topup_extension_2": ["Topup Extension 2"],
    "registration": ["registration", "Registration"],
}


def _apply_package_type_filter(query, package_type: str):
    slug = package_type.strip().lower().replace("-", "_")
    literals = _PACKAGE_TYPE_SLUG_TO_DB_VALUES.get(slug)
    if literals:
        return query.filter(UserPackagePayment.package_type.in_(literals))
    return query.filter(
        func.lower(func.coalesce(UserPackagePayment.package_type, "")) == package_type.strip().lower()
    )


router = APIRouter(
    prefix="/admin/payments",
    tags=["admin-payments"],
    dependencies=[Depends(get_current_admin)],
)


class PagedPaymentsResponse(BaseModel):
    total: int
    items: list[dict[str, Any]]


def _base_query(db: Session):
    return (
        db.query(UserPackagePayment, User)
        .join(User, User.id == UserPackagePayment.user_id)
    )


@router.get("", response_model=PagedPaymentsResponse)
def list_payments(
    package_type: Optional[str] = Query(None, description="topup/topup_extension/topup_extension_2/registration"),
    q: Optional[str] = Query(None, description="Search name/email/contact"),
    payment_status: Optional[str] = Query(None),
    sort_by: Optional[str] = Query(None, description="Column to sort by (id, payment_date, payment_status, subscription)"),
    order: str = Query("desc", description="sort order (asc, desc)"),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=1000),
    db: Session = Depends(get_db),
) -> PagedPaymentsResponse:
    query = _base_query(db)
    if package_type:
        query = _apply_package_type_filter(query, package_type)
    if payment_status:
        query = query.filter(func.lower(func.coalesce(UserPackagePayment.payment_status, "")) == payment_status.strip().lower())
    if q:
        s = f"%{q.strip().lower()}%"
        query = query.filter(
            func.lower(func.coalesce(User.name, "")).like(s)
            | func.lower(func.coalesce(User.email, "")).like(s)
            | func.lower(func.coalesce(User.contact_number, "")).like(s)
        )
    total = query.count()

    # Dynamic sorting
    if sort_by:
        col = getattr(UserPackagePayment, sort_by, None)
        if col:
            if order.lower() == "asc":
                query = query.order_by(col.asc())
            else:
                query = query.order_by(col.desc())
        else:
            query = query.order_by(UserPackagePayment.id.desc())
    else:
        query = query.order_by(UserPackagePayment.id.desc())

    rows = query.offset(offset).limit(limit).all()
    items = []
    for p, u in rows:
        items.append(
            {
                "id": p.id,
                "user_id": p.user_id,
                "user_name": u.name,
                "user_email": u.email,
                "subscription": p.subscription,
                "package_id": p.package_id,
                "package_type": p.package_type,
                "currency_name": p.currency_name,
                "payment_request_id": p.payment_request_id,
                "payment_id": p.payment_id,
                "payment_status": p.payment_status,
                "payment_type": p.payment_type,
                "payment_date": p.payment_date.isoformat() if p.payment_date else None,
            }
        )
    return PagedPaymentsResponse(total=total, items=items)


class OfflineMarkPaid(BaseModel):
    payment_details: Optional[str] = None


@router.post("/{payment_row_id}/offline-credit")
def offline_credit(payment_row_id: int, payload: OfflineMarkPaid, db: Session = Depends(get_db)) -> dict:
    row = db.query(UserPackagePayment).filter(UserPackagePayment.id == payment_row_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Payment row not found")
    row.payment_status = "Credit"
    row.payment_type = "Offline"
    row.payment_date = datetime.utcnow()
    if payload.payment_details:
        row.payment_details = payload.payment_details
    db.add(row)
    db.commit()
    return {"status": "ok"}


@router.post("/{payment_row_id}/refund")
def refund(payment_row_id: int, db: Session = Depends(get_db)) -> dict:
    row = db.query(UserPackagePayment).filter(UserPackagePayment.id == payment_row_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Payment row not found")
    row.payment_status = "Refund"
    db.add(row)
    db.commit()
    return {"status": "ok"}


@router.get("/export.csv")
def export_payments_csv(
    package_type: Optional[str] = Query(None),
    db: Session = Depends(get_db),
) -> Response:
    query = _base_query(db)
    if package_type:
        query = _apply_package_type_filter(query, package_type)
    rows = query.order_by(UserPackagePayment.id.desc()).all()

    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(
        [
            "id",
            "user_id",
            "user_name",
            "user_email",
            "subscription",
            "package_id",
            "package_type",
            "currency_name",
            "payment_request_id",
            "payment_id",
            "payment_status",
            "payment_type",
            "payment_date",
        ]
    )
    for p, u in rows:
        w.writerow(
            [
                p.id,
                p.user_id,
                u.name or "",
                u.email or "",
                p.subscription or "",
                p.package_id or "",
                p.package_type or "",
                p.currency_name or "",
                p.payment_request_id or "",
                p.payment_id or "",
                p.payment_status or "",
                p.payment_type or "",
                p.payment_date.isoformat() if p.payment_date else "",
            ]
        )

    return Response(
        content=buf.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=payments.csv"},
    )

