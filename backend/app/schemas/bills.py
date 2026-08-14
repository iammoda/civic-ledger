from __future__ import annotations

from datetime import date
from typing import Any

from pydantic import BaseModel

from app.schemas.common import AnalysisState, DataGap
from app.schemas.votes import VoteListItem


class BillDeathInfo(BaseModel):
    mechanism: str  # defeated_vote | died_committee | died_order_paper | ...
    stage: str | None = None
    occurred_on: date | None = None
    attribution_en: str | None = None
    # Link to the recorded division that killed it, when there was one.
    kill_vote_number: str | None = None
    kill_vote_chamber: str | None = None
    kill_vote_session: str | None = None


class DissenterItem(BaseModel):
    """An MP who broke party ranks on one of this bill's recorded votes."""

    person_slug: str
    full_name: str
    image_url: str | None = None
    party_slug: str | None = None
    ballot: str
    vote_number: str
    session: str
    chamber: str


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
    outcome: str = "pending"
    is_law: bool = False
    death: BillDeathInfo | None = None
    # Plain-language "what this bill is" (published AI summary), for lists.
    one_sentence: str | None = None


class BillDetail(BillListItem):
    # Machine-readable LEGISinfo status code, e.g. "HouseInCommittee".
    status_code: str | None = None
    legisinfo_url: str | None = None
    text_url: str | None = None
    # Human-written by the Library of Parliament — always attributed, no AI.
    official_summary_en: str | None = None
    topics: list[str] = []
    analyses: list[AnalysisState] = []
    related_votes: list[VoteListItem] = []
    sector_impacts: list[dict[str, Any]] = []
    omnibus_components: list[dict[str, Any]] = []
    dissenters: list[DissenterItem] = []
    data_gaps: list[DataGap] = []
