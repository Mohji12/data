from __future__ import annotations

import hashlib
import hmac
import logging
import re
import secrets
import time
from typing import NamedTuple

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import User
from app.services.password_crypto import php_password_for_db


def _user_is_approved(approve: object) -> bool:
    if approve is None:
        return False
    if isinstance(approve, bool):
        return approve
    if isinstance(approve, (int, float)):
        return int(approve) == 1
    return str(approve).strip() == "1"
from app.services.email_templates import password_reset_otp_template
from app.services.mailer import send_html_email

logger = logging.getLogger(__name__)

_TOKEN_PREFIX = "otp:v1:"
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class OtpPayload(NamedTuple):
    otp_hash: str
    expires_at: int
    issued_at: int


def _normalize_email(email: str) -> str:
    return email.strip().lower()


def _otp_hmac(email: str, otp: str) -> str:
    secret = (get_settings().api_token_secret or "critical-care-classes-fastapi-secret").encode()
    msg = f"{_normalize_email(email)}:{otp.strip()}".encode()
    return hmac.new(secret, msg, hashlib.sha256).hexdigest()


def _encode_token(payload: OtpPayload) -> str:
    return f"{_TOKEN_PREFIX}{payload.otp_hash}:{payload.expires_at}:{payload.issued_at}"


def _parse_token(raw: str | None) -> OtpPayload | None:
    if not raw or not str(raw).startswith(_TOKEN_PREFIX):
        return None
    parts = str(raw)[len(_TOKEN_PREFIX) :].split(":")
    if len(parts) != 3:
        return None
    try:
        return OtpPayload(otp_hash=parts[0], expires_at=int(parts[1]), issued_at=int(parts[2]))
    except ValueError:
        return None


def _generate_otp(length: int) -> str:
    return "".join(secrets.choice("0123456789") for _ in range(length))


def _find_eligible_user(db: Session, email: str) -> User | None:
    user = (
        db.query(User)
        .filter(func.lower(func.trim(User.email)) == _normalize_email(email))
        .first()
    )
    if not user or not _user_is_approved(getattr(user, "approve", None)):
        return None
    return user


def request_password_reset_otp(db: Session, email: str) -> dict:
    """
    Send a numeric OTP to approved users. Always returns the same message shape
    when the email format is valid (avoids account enumeration).
    """
    email = email.strip()
    if not email or not _EMAIL_RE.match(email):
        raise ValueError("Enter a valid email address.")

    settings = get_settings()
    if not settings.smtp_host:
        raise RuntimeError(
            "Password reset email is not configured. Contact support or try again later."
        )

    user = _find_eligible_user(db, email)
    now = int(time.time())
    cooldown = settings.password_reset_otp_resend_seconds
    ttl_seconds = settings.password_reset_otp_ttl_minutes * 60

    if user:
        existing = _parse_token(user.forgot_token)
        if existing and (now - existing.issued_at) < cooldown:
            wait = cooldown - (now - existing.issued_at)
            raise ValueError(f"Please wait {wait} seconds before requesting another code.")

        otp = _generate_otp(settings.password_reset_otp_length)
        payload = OtpPayload(
            otp_hash=_otp_hmac(email, otp),
            expires_at=now + ttl_seconds,
            issued_at=now,
        )
        user.forgot_token = _encode_token(payload)
        db.add(user)
        db.commit()

        try:
            html = password_reset_otp_template(
                user.name or "Learner",
                otp,
                settings.password_reset_otp_ttl_minutes,
            )
            send_html_email(
                user.email,
                "Your password reset code — Harish Critical Care Classes",
                html,
            )
        except Exception as exc:
            logger.exception("password reset OTP email failed for user_id=%s", user.id)
            user.forgot_token = None
            db.add(user)
            db.commit()
            raise RuntimeError("Could not send the verification email. Try again later.") from exc

    return {
        "message": "If this email is registered and approved, a verification code has been sent.",
    }


def reset_password_with_otp(db: Session, email: str, otp: str, new_password: str) -> dict:
    email = email.strip()
    otp = (otp or "").strip()
    new_password = new_password or ""

    if not email or not _EMAIL_RE.match(email):
        raise ValueError("Enter a valid email address.")
    if not re.fullmatch(r"\d{4,8}", otp):
        raise ValueError("Enter the verification code from your email.")
    if len(new_password) != 8:
        raise ValueError("Password must be exactly 8 characters.")

    user = _find_eligible_user(db, email)
    if not user:
        raise ValueError("Invalid email or verification code.")

    payload = _parse_token(user.forgot_token)
    now = int(time.time())
    if not payload or now > payload.expires_at:
        raise ValueError("Verification code expired. Request a new code.")

    expected = _otp_hmac(email, otp)
    if not hmac.compare_digest(payload.otp_hash, expected):
        raise ValueError("Invalid email or verification code.")

    user.password = php_password_for_db(new_password)
    user.forgot_token = None
    db.add(user)
    db.commit()

    return {"message": "Password updated successfully. You can sign in now."}
