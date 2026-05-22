from __future__ import annotations
import hashlib

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.admin_security import create_admin_token, get_current_admin
from app.db import get_db
from app.models import Admin

router = APIRouter(prefix="/admin/auth", tags=["admin-auth"])


class AdminLoginRequest(BaseModel):
    username: str
    password: str


class AdminLoginResponse(BaseModel):
    admin_id: int
    name: str | None = None
    username: str
    user_type: str | None = None
    access_token: str
    token_type: str = "bearer"


@router.post("/login", response_model=AdminLoginResponse)
def admin_login(payload: AdminLoginRequest, db: Session = Depends(get_db)) -> AdminLoginResponse:
    username = payload.username.strip()
    admin = db.query(Admin).filter(Admin.username == username).first()
    if not admin:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    md5 = hashlib.md5(payload.password.encode("utf-8")).hexdigest()
    if (admin.password or "").strip() != md5:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    token = create_admin_token(admin_id=admin.id, username=admin.username, user_type=admin.user_type)
    return AdminLoginResponse(
        admin_id=admin.id,
        name=admin.name,
        username=admin.username,
        user_type=admin.user_type,
        access_token=token,
    )


@router.get("/me", response_model=AdminLoginResponse)
def admin_me(admin: Admin = Depends(get_current_admin)) -> AdminLoginResponse:
    token = create_admin_token(admin_id=admin.id, username=admin.username, user_type=admin.user_type)
    return AdminLoginResponse(
        admin_id=admin.id,
        name=admin.name,
        username=admin.username,
        user_type=admin.user_type,
        access_token=token,
    )


@router.post("/logout")
def admin_logout() -> dict:
    # Stateless tokens: frontend deletes token.
    return {"status": "ok"}

