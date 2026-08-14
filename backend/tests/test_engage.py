"""Phase 8 tests: letters citing real ballots."""
from __future__ import annotations

from datetime import date

import pytest
from fastapi.testclient import TestClient

from app.db.session import get_db
from app.ingestion.sync import SyncContext
from app.main import app
from app.models import (
    Ballot,
    Bill,
    Jurisdiction,
    LegislatureSession,
    Person,
    PersonMembership,
    PersonStats,
    Vote,
)
from app.services.letters import build_letter


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


# --- The Receipts ---


def test_receipts_ontario_scope(db, client) -> None:
    jur = Jurisdiction(code="ca-on", name_en="Legislative Assembly of Ontario", level="provincial")
    db.add(jur)
    db.flush()
    session = LegislatureSession(jurisdiction_id=jur.id, parliament_number=44, session_number=1)
    db.add(session)
    mpp = Person(slug="pat-mpp", full_name="Pat MPP")
    db.add(mpp)
    db.flush()
    db.add(
        PersonMembership(
            person_id=mpp.id, riding_name="Testville North", province_code="ON", is_current=True
        )
    )
    db.add(
        PersonStats(
            person_id=mpp.id,
            session_id=session.id,
            votes_eligible=40,
            votes_cast=32,
            attendance_pct=80.0,
            dissent_count=2,
        )
    )
    db.commit()

    response = client.get("/v1/receipts?scope=ontario")
    assert response.status_code == 200
    data = response.json()
    keys = [board["key"] for board in data["boards"]]
    # Ontario = voting boards only; money boards stay federal.
    assert keys == ["most_dissents", "lowest_attendance"]
    assert all("Queen's Park" in board["subtitle"] for board in data["boards"])
    row = data["boards"][0]["rows"][0]
    assert row["person_name"] == "Pat MPP"
    assert row["riding"] == "Testville North, ON"  # province appended

    # Federal scope still answers (and rejects unknown scopes).
    assert client.get("/v1/receipts").status_code == 200
    assert client.get("/v1/receipts?scope=alberta").status_code == 422


# --- Notification matcher ---


