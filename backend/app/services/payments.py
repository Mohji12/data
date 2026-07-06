from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import time
import urllib.error
import urllib.request
from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import inspect
from sqlalchemy.orm import Session, load_only

from app.core.config import get_settings
from app.models import CouponMaster, Option, Package, RegistrationPaymentTxn, User, UserPackagePayment, UserSubscription
from app.services.email_templates import (
    EMAIL_TEMPLATE_TYPE_REGISTRATION_THANK_YOU,
    REGISTRATION_THANK_YOU_SUBJECT,
    render_registration_thank_you_html,
    resolve_batch_template_email,
)
from app.services.mailer import send_html_email
from app.services.access import (
    _user_has_extension_payment,
    batch_slug,
    find_active_user_subscription,
    get_extension_batch_settings,
    get_extension_offer,
    parse_iso_date,
)
from app.services.registration import activate_user_subscription, extend_active_subscription
from app.schemas import PaymentFinalizeResponse, PaymentOrderResponse

logger = logging.getLogger(__name__)

THANK_YOU_SENT_OPTION_PREFIX = "thank_you_sent::"


def _thank_you_sent_option_key(user_id: int) -> str:
    return f"{THANK_YOU_SENT_OPTION_PREFIX}{user_id}"


def registration_thank_you_was_sent(db: Session, user_id: int) -> bool:
    row = db.query(Option).filter(Option.option_name == _thank_you_sent_option_key(user_id)).first()
    return bool(row and (row.option_value or "").strip())


def _mark_registration_thank_you_sent(db: Session, user_id: int) -> None:
    key = _thank_you_sent_option_key(user_id)
    row = db.query(Option).filter(Option.option_name == key).first()
    if not row:
        row = Option(option_name=key, option_value="1")
    else:
        row.option_value = "1"
    db.add(row)
    db.commit()


def _package_for_thank_you_email(db: Session, user: User, txn: RegistrationPaymentTxn | None = None) -> Package | None:
    pkg_id = (txn.package_id if txn else None) or user.package_id
    if not pkg_id:
        return None
    return db.query(Package).filter(Package.id == pkg_id).first()


def try_send_registration_thank_you_email(
    db: Session,
    user: User,
    pkg: Package | None = None,
    *,
    force: bool = False,
) -> bool:
    """Send thank-you email once per user unless force=True (admin resend)."""
    if not force and registration_thank_you_was_sent(db, user.id):
        logger.info("thank-you email already recorded for user_id=%s", user.id)
        return True
    if _send_registration_thank_you_email(db, user, pkg):
        _mark_registration_thank_you_sent(db, user.id)
        return True
    return False


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


def init_extension_payment(db: Session, user: User) -> dict:
    try_finalize_pending_extension_payment(db, user)
    offer = get_extension_offer(db, user)
    if not offer.get("enabled"):
        raise HTTPException(status_code=400, detail=offer.get("reason") or "Extension is not available")

    active_sub = find_active_user_subscription(db, user)
    batch_slug_val = (active_sub.batch_slug or "").strip() if active_sub else ""
    package_id = (active_sub.package_id if active_sub else None) or user.package_id
    if not batch_slug_val:
        batch_slug_val = batch_slug(user.subscription)

    # Payment is ALWAYS in INR for Razorpay
    payment_amount_inr = float(offer.get("payment_amount_inr") or offer.get("estimated_amount") or 0.0)
    display_amount = float(offer.get("estimated_amount") or 0.0)
    display_currency = str(offer.get("currency_name") or "INR").upper()

    if payment_amount_inr <= 0:
        raise HTTPException(status_code=400, detail="Calculated extension amount is invalid")

    request_id = f"ext_{user.id}_{int(time.time())}"
    txn = RegistrationPaymentTxn(
        request_id=request_id,
        user_id=user.id,
        batch_slug=batch_slug_val,
        package_id=package_id,
        amount=payment_amount_inr,
        currency="INR",
        gateway="extension",
        gateway_status="created",
        is_finalized="0",
    )
    db.add(txn)
    db.commit()
    return {
        "request_id": request_id,
        "amount": payment_amount_inr,
        "currency": "INR",
        "display_amount": display_amount,
        "display_currency": display_currency,
        "extension_months": int(offer.get("extension_months") or 2),
    }


def _razorpay_auth_header() -> tuple[str, str]:
    settings = get_settings()
    key_id = (settings.payment_key_id or "").strip()
    key_secret = (settings.payment_key_secret or "").strip()
    if not key_id or not key_secret:
        raise HTTPException(
            status_code=503,
            detail="Razorpay is not configured (PAYMENT_KEY_ID / PAYMENT_KEY_SECRET).",
        )
    token = base64.b64encode(f"{key_id}:{key_secret}".encode()).decode()
    return key_id, f"Basic {token}"


