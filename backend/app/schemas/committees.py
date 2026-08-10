from __future__ import annotations

from pydantic import BaseModel

from app.schemas.common import CommitteeEventSummary


class CommitteeMember(BaseModel):
    person_slug: str
    full_name: str
    role: str | None = None
    party_slug: str | None = None


class CommitteeListItem(BaseModel):
    slug: str
    name_en: str
    chamber: str | None = None


class CommitteeDetail(CommitteeListItem):
    source_url: str | None = None
    members: list[CommitteeMember] = []
    events: list[CommitteeEventSummary] = []
