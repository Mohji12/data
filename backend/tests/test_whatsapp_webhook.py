from __future__ import annotations

import hashlib
import hmac
import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import get_settings
from app.db import get_db
from app.models import Base, User, WhatsAppWebhookEvent
from app.routers.whatsapp_webhook import router as whatsapp_webhook_router


def _make_client():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine, tables=[User.__table__, WhatsAppWebhookEvent.__table__])
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)

    app = FastAPI()
    app.include_router(whatsapp_webhook_router)

    def override_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_db
    return TestClient(app), SessionLocal


def _sign(body: bytes, secret: str) -> str:
    digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


@pytest.fixture(autouse=True)
def clear_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_get_webhook_verification_success(monkeypatch):
    monkeypatch.setenv("WHATSAPP_VERIFY_TOKEN", "my-verify-token")
    client, _ = _make_client()
    res = client.get(
        "/webhook",
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": "my-verify-token",
            "hub.challenge": "1234567890",
        },
    )
    assert res.status_code == 200
    assert res.text == "1234567890"
    assert res.headers["content-type"].startswith("text/plain")


def test_get_webhook_verification_rejects_bad_token(monkeypatch):
    monkeypatch.setenv("WHATSAPP_VERIFY_TOKEN", "expected")
    client, _ = _make_client()
    res = client.get(
        "/webhook",
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": "wrong",
            "hub.challenge": "1234567890",
        },
    )
    assert res.status_code == 403


def test_post_webhook_stores_inbound_message(monkeypatch):
    monkeypatch.setenv("WHATSAPP_APP_SECRET", "app-secret")
    client, SessionLocal = _make_client()
    db = SessionLocal()
    db.add(User(id=1, email="a@example.com", password="x", contact_number="+919876543210"))
    db.commit()
    db.close()

    payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "WABA_ID",
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "metadata": {"display_phone_number": "15550001111"},
                            "messages": [
                                {
                                    "from": "919876543210",
                                    "id": "wamid.inbound1",
                                    "timestamp": "1710000000",
                                    "type": "text",
                                    "text": {"body": "Hello"},
                                }
                            ],
                        },
                    }
                ],
            }
        ],
    }
    body = json.dumps(payload).encode("utf-8")
    res = client.post(
        "/webhook",
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-Hub-Signature-256": _sign(body, "app-secret"),
        },
    )
    assert res.status_code == 200
    assert res.json()["processed"] == 1

    db = SessionLocal()
    row = db.query(WhatsAppWebhookEvent).first()
    assert row is not None
    assert row.wa_message_id == "wamid.inbound1"
    assert row.user_id == 1
    db.close()


def test_post_webhook_rejects_invalid_signature(monkeypatch):
    monkeypatch.setenv("WHATSAPP_APP_SECRET", "app-secret")
    client, _ = _make_client()
    body = b'{"object":"whatsapp_business_account","entry":[]}'
    res = client.post(
        "/webhook",
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-Hub-Signature-256": "sha256=deadbeef",
        },
    )
    assert res.status_code == 401
