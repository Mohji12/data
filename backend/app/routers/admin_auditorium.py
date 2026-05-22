from __future__ import annotations
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.admin_security import get_current_admin, require_admin_type
from app.db import get_db
from app.models import Option

router = APIRouter(prefix="/admin/auditorium", tags=["admin-auditorium"], dependencies=[Depends(get_current_admin)])


class AuditoriumResponse(BaseModel):
    auditorium_link: str = ""
    display_auditorium_link: str = "0"
    access_auditorium_link: list[str] = []


class AuditoriumSaveRequest(BaseModel):
    auditorium_link: str = Field(default="", description="Embed URL (e.g. https://vimeo.com/event/3239165/embed)")
    display_auditorium_link: str = Field(default="0", description="0/1")
    access_auditorium_link: list[str] = Field(default_factory=list, description="Allowed batch/subscription names")


@router.get("", response_model=AuditoriumResponse)
def get_auditorium(db: Session = Depends(get_db)) -> AuditoriumResponse:
    def _get(name: str) -> str:
        r = db.query(Option).filter(Option.option_name == name).first()
        return r.option_value if r and r.option_value else ""

    auditorium_link = _get("auditorium_link")
    display = _get("display_auditorium_link") or "0"
    access_raw = _get("access_auditorium_link")
    access_list = [s.strip() for s in access_raw.split(",") if s.strip()] if access_raw else []
    return AuditoriumResponse(
        auditorium_link=auditorium_link,
        display_auditorium_link=display,
        access_auditorium_link=access_list,
    )


@router.post("/save", dependencies=[Depends(require_admin_type("techadmin"))])
def save_auditorium(req: AuditoriumSaveRequest, db: Session = Depends(get_db)) -> dict:
    def _upsert(name: str, value: str) -> None:
        r = db.query(Option).filter(Option.option_name == name).first()
        if not r:
            r = Option(option_name=name, option_value=value)
        else:
            r.option_value = value
        db.add(r)

    _upsert("auditorium_link", req.auditorium_link)
    _upsert("display_auditorium_link", req.display_auditorium_link)
    _upsert("access_auditorium_link", ",".join([s.strip() for s in req.access_auditorium_link if s and s.strip()]))
    db.commit()
    return {"status": "ok"}

