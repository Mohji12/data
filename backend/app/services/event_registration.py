from __future__ import annotations

import json
import logging
import re
import uuid
from datetime import datetime
from typing import Any

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import Country, EventPaymentTxn, EventRegistration, Option
from app.services.email_templates import event_registration_confirmation_template
from app.services.mailer import send_html_email

logger = logging.getLogger(__name__)

EVENT_TITLE = '1st NATIONAL "ICU-D CONCLAVE"'
EVENT_DATES = "11th and 12th July 2026"
EVENT_CONFIRMATION_EMAIL_SUBJECT = 'Welcome to 1st National "ICU-ID Conclave 2026"'
REG_NUMBER_PREFIX = "ICUD2026-"
_EVENT_CONFIRMATION_SENT_PREFIX = "event_confirmation_sent::"
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_VALID_CATEGORIES = {"clinician", "student"}
_CATEGORY_LABELS = {
    "clinician": "Practicing Clinician",
    "student": "Student",
}


def icu_d_conclave_slug() -> str:
    return get_settings().event_icu_d_conclave_slug or "icu-d-conclave-2026"


def _event_fee_breakdown() -> dict[str, float]:
    settings = get_settings()
    base = float(settings.event_icu_d_conclave_fee_inr or 0)
    gst_percent = float(settings.event_icu_d_conclave_gst_percent or 18)
    gst_amount = round(base * gst_percent / 100, 2)
    total = round(base + gst_amount, 2)
    return {
        "base_fee_inr": base,
        "gst_percent": gst_percent,
        "gst_amount_inr": gst_amount,
        "total_fee_inr": total,
        "fee_inr": total,
    }


def _event_promo_codes() -> set[str]:
    return set(get_settings().event_icu_d_conclave_promo_codes or [])


def _is_valid_event_promo(promo_code: str | None) -> bool:
    code = (promo_code or "").strip().upper()
    if not code:
        return False
    return code in _event_promo_codes()


def _apply_promo_to_fees(fees: dict[str, float], promo_code: str | None) -> dict[str, Any]:
    code = (promo_code or "").strip()
    if not code:
        return {**fees, "promo_applied": False, "promo_code": ""}
    if not _is_valid_event_promo(code):
        return {**fees, "promo_applied": False, "promo_code": code, "promo_invalid": True}
    gst_percent = float(fees.get("gst_percent") or 18)
    return {
        "base_fee_inr": 0.0,
        "gst_percent": gst_percent,
        "gst_amount_inr": 0.0,
        "total_fee_inr": 0.0,
        "fee_inr": 0.0,
        "promo_applied": True,
        "promo_code": code.upper(),
        "promo_invalid": False,
    }


def get_event_payable_amount(promo_code: str | None = None) -> dict[str, Any]:
    base = _event_fee_breakdown()
    result = _apply_promo_to_fees(base, promo_code)
    if result.get("promo_invalid"):
        return {**base, "promo_applied": False, "promo_invalid": True, "promo_code": result.get("promo_code", "")}
    return result


def get_event_public_config() -> dict[str, Any]:
    settings = get_settings()
    slug = icu_d_conclave_slug()
    fees = _event_fee_breakdown()
    return {
        "event_slug": slug,
        "title": EVENT_TITLE,
        "dates": EVENT_DATES,
        **fees,
        "active": bool(settings.event_icu_d_conclave_active),
        "contact_phone": "+91 8095218493",
        "contact_name": "Dr. Harish Mallapura Maheshwarappa",
        "register_path": f"/events/{slug}/register",
        "promo_enabled": bool(_event_promo_codes()),
    }


def _normalize_email(email: str) -> str:
    return email.strip().lower()


def _allocate_registration_number(db: Session, event_slug: str) -> str:
    prefix = REG_NUMBER_PREFIX
    last = (
        db.query(EventRegistration)
        .filter(
            EventRegistration.event_slug == event_slug,
            EventRegistration.registration_number.like(f"{prefix}%"),
        )
        .order_by(EventRegistration.id.desc())
        .first()
    )
    seq = 1
    if last and last.registration_number:
        try:
            seq = int(str(last.registration_number).split("-")[-1]) + 1
        except ValueError:
            seq = (
                db.query(func.count(EventRegistration.id))
                .filter(EventRegistration.event_slug == event_slug)
                .scalar()
                or 0
            ) + 1
    return f"{prefix}{seq:06d}"


