"""Shared Redis connection for cache, rate limits, and RQ."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from app.core.config import get_settings
from app.core.redis_url import normalize_redis_url

if TYPE_CHECKING:
    import redis

logger = logging.getLogger(__name__)

_client: redis.Redis | None = None
_client_checked: bool = False
_client_ok: bool = False


def redis_enabled() -> bool:
    return get_settings().redis_enabled


def get_redis() -> redis.Redis | None:
    """Return a shared Redis client, or None if disabled or unreachable."""
    global _client, _client_checked, _client_ok
    if not redis_enabled():
        return None
    if _client_checked and not _client_ok:
        return None
    if _client is not None:
        return _client
    try:
        import redis as redis_lib

        settings = get_settings()
        url = normalize_redis_url(settings.redis_url, force_tls=settings.redis_tls)
        _client = redis_lib.Redis.from_url(
            url,
            decode_responses=True,
            socket_connect_timeout=settings.redis_socket_timeout_sec,
            socket_timeout=settings.redis_socket_timeout_sec,
        )
        _client.ping()
        _client_ok = True
        _client_checked = True
        return _client
    except Exception as exc:
        logger.warning("Redis unavailable: %s", exc)
        _client = None
        _client_ok = False
        _client_checked = True
        return None


def redis_health() -> str:
    if not redis_enabled():
        return "disabled"
    client = get_redis()
    if client is None:
        return "down"
    try:
        client.ping()
        return "ok"
    except Exception:
        return "down"


def reset_redis_client_for_tests() -> None:
    global _client, _client_checked, _client_ok
    _client = None
    _client_checked = False
    _client_ok = False
