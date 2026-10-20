"""ZeptoMail webhook auth, idempotency, and bounce suppression."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
from urllib.parse import quote

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import get_settings
from app.db import get_db
from app.models import MailCampaign, MailCampaignRecipient, MailCampaignTemplate, MailProviderEvent, MailSuppression
from app.routers.mail_zepto_webhook import router
from app.services.mail_zepto_webhook import process_zepto_webhook


def _session():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    MailCampaignTemplate.__table__.create(bind=engine)
    MailCampaign.__table__.create(bind=engine)
    MailCampaignRecipient.__table__.create(bind=engine)
    MailSuppression.__table__.create(bind=engine)
    MailProviderEvent.__table__.create(bind=engine)
    return sessionmaker(bind=engine, autocommit=False, autoflush=False)()


def _client(db, monkeypatch):
    monkeypatch.setenv("ZEPTOMAIL_WEBHOOK_AUTHORIZATION_VALUE", "secret-token")
    monkeypatch.setenv("ZEPTOMAIL_WEBHOOK_AUTH_KEY", "")
    get_settings.cache_clear()
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app)


def _bounce_payload(event_name="hardbounce", email="bad@ex.com", webhook_id="wh-1", extra=None):
    body = {
        "event_name": [event_name],
        "event_message": [
            {
                "email_info": {
                    "client_reference": extra.get("client_reference") if extra else None,
                    "to": [{"email_address": {"address": email, "name": "X"}}],
                    "processed_time": "2026-10-20T12:00:00Z",
                    "object": "email",
                },
                "event_data": [
                    {
                        "details": [
                            {
                                "reason": "bad-mailbox",
                                "bounced_recipient": email,
                                "time": "2026-10-20T12:00:01Z",
                                "diagnostic_message": "550 user unknown",
                            }
                        ],
                        "object": event_name,
                    }
                ],
                "request_id": "req-1",
            }
        ],
        "webhook_request_id": webhook_id,
    }
    if extra:
        body.update(extra)
    return body


def test_webhook_rejects_without_auth(monkeypatch):
    db = _session()
    monkeypatch.setenv("ZEPTOMAIL_WEBHOOK_AUTHORIZATION_VALUE", "")
    monkeypatch.setenv("ZEPTOMAIL_WEBHOOK_AUTH_KEY", "")
    get_settings.cache_clear()
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_db] = lambda: db
    client = TestClient(app)
    res = client.post("/mail/zepto/webhook", json=_bounce_payload())
    assert res.status_code == 401
    db.close()
    get_settings.cache_clear()


def test_hard_bounce_suppresses(monkeypatch):
    db = _session()
    client = _client(db, monkeypatch)
    res = client.post(
        "/mail/zepto/webhook",
        json=_bounce_payload(),
        headers={"Authorization": "secret-token"},
    )
    assert res.status_code == 200
    assert res.json()["processed"] == 1
    row = db.query(MailSuppression).filter(MailSuppression.email == "bad@ex.com").first()
    assert row is not None
    assert row.reason == "hard_bounce"
    db.close()
    get_settings.cache_clear()


def test_duplicate_webhook_is_idempotent(monkeypatch):
    db = _session()
    payload = _bounce_payload(webhook_id="dup-1")
    first = process_zepto_webhook(db, payload)
    second = process_zepto_webhook(db, payload)
    assert first["processed"] == 1
    assert second["skipped"] == 1
    assert db.query(MailSuppression).count() == 1
    db.close()


def test_soft_bounce_suppresses_after_three():
    db = _session()
    for i in range(3):
        process_zepto_webhook(
            db,
            _bounce_payload(event_name="softbounce", email="soft@ex.com", webhook_id=f"s-{i}"),
        )
    row = db.query(MailSuppression).filter(MailSuppression.email == "soft@ex.com").first()
    assert row is not None
    assert row.reason == "soft_bounce"
    assert row.bounce_count >= 3
    db.close()


def test_complaint_and_missing_campaign():
    db = _session()
    payload = {
        "event_name": ["feedback loop"],
        "event_message": [
            {
                "email_info": {"to": [{"email_address": {"address": "spam@ex.com"}}], "object": "fbl_complaint"},
                "event_data": [{"details": [{"fblFrom": "spam@ex.com"}], "object": "fbl_complaint"}],
                "request_id": "r-c",
            }
        ],
        "webhook_request_id": "wh-c",
    }
    out = process_zepto_webhook(db, payload)
    assert out["processed"] == 1
    row = db.query(MailSuppression).filter(MailSuppression.email == "spam@ex.com").first()
    assert row.reason == "complaint"
    db.close()


def test_hmac_signature_accepts(monkeypatch):
    db = _session()
    key = "agent-auth-key"
    monkeypatch.setenv("ZEPTOMAIL_WEBHOOK_AUTH_KEY", key)
    monkeypatch.setenv("ZEPTOMAIL_WEBHOOK_AUTHORIZATION_VALUE", "")
    get_settings.cache_clear()
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_db] = lambda: db
    client = TestClient(app)
    payload = _bounce_payload(email="sig@ex.com", webhook_id="wh-sig")
    raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    digest = hmac.new(key.encode("utf-8"), raw, hashlib.sha256).digest()
    sig = quote(base64.b64encode(digest).decode("ascii"), safe="")
    import time

    ts = str(int(time.time() * 1000))
    header = f"ts={ts}; s={sig}; s-algorithm=HmacSHA256"
    res = client.post("/mail/zepto/webhook", content=raw, headers={"Content-Type": "application/json", "producer-signature": header})
    assert res.status_code == 200
    db.close()
    get_settings.cache_clear()


def test_delivered_does_not_overwrite_bounce():
    db = _session()
    tpl = MailCampaignTemplate(name="t", subject="s")
    db.add(tpl)
    db.commit()
    camp = MailCampaign(name="c", template_id=tpl.id, audience_type="list", audience_json="{}", status="sent")
    db.add(camp)
    db.commit()
    rec = MailCampaignRecipient(
        campaign_id=camp.id, email="d@ex.com", status="accepted", tracking_token="td", delivery_status="hard_bounce"
    )
    db.add(rec)
    db.commit()
    process_zepto_webhook(
        db,
        {
            "event_name": ["delivered"],
            "event_message": [
                {
                    "email_info": {"client_reference": f"{camp.id}:{rec.id}", "to": [{"email_address": {"address": "d@ex.com"}}]},
                    "event_data": [{"details": [{}], "object": "delivered"}],
                    "request_id": "del-1",
                }
            ],
            "webhook_request_id": "wh-del",
        },
    )
    db.refresh(rec)
    assert rec.delivery_status == "hard_bounce"
    db.close()
