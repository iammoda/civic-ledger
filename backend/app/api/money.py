from __future__ import annotations

from collections import Counter
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.ratelimit import rate_limit
from app.db.session import get_db
from app.models import Contribution, Correction, IntegrityFlag, LobbyCommunication, Person
from app.services.lazy import enqueue


router = APIRouter(tags=["money"])

REGISTRY_URL = "https://lobbycanada.gc.ca/app/secure/ocl/lrs/do/cmmLgPblcVw?comlogId={comlog}"


def _registry_url(source_ref: str | None) -> str | None:
    if not source_ref:
        return None
    comlog = source_ref.split("-", 1)[0].strip()
    return REGISTRY_URL.format(comlog=comlog) if comlog.isdigit() else None


class LobbyCommItem(BaseModel):
    comm_date: date | None = None
    client_name: str | None = None
    client_description: str | None = None
    registrant_name: str | None = None
    subjects: str | None = None
    institution: str | None = None
    dpoh_title: str | None = None
    registry_url: str | None = None


class TopClient(BaseModel):
    name: str
    count: int
    # One-line "what is this org" (AI-generated, cached, human language).
    description: str | None = None


class SubjectCount(BaseModel):
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
    top_subjects: list[SubjectCount]
    recent_communications: list[LobbyCommItem]
    donations_total: float
    donations_count: int
    top_donors: list[TopDonor]
    flags: list[FlagItem]
    sources_note: str


@router.get("/politicians/{slug}/money", response_model=MoneyResponse)
async def politician_money(slug: str, db: Session = Depends(get_db)) -> MoneyResponse:
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

    top_client_rows = db.execute(
        select(LobbyCommunication.client_name, func.count().label("n"))
        .where(LobbyCommunication.dpoh_person_id == person.id, LobbyCommunication.client_name.is_not(None))
        .group_by(LobbyCommunication.client_name)
        .order_by(func.count().desc())
        .limit(10)
    ).all()

    # Org blurbs: cached where available; unknown orgs get a lazy job (cheap, budget-gated).
    from app.llm.org_profiles import published_profiles, unprofiled

    client_names = [name for name, _ in top_client_rows]
    descriptions = published_profiles(db, client_names)
    missing = unprofiled(db, client_names)
    if missing:
        await enqueue("profile_lobby_orgs_job", missing)

    top_clients = [
        TopClient(name=name, count=count, description=descriptions.get(name))
        for name, count in top_client_rows
    ]

    # What they're lobbied ABOUT: aggregate the registry's own subject codes.
    subject_counter: Counter[str] = Counter()
    for (subjects,) in db.execute(
        select(LobbyCommunication.subjects).where(
            LobbyCommunication.dpoh_person_id == person.id, LobbyCommunication.subjects.is_not(None)
        )
    ).all():
        for raw in (subjects or "").split(","):
            name = raw.strip()
            if name:
                subject_counter[name] += 1
    top_subjects = [SubjectCount(name=name, count=count) for name, count in subject_counter.most_common(8)]

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
        top_subjects=top_subjects,
        recent_communications=[
            LobbyCommItem(
                comm_date=c.comm_date,
                client_name=c.client_name,
                client_description=descriptions.get(c.client_name or ""),
                registrant_name=c.registrant_name,
                subjects=c.subjects,
                institution=c.institution,
                dpoh_title=c.dpoh_title,
                registry_url=_registry_url(c.source_ref),
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


class LobbyingSearchResponse(BaseModel):
    slug: str
    full_name: str
    total: int
    items: list[LobbyCommItem]
    subjects: list[SubjectCount]


@router.get("/politicians/{slug}/lobbying", response_model=LobbyingSearchResponse)
def politician_lobbying(
    slug: str,
    q: str | None = Query(default=None, max_length=200),
    subject: str | None = Query(default=None, max_length=200),
    limit: int = Query(default=25, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> LobbyingSearchResponse:
    """Every registered lobbying contact naming this MP — searchable.

    Each row is a communication report a lobbyist was legally required to
    file: a meeting, call, or arranged communication with this office holder.
    """
    person = db.scalar(select(Person).where(Person.slug == slug))
    if person is None:
        raise HTTPException(status_code=404, detail="Politician not found")

    query = select(LobbyCommunication).where(LobbyCommunication.dpoh_person_id == person.id)
    if q:
        needle = q.strip().lower()
        query = query.where(
            or_(
                func.lower(func.coalesce(LobbyCommunication.client_name, "")).contains(needle, autoescape=True),
                func.lower(func.coalesce(LobbyCommunication.registrant_name, "")).contains(needle, autoescape=True),
                func.lower(func.coalesce(LobbyCommunication.subjects, "")).contains(needle, autoescape=True),
            )
        )
    if subject:
        query = query.where(
            func.lower(func.coalesce(LobbyCommunication.subjects, "")).contains(subject.strip().lower(), autoescape=True)
        )

    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    comms = db.scalars(
        query.order_by(LobbyCommunication.comm_date.desc().nullslast()).offset(offset).limit(limit)
    ).all()

    from app.llm.org_profiles import published_profiles

    descriptions = published_profiles(db, [c.client_name or "" for c in comms])

    # Subject chips for the filter bar (all-time, unfiltered).
    subject_counter: Counter[str] = Counter()
    for (subjects_val,) in db.execute(
        select(LobbyCommunication.subjects).where(
            LobbyCommunication.dpoh_person_id == person.id, LobbyCommunication.subjects.is_not(None)
        )
    ).all():
        for raw in (subjects_val or "").split(","):
            name = raw.strip()
            if name:
                subject_counter[name] += 1

    return LobbyingSearchResponse(
        slug=person.slug,
        full_name=person.full_name,
        total=total,
        items=[
            LobbyCommItem(
                comm_date=c.comm_date,
                client_name=c.client_name,
                client_description=descriptions.get(c.client_name or ""),
                registrant_name=c.registrant_name,
                subjects=c.subjects,
                institution=c.institution,
                dpoh_title=c.dpoh_title,
                registry_url=_registry_url(c.source_ref),
            )
            for c in comms
        ],
        subjects=[SubjectCount(name=name, count=count) for name, count in subject_counter.most_common(12)],
    )


@router.post(
    "/corrections",
    status_code=201,
    # Unauthenticated public write — throttle to keep spam manageable.
    dependencies=[Depends(rate_limit("corrections", limit=5, window_seconds=3600))],
)
def submit_correction(payload: CorrectionRequest, db: Session = Depends(get_db)) -> dict:
    correction = Correction(
        page_url=payload.page_url.strip(),
        message=payload.message.strip(),
        contact=(payload.contact or "").strip() or None,
    )
    db.add(correction)
    db.commit()
    return {"ok": True, "id": correction.id}
