"""Public ZeptoMail bounce / complaint / delivered webhook."""

from __future__ import annotations

import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.services.mail_zepto_webhook import parse_webhook_body, process_zepto_webhook, verify_zepto_request

logger = logging.getLogger(__name__)

router = APIRouter(tags=["mail-zepto-webhook"])


@router.post("/mail/zepto/webhook")
async def zepto_mail_webhook(request: Request, db: Session = Depends(get_db)):
    body = await request.body()
    header_map = {k: v for k, v in request.headers.items()}
    if not verify_zepto_request(body, header_map):
        logger.warning("ZeptoMail webhook rejected: authentication failed")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")
    try:
        payload = parse_webhook_body(body)
    except (ValueError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid JSON webhook body") from exc
    try:
        return process_zepto_webhook(db, payload)
    except Exception:
        logger.exception("ZeptoMail webhook processing failed")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Webhook processing failed")
