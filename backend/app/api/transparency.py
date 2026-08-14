"""Public transparency endpoints: live source freshness + coverage scorecard.

No auth: the whole point is that anyone can audit what this platform knows,
when it learned it, and what it cannot know.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.data.transparency import HONEST_LIMITS, SCORECARD
from app.db.session import get_db
from app.models import (
    Ballot,
    Chamber,
    IngestionRun,
    Jurisdiction,
    Meeting,
    Motion,
    Person,
    Vote,
)

router = APIRouter(prefix="/transparency", tags=["transparency"])


@router.get("/status")
def source_status(db: Session = Depends(get_db)) -> dict:
    """Latest run per ingestion job: what synced, when, and whether it worked."""
    latest_ids = (
        select(func.max(IngestionRun.id))
        .group_by(IngestionRun.source_name, IngestionRun.job_name)
        .scalar_subquery()
    )
    runs = db.scalars(
        select(IngestionRun).where(IngestionRun.id.in_(latest_ids)).order_by(IngestionRun.source_name)
    ).all()
    return {
        "jobs": [
            {
                "source": run.source_name,
                "job": run.job_name,
                "status": run.status,
                "started_at": run.started_at.isoformat() if run.started_at else None,
                "finished_at": run.finished_at.isoformat() if run.finished_at else None,
                "item_count": run.item_count,
                # Errors are public too — a failed sync is a data gap.
                "error": (run.error_message or None),
            }
            for run in runs
        ]
    }


def _live_counts(db: Session) -> dict[str, dict[str, int]]:
    """Per-jurisdiction row counts so the scorecard shows real numbers."""
    counts: dict[str, dict[str, int]] = {}
    rows = db.execute(
        select(Jurisdiction.code, func.count(func.distinct(Person.id)))
        .join(Chamber, Chamber.jurisdiction_id == Jurisdiction.id)
        .join(Person, Person.chamber_id == Chamber.id)
        .group_by(Jurisdiction.code)
    ).all()
    for code, n in rows:
        counts.setdefault(code, {})["people"] = n
    rows = db.execute(
        select(Jurisdiction.code, func.count(Vote.id), func.coalesce(func.sum(Vote.yea_total + Vote.nay_total), 0))
        .join(Chamber, Chamber.jurisdiction_id == Jurisdiction.id)
        .join(Vote, Vote.chamber_id == Chamber.id)
        .group_by(Jurisdiction.code)
    ).all()
    for code, votes, ballots in rows:
        counts.setdefault(code, {})["votes"] = votes
        counts.setdefault(code, {})["ballots"] = int(ballots)
    rows = db.execute(
        select(Jurisdiction.code, func.count(Meeting.id))
        .join(Chamber, Chamber.jurisdiction_id == Jurisdiction.id)
        .join(Meeting, Meeting.chamber_id == Chamber.id)
        .where(Meeting.minutes_parsed.is_(True))
        .group_by(Jurisdiction.code)
    ).all()
    for code, n in rows:
        counts.setdefault(code, {})["meetings"] = n
    rows = db.execute(
        select(Jurisdiction.code, func.count(Motion.id))
        .join(Chamber, Chamber.jurisdiction_id == Jurisdiction.id)
        .join(Meeting, Meeting.chamber_id == Chamber.id)
        .join(Motion, Motion.meeting_id == Meeting.id)
        .group_by(Jurisdiction.code)
    ).all()
    for code, n in rows:
        counts.setdefault(code, {})["motions"] = n
    return counts


@router.get("/coverage")
def coverage(db: Session = Depends(get_db)) -> dict:
    live = _live_counts(db)
    entries = []
    for entry in SCORECARD:
        code = entry.get("jurisdiction_code")
        entries.append({**entry, "live": live.get(code, {}) if code else {}})
    return {"scorecard": entries, "honest_limits": HONEST_LIMITS}
