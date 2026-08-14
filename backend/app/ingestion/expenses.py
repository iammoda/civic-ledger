"""MP expense ingestion — House of Commons Proactive Disclosure.

Three layers, all deterministic HTML/CSV parsing (no LLM anywhere):
1. Quarter discovery from the members index page nav
2. Quarterly summary CSV (per-MP category totals)
3. Per-MP detail pages: contract / hospitality / travel line items

Detail pages are nested-table HTML; parsers are structure-tolerant and
fixture-tested against captured real pages.
"""
from __future__ import annotations

import asyncio
import hashlib
import re
from datetime import date, datetime
from typing import Any

import httpx
from selectolax.parser import HTMLParser, Node
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.ingestion.influence import get_or_create_org, normalize_person_name
from app.models import ExpenseItem, ExpenseSummary

settings = get_settings()

BASE = "https://www.ourcommons.ca"
MEMBERS_INDEX = f"{BASE}/ProactiveDisclosure/en/members"

CLAIM_RE = re.compile(r"^[A-Z]{0,2}\d{5,}$")
MONEY_RE = re.compile(r"-?\$[\d,]+(?:\.\d{2})?")
TRAVELLER_TYPES = {"member", "employee", "designated traveller", "dependant", "house officer"}


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("\u2013", "-")).strip()


def parse_money(text: str) -> float | None:
    match = MONEY_RE.search(text.replace(" ", ""))
    if not match:
        return None
    try:
        return float(match.group(0).replace("$", "").replace(",", ""))
    except ValueError:
        return None


def parse_date_any(text: str) -> date | None:
    text = _clean(text)
    # "From 2024-03-17 to 2024-05-17" -> start date
    range_match = re.search(r"(\d{4}-\d{2}-\d{2})", text)
    if range_match:
        try:
            return datetime.strptime(range_match.group(1), "%Y-%m-%d").date()
        except ValueError:
            return None
    return None


# ---------------------------------------------------------------------------
# Quarter discovery + summary CSV
# ---------------------------------------------------------------------------

def discover_quarters(index_html: str) -> list[tuple[int, int]]:
    """(fiscal_year, quarter) pairs available in the nav, newest first."""
    pairs = {
        (int(y), int(q))
        for y, q in re.findall(r"/ProactiveDisclosure/en/members/(20\d\d)/([1-4])", index_html)
    }
    return sorted(pairs, reverse=True)


def find_summary_csv_path(quarter_html: str) -> str | None:
    match = re.search(r'href="(/ProactiveDisclosure/en/members/[0-9a-f-]{36}/csv)"', quarter_html)
    return match.group(1) if match else None


def parse_summary_csv(text: str) -> list[dict[str, Any]]:
    import csv
    import io

    text = text.lstrip("\ufeff")  # ourcommons CSVs ship with a UTF-8 BOM
    rows = []
    for row in csv.DictReader(io.StringIO(text)):
        name = (row.get("Name") or "").strip()
        if not name or name.lower() == "vacant":
            continue

        def money(key: str) -> float:
            raw = (row.get(key) or "0").replace("$", "").replace(",", "").strip()
            try:
                return float(raw)
            except ValueError:
                return 0.0

        rows.append(
            {
                "mp_name_raw": name,
                "constituency": (row.get("Constituency") or "").strip() or None,
                "caucus": (row.get("Caucus") or "").strip() or None,
                "salaries": money("Salaries"),
                "travel": money("Travel"),
                "hospitality": money("Hospitality"),
                "contracts": money("Contracts"),
            }
        )
    return rows


# ---------------------------------------------------------------------------
# Quarter page: per-MP detail links
# ---------------------------------------------------------------------------

