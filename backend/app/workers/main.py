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
    """Weekly: MPs + committees + memberships + cabinet roles + glossary."""
    from app.data.glossary import seed_glossary
    from app.db.session import SessionLocal
    from app.ingestion.committee_members import sync_committee_memberships
    from app.ingestion.ministry import fetch_ministries_html, sync_ministers
    from app.ingestion.openparliament import OpenParliamentClient
    from app.ingestion.sync import SyncContext, sync_committees, sync_politicians

    db = SessionLocal()
    try:
        sync_ctx = SyncContext(db)
        async with OpenParliamentClient() as client:
            await sync_politicians(sync_ctx, client)
            await sync_committees(sync_ctx, client)
        await sync_committee_memberships(db)
        html = await fetch_ministries_html()
        if html:
            sync_ministers(db, html)
        seed_glossary(db)
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


async def profile_lobby_orgs_job(ctx: dict[str, Any], org_names: list[str]) -> None:
    """Lazy: one-line 'what is this org' blurbs for lobbying clients."""
    from app.db.session import SessionLocal
    from app.llm.budget import BudgetExceededError
    from app.llm.org_profiles import profile_org

    db = SessionLocal()
    try:
        for name in org_names[:12]:  # Cap per job; the money page enqueues top clients only.
            try:
                await profile_org(db, name)
            except BudgetExceededError:
                return
    finally:
        db.close()


async def analyze_new_content(ctx: dict[str, Any]) -> None:
    """Eager pass: current-session content gets analysis before anyone asks.

    Batch-limited per run so a backlog can never stampede the budget —
    the monthly cap in ensure_budget() is the hard stop either way.
    """
    from app.data.topics import seed_topics
    from app.db.session import SessionLocal
    from app.llm.analyses import analyze_bill, normalize_vote, tag_bill_topics, tag_motion_topics, tag_petition_topics
    from app.llm.budget import BudgetExceededError
    from app.models import AnalysisResult, Bill, EntityTopic, Jurisdiction, LegislatureSession, Motion, Petition, Vote

    db = SessionLocal()
    try:
        seed_topics(db)
        # Federal current session only: with multiple legislatures in the DB
        # there are several is_current sessions; LLM spend stays scoped to
        # the federal record until other levels get an explicit budget.
        current = db.scalar(
            select(LegislatureSession)
            .join(Jurisdiction, LegislatureSession.jurisdiction_id == Jurisdiction.id)
            .where(
                LegislatureSession.is_current.is_(True),
                Jurisdiction.code == get_settings().default_jurisdiction,
            )
        )
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

        # Untagged municipal motions: alias-only pass, zero LLM cost.
        tagged_motion_ids = select(EntityTopic.entity_id).where(EntityTopic.entity_type == "motion")
        motions = db.scalars(
            select(Motion)
            .where(Motion.id.not_in(tagged_motion_ids))
            .order_by(Motion.id.desc())
            .limit(500)
        ).all()
        for motion in motions:
            tag_motion_topics(db, motion.id)

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


async def enrich_bills_job(ctx: dict[str, Any]) -> None:
    """Hourly Tier-0 enrichment: official LoP summaries + full bill text."""
    from app.db.session import SessionLocal
    from app.ingestion.enrich import enrich_bills

    db = SessionLocal()
    try:
        await enrich_bills(db, limit=100)
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
        await embed_pending(db, entity_type="motion")
    finally:
        db.close()


