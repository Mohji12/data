"""Configurable mock-test attempt limits (default, per-batch, per-user)."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session

from app.models import Option, User
from app.services.access import get_option_value

DEFAULT_MAX_ATTEMPTS = 2
OPTION_NAME = "mock_test_max_attempts_config"
MIN_ATTEMPTS = 1
MAX_ATTEMPTS = 50


def _clamp_attempts(value: int) -> int:
    return max(MIN_ATTEMPTS, min(MAX_ATTEMPTS, int(value)))


def _empty_config() -> dict[str, Any]:
    return {"default": DEFAULT_MAX_ATTEMPTS, "batches": {}, "users": {}}


def _normalize_config(raw: dict[str, Any]) -> dict[str, Any]:
    out = _empty_config()
    try:
        default = int(raw.get("default", DEFAULT_MAX_ATTEMPTS))
    except (TypeError, ValueError):
        default = DEFAULT_MAX_ATTEMPTS
    out["default"] = _clamp_attempts(default)

    batches_in = raw.get("batches") if isinstance(raw.get("batches"), dict) else {}
    users_in = raw.get("users") if isinstance(raw.get("users"), dict) else {}

    batches: dict[str, int] = {}
    for key, val in batches_in.items():
        name = str(key).strip()
        if not name:
            continue
        try:
            batches[name] = _clamp_attempts(int(val))
        except (TypeError, ValueError):
            continue

    users: dict[str, int] = {}
    for key, val in users_in.items():
        uid = str(key).strip()
        if not uid:
            continue
        try:
            users[uid] = _clamp_attempts(int(val))
        except (TypeError, ValueError):
            continue

    out["batches"] = batches
    out["users"] = users
    return out


def load_attempt_limits_config(db: Session) -> dict[str, Any]:
    raw = get_option_value(db, OPTION_NAME)
    if not raw:
        return _empty_config()
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return _empty_config()
    if not isinstance(parsed, dict):
        return _empty_config()
    return _normalize_config(parsed)


def save_attempt_limits_config(db: Session, config: dict[str, Any]) -> dict[str, Any]:
    normalized = _normalize_config(config)
    payload = json.dumps(normalized, separators=(",", ":"))
    row = db.query(Option).filter(Option.option_name == OPTION_NAME).first()
    if row:
        row.option_value = payload
    else:
        db.add(Option(option_name=OPTION_NAME, option_value=payload))
    db.commit()
    return normalized


def _batch_override_for_subscription(
    config: dict[str, Any], subscription: str | None
) -> int | None:
    sub = (subscription or "").strip()
    if not sub:
        return None
    batches: dict[str, int] = config.get("batches") or {}
    lowered = sub.lower()
    for name, limit in batches.items():
        if (name or "").strip().lower() == lowered:
            return int(limit)
    return None


def get_max_attempts_for_user(db: Session, user: User) -> int:
    config = load_attempt_limits_config(db)
    uid = str(user.id)
    users: dict[str, int] = config.get("users") or {}
    if uid in users:
        return int(users[uid])
    batch_limit = _batch_override_for_subscription(config, user.subscription)
    if batch_limit is not None:
        return batch_limit
    return int(config.get("default", DEFAULT_MAX_ATTEMPTS))


def describe_attempt_limits_for_user(db: Session, user: User) -> dict[str, Any]:
    config = load_attempt_limits_config(db)
    uid = str(user.id)
    users: dict[str, int] = config.get("users") or {}
    user_override = users.get(uid)
    batch_override = _batch_override_for_subscription(config, user.subscription)
    default = int(config.get("default", DEFAULT_MAX_ATTEMPTS))
    effective = get_max_attempts_for_user(db, user)
    return {
        "user_id": user.id,
        "default_max_attempts": default,
        "batch_override": batch_override,
        "user_override": user_override,
        "effective_max_attempts": effective,
        "subscription": user.subscription,
    }


def set_default_max_attempts(db: Session, value: int) -> dict[str, Any]:
    config = load_attempt_limits_config(db)
    config["default"] = _clamp_attempts(value)
    return save_attempt_limits_config(db, config)


def set_batch_max_attempts(db: Session, batch_name: str, value: int | None) -> dict[str, Any]:
    batch_name = (batch_name or "").strip()
    if not batch_name:
        raise ValueError("Batch name is required")
    config = load_attempt_limits_config(db)
    batches: dict[str, int] = dict(config.get("batches") or {})
    if value is None:
        batches = {k: v for k, v in batches.items() if k.strip().lower() != batch_name.lower()}
    else:
        # Preserve canonical casing from admin input
        batches = {k: v for k, v in batches.items() if k.strip().lower() != batch_name.lower()}
        batches[batch_name] = _clamp_attempts(value)
    config["batches"] = batches
    return save_attempt_limits_config(db, config)


def set_user_max_attempts(db: Session, user_id: int, value: int | None) -> dict[str, Any]:
    config = load_attempt_limits_config(db)
    users: dict[str, int] = dict(config.get("users") or {})
    key = str(user_id)
    if value is None:
        users.pop(key, None)
    else:
        users[key] = _clamp_attempts(value)
    config["users"] = users
    saved = save_attempt_limits_config(db, config)
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return {"config": saved, "user": None}
    return {"config": saved, "user": describe_attempt_limits_for_user(db, user)}
