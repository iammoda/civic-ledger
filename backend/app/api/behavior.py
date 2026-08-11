"""Behavior endpoints: MP voting records with party context, comparison."""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.db.session import get_db
from app.models import (
    Ballot,
    Contribution,
    LegislatureSession,
    LobbyCommunication,
    Party,
    Person,
    PersonMembership,
    PersonStats,
    Vote,
)


router = APIRouter(tags=["behavior"])


class BallotRecord(BaseModel):
    vote_number: str
    session: str
    chamber: str
    occurred_on: date
    description_en: str
    plain_meaning_en: str | None = None
    ballot: str
    # What their ballot did to the matter: advanced | blocked | other | None
    ballot_effect: str | None = None
    result: str | None = None
    broke_party_line: bool
    # "With 118 of 119 voting Liberal MPs" / "One of 3 Liberal MPs to differ"
    party_context: str | None = None
    bill_number: str | None = None


class VotingRecordResponse(BaseModel):
    slug: str
    full_name: str
    total_ballots: int
    dissent_count: int
    items: list[BallotRecord]


def _ballot_effect(ballot: str, yea_effect: str | None) -> str | None:
    """Translate a raw ballot + motion direction into what the MP did."""
    if ballot not in {"yea", "nay"} or yea_effect not in {"advance", "block"}:
        return None
    if ballot == "yea":
        return "advanced" if yea_effect == "advance" else "blocked"
    return "blocked" if yea_effect == "advance" else "advanced"


def _party_context(
    party_counts: dict[tuple[int, str, str], int],
    vote_id: int,
    party_slug: str | None,
    ballot_value: str,
    party_label: str | None,
) -> str | None:
    if not party_slug or ballot_value not in {"yea", "nay"}:
        return None
    same = party_counts.get((vote_id, party_slug, ballot_value), 0)
    opposite = "nay" if ballot_value == "yea" else "yea"
    other = party_counts.get((vote_id, party_slug, opposite), 0)
    total_cast = same + other
    if total_cast < 2:
        return None
    label = party_label or party_slug
    if same <= other:
        return f"One of {same} {label} MPs to vote this way — {other} voted the other way"
    return f"With {same} of {total_cast} voting {label} MPs"


@router.get("/politicians/{slug}/votes", response_model=VotingRecordResponse)
def politician_votes(
    slug: str,
    dissent_only: bool = Query(default=False),
    limit: int = Query(default=25, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> VotingRecordResponse:
    person = db.scalar(select(Person).where(Person.slug == slug))
    if person is None:
        raise HTTPException(status_code=404, detail="Politician not found")

    base = select(Ballot).where(Ballot.person_id == person.id)
    total_ballots = db.scalar(select(func.count()).select_from(base.subquery())) or 0
    dissent_count = db.scalar(
        select(func.count()).select_from(
            base.where(Ballot.broke_party_line.is_(True)).subquery()
        )
    ) or 0

    query = base
    if dissent_only:
        query = query.where(Ballot.broke_party_line.is_(True))
    ballots = db.scalars(
        query.join(Vote, Ballot.vote_id == Vote.id)
        .options(
            selectinload(Ballot.vote).selectinload(Vote.session),
            selectinload(Ballot.vote).selectinload(Vote.chamber),
            selectinload(Ballot.vote).selectinload(Vote.bill),
        )
        .order_by(Vote.occurred_on.desc())
        .offset(offset)
        .limit(limit)
    ).all()

    # Party ballot counts for these votes, one grouped query.
    vote_ids = [b.vote_id for b in ballots]
    party_counts: dict[tuple[int, str, str], int] = {}
    if vote_ids:
        rows = db.execute(
            select(Ballot.vote_id, Ballot.party_slug, Ballot.ballot, func.count())
            .where(Ballot.vote_id.in_(vote_ids), Ballot.party_slug.is_not(None))
            .group_by(Ballot.vote_id, Ballot.party_slug, Ballot.ballot)
        ).all()
        for vote_id, party_slug, ballot_value, count in rows:
            party_counts[(vote_id, party_slug, ballot_value)] = count

    party_labels: dict[str, str] = {
        p_slug: short for p_slug, short in db.execute(select(Party.slug, Party.short_name)).all()
    }

    items = [
        BallotRecord(
            vote_number=b.vote.number,
            session=b.vote.session.label,
            chamber=b.vote.chamber.slug,
            occurred_on=b.vote.occurred_on,
            description_en=b.vote.description_en,
            plain_meaning_en=b.vote.plain_meaning_en,
            ballot=b.ballot,
            ballot_effect=_ballot_effect(b.ballot, b.vote.yea_effect),
            result=b.vote.result,
            broke_party_line=b.broke_party_line,
            party_context=_party_context(
                party_counts, b.vote_id, b.party_slug, b.ballot, party_labels.get(b.party_slug or "")
            ),
            bill_number=b.vote.bill.number if b.vote.bill else None,
        )
        for b in ballots
    ]

    return VotingRecordResponse(
        slug=person.slug,
        full_name=person.full_name,
        total_ballots=total_ballots,
        dissent_count=dissent_count,
        items=items,
    )


class ComparisonSide(BaseModel):
    slug: str
    full_name: str
    party: str | None = None
    riding: str | None = None
    attendance_pct: float | None = None
    party_line_pct: float | None = None
    dissent_count: int | None = None
    votes_cast: int | None = None
    lobbying_last_12mo: int
    donations_total: float


class CompareResponse(BaseModel):
    a: ComparisonSide
    b: ComparisonSide


def _comparison_side(db: Session, slug: str) -> ComparisonSide:
    person = db.scalar(
        select(Person)
        .where(Person.slug == slug)
        .options(selectinload(Person.memberships).selectinload(PersonMembership.party))
    )
    if person is None:
        raise HTTPException(status_code=404, detail=f"Politician not found: {slug}")

    current = next((m for m in person.memberships if m.is_current), None)
    stats = db.scalar(
        select(PersonStats)
        .join(LegislatureSession, PersonStats.session_id == LegislatureSession.id)
        .where(PersonStats.person_id == person.id)
        .order_by(
            LegislatureSession.parliament_number.desc(),
            LegislatureSession.session_number.desc(),
        )
        .limit(1)
    )
    from datetime import timedelta

    year_ago = date.today() - timedelta(days=365)
    lobbying = db.scalar(
        select(func.count())
        .select_from(LobbyCommunication)
        .where(LobbyCommunication.dpoh_person_id == person.id, LobbyCommunication.comm_date >= year_ago)
    ) or 0
    donations = db.scalar(
        select(func.coalesce(func.sum(Contribution.amount), 0.0)).where(
            Contribution.recipient_person_id == person.id
        )
    ) or 0.0

    return ComparisonSide(
        slug=person.slug,
        full_name=person.full_name,
        party=current.party.short_name if current and current.party else None,
        riding=current.riding_name if current else None,
        attendance_pct=stats.attendance_pct if stats else None,
        party_line_pct=stats.party_line_pct if stats else None,
        dissent_count=stats.dissent_count if stats else None,
        votes_cast=stats.votes_cast if stats else None,
        lobbying_last_12mo=lobbying,
        donations_total=float(donations),
    )


@router.get("/compare", response_model=CompareResponse)
def compare(a: str = Query(), b: str = Query(), db: Session = Depends(get_db)) -> CompareResponse:
    return CompareResponse(a=_comparison_side(db, a), b=_comparison_side(db, b))
