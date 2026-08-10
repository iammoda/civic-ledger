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
