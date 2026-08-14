"""Municipal meeting minutes via eScribe (OnBoard) portals.

One adapter, many cities: every eScribe tenant exposes the same calendar
JSON API and renders minutes as static HTML with semantic CSS classes
(AgendaHeaderAttendance, AgendaItemMotion, MotionVoters). Verified live
against Mississauga, Brampton, Ottawa, Calgary and Halifax tenants.

What we extract, per meeting:
- attendance   (Members present / absent / regrets)
- motions      (resolution number, mover, seconder, text, result)
- member votes (MotionVoters tables -> shared Vote/Ballot rows)
- conflict-of-interest declarations

Transparency rules baked in:
- every Meeting/Motion stores the URL of the official minutes page
- attendance rows keep the raw printed name (source_name)
- unmatched names are logged, never silently dropped for declarations
"""
from __future__ import annotations

import asyncio
import logging
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any

import httpx
from selectolax.parser import HTMLParser, Node
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.ingestion.sync import compute_party_lines, slugify
from app.models import (
    Ballot,
    Chamber,
    ConflictDeclaration,
    Jurisdiction,
    LegislatureSession,
    Meeting,
    MeetingAttendance,
    Motion,
    Person,
    Vote,
)

logger = logging.getLogger(__name__)
settings = get_settings()


@dataclass(slots=True)
class EscribeTenant:
    tenant: str  # "mississauga" -> pub-mississauga.escribemeetings.com
    jurisdiction_code: str  # Matches the Represent-synced jurisdiction.
    bodies: tuple[str, ...]  # Meeting names to ingest (council + committees).
    term_start: date  # Current council term; backfill floor.


# Council bodies chosen per tenant: the council itself plus the committees
# of the whole where the substantive votes happen. Extend deliberately.
TENANTS: list[EscribeTenant] = [
    EscribeTenant(
        tenant="mississauga",
        jurisdiction_code="mississauga-city-council",
        bodies=("Council", "General Committee", "Budget Committee"),
        term_start=date(2022, 11, 15),
    ),
    EscribeTenant(
        tenant="brampton",
        jurisdiction_code="brampton-city-council",
        bodies=("City Council", "Committee of Council"),
        term_start=date(2022, 11, 15),
    ),
    EscribeTenant(
        tenant="ottawa",
        jurisdiction_code="ottawa-city-council",
        bodies=("City Council",),
        term_start=date(2022, 11, 15),
    ),
    EscribeTenant(
        tenant="calgary",
        jurisdiction_code="calgary-city-council",
        bodies=(
            "Regular Meeting of Council",
            "Combined Meeting of Council",
            "Public Hearing Meeting of Council",
            "Special Meeting of Council",
            "Strategic Meeting of Council",
        ),
        term_start=date(2025, 10, 20),
    ),
    EscribeTenant(
        tenant="halifax",
        jurisdiction_code="halifax-regional-council",
        bodies=("Halifax Regional Council",),
        term_start=date(2024, 11, 1),
    ),
]

# Re-parse minutes for meetings newer than this — minutes get posted and
# occasionally amended in the weeks after a meeting.
REPARSE_WINDOW_DAYS = 45
REQUEST_DELAY_SECONDS = 0.4

# Honorific/role prefixes seen in minutes across tenants.
_ROLE_PREFIX_RE = re.compile(
    r"^(?:his worship\s+)?(?:her worship\s+)?(?:mayor|deputy mayor and councillor|deputy mayor|"
    r"regional councillor|city councillor|councillor|chair|vice-chair)\s+",
    re.IGNORECASE,
)
_WARD_SUFFIX_RE = re.compile(r",?\s*\(?ward\s+\d+\)?\s*$", re.IGNORECASE)
_PAREN_RE = re.compile(r"\s*\([^)]*\)\s*")


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("\xa0", " ")).strip()


def normalize_minutes_name(name: str) -> str:
    """'Deputy Mayor and Councillor John Kovac, Ward 4' -> 'john kovac'."""
    name = _clean(name)
    name = _WARD_SUFFIX_RE.sub("", name)
    name = _ROLE_PREFIX_RE.sub("", name)
    name = _PAREN_RE.sub(" ", name)
    name = name.rstrip(",")
    name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    return _clean(name).lower()


@dataclass(slots=True)
class ParsedAttendance:
    name: str  # Raw printed name.
    status: str  # present | absent | regrets


