from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel


class PageMeta(BaseModel):
    total: int
    limit: int
    offset: int


class PaginatedResponse(BaseModel):
    items: list[Any]
    meta: PageMeta


class PartySummary(BaseModel):
    name: str
    short_name: str
    slug: str
    color: str | None = None


class MembershipSummary(BaseModel):
    party: PartySummary | None = None
    riding_name: str | None = None
    region_name: str | None = None
    province_code: str | None = None
    role_title: str | None = None
    is_current: bool = True
    started_on: date | None = None
    ended_on: date | None = None


class DataGap(BaseModel):
    code: str
    label: str
    detail: str


class AnalysisState(BaseModel):
    analysis_type: str
    status: str
    confidence_score: float | None = None
    blocked_reason: str | None = None
    citations: list[dict[str, Any]] | None = None
    payload: dict[str, Any] | None = None


class CommitteeEventSummary(BaseModel):
    event_type: str
    title_en: str
    occurred_at: datetime | None = None
    source_url: str | None = None
