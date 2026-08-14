"""Best-effort Redis access with graceful degradation.

Used by inbound rate limiting and the Ask answer cache. When Redis is
unreachable (dev, tests), callers fall back to small in-process stores —
features keep working, they just don't share state across processes.

The availability check runs once per process: these are long-running
API/worker processes where Redis is expected up at start.
"""
from __future__ import annotations

_client = None
_checked = False


def redis_client():
    global _client, _checked
    if not _checked:
        _checked = True
        try:
            import redis

            from app.core.config import get_settings

            client = redis.Redis.from_url(
                get_settings().redis_url,
                socket_connect_timeout=0.5,
                socket_timeout=0.5,
                decode_responses=True,
            )
            client.ping()
            _client = client
        except Exception:
            _client = None
    return _client