def parse_member_rows(quarter_html: str) -> list[dict[str, Any]]:
    """Member rows with name/constituency/caucus + detail-page member uuid."""
    tree = HTMLParser(quarter_html)
    members = []
    for tr in tree.css("tr.expenses-main-info"):
        cells = tr.css("td")
        if len(cells) < 4:
            continue
        name = _clean(cells[0].text())
        if not name or name.lower() == "vacant":
            continue
        uuid_match = None
        categories: dict[str, str] = {}
        for link in tr.css("a"):
            href = link.attributes.get("href") or ""
            match = re.search(
                r"/members/(travel|hospitality|contract)/(20\d\d)/([1-4])/([0-9a-f-]{36})", href
            )
            if match:
                categories[match.group(1)] = href
                uuid_match = match.group(4)
        members.append(
            {
                "mp_name_raw": name,
                "constituency": _clean(cells[1].text()) or None,
                "caucus": _clean(cells[2].text()) or None,
                "member_uuid": uuid_match,
                "detail_paths": categories,  # only categories with spend > 0
            }
        )
    return members


# ---------------------------------------------------------------------------
# Detail parsers (contract / hospitality / travel)
# ---------------------------------------------------------------------------

def _cell_texts(tr: Node) -> list[str]:
    return [_clean(td.text(separator=" ")) for td in tr.css("td")]


def parse_contract_detail(html: str) -> list[dict[str, Any]]:
    """Rows: Supplier, Description, Date, Total."""
    tree = HTMLParser(html)
    items = []
    for tr in tree.css("tr.expenses-main-info"):
        cells = _cell_texts(tr)
        if len(cells) < 4:
            continue
        amount = parse_money(cells[3])
        if amount is None:
            continue
        items.append(
            {
                "supplier": cells[0] or None,
                "description": cells[1] or None,
                "occurred_on": parse_date_any(cells[2]),
                "amount": amount,
            }
        )
    return items


def parse_hospitality_detail(html: str) -> list[dict[str, Any]]:
    """Event rows (date, location, attendees, purpose, total) followed by
    claim/supplier sub-rows. Sub-rows become the items (searchable
    suppliers), inheriting event context; events without sub-rows are
    emitted directly."""
    tree = HTMLParser(html)
    items: list[dict[str, Any]] = []
    current_event: dict[str, Any] | None = None
    event_had_subitems = False

    def flush_event() -> None:
        nonlocal current_event, event_had_subitems
        if current_event is not None and not event_had_subitems:
            items.append(dict(current_event))
        current_event = None
        event_had_subitems = False

    for tr in tree.css("tr"):
        classes = tr.attributes.get("class") or ""
        if "hidden" in classes:
            continue  # Mobile duplicate of the sub-table.
        cells = _cell_texts(tr)
        if not cells:
            continue

        if "expenses-main-info" in classes and len(cells) >= 5:
            flush_event()
            current_event = {
                "occurred_on": parse_date_any(cells[0]),
                "city": cells[1] or None,
                "description": f"Hospitality: {cells[3]}" if cells[3] else "Hospitality",
                "purpose": cells[3] or None,
                "amount": parse_money(cells[4]) or 0.0,
                "supplier": None,
            }
            continue

        # Claim sub-row: [claim_ref, supplier, amount]
        if current_event is not None and len(cells) == 3 and CLAIM_RE.match(cells[0] or ""):
            amount = parse_money(cells[2])
            if amount is None:
                continue
            items.append(
                {
                    **{k: current_event[k] for k in ("occurred_on", "city", "purpose", "description")},
                    "supplier": cells[1] or None,
                    "claim_ref": cells[0],
                    "amount": amount,
                }
            )
            event_had_subitems = True

    flush_event()
    return items


def parse_travel_detail(html: str) -> list[dict[str, Any]]:
    """Claim rows: [Claim#, date range, transport, accommodation, meals,
    points..., Total]; each followed by a nested traveller table whose first
    row provides traveller/purpose/destination context."""
    tree = HTMLParser(html)
    items: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None

    for tr in tree.css("tr"):
        classes = tr.attributes.get("class") or ""
        if "hidden" in classes:
            continue
        cells = _cell_texts(tr)
        if not cells:
            continue

        if CLAIM_RE.match(cells[0] or "") and len(cells) >= 5:
            money_cells = [parse_money(c) for c in cells[1:]]
            amounts = [m for m in money_cells if m is not None]
            if not amounts:
                continue
            current = {
                "claim_ref": cells[0],
                "occurred_on": parse_date_any(cells[1]),
                "amount": amounts[-1],  # Last $ column is the claim total.
                "description": "Travel claim",
                "supplier": None,
                "traveller_name": None,
                "traveller_type": None,
                "purpose": None,
                "city": None,
            }
            items.append(current)
            continue

        # First traveller row after a claim: [name, type, purpose, date/city, from, to]
        if (
            current is not None
            and current["traveller_name"] is None
            and len(cells) >= 4
            and (cells[1] or "").lower() in TRAVELLER_TYPES
        ):
            current["traveller_name"] = cells[0] or None
            current["traveller_type"] = cells[1] or None
            current["purpose"] = cells[2] or None
            current["city"] = cells[-1] or None
            if current["description"] == "Travel claim" and cells[2]:
                current["description"] = f"Travel: {cells[2]}"

    return items


