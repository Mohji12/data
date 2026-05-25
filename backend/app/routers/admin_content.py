from __future__ import annotations
import csv
import io
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session, load_only

from app.admin_security import get_current_admin, require_admin_type
from app.core.config import get_settings
from app.db import get_db
from app.models import Audit, FolderMaster, User, Video, VideoQuestion
from app.services.uploads import save_admin_image, save_video_thumbnail, video_thumbnail_upload_dir

router = APIRouter(prefix="/admin/content", tags=["admin-content"], dependencies=[Depends(get_current_admin)])


def _admin_video_image_url(filename: Optional[str]) -> Optional[str]:
    if not filename or not str(filename).strip():
        return None
    settings = get_settings()
    # Thumbnails are served by the API (`/upload/video/image` mount), not the static SPA host.
    base = (
        (settings.legacy_upload_base_url or "").strip().rstrip("/")
        or (settings.api_public_base_url or "").strip().rstrip("/")
    )
    if not base:
        return None
    return f"{base}/upload/video/image/{str(filename).strip()}"


def _remove_stored_video_thumbnail(filename: Optional[str]) -> None:
    """Delete thumbnail from disk (PHP-style path and legacy FastAPI folder)."""
    if not filename or not str(filename).strip():
        return
    fn = str(filename).strip()
    for root in (video_thumbnail_upload_dir(), Path(__file__).resolve().parent.parent.parent / "uploads" / "video_images"):
        p = root / fn
        if p.is_file():
            try:
                p.unlink()
            except OSError:
                pass


def _parse_folder_ids(folder_csv: Optional[str]) -> list[int]:
    raw = (folder_csv or "").strip()
    if not raw:
        return []
    ids: list[int] = []
    for part in raw.split(","):
        p = part.strip()
        if p.isdigit():
            ids.append(int(p))
    return ids


def _folder_names_from_ids(ids: list[int], by_id: dict[int, str]) -> str:
    return ", ".join(by_id.get(i, "") for i in ids if by_id.get(i))


def _load_folder_name_map(db: Session, folder_csvs: list[Optional[str]]) -> dict[int, str]:
    all_ids: set[int] = set()
    for csv in folder_csvs:
        all_ids.update(_parse_folder_ids(csv))
    if not all_ids:
        return {}
    rows = db.query(FolderMaster).filter(FolderMaster.id.in_(all_ids)).all()
    return {r.id: (r.name or "") for r in rows}


def _folder_names_from_csv(db: Session, folder_csv: Optional[str]) -> str:
    ids = _parse_folder_ids(folder_csv)
    if not ids:
        return ""
    by_id = _load_folder_name_map(db, [folder_csv])
    return _folder_names_from_ids(ids, by_id)


class FolderPayload(BaseModel):
    name: str
    status: str = "1"
    batch: Optional[str] = None
    display_order: int = 0


@router.get("/folders")
def list_folders(
    q: Optional[str] = Query(None),
    batch: Optional[str] = Query(None),
    sort_by: Optional[str] = Query(None, description="id, name, display_order"),
    order: str = Query("asc"),
    db: Session = Depends(get_db),
) -> list[dict]:
    query = db.query(FolderMaster)
    if q:
        s = f"%{q.strip().lower()}%"
        query = query.filter(func.lower(func.coalesce(FolderMaster.name, "")).like(s))
    if batch:
        query = query.filter(func.lower(func.coalesce(FolderMaster.batch, "")).like(f"%{batch.strip().lower()}%"))

    # Dynamic sorting
    if sort_by:
        col = getattr(FolderMaster, sort_by, None)
        if col:
            if order.lower() == "asc":
                query = query.order_by(col.asc())
            else:
                query = query.order_by(col.desc())
        else:
            query = query.order_by(FolderMaster.display_order.asc(), FolderMaster.id.desc())
    else:
        query = query.order_by(FolderMaster.display_order.asc(), FolderMaster.id.desc())

    rows = query.all()
    return [{"id": f.id, "name": f.name, "status": f.status, "batch": f.batch, "display_order": f.display_order} for f in rows]


@router.post("/folders", dependencies=[Depends(require_admin_type("techadmin"))])
def create_folder(payload: FolderPayload, db: Session = Depends(get_db)) -> dict:
    f = FolderMaster(name=payload.name, status=payload.status, batch=payload.batch, display_order=payload.display_order)
    db.add(f)
    db.commit()
    db.refresh(f)
    return {"id": f.id}


@router.put("/folders/{folder_id}", dependencies=[Depends(require_admin_type("techadmin"))])
def update_folder(folder_id: int, payload: FolderPayload, db: Session = Depends(get_db)) -> dict:
    f = db.query(FolderMaster).filter(FolderMaster.id == folder_id).first()
    if not f:
        raise HTTPException(status_code=404, detail="Folder not found")
    f.name = payload.name
    f.status = payload.status
    f.batch = payload.batch
    f.display_order = payload.display_order
    db.add(f)
    db.commit()
    return {"status": "ok"}


