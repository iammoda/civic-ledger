"""Derived stats tests: attendance, party-line %, dissent counts."""
from __future__ import annotations

from datetime import date

from sqlalchemy import select

from app.ingestion.stats import compute_all_stats, mark_current_session
from app.ingestion.sync import SyncContext
from app.models import Ballot, Person, PersonMembership, PersonStats, Vote


def _setup(db):
    ctx = SyncContext(db)
    session = ctx.session_for_label("45-1")
    person = Person(slug="jane-doe", full_name="Jane Doe", chamber_id=ctx.house.id)
    db.add(person)
    db.flush()
    db.add(
        PersonMembership(
            person_id=person.id,
            chamber_id=ctx.house.id,
            started_on=date(2025, 1, 1),
            ended_on=None,
            is_current=True,
        )
    )
    votes = []
    for i in range(4):
        vote = Vote(
            session_id=session.id,
            chamber_id=ctx.house.id,
            number=str(i + 1),
            occurred_on=date(2026, 3, i + 1),
            description_en=f"Division {i + 1}",
        )
        db.add(vote)
        votes.append(vote)
    db.flush()
    return ctx, session, person, votes


def test_attendance_party_line_and_dissents(db) -> None:
    ctx, session, person, votes = _setup(db)
    # Casts ballots in 3 of 4 votes; dissents once.
    db.add(Ballot(vote_id=votes[0].id, person_id=person.id, ballot="yea", party_slug="liberal"))
    db.add(Ballot(vote_id=votes[1].id, person_id=person.id, ballot="nay", party_slug="liberal", broke_party_line=True))
    db.add(Ballot(vote_id=votes[2].id, person_id=person.id, ballot="yea", party_slug="liberal"))
    db.add(Ballot(vote_id=votes[3].id, person_id=person.id, ballot="absent", party_slug="liberal"))
    db.commit()

    computed = compute_all_stats(db)
    assert computed == 1

    stats = db.scalar(select(PersonStats))
    assert stats.votes_eligible == 4
    assert stats.votes_cast == 3
    assert stats.attendance_pct == 75.0
    assert stats.party_line_pct == round(100.0 * 2 / 3, 1)
    assert stats.dissent_count == 1


def test_eligibility_respects_membership_window(db) -> None:
    ctx, session, person, votes = _setup(db)
    membership = db.scalar(select(PersonMembership))
    membership.started_on = date(2026, 3, 3)  # joined before votes 3 & 4 only
    db.add(Ballot(vote_id=votes[2].id, person_id=person.id, ballot="yea", party_slug="liberal"))
    db.commit()

    compute_all_stats(db)
    stats = db.scalar(select(PersonStats))
    assert stats.votes_eligible == 2
    assert stats.votes_cast == 1
    assert stats.attendance_pct == 50.0


def test_mark_current_session(db) -> None:
    ctx = SyncContext(db)
    old = ctx.session_for_label("44-1")
    new = ctx.session_for_label("45-1")
    db.add(Vote(session_id=old.id, chamber_id=ctx.house.id, number="1", occurred_on=date(2023, 1, 1), description_en="old"))
    db.add(Vote(session_id=new.id, chamber_id=ctx.house.id, number="1", occurred_on=date(2026, 1, 1), description_en="new"))
    db.commit()

    current = mark_current_session(db)
    assert current is not None
    assert current.label == "45-1"
    db.refresh(old)
    assert old.is_current is False
