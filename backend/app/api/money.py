from __future__ import annotations

from collections import Counter
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.ratelimit import rate_limit
from app.db.session import get_db
from app.models import Chamber, Contribution, Correction, IntegrityFlag, LobbyCommunication, LobbyRegistration, LobbyRegistrationMpp, Person
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
    # Privacy by design: federal donors are private individuals (corporate
    # donations are banned) capped at ~$1,700/yr. We publish aggregates only —
    # naming ordinary citizens would punish participation, not power.
    flags: list[FlagItem]
    sources_note: str


@router.get("/politicians/{slug}/money", response_model=MoneyResponse)
async def politician_money(slug: str, db: Session = Depends(get_db)) -> MoneyResponse:
    # DB aggregation runs in the threadpool (it's a dozen queries); only the
    # lazy org-profile enqueue (async Redis) stays on the event loop.
    response, missing_orgs = await run_in_threadpool(_politician_money_sync, db, slug)
    if missing_orgs:
        await enqueue("profile_lobby_orgs_job", missing_orgs)
    return response


def _politician_money_sync(db: Session, slug: str) -> tuple[MoneyResponse, list[str]]:
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

    # Org blurbs: cached where available; unknown orgs get a lazy job (cheap,
    # budget-gated) — enqueued by the async wrapper.
    from app.llm.org_profiles import published_profiles, unprofiled

    client_names = [name for name, _ in top_client_rows]
    descriptions = published_profiles(db, client_names)
    missing = unprofiled(db, client_names)

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

    # NOTE: no named donor list, deliberately. Federal donors are private
    # individuals capped at ~$1,700 — naming them would expose ordinary
    # citizens, not power. Aggregates only; the detectors still see the
    # raw rows and human-reviewed flags can cite specifics when warranted.

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
    ), missing


class CorrectionRequest(BaseModel):
    page_url: str = Field(min_length=1, max_length=1000)
    message: str = Field(min_length=10, max_length=5000)
    contact: str | None = Field(default=None, max_length=255)


class LobbyingSearchResponse(BaseModel):
    slug: str
    # Which registry these reports come from: ca (federal) | bc (ORL).
    registry: str = "ca"
    full_name: str
    total: int
    items: list[LobbyCommItem]
    subjects: list[SubjectCount]


def _lobbying_search_query(person_id: int, q: str | None, subject: str | None):
    """Shared filter set for the JSON search and the CSV export."""
    query = select(LobbyCommunication).where(LobbyCommunication.dpoh_person_id == person_id)
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
    return query


CSV_EXPORT_CAP = 10_000


