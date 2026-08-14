from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.ratelimit import rate_limit
from app.db.session import get_db
from app.models import Person
from app.services.letters import build_letter, polish_letter


router = APIRouter(prefix="/actions", tags=["actions"])


class LetterRequest(BaseModel):
    mp_slug: str = Field(min_length=1, max_length=255)
    concern: str = Field(min_length=10, max_length=2000)
    bill_session: str | None = Field(default=None, max_length=16)
    bill_number: str | None = Field(default=None, max_length=16)
    polish: bool = False


class CitationModel(BaseModel):
    vote_number: str
    session: str
    occurred_on: str
    description_en: str
    effect: str | None = None
    ballot: str


class LetterResponse(BaseModel):
    letter_text: str
    mp_name: str
    mp_email: str | None = None
    riding: str | None = None
    citations: list[CitationModel]
    polished: bool


@router.post(
    "/letter",
    response_model=LetterResponse,
    # polish=true costs an LLM call — throttle per IP.
    dependencies=[Depends(rate_limit("letter", limit=10, window_seconds=600))],
)
async def draft_letter(
    payload: LetterRequest,
    db: Session = Depends(get_db),
) -> LetterResponse:
    """Anonymous by design: the caller says which MP (from the postal lookup); nothing is stored."""
    mp = db.scalar(select(Person).where(Person.slug == payload.mp_slug))
    if mp is None:
        raise HTTPException(status_code=404, detail="MP not found — check the slug from the postal lookup.")

    letter = build_letter(
        db,
        mp=mp,
        concern=payload.concern,
        bill_session=payload.bill_session,
        bill_number=payload.bill_number,
    )
    if payload.polish:
        letter = await polish_letter(db, letter)

    return LetterResponse(
        letter_text=letter.letter_text,
        mp_name=letter.mp_name,
        mp_email=letter.mp_email,
        riding=letter.riding,
        citations=[
            CitationModel(
                vote_number=c.vote_number,
                session=c.session,
                occurred_on=c.occurred_on.isoformat(),
                description_en=c.description_en,
                effect=c.effect,
                ballot=c.ballot,
            )
            for c in letter.citations
        ],
        polished=letter.polished,
    )
