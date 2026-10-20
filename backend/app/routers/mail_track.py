"""Public click-through and unsubscribe endpoints for campaign mail."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import MailCampaignRecipient, MailClickEvent, MailSuppression
from app.services.mail_campaign_audience import normalize_email
from app.services.mail_campaign_render import dest_url_is_allowed

router = APIRouter(tags=["mail-track"])


@router.get("/mail/t/{token}")
def mail_click_track(
    token: str,
    request: Request,
    u: str = Query(..., min_length=8),
    db: Session = Depends(get_db),
):
    if not dest_url_is_allowed(u):
        return HTMLResponse("Invalid link.", status_code=400)
    rec = db.query(MailCampaignRecipient).filter(MailCampaignRecipient.tracking_token == token).first()
    if rec:
        db.add(
            MailClickEvent(
                recipient_id=rec.id,
                campaign_id=rec.campaign_id,
                dest_url=u[:4000],
                ip=(request.client.host if request.client else None),
                user_agent=(request.headers.get("user-agent") or "")[:500],
            )
        )
        db.commit()
    return RedirectResponse(url=u, status_code=302)


@router.get("/mail/u/{token}")
def mail_unsubscribe(token: str, db: Session = Depends(get_db)):
    rec = db.query(MailCampaignRecipient).filter(MailCampaignRecipient.tracking_token == token).first()
    if rec and rec.email:
        email = normalize_email(rec.email)
        existing = db.query(MailSuppression).filter(MailSuppression.email == email).first()
        if not existing:
            db.add(MailSuppression(email=email, reason="unsubscribe"))
            db.commit()
    return HTMLResponse(
        "<html><body style='font-family:sans-serif;padding:40px;'>"
        "<h1>Unsubscribed</h1><p>You will no longer receive campaign emails from this list.</p>"
        "</body></html>"
    )