@dataclass(slots=True)
class ParsedMotion:
    sequence: int
    resolution_number: str | None
    item_title: str | None
    text: str
    mover: str | None
    seconder: str | None
    result: str
    # {"yea": [names], "nay": [names], "abstain": [names], "absent": [names]}
    votes: dict[str, list[str]] = field(default_factory=dict)


@dataclass(slots=True)
class ParsedMinutes:
    attendance: list[ParsedAttendance]
    motions: list[ParsedMotion]
    declarations: list[str]  # Raw declaration lines ("Nil" filtered out).


class EscribeClient:
    def __init__(self, tenant: str) -> None:
        self.base = f"https://pub-{tenant}.escribemeetings.com"
        self._client = httpx.AsyncClient(
            headers={"User-Agent": f"Mozilla/5.0 (compatible; {settings.ingestion_user_agent})"},
            timeout=60.0,
            follow_redirects=True,
        )

    async def __aenter__(self) -> "EscribeClient":
        return self

    async def __aexit__(self, *exc: Any) -> None:
        await self._client.aclose()

    async def list_meetings(self, start: date, end: date) -> list[dict[str, Any]]:
        await asyncio.sleep(REQUEST_DELAY_SECONDS)
        response = await self._client.post(
            f"{self.base}/MeetingsCalendarView.aspx/GetCalendarMeetings",
            json={
                "calendarStartDate": start.isoformat(),
                "calendarEndDate": end.isoformat(),
                "filters": [],
            },
        )
        response.raise_for_status()
        return response.json().get("d", [])

    def minutes_url(self, meeting_guid: str) -> str:
        return f"{self.base}/Meeting.aspx?Id={meeting_guid}&Agenda=PostMinutes&lang=English"

    async def fetch_minutes(self, meeting_guid: str) -> str | None:
        await asyncio.sleep(REQUEST_DELAY_SECONDS)
        try:
            response = await self._client.get(self.minutes_url(meeting_guid))
            response.raise_for_status()
            return response.text
        except httpx.HTTPError as exc:
            logger.warning("escribe minutes fetch failed %s: %s", meeting_guid, exc)
            return None


# --- Parsing ----------------------------------------------------------------


def _attendance_status(label: str) -> str | None:
    """Label div -> status. Staff and non-member rows return None."""
    lowered = label.lower()
    if "staff" in lowered or "also" in lowered or "other" in lowered:
        return None
    if "member" in lowered or "present" in lowered or "regrets" in lowered or "absent" in lowered:
        if "regret" in lowered:
            return "regrets"
        if "absent" in lowered:
            return "absent"
        return "present"
    return None


def parse_attendance(tree: HTMLParser) -> list[ParsedAttendance]:
    block = tree.css_first("div.AgendaHeaderAttendance")
    if block is None:
        return []
    rows: list[ParsedAttendance] = []
    for label_node in block.css("div.Label"):
        status = _attendance_status(_clean(label_node.text()))
        if status is None:
            continue
        value = label_node.next
        while value is not None and (
            not hasattr(value, "attributes") or (value.attributes.get("class") or "") != "Value"
        ):
            value = value.next
        if value is None:
            continue
        for li in value.css("li"):
            name = _clean(li.text(separator=" "))
            if name:
                rows.append(ParsedAttendance(name=name, status=status))
    return rows


_RESULT_MAP = [
    ("carried", "carried"),
    ("lost", "lost"),
    ("defeated", "lost"),
    ("referred", "referred"),
    ("withdrawn", "withdrawn"),
    ("deferred", "referred"),
]

_VOTE_BUCKETS = [
    (("yes", "yea", "in favour", "for"), "yea"),
    (("no", "nay", "against", "opposed"), "nay"),
    (("abstain",), "abstain"),
    (("absent", "conflict"), "absent"),
]


def _motion_result(text: str) -> str:
    lowered = text.lower()
    for needle, result in _RESULT_MAP:
        if needle in lowered:
            return result
    return "unknown"


def _vote_bucket(label: str) -> str | None:
    lowered = label.lower()
    for needles, bucket in _VOTE_BUCKETS:
        if any(lowered.startswith(n) for n in needles):
            return bucket
    return None


def _label_value(node: Node, cls: str) -> str | None:
    """<div class='MovedBy'><span class='Label'>..</span><span class='Value'>name</span>"""
    container = node.css_first(f"div.{cls}")
    if container is None:
        return None
    value = container.css_first("span.Value")
    text = _clean(value.text(separator=" ")) if value is not None else ""
    if not text:
        # Some tenants skip the span structure; strip the label text.
        text = _clean(container.text(separator=" "))
        text = re.sub(r"^(moved by|seconded by|resolution)\s*", "", text, flags=re.IGNORECASE)
    return text or None