@router.get(
    "/politicians/{slug}/lobbying.csv",
    dependencies=[Depends(rate_limit("export", limit=10, window_seconds=600))],
)
def politician_lobbying_csv(
    slug: str,
    q: str | None = Query(default=None, max_length=200),
    subject: str | None = Query(default=None, max_length=200),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    """Every registered lobbying contact naming this MP, as a CSV.

    Same filters as the search page; capped at 10k rows. Data source:
    Registry of Lobbyists communication reports.
    """
    import csv
    import io

    person = db.scalar(select(Person).where(Person.slug == slug))
    if person is None:
        raise HTTPException(status_code=404, detail="Politician not found")

    query = _lobbying_search_query(person.id, q, subject)
    comms = db.scalars(
        query.order_by(LobbyCommunication.comm_date.desc().nullslast()).limit(CSV_EXPORT_CAP)
    ).all()

    def rows():
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(
            ["date", "client", "lobbyist", "institution", "office_holder_title", "subjects", "registry_url"]
        )
        for c in comms:
            writer.writerow([
                c.comm_date.isoformat() if c.comm_date else "",
                c.client_name or "", c.registrant_name or "", c.institution or "",
                c.dpoh_title or "", c.subjects or "", _registry_url(c.source_ref) or "",
            ])
            yield buffer.getvalue()
            buffer.seek(0)
            buffer.truncate(0)

    return StreamingResponse(
        rows(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="lobbying-{slug}.csv"'},
    )


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

    query = _lobbying_search_query(person.id, q, subject)

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

    chamber = db.scalar(select(Chamber).where(Chamber.id == person.chamber_id)) if person.chamber_id else None
    registry = "bc" if chamber is not None and chamber.slug == "bc-assembly" else "ca"

    return LobbyingSearchResponse(
        slug=person.slug,
        registry=registry,
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

# ---------------------------------------------------------------------------
# Ontario lobbyist registry (registrations — NOT communication logs)
# ---------------------------------------------------------------------------

class OntarioRegistrationItem(BaseModel):
    registration_number: str
    lobbyist_name: str | None = None
    firm_name: str | None = None
    lobbyist_type: str
    client_name: str | None = None
    client_description: str | None = None
    subject_matters: str | None = None
    goals: str | None = None
    target_ministries: list[str] = []
    target_mpp_offices: list[str] = []
    initial_filing_date: date | None = None
    last_amendment_date: date | None = None
    techniques: str | None = None
    registry_note: str


ONTARIO_REGISTRY_NOTE = (
    "Ontario publishes lobbying REGISTRATIONS — who is registered to lobby "
    "which offices about what — not per-meeting logs like the federal "
    "registry. A registration means licensed to lobby, never met with."
)


def _registration_item(reg: LobbyRegistration) -> OntarioRegistrationItem:
    return OntarioRegistrationItem(
        registration_number=reg.registration_number,
        lobbyist_name=reg.lobbyist_name,
        firm_name=reg.firm_name,
        lobbyist_type=reg.lobbyist_type,
        client_name=reg.client_name,
        client_description=reg.client_description,
        subject_matters=reg.subject_matters,
        goals=reg.goals,
        target_ministries=(reg.target_ministries or "").split("\n") if reg.target_ministries else [],
        target_mpp_offices=(reg.target_mpp_offices or "").split("\n") if reg.target_mpp_offices else [],
        initial_filing_date=reg.initial_filing_date,
        last_amendment_date=reg.last_amendment_date,
        techniques=reg.techniques,
        registry_note=ONTARIO_REGISTRY_NOTE,
    )


class OntarioRegistrationsResponse(BaseModel):
    total: int
    items: list[OntarioRegistrationItem]
    registry_note: str = ONTARIO_REGISTRY_NOTE


@router.get("/lobbying/ontario", response_model=OntarioRegistrationsResponse)
def ontario_registrations(
    q: str | None = Query(default=None, max_length=200),
    subject: str | None = Query(default=None, max_length=200),
    ministry: str | None = Query(default=None, max_length=200),
    limit: int = Query(default=25, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> OntarioRegistrationsResponse:
    """Ontario's active lobbying registrations, searchable — the provincial
    counterpart to the federal communications explorer."""
    query = select(LobbyRegistration).where(
        LobbyRegistration.status == "active", LobbyRegistration.jurisdiction_code == "on"
    )
    if q:
        for token in q.strip().lower().split()[:6]:
            query = query.where(
                or_(
                    func.lower(func.coalesce(LobbyRegistration.client_name, "")).contains(token, autoescape=True),
                    func.lower(func.coalesce(LobbyRegistration.firm_name, "")).contains(token, autoescape=True),
                    func.lower(func.coalesce(LobbyRegistration.lobbyist_name, "")).contains(token, autoescape=True),
                    func.lower(func.coalesce(LobbyRegistration.goals, "")).contains(token, autoescape=True),
                )
            )
    if subject:
        query = query.where(
            func.lower(func.coalesce(LobbyRegistration.subject_matters, "")).contains(
                subject.strip().lower(), autoescape=True
            )
        )
    if ministry:
        query = query.where(
            func.lower(func.coalesce(LobbyRegistration.target_ministries, "")).contains(
                ministry.strip().lower(), autoescape=True
            )
        )

    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    items = db.scalars(
        query.order_by(LobbyRegistration.last_amendment_date.desc().nullslast()).offset(offset).limit(limit)
    ).all()
    return OntarioRegistrationsResponse(total=total, items=[_registration_item(r) for r in items])


class MppLobbyingResponse(BaseModel):
    slug: str
    full_name: str
    total: int
    # How the filings name this person: their constituency office directly,
    # or a ministry/minister's office they lead.
    office_count: int = 0
    ministry_count: int = 0
    items: list[OntarioRegistrationItem]
    registry_note: str = ONTARIO_REGISTRY_NOTE


@router.get("/politicians/{slug}/lobbying-registrations", response_model=MppLobbyingResponse)
def mpp_lobbying_registrations(
    slug: str,
    limit: int = Query(default=25, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> MppLobbyingResponse:
    """Registrations that name this MPP's office as a lobbying target."""
    person = db.scalar(select(Person).where(Person.slug == slug))
    if person is None:
        raise HTTPException(status_code=404, detail="Politician not found")

    query = (
        select(LobbyRegistration)
        .join(LobbyRegistrationMpp, LobbyRegistrationMpp.registration_id == LobbyRegistration.id)
        .where(LobbyRegistrationMpp.person_id == person.id, LobbyRegistration.status == "active")
    )
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    kind_counts = dict(
        db.execute(
            select(LobbyRegistrationMpp.target_kind, func.count())
            .join(LobbyRegistration, LobbyRegistrationMpp.registration_id == LobbyRegistration.id)
            .where(LobbyRegistrationMpp.person_id == person.id, LobbyRegistration.status == "active")
            .group_by(LobbyRegistrationMpp.target_kind)
        ).all()
    )
    items = db.scalars(
        query.order_by(LobbyRegistration.last_amendment_date.desc().nullslast()).offset(offset).limit(limit)
    ).all()
    return MppLobbyingResponse(
        slug=person.slug,
        full_name=person.full_name,
        total=total,
        office_count=int(kind_counts.get("mpp_office", 0)),
        ministry_count=int(kind_counts.get("ministry", 0)),
        items=[_registration_item(r) for r in items],
    )

class BcCommsResponse(BaseModel):
    total: int
    items: list[LobbyCommItem]
    registry_note: str = (
        "BC publishes per-meeting Lobbying Activity Reports (since May 2020) — "
        "each row is a dated communication a lobbyist was required to report. "
        "Source: Office of the Registrar of Lobbyists for BC, open data."
    )


@router.get("/lobbying/bc", response_model=BcCommsResponse)
def bc_lobbying(
    q: str | None = Query(default=None, max_length=200),
    subject: str | None = Query(default=None, max_length=200),
    limit: int = Query(default=25, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> BcCommsResponse:
    """BC's lobbying activity reports, searchable — real meeting logs, the
    same shape as the federal registry."""
    query = select(LobbyCommunication).where(LobbyCommunication.jurisdiction_code == "bc")
    if q:
        for token in q.strip().lower().split()[:6]:
            query = query.where(
                or_(
                    func.lower(func.coalesce(LobbyCommunication.client_name, "")).contains(token, autoescape=True),
                    func.lower(func.coalesce(LobbyCommunication.registrant_name, "")).contains(token, autoescape=True),
                    func.lower(LobbyCommunication.dpoh_name).contains(token, autoescape=True),
                    func.lower(func.coalesce(LobbyCommunication.institution, "")).contains(token, autoescape=True),
                )
            )
    if subject:
        query = query.where(
            func.lower(func.coalesce(LobbyCommunication.subjects, "")).contains(
                subject.strip().lower(), autoescape=True
            )
        )
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    comms = db.scalars(
        query.order_by(LobbyCommunication.comm_date.desc().nullslast()).offset(offset).limit(limit)
    ).all()
    return BcCommsResponse(
        total=total,
        items=[
            LobbyCommItem(
                comm_date=c.comm_date,
                client_name=c.client_name,
                registrant_name=c.registrant_name,
                subjects=c.subjects,
                institution=c.institution,
                dpoh_title=f"{c.dpoh_name}" + (f" — {c.dpoh_title}" if c.dpoh_title else ""),
                registry_url=None,
            )
            for c in comms
        ],
    )
