from __future__ import annotations

import asyncio

import httpx

from app.core.config import get_settings


settings = get_settings()


class SenateClient:
    """Initial adapter point for official Senate/Parliament sources."""

    def __init__(self, base_url: str = "https://sencanada.ca", rate_limit_seconds: float = 0.6) -> None:
        self.base_url = base_url
        self._rate_limit_seconds = rate_limit_seconds
        self._headers = {"User-Agent": settings.ingestion_user_agent}

    async def fetch(self, path: str) -> str:
        async with httpx.AsyncClient(base_url=self.base_url, headers=self._headers, timeout=30.0) as client:
            response = await client.get(path)
            response.raise_for_status()
            await asyncio.sleep(self._rate_limit_seconds)
            return response.text
