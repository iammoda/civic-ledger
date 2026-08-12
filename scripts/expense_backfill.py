"""Resumable expense backfill: all discovered quarters, oldest failures
retried safely. Each quarter gets a fresh session so one failure can never
cascade (the bug that killed the first run: no rollback -> every later
quarter failed with 'invalid transaction')."""
from __future__ import annotations

import asyncio
import sys

sys.path.insert(0, "backend")

from app.db.session import SessionLocal  # noqa: E402
from app.ingestion.expenses import ExpensesClient, discover_quarters, sync_quarter  # noqa: E402


async def main() -> None:
    async with ExpensesClient() as client:
        html = await client.get_text("/ProactiveDisclosure/en/members")
        quarters = discover_quarters(html or "")
        print(f"backfilling {len(quarters)} quarters: {quarters}", flush=True)
        for fiscal_year, quarter in quarters:
            db = SessionLocal()  # Fresh session per quarter: failures isolate.
            try:
                counts = await sync_quarter(db, client, fiscal_year=fiscal_year, quarter=quarter)
                print(f"  {fiscal_year} Q{quarter}: {counts}", flush=True)
            except Exception as exc:  # noqa: BLE001
                db.rollback()
                print(f"  {fiscal_year} Q{quarter}: FAILED {exc}", flush=True)
            finally:
                db.close()
    print("BACKFILL DONE", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
