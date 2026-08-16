"""Ontario lobbyist registry: registrations, from lobbyist.oico.on.ca.

What Ontario publishes is different from Ottawa: *registrations* (who is
licensed to lobby which ministries/offices about what) — NOT per-meeting
communication logs. Nothing here means "met with"; it means "registered
to lobby". The UI copy must preserve that distinction.

The registry is a 2011-era ASP.NET WebForms app (Telerik RadGrid) with no
export or API, so this module drives it the way a browser does. The one
reliable primitive (verified empirically) is: a FRESHLY rendered grid
state supports exactly ONE row "click" (__EVENTARGUMENT=RowClick;<idx>);
any further click from the same or a stale state returns the WRONG
registration. The walker is built around that constraint:

1. Metadata pass: quick-search (active) and walk pages with the pager's
   "Next Page" control, collecting rows only (no clicks) — the grid is
   ordered by Last Amendment Date descending, so incremental syncs stop
   at the first fully-known page.
2. Detail pass, one registration at a time: re-run the search restricted
   to that registration's amendment DATE (the date-range filter), page to
   its row, and click once from that fresh state. Every parsed detail is
   verified against the expected registration number and skipped loudly
   on mismatch.

Deterministic parsing only — no LLM anywhere in ingestion.
"""
from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass, field
from datetime import date, datetime

import httpx
from selectolax.parser import HTMLParser
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import Chamber, LobbyRegistration, LobbyRegistrationMpp, Person, PersonMembership, PersonRole

logger = logging.getLogger(__name__)

BASE_URL = "https://lobbyist.oico.on.ca/Pages/Public/PublicSearch/"
GRID = "ctl00$BodyContent$ucSearchResults$gridSearchResults$GridRegistrationList"
REQUEST_DELAY_SECONDS = 0.5

_TYPE_MAP = {
    "consultant": "consultant",
    "in-house organization": "in_house_organization",
    "in-house persons": "in_house_persons",
}

MPP_OFFICE_PREFIX = "Office of the Member for "


# ---------------------------------------------------------------------------
# Parsing (pure functions, fixture-tested)
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class GridRow:
    lobbyist_name: str
    last_amendment_date: date | None
    client_name: str | None
    firm_name: str | None
    lobbyist_type: str
    registration_number: str
    status: str


@dataclass(slots=True)
class RegistrationDetail:
    registration_number: str = ""
    lobbyist_number: str | None = None
    lobbyist_name: str | None = None
    firm_name: str | None = None
    client_name: str | None = None
    client_description: str | None = None
    initial_filing_date: date | None = None
    subject_matters: str | None = None
    goals: str | None = None
    target_ministries: list[str] = field(default_factory=list)
    target_mpp_offices: list[str] = field(default_factory=list)
    techniques: str | None = None


def _parse_grid_date(raw: str) -> date | None:
    raw = raw.strip()
    try:
        return datetime.strptime(raw, "%m-%d-%Y").date()
    except ValueError:
        return None


def _clean(text: str | None) -> str:
    return re.sub(r"\s+", " ", text or "").replace("\xa0", " ").strip()


def parse_grid_rows(html: str) -> list[GridRow]:
    """The visible + hidden cells of every result row, in row order."""
    tree = HTMLParser(html)
    rows: list[GridRow] = []
    for tr in tree.css("tr.rgRow, tr.rgAltRow"):
        cells = [_clean(td.text()) for td in tr.css("td")]
        if len(cells) < 8:
            continue
        raw_type = cells[4].lower()
        lobbyist_type = next((v for k, v in _TYPE_MAP.items() if k in raw_type), "consultant")
        rows.append(
            GridRow(
                lobbyist_name=cells[0],
                last_amendment_date=_parse_grid_date(cells[1]),
                client_name=cells[2] or None,
                firm_name=cells[3] or None,
                lobbyist_type=lobbyist_type,
                registration_number=cells[5],
                status=(cells[7] or "active").lower(),
            )
        )
    return rows


def parse_next_page_target(html: str) -> str | None:
    m = re.search(r'name="([^"]*)"[^>]*class="rgPageNext"', html)
    return m.group(1) if m else None


def parse_total_items(html: str) -> int | None:
    m = re.search(r"<strong>(\d+)</strong>\s*items", html)
    return int(m.group(1)) if m else None


