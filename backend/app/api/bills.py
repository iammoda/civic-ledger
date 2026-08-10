from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db.session import get_db
from app.models import Bill, Vote
from app.schemas.bills import BillDetail, BillListItem
from app.schemas.common import AnalysisState, DataGap, PageMeta
from app.schemas.votes import VoteListItem


router = APIRouter(prefix="/bills", tags=["bills"])


@router.get("")
def list_bills(
    chamber: str | None = None,
    bill_type: str | None = None,
    limit: int = Query(default=25, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> dict:
    bills = db.scalars(
        select(Bill)
        .options(selectinload(Bill.session), selectinload(Bill.chamber), selectinload(Bill.sponsor))
        .order_by(Bill.introduced_on.desc().nullslast(), Bill.number)
        .offset(offset)
        .limit(limit)
    ).all()

    items: list[BillListItem] = []
    for bill in bills:
        if chamber and bill.chamber.slug != chamber:
            continue
        if bill_type and bill.bill_type != bill_type:
            continue

        items.append(
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
        )

    return {
        "items": [item.model_dump() for item in items],
        "meta": PageMeta(total=len(items), limit=limit, offset=offset).model_dump(),
    }


@router.get("/{session}/{number}", response_model=BillDetail)
def get_bill(session: str, number: str, db: Session = Depends(get_db)) -> BillDetail:
    bill = db.scalar(
        select(Bill)
        .where(Bill.number == number)
        .options(
            selectinload(Bill.session),
            selectinload(Bill.chamber),
            selectinload(Bill.sponsor),
            selectinload(Bill.analyses),
            selectinload(Bill.votes).selectinload(Vote.chamber),
            selectinload(Bill.votes).selectinload(Vote.session),
        )
    )
    if bill is None or bill.session.label != session:
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
    if not analyses:
        data_gaps.append(
            DataGap(
                code="analysis_pending",
                label="Analysis pending",
                detail="AI-generated bill analysis has not completed for this bill yet.",
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
