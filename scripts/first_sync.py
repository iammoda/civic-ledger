"""First live sync: current Parliament + petitions + newest expense quarter."""
from __future__ import annotations

import asyncio
import sys

sys.path.insert(0, "backend")

from app.db.session import SessionLocal  # noqa: E402
from app.ingestion.expenses import ExpensesClient, sync_expenses  # noqa: E402
from app.ingestion.openparliament import OpenParliamentClient  # noqa: E402
from app.ingestion.petitions import PetitionsClient, sync_petitions  # noqa: E402
from app.ingestion.stats import compute_all_stats  # noqa: E402
from app.ingestion.sync import SyncContext, sync_bills, sync_politicians, sync_votes  # noqa: E402
from app.services.detectors import run_all_detectors  # noqa: E402

CURRENT_SESSION = "45-1"


async def main() -> None:
    db = SessionLocal()
    try:
        ctx = SyncContext(db)
        async with OpenParliamentClient() as client:
            print("[1/6] politicians (current MPs + membership history)...", flush=True)
            n = await sync_politicians(ctx, client)
            print(f"      -> {n} politicians", flush=True)

            print(f"[2/6] bills, session {CURRENT_SESSION}...", flush=True)
            n = await sync_bills(ctx, client, session_label=CURRENT_SESSION)
            print(f"      -> {n} bills", flush=True)

            print(f"[3/6] votes + every ballot, session {CURRENT_SESSION}...", flush=True)
            n = await sync_votes(ctx, client, session_label=CURRENT_SESSION, stop_at_existing=False)
            print(f"      -> {n} votes", flush=True)

        print("[4/6] e-petitions...", flush=True)
        async with PetitionsClient() as pclient:
            n = await sync_petitions(db, pclient)
        print(f"      -> {n} petition rows", flush=True)

        print("[5/6] expenses, newest quarter...", flush=True)
        async with ExpensesClient() as eclient:
            counts = await sync_expenses(db, eclient)
        print(f"      -> {counts}", flush=True)

        print("[6/6] derived stats + integrity detectors...", flush=True)
        stats = compute_all_stats(db)
        flags = run_all_detectors(db)
        print(f"      -> {stats} stat rows; new flags: {flags}", flush=True)
        print("DONE", flush=True)
    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(main())
