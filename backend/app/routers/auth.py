from __future__ import annotations
import logging
from datetime import datetime
from typing import Annotated, Any, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, EmailStr, Field, ValidationError
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db import get_db
from app.models import LoginActivity, User
from app.security import (
    create_access_token,
    create_session_id,
    decode_access_token_for_refresh,
    assert_active_user_session,
    get_current_user,
)
from app.services.batch_access import ensure_user_batch_active
from app.services.password_crypto import password_matches_stored, php_password_for_db
from app.services.password_reset_otp import request_password_reset_otp, reset_password_with_otp

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])
_bearer = HTTPBearer(auto_error=False)


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


def _is_ccm2_practical_series(subscription: object) -> bool:
    """Block login for CCM 2 Practical/Partical series users."""
    if subscription is None:
        return False
    value = " ".join(str(subscription).strip().lower().split())
    blocked = {
        "ccm 2 partical series",
        "ccm 2 practical series",
    }
    return value in blocked

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

    if _is_ccm2_practical_series(getattr(user, "subscription", None)):
        logger.info("login blocked: subscription disabled for %s", email)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Login is disabled for this subscription.",
        )

    pwd = (request.password or "").strip()
    if pwd:
        if not password_matches_stored(user.password, pwd):
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
        canonical = php_password_for_db(pwd)
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


class SessionRefreshResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


@router.get("/session/check", response_model=SessionCheckResponse)
def session_check(_current_user: User = Depends(get_current_user)) -> SessionCheckResponse:
    """Lightweight poll — get_current_user already validates login_token vs JWT sid."""
    return SessionCheckResponse(valid=True)


@router.post("/session/refresh", response_model=SessionRefreshResponse)
def session_refresh(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> SessionRefreshResponse:
    """Issue a fresh JWT for the same device session.

    Accepts a recently expired token (grace window) so a long mock exam can keep
    saving answers without forcing a full re-login mid-test.
    """
    if not creds:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authorization token",
        )
    settings = get_settings()
    grace = max(0, int(settings.api_token_refresh_grace_hours)) * 3600
    payload = decode_access_token_for_refresh(creds.credentials, grace_seconds=grace)
    user_id = int(payload.get("uid", 0))
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User session not found",
        )
    assert_active_user_session(user, payload)
    ensure_user_batch_active(db, user)
    token = create_access_token(
        user_id=user.id,
        email=user.email or str(payload.get("email") or ""),
        session_id=str(payload.get("sid") or user.login_token or ""),
    )
    return SessionRefreshResponse(access_token=token)


class ForgotPasswordOtpRequest(BaseModel):
    email: EmailStr


class ResetPasswordOtpRequest(BaseModel):
    email: EmailStr
    otp: str = Field(min_length=4, max_length=8, pattern=r"^\d+$")
    password: str = Field(min_length=8, max_length=8)


@router.post("/forgot-password/request-otp")
def forgot_password_request_otp(
    body: ForgotPasswordOtpRequest,
    db: Session = Depends(get_db),
) -> dict:
    """Send a numeric OTP to approved accounts (no reset link)."""
    try:
        return request_password_reset_otp(db, str(body.email))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc


@router.post("/forgot-password/reset")
def forgot_password_reset_with_otp(
    body: ResetPasswordOtpRequest,
    db: Session = Depends(get_db),
) -> dict:
    """Verify OTP and set a new password (PHP-compatible encryption)."""
    try:
        return reset_password_with_otp(db, str(body.email), body.otp, body.password)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


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
