"""Export current-Parliament bill texts to a work directory for summarization.

Creates /tmp/civic-bills/{number}.txt (bill text, already capped at 40k chars
by ingestion) and /tmp/civic-bills/manifest.json with metadata + priority.

Usage: PYTHONPATH=backend python3 scripts/export_bill_worklist.py
"""
from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models import AnalysisResult, Bill, LegislatureSession, Vote

OUT = Path("/tmp/civic-bills")


def main() -> None:
    OUT.mkdir(exist_ok=True)
    manifest = []
    with SessionLocal() as db:
        bills = db.scalars(
            select(Bill)
            .join(LegislatureSession, Bill.session_id == LegislatureSession.id)
            .where(LegislatureSession.parliament_number == 45)
            .order_by(Bill.number)
        ).all()
        voted_bill_ids = set(
            db.scalars(select(Vote.bill_id).where(Vote.bill_id.is_not(None))).all()
        )
        summarized = set(
            db.scalars(
                select(AnalysisResult.bill_id).where(
                    AnalysisResult.analysis_type == "plain_summary",
                    AnalysisResult.status == "published",
                )
            ).all()
        )
        for bill in bills:
            has_text = bool(bill.full_text_en)
            if has_text:
                (OUT / f"{bill.number}.txt").write_text(bill.full_text_en, encoding="utf-8")
            manifest.append(
                {
                    "number": bill.number,
                    "session": "45-1",
                    "title_en": bill.title_en,
                    "short_title_en": bill.short_title_en,
                    "status_en": bill.status_en,
                    "bill_type": bill.bill_type,
                    "has_text": has_text,
                    "text_chars": len(bill.full_text_en or ""),
                    "has_votes": bill.id in voted_bill_ids,
                    "already_summarized": bill.id in summarized,
                }
            )
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    todo = [m for m in manifest if m["has_text"] and not m["already_summarized"]]
    print(f"{len(manifest)} bills; {len(todo)} to summarize; "
          f"{sum(1 for m in todo if m['has_votes'])} of those have votes")


if __name__ == "__main__":
    main()
