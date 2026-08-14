"""Toronto City Council voting record -> shared Vote/Ballot tables.

Source: City of Toronto Open Data, "Members of Toronto City Council -
Voting Record" (CKAN datastore, refreshed as council meets). One row per
member per vote; we group rows into Vote events and store each member's
position as a Ballot.

Toronto is one of only two Canadian cities publishing this (the other is
Vancouver) — every other council gets the eScribe minutes treatment.
"""
from __future__ import annotations

import hashlib
import logging
import re
from datetime import date, datetime
from typing import Any, Iterable

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.ingestion.escribe import normalize_minutes_name
from app.ingestion.sync import slugify
from app.models import Ballot, Chamber, Jurisdiction, LegislatureSession, Person, Vote

logger = logging.getLogger(__name__)
settings = get_settings()

CKAN_BASE = "https://ckan0.cf.opendata.inter.prod-toronto.ca"
RESOURCE_ID = "55ead013-2331-4686-9895-9e8145b94189"  # member-voting-record-2022-2026
JURISDICTION_CODE = "toronto-city-council"
TERM_START_YEAR = 2022
PAGE_SIZE = 10000
DATASET_URL = (
    "https://open.toronto.ca/dataset/members-of-toronto-city-council-voting-record/"
)

BALLOT_MAP = {"yes": "yea", "no": "nay", "absent": "absent", "abstain": "abstain"}


