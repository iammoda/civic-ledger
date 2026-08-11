"""Graveyard API tests: outcome filters, death serialization, topics."""
from __future__ import annotations

from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.data.topics import seed_topics
from app.db.session import get_db
from app.ingestion.sync import SyncContext
from app.main import app
from app.models import Bill, BillDeath, EntityTopic, Topic, Vote


@pytest.fixture()
def client(db):
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def _seed_bills(db):
    ctx = SyncContext(db)
    session = ctx.session_for_label("45-1")

    law = Bill(
        session_id=session.id, chamber_id=ctx.house.id, number="C-1",
        title_en="An Act that became law", outcome="enacted", is_law=True,
        introduced_on=date(2026, 1, 1),
    )
    pending = Bill(
        session_id=session.id, chamber_id=ctx.house.id, number="C-2",
        title_en="An Act in progress", outcome="pending", introduced_on=date(2026, 2, 1),
    )
    dead = Bill(
        session_id=session.id, chamber_id=ctx.house.id, number="C-3",
        title_en="An Act that died in committee", outcome="died_committee",
        introduced_on=date(2026, 3, 1),
    )
    defeated = Bill(
        session_id=session.id, chamber_id=ctx.house.id, number="C-4",
        title_en="An Act defeated at second reading", outcome="defeated_vote",
        introduced_on=date(2026, 4, 1),
    )
    db.add_all([law, pending, dead, defeated])
    db.flush()

    kill_vote = Vote(
        session_id=session.id, chamber_id=ctx.house.id, bill_id=defeated.id, number="55",
        occurred_on=date(2026, 5, 10), description_en="2nd reading of Bill C-4",
        result="Negatived", yea_total=128, nay_total=152,
    )
    db.add(kill_vote)
    db.flush()
    db.add(BillDeath(
        bill_id=dead.id, mechanism="died_committee", stage="committee",
        occurred_on=date(2026, 6, 1),
        attribution_en="Died in committee when the session ended — never brought forward for a vote.",
    ))
    db.add(BillDeath(
        bill_id=defeated.id, mechanism="defeated_vote", stage="second-reading",
        occurred_on=date(2026, 5, 10), kill_vote_id=kill_vote.id,
        attribution_en="Defeated 128–152: 2nd reading of Bill C-4",
    ))
    db.commit()
    return law, pending, dead, defeated


def test_outcome_group_filters(db, client) -> None:
    _seed_bills(db)

    everything = client.get("/v1/bills").json()
    assert everything["meta"]["total"] == 4
    outcomes = {item["number"]: item["outcome"] for item in everything["items"]}
    assert outcomes == {"C-1": "enacted", "C-2": "pending", "C-3": "died_committee", "C-4": "defeated_vote"}

    law = client.get("/v1/bills", params={"outcome_group": "law"}).json()
    assert [i["number"] for i in law["items"]] == ["C-1"]
    assert law["items"][0]["is_law"] is True

    dead = client.get("/v1/bills", params={"outcome_group": "dead"}).json()
    assert dead["meta"]["total"] == 2
    # Newest death first (C-3 died June 1, C-4 died May 10).
    assert [i["number"] for i in dead["items"]] == ["C-3", "C-4"]
    # Death info attached in dead listings.
    assert dead["items"][0]["death"]["mechanism"] == "died_committee"
    assert "never brought forward" in dead["items"][0]["death"]["attribution_en"]


def test_bill_detail_serializes_death_with_kill_vote(db, client) -> None:
    _seed_bills(db)
    detail = client.get("/v1/bills/45-1/C-4").json()
    assert detail["outcome"] == "defeated_vote"
    assert detail["death"]["kill_vote_number"] == "55"
    assert detail["death"]["kill_vote_chamber"] == "house"
    assert detail["death"]["kill_vote_session"] == "45-1"
    assert "Defeated 128–152" in detail["death"]["attribution_en"]

    alive = client.get("/v1/bills/45-1/C-2").json()
    assert alive["death"] is None
    assert alive["outcome"] == "pending"


def test_bill_topic_filter_and_detail_topics(db, client) -> None:
    law, pending, dead, defeated = _seed_bills(db)
    seed_topics(db)
    housing = db.scalar(select(Topic).where(Topic.slug == "housing"))
    db.add(EntityTopic(topic_id=housing.id, entity_type="bill", entity_id=dead.id, source="alias"))
    db.commit()

    filtered = client.get("/v1/bills", params={"outcome_group": "dead", "topic": "housing"}).json()
    assert [i["number"] for i in filtered["items"]] == ["C-3"]

    nothing = client.get("/v1/bills", params={"topic": "no-such-topic"}).json()
    assert nothing["meta"]["total"] == 0

    detail = client.get("/v1/bills/45-1/C-3").json()
    assert detail["topics"] == ["Housing"]
