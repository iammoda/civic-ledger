from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.core.ratelimit import rate_limit
from app.db.session import get_db
from app.models import Chamber, ExpenseItem, Person, PersonMembership, PersonRole
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


class SearchPersonItem(BaseModel):
    slug: str
    full_name: str
    image_url: str | None = None
    party_slug: str | None = None
    riding: str | None = None
    province_code: str | None = None
    level: str | None = None
    roles: list[str] = []


class SearchExpenseItem(BaseModel):
    id: int
    supplier: str | None = None
    description: str | None = None
    category: str
    amount: float
    quarter: int
    fiscal_year: int
    mp_name: str | None = None
    mp_slug: str | None = None
    source_url: str


class SearchResponse(BaseModel):
    query: str
    results: list[SearchResultItem]
    people: list[SearchPersonItem] = []
    expenses: list[SearchExpenseItem] = []


def _search_people(db: Session, q: str, *, limit: int = 8) -> list[SearchPersonItem]:
    """Representatives matched by name or riding (current memberships).

    Exact-prefix name matches lead so "jag" surfaces "Jagmeet Singh" ahead of
    anyone whose riding merely contains the string.
    """
    from app.api.politicians import _current_membership, _level_of

    needle = q.strip().lower()
    name_prefix = func.lower(Person.full_name).startswith(needle, autoescape=True)
    people = db.scalars(
        select(Person)
        .where(
            or_(
                func.lower(Person.full_name).contains(needle, autoescape=True),
                Person.memberships.any(
                    and_(
                        PersonMembership.is_current.is_(True),
                        func.lower(func.coalesce(PersonMembership.riding_name, "")).contains(
                            needle, autoescape=True
                        ),
                    )
                ),
            )
        )
        .options(
            selectinload(Person.memberships).selectinload(PersonMembership.party),
            selectinload(Person.chamber).selectinload(Chamber.jurisdiction),
        )
        .order_by(name_prefix.desc(), Person.full_name)
        .limit(limit)
    ).all()
    if not people:
        return []

    # Current cabinet/officer titles, batched (e.g. "Minister of Finance").
    roles_by_person: dict[int, list[str]] = {}
    for person_id, title in db.execute(
        select(PersonRole.person_id, PersonRole.title_en)
        .where(
            PersonRole.person_id.in_([p.id for p in people]),
            PersonRole.is_current.is_(True),
        )
        .order_by(PersonRole.id)
    ).all():
        roles_by_person.setdefault(person_id, []).append(title)

    items: list[SearchPersonItem] = []
    for person in people:
        membership = _current_membership(person)
        items.append(
            SearchPersonItem(
                slug=person.slug,
                full_name=person.full_name,
                image_url=person.image_url,
                party_slug=membership.party.slug if membership and membership.party else None,
                riding=membership.riding_name if membership else None,
                province_code=membership.province_code if membership else None,
                level=_level_of(person),
                roles=roles_by_person.get(person.id, []),
            )
        )
    return items


def _search_expenses(db: Session, q: str, *, limit: int = 8) -> list[SearchExpenseItem]:
    """Expense line items — same matching as /v1/expenses/search, biggest first."""
    needle = q.strip().lower()
    items = db.scalars(
        select(ExpenseItem)
        .where(
            or_(
                func.lower(func.coalesce(ExpenseItem.supplier, "")).contains(needle, autoescape=True),
                func.lower(func.coalesce(ExpenseItem.description, "")).contains(needle, autoescape=True),
                func.lower(func.coalesce(ExpenseItem.purpose, "")).contains(needle, autoescape=True),
                func.lower(func.coalesce(ExpenseItem.city, "")).contains(needle, autoescape=True),
                func.lower(ExpenseItem.mp_name_raw).contains(needle, autoescape=True),
            )
        )
        .order_by(ExpenseItem.amount.desc())
        .limit(limit)
    ).all()
    if not items:
        return []

    person_ids = {i.person_id for i in items if i.person_id}
    people: dict[int, tuple[str, str | None]] = {
        pid: (name, slug)
        for pid, name, slug in db.execute(
            select(Person.id, Person.full_name, Person.slug).where(Person.id.in_(person_ids or {0}))
        ).all()
    }

    results: list[SearchExpenseItem] = []
    for item in items:
        name, slug = people.get(item.person_id or 0, (item.mp_name_raw, None))
        results.append(
            SearchExpenseItem(
                id=item.id,
                supplier=item.supplier,
                description=item.description,
                category=item.category,
                amount=item.amount,
                quarter=item.quarter,
                fiscal_year=item.fiscal_year,
                mp_name=name,
                mp_slug=slug,
                source_url=item.source_url,
            )
        )
    return results


@router.get(
    "/search",
    response_model=SearchResponse,
    # Each search can trigger an embedding call — throttle per IP.
    dependencies=[Depends(rate_limit("search", limit=30, window_seconds=60))],
)
async def search(
    q: str = Query(min_length=2, max_length=200),
    limit: int = Query(default=20, le=50),
    db: Session = Depends(get_db),
) -> SearchResponse:
    results = await hybrid_search(db, q, limit=limit)
    # People + expenses run after hybrid_search (the session is sync — used
    # sequentially, in a worker thread so slow queries can't stall the loop).
    people, expenses = await asyncio.to_thread(
        lambda: (_search_people(db, q), _search_expenses(db, q))
    )
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
        people=people,
        expenses=expenses,
    )


class AskRequest(BaseModel):
    question: str = Field(min_length=8, max_length=500)
    # Optional MP slug (from the anonymous postal lookup) to weave their ballots in.
    mp_slug: str | None = Field(default=None, max_length=255)


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


@router.post(
    "/ask",
    response_model=AskResponseModel,
    # LLM-backed: the costliest endpoint on the site. Budget/quota exhaustion
    # degrades inside the service; this guards against per-IP hammering.
    dependencies=[Depends(rate_limit("ask", limit=10, window_seconds=600))],
)
async def ask_question(
    payload: AskRequest,
    db: Session = Depends(get_db),
) -> AskResponseModel:
    # Anonymous: callers who know their MP (postal lookup) get that MP's ballots woven in.
    mp_person_id: int | None = None
    if payload.mp_slug:
        person = db.scalar(select(Person).where(Person.slug == payload.mp_slug))
        if person is not None:
            mp_person_id = person.id

    try:
        response = await run_ask(db, payload.question.strip(), mp_person_id=mp_person_id)
    except RuntimeError as exc:
        # Never leak internals (budget state, provider errors) to clients.
        raise HTTPException(
            status_code=503,
            detail="Ask is temporarily unavailable — please try again shortly.",
        ) from exc

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
