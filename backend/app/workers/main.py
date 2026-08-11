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
    from app.llm.analyses import analyze_bill, normalize_vote, tag_bill_topics, tag_petition_topics
    from app.llm.budget import BudgetExceededError
    from app.models import AnalysisResult, Bill, EntityTopic, LegislatureSession, Petition, Vote

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

        # Untagged petitions: modest hourly batch (alias pass is free).
        tagged_petition_ids = select(EntityTopic.entity_id).where(
            EntityTopic.entity_type == "petition", EntityTopic.source == "llm"
        )
        petitions = db.scalars(
            select(Petition)
            .where(Petition.id.not_in(tagged_petition_ids))
            .order_by(Petition.id.desc())
            .limit(20)
        ).all()

        try:
            for vote in votes:
                await normalize_vote(db, vote.id)
            for bill in bills:
                await analyze_bill(db, bill.id)
                await tag_bill_topics(db, bill.id)
            for petition in petitions:
                await tag_petition_topics(db, petition.id)
        except BudgetExceededError:
            return  # Hard cap reached; resume next month.
    finally:
        db.close()


async def sync_petitions_job(ctx: dict[str, Any]) -> None:
    """Daily e-petitions sync (open sweep + recent pages + prayer texts)."""
    from datetime import datetime, timezone

    from app.db.session import SessionLocal
    from app.ingestion.petitions import PetitionsClient, sync_petitions
    from app.models import IngestionRun

    db = SessionLocal()
    try:
        run = IngestionRun(source_name="ourcommons_petitions", job_name="petitions_sync", status="running")
        db.add(run)
        db.commit()
        try:
            async with PetitionsClient() as client:
                run.item_count = await sync_petitions(db, client)
            run.status = "succeeded"
        except Exception as exc:  # noqa: BLE001
            db.rollback()
            run.status = "failed"
            run.error_message = str(exc)[:2000]
            raise
        finally:
            run.finished_at = datetime.now(timezone.utc)
            db.commit()
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
        await embed_pending(db, entity_type="petition")
    finally:
        db.close()


async def sync_influence_job(ctx: dict[str, Any]) -> None:
    """Weekly: lobbying communications + contributions exports (config URLs).
    WAF-blocked or empty downloads fail the audit row honestly."""
    from datetime import datetime, timezone

    from app.core.config import get_settings
    from app.db.session import SessionLocal
    from app.ingestion.influence import download_export, sync_contributions, sync_lobby_communications
    from app.models import IngestionRun

    settings = get_settings()
    db = SessionLocal()
    try:
        for source, url, sync_fn in (
            ("lobby_registry", settings.lobby_export_url, sync_lobby_communications),
            ("elections_canada", settings.contributions_export_url, sync_contributions),
        ):
            if not url:
                continue
            run = IngestionRun(source_name=source, job_name=f"{source}_sync", status="running")
            db.add(run)
            db.commit()
            try:
                csv_text = await download_export(url)
                if csv_text is None:
                    raise RuntimeError(f"Download failed or empty: {url}")
                run.item_count = sync_fn(db, csv_text)
                run.status = "succeeded"
            except Exception as exc:  # noqa: BLE001
                db.rollback()
                run.status = "failed"
                run.error_message = str(exc)[:2000]
            finally:
                run.finished_at = datetime.now(timezone.utc)
                db.commit()
    finally:
        db.close()


async def run_detectors_job(ctx: dict[str, Any]) -> None:
    """Nightly integrity detectors -> pending_review flags."""
    from app.db.session import SessionLocal
    from app.services.detectors import run_all_detectors

    db = SessionLocal()
    try:
        run_all_detectors(db)
    finally:
        db.close()


async def match_notifications_job(ctx: dict[str, Any]) -> None:
    """Hourly: follows x new events -> in-app notifications (deduped)."""
    from app.db.session import SessionLocal
    from app.services.notifications import match_notifications

    db = SessionLocal()
    try:
        match_notifications(db)
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
        sync_petitions_job,
        sync_influence_job,
        run_detectors_job,
        match_notifications_job,
    ]
    cron_jobs = [
        cron(ingest_incremental, minute={0, 30}),
        cron(analyze_new_content, minute={45}),  # hourly eager pass
        cron(embed_new_content, minute={50}),  # hourly, after analysis
        cron(match_notifications_job, minute={55}),  # hourly, after content lands
        cron(sync_petitions_job, hour={5}, minute={30}),  # daily 05:30 UTC
        cron(compute_stats, hour={7}, minute={15}),  # nightly, 07:15 UTC
        cron(run_detectors_job, hour={8}, minute={0}),  # nightly, after stats
        cron(refresh_politicians, weekday=0, hour={6}, minute={0}),  # Mondays
        cron(sync_influence_job, weekday=1, hour={4}, minute={0}),  # Tuesdays
    ]
    redis_settings = RedisSettings.from_dsn(get_settings().redis_url)
    job_timeout = 3600 * 6
