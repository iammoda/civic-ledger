"""Engagement endpoints: the homepage digest + The Receipts leaderboards.

Everything here is a pure algorithm over official records — identical math
for every party and every MP. Caveats ship WITH the numbers, not buried in
a methodology page (see the note fields).
"""
from __future__ import annotations

from datetime import date, timedelta

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.db.session import get_db
from app.models import (
    Bill,
    BillDeath,
    Chamber,
    ExpenseItem,
    ExpenseSummary,
    Jurisdiction,
    LegislatureSession,
    LobbyCommunication,
    Person,
    PersonMembership,
    PersonStats,
    Party,
    Vote,
)


router = APIRouter(tags=["engage"])


# ---------------------------------------------------------------------------
# This week in Ottawa (homepage digest)
# ---------------------------------------------------------------------------


class DigestStory(BaseModel):
    kind: str  # closest_vote | biggest_expense | most_lobbied | bill_died
    eyebrow: str
    headline: str
    detail: str | None = None
    url_path: str
    occurred_on: date | None = None


class DigestResponse(BaseModel):
    stories: list[DigestStory]


def _closest_vote_story(db: Session) -> DigestStory | None:
    recent = db.scalars(
        select(Vote)
        .join(Chamber, Vote.chamber_id == Chamber.id)
        .where(Chamber.slug.in_(["house", "senate"]))
        .options(selectinload(Vote.session), selectinload(Vote.chamber), selectinload(Vote.bill))
        .order_by(Vote.occurred_on.desc())
        .limit(50)
    ).all()
    if not recent:
        return None
    cutoff = recent[0].occurred_on - timedelta(days=14)
    window = [v for v in recent if v.occurred_on >= cutoff and (v.yea_total + v.nay_total) > 0]
    if not window:
        return None
    closest = min(window, key=lambda v: abs(v.yea_total - v.nay_total) / (v.yea_total + v.nay_total))
    margin = abs(closest.yea_total - closest.nay_total)
    flip = margin // 2 + 1
    bill_bit = f" on Bill {closest.bill.number}" if closest.bill else ""
    return DigestStory(
        kind="closest_vote",
        eyebrow="Closest vote",
        headline=f"{'Passed' if (closest.result or '').lower() == 'passed' else 'Failed'} by {margin} — "
        f"{flip} MP{'s' if flip != 1 else ''} switching sides would have flipped it{bill_bit}.",
        detail=closest.plain_meaning_en or closest.description_en,
        url_path=f"/votes/{closest.chamber.slug}/{closest.session.label}/{closest.number}",
        occurred_on=closest.occurred_on,
    )


def _biggest_expense_story(db: Session) -> DigestStory | None:
    latest = db.execute(
        select(ExpenseItem.fiscal_year, ExpenseItem.quarter)
        .where(ExpenseItem.scope == "federal")
        .order_by(ExpenseItem.fiscal_year.desc(), ExpenseItem.quarter.desc())
        .limit(1)
    ).first()
    if latest is None:
        return None
    fiscal_year, quarter = latest
    item = db.scalar(
        select(ExpenseItem)
        .where(ExpenseItem.fiscal_year == fiscal_year, ExpenseItem.quarter == quarter, ExpenseItem.scope == "federal")
        .order_by(ExpenseItem.amount.desc())
        .limit(1)
    )
    if item is None:
        return None
    person = db.get(Person, item.person_id) if item.person_id else None
    who = person.full_name if person else item.mp_name_raw
    what = item.supplier or item.description or item.purpose or "an expense"
    return DigestStory(
        kind="biggest_expense",
        eyebrow="Biggest expense filed",
        headline=f"{who} billed ${item.amount:,.0f} to {what}.",
        detail=f"{item.category} · Q{quarter} FY{fiscal_year} — large amounts are often routine; judge for yourself.",
        url_path=f"/politicians/{person.slug}" if person else "/expenses",
        occurred_on=item.occurred_on,
    )


