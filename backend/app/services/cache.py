"""JSON cache helpers backed by Redis (graceful no-op when disabled)."""

from __future__ import annotations

import json
from typing import Any, Callable, TypeVar

from app.core.config import get_settings
from app.core.redis_client import get_redis

T = TypeVar("T")


def cache_get(key: str) -> Any | None:
    client = get_redis()
    if client is None:
        return None
    try:
        raw = client.get(key)
        if raw is None:
            return None
        return json.loads(raw)
    except Exception:
        return None


def cache_set(key: str, value: Any, ttl_sec: int | None = None) -> None:
    client = get_redis()
    if client is None:
        return
    ttl = ttl_sec if ttl_sec is not None else get_settings().cache_default_ttl_sec
    try:
        client.setex(key, max(1, int(ttl)), json.dumps(value, default=str))
    except Exception:
        return


def cache_delete(key: str) -> None:
    client = get_redis()
    if client is None:
        return
    try:
        client.delete(key)
    except Exception:
        return


def cache_delete_prefix(prefix: str) -> None:
    client = get_redis()
    if client is None or not prefix:
        return
    try:
        cursor = 0
        while True:
            cursor, keys = client.scan(cursor=cursor, match=f"{prefix}*", count=200)
            if keys:
                client.delete(*keys)
            if cursor == 0:
                break
    except Exception:
        return


def cached_json(
    key: str,
    ttl_sec: int,
    builder: Callable[[], T],
) -> T:
    hit = cache_get(key)
    if hit is not None:
        return hit  # type: ignore[return-value]
    value = builder()
    cache_set(key, value, ttl_sec=ttl_sec)
    return value


def invalidate_option_cache(option_name: str | None = None) -> None:
    from app.services.access import clear_local_option_cache

    clear_local_option_cache(option_name)
    if option_name:
        cache_delete(f"opt:{option_name}")
    else:
        cache_delete_prefix("opt:")


def invalidate_batch_active_cache(user_id: int | None = None) -> None:
    if user_id is not None:
        cache_delete(f"batch:active:user:{int(user_id)}")
    else:
        cache_delete_prefix("batch:active:")
