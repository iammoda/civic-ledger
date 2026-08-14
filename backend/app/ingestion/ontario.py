"""Ontario legislature (ola.org) -> bills + division votes + ballots.

Deterministic HTML parsing only — no LLM. Everything lands in the same
Bill/Vote/Ballot tables as the federal record, under the "ca-on"
jurisdiction and the "on-assembly" chamber (people come from the
Represent sync; sponsors and ballots are matched to those MPP rows).

Sources (per session):
- index:  /en/legislative-business/bills/parliament-{p}/session-{s}
- detail: index + /bill-{number}  (status table + inline division votes
  with full Ayes/Nays member rolls — no separate votes feed needed)
"""
from __future__ import annotations

import asyncio
import logging
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

import httpx
from selectolax.parser import HTMLParser
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.ingestion.sync import compute_party_lines, slugify
from app.models import (
    Ballot,
    Bill,
    Chamber,
    Jurisdiction,
    LegislatureSession,
    Person,
    PersonMembership,
    Vote,
)

logger = logging.getLogger(__name__)
settings = get_settings()

OLA_BASE = "https://www.ola.org"
JURISDICTION_CODE = "ca-on"
CHAMBER_SLUG = "on-assembly"
# Ontario's 44th Parliament, 1st session (2025-). Extend for backfills.
DEFAULT_SESSIONS: list[tuple[int, int]] = [(44, 1)]

_VOTE_HEADER_RE = re.compile(
    r"^(?P<what>.+?)\s*[-–]\s*(?P<result>Carried|Lost|Tied)\s*\((?P<date>[A-Z][a-z]+ \d{1,2}, \d{4})\)$"
)
_HON_RE = re.compile(r"^Hon\.?\s+", re.IGNORECASE)
_NICK_RE = re.compile(r"\s*\([^)]*\)\s*")


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _parse_date(text: str) -> date | None:
    try:
        return datetime.strptime(_clean(text), "%B %d, %Y").date()
    except ValueError:
        return None


def normalize_name(name: str) -> str:
    """'Hon. France Gélinas' / 'Jennifer (Jennie) Stevens' -> matchable key."""
    name = _HON_RE.sub("", _clean(name))
    name = _NICK_RE.sub(" ", name)
    name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    return _clean(name).lower()


@dataclass(slots=True)
class OntarioBillStub:
    number: str
    title: str
    sponsor_names: list[str]
    path: str
    has_minister_sponsor: bool = False  # "Hon." in the raw sponsor cell.


@dataclass(slots=True)
class OntarioDivision:
    description: str  # e.g. "Vote on third reading"
    result: str  # Carried | Lost | Tied
    occurred_on: date
    ayes: list[str] = field(default_factory=list)
    nays: list[str] = field(default_factory=list)


@dataclass(slots=True)
class OntarioBillDetail:
    status_en: str | None
    introduced_on: date | None
    received_royal_assent: bool
    divisions: list[OntarioDivision] = field(default_factory=list)


class OntarioClient:
    def __init__(self) -> None:
        self._client = httpx.AsyncClient(
            base_url=OLA_BASE,
            headers={"User-Agent": f"Mozilla/5.0 (compatible; {settings.ingestion_user_agent})"},
            timeout=60.0,
            follow_redirects=True,
        )

    async def __aenter__(self) -> "OntarioClient":
        return self

    async def __aexit__(self, *exc: Any) -> None:
        await self._client.aclose()

    async def fetch(self, path: str) -> str | None:
        try:
            await asyncio.sleep(0.3)  # Politeness: ~190 pages per session sync.
            response = await self._client.get(path)
            response.raise_for_status()
            return response.text
        except httpx.HTTPError as exc:
            logger.warning("ola fetch failed %s: %s", path, exc)
            return None


def session_path(parliament: int, session: int) -> str:
    return f"/en/legislative-business/bills/parliament-{parliament}/session-{session}"


