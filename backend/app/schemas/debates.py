from __future__ import annotations

from datetime import date
from typing import Any

from pydantic import BaseModel

from app.schemas.common import AnalysisState


class SpeechItem(BaseModel):
    sequence: int
    person_slug: str | None = None
    full_name: str | None = None
    heading_en: str | None = None
    topic_slug: str | None = None
    content_en: str


class DebateDetail(BaseModel):
    chamber: str
    occurred_on: date
    title_en: str | None = None
    source_url: str | None = None
    speeches: list[SpeechItem] = []
    analyses: list[AnalysisState] = []
    related_bills: list[dict[str, Any]] = []
