"""Admin assistant. Answers from dashboard totals and a narrow user lookup.

Requires an authenticated admin. Counts are one database round trip.
"""

from __future__ import annotations

import time

from sqlalchemy import func, or_, text
from sqlalchemy.orm import Session

from app.models import Admin, User
from app.services.course_hierarchy import describe_batch, list_batches, match_batch_name

SUGGESTIONS = [
    "Show batches and packages",
    "Show dashboard totals",
    "How many active users?",
    "What is the revenue?",
]

_CACHE_SECONDS = 30.0
_totals_cache: tuple[float, dict] | None = None


def _totals(db: Session) -> dict:
    global _totals_cache
    now = time.monotonic()
    if _totals_cache and now - _totals_cache[0] < _CACHE_SECONDS:
        return _totals_cache[1]
    row = db.execute(
        text(
            """
            SELECT
              (SELECT COUNT(*) FROM users) AS total_users,
              (SELECT COUNT(*) FROM users WHERE LOWER(COALESCE(payment_status, '')) = 'credit') AS active_users,
              (SELECT COALESCE(SUM(total_amount), 0) FROM users WHERE LOWER(COALESCE(payment_status, '')) = 'credit') AS revenue,
              (SELECT COUNT(*) FROM videos) AS total_videos,
              (SELECT COUNT(*) FROM video_question) AS pending_questions
            """
        )
    ).one()
    data = {
        "total_users": int(row.total_users or 0),
        "active_users": int(row.active_users or 0),
        "revenue": float(row.revenue or 0),
        "total_videos": int(row.total_videos or 0),
        "pending_questions": int(row.pending_questions or 0),
    }
    _totals_cache = (now, data)
    return data


def _money(amount: float) -> str:
    return f"₹{amount:,.0f}"


def _overview(admin: Admin, totals: dict) -> str:
    name = (admin.name or admin.username or "Admin").strip()
    return "\n".join(
        [
            f"Hello {name}. These figures are from the database.",
            f"Total users: {totals['total_users']}.",
            f"Active paid users: {totals['active_users']}.",
            f"Revenue: {_money(totals['revenue'])}.",
            f"Videos: {totals['total_videos']}.",
            f"Video questions: {totals['pending_questions']}.",
        ]
    )


def _lookup_users(db: Session, text: str) -> str | None:
    raw = text.strip()
    if "@" not in raw and not raw.startswith("user ") and "student " not in raw:
        return None
    needle = raw
    for prefix in ("find user ", "find student ", "user ", "student ", "search "):
        if needle.startswith(prefix):
            needle = needle[len(prefix) :].strip()
    if len(needle) < 3:
        return None
    like = f"%{needle}%"
    rows = (
        db.query(User.name, User.email, User.subscription, User.payment_status)
        .filter(or_(func.lower(User.email).like(like.lower()), func.lower(User.name).like(like.lower())))
        .order_by(User.id.desc())
        .limit(5)
        .all()
    )
    if not rows:
        return f"No user matched “{needle}”."
    lines = [f"Matching users for “{needle}”:"]
    for name, email, subscription, payment in rows:
        lines.append(
            f"- {name or 'Unnamed'} ({email}), course {subscription or 'not set'}, payment {payment or 'unknown'}."
        )
    return "\n".join(lines)


def answer_admin(db: Session, admin: Admin, message: str) -> dict:
    text = " ".join((message or "").split()).strip().lower()
    if not text or text in {"hi", "hello", "hey", "help"}:
        name = (admin.name or admin.username or "Admin").strip()
        reply = (
            f"Hello {name}. Ask for a batch, for example “Batch 15”, to see every learner and package "
            "for that batch, or ask for totals and revenue."
        )
    elif (named := match_batch_name(db, text)):
        reply = describe_batch(db, named, for_admin=True)
    elif (found := _lookup_users(db, text)):
        reply = found
    elif any(word in text for word in ("batch", "package", "hierarch", "module", "folder", "detail", "specific")):
        reply = list_batches(db)
    else:
        totals = _totals(db)
        if any(word in text for word in ("revenue", "payment", "money", "amount")):
            reply = f"Recorded revenue from paid users is {_money(totals['revenue'])}."
        elif any(word in text for word in ("active",)):
            reply = f"Active paid users: {totals['active_users']} of {totals['total_users']} total users."
        elif any(word in text for word in ("video", "question")):
            reply = f"Videos: {totals['total_videos']}. Video questions stored: {totals['pending_questions']}."
        elif any(word in text for word in ("user", "student", "registration")):
            reply = f"Total users: {totals['total_users']}. Active paid users: {totals['active_users']}."
        else:
            reply = _overview(admin, totals)
    return {"reply": reply, "suggestions": SUGGESTIONS}
