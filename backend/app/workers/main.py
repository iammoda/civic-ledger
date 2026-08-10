"""arq worker: background jobs + scheduled ingestion.

Run with: arq app.workers.main.WorkerSettings
One worker process handles queued tasks and cron schedules:
- incremental sync every 30 minutes
- weekly politician refresh (memberships, floor-crossings)
- nightly derived stats (attendance, party-line, dissents)
"""
from __future__ import annotations

from typing import Any

from arq import cron
from arq.connections import RedisSettings

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


class WorkerSettings:
    functions = [ingest_incremental, ingest_full, refresh_politicians, compute_stats]
    cron_jobs = [
        cron(ingest_incremental, minute={0, 30}),
        cron(compute_stats, hour={7}, minute={15}),  # nightly, 07:15 UTC
        cron(refresh_politicians, weekday=0, hour={6}, minute={0}),  # Mondays
    ]
    redis_settings = RedisSettings.from_dsn(get_settings().redis_url)
    job_timeout = 3600 * 6
