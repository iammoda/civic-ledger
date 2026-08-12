"""Tier-0 bill enrichment — zero AI.

- Official short legislative summaries from LEGISinfo JSON (written by the
  Library of Parliament; always attributed as such)
- Full bill text from parl.ca (already deterministic) stored for full-text
  search, so "protecting the environment" finds bills whose *content*
  matches even when titles don't.
"""
from __future__ import annotations

import asyncio
import re

import httpx
from selectolax.parser import HTMLParser
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.config import get_settings
from app.ingestion.billtext import fetch_bill_text
from app.models import Bill

settings = get_settings()

LEGISINFO_JSON = "https://www.parl.ca/legisinfo/en/bill/{session}/{number}/json"

# The placeholder LEGISinfo shows before the Library writes the summary.
_PLACEHOLDER_RE = re.compile(r"legislative summary is currently being prepared", re.IGNORECASE)


def clean_summary_html(html: str | None) -> str | None:
    if not html:
        return None
    if _PLACEHOLDER_RE.search(html):
        return None
    text = HTMLParser(html).text(separator="\n")
    lines = [line.strip() for line in text.splitlines()]
    cleaned = "\n".join(line for line in lines if line)
    return cleaned or None


async def enrich_bill(db: Session, bill: Bill, client: httpx.AsyncClient, *, rate: float = 0.6) -> bool:
    """Fetch official summary + full text for one bill. True if changed."""
    changed = False

    if bill.official_summary_en is None and bill.session is not None:
        url = LEGISINFO_JSON.format(session=bill.session.label, number=bill.number)
        try:
            response = await client.get(url)
            await asyncio.sleep(rate)
            if response.status_code == 200:
                payload = response.json()
                record = payload[0] if isinstance(payload, list) and payload else None
                if record:
                    summary = clean_summary_html(record.get("ShortLegislativeSummaryEn"))
                    if summary:
                        bill.official_summary_en = summary[:20000]
                        changed = True
        except (httpx.HTTPError, ValueError):
            pass

    if bill.full_text_en is None and bill.text_url:
        text = await fetch_bill_text(db, bill_id=bill.id, text_url=bill.text_url)
        if text:
            bill.full_text_en = text
            changed = True

    return changed


async def enrich_bills(db: Session, *, limit: int = 500) -> dict[str, int]:
    """Enrich bills missing summaries/text, newest first."""
    headers = {"User-Agent": f"Mozilla/5.0 (compatible; {settings.ingestion_user_agent})"}
    bills = db.scalars(
        select(Bill)
        .options(selectinload(Bill.session))
        .where((Bill.official_summary_en.is_(None)) | ((Bill.full_text_en.is_(None)) & (Bill.text_url.is_not(None))))
        .order_by(Bill.id.desc())
        .limit(limit)
    ).all()

    counts = {"checked": 0, "enriched": 0}
    async with httpx.AsyncClient(headers=headers, timeout=60.0, follow_redirects=True) as client:
        for bill in bills:
            counts["checked"] += 1
            if await enrich_bill(db, bill, client):
                counts["enriched"] += 1
            if counts["checked"] % 25 == 0:
                db.commit()
    db.commit()
    return counts
