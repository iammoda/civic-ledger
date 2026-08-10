from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.session import get_db
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


@router.post("/ask", response_model=AskResponseModel)
async def ask_question(payload: AskRequest, db: Session = Depends(get_db)) -> AskResponseModel:
    try:
        response = await run_ask(db, payload.question.strip())
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
    )
