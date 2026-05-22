import base64
import hashlib
import hmac
import json
import time
from typing import Any

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db import get_db
from app.models import Admin

_bearer = HTTPBearer(auto_error=False)


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _b64url_decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode((data + padding).encode("ascii"))


def create_admin_token(admin_id: int, username: str, user_type: str | None) -> str:
    settings = get_settings()
    payload = {
        "aid": admin_id,
        "username": username,
        "user_type": user_type,
        "exp": int(time.time()) + (settings.api_token_ttl_hours * 3600),
    }
    body = _b64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    sig = hmac.new(
        settings.api_token_secret.encode("utf-8"),
        b"admin:" + body.encode("ascii"),
        hashlib.sha256,
    ).digest()
    return f"{body}.{_b64url_encode(sig)}"


def decode_admin_token(token: str) -> dict[str, Any]:
    settings = get_settings()
    try:
        body, sig = token.split(".", 1)
        expected = hmac.new(
            settings.api_token_secret.encode("utf-8"),
            b"admin:" + body.encode("ascii"),
            hashlib.sha256,
        ).digest()
        sent = _b64url_decode(sig)
        if not hmac.compare_digest(expected, sent):
            raise ValueError("invalid signature")
        payload = json.loads(_b64url_decode(body).decode("utf-8"))
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired admin token",
        ) from exc

    if int(payload.get("exp", 0)) < int(time.time()):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired admin token",
        )
    return payload


def get_current_admin(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> Admin:
    if not creds:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing admin authorization token",
        )
    payload = decode_admin_token(creds.credentials)
    admin_id = int(payload.get("aid", 0))
    admin = db.query(Admin).filter(Admin.id == admin_id).first()
    if not admin:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Admin session not found",
        )
    return admin


def require_admin_type(required: str):
    def _dep(admin: Admin = Depends(get_current_admin)) -> Admin:
        if (admin.user_type or "").strip().lower() != required.lower():
            raise HTTPException(status_code=403, detail="Insufficient admin permissions")
        return admin

    return _dep

