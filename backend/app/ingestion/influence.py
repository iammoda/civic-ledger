"""Money & influence ingestion: Registry of Lobbyists + Elections Canada.

Both sources publish bulk CSV exports (sometimes zipped). Government WAFs
can be picky, so downloads are config-driven (LOBBY_EXPORT_URL /
CONTRIBUTIONS_EXPORT_URL) and parsing is header-alias tolerant: exports
have shifted column names over the years, so each logical field accepts
several known header spellings. A failed download is an IngestionRun
failure and a UI Data Gap — never fabricated data.
"""
from __future__ import annotations

import csv
import hashlib
import io
import re
import unicodedata
import zipfile
from datetime import date, datetime
from typing import Any, Iterable

import httpx
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import Contribution, LobbyCommunication, Organization, Person

settings = get_settings()

# ---------------------------------------------------------------------------
# Normalization / matching helpers
# ---------------------------------------------------------------------------

_ORG_SUFFIXES = re.compile(
    r"\b(inc|inc\.|incorporated|ltd|ltd\.|limited|llp|llc|corp|corp\.|corporation|co|co\.|company|"
    r"lp|plc|ulc|s\.a\.|gmbh|ag|association|assn|canada)\b\.?",
    re.IGNORECASE,
)


def normalize_name(value: str) -> str:
    """Aggressive normalization for entity resolution across sources."""
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    value = value.lower()
    value = _ORG_SUFFIXES.sub(" ", value)
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def normalize_person_name(value: str) -> str:
    """'Smith, John Andrew' / 'Hon. John Smith' -> 'john smith'."""
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    if "," in value:
        last, _, first = value.partition(",")
        value = f"{first} {last}"
    value = re.sub(r"\b(hon|honourable|right|dr|mr|mrs|ms|mp|senator)\b\.?", " ", value, flags=re.IGNORECASE)
    value = re.sub(r"[^a-zA-Z\- ]+", " ", value).lower()
    parts = value.split()
    if len(parts) > 2:
        parts = [parts[0], parts[-1]]  # first + last
    return " ".join(parts)


def get_or_create_org(db: Session, name: str) -> Organization | None:
    if not name or not name.strip():
        return None
    normalized = normalize_name(name)
    if not normalized:
        return None
    org = db.scalar(select(Organization).where(Organization.normalized_name == normalized))
    if org is None:
        org = Organization(name=name.strip()[:500], normalized_name=normalized[:500])
        db.add(org)
        db.flush()
    return org


def build_person_name_index(db: Session) -> dict[str, int]:
    """normalized full name -> person_id, for DPOH/recipient matching."""
    index: dict[str, int] = {}
    for person_id, full_name in db.execute(select(Person.id, Person.full_name)).all():
        index[normalize_person_name(full_name)] = person_id
    return index


# ---------------------------------------------------------------------------
# Tolerant CSV access
# ---------------------------------------------------------------------------

def _build_header_map(fieldnames: Iterable[str], aliases: dict[str, tuple[str, ...]]) -> dict[str, str]:
    """logical field -> actual CSV header, matched case-insensitively."""
    normalized = {re.sub(r"[^a-z0-9]", "", (h or "").lower()): h for h in fieldnames}
    mapping: dict[str, str] = {}
    for field, options in aliases.items():
        for option in options:
            key = re.sub(r"[^a-z0-9]", "", option.lower())
            if key in normalized:
                mapping[field] = normalized[key]
                break
    return mapping


def _get(row: dict, header_map: dict[str, str], field: str) -> str:
    header = header_map.get(field)
    return (row.get(header) or "").strip() if header else ""


def _parse_date_any(value: str) -> date | None:
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%Y/%m/%d", "%B %d, %Y"):
        try:
            return datetime.strptime(value.strip(), fmt).date()
        except (ValueError, AttributeError):
            continue
    return None


# ---------------------------------------------------------------------------
# Registry of Lobbyists — communication reports
# ---------------------------------------------------------------------------

