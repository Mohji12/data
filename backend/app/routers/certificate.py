from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import User
from app.security import get_current_user
from app.services.access import (
    bool_option,
    can_access_certificate,
    format_certificate_date,
    get_certificate_batch_settings,
    resolve_certificate_completion_date,
)
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
    completion_date = resolve_certificate_completion_date(db, current_user)
    completion_text = format_certificate_date(completion_date)
    # Center line: course completion date (covers template "Third Batch..." text).
    # Bottom-right issue date uses the same completion date when show_date is on.
    date_text = completion_text if show_date and completion_text else ""

    pdf_bytes = build_certificate_pdf(
        full_name=full_name,
        subscription=current_user.subscription,
        # Do not print static batch labels like "Third Batch - July to December 2021".
        certificate_batch_label=None,
        certificate_date_text=date_text,
        certificate_course_line=batch_settings.get("course_line") or None,
        certificate_program_line=batch_settings.get("program_line") or None,
        certificate_show_date=show_date and bool(date_text),
        certificate_name_size=batch_settings.get("name_size") or None,
        certificate_completion_date_text=completion_text or None,
    )
    safe_name = (full_name or "Learner").replace(" ", "_")
    filename = f"{safe_name}_certificate.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
