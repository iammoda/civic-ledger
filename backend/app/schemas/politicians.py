from __future__ import annotations

from pydantic import BaseModel

from app.schemas.common import CommitteeEventSummary, MembershipSummary


class CommitteeMembershipSummary(BaseModel):
    committee_slug: str
    committee_name: str
    role: str | None = None


class PoliticianListItem(BaseModel):
    slug: str
    full_name: str
    chamber: str | None = None
    image_url: str | None = None
    email: str | None = None
    current_membership: MembershipSummary | None = None


class PoliticianVoteStats(BaseModel):
    votes_attended_pct: float | None = None
    party_line_voting_pct: float | None = None
    free_vote_participation_pct: float | None = None
    votes_eligible: int | None = None
    votes_cast: int | None = None
    dissent_count: int | None = None


class PoliticianDetail(PoliticianListItem):
    bio_en: str | None = None
    bio_fr: str | None = None
    memberships: list[MembershipSummary] = []
    committees: list[CommitteeMembershipSummary] = []
    committee_events: list[CommitteeEventSummary] = []
    sponsored_bill_numbers: list[str] = []
    stats: PoliticianVoteStats | None = None
