"""Session dates + Graveyard hygiene: death-date backfill and pro forma bills."""
from __future__ import annotations

from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.data.sessions import mark_pro_forma_bills, seed_session_dates
from app.db.session import get_db
from app.ingestion.sync import SyncContext, sweep_session_deaths
from app.main import app
from app.models import Bill, BillDeath, LegislatureSession


@pytest.fixture()
def client(db):
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_seed_session_dates_backfills_sweep_deaths(db) -> None:
    ctx = SyncContext(db)
    session = ctx.session_for_label("44-1")
    bill = Bill(
        session_id=session.id, chamber_id=ctx.house.id, number="C-99",
        title_en="An Act that died undated", outcome="died_order_paper",
    )
    db.add(bill)
    db.flush()
    db.add(BillDeath(bill_id=bill.id, mechanism="died_order_paper", occurred_on=None))
    db.commit()

    updated = seed_session_dates(db)
    assert updated == 1
    death = db.scalar(select(BillDeath).where(BillDeath.bill_id == bill.id))
    assert death.occurred_on == date(2025, 3, 23)  # 44-1 dissolution
    session_row = db.get(LegislatureSession, session.id)
    assert session_row.ended_on == date(2025, 3, 23)
    assert session_row.is_current is False

    # Idempotent: nothing left to backfill.
    assert seed_session_dates(db) == 0

    # Deaths with a real recorded date are never overwritten.


def test_seed_session_dates_marks_current_session(db) -> None:
    ctx = SyncContext(db)
    session = ctx.session_for_label("45-1")
    db.commit()
    seed_session_dates(db)
    row = db.get(LegislatureSession, session.id)
    assert row.is_current is True and row.ended_on is None


def test_pro_forma_bills_leave_the_graveyard(db, client) -> None:
    ctx = SyncContext(db)
    session = ctx.session_for_label("44-1")
    pro_forma = Bill(
        session_id=session.id, chamber_id=ctx.house.id, number="C-1",
        title_en="An Act respecting the administration of oaths of office",
        outcome="died_order_paper",
    )
    real = Bill(
        session_id=session.id, chamber_id=ctx.house.id, number="C-45",
        title_en="A real bill that died", outcome="died_order_paper",
    )
    db.add_all([pro_forma, real])
    db.flush()
    db.add(BillDeath(bill_id=pro_forma.id, mechanism="died_order_paper"))
    db.add(BillDeath(bill_id=real.id, mechanism="died_order_paper"))
    db.commit()

    assert mark_pro_forma_bills(db) == 1
    assert db.get(Bill, pro_forma.id).outcome == "pro_forma"

    dead = client.get("/v1/bills", params={"outcome_group": "dead"}).json()
    numbers = {item["number"] for item in dead["items"]}
    assert "C-45" in numbers
    assert "C-1" not in numbers


def test_sweep_skips_pro_forma_bills(db) -> None:
    ctx = SyncContext(db)
    session = ctx.session_for_label("44-1")
    db.add(Bill(session_id=session.id, chamber_id=ctx.house.id, number="S-1",
                title_en="An Act relating to railways", outcome="pending"))
    db.add(Bill(session_id=session.id, chamber_id=ctx.house.id, number="C-77",
                title_en="Unfinished business", outcome="pending"))
    db.commit()
    seed_session_dates(db)

    swept = sweep_session_deaths(ctx, "44-1")
    assert swept == 1  # only the real bill
    bills = {b.number: b.outcome for b in db.scalars(select(Bill)).all()}
    assert bills["C-77"] == "died_order_paper"
    assert bills["S-1"] == "pending"  # untouched, marked pro_forma by the weekly job
