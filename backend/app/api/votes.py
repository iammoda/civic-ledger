from __future__ import annotations

from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.db.session import get_db
from app.models import Ballot, Chamber, LegislatureSession, Party, Vote
from app.schemas.common import PageMeta
from app.schemas.votes import BallotItem, PartyBreakdown, VoteDetail, VoteListItem


router = APIRouter(prefix="/votes", tags=["votes"])


@router.get("")
def list_votes(
    chamber: str | None = None,
    result: str | None = None,
    limit: int = Query(default=25, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> dict:
    query = select(Vote)
    if chamber:
        query = query.join(Chamber, Vote.chamber_id == Chamber.id).where(Chamber.slug == chamber)
    if result:
        query = query.where(Vote.result == result)

    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    votes = db.scalars(
        query.options(selectinload(Vote.chamber), selectinload(Vote.session))
        .order_by(Vote.occurred_on.desc())
        .offset(offset)
        .limit(limit)
    ).all()

    items = [
        VoteListItem(
            chamber=vote.chamber.slug,
            session=vote.session.label,
            number=vote.number,
            occurred_on=vote.occurred_on,
            description_en=vote.description_en,
            result=vote.result,
            yea_total=vote.yea_total,
            nay_total=vote.nay_total,
            vote_type=vote.vote_type,
        )
        for vote in votes
    ]

    return {
        "items": [item.model_dump() for item in items],
        "meta": PageMeta(total=total, limit=limit, offset=offset).model_dump(),
    }


@router.get("/{chamber}/{session}/{number}", response_model=VoteDetail)
def get_vote(chamber: str, session: str, number: str, db: Session = Depends(get_db)) -> VoteDetail:
    parliament, _, session_no = session.partition("-")
    if not (parliament.isdigit() and session_no.isdigit()):
        raise HTTPException(status_code=404, detail="Invalid session")
    vote = db.scalar(
        select(Vote)
        .join(Chamber, Vote.chamber_id == Chamber.id)
        .join(LegislatureSession, Vote.session_id == LegislatureSession.id)
        .where(
            Vote.number == number,
            Chamber.slug == chamber,
            LegislatureSession.parliament_number == int(parliament),
            LegislatureSession.session_number == int(session_no),
        )
        .options(
            selectinload(Vote.chamber),
            selectinload(Vote.session),
            selectinload(Vote.bill),
            selectinload(Vote.ballots).selectinload(Ballot.person),
        )
    )
    if vote is None:
        raise HTTPException(status_code=404, detail="Vote not found")

    party_names: dict[str, str] = {
        slug: name for slug, name in db.execute(select(Party.slug, Party.name_en)).all()
    }

    party_totals: dict[str, PartyBreakdown] = defaultdict(
        lambda: PartyBreakdown(party_slug="unknown", party_name=None)
    )
    ballots: list[BallotItem] = []
    dissents: dict[str, int] = defaultdict(int)
    for ballot in vote.ballots:
        party_slug = ballot.party_slug or "unknown"
        summary = party_totals[party_slug]
        summary.party_slug = party_slug
        summary.party_name = party_names.get(party_slug)
        if ballot.ballot == "yea":
            summary.yea += 1
        elif ballot.ballot == "nay":
            summary.nay += 1
        elif ballot.ballot == "paired":
            summary.paired += 1
        else:
            summary.absent += 1
        if ballot.broke_party_line:
            dissents[party_slug] += 1

        ballots.append(
            BallotItem(
                person_slug=ballot.person.slug,
                full_name=ballot.person.full_name,
                party_slug=party_slug,
                ballot=ballot.ballot,
                broke_party_line=ballot.broke_party_line,
            )
        )

    for party_slug, summary in party_totals.items():
        cast_yn = summary.yea + summary.nay
        if cast_yn:
            summary.disagreement_pct = round(100.0 * dissents[party_slug] / cast_yn, 1)

    return VoteDetail(
        chamber=vote.chamber.slug,
        session=vote.session.label,
        number=vote.number,
        occurred_on=vote.occurred_on,
        description_en=vote.description_en,
        result=vote.result,
        yea_total=vote.yea_total,
        nay_total=vote.nay_total,
        vote_type=vote.vote_type,
        related_bill_number=vote.bill.number if vote.bill else None,
        source_url=vote.source_url,
        yea_effect=vote.yea_effect,
        plain_meaning_en=vote.plain_meaning_en,
        party_breakdown=list(party_totals.values()),
        ballots=ballots,
    )
