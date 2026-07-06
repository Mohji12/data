from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.admin_security import get_current_admin
from app.db import get_db
from app.models import RegistrationPaymentTxn, User
from app.schemas import (
    ExtensionRequestActionPayload,
    ExtensionRequestActionResponse,
    ExtensionRequestItem,
    PagedExtensionRequestsResponse,
)
from app.services.access import find_active_user_subscription
from app.services.payments import (
    apply_offline_extension_credit,
    extension_txn_payload_fields,
    reject_extension_request,
    try_finalize_extension_txn,
)

router = APIRouter(
    prefix="/admin/extension-requests",
    tags=["admin-extension-requests"],
    dependencies=[Depends(get_current_admin)],
)

_PENDING_STATUSES = {"created", "order_created", "payment_failed", "pending_offline", "rejected"}


def _txn_to_item(txn: RegistrationPaymentTxn, user: User) -> ExtensionRequestItem:
    fields = extension_txn_payload_fields(txn)
    return ExtensionRequestItem(
        id=txn.id,
        request_id=txn.request_id,
        user_id=user.id,
        user_name=user.name,
        user_email=user.email,
        user_contact=user.contact_number,
        subscription=user.subscription,
        batch_slug=txn.batch_slug,
        amount=float(txn.amount or 0.0),
        currency=(txn.currency or "INR"),
        gateway_status=(txn.gateway_status or "created"),
        gateway_order_id=txn.gateway_order_id,
        offline_reference=fields.get("offline_reference"),
        student_note=fields.get("student_note"),
        failure_reason=fields.get("failure_reason"),
        admin_note=fields.get("admin_note"),
        created_at=txn.created_at.isoformat() if txn.created_at else None,
        updated_at=txn.updated_at.isoformat() if txn.updated_at else None,
    )


@router.get("", response_model=PagedExtensionRequestsResponse)
def list_extension_requests(
    status: Optional[str] = Query(None, description="pending_offline/payment_failed/order_created/created/rejected/all"),
    q: Optional[str] = Query(None, description="Search name/email"),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
) -> PagedExtensionRequestsResponse:
    query = (
        db.query(RegistrationPaymentTxn, User)
        .join(User, User.id == RegistrationPaymentTxn.user_id)
        .filter(
            RegistrationPaymentTxn.gateway == "extension",
            RegistrationPaymentTxn.is_finalized != "1",
        )
    )

    status_filter = (status or "").strip().lower()
    if status_filter and status_filter != "all":
        if status_filter == "abandoned":
            query = query.filter(RegistrationPaymentTxn.gateway_status.in_(["created", "order_created"]))
        elif status_filter in _PENDING_STATUSES:
            query = query.filter(RegistrationPaymentTxn.gateway_status == status_filter)
        else:
            query = query.filter(RegistrationPaymentTxn.gateway_status == status_filter)

    if q:
        s = f"%{q.strip().lower()}%"
        query = query.filter(
            (User.name.ilike(s)) | (User.email.ilike(s)) | (User.contact_number.ilike(s))
        )

    total = query.count()
    rows = (
        query.order_by(RegistrationPaymentTxn.id.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    items = [_txn_to_item(txn, user) for txn, user in rows]
    return PagedExtensionRequestsResponse(total=total, items=items)


def _get_extension_request_txn(db: Session, request_id: str) -> RegistrationPaymentTxn:
    rid = (request_id or "").strip()
    if not rid:
        raise HTTPException(status_code=422, detail="request_id is required")
    txn = (
        db.query(RegistrationPaymentTxn)
        .filter(
            RegistrationPaymentTxn.request_id == rid,
            RegistrationPaymentTxn.gateway == "extension",
        )
        .first()
    )
    if not txn:
        raise HTTPException(status_code=404, detail="Extension request not found")
    return txn


@router.post("/{request_id}/approve", response_model=ExtensionRequestActionResponse)
def approve_extension_request(
    request_id: str,
    payload: ExtensionRequestActionPayload,
    db: Session = Depends(get_db),
) -> ExtensionRequestActionResponse:
    txn = _get_extension_request_txn(db, request_id)
    result = apply_offline_extension_credit(
        db,
        txn,
        payment_details=payload.payment_details,
        admin_note=payload.admin_note,
    )
    return ExtensionRequestActionResponse(**result)


@router.post("/{request_id}/reject", response_model=ExtensionRequestActionResponse)
def reject_extension_request_endpoint(
    request_id: str,
    payload: ExtensionRequestActionPayload,
    db: Session = Depends(get_db),
) -> ExtensionRequestActionResponse:
    txn = _get_extension_request_txn(db, request_id)
    result = reject_extension_request(db, txn, admin_note=payload.admin_note)
    return ExtensionRequestActionResponse(**result)


@router.post("/{request_id}/sync-razorpay", response_model=ExtensionRequestActionResponse)
def sync_extension_razorpay(
    request_id: str,
    db: Session = Depends(get_db),
) -> ExtensionRequestActionResponse:
    txn = _get_extension_request_txn(db, request_id)
    synced = try_finalize_extension_txn(db, txn)
    if not synced:
        raise HTTPException(status_code=400, detail="Extension could not be synced from Razorpay")
    user = db.query(User).filter(User.id == txn.user_id).first()
    active = find_active_user_subscription(db, user) if user else None
    extended_end = active.end_at.isoformat() if active and active.end_at else None
    return ExtensionRequestActionResponse(
        status="ok",
        message="Extension synced from Razorpay and applied.",
        extended_end_at=extended_end,
    )
