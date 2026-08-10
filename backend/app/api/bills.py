from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.db.session import get_db
from app.models import Bill, Chamber, LegislatureSession, Vote
from app.schemas.bills import BillDetail, BillListItem
from app.schemas.common import AnalysisState, DataGap, PageMeta
from app.schemas.votes import VoteListItem
from app.services.lazy import enqueue


router = APIRouter(prefix="/bills", tags=["bills"])


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
    limit: int = Query(default=25, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> dict:
    query = select(Bill)
    if chamber:
        query = query.join(Chamber, Bill.chamber_id == Chamber.id).where(Chamber.slug == chamber)
    if bill_type:
        query = query.where(Bill.bill_type == bill_type)

    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    bills = db.scalars(
        query.options(selectinload(Bill.session), selectinload(Bill.chamber), selectinload(Bill.sponsor))
        .order_by(Bill.introduced_on.desc().nullslast(), Bill.number)
        .offset(offset)
        .limit(limit)
    ).all()

    items = [
        BillListItem(
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
        )
        for bill in bills
    ]

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
            selectinload(Bill.votes).selectinload(Vote.chamber),
            selectinload(Bill.votes).selectinload(Vote.session),
        )
    )
    if bill is None:
        raise HTTPException(status_code=404, detail="Bill not found")

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
    has_summary = any(a.analysis_type == "plain_summary" and a.status == "published" for a in analyses)
    if not has_summary:
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
        legisinfo_url=bill.legisinfo_url,
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