def parse_bills_index(html: str) -> list[OntarioBillStub]:
    """The session index table: number | title | sponsor(s)."""
    tree = HTMLParser(html)
    stubs: list[OntarioBillStub] = []
    for row in tree.css("table tbody tr"):
        cells = row.css("td")
        if len(cells) < 2:
            continue
        link = row.css_first("a")
        number = _clean(cells[0].text())
        title = _clean(cells[1].text())
        if not number or not title or link is None:
            continue
        # Sponsor cell: "Ford, Hon. Doug (Premier)" — possibly several.
        sponsors: list[str] = []
        has_minister = False
        if len(cells) >= 3:
            raw = cells[2].text(separator="\n")
            has_minister = "Hon." in raw
            for chunk in raw.split("\n"):
                chunk = _NICK_RE.sub(" ", _clean(chunk))
                if not chunk or "," not in chunk:
                    continue
                last, _, first = chunk.partition(",")
                first = _HON_RE.sub("", _clean(first))
                if first and last:
                    sponsors.append(f"{first} {_clean(last)}")
        stubs.append(
            OntarioBillStub(
                number=number,
                title=title,
                sponsor_names=sponsors,
                path=link.attributes.get("href") or "",
                has_minister_sponsor=has_minister,
            )
        )
    return stubs


def _parse_status_table(tree: HTMLParser) -> tuple[str | None, date | None, bool]:
    """Status tab table (newest first): Date | Bill stage | Event | Outcome."""
    status_tab = tree.css_first("div.bill-status-tab")
    if status_tab is None:
        return None, None, False
    status_en: str | None = None
    introduced_on: date | None = None
    royal_assent = False
    for row in status_tab.css("table tr"):
        cells = [_clean(c.text(separator=" ")) for c in row.css("td")]
        if len(cells) < 3 or not cells[0]:
            continue
        row_date = _parse_date(cells[0])
        stage, event = cells[1], cells[2]
        if status_en is None and stage:
            status_en = f"{stage} — {event}" if event and event != "-" else stage
        if stage.lower() == "first reading" and row_date is not None:
            introduced_on = row_date  # Table is newest-first; keep the last hit.
        if "royal assent" in stage.lower():
            royal_assent = True
    return status_en, introduced_on, royal_assent


def _parse_divisions(tree: HTMLParser) -> list[OntarioDivision]:
    """Votes tab: h2 headers ("Vote on third reading - Carried (June 4, 2025)")
    each followed by Ayes/Nays member rolls."""
    votes_tab = tree.css_first("div.bill-votes-tab")
    if votes_tab is None:
        return []
    divisions: list[OntarioDivision] = []
    for header in votes_tab.css("h2.view-grouping-header"):
        match = _VOTE_HEADER_RE.match(_clean(header.text(separator=" ")))
        if match is None:
            continue
        occurred_on = _parse_date(match.group("date"))
        if occurred_on is None:
            continue
        division = OntarioDivision(
            description=_clean(match.group("what")),
            result=match.group("result"),
            occurred_on=occurred_on,
        )
        grouping = header.next
        while grouping is not None and (grouping.tag != "div"):
            grouping = grouping.next
        if grouping is None:
            continue
        # Structure: <h3>Ayes (71)</h3><div class="row"><div class="col-…">name…
        # Walk each h3's following siblings until the next h3.
        for heading_node in grouping.css("h3"):
            heading = _clean(heading_node.text(separator=" ")).lower()
            if heading.startswith("ayes"):
                bucket = division.ayes
            elif heading.startswith("nays"):
                bucket = division.nays
            else:
                continue
            sibling = heading_node.next
            while sibling is not None and sibling.tag != "h3":
                if sibling.tag == "div":
                    for cell in sibling.css("div"):
                        if "col-" in (cell.attributes.get("class") or ""):
                            name = _clean(cell.text(separator=" "))
                            if name:
                                bucket.append(name)
                sibling = sibling.next
        divisions.append(division)
    return divisions


def parse_bill_detail(html: str) -> OntarioBillDetail:
    tree = HTMLParser(html)
    status_en, introduced_on, royal_assent = _parse_status_table(tree)
    return OntarioBillDetail(
        status_en=status_en,
        introduced_on=introduced_on,
        received_royal_assent=royal_assent,
        divisions=_parse_divisions(tree),
    )


# --- Persistence -----------------------------------------------------------


