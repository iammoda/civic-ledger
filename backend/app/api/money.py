from __future__ import annotations

from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import Contribution, Correction, IntegrityFlag, LobbyCommunication, Person


router = APIRouter(tags=["money"])


class LobbyCommItem(BaseModel):
    comm_date: date | None = None
    client_name: str | None = None
    registrant_name: str | None = None
    subjects: str | None = None


class TopClient(BaseModel):
    name: str
    count: int


class TopDonor(BaseModel):
    name: str
    total: float
    count: int


class FlagItem(BaseModel):
    detector: str
    headline_en: str
    detail_en: str | None = None
    confidence: float | None = None
    evidence: dict | None = None
    created_at_date: str | None = None


class MoneyResponse(BaseModel):
    slug: str
    full_name: str
    lobbying_total: int
    lobbying_last_12mo: int
    top_clients: list[TopClient]
    recent_communications: list[LobbyCommItem]
    donations_total: float
    donations_count: int
    top_donors: list[TopDonor]
    flags: list[FlagItem]
    sources_note: str


@router.get("/politicians/{slug}/money", response_model=MoneyResponse)
def politician_money(slug: str, db: Session = Depends(get_db)) -> MoneyResponse:
    person = db.scalar(select(Person).where(Person.slug == slug))
    if person is None:
        raise HTTPException(status_code=404, detail="Politician not found")

    lobbying_total = db.scalar(
        select(func.count()).select_from(LobbyCommunication).where(LobbyCommunication.dpoh_person_id == person.id)
    ) or 0
    year_ago = date.today() - timedelta(days=365)
    lobbying_last_12mo = db.scalar(
        select(func.count())
        .select_from(LobbyCommunication)
        .where(LobbyCommunication.dpoh_person_id == person.id, LobbyCommunication.comm_date >= year_ago)
    ) or 0

    top_clients = [
        TopClient(name=name, count=count)
        for name, count in db.execute(
            select(LobbyCommunication.client_name, func.count().label("n"))
            .where(LobbyCommunication.dpoh_person_id == person.id, LobbyCommunication.client_name.is_not(None))
            .group_by(LobbyCommunication.client_name)
            .order_by(func.count().desc())
            .limit(10)
        ).all()
    ]

    recent = db.scalars(
        select(LobbyCommunication)
        .where(LobbyCommunication.dpoh_person_id == person.id)
        .order_by(LobbyCommunication.comm_date.desc().nullslast())
        .limit(15)
    ).all()

    donations_total = db.scalar(
        select(func.coalesce(func.sum(Contribution.amount), 0.0)).where(
            Contribution.recipient_person_id == person.id
        )
    ) or 0.0
    donations_count = db.scalar(
        select(func.count()).select_from(Contribution).where(Contribution.recipient_person_id == person.id)
    ) or 0

    top_donors = [
        TopDonor(name=name, total=float(total), count=count)
        for name, total, count in db.execute(
            select(
                Contribution.contributor_name,
                func.sum(Contribution.amount).label("total"),
                func.count().label("n"),
            )
            .where(Contribution.recipient_person_id == person.id)
            .group_by(Contribution.contributor_name)
            .order_by(func.sum(Contribution.amount).desc())
            .limit(10)
        ).all()
    ]

    # Only human-approved flags are public.
    flags = db.scalars(
        select(IntegrityFlag)
        .where(IntegrityFlag.person_id == person.id, IntegrityFlag.status == "published")
        .order_by(IntegrityFlag.created_at.desc())
    ).all()

    return MoneyResponse(
        slug=person.slug,
        full_name=person.full_name,
        lobbying_total=lobbying_total,
        lobbying_last_12mo=lobbying_last_12mo,
        top_clients=top_clients,
        recent_communications=[
            LobbyCommItem(
                comm_date=c.comm_date,
                client_name=c.client_name,
                registrant_name=c.registrant_name,
                subjects=c.subjects,
            )
            for c in recent
        ],
        donations_total=float(donations_total),
        donations_count=donations_count,
        top_donors=top_donors,
        flags=[
            FlagItem(
                detector=f.detector,
                headline_en=f.headline_en,
                detail_en=f.detail_en,
                confidence=f.confidence,
                evidence=f.evidence,
                created_at_date=f.created_at.date().isoformat() if f.created_at else None,
            )
            for f in flags
        ],
        sources_note=(
            "Lobbying: Registry of Lobbyists communication reports. Donations: "
            "Elections Canada financial returns. Flagged patterns are "
            "human-reviewed before publishing and describe verifiable records, "
            "not conclusions."
        ),
    )


class CorrectionRequest(BaseModel):
    page_url: str = Field(min_length=1, max_length=1000)
    message: str = Field(min_length=10, max_length=5000)
    contact: str | None = Field(default=None, max_length=255)


@router.post("/corrections", status_code=201)
def submit_correction(payload: CorrectionRequest, db: Session = Depends(get_db)) -> dict:
    correction = Correction(
        page_url=payload.page_url.strip(),
        message=payload.message.strip(),
        contact=(payload.contact or "").strip() or None,
    )
    db.add(correction)
    db.commit()
    return {"ok": True, "id": correction.id}
