"""Integrity pattern detectors.

Deterministic computations over lobbying + contribution + bill data.
Every finding becomes an IntegrityFlag with status='pending_review' —
NOTHING publishes without a human decision in the review queue.

Language rule: headlines state verifiable facts and counts, never
characterizations. The same detectors run on every member of every
party — there is no party-specific logic anywhere.
"""
from __future__ import annotations

import hashlib
from collections import defaultdict
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ingestion.influence import normalize_name
from app.models import (
    Bill,
    BillDeath,
    Contribution,
    EntityTopic,
    IntegrityFlag,
    LobbyCommunication,
    Person,
    Topic,
)

# Detector thresholds — documented on the public methodology page.
CLUSTER_WINDOW_DAYS = 30
CLUSTER_MIN_CONTACTS = 6
CLUSTER_BASELINE_MULTIPLIER = 3.0
DEATH_WINDOW_DAYS = 60
DEATH_MIN_CONTACTS = 3
OVERLAP_MIN_AMOUNT = 200.0


def _fingerprint(*parts: object) -> str:
    return hashlib.sha256("|".join(str(p) for p in parts).encode()).hexdigest()[:64]


def _upsert_flag(
    db: Session,
    *,
    detector: str,
    fingerprint: str,
    headline: str,
    detail: str | None,
    confidence: float,
    evidence: dict,
    person_id: int | None = None,
    bill_id: int | None = None,
    organization_id: int | None = None,
) -> bool:
    """Insert if new. Existing flags are never touched — a human may have
    already reviewed them. Returns True when a new flag was created."""
    existing = db.scalar(select(IntegrityFlag).where(IntegrityFlag.fingerprint == fingerprint))
    if existing is not None:
        return False
    db.add(
        IntegrityFlag(
            detector=detector,
            fingerprint=fingerprint,
            headline_en=headline,
            detail_en=detail,
            confidence=confidence,
            evidence=evidence,
            person_id=person_id,
            bill_id=bill_id,
            organization_id=organization_id,
        )
    )
    db.flush()
    return True


# ---------------------------------------------------------------------------
# Detector 1: lobbying contact clusters
# ---------------------------------------------------------------------------

def detect_contact_clusters(db: Session) -> int:
    """An MP received an unusual burst of lobbying contacts in a 30-day
    window (>= max(6, 3x their monthly baseline))."""
    comms = db.execute(
        select(
            LobbyCommunication.dpoh_person_id,
            LobbyCommunication.comm_date,
            LobbyCommunication.id,
            LobbyCommunication.client_name,
        ).where(
            LobbyCommunication.dpoh_person_id.is_not(None),
            LobbyCommunication.comm_date.is_not(None),
        )
    ).all()

    by_person: dict[int, list[tuple[date, int, str | None]]] = defaultdict(list)
    for person_id, comm_date, comm_id, client in comms:
        by_person[person_id].append((comm_date, comm_id, client))

    created = 0
    for person_id, entries in by_person.items():
        entries.sort()
        total = len(entries)
        if total < CLUSTER_MIN_CONTACTS:
            continue

        # Densest window anchored at each contact.
        best_window: list[tuple[date, int, str | None]] = []
        for i, (start_date, _, _) in enumerate(entries):
            window = [e for e in entries[i:] if (e[0] - start_date).days <= CLUSTER_WINDOW_DAYS]
            if len(window) > len(best_window):
                best_window = window

        # Baseline: their activity OUTSIDE the burst window, per month.
        # (Including the burst in its own baseline would make an MP with no
        # prior history mathematically unflaggable.)
        outside = total - len(best_window)
        span_days = max((entries[-1][0] - entries[0][0]).days, 30)
        outside_days = max(span_days - CLUSTER_WINDOW_DAYS, 30)
        monthly_baseline = outside / (outside_days / 30.0)
        threshold = max(CLUSTER_MIN_CONTACTS, int(monthly_baseline * CLUSTER_BASELINE_MULTIPLIER))
        if len(best_window) < threshold:
            continue

        person = db.get(Person, person_id)
        if person is None:
            continue
        window_start, window_end = best_window[0][0], best_window[-1][0]
        clients = sorted({c for _, _, c in best_window if c})
        fingerprint = _fingerprint("cluster", person_id, window_start.isoformat())
        headline = (
            f"{person.full_name} was named in {len(best_window)} lobbying communication "
            f"reports in the {CLUSTER_WINDOW_DAYS} days starting {window_start.isoformat()}."
        )
        detail = (
            f"Baseline is about {monthly_baseline:.1f} contacts per month. "
            f"Clients in this window: {', '.join(clients[:10])}"
            + ("…" if len(clients) > 10 else "")
            + ". Source: Registry of Lobbyists communication reports."
        )
        if _upsert_flag(
            db,
            detector="lobbying_contact_cluster",
            fingerprint=fingerprint,
            headline=headline,
            detail=detail,
            confidence=min(0.95, len(best_window) / (threshold * 2)),
            evidence={
                "window_start": window_start.isoformat(),
                "window_end": window_end.isoformat(),
                "contact_count": len(best_window),
                "monthly_baseline": round(monthly_baseline, 2),
                "communication_ids": [comm_id for _, comm_id, _ in best_window],
                "clients": clients,
            },
            person_id=person_id,
        ):
            created += 1
    db.commit()
    return created


