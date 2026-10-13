"""RQ worker entrypoints for WhatsApp bulk send."""

from __future__ import annotations

from typing import Any


def run_whatsapp_bulk_job(admin_id: int, payload_dict: dict[str, Any]) -> dict[str, Any]:
    from app.db import SessionLocal
    from app.models import Admin
    from app.services.whatsapp_bulk_dispatch import (
        WhatsAppBulkSendPayload,
        execute_whatsapp_bulk_send,
    )

    db = SessionLocal()
    try:
        admin = db.query(Admin).filter(Admin.id == int(admin_id)).first()
        if not admin:
            raise RuntimeError(f"Admin {admin_id} not found")
        payload = WhatsAppBulkSendPayload.model_validate(payload_dict)
        return execute_whatsapp_bulk_send(db, admin, payload)
    finally:
        db.close()
