import Link from "next/link";

import { DataGap } from "@/components/data-gap";
import { LevelBadge, WhoDoesWhat } from "@/components/level-badge";
import { PageShell } from "@/components/page-shell";
import { listBills, listPoliticians, listVotes } from "@/lib/api";
import { billTypeLabel, formatDateShort, humanizeBillTitle, humanizeMotion, humanizeStatus } from "@/lib/humanize";
import { lookupPostal } from "@/lib/me";

export const metadata = {
  title: "Civic Ledger — who represents you, and what have they done?"
};

export default async function HomePage({
  searchParams
}: {
  searchParams: Promise<{ postal?: string }>;
}) {
  const { postal } = await searchParams;
  const postalQuery = (postal ?? "").trim();
  const [politicians, votes, bills, lookup] = await Promise.all([
    listPoliticians({ limit: 1 }),
    listVotes(),
    listBills(),
    postalQuery ? lookupPostal(postalQuery) : Promise.resolve(null)
  ]);

  const apiUp = Boolean(politicians || votes || bills);
  const mpCount = politicians?.meta.total ?? 0;
  const voteCount = votes?.meta.total ?? 0;
  const billCount = bills?.meta.total ?? 0;

  return (
    <PageShell
      eyebrow="Canada · All three levels of government"
      title="Who represents you — and what have they actually done?"
      description="Enter your postal code to meet all your representatives. Ask any question. Every claim cites the official record."
    >
      {/* Postal-first: the fastest way to make it personal. Nothing stored. */}
      <section className="mb-8">
        <div className="glass-card p-6 sm:p-8">
          <label htmlFor="home-postal" className="text-sm font-semibold uppercase tracking-wide text-accent">
            Start with your postal code
          </label>
          <form action="/" method="get" className="mt-3 flex flex-col gap-3 sm:flex-row">
            <input
              id="home-postal"
              name="postal"
              defaultValue={postalQuery}
              placeholder="K1A 0A6"
              maxLength={7}
              required
              className="w-full rounded-lg border border-border bg-white px-4 py-3 text-lg outline-none focus:border-accent sm:max-w-xs"
            />
            <button
              type="submit"
              className="rounded-lg bg-ink px-6 py-3 text-base font-semibold text-white transition hover:bg-slate-700"
            >
              Find my representatives
            </button>
            <span className="self-center text-xs text-slate-500">
              Used for the lookup only — never stored.
            </span>
          </form>

          {postalQuery && lookup === null ? (
            <p className="mt-4 text-sm text-signal">
              That doesn&apos;t look like a valid postal code (format: K1A 0A6), or the lookup service is
              briefly unavailable.
            </p>
          ) : null}

          {lookup?.ladder?.length ? (
            <div className="mt-5 grid gap-2">
              {lookup.ladder.map((rep) => (
                <div
                  key={`${rep.office}-${rep.name}`}
                  className="flex flex-wrap items-center gap-3 rounded-xl border border-border bg-white p-3"
                >
                  <LevelBadge level={rep.level} />
                  <div className="min-w-0 flex-1">
                    <p className="font-semibold">
                      {rep.person_slug ? (
                        <Link href={`/politicians/${rep.person_slug}`} className="text-accent hover:underline">
                          {rep.name}
                        </Link>
                      ) : (
                        rep.name
                      )}
                      <span className="ml-2 font-normal text-slate-500">
                        {rep.office}
                        {rep.party_name ? ` · ${rep.party_name}` : ""}
                      </span>
                    </p>
                    <p className="truncate text-sm text-slate-500">{rep.district_name}</p>
                  </div>
                  {rep.level === "federal" && rep.person_slug ? (
                    <Link
                      href={`/politicians/${rep.person_slug}`}
                      className="rounded-lg bg-teal-700 px-4 py-2 text-sm font-semibold text-white transition hover:bg-teal-800"
                    >
                      Full record →
                    </Link>
                  ) : rep.email ? (
                    <a
                      href={`mailto:${rep.email}`}
                      className="rounded-lg border border-border px-4 py-2 text-sm font-semibold text-slate-700 transition hover:border-accent hover:text-accent"
                    >
                      Contact
                    </a>
                  ) : rep.url ? (
                    <a
                      href={rep.url}
                      target="_blank"
                      rel="noreferrer"
                      className="rounded-lg border border-border px-4 py-2 text-sm font-semibold text-slate-700 transition hover:border-accent hover:text-accent"
                    >
                      Official page ↗
                    </a>
                  ) : null}
                </div>
              ))}
              <p className="text-xs text-slate-500">
                Federal MPs get the full record here (votes, money, expenses). Provincial and municipal
                representatives are contact-only for now — that data lives with their governments.
              </p>
            </div>
          ) : postalQuery && lookup && !lookup.ladder?.length ? (
            <p className="mt-4 text-sm text-slate-600">No representatives found for that postal code.</p>
          ) : null}
        </div>
      </section>

      {/* Ask */}
      <section className="mb-8">
        <div className="glass-card p-6 sm:p-8">
          <label htmlFor="home-q" className="text-sm font-semibold uppercase tracking-wide text-accent">
            Or ask anything
          </label>
          <form action="/ask" method="get" className="mt-3 flex flex-col gap-3 sm:flex-row">
            <input
              id="home-q"
              name="q"
              minLength={8}
              maxLength={500}
              required
              placeholder="I can't afford rent — who is responsible?"
              className="w-full rounded-lg border border-border bg-white px-4 py-3 text-lg outline-none focus:border-accent"
            />
            <button
              type="submit"
              className="rounded-lg bg-ink px-6 py-3 text-base font-semibold text-white transition hover:bg-slate-700"
            >
              Ask
            </button>
          </form>
          <div className="mt-3 flex flex-wrap gap-2 text-sm">
            {["Why are groceries so expensive?", "What happened to pharmacare?", "Is anyone fixing housing?"].map(
              (example) => (
                <Link
                  key={example}
                  href={`/ask?q=${encodeURIComponent(example)}`}
                  className="rounded-lg border border-border bg-white px-3 py-1.5 text-slate-600 transition hover:border-accent hover:text-accent"
                >
                  {example}
                </Link>
              )
            )}
          </div>
        </div>
      </section>

      {/* Who does what */}
      <section className="mb-8">
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-500">
          Who does what in Canada
        </h2>
        <WhoDoesWhat />
      </section>

      {/* Fast fact + explore */}
      <section className="mb-8">
        <div className="glass-card p-6 sm:p-8">
          {apiUp ? (
            <p className="text-xl font-medium leading-8 sm:text-2xl sm:leading-9">
              Tracking <span className="font-bold text-accent">{mpCount.toLocaleString()} federal politicians</span>,{" "}
              <span className="font-bold text-accent">{voteCount.toLocaleString()} recorded votes</span>, and{" "}
              <span className="font-bold text-accent">{billCount.toLocaleString()} bills</span> — every vote
              translated to plain language, every dead bill with a cause of death, updated every 30 minutes.
            </p>
          ) : (
            <DataGap
              title="Data temporarily unavailable"
              detail="The data service isn't responding right now. Nothing is wrong with your connection — try again in a minute."
            />
          )}
          <div className="mt-5 flex flex-wrap gap-2">
            <Link href="/bills" className="rounded-lg bg-ink px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-slate-700">
              Bills
            </Link>
            <Link href="/votes" className="rounded-lg border border-border bg-white px-4 py-2.5 text-sm font-semibold text-slate-700 transition hover:border-accent hover:text-accent">
              Votes
            </Link>
            <Link href="/petitions" className="rounded-lg border border-border bg-white px-4 py-2.5 text-sm font-semibold text-slate-700 transition hover:border-accent hover:text-accent">
              Petitions
            </Link>
            <Link href="/expenses" className="rounded-lg border border-border bg-white px-4 py-2.5 text-sm font-semibold text-slate-700 transition hover:border-accent hover:text-accent">
              MP expenses
            </Link>
            <Link href="/graveyard" className="rounded-lg border border-signal/40 bg-white px-4 py-2.5 text-sm font-semibold text-signal transition hover:bg-signal hover:text-white">
              The Graveyard
            </Link>
            <Link href="/search" className="rounded-lg border border-border bg-white px-4 py-2.5 text-sm font-semibold text-slate-700 transition hover:border-accent hover:text-accent">
              Search
            </Link>
          </div>
        </div>
      </section>

      {/* Recent activity, humanized */}
      <section className="grid gap-6 lg:grid-cols-2">
        <div className="glass-card p-6">
          <div className="flex items-center justify-between">
            <h2 className="text-xl font-bold">Latest votes</h2>
            <Link href="/votes" className="text-sm font-semibold text-accent hover:underline">
              See all
            </Link>
          </div>
          <div className="mt-4 space-y-3">
            {votes?.items.slice(0, 5).map((vote) => {
              const motion = humanizeMotion(vote.description_en);
              return (
                <Link
                  key={`${vote.chamber}-${vote.session}-${vote.number}`}
                  href={`/votes/${vote.chamber}/${vote.session}/${vote.number}`}
                  className="block rounded-xl border border-border bg-white p-4 transition hover:border-accent"
                >
                  <div className="flex items-center gap-2">
                    <LevelBadge level="federal" />
                    <span className="text-xs text-slate-500">{formatDateShort(vote.occurred_on)}</span>
                    <span
                      className={`ml-auto text-sm font-semibold ${vote.result === "Passed" ? "text-teal-700" : "text-signal"}`}
                    >
                      {vote.result === "Passed" ? "Passed" : vote.result === "Negatived" ? "Failed" : vote.result}{" "}
                      {vote.yea_total}–{vote.nay_total}
                    </span>
                  </div>
                  <p className="mt-2 font-semibold leading-6">
                    {vote.plain_meaning_en ?? motion.headline}
                  </p>
                  {!vote.plain_meaning_en && motion.headline !== motion.raw ? (
                    <p className="mt-1 truncate text-xs text-slate-400">{motion.raw}</p>
                  ) : null}
                </Link>
              );
            })}
            {!votes?.items.length ? (
              <DataGap
                title={apiUp ? "No votes yet" : "Data temporarily unavailable"}
                detail={
                  apiUp
                    ? "Votes appear here after the first data sync."
                    : "The data service isn't responding — try again in a minute."
                }
              />
            ) : null}
          </div>
        </div>

        <div className="glass-card p-6">
          <div className="flex items-center justify-between">
            <h2 className="text-xl font-bold">Latest bills</h2>
            <Link href="/bills" className="text-sm font-semibold text-accent hover:underline">
              See all
            </Link>
          </div>
          <div className="mt-4 space-y-3">
            {bills?.items.slice(0, 5).map((bill) => {
              const title = humanizeBillTitle(bill.title_en, bill.short_title_en);
              const status = humanizeStatus(bill.status_en);
              return (
                <Link
                  key={`${bill.session}-${bill.number}`}
                  href={`/bills/${bill.session}/${bill.number}`}
                  className="block rounded-xl border border-border bg-white p-4 transition hover:border-accent"
                >
                  <div className="flex flex-wrap items-center gap-2">
                    <LevelBadge level="federal" />
                    <span className="rounded-md bg-slate-100 px-2 py-0.5 text-xs font-semibold text-slate-600">
                      {bill.number}
                    </span>
                    <span className="text-xs text-slate-500">{billTypeLabel(bill.bill_type)}</span>
                  </div>
                  <p className="mt-2 font-semibold leading-6">{title.headline}</p>
                  <p className="mt-1 text-sm text-slate-600" title={status.raw}>
                    {status.label}
                    {status.hint ? <span className="text-slate-400"> — {status.hint}</span> : null}
                  </p>
                </Link>
              );
            })}
            {!bills?.items.length ? (
              <DataGap
                title={apiUp ? "No bills yet" : "Data temporarily unavailable"}
                detail={
                  apiUp
                    ? "Bills appear here after the first data sync."
                    : "The data service isn't responding — try again in a minute."
                }
              />
            ) : null}
          </div>
        </div>
      </section>
    </PageShell>
  );
}
