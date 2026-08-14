from __future__ import annotations

import asyncio
from typing import Any

import httpx
from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.ingestion.http_retry import get_with_retries


settings = get_settings()


class Pagination(BaseModel):
    next_url: str | None = None
    offset: int = 0
    limit: int = 0


class OpenParliamentPage(BaseModel):
    # The API nests pagination under a "pagination" key.
    pagination: Pagination = Field(default_factory=Pagination)
    objects: list[dict[str, Any]] = Field(default_factory=list)


class OpenParliamentClient:
    base_url = "https://api.openparliament.ca"

    def __init__(self, rate_limit_seconds: float = 0.6) -> None:
        self._rate_limit_seconds = rate_limit_seconds
        self._headers = {
            "User-Agent": settings.ingestion_user_agent,
            "Accept": "application/json",
        }
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> "OpenParliamentClient":
        self._client = httpx.AsyncClient(base_url=self.base_url, headers=self._headers, timeout=30.0)
        return self

    async def __aexit__(self, *exc: object) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def _get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        if self._client is None:
            raise RuntimeError("Client not started; use 'async with OpenParliamentClient() as client'")
        # next_url already carries its full query string — appending params
        # again duplicates keys and breaks the API's offset handling.
        if "?" in path:
            merged: dict[str, Any] | None = dict(params) if params else None
        else:
            merged = {"format": "json", **(params or {})}
        # Retries: a single transient 502 must not abort a multi-thousand-item
        # sync run mid-way.
        response = await get_with_retries(self._client, path, params=merged)
        await asyncio.sleep(self._rate_limit_seconds)
        return response.json()

    async def fetch_detail(self, path: str) -> dict[str, Any]:
        """Fetch a single object, e.g. /politicians/some-slug/ or /votes/45-1/173/."""
        return await self._get(path)

    async def fetch_page(self, path: str, params: dict[str, Any] | None = None) -> OpenParliamentPage:
        return OpenParliamentPage.model_validate(await self._get(path, params=params))

    async def paginate(
        self,
        path: str,
        params: dict[str, Any] | None = None,
        *,
        max_pages: int | None = None,
    ) -> list[dict[str, Any]]:
        """Collect all objects, following nested pagination.next_url."""
        items: list[dict[str, Any]] = []
        pages = 0
        current_path: str | None = path
        current_params = params
        while current_path:
            page = await self.fetch_page(current_path, params=current_params)
            items.extend(page.objects)
            pages += 1
            if max_pages is not None and pages >= max_pages:
                break
            # next_url already carries the query string.
            current_path = page.pagination.next_url
            current_params = None
        return items

    async def iter_pages(
        self,
        path: str,
        params: dict[str, Any] | None = None,
    ):
        """Async generator of pages, for early-exit incremental syncs."""
        current_path: str | None = path
        current_params = params
        while current_path:
            page = await self.fetch_page(current_path, params=current_params)
            yield page.objects
            current_path = page.pagination.next_url
            current_params = None
