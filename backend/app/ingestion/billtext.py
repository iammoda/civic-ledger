"""Fetch bill text from parl.ca DocumentViewer — deterministic HTML parse.

Used as LLM *input* only; ingestion itself never calls a model.
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone

import httpx
from selectolax.parser import HTMLParser
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import Document

settings = get_settings()

# Claude input cap for bill text (chars). ~10k tokens — plenty for summaries.
MAX_TEXT_CHARS = 40_000


def extract_text(html: str) -> str:
    tree = HTMLParser(html)
    for selector in ("script", "style", "nav", "header", "footer"):
        for node in tree.css(selector):
            node.decompose()
    root = tree.css_first("#publicationContent") or tree.css_first("main") or tree.body
    if root is None:
        return ""
    text = root.text(separator="\n")
    lines = [line.strip() for line in text.splitlines()]
    return "\n".join(line for line in lines if line)


async def fetch_bill_text(db: Session, *, bill_id: int, text_url: str) -> str | None:
    """Fetch + parse bill text; record a Document provenance row."""
    headers = {"User-Agent": settings.ingestion_user_agent}
    try:
        async with httpx.AsyncClient(headers=headers, timeout=60.0, follow_redirects=True) as client:
            response = await client.get(text_url)
            response.raise_for_status()
    except httpx.HTTPError:
        return None

    text = extract_text(response.text)
    if not text:
        return None

    checksum = hashlib.sha256(text.encode()).hexdigest()
    doc = db.scalar(
        select(Document).where(
            Document.entity_type == "bill",
            Document.entity_id == bill_id,
            Document.document_type == "bill_text",
        )
    )
    if doc is None:
        doc = Document(
            source_system="parl.ca",
            source_url=text_url,
            document_type="bill_text",
            entity_type="bill",
            entity_id=bill_id,
        )
        db.add(doc)
    doc.source_url = text_url
    doc.checksum = checksum
    doc.fetched_at = datetime.now(timezone.utc)
    db.flush()

    return text[:MAX_TEXT_CHARS]
