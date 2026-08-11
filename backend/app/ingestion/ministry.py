"""Cabinet (ministry) ingestion from ourcommons.ca — who is responsible.

Parses the ministries page tiles into PersonRole(role_type="minister")
rows with portfolio->topic mapping, so Ask can answer with a person.
Cabinet shuffles become visible history (roles get end-dated).
"""
from __future__ import annotations

import asyncio
from datetime import date

import httpx
from selectolax.parser import HTMLParser
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.ingestion.influence import normalize_person_name
from app.models import Person, PersonRole, Topic

settings = get_settings()

MINISTRIES_URL = "https://www.ourcommons.ca/Members/en/ministries"

# Minister-title keywords -> topic slug (checked in order, first match wins).
PORTFOLIO_TOPIC_HINTS: list[tuple[tuple[str, ...], str]] = [
    (("housing", "infrastructure"), "housing"),
    (("health",), "healthcare"),
    (("environment", "climate"), "climate-environment"),
    (("finance",), "taxes"),
    (("national revenue",), "taxes"),
    (("employment", "workforce", "labour"), "jobs-economy"),
    (("immigration", "citizenship"), "immigration"),
    (("indigenous", "crown-indigenous", "northern affairs"), "indigenous"),
    (("defence",), "defence-security"),
    (("public safety",), "public-safety"),
    (("justice", "attorney general"), "justice-rights"),
    (("seniors",), "seniors-pensions"),
    (("families", "children", "social development"), "families-children"),
    (("transport",), "transport-infrastructure"),
    (("agriculture", "agri-food"), "agriculture-food"),
    (("fisheries", "oceans"), "fisheries-oceans"),
    (("energy", "natural resources"), "energy-resources"),
    (("innovation", "science", "industry"), "trade-industry"),
    (("international trade", "export"), "trade-industry"),
    (("small business",), "small-business"),
    (("veterans",), "veterans"),
    (("heritage", "culture"), "arts-culture"),
    (("official languages",), "official-languages"),
    (("democratic institutions",), "democracy-ethics"),
    (("foreign affairs", "international development", "global affairs"), "foreign-affairs"),
    (("disability", "accessibility"), "disability-accessibility"),
    (("digital", "artificial intelligence"), "privacy-digital"),
]


def portfolio_topic_slug(title: str) -> str | None:
    lowered = title.lower()
    for keywords, slug in PORTFOLIO_TOPIC_HINTS:
        if any(keyword in lowered for keyword in keywords):
            return slug
    return None


def parse_ministry_tiles(html: str) -> list[dict[str, str]]:
    """[{name, title, constituency}] from the ministries page tiles."""
    tree = HTMLParser(html)
    ministers: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for tile in tree.css(".ce-mip-mp-tile-container"):
        name_node = tile.css_first(".ce-mip-mp-name")
        if name_node is None:
            continue
        name = name_node.text().strip()
        # The role title is the plain sibling <div> after the name.
        title = ""
        node = name_node.next
        while node is not None:
            if node.tag == "div":
                text = node.text(separator=" ").strip()
                if text:
                    title = text
                    break
            node = node.next
        constituency_node = tile.css_first(".ce-mip-mp-constituency")
        key = (name.lower(), title.lower())
        if not name or not title or key in seen:
            continue
        seen.add(key)
        ministers.append(
            {
                "name": name,
                "title": title,
                "constituency": constituency_node.text().strip() if constituency_node else "",
            }
        )
    return ministers


async def fetch_ministries_html() -> str | None:
    headers = {
        "User-Agent": f"Mozilla/5.0 (compatible; {settings.ingestion_user_agent})",
        "Accept-Language": "en-CA,en;q=0.9",
    }
    try:
        async with httpx.AsyncClient(headers=headers, timeout=60.0, follow_redirects=True) as client:
            for attempt in range(3):
                response = await client.get(MINISTRIES_URL)
                if response.status_code == 200 and "ce-mip-mp-tile-container" in response.text:
                    return response.text
                await asyncio.sleep(2.0 * (attempt + 1))
    except httpx.HTTPError:
        return None
    return None


def sync_ministers(db: Session, html: str) -> int:
    """Upsert current minister roles; end-date roles that disappeared."""
    ministers = parse_ministry_tiles(html)
    if not ministers:
        return 0

    name_index = {
        normalize_person_name(full_name): person_id
        for person_id, full_name in db.execute(select(Person.id, Person.full_name)).all()
    }
    valid_topics = {t.slug for t in db.scalars(select(Topic)).all()}
    today = date.today()

    active_keys: set[tuple[int, str]] = set()
    count = 0
    for minister in ministers:
        person_id = name_index.get(normalize_person_name(minister["name"]))
        if person_id is None:
            continue
        title = minister["title"][:255]
        active_keys.add((person_id, title.lower()))

        existing = db.scalar(
            select(PersonRole).where(
                PersonRole.person_id == person_id,
                PersonRole.role_type == "minister",
                PersonRole.title_en == title,
                PersonRole.is_current.is_(True),
            )
        )
        if existing is None:
            slug = portfolio_topic_slug(title)
            db.add(
                PersonRole(
                    person_id=person_id,
                    role_type="minister",
                    title_en=title,
                    portfolio_slug=slug if slug in valid_topics else slug,
                    started_on=today,
                    is_current=True,
                    source_url=MINISTRIES_URL,
                )
            )
            count += 1

    # Cabinet shuffle: end-date roles no longer listed.
    for role in db.scalars(
        select(PersonRole).where(PersonRole.role_type == "minister", PersonRole.is_current.is_(True))
    ).all():
        if (role.person_id, role.title_en.lower()) not in active_keys:
            role.is_current = False
            role.ended_on = today

    db.commit()
    return count
