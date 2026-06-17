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
    sub = (user.subscription or "").strip()
    if not sub:
        return False, "No batch is assigned to your account."

    row = (
        db.query(BatchMaster)
        .filter(func.lower(func.trim(BatchMaster.name)) == sub.lower())
        .order_by(BatchMaster.id.desc())
        .first()
    )
    if not row:
        return True, None
    if _batch_status_is_active(row.status):
        return True, None
    if is_certificate_only_user(db, user):
        ok, _ = can_access_certificate(db, user)
        if ok:
            return True, None
    # Paid, approved enrollees keep login when batch is closed to new registration only.
    payment = str(getattr(user, "payment_status", None) or "").strip().lower()
    approved = str(getattr(user, "approve", None) or "").strip()
    if payment == "credit" and approved == "1":
        return True, None
    return (
        False,
        f"The batch “{sub}” has been deactivated by the administrator. Login and dashboard access are not available.",
    )


def ensure_user_batch_active(db: Session, user: User) -> None:
    """Raise 403 when admin set batch_master.status to 0 for this user's subscription."""
    ok, reason = user_subscription_batch_active(db, user)
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=reason or "Your batch is not active.",
        )
