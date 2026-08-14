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
    ExpenseSummary,
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
    # "provincial" is the canonical scope; "ontario" stays as an alias.
    assert client.get("/v1/receipts?scope=provincial").status_code == 200
    assert client.get("/v1/receipts?scope=alberta").status_code == 422


def test_receipts_federal_province_filter(db, client) -> None:
    ctx = SyncContext(db)
    session = ctx.session_for_label("45-1")

    mb_mp = Person(slug="mb-mp", full_name="Morgan Brandon", chamber_id=ctx.house.id)
    on_mp = Person(slug="on-mp", full_name="Olivia Nash", chamber_id=ctx.house.id)
    db.add_all([mb_mp, on_mp])
    db.flush()
    db.add_all(
        [
            PersonMembership(
                person_id=mb_mp.id, chamber_id=ctx.house.id, riding_name="Winnipeg Test",
                province_code="MB", is_current=True,
            ),
            PersonMembership(
                person_id=on_mp.id, chamber_id=ctx.house.id, riding_name="Toronto Test",
                province_code="ON", is_current=True,
            ),
            ExpenseSummary(
                person_id=mb_mp.id, mp_name_raw="Brandon, Morgan", fiscal_year=2025, quarter=2,
                salaries=100000.0, travel=5000.0, hospitality=1000.0, contracts=2000.0,
            ),
            ExpenseSummary(
                person_id=on_mp.id, mp_name_raw="Nash, Olivia", fiscal_year=2025, quarter=2,
                salaries=200000.0, travel=9000.0, hospitality=3000.0, contracts=8000.0,
            ),
            PersonStats(
                person_id=mb_mp.id, session_id=session.id,
                votes_eligible=40, votes_cast=35, attendance_pct=87.5, dissent_count=3,
            ),
            PersonStats(
                person_id=on_mp.id, session_id=session.id,
                votes_eligible=40, votes_cast=40, attendance_pct=100.0, dissent_count=1,
            ),
        ]
    )
    db.commit()

    response = client.get("/v1/receipts?scope=federal&province=mb")  # lowercase → uppercased
    assert response.status_code == 200
    data = response.json()
    assert data["boards"], "province filter should still surface the MB person's boards"
    for board in data["boards"]:
        assert "· MB MPs only" in board["subtitle"]
        names = {row["person_name"] for row in board["rows"]}
        assert names == {"Morgan Brandon"}, f"{board['key']} leaked non-MB rows: {names}"

    # Unfiltered federal scope still shows both MPs.
    unfiltered = client.get("/v1/receipts").json()
    all_names = {row["person_name"] for board in unfiltered["boards"] for row in board["rows"]}
    assert {"Morgan Brandon", "Olivia Nash"} <= all_names


def test_receipts_provincial_non_ontario_returns_note(db, client) -> None:
    response = client.get("/v1/receipts?scope=provincial&province=BC")
    assert response.status_code == 200
    data = response.json()
    assert data["boards"] == []
    assert data["note"] is not None
    assert "Only Ontario publishes machine-readable MPP votes" in data["note"]
    assert "Only Ontario publishes machine-readable MPP votes" in data["generated_note"]


# --- Notification matcher ---


