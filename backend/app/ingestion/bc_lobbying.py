"""BC lobbying, from the ORL's open-data exports (lobbyistsregistrar.bc.ca).

BC publishes what Ontario doesn't: **Lobbying Activity Reports** — dated,
per-meeting logs naming the public office holders lobbied (since May 2020),
plus registration returns (since 2010). Both ship as monthly CSV ZIPs under
an open-data licence, so this is a download-and-parse pipeline like the
federal registry — no scraping.

- Activity reports -> lobby_communications (jurisdiction_code="bc"), one
  row per (report, office holder), elected MLAs matched to People by name.
- Registration returns -> lobby_registrations (jurisdiction_code="bc"),
  active = no end date, latest version per registration number.

Deterministic parsing only — no LLM anywhere in ingestion.
"""
from __future__ import annotations

import csv
import io
import logging
import zipfile
from datetime import date, datetime
from pathlib import Path

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import Chamber, LobbyCommunication, LobbyRegistration, Person

logger = logging.getLogger(__name__)

settings = get_settings()

LAR_URL = "https://www.lobbyistsregistrar.bc.ca/app/secure/orl/lrs/do/mssDtstRprt?file=ORL_LAR_Data.zip"
REGISTRATIONS_URL = (
    "https://www.lobbyistsregistrar.bc.ca/app/secure/orl/lrs/do/mssDtstRprt?file=ORL_Registration_Data.zip"
)


def _read_csv(zf: zipfile.ZipFile, name: str) -> list[dict[str, str]]:
    with zf.open(name) as fh:
        text = io.TextIOWrapper(fh, encoding="utf-8-sig", errors="replace")
        return [
            {key: ("" if value in (None, "null") else value) for key, value in row.items()}
            for row in csv.DictReader(text)
        ]