def _razorpay_api_get(path: str) -> dict:
    _, auth = _razorpay_auth_header()
    req = urllib.request.Request(
        f"https://api.razorpay.com{path}",
        headers={"Authorization": auth},
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        raw = e.read().decode() if e.fp else ""
        try:
            err = json.loads(raw)
            desc = err.get("error", {}).get("description") or err.get("message") or raw
        except json.JSONDecodeError:
            desc = raw or str(e.reason)
        raise HTTPException(status_code=502, detail=f"Razorpay API failed: {desc}") from e


def _razorpay_create_order(
    key_id: str,
    key_secret: str,
    amount_smallest_unit: int,
    currency: str,
    receipt: str,
    notes: dict[str, str] | None = None,
) -> dict:
    """POST /v1/orders — Checkout requires a real Razorpay order id, not a local placeholder."""
    payload: dict = {
        "amount": amount_smallest_unit,
        "currency": currency.upper(),
        "receipt": receipt[:40],
        "payment_capture": 1,
    }
    if notes:
        payload["notes"] = {k: str(v)[:256] for k, v in notes.items()}
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        "https://api.razorpay.com/v1/orders",
        data=body,
        headers={
            "Authorization": f"Basic {base64.b64encode(f'{key_id}:{key_secret}'.encode()).decode()}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        raw = e.read().decode() if e.fp else ""
        try:
            err = json.loads(raw)
            desc = err.get("error", {}).get("description") or err.get("message") or raw
        except json.JSONDecodeError:
            desc = raw or str(e.reason)
        raise HTTPException(status_code=502, detail=f"Razorpay order failed: {desc}") from e


def create_payment_order(db: Session, request_id: str) -> PaymentOrderResponse:
    txn = db.query(RegistrationPaymentTxn).filter(RegistrationPaymentTxn.request_id == request_id).first()
    if not txn:
        raise HTTPException(status_code=404, detail="Registration request not found")
    user = db.query(User).filter(User.id == txn.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    is_extension = (txn.gateway or "").strip().lower() == "extension"
    if txn.is_finalized == "1" or ((user.payment_status or "").strip().lower() == "credit" and not is_extension):
        raise HTTPException(status_code=400, detail="Payment already completed for this registration.")

    settings = get_settings()
    key_id = (settings.payment_key_id or "").strip()
    key_secret = (settings.payment_key_secret or "").strip()
    if not key_id or not key_secret:
        raise HTTPException(
            status_code=503,
            detail=(
                "Razorpay is not configured. Set PAYMENT_KEY_ID and PAYMENT_KEY_SECRET in the backend .env "
                "(Dashboard → Settings → API Keys — use Test keys for sandbox)."
            ),
        )

    amount = float(txn.amount or 0.0)
    currency = (txn.currency or "INR").upper()
    smallest = int(round(amount * 100))
    if smallest < 100:
        raise HTTPException(
            status_code=400,
            detail="Order amount is too small for Razorpay (minimum 100 paise / smallest currency unit).",
        )

    receipt_base = (request_id.replace("-", "") or "reg")[:28]
    receipt = f"{receipt_base}_{int(time.time())}"[:40]

    order_json = _razorpay_create_order(
        key_id,
        key_secret,
        smallest,
        currency,
        receipt=receipt,
        notes={
            "user_id": str(user.id),
            "subscription": (user.subscription or "")[:200],
            "request_id": (request_id or "")[:256],
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
        user_name=user.name or "",
        user_email=user.email,
        user_contact=user.contact_number,
    )


def _verify_signature(order_id: str, payment_id: str, signature: str) -> bool:
    settings = get_settings()
    secret = (settings.payment_key_secret or "").strip()
    if not secret:
        return True
    if not (signature or "").strip():
        return False
    body = f"{order_id}|{payment_id}".encode("utf-8")
    digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(digest, signature.strip())


def _razorpay_payment_is_captured(order_id: str, payment_id: str) -> bool:
    """Confirm with Razorpay API that this payment exists and is captured for the order."""
    order_id = (order_id or "").strip()
    payment_id = (payment_id or "").strip()
    if not order_id or not payment_id:
        return False
    try:
        data = _razorpay_api_get(f"/v1/payments/{payment_id}")
    except HTTPException:
        return False
    status = (data.get("status") or "").lower()
    return status in {"captured", "authorized"} and (data.get("order_id") or "").strip() == order_id


def _txn_by_request_or_order(
    db: Session,
    *,
    request_id: str | None = None,
    order_id: str | None = None,
) -> RegistrationPaymentTxn | None:
    rid = (request_id or "").strip()
    if rid:
        txn = db.query(RegistrationPaymentTxn).filter(RegistrationPaymentTxn.request_id == rid).first()
        if txn:
            return txn
    oid = (order_id or "").strip()
    if oid:
        return (
            db.query(RegistrationPaymentTxn)
            .filter(RegistrationPaymentTxn.gateway_order_id == oid)
            .order_by(RegistrationPaymentTxn.id.desc())
            .first()
        )
    return None


def _send_registration_thank_you_email(db: Session, user: User, pkg: Package | None) -> bool:
    settings = get_settings()
    if not (settings.smtp_host or "").strip() or not (user.email or "").strip():
        logger.warning(
            "thank-you email skipped: smtp_host=%r user_email=%r user_id=%s",
            settings.smtp_host,
            user.email,
            user.id,
        )
        return False
    try:
        html = render_registration_thank_you_html(user, pkg)
        subject, html = resolve_batch_template_email(
            db,
            user,
            EMAIL_TEMPLATE_TYPE_REGISTRATION_THANK_YOU,
            default_subject=REGISTRATION_THANK_YOU_SUBJECT,
            default_html=html,
            package=pkg,
        )
        send_html_email(
            (user.email or "").strip(),
            subject,
            html,
            cc=settings.smtp_cc or None,
            bcc=settings.smtp_bcc or None,
        )
        logger.info("thank-you email sent to user_id=%s email=%s", user.id, user.email)
        return True
    except Exception as exc:
        err = str(exc)
        if "550" in err and "not verified" in err.lower():
            logger.error(
                "thank-you email FAILED (SMTP sender not verified). Set SMTP_FROM to an address "
                "verified in ZeptoMail (Mail Agents) or your SMTP provider, then retry. user_id=%s email=%s",
                user.id,
                user.email,
            )
        else:
            logger.error(
                "post-payment thank-you email FAILED for user_id=%s email=%s: %s",
                user.id,
                user.email,
                exc,
                exc_info=True,
            )
        return False


def _parse_txn_callback_payload(txn: RegistrationPaymentTxn) -> dict:
    raw = (txn.callback_payload or "").strip()
    if not raw:
        return {}
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        return {}


def _merge_txn_callback_payload(txn: RegistrationPaymentTxn, updates: dict) -> dict:
    data = _parse_txn_callback_payload(txn)
    for key, value in updates.items():
        if value is not None:
            data[key] = value
    txn.callback_payload = json.dumps(data)
    return data


def extension_txn_payload_fields(txn: RegistrationPaymentTxn) -> dict[str, str | None]:
    data = _parse_txn_callback_payload(txn)
    return {
        "offline_reference": (data.get("offline_reference") or "").strip() or None,
        "student_note": (data.get("student_note") or "").strip() or None,
        "failure_reason": (data.get("failure_reason") or "").strip() or None,
        "admin_note": (data.get("admin_note") or "").strip() or None,
    }


def _get_pending_extension_txn(db: Session, user: User, request_id: str) -> RegistrationPaymentTxn:
    rid = (request_id or "").strip()
    if not rid:
        raise HTTPException(status_code=422, detail="request_id is required")
    txn = (
        db.query(RegistrationPaymentTxn)
        .filter(
            RegistrationPaymentTxn.request_id == rid,
            RegistrationPaymentTxn.user_id == user.id,
            RegistrationPaymentTxn.gateway == "extension",
        )
        .first()
    )
    if not txn:
        raise HTTPException(status_code=404, detail="Extension transaction not found")
    if (txn.is_finalized or "").strip() == "1":
        raise HTTPException(status_code=400, detail="This extension payment is already finalized.")
    status = (txn.gateway_status or "").strip().lower()
    if status == "rejected":
        raise HTTPException(status_code=400, detail="This extension request was rejected. Start a new extension payment.")
    return txn


def report_extension_payment_failed(
    db: Session,
    user: User,
    *,
    request_id: str,
    reason: str | None = None,
) -> dict:
    txn = _get_pending_extension_txn(db, user, request_id)
    txn.gateway_status = "payment_failed"
    _merge_txn_callback_payload(txn, {"failure_reason": (reason or "").strip() or None})
    db.add(txn)
    db.commit()
    return {
        "status": "ok",
        "message": "Payment failure recorded.",
        "gateway_status": txn.gateway_status,
    }


def report_extension_offline_payment(
    db: Session,
    user: User,
    *,
    request_id: str,
    offline_reference: str,
    note: str | None = None,
) -> dict:
    ref = (offline_reference or "").strip()
    if not ref:
        raise HTTPException(status_code=422, detail="offline_reference is required")
    txn = _get_pending_extension_txn(db, user, request_id)
    txn.gateway_status = "pending_offline"
    _merge_txn_callback_payload(
        txn,
        {
            "offline_reference": ref,
            "student_note": (note or "").strip() or None,
        },
    )
    db.add(txn)
    db.commit()
    return {
        "status": "ok",
        "message": "Offline payment details submitted for admin review.",
        "gateway_status": txn.gateway_status,
    }


def apply_offline_extension_credit(
    db: Session,
    txn: RegistrationPaymentTxn,
    *,
    payment_details: str | None = None,
    admin_note: str | None = None,
) -> dict:
    if (txn.gateway or "").strip().lower() != "extension":
        raise HTTPException(status_code=400, detail="Not an extension transaction")
    if (txn.is_finalized or "").strip() == "1":
        raise HTTPException(status_code=400, detail="Extension payment already finalized")
    status = (txn.gateway_status or "").strip().lower()
    if status == "rejected":
        raise HTTPException(status_code=400, detail="Cannot approve a rejected extension request")

    user = db.query(User).filter(User.id == txn.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if _user_has_extension_payment(db, user):
        raise HTTPException(status_code=400, detail="User already has an approved extension payment")

    now = datetime.utcnow()
    payment_id = f"offline_ext_{user.id}_{int(now.timestamp())}"
    payload = {
        "source": "admin_offline_extension",
        "details": payment_details or "",
        "admin_note": admin_note or "",
        **_parse_txn_callback_payload(txn),
    }
    _apply_registration_payment_success(
        db,
        txn=txn,
        user=user,
        order_id=(txn.gateway_order_id or txn.request_id),
        payment_id=payment_id,
        signature="",
        raw_payload=payload,
        source="admin_offline_extension",
        payment_type="Offline",
    )

    active = find_active_user_subscription(db, user)
    extended_end = active.end_at.isoformat() if active and active.end_at else None
    return {
        "status": "ok",
        "message": "Extension approved and applied.",
        "extended_end_at": extended_end,
    }


def reject_extension_request(
    db: Session,
    txn: RegistrationPaymentTxn,
    *,
    admin_note: str | None = None,
) -> dict:
    if (txn.gateway or "").strip().lower() != "extension":
        raise HTTPException(status_code=400, detail="Not an extension transaction")
    if (txn.is_finalized or "").strip() == "1":
        raise HTTPException(status_code=400, detail="Extension payment already finalized")
    txn.gateway_status = "rejected"
    _merge_txn_callback_payload(txn, {"admin_note": (admin_note or "").strip() or None})
    db.add(txn)
    db.commit()
    return {"status": "ok", "message": "Extension request rejected."}


def try_finalize_extension_txn(db: Session, txn: RegistrationPaymentTxn) -> dict | None:
    """Try to finalize one extension txn from Razorpay capture (admin sync)."""
    if (txn.gateway or "").strip().lower() != "extension":
        raise HTTPException(status_code=400, detail="Not an extension transaction")
    if (txn.is_finalized or "").strip() == "1":
        return {"request_id": txn.request_id, "payment_id": txn.gateway_payment_id or ""}

    order_id = (txn.gateway_order_id or "").strip()
    if not order_id:
        raise HTTPException(status_code=400, detail="No Razorpay order id on this request")

    user = db.query(User).filter(User.id == txn.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    try:
        payload = _razorpay_api_get(f"/v1/orders/{order_id}/payments")
    except HTTPException as exc:
        raise HTTPException(status_code=400, detail="Could not verify payment with Razorpay") from exc

    items = payload.get("items") or []
    paid = next(
        (p for p in items if (p.get("status") or "").lower() in {"captured", "authorized"}),
        None,
    )
    if not paid:
        raise HTTPException(
            status_code=400,
            detail="Razorpay has no captured payment for this order yet.",
        )

    payment_id = str(paid.get("id") or "").strip()
    if not payment_id:
        raise HTTPException(status_code=502, detail="Razorpay returned a payment without an id")

    finalize_payment(
        db,
        request_id=txn.request_id,
        order_id=order_id,
        payment_id=payment_id,
        signature="",
        raw_payload=paid,
        source="extension_admin_sync",
        verify_signature=False,
    )
    return {"request_id": txn.request_id, "payment_id": payment_id}


def _apply_registration_payment_success(
    db: Session,
    *,
    txn: RegistrationPaymentTxn,
    user: User,
    order_id: str,
    payment_id: str,
    signature: str,
    raw_payload: dict | None,
    source: str,
    payment_type: str = "Online",
) -> None:
    txn.gateway_order_id = order_id
    txn.gateway_payment_id = payment_id
    txn.gateway_signature = signature
    txn.gateway_status = "paid"
    txn.is_finalized = "1"
    if source == "webhook":
        txn.webhook_payload = json.dumps(raw_payload or {})
    else:
        txn.callback_payload = json.dumps(raw_payload or {})

    is_extension = (txn.gateway or "").strip().lower() == "extension"
    now = datetime.utcnow()
    user.payment_id = payment_id
    user.payment_signature = signature
    user.payment_type = payment_type
    user.payment_date = now
    user.payment_details = json.dumps(raw_payload or {})
    if not is_extension:
        user.payment_status = "Credit"
        if (user.approve or "").strip() != "1":
            user.approve = "1"

    pkg = db.query(Package).filter(Package.id == txn.package_id).first()
    if is_extension:
        manual = get_extension_batch_settings(db, user.subscription)
        extend_months = int(manual.get("months") or 2)
        base_day = parse_iso_date(manual.get("base_date"))
        extension_base = (
            datetime.combine(base_day, datetime.max.time()).replace(microsecond=0) if base_day else None
        )
        extend_active_subscription(
            db,
            user_id=user.id,
            batch_slug=(txn.batch_slug or batch_slug(user.subscription)),
            extend_months=extend_months,
            activated_at=now,
            extension_base_date=extension_base,
            package_id=txn.package_id or user.package_id,
        )
    elif pkg:
        plan_type = (pkg.plan_type or "one_time").strip().lower()
        if plan_type == "subscription":
            activate_user_subscription(
                db,
                user_id=user.id,
                batch_slug=(txn.batch_slug or ""),
                package_id=pkg.id,
                duration_months=pkg.duration_months,
                activated_at=user.payment_date or now,
            )

    if txn.coupon_code:
        coupon = (
            _coupon_query(db)
            .filter(CouponMaster.code == txn.coupon_code, CouponMaster.status.in_(["0", "1"]))
            .first()
        )
        if coupon:
            coupon.status = "2"
            db.add(coupon)

    upp = (
        db.query(UserPackagePayment)
        .filter(
            UserPackagePayment.user_id == user.id,
            UserPackagePayment.payment_request_id == txn.request_id,
        )
        .order_by(UserPackagePayment.id.desc())
        .first()
    )
    if not upp:
        upp = UserPackagePayment(
            user_id=user.id,
            package_id=txn.package_id,
            subscription=user.subscription,
            package_type="Topup Extension" if is_extension else "registration",
            currency_name=txn.currency,
            payment_request_id=txn.request_id,
        )
    upp.payment_id = payment_id
    upp.payment_status = "Credit"
    upp.payment_type = payment_type
    upp.payment_date = user.payment_date
    upp.payment_signature = signature
    upp.payment_details = user.payment_details
    db.add(upp)
    db.add(txn)
    db.add(user)
    db.commit()
    if not is_extension:
        try_send_registration_thank_you_email(db, user, pkg)
    logger.info(
        "registration payment captured user_id=%s request_id=%s order_id=%s payment_id=%s source=%s",
        user.id,
        txn.request_id,
        order_id,
        payment_id,
        source,
    )


def try_finalize_pending_extension_payment(db: Session, user: User) -> dict | None:
    """If Razorpay captured an extension payment but callback missed, apply extension now."""
    txn = (
        db.query(RegistrationPaymentTxn)
        .filter(
            RegistrationPaymentTxn.user_id == user.id,
            RegistrationPaymentTxn.gateway == "extension",
            RegistrationPaymentTxn.is_finalized != "1",
        )
        .order_by(RegistrationPaymentTxn.id.desc())
        .all()
    )
    for row in txn:
        order_id = (row.gateway_order_id or "").strip()
        if not order_id:
            continue
        try:
            payload = _razorpay_api_get(f"/v1/orders/{order_id}/payments")
        except HTTPException:
            continue
        items = payload.get("items") or []
        paid = next(
            (p for p in items if (p.get("status") or "").lower() in {"captured", "authorized"}),
            None,
        )
        if not paid:
            continue
        payment_id = str(paid.get("id") or "").strip()
        if not payment_id:
            continue
        finalize_payment(
            db,
            request_id=row.request_id,
            order_id=order_id,
            payment_id=payment_id,
            signature="",
            raw_payload=paid,
            source="extension_sync",
            verify_signature=False,
        )
        logger.info(
            "extension payment auto-finalized user_id=%s request_id=%s payment_id=%s",
            user.id,
            row.request_id,
            payment_id,
        )
        return {"request_id": row.request_id, "payment_id": payment_id}
    return None


def confirm_extension_payment(
    db: Session,
    user: User,
    *,
    request_id: str | None = None,
    order_id: str | None = None,
    payment_id: str | None = None,
    signature: str | None = None,
    raw_payload: dict | None = None,
) -> dict:
    """Finalize extension checkout and extend course access (Razorpay capture is source of truth)."""
    if request_id and order_id and payment_id:
        txn = (
            db.query(RegistrationPaymentTxn)
            .filter(
                RegistrationPaymentTxn.request_id == request_id,
                RegistrationPaymentTxn.user_id == user.id,
                RegistrationPaymentTxn.gateway == "extension",
            )
            .first()
        )
        if not txn:
            raise HTTPException(status_code=404, detail="Extension transaction not found")
        finalize_payment(
            db,
            request_id=request_id,
            order_id=order_id,
            payment_id=payment_id,
            signature=signature or "",
            raw_payload=raw_payload,
            source="extension_confirm",
            verify_signature=False,
        )
    else:
        synced = try_finalize_pending_extension_payment(db, user)
        if not synced:
            raise HTTPException(
                status_code=400,
                detail="No captured extension payment found yet. Complete payment in Razorpay first.",
            )

    active = find_active_user_subscription(db, user)
    manual = get_extension_batch_settings(db, user.subscription)
    months = int(manual.get("months") or 2)
    extended_end = active.end_at.isoformat() if active and active.end_at else None
    return {
        "status": "ok",
        "message": "Extension applied successfully.",
        "extension_months": months,
        "extended_end_at": extended_end,
        "extension_active": bool(active and active.end_at),
    }


def sync_registration_payment_from_razorpay(db: Session, user_id: int) -> PaymentFinalizeResponse:
    """
    Recover missed payment callbacks: verify captured payment on Razorpay order, then finalize locally.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    ext_synced = try_finalize_pending_extension_payment(db, user)
    if ext_synced:
        return PaymentFinalizeResponse(
            request_id=ext_synced["request_id"],
            status="ok",
            payment_status=user.payment_status or "Credit",
            approve=user.approve or "1",
            user_id=user.id,
            message="Extension payment synced from Razorpay",
        )

    if (user.payment_status or "").strip().lower() == "credit":
        pkg = _package_for_thank_you_email(db, user)
        try_send_registration_thank_you_email(db, user, pkg)
        return PaymentFinalizeResponse(
            request_id=(user.payment_request_id or ""),
            status="ok",
            payment_status="Credit",
            approve=user.approve or "1",
            user_id=user.id,
            message="Payment already marked Credit",
        )

    txn = (
        db.query(RegistrationPaymentTxn)
        .filter(
            RegistrationPaymentTxn.user_id == user.id,
            RegistrationPaymentTxn.is_finalized != "1",
        )
        .order_by(RegistrationPaymentTxn.id.desc())
        .first()
    )
    if not txn:
        txn = (
            db.query(RegistrationPaymentTxn)
            .filter(RegistrationPaymentTxn.user_id == user.id)
            .order_by(RegistrationPaymentTxn.id.desc())
            .first()
        )
    if not txn:
        raise HTTPException(status_code=400, detail="No registration payment transaction found for this user.")

    order_id = (txn.gateway_order_id or "").strip()
    if not order_id:
        raise HTTPException(status_code=400, detail="No Razorpay order id on file. User must complete checkout again.")

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

    if txn.is_finalized == "1":
        user.payment_status = "Credit"
        user.approve = user.approve or "1"
        if not user.payment_id:
            user.payment_id = payment_id
        db.add(user)
        db.commit()
        pkg = _package_for_thank_you_email(db, user, txn)
        try_send_registration_thank_you_email(db, user, pkg)
        return PaymentFinalizeResponse(
            request_id=txn.request_id,
            status="ok",
            payment_status="Credit",
            approve=user.approve or "1",
            user_id=user.id,
            message="User payment status updated to Credit",
        )

    _apply_registration_payment_success(
        db,
        txn=txn,
        user=user,
        order_id=order_id,
        payment_id=payment_id,
        signature="",
        raw_payload=paid,
        source="admin_sync",
        payment_type="Online",
    )
    return PaymentFinalizeResponse(
        request_id=txn.request_id,
        status="ok",
        payment_status="Credit",
        approve=user.approve or "1",
        user_id=user.id,
        message="Payment synced from Razorpay",
    )


def apply_offline_registration_credit(
    db: Session,
    user: User,
    *,
    payment_details: str | None = None,
) -> None:
    """Admin: mark registration paid when Razorpay callback never ran."""
    if (user.payment_status or "").strip().lower() == "credit":
        return

    txn = (
        db.query(RegistrationPaymentTxn)
        .filter(
            RegistrationPaymentTxn.user_id == user.id,
            RegistrationPaymentTxn.is_finalized != "1",
            RegistrationPaymentTxn.gateway != "extension",
        )
        .order_by(RegistrationPaymentTxn.id.desc())
        .first()
    )
    now = datetime.utcnow()
    payment_id = f"offline_{user.id}_{int(now.timestamp())}"

    if txn:
        _apply_registration_payment_success(
            db,
            txn=txn,
            user=user,
            order_id=(txn.gateway_order_id or txn.request_id),
            payment_id=payment_id,
            signature="",
            raw_payload={"source": "admin_offline_credit", "details": payment_details or ""},
            source="admin_offline",
            payment_type="Offline",
        )
        if payment_details:
            user.payment_details = payment_details
            db.add(user)
            db.commit()
        return

    user.payment_status = "Credit"
    user.payment_type = "Offline"
    user.payment_date = now
    user.approve = "1"
    user.payment_id = payment_id
    if payment_details:
        user.payment_details = payment_details

    if user.coupon_code:
        coupon = _coupon_query(db).filter(CouponMaster.code == user.coupon_code).first()
        if coupon:
            coupon.status = "2"
            db.add(coupon)

    pkg = db.query(Package).filter(Package.id == user.package_id).first() if user.package_id else None
    if pkg and (pkg.plan_type or "").strip().lower() == "subscription":
        activate_user_subscription(
            db,
            user_id=user.id,
            batch_slug=(user.subscription or "").strip().lower(),
            package_id=pkg.id,
            duration_months=pkg.duration_months,
            activated_at=now,
        )

    upp = (
        db.query(UserPackagePayment)
        .filter(UserPackagePayment.user_id == user.id)
        .order_by(UserPackagePayment.id.desc())
        .first()
    )
    if not upp and user.package_id:
        upp = UserPackagePayment(
            user_id=user.id,
            package_id=user.package_id,
            subscription=user.subscription,
            package_type="registration",
            currency_name=user.currency_name,
            payment_request_id=user.payment_request_id,
        )
    if upp:
        upp.payment_status = "Credit"
        upp.payment_type = "Offline"
        upp.payment_date = now
        upp.payment_id = payment_id
        if payment_details:
            upp.payment_details = payment_details
        db.add(upp)

    db.add(user)
    db.commit()
    try_send_registration_thank_you_email(db, user, pkg)


def confirm_registration_after_payment(db: Session, registration_id: int) -> dict:
    """
    Thank-you page hook: finalize Razorpay payment if needed and (re)send thank-you email.
    Idempotent — safe to call after /payment/callback.
    """
    user = db.query(User).filter(User.id == registration_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Registration not found")

    payment_status = (user.payment_status or "").strip()
    if payment_status.lower() != "credit":
        try:
            sync_registration_payment_from_razorpay(db, user.id)
            db.refresh(user)
            payment_status = (user.payment_status or "").strip()
        except HTTPException:
            pass

    if payment_status.lower() != "credit":
        return {
            "status": "pending",
            "payment_status": payment_status or "Pending",
            "email_sent": False,
            "message": "Payment not completed yet",
        }

    txn = (
        db.query(RegistrationPaymentTxn)
        .filter(RegistrationPaymentTxn.user_id == user.id)
        .order_by(RegistrationPaymentTxn.id.desc())
        .first()
    )
    pkg = _package_for_thank_you_email(db, user, txn)
    email_sent = try_send_registration_thank_you_email(db, user, pkg)
    return {
        "status": "ok",
        "payment_status": "Credit",
        "email_sent": email_sent,
        "message": "Thank-you email sent" if email_sent else "Thank-you email could not be sent (check SMTP logs)",
    }


def _verify_webhook_signature(body: bytes, signature_header: str) -> bool:
    settings = get_settings()
    secret = (settings.payment_webhook_secret or "").strip()
    if not secret:
        return True
    sig = (signature_header or "").strip()
    if not sig:
        return False
    digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(digest, sig)


def process_razorpay_webhook(db: Session, payload: dict) -> PaymentFinalizeResponse | dict:
    """
    Handle Razorpay `payment.captured` webhooks (and legacy flat test payloads).
    Finalizes using Razorpay API verification, not checkout HMAC.
    """
    event = (payload.get("event") or "").strip()
    if event and event not in {"payment.captured", "order.paid"}:
        return {"status": "ignored", "event": event}

    entity = payload.get("payload", {}).get("payment", {}).get("entity") or {}
    if not entity and event:
        return {"status": "ignored", "event": event, "reason": "no payment entity"}

    order_id = (
        (entity.get("order_id") or "").strip()
        or (payload.get("order_id") or "").strip()
    )
    payment_id = (
        (entity.get("id") or "").strip()
        or (payload.get("payment_id") or "").strip()
    )
    notes = entity.get("notes") or payload.get("notes") or {}
    if isinstance(notes, list):
        notes = {}
    request_id = (notes.get("request_id") or payload.get("request_id") or "").strip()
    event_request_id = (notes.get("event_request_id") or "").strip()

    if not order_id or not payment_id:
        raise HTTPException(status_code=400, detail="Invalid webhook payload: missing order_id or payment_id")

    txn = _txn_by_request_or_order(db, request_id=request_id or None, order_id=order_id)
    if not txn:
        from app.services.event_payments import process_event_razorpay_webhook

        event_result = process_event_razorpay_webhook(
            db,
            order_id=order_id,
            payment_id=payment_id,
            request_id=event_request_id or request_id or None,
            payload=payload,
        )
        if event_result is not None:
            return event_result
        raise HTTPException(status_code=404, detail="Transaction not found for webhook")

    return finalize_payment(
        db=db,
        request_id=txn.request_id,
        order_id=order_id,
        payment_id=payment_id,
        signature="",
        raw_payload=payload,
        source="webhook",
        verify_signature=False,
    )


def finalize_payment(
    db: Session,
    request_id: str,
    order_id: str,
    payment_id: str,
    signature: str,
    raw_payload: dict | None = None,
    source: str = "callback",
    *,
    verify_signature: bool = True,
) -> PaymentFinalizeResponse:
    txn = db.query(RegistrationPaymentTxn).filter(RegistrationPaymentTxn.request_id == request_id).first()
    if not txn:
        raise HTTPException(status_code=404, detail="Transaction not found")
    user = db.query(User).filter(User.id == txn.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if txn.is_finalized == "1":
        if (user.payment_status or "").strip().lower() == "credit":
            pkg = _package_for_thank_you_email(db, user, txn)
            try_send_registration_thank_you_email(db, user, pkg)
        return PaymentFinalizeResponse(
            request_id=request_id,
            status="ok",
            payment_status=user.payment_status or "Credit",
            approve=user.approve or "1",
            user_id=user.id,
            message="Payment already finalized",
        )

    signature_ok = (not verify_signature) or _verify_signature(order_id, payment_id, signature)
    captured_on_gateway = _razorpay_payment_is_captured(order_id, payment_id)

    if verify_signature and not signature_ok:
        if captured_on_gateway:
            logger.warning(
                "checkout signature mismatch but Razorpay payment is captured; finalizing request_id=%s payment_id=%s",
                request_id,
                payment_id,
            )
        else:
            is_extension = (txn.gateway or "").strip().lower() == "extension"
            txn.gateway_status = "signature_failed"
            if not is_extension:
                user.payment_status = "Failed"
                user.approve = "0"
            txn.callback_payload = json.dumps(raw_payload or {})
            db.add(txn)
            if not is_extension:
                db.add(user)
            db.commit()
            logger.error(
                "payment not captured: invalid signature and Razorpay status not captured request_id=%s order_id=%s",
                request_id,
                order_id,
            )
            raise HTTPException(
                status_code=400,
                detail="Invalid payment signature. Payment was not confirmed as captured on Razorpay.",
            )

    if not verify_signature and not captured_on_gateway:
        raise HTTPException(
            status_code=400,
            detail="Payment is not captured on Razorpay yet. Try again after payment completes.",
        )

    _apply_registration_payment_success(
        db,
        txn=txn,
        user=user,
        order_id=order_id,
        payment_id=payment_id,
        signature=signature,
        raw_payload=raw_payload,
        source=source,
        payment_type="Online",
    )

    return PaymentFinalizeResponse(
        request_id=request_id,
        status="ok",
        payment_status=user.payment_status or "Credit",
        approve=user.approve or "1",
        user_id=user.id,
        message="Payment finalized",
    )
