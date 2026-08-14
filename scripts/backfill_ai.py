"""Self-serve AI backfill: summaries + topics for bills that don't have them.

Requires ANTHROPIC_API_KEY in .env. Respects the monthly budget cap and the
cache-forever contract (published analyses are never regenerated). New bills
also get picked up automatically by the hourly worker cron once the key is
set — this script just does the whole backlog in one sitting.

Usage:
  PYTHONPATH=backend python3 scripts/backfill_ai.py --dry-run   # count + cost estimate
  PYTHONPATH=backend python3 scripts/backfill_ai.py             # run it
"""
from __future__ import annotations

import argparse
import asyncio
import sys

from sqlalchemy import select

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.llm.budget import BudgetExceededError
from app.models import AnalysisResult, Bill, LegislatureSession

# Rough per-bill cost: ~10k input tokens (40k chars) + ~1k output on the fast
# model, with one readability retry on some bills.
EST_COST_PER_BILL_USD = 0.05


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--parliament", type=int, default=45)
    args = parser.parse_args()

    settings = get_settings()

    with SessionLocal() as db:
        summarized = set(
            db.scalars(
                select(AnalysisResult.bill_id).where(
                    AnalysisResult.analysis_type == "plain_summary",
                    AnalysisResult.status.in_(["published", "blocked"]),
                )
            ).all()
        )
        bills = [
            b
            for b in db.scalars(
                select(Bill)
                .join(LegislatureSession, Bill.session_id == LegislatureSession.id)
                .where(LegislatureSession.parliament_number == args.parliament)
                .order_by(Bill.number)
            ).all()
            if b.id not in summarized
        ]

        print(f"{len(bills)} bills need summaries (parliament {args.parliament}).")
        print(f"Estimated cost: ~${len(bills) * EST_COST_PER_BILL_USD:.2f} "
              f"(budget cap: ${settings.llm_monthly_budget_usd:.0f}/month, enforced per call)")
        if args.dry_run:
            for bill in bills[:20]:
                print(f"  {bill.number} — {(bill.short_title_en or bill.title_en)[:70]}")
            if len(bills) > 20:
                print(f"  … and {len(bills) - 20} more")
            return 0

        if not settings.anthropic_api_key:
            print("ANTHROPIC_API_KEY is not set in .env — add it first.", file=sys.stderr)
            return 1

        from app.llm.analyses import analyze_bill, tag_bill_topics

        done = 0
        for bill in bills:
            try:
                asyncio.run(analyze_bill(db, bill.id))
                asyncio.run(tag_bill_topics(db, bill.id))
                done += 1
                print(f"  {bill.number} ✓  ({done}/{len(bills)})")
            except BudgetExceededError:
                print("Monthly budget cap reached — stopping. Re-run next month or raise the cap.")
                break
            except Exception as exc:  # noqa: BLE001 — keep going through the backlog
                print(f"  {bill.number} FAILED: {exc}", file=sys.stderr)
        print(f"Done: {done} of {len(bills)}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
