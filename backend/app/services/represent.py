"""Postal code -> riding + MP via the Represent API (Open North).

Privacy: the postal code is used for the lookup only — never stored.
Postal codes can span riding boundaries; when they do, we return every
candidate and the UI asks the user to pick.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

import httpx
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.config import get_settings
from app.models import Person, PersonMembership

settings = get_settings()

REPRESENT_BASE = "https://represent.opennorth.ca"
POSTAL_RE = re.compile(r"^[A-Za-z]\d[A-Za-z]\d[A-Za-z]\d$")


@dataclass(slots=True)
class MpCandidate:
    riding_name: str
    province: str | None
    mp_name: str
    party_name: str | None
    person_slug: str | None  # Matched to our Person, when possible.


@dataclass(slots=True)
class LadderRep:
    """Any elected official returned by Represent (all levels)."""

    level: str  # federal | provincial | municipal
    office: str  # MP, MPP, MLA, Mayor, Councillor...
    name: str
    district_name: str | None
    party_name: str | None
    email: str | None
    url: str | None
    person_slug: str | None = None  # Matched for MPs only (deep data)


PROVINCIAL_OFFICES = {"mpp", "mla", "mna", "mha"}
MUNICIPAL_OFFICES = {"mayor", "councillor", "regional councillor", "alderman", "conseiller", "mairesse", "maire"}


def _office_level(office: str) -> str | None:
    normalized = (office or "").strip().lower()
    if normalized == "mp":
        return "federal"
    if normalized in PROVINCIAL_OFFICES:
        return "provincial"
    if normalized in MUNICIPAL_OFFICES:
        return "municipal"
    return None


def extract_ladder(db: Session, payload: dict) -> list[LadderRep]:
    """All representatives across levels, deduped by (office, name)."""
    seen: set[tuple[str, str]] = set()
    ladder: list[LadderRep] = []
    for key in ("representatives_centroid", "representatives_concordance"):
        for rep in payload.get(key) or []:
            office = rep.get("elected_office") or ""
            level = _office_level(office)
            if level is None:
                continue
            name = rep.get("name") or ""
            dedupe_key = (office.lower(), name.lower())
            if not name or dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            district = rep.get("district_name") or ""
            ladder.append(
                LadderRep(
                    level=level,
                    office=office,
                    name=name,
                    district_name=district or None,
                    party_name=rep.get("party_name") or None,
                    email=rep.get("email") or None,
                    url=rep.get("url") or None,
                    person_slug=_match_person(db, name, district) if level == "federal" else None,
                )
            )
    order = {"federal": 0, "provincial": 1, "municipal": 2}
    ladder.sort(key=lambda r: (order[r.level], r.office, r.name))
    return ladder


async def lookup_postal_full(db: Session, postal_code: str) -> tuple[list[MpCandidate], list[LadderRep]] | None:
    """MP candidates + the full representative ladder. None on failure."""
    normalized = normalize_postal(postal_code)
    if normalized is None:
        return None
    headers = {"User-Agent": settings.ingestion_user_agent}
    try:
        async with httpx.AsyncClient(headers=headers, timeout=15.0) as client:
            response = await client.get(f"{REPRESENT_BASE}/postcodes/{normalized}/")
            if response.status_code == 404:
                return [], []
            response.raise_for_status()
            payload = response.json()
    except httpx.HTTPError:
        return None

    province = payload.get("province")
    candidates = []
    for rep in extract_mp_candidates(payload):
        riding = rep.get("district_name") or ""
        name = rep.get("name") or ""
        candidates.append(
            MpCandidate(
                riding_name=riding,
                province=province,
                mp_name=name,
                party_name=rep.get("party_name"),
                person_slug=_match_person(db, name, riding),
            )
        )
    return candidates, extract_ladder(db, payload)


def normalize_postal(code: str) -> str | None:
    cleaned = code.replace(" ", "").replace("-", "").upper()
    return cleaned if POSTAL_RE.match(cleaned) else None


def _match_person(db: Session, mp_name: str, riding_name: str) -> str | None:
    """Match a Represent MP to our Person by name, then riding."""
    person = db.scalar(
        select(Person).where(func.lower(Person.full_name) == mp_name.lower())
    )
    if person is not None:
        return person.slug
    membership = db.scalar(
        select(PersonMembership)
        .options(selectinload(PersonMembership.person))
        .where(
            func.lower(PersonMembership.riding_name) == riding_name.lower(),
            PersonMembership.is_current.is_(True),
        )
    )
    return membership.person.slug if membership is not None else None


def extract_mp_candidates(payload: dict) -> list[dict]:
    """Dedupe MP entries across centroid + concordance representative sets."""
    seen: dict[str, dict] = {}
    for key in ("representatives_centroid", "representatives_concordance"):
        for rep in payload.get(key) or []:
            if rep.get("elected_office") != "MP":
                continue
            district = rep.get("district_name") or ""
            if district and district not in seen:
                seen[district] = rep
    return list(seen.values())


async def lookup_postal(db: Session, postal_code: str) -> list[MpCandidate] | None:
    """Returns candidates (1 = unambiguous, >1 = user picks), None on failure."""
    normalized = normalize_postal(postal_code)
    if normalized is None:
        return None
    headers = {"User-Agent": settings.ingestion_user_agent}
    try:
        async with httpx.AsyncClient(headers=headers, timeout=15.0) as client:
            response = await client.get(f"{REPRESENT_BASE}/postcodes/{normalized}/")
            if response.status_code == 404:
                return []
            response.raise_for_status()
            payload = response.json()
    except httpx.HTTPError:
        return None

    province = payload.get("province")
    candidates = []
    for rep in extract_mp_candidates(payload):
        riding = rep.get("district_name") or ""
        name = rep.get("name") or ""
        candidates.append(
            MpCandidate(
                riding_name=riding,
                province=province,
                mp_name=name,
                party_name=rep.get("party_name"),
                person_slug=_match_person(db, name, riding),
            )
        )
    return candidates
