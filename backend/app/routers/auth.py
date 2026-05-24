from __future__ import annotations
import base64
import binascii
import hashlib
import hmac
import logging
import re
import string
from datetime import datetime
from typing import Annotated, Any, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db import get_db
from app.models import LoginActivity, User
from app.security import create_access_token, create_session_id, get_current_user
from app.services.batch_access import ensure_user_batch_active

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


def _payment_is_credit(payment_status: object) -> bool:
    """Match PHP-style payment flag (column may be str with different casing)."""
    if payment_status is None:
        return False
    return str(payment_status).strip().lower() == "credit"


def _user_is_approved(approve: object) -> bool:
    """
    Approve column is often '1'/'0' (string) but may be int 1/0 from DB/driver quirks.
    """
    if approve is None:
        return False
    if isinstance(approve, bool):
        return approve
    if isinstance(approve, (int, float)):
        return int(approve) == 1
    return str(approve).strip() == "1"

# Same secrets as PHP application/helpers/crud_helper.php::my_simple_crypt
_SECRET_KEY = "9meVE6j?G!u%Z?55vSb26zGGphWJQbG*"
_SECRET_IV = "9meVE6j?G!u%Z?55"

# Inner base64 layer sometimes damaged by charset / copy-paste (extend if needed)
_INNER_BYTE_FIX: dict[int, int] = {0x96: ord("V")}
_B64_CHARS = frozenset(string.ascii_letters + string.digits + "+/=")


def _aes_key_iv() -> tuple[bytes, bytes]:
    key = hashlib.sha256(_SECRET_KEY.encode()).hexdigest().encode()[:32]
    iv = hashlib.sha256(_SECRET_IV.encode()).hexdigest().encode()[:16]
    return key, iv


def _encrypt_plain_to_single_b64(plain: str) -> str:
    """
    Inner layer only: base64(AES-CBC ciphertext).
    PHP openssl_encrypt(..., 0, iv) returns this same string (before PHP's outer base64_encode).
    """
    key, iv = _aes_key_iv()
    padder = padding.PKCS7(128).padder()
    padded_data = padder.update(plain.encode()) + padder.finalize()
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
    encryptor = cipher.encryptor()
    ct = encryptor.update(padded_data) + encryptor.finalize()
    return base64.b64encode(ct).decode("ascii")


def _php_password_for_db(plain: str) -> str:
    """
    Exact string PHP stores: base64_encode( openssl_encrypt(...) )
    With PHP options=0, openssl_encrypt returns base64 text, so this is double base64 (~32 chars for 8-char passwords).
    """
    inner = _encrypt_plain_to_single_b64(plain)
    return base64.b64encode(inner.encode("ascii")).decode("ascii")


def _stored_password_variants(plain: str) -> tuple[str, str]:
    """
    Inner (24-ish chars) vs outer / PHP users.password (32-ish chars).
    Login must accept both; DB should stay on outer for PHP website compatibility.
    """
    inner = _encrypt_plain_to_single_b64(plain)
    outer = base64.b64encode(inner.encode("ascii")).decode("ascii")
    return inner, outer


def _inner_base64_string_from_outer_raw(raw: bytes) -> str:
    """Recover inner PHP base64 string from outer decode bytes (handles minor byte damage)."""
    fixed = bytes(_INNER_BYTE_FIX.get(b, b) for b in raw)
    try:
        inner = fixed.decode("ascii")
    except UnicodeDecodeError:
        inner = fixed.decode("latin-1").translate(str.maketrans({"\x96": "V"}))
        inner = "".join(c for c in inner if c in _B64_CHARS)
    if not inner or not re.fullmatch(r"[A-Za-z0-9+/]+=*", inner):
        raise ValueError("invalid inner base64 layer")
    return inner


def _ciphertext_from_stored(stored_b64: str) -> bytes:
    """Undo one or two layers of base64 to get AES ciphertext (multiple of 16 bytes)."""
    raw = base64.b64decode(stored_b64)
    if len(raw) % 16 == 0:
        return raw
    inner = _inner_base64_string_from_outer_raw(raw)
    try:
        return base64.b64decode(inner, validate=True)
    except (ValueError, binascii.Error):
        return base64.b64decode(inner)


def _consteq(a: str, b: str) -> bool:
    """Constant-time string compare; False if lengths differ (avoids ValueError)."""
    if len(a) != len(b):
        return False
    return hmac.compare_digest(a.encode("utf-8"), b.encode("utf-8"))


def _password_matches_stored(stored: str, plain: str) -> bool:
    """
    Match against how passwords appear in `users.password` from PHP or legacy tools.
    """
    stored = (stored or "").strip()
    plain = plain or ""
    if not stored:
        return False
    # Plaintext (some test / migrated rows)
    if _consteq(stored, plain):
        return True
    single_b64, double_b64 = _stored_password_variants(plain)
    if _consteq(stored, single_b64):
        return True
    if _consteq(stored, double_b64):
        return True
    # Decrypt stored blob and compare (single- or double-wrapped base64)
    try:
        decrypted = my_simple_crypt(stored, "decrypt")
        return _consteq(decrypted, plain)
    except Exception:
        return False