def _most_lobbied_story(db: Session) -> DigestStory | None:
    latest_date = db.scalar(
        select(func.max(LobbyCommunication.comm_date)).where(
            LobbyCommunication.jurisdiction_code == "ca"
        )
    )
    if latest_date is None:
        return None
    cutoff = latest_date - timedelta(days=30)
    row = db.execute(
        select(LobbyCommunication.dpoh_person_id, func.count().label("n"))
        .where(
            LobbyCommunication.dpoh_person_id.is_not(None),
            LobbyCommunication.comm_date >= cutoff,
            LobbyCommunication.jurisdiction_code == "ca",
        )
        .group_by(LobbyCommunication.dpoh_person_id)
        .order_by(func.count().desc())
        .limit(1)
    ).first()
    if row is None:
        return None
    person = db.get(Person, row[0])
    if person is None:
        return None
    return DigestStory(
        kind="most_lobbied",
        eyebrow="Most lobbied this month",
        headline=f"Lobbyists reported {row[1]} contacts with {person.full_name} in 30 days.",
        detail="From the official Registry of Lobbyists. Access, on the record.",
        url_path=f"/politicians/{person.slug}/lobbying",
        occurred_on=latest_date,
    )


def _bill_died_story(db: Session) -> DigestStory | None:
    death = db.scalar(select(BillDeath).order_by(BillDeath.occurred_on.desc().nullslast()).limit(1))
    if death is None:
        return None
    bill = db.get(Bill, death.bill_id)
    if bill is None:
        return None
    session = db.get(LegislatureSession, bill.session_id)
    mechanism = (death.mechanism or "").replace("_", " ")
    title = (bill.short_title_en or "").strip() or bill.title_en
    return DigestStory(
        kind="bill_died",
        eyebrow="From the Graveyard",
        headline=f"Bill {bill.number} — {title} — is dead ({mechanism}).",
        detail=death.attribution_en,
        url_path=f"/bills/{session.label}/{bill.number}" if session else "/graveyard",
        occurred_on=death.occurred_on,
    )


# The digest is identical for every visitor and its inputs change at most a
# few times a day — don't recompute four aggregate scans per homepage hit.
_DIGEST_TTL_SECONDS = 900
_digest_cache: dict[str, object] = {"expires": 0.0, "value": None}


@router.get("/digest", response_model=DigestResponse)
def digest(db: Session = Depends(get_db)) -> DigestResponse:
    """Auto-generated story cards. Pure algorithm, zero editorial picks."""
    import time

    now = time.time()
    cached = _digest_cache["value"]
    if cached is not None and now < float(_digest_cache["expires"]):
        return cached  # type: ignore[return-value]

    stories = [
        story
        for story in (
            _closest_vote_story(db),
            _biggest_expense_story(db),
            _most_lobbied_story(db),
            _bill_died_story(db),
        )
        if story is not None
    ]
    response = DigestResponse(stories=stories)
    _digest_cache["value"] = response
    _digest_cache["expires"] = now + _DIGEST_TTL_SECONDS
    return response


# ---------------------------------------------------------------------------
# The Receipts (leaderboards)
# ---------------------------------------------------------------------------


class ReceiptRow(BaseModel):
    person_slug: str | None = None
    person_name: str
    party: str | None = None
    riding: str | None = None
    image_url: str | None = None
    value: float
    display: str  # pre-formatted value, e.g. "$183,220" or "12 missed"
    context: str | None = None  # per-row context, e.g. supplier name


class ReceiptBoard(BaseModel):
    key: str
    title: str
    subtitle: str
    caveat: str  # ships with the board, on the page — not buried
    rows: list[ReceiptRow]


class ReceiptsResponse(BaseModel):
    boards: list[ReceiptBoard]
    generated_note: str
    # Set when a filter yields no boards for a structural reason (e.g. a
    # province whose legislature publishes no machine-readable votes yet).
    note: str | None = None