def _parse_motion_votes(motion_node: Node) -> dict[str, list[str]]:
    votes: dict[str, list[str]] = {}
    table = motion_node.css_first("table.MotionVoters")
    if table is None:
        return votes
    current: str | None = None
    for row in table.css("tr"):
        vote_cell = row.css_first("td.VoterVote")
        users_cell = row.css_first("td.VotesUsers")
        if vote_cell is not None:
            current = _vote_bucket(_clean(vote_cell.text()))
        if users_cell is None or current is None:
            continue
        names = [_clean(n) for n in users_cell.text(separator=" ").replace(" and ", ",").split(",")]
        for name in names:
            if name:
                votes.setdefault(current, []).append(name)
    return votes


def _item_title_for(motion_node: Node) -> str | None:
    """Nearest enclosing AgendaItemContainer's heading. Containers nest
    (section 10 contains item 10.1), so walk up to the closest one."""
    ancestor = motion_node.parent
    while ancestor is not None:
        if "AgendaItemContainer" in (ancestor.attributes.get("class") or ""):
            heading = ancestor.css_first("h2, h3")
            if heading is not None:
                title = _clean(heading.text(separator=" "))
                if title:
                    return title[:500]
        ancestor = ancestor.parent
    return None


def parse_motions(tree: HTMLParser) -> list[ParsedMotion]:
    motions: list[ParsedMotion] = []
    for sequence, node in enumerate(tree.css("li.AgendaItemMotion"), start=1):
        number_node = node.css_first("div.Number span.Value") or node.css_first("div.Number u")
        resolution = _clean(number_node.text()) if number_node is not None else None
        text_node = node.css_first("div.MotionText")
        result_node = node.css_first("div.MotionResult")
        motions.append(
            ParsedMotion(
                sequence=sequence,
                resolution_number=(resolution or None),
                item_title=_item_title_for(node),
                text=_clean(text_node.text(separator="\n"))[:20000] if text_node else "",
                mover=_label_value(node, "MovedBy"),
                seconder=_label_value(node, "SecondedBy"),
                result=_motion_result(_clean(result_node.text()) if result_node else ""),
                votes=_parse_motion_votes(node),
            )
        )
    return motions


_DECLARATION_HEADING_RE = re.compile(r"declaration.{0,4}of\s+conflict", re.IGNORECASE)


def parse_declarations(tree: HTMLParser) -> list[str]:
    """Text lines under the 'Declaration of Conflict of Interest' item."""
    for container in tree.css("div.AgendaItemContainer"):
        heading = container.css_first("h2, h3")
        if heading is None or not _DECLARATION_HEADING_RE.search(heading.text()):
            continue
        body = container.css_first("div.AgendaItemMinutes")
        if body is None:
            return []
        lines = [
            _clean(p.text(separator=" "))
            for p in (body.css("p, li") or [body])
        ]
        return [l for l in lines if l and l.lower() not in {"nil", "none", "nil.", "none."}]
    return []


_NARRATIVE_MOVED_RE = re.compile(
    r"^MOVED by\s+(?P<mover>[^,;]+?)(?:,?\s+(?:and\s+)?seconded by\s+(?P<seconder>[^,;]+?))?\s*$",
    re.IGNORECASE,
)
_NARRATIVE_RESULT_RE = re.compile(
    r"MOTION\s+PUT\s+AND\s+(?P<result>PASSED|DEFEATED|LOST)", re.IGNORECASE
)


def _parse_narrative_motions(tree: HTMLParser) -> list[ParsedMotion]:
    """Fallback for tenants (e.g. Halifax) whose minutes narrate motions as
    'MOVED by X, seconded by Y ... MOTION PUT AND PASSED' inside the item
    body instead of structured AgendaItemMotion elements."""
    motions: list[ParsedMotion] = []
    sequence = 0
    for body in tree.css("div.AgendaItemMinutes"):
        paragraphs = [_clean(p.text(separator=" ")) for p in body.css("p")]
        current: dict[str, Any] | None = None
        for paragraph in paragraphs:
            moved = _NARRATIVE_MOVED_RE.match(paragraph)
            if moved:
                current = {
                    "mover": _clean(moved.group("mover")),
                    "seconder": _clean(moved.group("seconder") or "") or None,
                    "text": [],
                }
                continue
            if current is None:
                continue
            result_match = _NARRATIVE_RESULT_RE.search(paragraph)
            if result_match:
                sequence += 1
                container = body.parent
                title = None
                while container is not None:
                    if "AgendaItemContainer" in (container.attributes.get("class") or ""):
                        heading = container.css_first("h2, h3")
                        if heading is not None:
                            title = _clean(heading.text(separator=" "))[:500] or None
                        break
                    container = container.parent
                motions.append(
                    ParsedMotion(
                        sequence=sequence,
                        resolution_number=None,
                        item_title=title,
                        text=_clean("\n".join(current["text"]))[:20000],
                        mover=current["mover"],
                        seconder=current["seconder"],
                        result="carried" if result_match.group("result").upper() == "PASSED" else "lost",
                    )
                )
                current = None
            else:
                current["text"].append(paragraph)
    return motions


