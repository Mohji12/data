from __future__ import annotations

import json
import logging
import time
from datetime import datetime

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import EventPaymentTxn, EventRegistration
from app.schemas import PaymentOrderResponse
from app.services.event_registration import (
    event_registration_slugs,
    icu_d_conclave_slug,
    try_send_event_confirmation_email,
)
from app.services.payments import (
    _razorpay_api_get,
    _razorpay_create_order,
    _razorpay_payment_is_captured,
    _verify_signature,
)

logger = logging.getLogger(__name__)


def _event_txn_by_request_or_order(
    db: Session,
    *,
    request_id: str | None = None,
    order_id: str | None = None,
) -> EventPaymentTxn | None:
    rid = (request_id or "").strip()
    if rid:
        txn = db.query(EventPaymentTxn).filter(EventPaymentTxn.request_id == rid).first()
        if txn:
            return txn
    oid = (order_id or "").strip()
    if oid:
        return (
            db.query(EventPaymentTxn)
            .filter(EventPaymentTxn.gateway_order_id == oid)
            .order_by(EventPaymentTxn.id.desc())
            .first()
        )
    return None


def create_event_payment_order(db: Session, request_id: str) -> PaymentOrderResponse:
    txn = db.query(EventPaymentTxn).filter(EventPaymentTxn.request_id == request_id).first()
    if not txn:
        raise HTTPException(status_code=404, detail="Event registration request not found")

    reg = db.query(EventRegistration).filter(EventRegistration.id == txn.event_registration_id).first()
    if not reg:
        raise HTTPException(status_code=404, detail="Event registration not found")

    if txn.is_finalized == "1" or (reg.payment_status or "").strip().lower() == "credit":
        raise HTTPException(status_code=400, detail="Payment already completed for this registration.")

    settings = get_settings()
    key_id = (settings.payment_key_id or "").strip()
    key_secret = (settings.payment_key_secret or "").strip()
    if not key_id or not key_secret:
        raise HTTPException(
            status_code=503,
            detail=(
                "Razorpay is not configured. Set PAYMENT_KEY_ID and PAYMENT_KEY_SECRET in the backend .env."
            ),
        )

    amount = float(txn.amount or 0.0)
    currency = (txn.currency or "INR").upper()
    smallest = int(round(amount * 100))
    if smallest < 100:
        raise HTTPException(
            status_code=400,
            detail="Order amount is too small for Razorpay (minimum 100 paise).",
        )

    receipt_base = (request_id.replace("-", "") or "evt")[:24]
    receipt = f"evt_{receipt_base}_{int(time.time())}"[:40]

    order_json = _razorpay_create_order(
        key_id,
        key_secret,
        smallest,
        currency,
        receipt=receipt,
        notes={
            "event_request_id": (request_id or "")[:256],
            "event_registration_id": str(reg.id),
            "registration_number": (reg.registration_number or "")[:256],
        },
    )
    razorpay_order_id = order_json.get("id")
    if not razorpay_order_id:
        raise HTTPException(status_code=502, detail="Razorpay returned no order id")

    txn.gateway_order_id = razorpay_order_id
    txn.gateway_status = "order_created"
    db.add(txn)
    db.commit()

    return PaymentOrderResponse(
        request_id=request_id,
        gateway=settings.payment_gateway_name,
        order_id=razorpay_order_id,
        amount=amount,
        currency=currency,
        key_id=key_id,
        user_name=reg.full_name or "",
        user_email=reg.email,
        user_contact=reg.phone,
    )


