from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import User
from app.security import get_current_user
from app.services.access import bool_option, can_access_certificate, get_certificate_batch_settings
from app.services.certificates import build_certificate_pdf

router = APIRouter(prefix="/certificate", tags=["certificate"])


@router.get("/download.pdf")
def download_certificate(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    ok, reason = can_access_certificate(db, current_user)
    if not ok:
        raise HTTPException(status_code=403, detail=reason or "Certificate access denied")

    full_name = f"{(current_user.title or '').strip()} {(current_user.name or '').strip()}".strip()
    if not full_name:
        full_name = current_user.email
    batch_settings = get_certificate_batch_settings(db, current_user.subscription)
    show_date = bool_option(batch_settings.get("show_date"))
    fixed_date = (batch_settings.get("fixed_date") or "").strip()
    date_text = fixed_date or (datetime.utcnow().date().isoformat() if show_date else "")

    pdf_bytes = build_certificate_pdf(
        full_name=full_name,
        subscription=current_user.subscription,
        certificate_batch_label=batch_settings.get("batch_label") or current_user.subscription,
        certificate_date_text=date_text,
        certificate_course_line=batch_settings.get("course_line") or None,
        certificate_program_line=batch_settings.get("program_line") or None,
        certificate_show_date=show_date,
        certificate_name_size=batch_settings.get("name_size") or None,
    )
    safe_name = (full_name or "Learner").replace(" ", "_")
    filename = f"{safe_name}_certificate.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