def parse_minutes(html: str) -> ParsedMinutes:
    tree = HTMLParser(html)
    motions = parse_motions(tree)
    if not motions:
        motions = _parse_narrative_motions(tree)
    return ParsedMinutes(
        attendance=parse_attendance(tree),
        motions=motions,
        declarations=parse_declarations(tree),
    )


# --- Persistence -------------------------------------------------------------


class EscribeSyncContext:
    def __init__(self, db: Session, tenant: EscribeTenant) -> None:
        self.db = db
        self.tenant = tenant
        jurisdiction = db.scalar(
            select(Jurisdiction).where(Jurisdiction.code == tenant.jurisdiction_code)
        )
        if jurisdiction is None:
            raise RuntimeError(
                f"jurisdiction {tenant.jurisdiction_code} missing — run the Represent sync first"
            )
        self.jurisdiction = jurisdiction
        chamber = db.scalar(
            select(Chamber).where(Chamber.jurisdiction_id == jurisdiction.id, Chamber.slug == "council")
        )
        if chamber is None:
            raise RuntimeError(f"council chamber missing for {tenant.jurisdiction_code}")
        self.chamber = chamber
        self._roster: dict[str, Person] | None = None
        self._session: LegislatureSession | None = None

    def council_session(self) -> LegislatureSession:
        """Council term as a session: parliament_number = term start year."""
        if self._session is not None:
            return self._session
        term_year = self.tenant.term_start.year
        row = self.db.scalar(
            select(LegislatureSession).where(
                LegislatureSession.jurisdiction_id == self.jurisdiction.id,
                LegislatureSession.parliament_number == term_year,
                LegislatureSession.session_number == 1,
            )
        )
        if row is None:
            row = LegislatureSession(
                jurisdiction_id=self.jurisdiction.id,
                parliament_number=term_year,
                session_number=1,
                started_on=self.tenant.term_start,
                is_current=True,
            )
            self.db.add(row)
            self.db.flush()
        self._session = row
        return row

    def _load_roster(self) -> dict[str, Person]:
        """Match keys: full name, 'f. lastname' initial form, bare last name
        (only when unique in the roster)."""
        if self._roster is not None:
            return self._roster
        roster: dict[str, Person] = {}
        last_names: dict[str, list[Person]] = {}
        people = self.db.scalars(
            select(Person).where(Person.chamber_id == self.chamber.id)
        ).all()
        for person in people:
            full = normalize_minutes_name(person.full_name)
            roster[full] = person
            parts = full.split()
            if len(parts) >= 2:
                roster[f"{parts[0][0]}. {parts[-1]}"] = person
                roster[f"{parts[0][0]} {parts[-1]}"] = person
                last_names.setdefault(parts[-1], []).append(person)
        for last, persons in last_names.items():
            if len(persons) == 1 and last not in roster:
                roster[last] = persons[0]
        self._roster = roster
        return roster

    def match_person(self, printed_name: str) -> Person | None:
        key = normalize_minutes_name(printed_name)
        roster = self._load_roster()
        person = roster.get(key)
        if person is None and key:
            # "b. butt" already covered; try dropping middle initials.
            parts = key.replace(".", "").split()
            if len(parts) >= 2:
                person = roster.get(f"{parts[0][0]}. {parts[-1]}") or roster.get(parts[-1])
        if person is None:
            logger.debug("escribe %s: unmatched name %r", self.tenant.tenant, printed_name)
        return person