def _apply_event_payment_success(
    db: Session,
    *,
    txn: EventPaymentTxn,
    reg: EventRegistration,
    order_id: str,
    payment_id: str,
    signature: str,
    raw_payload: dict | None,
    source: str,
) -> bool:
    txn.gateway_order_id = order_id
    txn.gateway_payment_id = payment_id
    txn.gateway_signature = signature
    txn.gateway_status = "paid"
    txn.is_finalized = "1"
    if source == "webhook":
        txn.webhook_payload = json.dumps(raw_payload or {})
    else:
        txn.callback_payload = json.dumps(raw_payload or {})

    now = datetime.utcnow()
    reg.payment_id = payment_id
    reg.payment_signature = signature
    reg.payment_type = "Online"
    reg.payment_date = now
    reg.payment_status = "Credit"
    reg.payment_details = json.dumps(raw_payload or {})
    reg.updated_at = now

    db.add(txn)
    db.add(reg)
    db.commit()
    db.refresh(reg)

    email_sent = try_send_event_confirmation_email(db, reg)
    logger.info(
        "event payment captured reg_id=%s request_id=%s order_id=%s payment_id=%s source=%s email_sent=%s",
        reg.id,
        txn.request_id,
        order_id,
        payment_id,
        source,
        email_sent,
    )
    return email_sent


def finalize_event_payment(
    db: Session,
    request_id: str,
    order_id: str,
    payment_id: str,
    signature: str,
    raw_payload: dict | None = None,
    source: str = "callback",
    *,
    verify_signature: bool = True,
) -> dict:
    txn = db.query(EventPaymentTxn).filter(EventPaymentTxn.request_id == request_id).first()
    if not txn:
        raise HTTPException(status_code=404, detail="Event transaction not found")

    reg = db.query(EventRegistration).filter(EventRegistration.id == txn.event_registration_id).first()
    if not reg:
        raise HTTPException(status_code=404, detail="Event registration not found")

    if txn.is_finalized == "1":
        email_sent = try_send_event_confirmation_email(db, reg)
        return {
            "request_id": request_id,
            "status": "ok",
            "payment_status": reg.payment_status or "Credit",
            "registration_id": reg.id,
            "registration_number": reg.registration_number,
            "email_sent": email_sent,
            "message": "Payment already finalized",
        }

    signature_ok = (not verify_signature) or _verify_signature(order_id, payment_id, signature)
    captured_on_gateway = _razorpay_payment_is_captured(order_id, payment_id)

    if verify_signature and not signature_ok:
        if captured_on_gateway:
            logger.warning(
                "event checkout signature mismatch but payment captured request_id=%s",
                request_id,
            )
        else:
            txn.gateway_status = "signature_failed"
            reg.payment_status = "Failed"
            txn.callback_payload = json.dumps(raw_payload or {})
            db.add(txn)
            db.add(reg)
            db.commit()
            raise HTTPException(
                status_code=400,
                detail="Invalid payment signature. Payment was not confirmed as captured on Razorpay.",
            )

    if not verify_signature and not captured_on_gateway:
        raise HTTPException(
            status_code=400,
            detail="Payment is not captured on Razorpay yet. Try again after payment completes.",
        )

    email_sent = _apply_event_payment_success(
        db,
        txn=txn,
        reg=reg,
        order_id=order_id,
        payment_id=payment_id,
        signature=signature,
        raw_payload=raw_payload,
        source=source,
    )

    return {
        "request_id": request_id,
        "status": "ok",
        "payment_status": "Credit",
        "registration_id": reg.id,
        "registration_number": reg.registration_number,
        "email_sent": email_sent,
        "message": "Payment finalized",
    }


