from __future__ import annotations

from datetime import date

from pydantic import BaseModel


class PartyBreakdown(BaseModel):
    party_slug: str
    party_name: str | None = None
    yea: int = 0
    nay: int = 0
    paired: int = 0
    absent: int = 0
    disagreement_pct: float | None = None


class BallotItem(BaseModel):
    person_slug: str
    full_name: str
    party_slug: str | None = None
    ballot: str
    broke_party_line: bool = False


class VoteListItem(BaseModel):
    chamber: str
    session: str
    number: str
    occurred_on: date
    description_en: str
    result: str | None = None
    yea_total: int = 0
    nay_total: int = 0
    vote_type: str
    yea_effect: str | None = None
    plain_meaning_en: str | None = None


class VoteDetail(VoteListItem):
    related_bill_number: str | None = None
    source_url: str | None = None
    party_breakdown: list[PartyBreakdown] = []
    ballots: list[BallotItem] = []