def _upsert_meeting(
    ctx: EscribeSyncContext, raw: dict[str, Any], minutes_url: str
) -> Meeting:
    db = ctx.db
    source_id = f"{ctx.tenant.tenant}:{raw['ID']}"
    started = datetime.strptime(raw["StartDate"], "%Y/%m/%d %H:%M:%S")
    meeting = db.scalar(
        select(Meeting).where(Meeting.source_system == "escribe", Meeting.source_id == source_id)
    )
    if meeting is None:
        meeting = Meeting(
            chamber_id=ctx.chamber.id,
            source_system="escribe",
            source_id=source_id,
            body_name=_clean(raw["MeetingName"]),
            meeting_date=started.date(),
        )
        db.add(meeting)
    meeting.body_name = _clean(raw["MeetingName"])
    meeting.started_at = started
    meeting.meeting_date = started.date()
    meeting.minutes_url = minutes_url
    db.flush()
    return meeting


def _persist_attendance(ctx: EscribeSyncContext, meeting: Meeting, rows: list[ParsedAttendance]) -> int:
    db = ctx.db
    count = 0
    for row in rows:
        person = ctx.match_person(row.name)
        if person is None:
            logger.info(
                "escribe %s: attendance name unmatched %r (%s)",
                ctx.tenant.tenant, row.name, meeting.minutes_url,
            )
            continue
        existing = db.scalar(
            select(MeetingAttendance).where(
                MeetingAttendance.meeting_id == meeting.id,
                MeetingAttendance.person_id == person.id,
            )
        )
        if existing is None:
            existing = MeetingAttendance(meeting_id=meeting.id, person_id=person.id)
            db.add(existing)
        existing.status = row.status
        existing.source_name = row.name[:255]
        count += 1
    db.flush()
    return count


def _vote_number_for(meeting: Meeting, parsed: ParsedMotion) -> str:
    base = parsed.resolution_number or f"seq{parsed.sequence}"
    return f"{meeting.meeting_date.isoformat()}-{slugify(base)}"[:64]


def _persist_motion_vote(
    ctx: EscribeSyncContext, meeting: Meeting, parsed: ParsedMotion
) -> Vote | None:
    """MotionVoters -> shared Vote/Ballot rows (same tables as Parliament)."""
    if not parsed.votes:
        return None
    db = ctx.db
    session = ctx.council_session()
    number = _vote_number_for(meeting, parsed)
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
            occurred_on=meeting.meeting_date,
            description_en="",
        )
        db.add(vote)
    title = parsed.item_title or "Motion"
    vote.occurred_on = meeting.meeting_date
    vote.description_en = f"{meeting.body_name}: {title} — {parsed.text[:300]}".strip(" —")
    vote.result = "Passed" if parsed.result == "carried" else "Negatived" if parsed.result == "lost" else None
    vote.yea_total = len(parsed.votes.get("yea", []))
    vote.nay_total = len(parsed.votes.get("nay", []))
    vote.source_url = meeting.minutes_url
    vote.vote_type = "free"  # Councils have no party whips.
    db.flush()

    for bucket, ballot_value in (("yea", "yea"), ("nay", "nay"), ("abstain", "abstain"), ("absent", "absent")):
        for name in parsed.votes.get(bucket, []):
            person = ctx.match_person(name)
            if person is None:
                logger.info(
                    "escribe %s: ballot name unmatched %r (%s)",
                    ctx.tenant.tenant, name, meeting.minutes_url,
                )
                continue
            ballot = db.scalar(
                select(Ballot).where(Ballot.vote_id == vote.id, Ballot.person_id == person.id)
            )
            if ballot is None:
                ballot = Ballot(vote_id=vote.id, person_id=person.id, ballot=ballot_value)
                db.add(ballot)
            ballot.ballot = ballot_value
    db.flush()
    compute_party_lines(db, vote)
    return vote


def _persist_motions(ctx: EscribeSyncContext, meeting: Meeting, motions: list[ParsedMotion]) -> int:
    db = ctx.db
    for parsed in motions:
        motion = db.scalar(
            select(Motion).where(Motion.meeting_id == meeting.id, Motion.sequence == parsed.sequence)
        )
        if motion is None:
            motion = Motion(meeting_id=meeting.id, sequence=parsed.sequence)
            db.add(motion)
        motion.resolution_number = parsed.resolution_number
        motion.item_title = parsed.item_title
        motion.text_en = parsed.text
        motion.result = parsed.result
        motion.source_url = meeting.minutes_url
        mover = ctx.match_person(parsed.mover) if parsed.mover else None
        seconder = ctx.match_person(parsed.seconder) if parsed.seconder else None
        motion.mover_person_id = mover.id if mover else None
        motion.seconder_person_id = seconder.id if seconder else None
        vote = _persist_motion_vote(ctx, meeting, parsed)
        motion.vote_id = vote.id if vote else None
    db.flush()
    return len(motions)


