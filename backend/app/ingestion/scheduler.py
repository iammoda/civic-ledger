from __future__ import annotations

import asyncio

from apscheduler.schedulers.blocking import BlockingScheduler

from app.ingestion.run import run_sync


def start_scheduler() -> None:
    scheduler = BlockingScheduler()
    scheduler.add_job(lambda: asyncio.run(run_sync("incremental")), "interval", minutes=30)
    scheduler.start()


if __name__ == "__main__":
    start_scheduler()
