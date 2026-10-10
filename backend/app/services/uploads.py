from __future__ import annotations

import os
import uuid
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

from fastapi import HTTPException, UploadFile

from app.core.config import get_settings
from app.services.s3_storage import s3_uploads_enabled, upload_user_document

ALLOWED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png", ".webp"}
MAX_FILE_BYTES = 5 * 1024 * 1024


def save_registration_document(file: UploadFile) -> str:
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Unsupported document type")

    content = file.file.read()
    if len(content) > MAX_FILE_BYTES:
        raise HTTPException(status_code=400, detail="Document exceeds 5MB limit")

    settings = get_settings()
    if s3_uploads_enabled(settings):
        return upload_user_document(content, suffix, settings)

    uploads_dir = Path(__file__).resolve().parent.parent.parent / "uploads" / "registration"
    os.makedirs(uploads_dir, exist_ok=True)
    filename = f"{uuid.uuid4().hex}{suffix}"
    path = uploads_dir / filename
    path.write_bytes(content)
    return filename


MAX_VIDEO_BYTES = 200 * 1024 * 1024


def save_batch_brochure(file: UploadFile) -> str:
    suffix = Path(file.filename or "").suffix.lower()
    if suffix != ".pdf":
        raise HTTPException(status_code=400, detail="Only PDF brochure is allowed")

    content = file.file.read()
    if len(content) > MAX_FILE_BYTES:
        raise HTTPException(status_code=400, detail="Brochure exceeds 5MB limit")

    uploads_dir = Path(__file__).resolve().parent.parent.parent / "uploads" / "brochures"
    os.makedirs(uploads_dir, exist_ok=True)
    filename = f"{uuid.uuid4().hex}{suffix}"
    (uploads_dir / filename).write_bytes(content)
    return filename


def save_batch_video(file: UploadFile) -> str:
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in {".mp4", ".mov", ".avi", ".mkv"}:
        raise HTTPException(status_code=400, detail="Unsupported video format. Use MP4, MOV, AVI, or MKV.")

    # Note: For large videos, reading into memory might be risky. 
    # But for now, we follow the pattern of other upload functions.
    content = file.file.read()
    if len(content) > MAX_VIDEO_BYTES:
        raise HTTPException(status_code=400, detail="Video exceeds 200MB limit")

    uploads_dir = Path(__file__).resolve().parent.parent.parent / "uploads" / "batch_videos"
    os.makedirs(uploads_dir, exist_ok=True)
    filename = f"{uuid.uuid4().hex}{suffix}"
    (uploads_dir / filename).write_bytes(content)
    return filename


def video_thumbnail_upload_dir() -> Path:
    """Matches legacy PHP path segment: upload/video/image/"""
    return Path(__file__).resolve().parent.parent.parent / "uploads" / "video" / "image"


# These hosts do not serve uploads/video/image. krintixsample returns HTML; the
# marketing site is the public website, not the API.
_BLOCKED_THUMBNAIL_HOSTS = {
    "krintixsample.site",
    "www.krintixsample.site",
    "harishcriticalcareclasses.com",
    "www.harishcriticalcareclasses.com",
}
_VIDEO_THUMBNAIL_API = "https://api.harishcriticalcareclasses.com"


def _usable_thumbnail_base(url: str) -> Optional[str]:
    base = (url or "").strip().rstrip("/")
    if not base:
        return None
    host = (urlparse(base).hostname or "").lower()
    if not host or host in {"127.0.0.1", "localhost", "0.0.0.0"}:
        return None
    if host in _BLOCKED_THUMBNAIL_HOSTS:
        return None
    return base


def public_video_thumbnail_url(image: Optional[str]) -> Optional[str]:
    """URL for a file stored under uploads/video/image and served at /upload/video/image/.

    Those files live on the API host. krintixsample.site and the marketing site
    return a web page for this path, so they are never used.
    """
    raw = (image or "").strip().replace("\\", "/")
    if not raw:
        return None
    marker = "/upload/video/image/"
    if raw.startswith("http://") or raw.startswith("https://"):
        idx = raw.find(marker)
        name = raw[idx + len(marker):] if idx >= 0 else raw.split("/")[-1]
    else:
        name = raw.split("/")[-1]
    name = name.split("?")[0].split("#")[0].strip()
    if not name or name in {".", ".."} or "/" in name:
        return None
    settings = get_settings()
    base = _usable_thumbnail_base(settings.api_public_base_url) or _usable_thumbnail_base(
        settings.legacy_upload_base_url
    )
    if not base:
        configured = f"{settings.api_public_base_url} {settings.legacy_upload_base_url}".lower()
        if "127.0.0.1" in configured or "localhost" in configured:
            return f"/upload/video/image/{name}"
        base = _VIDEO_THUMBNAIL_API
    return f"{base}/upload/video/image/{name}"


