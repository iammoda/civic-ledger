"""Federal session dates: when each Parliament's sessions began and ended.

The end of a session (prorogation or dissolution) is the date every
unfinished bill on the Order Paper died — the Graveyard can't answer
"when did this die?" without it. Neither OpenParliament nor LEGISinfo
exposes session dates via API, and for *past* sessions they are fixed
historical facts, so they are seeded as data with a primary-source
citation rather than scraped.

Source: Library of Parliament, "Parliaments and Sessions" (parl.gc.ca);
prorogation/dissolution proclamations in the Canada Gazette.
"""
from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import BillDeath, Jurisdiction, LegislatureSession

# (parliament, session) -> (started_on, ended_on, how_it_ended)
# ended_on None = still sitting.
FEDERAL_SESSIONS: dict[tuple[int, int], tuple[date, date | None, str | None]] = {
    (43, 1): (date(2019, 12, 5), date(2020, 8, 18), "prorogation"),
    (43, 2): (date(2020, 9, 23), date(2021, 8, 15), "dissolution"),
    (44, 1): (date(2021, 11, 22), date(2025, 3, 23), "dissolution"),
    (45, 1): (date(2025, 5, 26), None, None),
}

# Session-end sweeps: mechanisms whose date IS the session's end date.
SWEEP_MECHANISMS = ("died_order_paper", "died_committee", "died_senate")

# By parliamentary convention, C-1 ("oaths of office") and S-1 ("railways")
# are pro forma bills: introduced ceremonially at each session's opening to
# assert each chamber's independence, never printed, never meant to pass.
# Counting them as "died" bills is noise — the Graveyard mourns real bills.
PRO_FORMA_NUMBERS = ("C-1", "S-1")


def mark_pro_forma_bills(db: Session) -> int:
    """Give ceremonial C-1/S-1 bills their own outcome (outside dead/law/
    pending groups) and drop their bill-death rows. Idempotent."""
    from app.models import Bill, Chamber

    federal_chambers = (
        select(Chamber.id)
        .join(Jurisdiction, Chamber.jurisdiction_id == Jurisdiction.id)
        .where(Jurisdiction.code == "ca")
        .scalar_subquery()
    )
    bills = db.scalars(
        select(Bill).where(Bill.number.in_(PRO_FORMA_NUMBERS), Bill.chamber_id.in_(federal_chambers))
    ).all()
    changed = 0
    for bill in bills:
        if bill.outcome != "pro_forma":
            bill.outcome = "pro_forma"
            changed += 1
        death = db.scalar(select(BillDeath).where(BillDeath.bill_id == bill.id))
        if death is not None:
            db.delete(death)
    db.commit()
    return changed


def seed_session_dates(db: Session) -> int:
    """Set started_on/ended_on/is_current on federal sessions, then backfill
    occurred_on for session-end bill deaths that were recorded before the
    end dates were known. Idempotent."""
    jurisdiction = db.scalar(select(Jurisdiction).where(Jurisdiction.code == "ca"))
    if jurisdiction is None:
        return 0

    updated = 0
    for (parliament, session_no), (started, ended, _how) in FEDERAL_SESSIONS.items():
        session = db.scalar(
            select(LegislatureSession).where(
                LegislatureSession.jurisdiction_id == jurisdiction.id,
                LegislatureSession.parliament_number == parliament,
                LegislatureSession.session_number == session_no,
            )
        )
        if session is None:
            continue
        session.started_on = started
        session.ended_on = ended
        session.is_current = ended is None

        if ended is not None:
            # Backfill: sweep deaths recorded without a date get the end date.
            deaths = db.scalars(
                select(BillDeath)
                .join(BillDeath.bill)
                .where(
                    BillDeath.occurred_on.is_(None),
                    BillDeath.mechanism.in_(SWEEP_MECHANISMS),
                )
            ).all()
            for death in deaths:
                if death.bill.session_id == session.id:
                    death.occurred_on = ended
                    updated += 1
    db.commit()
    return updated
