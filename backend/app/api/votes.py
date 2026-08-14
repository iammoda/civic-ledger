from __future__ import annotations

from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.config import get_settings
from app.db.session import get_db
from app.llm.analyses import vote_stage
from app.models import AnalysisResult, Ballot, Bill, Chamber, Jurisdiction, LegislatureSession, Party, Vote
from app.schemas.common import PageMeta
from app.schemas.votes import BallotItem, PartyBreakdown, VoteDetail, VoteListItem


router = APIRouter(prefix="/votes", tags=["votes"])

settings = get_settings()


def _bill_display_title(bill: Bill | None) -> str | None:
    """Short title when it reads well; long title otherwise."""
    if bill is None:
        return None
    short = (bill.short_title_en or "").strip()
    if short and not short.lower().startswith("an act"):
        return short
    return (bill.title_en or "").strip() or None


def _bill_one_sentences(db: Session, bill_ids: list[int]) -> dict[int, str]:
    """Published one-sentence AI summaries for a set of bills, one query."""
    if not bill_ids:
        return {}
    rows = db.execute(
        select(AnalysisResult.bill_id, AnalysisResult.payload).where(
            AnalysisResult.bill_id.in_(bill_ids),
            AnalysisResult.analysis_type == "plain_summary",
            AnalysisResult.status == "published",
        )
    ).all()
    out: dict[int, str] = {}
    for bill_id, payload in rows:
        sentence = (payload or {}).get("one_sentence")
        if bill_id is not None and sentence:
            out[bill_id] = sentence
    return out


@router.get("")
def list_votes(
    chamber: str | None = None,
    result: str | None = None,
    limit: int = Query(default=25, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> dict:
    # Federal record only; provincial votes ship with their own routes.
    query = (
        select(Vote)
        .join(LegislatureSession, Vote.session_id == LegislatureSession.id)
        .join(Jurisdiction, LegislatureSession.jurisdiction_id == Jurisdiction.id)
        .where(Jurisdiction.code == settings.default_jurisdiction)
    )
    if chamber:
        query = query.join(Chamber, Vote.chamber_id == Chamber.id).where(Chamber.slug == chamber)
    if result:
        query = query.where(Vote.result == result)

    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    votes = db.scalars(
        query.options(
            selectinload(Vote.chamber),
            selectinload(Vote.session),
            selectinload(Vote.bill),
        )
        .order_by(Vote.occurred_on.desc())
        .offset(offset)
        .limit(limit)
    ).all()

    one_sentences = _bill_one_sentences(
        db, [vote.bill_id for vote in votes if vote.bill_id is not None]
    )

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
            yea_effect=vote.yea_effect,
            plain_meaning_en=vote.plain_meaning_en,
            bill_number=vote.bill.number if vote.bill else None,
            bill_title=_bill_display_title(vote.bill),
            bill_one_sentence=one_sentences.get(vote.bill_id) if vote.bill_id else None,
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
            # Chamber slugs disambiguate jurisdictions here: "house"/"senate"
            # are federal, provincial assemblies are prefixed ("on-assembly").
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

    # "About this bill" context: the one-sentence summary if we have one.
    bill_summary: str | None = None
    bill_summary_source: str | None = None
    if vote.bill is not None:
        analysis = db.scalar(
            select(AnalysisResult).where(
                AnalysisResult.bill_id == vote.bill.id,
                AnalysisResult.analysis_type == "plain_summary",
                AnalysisResult.status == "published",
            )
        )
        if analysis is not None and analysis.payload:
            bill_summary = analysis.payload.get("one_sentence")
            bill_summary_source = "ai" if bill_summary else None
        if not bill_summary and vote.bill.official_summary_en:
            # First sentence of the Library of Parliament summary.
            official = vote.bill.official_summary_en.strip()
            bill_summary = official.split(". ")[0].rstrip(".") + "." if official else None
            bill_summary_source = "official" if bill_summary else None

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
        bill_number=vote.bill.number if vote.bill else None,
        bill_title=_bill_display_title(vote.bill),
        bill_short_title=(vote.bill.short_title_en if vote.bill else None),
        bill_summary=bill_summary,
        bill_summary_source=bill_summary_source,
        bill_status=(vote.bill.status_en if vote.bill else None),
        stage=vote_stage(vote.description_en or ""),
        source_url=vote.source_url,
        yea_effect=vote.yea_effect,
        plain_meaning_en=vote.plain_meaning_en,
        party_breakdown=list(party_totals.values()),
        ballots=ballots,
    )
