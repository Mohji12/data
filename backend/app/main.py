from __future__ import annotations

import logging
import threading
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from mangum import Mangum
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.redis_client import redis_health
from app.db import engine, get_db
from app.models import (
    EmailTemplateMaster,
    EventPaymentTxn,
    EventRegistration,
    MailCampaign,
    MailCampaignRecipient,
    MailCampaignTemplate,
    MailClickEvent,
    MailProviderEvent,
    MailSuppression,
    RegistrationPaymentTxn,
    WhatsAppWebhookEvent,
)
from app.routers.dashboard import router as dashboard_router
from app.routers.exams import router as exams_router
from app.routers.auth import router as auth_router
from app.routers.registration import router as registration_router
from app.routers.videos import router as videos_router
from app.routers.admin_auth import router as admin_auth_router
from app.routers.admin_users import router as admin_users_router
from app.routers.admin_payments import router as admin_payments_router
from app.routers.admin_content import router as admin_content_router
from app.routers.admin_commerce import router as admin_commerce_router
from app.routers.admin_quiz import router as admin_quiz_router
from app.routers.admin_misc import router as admin_misc_router
from app.routers.admin_auditorium import router as admin_auditorium_router
from app.routers.admin_whatsapp import router as admin_whatsapp_router
from app.routers.certificate import router as certificate_router
from app.routers.events import router as events_router
from app.routers.admin_events import router as admin_events_router
from app.routers.admin_extension_requests import router as admin_extension_requests_router
from app.routers.whatsapp_webhook import router as whatsapp_webhook_router
from app.routers.admin_mail_campaigns import router as admin_mail_router
from app.routers.mail_track import router as mail_track_router
from app.routers.mail_zepto_webhook import router as mail_zepto_webhook_router


def _ensure_event_registration_fee_columns() -> None:
    """Add fee breakdown columns to existing event_registration tables."""
    columns = {
        "base_fee_inr": "DOUBLE DEFAULT 0",
        "gst_percent": "DOUBLE DEFAULT 18",
        "gst_amount_inr": "DOUBLE DEFAULT 0",
        "fee_label": "VARCHAR(64) DEFAULT NULL",
    }
    with engine.begin() as conn:
        existing = {
            row[0]
            for row in conn.execute(
                text(
                    "SELECT COLUMN_NAME FROM information_schema.COLUMNS "
                    "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'event_registration'"
                )
            )
        }
        for name, ddl in columns.items():
            if name not in existing:
                conn.execute(text(f"ALTER TABLE event_registration ADD COLUMN {name} {ddl}"))


def _table_columns(conn, table: str) -> set[str]:
    return {
        row[0]
        for row in conn.execute(
            text(
                "SELECT COLUMN_NAME FROM information_schema.COLUMNS "
                f"WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = '{table}'"
            )
        )
    }


def _ensure_columns(table: str, columns: dict[str, str]) -> None:
    with engine.begin() as conn:
        existing = _table_columns(conn, table)
        if not existing:
            return
        for name, ddl in columns.items():
            if name not in existing:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}"))