def _value_by_id_suffix(tree: HTMLParser, suffix: str) -> str | None:
    """WebForms convention: every field is a span/td whose id ends with a
    stable suffix; only the ucXxx prefixes vary between layouts."""
    node = tree.css_first(f'[id$="{suffix}"]')
    return _clean(node.text()) if node else None


def _items_by_id_suffix(tree: HTMLParser, suffix: str) -> list[str]:
    """<br>-separated target lists across every lobbying-activity section
    (Bill, Regulation, GrantContribution, ...), deduped in filing order."""
    seen: dict[str, None] = {}
    for node in tree.css(f'[id$="{suffix}"]'):
        for chunk in re.split(r"<br\s*/?>", node.html or ""):
            text = _clean(re.sub(r"<[^>]+>", " ", chunk))
            if text and text != "-":
                seen.setdefault(text, None)
    return list(seen)


def parse_registration_detail(html: str) -> RegistrationDetail:
    tree = HTMLParser(html)
    detail = RegistrationDetail()

    detail.registration_number = _value_by_id_suffix(tree, "_lblRegistrationNumberValue") or ""
    detail.lobbyist_number = _value_by_id_suffix(tree, "_lblLobbyistNumberValue")
    first = _value_by_id_suffix(tree, "_lblFirstNameValue") or ""
    last = _value_by_id_suffix(tree, "_lblLastNameValue") or ""
    detail.lobbyist_name = _clean(f"{first} {last}") or None
    detail.firm_name = _value_by_id_suffix(tree, "_lblFirmNameValue")
    detail.client_name = _value_by_id_suffix(tree, "_txtClientName")
    detail.client_description = _value_by_id_suffix(tree, "_txtClientBusinessDescription")
    filed = _value_by_id_suffix(tree, "_lblInitialFilingDateValue")
    if filed:
        try:
            detail.initial_filing_date = datetime.strptime(filed, "%Y-%m-%d").date()
        except ValueError:
            pass

    # Both layouts: SubjectMatters (consultant) / OLSubjectMatters (in-house).
    # Values are <br>- or semicolon-separated; normalize to "; ".
    subject_parts = _items_by_id_suffix(tree, "_lblSubjectMatter")
    subject_parts += [p for p in _items_by_id_suffix(tree, "_lblSubjectMatterOther") if p not in subject_parts]
    subjects = "; ".join(p.strip(";") for p in subject_parts)
    detail.subject_matters = re.sub(r";\s*;", ";", subjects).strip("; ") or None

    goals: dict[str, None] = {}
    for node in tree.css('[id$="_txtGoalDescription"]'):
        text = _clean(node.text())
        if text:
            goals.setdefault(text, None)
    detail.goals = " · ".join(goals) or None

    ministries = _items_by_id_suffix(tree, "_cellMinistersOfficesItems")
    ministries += [m for m in _items_by_id_suffix(tree, "_cellMinistriesItems") if m not in ministries]
    detail.target_ministries = ministries
    detail.target_mpp_offices = _items_by_id_suffix(tree, "_cellMPPItems")

    detail.techniques = _value_by_id_suffix(tree, "_lblCommunicationTechiquesUsed")
    return detail


def mpp_riding(office: str) -> str | None:
    """'Office of the Member for Niagara West' -> 'Niagara West'."""
    if office.startswith(MPP_OFFICE_PREFIX):
        return office[len(MPP_OFFICE_PREFIX):].strip() or None
    return None


# ---------------------------------------------------------------------------
# WebForms driver
# ---------------------------------------------------------------------------