class OntarioSyncContext:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.jurisdiction = self._ensure_jurisdiction()
        self.chamber = self._ensure_chamber()
        self._people_by_name: dict[str, Person] | None = None

    def _ensure_jurisdiction(self) -> Jurisdiction:
        jur = self.db.scalar(select(Jurisdiction).where(Jurisdiction.code == JURISDICTION_CODE))
        if jur is None:
            jur = Jurisdiction(
                code=JURISDICTION_CODE,
                name_en="Legislative Assembly of Ontario",
                country_code="CA",
                level="provincial",
            )
            self.db.add(jur)
            self.db.flush()
        return jur

    def _ensure_chamber(self) -> Chamber:
        chamber = self.db.scalar(
            select(Chamber).where(
                Chamber.jurisdiction_id == self.jurisdiction.id, Chamber.slug == CHAMBER_SLUG
            )
        )
        if chamber is None:
            chamber = Chamber(
                jurisdiction_id=self.jurisdiction.id,
                slug=CHAMBER_SLUG,
                name_en="Legislative Assembly of Ontario",
                is_elected=True,
            )
            self.db.add(chamber)
            self.db.flush()
        return chamber

    def session_for(self, parliament: int, session_no: int) -> LegislatureSession:
        row = self.db.scalar(
            select(LegislatureSession).where(
                LegislatureSession.jurisdiction_id == self.jurisdiction.id,
                LegislatureSession.parliament_number == parliament,
                LegislatureSession.session_number == session_no,
            )
        )
        if row is None:
            row = LegislatureSession(
                jurisdiction_id=self.jurisdiction.id,
                parliament_number=parliament,
                session_number=session_no,
                is_current=False,  # mark_current_session() owns this flag.
            )
            self.db.add(row)
            self.db.flush()
        return row

    def match_person(self, name: str) -> Person | None:
        """OLA names -> MPP Person rows (Represent-synced, same origin)."""
        if self._people_by_name is None:
            self._people_by_name = {}
            people = self.db.scalars(
                select(Person).where(Person.chamber_id == self.chamber.id)
            ).all()
            for person in people:
                self._people_by_name[normalize_name(person.full_name)] = person
        return self._people_by_name.get(normalize_name(name))

    def ensure_person(self, name: str) -> Person:
        """Match, or create a minimal MPP from the official vote roll.

        Represent's Ontario roster occasionally lags a couple of members;
        anyone appearing in an ola.org division is a sitting MPP and must
        not lose ballots. The weekly Represent sync adopts these stubs
        (matched by chamber + normalized name) and fills in the details.
        """
        person = self.match_person(name)
        if person is not None:
            return person
        display_name = _NICK_RE.sub(" ", _HON_RE.sub("", _clean(name)))
        display_name = _clean(display_name)
        slug = f"on-{slugify(display_name)}"
        if self.db.scalar(select(Person).where(Person.slug == slug)) is not None:
            slug = f"{slug}-mpp"
        person = Person(
            slug=slug,
            full_name=display_name,
            chamber_id=self.chamber.id,
            source_system="ola",
            source_id=normalize_name(name),
        )
        self.db.add(person)
        self.db.flush()
        self.db.add(
            PersonMembership(person_id=person.id, chamber_id=self.chamber.id, is_current=True)
        )
        self.db.flush()
        logger.info("ontario: created MPP missing from Represent roster: %s", display_name)
        assert self._people_by_name is not None
        self._people_by_name[normalize_name(name)] = person
        self._people_by_name[normalize_name(display_name)] = person
        return person

    def party_slug_of(self, person: Person) -> str | None:
        membership = self.db.scalar(
            select(PersonMembership).where(
                PersonMembership.person_id == person.id,
                PersonMembership.is_current.is_(True),
            )
        )
        if membership is None or membership.party_id is None:
            return None
        from app.models import Party

        party = self.db.get(Party, membership.party_id)
        return party.slug if party else None


def _bill_type(stub: OntarioBillStub) -> str:
    if stub.number.upper().startswith("PR"):
        return "private"
    if stub.has_minister_sponsor or stub.number == "1":
        return "government"
    return "private_member"