# ---------------------------------------------------------------------------
# Detector 2: donor / lobbyist-client overlap
# ---------------------------------------------------------------------------

def detect_donor_lobbyist_overlap(db: Session) -> int:
    """Someone donated to an MP's campaign AND appears as a lobbying
    client/registrant on communications naming the same MP."""
    contributions = db.execute(
        select(
            Contribution.recipient_person_id,
            Contribution.normalized_contributor,
            Contribution.contributor_name,
            Contribution.amount,
            Contribution.id,
        ).where(
            Contribution.recipient_person_id.is_not(None),
            Contribution.amount >= OVERLAP_MIN_AMOUNT,
        )
    ).all()

    donors_by_person: dict[int, dict[str, dict]] = defaultdict(dict)
    for person_id, normalized, name, amount, contribution_id in contributions:
        slot = donors_by_person[person_id].setdefault(
            normalized, {"name": name, "total": 0.0, "ids": []}
        )
        slot["total"] += amount
        slot["ids"].append(contribution_id)

    comms = db.execute(
        select(
            LobbyCommunication.dpoh_person_id,
            LobbyCommunication.client_name,
            LobbyCommunication.registrant_name,
            LobbyCommunication.id,
            LobbyCommunication.comm_date,
        ).where(LobbyCommunication.dpoh_person_id.is_not(None))
    ).all()

    lobby_by_person: dict[int, dict[str, list]] = defaultdict(lambda: defaultdict(list))
    for person_id, client, registrant, comm_id, comm_date in comms:
        for name in (client, registrant):
            if name:
                lobby_by_person[person_id][normalize_name(name)].append(
                    (comm_id, comm_date.isoformat() if comm_date else None, name)
                )

    created = 0
    for person_id, donors in donors_by_person.items():
        lobby_names = lobby_by_person.get(person_id, {})
        for normalized, donor in donors.items():
            if not normalized or normalized not in lobby_names:
                continue
            person = db.get(Person, person_id)
            if person is None:
                continue
            matches = lobby_names[normalized]
            fingerprint = _fingerprint("overlap", person_id, normalized)
            headline = (
                f"{donor['name']} contributed ${donor['total']:,.0f} to {person.full_name}'s "
                f"campaign and appears on {len(matches)} lobbying communication report(s) "
                f"naming {person.full_name}."
            )
            detail = (
                "Contribution records: Elections Canada financial returns. "
                "Communication reports: Registry of Lobbyists. Name matching is "
                "normalized text matching and can produce false positives for "
                "common names — verify before drawing conclusions."
            )
            if _upsert_flag(
                db,
                detector="donor_lobbyist_overlap",
                fingerprint=fingerprint,
                headline=headline,
                detail=detail,
                confidence=0.6,  # Name matching — inherently fuzzy.
                evidence={
                    "contributor": donor["name"],
                    "total_amount": round(donor["total"], 2),
                    "contribution_ids": donor["ids"],
                    "communications": [
                        {"id": comm_id, "date": comm_date, "as_name": name}
                        for comm_id, comm_date, name in matches
                    ],
                },
                person_id=person_id,
            ):
                created += 1
    db.commit()
    return created


