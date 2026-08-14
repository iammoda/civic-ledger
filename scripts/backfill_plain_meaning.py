"""Regenerate Vote.plain_meaning_en with the bill-aware templates.

Only touches votes the deterministic heuristics can classify (free — no LLM).
Votes whose direction came from the LLM keep their existing sentence.

Usage:
  PYTHONPATH=backend python3 scripts/backfill_plain_meaning.py [--dry-run]
"""
from __future__ import annotations

import argparse
import sys

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.db.session import SessionLocal
from app.llm.analyses import _heuristic_plain_meaning, heuristic_vote_direction
from app.models import Bill, Vote


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Print changes without writing")
    args = parser.parse_args()

    updated = 0
    skipped = 0
    with SessionLocal() as db:
        votes = db.scalars(select(Vote).options(selectinload(Vote.chamber))).all()
        for vote in votes:
            effect = heuristic_vote_direction(vote.description_en or "")
            if effect is None:
                skipped += 1  # LLM-classified or unknown: leave as-is.
                continue
            bill = db.get(Bill, vote.bill_id) if vote.bill_id else None
            chamber_slug = vote.chamber.slug if vote.chamber is not None else "house"
            meaning = _heuristic_plain_meaning(vote, effect, bill=bill, chamber_slug=chamber_slug)
            if meaning != vote.plain_meaning_en or vote.yea_effect != effect:
                if args.dry_run:
                    print(f"Vote {vote.number}: {meaning}")
                else:
                    vote.yea_effect = effect
                    vote.plain_meaning_en = meaning
                updated += 1
        if not args.dry_run:
            db.commit()

    print(f"{'Would update' if args.dry_run else 'Updated'} {updated} votes; left {skipped} untouched.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
