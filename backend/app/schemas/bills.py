from __future__ import annotations

from datetime import date
from typing import Any

from pydantic import BaseModel

from app.schemas.common import AnalysisState, DataGap
from app.schemas.votes import VoteListItem


class BillListItem(BaseModel):
    session: str
    chamber: str
    number: str
    title_en: str
    short_title_en: str | None = None
    status_en: str | None = None
    bill_type: str
    introduced_on: date | None = None
    sponsor_slug: str | None = None
    sponsor_name: str | None = None
    is_omnibus: bool = False


class BillDetail(BillListItem):
    legisinfo_url: str | None = None
    analyses: list[AnalysisState] = []
    related_votes: list[VoteListItem] = []
    sector_impacts: list[dict[str, Any]] = []
    omnibus_components: list[dict[str, Any]] = []
    data_gaps: list[DataGap] = []
