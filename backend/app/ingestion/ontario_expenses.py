"""Ontario MPP expense disclosures, from ola.org.

The Legislative Assembly publishes each MPP's expenses as a per-member CSV
(travel / accommodation / meals / hospitality, with purpose and location)
linked from /en/members/expense-disclosure/<slug>. Server-rendered pages,
clean CSVs — no PDFs, no JavaScript.

Pipeline (all deterministic):
1. /en/members/current -> the ~124 sitting members' ola.org slugs.
2. Each member's expense-disclosure page -> their CSV URL + the
   "Expenses paid to LAST, First - (Riding)" line for person matching.
3. CSV rows -> expense_items with scope="on-mpp" (kept out of the federal
   explorer by default), fingerprint-deduped so re-runs are no-ops.
"""
from __future__ import annotations

import asyncio
import csv
import hashlib
import io
import logging
import re
from dataclasses import dataclass
from datetime import date, datetime

import httpx
from selectolax.parser import HTMLParser
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import Chamber, ExpenseItem, Person, PersonMembership

logger = logging.getLogger(__name__)

BASE_URL = "https://www.ola.org"
REQUEST_DELAY_SECONDS = 0.5

# CSV amount columns -> our category values.
CATEGORY_COLUMNS = {
    "Travel ($)": "travel",
    "Accommodation ($)": "accommodation",
    "Meals ($)": "meals",
    "Hospitality / Events ($)": "hospitality",
}


@dataclass(slots=True)
class MemberDisclosure:
    ola_slug: str
    csv_url: str | None
    display_name: str | None  # "Anand, Deepak"
    riding: str | None  # "Mississauga—Malton"


@dataclass(slots=True)
class ExpenseRow:
    incurred_from: date | None
    incurred_to: date | None
    category: str
    amount: float
    purpose: str | None
    location: str | None


def parse_member_slugs(html: str) -> list[str]:
    """ola.org slugs of every current MPP, from /en/members/current."""
    slugs = re.findall(r'href="/en/members/all/([a-z0-9-]+)"', html)
    return list(dict.fromkeys(slugs))


def parse_disclosure_page(html: str, ola_slug: str) -> MemberDisclosure:
    tree = HTMLParser(html)
    csv_url = None
    for node in tree.css("a[href]"):
        href = node.attributes.get("href") or ""
        if "/expense-disclosure/" in href and href.endswith(".csv"):
            csv_url = href if href.startswith("http") else BASE_URL + href
            break
    display_name = riding = None
    m = re.search(r"Expenses paid to\s+([^(<]+?)\s*-\s*\(([^)<]+)\)", tree.body.text() if tree.body else "")
    if m:
        display_name = m.group(1).strip()
        riding = m.group(2).strip()
    return MemberDisclosure(ola_slug=ola_slug, csv_url=csv_url, display_name=display_name, riding=riding)


def _parse_amount(raw: str) -> float:
    raw = (raw or "").replace(",", "").replace("$", "").strip()
    if not raw:
        return 0.0
    try:
        return float(raw)
    except ValueError:
        return 0.0


def _parse_date(raw: str) -> date | None:
    raw = (raw or "").strip()
    for fmt in ("%Y-%m-%d", "%B %d, %Y"):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    return None


def parse_expense_csv(text: str) -> list[ExpenseRow]:
    """One row per (line, non-zero category column) — a line billing both
    travel and meals becomes two categorized rows, like the federal data."""
    rows: list[ExpenseRow] = []
    reader = csv.DictReader(io.StringIO(text))
    for line in reader:
        incurred_from = _parse_date(line.get("Date Incurred From", ""))
        incurred_to = _parse_date(line.get("Date Incurred To", ""))
        purpose = (line.get("Purpose of Expense") or "").strip() or None
        location = (line.get("Location") or "").strip() or None
        for column, category in CATEGORY_COLUMNS.items():
            amount = _parse_amount(line.get(column, ""))
            if amount == 0.0:
                continue  # includes credits netting to zero; category not used
            rows.append(
                ExpenseRow(
                    incurred_from=incurred_from,
                    incurred_to=incurred_to,
                    category=category,
                    amount=amount,
                    purpose=purpose,
                    location=location,
                )
            )
    return rows


def _fingerprint(ola_slug: str, row: ExpenseRow) -> str:
    raw = "|".join(
        str(part)
        for part in (
            "on-mpp", ola_slug, row.incurred_from, row.incurred_to,
            row.category, f"{row.amount:.2f}", row.purpose, row.location,
        )
    )
    return hashlib.sha256(raw.encode()).hexdigest()


def _quarter(d: date) -> tuple[int, int]:
    """Ontario disclosures use calendar quarters."""
    return d.year, (d.month - 1) // 3 + 1


def _ontario_mpp_index(db: Session) -> dict[str, int]:
    rows = db.execute(
        select(PersonMembership.riding_name, PersonMembership.person_id)
        .join(Person, PersonMembership.person_id == Person.id)
        .join(Chamber, Person.chamber_id == Chamber.id)
        .where(Chamber.slug == "on-assembly", PersonMembership.is_current.is_(True))
    ).all()
    return {riding.lower(): person_id for riding, person_id in rows if riding}


def persist_member_expenses(
    db: Session,
    disclosure: MemberDisclosure,
    rows: list[ExpenseRow],
    mpp_index: dict[str, int],
    existing_fingerprints: set[str],
) -> int:
    person_id = mpp_index.get((disclosure.riding or "").lower())
    name = disclosure.display_name or disclosure.ola_slug
    count = 0
    for row in rows:
        fingerprint = _fingerprint(disclosure.ola_slug, row)
        if fingerprint in existing_fingerprints:
            continue
        existing_fingerprints.add(fingerprint)
        occurred = row.incurred_from or row.incurred_to
        fiscal_year, quarter = _quarter(occurred) if occurred else (0, 0)
        db.add(
            ExpenseItem(
                person_id=person_id,
                mp_name_raw=name,
                category=row.category,
                scope="on-mpp",
                fiscal_year=fiscal_year,
                quarter=quarter,
                occurred_on=occurred,
                description=row.purpose,
                purpose=row.purpose,
                city=row.location,
                amount=row.amount,
                source_url=disclosure.csv_url or f"{BASE_URL}/en/members/expense-disclosure/{disclosure.ola_slug}",
                fingerprint=fingerprint,
            )
        )
        count += 1
    return count


async def sync_ontario_expenses(db: Session) -> int:
    """Every sitting MPP's expense CSV -> expense_items (scope on-mpp)."""
    headers = {"User-Agent": get_settings().ingestion_user_agent}
    mpp_index = _ontario_mpp_index(db)
    existing = {
        fp
        for (fp,) in db.execute(
            select(ExpenseItem.fingerprint).where(ExpenseItem.scope == "on-mpp")
        ).all()
    }

    async def get_with_retries(client: httpx.AsyncClient, url: str) -> httpx.Response:
        last_exc: Exception | None = None
        for attempt in range(3):
            try:
                response = await client.get(url)
                await asyncio.sleep(REQUEST_DELAY_SECONDS)
                return response
            except httpx.TransportError as exc:
                last_exc = exc
                await asyncio.sleep(2.0 * (attempt + 1))
        assert last_exc is not None
        raise last_exc

    count = 0
    async with httpx.AsyncClient(headers=headers, timeout=60.0, follow_redirects=True) as client:
        members_page = await get_with_retries(client, BASE_URL + "/en/members/current")
        members_page.raise_for_status()
        slugs = parse_member_slugs(members_page.text)
        logger.info("ontario expenses: %d sitting MPPs", len(slugs))

        for ola_slug in slugs:
            try:
                page = await get_with_retries(client, f"{BASE_URL}/en/members/expense-disclosure/{ola_slug}")
                if page.status_code == 404:
                    continue  # no disclosure page (e.g. brand-new member)
                page.raise_for_status()
                disclosure = parse_disclosure_page(page.text, ola_slug)
                if not disclosure.csv_url:
                    logger.warning("ontario expenses: no CSV link for %s", ola_slug)
                    continue
                csv_response = await get_with_retries(client, disclosure.csv_url)
                csv_response.raise_for_status()
                rows = parse_expense_csv(csv_response.text)
                count += persist_member_expenses(db, disclosure, rows, mpp_index, existing)
                db.commit()
            except httpx.HTTPError as exc:
                # One member must not sink the run.
                logger.warning(
                    "ontario expenses: %s failed (%s); continuing", ola_slug, type(exc).__name__
                )
                db.rollback()
    db.commit()
    return count
