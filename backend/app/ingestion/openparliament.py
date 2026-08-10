from __future__ import annotations

import asyncio
from typing import Any

import httpx
from pydantic import BaseModel, Field

from app.core.config import get_settings


settings = get_settings()


class OpenParliamentPage(BaseModel):
    next_url: str | None = Field(default=None, alias="next")
    objects: list[dict[str, Any]] = Field(default_factory=list)


class OpenParliamentClient:
    base_url = "https://api.openparliament.ca"

    def __init__(self, rate_limit_seconds: float = 0.6) -> None:
        self._rate_limit_seconds = rate_limit_seconds
        self._headers = {"User-Agent": settings.ingestion_user_agent}

    async def fetch_page(self, path: str, params: dict[str, Any] | None = None) -> OpenParliamentPage:
        async with httpx.AsyncClient(base_url=self.base_url, headers=self._headers, timeout=30.0) as client:
            response = await client.get(path, params=params)
            response.raise_for_status()
            await asyncio.sleep(self._rate_limit_seconds)
            return OpenParliamentPage.model_validate(response.json())

    async def paginate(self, path: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        current_path = path
        current_params = params
        while current_path:
            page = await self.fetch_page(current_path, params=current_params)
            items.extend(page.objects)
            current_path = page.next_url
            current_params = None
        return items