async def sync_influence_job(ctx: dict[str, Any]) -> None:
    """Weekly: lobbying communications + contributions. Imports-dir files
    win over HTTP (lobbycanada is Cloudflare-walled for scripts)."""
    from datetime import datetime, timezone

    from app.core.config import get_settings
    from app.db.session import SessionLocal
    from app.ingestion.influence import (
        download_bytes,
        download_to_file,
        sync_contributions_file,
        sync_lobby_communications,
    )
    from app.models import IngestionRun

    settings = get_settings()
    db = SessionLocal()
    try:
        # --- Registry of Lobbyists (relational zip) ---
        if settings.lobby_export_url:
            run = IngestionRun(source_name="lobby_registry", job_name="lobby_registry_sync", status="running")
            db.add(run)
            db.commit()
            try:
                zip_bytes = await download_bytes(settings.lobby_export_url)
                if zip_bytes is None:
                    raise RuntimeError(
                        "Download failed (Cloudflare?). Drop the zip in "
                        f"{settings.imports_dir} and re-run."
                    )
                run.item_count = sync_lobby_communications(db, zip_bytes)
                run.status = "succeeded"
            except Exception as exc:  # noqa: BLE001
                db.rollback()
                run.status = "failed"
                run.error_message = str(exc)[:2000]
            finally:
                run.finished_at = datetime.now(timezone.utc)
                db.commit()

        # --- Elections Canada contributions (streamed) ---
        if settings.contributions_export_url:
            run = IngestionRun(source_name="elections_canada", job_name="contributions_sync", status="running")
            db.add(run)
            db.commit()
            try:
                path = await download_to_file(settings.contributions_export_url)
                if path is None:
                    raise RuntimeError(f"Download failed: {settings.contributions_export_url}")
                run.item_count = sync_contributions_file(db, path)
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


async def sync_expenses_job(ctx: dict[str, Any], quarters: list | None = None) -> None:
    """Weekly: MP expense summaries + line items (current quarter by default;
    pass explicit [(year, quarter), ...] for backfill runs)."""
    from datetime import datetime, timezone

    from app.db.session import SessionLocal
    from app.ingestion.expenses import ExpensesClient, sync_expenses
    from app.models import IngestionRun

    db = SessionLocal()
    try:
        run = IngestionRun(source_name="proactive_disclosure", job_name="expenses_sync", status="running")
        db.add(run)
        db.commit()
        try:
            async with ExpensesClient() as client:
                quarter_tuples = [tuple(q) for q in quarters] if quarters else None
                counts = await sync_expenses(db, client, quarters=quarter_tuples)
            run.item_count = counts["summaries"] + counts["items"]
            run.metadata_json = counts
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


async def sync_representatives_job(ctx: dict[str, Any]) -> None:
    """Weekly: provincial MPPs/MLAs + municipal councillors/mayors from the
    Represent API (all ~120 sets). Rosters change slowly; weekly is plenty."""
    from datetime import datetime, timezone

    from app.db.session import SessionLocal
    from app.ingestion.represent_people import RepresentClient, sync_represent_people
    from app.models import IngestionRun

    db = SessionLocal()
    try:
        run = IngestionRun(source_name="represent", job_name="representatives_sync", status="running")
        db.add(run)
        db.commit()
        try:
            async with RepresentClient() as client:
                counts = await sync_represent_people(db, client)
            run.item_count = counts["people"]
            run.metadata_json = counts
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


async def sync_ontario_job(ctx: dict[str, Any]) -> None:
    """Nightly: Ontario bills + division votes + MPP ballots from ola.org."""
    from datetime import datetime, timezone

    from app.db.session import SessionLocal
    from app.ingestion.ontario import OntarioClient, sync_ontario
    from app.ingestion.stats import mark_current_session
    from app.models import IngestionRun

    db = SessionLocal()
    try:
        run = IngestionRun(source_name="ola", job_name="ontario_sync", status="running")
        db.add(run)
        db.commit()
        try:
            async with OntarioClient() as client:
                counts = await sync_ontario(db, client)
            mark_current_session(db)
            run.item_count = counts["bills"] + counts["votes"]
            run.metadata_json = counts
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


