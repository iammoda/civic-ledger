from __future__ import annotations

from datetime import date
from statistics import median

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.ratelimit import rate_limit
from app.db.session import get_db
from app.models import ExpenseItem, ExpenseSummary, IntegrityFlag, Party, Person, PersonMembership
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
    mp_image_url: str | None = None
    mp_party: str | None = None
    flagged: bool = False


class BudgetContext(BaseModel):
    """Office-budget utilization for the latest fiscal year on record.

    annual_budget comes from configuration (the BOIE-published base Members'
    Office Budget) — when unset, the block is omitted rather than invented.
    """

    fiscal_year: int
    annual_budget: float
    ytd_total: float
    quarters_reported: int
    utilization_pct: float
    note: str


class MpExpensesResponse(BaseModel):
    slug: str
    full_name: str
    quarters: list[QuarterTotals]
    top_items: list[ExpenseItemModel]
    top_suppliers: list[dict]
    flags: list[dict]
    sources_note: str
    budget: BudgetContext | None = None
    # Where their latest-quarter total sits among ALL MPs that quarter (0-100).
    spend_percentile: float | None = None
    mp_annual_salary: float | None = None


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

    # Budget utilization (configured base MOB; hidden when unset — no invented numbers).
    from app.core.config import get_settings

    settings = get_settings()
    budget: BudgetContext | None = None
    if quarters and settings.mob_annual_budget > 0:
        latest_fy = quarters[0].fiscal_year
        fy_quarters = [q for q in quarters if q.fiscal_year == latest_fy]
        ytd = round(sum(q.total for q in fy_quarters), 2)
        budget = BudgetContext(
            fiscal_year=latest_fy,
            annual_budget=settings.mob_annual_budget,
            ytd_total=ytd,
            quarters_reported=len(fy_quarters),
            utilization_pct=round(100.0 * ytd / settings.mob_annual_budget, 1),
            note=(
                "Against the base Members' Office Budget set by the Board of "
                "Internal Economy. Large or remote ridings get supplements on "
                "top of the base, so their true budget is higher."
            ),
        )

    # Percentile among ALL MPs for the latest quarter on record.
    spend_percentile: float | None = None
    if quarters:
        latest = quarters[0]
        peer_totals = db.execute(
            select(
                ExpenseSummary.salaries
                + ExpenseSummary.travel
                + ExpenseSummary.hospitality
                + ExpenseSummary.contracts
            ).where(
                ExpenseSummary.fiscal_year == latest.fiscal_year,
                ExpenseSummary.quarter == latest.quarter,
            )
        ).scalars().all()
        values = [float(v) for v in peer_totals]
        if len(values) >= 20:
            below = sum(1 for v in values if v < latest.total)
            spend_percentile = round(100.0 * below / len(values), 0)

    return MpExpensesResponse(
        slug=person.slug,
        full_name=person.full_name,
        quarters=quarters,
        top_items=[_item_model(i) for i in top_items],
        top_suppliers=top_suppliers,
        budget=budget,
        spend_percentile=spend_percentile,
        mp_annual_salary=settings.mp_annual_salary or None,
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


def _expense_search_query(
    q: str | None,
    category: str | None,
    fiscal_year: int | None,
    min_amount: float | None,
    traveller_type: str | None,
):
    """Shared filter set for the JSON explorer and the CSV export."""
    query = select(ExpenseItem)
    if q:
        needle = q.strip().lower()
        query = query.where(
            or_(
                func.lower(func.coalesce(ExpenseItem.supplier, "")).contains(needle, autoescape=True),
                func.lower(func.coalesce(ExpenseItem.description, "")).contains(needle, autoescape=True),
                func.lower(func.coalesce(ExpenseItem.purpose, "")).contains(needle, autoescape=True),
                func.lower(func.coalesce(ExpenseItem.city, "")).contains(needle, autoescape=True),
                func.lower(ExpenseItem.mp_name_raw).contains(needle, autoescape=True),
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
    return query


CSV_EXPORT_CAP = 10_000


@router.get(
    "/expenses/search.csv",
    # Bulk export: cheap per row but big; keep scrapers polite.
    dependencies=[Depends(rate_limit("export", limit=10, window_seconds=600))],
)
def search_expenses_csv(
    q: str | None = Query(default=None, max_length=200),
    category: str | None = Query(default=None, pattern="^(travel|hospitality|contract)$"),
    fiscal_year: int | None = None,
    min_amount: float | None = Query(default=None, ge=0),
    traveller_type: str | None = Query(default=None, max_length=64),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    """The current expense search, as a CSV — for journalists and spreadsheets.

    Same filters as /expenses/search; capped at 10k rows (narrow the filters
    for more specific slices). Data source: House of Commons Members' Expenditure
    Reports (Proactive Disclosure).
    """
    import csv
    import io

    query = _expense_search_query(q, category, fiscal_year, min_amount, traveller_type)
    items = db.scalars(query.order_by(ExpenseItem.amount.desc()).limit(CSV_EXPORT_CAP)).all()

    def rows():
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(
            ["fiscal_year", "quarter", "date", "mp_name", "category", "supplier",
             "description", "purpose", "city", "traveller_type", "amount_cad"]
        )
        for item in items:
            writer.writerow([
                item.fiscal_year, item.quarter,
                item.occurred_on.isoformat() if item.occurred_on else "",
                item.mp_name_raw, item.category, item.supplier or "",
                item.description or "", item.purpose or "", item.city or "",
                item.traveller_type or "", f"{item.amount:.2f}",
            ])
            yield buffer.getvalue()
            buffer.seek(0)
            buffer.truncate(0)

    return StreamingResponse(
        rows(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="mp-expenses.csv"'},
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
    query = _expense_search_query(q, category, fiscal_year, min_amount, traveller_type)

    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    order = ExpenseItem.amount.desc() if sort == "amount" else ExpenseItem.occurred_on.desc().nullslast()
    items = db.scalars(query.order_by(order).offset(offset).limit(limit)).all()

    # MP display info (name, slug, photo, party) + published-flag markers, batched.
    person_ids = {i.person_id for i in items if i.person_id}
    people: dict[int, tuple[str, str, str | None]] = {
        pid: (name, slug, image_url)
        for pid, name, slug, image_url in db.execute(
            select(Person.id, Person.full_name, Person.slug, Person.image_url).where(
                Person.id.in_(person_ids or {0})
            )
        ).all()
    }
    parties: dict[int, str | None] = {
        pid: party_slug
        for pid, party_slug in db.execute(
            select(PersonMembership.person_id, Party.slug)
            .join(Party, PersonMembership.party_id == Party.id)
            .where(PersonMembership.person_id.in_(person_ids or {0}), PersonMembership.is_current.is_(True))
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

    def _search_model(item: ExpenseItem) -> ExpenseItemModel:
        name, slug, image_url = people.get(item.person_id or 0, (item.mp_name_raw, None, None))
        model = _item_model(
            item,
            mp_name=name if item.person_id else item.mp_name_raw,
            mp_slug=slug if item.person_id else None,
            flagged=item.person_id in flagged_person_ids,
        )
        model.mp_image_url = image_url if item.person_id else None
        model.mp_party = parties.get(item.person_id or 0)
        return model

    return {
        "items": [_search_model(item).model_dump() for item in items],
        "meta": PageMeta(total=total, limit=limit, offset=offset).model_dump(),
    }
