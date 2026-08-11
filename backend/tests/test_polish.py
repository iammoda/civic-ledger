"""App-polish tests: ask with your MP's ballots, MP search, vote list fields."""
from __future__ import annotations

from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

import app.services.ask as ask_mod
from app.db.session import get_db
from app.ingestion.sync import SyncContext
from app.main import app
from app.models import Ballot, Bill, Person, PersonMembership, UserProfile, Vote
from app.services.ask import ask
from test_accounts import _seed_auth_user
from test_search_ask import UnconfiguredLLM


@pytest.fixture()
def client(db):
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def _seed_mp_bill_vote(db):
    ctx = SyncContext(db)
    session = ctx.session_for_label("45-1")
    party = ctx.party_for_names("Liberal Party of Canada", "Liberal")
    mp = Person(slug="jane-doe", full_name="Jane Doe", chamber_id=ctx.house.id)
    db.add(mp)
    db.flush()
    db.add(
        PersonMembership(
            person_id=mp.id, party_id=party.id, chamber_id=ctx.house.id,
            riding_name="Testville", province_code="ON",
            started_on=date(2025, 1, 1), is_current=True,
        )
    )
    bill = Bill(
        session_id=session.id, chamber_id=ctx.house.id, number="C-56",
        title_en="An Act respecting affordable housing",
        short_title_en="Affordable Housing Act", status_en="At second reading",
    )
    db.add(bill)
    db.flush()
    vote = Vote(
        session_id=session.id, chamber_id=ctx.house.id, bill_id=bill.id, number="88",
        occurred_on=date(2026, 4, 2), description_en="2nd reading of Bill C-56, affordable housing",
        yea_effect="advance", plain_meaning_en="A Yes vote moved this forward.",
        result="Passed", yea_total=177, nay_total=140,
    )
    db.add(vote)
    db.flush()
    db.add(Ballot(vote_id=vote.id, person_id=mp.id, ballot="nay", party_slug="liberal"))
    db.commit()
    return mp, bill, vote


# --- Ask with MP ballots ---


async def test_ask_includes_my_mp_ballots(db, monkeypatch) -> None:
    mp, bill, vote = _seed_mp_bill_vote(db)
    monkeypatch.setattr(ask_mod, "LLMClient", UnconfiguredLLM)

    response = await ask(db, "I can't afford housing anymore", mp_person_id=mp.id)
    assert response.my_mp_name == "Jane Doe"
    assert response.my_mp_slug == "jane-doe"
    assert len(response.mp_ballots) == 1
    ballot = response.mp_ballots[0]
    assert ballot.bill_number == "C-56"
    assert ballot.effect == "blocked"  # Nay on an advancing motion.
    assert "moved this forward" in ballot.description_en


async def test_ask_without_mp_has_no_ballots(db, monkeypatch) -> None:
    _seed_mp_bill_vote(db)
    monkeypatch.setattr(ask_mod, "LLMClient", UnconfiguredLLM)
    response = await ask(db, "I can't afford housing anymore")
    assert response.my_mp_name is None
    assert response.mp_ballots == []


def test_ask_endpoint_uses_profile_mp(db, client, monkeypatch) -> None:
    mp, _, _ = _seed_mp_bill_vote(db)
    monkeypatch.setattr(ask_mod, "LLMClient", UnconfiguredLLM)
    _seed_auth_user(db, token="tok1")
    db.add(UserProfile(user_id="u1", riding_name="Testville", mp_person_id=mp.id))
    db.commit()

    signed_in = client.post(
        "/v1/ask",
        json={"question": "I can't afford housing anymore"},
        cookies={"better-auth.session_token": "tok1.sig"},
    ).json()
    assert signed_in["my_mp_name"] == "Jane Doe"
    assert signed_in["mp_ballots"][0]["effect"] == "blocked"

    anonymous = client.post("/v1/ask", json={"question": "I can't afford housing anymore"}).json()
    assert anonymous["my_mp_name"] is None
    assert anonymous["mp_ballots"] == []


# --- MP name search ---


def test_politicians_name_search(db, client) -> None:
    _seed_mp_bill_vote(db)
    ctx = SyncContext(db)
    db.add(Person(slug="bob-roe", full_name="Bob Roe", chamber_id=ctx.house.id))
    db.commit()

    hit = client.get("/v1/politicians", params={"q": "jane"}).json()
    assert hit["meta"]["total"] == 1
    assert hit["items"][0]["full_name"] == "Jane Doe"

    miss = client.get("/v1/politicians", params={"q": "zzz"}).json()
    assert miss["meta"]["total"] == 0


# --- Vote list fields ---


def test_vote_list_includes_direction_fields(db, client) -> None:
    _seed_mp_bill_vote(db)
    votes = client.get("/v1/votes").json()
    item = votes["items"][0]
    assert item["yea_effect"] == "advance"
    assert item["plain_meaning_en"] == "A Yes vote moved this forward."