def question_image_upload_dir() -> Path:
    """Legacy PHP: upload/questions/image/"""
    return Path(__file__).resolve().parent.parent.parent / "uploads" / "questions" / "image"


def save_question_image(file: UploadFile) -> str:
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in {".jpg", ".jpeg", ".png", ".webp"}:
        raise HTTPException(status_code=400, detail="Unsupported image type")
    content = file.file.read()
    if len(content) > MAX_FILE_BYTES:
        raise HTTPException(status_code=400, detail="Image exceeds 5MB limit")
    d = question_image_upload_dir()
    os.makedirs(d, exist_ok=True)
    filename = f"{uuid.uuid4().hex}{suffix}"
    (d / filename).write_bytes(content)
    return filename


def remove_question_image_file(filename: Optional[str]) -> None:
    if not filename or not str(filename).strip():
        return
    fn = str(filename).strip()
    for root in (question_image_upload_dir(), Path(__file__).resolve().parent.parent.parent / "uploads" / "question_images"):
        p = root / fn
        if p.is_file():
            try:
                p.unlink()
            except OSError:
                pass


def save_video_thumbnail(file: UploadFile) -> str:
    """Admin video list thumbnail → uploads/video/image/ (same relative path as PHP)."""
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in {".jpg", ".jpeg", ".png", ".webp"}:
        raise HTTPException(status_code=400, detail="Unsupported image type")
    content = file.file.read()
    if len(content) > MAX_FILE_BYTES:
        raise HTTPException(status_code=400, detail="Image exceeds 5MB limit")
    d = video_thumbnail_upload_dir()
    os.makedirs(d, exist_ok=True)
    filename = f"{uuid.uuid4().hex}{suffix}"
    (d / filename).write_bytes(content)
    return filename


def whatsapp_image_upload_dir() -> Path:
    """Admin WhatsApp campaign images (served at /upload/whatsapp/)."""
    return Path(__file__).resolve().parent.parent.parent / "uploads" / "whatsapp"


def save_whatsapp_image(file: UploadFile) -> str:
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in {".jpg", ".jpeg", ".png", ".webp"}:
        raise HTTPException(status_code=400, detail="Unsupported image type. Use JPG, PNG, or WEBP.")
    content = file.file.read()
    if len(content) > MAX_FILE_BYTES:
        raise HTTPException(status_code=400, detail="Image exceeds 5MB limit")
    d = whatsapp_image_upload_dir()
    os.makedirs(d, exist_ok=True)
    filename = f"{uuid.uuid4().hex}{suffix}"
    (d / filename).write_bytes(content)
    return filename


def whatsapp_image_path(filename: str) -> Path:
    fn = Path((filename or "").strip()).name
    if not fn:
        raise HTTPException(status_code=400, detail="Invalid image filename")
    return whatsapp_image_upload_dir() / fn


def whatsapp_image_public_url(filename: str) -> str:
    settings = get_settings()
    base = (settings.api_public_base_url or "").strip().rstrip("/")
    if not base or not base.lower().startswith("https://"):
        raise HTTPException(
            status_code=422,
            detail=(
                "API_PUBLIC_BASE_URL must be a public HTTPS URL so Meta can fetch images for templates. "
                "For image + free text (24h window), use Send mode: Free text."
            ),
        )
    fn = Path((filename or "").strip()).name
    return f"{base}/upload/whatsapp/{fn}"


def save_admin_image(file: UploadFile, kind: str) -> str:
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in {".jpg", ".jpeg", ".png", ".webp"}:
        raise HTTPException(status_code=400, detail="Unsupported image type")
    content = file.file.read()
    if len(content) > MAX_FILE_BYTES:
        raise HTTPException(status_code=400, detail="Image exceeds 5MB limit")
    uploads_dir = Path(__file__).resolve().parent.parent.parent / "uploads" / kind
    os.makedirs(uploads_dir, exist_ok=True)
    filename = f"{uuid.uuid4().hex}{suffix}"
    (uploads_dir / filename).write_bytes(content)
    return filename
