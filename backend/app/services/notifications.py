"""Notification matcher: follows x new events -> in-app notifications.

Runs hourly. Fingerprints make re-runs idempotent; weekly grouping keys
keep MP-activity notifications quiet (one per week, not one per vote).
No email anywhere — these power the bell and the catch-me-up feed.
"""
from __future__ import annotations

import hashlib
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models import (
    Ballot,
    Bill,
    BillDeath,
    EntityTopic,
    Notification,
    Person,
    Petition,
    Topic,
    UserFollow,
    Vote,
)

LOOKBACK_DAYS = 7
PETITION_CLOSING_DAYS = 7
# Cosine-distance ceiling for question-follow matches (text-embedding-3-small).
QUESTION_MATCH_MAX_DISTANCE = 0.55
_STOPWORDS = {
    "the", "and", "for", "that", "this", "with", "from", "have", "what", "who",
    "why", "how", "can", "cant", "cannot", "about", "will", "are", "was", "were",
    "not", "get", "got", "its", "any", "does", "did", "should", "would", "could",
    "afford", "going", "being", "been", "they", "them", "their", "there",
}


def _significant_tokens(text: str) -> set[str]:
    import re

    return {
        token
        for token in re.findall(r"[a-z]{4,}", text.lower())
        if token not in _STOPWORDS
    }


def _keyword_question_match(db: Session, question: str, bill: Bill) -> bool:
    """Fallback matcher: token overlap with title + topic names/aliases."""
    question_tokens = _significant_tokens(question)
    if not question_tokens:
        return False
    bill_text = " ".join(filter(None, [bill.title_en, bill.short_title_en]))
    topic_rows = db.execute(
        select(Topic.name_en, Topic.aliases_en)
        .join(EntityTopic, EntityTopic.topic_id == Topic.id)
        .where(EntityTopic.entity_type == "bill", EntityTopic.entity_id == bill.id)
    ).all()
    for name, aliases in topic_rows:
        bill_text += f" {name} {aliases or ''}"
    return len(question_tokens & _significant_tokens(bill_text)) >= 2


def _question_embedding(db: Session, follow: UserFollow) -> list[float] | None:
    """Get-or-create the cached embedding for a watched question."""
    from app.llm.base import EmbeddingClient
    from app.models import Embedding

    existing = db.scalar(
        select(Embedding).where(
            Embedding.entity_type == "question", Embedding.entity_id == follow.id
        )
    )
    if existing is not None:
        return list(existing.vector)
    client = EmbeddingClient()
    if not client.is_configured():
        return None
    vector = client.embed([follow.target_ref])[0]
    import hashlib

    db.add(
        Embedding(
            entity_type="question",
            entity_id=follow.id,
            content_hash=hashlib.sha256(follow.target_ref.encode()).hexdigest(),
            model_name=client.model,
            vector=vector,
        )
    )
    db.flush()
    return vector


def _match_question_follow(db: Session, follow: UserFollow, cutoff: datetime) -> list[Bill]:
    """New bills matching a watched question: vector similarity on Postgres,
    keyword-overlap fallback everywhere else."""
    from app.models import Embedding

    new_bills = db.scalars(
        select(Bill).options(selectinload(Bill.session)).where(Bill.created_at >= cutoff)
    ).all()
    if not new_bills:
        return []

    is_postgres = db.get_bind().dialect.name == "postgresql"
    if is_postgres:
        vector = _question_embedding(db, follow)
        if vector is not None:
            bill_ids = [bill.id for bill in new_bills]
            matched_ids = {
                row[0]
                for row in db.execute(
                    select(Embedding.entity_id)
                    .where(
                        Embedding.entity_type == "bill",
                        Embedding.entity_id.in_(bill_ids),
                        Embedding.vector.cosine_distance(vector) <= QUESTION_MATCH_MAX_DISTANCE,
                    )
                ).all()
            }
            vector_hits = [bill for bill in new_bills if bill.id in matched_ids]
            # Bills without embeddings yet still get the keyword pass.
            unembedded = [
                bill
                for bill in new_bills
                if bill.id not in matched_ids
                and db.scalar(
                    select(Embedding.id).where(
                        Embedding.entity_type == "bill", Embedding.entity_id == bill.id
                    )
                )
                is None
                and _keyword_question_match(db, follow.target_ref, bill)
            ]
            return vector_hits + unembedded

    return [bill for bill in new_bills if _keyword_question_match(db, follow.target_ref, bill)]