class OntarioLobbyRegistryClient:
    """Drives the public-search WebForms app over plain httpx."""

    def __init__(self) -> None:
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> "OntarioLobbyRegistryClient":
        self._client = httpx.AsyncClient(
            headers={"User-Agent": get_settings().ingestion_user_agent},
            timeout=90.0,
            follow_redirects=True,
        )
        return self

    async def __aexit__(self, *exc: object) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    @staticmethod
    def _state(html: str) -> dict[str, str]:
        def hidden(name: str) -> str:
            m = re.search(rf'id="{name}" value="([^"]*)"', html)
            return m.group(1) if m else ""

        return {
            name: hidden(name)
            for name in ("__VIEWSTATE", "__VIEWSTATEGENERATOR", "__VIEWSTATEENCRYPTED", "__EVENTVALIDATION")
        }

    async def _post(self, url: str, data: dict[str, str]) -> str:
        """POST with retries — these are idempotent page renders, and a
        single transient ReadError must not abort a multi-hour crawl."""
        assert self._client is not None
        last_exc: Exception | None = None
        for attempt in range(3):
            try:
                response = await self._client.post(url, data=data)
                response.raise_for_status()
                await asyncio.sleep(REQUEST_DELAY_SECONDS)
                return response.text
            except httpx.TransportError as exc:
                last_exc = exc
                await asyncio.sleep(2.0 * (attempt + 1))
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code < 500:
                    raise
                last_exc = exc
                await asyncio.sleep(2.0 * (attempt + 1))
        assert last_exc is not None
        raise last_exc

    async def _get(self, url: str) -> str:
        assert self._client is not None
        last_exc: Exception | None = None
        for attempt in range(3):
            try:
                response = await self._client.get(url)
                response.raise_for_status()
                await asyncio.sleep(REQUEST_DELAY_SECONDS)
                return response.text
            except httpx.TransportError as exc:
                last_exc = exc
                await asyncio.sleep(2.0 * (attempt + 1))
        assert last_exc is not None
        raise last_exc

    @staticmethod
    def _date_fields(prefix: str, iso: str) -> dict[str, str]:
        """Telerik RadDatePicker fields, exactly as a browser posts them."""
        return {
            f"ctl00$BodyContent$ucQuickSearch$dp{prefix}": iso,
            f"ctl00_BodyContent_ucQuickSearch_dp{prefix}_dateInput_text": iso,
            f"ctl00$BodyContent$ucQuickSearch$dp{prefix}$dateInput": f"{iso}-00-00-00",
        }

    async def _search(self, extra: dict[str, str]) -> str:
        landing = await self._get(BASE_URL + "Default.aspx")
        return await self._post(
            BASE_URL + "Default.aspx",
            {
                "__EVENTTARGET": "",
                "__EVENTARGUMENT": "",
                "__LASTFOCUS": "",
                **self._state(landing),
                "ctl00$BodyContent$ucQuickSearch$rdoStatusGroup1": "rdoCurrentlyActive",
                **extra,
                "ctl00$BodyContent$ucQuickSearch$btnSearch": "SEARCH",
            },
        )

    async def search_active(self) -> str:
        """Quick search for all active registrations; returns page 1 HTML."""
        return await self._search({})

    async def search_window(self, start: date, end: date, *, lobbyist: str | None = None) -> str:
        """Active registrations last amended within [start, end], optionally
        narrowed to a lobbyist name — tiny result sets make row clicks cheap
        and deterministic."""
        extra = {
            "ctl00$BodyContent$ucQuickSearch$rdoStatusGroup2": "rdoActiveWithinDates",
            **self._date_fields("FromDate", start.isoformat()),
            **self._date_fields("ToDate", end.isoformat()),
        }
        if lobbyist:
            extra["ctl00$BodyContent$ucQuickSearch$txtSearchByLobbyist"] = lobbyist
        return await self._search(extra)

    async def next_page(self, current_html: str) -> str | None:
        target = parse_next_page_target(current_html)
        if not target:
            return None
        return await self._post(
            BASE_URL + "SearchResults.aspx",
            {"__EVENTTARGET": target, "__EVENTARGUMENT": "", **self._state(current_html)},
        )

    async def fetch_detail(self, grid_html: str, row_index: int) -> str:
        """Row click from a grid page's saved state -> detail page HTML."""
        return await self._post(
            BASE_URL + "SearchResults.aspx",
            {
                "__EVENTTARGET": GRID,
                "__EVENTARGUMENT": f"RowClick;{row_index}",
                **self._state(grid_html),
            },
        )


# ---------------------------------------------------------------------------
# Sync
# ---------------------------------------------------------------------------

def _ontario_mpp_index(db: Session) -> dict[str, int]:
    """lowercased current riding name -> person_id, Ontario assembly only."""
    rows = db.execute(
        select(PersonMembership.riding_name, PersonMembership.person_id)
        .join(Person, PersonMembership.person_id == Person.id)
        .join(Chamber, Person.chamber_id == Chamber.id)
        .where(Chamber.slug == "on-assembly", PersonMembership.is_current.is_(True))
    ).all()
    return {riding.lower(): person_id for riding, person_id in rows if riding}


