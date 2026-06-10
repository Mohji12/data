from __future__ import annotations
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from mangum import Mangum
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db import engine, get_db
from app.models import (
    EmailTemplateMaster,
    EventPaymentTxn,
    EventRegistration,
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
from app.routers.whatsapp_webhook import router as whatsapp_webhook_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    if settings.auto_create_registration_txn_table:
        RegistrationPaymentTxn.__table__.create(bind=engine, checkfirst=True)
        EmailTemplateMaster.__table__.create(bind=engine, checkfirst=True)
    if settings.auto_create_event_tables:
        EventRegistration.__table__.create(bind=engine, checkfirst=True)
        EventPaymentTxn.__table__.create(bind=engine, checkfirst=True)
    if settings.auto_create_whatsapp_webhook_table:
        WhatsAppWebhookEvent.__table__.create(bind=engine, checkfirst=True)
    yield


app = FastAPI(title="Mock Test Backend", lifespan=lifespan)

_settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=_settings.cors_origins,
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
app.include_router(whatsapp_webhook_router)

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


@app.get("/")
def root() -> dict:
    return {"message": "Welcome to Critical Care Classes Mock Test Backend"}


@app.get("/health/db")
def health_db(db: Session = Depends(get_db)) -> dict:
    db.execute(text("SELECT 1"))
    return {"status": "ok"}


handler = Mangum(app)
# Auto-reload trigger (domain update)