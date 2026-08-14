"""Insert a bill plain-language summary produced in-session (no API key).

Runs the SAME quality gates as the LLM pipeline: readability grade <= 8.5
target with a hard ceiling of 11, published through the same AnalysisResult
table with citations, plus optional topic tags (validated against the topics
table) and an omnibus flag.

Usage:
  PYTHONPATH=backend python3 scripts/insert_summary.py payload.json [--force]

Payload JSON:
{
  "number": "C-30", "session": "45-1",
  "one_sentence": "...",
  "what_it_does": ["..."], "who_it_affects": ["..."], "what_changes": ["..."],
  "detailed_summary": "...",
  "confidence": 0.9,
  "topics": ["housing", "taxes"],          # optional, must match topic slugs
  "is_omnibus": false                        # optional
}

Exit codes: 0 ok · 2 readability failure (rewrite simpler and retry) · 3 other error.
"""
from __future__ import annotations

import json
import sys

from sqlalchemy import select

from app.db.session import SessionLocal
from app.llm.readability import HARD_CEILING, reading_grade
from app.models import AnalysisResult, Bill, EntityTopic, LegislatureSession, Topic

TARGET_GRADE = 8.5


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    force = "--force" in sys.argv
    if not args:
        print("usage: insert_summary.py payload.json [--force]", file=sys.stderr)
        return 3
    payload = json.loads(open(args[0], encoding="utf-8").read())

    required = ["number", "session", "one_sentence", "what_it_does", "who_it_affects", "what_changes", "detailed_summary"]
    missing = [k for k in required if not payload.get(k)]
    if missing:
        print(f"missing fields: {missing}", file=sys.stderr)
        return 3

    # Readability gate — identical spirit to the pipeline: the user-facing
    # prose must be plain. Grade > target fails so the writer simplifies.
    prose = " ".join(
        [payload["one_sentence"]]
        + payload["what_it_does"]
        + payload["who_it_affects"]
        + payload["what_changes"]
        + [payload["detailed_summary"]]
    )
    grade = reading_grade(prose)
    if grade > TARGET_GRADE:
        verdict = "HARD FAIL" if grade > HARD_CEILING else "too complex"
        print(f"READABILITY {verdict}: grade {grade:.1f} > {TARGET_GRADE}. Rewrite simpler (shorter sentences, everyday words).", file=sys.stderr)
        return 2

    parliament, _, session_no = payload["session"].partition("-")
    with SessionLocal() as db:
        bill = db.scalar(
            select(Bill)
            .join(LegislatureSession, Bill.session_id == LegislatureSession.id)
            .where(
                Bill.number == payload["number"],
                LegislatureSession.parliament_number == int(parliament),
                LegislatureSession.session_number == int(session_no),
            )
        )
        if bill is None:
            print(f"bill not found: {payload['session']}/{payload['number']}", file=sys.stderr)
            return 3

        existing = db.scalar(
            select(AnalysisResult).where(
                AnalysisResult.bill_id == bill.id, AnalysisResult.analysis_type == "plain_summary"
            )
        )
        if existing is not None and existing.status == "published" and not force:
            print(f"{bill.number}: already summarized (use --force to overwrite)")
            return 0

        citations = []
        if bill.legisinfo_url:
            citations.append({"label": "LEGISinfo (official bill record)", "url": bill.legisinfo_url})
        if bill.text_url:
            citations.append({"label": "Full bill text (parl.ca)", "url": bill.text_url})

        result = existing or AnalysisResult(bill_id=bill.id, analysis_type="plain_summary")
        result.status = "published"
        result.confidence_score = float(payload.get("confidence", 0.85))
        result.citations = citations
        result.model_name = "claude-session-grounded"
        result.payload = {
            "one_sentence": payload["one_sentence"],
            "what_it_does": payload["what_it_does"],
            "who_it_affects": payload["who_it_affects"],
            "what_changes": payload["what_changes"],
            "detailed_summary": payload["detailed_summary"],
            "reading_grade": round(grade, 2),
            "had_bill_text": True,
        }
        result.blocked_reason = None
        db.add(result)

        # Topic tags (validated against the canonical topic list).
        applied_topics = []
        for slug in payload.get("topics", []) or []:
            topic = db.scalar(select(Topic).where(Topic.slug == slug))
            if topic is None:
                print(f"  skipping unknown topic: {slug}", file=sys.stderr)
                continue
            link = db.scalar(
                select(EntityTopic).where(
                    EntityTopic.topic_id == topic.id,
                    EntityTopic.entity_type == "bill",
                    EntityTopic.entity_id == bill.id,
                )
            )
            if link is None:
                db.add(EntityTopic(topic_id=topic.id, entity_type="bill", entity_id=bill.id, source="session"))
            applied_topics.append(slug)

        if payload.get("is_omnibus"):
            bill.is_omnibus = True

        db.commit()
        print(f"{bill.number}: published (grade {grade:.1f}; topics: {', '.join(applied_topics) or 'none'})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
