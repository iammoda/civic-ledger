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

# The Registry of Lobbyists communications export is a RELATIONAL zip of
# five CSVs joined on COMLOG_ID (verified against the real file):
#   Communication_PrimaryExport.csv   — one row per communication
#   Communication_DpohExport.csv      — one row per official contacted
#   Communication_SubjectMattersExport.csv — SMT-nn codes per communication
#   Codes_SubjectMatterTypesExport.csv     — SMT code -> English name
PARLIAMENT_INSTITUTIONS = ("house of commons", "senate", "parliament")


def _read_zip_csvs(zip_bytes: bytes) -> dict[str, list[dict[str, str]]]:
    """name -> DictReader rows for every CSV in the archive."""
    out: dict[str, list[dict[str, str]]] = {}
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as archive:
        for name in archive.namelist():
            if not name.lower().endswith(".csv"):
                continue
            with archive.open(name) as fh:
                text = io.TextIOWrapper(fh, encoding="utf-8-sig", errors="replace")
                out[name.rsplit("/", 1)[-1]] = list(csv.DictReader(text))
    return out


def _nn(value: str | None) -> str:
    """Registry uses literal 'null' strings."""
    value = (value or "").strip()
    return "" if value.lower() == "null" else value


def parse_lobby_zip(zip_bytes: bytes, *, since_year: int) -> list[dict[str, Any]]:
    """Join the relational export into one row per (communication, DPOH)."""
    files = _read_zip_csvs(zip_bytes)

    def pick(fragment: str) -> list[dict[str, str]]:
        for name, rows in files.items():
            if fragment.lower() in name.lower():
                return rows
        return []

    primary = pick("PrimaryExport")
    dpoh_rows = pick("DpohExport")
    subject_rows = pick("SubjectMattersExport")
    code_rows = pick("SubjectMatterTypes")
    if not primary or not dpoh_rows:
        raise ValueError(
            f"Lobby zip missing expected members; found: {sorted(files)}"
        )

    code_names = {
        _nn(row.get("SUBJECT_CODE_OBJET")): _nn(row.get("SMT_EN_DESC"))
        for row in code_rows
    }
    subjects_by_comlog: dict[str, list[str]] = {}
    for row in subject_rows:
        comlog = _nn(row.get("COMLOG_ID"))
        code = _nn(row.get("SUBJECT_CODE_OBJET"))
        label = code_names.get(code) or _nn(row.get("CUSTOM_SUBJ_OBJET_PERSO")) or code
        if comlog and label:
            subjects_by_comlog.setdefault(comlog, []).append(label)

    primary_by_comlog: dict[str, dict[str, Any]] = {}
    for row in primary:
        comlog = _nn(row.get("COMLOG_ID"))
        if not comlog:
            continue
        comm_date = _parse_date_any(_nn(row.get("COMM_DATE")))
        if comm_date is None or comm_date.year < since_year:
            continue
        registrant = " ".join(
            part for part in (_nn(row.get("RGSTRNT_1ST_NM_PRENOM_DCLRNT")), _nn(row.get("RGSTRNT_LAST_NM_DCLRNT"))) if part
        )
        primary_by_comlog[comlog] = {
            "comm_date": comm_date,
            "client_name": _nn(row.get("EN_CLIENT_ORG_CORP_NM_AN")) or None,
            "registrant_name": registrant or None,
        }

    rows: list[dict[str, Any]] = []
    for row in dpoh_rows:
        comlog = _nn(row.get("COMLOG_ID"))
        base = primary_by_comlog.get(comlog)
        if base is None:
            continue  # Outside the since-year window (or orphan row).
        dpoh_name = " ".join(
            part for part in (_nn(row.get("DPOH_FIRST_NM_PRENOM_TCPD")), _nn(row.get("DPOH_LAST_NM_TCPD"))) if part
        )
        if not dpoh_name:
            continue
        institution = _nn(row.get("INSTITUTION")) or _nn(row.get("OTHER_INSTITUTION_AUTRE"))
        rows.append(
            {
                "source_ref": comlog,
                "comm_date": base["comm_date"],
                "client_name": base["client_name"],
                "registrant_name": base["registrant_name"],
                "dpoh_name": dpoh_name,
                "dpoh_title": _nn(row.get("DPOH_TITLE_TITRE_TCPD")) or None,
                "institution": institution or None,
                "subjects": ", ".join(dict.fromkeys(subjects_by_comlog.get(comlog, []))) or None,
            }
        )
    return rows


