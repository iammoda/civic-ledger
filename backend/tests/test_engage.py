"""Phase 8 tests: letters citing real ballots, notification matcher."""
from __future__ import annotations

from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.data.topics import seed_topics
from app.db.session import get_db
from app.ingestion.sync import SyncContext
from app.main import app
from app.models import (
    Ballot,
    Bill,
    BillDeath,
    EntityTopic,
    Notification,
    Person,
    PersonMembership,
    Petition,
    Topic,
    UserFollow,
    Vote,
)
from app.services.letters import build_letter
from app.services.notifications import match_notifications, parliament_is_sitting


@pytest.fixture()
def client(db):
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def _mp_with_bill_votes(db):
    ctx = SyncContext(db)
    session = ctx.session_for_label("45-1")
    mp = Person(slug="jane-doe", full_name="Jane Doe", chamber_id=ctx.house.id, email="jane.doe@parl.gc.ca")
    db.add(mp)
    db.flush()
    db.add(
        PersonMembership(
            person_id=mp.id, chamber_id=ctx.house.id, riding_name="Testville",
            started_on=date(2025, 1, 1), is_current=True,
        )
    )
    bill = Bill(session_id=session.id, chamber_id=ctx.house.id, number="C-30", title_en="An Act about housing")
    db.add(bill)
    db.flush()
    vote = Vote(
        session_id=session.id, chamber_id=ctx.house.id, bill_id=bill.id, number="173",
        occurred_on=date(2026, 6, 18), description_en="3rd reading and adoption of Bill C-30",
        yea_effect="advance", result="Passed",
    )
    db.add(vote)
    db.flush()
    db.add(Ballot(vote_id=vote.id, person_id=mp.id, ballot="nay", party_slug="liberal"))
    db.commit()
    return mp, bill, vote


# --- Letters ---


def test_letter_cites_real_ballot(db) -> None:
    mp, bill, vote = _mp_with_bill_votes(db)
    letter = build_letter(
        db, mp=mp, concern="Rent is out of control in our riding.",
        bill_session="45-1", bill_number="C-30",
    )
    assert "Dear Jane Doe," in letter.letter_text
    assert "in Testville" in letter.letter_text
    assert "Rent is out of control" in letter.letter_text
    # Nay on an advancing motion -> "voted to block".
    assert "you voted to block it (Vote 173)" in letter.letter_text
    assert letter.citations[0].effect == "blocked"
    assert letter.mp_email == "jane.doe@parl.gc.ca"


def test_letter_without_bill_or_record(db) -> None:
    mp, _, _ = _mp_with_bill_votes(db)
    letter = build_letter(db, mp=mp, concern="Please support rural broadband.")
    assert "Please tell me your position" in letter.letter_text
    assert letter.citations == []

    # Bill given but MP never voted on it.
    letter2 = build_letter(
        db, mp=mp, concern="Concern text here.", bill_session="45-1", bill_number="C-99",
    )
    assert "could not find a recorded vote" in letter2.letter_text


def test_letter_endpoint_unknown_mp(db, client) -> None:
    response = client.post(
        "/v1/actions/letter",
        json={"mp_slug": "nobody-here", "concern": "This is my concern text."},
    )
    assert response.status_code == 404  # Anonymous flow: MP slug must exist.


def test_letter_endpoint_full_flow(db, client) -> None:
    mp, bill, _ = _mp_with_bill_votes(db)

    response = client.post(
        "/v1/actions/letter",
        json={
            "mp_slug": "jane-doe",
            "concern": "Rent is out of control.",
            "bill_session": "45-1",
            "bill_number": "C-30",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "Vote 173" in data["letter_text"]
    assert data["citations"][0]["effect"] == "blocked"
    assert data["polished"] is False


# --- Notification matcher ---


def _followed_user(db, target_type: str, target_ref: str, user_id: str = "u1") -> None:
    db.add(UserFollow(user_id=user_id, target_type=target_type, target_ref=target_ref))
    db.commit()


def test_topic_follow_notifies_new_and_dead_bills(db) -> None:
    mp, bill, vote = _mp_with_bill_votes(db)
    seed_topics(db)
    housing = db.scalar(select(Topic).where(Topic.slug == "housing"))
    db.add(EntityTopic(topic_id=housing.id, entity_type="bill", entity_id=bill.id, source="alias"))
    db.add(BillDeath(bill_id=bill.id, mechanism="died_committee", occurred_on=date(2026, 6, 20)))
    db.commit()
    _followed_user(db, "topic", "housing")

    created = match_notifications(db)
    kinds = {n.kind for n in db.scalars(select(Notification)).all()}
    assert "bill_new" in kinds
    assert "bill_died" in kinds
    assert created >= 2
    # Idempotent.
    assert match_notifications(db) == 0


def test_person_follow_notifies_dissent_and_weekly_rollup(db) -> None:
    mp, bill, vote = _mp_with_bill_votes(db)
    ballot = db.scalar(select(Ballot))
    ballot.broke_party_line = True
    vote.occurred_on = date.today() - timedelta(days=2)
    db.commit()
    _followed_user(db, "person", "jane-doe")

    match_notifications(db)
    notifications = db.scalars(select(Notification)).all()
    kinds = {n.kind for n in notifications}
    assert "mp_dissent" in kinds
    assert "mp_voted" in kinds
    dissent = next(n for n in notifications if n.kind == "mp_dissent")
    assert "broke party ranks" in dissent.title_en


def test_topic_follow_notifies_closing_petitions(db) -> None:
    seed_topics(db)
    housing = db.scalar(select(Topic).where(Topic.slug == "housing"))
    petition = Petition(
        number="e-1", title_en="Fix housing", state="open",
        closes_at=date.today() + timedelta(days=3), signature_count=1200,
        source_url="https://www.ourcommons.ca/petitions/en/Petition/Details?Petition=e-1",
    )
    db.add(petition)
    db.flush()
    db.add(EntityTopic(topic_id=housing.id, entity_type="petition", entity_id=petition.id, source="alias"))
    db.commit()
    _followed_user(db, "topic", "housing")

    match_notifications(db)
    notification = db.scalar(select(Notification).where(Notification.kind == "petition_closing"))
    assert notification is not None
    assert "closing in 3 days" in notification.title_en
    assert "1,200 signatures" in notification.body_en


def test_bill_follow_notifies_votes(db) -> None:
    mp, bill, vote = _mp_with_bill_votes(db)
    vote.occurred_on = date.today() - timedelta(days=1)
    db.commit()
    _followed_user(db, "bill", "45-1/C-30")

    match_notifications(db)
    notification = db.scalar(select(Notification).where(Notification.kind == "vote_result"))
    assert notification is not None
    assert "C-30" in notification.title_en


# --- Feed API removed with sign-in; notification matcher above still powers digests. ---


def test_parliament_sitting_heuristic(db) -> None:
    assert parliament_is_sitting(db) is False  # No votes at all.
    _mp_with_bill_votes(db)
    assert parliament_is_sitting(db, today=date(2026, 6, 25)) is True
    assert parliament_is_sitting(db, today=date(2026, 9, 25)) is False