# ---------------------------------------------------------------------------
# Client + sync
# ---------------------------------------------------------------------------

class ExpensesClient:
    def __init__(self, rate_limit_seconds: float = 0.6) -> None:
        self._rate = rate_limit_seconds
        # ourcommons' WAF intermittently serves an interstitial to
        # non-browser UAs; identify honestly but with a browser prefix.
        self._headers = {
            "User-Agent": f"Mozilla/5.0 (compatible; {settings.ingestion_user_agent})",
            "Accept": "text/html,application/xhtml+xml,text/csv;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-CA,en;q=0.9",
        }
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> "ExpensesClient":
        self._client = httpx.AsyncClient(
            base_url=BASE, headers=self._headers, timeout=60.0, follow_redirects=True
        )
        return self

    async def __aexit__(self, *exc: object) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def get_text(self, path: str) -> str | None:
        assert self._client is not None
        try:
            response = await self._client.get(path)
            response.raise_for_status()
        except httpx.HTTPError:
            return None
        await asyncio.sleep(self._rate)
        return response.text


def _match_person_id(db: Session, name_index: dict[str, int], mp_name_raw: str) -> int | None:
    return name_index.get(normalize_person_name(mp_name_raw))


def _item_fingerprint(mp_name_raw: str, fiscal_year: int, quarter: int, category: str, item: dict[str, Any], seq: int) -> str:
    raw = "|".join(
        str(v)
        for v in (
            mp_name_raw, fiscal_year, quarter, category,
            item.get("supplier"), item.get("description"), item.get("occurred_on"),
            item.get("amount"), item.get("claim_ref"), item.get("traveller_name"), seq,
        )
    )
    return hashlib.sha256(raw.encode()).hexdigest()


