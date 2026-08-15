"""OpenParliament → Postgres persistence.

Deterministic parsers only — no LLM anywhere in ingestion. All writes are
idempotent upserts keyed on natural keys, so re-running a sync is safe.
"""
from __future__ import annotations

import logging
import re
import unicodedata
from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

from app.core.classification import PartyDisagreementSignal, classify_vote_type
from app.core.config import get_settings
from app.ingestion.openparliament import OpenParliamentClient
from app.models import (
    Ballot,
    Bill,
    BillDeath,
    Chamber,
    Jurisdiction,
    LegislatureSession,
    Party,
    Person,
    PersonMembership,
    RepresentationEvent,
    Vote,
)

settings = get_settings()

BALLOT_MAP = {"yes": "yea", "no": "nay", "paired": "paired", "didn't vote": "absent"}


def slugify(value: str) -> str:
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    value = re.sub(r"[^a-zA-Z0-9]+", "-", value).strip("-").lower()
    return value or "unknown"


def parse_date(value: str | None) -> date | None:
    return date.fromisoformat(value) if value else None


def path_slug(url: str | None) -> str | None:
    """'/politicians/ziad-aboultaif/' -> 'ziad-aboultaif'."""
    if not url:
        return None
    parts = [p for p in url.split("/") if p]
    return parts[-1] if parts else None