def sync_lobby_communications(db: Session, zip_bytes: bytes, *, parliament_only: bool = True) -> int:
    """Upsert (communication, DPOH) rows; match parliamentarians to People."""
    rows = parse_lobby_zip(zip_bytes, since_year=settings.influence_since_year)
    name_index = build_person_name_index(db)

    # Preload existing keys once — the export has hundreds of thousands of
    # rows and a per-row SELECT would take hours.
    existing_keys = {
        (source_ref, dpoh_name)
        for source_ref, dpoh_name in db.execute(
            select(LobbyCommunication.source_ref, LobbyCommunication.dpoh_name)
        ).all()
    }

    count = 0
    for row in rows:
        institution = (row["institution"] or "").lower()
        if parliament_only and institution and not any(k in institution for k in PARLIAMENT_INSTITUTIONS):
            continue
        key = (row["source_ref"], row["dpoh_name"])
        if key in existing_keys:
            continue
        existing_keys.add(key)
        org = get_or_create_org(db, row["client_name"] or "")
        db.add(
            LobbyCommunication(
                source_ref=row["source_ref"],
                comm_date=row["comm_date"],
                client_name=row["client_name"],
                registrant_name=row["registrant_name"],
                dpoh_name=row["dpoh_name"],
                dpoh_title=row["dpoh_title"],
                institution=row["institution"],
                subjects=row["subjects"],
                client_org_id=org.id if org else None,
                dpoh_person_id=name_index.get(normalize_person_name(row["dpoh_name"])),
            )
        )
        count += 1
        if count % 2000 == 0:
            db.commit()
    db.commit()
    return count


# ---------------------------------------------------------------------------
# Elections Canada — contributions
# ---------------------------------------------------------------------------

CONTRIBUTION_ALIASES: dict[str, tuple[str, ...]] = {
    "contributor_name": ("Contributor name", "CONTRIBUTOR_NAME", "Contributor's name", "NAME"),
    "contributor_city": ("Contributor City", "Contributor's city", "CITY", "Contributor city"),
    "contributor_province": ("Contributor Province", "Contributor's province", "PROVINCE", "Contributor province"),
    "amount": ("Monetary amount", "AMOUNT", "Contribution amount", "MON_AMOUNT", "Amount"),
    "received_on": ("Contribution Received date", "DATE_RECEIVED", "Date received", "CONTRIBUTION_DATE"),
    "recipient_name": ("Recipient", "RECIPIENT", "Candidate name", "Recipient name"),
    "recipient_party": ("Political Party of Recipient", "Political party of recipient", "PARTY", "Recipient party"),
    "recipient_type": ("Political Entity", "Political entity", "ENTITY_TYPE", "Recipient type"),
    "form_id": ("Form ID", "FORM_ID"),
    "report_part": ("Part Number of Return", "Financial Report part"),
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
                "form_id": _get(row, header_map, "form_id") or None,
                "report_part": _get(row, header_map, "report_part") or None,
            }
        )
    return rows


def _contribution_fingerprint(row: dict[str, Any]) -> str:
    raw = "|".join(
        str(row.get(k) or "")
        for k in (
            "contributor_name", "contributor_city", "amount", "received_on",
            "recipient_name", "recipient_type", "form_id", "report_part",
        )
    )
    return hashlib.sha256(raw.encode()).hexdigest()


def _insert_contribution_rows(
    db: Session,
    rows: Iterable[dict[str, Any]],
    name_index: dict[str, int],
    existing_fingerprints: set[str],
) -> int:
    count = 0
    batch = 0
    for row in rows:
        fingerprint = _contribution_fingerprint(row)
        if fingerprint in existing_fingerprints:
            continue
        existing_fingerprints.add(fingerprint)
        db.add(
            Contribution(
                contributor_name=row["contributor_name"][:255],
                normalized_contributor=normalize_name(row["contributor_name"])[:255],
                contributor_city=(row["contributor_city"] or None) and row["contributor_city"][:128],
                contributor_province=(row["contributor_province"] or None) and row["contributor_province"][:8],
                amount=row["amount"],
                received_on=row["received_on"],
                recipient_name=row["recipient_name"][:255],
                recipient_party=(row["recipient_party"] or None) and row["recipient_party"][:255],
                recipient_person_id=name_index.get(normalize_person_name(row["recipient_name"])),
                recipient_type=row["recipient_type"],
                source_fingerprint=fingerprint,
            )
        )
        count += 1
        batch += 1
        if batch >= 5000:
            # Small-ish batches so one dupe fingerprint slipping past the
            # in-memory set doesn't invalidate a huge unit of work.
            try:
                db.commit()
            except Exception as exc:
                print(f"  batch commit failed at count={count}: {exc.__class__.__name__}", flush=True)
                db.rollback()
            batch = 0
    try:
        db.commit()
    except Exception:
        db.rollback()
    return count


def sync_contributions(db: Session, csv_text: str) -> int:
    """Small-CSV variant (tests/fixtures). Bulk data uses the file variant."""
    name_index = build_person_name_index(db)
    existing = {fp for (fp,) in db.execute(select(Contribution.source_fingerprint)).all()}
    return _insert_contribution_rows(db, parse_contributions_csv(csv_text), name_index, existing)