def _person_display(db: Session, person_ids: list[int]) -> dict[int, tuple[str, str, str | None, str | None, str | None]]:
    """id -> (name, slug, image_url, party_slug, riding)."""
    if not person_ids:
        return {}
    people = {
        pid: (name, slug, image)
        for pid, name, slug, image in db.execute(
            select(Person.id, Person.full_name, Person.slug, Person.image_url).where(Person.id.in_(person_ids))
        ).all()
    }
    memberships: dict[int, tuple[str | None, str | None]] = {}
    for pid, party_slug, riding, province in db.execute(
        select(
            PersonMembership.person_id,
            Party.slug,
            PersonMembership.riding_name,
            PersonMembership.province_code,
        )
        .outerjoin(Party, PersonMembership.party_id == Party.id)
        .where(PersonMembership.person_id.in_(person_ids), PersonMembership.is_current.is_(True))
    ).all():
        # "Winnipeg South Centre, MB" — the riding alone rarely places the MP.
        if riding and province:
            riding = f"{riding}, {province}"
        memberships[pid] = (party_slug, riding)
    return {
        pid: (name, slug, image, memberships.get(pid, (None, None))[0], memberships.get(pid, (None, None))[1])
        for pid, (name, slug, image) in people.items()
    }


def _latest_quarter(db: Session) -> tuple[int, int] | None:
    row = db.execute(
        select(ExpenseSummary.fiscal_year, ExpenseSummary.quarter)
        .order_by(ExpenseSummary.fiscal_year.desc(), ExpenseSummary.quarter.desc())
        .limit(1)
    ).first()
    return (row[0], row[1]) if row else None


def _biggest_expense_contexts(db: Session, person_ids: list[int], fy: int, q: int) -> dict[int, str]:
    """id -> "biggest: $83,000 contract — Marco Paoli o/a Kylemore Solutions".

    One tiny max-amount lookup per leaderboard row (10 ids) — glance context
    so a big total is immediately explainable without a click.
    """
    contexts: dict[int, str] = {}
    for pid in person_ids:
        item = db.scalar(
            select(ExpenseItem)
            .where(ExpenseItem.person_id == pid, ExpenseItem.fiscal_year == fy, ExpenseItem.quarter == q, ExpenseItem.scope == "federal")
            .order_by(ExpenseItem.amount.desc())
            .limit(1)
        )
        if item is None:
            continue
        what = item.supplier or item.description or item.purpose
        label = f"biggest: ${item.amount:,.0f} {item.category}"
        contexts[pid] = f"{label} — {what}" if what else label
    return contexts


def _top_client_contexts(db: Session, person_ids: list[int], cutoff: date) -> dict[int, str]:
    """id -> "most contacts: Calgary Confederation (31)" for the same window."""
    if not person_ids:
        return {}
    top: dict[int, tuple[str, int]] = {}
    for pid, client, n in db.execute(
        select(LobbyCommunication.dpoh_person_id, LobbyCommunication.client_name, func.count().label("n"))
        .where(
            LobbyCommunication.dpoh_person_id.in_(person_ids),
            LobbyCommunication.comm_date >= cutoff,
            LobbyCommunication.client_name.is_not(None),
        )
        .group_by(LobbyCommunication.dpoh_person_id, LobbyCommunication.client_name)
    ).all():
        if pid not in top or n > top[pid][1]:
            top[pid] = (client, n)
    return {pid: f"most contacts: {client} ({n})" for pid, (client, n) in top.items()}


def _latest_stats_session_id(db: Session, scope: str) -> int | None:
    """Latest session (that has PersonStats) for the requested legislature."""
    query = (
        select(PersonStats.session_id)
        .join(LegislatureSession, PersonStats.session_id == LegislatureSession.id)
        .join(Jurisdiction, LegislatureSession.jurisdiction_id == Jurisdiction.id)
        .order_by(LegislatureSession.parliament_number.desc(), LegislatureSession.session_number.desc())
        .limit(1)
    )
    if scope == "provincial":
        query = query.where(Jurisdiction.level == "provincial", Jurisdiction.code == "ca-on")
    else:
        query = query.where(Jurisdiction.level == "federal")
    return db.scalar(query)


# Ontario ships voting boards only — say why, on the board itself.
_ONTARIO_MONEY_CAVEAT = (
    " Ontario publishes no machine-readable per-MPP expense or lobbying data, "
    "so the money boards remain federal-only."
)

