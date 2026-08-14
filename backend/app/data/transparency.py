"""The transparency scorecard: what each government publishes, what we
ingest, and what is missing — with reasons.

This is deliberately a hand-maintained fact table. Every entry reflects
something we verified against the actual source (or its absence). When a
government starts publishing better data, update this file and build the
adapter — the scorecard is the to-do list.
"""
from __future__ import annotations

# coverage values: "full" | "partial" | "none"
SCORECARD: list[dict] = [
    {
        "name": "Parliament of Canada (federal)",
        "level": "federal",
        "jurisdiction_code": "ca",
        "votes": "full",
        "attendance": "full",
        "money": "full",
        "lobbying": "full",
        "notes": "Votes, bills, expenses, lobbying, donations — all from official APIs and exports.",
        "sources": [
            {"label": "OpenParliament", "url": "https://openparliament.ca"},
            {"label": "LEGISinfo", "url": "https://www.parl.ca/legisinfo"},
            {"label": "Proactive disclosure", "url": "https://www.ourcommons.ca/proactivedisclosure"},
        ],
    },
    {
        "name": "Legislative Assembly of Ontario",
        "level": "provincial",
        "jurisdiction_code": "ca-on",
        "votes": "full",
        "attendance": "partial",
        "money": "none",
        "lobbying": "none",
        "notes": "Bills and division votes scraped nightly from ola.org (no API exists). "
        "Attendance is derived from division participation. MPP expenses are PDF-only; "
        "Ontario's lobbyist registry is not yet ingested.",
        "sources": [{"label": "ola.org bills", "url": "https://www.ola.org/en/legislative-business/bills"}],
    },
    {
        "name": "Other provincial & territorial legislatures (12)",
        "level": "provincial",
        "jurisdiction_code": None,
        "votes": "none",
        "attendance": "none",
        "money": "none",
        "lobbying": "none",
        "notes": "Members and contact info sync weekly from Represent. No machine-readable "
        "votes ingested yet — each legislature publishes differently; adapters wanted.",
        "sources": [{"label": "Represent API", "url": "https://represent.opennorth.ca"}],
    },
    {
        "name": "Toronto City Council",
        "level": "municipal",
        "jurisdiction_code": "toronto-city-council",
        "votes": "full",
        "attendance": "none",
        "money": "none",
        "lobbying": "none",
        "notes": "One of only two Canadian cities publishing a machine-readable per-member "
        "voting record. Lobbyist registry export exists but is not yet ingested.",
        "sources": [
            {
                "label": "Voting record (Open Data)",
                "url": "https://open.toronto.ca/dataset/members-of-toronto-city-council-voting-record/",
            }
        ],
    },
    {
        "name": "Vancouver City Council",
        "level": "municipal",
        "jurisdiction_code": "vancouver-city-council",
        "votes": "full",
        "attendance": "none",
        "money": "none",
        "lobbying": "none",
        "notes": "Publishes a machine-readable per-member voting record (80k+ records).",
        "sources": [
            {
                "label": "Council voting records (Open Data)",
                "url": "https://opendata.vancouver.ca/explore/dataset/council-voting-records/",
            }
        ],
    },
    {
        "name": "Mississauga City Council",
        "level": "municipal",
        "jurisdiction_code": "mississauga-city-council",
        "votes": "partial",
        "attendance": "full",
        "money": "none",
        "lobbying": "none",
        "notes": "No open-data voting record. We parse the official eScribe minutes: "
        "attendance, motions with movers/seconders, and per-member votes where the minutes "
        "print them. Annual pay/expense statements (Municipal Act s.284) are PDF-only.",
        "sources": [{"label": "Council minutes (eScribe)", "url": "https://pub-mississauga.escribemeetings.com"}],
    },
    {
        "name": "Brampton City Council",
        "level": "municipal",
        "jurisdiction_code": "brampton-city-council",
        "votes": "partial",
        "attendance": "full",
        "money": "none",
        "lobbying": "none",
        "notes": "eScribe minutes: attendance, motions, and recorded votes when demanded.",
        "sources": [{"label": "Council minutes (eScribe)", "url": "https://pub-brampton.escribemeetings.com"}],
    },
    {
        "name": "Ottawa City Council",
        "level": "municipal",
        "jurisdiction_code": "ottawa-city-council",
        "votes": "partial",
        "attendance": "full",
        "money": "none",
        "lobbying": "none",
        "notes": "eScribe minutes: attendance, motions, and recorded votes when demanded.",
        "sources": [{"label": "Council minutes (eScribe)", "url": "https://pub-ottawa.escribemeetings.com"}],
    },
    {
        "name": "Calgary City Council",
        "level": "municipal",
        "jurisdiction_code": "calgary-city-council",
        "votes": "partial",
        "attendance": "full",
        "money": "none",
        "lobbying": "none",
        "notes": "eScribe minutes: attendance, motions, and recorded votes when demanded.",
        "sources": [{"label": "Council minutes (eScribe)", "url": "https://pub-calgary.escribemeetings.com"}],
    },
    {
        "name": "Halifax Regional Council",
        "level": "municipal",
        "jurisdiction_code": "halifax-regional-council",
        "votes": "partial",
        "attendance": "full",
        "money": "none",
        "lobbying": "none",
        "notes": "eScribe minutes: attendance, motions, and recorded votes when demanded.",
        "sources": [{"label": "Council minutes (eScribe)", "url": "https://pub-halifax.escribemeetings.com"}],
    },
    {
        "name": "~100 other municipal councils",
        "level": "municipal",
        "jurisdiction_code": None,
        "votes": "none",
        "attendance": "none",
        "money": "none",
        "lobbying": "none",
        "notes": "People and contact info only (Represent, weekly). Not covered and why: "
        "Winnipeg, Surrey, Windsor, Regina, Kelowna and Burlington use meeting platforms "
        "we have no parser for yet; Montreal publishes no council-vote dataset at all. "
        "Most decisions at every council pass on unrecorded voice votes — no data source "
        "can recover per-member positions for those.",
        "sources": [],
    },
]

# What voice votes make unknowable — shown verbatim on the transparency page.
HONEST_LIMITS = [
    "Most municipal council decisions pass on unrecorded voice votes. Unless a member "
    "demands a recorded vote, no per-member position exists anywhere — not even in the "
    "official minutes. Absence of a vote here is absence in the public record itself.",
    "Attendance is parsed from the official minutes' attendance section. Members who "
    "joined or left mid-term will show fewer eligible meetings; partial-day attendance "
    "is counted as present.",
    "Name matching from minutes to people is automated (honorifics, initials and wards "
    "are normalized). Unmatched names are logged and re-checked, never guessed.",
    "Provincial and municipal money (salaries, expenses, donations, lobbying) is mostly "
    "published as PDFs or not at all — it is on the roadmap per city, and its absence "
    "is marked on each profile.",
]
