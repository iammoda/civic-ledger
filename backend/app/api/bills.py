from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.db.session import get_db
from app.models import Bill, BillDeath, Chamber, EntityTopic, LegislatureSession, Topic, Vote
from app.schemas.bills import BillDeathInfo, BillDetail, BillListItem
from app.schemas.common import AnalysisState, DataGap, PageMeta
from app.schemas.votes import VoteListItem
from app.services.lazy import enqueue


router = APIRouter(prefix="/bills", tags=["bills"])

DEAD_OUTCOMES = (
    "defeated_vote",
    "died_committee",
    "died_order_paper",
    "died_senate",
    "withdrawn",
    "not_proceeded_with",
)
OUTCOME_GROUPS: dict[str, tuple[str, ...]] = {
    "dead": DEAD_OUTCOMES,
    "law": ("enacted",),
    "pending": ("pending",),
}


def _death_info(db: Session, bill: Bill) -> BillDeathInfo | None:
    death = bill.death
    if death is None:
        return None
    kill_vote = db.scalar(
        select(Vote)
        .options(selectinload(Vote.session), selectinload(Vote.chamber))
        .where(Vote.id == death.kill_vote_id)
    ) if death.kill_vote_id else None
    return BillDeathInfo(
        mechanism=death.mechanism,
        stage=death.stage,
        occurred_on=death.occurred_on,
        attribution_en=death.attribution_en,
        kill_vote_number=kill_vote.number if kill_vote else None,
        kill_vote_chamber=kill_vote.chamber.slug if kill_vote else None,
        kill_vote_session=kill_vote.session.label if kill_vote else None,
    )


def _list_item(db: Session, bill: Bill, *, with_death: bool = False) -> BillListItem:
    return BillListItem(
        session=bill.session.label,
        chamber=bill.chamber.slug,
        number=bill.number,
        title_en=bill.title_en,
        short_title_en=bill.short_title_en,
        status_en=bill.status_en,
        bill_type=bill.bill_type,
        introduced_on=bill.introduced_on,
        sponsor_slug=bill.sponsor.slug if bill.sponsor else None,
        sponsor_name=bill.sponsor.full_name if bill.sponsor else None,
        is_omnibus=bill.is_omnibus,
        outcome=bill.outcome,
        is_law=bill.is_law,
        death=_death_info(db, bill) if with_death else None,
    )


def _session_clauses(label: str) -> list:
    """'45-1' -> column filters. label is a Python property, not a column."""
    parliament, _, session_no = label.partition("-")
    if not (parliament.isdigit() and session_no.isdigit()):
        raise HTTPException(status_code=404, detail="Invalid session")
    return [
        LegislatureSession.parliament_number == int(parliament),
        LegislatureSession.session_number == int(session_no),
    ]


