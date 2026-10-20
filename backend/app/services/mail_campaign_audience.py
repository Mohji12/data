"""Resolve campaign audiences from users, batches, or pasted lists."""

from __future__ import annotations

import json
import re
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import MailSuppression, User

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def normalize_email(email: str) -> str:
    return (email or "").strip().lower()


def is_valid_email(email: str) -> bool:
    return bool(_EMAIL_RE.match(normalize_email(email)))


def suppression_set(db: Session) -> set[str]:
    rows = db.query(MailSuppression.email).all()
    return {normalize_email(r[0]) for r in rows if r[0]}


def _eligible_user_query(db: Session):
    return db.query(User).filter(
        func.length(func.trim(User.email)) > 3,
        func.lower(func.coalesce(User.payment_status, "")) == "credit",
        User.approve == "1",
    )


def _row_to_recipient(user: User) -> dict[str, Any]:
    return {
        "user_id": user.id,
        "email": normalize_email(user.email or ""),
        "name": (user.name or "").strip(),
        "batch": (user.subscription or "").strip(),
    }


def parse_pasted_list(raw: str) -> tuple[list[dict[str, Any]], list[str], int]:
    """Return (accepted, invalid, duplicate_count)."""
    accepted: list[dict[str, Any]] = []
    invalid: list[str] = []
    seen: set[str] = set()
    dupes = 0
    text = (raw or "").replace("\r\n", "\n").replace(";", "\n")
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        if "\t" in line:
            groups = [[p.strip() for p in line.split("\t")]]
        else:
            tokens = [p.strip() for p in line.split(",") if p.strip()]
            if len(tokens) > 1 and all(is_valid_email(t) for t in tokens):
                groups = [[t] for t in tokens]
            else:
                groups = [tokens]
        for parts in groups:
            email = parts[0] if parts else ""
            if not email:
                continue
            if not is_valid_email(email):
                invalid.append(email)
                continue
            key = normalize_email(email)
            if key in seen:
                dupes += 1
                continue
            seen.add(key)
            name = parts[1] if len(parts) > 1 else ""
            batch = parts[2] if len(parts) > 2 else ""
            accepted.append({"user_id": None, "email": key, "name": name, "batch": batch})
    return accepted, invalid, dupes


def parse_audience_json(raw: str | None) -> dict[str, Any]:
    try:
        data = json.loads(raw or "{}")
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def resolve_audience(
    db: Session,
    audience_type: str,
    audience: dict[str, Any],
) -> dict[str, Any]:
    blocked = suppression_set(db)
    kind = (audience_type or "").strip().lower()
    recipients: list[dict[str, Any]] = []
    invalid: list[str] = []
    dupes = 0

    if kind == "all":
        for user in _eligible_user_query(db).all():
            rec = _row_to_recipient(user)
            if rec["email"] and rec["email"] not in blocked:
                recipients.append(rec)
    elif kind == "batch":
        names = audience.get("batches") or audience.get("batch_names") or []
        if isinstance(names, str):
            names = [names]
        wanted = {str(n).strip().lower() for n in names if str(n).strip()}
        for user in _eligible_user_query(db).all():
            sub = (user.subscription or "").strip().lower()
            if sub not in wanted:
                continue
            rec = _row_to_recipient(user)
            if rec["email"] and rec["email"] not in blocked:
                recipients.append(rec)
    elif kind == "list":
        pasted = str(audience.get("pasted") or audience.get("emails") or "")
        if isinstance(audience.get("recipients"), list):
            lines = []
            for item in audience["recipients"]:
                if isinstance(item, str):
                    lines.append(item)
                elif isinstance(item, dict):
                    lines.append(
                        "\t".join(
                            [
                                str(item.get("email") or ""),
                                str(item.get("name") or ""),
                                str(item.get("batch") or ""),
                            ]
                        )
                    )
            pasted = "\n".join(lines)
        accepted, invalid, dupes = parse_pasted_list(pasted)
        for rec in accepted:
            if rec["email"] in blocked:
                continue
            recipients.append(rec)
    else:
        raise ValueError("audience_type must be batch, all, or list")

    unique: list[dict[str, Any]] = []
    seen: set[str] = set()
    for rec in recipients:
        key = rec["email"]
        if key in seen:
            dupes += 1
            continue
        seen.add(key)
        unique.append(rec)

    return {
        "count": len(unique),
        "recipients": unique,
        "preview": unique[:20],
        "invalid": invalid[:50],
        "invalid_count": len(invalid),
        "duplicate_count": dupes,
        "suppressed_skipped": len(recipients) - len(unique) if False else 0,
    }
