"""Normalize Redis URLs (Upstash and other TLS endpoints)."""

from __future__ import annotations

from urllib.parse import urlparse, urlunparse


def normalize_redis_url(url: str, *, force_tls: bool = False) -> str:
    """
    Return a URL suitable for redis-py.

    Upstash: use ``rediss://`` (TLS). If you copy ``redis://`` from the Upstash UI,
    we upgrade automatically when the host is ``*.upstash.io``.
    """
    raw = (url or "").strip()
    if not raw:
        return raw

    parsed = urlparse(raw)
    scheme = (parsed.scheme or "redis").lower()
    host = (parsed.hostname or "").lower()

    use_tls = force_tls or scheme == "rediss" or host.endswith(".upstash.io")
    if use_tls and scheme == "redis":
        scheme = "rediss"

    if parsed.port:
        netloc = parsed.netloc
    else:
        # Preserve user:pass@host when port omitted
        netloc = parsed.netloc

    return urlunparse((scheme, netloc, parsed.path or "", parsed.params, parsed.query, parsed.fragment))
