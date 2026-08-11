from __future__ import annotations

from datetime import date
from statistics import median

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import ExpenseItem, ExpenseSummary, IntegrityFlag, Person
from app.schemas.common import PageMeta


router = APIRouter(tags=["expenses"])

CATEGORIES = ("travel", "hospitality", "contract")


class QuarterTotals(BaseModel):
    fiscal_year: int
    quarter: int
    salaries: float
    travel: float
    hospitality: float
    contracts: float
    total: float
    caucus_median_total: float | None = None


class ExpenseItemModel(BaseModel):
    id: int
    category: str
    fiscal_year: int
    quarter: int
    supplier: str | None = None
    description: str | None = None
    occurred_on: date | None = None
    amount: float
    traveller_name: str | None = None
    traveller_type: str | None = None
    purpose: str | None = None
    city: str | None = None
    source_url: str
    mp_name: str | None = None
    mp_slug: str | None = None
    flagged: bool = False


class MpExpensesResponse(BaseModel):
    slug: str
    full_name: str
    quarters: list[QuarterTotals]
    top_items: list[ExpenseItemModel]
    top_suppliers: list[dict]
    flags: list[dict]
    sources_note: str


def _item_model(item: ExpenseItem, *, mp_name: str | None = None, mp_slug: str | None = None, flagged: bool = False) -> ExpenseItemModel:
    return ExpenseItemModel(
        id=item.id,
        category=item.category,
        fiscal_year=item.fiscal_year,
        quarter=item.quarter,
        supplier=item.supplier,
        description=item.description,
        occurred_on=item.occurred_on,
        amount=item.amount,
        traveller_name=item.traveller_name,
        traveller_type=item.traveller_type,
        purpose=item.purpose,
        city=item.city,
        source_url=item.source_url,
        mp_name=mp_name,
        mp_slug=mp_slug,
        flagged=flagged,
    )


@router.get("/politicians/{slug}/expenses", response_model=MpExpensesResponse)
def politician_expenses(slug: str, db: Session = Depends(get_db)) -> MpExpensesResponse:
    person = db.scalar(select(Person).where(Person.slug == slug))
    if person is None:
        raise HTTPException(status_code=404, detail="Politician not found")

    summaries = db.scalars(
        select(ExpenseSummary)
        .where(ExpenseSummary.person_id == person.id)
        .order_by(ExpenseSummary.fiscal_year.desc(), ExpenseSummary.quarter.desc())
        .limit(12)
    ).all()

    # Caucus median (total of 4 categories) per quarter, for context lines.
    quarters: list[QuarterTotals] = []
    for s in summaries:
        caucus_median = None
        if s.caucus:
            peer_rows = db.execute(
                select(
                    ExpenseSummary.salaries
                    + ExpenseSummary.travel
                    + ExpenseSummary.hospitality
                    + ExpenseSummary.contracts
                ).where(
                    ExpenseSummary.caucus == s.caucus,
                    ExpenseSummary.fiscal_year == s.fiscal_year,
                    ExpenseSummary.quarter == s.quarter,
                )
            ).scalars().all()
            if len(peer_rows) >= 5:
                caucus_median = round(median(float(v) for v in peer_rows), 2)
        quarters.append(
            QuarterTotals(
                fiscal_year=s.fiscal_year,
                quarter=s.quarter,
                salaries=s.salaries,
                travel=s.travel,
                hospitality=s.hospitality,
                contracts=s.contracts,
                total=round(s.salaries + s.travel + s.hospitality + s.contracts, 2),
                caucus_median_total=caucus_median,
            )
        )

    top_items = db.scalars(
        select(ExpenseItem)
        .where(ExpenseItem.person_id == person.id)
        .order_by(ExpenseItem.amount.desc())
        .limit(8)
    ).all()

    top_suppliers = [
        {"supplier": supplier, "total": round(float(total), 2), "count": int(count)}
        for supplier, total, count in db.execute(
            select(ExpenseItem.supplier, func.sum(ExpenseItem.amount), func.count())
            .where(ExpenseItem.person_id == person.id, ExpenseItem.supplier.is_not(None))
            .group_by(ExpenseItem.supplier)
            .order_by(func.sum(ExpenseItem.amount).desc())
            .limit(8)
        ).all()
    ]

    flags = db.scalars(
        select(IntegrityFlag).where(
            IntegrityFlag.person_id == person.id,
            IntegrityFlag.status == "published",
            IntegrityFlag.detector.like("expense_%"),
        )
    ).all()

    return MpExpensesResponse(
        slug=person.slug,
        full_name=person.full_name,
        quarters=quarters,
        top_items=[_item_model(i) for i in top_items],
        top_suppliers=top_suppliers,
        flags=[
            {
                "detector": f.detector,
                "headline_en": f.headline_en,
                "detail_en": f.detail_en,
                "evidence": f.evidence,
            }
            for f in flags
        ],
        sources_note=(
            "Source: House of Commons Members' Expenditures (Proactive "
            "Disclosure), quarterly. Salaries are staff payroll budgets, not "
            "the MP's own pay. Flagged patterns are human-reviewed before "
            "publishing."
        ),
    )


