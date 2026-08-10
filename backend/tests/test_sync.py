"""Ingestion persistence tests: upsert idempotency, dead bills, party lines."""
from __future__ import annotations

from datetime import date

from sqlalchemy import select

from app.ingestion.sync import (
    SyncContext,
    compute_party_lines,
    outcome_from_status_code,
    stage_from_status_code,
    slugify,
    sweep_session_deaths,
    upsert_bill_from_detail,
    upsert_person_from_detail,
)
from app.models import Ballot, Bill, BillDeath, Person, PersonMembership, RepresentationEvent, Vote


POLITICIAN_DETAIL = {
    "name": "Jane Doe",
    "given_name": "Jane",
    "family_name": "Doe",
    "email": "jane.doe@parl.gc.ca",
    "image": "/media/polpics/jane.jpg",
    "links": [{"url": "https://www.ourcommons.ca/members/en/jane-doe(1)"}],
    "memberships": [
        {
            "start_date": "2021-09-20",
            "end_date": None,
            "party": {"name": {"en": "Liberal Party of Canada"}, "short_name": {"en": "Liberal"}},
            "label": {"en": "Liberal MP for Testville"},
            "riding": {"name": {"en": "Testville"}, "province": "ON", "id": 35001},
        }
    ],
}

BILL_DETAIL = {
    "session": "45-1",
    "number": "C-30",
    "legisinfo_id": 14049789,
    "introduced": "2026-04-29",
    "name": {"en": "An Act about testing", "fr": "Loi sur les tests"},
    "short_title": {"en": "Testing Act", "fr": ""},
    "status": {"en": "Law (royal assent given)"},
    "status_code": "RoyalAssentGiven",
    "law": True,
    "private_member_bill": False,
    "legisinfo_url": "https://www.parl.ca/legisinfo/en/bill/45-1/C-30",
    "text_url": "https://www.parl.ca/DocumentViewer/en/14205503",
}


def test_slugify() -> None:
    assert slugify("Bloc Québécois") == "bloc-quebecois"
    assert slugify("NDP") == "ndp"


def test_person_upsert_is_idempotent(db) -> None:
    ctx = SyncContext(db)
    upsert_person_from_detail(ctx, "jane-doe", POLITICIAN_DETAIL)
    upsert_person_from_detail(ctx, "jane-doe", POLITICIAN_DETAIL)
    db.commit()

    people = db.scalars(select(Person)).all()
    memberships = db.scalars(select(PersonMembership)).all()
    assert len(people) == 1
    assert len(memberships) == 1
    assert people[0].email == "jane.doe@parl.gc.ca"
    assert memberships[0].province_code == "ON"


def test_floor_crossing_creates_event(db) -> None:
    ctx = SyncContext(db)
    upsert_person_from_detail(ctx, "jane-doe", POLITICIAN_DETAIL)
    db.commit()

    crossed = {
        **POLITICIAN_DETAIL,
        "memberships": [
            {**POLITICIAN_DETAIL["memberships"][0], "end_date": "2026-01-10"},
            {
                "start_date": "2026-01-11",
                "end_date": None,
                "party": {"name": {"en": "Conservative Party of Canada"}, "short_name": {"en": "Conservative"}},
                "label": {"en": "Conservative MP for Testville"},
                "riding": {"name": {"en": "Testville"}, "province": "ON", "id": 35001},
            },
        ],
    }
    upsert_person_from_detail(ctx, "jane-doe", crossed)
    db.commit()

    events = db.scalars(select(RepresentationEvent)).all()
    assert len(events) == 1
    assert events[0].event_type == "floor_crossing"
    assert events[0].occurred_on == date(2026, 1, 11)


def test_bill_upsert_maps_outcome_and_is_idempotent(db) -> None:
    ctx = SyncContext(db)
    upsert_bill_from_detail(ctx, BILL_DETAIL)
    upsert_bill_from_detail(ctx, BILL_DETAIL)
    db.commit()

    bills = db.scalars(select(Bill)).all()
    assert len(bills) == 1
    assert bills[0].outcome == "enacted"
    assert bills[0].is_law is True
    assert bills[0].legisinfo_id == 14049789


def test_outcome_mapping() -> None:
    assert outcome_from_status_code("RoyalAssentGiven", law=False) == "enacted"
    assert outcome_from_status_code("DefeatedHouseAtSecondReading", law=False) == "defeated_vote"
    assert outcome_from_status_code("BillWithdrawn", law=False) == "withdrawn"
    assert outcome_from_status_code("WillNotBeProceededWith", law=False) == "not_proceeded_with"
    assert outcome_from_status_code("HouseInCommittee", law=False) == "pending"
    assert stage_from_status_code("HouseInCommittee") == "committee"
    assert stage_from_status_code("SenateAtSecondReading") == "second-reading"


def test_senate_bill_assigned_to_senate_chamber(db) -> None:
    ctx = SyncContext(db)
    bill = upsert_bill_from_detail(ctx, {**BILL_DETAIL, "number": "S-5", "law": False, "status_code": "SenateAt1stReading", "status": {"en": "At first reading in the Senate"}})
    assert bill.chamber_id == ctx.senate.id


def test_session_end_sweep_kills_pending_bills(db) -> None:
    ctx = SyncContext(db)
    pending_committee = upsert_bill_from_detail(
        ctx,
        {**BILL_DETAIL, "number": "C-99", "law": False, "status_code": "HouseInCommittee", "status": {"en": "In committee"}},
    )
    pending_plain = upsert_bill_from_detail(
        ctx,
        {**BILL_DETAIL, "number": "C-98", "law": False, "status_code": "HouseAt2ndReading", "status": {"en": "At second reading"}},
    )
    enacted = upsert_bill_from_detail(ctx, BILL_DETAIL)
    db.commit()

    killed = sweep_session_deaths(ctx, "45-1")
    assert killed == 2

    db.refresh(pending_committee)
    db.refresh(pending_plain)
    db.refresh(enacted)
    assert pending_committee.outcome == "died_committee"
    assert pending_plain.outcome == "died_order_paper"
    assert enacted.outcome == "enacted"

    deaths = {d.bill_id: d for d in db.scalars(select(BillDeath)).all()}
    assert deaths[pending_committee.id].mechanism == "died_committee"
    assert "never brought forward" in deaths[pending_committee.id].attribution_en


def test_compute_party_lines(db) -> None:
    ctx = SyncContext(db)
    session = ctx.session_for_label("45-1")
    vote = Vote(
        session_id=session.id,
        chamber_id=ctx.house.id,
        number="1",
        occurred_on=date(2026, 6, 18),
        description_en="Test division",
    )
    db.add(vote)
    db.flush()

    people = []
    for i in range(4):
        person = Person(slug=f"mp-{i}", full_name=f"MP {i}")
        db.add(person)
        db.flush()
        people.append(person)

    # 3 Liberals vote yea, 1 votes nay (the dissenter).
    for i, ballot_value in enumerate(["yea", "yea", "yea", "nay"]):
        db.add(Ballot(vote_id=vote.id, person_id=people[i].id, ballot=ballot_value, party_slug="liberal"))
    db.flush()

    compute_party_lines(db, vote)
    db.commit()

    dissenters = [b for b in db.scalars(select(Ballot)).all() if b.broke_party_line]
    assert len(dissenters) == 1
    assert dissenters[0].ballot == "nay"
