from __future__ import annotations

import json
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile
from pydantic import BaseModel
from sqlalchemy import Date, and_, cast, func, or_
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Country, Package, RegistrationPaymentTxn, User, Testimonial
from app.security import get_current_user
from app.schemas import (
    BatchDefinition,
    FeeStructureResponse,
    RegistrationCatalogItem,
    PayableAmountRequest,
    PayableAmountResponse,
    PaymentFinalizeRequest,
    PaymentFinalizeResponse,
    PaymentOrderRequest,
    PaymentOrderResponse,
    RegistrationIdentityCheckRequest,
    RegistrationIdentityCheckResponse,
    RegistrationInitRequest,
    RegistrationInitResponse,
    RegistrationStatusResponse,
    ExtensionConfirmRequest,
    ExtensionConfirmResponse,
    ExtensionInitResponse,
)
from app.services.payments import (
    confirm_registration_after_payment,
    confirm_extension_payment,
    create_payment_order,
    finalize_payment,
    init_extension_payment,
    process_razorpay_webhook,
    _verify_webhook_signature,
)
from app.services.registration import (
    build_registration_catalog,
    _to_display_usd,
    _package_end_open_on_or_after,
    package_subscription_for_batch,
    build_fee_structure_response,
    check_old_student_discount,
    check_registration_identity,
    get_payable_amount,
    get_registration_batch,
    initialize_registration,
    list_batches,
    query_active_packages_for_registration,
    _registration_category_for_packages,
    _resolve_package_line_amounts,
)
from app.services.uploads import save_registration_document

router = APIRouter(prefix="/registration", tags=["registration"])


# ── Country list (was missing – the React form queries this) ──────────────

class CountryOut(BaseModel):
    id: int
    name: str


@router.get("/countries", response_model=list[CountryOut])
def registration_countries(db: Session = Depends(get_db)) -> list[CountryOut]:
    """Country list for registration (legacy PHP loads all rows from `country`, no status filter)."""
    rows = db.query(Country).order_by(Country.name).all()
    if not rows:
        return []
    out: list[CountryOut] = []
    for r in rows:
        name = (r.name or "").strip()
        if not name:
            continue
        status = str(r.status).strip() if r.status is not None else ""
        if status and status not in {"1", "true", "yes", "on"}:
            continue
        out.append(CountryOut(id=r.id, name=name))
    if not out:
        out = [CountryOut(id=r.id, name=(r.name or "").strip()) for r in rows if (r.name or "").strip()]
    return out


@router.get("/batches", response_model=list[BatchDefinition])
def registration_batches(db: Session = Depends(get_db)) -> list[BatchDefinition]:
    return list_batches(db)


@router.get("/catalog", response_model=list[RegistrationCatalogItem])
def registration_catalog(
    include_inactive: bool = Query(False),
    db: Session = Depends(get_db),
) -> list[RegistrationCatalogItem]:
    return build_registration_catalog(db, include_inactive=include_inactive)


# ── Package list for a batch + country (React Step 3 uses this) ───────────

class PackageOut(BaseModel):
    id: int
    name: str
    subscription: Optional[str] = None
    category_name: Optional[str] = None
    gross_amount: float
    gst_percentage: float
    gst_amount: float
    total_amount: float
    plan_type: str = "one_time"
    duration_months: Optional[int] = None
    currency_name: str = "INR"
    pricing_window_label: Optional[str] = None
    sale_start: Optional[str] = None
    sale_end: Optional[str] = None
    is_current_window: bool = False
    is_upcoming_window: bool = False