def sync_contributions_file(db: Session, zip_path: str) -> int:
    """Streaming ingest of the Elections Canada bulk export.

    The CSV inside is 2.17 GB / ~7M rows back to 2004 — we stream line by
    line (never materializing the file), keep candidate contributions from
    INFLUENCE_SINCE_YEAR on, and dedupe against a preloaded fingerprint set
    (a per-row SELECT would take hours)."""
    since_year = settings.influence_since_year
    name_index = build_person_name_index(db)
    existing = {fp for (fp,) in db.execute(select(Contribution.source_fingerprint)).all()}

    def streamed_rows() -> Iterable[dict[str, Any]]:
        with zipfile.ZipFile(zip_path) as archive:
            csv_names = [n for n in archive.namelist() if n.lower().endswith(".csv")]
            if not csv_names:
                raise ValueError(f"No CSV inside {zip_path}")
            with archive.open(csv_names[0]) as fh:
                text = io.TextIOWrapper(fh, encoding="utf-8-sig", errors="replace")
                reader = csv.DictReader(text)
                header_map = _build_header_map(reader.fieldnames or [], CONTRIBUTION_ALIASES)
                if "contributor_name" not in header_map or "recipient_name" not in header_map:
                    raise ValueError(f"Unrecognized contributions headers: {reader.fieldnames}")
                for row in reader:
                    entity = _get(row, header_map, "recipient_type")
                    if entity and not entity.lower().startswith("candidate"):
                        continue  # Per-MP view: candidate returns only.
                    received = _parse_date_any(_get(row, header_map, "received_on"))
                    if received is None or received.year < since_year:
                        continue
                    contributor = _get(row, header_map, "contributor_name")
                    recipient = _get(row, header_map, "recipient_name")
                    if not contributor or not recipient:
                        continue
                    amount_text = _get(row, header_map, "amount").replace("$", "").replace(",", "")
                    try:
                        amount = float(amount_text)
                    except ValueError:
                        continue
                    if amount <= 0:
                        continue
                    yield {
                        "contributor_name": contributor,
                        "contributor_city": _get(row, header_map, "contributor_city") or None,
                        "contributor_province": _get(row, header_map, "contributor_province") or None,
                        "amount": amount,
                        "received_on": received,
                        "recipient_name": recipient,
                        "recipient_party": _get(row, header_map, "recipient_party") or None,
                        "recipient_type": entity or None,
                        "form_id": _get(row, header_map, "form_id") or None,
                        "report_part": _get(row, header_map, "report_part") or None,
                    }

    return _insert_contribution_rows(db, streamed_rows(), name_index, existing)


# ---------------------------------------------------------------------------
# Download helpers (config-driven URLs; ZIP or plain CSV)
# ---------------------------------------------------------------------------

def _imports_path(url: str) -> "Path | None":
    """Manually-downloaded copy in IMPORTS_DIR wins (Cloudflare bypass)."""
    from pathlib import Path

    filename = url.rsplit("/", 1)[-1]
    candidate = Path(settings.imports_dir) / filename
    return candidate if candidate.exists() and candidate.stat().st_size > 0 else None


async def download_bytes(url: str) -> bytes | None:
    """Small exports (lobby zip ~24MB). Imports dir first, then HTTP.

    Note: lobbycanada.gc.ca sits behind Cloudflare Turnstile whose
    cf_clearance is bound to the browser's TLS fingerprint; httpx cannot
    reproduce it. Run `scripts/refresh_lobby_export.py` to drop the ZIP
    into IMPORTS_DIR — this function will find it there first.
    """
    if not url:
        return None
    local = _imports_path(url)
    if local is not None:
        return local.read_bytes()
    headers = {"User-Agent": f"Mozilla/5.0 (compatible; {settings.ingestion_user_agent})"}
    try:
        async with httpx.AsyncClient(headers=headers, timeout=300.0, follow_redirects=True) as client:
            response = await client.get(url)
            response.raise_for_status()
            # A Cloudflare interstitial is HTML, not a zip — treat as failure.
            if response.content[:2] != b"PK" and "zip" not in (
                response.headers.get("content-type") or ""
            ):
                return None
            return response.content
    except httpx.HTTPError:
        return None


async def download_to_file(url: str) -> str | None:
    """Large exports (elections zip 113MB): stream to IMPORTS_DIR, return path."""
    if not url:
        return None
    local = _imports_path(url)
    if local is not None:
        return str(local)
    from pathlib import Path

    dest_dir = Path(settings.imports_dir)
    try:
        dest_dir.mkdir(parents=True, exist_ok=True)
    except OSError:
        import tempfile

        dest_dir = Path(tempfile.gettempdir())
    dest = dest_dir / url.rsplit("/", 1)[-1]
    headers = {"User-Agent": f"Mozilla/5.0 (compatible; {settings.ingestion_user_agent})"}
    try:
        async with httpx.AsyncClient(headers=headers, timeout=1800.0, follow_redirects=True) as client:
            async with client.stream("GET", url) as response:
                response.raise_for_status()
                with open(dest, "wb") as fh:
                    async for chunk in response.aiter_bytes(1 << 20):
                        fh.write(chunk)
        return str(dest)
    except httpx.HTTPError:
        dest.unlink(missing_ok=True)
        return None