def _persist_declarations(ctx: EscribeSyncContext, meeting: Meeting, lines: list[str]) -> int:
    db = ctx.db
    for line in lines:
        note = line[:2000]
        exists = db.scalar(
            select(ConflictDeclaration).where(
                ConflictDeclaration.meeting_id == meeting.id,
                ConflictDeclaration.note == note,
            )
        )
        if exists is not None:
            continue
        # Best effort person match against any roster name in the line.
        person = None
        person_name = None
        for key_name, roster_person in ctx._load_roster().items():
            if len(key_name) > 4 and key_name in normalize_minutes_name(line):
                person, person_name = roster_person, roster_person.full_name
                break
        db.add(
            ConflictDeclaration(
                meeting_id=meeting.id,
                person_id=person.id if person else None,
                person_name=person_name,
                note=note,
            )
        )
    db.flush()
    return len(lines)


def _month_windows(start: date, end: date) -> list[tuple[date, date]]:
    windows = []
    cursor = start.replace(day=1)
    while cursor <= end:
        nxt = (cursor.replace(day=28) + timedelta(days=4)).replace(day=1)
        windows.append((cursor, min(nxt, end + timedelta(days=1))))
        cursor = nxt
    return windows


async def sync_escribe_tenant(
    db: Session, tenant: EscribeTenant, *, since: date | None = None, force: bool = False
) -> dict[str, int]:
    """Sync one tenant. Default: incremental (last synced meeting minus the
    re-parse window). Pass since=tenant.term_start for a term backfill and
    force=True to re-parse meetings after a parser upgrade."""
    ctx = EscribeSyncContext(db, tenant)
    counts = {"meetings": 0, "attendance": 0, "motions": 0, "declarations": 0}

    if since is None:
        latest = db.scalar(
            select(Meeting.meeting_date)
            .where(Meeting.chamber_id == ctx.chamber.id)
            .order_by(Meeting.meeting_date.desc())
            .limit(1)
        )
        since = (latest - timedelta(days=REPARSE_WINDOW_DAYS)) if latest else tenant.term_start

    today = date.today()
    async with EscribeClient(tenant.tenant) as client:
        for window_start, window_end in _month_windows(since, today):
            try:
                raw_meetings = await client.list_meetings(window_start, window_end)
            except httpx.HTTPError as exc:
                logger.warning("escribe %s calendar failed %s: %s", tenant.tenant, window_start, exc)
                continue
            for raw in raw_meetings:
                name = _clean(raw.get("MeetingName") or "")
                if name not in tenant.bodies:
                    continue
                if "cancelled" in name.lower():
                    continue
                started = datetime.strptime(raw["StartDate"], "%Y/%m/%d %H:%M:%S")
                if started.date() > today:
                    continue  # Minutes can't exist yet.
                minutes_url = client.minutes_url(raw["ID"])
                meeting = _upsert_meeting(ctx, raw, minutes_url)
                fresh = (today - meeting.meeting_date).days <= REPARSE_WINDOW_DAYS
                if meeting.minutes_parsed and not fresh and not force:
                    continue  # Already parsed and past the amendment window.
                html = await client.fetch_minutes(raw["ID"])
                if html is None:
                    continue
                parsed = parse_minutes(html)
                if not parsed.attendance:
                    # Minutes not published yet (agenda-only page).
                    db.commit()
                    continue
                counts["attendance"] += _persist_attendance(ctx, meeting, parsed.attendance)
                counts["motions"] += _persist_motions(ctx, meeting, parsed.motions)
                counts["declarations"] += _persist_declarations(ctx, meeting, parsed.declarations)
                meeting.minutes_parsed = True
                counts["meetings"] += 1
                db.commit()
    db.commit()
    return counts


async def sync_all_escribe(db: Session, *, backfill: bool = False) -> dict[str, dict[str, int]]:
    results: dict[str, dict[str, int]] = {}
    for tenant in TENANTS:
        try:
            results[tenant.tenant] = await sync_escribe_tenant(
                db, tenant, since=tenant.term_start if backfill else None
            )
        except Exception as exc:  # noqa: BLE001 — one city must not sink the rest.
            logger.exception("escribe %s failed: %s", tenant.tenant, exc)
            db.rollback()
            results[tenant.tenant] = {"error": 1}
    return results