@router.get("/packages", response_model=list[PackageOut])
def registration_packages(
    batch_slug: str,
    country_id: int = 101,
    registration_type: str | None = Query(None, description="Indian Delegates | Foreign Delegates"),
    selected_package_id: int | None = Query(None),
    db: Session = Depends(get_db),
) -> list[PackageOut]:
    from app.services.registration import (
        _as_date,
        _group_packages_by_pricing_window,
        _get_usd_rate,
        _is_india_country,
        _tier_label_from_package,
    )

    batch = get_registration_batch(db, batch_slug)

    pkgs = query_active_packages_for_registration(
        db, batch, country_id, registration_type=registration_type
    )
    today = date.today()
    expected_category = _registration_category_for_packages(db, country_id, registration_type)
    is_india = expected_category == "Indian Delegates"
    usd_rate = _get_usd_rate(db) if not is_india else 1.0
    currency = "INR" if is_india else "USD"

    # If user clicked "Apply for this plan", force-include that specific valid package
    # so Step 3 never collapses to a different overlapping tier.
    if selected_package_id and not any(p.id == selected_package_id for p in pkgs):
        pkg_sub = package_subscription_for_batch(batch)
        picked = (
            db.query(Package)
            .filter(
                Package.id == selected_package_id,
                func.lower(func.trim(Package.subscription)) == pkg_sub.casefold(),
                Package.status == "1",
                Package.category_name == expected_category,
                or_(Package.start_date.is_(None), cast(Package.start_date, Date) <= date.today()),
                _package_end_open_on_or_after(date.today()),
            )
            .first()
        )
        if picked:
            pkgs = [picked, *pkgs]

    window_meta: dict[int, dict[str, object]] = {}
    sub_rows = [p for p in pkgs if (p.plan_type or "").strip().lower() == "subscription"]
    if sub_rows:
        for group in _group_packages_by_pricing_window(sub_rows):
            start = group["start"]
            end = group["end"]
            label = str(group["label"])
            for pkg in group["packages"]:  # type: ignore[union-attr]
                pkg_start = _as_date(pkg.start_date) or start
                pkg_end = _as_date(pkg.end_date) if pkg.end_date is not None else end
                is_current = (
                    (pkg_start is None or pkg_start <= today)
                    and (pkg_end is None or pkg_end >= today)
                )
                is_upcoming = pkg_start is not None and pkg_start > today
                window_meta[pkg.id] = {
                    "label": label,
                    "start": pkg_start,
                    "end": pkg_end,
                    "is_current": is_current,
                    "is_upcoming": is_upcoming,
                }

    result: list[PackageOut] = []
    for p in pkgs:
        gross, gst_pct, gst_amt, total = _resolve_package_line_amounts(p)
        if not is_india:
            gross = _to_display_usd(gross, usd_rate)
            gst_amt = _to_display_usd(gst_amt, usd_rate)
            total = _to_display_usd(total, usd_rate)
        meta = window_meta.get(p.id, {})
        start_d = meta.get("start")
        end_d = meta.get("end")
        result.append(PackageOut(
            id=p.id,
            name=p.name or "",
            subscription=p.subscription,
            category_name=p.category_name,
            gross_amount=gross,
            gst_percentage=gst_pct,
            gst_amount=gst_amt,
            total_amount=total,
            plan_type=(p.plan_type or "one_time"),
            duration_months=p.duration_months,
            currency_name=currency,
            pricing_window_label=meta.get("label") or _tier_label_from_package(p),
            sale_start=start_d.isoformat() if start_d else None,
            sale_end=end_d.isoformat() if end_d else None,
            is_current_window=bool(meta.get("is_current", True)),
            is_upcoming_window=bool(meta.get("is_upcoming", False)),
        ))
    return result


@router.get("/fee-structure", response_model=FeeStructureResponse)
def registration_fee_structure(batch_slug: str, db: Session = Depends(get_db)) -> FeeStructureResponse:
    """All active pricing tiers for a batch (for public fee pages). Uses `package` + `batch_master.registration_fee_structure` notice."""
    return build_fee_structure_response(db, batch_slug)


# ── Old student discount check ────────────────────────────────────────────

class OldStudentCheckRequest(BaseModel):
    email: str
    subscription: str


class OldStudentCheckResponse(BaseModel):
    is_old_student: bool
    discount_inr: float = 0.0
    discount_usd: float = 0.0


@router.post("/old-student-check", response_model=OldStudentCheckResponse)
def old_student_check(
    payload: OldStudentCheckRequest,
    db: Session = Depends(get_db),
) -> OldStudentCheckResponse:
    return check_old_student_discount(db, payload.email, payload.subscription)


@router.post("/check-identity", response_model=RegistrationIdentityCheckResponse)
def registration_check_identity(
    payload: RegistrationIdentityCheckRequest,
    db: Session = Depends(get_db),
) -> RegistrationIdentityCheckResponse:
    """Step-1 guard: block duplicate email or mobile before continuing registration."""
    return RegistrationIdentityCheckResponse(**check_registration_identity(
        db, payload.email, payload.contact_number
    ))


@router.post("/payable-amount", response_model=PayableAmountResponse)
def payable_amount(payload: PayableAmountRequest, db: Session = Depends(get_db)) -> PayableAmountResponse:
    return get_payable_amount(db, payload)


@router.post("/init", response_model=RegistrationInitResponse)
def registration_init(
    payload: RegistrationInitRequest,
    db: Session = Depends(get_db),
) -> RegistrationInitResponse:
    return initialize_registration(db, payload)


