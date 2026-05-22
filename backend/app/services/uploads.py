from __future__ import annotations

import os
import uuid
from pathlib import Path
from typing import Optional

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
