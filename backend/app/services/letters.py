"""Contact-your-MP letters that cite the MP's actual voting record.

The letter skeleton is deterministic (facts inserted verbatim from the
database); Claude optionally polishes tone/flow when configured, but the
cited facts are never model-generated.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.behavior import _ballot_effect
from app.core.config import get_settings
from app.llm.base import LLMClient
from app.llm.budget import BudgetExceededError, ensure_budget, record_usage
from app.models import Ballot, Bill, Jurisdiction, LegislatureSession, Person, PersonMembership, Vote


@dataclass(slots=True)
class BallotCitation:
    vote_number: str
    session: str
    occurred_on: date
    description_en: str
    effect: str | None  # advanced | blocked | None
    ballot: str


@dataclass(slots=True)
class LetterResult:
    letter_text: str
    mp_name: str
    mp_email: str | None
    riding: str | None
    citations: list[BallotCitation] = field(default_factory=list)
    polished: bool = False


def _mp_ballots_on_bill(db: Session, person_id: int, session_label: str, bill_number: str) -> list[BallotCitation]:
    parliament, _, session_no = session_label.partition("-")
    if not (parliament.isdigit() and session_no.isdigit()):
        return []
    bill = db.scalar(
        select(Bill)
        .join(LegislatureSession, Bill.session_id == LegislatureSession.id)
        .join(Jurisdiction, LegislatureSession.jurisdiction_id == Jurisdiction.id)
        .where(
            Bill.number == bill_number,
            # MP letters cite the federal record; session labels repeat
            # across legislatures.
            Jurisdiction.code == get_settings().default_jurisdiction,
            LegislatureSession.parliament_number == int(parliament),
            LegislatureSession.session_number == int(session_no),
        )
    )
    if bill is None:
        return []
    ballots = db.scalars(
        select(Ballot)
        .join(Vote, Ballot.vote_id == Vote.id)
        .where(Ballot.person_id == person_id, Vote.bill_id == bill.id)
        .options(selectinload(Ballot.vote).selectinload(Vote.session))
        .order_by(Vote.occurred_on)
    ).all()
    return [
        BallotCitation(
            vote_number=b.vote.number,
            session=b.vote.session.label,
            occurred_on=b.vote.occurred_on,
            description_en=b.vote.description_en,
            effect=_ballot_effect(b.ballot, b.vote.yea_effect),
            ballot=b.ballot,
        )
        for b in ballots
    ]


def _record_paragraph(mp_name: str, bill_number: str, citations: list[BallotCitation]) -> str:
    if not citations:
        return (
            f"I could not find a recorded vote by you on Bill {bill_number} yet, "
            "so I would like to know where you stand."
        )
    lines = []
    for citation in citations:
        when = citation.occurred_on.strftime("%B %-d, %Y") if citation.occurred_on else "an earlier date"
        if citation.effect:
            action = "advance" if citation.effect == "advanced" else "block"
            lines.append(f"On {when}, you voted to {action} it (Vote {citation.vote_number}).")
        elif citation.ballot in {"paired", "absent"}:
            lines.append(f"On {when}, you did not cast a Yes or No vote (Vote {citation.vote_number}).")
        else:
            lines.append(
                f"On {when}, you voted {citation.ballot.capitalize()} (Vote {citation.vote_number})."
            )
    return "Your public voting record on this bill shows: " + " ".join(lines)


def build_letter(
    db: Session,
    *,
    mp: Person,
    concern: str,
    bill_session: str | None = None,
    bill_number: str | None = None,
) -> LetterResult:
    membership = db.scalar(
        select(PersonMembership).where(
            PersonMembership.person_id == mp.id, PersonMembership.is_current.is_(True)
        )
    )
    riding = membership.riding_name if membership else None

    citations: list[BallotCitation] = []
    paragraphs = [
        f"Dear {mp.full_name},",
        (
            f"I am your constituent{f' in {riding}' if riding else ''}, and I am writing about "
            "something that matters to me:"
        ),
        concern.strip(),
    ]
    if bill_session and bill_number:
        citations = _mp_ballots_on_bill(db, mp.id, bill_session, bill_number)
        paragraphs.append(_record_paragraph(mp.full_name, bill_number, citations))
        paragraphs.append(
            "Please explain your position on this, and what you plan to do about it "
            "on behalf of our riding."
        )
    else:
        paragraphs.append(
            "Please tell me your position on this, and what you plan to do about it "
            "on behalf of our riding."
        )
    paragraphs.append(
        "I understand MPs balance many priorities, and I appreciate a substantive reply.\n\n"
        "Respectfully,\n[Your name]\n[Your address in the riding]"
    )

    return LetterResult(
        letter_text="\n\n".join(paragraphs),
        mp_name=mp.full_name,
        mp_email=mp.email,
        riding=riding,
        citations=citations,
    )


POLISH_SCHEMA = {
    "type": "object",
    "properties": {
        "letter_text": {
            "type": "string",
            "description": "The polished letter. Keep every factual claim exactly as given.",
        }
    },
    "required": ["letter_text"],
}


async def polish_letter(db: Session, letter: LetterResult) -> LetterResult:
    """Optional Claude pass for tone/flow. Facts must survive verbatim —
    the prompt forbids changing vote citations."""
    client = LLMClient(fast=True)
    if not client.is_configured():
        return letter
    try:
        ensure_budget(db)
    except BudgetExceededError:
        return letter  # Deterministic letter still works; polish is optional.
    prompt = (
        "Improve the flow and tone of this constituent letter to a Member of "
        "Parliament. Rules: keep it respectful and non-partisan; do NOT change, "
        "add, or remove any factual claims, dates, vote numbers, or names; keep "
        "the [Your name] placeholders; plain language, reading grade 8.\n\n"
        f"{letter.letter_text}"
    )
    result = await asyncio.to_thread(
        client.structured_response,
        prompt=prompt,
        schema=POLISH_SCHEMA,
        max_tokens=1200,
    )
    record_usage(db, result, job_name="letter_polish")
    db.commit()
    polished_text = result.data.get("letter_text") or letter.letter_text
    # Safety: all vote numbers must survive the polish.
    for citation in letter.citations:
        if f"Vote {citation.vote_number}" not in polished_text:
            return letter  # Model dropped a fact — keep the deterministic version.
    letter.letter_text = polished_text
    letter.polished = True
    return letter
