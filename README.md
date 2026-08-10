# Civic Ledger

**Type a problem → see who's responsible, how your representatives voted, who funds and lobbies them, and what you can do about it — in plain language anyone can understand.**

A non-partisan civic accountability platform for **Canada and the USA**. Public product, English-first (bilingual-ready schema).

## The mission

Pieces of this exist (GovTrack for US votes, OpenSecrets for US money, OpenParliament for Canada) — but nobody connects them. The combined view of *bills × votes × money × lobbying* is sold to lobbyists for $5k–20k/yr (Quorum, FiscalNote). This platform gives it to citizens.

## Core features

1. **Ask** — natural-language entry point: "I can't afford rent" → which level of government is responsible (federal/provincial/municipal), which ministry, related bills (live *and* dead), how *your* rep voted, open petitions/comment periods, and a ready-to-send letter. Answers are cited, plain-language-first.
2. **Rep accountability** — real stats per MP/member of Congress: attendance, party-line %, dissents, full voting record, sponsored bills, committee work.
3. **The Graveyard (dead-bill tracking)** — most bills die without a visible vote. We track *how* each bill died (defeated, died in committee, prorogation, failed cloture, veto, cross-chamber death) and *who is attributable* — including lobbying activity clustered right before a quiet death.
4. **Money & Influence engine** — donors (FEC, Elections Canada), lobbying (LDA, Registry of Lobbyists), government contracts/grants (USAspending, CA proactive disclosure), financial disclosures and STOCK Act trades — entity-resolved into a relationship graph with pattern detectors: nepotism signals, donor→contract matching, lobbying-before-vote/death, stock-trade conflicts, revolving door, patronage appointments. **Every flag requires human review before publishing** and links to primary-source documents.
5. **Behavior & promises** — party-discipline scores, say-vs-vote contradiction flags, side-by-side rep comparison, and a promise tracker (kept / broken / stalled) matched to real votes and spending.
6. **Elections module** — incumbent term report cards, challenger lists, seat-margin context, in-app election reminders.
7. **Personalization** — sign in (Google), enter postal code (CA) or address (US) → your reps; follow topics, reps, bills, or save an Ask question as a watched issue. In-app notification center + "catch me up" view. **No email anywhere.**
8. **Action layer** — Claude-drafted contact-your-rep letters citing their actual ballots, consultation/brief deadlines, regulatory comment periods (the US petition-equivalent).

## Plain Language System ("idiot-proof" by design)

- **Enforced grade 6–8 reading level** — every AI summary is readability-scored (Flesch–Kincaid); too complex gets auto-regenerated before it can publish
- **Layered depth** — one plain sentence → three bullets (what it does / who it affects / what changes for you) → detailed summary → actual legal text with jargon tooltips
- **Vote direction normalization** — procedural motions invert meaning (Yea on a hoist amendment *kills* the bill). We always show **"voted to advance" / "voted to block"**, never raw Yea/Nay
- Jargon glossary tooltips, Simple/Standard/Expert sitewide toggle, contextual civics 101 explainers, "was this clear?" feedback loop

## Neutrality by architecture

- Identical detectors, stats, prompts, and UI run on every member of every party — no party-specific logic exists in the codebase
- Facts + citations only; we never editorialize ("voted to block", "met 14× with X lobbyists") — the evidence decides
- Primary sources only (Parliament, Congress, FEC, Elections Canada, official registries) — no media, no advocacy orgs
- Automated bias audits (tone symmetry across parties, published on the methodology page), human review queue, public corrections changelog
- Neutrality = symmetric *process*, not forced equal outcomes

## Privacy posture

- Location is **asked, never detected** — we store only the derived riding/district ID, never your address or coordinates; works logged-out
- Interests are **explicit follows only** — suggestions, never auto-profiling; no ad-tech, no third-party analytics; full data export/delete

## Data sources

| Signal | Canada | USA |
|---|---|---|
| Votes / bills | OpenParliament (1994+), LEGISinfo, OurCommons | Congress.gov API, House/Senate roll-call XML (1989+), Voteview (1789+) |
| Rep lookup | Represent API (postal code) | Census Geocoder (address → district) |
| Donors | Elections Canada open data | FEC API (1979+) |
| Lobbying | Registry of Lobbyists monthly exports | Senate LDA API (lda.gov) |
| Money out | Proactive disclosure contracts/grants | USAspending API |
| Conflicts | Ethics Commissioner registry, expenses | Financial disclosures, STOCK Act PTRs |
| Participation | HoC e-petitions, Canada Gazette consultations | Federal Register / Regulations.gov comment periods |

