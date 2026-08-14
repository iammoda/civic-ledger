"""Ingestion orchestrator.

- incremental: new votes/ballots since last run + current-session bills
- full: all politicians (incl. former), all bills, all votes

Every job writes an IngestionRun audit row (status, counts, errors).
"""
from __future__ import annotations

import argparse
import asyncio
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone

from app.db.session import SessionLocal
from app.ingestion.openparliament import OpenParliamentClient
from app.ingestion.stats import compute_all_stats, mark_current_session
from app.ingestion.sync import (
    SyncContext,
    sweep_session_deaths,
    sync_bills,
    sync_politicians,
    sync_votes,
)


def sweep_ended_sessions(db, ctx: SyncContext) -> int:
    """Prorogation/dissolution kills every unfinished bill: any session
    that is no longer current gets its pending bills marked dead."""
    from sqlalchemy import select

    from app.models import Bill, LegislatureSession

    mark_current_session(db)
    swept = 0
    # Federal jurisdiction only: session labels ("44-1") repeat across
    # legislatures, and ctx resolves labels within the federal jurisdiction.
    ended_sessions = db.scalars(
        select(LegislatureSession).where(
            LegislatureSession.is_current.is_(False),
            LegislatureSession.jurisdiction_id == ctx.jurisdiction.id,
        )
    ).all()
    for session in ended_sessions:
        has_pending = db.scalar(
            select(Bill.id).where(Bill.session_id == session.id, Bill.outcome == "pending").limit(1)
        )
        if has_pending is not None:
            swept += sweep_session_deaths(ctx, session.label)
    return swept


async def _audited(db, source: str, job: str, fn: Callable[[], Awaitable[int]]) -> int:
    from app.models import IngestionRun

    run = IngestionRun(source_name=source, job_name=job, status="running")
    db.add(run)
    db.commit()
    try:
        count = await fn()
        run.status = "succeeded"
        run.item_count = count
        return count
    except Exception as exc:  # noqa: BLE001 — audit then re-raise
        db.rollback()
        run.status = "failed"
        run.error_message = str(exc)[:2000]
        raise
    finally:
        run.finished_at = datetime.now(timezone.utc)
        db.commit()


async def run_sync(mode: str) -> None:
    db = SessionLocal()
    try:
        ctx = SyncContext(db)
        async with OpenParliamentClient() as client:
            if mode == "full":
                await _audited(db, "openparliament", "politicians_full",
                               lambda: sync_politicians(ctx, client, include_former=True))
                await _audited(db, "openparliament", "bills_full",
                               lambda: sync_bills(ctx, client))
                await _audited(db, "openparliament", "votes_full",
                               lambda: sync_votes(ctx, client, stop_at_existing=False))
            else:
                current = mark_current_session(db)
                session_label = current.label if current else None
                await _audited(db, "openparliament", "bills_incremental",
                               lambda: sync_bills(ctx, client, session_label=session_label))
                await _audited(db, "openparliament", "votes_incremental",
                               lambda: sync_votes(ctx, client, session_label=session_label))
        # After any sync: bury pending bills of sessions that have ended.
        sweep_ended_sessions(db, ctx)
    finally:
        db.close()


async def run_stats() -> None:
    db = SessionLocal()
    try:
        compute_all_stats(db)
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run ingestion jobs")
    parser.add_argument("--full", action="store_true", help="Run a full sync")
    parser.add_argument("--incremental", action="store_true", help="Run an incremental sync")
    parser.add_argument("--stats", action="store_true", help="Recompute derived stats")
    args = parser.parse_args()
    if args.stats:
        asyncio.run(run_stats())
        return
    mode = "full" if args.full else "incremental"
    asyncio.run(run_sync(mode))


if __name__ == "__main__":
    main()