def _ensure_mail_campaign_throttle_columns() -> None:
    _ensure_columns(
        "mail_campaign",
        {
            "send_batch_size": "INT NOT NULL DEFAULT 100",
            "send_pause_seconds": "INT NOT NULL DEFAULT 300",
            "next_wave_at": "DATETIME DEFAULT NULL",
            "skip_previously_bounced": "TINYINT(1) NOT NULL DEFAULT 1",
            "audience_snapshot_json": "TEXT",
        },
    )
    _ensure_columns(
        "mail_campaign_recipient",
        {
            "delivery_status": "VARCHAR(32) DEFAULT NULL",
            "bounced_at": "DATETIME DEFAULT NULL",
        },
    )
    _ensure_columns(
        "mail_suppression",
        {
            "source": "VARCHAR(64) NOT NULL DEFAULT 'unsubscribe_link'",
            "diagnostic": "TEXT",
            "bounce_count": "INT NOT NULL DEFAULT 0",
            "last_event_at": "DATETIME DEFAULT NULL",
            "created_by_admin_id": "INT DEFAULT NULL",
            "updated_at": "DATETIME DEFAULT NULL",
        },
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    if settings.auto_create_registration_txn_table:
        RegistrationPaymentTxn.__table__.create(bind=engine, checkfirst=True)
        EmailTemplateMaster.__table__.create(bind=engine, checkfirst=True)
    if settings.auto_create_event_tables:
        EventRegistration.__table__.create(bind=engine, checkfirst=True)
        EventPaymentTxn.__table__.create(bind=engine, checkfirst=True)
        _ensure_event_registration_fee_columns()
    if settings.auto_create_whatsapp_webhook_table:
        WhatsAppWebhookEvent.__table__.create(bind=engine, checkfirst=True)
    MailCampaignTemplate.__table__.create(bind=engine, checkfirst=True)
    MailCampaign.__table__.create(bind=engine, checkfirst=True)
    MailCampaignRecipient.__table__.create(bind=engine, checkfirst=True)
    MailClickEvent.__table__.create(bind=engine, checkfirst=True)
    MailSuppression.__table__.create(bind=engine, checkfirst=True)
    MailProviderEvent.__table__.create(bind=engine, checkfirst=True)
    _ensure_mail_campaign_throttle_columns()
    try:
        from app.core.job_queue import enqueue_mail_poll

        enqueue_mail_poll(delay_seconds=20)
    except Exception:
        pass
    stop_mail_poll = threading.Event()

    def _mail_poll_loop() -> None:
        while True:
            try:
                from app.jobs.mail_campaign import poll_due_campaigns

                poll_due_campaigns(requeue=False)
            except Exception:
                logging.getLogger(__name__).warning("mail poll loop failed", exc_info=True)
            if stop_mail_poll.wait(20):
                break

    threading.Thread(target=_mail_poll_loop, name="mail-campaign-poll", daemon=True).start()
    yield
    stop_mail_poll.set()


app = FastAPI(title="Mock Test Backend", lifespan=lifespan)

_settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=_settings.cors_origins,
    # Local Vite + Amplify/Vercel preview apps (frontend is cross-origin to the API host)
    allow_origin_regex=(
        r"https?://(localhost|127\.0\.0\.1)(:\d+)?"
        r"|https://.*\.amplifyapp\.com"
        r"|https://.*\.vercel\.app"
    ),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(exams_router)
app.include_router(auth_router)
app.include_router(dashboard_router)
app.include_router(videos_router)
app.include_router(registration_router)
app.include_router(admin_auth_router)
app.include_router(admin_users_router)
app.include_router(admin_payments_router)
app.include_router(admin_content_router)
app.include_router(admin_commerce_router)
app.include_router(admin_quiz_router)
app.include_router(admin_misc_router)
app.include_router(admin_auditorium_router)
app.include_router(admin_whatsapp_router)
app.include_router(certificate_router)
app.include_router(events_router)
app.include_router(admin_events_router)
app.include_router(admin_extension_requests_router)
app.include_router(whatsapp_webhook_router)
app.include_router(admin_mail_router)
app.include_router(mail_track_router)
app.include_router(mail_zepto_webhook_router)

# Same URL shape as PHP: files saved under uploads/registration (see uploads.save_registration_document).
registration_uploads = Path(__file__).resolve().parent.parent / "uploads" / "registration"
registration_uploads.mkdir(parents=True, exist_ok=True)
app.mount(
    "/upload/user/document_file",
    StaticFiles(directory=str(registration_uploads)),
    name="user_document_files",
)

brochure_uploads = Path(__file__).resolve().parent.parent / "uploads" / "brochures"
brochure_uploads.mkdir(parents=True, exist_ok=True)
app.mount(
    "/upload/brochures",
    StaticFiles(directory=str(brochure_uploads)),
    name="batch_brochures",
)

batch_video_uploads = Path(__file__).resolve().parent.parent / "uploads" / "batch_videos"
batch_video_uploads.mkdir(parents=True, exist_ok=True)
app.mount(
    "/upload/batch_videos",
    StaticFiles(directory=str(batch_video_uploads)),
    name="batch_videos",
)

video_uploads = Path(__file__).resolve().parent.parent / "uploads" / "video" / "image"
video_uploads.mkdir(parents=True, exist_ok=True)
app.mount(
    "/upload/video/image",
    StaticFiles(directory=str(video_uploads)),
    name="video_images",
)

quiz_uploads = Path(__file__).resolve().parent.parent / "uploads" / "questions" / "image"
quiz_uploads.mkdir(parents=True, exist_ok=True)
app.mount(
    "/upload/quiz/questions",
    StaticFiles(directory=str(quiz_uploads)),
    name="quiz_images",
)

whatsapp_uploads = Path(__file__).resolve().parent.parent / "uploads" / "whatsapp"
whatsapp_uploads.mkdir(parents=True, exist_ok=True)
app.mount(
    "/upload/whatsapp",
    StaticFiles(directory=str(whatsapp_uploads)),
    name="whatsapp_images",
)

campaign_uploads = Path(__file__).resolve().parent.parent / "uploads" / "campaigns"
campaign_uploads.mkdir(parents=True, exist_ok=True)
app.mount(
    "/upload/campaigns",
    StaticFiles(directory=str(campaign_uploads)),
    name="campaign_images",
)


@app.get("/")
def root() -> dict:
    return {"message": "Welcome to Critical Care Classes Mock Test Backend"}


@app.get("/health")
def health(db: Session = Depends(get_db)) -> dict:
    db_status = "ok"
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        db_status = "down"
    return {"api": "ok", "db": db_status, "redis": redis_health()}


@app.get("/health/db")
def health_db(db: Session = Depends(get_db)) -> dict:
    db.execute(text("SELECT 1"))
    return {"status": "ok"}


handler = Mangum(app)
# Auto-reload trigger (domain update)