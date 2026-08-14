"""Vancouver City Council voting record -> shared Vote/Ballot tables.

Source: City of Vancouver Open Data, "council-voting-records" — one row per
member per vote, with a stable vote_number to group by. Full-dump exports
endpoint (the paginated API caps at 10k offset; the dataset has 80k+ rows).
"""
from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Any, Iterable

import httpx
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.ingestion.escribe import normalize_minutes_name
from app.models import Ballot, Chamber, Jurisdiction, LegislatureSession, Person, Vote

logger = logging.getLogger(__name__)
settings = get_settings()

EXPORT_URL = (
    "https://opendata.vancouver.ca/api/explore/v2.1/catalog/datasets/"
    "council-voting-records/exports/json"
)
DATASET_URL = "https://opendata.vancouver.ca/explore/dataset/council-voting-records/"
JURISDICTION_CODE = "vancouver-city-council"
TERM_START = date(2022, 11, 7)

BALLOT_MAP = {
    "in favour": "yea",
    "opposed": "nay",
    "abstain": "abstain",
    "absent": "absent",
    "conflict": "absent",
    "leave of absence": "absent",
}


class VancouverClient:
    def __init__(self) -> None:
        self._client = httpx.AsyncClient(
            headers={"User-Agent": settings.ingestion_user_agent}, timeout=300.0
        )

    async def __aenter__(self) -> "VancouverClient":
        return self

    async def __aexit__(self, *exc: Any) -> None:
        await self._client.aclose()

    async def fetch_rows(self, since: date) -> list[dict[str, Any]]:
        response = await self._client.get(
            EXPORT_URL, params={"where": f"vote_date>='{since.isoformat()}'"}
        )
        response.raise_for_status()
        return response.json()


def sync_vancouver_votes(db: Session, rows: Iterable[dict[str, Any]]) -> dict[str, int]:
    jurisdiction = db.scalar(
        select(Jurisdiction).where(Jurisdiction.code == JURISDICTION_CODE)
    )
    if jurisdiction is None:
        raise RuntimeError("vancouver-city-council jurisdiction missing — run the Represent sync first")
    chamber = db.scalar(
        select(Chamber).where(Chamber.jurisdiction_id == jurisdiction.id, Chamber.slug == "council")
    )
    if chamber is None:
        raise RuntimeError("vancouver council chamber missing")
    session = db.scalar(
        select(LegislatureSession).where(
            LegislatureSession.jurisdiction_id == jurisdiction.id,
            LegislatureSession.parliament_number == TERM_START.year,
            LegislatureSession.session_number == 1,
        )
    )
    if session is None:
        session = LegislatureSession(
            jurisdiction_id=jurisdiction.id,
            parliament_number=TERM_START.year,
            session_number=1,
            started_on=TERM_START,
            is_current=True,
        )
        db.add(session)
        db.flush()

    roster: dict[str, Person] = {}
    for person in db.scalars(select(Person).where(Person.chamber_id == chamber.id)).all():
        roster[normalize_minutes_name(person.full_name)] = person
        # Vancouver prints "Councillor B Montague" — initial form.
        parts = normalize_minutes_name(person.full_name).split()
        if len(parts) >= 2:
            roster[f"{parts[0][0]} {parts[-1]}"] = person

    raw_groups: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        number = str(row.get("vote_number") or "")
        if number:
            raw_groups.setdefault(number, []).append(row)
    groups: dict[str, list[dict[str, Any]]] = {}
    for number, group in raw_groups.items():
        by_member = {(r.get("council_member") or ""): r for r in group}
        groups[number] = list(by_member.values())

    vote_ids = dict(
        db.execute(select(Vote.number, Vote.id).where(Vote.session_id == session.id)).all()
    )
    ballot_counts = dict(
        db.execute(
            select(Ballot.vote_id, func.count(Ballot.id))
            .join(Vote, Ballot.vote_id == Vote.id)
            .where(Vote.session_id == session.id)
            .group_by(Ballot.vote_id)
        ).all()
    )

    counts = {"votes": 0, "ballots": 0, "unmatched": 0, "skipped": 0}
    processed = 0
    for number, group in groups.items():
        existing_id = vote_ids.get(number)
        if existing_id is not None and ballot_counts.get(existing_id, 0) == len(group):
            counts["skipped"] += 1
            continue
        first = group[0]
        try:
            occurred = datetime.strptime(first.get("vote_date") or "", "%Y-%m-%d").date()
        except ValueError:
            continue
        yeas = sum(1 for r in group if (r.get("vote") or "").lower() == "in favour")
        nays = sum(1 for r in group if (r.get("vote") or "").lower() == "opposed")
        vote = db.get(Vote, existing_id) if existing_id else None
        if vote is None:
            vote = Vote(
                session_id=session.id,
                chamber_id=chamber.id,
                number=number,
                occurred_on=occurred,
                description_en="",
            )
            db.add(vote)
        decision = (first.get("decision") or "").strip()
        vote.occurred_on = occurred
        vote.description_en = f"{first.get('meeting_type') or 'Council'}: {first.get('agenda_description') or ''}"[:4000]
        vote.result = "Passed" if decision.lower().startswith("carried") else "Negatived" if decision.lower().startswith(("lost", "defeated")) else decision or None
        vote.yea_total = yeas
        vote.nay_total = nays
        vote.vote_type = "free"
        vote.source_url = DATASET_URL
        db.flush()

        existing_ballots = {
            b.person_id: b for b in db.scalars(select(Ballot).where(Ballot.vote_id == vote.id)).all()
        }
        for row in group:
            person = roster.get(normalize_minutes_name(row.get("council_member") or ""))
            if person is None:
                counts["unmatched"] += 1
                continue
            value = BALLOT_MAP.get((row.get("vote") or "").lower(), "absent")
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