def _parse_date(raw: str) -> date | None:
    raw = (raw or "").strip()
    if not raw:
        return None
    try:
        return datetime.strptime(raw[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def _person_name(last: str, first: str) -> str:
    return " ".join(part for part in (first.strip(), last.strip()) if part)


def _bc_people_index(db: Session) -> dict[str, int]:
    """Normalized 'first last' -> person_id for sitting BC MLAs."""
    rows = db.execute(
        select(Person.full_name, Person.id)
        .join(Chamber, Person.chamber_id == Chamber.id)
        .where(Chamber.slug == "bc-assembly")
    ).all()
    return {name.lower().strip(): person_id for name, person_id in rows if name}


# ---------------------------------------------------------------------------
# Lobbying Activity Reports -> lobby_communications
# ---------------------------------------------------------------------------

def parse_lar_zip(zip_bytes: bytes, *, since_year: int) -> list[dict]:
    """One row per (report, office holder), amended versions superseded."""
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        primary = _read_csv(zf, "LAR_Primary_Export.csv")
        spohs = _read_csv(zf, "LAR_SPOH_Export.csv")
        details = _read_csv(zf, "LAR_SubjectMatterDetails_Export.csv")
        subject_names = {
            row["SUBJECT_MATTER_ID"]: row["SUBJECT_MATTER"]
            for row in _read_csv(zf, "Subject_Matters_Export.csv")
        }

    superseded = {row["PREVIOUS_VERSION_LAR_ID"] for row in primary if row["PREVIOUS_VERSION_LAR_ID"]}

    subjects_by_lar: dict[str, str] = {}
    for row in details:
        ids = [part.strip() for part in (row["SUBJECT_MATTER_IDS"] or "").split(",") if part.strip()]
        names = [subject_names.get(sm_id, sm_id) for sm_id in ids]
        text = ", ".join(dict.fromkeys(names))
        topic = (row["TOPIC_OF_LOBBYING"] or "").strip()
        combined = " — ".join(part for part in (text, topic) if part)
        if combined:
            existing = subjects_by_lar.get(row["LAR_ID"])
            subjects_by_lar[row["LAR_ID"]] = f"{existing}; {combined}" if existing else combined

    spohs_by_lar: dict[str, list[dict[str, str]]] = {}
    for row in spohs:
        spohs_by_lar.setdefault(row["LAR_ID"], []).append(row)

    out: list[dict] = []
    for row in primary:
        lar_id = row["LAR_ID"]
        if lar_id in superseded:
            continue
        meeting_date = _parse_date(row["MEETING_DATE"])
        if meeting_date is None or meeting_date.year < since_year:
            continue
        registrant = _person_name(row["FILER_LAST_NAME"], row["FILER_FIRST_NAME"])
        in_house = _person_name(row["IH_LOBBYIST_LAST_NAME"], row["IH_LOBBYIST_FIRST_NAME"])
        subjects = subjects_by_lar.get(lar_id)
        for spoh in spohs_by_lar.get(lar_id, []):
            dpoh_name = _person_name(spoh["SPOH_LAST_NAME"], spoh["SPOH_FIRST_NAME"])
            if not dpoh_name:
                continue
            out.append(
                {
                    "source_ref": lar_id,
                    "comm_date": meeting_date,
                    "client_name": (row["CLIENT_ORG_NAME"] or "").strip() or None,
                    "registrant_name": in_house or registrant or None,
                    "dpoh_name": dpoh_name,
                    "dpoh_title": (spoh["SPOH_TITLE"] or "").strip() or None,
                    "institution": (spoh["BC_PUBLIC_AGENCY"] or spoh["BRANCH"] or "").strip() or None,
                    "subjects": subjects,
                }
            )
    return out


def sync_bc_communications(db: Session, zip_bytes: bytes) -> int:
    """Upsert BC (report, office holder) rows; match MLAs to People."""
    rows = parse_lar_zip(zip_bytes, since_year=settings.influence_since_year)
    people = _bc_people_index(db)

    existing_keys = {
        (source_ref, dpoh_name)
        for source_ref, dpoh_name in db.execute(
            select(LobbyCommunication.source_ref, LobbyCommunication.dpoh_name).where(
                LobbyCommunication.jurisdiction_code == "bc"
            )
        ).all()
    }

    count = 0
    for row in rows:
        key = (row["source_ref"], row["dpoh_name"])
        if key in existing_keys:
            continue
        existing_keys.add(key)
        db.add(
            LobbyCommunication(
                jurisdiction_code="bc",
                dpoh_person_id=people.get(row["dpoh_name"].lower()),
                **row,
            )
        )
        count += 1
        if count % 5000 == 0:
            db.commit()
    db.commit()
    return count


# ---------------------------------------------------------------------------
# Registration returns -> lobby_registrations
# ---------------------------------------------------------------------------

def parse_registrations_zip(zip_bytes: bytes) -> list[dict]:
    """Latest version of each ACTIVE registration return."""
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        primary = _read_csv(zf, "Registration_Primary_Export.csv")

    superseded = {row["PREVIOUS_VERSION_REG_ID"] for row in primary if row["PREVIOUS_VERSION_REG_ID"]}

    out: list[dict] = []
    for row in primary:
        if row["REG_ID"] in superseded:
            continue
        if row["REG_END_DATE"]:
            continue  # ended registrations: BC's own "active" definition
        reg_type = (row["REG_TYPE"] or "").strip().lower()
        out.append(
            {
                "registration_number": row["REG_NUM"],
                "lobbyist_number": row["FILER_NUM"] or None,
                "lobbyist_name": _person_name(row["FILER_LAST_NAME"], row["FILER_FIRST_NAME"]) or None,
                "firm_name": (row["FIRM_NAME"] or "").strip() or None,
                "lobbyist_type": "consultant" if reg_type == "cons" else "in_house_organization",
                "client_name": (row["CLIENT_ORG_NAME"] or "").strip() or None,
                "client_description": (row["CLIENT_ORG_BUS_DESC"] or "").strip() or None,
                "initial_filing_date": _parse_date(row["REG_START_DATE"]),
                "last_amendment_date": _parse_date(row["REG_POSTED_DATE"]),
            }
        )
    return out


def sync_bc_registrations(db: Session, zip_bytes: bytes) -> int:
    rows = parse_registrations_zip(zip_bytes)
    existing = {
        registration.registration_number: registration
        for registration in db.scalars(
            select(LobbyRegistration).where(LobbyRegistration.jurisdiction_code == "bc")
        ).all()
    }

    count = 0
    active_numbers: set[str] = set()
    for row in rows:
        active_numbers.add(row["registration_number"])
        registration = existing.get(row["registration_number"])
        if registration is None:
            registration = LobbyRegistration(
                registration_number=row["registration_number"], jurisdiction_code="bc"
            )
            db.add(registration)
            existing[row["registration_number"]] = registration
        elif registration.last_amendment_date == row["last_amendment_date"]:
            continue  # unchanged
        registration.status = "active"
        for field in (
            "lobbyist_number", "lobbyist_name", "firm_name", "lobbyist_type",
            "client_name", "client_description", "initial_filing_date", "last_amendment_date",
        ):
            setattr(registration, field, row[field])
        count += 1
        if count % 1000 == 0:
            db.commit()

    # Registrations that gained an end date disappear from the active parse —
    # mark them ended instead of leaving them active forever.
    for number, registration in existing.items():
        if number not in active_numbers and registration.status == "active":
            registration.status = "ended"
    db.commit()
    return count


# ---------------------------------------------------------------------------
# Download + sync
# ---------------------------------------------------------------------------

def _imports_path(filename: str) -> Path | None:
    """Manually-downloaded copy in IMPORTS_DIR wins (offline/dev runs)."""
    path = Path(settings.imports_dir) / filename
    return path if path.exists() else None


async def _download(url: str, fallback_filename: str) -> bytes | None:
    local = _imports_path(fallback_filename)
    if local is not None:
        return local.read_bytes()
    headers = {"User-Agent": settings.ingestion_user_agent}
    try:
        async with httpx.AsyncClient(headers=headers, timeout=600.0, follow_redirects=True) as client:
            response = await client.get(url)
            response.raise_for_status()
            return response.content
    except httpx.HTTPError as exc:
        logger.warning("bc lobbying: download failed for %s (%s)", fallback_filename, type(exc).__name__)
        return None


async def sync_bc_lobbying(db: Session) -> dict[str, int]:
    """Monthly: both ORL datasets. Partial success is fine — each dataset
    stands alone and re-runs are idempotent."""
    counts = {"communications": 0, "registrations": 0}
    lar_bytes = await _download(LAR_URL, "ORL_LAR_Data.zip")
    if lar_bytes:
        counts["communications"] = sync_bc_communications(db, lar_bytes)
    reg_bytes = await _download(REGISTRATIONS_URL, "ORL_Registration_Data.zip")
    if reg_bytes:
        counts["registrations"] = sync_bc_registrations(db, reg_bytes)
    return counts
