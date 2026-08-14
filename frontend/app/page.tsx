import Link from "next/link";

import { DataGap } from "@/components/data-gap";
import { LevelBadge, WhoDoesWhat } from "@/components/level-badge";
import { PageShell } from "@/components/page-shell";
import { PostalLookupForm } from "@/components/postal-lookup-form";
import { getDigest, listBills, listPoliticians, listVotes } from "@/lib/api";
import { billTypeLabel, formatDateShort, humanizeBillTitle, humanizeMotion, humanizeStatus } from "@/lib/humanize";
import { voteActionLine } from "@/lib/vote-action";

export const metadata = {
  title: "Civic Ledger — who represents you, and what have they done?"
};

export default async function HomePage() {
  const [politicians, votes, bills, digest] = await Promise.all([
    listPoliticians({ limit: 1, level: "federal" }),
    listVotes(),
    listBills(),
    getDigest()
  ]);

  const apiUp = Boolean(politicians || votes || bills);

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
          {/* POST via server action: the postal code never enters a URL. */}
          <PostalLookupForm mode="ladder" />
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

      {/* This week in Ottawa: auto-generated news briefs, zero editorial picks. */}
      <section className="mb-8">
        <div className="flex items-baseline justify-between border-b-2 border-ink/80 pb-2">
          <h2 className="font-serif text-xl font-bold">This week in Ottawa</h2>
          <span className="text-xs text-slate-500">computed from the official record</span>
        </div>
        {digest?.stories.length ? (
          <ol className="divide-y divide-border">
            {digest.stories.map((story, index) => (
              <li key={story.kind}>
                <Link
                  href={story.url_path}
                  className="group flex gap-4 py-4 transition hover:bg-white"
                >
                  <span className="w-6 shrink-0 pt-0.5 text-right font-serif text-lg font-bold text-slate-300">
                    {index + 1}
                  </span>
                  <div className="min-w-0">
                    <p className="kicker">
                      {story.eyebrow}
                      {story.occurred_on ? (
                        <span className="ml-2 font-normal normal-case tracking-normal text-slate-500">
                          {formatDateShort(story.occurred_on)}
                        </span>
                      ) : null}
                    </p>
                    <p className="mt-1 font-serif text-lg font-semibold leading-6 group-hover:text-accent">
                      {story.headline}
                    </p>
                    {story.detail ? (
                      <p className="mt-1 text-sm leading-6 text-slate-600">{story.detail}</p>
                    ) : null}
                  </div>
                </Link>
              </li>
            ))}
          </ol>
        ) : (
          <div className="mt-4">
            <DataGap
              title={apiUp ? "No stories yet" : "Data temporarily unavailable"}
              detail={
                apiUp
                  ? "Story cards appear after the first data sync."
                  : "The data service isn't responding right now — try again in a minute."
              }
            />
          </div>
        )}
        <div className="mt-4 flex flex-wrap gap-2 border-t border-border pt-4">
          <Link href="/issues" className="rounded-md bg-ink px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-slate-700">
            Browse by issue
          </Link>
          <Link href="/bills" className="rounded-md border border-border bg-white px-4 py-2.5 text-sm font-semibold text-slate-700 transition hover:border-accent hover:text-accent">
            Bills
          </Link>
          <Link href="/votes" className="rounded-md border border-border bg-white px-4 py-2.5 text-sm font-semibold text-slate-700 transition hover:border-accent hover:text-accent">
            Votes
          </Link>
          <Link href="/cabinet" className="rounded-md border border-border bg-white px-4 py-2.5 text-sm font-semibold text-slate-700 transition hover:border-accent hover:text-accent">
            Cabinet
          </Link>
          <Link href="/receipts" className="rounded-md border border-border bg-white px-4 py-2.5 text-sm font-semibold text-slate-700 transition hover:border-accent hover:text-accent">
            The Receipts
          </Link>
          <Link href="/expenses" className="rounded-md border border-border bg-white px-4 py-2.5 text-sm font-semibold text-slate-700 transition hover:border-accent hover:text-accent">
            Follow the money
          </Link>
          <Link href="/graveyard" className="rounded-md border border-signal/40 bg-white px-4 py-2.5 text-sm font-semibold text-signal transition hover:bg-signal hover:text-white">
            The Graveyard
          </Link>
          <Link href="/search" className="rounded-md border border-border bg-white px-4 py-2.5 text-sm font-semibold text-slate-700 transition hover:border-accent hover:text-accent">
            Search
          </Link>
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
              const isBill = Boolean(vote.bill_number);
              // Never headline a raw "An Act to…" — the one-liner explains better.
              const headline = isBill
                ? vote.bill_title && !vote.bill_title.toLowerCase().startsWith("an act")
                  ? vote.bill_title
                  : vote.bill_one_sentence ?? vote.bill_title ?? motion.headline
                : vote.plain_meaning_en ?? motion.headline;
              const subline = isBill && headline !== vote.bill_one_sentence ? vote.bill_one_sentence : null;
              const action = voteActionLine(vote);
              return (
                <Link
                  key={`${vote.chamber}-${vote.session}-${vote.number}`}
                  href={`/votes/${vote.chamber}/${vote.session}/${vote.number}`}
                  className="block rounded-md border border-border bg-white p-4 transition hover:border-accent"
                >
                  <div className="flex items-center gap-2">
                    <LevelBadge level="federal" />
                    {vote.bill_number ? (
                      <span className="rounded-md bg-slate-100 px-2 py-0.5 text-xs font-semibold text-slate-700">
                        {vote.bill_number}
                      </span>
                    ) : (
                      <span className="rounded-md bg-slate-100 px-2 py-0.5 text-xs text-slate-500">Motion</span>
                    )}
                    <span className="text-xs text-slate-500">{formatDateShort(vote.occurred_on)}</span>
                    <span
                      className={`ml-auto text-sm font-semibold tabular-nums ${vote.result === "Passed" ? "text-teal-700" : "text-signal"}`}
                    >
                      {vote.result === "Passed" ? "Passed" : vote.result === "Negatived" ? "Failed" : vote.result}{" "}
                      {vote.yea_total}–{vote.nay_total}
                    </span>
                  </div>
                  <p className="mt-2 font-semibold leading-6">{headline}</p>
                  {subline ? <p className="mt-1 text-sm leading-6 text-slate-600">{subline}</p> : null}
                  {action ? <p className="mt-1 text-xs font-medium text-slate-500">{action}</p> : null}
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
                  {bill.one_sentence ? (
                    <p className="mt-1 text-sm leading-6 text-slate-600">{bill.one_sentence}</p>
                  ) : null}
                  <p className="mt-1 text-sm text-slate-500" title={status.raw}>
                    {status.label}
                    {status.hint ? <span className="text-slate-500"> — {status.hint}</span> : null}
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