# ---------------------------------------------------------------------------
# Detector 3: lobbying before a quiet bill death
# ---------------------------------------------------------------------------

def _subject_topic_ids(db: Session, subjects: str | None) -> set[int]:
    if not subjects:
        return set()
    text = subjects.lower()
    matched: set[int] = set()
    for topic in db.scalars(select(Topic)).all():
        terms = [topic.name_en.lower()]
        if topic.aliases_en:
            terms.extend(a.strip().lower() for a in topic.aliases_en.split(","))
        if any(term and term in text for term in terms):
            matched.add(topic.id)
    return matched


def detect_lobbying_before_death(db: Session) -> int:
    """A bill died in committee / on the Order Paper, and lobbying
    communications on overlapping subject matter clustered in the 60 days
    before it died."""
    deaths = db.execute(
        select(BillDeath.bill_id, BillDeath.occurred_on, BillDeath.mechanism).where(
            BillDeath.occurred_on.is_not(None),
            BillDeath.mechanism.in_(["died_committee", "died_order_paper", "not_proceeded_with"]),
        )
    ).all()
    if not deaths:
        return 0

    comms = db.execute(
        select(
            LobbyCommunication.id,
            LobbyCommunication.comm_date,
            LobbyCommunication.subjects,
            LobbyCommunication.client_name,
        ).where(LobbyCommunication.comm_date.is_not(None))
    ).all()

    created = 0
    for bill_id, died_on, mechanism in deaths:
        bill_topic_ids = {
            row[0]
            for row in db.execute(
                select(EntityTopic.topic_id).where(
                    EntityTopic.entity_type == "bill", EntityTopic.entity_id == bill_id
                )
            ).all()
        }
        if not bill_topic_ids:
            continue

        window_start = died_on - timedelta(days=DEATH_WINDOW_DAYS)
        matching = []
        for comm_id, comm_date, subjects, client in comms:
            if not (window_start <= comm_date <= died_on):
                continue
            if _subject_topic_ids(db, subjects) & bill_topic_ids:
                matching.append((comm_id, comm_date.isoformat(), client))
        if len(matching) < DEATH_MIN_CONTACTS:
            continue

        bill = db.get(Bill, bill_id)
        if bill is None:
            continue
        clients = sorted({c for _, _, c in matching if c})
        fingerprint = _fingerprint("before_death", bill_id)
        mechanism_label = mechanism.replace("_", " ")
        headline = (
            f"Bill {bill.number} {mechanism_label} on {died_on.isoformat()}; "
            f"{len(matching)} lobbying communication report(s) on overlapping "
            f"subject matter were filed in the prior {DEATH_WINDOW_DAYS} days."
        )
        detail = (
            f"Clients on those reports: {', '.join(clients[:10])}"
            + ("…" if len(clients) > 10 else "")
            + ". Subject-matter overlap is computed against this bill's topic "
            "tags. Correlation in timing is not evidence of causation — this "
            "flag marks a pattern for human review."
        )
        if _upsert_flag(
            db,
            detector="lobbying_before_death",
            fingerprint=fingerprint,
            headline=headline,
            detail=detail,
            confidence=min(0.9, len(matching) / 10),
            evidence={
                "died_on": died_on.isoformat(),
                "mechanism": mechanism,
                "window_days": DEATH_WINDOW_DAYS,
                "communications": [
                    {"id": comm_id, "date": comm_date, "client": client}
                    for comm_id, comm_date, client in matching
                ],
                "clients": clients,
            },
            bill_id=bill_id,
        ):
            created += 1
    db.commit()
    return created


def run_all_detectors(db: Session) -> dict[str, int]:
    return {
        "lobbying_contact_cluster": detect_contact_clusters(db),
        "donor_lobbyist_overlap": detect_donor_lobbyist_overlap(db),
        "lobbying_before_death": detect_lobbying_before_death(db),
    }
