from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db.session import get_db
from app.models import Chamber, Debate, Speech
from app.schemas.common import AnalysisState
from app.schemas.debates import DebateDetail, SpeechItem


router = APIRouter(prefix="/debates", tags=["debates"])


@router.get("/{chamber}/{debate_date}", response_model=DebateDetail)
def get_debate(chamber: str, debate_date: date, db: Session = Depends(get_db)) -> DebateDetail:
    debate = db.scalar(
        select(Debate)
        .join(Chamber, Debate.chamber_id == Chamber.id)
        .where(Debate.occurred_on == debate_date, Chamber.slug == chamber)
        .options(selectinload(Debate.chamber), selectinload(Debate.speeches))
    )
    if debate is None:
        raise HTTPException(status_code=404, detail="Debate not found")

    return DebateDetail(
        chamber=debate.chamber.slug,
        occurred_on=debate.occurred_on,
        title_en=debate.title_en,
        source_url=debate.source_url,
        speeches=[
            SpeechItem(
                sequence=speech.sequence,
                heading_en=speech.heading_en,
                topic_slug=speech.topic_slug,
                content_en=speech.content_en,
            )
            for speech in sorted(debate.speeches, key=lambda item: item.sequence)
        ],
        analyses=[],
        related_bills=[],
    )
