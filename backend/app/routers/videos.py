from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import cast, func
from sqlalchemy.orm import Session
from sqlalchemy.types import Integer

from app.core.config import get_settings
from app.db import get_db
from app.models import Audit, FolderMaster, User, Video, VideoQuestion
from app.schemas import (
    VideoDetail,
    VideoFolderItem,
    VideoListItem,
    VideoListPage,
    VideoQuestionCreate,
    VideoQuestionCreateResponse,
)
from app.security import get_current_user
from app.services.access import can_access_video_library

router = APIRouter(prefix="/videos", tags=["videos"])


def _public_video_thumbnail_url(image: Optional[str]) -> Optional[str]:
    if not image or not str(image).strip():
        return None
    base = get_settings().legacy_upload_base_url.strip().rstrip("/")
    if base:
        return f"{base}/upload/video/image/{str(image).strip()}"
    return None


def _folder_label_from_video_csv(db: Session, video: Video) -> tuple[Optional[int], Optional[str]]:
    """Resolve folder id/name when `videos.folder` is comma-separated (legacy)."""
    raw = (video.folder or "").strip()
    if not raw:
        return None, None
    for part in raw.split(","):
        p = part.strip()
        if p.isdigit():
            fid = int(p)
            fm = db.query(FolderMaster).filter(FolderMaster.id == fid).first()
            if fm:
                return fid, fm.name
    return None, None


def _subscription_in_csv(subscription: str | None, csv_column: str | None) -> bool:
    """Match legacy PHP FIND_IN_SET(subscription, batch) / folder membership (comma-separated)."""
    sub = (subscription or "").strip()
    if not sub:
        return False
    parts = [p.strip() for p in (csv_column or "").split(",") if p.strip()]
    sub_l = sub.lower()
    return any(p.lower() == sub_l for p in parts)


def _ensure_video_access(db: Session, user: User) -> None:
    allowed, reason = can_access_video_library(db, user)
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=reason or "Video library access denied.",
        )


