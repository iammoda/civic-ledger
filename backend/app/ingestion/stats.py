"""Nightly derived stats: attendance, party-line %, dissent counts.

Computed from ballots — self-contained, no external calls.
"""
from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    Ballot,
    LegislatureSession,
    Person,
    PersonMembership,
    PersonStats,
    Vote,
)


def mark_current_session(db: Session) -> LegislatureSession | None:
    """The session containing the most recent vote is the current one.

    Scoped per jurisdiction: the federal session with the latest federal
    vote is current, an Ontario session with the latest Ontario vote is
    current, and neither can unseat the other. Returns the DEFAULT
    (federal) jurisdiction's current session — callers use it to drive
    the OpenParliament incremental sync.
    """
    from app.core.config import get_settings

    from app.models import Jurisdiction

    default_code = get_settings().default_jurisdiction
    jurisdiction_ids = db.scalars(
        select(LegislatureSession.jurisdiction_id)
        .join(Vote, Vote.session_id == LegislatureSession.id)
        .distinct()
    ).all()
    current = None
    for jurisdiction_id in jurisdiction_ids:
        session_id = db.execute(
            select(Vote.session_id)
            .join(LegislatureSession, Vote.session_id == LegislatureSession.id)
            .where(LegislatureSession.jurisdiction_id == jurisdiction_id)
            .order_by(Vote.occurred_on.desc())
            .limit(1)
        ).scalar_one_or_none()
        if session_id is None:
            continue
        sessions = db.scalars(
            select(LegislatureSession).where(LegislatureSession.jurisdiction_id == jurisdiction_id)
        ).all()
        for session in sessions:
            session.is_current = session.id == session_id
            if session.is_current:
                jurisdiction = db.get(Jurisdiction, jurisdiction_id)
                if jurisdiction is not None and jurisdiction.code == default_code:
                    current = session
    db.commit()
    return current


def _membership_windows(db: Session, person_id: int) -> list[tuple[date, date]]:
    rows = db.scalars(
        select(PersonMembership).where(PersonMembership.person_id == person_id)
    ).all()
    return [(m.started_on or date.min, m.ended_on or date.max) for m in rows]


def compute_person_session_stats(db: Session, person: Person, session: LegislatureSession) -> PersonStats | None:
    vote_dates = db.execute(
        select(Vote.id, Vote.occurred_on).where(
            Vote.session_id == session.id, Vote.chamber_id == person.chamber_id
        )
    ).all()
    if not vote_dates:
        return None

    windows = _membership_windows(db, person.id)

    def eligible(on: date) -> bool:
        return any(start <= on <= end for start, end in windows)

    eligible_vote_ids = {vote_id for vote_id, on in vote_dates if eligible(on)}
    if not eligible_vote_ids:
        return None

    ballots = db.scalars(
        select(Ballot).where(Ballot.person_id == person.id, Ballot.vote_id.in_(eligible_vote_ids))
    ).all()
    cast = [b for b in ballots if b.ballot in {"yea", "nay", "paired"}]
    cast_yn = [b for b in cast if b.ballot in {"yea", "nay"}]
    dissents = sum(1 for b in cast_yn if b.broke_party_line)

    stats = db.scalar(
        select(PersonStats).where(
            PersonStats.person_id == person.id, PersonStats.session_id == session.id
        )
    )
    if stats is None:
        stats = PersonStats(person_id=person.id, session_id=session.id)
        db.add(stats)

    stats.votes_eligible = len(eligible_vote_ids)
    stats.votes_cast = len(cast)
    stats.attendance_pct = round(100.0 * len(cast) / len(eligible_vote_ids), 1)
    stats.party_line_pct = (
        round(100.0 * (len(cast_yn) - dissents) / len(cast_yn), 1) if cast_yn else None
    )
    stats.dissent_count = dissents
    stats.computed_at = datetime.now(timezone.utc)
    return stats


def compute_all_stats(db: Session) -> int:
    """Recompute stats for every (person, session) pair that has ballots."""
    mark_current_session(db)
    pairs = db.execute(
        select(Ballot.person_id, Vote.session_id)
        .join(Vote, Ballot.vote_id == Vote.id)
        .group_by(Ballot.person_id, Vote.session_id)
    ).all()
    count = 0
    for person_id, session_id in pairs:
        person = db.get(Person, person_id)
        session = db.get(LegislatureSession, session_id)
        if person is None or session is None:
            continue
        if compute_person_session_stats(db, person, session) is not None:
            count += 1
        if count % 100 == 0:
            db.commit()
    db.commit()
    return count