@router.get("")
def list_bills(
    chamber: str | None = None,
    bill_type: str | None = None,
    outcome_group: str | None = Query(default=None, pattern="^(dead|law|pending)$"),
    topic: str | None = None,
    limit: int = Query(default=25, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> dict:
    query = select(Bill)
    if chamber:
        query = query.join(Chamber, Bill.chamber_id == Chamber.id).where(Chamber.slug == chamber)
    if bill_type:
        query = query.where(Bill.bill_type == bill_type)
    if outcome_group:
        query = query.where(Bill.outcome.in_(OUTCOME_GROUPS[outcome_group]))
    if topic:
        topic_row = db.scalar(select(Topic).where(Topic.slug == topic))
        if topic_row is None:
            return {"items": [], "meta": PageMeta(total=0, limit=limit, offset=offset).model_dump()}
        tagged = select(EntityTopic.entity_id).where(
            EntityTopic.topic_id == topic_row.id, EntityTopic.entity_type == "bill"
        )
        query = query.where(Bill.id.in_(tagged))

    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    order = (
        # The graveyard reads best newest-death-first.
        (BillDeath.occurred_on.desc().nullslast(), Bill.number)
        if outcome_group == "dead"
        else (Bill.introduced_on.desc().nullslast(), Bill.number)
    )
    if outcome_group == "dead":
        query = query.outerjoin(BillDeath, BillDeath.bill_id == Bill.id)
    bills = db.scalars(
        query.options(
            selectinload(Bill.session),
            selectinload(Bill.chamber),
            selectinload(Bill.sponsor),
            selectinload(Bill.death),
        )
        .order_by(*order)
        .offset(offset)
        .limit(limit)
    ).all()

    items = [_list_item(db, bill, with_death=bill.outcome in DEAD_OUTCOMES) for bill in bills]

    return {
        "items": [item.model_dump() for item in items],
        "meta": PageMeta(total=total, limit=limit, offset=offset).model_dump(),
    }


@router.get("/{session}/{number}", response_model=BillDetail)
async def get_bill(session: str, number: str, db: Session = Depends(get_db)) -> BillDetail:
    bill = db.scalar(
        select(Bill)
        .join(LegislatureSession, Bill.session_id == LegislatureSession.id)
        .where(Bill.number == number, *_session_clauses(session))
        .options(
            selectinload(Bill.session),
            selectinload(Bill.chamber),
            selectinload(Bill.sponsor),
            selectinload(Bill.analyses),
            selectinload(Bill.death),
            selectinload(Bill.votes).selectinload(Vote.chamber),
            selectinload(Bill.votes).selectinload(Vote.session),
        )
    )
    if bill is None:
        raise HTTPException(status_code=404, detail="Bill not found")

    topics = [
        name
        for (name,) in db.execute(
            select(Topic.name_en)
            .join(EntityTopic, EntityTopic.topic_id == Topic.id)
            .where(EntityTopic.entity_type == "bill", EntityTopic.entity_id == bill.id)
            .order_by(Topic.name_en)
        ).all()
    ]

    analyses = [
        AnalysisState(
            analysis_type=analysis.analysis_type,
            status=analysis.status,
            confidence_score=analysis.confidence_score,
            blocked_reason=analysis.blocked_reason,
            citations=analysis.citations,
            payload=analysis.payload,
        )
        for analysis in bill.analyses
    ]

    data_gaps = []
    summary_state = next(
        (a.status for a in analyses if a.analysis_type == "plain_summary"), None
    )
    if summary_state == "blocked":
        # A human-reviewable failure — do NOT re-enqueue (each attempt costs
        # two model calls; auto-retrying on page views burned budget).
        data_gaps.append(
            DataGap(
                code="analysis_blocked",
                label="Summary didn't meet our quality bar",
                detail=(
                    "The AI summary failed our readability checks and was blocked "
                    "rather than published. The official records below are unaffected."
                ),
            )
        )
    elif summary_state != "published":
        from app.core.config import get_settings

        if not get_settings().anthropic_api_key:
            # Honest no-AI mode: don't enqueue no-op jobs or promise
            # summaries that can't be generated.
            data_gaps.append(
                DataGap(
                    code="analysis_disabled",
                    label="AI summaries aren't enabled",
                    detail=(
                        "This instance runs without generative AI. The official "
                        "records and Library of Parliament summary (when available) "
                        "are shown instead."
                    ),
                )
            )
        else:
            # Lazy-analysis engine: first view triggers generation; cached forever.
            queued = await enqueue("analyze_bill_job", bill.id)
            data_gaps.append(
                DataGap(
                    code="analysis_pending",
                    label="Plain-language summary on its way" if queued else "Analysis pending",
                    detail=(
                        "We're writing the plain-language summary for this bill right now — "
                        "check back in a minute."
                        if queued
                        else "AI-generated bill analysis has not completed for this bill yet."
                    ),
                )
            )

    return BillDetail(
        session=bill.session.label,
        chamber=bill.chamber.slug,
        number=bill.number,
        title_en=bill.title_en,
        short_title_en=bill.short_title_en,
        status_en=bill.status_en,
        bill_type=bill.bill_type,
        introduced_on=bill.introduced_on,
        sponsor_slug=bill.sponsor.slug if bill.sponsor else None,
        sponsor_name=bill.sponsor.full_name if bill.sponsor else None,
        is_omnibus=bill.is_omnibus,
        outcome=bill.outcome,
        is_law=bill.is_law,
        death=_death_info(db, bill),
        legisinfo_url=bill.legisinfo_url,
        text_url=bill.text_url,
        official_summary_en=bill.official_summary_en,
        topics=topics,
        analyses=analyses,
        related_votes=[
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
            )
            for vote in bill.votes
        ],
        sector_impacts=next(
            (analysis.payload.get("sector_impacts", []) for analysis in bill.analyses if analysis.analysis_type == "sector_impact"),
            [],
        ),
        omnibus_components=next(
            (analysis.payload.get("components", []) for analysis in bill.analyses if analysis.analysis_type == "omnibus"),
            [],
        ),
        data_gaps=data_gaps,
    )