@router.get("/folders", response_model=list[VideoFolderItem])
def list_video_folders(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[VideoFolderItem]:
    _ensure_video_access(db, current_user)
    subscription = (current_user.subscription or "").strip()
    if not subscription:
        return []
    # PHP folder_wise: FIND_IN_SET(subscription, folder_master.batch)
    folders = (
        db.query(FolderMaster)
        .filter(
            FolderMaster.status == "1",
            func.find_in_set(subscription, func.coalesce(FolderMaster.batch, "")) > 0,
        )
        .order_by(FolderMaster.display_order.asc(), FolderMaster.id.asc())
        .all()
    )
    return [
        VideoFolderItem(id=f.id, name=f.name, display_order=f.display_order or 0)
        for f in folders
    ]


@router.get("", response_model=VideoListPage)
def list_videos(
    folder_id: Optional[int] = Query(None),
    title: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(12, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> VideoListPage:
    _ensure_video_access(db, current_user)
    subscription = (current_user.subscription or "").strip()
    if not subscription:
        return VideoListPage(items=[], total=0, page=page, page_size=page_size, has_more=False)

    # PHP: FIND_IN_SET(subscription, videos.batch); folder: FIND_IN_SET(folder_id, videos.folder)
    filters = [
        Video.status == "1",
        func.find_in_set(subscription, func.coalesce(Video.batch, "")) > 0,
    ]
    if folder_id is not None:
        filters.append(func.find_in_set(str(folder_id), func.coalesce(Video.folder, "")) > 0)
    if title:
        filters.append(func.lower(func.coalesce(Video.title, "")).contains(title.lower()))

    total = db.query(func.count(Video.id)).filter(*filters).scalar() or 0
    offset = (page - 1) * page_size

    selected_folder_name: str | None = None
    if folder_id is not None:
        fm = db.query(FolderMaster).filter(FolderMaster.id == folder_id).first()
        selected_folder_name = fm.name if fm else None

    base = db.query(Video).filter(*filters).order_by(Video.upload_date.desc(), Video.id.desc())
    video_rows = base.offset(offset).limit(page_size).all()

    items: list[VideoListItem] = []
    if folder_id is not None:
        for video in video_rows:
            items.append(
                VideoListItem(
                    id=video.id,
                    title=video.title,
                    folder_id=folder_id,
                    folder_name=selected_folder_name,
                    thumbnail_url=_public_video_thumbnail_url(video.image),
                    description=video.description,
                    upload_date=video.upload_date,
                )
            )
    else:
        joined = (
            db.query(Video, FolderMaster.name.label("folder_name"), FolderMaster.id.label("folder_id"))
            .outerjoin(FolderMaster, cast(Video.folder, Integer) == FolderMaster.id)
            .filter(*filters)
            .order_by(Video.upload_date.desc(), Video.id.desc())
            .offset(offset)
            .limit(page_size)
            .all()
        )
        for video, folder_name, folder_key in joined:
            items.append(
                VideoListItem(
                    id=video.id,
                    title=video.title,
                    folder_id=folder_key,
                    folder_name=folder_name,
                    thumbnail_url=_public_video_thumbnail_url(video.image),
                    description=video.description,
                    upload_date=video.upload_date,
                )
            )
    has_more = offset + len(items) < total
    return VideoListPage(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        has_more=has_more,
    )


@router.post("/{video_id}/play-audit")
def audit_video_play(
    video_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """PHP `show.php` play tracking: used by admin video-activity CSV."""
    _ensure_video_access(db, current_user)
    video = db.query(Video).filter(Video.id == video_id, Video.status == "1").first()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    if not _subscription_in_csv(current_user.subscription, video.batch):
        raise HTTPException(status_code=403, detail="Video not available for your subscription.")
    db.add(
        Audit(
            user_id=current_user.id,
            file_id=video.id,
            file_type="video",
            activity="Video Details Page Play Video",
            activity_details=f"Play Video - {video.title}",
            activity_datetime=datetime.utcnow(),
        )
    )
    db.commit()
    return {"status": "ok"}


@router.get("/{video_id}", response_model=VideoDetail)
def get_video_detail(
    video_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> VideoDetail:
    _ensure_video_access(db, current_user)

    video = db.query(Video).filter(Video.id == video_id, Video.status == "1").first()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    folder_key, folder_name = _folder_label_from_video_csv(db, video)
    if not _subscription_in_csv(current_user.subscription, video.batch):
        raise HTTPException(status_code=403, detail="Video not available for your subscription.")

    # PHP Videos::video_details — page open audit.
    db.add(
        Audit(
            user_id=current_user.id,
            file_id=video.id,
            file_type="video",
            activity="Video Details Page Open",
            activity_details=f"Video Title - {video.title}",
            activity_datetime=datetime.utcnow(),
        )
    )
    db.commit()

    return VideoDetail(
        id=video.id,
        title=video.title,
        description=video.description,
        folder_id=folder_key,
        folder_name=folder_name,
        thumbnail_url=_public_video_thumbnail_url(video.image),
        video_url=video.video_link,
        upload_date=video.upload_date,
    )


@router.post("/{video_id}/questions", response_model=VideoQuestionCreateResponse)
def submit_video_question(
    video_id: int,
    payload: VideoQuestionCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> VideoQuestionCreateResponse:
    _ensure_video_access(db, current_user)

    question_text = payload.question.strip()
    if not question_text:
        raise HTTPException(status_code=400, detail="Question is required.")

    exists = db.query(Video.id).filter(Video.id == video_id, Video.status == "1").first()
    if not exists:
        raise HTTPException(status_code=404, detail="Video not found")

    db.add(
        VideoQuestion(
            users_id=current_user.id,
            question=question_text,
            created_at=datetime.utcnow(),
        )
    )
    db.commit()

    return VideoQuestionCreateResponse(
        status="ok",
        message="Question submitted successfully.",
    )
