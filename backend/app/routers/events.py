from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas import PaymentFinalizeRequest, PaymentOrderRequest, PaymentOrderResponse
from app.services.event_payments import (
    confirm_event_registration_after_payment,
    create_event_payment_order,
    finalize_event_payment,
)
from app.services.event_registration import (
    get_event_public_config,
    get_event_payable_amount,
    get_event_registration_by_number,
    icu_d_conclave_slug,
    initialize_event_registration,
)

router = APIRouter(prefix="/events", tags=["events"])

_SLUG = icu_d_conclave_slug()


class EventInitRequest(BaseModel):
    full_name: str = Field(min_length=1, max_length=255)
    designation: str = Field(min_length=1, max_length=255)
    category: str = Field(description="clinician or student")
    specialty: str = Field(min_length=1, max_length=255)
    email: EmailStr
    phone: str = Field(min_length=8, max_length=50)
    country_id: int
    country_name: Optional[str] = None
    hospital: str = Field(min_length=1, max_length=255)
    city: str = Field(min_length=1, max_length=128)
    state: str = Field(min_length=1, max_length=128)
    council_state: str = Field(min_length=1, max_length=128)
    council_registration_number: str = Field(min_length=1, max_length=128)
    declaration_accepted: bool = False
    promo_code: Optional[str] = None


class EventPayableRequest(BaseModel):
    promo_code: Optional[str] = None


class EventPayableResponse(BaseModel):
    base_fee_inr: float
    gst_percent: float
    gst_amount_inr: float
    total_fee_inr: float
    fee_inr: float
    promo_applied: bool = False
    promo_invalid: bool = False


class EventInitResponse(BaseModel):
    registration_id: int
    registration_number: str
    request_id: str
    amount_inr: float
    payment_status: str
    base_fee_inr: float = 0
    gst_percent: float = 18
    gst_amount_inr: float = 0
    total_fee_inr: float = 0
    payment_required: bool = True
    promo_applied: bool = False
    email_sent: bool = False


class EventFinalizeResponse(BaseModel):
    request_id: str
    status: str
    payment_status: str
    registration_id: int
    registration_number: str
    email_sent: bool = False
    message: str


@router.get(f"/{_SLUG}/config")
def event_config() -> dict[str, Any]:
    return get_event_public_config()


@router.post(f"/{_SLUG}/payable", response_model=EventPayableResponse)
def event_payable(body: EventPayableRequest) -> EventPayableResponse:
    result = get_event_payable_amount(body.promo_code)
    return EventPayableResponse(**result)


@router.post(f"/{_SLUG}/init", response_model=EventInitResponse)
def event_init(
    payload: EventInitRequest,
    db: Session = Depends(get_db),
) -> EventInitResponse:
    result = initialize_event_registration(db, payload.model_dump())
    return EventInitResponse(**result)


@router.post(f"/{_SLUG}/payment/order", response_model=PaymentOrderResponse)
def event_payment_order(
    body: PaymentOrderRequest,
    db: Session = Depends(get_db),
) -> PaymentOrderResponse:
    return create_event_payment_order(db, body.request_id)


@router.post(f"/{_SLUG}/payment/callback", response_model=EventFinalizeResponse)
def event_payment_callback(
    payload: PaymentFinalizeRequest,
    db: Session = Depends(get_db),
) -> EventFinalizeResponse:
    result = finalize_event_payment(
        db=db,
        request_id=payload.request_id,
        order_id=payload.order_id,
        payment_id=payload.payment_id,
        signature=payload.signature,
        raw_payload=payload.raw_payload,
        source="callback",
    )
    return EventFinalizeResponse(**result)


@router.post(f"/{_SLUG}/registrations/{{registration_id}}/confirm")
def event_registration_confirm(
    registration_id: int,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return confirm_event_registration_after_payment(db, registration_id)


@router.get(f"/{_SLUG}/registrations/by-number/{{registration_number}}")
def event_registration_lookup(
    registration_number: str,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    row = get_event_registration_by_number(db, registration_number)
    if not row:
        raise HTTPException(status_code=404, detail="Registration not found")
    return {
        "registration_id": row.id,
        "registration_number": row.registration_number,
        "full_name": row.full_name,
        "payment_status": row.payment_status,
        "amount_inr": float(row.amount_inr or 0),
    }