def _ontario_minister_index(db: Session) -> dict[str, int]:
    """Normalized current-minister title -> person_id, Ontario assembly only.

    Includes the Premier and associate ministers; keys are lowercase titles
    ("minister of transportation", "premier", "attorney general").
    """
    rows = db.execute(
        select(PersonRole.title_en, PersonRole.person_id)
        .join(Person, PersonRole.person_id == Person.id)
        .join(Chamber, Person.chamber_id == Chamber.id)
        .where(
            Chamber.slug == "on-assembly",
            PersonRole.role_type == "minister",
            PersonRole.is_current.is_(True),
        )
    ).all()
    return {title.lower().strip(): person_id for title, person_id in rows if title}


def resolve_ministry_target(target: str, minister_index: dict[str, int]) -> int | None:
    """'Office of the Minister of Transportation' / 'Ministry of Transportation'
    -> the sitting minister's person_id (None when the portfolio is vacant or
    the string doesn't name a ministry)."""
    text = re.sub(r"\s+", " ", target).strip().lower()
    text = re.sub(r"^office of the ", "", text)
    candidates = [text]
    if text.startswith("ministry of "):
        candidates.append("minister of " + text[len("ministry of "):])
    if "premier" in text or text == "cabinet office":
        candidates.append("premier")
    if "attorney general" in text:
        candidates.append("attorney general")
        candidates.append("minister of the attorney general")
    for candidate in candidates:
        person_id = minister_index.get(candidate)
        if person_id is not None:
            return person_id
    return None


def upsert_stub(db: Session, row: GridRow) -> LobbyRegistration:
    """Phase 1: store what the grid alone gives us — the registration
    exists and is searchable immediately; details follow in phase 2.

    A changed amendment date flips detail_synced back to False so
    amendments get their details re-fetched."""
    registration = db.scalar(
        select(LobbyRegistration).where(
            LobbyRegistration.registration_number == row.registration_number
        )
    )
    if registration is None:
        registration = LobbyRegistration(
            registration_number=row.registration_number,
            jurisdiction_code="on",
            detail_synced=False,
        )
        db.add(registration)
    elif registration.last_amendment_date != row.last_amendment_date:
        registration.detail_synced = False

    registration.jurisdiction_code = "on"
    registration.lobbyist_number = registration.lobbyist_number or row.registration_number.split("-")[0]
    registration.lobbyist_name = row.lobbyist_name or registration.lobbyist_name
    registration.firm_name = row.firm_name or registration.firm_name
    registration.lobbyist_type = row.lobbyist_type
    registration.client_name = row.client_name or registration.client_name
    registration.status = row.status or "active"
    registration.last_amendment_date = row.last_amendment_date
    db.flush()
    return registration


def apply_detail(
    db: Session,
    registration: LobbyRegistration,
    detail: RegistrationDetail,
    mpp_index: dict[str, int],
    minister_index: dict[str, int] | None = None,
) -> None:
    """Phase 2: the full filing — goals, subjects, targets, person links."""
    registration.lobbyist_number = detail.lobbyist_number or registration.lobbyist_number
    registration.lobbyist_name = detail.lobbyist_name or registration.lobbyist_name
    registration.firm_name = detail.firm_name or registration.firm_name
    registration.client_name = detail.client_name or registration.client_name
    registration.client_description = detail.client_description
    registration.initial_filing_date = detail.initial_filing_date
    registration.subject_matters = detail.subject_matters
    registration.goals = detail.goals
    registration.target_ministries = "\n".join(detail.target_ministries) or None
    registration.target_mpp_offices = "\n".join(detail.target_mpp_offices) or None
    registration.techniques = detail.techniques
    registration.detail_synced = True
    db.flush()

    # Re-resolve person links from scratch (amendments change targets).
    for link in list(registration.mpp_links):
        db.delete(link)
    db.flush()
    seen: set[int] = set()
    for office in detail.target_mpp_offices:
        riding = mpp_riding(office)
        person_id = mpp_index.get(riding.lower()) if riding else None
        if person_id and person_id not in seen:
            seen.add(person_id)
            db.add(
                LobbyRegistrationMpp(
                    registration_id=registration.id,
                    person_id=person_id,
                    target_kind="mpp_office",
                    riding_as_filed=riding,
                )
            )
    # Ministry targets -> the sitting minister (one link per person; an
    # explicit constituency-office link wins over a ministry link).
    for target in detail.target_ministries:
        person_id = resolve_ministry_target(target, minister_index or {})
        if person_id and person_id not in seen:
            seen.add(person_id)
            db.add(
                LobbyRegistrationMpp(
                    registration_id=registration.id,
                    person_id=person_id,
                    target_kind="ministry",
                    riding_as_filed=None,
                )
            )


