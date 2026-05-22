from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import User
from app.security import get_current_user
from app.services.access import (
    bool_option,
    ensure_subscription_entitlement,
    get_certificate_batch_settings,
    get_option_value,
    subscription_allowed,
)
from app.services.certificates import build_certificate_pdf

router = APIRouter(prefix="/certificate", tags=["certificate"])


def _can_download_certificate(db: Session, user: User) -> tuple[bool, str | None]:
    if not bool_option(get_option_value(db, "display_download_certificate")):
        return False, "Certificate download is disabled by admin."
    allowed = get_option_value(db, "access_download_certificate")
    if allowed and not subscription_allowed(allowed, user.subscription):
        return False, "Your subscription does not include certificate download."
    batch_settings = get_certificate_batch_settings(db, user.subscription)
    if (batch_settings.get("enabled") or "").strip() != "1":
        return False, "Certificate download is disabled for your batch."
    if (user.payment_status or "").strip().lower() != "credit":
        return False, "Payment not completed."
    if (user.approve or "").strip() != "1":
        return False, "Account not approved."
    ent_ok, ent_reason = ensure_subscription_entitlement(db, user)
    if not ent_ok:
        return False, ent_reason
    return True, None


@router.get("/download.pdf")
def download_certificate(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    ok, reason = _can_download_certificate(db, current_user)
    if not ok:
        raise HTTPException(status_code=403, detail=reason or "Certificate access denied")

    full_name = f"{(current_user.title or '').strip()} {(current_user.name or '').strip()}".strip()
    if not full_name:
        full_name = current_user.email
    batch_settings = get_certificate_batch_settings(db, current_user.subscription)
    date_text = (batch_settings.get("fixed_date") or "").strip() or datetime.utcnow().date().isoformat()
    pdf_bytes = build_certificate_pdf(
        full_name=full_name,
        subscription=current_user.subscription,
        certificate_batch_label=batch_settings.get("batch_label") or current_user.subscription,
        certificate_date_text=date_text,
    )
    safe_name = (full_name or "Learner").replace(" ", "_")
    filename = f"{safe_name}_certificate.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )

