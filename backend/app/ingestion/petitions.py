"""House of Commons e-petitions ingestion.

Source: petitions.ourcommons.ca SearchAsync (JSON envelope containing a
server-rendered HTML fragment) — parsed deterministically with selectolax.
Petition text comes from the public Details page (.pet-prayer).
No LLM anywhere in ingestion.
"""
from __future__ import annotations

import asyncio
import re
from datetime import date, datetime
from typing import Any

import httpx
from selectolax.parser import HTMLParser
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import Person, Petition

settings = get_settings()

BASE = "https://www.ourcommons.ca"
SEARCH_ASYNC = f"{BASE}/petitions/en/Petition/SearchAsync"
DETAIL_URL = f"{BASE}/petitions/en/Petition/Details?Petition={{number}}"

_UNTIL_RE = re.compile(r"until\s+([A-Z][a-z]+ \d{1,2}, \d{4})")


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def parse_deadline(status_text: str) -> date | None:
    match = _UNTIL_RE.search(status_text)
    if not match:
        return None
    try:
        return datetime.strptime(match.group(1), "%B %d, %Y").date()
    except ValueError:
        return None


def parse_search_rows(html: str) -> list[dict[str, Any]]:
    """Parse petition rows out of the SearchAsync HTML fragment."""
    tree = HTMLParser(html)
    rows: list[dict[str, Any]] = []
    for tr in tree.css("tr.Pub"):
        cells = tr.css("td")
        if len(cells) < 6:
            continue
        link = cells[0].css_first("a.publicationTitleSearch")
        number_node = cells[0].css_first("span.spTitle")
        if link is None or number_node is None:
            continue
        number = _clean(number_node.text())
        spans = cells[0].css("span")
        title = _clean(spans[1].text()) if len(spans) > 1 else ""

        keywords: list[str] = []
        for kw in cells[1].css("a.index"):
            full = (kw.attributes.get("title") or "").strip()
            keywords.append(_clean(full or kw.text()))

        status_text = _clean(cells[3].text())
        sponsor = _clean(cells[4].text())
        signatures_text = _clean(cells[5].text()).replace(",", "")
        signatures = int(signatures_text) if signatures_text.isdigit() else 0

        rows.append(
            {
                "number": number,
                "title": title,
                "keywords": keywords,
                "status_text": status_text,
                "state": "open" if "open for signature" in status_text.lower() else "closed",
                "closes_at": parse_deadline(status_text),
                "sponsor_name": sponsor or None,
                "signature_count": signatures,
            }
        )
    return rows


def parse_petition_text(html: str) -> str | None:
    """Extract the petition prayer text from a Details page."""
    tree = HTMLParser(html)
    node = tree.css_first(".pet-details-text") or tree.css_first(".pet-prayer")
    if node is None:
        return None
    text = node.text(separator="\n")
    lines = [line.strip() for line in text.splitlines()]
    cleaned = "\n".join(line for line in lines if line)
    return cleaned or None


class PetitionsClient:
    def __init__(self, rate_limit_seconds: float = 0.6) -> None:
        self._rate_limit_seconds = rate_limit_seconds
        self._headers = {"User-Agent": settings.ingestion_user_agent}
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> "PetitionsClient":
        self._client = httpx.AsyncClient(headers=self._headers, timeout=30.0, follow_redirects=True)
        return self

    async def __aexit__(self, *exc: object) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def fetch_search_page(self, *, category: str, page: int) -> str:
        assert self._client is not None
        response = await self._client.post(
            SEARCH_ASYNC,
            params={"Category": category, "order": "Recent", "Page": page, "RPP": 20},
        )
        response.raise_for_status()
        await asyncio.sleep(self._rate_limit_seconds)
        return response.json().get("html") or ""

    async def fetch_detail_html(self, number: str) -> str | None:
        assert self._client is not None
        try:
            response = await self._client.get(DETAIL_URL.format(number=number))
            response.raise_for_status()
        except httpx.HTTPError:
            return None
        await asyncio.sleep(self._rate_limit_seconds)
        return response.text


def _match_sponsor(db: Session, name: str | None) -> int | None:
    if not name:
        return None
    person = db.scalar(select(Person).where(func.lower(Person.full_name) == name.lower()))
    return person.id if person else None


def upsert_petition_row(db: Session, row: dict[str, Any]) -> tuple[Petition, bool]:
    """Upsert one parsed row. Returns (petition, was_known_and_unchanged)."""
    petition = db.scalar(select(Petition).where(Petition.number == row["number"]))
    unchanged = (
        petition is not None
        and petition.signature_count == row["signature_count"]
        and petition.state == row["state"]
    )
    if petition is None:
        petition = Petition(
            number=row["number"],
            title_en=row["title"] or row["number"],
            source_url=DETAIL_URL.format(number=row["number"]),
        )
        db.add(petition)
    petition.title_en = row["title"] or petition.title_en
    petition.status_en = row["status_text"]
    petition.state = row["state"]
    petition.closes_at = row["closes_at"]
    petition.signature_count = row["signature_count"]
    petition.keywords_en = ", ".join(row["keywords"]) or None
    petition.sponsor_name = row["sponsor_name"]
    petition.sponsor_person_id = _match_sponsor(db, row["sponsor_name"])
    db.flush()
    return petition, unchanged


async def sync_petitions(
    db: Session,
    client: PetitionsClient,
    *,
    max_pages: int = 10,
    fetch_texts: int = 25,
) -> int:
    """Sync open petitions fully + recent pages of everything; fetch prayer
    text for petitions that lack it (rate-limited batch per run)."""
    count = 0

    # Open petitions: signatures/deadlines change; sweep all pages.
    page = 1
    while True:
        html = await client.fetch_search_page(category="Open", page=page)
        rows = parse_search_rows(html)
        if not rows:
            break
        for row in rows:
            upsert_petition_row(db, row)
            count += 1
        db.commit()
        page += 1
        if page > 100:  # Safety bound; ~200 open petitions typical.
            break

    # Recent overall pages: catches newly closed/presented petitions.
    consecutive_known = 0
    for page in range(1, max_pages + 1):
        html = await client.fetch_search_page(category="All", page=page)
        rows = parse_search_rows(html)
        if not rows:
            break
        page_all_known = True
        for row in rows:
            _, unchanged = upsert_petition_row(db, row)
            if not unchanged:
                page_all_known = False
            count += 1
        db.commit()
        consecutive_known = consecutive_known + 1 if page_all_known else 0
        if consecutive_known >= 2:
            break  # Deep into already-synced territory.

    # Prayer texts for petitions that lack them (used for topics/embeddings).
    missing = db.scalars(
        select(Petition).where(Petition.text_en.is_(None)).order_by(Petition.id.desc()).limit(fetch_texts)
    ).all()
    for petition in missing:
        detail_html = await client.fetch_detail_html(petition.number)
        if detail_html:
            petition.text_en = parse_petition_text(detail_html)
    db.commit()
    return count
