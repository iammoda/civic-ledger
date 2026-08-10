"""arq worker: background jobs + scheduled ingestion + analysis.

Run with: arq app.workers.main.WorkerSettings

Schedules:
- incremental data sync every 30 minutes
- eager analysis of new/current-session content hourly (summaries, vote
  direction, topic tags) — everything a typical user touches is instant
- nightly derived stats; weekly politician refresh

Lazy jobs (enqueued on first page view): analyze_bill_job, etc. Cached
forever once published, so each item is paid for at most once.
"""
from __future__ import annotations

from typing import Any

from arq import cron
from arq.connections import RedisSettings
from sqlalchemy import select

from app.core.config import get_settings
from app.ingestion.run import run_stats, run_sync


async def ingest_incremental(ctx: dict[str, Any]) -> None:
    await run_sync("incremental")


async def ingest_full(ctx: dict[str, Any]) -> None:
    await run_sync("full")


async def refresh_politicians(ctx: dict[str, Any]) -> None:
    from app.db.session import SessionLocal
    from app.ingestion.openparliament import OpenParliamentClient
    from app.ingestion.sync import SyncContext, sync_politicians

    db = SessionLocal()
    try:
        sync_ctx = SyncContext(db)
        async with OpenParliamentClient() as client:
            await sync_politicians(sync_ctx, client)
    finally:
        db.close()


async def compute_stats(ctx: dict[str, Any]) -> None:
    await run_stats()


# --- Analysis jobs (lazy engine + eager cron) ---


async def analyze_bill_job(ctx: dict[str, Any], bill_id: int) -> None:
    from app.db.session import SessionLocal
    from app.llm.analyses import analyze_bill, tag_bill_topics

    db = SessionLocal()
    try:
        await analyze_bill(db, bill_id)
        await tag_bill_topics(db, bill_id)
    finally:
        db.close()


async def normalize_vote_job(ctx: dict[str, Any], vote_id: int) -> None:
    from app.db.session import SessionLocal
    from app.llm.analyses import normalize_vote

    db = SessionLocal()
    try:
        await normalize_vote(db, vote_id)
    finally:
        db.close()


async def analyze_new_content(ctx: dict[str, Any]) -> None:
    """Eager pass: current-session content gets analysis before anyone asks.

    Batch-limited per run so a backlog can never stampede the budget —
    the monthly cap in ensure_budget() is the hard stop either way.
    """
    from app.data.topics import seed_topics
    from app.db.session import SessionLocal
    from app.llm.analyses import analyze_bill, normalize_vote, tag_bill_topics
    from app.llm.budget import BudgetExceededError
    from app.models import AnalysisResult, Bill, LegislatureSession, Vote

    db = SessionLocal()
    try:
        seed_topics(db)
        current = db.scalar(select(LegislatureSession).where(LegislatureSession.is_current.is_(True)))
        if current is None:
            return

        # Vote direction: heuristics are free — run generously.
        votes = db.scalars(
            select(Vote)
            .where(Vote.session_id == current.id, Vote.yea_effect.is_(None))
            .order_by(Vote.occurred_on.desc())
            .limit(200)
        ).all()
        # Bills lacking a published summary: modest hourly batch.
        analyzed_bill_ids = select(AnalysisResult.bill_id).where(
            AnalysisResult.analysis_type == "plain_summary",
            AnalysisResult.status.in_(["published", "blocked"]),
        )
        bills = db.scalars(
            select(Bill)
            .where(Bill.session_id == current.id, Bill.id.not_in(analyzed_bill_ids))
            .order_by(Bill.introduced_on.desc().nullslast())
            .limit(10)
        ).all()

        try:
            for vote in votes:
                await normalize_vote(db, vote.id)
            for bill in bills:
                await analyze_bill(db, bill.id)
                await tag_bill_topics(db, bill.id)
        except BudgetExceededError:
            return  # Hard cap reached; resume next month.
    finally:
        db.close()


async def embed_new_content(ctx: dict[str, Any]) -> None:
    """Embed new/changed bills and votes for hybrid search + Ask retrieval."""
    from app.db.session import SessionLocal
    from app.llm.embeddings import embed_pending

    db = SessionLocal()
    try:
        await embed_pending(db, entity_type="bill")
        await embed_pending(db, entity_type="vote")
    finally:
        db.close()


class WorkerSettings:
    functions = [
        ingest_incremental,
        ingest_full,
        refresh_politicians,
        compute_stats,
        analyze_bill_job,
        normalize_vote_job,
        analyze_new_content,
        embed_new_content,
    ]
    cron_jobs = [
        cron(ingest_incremental, minute={0, 30}),
        cron(analyze_new_content, minute={45}),  # hourly eager pass
        cron(embed_new_content, minute={50}),  # hourly, after analysis
        cron(compute_stats, hour={7}, minute={15}),  # nightly, 07:15 UTC
        cron(refresh_politicians, weekday=0, hour={6}, minute={0}),  # Mondays
    ]
    redis_settings = RedisSettings.from_dsn(get_settings().redis_url)
    job_timeout = 3600 * 6