LOBBY_ALIASES: dict[str, tuple[str, ...]] = {
    "comm_number": ("COMM_NUMBER", "COMLOG_ID", "COMMUNICATION_NUMBER", "NUM_COMM"),
    "comm_date": ("COMM_DATE", "DATE_COMM", "COMMUNICATION_DATE", "DATE"),
    "client_name": ("CLIENT_ORG_CORP_NM", "CLIENT_ORG_CORP_NM_AN", "CLIENT_NAME", "EN_CLIENT_ORG_CORP_NM", "CLIENT"),
    "registrant_name": ("REGISTRANT_NM", "REGISTRANT_NAME", "RGSTRNT_NM", "REGISTRANT"),
    "dpoh_name": ("DPOH_NM", "DPOH_NAME", "DPOH_LAST_NM_AND_FIRST_NM", "PUBLIC_OFFICE_HOLDER"),
    "dpoh_title": ("DPOH_TITLE", "DPOH_TITLE_EN", "TITLE"),
    "institution": ("INSTITUTION", "INSTITUTION_EN", "GOVT_INSTITUTION", "INSTITUTION_NM"),
    "subjects": ("SUBJECT_MATTER", "SUBJECT_MATTERS", "EN_SUBJ_MATTER", "SUBJECTS", "SUBJECT"),
}

PARLIAMENT_INSTITUTIONS = ("house of commons", "senate", "parliament")


def parse_lobby_csv(text: str) -> list[dict[str, Any]]:
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        return []
    header_map = _build_header_map(reader.fieldnames, LOBBY_ALIASES)
    if "comm_number" not in header_map or "dpoh_name" not in header_map:
        raise ValueError(f"Unrecognized lobby export headers: {reader.fieldnames}")
    rows = []
    for row in reader:
        dpoh = _get(row, header_map, "dpoh_name")
        if not dpoh:
            continue
        rows.append(
            {
                "source_ref": _get(row, header_map, "comm_number"),
                "comm_date": _parse_date_any(_get(row, header_map, "comm_date")),
                "client_name": _get(row, header_map, "client_name") or None,
                "registrant_name": _get(row, header_map, "registrant_name") or None,
                "dpoh_name": dpoh,
                "dpoh_title": _get(row, header_map, "dpoh_title") or None,
                "institution": _get(row, header_map, "institution") or None,
                "subjects": _get(row, header_map, "subjects") or None,
            }
        )
    return rows


def sync_lobby_communications(db: Session, csv_text: str, *, parliament_only: bool = True) -> int:
    """Upsert communication rows; match DPOHs to our people."""
    rows = parse_lobby_csv(csv_text)
    name_index = build_person_name_index(db)
    count = 0
    for row in rows:
        institution = (row["institution"] or "").lower()
        if parliament_only and institution and not any(k in institution for k in PARLIAMENT_INSTITUTIONS):
            continue

        existing = db.scalar(
            select(LobbyCommunication).where(
                LobbyCommunication.source_ref == row["source_ref"],
                LobbyCommunication.dpoh_name == row["dpoh_name"],
            )
        )
        if existing is None:
            existing = LobbyCommunication(source_ref=row["source_ref"], dpoh_name=row["dpoh_name"])
            db.add(existing)
        existing.comm_date = row["comm_date"]
        existing.client_name = row["client_name"]
        existing.registrant_name = row["registrant_name"]
        existing.dpoh_title = row["dpoh_title"]
        existing.institution = row["institution"]
        existing.subjects = row["subjects"]
        org = get_or_create_org(db, row["client_name"] or "")
        existing.client_org_id = org.id if org else None
        existing.dpoh_person_id = name_index.get(normalize_person_name(row["dpoh_name"]))
        count += 1
        if count % 500 == 0:
            db.commit()
    db.commit()
    return count


# ---------------------------------------------------------------------------
# Elections Canada — contributions
# ---------------------------------------------------------------------------

