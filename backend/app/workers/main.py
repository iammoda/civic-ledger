"""arq worker: background jobs + scheduled ingestion.

Run with: arq app.workers.main.WorkerSettings
Replaces the former APScheduler process — cron jobs live here so one
worker process handles both queued tasks and schedules.
"""
from __future__ import annotations

from typing import Any

from arq import cron
from arq.connections import RedisSettings

from app.core.config import get_settings
from app.ingestion.run import run_sync


async def ingest_incremental(ctx: dict[str, Any]) -> None:
    await run_sync("incremental")


async def ingest_full(ctx: dict[str, Any]) -> None:
    await run_sync("full")


class WorkerSettings:
    functions = [ingest_incremental, ingest_full]
    cron_jobs = [
        # Incremental sync every 30 minutes.
        cron(ingest_incremental, minute={0, 30}),
    ]
    redis_settings = RedisSettings.from_dsn(get_settings().redis_url)
