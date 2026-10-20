"""Shared Redis connection for cache, rate limits, and RQ."""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING

from app.core.config import get_settings
from app.core.redis_url import normalize_redis_url

if TYPE_CHECKING:
    import redis

logger = logging.getLogger(__name__)

_client: redis.Redis | None = None
_circuit_open_until: float = 0.0
_CIRCUIT_COOLDOWN_SEC = 30.0


def redis_enabled() -> bool:
    return get_settings().redis_enabled


def mark_redis_failure(exc: Exception | None = None) -> None:
    """Skip Redis briefly after a timeout so API workers are not blocked."""
    global _client, _circuit_open_until
    _client = None
    _circuit_open_until = time.monotonic() + _CIRCUIT_COOLDOWN_SEC
    if exc is not None:
        logger.warning("Redis unavailable, skipping for %ss: %s", int(_CIRCUIT_COOLDOWN_SEC), exc)


def get_redis() -> redis.Redis | None:
    """Return a shared Redis client, or None if disabled, circuit-open, or unreachable."""
    global _client
    if not redis_enabled():
        return None
    if time.monotonic() < _circuit_open_until:
        return None
    if _client is not None:
        return _client
    try:
        import redis as redis_lib

        settings = get_settings()
        timeout = float(settings.redis_socket_timeout_sec)
        url = normalize_redis_url(settings.redis_url, force_tls=settings.redis_tls)
        _client = redis_lib.Redis.from_url(
            url,
            decode_responses=True,
            socket_connect_timeout=timeout,
            socket_timeout=timeout,
            health_check_interval=30,
            retry_on_timeout=False,
        )
        _client.ping()
        return _client
    except Exception as exc:
        mark_redis_failure(exc)
        return None


def redis_health() -> str:
    if not redis_enabled():
        return "disabled"
    if time.monotonic() < _circuit_open_until:
        return "down"
    client = get_redis()
    if client is None:
        return "down"
    try:
        client.ping()
        return "ok"
    except Exception as exc:
        mark_redis_failure(exc)
        return "down"


def reset_redis_client_for_tests() -> None:
    global _client, _circuit_open_until
    _client = None
    _circuit_open_until = 0.0
