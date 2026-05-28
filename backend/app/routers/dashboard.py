from __future__ import annotations
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import User, UserPackagePayment
from app.schemas import (
    DashboardPaymentItem,
    DashboardProfile,
    DashboardProfileUpdateRequest,
    DashboardSummary,
    FeatureAccess,
    SubscriptionPeriodInfo,
)
from app.security import get_current_user
from app.services.access import (
    bool_option,
    can_access_mock_test,
    can_access_video_library,
    ensure_subscription_entitlement,
    get_extension_offer,
    get_certificate_batch_settings,
    get_option_value,
    get_subscription_period_for_profile,
    subscription_allowed,
)

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


def _build_dashboard_profile(db: Session, user: User) -> DashboardProfile:
    period_raw = get_subscription_period_for_profile(db, user)
    period = SubscriptionPeriodInfo(**period_raw) if period_raw else None
    return DashboardProfile(
        id=user.id,
        registration_type=user.registration_type,
        subscription=user.subscription,
        title=user.title,
        name=user.name,
        email=user.email,
        contact_number=user.contact_number,
        hospital=user.hospital,
        qualification=user.qualification,
        speciality=user.speciality,
        country_id=user.country_id,
        state=user.state,
        city=user.city,
        pin_code=user.pin_code,
        currency_name=user.currency_name,
        payment_status=user.payment_status,
        approve=user.approve,
        subscription_period=period,
    )


@router.get("/summary", response_model=DashboardSummary)
def dashboard_summary(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DashboardSummary:
    can_video, video_reason = can_access_video_library(db, current_user)

    mock_enabled, mock_reason = can_access_mock_test(db, current_user)

    certificate_enabled = False
    certificate_reason = None
    if not bool_option(get_option_value(db, "display_download_certificate")):
        certificate_reason = "Certificate download is disabled by admin."
    else:
        cert_allowed_subscriptions = get_option_value(db, "access_download_certificate")
        if cert_allowed_subscriptions and not subscription_allowed(
            cert_allowed_subscriptions, current_user.subscription
        ):
            certificate_reason = "Your subscription does not include certificate download."
        elif (get_certificate_batch_settings(db, current_user.subscription).get("enabled") or "").strip() != "1":
            certificate_reason = "Certificate download is disabled for your batch."
        elif (current_user.payment_status or "").strip().lower() != "credit":
            certificate_reason = "Payment not completed."
        elif (current_user.approve or "").strip() != "1":
            certificate_reason = "Account not approved."
        else:
            ent_ok, ent_reason = ensure_subscription_entitlement(db, current_user)
            if not ent_ok:
                certificate_reason = ent_reason
            else:
                certificate_enabled = True

    return DashboardSummary(
        user_id=current_user.id,
        name=current_user.name,
        email=current_user.email,
        subscription=current_user.subscription,
        video=FeatureAccess(enabled=can_video, reason=video_reason),
        mock_test=FeatureAccess(enabled=mock_enabled, reason=mock_reason),
        certificate=FeatureAccess(enabled=certificate_enabled, reason=certificate_reason),
        extension=get_extension_offer(db, current_user),
    )


@router.get("/profile", response_model=DashboardProfile)
def dashboard_profile(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DashboardProfile:
    return _build_dashboard_profile(db, current_user)


@router.get("/extension-offer")
def dashboard_extension_offer(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    return get_extension_offer(db, current_user)


@router.put("/profile", response_model=DashboardProfile)
def update_dashboard_profile(
    payload: DashboardProfileUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DashboardProfile:
    for field in (
        "title",
        "name",
        "contact_number",
        "hospital",
        "qualification",
        "speciality",
        "country_id",
        "state",
        "city",
        "pin_code",
    ):
        value = getattr(payload, field)
        if isinstance(value, str):
            value = value.strip()
        setattr(current_user, field, value)

    db.add(current_user)
    db.commit()
    db.refresh(current_user)

    return _build_dashboard_profile(db, current_user)


@router.get("/payments", response_model=list[DashboardPaymentItem])
def dashboard_payments(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[DashboardPaymentItem]:
    rows = (
        db.query(UserPackagePayment)
        .filter(UserPackagePayment.user_id == current_user.id)
        .order_by(UserPackagePayment.id.desc())
        .all()
    )

    return [
        DashboardPaymentItem(
            id=row.id,
            subscription=row.subscription,
            package_type=row.package_type,
            currency_name=row.currency_name,
            payment_status=row.payment_status,
            payment_type=row.payment_type,
            payment_date=row.payment_date,
        )
        for row in rows
    ]