def _resolve_country_name(db: Session, country_id: int | None) -> str:
    if not country_id:
        return ""
    row = db.query(Country).filter(Country.id == country_id).first()
    return (row.name or "").strip() if row else ""


def _validate_init_payload(data: dict[str, Any]) -> dict[str, Any]:
    settings = get_settings()
    if not settings.event_icu_d_conclave_active:
        raise HTTPException(status_code=403, detail="Event registration is currently closed.")

    base_fees = _event_fee_breakdown()
    if base_fees["total_fee_inr"] <= 0:
        raise HTTPException(
            status_code=503,
            detail="Event registration fee is not configured (EVENT_ICU_D_CONCLAVE_FEE_INR).",
        )

    promo_code = str(data.get("promo_code") or "").strip()
    fees = _apply_promo_to_fees(base_fees, promo_code)
    if promo_code and fees.get("promo_invalid"):
        raise HTTPException(status_code=400, detail="Invalid promo code.")

    email = _normalize_email(str(data.get("email") or ""))
    if not email or not _EMAIL_RE.match(email):
        raise HTTPException(status_code=400, detail="Enter a valid email address.")

    category = str(data.get("category") or "").strip().lower()
    if category not in _VALID_CATEGORIES:
        raise HTTPException(status_code=400, detail="Select a valid category.")

    phone = str(data.get("phone") or "").strip()
    if len(phone) < 8:
        raise HTTPException(status_code=400, detail="Enter a valid phone number.")

    if not bool(data.get("declaration_accepted")):
        raise HTTPException(status_code=400, detail="You must accept the declaration.")

    required_text = [
        ("full_name", "Full name"),
        ("designation", "Designation"),
        ("specialty", "Specialty"),
        ("hospital", "Hospital / Institution name"),
        ("city", "City"),
        ("state", "State"),
        ("council_state", "State in which registration was done"),
        ("council_registration_number", "Medical / Nursing council registration number"),
    ]
    for key, label in required_text:
        if not str(data.get(key) or "").strip():
            raise HTTPException(status_code=400, detail=f"{label} is required.")

    country_id = data.get("country_id")
    try:
        country_id_int = int(country_id) if country_id is not None else None
    except (TypeError, ValueError):
        country_id_int = None
    if not country_id_int:
        raise HTTPException(status_code=400, detail="Country is required.")

    return {
        "email": email,
        "category": category,
        "phone": phone,
        "country_id": country_id_int,
        "country_name": str(data.get("country_name") or "").strip(),
        "full_name": str(data["full_name"]).strip(),
        "designation": str(data["designation"]).strip(),
        "specialty": str(data["specialty"]).strip(),
        "hospital": str(data["hospital"]).strip(),
        "city": str(data["city"]).strip(),
        "state": str(data["state"]).strip(),
        "council_state": str(data["council_state"]).strip(),
        "council_registration_number": str(data["council_registration_number"]).strip(),
        **fees,
    }


def _complete_free_event_registration(
    db: Session,
    *,
    reg: EventRegistration,
    txn: EventPaymentTxn,
    promo_code: str,
) -> bool:
    now = datetime.utcnow()
    code = promo_code.strip().upper()
    reg.amount_inr = 0.0
    reg.payment_status = "Credit"
    reg.payment_type = "Promo"
    reg.payment_id = code
    reg.payment_date = now
    reg.payment_details = json.dumps({"promo_code": code, "amount_waived": True})
    reg.updated_at = now

    txn.amount = 0.0
    txn.gateway = "promo"
    txn.gateway_status = "waived"
    txn.is_finalized = "1"
    txn.updated_at = now

    db.add(reg)
    db.add(txn)
    db.commit()
    db.refresh(reg)
    return try_send_event_confirmation_email(db, reg)