@router.post("/payment/order", response_model=PaymentOrderResponse)
def payment_order(payload: PaymentOrderRequest, db: Session = Depends(get_db)) -> PaymentOrderResponse:
    return create_payment_order(db, payload.request_id)


@router.post("/extension/init", response_model=ExtensionInitResponse)
def extension_init(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ExtensionInitResponse:
    result = init_extension_payment(db, current_user)
    return ExtensionInitResponse(
        request_id=result["request_id"],
        amount=float(result["amount"]),
        currency=str(result["currency"]),
        extension_months=int(result.get("extension_months") or 2),
    )


@router.post("/extension/confirm", response_model=ExtensionConfirmResponse)
def extension_confirm(
    payload: ExtensionConfirmRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ExtensionConfirmResponse:
    """After Razorpay checkout, capture payment and extend course access."""
    result = confirm_extension_payment(
        db,
        current_user,
        request_id=payload.request_id,
        order_id=payload.order_id,
        payment_id=payload.payment_id,
        signature=payload.signature,
        raw_payload=payload.raw_payload,
    )
    return ExtensionConfirmResponse(**result)


@router.post("/payment/callback", response_model=PaymentFinalizeResponse)
def payment_callback(
    payload: PaymentFinalizeRequest,
    db: Session = Depends(get_db),
) -> PaymentFinalizeResponse:
    txn = db.query(RegistrationPaymentTxn).filter(RegistrationPaymentTxn.request_id == payload.request_id).first()
    is_extension = bool(txn and (txn.gateway or "").strip().lower() == "extension")
    return finalize_payment(
        db=db,
        request_id=payload.request_id,
        order_id=payload.order_id,
        payment_id=payload.payment_id,
        signature=payload.signature,
        raw_payload=payload.raw_payload,
        source="callback",
        verify_signature=not is_extension,
    )


@router.post("/{registration_id}/confirm")
def registration_confirm(
    registration_id: int,
    db: Session = Depends(get_db),
) -> dict:
    """Finalize payment if needed and send registration thank-you email (idempotent).

    Thank-you mail is sent only when payment_status is Credit and SMTP is configured on the API server.
    """
    return confirm_registration_after_payment(db, registration_id)


@router.post("/payment/webhook", response_model=None)
async def payment_webhook(
    request: Request,
    db: Session = Depends(get_db),
):
    body = await request.body()
    webhook_sig = request.headers.get("X-Razorpay-Signature", "")
    if not _verify_webhook_signature(body, webhook_sig):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")
    try:
        payload = json.loads(body.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="Invalid JSON webhook body") from exc
    return process_razorpay_webhook(db, payload)


@router.get("/{registration_id}/status", response_model=RegistrationStatusResponse)
def registration_status(registration_id: int, db: Session = Depends(get_db)) -> RegistrationStatusResponse:
    user = db.query(User).filter(User.id == registration_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Registration not found")
    txn = (
        db.query(RegistrationPaymentTxn)
        .filter(RegistrationPaymentTxn.user_id == user.id)
        .order_by(RegistrationPaymentTxn.id.desc())
        .first()
    )
    return RegistrationStatusResponse(
        registration_id=user.id,
        request_id=(txn.request_id if txn else ""),
        payment_status=(user.payment_status or "Pending"),
        approve=(user.approve or "0"),
        email=user.email,
        subscription=(user.subscription or ""),
    )


@router.get("/testimonials")
def list_public_testimonials(db: Session = Depends(get_db)) -> list[dict]:
    """Public list of active testimonials for the homepage."""
    rows = (
        db.query(Testimonial)
        .filter(Testimonial.status == "1")
        .order_by(Testimonial.display_order.asc(), Testimonial.id.desc())
        .all()
    )
    return [
        {
            "id": t.id,
            "text": t.text or "",
            "display_order": t.display_order if t.display_order is not None else 0,
        }
        for t in rows
    ]


@router.post("/upload-document")
def upload_document(file: UploadFile = File(...)) -> dict:
    from app.core.config import get_settings

    from app.services.s3_storage import public_registration_document_url

    filename = save_registration_document(file)
    settings = get_settings()
    view_url = public_registration_document_url(filename, settings) or ""
    return {"filename": filename, "view_url": view_url}


@router.post("/{registration_id}/upload-certificate")
def upload_registration_certificate(
    registration_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> dict:
    user = db.query(User).filter(User.id == registration_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Registration not found")
    filename = save_registration_document(file)
    user.document_file_2 = filename
    db.add(user)
    db.commit()
    return {"status": "ok", "filename": filename}
