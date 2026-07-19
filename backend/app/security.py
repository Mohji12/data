from __future__ import annotations
import base64
import hashlib
import hmac
import json
import secrets
import time
from typing import Any

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db import get_db
from app.models import User
from app.services.batch_access import ensure_user_batch_active

_bearer = HTTPBearer(auto_error=False)


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _b64url_decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode((data + padding).encode("ascii"))


SESSION_INVALID_DETAIL = "Logged in on another device"


def create_session_id() -> str:
    return secrets.token_urlsafe(32)


def create_access_token(user_id: int, email: str, session_id: str) -> str:
    settings = get_settings()
    payload = {
        "uid": user_id,
        "email": email,
        "sid": session_id,
        "exp": int(time.time()) + (settings.api_token_ttl_hours * 3600),
    }
    body = _b64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    sig = hmac.new(
        settings.api_token_secret.encode("utf-8"),
        body.encode("ascii"),
        hashlib.sha256,
    ).digest()
    return f"{body}.{_b64url_encode(sig)}"


def _parse_access_token_payload(token: str) -> dict[str, Any]:
    """Verify signature and return payload. Does not enforce expiry."""
    settings = get_settings()
    try:
        body, sig = token.split(".", 1)
        expected = hmac.new(
            settings.api_token_secret.encode("utf-8"),
            body.encode("ascii"),
            hashlib.sha256,
        ).digest()
        sent = _b64url_decode(sig)
        if not hmac.compare_digest(expected, sent):
            raise ValueError("invalid signature")
        payload = json.loads(_b64url_decode(body).decode("utf-8"))
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        ) from exc
    if not isinstance(payload, dict):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )
    return payload


def decode_access_token(token: str) -> dict[str, Any]:
    payload = _parse_access_token_payload(token)
    if int(payload.get("exp", 0)) < int(time.time()):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )
    return payload


def decode_access_token_for_refresh(token: str, *, grace_seconds: int) -> dict[str, Any]:
    """Allow recently expired tokens so an active exam session can renew the JWT."""
    payload = _parse_access_token_payload(token)
    exp = int(payload.get("exp", 0))
    now = int(time.time())
    if exp + max(0, grace_seconds) < now:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )
    return payload


def assert_active_user_session(user: User, payload: dict[str, Any]) -> None:
    """One active session per user — JWT sid must match users.login_token."""
    stored = (user.login_token or "").strip()
    token_sid = str(payload.get("sid") or "").strip()
    if not stored or not token_sid or not hmac.compare_digest(stored, token_sid):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=SESSION_INVALID_DETAIL,
        )


def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> User:
    if not creds:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authorization token",
        )
    payload = decode_access_token(creds.credentials)
    user_id = int(payload.get("uid", 0))
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User session not found",
        )
    assert_active_user_session(user, payload)
    ensure_user_batch_active(db, user)
    return user
