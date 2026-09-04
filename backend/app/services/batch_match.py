"""Comma-separated batch matching (PHP FIND_IN_SET parity)."""

from __future__ import annotations

from sqlalchemy import func


def subscription_in_batch_csv(subscription: str | None, batch_csv: str | None) -> bool:
    sub = (subscription or "").strip()
    if not sub:
        return False
    parts = [p.strip() for p in (batch_csv or "").split(",") if p.strip()]
    sub_l = sub.lower()
    return any(p.lower() == sub_l for p in parts)


def find_in_set_sql(column, subscription: str):
    """SQLAlchemy expression: FIND_IN_SET(subscription, column) > 0.

    Normalizes ", " spacing in the CSV so tokens with accidental spaces still match
    (common cause of videos appearing missing for a batch).
    """
    sub = (subscription or "").strip()
    normalized = func.replace(func.replace(func.coalesce(column, ""), ", ", ","), " ,", ",")
    return func.find_in_set(sub, normalized) > 0


def normalize_batch_csv(batch_csv: str | None) -> str:
    """Collapse ', ' / ' ,' spacing for storage consistency."""
    parts = [p.strip() for p in (batch_csv or "").split(",") if p.strip()]
    return ",".join(parts)
