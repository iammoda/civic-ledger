from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db.session import get_db
from app.models import Committee, CommitteeMembership
from app.schemas.committees import CommitteeDetail, CommitteeListItem, CommitteeMember
from app.schemas.common import CommitteeEventSummary, PageMeta


router = APIRouter(prefix="/committees", tags=["committees"])


@router.get("")
def list_committees(
    chamber: str | None = None,
    limit: int = Query(default=25, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> dict:
    committees = db.scalars(
        select(Committee)
        .options(selectinload(Committee.chamber))
        .order_by(Committee.name_en)
        .offset(offset)
        .limit(limit)
    ).all()

    items: list[CommitteeListItem] = []
    for committee in committees:
        if chamber and committee.chamber.slug != chamber:
            continue
        items.append(
            CommitteeListItem(
                slug=committee.slug,
                name_en=committee.name_en,
                chamber=committee.chamber.slug,
            )
        )

    return {
        "items": [item.model_dump() for item in items],
        "meta": PageMeta(total=len(items), limit=limit, offset=offset).model_dump(),
    }


@router.get("/{slug}", response_model=CommitteeDetail)
def get_committee(slug: str, db: Session = Depends(get_db)) -> CommitteeDetail:
    committee = db.scalar(
        select(Committee)
        .where(Committee.slug == slug)
        .options(
            selectinload(Committee.chamber),
            selectinload(Committee.memberships).selectinload(CommitteeMembership.person),
            selectinload(Committee.events),
        )
    )
    if committee is None:
        raise HTTPException(status_code=404, detail="Committee not found")

    return CommitteeDetail(
        slug=committee.slug,
        name_en=committee.name_en,
        chamber=committee.chamber.slug,
        source_url=committee.source_url,
        members=[
            CommitteeMember(
                person_slug=membership.person.slug,
                full_name=membership.person.full_name,
                role=membership.role,
            )
            for membership in committee.memberships
        ],
        events=[
            CommitteeEventSummary(
                event_type=event.event_type,
                title_en=event.title_en,
                occurred_at=event.occurred_at,
                source_url=event.source_url,
            )
            for event in committee.events
        ],
    )