class SyncContext:
    """Caches jurisdiction/chamber/session/party lookups within one sync run."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.jurisdiction = self._ensure_jurisdiction()
        self.house = self._ensure_chamber("house", "House of Commons")
        self.senate = self._ensure_chamber("senate", "Senate")
        self._sessions: dict[str, LegislatureSession] = {}
        self._parties: dict[str, Party] = {}

    def _ensure_jurisdiction(self) -> Jurisdiction:
        jur = self.db.scalar(select(Jurisdiction).where(Jurisdiction.code == settings.default_jurisdiction))
        if jur is None:
            jur = Jurisdiction(code=settings.default_jurisdiction, name_en="Canada", name_fr="Canada", country_code="CA")
            self.db.add(jur)
            self.db.flush()
        return jur

    def _ensure_chamber(self, slug: str, name_en: str) -> Chamber:
        chamber = self.db.scalar(
            select(Chamber).where(Chamber.jurisdiction_id == self.jurisdiction.id, Chamber.slug == slug)
        )
        if chamber is None:
            chamber = Chamber(jurisdiction_id=self.jurisdiction.id, slug=slug, name_en=name_en, is_elected=slug == "house")
            self.db.add(chamber)
            self.db.flush()
        return chamber

    def session_for_label(self, label: str) -> LegislatureSession:
        """'45-1' -> LegislatureSession row (created if missing)."""
        if label in self._sessions:
            return self._sessions[label]
        parliament, _, session_no = label.partition("-")
        row = self.db.scalar(
            select(LegislatureSession).where(
                LegislatureSession.jurisdiction_id == self.jurisdiction.id,
                LegislatureSession.parliament_number == int(parliament),
                LegislatureSession.session_number == int(session_no),
            )
        )
        if row is None:
            row = LegislatureSession(
                jurisdiction_id=self.jurisdiction.id,
                parliament_number=int(parliament),
                session_number=int(session_no),
                is_current=False,
            )
            self.db.add(row)
            self.db.flush()
        self._sessions[label] = row
        return row

    def party_for_names(self, name_en: str | None, short_name: str | None) -> Party | None:
        if not short_name and not name_en:
            return None
        slug = slugify(short_name or name_en or "")
        if slug in self._parties:
            return self._parties[slug]
        party = self.db.scalar(
            select(Party).where(Party.jurisdiction_id == self.jurisdiction.id, Party.slug == slug)
        )
        if party is None:
            party = Party(
                jurisdiction_id=self.jurisdiction.id,
                name_en=name_en or short_name or "",
                short_name=short_name or name_en or "",
                slug=slug,
            )
            self.db.add(party)
            self.db.flush()
        self._parties[slug] = party
        return party


# ---------------------------------------------------------------------------
# Politicians
# ---------------------------------------------------------------------------

def upsert_person_from_detail(ctx: SyncContext, slug: str, detail: dict[str, Any]) -> Person:
    """Upsert a Person and their party/riding membership history."""
    db = ctx.db
    person = db.scalar(select(Person).where(Person.slug == slug))
    image = detail.get("image")
    links = detail.get("links") or []
    website = links[0]["url"] if links else None
    if person is None:
        person = Person(slug=slug, full_name=detail.get("name") or slug, source_system="openparliament", source_id=slug)
        db.add(person)
    person.full_name = detail.get("name") or person.full_name
    person.given_name = detail.get("given_name")
    person.family_name = detail.get("family_name")
    person.email = detail.get("email")
    person.image_url = f"https://api.openparliament.ca{image}" if image and image.startswith("/") else image
    person.website_url = website
    person.chamber_id = ctx.house.id
    db.flush()

    previous_current: PersonMembership | None = db.scalar(
        select(PersonMembership)
        .where(PersonMembership.person_id == person.id, PersonMembership.is_current.is_(True))
        .order_by(PersonMembership.started_on.desc())
    )

    for membership_data in detail.get("memberships") or []:
        party_data = membership_data.get("party") or {}
        party = ctx.party_for_names(
            (party_data.get("name") or {}).get("en"),
            (party_data.get("short_name") or {}).get("en"),
        )
        riding = membership_data.get("riding") or {}
        riding_name = (riding.get("name") or {}).get("en")
        started_on = parse_date(membership_data.get("start_date"))
        ended_on = parse_date(membership_data.get("end_date"))

        existing = db.scalar(
            select(PersonMembership).where(
                PersonMembership.person_id == person.id,
                PersonMembership.started_on == started_on,
                PersonMembership.riding_name == riding_name,
            )
        )
        if existing is None:
            existing = PersonMembership(person_id=person.id, started_on=started_on, riding_name=riding_name)
            db.add(existing)
        existing.party_id = party.id if party else None
        existing.chamber_id = ctx.house.id
        existing.province_code = riding.get("province")
        existing.region_name = None
        existing.role_title = (membership_data.get("label") or {}).get("en")
        existing.ended_on = ended_on
        existing.is_current = ended_on is None
        db.flush()

        # Floor-crossing detection: a new current membership under a
        # different party than the previous current one.
        if (
            previous_current is not None
            and existing.id != previous_current.id
            and existing.is_current
            and previous_current.party_id is not None
            and existing.party_id is not None
            and existing.party_id != previous_current.party_id
            and (previous_current.ended_on is None or (started_on and previous_current.ended_on <= started_on))
        ):
            event = db.scalar(
                select(RepresentationEvent).where(
                    RepresentationEvent.person_id == person.id,
                    RepresentationEvent.event_type == "floor_crossing",
                    RepresentationEvent.occurred_on == started_on,
                )
            )
            if event is None:
                db.add(
                    RepresentationEvent(
                        person_id=person.id,
                        event_type="floor_crossing",
                        occurred_on=started_on,
                        from_party_id=previous_current.party_id,
                        to_party_id=existing.party_id,
                        details_en=f"{person.full_name} changed party affiliation.",
                    )
                )
            previous_current.is_current = False

    return person


async def ensure_person(ctx: SyncContext, client: OpenParliamentClient, politician_url: str) -> Person:
    """Get-or-fetch a person referenced by URL (e.g. from a ballot)."""
    slug = path_slug(politician_url)
    assert slug is not None
    person = ctx.db.scalar(select(Person).where(Person.slug == slug))
    if person is not None:
        return person
    detail = await client.fetch_detail(politician_url)
    return upsert_person_from_detail(ctx, slug, detail)


async def sync_politicians(ctx: SyncContext, client: OpenParliamentClient, *, include_former: bool = False) -> int:
    """Sync current (and optionally former) MPs with full membership history."""
    params: dict[str, Any] = {"limit": 100}
    if include_former:
        params["include"] = "former"
    listing = await client.paginate("/politicians/", params=params)
    count = 0
    for item in listing:
        slug = path_slug(item.get("url"))
        if not slug:
            continue
        detail = await client.fetch_detail(item["url"])
        upsert_person_from_detail(ctx, slug, detail)
        count += 1
    ctx.db.commit()
    return count


# ---------------------------------------------------------------------------
# Bills
# ---------------------------------------------------------------------------

# Exact/keyword mapping from LEGISinfo status codes to lifecycle outcomes.
def outcome_from_status_code(status_code: str | None, *, law: bool) -> str:
    if law:
        return "enacted"
    if not status_code:
        return "pending"
    code = status_code.lower()
    if "royalassent" in code:
        return "enacted"
    if "defeated" in code:
        return "defeated_vote"
    if "withdrawn" in code:
        return "withdrawn"
    if "notproceeded" in code or "willnotbeproceeded" in code:
        return "not_proceeded_with"
    return "pending"


def stage_from_status_code(status_code: str | None) -> str | None:
    if not status_code:
        return None
    code = status_code.lower()
    if "committee" in code:
        return "committee"
    if "thirdreading" in code:
        return "third-reading"
    if "secondreading" in code:
        return "second-reading"
    if "firstreading" in code:
        return "first-reading"
    if "reportstage" in code:
        return "report-stage"
    if "senate" in code:
        return "senate"
    return None


def upsert_bill_from_detail(ctx: SyncContext, detail: dict[str, Any]) -> Bill:
    db = ctx.db
    session = ctx.session_for_label(detail["session"])
    number = detail["number"]
    chamber = ctx.senate if number.upper().startswith("S-") else ctx.house

    bill = db.scalar(
        select(Bill).where(
            Bill.session_id == session.id,
            Bill.number == number,
            Bill.chamber_id == chamber.id,
        )
    )
    if bill is None:
        bill = Bill(session_id=session.id, chamber_id=chamber.id, number=number, title_en="")
        db.add(bill)

    name = detail.get("name") or {}
    short_title = detail.get("short_title") or {}
    status = detail.get("status") or {}
    bill.title_en = name.get("en") or bill.title_en or number
    bill.title_fr = name.get("fr")
    bill.short_title_en = short_title.get("en") or None
    bill.short_title_fr = short_title.get("fr") or None
    bill.status_en = status.get("en")
    bill.introduced_on = parse_date(detail.get("introduced"))
    bill.legisinfo_id = detail.get("legisinfo_id")
    bill.legisinfo_url = detail.get("legisinfo_url")
    bill.text_url = detail.get("text_url")
    bill.status_code = detail.get("status_code")
    bill.is_law = bool(detail.get("law"))
    bill.bill_type = "private_member" if detail.get("private_member_bill") else "government"
    bill.outcome = outcome_from_status_code(bill.status_code, law=bill.is_law)

    sponsor_slug = path_slug(detail.get("sponsor_politician_url"))
    if sponsor_slug:
        sponsor = db.scalar(select(Person).where(Person.slug == sponsor_slug))
        bill.sponsor_person_id = sponsor.id if sponsor else None

    db.flush()

    # A bill defeated on a recorded vote gets its death row now; the kill
    # vote is linked when votes sync (see link_kill_votes).
    if bill.outcome in {"defeated_vote", "withdrawn", "not_proceeded_with"}:
        _ensure_bill_death(
            ctx,
            bill,
            mechanism=bill.outcome if bill.outcome != "defeated_vote" else "defeated_vote",
            stage=stage_from_status_code(bill.status_code),
            attribution_en=bill.status_en,
        )
    return bill


def _ensure_bill_death(
    ctx: SyncContext,
    bill: Bill,
    *,
    mechanism: str,
    stage: str | None,
    attribution_en: str | None,
    occurred_on: date | None = None,
) -> BillDeath:
    death = ctx.db.scalar(select(BillDeath).where(BillDeath.bill_id == bill.id))
    if death is None:
        death = BillDeath(bill_id=bill.id, mechanism=mechanism)
        ctx.db.add(death)
    death.mechanism = mechanism
    death.stage = stage
    death.attribution_en = attribution_en
    if occurred_on:
        death.occurred_on = occurred_on
    ctx.db.flush()
    return death


async def sync_bills(ctx: SyncContext, client: OpenParliamentClient, *, session_label: str | None = None) -> int:
    """Sync bills (optionally scoped to one session) with LEGISinfo detail."""
    params: dict[str, Any] = {"limit": 100}
    if session_label:
        params["session"] = session_label
    listing = await client.paginate("/bills/", params=params)
    count = 0
    for item in listing:
        detail = await client.fetch_detail(item["url"])
        upsert_bill_from_detail(ctx, detail)
        count += 1
        if count % 50 == 0:
            ctx.db.commit()
    ctx.db.commit()
    return count


def sweep_session_deaths(ctx: SyncContext, session_label: str) -> int:
    """Mark still-pending bills of an ended session as died (prorogation/
    dissolution kills everything on the Order Paper)."""
    from app.data.sessions import PRO_FORMA_NUMBERS

    session = ctx.session_for_label(session_label)
    bills = ctx.db.scalars(
        select(Bill).where(
            Bill.session_id == session.id,
            Bill.outcome == "pending",
            # Ceremonial C-1/S-1 were never meant to pass — not deaths.
            Bill.number.not_in(PRO_FORMA_NUMBERS),
        )
    ).all()
    for bill in bills:
        stage = stage_from_status_code(bill.status_code)
        if stage == "committee":
            mechanism, outcome = "died_committee", "died_committee"
            attribution = "Died in committee when the session ended — never brought forward for a vote."
        elif stage == "senate" or (bill.chamber_id == ctx.house.id and (bill.status_code or "").lower().startswith("senate")):
            mechanism, outcome = "died_senate", "died_senate"
            attribution = "Passed the House but died in the Senate when the session ended."
        else:
            mechanism, outcome = "died_order_paper", "died_order_paper"
            attribution = "Died on the Order Paper when the session ended."
        bill.outcome = outcome
        _ensure_bill_death(ctx, bill, mechanism=mechanism, stage=stage, attribution_en=attribution, occurred_on=session.ended_on)
    ctx.db.commit()
    return len(bills)


# ---------------------------------------------------------------------------
# Votes & ballots
# ---------------------------------------------------------------------------

def _membership_at(db: Session, person_id: int, on: date) -> PersonMembership | None:
    memberships = db.scalars(
        select(PersonMembership).where(PersonMembership.person_id == person_id)
    ).all()
    for m in memberships:
        started = m.started_on or date.min
        ended = m.ended_on or date.max
        if started <= on <= ended:
            return m
    return None


def _party_slug_of(db: Session, membership: PersonMembership | None) -> str | None:
    if membership is None or membership.party_id is None:
        return None
    party = db.get(Party, membership.party_id)
    return party.slug if party else None


def compute_party_lines(db: Session, vote: Vote) -> None:
    """Set broke_party_line per ballot from each party's own majority."""
    ballots = db.scalars(select(Ballot).where(Ballot.vote_id == vote.id)).all()
    by_party: dict[str, list[Ballot]] = {}
    for ballot in ballots:
        if ballot.party_slug and ballot.ballot in {"yea", "nay"}:
            by_party.setdefault(ballot.party_slug, []).append(ballot)
    for party_ballots in by_party.values():
        yeas = sum(1 for b in party_ballots if b.ballot == "yea")
        nays = len(party_ballots) - yeas
        if yeas == nays or len(party_ballots) < 2:
            continue  # No discernible party line.
        majority = "yea" if yeas > nays else "nay"
        for ballot in party_ballots:
            ballot.broke_party_line = ballot.ballot != majority


