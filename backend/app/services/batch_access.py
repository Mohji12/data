"""Batch activation checks (kept separate to avoid import cycles with auth/security)."""

from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import BatchMaster, User
from app.services.access import can_access_certificate, is_certificate_only_user


def _batch_status_is_active(status: object) -> bool:
    return str(status or "").strip() == "1"


def user_subscription_batch_active(db: Session, user: User) -> tuple[bool, str | None]:
    """
    True when the user's `subscription` matches an active row in batch_master (status=1).
    If the name is not in batch_master, allow access (legacy PHP-only batch names).
    """
    from app.services.cache import cache_get, cache_set

    sub = (user.subscription or "").strip()
    if not sub:
        return False, "No batch is assigned to your account."

    cache_key = f"batch:active:user:{int(user.id)}"
    cached = cache_get(cache_key)
    if isinstance(cached, dict) and "active" in cached:
        return bool(cached["active"]), cached.get("reason")

    row = (
        db.query(BatchMaster)
        .filter(func.lower(func.trim(BatchMaster.name)) == sub.lower())
        .order_by(BatchMaster.id.desc())
        .first()
    )
    if not row:
        result = (True, None)
        cache_set(cache_key, {"active": True, "reason": None}, ttl_sec=120)
        return result
    if _batch_status_is_active(row.status):
        result = (True, None)
        cache_set(cache_key, {"active": True, "reason": None}, ttl_sec=120)
        return result
    if is_certificate_only_user(db, user):
        ok, _ = can_access_certificate(db, user)
        if ok:
            result = (True, None)
            cache_set(cache_key, {"active": True, "reason": None}, ttl_sec=120)
            return result
    # Paid, approved enrollees keep login when batch is closed to new registration only.
    payment = str(getattr(user, "payment_status", None) or "").strip().lower()
    approved = str(getattr(user, "approve", None) or "").strip()
    if payment == "credit" and approved == "1":
        result = (True, None)
        cache_set(cache_key, {"active": True, "reason": None}, ttl_sec=120)
        return result
    reason = (
        f"The batch “{sub}” has been deactivated by the administrator. "
        "Login and dashboard access are not available."
    )
    result = (False, reason)
    cache_set(cache_key, {"active": False, "reason": reason}, ttl_sec=120)
    return result


def ensure_user_batch_active(db: Session, user: User) -> None:
    """Raise 403 when admin set batch_master.status to 0 for this user's subscription."""
    ok, reason = user_subscription_batch_active(db, user)
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=reason or "Your batch is not active.",
        )