def upsert_ontario_bill(
    ctx: OntarioSyncContext,
    session: LegislatureSession,
    stub: OntarioBillStub,
    detail: OntarioBillDetail,
) -> Bill:
    db = ctx.db
    bill = db.scalar(
        select(Bill).where(
            Bill.session_id == session.id,
            Bill.chamber_id == ctx.chamber.id,
            Bill.number == stub.number,
        )
    )
    if bill is None:
        bill = Bill(
            session_id=session.id,
            chamber_id=ctx.chamber.id,
            number=stub.number,
            title_en=stub.title[:500],
        )
        db.add(bill)
    bill.title_en = stub.title[:500]
    bill.status_en = (detail.status_en or bill.status_en or "")[:255] or None
    bill.bill_type = _bill_type(stub)
    bill.introduced_on = detail.introduced_on or bill.introduced_on
    bill.summary_source_url = f"{OLA_BASE}{stub.path}"  # The ola.org bill page.
    if detail.received_royal_assent:
        bill.is_law = True
        bill.outcome = "enacted"
    sponsor = ctx.match_person(stub.sponsor_names[0]) if stub.sponsor_names else None
    if sponsor is not None:
        bill.sponsor_person_id = sponsor.id
    db.flush()
    return bill


def _vote_number(bill_number: str, division: OntarioDivision) -> str:
    """Stable synthetic number: OLA publishes no division numbers."""
    return f"{bill_number}-{slugify(division.description)}-{division.occurred_on.isoformat()}"[:64]


def upsert_ontario_vote(
    ctx: OntarioSyncContext,
    session: LegislatureSession,
    bill: Bill,
    division: OntarioDivision,
) -> Vote:
    db = ctx.db
    number = _vote_number(bill.number, division)
    vote = db.scalar(
        select(Vote).where(
            Vote.session_id == session.id,
            Vote.chamber_id == ctx.chamber.id,
            Vote.number == number,
        )
    )
    if vote is None:
        vote = Vote(
            session_id=session.id,
            chamber_id=ctx.chamber.id,
            number=number,
            occurred_on=division.occurred_on,
            description_en="",
        )
        db.add(vote)
    vote.bill_id = bill.id
    vote.occurred_on = division.occurred_on
    vote.description_en = f"Bill {bill.number} ({bill.title_en[:200]}) — {division.description}"
    vote.result = "Passed" if division.result == "Carried" else "Negatived" if division.result == "Lost" else division.result
    vote.yea_total = len(division.ayes)
    vote.nay_total = len(division.nays)
    vote.source_url = bill.summary_source_url
    # Readings advance the bill; a Yea is a vote to move it forward.
    lowered = division.description.lower()
    if "reading" in lowered or "committee report" in lowered:
        vote.yea_effect = "advance"
    db.flush()

    for names, value in ((division.ayes, "yea"), (division.nays, "nay")):
        for name in names:
            person = ctx.ensure_person(name)
            ballot = db.scalar(
                select(Ballot).where(Ballot.vote_id == vote.id, Ballot.person_id == person.id)
            )
            if ballot is None:
                ballot = Ballot(vote_id=vote.id, person_id=person.id, ballot=value)
                db.add(ballot)
            ballot.ballot = value
            ballot.party_slug = ctx.party_slug_of(person)
    db.flush()
    compute_party_lines(db, vote)
    return vote


async def sync_ontario(
    db: Session,
    client: OntarioClient,
    sessions: list[tuple[int, int]] | None = None,
) -> dict[str, int]:
    ctx = OntarioSyncContext(db)
    counts = {"bills": 0, "votes": 0}
    for parliament, session_no in sessions or DEFAULT_SESSIONS:
        index_html = await client.fetch(session_path(parliament, session_no))
        if index_html is None:
            continue
        session = ctx.session_for(parliament, session_no)
        for stub in parse_bills_index(index_html):
            if not stub.path:
                continue
            detail_html = await client.fetch(stub.path)
            if detail_html is None:
                continue
            detail = parse_bill_detail(detail_html)
            bill = upsert_ontario_bill(ctx, session, stub, detail)
            counts["bills"] += 1
            for division in detail.divisions:
                upsert_ontario_vote(ctx, session, bill, division)
                counts["votes"] += 1
            db.commit()
    db.commit()
    return counts