@router.delete("/folders/{folder_id}", dependencies=[Depends(require_admin_type("techadmin"))])
def delete_folder(folder_id: int, db: Session = Depends(get_db)) -> dict:
    f = db.query(FolderMaster).filter(FolderMaster.id == folder_id).first()
    if not f:
        raise HTTPException(status_code=404, detail="Folder not found")
    db.delete(f)
    db.commit()
    return {"status": "ok"}


class VideoPayload(BaseModel):
    """Mirrors PHP admin Videos save/update (batch = comma-separated batch names, folder = comma-separated folder ids)."""

    title: str
    description: str = ""
    image: Optional[str] = None
    video_link: str = ""
    folder: Optional[str] = None
    batch: str = ""
    status: str = "1"
    upload_date: Optional[datetime] = None


def _normalize_csv_field(s: Optional[str]) -> Optional[str]:
    if s is None:
        return None
    t = str(s).strip()
    return t if t else None


_VIDEO_LIST_COLUMNS = (
    Video.id,
    Video.title,
    Video.description,
    Video.status,
    Video.folder,
    Video.batch,
    Video.image,
    Video.video_link,
    Video.upload_date,
)

_VIDEO_SORT_COLUMNS = {"id", "title", "upload_date"}


def _serialize_video_row(v: Video, folder_map: dict[int, str]) -> dict:
    upload_date = v.upload_date
    if upload_date is not None and hasattr(upload_date, "isoformat"):
        upload_date_str = upload_date.isoformat()
    else:
        upload_date_str = str(upload_date) if upload_date else None
    return {
        "id": v.id,
        "title": v.title,
        "description": v.description,
        "status": v.status,
        "folder": v.folder,
        "folder_names": _folder_names_from_ids(_parse_folder_ids(v.folder), folder_map),
        "batch": v.batch,
        "image": v.image,
        "image_url": _admin_video_image_url(v.image),
        "video_link": v.video_link,
        "upload_date": upload_date_str,
    }