## Stack

- **Frontend:** Next.js 16 (App Router), TypeScript, Tailwind CSS 4, shadcn/ui
- **Backend:** FastAPI, SQLAlchemy 2.x, Alembic, PostgreSQL + pgvector, Redis + arq workers
- **AI:** Claude Sonnet 5 (analysis/extraction/Ask), Claude Haiku 4.5 (bulk tagging), Batch API for backfills, OpenAI `text-embedding-3-small` for semantic search — with a cost ledger, hard budget caps, and per-checkpoint spend reports
- **Auth:** better-auth, Google OAuth only (zero email infrastructure)
- **Hosting:** Vercel (frontend) + Fly/Railway (API/workers) + Neon Postgres + Upstash Redis; Sentry, CI/CD via GitHub Actions

## Design principles

- ≤5 top-level nav sections; progressive disclosure — dense data lives one click deeper
- Quiet, batched notifications; no gamification, no engagement tricks — **the information is the product**
- "Data Gap" is a first-class UI state: missing data is shown honestly, never papered over
- Built to survive: maintenance-mode architecture (AI analysis can pause; ingestion and core pages run unattended at ~$50/mo), upstream-source fallbacks, cost circuit breakers on `/ask`, legal insulation via review queue + citations + corrections process

## Build phases

| # | Phase |
|---|---|
| 0 | Foundation — git, dependency upgrades, pgvector, bug fixes, arq cron, env config |
| 1 | Canada pipeline — full persistence, ballots, dead-bill detection + attribution, amendments, derived stats |
| 2 | Claude intelligence — structured analyses, vote direction normalization, glossary, readability gate, cost caps |
| 3 | Search & Ask — hybrid FTS+vector search, cited RAG answers, jurisdiction classifier |
| 4 | Accounts — Google sign-in, rep lookup, topic follows, Simple/Standard/Expert toggle |
| 5 | US adapter — Congress.gov, roll-call XML, Voteview history, US dead-bill inference |
| 6 | Participation — e-petitions, Gazette consultations, Federal Register comment periods |
| 7 | Money & Integrity engine — donors, lobbying, contracts, disclosure extraction, entity resolution, 9 pattern detectors, human review queue |
| 8 | Behavior & promises — discipline scores, say-vs-vote flags, rep comparison, promise tracker |
| 9 | Elections module — report cards, challengers, seat margins, reminders |
| 10 | Actions & notifications — drafted letters, deadline alerts, in-app notification center |
| 11 | Growth, trust & hardening — share cards, public read API, bias audits, rate limits, WCAG AA, tests |
| 12 | Production deployment — CI/CD, managed infra, monitoring, staging, backups, spend dashboard |
| 13 | Backfill campaign — newest→oldest with per-checkpoint spend approval: Canada 1994+, US 1990+ (raw to 1789), integrity extraction 2008+ |

**Budget:** ~$21–37k all-in year one (backfill is a durable data asset, not burn), hard-capped with checkpoint approvals. The site becomes publicly useful after Phase 4; value ships incrementally every phase after.

## Quick start

1. Copy `.env.example` to `.env` and fill in keys (Anthropic, OpenAI, Google OAuth, congress.gov, FEC, LDA).
2. Start infrastructure with `docker compose up -d`.
3. Install frontend dependencies with `npm install`.
4. Create a Python virtualenv and install `backend/requirements.txt`.
5. Run `npm run dev` from the repo root.

## Current state

- Monorepo scaffold with federal domain model (17 tables, bilingual/multi-jurisdiction-ready)
- FastAPI internal `/v1` API skeleton
- Ingestion and LLM workflow stubs (Phase 0–1 rebuild in progress)
- Next.js consumer app shell for V1 pages

## Acceptance criteria

- "I can't afford rent" → plain-language answer naming the responsible level of government, related bills **including killed ones and who killed them**, your MP's translated ballots ("voted to block"), donor/lobbying context, and a ready-to-send letter — understandable by a 12-year-old, backed by cited primary sources
- Any rep page: real voting stats, full record, donors, lobbying meetings, integrity flags with source documents (post-review only)
- Search "pharmacare" → the dead bills, how each died, who killed them
- Following "Housing" + your MP → in-app feed items when votes, bills, deaths, petitions, or comment periods land
- Live at a public URL with CI, monitoring, backups, and LLM spend caps enforced
