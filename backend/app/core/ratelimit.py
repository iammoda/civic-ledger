"""Inbound rate limiting for endpoints that cost money or accept public writes.

Fixed-window counters per client IP: Redis (INCR + EXPIRE — atomic across
processes) when available, an in-process fallback otherwise. The platform is
anonymous by design, so the client IP is the only identity we have.

Note on X-Forwarded-For: we trust the first hop, which is correct behind a
single reverse proxy (Vercel/Fly/Railway). If the API is ever exposed
directly, a client could spoof the header — keep it behind a proxy.
"""
from __future__ import annotations

import threading
import time

from fastapi import HTTPException, Request

from app.core.config import get_settings
from app.core.kv import redis_client

_lock = threading.Lock()
_local: dict[str, tuple[int, int]] = {}  # key -> (window_id, count)


def _hit(key: str, limit: int, window_seconds: int) -> bool:
    """Count one hit against key; True while within the limit."""
    window = int(time.time() // window_seconds)
    r = redis_client()
    if r is not None:
        try:
            bucket = f"rl:{key}:{window}"
            count = r.incr(bucket)
            if int(count) == 1:
                r.expire(bucket, window_seconds + 1)
            return int(count) <= limit
        except Exception:
            pass  # Redis hiccup: fall through to the local counter.
    with _lock:
        if len(_local) > 10_000:  # bound memory under IP churn
            _local.clear()
        window_id, count = _local.get(key, (window, 0))
        if window_id != window:
            count = 0
        count += 1
        _local[key] = (window, count)
        return count <= limit


def within_quota(name: str, *, limit: int, window_seconds: int) -> bool:
    """Global (not per-IP) quota — e.g. the daily cap on generated Ask answers."""
    if not get_settings().rate_limit_enabled:
        return True
    return _hit(f"g:{name}", limit, window_seconds)


def client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def rate_limit(name: str, *, limit: int, window_seconds: int):
    """FastAPI dependency: 429 once a client IP exceeds limit per window."""

    def dependency(request: Request) -> None:
        if not get_settings().rate_limit_enabled:
            return
        if not _hit(f"{name}:{client_ip(request)}", limit, window_seconds):
            raise HTTPException(
                status_code=429,
                detail="Too many requests — please wait a moment and try again.",
                headers={"Retry-After": str(window_seconds)},
            )

    return dependency