@router.get("/videos")
def list_videos(
    q: Optional[str] = Query(None),
    batch: Optional[str] = Query(None),
    sort_by: Optional[str] = Query(None, description="id, title, upload_date"),
    order: str = Query("desc"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> dict:
    query = db.query(Video).options(load_only(*_VIDEO_LIST_COLUMNS))
    if q:
        s = f"%{q.strip().lower()}%"
        query = query.filter(func.lower(func.coalesce(Video.title, "")).like(s))
    if batch:
        query = query.filter(func.lower(func.coalesce(Video.batch, "")).like(f"%{batch.strip().lower()}%"))

    sort_key = (sort_by or "").strip().lower()
    if sort_key in _VIDEO_SORT_COLUMNS:
        col = getattr(Video, sort_key)
        if order.lower() == "asc":
            query = query.order_by(col.asc(), Video.id.asc())
        else:
            query = query.order_by(col.desc(), Video.id.desc())
    else:
        query = query.order_by(Video.upload_date.desc(), Video.id.desc())

    total = query.count()
    offset = (page - 1) * page_size
    rows = query.offset(offset).limit(page_size).all()
    folder_map = _load_folder_name_map(db, [v.folder for v in rows])
    return {
        "items": [_serialize_video_row(v, folder_map) for v in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/videos/{video_id}")
def get_video(video_id: int, db: Session = Depends(get_db)) -> dict:
    v = db.query(Video).filter(Video.id == video_id).first()
    if not v:
        raise HTTPException(status_code=404, detail="Video not found")
    return {
        "id": v.id,
        "title": v.title,
        "description": v.description or "",
        "status": v.status,
        "folder": v.folder,
        "folder_names": _folder_names_from_csv(db, v.folder),
        "batch": v.batch,
        "image": v.image,
        "image_url": _admin_video_image_url(v.image),
        "video_link": v.video_link or "",
        "upload_date": v.upload_date.isoformat() if v.upload_date else None,
    }


@router.post("/videos", dependencies=[Depends(require_admin_type("techadmin"))])
def create_video(payload: VideoPayload, db: Session = Depends(get_db)) -> dict:
    if not (payload.title or "").strip():
        raise HTTPException(status_code=422, detail="Title is required.")
    if not (payload.description or "").strip():
        raise HTTPException(status_code=422, detail="Description is required.")
    if not (payload.video_link or "").strip():
        raise HTTPException(status_code=422, detail="Video link is required.")
    if not (payload.batch or "").strip():
        raise HTTPException(status_code=422, detail="At least one batch is required.")
    if not (payload.image or "").strip():
        raise HTTPException(status_code=422, detail="Thumbnail image is required (upload first).")

    ud = payload.upload_date if payload.upload_date else datetime.utcnow()
    v = Video(
        title=payload.title.strip(),
        description=payload.description.strip(),
        image=(payload.image or "").strip(),
        video_link=payload.video_link.strip(),
        folder=_normalize_csv_field(payload.folder),
        batch=payload.batch.strip(),
        status=payload.status or "1",
        upload_date=ud,
    )
    db.add(v)
    db.commit()
    db.refresh(v)
    return {"id": v.id}


@router.put("/videos/{video_id}", dependencies=[Depends(require_admin_type("techadmin"))])
def update_video(video_id: int, payload: VideoPayload, db: Session = Depends(get_db)) -> dict:
    v = db.query(Video).filter(Video.id == video_id).first()
    if not v:
        raise HTTPException(status_code=404, detail="Video not found")
    if not (payload.title or "").strip():
        raise HTTPException(status_code=422, detail="Title is required.")
    if not (payload.description or "").strip():
        raise HTTPException(status_code=422, detail="Description is required.")
    if not (payload.video_link or "").strip():
        raise HTTPException(status_code=422, detail="Video link is required.")
    if not (payload.batch or "").strip():
        raise HTTPException(status_code=422, detail="At least one batch is required.")
    new_img = (payload.image or "").strip()
    if not new_img and not (v.image or "").strip():
        raise HTTPException(status_code=422, detail="Thumbnail image is required.")
    old_img = (v.image or "").strip()
    if new_img and old_img and new_img != old_img:
        _remove_stored_video_thumbnail(old_img)

    v.title = payload.title.strip()
    v.description = payload.description.strip()
    v.image = new_img or old_img
    v.video_link = payload.video_link.strip()
    v.folder = _normalize_csv_field(payload.folder)
    v.batch = payload.batch.strip()
    v.status = payload.status or "1"
    if payload.upload_date is not None:
        v.upload_date = payload.upload_date
    db.add(v)
    db.commit()
    return {"status": "ok"}


@router.delete("/videos/{video_id}", dependencies=[Depends(require_admin_type("techadmin"))])
def delete_video(video_id: int, db: Session = Depends(get_db)) -> dict:
    v = db.query(Video).filter(Video.id == video_id).first()
    if not v:
        raise HTTPException(status_code=404, detail="Video not found")
    _remove_stored_video_thumbnail(v.image)
    db.delete(v)
    db.commit()
    return {"status": "ok"}


@router.get("/video-questions")
def list_video_questions(db: Session = Depends(get_db)) -> list[dict]:
    rows = (
        db.query(VideoQuestion, User)
        .join(User, User.id == VideoQuestion.users_id)
        .order_by(VideoQuestion.id.desc())
        .all()
    )
    return [
        {
            "id": q.id,
            "user_id": q.users_id,
            "user_email": u.email,
            "video_id": None,
            "question": q.question,
            "created_at": q.created_at.isoformat() if q.created_at else None,
        }
        for q, u in rows
    ]


@router.delete("/video-questions/{question_id}")
def delete_video_question(question_id: int, db: Session = Depends(get_db)) -> dict:
    row = db.query(VideoQuestion).filter(VideoQuestion.id == question_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Question not found")
    db.delete(row)
    db.commit()
    return {"status": "ok"}


@router.post("/video-questions/delete-all", dependencies=[Depends(require_admin_type("techadmin"))])
def delete_all_video_questions(db: Session = Depends(get_db)) -> dict:
    db.query(VideoQuestion).delete()
    db.commit()
    return {"status": "ok"}


@router.get("/video-questions/export.csv")
def export_video_questions(db: Session = Depends(get_db)) -> Response:
    rows = (
        db.query(VideoQuestion, User)
        .join(User, User.id == VideoQuestion.users_id)
        .order_by(VideoQuestion.id.desc())
        .all()
    )
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["id", "user_id", "email", "video_id", "question", "created_at"])
    for q, u in rows:
        w.writerow([q.id, q.users_id, u.email or "", "", q.question or "", q.created_at.isoformat() if q.created_at else ""])
    return Response(content=buf.getvalue(), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=video_questions.csv"})


@router.get("/video-activity/export.csv", dependencies=[Depends(require_admin_type("techadmin"))])
def export_video_activity(db: Session = Depends(get_db)) -> Response:
    """PHP admin `Videos::download_video_activity`: play events only, columns Name / Email / Phone / Video / Date Time."""
    rows = (
        db.query(Audit, User)
        .join(User, User.id == Audit.user_id)
        .filter(
            Audit.activity == "Video Details Page Play Video",
            func.lower(func.coalesce(Audit.file_type, "")) == "video",
        )
        .order_by(Audit.id.asc())
        .all()
    )
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["Name", "Email", "Phone", "Video", "Date Time"])
    for a, u in rows:
        name = " ".join(x for x in [(u.title or "").strip(), (u.name or "").strip()] if x).strip()
        dt = a.activity_datetime
        w.writerow(
            [
                name,
                u.email or "",
                u.contact_number or "",
                (a.activity_details or "").strip(),
                dt.strftime("%d-%m-%Y %H:%M:%S") if dt else "",
            ]
        )
    return Response(content=buf.getvalue(), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=video_activity.csv"})


@router.post("/videos/upload-image", dependencies=[Depends(require_admin_type("techadmin"))])
def upload_video_image(file: UploadFile = File(...)) -> dict:
    filename = save_video_thumbnail(file)
    return {"filename": filename}

