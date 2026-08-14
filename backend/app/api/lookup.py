"""Anonymous lookups: postal-code representative ladder, topics, glossary.

No accounts exist on this platform. Postal codes are used for the lookup
only and never stored.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import GlossaryTerm, Topic
from app.services.represent import lookup_postal_full


router = APIRouter(tags=["lookup"])


class MpCandidateModel(BaseModel):
    riding_name: str
    province: str | None = None
    mp_name: str
    party_name: str | None = None
    person_slug: str | None = None


class LadderRepModel(BaseModel):
    level: str
    office: str
    name: str
    district_name: str | None = None
    party_name: str | None = None
    email: str | None = None
    url: str | None = None
    person_slug: str | None = None


class PostalLookupResponse(BaseModel):
    candidates: list[MpCandidateModel]
    ambiguous: bool
    # Your full ladder: MP (deep data) + MPP/MLA + councillor/mayor (contact).
    ladder: list[LadderRepModel] = []


@router.get("/lookup/postal/{code}", response_model=PostalLookupResponse)
async def postal_lookup(code: str, db: Session = Depends(get_db)) -> PostalLookupResponse:
    """Anonymous-first: works without an account; nothing is stored."""
    result = await lookup_postal_full(db, code)
    if result is None:
        raise HTTPException(status_code=502, detail="Postal lookup unavailable or invalid postal code")
    candidates, ladder = result
    return PostalLookupResponse(
        candidates=[
            MpCandidateModel(
                riding_name=c.riding_name,
                province=c.province,
                mp_name=c.mp_name,
                party_name=c.party_name,
                person_slug=c.person_slug,
            )
            for c in candidates
        ],
        ambiguous=len(candidates) > 1,
        ladder=[
            LadderRepModel(
                level=r.level, office=r.office, name=r.name, district_name=r.district_name,
                party_name=r.party_name, email=r.email, url=r.url, person_slug=r.person_slug,
            )
            for r in ladder
        ],
    )


class TopicItem(BaseModel):
    slug: str
    name_en: str
    description_en: str | None = None


@router.get("/topics", response_model=list[TopicItem])
def list_topics(db: Session = Depends(get_db)) -> list[TopicItem]:
    topics = db.scalars(select(Topic).order_by(Topic.name_en)).all()
    return [TopicItem(slug=t.slug, name_en=t.name_en, description_en=t.description_en) for t in topics]


class GlossaryItem(BaseModel):
    term: str
    definition_en: str


@router.get("/glossary", response_model=list[GlossaryItem])
def list_glossary(db: Session = Depends(get_db)) -> list[GlossaryItem]:
    terms = db.scalars(select(GlossaryTerm).order_by(GlossaryTerm.term)).all()
    return [GlossaryItem(term=t.term, definition_en=t.definition_en) for t in terms]