def _init_response_from_registration(
    *,
    registration_id: int,
    registration_number: str,
    request_id: str,
    fees: dict[str, Any],
    payment_status: str,
    payment_required: bool,
    email_sent: bool = False,
) -> dict[str, Any]:
    return {
        "registration_id": registration_id,
        "registration_number": registration_number,
        "request_id": request_id,
        "amount_inr": float(fees.get("total_fee_inr") or 0),
        "payment_status": payment_status,
        "payment_required": payment_required,
        "email_sent": email_sent,
        "promo_applied": bool(fees.get("promo_applied")),
        **{k: fees[k] for k in ("base_fee_inr", "gst_percent", "gst_amount_inr", "total_fee_inr") if k in fees},
    }


def _fee_breakdown_from_total(total_inr: float) -> dict[str, float]:
    """Reverse-calculate base + GST from a stored total (for confirmation emails)."""
    settings = get_settings()
    gst_percent = float(settings.event_icu_d_conclave_gst_percent or 18)
    total = round(float(total_inr or 0), 2)
    if total <= 0:
        return _event_fee_breakdown()
    base = round(total / (1 + gst_percent / 100), 2)
    gst_amount = round(total - base, 2)
    return {
        "base_fee_inr": base,
        "gst_percent": gst_percent,
        "gst_amount_inr": gst_amount,
        "total_fee_inr": total,
        "fee_inr": total,
    }


