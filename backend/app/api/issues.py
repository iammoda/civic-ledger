"""Issues: the topic taxonomy as an entry point — "I care about X, who
supports it and who doesn't?" — answered with receipts, not vibes.

Every number here is a straight computation over official records: bills
tagged to a topic via entity_topics, and every recorded ballot on those
bills. The caveat ships with the numbers (positions_note), because raw
yea/nay totals mix second readings, amendments, and final passage.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session, selectinload

from app.db.session import get_db
from app.models import AnalysisResult, Ballot, Bill, EntityTopic, Party, Topic, Vote


router = APIRouter(prefix="/issues", tags=["issues"])

DEAD_OUTCOMES = (
    "defeated_vote",
    "died_committee",
    "died_order_paper",
    "died_senate",
    "withdrawn",
    "not_proceeded_with",
)


class IssueListItem(BaseModel):
    slug: str
    name_en: str
    description_en: str | None = None
    bill_count: int
    law_count: int
    dead_count: int


class IssueListResponse(BaseModel):
    items: list[IssueListItem]


class IssueBill(BaseModel):
    session: str
    number: str
    title_en: str
    short_title_en: str | None = None
    outcome: str
    is_law: bool
    status_en: str | None = None
    one_sentence: str | None = None


class IssuePartyPosition(BaseModel):
    party_slug: str
    party_name: str | None = None
    yea: int
    nay: int


class IssueVote(BaseModel):
    """One of the recorded votes behind the party-position numbers — so
    "where the parties stood" is verifiable, not vibes."""

    chamber: str
    session: str
    number: str
    occurred_on: str
    description_en: str
    plain_meaning_en: str | None = None
    result: str | None = None
    yea_total: int
    nay_total: int
    bill_number: str | None = None


class IssueDetail(BaseModel):
    slug: str
    name_en: str
    description_en: str | None = None
    bills: list[IssueBill]
    party_positions: list[IssuePartyPosition]
    vote_count: int
    votes: list[IssueVote]
    positions_note: str


@router.get("", response_model=IssueListResponse)
def list_issues(db: Session = Depends(get_db)) -> IssueListResponse:
    rows = db.execute(
        select(
            Topic.slug,
            Topic.name_en,
            Topic.description_en,
            func.count(Bill.id).label("bill_count"),
            func.coalesce(func.sum(case((Bill.is_law.is_(True), 1), else_=0)), 0).label("law_count"),
            func.coalesce(func.sum(case((Bill.outcome.in_(DEAD_OUTCOMES), 1), else_=0)), 0).label("dead_count"),
        )
        .outerjoin(
            EntityTopic,
            (EntityTopic.topic_id == Topic.id) & (EntityTopic.entity_type == "bill"),
        )
        .outerjoin(Bill, Bill.id == EntityTopic.entity_id)
        .group_by(Topic.id, Topic.slug, Topic.name_en, Topic.description_en)
        .order_by(Topic.name_en)
    ).all()
    return IssueListResponse(
        items=[
            IssueListItem(
                slug=slug,
                name_en=name_en,
                description_en=description_en,
                bill_count=int(bill_count or 0),
                law_count=int(law_count or 0),
                dead_count=int(dead_count or 0),
            )
            for slug, name_en, description_en, bill_count, law_count, dead_count in rows
        ]
    )


@router.get("/{slug}", response_model=IssueDetail)
def get_issue(slug: str, db: Session = Depends(get_db)) -> IssueDetail:
    topic = db.scalar(select(Topic).where(Topic.slug == slug))
    if topic is None:
        raise HTTPException(status_code=404, detail="Unknown topic")

    # All bills tagged to this topic (subquery — party positions count every
    # tagged bill, not just the 50 we display).
    tagged_bill_ids = (
        select(EntityTopic.entity_id)
        .where(EntityTopic.topic_id == topic.id, EntityTopic.entity_type == "bill")
        .scalar_subquery()
    )
    voted_bill_ids = select(Vote.bill_id).where(Vote.bill_id.in_(tagged_bill_ids)).scalar_subquery()

    bills = db.scalars(
        select(Bill)
        .where(Bill.id.in_(tagged_bill_ids))
        .options(selectinload(Bill.session))
        # Bills that actually reached a recorded vote first — that's where
        # the receipts are — then newest introductions.
        .order_by(
            case((Bill.id.in_(voted_bill_ids), 0), else_=1),
            Bill.introduced_on.desc().nullslast(),
            Bill.number,
        )
        .limit(50)
    ).all()

    # Batch-join published plain summaries for the displayed bills.
    one_sentences: dict[int, str | None] = {}
    if bills:
        for bill_id, payload in db.execute(
            select(AnalysisResult.bill_id, AnalysisResult.payload).where(
                AnalysisResult.bill_id.in_([b.id for b in bills]),
                AnalysisResult.analysis_type == "plain_summary",
                AnalysisResult.status == "published",
            )
        ).all():
            one_sentences[bill_id] = (payload or {}).get("one_sentence")

    # One grouped query: every recorded yea/nay ballot on this topic's bills,
    # summed by party.
    ballot_rows = db.execute(
        select(Ballot.party_slug, Ballot.ballot, func.count())
        .join(Vote, Ballot.vote_id == Vote.id)
        .where(
            Vote.bill_id.in_(tagged_bill_ids),
            Ballot.party_slug.is_not(None),
            Ballot.ballot.in_(["yea", "nay"]),
        )
        .group_by(Ballot.party_slug, Ballot.ballot)
    ).all()

    positions: dict[str, dict[str, int]] = {}
    for party_slug, ballot, count in ballot_rows:
        positions.setdefault(party_slug, {"yea": 0, "nay": 0})[ballot] = int(count)

    party_names: dict[str, str] = {}
    if positions:
        for pslug, name_en in db.execute(
            select(Party.slug, Party.name_en).where(Party.slug.in_(list(positions)))
        ).all():
            party_names.setdefault(pslug, name_en)

    party_positions = sorted(
        (
            IssuePartyPosition(
                party_slug=pslug,
                party_name=party_names.get(pslug),
                yea=counts["yea"],
                nay=counts["nay"],
            )
            for pslug, counts in positions.items()
        ),
        key=lambda p: p.yea + p.nay,
        reverse=True,
    )

    vote_count = int(
        db.scalar(select(func.count(Vote.id)).where(Vote.bill_id.in_(tagged_bill_ids))) or 0
    )

    # The receipts for the party-position bars: every recorded vote counted,
    # newest first (capped — the point is verifiability, not pagination).
    counted_votes = db.scalars(
        select(Vote)
        .where(Vote.bill_id.in_(tagged_bill_ids))
        .options(
            selectinload(Vote.session),
            selectinload(Vote.chamber),
            selectinload(Vote.bill),
        )
        .order_by(Vote.occurred_on.desc(), Vote.number.desc())
        .limit(50)
    ).all()

    return IssueDetail(
        slug=topic.slug,
        name_en=topic.name_en,
        description_en=topic.description_en,
        bills=[
            IssueBill(
                session=bill.session.label,
                number=bill.number,
                title_en=bill.title_en,
                short_title_en=bill.short_title_en,
                outcome=bill.outcome,
                is_law=bill.is_law,
                status_en=bill.status_en,
                one_sentence=one_sentences.get(bill.id),
            )
            for bill in bills
        ],
        party_positions=party_positions,
        vote_count=vote_count,
        votes=[
            IssueVote(
                chamber=vote.chamber.slug,
                session=vote.session.label,
                number=vote.number,
                occurred_on=vote.occurred_on.isoformat(),
                description_en=vote.description_en,
                plain_meaning_en=vote.plain_meaning_en,
                result=vote.result,
                yea_total=vote.yea_total,
                nay_total=vote.nay_total,
                bill_number=vote.bill.number if vote.bill else None,
            )
            for vote in counted_votes
        ],
        positions_note=(
            f"Counts every recorded ballot on the {vote_count} votes tied to these bills — "
            "second readings, amendments, final passage. Procedural votes can invert meaning, "
            "so treat this as a pattern, not a scorecard."
        ),
    )
