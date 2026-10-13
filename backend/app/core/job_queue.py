"""RQ job enqueue helpers."""

from __future__ import annotations

import logging
from typing import Any

from app.core.config import get_settings
from app.core.redis_client import redis_enabled
from app.core.redis_url import normalize_redis_url

logger = logging.getLogger(__name__)


def _rq_connection():
    import redis

    settings = get_settings()
    url = normalize_redis_url(settings.redis_url, force_tls=settings.redis_tls)
    return redis.Redis.from_url(
        url,
        decode_responses=False,
        socket_connect_timeout=settings.redis_socket_timeout_sec,
        socket_timeout=settings.redis_socket_timeout_sec,
    )


def enqueue_whatsapp_bulk(admin_id: int, payload_dict: dict[str, Any]):
    if not redis_enabled():
        return None
    try:
        from rq import Queue

        conn = _rq_connection()
        conn.ping()
        queue = Queue("whatsapp", connection=conn)
        return queue.enqueue(
            "app.jobs.whatsapp_bulk.run_whatsapp_bulk_job",
            admin_id,
            payload_dict,
            job_timeout=3600,
            result_ttl=86400,
        )
    except Exception as exc:
        logger.warning("Failed to enqueue WhatsApp bulk job: %s", exc)
        return None


def get_job_status(job_id: str) -> dict[str, Any] | None:
    if not redis_enabled():
        return None
    try:
        from rq.job import Job

        conn = _rq_connection()
        job = Job.fetch(job_id, connection=conn)
        return {
            "job_id": job.id,
            "status": job.get_status(),
            "result": job.result if job.is_finished else None,
            "exc_info": job.exc_info if job.is_failed else None,
        }
    except Exception:
        return None