async def sync_vote_ballots(ctx: SyncContext, client: OpenParliamentClient, vote: Vote, vote_url: str) -> int:
    db = ctx.db
    records = await client.paginate("/votes/ballots/", params={"vote": vote_url, "limit": 400})
    count = 0
    for record in records:
        person = await ensure_person(ctx, client, record["politician_url"])
        ballot_value = BALLOT_MAP.get((record.get("ballot") or "").lower(), "absent")
        membership = _membership_at(db, person.id, vote.occurred_on)
        party_slug = _party_slug_of(db, membership)

        existing = db.scalar(
            select(Ballot).where(Ballot.vote_id == vote.id, Ballot.person_id == person.id)
        )
        if existing is None:
            existing = Ballot(vote_id=vote.id, person_id=person.id, ballot=ballot_value)
            db.add(existing)
        existing.ballot = ballot_value
        existing.party_slug = party_slug
        count += 1
    db.flush()
    compute_party_lines(db, vote)
    db.commit()
    return count


def _disagreement_signals(detail: dict[str, Any]) -> list[PartyDisagreementSignal]:
    signals: list[PartyDisagreementSignal] = []
    for pv in detail.get("party_votes") or []:
        party = pv.get("party") or {}
        short = (party.get("short_name") or {}).get("en") or ""
        signals.append(
            PartyDisagreementSignal(
                party_slug=slugify(short),
                disagreement_pct=float(pv.get("disagreement") or 0.0) * 100.0,
            )
        )
    return signals