class TorontoClient:
    def __init__(self) -> None:
        self._client = httpx.AsyncClient(
            base_url=CKAN_BASE,
            headers={"User-Agent": settings.ingestion_user_agent},
            timeout=120.0,
        )

    async def __aenter__(self) -> "TorontoClient":
        return self

    async def __aexit__(self, *exc: Any) -> None:
        await self._client.aclose()

    async def iter_rows(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        offset = 0
        while True:
            response = await self._client.get(
                "/api/3/action/datastore_search",
                params={"id": RESOURCE_ID, "limit": PAGE_SIZE, "offset": offset},
            )
            response.raise_for_status()
            result = response.json()["result"]
            batch = result.get("records", [])
            rows.extend(batch)
            offset += len(batch)
            if not batch or offset >= result.get("total", 0):
                return rows


def _parse_dt(value: str) -> datetime | None:
    """'2022-11-23 15:17 PM' — the AM/PM suffix duplicates 24h time; ignore it."""
    cleaned = re.sub(r"\s*(AM|PM)$", "", (value or "").strip())
    try:
        return datetime.strptime(cleaned, "%Y-%m-%d %H:%M")
    except ValueError:
        return None


def vote_group_key(row: dict[str, Any]) -> tuple:
    return (
        (row.get("Committee") or "").strip(),
        (row.get("Date/Time") or "").strip(),
        (row.get("Agenda Item #") or "").strip(),
        (row.get("Motion Type") or "").strip(),
        (row.get("Vote Description") or "").strip(),
    )


def vote_number_for(key: tuple, occurred_on: date) -> str:
    digest = hashlib.sha256("|".join(key).encode()).hexdigest()[:10]
    item = slugify(key[2])[:30] or "item"
    return f"{occurred_on.isoformat()}-{item}-{digest}"[:64]


def _result_of(raw: str) -> str | None:
    lowered = (raw or "").lower()
    if lowered.startswith("carried"):
        return "Passed"
    if lowered.startswith("lost") or lowered.startswith("defeated"):
        return "Negatived"
    return raw or None


def sync_toronto_votes(db: Session, rows: Iterable[dict[str, Any]]) -> dict[str, int]:
    jurisdiction = db.scalar(
        select(Jurisdiction).where(Jurisdiction.code == JURISDICTION_CODE)
    )
    if jurisdiction is None:
        raise RuntimeError("toronto-city-council jurisdiction missing — run the Represent sync first")
    chamber = db.scalar(
        select(Chamber).where(Chamber.jurisdiction_id == jurisdiction.id, Chamber.slug == "council")
    )
    if chamber is None:
        raise RuntimeError("toronto council chamber missing")
    session = db.scalar(
        select(LegislatureSession).where(
            LegislatureSession.jurisdiction_id == jurisdiction.id,
            LegislatureSession.parliament_number == TERM_START_YEAR,
            LegislatureSession.session_number == 1,
        )
    )
    if session is None:
        session = LegislatureSession(
            jurisdiction_id=jurisdiction.id,
            parliament_number=TERM_START_YEAR,
            session_number=1,
            started_on=date(TERM_START_YEAR, 11, 15),
            is_current=True,
        )
        db.add(session)
        db.flush()

    # Name -> person map (Toronto prints clean "First Last" names).
    roster: dict[str, Person] = {}
    for person in db.scalars(select(Person).where(Person.chamber_id == chamber.id)).all():
        roster[normalize_minutes_name(person.full_name)] = person

    # Group member-rows into vote events. Identical motions recorded in the
    # same minute collapse into one group — dedupe per member (keep last).
    raw_groups: dict[tuple, list[dict[str, Any]]] = {}
    for row in rows:
        raw_groups.setdefault(vote_group_key(row), []).append(row)
    groups: dict[tuple, list[dict[str, Any]]] = {}
    for key, group in raw_groups.items():
        by_member: dict[str, dict[str, Any]] = {}
        for row in group:
            name = f"{row.get('First Name') or ''} {row.get('Last Name') or ''}".strip()
            by_member[name] = row
        groups[key] = list(by_member.values())

    # Existing votes + ballot counts, for cheap idempotent re-runs.
    vote_ids = dict(
        db.execute(select(Vote.number, Vote.id).where(Vote.session_id == session.id)).all()
    )
    from sqlalchemy import func as _func

    ballot_counts = dict(
        db.execute(
            select(Ballot.vote_id, _func.count(Ballot.id))
            .join(Vote, Ballot.vote_id == Vote.id)
            .where(Vote.session_id == session.id)
            .group_by(Ballot.vote_id)
        ).all()
    )

    counts = {"votes": 0, "ballots": 0, "unmatched": 0, "skipped": 0}
    processed = 0
    for key, group in groups.items():
        occurred = _parse_dt(key[1])
        if occurred is None:
            continue
        number = vote_number_for(key, occurred.date())
        existing_id = vote_ids.get(number)
        if existing_id is not None and ballot_counts.get(existing_id, 0) == len(group):
            counts["skipped"] += 1
            continue

        committee, _, item, motion_type, description = key
        yeas = sum(1 for r in group if (r.get("Vote") or "").lower() == "yes")
        nays = sum(1 for r in group if (r.get("Vote") or "").lower() == "no")
        vote = db.get(Vote, existing_id) if existing_id else None
        if vote is None:
            vote = Vote(
                session_id=session.id,
                chamber_id=chamber.id,
                number=number,
                occurred_on=occurred.date(),
                description_en="",
            )
            db.add(vote)
        vote.occurred_on = occurred.date()
        vote.description_en = f"{committee} {item}: {group[0].get('Agenda Item Title') or ''} — {motion_type}: {description}"[:4000]
        vote.result = _result_of(group[0].get("Result") or "")
        vote.yea_total = yeas
        vote.nay_total = nays
        vote.vote_type = "free"  # Municipal: no party whips.
        vote.source_url = DATASET_URL
        db.flush()

        existing_ballots = {
            b.person_id: b for b in db.scalars(select(Ballot).where(Ballot.vote_id == vote.id)).all()
        }
        for row in group:
            name = f"{row.get('First Name') or ''} {row.get('Last Name') or ''}".strip()
            person = roster.get(normalize_minutes_name(name))
            if person is None:
                counts["unmatched"] += 1
                continue
            value = BALLOT_MAP.get((row.get("Vote") or "").lower(), "absent")
            ballot = existing_ballots.get(person.id)
            if ballot is None:
                ballot = Ballot(vote_id=vote.id, person_id=person.id, ballot=value)
                db.add(ballot)
            ballot.ballot = value
            counts["ballots"] += 1
        counts["votes"] += 1
        processed += 1
        if processed % 200 == 0:
            db.commit()
    db.commit()
    return counts
