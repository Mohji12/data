"""Redis sliding-window rate limits (no-op when Redis disabled)."""

from __future__ import annotations

from fastapi import HTTPException, Request, status

from app.core.config import get_settings
from app.core.redis_client import get_redis, mark_redis_failure


def client_ip(request: Request) -> str:
    """Client IP; uses first X-Forwarded-For hop when behind nginx on EC2."""
    forwarded = (request.headers.get("x-forwarded-for") or "").strip()
    if forwarded:
        return forwarded.split(",")[0].strip() or "unknown"
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


def _check_limit(key: str, limit: int, window_sec: int) -> bool:
    """Return True if request is allowed."""
    client = get_redis()
    if client is None:
        return True
    try:
        count = client.incr(key)
        if count == 1:
            client.expire(key, window_sec)
        return int(count) <= limit
    except Exception as exc:
        mark_redis_failure(exc)
        return True


def enforce_rate_limit(key: str, limit: int, window_sec: int, detail: str) -> None:
    if not _check_limit(key, limit, window_sec):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=detail,
        )


def enforce_login_rate_limit(request: Request) -> None:
    settings = get_settings()
    ip = client_ip(request)
    enforce_rate_limit(
        f"rl:login:ip:{ip}",
        settings.rate_limit_login_per_min,
        60,
        "Too many login attempts. Please wait a minute and try again.",
    )


def enforce_otp_request_rate_limit(email: str) -> None:
    settings = get_settings()
    norm = email.strip().lower()
    enforce_rate_limit(
        f"rl:otp:email:{norm}",
        settings.rate_limit_otp_per_hour,
        3600,
        "Too many password reset requests for this email. Try again later.",
    )


def enforce_otp_verify_rate_limit(request: Request) -> None:
    settings = get_settings()
    ip = client_ip(request)
    enforce_rate_limit(
        f"rl:otp:verify:ip:{ip}",
        settings.rate_limit_otp_verify_per_min,
        60,
        "Too many verification attempts. Please wait and try again.",
    )