async def upsert_vote_from_detail(ctx: SyncContext, client: OpenParliamentClient, detail: dict[str, Any]) -> Vote:
    db = ctx.db
    session = ctx.session_for_label(detail["session"])
    number = str(detail["number"])
    description = detail.get("description") or {}

    vote = db.scalar(
        select(Vote).where(
            Vote.session_id == session.id,
            Vote.chamber_id == ctx.house.id,
            Vote.number == number,
        )
    )
    if vote is None:
        occurred_on = parse_date(detail.get("date"))
        if occurred_on is None:
            # Never fabricate a datum on a provenance-first platform: a vote
            # without a date in the source is skipped and logged, not guessed.
            raise ValueError(f"Vote {detail.get('session')}/{number} has no parseable date; skipping upsert")
        vote = Vote(
            session_id=session.id,
            chamber_id=ctx.house.id,
            number=number,
            occurred_on=occurred_on,
            description_en=description.get("en") or "",
        )
        db.add(vote)
    vote.occurred_on = parse_date(detail.get("date")) or vote.occurred_on
    vote.description_en = description.get("en") or vote.description_en
    vote.description_fr = description.get("fr")
    vote.result = detail.get("result")
    vote.yea_total = detail.get("yea_total") or 0
    vote.nay_total = detail.get("nay_total") or 0
    vote.paired_total = detail.get("paired_total") or 0
    vote.source_url = f"https://api.openparliament.ca{detail.get('url', '')}"
    vote.vote_type = classify_vote_type(
        description=vote.description_en,
        yea_total=vote.yea_total,
        nay_total=vote.nay_total,
        disagreement_signals=_disagreement_signals(detail),
    )

    # Link to bill; create a placeholder if bills sync hasn't reached it yet.
    bill_url = detail.get("bill_url")
    if bill_url:
        bill_number = path_slug(bill_url)
        if bill_number:
            chamber = ctx.senate if bill_number.upper().startswith("S-") else ctx.house
            bill = db.scalar(
                select(Bill).where(
                    Bill.session_id == session.id,
                    Bill.number == bill_number,
                    Bill.chamber_id == chamber.id,
                )
            )
            if bill is None:
                bill = Bill(
                    session_id=session.id,
                    chamber_id=chamber.id,
                    number=bill_number,
                    title_en=bill_number,
                )
                db.add(bill)
                db.flush()
            vote.bill_id = bill.id

            # Defeat on a reading vote = the kill vote.
            desc = vote.description_en.lower()
            if vote.result == "Negatived" and ("reading" in desc or "passage" in desc):
                bill.outcome = "defeated_vote"
                death = _ensure_bill_death(
                    ctx,
                    bill,
                    mechanism="defeated_vote",
                    stage=stage_from_status_code(bill.status_code),
                    attribution_en=f"Defeated {vote.yea_total}\u2013{vote.nay_total}: {vote.description_en}",
                    occurred_on=vote.occurred_on,
                )
                death.kill_vote_id = vote.id

    db.flush()
    return vote


