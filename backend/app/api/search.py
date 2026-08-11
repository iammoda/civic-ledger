from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.auth import AuthUser, get_current_user
from app.db.session import get_db
from app.models import UserProfile
from app.services.ask import ask as run_ask
from app.services.search import hybrid_search


router = APIRouter(tags=["search"])


class SearchResultItem(BaseModel):
    entity_type: str
    title: str
    snippet: str
    url_path: str
    score: float
    outcome: str | None = None


class SearchResponse(BaseModel):
    query: str
    results: list[SearchResultItem]


@router.get("/search", response_model=SearchResponse)
async def search(
    q: str = Query(min_length=2, max_length=200),
    limit: int = Query(default=20, le=50),
    db: Session = Depends(get_db),
) -> SearchResponse:
    results = await hybrid_search(db, q, limit=limit)
    return SearchResponse(
        query=q,
        results=[
            SearchResultItem(
                entity_type=r.entity_type,
                title=r.title,
                snippet=r.snippet,
                url_path=r.url_path,
                score=r.score,
                outcome=r.outcome,
            )
            for r in results
        ],
    )


class AskRequest(BaseModel):
    question: str = Field(min_length=8, max_length=500)


class AskEvidenceItem(SearchResultItem):
    index: int


class MpBallotItem(BaseModel):
    bill_number: str
    vote_number: str
    session: str
    chamber: str
    occurred_on: str
    description_en: str
    effect: str | None = None
    ballot: str


class ResponsibleMinisterModel(BaseModel):
    name: str
    slug: str
    title: str


class AskResponseModel(BaseModel):
    question: str
    answer_sentence: str | None = None
    answer_detail: str | None = None
    jurisdiction_level: str
    jurisdiction_note: str | None = None
    responsible_ministry: str | None = None
    evidence: list[AskEvidenceItem] = []
    cited_indexes: list[int] = []
    generated: bool
    my_mp_name: str | None = None
    my_mp_slug: str | None = None
    mp_ballots: list[MpBallotItem] = []
    minister: ResponsibleMinisterModel | None = None


@router.post("/ask", response_model=AskResponseModel)
async def ask_question(
    payload: AskRequest,
    user: AuthUser | None = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AskResponseModel:
    # Signed-in users with a saved riding get their MP's ballots woven in.
    mp_person_id: int | None = None
    if user is not None:
        profile = db.get(UserProfile, user.id)
        if profile is not None:
            mp_person_id = profile.mp_person_id

    try:
        response = await run_ask(db, payload.question.strip(), mp_person_id=mp_person_id)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return AskResponseModel(
        question=response.question,
        answer_sentence=response.answer_sentence,
        answer_detail=response.answer_detail,
        jurisdiction_level=response.jurisdiction_level,
        jurisdiction_note=response.jurisdiction_note,
        responsible_ministry=response.responsible_ministry,
        evidence=[
            AskEvidenceItem(
                index=i,
                entity_type=r.entity_type,
                title=r.title,
                snippet=r.snippet,
                url_path=r.url_path,
                score=r.score,
                outcome=r.outcome,
            )
            for i, r in enumerate(response.evidence, start=1)
        ],
        cited_indexes=response.cited_indexes,
        generated=response.generated,
        my_mp_name=response.my_mp_name,
        my_mp_slug=response.my_mp_slug,
        minister=(
            ResponsibleMinisterModel(
                name=response.minister.name, slug=response.minister.slug, title=response.minister.title
            )
            if response.minister
            else None
        ),
        mp_ballots=[
            MpBallotItem(
                bill_number=b.bill_number,
                vote_number=b.vote_number,
                session=b.session,
                chamber=b.chamber,
                occurred_on=b.occurred_on.isoformat(),
                description_en=b.description_en,
                effect=b.effect,
                ballot=b.ballot,
            )
            for b in response.mp_ballots
        ],
    )