async def sync_quarter(
    db: Session,
    client: ExpensesClient,
    *,
    fiscal_year: int,
    quarter: int,
    fetch_details: bool = True,
    max_members: int | None = None,
) -> dict[str, int]:
    """Sync one quarter: summary rows + (optionally) all detail line items."""
    from app.ingestion.influence import build_person_name_index

    quarter_path = f"/ProactiveDisclosure/en/members/{fiscal_year}/{quarter}"
    quarter_html = await client.get_text(quarter_path)
    if quarter_html is None:
        raise RuntimeError(f"Quarter page unavailable: {quarter_path}")

    name_index = build_person_name_index(db)
    counts = {"summaries": 0, "items": 0}

    # 1. Summary CSV (authoritative totals). The WAF sometimes serves an
    # HTML interstitial instead of CSV — validate and retry.
    csv_path = find_summary_csv_path(quarter_html)
    if csv_path:
        for attempt in range(3):
            csv_text = await client.get_text(csv_path)
            if csv_text and "Name" in csv_text.splitlines()[0]:
                break
            await asyncio.sleep(2.0 * (attempt + 1))
            csv_text = None
        if csv_text:
            # The source occasionally lists an MP twice (e.g. riding change
            # mid-quarter) — merge rows by name, summing the amounts.
            merged: dict[str, dict[str, Any]] = {}
            for row in parse_summary_csv(csv_text):
                slot = merged.get(row["mp_name_raw"])
                if slot is None:
                    merged[row["mp_name_raw"]] = dict(row)
                else:
                    for key in ("salaries", "travel", "hospitality", "contracts"):
                        slot[key] += row[key]
            for row in merged.values():
                existing = db.scalar(
                    select(ExpenseSummary).where(
                        ExpenseSummary.mp_name_raw == row["mp_name_raw"],
                        ExpenseSummary.fiscal_year == fiscal_year,
                        ExpenseSummary.quarter == quarter,
                    )
                )
                if existing is None:
                    existing = ExpenseSummary(
                        mp_name_raw=row["mp_name_raw"], fiscal_year=fiscal_year, quarter=quarter
                    )
                    db.add(existing)
                existing.constituency = row["constituency"]
                existing.caucus = row["caucus"]
                existing.salaries = row["salaries"]
                existing.travel = row["travel"]
                existing.hospitality = row["hospitality"]
                existing.contracts = row["contracts"]
                existing.person_id = _match_person_id(db, name_index, row["mp_name_raw"])
                existing.source_url = f"{BASE}{quarter_path}"
                counts["summaries"] += 1
            db.commit()

    if not fetch_details:
        return counts

    # 2. Detail line items per member per category.
    parsers = {
        "contract": parse_contract_detail,
        "hospitality": parse_hospitality_detail,
        "travel": parse_travel_detail,
    }
    members = parse_member_rows(quarter_html)
    if max_members is not None:
        members = members[:max_members]

    for member in members:
        person_id = _match_person_id(db, name_index, member["mp_name_raw"])
        for category, path in member["detail_paths"].items():
            # Skip if this member/category/quarter is already ingested.
            already = db.scalar(
                select(ExpenseItem.id)
                .where(
                    ExpenseItem.mp_name_raw == member["mp_name_raw"],
                    ExpenseItem.fiscal_year == fiscal_year,
                    ExpenseItem.quarter == quarter,
                    ExpenseItem.category == category,
                )
                .limit(1)
            )
            if already is not None:
                continue

            detail_html = await client.get_text(path)
            if detail_html is None:
                continue
            items = parsers[category](detail_html)
            for seq, item in enumerate(items):
                fingerprint = _item_fingerprint(
                    member["mp_name_raw"], fiscal_year, quarter, category, item, seq
                )
                if db.scalar(select(ExpenseItem.id).where(ExpenseItem.fingerprint == fingerprint)):
                    continue
                org = get_or_create_org(db, item.get("supplier") or "")
                db.add(
                    ExpenseItem(
                        person_id=person_id,
                        mp_name_raw=member["mp_name_raw"],
                        category=category,
                        fiscal_year=fiscal_year,
                        quarter=quarter,
                        supplier=(item.get("supplier") or None),
                        organization_id=org.id if org else None,
                        description=item.get("description"),
                        occurred_on=item.get("occurred_on"),
                        amount=item.get("amount") or 0.0,
                        traveller_name=item.get("traveller_name"),
                        traveller_type=item.get("traveller_type"),
                        purpose=item.get("purpose"),
                        city=item.get("city"),
                        claim_ref=item.get("claim_ref"),
                        source_url=f"{BASE}{path}",
                        fingerprint=fingerprint,
                    )
                )
                counts["items"] += 1
        db.commit()

    return counts


async def sync_expenses(
    db: Session,
    client: ExpensesClient,
    *,
    quarters: list[tuple[int, int]] | None = None,
    fetch_details: bool = True,
) -> dict[str, int]:
    """Sync the given quarters (default: newest quarter only)."""
    if quarters is None:
        # The WAF occasionally serves an interstitial on the first hit;
        # retry discovery a few times before giving up.
        discovered: list[tuple[int, int]] = []
        for attempt in range(4):
            index_html = await client.get_text("/ProactiveDisclosure/en/members")
            if index_html:
                discovered = discover_quarters(index_html)
                if discovered:
                    break
            await asyncio.sleep(2.0 * (attempt + 1))
        if not discovered:
            raise RuntimeError("No quarters discovered (index unavailable after retries)")
        quarters = discovered[:1]

    totals = {"summaries": 0, "items": 0}
    for fiscal_year, quarter in quarters:
        counts = await sync_quarter(
            db, client, fiscal_year=fiscal_year, quarter=quarter, fetch_details=fetch_details
        )
        totals["summaries"] += counts["summaries"]
        totals["items"] += counts["items"]
    return totals
