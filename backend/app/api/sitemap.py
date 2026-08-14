"""Every indexable page path, for the frontend's sitemap.xml.

One lightweight endpoint so the frontend can emit a complete sitemap
without paging through the public API. A civic site lives or dies by
search discoverability — thousands of bill/vote/MP permalinks need to
be crawlable. Capped defensively (sitemaps top out at 50k URLs).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.db.session import get_db
from app.models import Bill, Committee, EntityTopic, Person, Topic, Vote

router = APIRouter(tags=["sitemap"])

MAX_PATHS = 45_000


class SitemapResponse(BaseModel):
    paths: list[str]


@router.get("/sitemap-paths", response_model=SitemapResponse)
def sitemap_paths(db: Session = Depends(get_db)) -> SitemapResponse:
    paths: list[str] = []

    people = db.scalars(select(Person.slug).order_by(Person.id)).all()
    paths.extend(f"/politicians/{slug}" for slug in people)

    bills = db.scalars(
        select(Bill).options(selectinload(Bill.session)).order_by(Bill.id)
    ).all()
    paths.extend(f"/bills/{bill.session.label}/{bill.number}" for bill in bills)

    votes = db.scalars(
        select(Vote)
        .options(selectinload(Vote.session), selectinload(Vote.chamber))
        .order_by(Vote.id)
    ).all()
    paths.extend(f"/votes/{vote.chamber.slug}/{vote.session.label}/{vote.number}" for vote in votes)

    committees = db.scalars(select(Committee.slug).distinct()).all()
    paths.extend(f"/committees/{slug}" for slug in committees)

    # Issues = topics that actually have bills attached (mirrors /issues).
    issue_slugs = db.scalars(
        select(Topic.slug)
        .join(EntityTopic, EntityTopic.topic_id == Topic.id)
        .where(EntityTopic.entity_type == "bill")
        .group_by(Topic.slug)
        .having(func.count(EntityTopic.id) > 0)
    ).all()
    paths.extend(f"/issues/{slug}" for slug in issue_slugs)

    return SitemapResponse(paths=paths[:MAX_PATHS])
