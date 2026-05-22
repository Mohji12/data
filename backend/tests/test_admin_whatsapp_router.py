from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings
from app.models import Admin, Audit, Base
from app.routers import admin_whatsapp as admin_whatsapp_router


def _make_db():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine, tables=[Admin.__table__, Audit.__table__])
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    return SessionLocal()


def test_bulk_send_requires_configuration(monkeypatch):
    get_settings.cache_clear()
    monkeypatch.delenv("WHATSAPP_API_KEY", raising=False)
    monkeypatch.delenv("WHATSAPP_PHONE_NUMBER_ID", raising=False)
    get_settings.cache_clear()

    db = _make_db()
    admin = Admin(username="tech", password="x", user_type="techadmin")
    db.add(admin)
    db.commit()
    db.refresh(admin)

    payload = admin_whatsapp_router.WhatsAppBulkSendPayload(
        message="hello",
        recipients=[admin_whatsapp_router.BulkRecipient(phone="+919876543210", user_id=1)],
    )
    try:
        admin_whatsapp_router.bulk_send_whatsapp(payload=payload, db=db, current_admin=admin)
        assert False, "Expected configuration error"
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 503


def test_bulk_send_returns_summary_and_audits(monkeypatch):
    monkeypatch.setenv("WHATSAPP_API_KEY", "token")
    monkeypatch.setenv("WHATSAPP_PHONE_NUMBER_ID", "123")
    get_settings.cache_clear()

    db = _make_db()
    admin = Admin(username="tech2", password="x", user_type="techadmin")
    db.add(admin)
    db.commit()
    db.refresh(admin)

    def fake_bulk_send(phones, message):
        return {
            "total": 2,
            "sent": 1,
            "failed": 1,
            "results": [
                {"phone": phones[0], "success": True, "provider_message_id": "wamid.1", "error": None, "status_code": 200},
                {"phone": phones[1], "success": False, "provider_message_id": None, "error": "invalid", "status_code": 400},
            ],
        }

    monkeypatch.setattr(admin_whatsapp_router, "send_bulk_text", fake_bulk_send)

    payload = admin_whatsapp_router.WhatsAppBulkSendPayload(
        message="hello",
        recipients=[
            admin_whatsapp_router.BulkRecipient(phone="+919876543210", user_id=11),
            admin_whatsapp_router.BulkRecipient(phone="+919876543211", user_id=12),
        ],
    )
    out = admin_whatsapp_router.bulk_send_whatsapp(payload=payload, db=db, current_admin=admin)

    assert out["total"] == 2
    assert out["sent"] == 1
    assert out["failed"] == 1

    rows = db.query(Audit).all()
    assert len(rows) == 2
