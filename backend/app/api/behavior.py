"""Behavior endpoints: MP voting records with party context."""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.api.votes import _bill_display_title, _bill_one_sentences
from app.db.session import get_db
from app.models import (
    Ballot,
    Party,
    Person,
    Vote,
)


router = APIRouter(tags=["behavior"])

# Ballot values that count as showing up. Anything else ("absent", legacy
# strings) means the MP didn't vote.
CAST_VALUES = {"yea", "nay"}
PARTICIPATED_VALUES = {"yea", "nay", "paired"}


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
    bill_title: str | None = None
    # Published AI one-sentence summary of the bill, when we have one.
    bill_one_sentence: str | None = None


class VotingRecordResponse(BaseModel):
    slug: str
    full_name: str
    total_ballots: int
    dissent_count: int
    # Participation: cast = yea/nay; missed = anything outside yea/nay/paired.
    cast_count: int
    missed_count: int
    participation_pct: float | None = None
    # Among the most recent 30 ballots: how many they missed. Powers the
    # "missing more votes lately" callout on the frontend.
    recent_missed_count: int
    recent_total: int
    # How many ballots match the current filter — for pagination.
    total_filtered: int = 0
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
    filter: str = Query(default="all", pattern="^(all|dissent|missed)$"),
    # Deprecated: kept for backwards compat; dissent_only=true means filter=dissent.
    dissent_only: bool = Query(default=False),
    limit: int = Query(default=25, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> VotingRecordResponse:
    person = db.scalar(select(Person).where(Person.slug == slug))
    if person is None:
        raise HTTPException(status_code=404, detail="Politician not found")

    if dissent_only and filter == "all":
        filter = "dissent"

    base = select(Ballot).where(Ballot.person_id == person.id)
    dissent_count = db.scalar(
        select(func.count()).select_from(
            base.where(Ballot.broke_party_line.is_(True)).subquery()
        )
    ) or 0

    # One grouped query gives every participation stat at once.
    ballot_value_counts: dict[str, int] = {
        value: count
        for value, count in db.execute(
            select(Ballot.ballot, func.count())
            .where(Ballot.person_id == person.id)
            .group_by(Ballot.ballot)
        ).all()
    }
    total_ballots = sum(ballot_value_counts.values())
    cast_count = sum(c for v, c in ballot_value_counts.items() if v in CAST_VALUES)
    paired_count = sum(c for v, c in ballot_value_counts.items() if v == "paired")
    missed_count = total_ballots - cast_count - paired_count
    participation_pct = (
        round(100.0 * (cast_count + paired_count) / total_ballots, 1) if total_ballots else None
    )

    # Recent trend: just the ballot values of the last 30 votes by date.
    recent_values = db.scalars(
        select(Ballot.ballot)
        .join(Vote, Ballot.vote_id == Vote.id)
        .where(Ballot.person_id == person.id)
        .order_by(Vote.occurred_on.desc())
        .limit(30)
    ).all()
    recent_total = len(recent_values)
    recent_missed_count = sum(1 for v in recent_values if v not in PARTICIPATED_VALUES)

    query = base
    if filter == "dissent":
        query = query.where(Ballot.broke_party_line.is_(True))
    elif filter == "missed":
        query = query.where(Ballot.ballot.not_in(PARTICIPATED_VALUES))
    total_filtered = db.scalar(select(func.count()).select_from(query.subquery())) or 0
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

    one_sentences = _bill_one_sentences(
        db, [b.vote.bill_id for b in ballots if b.vote.bill_id is not None]
    )

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
            bill_title=_bill_display_title(b.vote.bill),
            bill_one_sentence=one_sentences.get(b.vote.bill_id) if b.vote.bill_id else None,
        )
        for b in ballots
    ]

    return VotingRecordResponse(
        slug=person.slug,
        full_name=person.full_name,
        total_ballots=total_ballots,
        dissent_count=dissent_count,
        cast_count=cast_count,
        missed_count=missed_count,
        participation_pct=participation_pct,
        recent_missed_count=recent_missed_count,
        recent_total=recent_total,
        total_filtered=total_filtered,
        items=items,
    )