# Provincial vote data exists only for Ontario today — say why, not just 404.
_NON_ONTARIO_PROVINCIAL_NOTE = (
    "Only Ontario publishes machine-readable MPP votes so far — other provinces "
    "appear as their legislatures publish data."
)

_GENERATED_NOTE = (
    "Every board is a straight computation over official records — the same math for every "
    "party and every MP, refreshed as new disclosures land. Nobody hand-picks who appears here."
)


@router.get("/receipts", response_model=ReceiptsResponse)
def receipts(
    scope: str = Query(default="federal", pattern="^(federal|ontario|provincial)$"),
    province: str | None = Query(default=None, max_length=2),
    db: Session = Depends(get_db),
) -> ReceiptsResponse:
    boards: list[ReceiptBoard] = []
    # "ontario" is a backward-compat alias for the provincial scope.
    if scope == "ontario":
        scope = "provincial"
    is_provincial = scope == "provincial"
    province = province.upper() if province else None

    # Provincial vote data exists only for Ontario today: any other province
    # gets an honest, explanatory empty response instead of a silent blank.
    if is_provincial and province not in (None, "ON"):
        return ReceiptsResponse(
            boards=[],
            generated_note=_NON_ONTARIO_PROVINCIAL_NOTE,
            note=_NON_ONTARIO_PROVINCIAL_NOTE,
        )

    # Federal scope + province: restrict every board to people whose CURRENT
    # membership is in that province. Resolved once, applied per board.
    province_person_ids: set[int] | None = None
    if province and not is_provincial:
        province_person_ids = set(
            db.scalars(
                select(PersonMembership.person_id).where(
                    PersonMembership.is_current.is_(True),
                    PersonMembership.province_code == province,
                )
            ).all()
        )
    province_suffix = f" · {province} MPs only" if province_person_ids is not None else ""

    # 1. Top office spenders, latest quarter (federal only — HoC disclosures).
    quarter = _latest_quarter(db) if not is_provincial else None
    if quarter:
        fy, q = quarter
        spend_query = (
            select(
                ExpenseSummary.person_id,
                ExpenseSummary.mp_name_raw,
                (
                    ExpenseSummary.salaries
                    + ExpenseSummary.travel
                    + ExpenseSummary.hospitality
                    + ExpenseSummary.contracts
                ).label("total"),
            )
            .where(ExpenseSummary.fiscal_year == fy, ExpenseSummary.quarter == q)
            .order_by(func.coalesce(
                ExpenseSummary.salaries
                + ExpenseSummary.travel
                + ExpenseSummary.hospitality
                + ExpenseSummary.contracts,
                0,
            ).desc())
            .limit(10)
        )
        if province_person_ids is not None:
            spend_query = spend_query.where(ExpenseSummary.person_id.in_(province_person_ids))
        rows = db.execute(spend_query).all()
        if rows:
            display = _person_display(db, [r[0] for r in rows if r[0]])
            item_contexts = _biggest_expense_contexts(db, [r[0] for r in rows if r[0]], fy, q)
            boards.append(
                ReceiptBoard(
                    key="top_spenders",
                    title="Top office spenders",
                    subtitle=f"Total office spending, Q{q} FY{fy}–{fy + 1}{province_suffix}",
                    caveat=(
                        "High spending is often legitimate: big or northern ridings cost more to serve, "
                        "and staff payroll dominates every MP's budget. Every line traces to the official "
                        "disclosure — click through and judge for yourself."
                    ),
                    rows=[
                        ReceiptRow(
                            person_slug=display.get(pid, (None, None, None, None, None))[1] if pid else None,
                            person_name=display.get(pid, (raw_name, None, None, None, None))[0] if pid else raw_name,
                            image_url=display.get(pid, (None, None, None, None, None))[2] if pid else None,
                            party=display.get(pid, (None, None, None, None, None))[3] if pid else None,
                            riding=display.get(pid, (None, None, None, None, None))[4] if pid else None,
                            value=float(total or 0),
                            display=f"${float(total or 0):,.0f}",
                            context=item_contexts.get(pid) if pid else None,
                        )
                        for pid, raw_name, total in rows
                    ],
                )
            )

    # 2. Most lobbied, last 12 months (federal only — Registry of Lobbyists).
    latest_comm = None if is_provincial else db.scalar(select(func.max(LobbyCommunication.comm_date)))
    if latest_comm:
        cutoff = latest_comm - timedelta(days=365)
        lobby_query = (
            select(LobbyCommunication.dpoh_person_id, func.count().label("n"))
            .where(LobbyCommunication.dpoh_person_id.is_not(None), LobbyCommunication.comm_date >= cutoff)
            .group_by(LobbyCommunication.dpoh_person_id)
            .order_by(func.count().desc())
            .limit(10)
        )
        if province_person_ids is not None:
            lobby_query = lobby_query.where(LobbyCommunication.dpoh_person_id.in_(province_person_ids))
        rows = db.execute(lobby_query).all()
        if rows:
            display = _person_display(db, [r[0] for r in rows])
            client_contexts = _top_client_contexts(db, [r[0] for r in rows], cutoff)
            boards.append(
                ReceiptBoard(
                    key="most_lobbied",
                    title="Most lobbied",
                    subtitle=f"Registered lobbying contacts in the last 12 months{province_suffix}",
                    caveat=(
                        "Ministers and committee chairs get lobbied more because of their roles — "
                        "a contact is registered access, not evidence of influence. Each count links "
                        "to the searchable registry records."
                    ),
                    rows=[
                        ReceiptRow(
                            person_slug=display.get(pid, ("", None, None, None, None))[1],
                            person_name=display.get(pid, ("Unknown", None, None, None, None))[0],
                            image_url=display.get(pid, (None, None, None, None, None))[2],
                            party=display.get(pid, (None, None, None, None, None))[3],
                            riding=display.get(pid, (None, None, None, None, None))[4],
                            value=float(n),
                            display=f"{n} contacts",
                            context=client_contexts.get(pid),
                        )
                        for pid, n in rows
                    ],
                )
            )

    # 3 + 4. Dissent + attendance from PersonStats — latest session of the
    # requested legislature (federal Parliament or Ontario's Queen's Park).
    session_phrase = "this session at Queen's Park" if is_provincial else "this session"
    member_label = "MPPs" if is_provincial else "MPs"
    latest_session_id = _latest_stats_session_id(db, scope)
    if latest_session_id:
        dissent_query = (
            select(PersonStats)
            .where(PersonStats.session_id == latest_session_id, PersonStats.dissent_count > 0)
            .order_by(PersonStats.dissent_count.desc())
            .limit(10)
        )
        if province_person_ids is not None:
            dissent_query = dissent_query.where(PersonStats.person_id.in_(province_person_ids))
        dissent_rows = db.scalars(dissent_query).all()
        if dissent_rows:
            display = _person_display(db, [s.person_id for s in dissent_rows])
            boards.append(
                ReceiptBoard(
                    key="most_dissents",
                    title="Most independent voters",
                    subtitle=f"Votes against their own party {session_phrase}{province_suffix}",
                    caveat=(
                        f"Breaking ranks is rare in Canada's whipped party system — these {member_label} did it "
                        "most. Independents can't 'dissent' (no party line to break)."
                        + (_ONTARIO_MONEY_CAVEAT if is_provincial else "")
                    ),
                    rows=[
                        ReceiptRow(
                            person_slug=display.get(s.person_id, ("", None, None, None, None))[1],
                            person_name=display.get(s.person_id, ("Unknown", None, None, None, None))[0],
                            image_url=display.get(s.person_id, (None, None, None, None, None))[2],
                            party=display.get(s.person_id, (None, None, None, None, None))[3],
                            riding=display.get(s.person_id, (None, None, None, None, None))[4],
                            value=float(s.dissent_count),
                            display=f"{s.dissent_count} dissent{'s' if s.dissent_count != 1 else ''}",
                        )
                        for s in dissent_rows
                    ],
                )
            )

        # Structural exemption: the Speaker only votes to break ties, so raw
        # attendance would smear them (the TheyWorkForYou lesson). We have no
        # reliable Speaker flag in the data, but an MP who cast ZERO votes all
        # session is structurally not voting (Speaker) — exclude, and say so.
        attendance_query = (
            select(PersonStats)
            .where(
                PersonStats.session_id == latest_session_id,
                PersonStats.attendance_pct.is_not(None),
                PersonStats.votes_eligible >= 30,  # short tenures distort rates
                PersonStats.votes_cast > 0,  # Speaker never votes except ties
            )
            .order_by(PersonStats.attendance_pct.asc())
            .limit(10)
        )
        if province_person_ids is not None:
            attendance_query = attendance_query.where(PersonStats.person_id.in_(province_person_ids))
        attendance_rows = db.scalars(attendance_query).all()
        if attendance_rows:
            display = _person_display(db, [s.person_id for s in attendance_rows])
            boards.append(
                ReceiptBoard(
                    key="lowest_attendance",
                    title="Missed the most votes",
                    subtitle=f"Lowest share of eligible votes cast {session_phrase} (min. 30 eligible votes){province_suffix}",
                    caveat=(
                        "Some absences are structural: ministers travel on government business, party "
                        f"leaders campaign, and {member_label} miss votes for health and family reasons the record "
                        "doesn't show. The Speaker (who only votes to break ties) is excluded. A low "
                        "number is a question to ask, not a verdict."
                        + (_ONTARIO_MONEY_CAVEAT if is_provincial else "")
                    ),
                    rows=[
                        ReceiptRow(
                            person_slug=display.get(s.person_id, ("", None, None, None, None))[1],
                            person_name=display.get(s.person_id, ("Unknown", None, None, None, None))[0],
                            image_url=display.get(s.person_id, (None, None, None, None, None))[2],
                            party=display.get(s.person_id, (None, None, None, None, None))[3],
                            riding=display.get(s.person_id, (None, None, None, None, None))[4],
                            value=float(s.attendance_pct or 0),
                            display=f"{s.attendance_pct:.0f}% attendance",
                            context=f"cast {s.votes_cast} of {s.votes_eligible} eligible votes",
                        )
                        for s in attendance_rows
                    ],
                )
            )

    # 5. Biggest single contracts on record (federal only — HoC disclosures).
    contract_rows: list[ExpenseItem] = []
    if not is_provincial:
        contract_query = (
            select(ExpenseItem)
            .where(ExpenseItem.category == "contract", ExpenseItem.scope == "federal")
            .order_by(ExpenseItem.amount.desc())
            .limit(10)
        )
        if province_person_ids is not None:
            contract_query = contract_query.where(ExpenseItem.person_id.in_(province_person_ids))
        contract_rows = db.scalars(contract_query).all()
    if contract_rows:
        display = _person_display(db, [i.person_id for i in contract_rows if i.person_id])
        boards.append(
            ReceiptBoard(
                key="biggest_contracts",
                title="Biggest single contracts",
                subtitle=f"Largest individual contracts in the disclosures we've ingested{province_suffix}",
                caveat=(
                    "Contracts cover everything from office renovations to research — the size alone "
                    "says nothing about value for money. Every row links to the official record."
                ),
                rows=[
                    ReceiptRow(
                        person_slug=display.get(i.person_id or 0, ("", None, None, None, None))[1],
                        person_name=display.get(i.person_id or 0, (i.mp_name_raw, None, None, None, None))[0],
                        image_url=display.get(i.person_id or 0, (None, None, None, None, None))[2],
                        party=display.get(i.person_id or 0, (None, None, None, None, None))[3],
                        riding=display.get(i.person_id or 0, (None, None, None, None, None))[4],
                        value=float(i.amount),
                        display=f"${i.amount:,.0f}",
                        context=f"{i.supplier or i.description or 'contract'} · Q{i.quarter} FY{i.fiscal_year}",
                    )
                    for i in contract_rows
                ],
            )
        )

    return ReceiptsResponse(boards=boards, generated_note=_GENERATED_NOTE)
