from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import EntityTopic, Person, Petition, Topic
from app.schemas.common import PageMeta


router = APIRouter(prefix="/petitions", tags=["petitions"])


class PetitionItem(BaseModel):
    number: str
    title_en: str
    state: str
    status_en: str | None = None
    closes_at: date | None = None
    days_left: int | None = None
    signature_count: int
    keywords: list[str] = []
    sponsor_name: str | None = None
    sponsor_slug: str | None = None
    sign_url: str
    topics: list[str] = []


@router.get("")
def list_petitions(
    state: str | None = Query(default=None, pattern="^(open|closed)$"),
    topic: str | None = None,
    limit: int = Query(default=25, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> dict:
    query = select(Petition)
    if state:
        query = query.where(Petition.state == state)
    if topic:
        topic_row = db.scalar(select(Topic).where(Topic.slug == topic))
        if topic_row is None:
            return {"items": [], "meta": PageMeta(total=0, limit=limit, offset=offset).model_dump()}
        tagged_ids = select(EntityTopic.entity_id).where(
            EntityTopic.topic_id == topic_row.id, EntityTopic.entity_type == "petition"
        )
        query = query.where(Petition.id.in_(tagged_ids))

    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    petitions = db.scalars(
        query.order_by(
            Petition.state.desc(),  # open before closed
            Petition.closes_at.asc().nullslast(),
        )
        .offset(offset)
        .limit(limit)
    ).all()

    # Topic labels per petition, one query.
    ids = [p.id for p in petitions]
    topic_map: dict[int, list[str]] = {}
    if ids:
        rows = db.execute(
            select(EntityTopic.entity_id, Topic.name_en)
            .join(Topic, EntityTopic.topic_id == Topic.id)
            .where(EntityTopic.entity_type == "petition", EntityTopic.entity_id.in_(ids))
        ).all()
        for entity_id, name in rows:
            topic_map.setdefault(entity_id, []).append(name)

    sponsor_slugs: dict[int, str] = {}
    sponsor_ids = [p.sponsor_person_id for p in petitions if p.sponsor_person_id]
    if sponsor_ids:
        for pid, slug in db.execute(select(Person.id, Person.slug).where(Person.id.in_(sponsor_ids))).all():
            sponsor_slugs[pid] = slug

    today = date.today()
    items = [
        PetitionItem(
            number=p.number,
            title_en=p.title_en,
            state=p.state,
            status_en=p.status_en,
            closes_at=p.closes_at,
            days_left=(p.closes_at - today).days if (p.state == "open" and p.closes_at) else None,
            signature_count=p.signature_count,
            keywords=[k.strip() for k in (p.keywords_en or "").split(",") if k.strip()],
            sponsor_name=p.sponsor_name,
            sponsor_slug=sponsor_slugs.get(p.sponsor_person_id) if p.sponsor_person_id else None,
            sign_url=p.source_url,
            topics=sorted(topic_map.get(p.id, [])),
        )
        for p in petitions
    ]

    return {
        "items": [item.model_dump() for item in items],
        "meta": PageMeta(total=total, limit=limit, offset=offset).model_dump(),
    }