def sync_event_payment_from_razorpay(db: Session, registration_id: int) -> dict:
    """Recover missed payment callbacks: verify captured payment on Razorpay, then finalize locally."""
    reg = (
        db.query(EventRegistration)
        .filter(
            EventRegistration.id == registration_id,
            EventRegistration.event_slug.in_(event_registration_slugs()),
        )
        .first()
    )
    if not reg:
        raise HTTPException(status_code=404, detail="Registration not found")

    if (reg.payment_status or "").strip().lower() == "credit":
        email_sent = try_send_event_confirmation_email(db, reg)
        return {
            "status": "ok",
            "payment_status": "Credit",
            "registration_id": reg.id,
            "registration_number": reg.registration_number,
            "email_sent": email_sent,
            "message": "Payment already marked Credit",
        }

    txn = (
        db.query(EventPaymentTxn)
        .filter(
            EventPaymentTxn.event_registration_id == reg.id,
            EventPaymentTxn.is_finalized != "1",
        )
        .order_by(EventPaymentTxn.id.desc())
        .first()
    )
    if not txn:
        txn = (
            db.query(EventPaymentTxn)
            .filter(EventPaymentTxn.event_registration_id == reg.id)
            .order_by(EventPaymentTxn.id.desc())
            .first()
        )
    if not txn:
        raise HTTPException(status_code=400, detail="No event payment transaction found for this registration.")

    order_id = (txn.gateway_order_id or "").strip()
    if not order_id:
        raise HTTPException(status_code=400, detail="No Razorpay order id on file. Complete checkout again.")

    payload = _razorpay_api_get(f"/v1/orders/{order_id}/payments")
    items = payload.get("items") or []
    paid = next(
        (
            p
            for p in items
            if (p.get("status") or "").lower() in {"captured", "authorized"}
        ),
        None,
    )
    if not paid:
        raise HTTPException(
            status_code=400,
            detail="Razorpay has no captured payment for this order yet. Confirm payment in Razorpay dashboard first.",
        )

    payment_id = str(paid.get("id") or "").strip()
    if not payment_id:
        raise HTTPException(status_code=502, detail="Razorpay returned a payment without an id.")

    return finalize_event_payment(
        db=db,
        request_id=txn.request_id,
        order_id=order_id,
        payment_id=payment_id,
        signature="",
        raw_payload={"source": "sync_from_razorpay"},
        source="sync",
        verify_signature=False,
    )


def confirm_event_registration_after_payment(db: Session, registration_id: int) -> dict:
    """
    Thank-you page hook: sync Razorpay payment if needed and send confirmation email once.
    Idempotent — safe to call after /payment/callback.
    """
    reg = (
        db.query(EventRegistration)
        .filter(
            EventRegistration.id == registration_id,
            EventRegistration.event_slug.in_(event_registration_slugs()),
        )
        .first()
    )
    if not reg:
        raise HTTPException(status_code=404, detail="Registration not found")

    payment_status = (reg.payment_status or "").strip()
    if payment_status.lower() != "credit":
        try:
            sync_event_payment_from_razorpay(db, registration_id)
            db.refresh(reg)
            payment_status = (reg.payment_status or "").strip()
        except HTTPException:
            pass

    if payment_status.lower() != "credit":
        return {
            "status": "pending",
            "payment_status": payment_status or "Pending",
            "registration_number": reg.registration_number,
            "email_sent": False,
            "message": "Payment not completed yet",
        }

    email_sent = try_send_event_confirmation_email(db, reg)
    return {
        "status": "ok",
        "payment_status": "Credit",
        "registration_number": reg.registration_number,
        "email_sent": email_sent,
        "message": "Confirmation email sent" if email_sent else "Confirmation email could not be sent (check SMTP logs)",
    }


def process_event_razorpay_webhook(
    db: Session,
    *,
    order_id: str,
    payment_id: str,
    request_id: str | None,
    payload: dict,
) -> dict | None:
    """Finalize event payment from webhook notes when course txn is not found."""
    rid = (request_id or "").strip()
    txn = _event_txn_by_request_or_order(db, request_id=rid or None, order_id=order_id)
    if not txn:
        return None
    reg = db.query(EventRegistration).filter(EventRegistration.id == txn.event_registration_id).first()
    if not reg or reg.event_slug not in event_registration_slugs():
        return None
    return finalize_event_payment(
        db=db,
        request_id=txn.request_id,
        order_id=order_id,
        payment_id=payment_id,
        signature="",
        raw_payload=payload,
        source="webhook",
        verify_signature=False,
    )
