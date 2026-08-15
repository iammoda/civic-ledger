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
from app.models import Chamber, LobbyRegistration, LobbyRegistrationMpp, Person, PersonMembership

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

    async def search_window(self, start: date, end: date) -> str:
        """Active registrations last amended within [start, end]."""
        return await self._search(
            {
                "ctl00$BodyContent$ucQuickSearch$rdoStatusGroup2": "rdoActiveWithinDates",
                **self._date_fields("FromDate", start.isoformat()),
                **self._date_fields("ToDate", end.isoformat()),
            }
        )

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


def upsert_registration(
    db: Session,
    row: GridRow,
    detail: RegistrationDetail,
    mpp_index: dict[str, int],
) -> LobbyRegistration:
    registration = db.scalar(
        select(LobbyRegistration).where(
            LobbyRegistration.registration_number == row.registration_number
        )
    )
    if registration is None:
        registration = LobbyRegistration(registration_number=row.registration_number)
        db.add(registration)

    registration.jurisdiction_code = "on"
    registration.lobbyist_number = detail.lobbyist_number or row.registration_number.split("-")[0]
    registration.lobbyist_name = detail.lobbyist_name or row.lobbyist_name
    registration.firm_name = detail.firm_name or row.firm_name
    registration.lobbyist_type = row.lobbyist_type
    registration.client_name = detail.client_name or row.client_name
    registration.client_description = detail.client_description
    registration.status = row.status or "active"
    registration.initial_filing_date = detail.initial_filing_date
    registration.last_amendment_date = row.last_amendment_date
    registration.subject_matters = detail.subject_matters
    registration.goals = detail.goals
    registration.target_ministries = "\n".join(detail.target_ministries) or None
    registration.target_mpp_offices = "\n".join(detail.target_mpp_offices) or None
    registration.techniques = detail.techniques
    db.flush()

    # Re-resolve MPP links from scratch (amendments change targets).
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
                    riding_as_filed=riding,
                )
            )
    return registration


async def _collect_rows(
    client: OntarioLobbyRegistryClient,
    *,
    known: dict[str, date | None],
    watermark: date | None,
    full: bool,
    max_pages: int | None,
) -> list[GridRow]:
    """Metadata pass: walk the grid (no clicks), newest amendments first."""
    collected: dict[str, GridRow] = {}
    grid_html = await client.search_active()
    # Hard ceiling from the grid's own item count — the pager's "Next"
    # control still renders on the last page, so without this the walk
    # would loop there forever.
    total_items = parse_total_items(grid_html)
    page_ceiling = (total_items // 10 + 2) if total_items else 500
    previous_page_ids: set[str] = set()
    page_no = 1
    while True:
        rows = parse_grid_rows(grid_html)
        if not rows:
            break
        page_ids = {row.registration_number for row in rows}
        if page_ids == previous_page_ids:
            break  # pager wrapped: same page twice = we're at the end
        previous_page_ids = page_ids
        fresh = [
            row
            for row in rows
            if row.registration_number not in collected
            and not (
                row.registration_number in known
                and known[row.registration_number] == row.last_amendment_date
            )
        ]
        for row in fresh:
            collected[row.registration_number] = row
        if page_no % 25 == 0:
            logger.info("ontario lobbying: walked %d pages, %d to fetch", page_no, len(collected))
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
                "ontario lobbying: page walk stopped at page %d (%s); syncing what we have",
                page_no, type(exc).__name__,
            )
            break
        if next_html is None:
            break
        grid_html = next_html
    return list(collected.values())


async def _harvest_window(
    client: OntarioLobbyRegistryClient,
    window_date: date,
    remaining: dict[str, GridRow],
) -> list[tuple[GridRow, RegistrationDetail]]:
    """Fetch details for the still-wanted registrations amended around a date.

    Two registry quirks shape this (both verified empirically):
    - the date-range filter is edge-exclusive, so search date ± 1 day;
    - only the FIRST row-click after a fresh render chain returns a
      trustworthy detail, and the server-side row order behind
      RowClick;<i> does not match the displayed order.

    So: for every index i in the window, run a fresh search chain (search,
    page to i's page, click i once), parse whatever registration comes
    back, and keep it if it's one we want. Identity always comes from the
    parsed registration number — never from grid position.
    """
    from datetime import timedelta

    window_start = window_date - timedelta(days=1)
    window_end = window_date + timedelta(days=1)

    wanted_here = {
        number
        for number, row in remaining.items()
        if row.last_amendment_date and window_start <= row.last_amendment_date <= window_end
    }
    if not wanted_here:
        return []

    first_page = await client.search_window(window_start, window_end)
    total = parse_total_items(first_page) or len(parse_grid_rows(first_page))

    harvested: list[tuple[GridRow, RegistrationDetail]] = []
    for index in range(total):
        if not wanted_here:
            break
        page_no, row_in_page = divmod(index, 10)
        grid_html = first_page if index == 0 else await client.search_window(window_start, window_end)
        for _ in range(page_no):
            next_html = await client.next_page(grid_html)
            if next_html is None:
                grid_html = None
                break
            grid_html = next_html
        if grid_html is None:
            continue
        try:
            detail_html = await client.fetch_detail(grid_html, row_in_page)
            detail = parse_registration_detail(detail_html)
        except (httpx.HTTPError, ValueError) as exc:
            logger.warning(
                "ontario lobbying: window %s index %d failed (%s); continuing",
                window_date, index, type(exc).__name__,
            )
            continue
        number = detail.registration_number
        if number in wanted_here:
            harvested.append((remaining[number], detail))
            wanted_here.discard(number)
            del remaining[number]
    for number in wanted_here:
        logger.warning("ontario lobbying: could not harvest %s; will retry next sync", number)
    return harvested


async def sync_ontario_lobbying(
    db: Session, *, full: bool = False, max_pages: int | None = None
) -> int:
    """Sync Ontario lobbyist registrations. Incremental by default: only
    rows amended since the newest amendment already stored are fetched.
    `full=True` re-walks the whole registry (~4k details, politely slow)."""
    watermark: date | None = None
    if not full:
        watermark = db.scalar(select(func.max(LobbyRegistration.last_amendment_date)))

    known: dict[str, date | None] = {
        number: amended
        for number, amended in db.execute(
            select(LobbyRegistration.registration_number, LobbyRegistration.last_amendment_date)
        ).all()
    }
    mpp_index = _ontario_mpp_index(db)

    count = 0
    async with OntarioLobbyRegistryClient() as client:
        rows = await _collect_rows(
            client, known=known, watermark=watermark, full=full, max_pages=max_pages
        )
        logger.info("ontario lobbying: %d registrations to fetch", len(rows))
        remaining = {
            row.registration_number: row for row in rows if row.last_amendment_date is not None
        }
        for window_date in sorted(
            {row.last_amendment_date for row in remaining.values()}, reverse=True
        ):
            if not any(
                row.last_amendment_date == window_date for row in remaining.values()
            ):
                continue  # already harvested via an adjacent window
            try:
                harvested = await _harvest_window(client, window_date, remaining)
            except httpx.HTTPError as exc:
                logger.warning(
                    "ontario lobbying: window %s failed (%s); continuing",
                    window_date,
                    type(exc).__name__,
                )
                continue
            for row, detail in harvested:
                upsert_registration(db, row, detail, mpp_index)
                count += 1
            db.commit()
            if count and count % 100 < len(harvested):
                logger.info("ontario lobbying: %d registrations synced so far", count)

    db.commit()
    return count
