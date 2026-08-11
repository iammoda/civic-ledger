"""Committee membership ingestion from ourcommons.ca Members pages.

The pages are server-rendered (desktop cards); we parse names and match
to our Person records. Chair/vice-chair roles aren't in this markup —
memberships land as plain members for now.
"""
from __future__ import annotations

import asyncio
import re

import httpx
from selectolax.parser import HTMLParser
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.ingestion.influence import normalize_person_name
from app.models import Committee, CommitteeMembership, Person

settings = get_settings()

BASE = "https://www.ourcommons.ca"
ACRONYM_RE = re.compile(r"/Committees/en/([A-Z]{3,5})")


def parse_member_names(html: str) -> list[str]:
    """Full names from desktop member cards, deduped in order."""
    tree = HTMLParser(html)
    names: list[str] = []
    seen: set[str] = set()
    for card in tree.css(".committee-member-card.hidden-xs .full-name"):
        first = card.css_first(".first-name")
        last = card.css_first(".last-name")
        if first is None or last is None:
            continue
        full = f"{first.text().strip()} {last.text().strip()}".strip()
        if full and full.lower() not in seen:
            seen.add(full.lower())
            names.append(full)
    return names


def committee_acronym(committee: Committee) -> str | None:
    if not committee.source_url:
        return None
    match = ACRONYM_RE.search(committee.source_url)
    return match.group(1) if match else None


async def sync_committee_memberships(db: Session, *, rate_limit_seconds: float = 0.6) -> int:
    """For each committee with an official source URL, sync current members."""
    headers = {
        "User-Agent": f"Mozilla/5.0 (compatible; {settings.ingestion_user_agent})",
        "Accept-Language": "en-CA,en;q=0.9",
    }
    name_index = {
        normalize_person_name(full_name): person_id
        for person_id, full_name in db.execute(select(Person.id, Person.full_name)).all()
    }

    committees = db.scalars(select(Committee).where(Committee.source_url.is_not(None))).all()
    total = 0
    async with httpx.AsyncClient(headers=headers, timeout=60.0, follow_redirects=True) as client:
        for committee in committees:
            acronym = committee_acronym(committee)
            if acronym is None:
                continue
            try:
                response = await client.get(f"{BASE}/Committees/en/{acronym}/Members")
                response.raise_for_status()
            except httpx.HTTPError:
                continue
            await asyncio.sleep(rate_limit_seconds)

            names = parse_member_names(response.text)
            if not names:
                continue

            current_person_ids: set[int] = set()
            for name in names:
                person_id = name_index.get(normalize_person_name(name))
                if person_id is None:
                    continue
                current_person_ids.add(person_id)
                existing = db.scalar(
                    select(CommitteeMembership).where(
                        CommitteeMembership.committee_id == committee.id,
                        CommitteeMembership.person_id == person_id,
                    )
                )
                if existing is None:
                    db.add(CommitteeMembership(committee_id=committee.id, person_id=person_id))
                    total += 1
                else:
                    existing.is_current = True

            # Members no longer on the page rotate off.
            for membership in db.scalars(
                select(CommitteeMembership).where(
                    CommitteeMembership.committee_id == committee.id,
                    CommitteeMembership.is_current.is_(True),
                )
            ).all():
                if membership.person_id not in current_person_ids:
                    membership.is_current = False
            db.commit()
    return total
