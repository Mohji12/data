from __future__ import annotations

import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from app.db import get_db
from app.services.whatsapp_webhook import (
    process_whatsapp_webhook,
    verify_meta_challenge,
    verify_meta_signature,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhook", tags=["whatsapp-webhook"])


@router.get("")
def whatsapp_webhook_verify(
    hub_mode: str = Query(alias="hub.mode"),
    hub_verify_token: str = Query(alias="hub.verify_token"),
    hub_challenge: str = Query(alias="hub.challenge"),
) -> PlainTextResponse:
    """
    Meta WhatsApp Cloud API subscription verification.
    Returns hub.challenge as plain text when hub.verify_token matches WHATSAPP_VERIFY_TOKEN.
    """
    challenge = verify_meta_challenge(
        mode=hub_mode,
        verify_token=hub_verify_token,
        challenge=hub_challenge,
    )
    if challenge is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Verification failed")
    logger.info("WhatsApp webhook verified (Meta challenge accepted)")
    return PlainTextResponse(content=challenge, status_code=200)


@router.post("")
async def whatsapp_webhook_receive(
    request: Request,
    db: Session = Depends(get_db),
) -> dict:
    """Receive inbound WhatsApp messages, delivery/read statuses, and errors from Meta."""
    body = await request.body()
    signature = request.headers.get("X-Hub-Signature-256", "")
    if not verify_meta_signature(body, signature):
        logger.warning("WhatsApp webhook rejected: invalid X-Hub-Signature-256")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid webhook signature")

    try:
        payload = json.loads(body.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid JSON webhook body") from exc

    if not isinstance(payload, dict):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Webhook body must be a JSON object")

    return process_whatsapp_webhook(db, payload)