async def sync_votes(
    ctx: SyncContext,
    client: OpenParliamentClient,
    *,
    session_label: str | None = None,
    stop_at_existing: bool = True,
) -> int:
    """Sync votes newest-first; incremental mode stops at first known vote."""
    db = ctx.db
    params: dict[str, Any] = {"limit": 100}
    if session_label:
        params["session"] = session_label

    count = 0
    done = False
    async for page in client.iter_pages("/votes/", params=params):
        for item in page:
            session = ctx.session_for_label(item["session"])
            number = str(item["number"])
            existing = db.scalar(
                select(Vote).where(
                    Vote.session_id == session.id,
                    Vote.chamber_id == ctx.house.id,
                    Vote.number == number,
                )
            )
            has_ballots = False
            if existing is not None:
                has_ballots = db.scalar(select(Ballot.id).where(Ballot.vote_id == existing.id).limit(1)) is not None
            if existing is not None and has_ballots and stop_at_existing:
                done = True
                break
            detail = await client.fetch_detail(item["url"])
            try:
                vote = await upsert_vote_from_detail(ctx, client, detail)
            except ValueError as exc:
                logger.warning("skipping vote: %s", exc)
                continue
            await sync_vote_ballots(ctx, client, vote, item["url"])
            count += 1
        if done:
            break
    db.commit()
    return count


# ---------------------------------------------------------------------------
# Committees
# ---------------------------------------------------------------------------

async def sync_committees(ctx: SyncContext, client: OpenParliamentClient) -> int:
    """Upsert committees from OpenParliament (names, slugs, official links).

    Memberships are not exposed by OpenParliament; they are synced
    separately when an official source is available.
    """
    from app.models import Committee

    db = ctx.db
    listing = await client.paginate("/committees/", params={"limit": 100})
    count = 0
    for item in listing:
        slug = item.get("slug")
        if not slug:
            continue
        detail = await client.fetch_detail(item["url"])
        name = detail.get("name") or {}
        short_name = detail.get("short_name") or {}
        sessions = detail.get("sessions") or []
        newest = sessions[0] if sessions else {}

        committee = db.scalar(
            select(Committee).where(Committee.chamber_id == ctx.house.id, Committee.slug == slug)
        )
        if committee is None:
            committee = Committee(chamber_id=ctx.house.id, slug=slug, name_en="")
            db.add(committee)
        committee.name_en = name.get("en") or short_name.get("en") or slug
        committee.name_fr = name.get("fr")
        committee.source_url = newest.get("source_url")
        if newest.get("session"):
            committee.session_id = ctx.session_for_label(newest["session"]).id
        db.flush()
        count += 1
    db.commit()
    return count