@router.get("/expenses/search")
def search_expenses(
    q: str | None = Query(default=None, max_length=200),
    category: str | None = Query(default=None, pattern="^(travel|hospitality|contract)$"),
    fiscal_year: int | None = None,
    min_amount: float | None = Query(default=None, ge=0),
    traveller_type: str | None = Query(default=None, max_length=64),
    sort: str = Query(default="amount", pattern="^(amount|date)$"),
    limit: int = Query(default=25, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> dict:
    """Cross-MP searchable expense explorer. Biggest-first by default."""
    query = select(ExpenseItem)
    if q:
        needle = q.strip().lower()
        query = query.where(
            or_(
                func.lower(func.coalesce(ExpenseItem.supplier, "")).contains(needle),
                func.lower(func.coalesce(ExpenseItem.description, "")).contains(needle),
                func.lower(func.coalesce(ExpenseItem.purpose, "")).contains(needle),
                func.lower(func.coalesce(ExpenseItem.city, "")).contains(needle),
                func.lower(ExpenseItem.mp_name_raw).contains(needle),
            )
        )
    if category:
        query = query.where(ExpenseItem.category == category)
    if fiscal_year:
        query = query.where(ExpenseItem.fiscal_year == fiscal_year)
    if min_amount is not None:
        query = query.where(ExpenseItem.amount >= min_amount)
    if traveller_type:
        query = query.where(func.lower(ExpenseItem.traveller_type) == traveller_type.lower())

    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    order = ExpenseItem.amount.desc() if sort == "amount" else ExpenseItem.occurred_on.desc().nullslast()
    items = db.scalars(query.order_by(order).offset(offset).limit(limit)).all()

    # MP display info + published-flag markers, batched.
    person_ids = {i.person_id for i in items if i.person_id}
    people = {
        pid: (name, slug)
        for pid, name, slug in db.execute(
            select(Person.id, Person.full_name, Person.slug).where(Person.id.in_(person_ids or {0}))
        ).all()
    }
    flagged_person_ids = {
        row[0]
        for row in db.execute(
            select(IntegrityFlag.person_id).where(
                IntegrityFlag.status == "published",
                IntegrityFlag.detector.like("expense_%"),
                IntegrityFlag.person_id.in_(person_ids or {0}),
            )
        ).all()
    }

    return {
        "items": [
            _item_model(
                item,
                mp_name=people.get(item.person_id, (item.mp_name_raw, None))[0] if item.person_id else item.mp_name_raw,
                mp_slug=people.get(item.person_id, (None, None))[1] if item.person_id else None,
                flagged=item.person_id in flagged_person_ids,
            ).model_dump()
            for item in items
        ],
        "meta": PageMeta(total=total, limit=limit, offset=offset).model_dump(),
    }