def my_simple_crypt(string, action="encrypt"):
    key, iv = _aes_key_iv()

    if action == "encrypt":
        # Match PHP crud_helper.php (double layer — what Register.php saves)
        return _php_password_for_db(string)

    ct = _ciphertext_from_stored(string)
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
    decryptor = cipher.decryptor()
    padded_data = decryptor.update(ct) + decryptor.finalize()
    unpadder = padding.PKCS7(128).unpadder()
    data = unpadder.update(padded_data) + unpadder.finalize()
    return data.decode()

class LoginRequest(BaseModel):
    """Internal validation for POST /auth/login JSON.

    Only **email** is required. **password** may be omitted, null, or \"\" — then email-only
    rules apply (mock test). If a non-empty password is sent, it is verified like the PHP site.
    """

    email: str
    password: Optional[str] = Field(
        default=None,
        description="Optional. Omit for email-only mock test login.",
    )


class UserResponse(BaseModel):
    id: int
    name: str | None = None
    email: str
    subscription: str | None = None
    package_id: int | None = None

    model_config = {"from_attributes": True}


class LoginResponse(UserResponse):
    """Session bootstrap payload for dashboard/video/mock-test flows."""

    user_id: int = Field(description="Same as id; use as user_id query param on exam APIs")
    list_exams_url: str = Field(description="Relative path: GET with this + your API base URL")
    dashboard_url: str = Field(description="Frontend route to post-login dashboard")
    videos_url: str = Field(description="Frontend route to video folders")
    mock_tests_url: str = Field(description="Frontend route to mock test listing")
    access_token: str = Field(description="Bearer token for protected APIs")
    token_type: str = Field(default="bearer")


@router.post("/login", response_model=LoginResponse)
def login(
    _request: Request,
    body: Annotated[
        dict[str, Any],
        Body(
            openapi_examples={
                "email_only": {
                    "summary": "Mock test (email only)",
                    "description": "Send only your registered email — no password.",
                    "value": {"email": "you@example.com"},
                },
                "with_password": {
                    "summary": "With password (optional)",
                    "description": "Same as main website login when you include password.",
                    "value": {"email": "you@example.com", "password": "your-password"},
                },
            },
            description=(
                "**email** (string, required). **password** (string) is optional — "
                "leave it out for mock test; clients may still send it for full login."
            ),
        ),
    ],
    db: Session = Depends(get_db),
):
    try:
        request = LoginRequest.model_validate(body)
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=e.errors(),
        ) from e

    email = request.email.strip()
    user = (
        db.query(User)
        .filter(func.lower(func.trim(User.email)) == email.lower())
        .first()
    )
    if not user:
        logger.info("login failed: no user for email=%s", email)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    pwd = (request.password or "").strip()
    if pwd:
        if not _password_matches_stored(user.password, pwd):
            logger.info("login failed: bad password for email=%s", email)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password",
            )
    else:
        # Email-only: optionally require paid + approved (see EMAIL_ONLY_LOGIN_STRICT)
        settings = get_settings()
        if settings.email_only_login_strict:
            if not _payment_is_credit(getattr(user, "payment_status", None)):
                logger.info("login failed: email-only but payment not Credit for %s", email)
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Account is not active for mock test (payment required).",
                )
            if not _user_is_approved(getattr(user, "approve", None)):
                logger.info("login failed: email-only but not approved for %s", email)
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Account is not approved for mock test.",
                )

    # batch_master.status=0 → no login (matches admin "deactivate batch" intent).
    try:
        ensure_user_batch_active(db, user)
    except HTTPException as exc:
        logger.info("login failed: batch inactive for %s — %s", email, exc.detail)
        raise

    if pwd and get_settings().auth_sync_password_on_login:
        canonical = _php_password_for_db(pwd)
        if (user.password or "").strip() != canonical:
            user.password = canonical
            db.add(user)
            db.commit()
            db.refresh(user)

    list_path = f"/exams?user_id={user.id}"
    session_id = create_session_id()
    user.login_token = session_id
    user.is_login = "Yes"
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token(user_id=user.id, email=user.email, session_id=session_id)

    # Same table as PHP Login.php (login_activity).
    try:
        db.add(
            LoginActivity(
                users_id=user.id,
                activity="Login",
                activity_datetime=datetime.utcnow(),
            )
        )
        db.commit()
    except Exception as exc:
        logger.warning("login_activity insert failed (table/schema?): %s", exc)
        db.rollback()

    return LoginResponse(
        id=user.id,
        name=user.name,
        email=user.email,
        subscription=user.subscription,
        package_id=user.package_id,
        user_id=user.id,
        list_exams_url=list_path,
        dashboard_url="/dashboard",
        videos_url="/videos/folders",
        mock_tests_url="/mock/exams",
        access_token=token,
        token_type="bearer",
    )


class SessionCheckResponse(BaseModel):
    valid: bool = True


@router.get("/session/check", response_model=SessionCheckResponse)
def session_check(_current_user: User = Depends(get_current_user)) -> SessionCheckResponse:
    """Lightweight poll — get_current_user already validates login_token vs JWT sid."""
    return SessionCheckResponse(valid=True)


@router.post("/logout")
def logout(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    current_user.login_token = ""
    current_user.is_login = "No"
    db.add(current_user)
    try:
        db.add(
            LoginActivity(
                users_id=current_user.id,
                activity="Logout",
                activity_datetime=datetime.utcnow(),
            )
        )
        db.commit()
    except Exception as exc:
        logger.warning("login_activity insert failed on logout: %s", exc)
        db.rollback()
    return {"status": "ok"}
