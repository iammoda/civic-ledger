"""Shared retry/backoff for ingestion HTTP calls.

One transient 502 used to abort an entire multi-thousand-item sync run.
Retries cover transport errors, 429 and 5xx (with exponential backoff);
4xx responses are permanent and raise immediately.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

RETRYABLE_STATUS = {429, 500, 502, 503, 504}


async def get_with_retries(
    client: httpx.AsyncClient,
    url: str,
    *,
    params: dict[str, Any] | None = None,
    attempts: int = 3,
    base_delay: float = 1.5,
) -> httpx.Response:
    """GET with retries; returns a response that already passed raise_for_status."""
    last_exc: Exception | None = None
    for attempt in range(attempts):
        try:
            response = await client.get(url, params=params)
            if response.status_code in RETRYABLE_STATUS:
                response.raise_for_status()
            response.raise_for_status()
            return response
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code not in RETRYABLE_STATUS:
                raise  # Permanent (404, 403, ...): retrying won't help.
            last_exc = exc
        except httpx.TransportError as exc:
            last_exc = exc
        if attempt < attempts - 1:
            delay = base_delay * (2**attempt)
            logger.warning("GET %s failed (%s); retrying in %.1fs", url, type(last_exc).__name__, delay)
            await asyncio.sleep(delay)
    assert last_exc is not None
    raise last_exc
