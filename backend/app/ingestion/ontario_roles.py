"""Ontario MPP roles (Premier, ministers, PAs, House officers), from ola.org.

Each member page carries a "Current roles" block. Weekly sync turns those
into PersonRole rows — the same shape the federal ministry sync writes —
which unlocks minister badges, an Ontario cabinet view, and resolving
lobbying-registration ministry targets to the actual minister.

Deterministic parsing only — no LLM anywhere in ingestion.
"""
from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass
from datetime import date

import httpx
from selectolax.parser import HTMLParser
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.ingestion.ministry import portfolio_topic_slug
from app.ingestion.ontario_expenses import _ontario_mpp_index, parse_member_slugs
from app.models import Chamber, Person, PersonRole, Topic

logger = logging.getLogger(__name__)

BASE_URL = "https://www.ola.org"
REQUEST_DELAY_SECONDS = 0.5


@dataclass(slots=True)
class MemberRoles:
    ola_slug: str
    riding: str | None
    roles: list[str]


def _role_type(title: str) -> str | None:
    """Map an ola.org role title onto the PersonRole vocabulary.

    Party-leader roles (other than Premier) are skipped: "Leader, X Party"
    is a party job, not a Crown or House office.
    """
    lowered = title.lower()
    if lowered == "premier" or lowered.startswith("premier "):
        return "minister"
    if lowered.startswith(("minister ", "associate minister", "attorney general")):
        return "minister"
    if lowered.startswith("parliamentary assistant"):
        return "parliamentary_secretary"
    if lowered.startswith(("speaker", "deputy speaker")) or "house leader" in lowered or "whip" in lowered:
        return "house_officer"
    if lowered.startswith("leader of the official opposition"):
        return "house_officer"
    return None


def parse_member_roles(html: str, ola_slug: str) -> MemberRoles:
    tree = HTMLParser(html)
    riding = None
    m = re.search(r'Riding map for ([^"<]+)"', html)
    if m:
        riding = m.group(1).strip()

    roles: dict[str, None] = {}
    block = tree.css_first('[class*="member_current_role_block"]')
    if block is not None:
        for li in block.css("li"):
            # Each <li> repeats the title (visually-hidden + aria-hidden spans).
            span = li.css_first("span")
            text = re.sub(r"\s+", " ", (span.text() if span else li.text()) or "").strip()
            if text:
                roles.setdefault(text, None)
    return MemberRoles(ola_slug=ola_slug, riding=riding, roles=list(roles))


def sync_member_roles(db: Session, members: list[MemberRoles]) -> int:
    """Upsert current Ontario roles; end-date roles that disappeared.

    Scoped strictly to on-assembly people — federal cabinet rows are
    untouched.
    """
    mpp_index = _ontario_mpp_index(db)
    valid_topics = {t.slug for t in db.scalars(select(Topic)).all()}
    today = date.today()

    seen_role_ids: set[int] = set()
    count = 0
    for member in members:
        person_id = mpp_index.get((member.riding or "").lower())
        if person_id is None:
            continue
        for title in member.roles:
            role_type = _role_type(title)
            if role_type is None:
                continue
            existing = db.scalar(
                select(PersonRole).where(
                    PersonRole.person_id == person_id,
                    PersonRole.role_type == role_type,
                    PersonRole.title_en == title,
                    PersonRole.is_current.is_(True),
                )
            )
            if existing is None:
                slug = portfolio_topic_slug(title) if role_type == "minister" else None
                existing = PersonRole(
                    person_id=person_id,
                    role_type=role_type,
                    title_en=title,
                    portfolio_slug=slug if slug in valid_topics else slug,
                    started_on=today,
                    is_current=True,
                    source_url=f"{BASE_URL}/en/members/all/{member.ola_slug}",
                )
                db.add(existing)
                db.flush()
                count += 1
            seen_role_ids.add(existing.id)

    # End-date Ontario roles that no longer appear (cabinet shuffles).
    ontario_people = (
        select(Person.id)
        .join(Chamber, Person.chamber_id == Chamber.id)
        .where(Chamber.slug == "on-assembly")
        .scalar_subquery()
    )
    stale = db.scalars(
        select(PersonRole).where(
            PersonRole.is_current.is_(True),
            PersonRole.person_id.in_(ontario_people),
            PersonRole.id.not_in(seen_role_ids or {0}),
        )
    ).all()
    for role in stale:
        role.is_current = False
        role.ended_on = today
    db.commit()
    return count


async def sync_ontario_roles(db: Session) -> int:
    """Fetch every sitting MPP's page and sync their current roles."""
    headers = {"User-Agent": get_settings().ingestion_user_agent}
    members: list[MemberRoles] = []

    async with httpx.AsyncClient(headers=headers, timeout=60.0, follow_redirects=True) as client:
        listing = await client.get(BASE_URL + "/en/members/current")
        listing.raise_for_status()
        await asyncio.sleep(REQUEST_DELAY_SECONDS)
        slugs = parse_member_slugs(listing.text)
        logger.info("ontario roles: %d sitting MPPs", len(slugs))

        for ola_slug in slugs:
            try:
                page = None
                for attempt in range(3):
                    try:
                        page = await client.get(f"{BASE_URL}/en/members/all/{ola_slug}")
                        break
                    except httpx.TransportError:
                        await asyncio.sleep(2.0 * (attempt + 1))
                if page is None or page.status_code != 200:
                    continue
                await asyncio.sleep(REQUEST_DELAY_SECONDS)
                members.append(parse_member_roles(page.text, ola_slug))
            except httpx.HTTPError as exc:
                logger.warning("ontario roles: %s failed (%s); continuing", ola_slug, type(exc).__name__)

    # Only end-date when the crawl actually covered the assembly — a
    # half-failed run must not strip everyone's roles.
    if len(members) < len(slugs) * 0.8:
        logger.warning(
            "ontario roles: only %d/%d member pages fetched; skipping sync", len(members), len(slugs)
        )
        return 0
    return sync_member_roles(db, members)
