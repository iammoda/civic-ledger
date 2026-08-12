"""Historical Parliament ingestion: bills + votes + every ballot for the
given sessions, newest first. Fresh session per step so failures isolate;
fully resumable (upserts skip existing ballots)."""
from __future__ import annotations

import asyncio
import sys

sys.path.insert(0, "backend")

from app.db.session import SessionLocal  # noqa: E402
from app.ingestion.openparliament import OpenParliamentClient  # noqa: E402
from app.ingestion.sync import SyncContext, sync_bills, sync_votes  # noqa: E402

SESSIONS = ["44-1", "43-2", "43-1"]


async def main() -> None:
    async with OpenParliamentClient() as client:
        for label in SESSIONS:
            for step, runner in (
                ("bills", lambda ctx: sync_bills(ctx, client, session_label=label)),
                ("votes", lambda ctx: sync_votes(ctx, client, session_label=label, stop_at_existing=False)),
            ):
                db = SessionLocal()
                try:
                    ctx = SyncContext(db)
                    count = await runner(ctx)
                    print(f"  {label} {step}: {count}", flush=True)
                except Exception as exc:  # noqa: BLE001
                    db.rollback()
                    print(f"  {label} {step}: FAILED {exc}", flush=True)
                finally:
                    db.close()
    print("HISTORY DONE", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
