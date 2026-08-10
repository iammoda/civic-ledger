from __future__ import annotations

from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db.session import get_db
from app.models import Ballot, Vote
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
    votes = db.scalars(
        select(Vote)
        .options(selectinload(Vote.chamber), selectinload(Vote.session))
        .order_by(Vote.occurred_on.desc())
        .offset(offset)
        .limit(limit)
    ).all()

    items: list[VoteListItem] = []
    for vote in votes:
        if chamber and vote.chamber.slug != chamber:
            continue
        if result and vote.result != result:
            continue

        items.append(
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
        )

    return {
        "items": [item.model_dump() for item in items],
        "meta": PageMeta(total=len(items), limit=limit, offset=offset).model_dump(),
    }


@router.get("/{chamber}/{session}/{number}", response_model=VoteDetail)
def get_vote(chamber: str, session: str, number: str, db: Session = Depends(get_db)) -> VoteDetail:
    vote = db.scalar(
        select(Vote)
        .where(Vote.number == number)
        .options(
            selectinload(Vote.chamber),
            selectinload(Vote.session),
            selectinload(Vote.bill),
            selectinload(Vote.ballots).selectinload(Ballot.person),
        )
    )
    if vote is None or vote.chamber.slug != chamber or vote.session.label != session:
        raise HTTPException(status_code=404, detail="Vote not found")

    party_totals: dict[str, PartyBreakdown] = defaultdict(
        lambda: PartyBreakdown(party_slug="unknown", party_name=None)
    )
    ballots: list[BallotItem] = []
    for ballot in vote.ballots:
        party_slug = ballot.party_slug or "unknown"
        summary = party_totals[party_slug]
        summary.party_slug = party_slug
        if ballot.ballot == "yea":
            summary.yea += 1
        elif ballot.ballot == "nay":
            summary.nay += 1
        elif ballot.ballot == "paired":
            summary.paired += 1
        else:
            summary.absent += 1

        ballots.append(
            BallotItem(
                person_slug=ballot.person.slug,
                full_name=ballot.person.full_name,
                party_slug=party_slug,
                ballot=ballot.ballot,
                broke_party_line=ballot.broke_party_line,
            )
        )

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
        party_breakdown=list(party_totals.values()),
        ballots=ballots,
    )