CONTRIBUTION_ALIASES: dict[str, tuple[str, ...]] = {
    "contributor_name": ("Contributor name", "CONTRIBUTOR_NAME", "Contributor's name", "NAME"),
    "contributor_city": ("Contributor's city", "CITY", "Contributor city"),
    "contributor_province": ("Contributor's province", "PROVINCE", "Contributor province"),
    "amount": ("Monetary amount", "AMOUNT", "Contribution amount", "MON_AMOUNT", "Amount"),
    "received_on": ("Contribution Received date", "DATE_RECEIVED", "Date received", "CONTRIBUTION_DATE"),
    "recipient_name": ("Recipient", "RECIPIENT", "Candidate name", "Recipient name"),
    "recipient_party": ("Political party of recipient", "PARTY", "Political affiliation", "Recipient party"),
    "recipient_type": ("Political entity", "ENTITY_TYPE", "Recipient type"),
}


def parse_contributions_csv(text: str) -> list[dict[str, Any]]:
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        return []
    header_map = _build_header_map(reader.fieldnames, CONTRIBUTION_ALIASES)
    if "contributor_name" not in header_map or "recipient_name" not in header_map:
        raise ValueError(f"Unrecognized contributions headers: {reader.fieldnames}")
    rows = []
    for row in reader:
        contributor = _get(row, header_map, "contributor_name")
        recipient = _get(row, header_map, "recipient_name")
        if not contributor or not recipient:
            continue
        amount_text = _get(row, header_map, "amount").replace("$", "").replace(",", "")
        try:
            amount = float(amount_text)
        except ValueError:
            amount = 0.0
        rows.append(
            {
                "contributor_name": contributor,
                "contributor_city": _get(row, header_map, "contributor_city") or None,
                "contributor_province": _get(row, header_map, "contributor_province") or None,
                "amount": amount,
                "received_on": _parse_date_any(_get(row, header_map, "received_on")),
                "recipient_name": recipient,
                "recipient_party": _get(row, header_map, "recipient_party") or None,
                "recipient_type": _get(row, header_map, "recipient_type") or None,
            }
        )
    return rows


def _contribution_fingerprint(row: dict[str, Any]) -> str:
    raw = "|".join(
        str(row.get(k) or "")
        for k in ("contributor_name", "amount", "received_on", "recipient_name", "recipient_type")
    )
    return hashlib.sha256(raw.encode()).hexdigest()


def sync_contributions(db: Session, csv_text: str) -> int:
    rows = parse_contributions_csv(csv_text)
    name_index = build_person_name_index(db)
    count = 0
    for row in rows:
        fingerprint = _contribution_fingerprint(row)
        existing = db.scalar(select(Contribution).where(Contribution.source_fingerprint == fingerprint))
        if existing is not None:
            continue
        db.add(
            Contribution(
                contributor_name=row["contributor_name"][:255],
                normalized_contributor=normalize_name(row["contributor_name"])[:255],
                contributor_city=row["contributor_city"],
                contributor_province=row["contributor_province"],
                amount=row["amount"],
                received_on=row["received_on"],
                recipient_name=row["recipient_name"][:255],
                recipient_party=row["recipient_party"],
                recipient_person_id=name_index.get(normalize_person_name(row["recipient_name"])),
                recipient_type=row["recipient_type"],
                source_fingerprint=fingerprint,
            )
        )
        count += 1
        if count % 1000 == 0:
            db.commit()
    db.commit()
    return count


# ---------------------------------------------------------------------------
# Download helpers (config-driven URLs; ZIP or plain CSV)
# ---------------------------------------------------------------------------

async def download_export(url: str) -> str | None:
    """Download a CSV (optionally inside a ZIP). None on failure."""
    if not url:
        return None
    headers = {"User-Agent": settings.ingestion_user_agent}
    try:
        async with httpx.AsyncClient(headers=headers, timeout=300.0, follow_redirects=True) as client:
            response = await client.get(url)
            response.raise_for_status()
    except httpx.HTTPError:
        return None

    content = response.content
    if url.endswith(".zip") or content[:2] == b"PK":
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            csv_names = [n for n in archive.namelist() if n.lower().endswith(".csv")]
            if not csv_names:
                return None
            # Largest CSV is the data file.
            biggest = max(csv_names, key=lambda n: archive.getinfo(n).file_size)
            return archive.read(biggest).decode("utf-8-sig", errors="replace")
    return content.decode("utf-8-sig", errors="replace")