def upsert_registration(
    db: Session,
    row: GridRow,
    detail: RegistrationDetail,
    mpp_index: dict[str, int],
    minister_index: dict[str, int] | None = None,
) -> LobbyRegistration:
    """Stub + detail in one step (used by tests and single-shot paths)."""
    registration = upsert_stub(db, row)
    apply_detail(db, registration, detail, mpp_index, minister_index)
    return registration


async def _walk_grid(
    db: Session,
    client: OntarioLobbyRegistryClient,
    *,
    watermark: date | None,
    full: bool,
    max_pages: int | None,
) -> tuple[int, int | None, set[str], bool]:
    """Phase 1: walk the grid newest-amendments-first, upserting stubs.

    Returns (stub_count, registry_total, seen_numbers, walk_completed).
    Incremental walks stop at the first fully-known page; only a COMPLETED
    full walk is allowed to end-date vanished registrations.
    """
    known: dict[str, date | None] = {
        number: amended
        for number, amended in db.execute(
            select(LobbyRegistration.registration_number, LobbyRegistration.last_amendment_date).where(
                LobbyRegistration.jurisdiction_code == "on"
            )
        ).all()
    }

    grid_html = await client.search_active()
    registry_total = parse_total_items(grid_html)
    page_ceiling = (registry_total // 10 + 2) if registry_total else 500
    previous_page_ids: set[str] = set()
    seen: set[str] = set()
    stubs = 0
    walk_completed = False
    page_no = 1
    while True:
        rows = parse_grid_rows(grid_html)
        if not rows:
            walk_completed = True
            break
        page_ids = {row.registration_number for row in rows}
        if page_ids == previous_page_ids:
            walk_completed = True  # pager wrapped: same page twice = the end
            break
        previous_page_ids = page_ids

        fresh = False
        for row in rows:
            if row.registration_number in seen:
                continue
            seen.add(row.registration_number)
            unchanged = (
                row.registration_number in known
                and known[row.registration_number] == row.last_amendment_date
            )
            if not unchanged:
                fresh = True
                upsert_stub(db, row)
                stubs += 1
        db.commit()

        if page_no % 25 == 0:
            logger.info("ontario lobbying: walked %d pages, %d stubs", page_no, stubs)
        newest = max((r.last_amendment_date for r in rows if r.last_amendment_date), default=None)
        if not full and watermark is not None and not fresh and (newest is None or newest <= watermark):
            break
        page_no += 1
        if page_no > page_ceiling or (max_pages is not None and page_no > max_pages):
            break
        try:
            next_html = await client.next_page(grid_html)
        except httpx.HTTPError as exc:
            logger.warning(
                "ontario lobbying: walk stopped at page %d (%s); stubs so far are kept",
                page_no, type(exc).__name__,
            )
            break
        if next_html is None:
            walk_completed = True
            break
        grid_html = next_html
    return stubs, registry_total, seen, walk_completed


async def _fetch_one(
    client: OntarioLobbyRegistryClient, registration: LobbyRegistration
) -> RegistrationDetail | None:
    """One registration's detail via a NARROW search (amendment-date window
    + lobbyist name), which usually returns 1-3 rows.

    Rows sharing an amendment date render in unstable order between
    requests, so identity always comes from the parsed registration number:
    click the index where it's displayed, verify, and retry a couple of
    times on shuffles — with tiny result sets that converges immediately.
    """
    from datetime import timedelta

    if registration.last_amendment_date is None:
        return None
    window_start = registration.last_amendment_date - timedelta(days=1)
    window_end = registration.last_amendment_date + timedelta(days=1)

    for _attempt in range(3):
        grid_html = await client.search_window(
            window_start, window_end, lobbyist=registration.lobbyist_name
        )
        page_budget = 5
        while page_budget:
            rows = parse_grid_rows(grid_html)
            index = next(
                (
                    i
                    for i, r in enumerate(rows)
                    if r.registration_number == registration.registration_number
                ),
                None,
            )
            if index is not None:
                detail = parse_registration_detail(await client.fetch_detail(grid_html, index))
                if detail.registration_number == registration.registration_number:
                    return detail
                break  # shuffled: fresh search, try again
            page_budget -= 1
            next_html = await client.next_page(grid_html)
            if next_html is None:
                break
            grid_html = next_html
    logger.warning(
        "ontario lobbying: could not fetch %s; will retry next sync",
        registration.registration_number,
    )
    return None


async def sync_ontario_lobbying(
    db: Session, *, full: bool = False, max_pages: int | None = None
) -> dict[str, int]:
    """Two-phase sync. Phase 1 (fast): walk the grid, upsert stub rows so
    every registration is listed immediately. Phase 2 (slow, resumable):
    fetch full filings for rows with detail_synced=False — including ones
    left over from interrupted earlier runs.

    Returns counts, including the registry's own total so callers can
    record coverage honestly.
    """
    watermark: date | None = None
    if not full:
        watermark = db.scalar(
            select(func.max(LobbyRegistration.last_amendment_date)).where(
                LobbyRegistration.jurisdiction_code == "on"
            )
        )

    mpp_index = _ontario_mpp_index(db)
    minister_index = _ontario_minister_index(db)

    async with OntarioLobbyRegistryClient() as client:
        stubs, registry_total, seen, walk_completed = await _walk_grid(
            db, client, watermark=watermark, full=full, max_pages=max_pages
        )

        # Only a COMPLETED full walk may end-date vanished registrations —
        # a partial walk hasn't seen everything that's still active.
        ended = 0
        if full and walk_completed and seen:
            stale = db.scalars(
                select(LobbyRegistration).where(
                    LobbyRegistration.jurisdiction_code == "on",
                    LobbyRegistration.status == "active",
                    LobbyRegistration.registration_number.not_in(seen),
                )
            ).all()
            for registration in stale:
                registration.status = "ended"
                ended += 1
            db.commit()

        # Phase 2: every unsynced stub, newest first (also resumes leftovers).
        pending = db.scalars(
            select(LobbyRegistration)
            .where(
                LobbyRegistration.jurisdiction_code == "on",
                LobbyRegistration.detail_synced.is_(False),
                LobbyRegistration.status == "active",
            )
            .order_by(LobbyRegistration.last_amendment_date.desc().nullslast())
        ).all()
        logger.info("ontario lobbying: %d stubs new, %d details pending", stubs, len(pending))

        details = 0
        for registration in pending:
            try:
                detail = await _fetch_one(client, registration)
            except httpx.HTTPError as exc:
                logger.warning(
                    "ontario lobbying: fetch failed for %s (%s); continuing",
                    registration.registration_number,
                    type(exc).__name__,
                )
                continue
            if detail is None:
                continue
            apply_detail(db, registration, detail, mpp_index, minister_index)
            details += 1
            if details % 25 == 0:
                db.commit()
            if details % 100 == 0:
                logger.info("ontario lobbying: %d details synced so far", details)
        db.commit()

    synced_active = db.scalar(
        select(func.count(LobbyRegistration.id)).where(
            LobbyRegistration.jurisdiction_code == "on",
            LobbyRegistration.status == "active",
        )
    ) or 0
    still_pending = db.scalar(
        select(func.count(LobbyRegistration.id)).where(
            LobbyRegistration.jurisdiction_code == "on",
            LobbyRegistration.detail_synced.is_(False),
            LobbyRegistration.status == "active",
        )
    ) or 0
    if registry_total and synced_active != registry_total:
        logger.warning(
            "ontario lobbying: coverage drift — registry says %d active, we hold %d",
            registry_total, synced_active,
        )
    return {
        "stubs": stubs,
        "details": details,
        "ended": ended,
        "registry_total": registry_total or 0,
        "stored_active": int(synced_active),
        "details_pending": int(still_pending),
    }


def backfill_ministry_links(db: Session) -> int:
    """Resolve ministry targets to sitting ministers for registrations that
    were crawled before roles existed (or after a cabinet shuffle)."""
    minister_index = _ontario_minister_index(db)
    if not minister_index:
        return 0
    created = 0
    registrations = db.scalars(
        select(LobbyRegistration).where(LobbyRegistration.target_ministries.is_not(None))
    ).all()
    for registration in registrations:
        linked = {link.person_id for link in registration.mpp_links}
        for target in (registration.target_ministries or "").split("\n"):
            person_id = resolve_ministry_target(target, minister_index)
            if person_id and person_id not in linked:
                linked.add(person_id)
                db.add(
                    LobbyRegistrationMpp(
                        registration_id=registration.id,
                        person_id=person_id,
                        target_kind="ministry",
                    )
                )
                created += 1
    db.commit()
    return created