def initialize_event_registration(db: Session, payload: dict[str, Any]) -> dict[str, Any]:
    slug = icu_d_conclave_slug()
    validated = _validate_init_payload(payload)

    paid = (
        db.query(EventRegistration)
        .filter(
            EventRegistration.event_slug == slug,
            func.lower(EventRegistration.email) == validated["email"],
            func.lower(func.trim(EventRegistration.payment_status)) == "credit",
        )
        .first()
    )
    if paid:
        raise HTTPException(
            status_code=409,
            detail=f"You are already registered for this event (registration number {paid.registration_number}).",
        )

    pending = (
        db.query(EventRegistration)
        .filter(
            EventRegistration.event_slug == slug,
            func.lower(EventRegistration.email) == validated["email"],
            func.lower(func.trim(EventRegistration.payment_status)) == "pending",
        )
        .order_by(EventRegistration.id.desc())
        .first()
    )
    if pending:
        txn = (
            db.query(EventPaymentTxn)
            .filter(
                EventPaymentTxn.event_registration_id == pending.id,
                EventPaymentTxn.is_finalized != "1",
            )
            .order_by(EventPaymentTxn.id.desc())
            .first()
        )
        if txn:
            fees = validated if validated.get("promo_applied") else _fee_breakdown_from_total(
                float(pending.amount_inr or validated["fee_inr"])
            )
            if validated.get("promo_applied"):
                pending.amount_inr = 0.0
                txn.amount = 0.0
                db.add(pending)
                db.add(txn)
                db.flush()
            if float(fees.get("total_fee_inr") or 0) <= 0 and validated.get("promo_applied"):
                email_sent = _complete_free_event_registration(
                    db,
                    reg=pending,
                    txn=txn,
                    promo_code=str(validated.get("promo_code") or ""),
                )
                return _init_response_from_registration(
                    registration_id=pending.id,
                    registration_number=pending.registration_number,
                    request_id=txn.request_id,
                    fees=fees,
                    payment_status="Credit",
                    payment_required=False,
                    email_sent=email_sent,
                )
            db.commit()
            return _init_response_from_registration(
                registration_id=pending.id,
                registration_number=pending.registration_number,
                request_id=txn.request_id,
                fees=fees,
                payment_status=pending.payment_status or "Pending",
                payment_required=True,
            )

    country_name = validated["country_name"] or _resolve_country_name(db, validated["country_id"])
    reg_number = _allocate_registration_number(db, slug)
    request_id = uuid.uuid4().hex

    row = EventRegistration(
        event_slug=slug,
        registration_number=reg_number,
        full_name=validated["full_name"],
        designation=validated["designation"],
        category=validated["category"],
        specialty=validated["specialty"],
        email=validated["email"],
        phone=validated["phone"],
        country_id=validated["country_id"],
        country_name=country_name,
        hospital=validated["hospital"],
        city=validated["city"],
        state=validated["state"],
        council_state=validated["council_state"],
        council_registration_number=validated["council_registration_number"],
        declaration_accepted="1",
        payment_status="Pending",
        amount_inr=validated["fee_inr"],
        payment_type="Online",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(row)
    db.flush()

    txn = EventPaymentTxn(
        request_id=request_id,
        event_registration_id=row.id,
        amount=validated["fee_inr"],
        currency="INR",
        gateway="razorpay",
        gateway_status="created",
        is_finalized="0",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(txn)
    db.commit()
    db.refresh(row)

    if float(validated.get("total_fee_inr") or 0) <= 0 and validated.get("promo_applied"):
        email_sent = _complete_free_event_registration(
            db,
            reg=row,
            txn=txn,
            promo_code=str(validated.get("promo_code") or ""),
        )
        return _init_response_from_registration(
            registration_id=row.id,
            registration_number=row.registration_number,
            request_id=request_id,
            fees=validated,
            payment_status="Credit",
            payment_required=False,
            email_sent=email_sent,
        )

    return _init_response_from_registration(
        registration_id=row.id,
        registration_number=row.registration_number,
        request_id=request_id,
        fees=validated,
        payment_status=row.payment_status or "Pending",
        payment_required=True,
    )


def _event_confirmation_sent_key(registration_id: int) -> str:
    return f"{_EVENT_CONFIRMATION_SENT_PREFIX}{registration_id}"


def event_confirmation_email_was_sent(db: Session, registration_id: int) -> bool:
    row = db.query(Option).filter(Option.option_name == _event_confirmation_sent_key(registration_id)).first()
    return bool(row and (row.option_value or "").strip() == "1")


def _mark_event_confirmation_email_sent(db: Session, registration_id: int) -> None:
    key = _event_confirmation_sent_key(registration_id)
    row = db.query(Option).filter(Option.option_name == key).first()
    if row:
        row.option_value = "1"
    else:
        db.add(Option(option_name=key, option_value="1"))
    db.commit()


def try_send_event_confirmation_email(
    db: Session,
    registration: EventRegistration,
    *,
    force: bool = False,
) -> bool:
    if (registration.payment_status or "").strip().lower() != "credit":
        return False
    if not force and event_confirmation_email_was_sent(db, registration.id):
        logger.info("event confirmation email already sent reg_id=%s", registration.id)
        return True
    settings = get_settings()
    if not settings.smtp_host:
        logger.warning("event confirmation email skipped: SMTP not configured reg=%s", registration.id)
        return False
    if not (registration.email or "").strip():
        logger.warning("event confirmation email skipped: no email on reg_id=%s", registration.id)
        return False
    html = event_registration_confirmation_template(
        registration_number=registration.registration_number or "",
    )
    subject = EVENT_CONFIRMATION_EMAIL_SUBJECT
    try:
        send_html_email(
            registration.email.strip(),
            subject,
            html,
            cc=settings.smtp_cc or None,
            bcc=settings.smtp_bcc or None,
        )
        _mark_event_confirmation_email_sent(db, registration.id)
        logger.info(
            "event confirmation email sent reg_id=%s email=%s reg_number=%s",
            registration.id,
            registration.email,
            registration.registration_number,
        )
        return True
    except Exception as exc:
        logger.exception(
            "event confirmation email failed reg_id=%s email=%s: %s",
            registration.id,
            registration.email,
            exc,
        )
        return False


def confirm_event_registration(db: Session, registration_id: int) -> dict[str, Any]:
    """Legacy hook — prefer confirm_event_registration_after_payment in event_payments."""
    from app.services.event_payments import confirm_event_registration_after_payment

    return confirm_event_registration_after_payment(db, registration_id)


def get_event_registration_by_number(
    db: Session, registration_number: str
) -> EventRegistration | None:
    return (
        db.query(EventRegistration)
        .filter(
            EventRegistration.event_slug == icu_d_conclave_slug(),
            EventRegistration.registration_number == registration_number.strip(),
        )
        .first()
    )