async def sync_municipal_job(ctx: dict[str, Any], backfill: bool = False) -> None:
    """Nightly: municipal council/committee minutes via eScribe — attendance,
    motions, per-member votes, conflict declarations. backfill=True re-syncs
    each tenant from its council-term start."""
    from datetime import datetime, timezone

    from app.db.session import SessionLocal
    from app.ingestion.escribe import sync_all_escribe
    from app.models import IngestionRun

    db = SessionLocal()
    try:
        run = IngestionRun(source_name="escribe", job_name="municipal_sync", status="running")
        db.add(run)
        db.commit()
        try:
            results = await sync_all_escribe(db, backfill=backfill)
            run.item_count = sum(
                c.get("meetings", 0) + c.get("motions", 0) for c in results.values()
            )
            run.metadata_json = results
            run.status = "failed" if all("error" in c for c in results.values()) else "succeeded"
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


async def sync_opendata_votes_job(ctx: dict[str, Any]) -> None:
    """Weekly: full per-member council voting records for the two cities
    that publish them (Toronto CKAN, Vancouver Open Data)."""
    from datetime import datetime, timezone

    from app.db.session import SessionLocal
    from app.ingestion.toronto_votes import TorontoClient, sync_toronto_votes
    from app.ingestion.vancouver_votes import TERM_START, VancouverClient, sync_vancouver_votes
    from app.models import IngestionRun

    db = SessionLocal()
    try:
        run = IngestionRun(source_name="municipal_opendata", job_name="opendata_votes_sync", status="running")
        db.add(run)
        db.commit()
        results: dict[str, Any] = {}
        try:
            async with TorontoClient() as client:
                rows = await client.iter_rows()
            results["toronto"] = sync_toronto_votes(db, rows)
            async with VancouverClient() as client:
                van_rows = await client.fetch_rows(TERM_START)
            results["vancouver"] = sync_vancouver_votes(db, van_rows)
            run.item_count = sum(r.get("votes", 0) for r in results.values())
            run.metadata_json = results
            run.status = "succeeded"
        except Exception as exc:  # noqa: BLE001
            db.rollback()
            run.status = "failed"
            run.metadata_json = results or None
            run.error_message = str(exc)[:2000]
            raise
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


class WorkerSettings:
    functions = [
        ingest_incremental,
        ingest_full,
        refresh_politicians,
        compute_stats,
        analyze_bill_job,
        normalize_vote_job,
        profile_lobby_orgs_job,
        analyze_new_content,
        enrich_bills_job,
        embed_new_content,
        sync_petitions_job,
        sync_influence_job,
        sync_expenses_job,
        sync_representatives_job,
        sync_ontario_job,
        sync_municipal_job,
        sync_opendata_votes_job,
        run_detectors_job,
    ]
    cron_jobs = [
        cron(ingest_incremental, minute={0, 30}),
        cron(analyze_new_content, minute={45}),  # hourly eager pass
        cron(enrich_bills_job, minute={40}),  # hourly Tier-0 enrichment
        cron(embed_new_content, minute={50}),  # hourly, after analysis
        cron(sync_petitions_job, hour={5}, minute={30}),  # daily 05:30 UTC
        cron(compute_stats, hour={7}, minute={15}),  # nightly, 07:15 UTC
        cron(run_detectors_job, hour={8}, minute={0}),  # nightly, after stats
        cron(refresh_politicians, weekday=0, hour={6}, minute={0}),  # Mondays
        cron(sync_influence_job, weekday=1, hour={4}, minute={0}),  # Tuesdays
        cron(sync_expenses_job, weekday=2, hour={4}, minute={0}),  # Wednesdays
        cron(sync_representatives_job, weekday=3, hour={4}, minute={0}),  # Thursdays
        cron(sync_ontario_job, hour={6}, minute={30}),  # nightly 06:30 UTC
        cron(sync_municipal_job, hour={9}, minute={0}),  # nightly 09:00 UTC
        cron(sync_opendata_votes_job, weekday=4, hour={4}, minute={0}),  # Fridays
    ]
    redis_settings = RedisSettings.from_dsn(get_settings().redis_url)
    job_timeout = 3600 * 6
