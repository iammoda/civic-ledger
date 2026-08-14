# Civic Ledger (working name)

**Type a problem → see who's responsible, how your MP voted, who funds and lobbies them, and contact them in one tap — in plain language anyone can understand.**

A non-partisan, open-source civic accountability platform for **Canada**. English-first (bilingual-ready schema; French is the #1 fast-follow).

## The mission

Hold Canadian politicians accountable. Make it easy for anyone to see how their representatives are helping or hurting them — and to act on it. The combined view of *bills × votes × money × lobbying* exists today only in enterprise tools sold to lobbyists for $5–20k/yr. This platform gives it to citizens. Not for profit — the information is the product.

## Core features

1. **Ask** — natural-language entry: "I can't afford rent" → which level of government is responsible (federal/provincial/municipal), **the responsible minister and opposition critics** (real people with contact buttons, not abstractions), related bills (live *and* dead), how *your* MP voted, open petitions/consultations, and a ready-to-send letter. Provincial issues hand off gracefully: "This is provincial — your MPP is X, contact them here" (via Represent API, no provincial data ingestion required).
2. **MP accountability** — real stats: attendance, party-line %, dissents, full voting record, sponsored bills, committee work, seat-margin context, floor-crossing/resignation events.
3. **The Graveyard (dead-bill tracking)** — most bills die without a visible vote. We track *how* each bill died (defeated, died in committee, prorogation, died in Senate) and *who is attributable* — including lobbying activity clustered right before a quiet death.
4. **Money & Influence** — donations (Elections Canada), lobbying (Registry of Lobbyists, incl. subject codes), government contracts/grants, ethics/travel/gifts registries — entity-resolved into a relationship graph with pattern detectors: family payments, donor→contract matching, lobbying-before-vote/death, patronage appointments, revolving door. **Every flag requires human review before publishing** and links to primary-source documents. In-app corrections/dispute form.
5. **Behavior** — party-discipline scores, side-by-side MP comparison; promise tracking via Polimetre link-out (attributed).
6. **Personalization, zero accounts** — postal code → your full representative ladder; "Set as my MP" lives in your browser's localStorage only (nothing stored server-side, no sign-in anywhere). Every vote page then shows how *your* MP voted. **No email, no accounts, no tracking.**
7. **Action layer** — Claude-drafted contact-your-MP letters citing their actual ballots; **"Contact your MP about this" on every page**; petition and consultation deadlines matched to your topics.

## Plain Language System

- **Enforced grade 6–8 reading level** — every AI summary is readability-scored; too complex gets auto-regenerated before it can publish
- **Layered depth** — one plain sentence → three bullets (what it does / who it affects / what changes for you) → detailed summary → actual legal text with jargon tooltips
- **Vote direction normalization** — procedural motions invert meaning (Yea on a hoist amendment *kills* the bill). We always show **"voted to advance" / "voted to block"**, never raw Yea/Nay
- **Party-context one-liners** — "voted to block, along with all 119 of her party" vs "one of only 3 Conservatives to dissent"
- Jargon glossary tooltips, Simple/Standard/Expert toggle, contextual civics-101 explainers, colloquialism aliases ("carbon tax" → "fuel charge"), "was this clear?" feedback loop

## Neutrality by architecture

- Identical detectors, stats, prompts, and UI run on every member of every party — no party-specific logic exists in the codebase
- Facts + citations only; we never editorialize — the evidence decides
- Primary sources only (Parliament, Elections Canada, official registries) — no media, no advocacy orgs
- Automated bias audits (tone symmetry across parties, published on the methodology page), human review queue, public corrections changelog
- Consumed third-party analysis is always attributed ("Summary based on Library of Parliament...") — never silently blended
- Neutrality = symmetric *process*, not forced equal outcomes

## Privacy posture

- Location is **asked, never detected** — we store only the derived riding ID, never your address; works logged-out
- Interests are **explicit follows only** — suggestions, never auto-profiling; no ad-tech, no cookies, no third-party analytics (server-side aggregate counters only); full data export/delete

## Data sources (all Canadian, all primary)

| Signal | Source |
|---|---|
| Votes / bills / debates | OpenParliament API (1994+), LEGISinfo, OurCommons (fallback ingestion) |
| Bill summaries (pre-analyzed) | LEGISinfo descriptions, Library of Parliament Legislative Summaries |
| MP lookup | Represent API (postal code → riding; all-level rep ladder) |
| Provincial & municipal people | Represent API bulk rosters (13 legislatures, ~108 councils; weekly sync) |
| Ontario bills / votes / ballots | ola.org bill pages (status tables + division rolls; nightly sync) |
| Municipal meetings (Mississauga, Brampton, Ottawa, Calgary, Halifax) | Official eScribe minutes — attendance, motions, per-member votes, conflict declarations (nightly) |
| Toronto & Vancouver council votes | City open-data voting records (weekly) |
| Cabinet / critics | OurCommons ministry data, party shadow-cabinet listings |
| Donations | Elections Canada open data |
| Lobbying | Registry of Lobbyists monthly exports (incl. subject-matter codes) |
| Money out | Proactive-disclosure contracts & grants |
| Conflicts | Ethics Commissioner registry, sponsored travel, gifts, MP expenditures |
| Participation | HoC e-petitions, Canada Gazette, Consulting with Canadians |
| Family relations (entity graph seed) | Wikidata (CC0) |
| Promises | Polimetre (Laval University) — attributed link-out |

## Architecture principles

- **Ingestion is 100% deterministic code — zero LLM scraping.** Structured APIs/CSV/XML parsed directly into Postgres
- **Eager embeddings, lazy analysis** — the full archive (1994+) is ingested free and embedded (~$100 one-time); Claude analysis is generated eagerly for the current Parliament + daily new content, and **on first view (then cached forever) for history**. Spend follows real usage
- Claude Sonnet 5 (analysis, Ask, extraction) + Haiku 4.5 (bulk tagging) + Batch API, with a cost ledger, hard budget caps, and a spend dashboard
- "Data Gap" is a first-class UI state — missing data is shown honestly, never papered over
- **Built to survive:** maintenance-mode architecture (AI analysis can pause; ingestion and core pages run unattended at ~$50/mo), upstream-source fallbacks (direct OurCommons/LEGISinfo ingestion if OpenParliament dies), cost circuit breakers on Ask, legal insulation via review queue + citations + corrections process. Target: <2 hrs/month human attention

## Stack

- **Frontend:** Next.js 16 (App Router), TypeScript, Tailwind CSS 4, hand-rolled component library (no UI framework), horizontal-scroll mobile nav
- **Backend:** FastAPI, SQLAlchemy 2.x, Alembic, PostgreSQL + pgvector, Redis + arq workers
- **Auth:** none — the platform is fully anonymous. Admin review queue uses a static `ADMIN_API_TOKEN` header.
- **Hosting:** Vercel + Fly/Railway + Neon Postgres + Upstash Redis; Sentry; GitHub Actions CI/CD
- **License:** AGPL-3.0 (proposed), public repo at launch

## Build phases

| # | Phase | Status |
|---|---|---|
| 0 | Foundation — git, dependency upgrades, pgvector, bug fixes, arq cron, env config | ✅ shipped |
| 1 | Canada pipeline — full persistence, ballots, dead-bill detection + attribution, derived stats, floor-crossing events | ✅ shipped |
| 2 | Claude intelligence — layered summaries, vote direction normalization, readability gate, lazy-analysis engine, cost ledger + hard caps | ✅ shipped |
| 3 | Search & Ask — hybrid FTS+vector search, cited answers, jurisdiction classifier, colloquialism aliases | ✅ shipped |
| 4 | Accounts — later **removed by design**: replaced with anonymous postal lookup + device-only "my MP" (localStorage) | ✅ shipped, then simplified |
| 5 | Participation — e-petitions with deadlines/signatures/topic matching, in search + Ask evidence | ✅ shipped |
| 6 | Money & Integrity — lobbying + donations ingestion, entity resolution, 3 party-blind detectors, human review queue, corrections form, methodology page | ✅ shipped |
| 7 | Behavior — voting records with party-context lines, dissent filter, MP comparison, Polimetre link-out | ✅ shipped |
| 8 | Actions & notifications — letters citing real ballots, contact-everywhere, notification matcher, recess-aware catch-me-up feed | ✅ shipped |
| 9 | Growth, trust & hardening — ✅ share cards (OG images), rate limits + /ask quotas + answer cache, privacy/terms, sitemap/robots/JSON-LD, error/loading pages, a11y pass · 🔜 cite-this permalinks, CSV exports, bias audits, aggregate counters, seat margins | 🔶 mostly shipped |
| 10 | Production deployment — ✅ GitHub Actions CI, backend Dockerfile, real healthcheck, debug-off prod config, nightly pg_dump script · 🔜 Vercel + Fly/Railway + Neon + Upstash, Sentry, staging, spend dashboard | 🔶 in progress |
| 11 | Backfill — embeddings archive-wide, eager current Parliament, lazy engine for history | 🔜 after 10 |

**Also shipped since:** MP expense reports (scraper + 5 review-gated detectors + searchable `/expenses` explorer + MP-page cards), the Graveyard UI, representative ladder (MP/MPP/councillor contacts), committees + memberships ingestion, cabinet-minister tracking with a "responsible minister" card in Ask (guardrailed — shown only when evidence supports it), and a plain-language glossary with jargon tooltips. **Engagement overhaul (2026-08):** sign-in removed entirely; bill-aware plain-language vote sentences ("MPs passed Bill C-30 at third reading, 166–159 — next stop: the Senate"); party-color donut charts + party identity system + MP photos; bill journey stepper; missed-votes tracking with participation trends; lobbying explainers, AI org blurbs, per-MP searchable lobbying pages and subject chips; budget-utilization + spend percentiles on expenses; "This week in Ottawa" digest; The Receipts leaderboards (with printed caveats — the TheyWorkForYou lesson); device-only "my MP"; public charter page. The database runs locally on an external drive (`scripts/db-start.sh`) with live data: 343 MPs, 57k+ ballots, 100k+ expense line items and growing.

**Fast-follow (parked):** French (#1), opposition-critic tracking, Gazette consultations, elections module, own promise tracker, say-vs-vote flags, keyed public API, embeddable widgets, other provincial legislatures' bills/votes (people are already in), more eScribe cities (Hamilton/London/Markham/etc. — add a tenant config entry), Toronto lobbyist registry ZIP ingestion, municipal pay/expense statements (Municipal Act s.284, per-city PDFs), non-eScribe cities (Winnipeg/Surrey/Windsor need other-vendor parsers), provincial money (lobbyist registries, Elections Ontario), US (indefinitely).

**Current test suite:** 135 backend tests passing (CI-enforced with ruff); frontend builds, typechecks and lints clean.

**Budget:** ~$1.5–2.5k all-in year one, hard-capped. Publicly useful after Phase 4.

## Quick start

1. Copy `.env.example` to `.env` and fill in keys (Anthropic, OpenAI).
2. Start infrastructure with `docker compose up -d` (or `scripts/db-start.sh` for the external-drive setup).
3. Install frontend dependencies with `npm install`.
4. Create a Python virtualenv and install `backend/requirements.txt`.
5. Apply migrations: `cd backend && PYTHONPATH=. alembic upgrade head` (Alembic is the only schema path).
6. Run `npm run dev` from the repo root.

**Backups:** `scripts/db-backup.sh` dumps the DB (custom format, rotated, optional rclone offsite) — run it nightly from cron. **Abuse protection:** per-IP rate limits guard `/ask`, `/actions/letter`, `/corrections` and `/search`; identical Ask questions are served from a 24h answer cache; a site-wide daily generation quota degrades Ask to search-only rather than failing.

### Enabling AI summaries for new bills

Every current bill (Parliament 45) already ships with a grounded, readability-gated
plain-language summary. For bills that arrive later:

1. Put your key in `.env`: `ANTHROPIC_API_KEY=sk-ant-…`
2. See what's missing and what it costs: `PYTHONPATH=backend python3 scripts/backfill_ai.py --dry-run`
3. Run it: `PYTHONPATH=backend python3 scripts/backfill_ai.py`
4. Restart the worker — the hourly cron then summarizes new bills automatically.

Spending is hard-capped by `LLM_MONTHLY_BUDGET_USD`; published summaries are cached forever.

## Acceptance test

"I can't afford rent" → *"Rent rules are mostly provincial — your MPP is [name], contact them here. Federally, housing funding flows through [minister], held to account by critics [names]. Here's the housing bill that died in committee last fall, who killed it, who lobbied the week before, and how your MP voted — 'voted to block, along with her whole party.' Send them a letter about it in one tap."* — readable by a 12-year-old, cited to primary sources, no email, no tracking, open source.
