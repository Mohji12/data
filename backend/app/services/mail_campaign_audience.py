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


def suppression_map(db: Session) -> dict[str, MailSuppression]:
    rows = db.query(MailSuppression).all()
    return {normalize_email(r.email): r for r in rows if r.email}


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


def parse_pasted_list(
    raw: str,
    extra_map: dict[str, int] | None = None,
) -> tuple[list[dict[str, Any]], list[str], int]:
    """Return (accepted, invalid, duplicate_count). extra_map stores extra copies per email."""
    accepted: list[dict[str, Any]] = []
    invalid: list[str] = []
    seen: set[str] = set()
    extras = extra_map if extra_map is not None else {}
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
                extras[key] = extras.get(key, 0) + 1
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


def _raw_candidates(
    db: Session,
    audience_type: str,
    audience: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[str], int, dict[str, int]]:
    kind = (audience_type or "").strip().lower()
    invalid: list[str] = []
    dupes = 0
    extra_map: dict[str, int] = {}
    if kind == "all":
        rows = [_row_to_recipient(user) for user in _eligible_user_query(db).all() if (user.email or "").strip()]
        return rows, invalid, dupes, extra_map
    if kind == "batch":
        names = audience.get("batches") or audience.get("batch_names") or []
        if isinstance(names, str):
            names = [names]
        wanted = {str(n).strip().lower() for n in names if str(n).strip()}
        rows = []
        for user in _eligible_user_query(db).all():
            sub = (user.subscription or "").strip().lower()
            if sub not in wanted:
                continue
            rec = _row_to_recipient(user)
            if rec["email"]:
                rows.append(rec)
        return rows, invalid, dupes, extra_map
    if kind == "list":
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
        accepted, invalid, dupes = parse_pasted_list(pasted, extra_map)
        return accepted, invalid, dupes, extra_map
    raise ValueError("audience_type must be batch, all, or list")


def resolve_audience(
    db: Session,
    audience_type: str,
    audience: dict[str, Any],
    *,
    skip_previously_bounced: bool = True,
    exclude_emails: list[str] | None = None,
    check_dns: bool = False,
) -> dict[str, Any]:
    from app.services.mail_campaign_validate import classify_address
    from app.services.mail_suppression import should_skip_send

    raw, parsed_invalid, dupes, extra_map = _raw_candidates(db, audience_type, audience)
    blocked = suppression_map(db)
    excluded = {normalize_email(e) for e in (exclude_emails or audience.get("exclude_emails") or []) if e}
    unique: list[dict[str, Any]] = []
    seen: set[str] = set()
    invalid = list(parsed_invalid)
    unverified: list[str] = []
    disposable: list[str] = []
    previously_bounced: list[str] = []
    unsubscribed: list[str] = []
    complaints: list[str] = []
    role_warnings: list[str] = []
    flagged: list[dict[str, Any]] = []
    eligible: list[dict[str, Any]] = []

    for rec in raw:
        key = normalize_email(rec.get("email") or "")
        if not key:
            continue
        if key in seen:
            extra_map[key] = extra_map.get(key, 0) + 1
            dupes += 1
            continue
        seen.add(key)
        rec = {**rec, "email": key}
        unique.append(rec)
        classified = classify_address(key, check_dns=check_dns)
        rec["flag"] = classified.get("flag") or ""
        rec["dns_status"] = classified.get("dns_status")
        rec["role_warning"] = bool(classified.get("role_warning"))
        supp = blocked.get(key)
        skip = should_skip_send(supp, skip_previously_bounced)
        if key in excluded:
            rec["flag"] = rec["flag"] or "excluded"
            flagged.append(rec)
            continue
        if not classified["syntax_ok"] or classified.get("flag") == "invalid":
            invalid.append(key)
            rec["flag"] = "invalid"
            flagged.append(rec)
            continue
        if classified.get("disposable"):
            disposable.append(key)
            rec["flag"] = "disposable"
            flagged.append(rec)
            continue
        if supp:
            reason = (supp.reason or "").strip().lower()
            rec["suppression_reason"] = reason
            if reason == "unsubscribe":
                unsubscribed.append(key)
                rec["flag"] = "unsubscribed"
                flagged.append(rec)
                continue
            if reason == "complaint":
                complaints.append(key)
                rec["flag"] = "complaint"
                flagged.append(rec)
                continue
            if reason == "hard_bounce" or (skip and reason == "soft_bounce"):
                previously_bounced.append(key)
                rec["flag"] = "previously_bounced"
                flagged.append(rec)
                continue
            if skip:
                rec["flag"] = reason or "suppressed"
                flagged.append(rec)
                continue
        if classified.get("dns_status") == "unverified":
            unverified.append(key)
            rec["flag"] = "unverified"
        if classified.get("role_warning"):
            role_warnings.append(key)
        eligible.append(rec)

    duplicate_emails = [
        {"email": email, "extra": extra, "total": extra + 1}
        for email, extra in sorted(extra_map.items(), key=lambda item: (-item[1], item[0]))
    ]
    snapshot = {
        "eligible": len(eligible),
        "invalid": len(invalid),
        "unverified": len(unverified),
        "previously_bounced": len(previously_bounced),
        "disposable": len(disposable),
        "unsubscribed": len(unsubscribed),
        "complaints": len(complaints),
        "role_warnings": len(role_warnings),
        "duplicate_count": dupes,
        "duplicate_address_count": len(extra_map),
        "excluded": len(excluded),
        "skip_previously_bounced": skip_previously_bounced,
        "exclude_emails": sorted(excluded),
    }
    return {
        "count": len(eligible),
        "recipients": eligible,
        "preview": eligible[:20] + flagged[:20],
        "invalid": invalid[:50],
        "invalid_count": len(invalid),
        "duplicate_count": dupes,
        "duplicate_address_count": len(extra_map),
        "duplicate_emails": duplicate_emails[:50],
        "unverified": unverified[:50],
        "unverified_count": len(unverified),
        "previously_bounced": previously_bounced[:50],
        "previously_bounced_count": len(previously_bounced),
        "disposable": disposable[:50],
        "disposable_count": len(disposable),
        "unsubscribed": unsubscribed[:50],
        "unsubscribed_count": len(unsubscribed),
        "complaints": complaints[:50],
        "complaints_count": len(complaints),
        "role_warnings": role_warnings[:50],
        "role_warning_count": len(role_warnings),
        "flagged": flagged[:50],
        "snapshot": snapshot,
        "suppressed_skipped": len(unique) - len(eligible),
    }
