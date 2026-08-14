"""Provincial + municipal people via the Represent API (Open North).

Bulk-syncs every provincial/territorial legislature and municipal council
that Represent covers (~1,800 people) into the same Person/Membership
schema the federal MPs use. Deterministic, idempotent upserts keyed on
(source_system="represent", source_id="{set_slug}/{name-slug}").

Federal MPs are NOT synced here — they come from OpenParliament with far
richer data (see app.ingestion.sync). The house-of-commons set is skipped.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, AsyncIterator

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.ingestion.sync import slugify
from app.models import Chamber, Jurisdiction, Party, Person, PersonMembership

logger = logging.getLogger(__name__)
settings = get_settings()

REPRESENT_BASE = "https://represent.opennorth.ca"
PAGE_SIZE = 100
SOURCE_SYSTEM = "represent"
# Represent allows 60 req/min; stay comfortably under it.
REQUEST_DELAY_SECONDS = 1.2
MAX_RETRIES = 4

# Provincial/territorial representative sets -> (jurisdiction code, province code).
# Municipal sets are everything else; their set slug becomes the jurisdiction code.
PROVINCIAL_SETS: dict[str, tuple[str, str]] = {
    "alberta-legislature": ("ca-ab", "AB"),
    "bc-legislature": ("ca-bc", "BC"),
    "manitoba-legislature": ("ca-mb", "MB"),
    "new-brunswick-legislature": ("ca-nb", "NB"),
    "newfoundland-labrador-legislature": ("ca-nl", "NL"),
    "northwest-territories-legislature": ("ca-nt", "NT"),
    "nova-scotia-legislature": ("ca-ns", "NS"),
    "ontario-legislature": ("ca-on", "ON"),
    "pei-legislature": ("ca-pe", "PE"),
    "quebec-assemblee-nationale": ("ca-qc", "QC"),
    "saskatchewan-legislature": ("ca-sk", "SK"),
    "yukon-legislature": ("ca-yt", "YT"),
}

SKIPPED_SETS = {"house-of-commons"}  # Federal comes from OpenParliament.


def person_source_id(set_slug: str, name: str) -> str:
    return f"{set_slug}/{slugify(name)}"


def person_slug_for(set_slug: str, name: str) -> str:
    """'ontario-legislature' + 'David Smith' -> 'on-david-smith';
    municipal sets keep their full set slug as the prefix."""
    provincial = PROVINCIAL_SETS.get(set_slug)
    prefix = provincial[1].lower() if provincial else set_slug
    return f"{prefix}-{slugify(name)}"


class RepresentClient:
    def __init__(self) -> None:
        self._client = httpx.AsyncClient(
            base_url=REPRESENT_BASE,
            headers={"User-Agent": settings.ingestion_user_agent},
            timeout=30.0,
        )

    async def __aenter__(self) -> "RepresentClient":
        return self

    async def __aexit__(self, *exc: Any) -> None:
        await self._client.aclose()

    async def _get(self, path: str, params: dict[str, Any]) -> httpx.Response:
        """Throttled GET with backoff on 429 (Represent: 60 req/min)."""
        await asyncio.sleep(REQUEST_DELAY_SECONDS)
        for attempt in range(MAX_RETRIES):
            response = await self._client.get(path, params=params)
            if response.status_code != 429:
                response.raise_for_status()
                return response
            retry_after = float(response.headers.get("Retry-After") or 30 * (attempt + 1))
            logger.info("represent 429 on %s; sleeping %.0fs", path, retry_after)
            await asyncio.sleep(retry_after)
        response.raise_for_status()
        return response

    async def list_sets(self) -> list[dict[str, Any]]:
        response = await self._get("/representative-sets/", params={"limit": 0})
        return response.json().get("objects", [])

    async def iter_representatives(self, set_slug: str) -> AsyncIterator[dict[str, Any]]:
        offset = 0
        while True:
            response = await self._get(
                f"/representatives/{set_slug}/",
                params={"limit": PAGE_SIZE, "offset": offset},
            )
            payload = response.json()
            for rep in payload.get("objects", []):
                yield rep
            if not payload.get("meta", {}).get("next"):
                return
            offset += PAGE_SIZE


def set_slug_from_url(url: str | None) -> str | None:
    """'/representative-sets/ontario-legislature/' -> 'ontario-legislature'."""
    if not url:
        return None
    parts = [p for p in url.split("/") if p]
    return parts[-1] if parts else None


def _ensure_jurisdiction(db: Session, set_slug: str, set_name: str) -> Jurisdiction:
    provincial = PROVINCIAL_SETS.get(set_slug)
    code = provincial[0] if provincial else set_slug
    level = "provincial" if provincial else "municipal"
    jur = db.scalar(select(Jurisdiction).where(Jurisdiction.code == code))
    if jur is None:
        jur = Jurisdiction(code=code, name_en=set_name, country_code="CA", level=level)
        db.add(jur)
        db.flush()
    return jur


def _ensure_chamber(db: Session, jurisdiction: Jurisdiction, set_name: str) -> Chamber:
    # Provincial assembly slugs are province-prefixed ("on-assembly") so
    # chamber slugs stay globally unique — the public vote routes rely on
    # that ("house"/"senate" federal, "{prov}-assembly" provincial).
    if jurisdiction.level == "provincial":
        slug = f"{jurisdiction.code.removeprefix('ca-')}-assembly"
    else:
        slug = "council"
    chamber = db.scalar(
        select(Chamber).where(Chamber.jurisdiction_id == jurisdiction.id, Chamber.slug == slug)
    )
    if chamber is None:
        # Migrate any pre-prefix "assembly" chamber instead of duplicating.
        legacy = db.scalar(
            select(Chamber).where(Chamber.jurisdiction_id == jurisdiction.id, Chamber.slug == "assembly")
        )
        if legacy is not None:
            legacy.slug = slug
            db.flush()
            return legacy
        chamber = Chamber(
            jurisdiction_id=jurisdiction.id, slug=slug, name_en=set_name, is_elected=True
        )
        db.add(chamber)
        db.flush()
    return chamber


def _ensure_party(
    db: Session, jurisdiction: Jurisdiction, cache: dict[str, Party], name: str | None
) -> Party | None:
    if not name:
        return None
    slug = slugify(name)
    if slug in cache:
        return cache[slug]
    party = db.scalar(
        select(Party).where(Party.jurisdiction_id == jurisdiction.id, Party.slug == slug)
    )
    if party is None:
        party = Party(
            jurisdiction_id=jurisdiction.id,
            name_en=name,
            short_name=name[:64],
            slug=slug,
        )
        db.add(party)
        db.flush()
    cache[slug] = party
    return party


def _unique_person_slug(db: Session, wanted: str, source_id: str) -> str:
    """Person.slug is globally unique (shared with MP slugs); suffix on clash."""
    candidate = wanted
    for attempt in range(2, 10):
        existing = db.scalar(select(Person).where(Person.slug == candidate))
        if existing is None or (
            existing.source_system == SOURCE_SYSTEM and existing.source_id == source_id
        ):
            return candidate
        candidate = f"{wanted}-{attempt}"
    return candidate


def upsert_representative(
    db: Session,
    rep: dict[str, Any],
    *,
    set_slug: str,
    jurisdiction: Jurisdiction,
    chamber: Chamber,
    party_cache: dict[str, Party],
) -> Person | None:
    name = (rep.get("name") or "").strip()
    if not name:
        return None
    source_id = person_source_id(set_slug, name)

    person = db.scalar(
        select(Person).where(
            Person.source_system == SOURCE_SYSTEM, Person.source_id == source_id
        )
    )
    if person is None:
        # Adopt stubs the Ontario vote-roll ingestion created for members
        # missing from the Represent roster (same slug derivation).
        person = db.scalar(
            select(Person).where(
                Person.slug == person_slug_for(set_slug, name),
                Person.source_system == "ola",
            )
        )
        if person is not None:
            person.source_system = SOURCE_SYSTEM
            person.source_id = source_id
    if person is None:
        person = Person(
            slug=_unique_person_slug(db, person_slug_for(set_slug, name), source_id),
            full_name=name,
            source_system=SOURCE_SYSTEM,
            source_id=source_id,
        )
        db.add(person)

    person.full_name = name
    person.given_name = (rep.get("first_name") or None) or person.given_name
    person.family_name = (rep.get("last_name") or None) or person.family_name
    person.email = (rep.get("email") or None) or person.email
    person.image_url = (rep.get("photo_url") or None) or person.image_url
    person.website_url = rep.get("url") or rep.get("personal_url") or person.website_url
    person.offices_json = rep.get("offices") or None
    person.chamber_id = chamber.id
    db.flush()

    party = _ensure_party(db, jurisdiction, party_cache, rep.get("party_name"))
    riding = (rep.get("district_name") or "").strip() or None
    role = (rep.get("elected_office") or "").strip() or None

    membership = db.scalar(
        select(PersonMembership).where(
            PersonMembership.person_id == person.id,
            PersonMembership.chamber_id == chamber.id,
        )
    )
    if membership is None:
        membership = PersonMembership(person_id=person.id, chamber_id=chamber.id)
        db.add(membership)
    membership.party_id = party.id if party else None
    membership.riding_name = riding
    membership.role_title = role
    membership.province_code = (
        PROVINCIAL_SETS[set_slug][1] if set_slug in PROVINCIAL_SETS else membership.province_code
    )
    membership.is_current = True
    db.flush()
    return person


def _retire_missing(
    db: Session, chamber: Chamber, seen_source_ids: set[str]
) -> int:
    """People no longer in the roster keep their record, lose is_current."""
    retired = 0
    memberships = db.scalars(
        select(PersonMembership).where(
            PersonMembership.chamber_id == chamber.id,
            PersonMembership.is_current.is_(True),
        )
    ).all()
    for membership in memberships:
        person = db.get(Person, membership.person_id)
        if person is None or person.source_system != SOURCE_SYSTEM:
            continue
        if person.source_id not in seen_source_ids:
            membership.is_current = False
            retired += 1
    return retired


async def sync_represent_people(db: Session, client: RepresentClient) -> dict[str, int]:
    """Every provincial + municipal representative set -> Person rows."""
    counts = {"sets": 0, "people": 0, "retired": 0}
    for rep_set in await client.list_sets():
        set_slug = set_slug_from_url(rep_set.get("url")) or ""
        if not set_slug or set_slug in SKIPPED_SETS:
            continue
        set_name = rep_set.get("name") or set_slug
        jurisdiction = _ensure_jurisdiction(db, set_slug, set_name)
        chamber = _ensure_chamber(db, jurisdiction, set_name)
        party_cache: dict[str, Party] = {}
        seen: set[str] = set()
        try:
            async for rep in client.iter_representatives(set_slug):
                person = upsert_representative(
                    db,
                    rep,
                    set_slug=set_slug,
                    jurisdiction=jurisdiction,
                    chamber=chamber,
                    party_cache=party_cache,
                )
                if person is not None:
                    seen.add(person.source_id or "")
                    counts["people"] += 1
        except httpx.HTTPError as exc:
            # One flaky set must not sink the other ~120.
            logger.warning("represent set %s failed: %s", set_slug, exc)
            db.commit()
            continue
        counts["retired"] += _retire_missing(db, chamber, seen)
        counts["sets"] += 1
        db.commit()
    return counts