def _fingerprint(*parts: object) -> str:
    return hashlib.sha256("|".join(str(p) for p in parts).encode()).hexdigest()[:64]


def _notify(
    db: Session,
    *,
    user_id: str,
    kind: str,
    title: str,
    body: str | None,
    url_path: str | None,
    matched_follow: str,
    fingerprint: str,
) -> bool:
    existing = db.scalar(
        select(Notification.id).where(
            Notification.user_id == user_id, Notification.fingerprint == fingerprint
        )
    )
    if existing is not None:
        return False
    db.add(
        Notification(
            user_id=user_id,
            kind=kind,
            title_en=title,
            body_en=body,
            url_path=url_path,
            matched_follow=matched_follow,
            fingerprint=fingerprint,
        )
    )
    db.flush()
    return True


def _topic_bill_ids(db: Session, topic_id: int) -> set[int]:
    return {
        row[0]
        for row in db.execute(
            select(EntityTopic.entity_id).where(
                EntityTopic.entity_type == "bill", EntityTopic.topic_id == topic_id
            )
        ).all()
    }


def match_notifications(db: Session, *, now: datetime | None = None) -> int:
    now = now or datetime.now(timezone.utc)
    cutoff = now.replace(tzinfo=None) - timedelta(days=LOOKBACK_DAYS)
    today = now.date()
    created = 0

    follows = db.scalars(select(UserFollow)).all()
    topics_by_slug = {t.slug: t for t in db.scalars(select(Topic)).all()}

    for follow in follows:
        matched = f"{follow.target_type}:{follow.target_ref}"

        if follow.target_type == "topic":
            topic = topics_by_slug.get(follow.target_ref)
            if topic is None:
                continue
            bill_ids = _topic_bill_ids(db, topic.id)

            # New bills on this topic.
            if bill_ids:
                new_bills = db.scalars(
                    select(Bill)
                    .options(selectinload(Bill.session))
                    .where(Bill.id.in_(bill_ids), Bill.created_at >= cutoff)
                ).all()
                for bill in new_bills:
                    if _notify(
                        db,
                        user_id=follow.user_id,
                        kind="bill_new",
                        title=f"New {topic.name_en.lower()} bill: {bill.number}",
                        body=bill.short_title_en or bill.title_en,
                        url_path=f"/bills/{bill.session.label}/{bill.number}",
                        matched_follow=matched,
                        fingerprint=_fingerprint("bill_new", bill.id),
                    ):
                        created += 1

                # Bills on this topic that just died.
                deaths = db.scalars(
                    select(BillDeath)
                    .options(selectinload(BillDeath.bill).selectinload(Bill.session))
                    .where(BillDeath.bill_id.in_(bill_ids), BillDeath.created_at >= cutoff)
                ).all()
                for death in deaths:
                    bill = death.bill
                    if _notify(
                        db,
                        user_id=follow.user_id,
                        kind="bill_died",
                        title=f"A {topic.name_en.lower()} bill died: {bill.number}",
                        body=death.attribution_en or death.mechanism.replace("_", " "),
                        url_path=f"/bills/{bill.session.label}/{bill.number}",
                        matched_follow=matched,
                        fingerprint=_fingerprint("bill_died", bill.id),
                    ):
                        created += 1

            # Petitions on this topic closing soon.
            petition_ids = {
                row[0]
                for row in db.execute(
                    select(EntityTopic.entity_id).where(
                        EntityTopic.entity_type == "petition", EntityTopic.topic_id == topic.id
                    )
                ).all()
            }
            if petition_ids:
                closing = db.scalars(
                    select(Petition).where(
                        Petition.id.in_(petition_ids),
                        Petition.state == "open",
                        Petition.closes_at.is_not(None),
                        Petition.closes_at <= today + timedelta(days=PETITION_CLOSING_DAYS),
                        Petition.closes_at >= today,
                    )
                ).all()
                for petition in closing:
                    days_left = (petition.closes_at - today).days
                    if _notify(
                        db,
                        user_id=follow.user_id,
                        kind="petition_closing",
                        title=f"Petition closing in {days_left} day{'s' if days_left != 1 else ''}: {petition.title_en}",
                        body=f"{petition.signature_count:,} signatures so far ({petition.number}).",
                        url_path=petition.source_url,
                        matched_follow=matched,
                        fingerprint=_fingerprint("petition_closing", petition.id),
                    ):
                        created += 1

        elif follow.target_type == "person":
            person = db.scalar(select(Person).where(Person.slug == follow.target_ref))
            if person is None:
                continue

            # Dissents: individually noteworthy.
            dissents = db.scalars(
                select(Ballot)
                .join(Vote, Ballot.vote_id == Vote.id)
                .options(
                    selectinload(Ballot.vote).selectinload(Vote.session),
                    selectinload(Ballot.vote).selectinload(Vote.chamber),
                )
                .where(
                    Ballot.person_id == person.id,
                    Ballot.broke_party_line.is_(True),
                    Vote.occurred_on >= cutoff.date(),
                )
            ).all()
            for ballot in dissents:
                vote = ballot.vote
                if _notify(
                    db,
                    user_id=follow.user_id,
                    kind="mp_dissent",
                    title=f"{person.full_name} broke party ranks",
                    body=vote.plain_meaning_en or vote.description_en,
                    url_path=f"/votes/{vote.chamber.slug}/{vote.session.label}/{vote.number}",
                    matched_follow=matched,
                    fingerprint=_fingerprint("mp_dissent", person.id, vote.id),
                ):
                    created += 1

            # Regular activity: one quiet weekly rollup, never per-vote pings.
            week_bucket = today.isocalendar()
            vote_count = db.scalar(
                select(func.count())
                .select_from(Ballot)
                .join(Vote, Ballot.vote_id == Vote.id)
                .where(
                    Ballot.person_id == person.id,
                    Ballot.ballot.in_(["yea", "nay", "paired"]),
                    Vote.occurred_on >= cutoff.date(),
                )
            ) or 0
            if vote_count > 0:
                if _notify(
                    db,
                    user_id=follow.user_id,
                    kind="mp_voted",
                    title=f"{person.full_name} voted in {vote_count} division{'s' if vote_count != 1 else ''} this week",
                    body="See how — every vote translated to plain language.",
                    url_path=f"/politicians/{person.slug}",
                    matched_follow=matched,
                    fingerprint=_fingerprint("mp_voted", person.id, week_bucket.year, week_bucket.week),
                ):
                    created += 1

        elif follow.target_type == "question":
            for bill in _match_question_follow(db, follow, cutoff):
                short_question = follow.target_ref[:80] + ("…" if len(follow.target_ref) > 80 else "")
                if _notify(
                    db,
                    user_id=follow.user_id,
                    kind="question_match",
                    title=f"New bill may relate to your question: “{short_question}”",
                    body=f"{bill.number} — {bill.short_title_en or bill.title_en}",
                    url_path=f"/bills/{bill.session.label}/{bill.number}",
                    matched_follow=matched,
                    fingerprint=_fingerprint("question_match", follow.id, bill.id),
                ):
                    created += 1

        elif follow.target_type == "bill":
            session_label, _, number = follow.target_ref.partition("/")
            bill = None
            for candidate in db.scalars(
                select(Bill).options(selectinload(Bill.session)).where(Bill.number == number)
            ).all():
                if candidate.session.label == session_label:
                    bill = candidate
                    break
            if bill is None:
                continue

            votes = db.scalars(
                select(Vote)
                .options(selectinload(Vote.session), selectinload(Vote.chamber))
                .where(Vote.bill_id == bill.id, Vote.occurred_on >= cutoff.date())
            ).all()
            for vote in votes:
                if _notify(
                    db,
                    user_id=follow.user_id,
                    kind="vote_result",
                    title=f"{bill.number} was voted on: {vote.result or 'result pending'}",
                    body=vote.plain_meaning_en or vote.description_en,
                    url_path=f"/votes/{vote.chamber.slug}/{vote.session.label}/{vote.number}",
                    matched_follow=matched,
                    fingerprint=_fingerprint("vote_result", vote.id),
                ):
                    created += 1

            death = db.scalar(
                select(BillDeath).where(BillDeath.bill_id == bill.id, BillDeath.created_at >= cutoff)
            )
            if death is not None:
                if _notify(
                    db,
                    user_id=follow.user_id,
                    kind="bill_died",
                    title=f"{bill.number} died",
                    body=death.attribution_en or death.mechanism.replace("_", " "),
                    url_path=f"/bills/{bill.session.label}/{bill.number}",
                    matched_follow=matched,
                    fingerprint=_fingerprint("bill_died", bill.id),
                ):
                    created += 1

    db.commit()
    return created


def parliament_is_sitting(db: Session, *, today: date | None = None) -> bool:
    """Heuristic: any recorded division in the last 21 days."""
    today = today or date.today()
    latest = db.scalar(select(func.max(Vote.occurred_on)))
    return latest is not None and (today - latest).days <= 21
