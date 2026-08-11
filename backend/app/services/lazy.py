"""Lazy-analysis engine: analysis is generated on first view, cached forever.

The API enqueues arq jobs fire-and-forget; if Redis is down the page still
renders (the analysis stays a Data Gap until a worker picks it up later).
"""
from __future__ import annotations

import logging

from arq import create_pool
from arq.connections import ArqRedis, RedisSettings

from app.core.config import get_settings

logger = logging.getLogger(__name__)

_pool: ArqRedis | None = None


async def _get_pool() -> ArqRedis | None:
    global _pool
    if _pool is None:
        try:
            settings = RedisSettings.from_dsn(get_settings().redis_url)
            # Fail fast: a page view must never hang on Redis retries.
            settings.conn_retries = 1
            settings.conn_retry_delay = 0
            _pool = await create_pool(settings)
        except Exception as exc:  # noqa: BLE001 — Redis-down must not break pages
            logger.warning("arq pool unavailable: %s", exc)
            return None
    return _pool


async def enqueue(job_name: str, *args: object) -> bool:
    """Fire-and-forget enqueue. Returns False when Redis is unreachable.

    _job_id dedupes: repeated views of the same bill enqueue one job.
    """
    pool = await _get_pool()
    if pool is None:
        return False
    try:
        job_id = f"{job_name}:{':'.join(str(a) for a in args)}"
        await pool.enqueue_job(job_name, *args, _job_id=job_id)
        return True
    except Exception as exc:  # noqa: BLE001 — lazy path must never break a page view
        logger.warning("enqueue %s failed: %s", job_name, exc)
        return False
