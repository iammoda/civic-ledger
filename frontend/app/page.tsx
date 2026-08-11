import Link from "next/link";

import { DataGap } from "@/components/data-gap";
import { PageShell } from "@/components/page-shell";
import { StatGrid } from "@/components/stat-grid";
import { listBills, listPoliticians, listVotes } from "@/lib/api";

export default async function HomePage() {
  const [politicians, votes, bills] = await Promise.all([listPoliticians(), listVotes(), listBills()]);

  return (
    <PageShell
      eyebrow="Canada · Federal"
      title="Who is responsible — and what did they do about it?"
      description="Type your problem in plain words. See how your MP voted, which bills lived or died, and who's accountable — with sources for everything."
    >
      <section className="mb-10">
        <form action="/ask" method="get" className="glass-card rounded-[2rem] p-8">
          <label htmlFor="home-q" className="text-sm uppercase tracking-[0.22em] text-accent">
            Ask anything
          </label>
          <div className="mt-4 flex flex-col gap-3 sm:flex-row">
            <input
              id="home-q"
              name="q"
              minLength={8}
              maxLength={500}
              required
              placeholder="I can't afford rent — who is responsible?"
              className="w-full rounded-full border border-black/10 bg-white px-6 py-4 text-lg outline-none focus:border-accent"
            />
            <button type="submit" className="rounded-full bg-slate-900 px-8 py-4 text-base font-medium text-white">
              Ask
            </button>
          </div>
          <div className="mt-4 flex flex-wrap gap-2 text-sm">
            {["Why are groceries so expensive?", "What happened to pharmacare?", "Is anyone fixing housing?"].map(
              (example) => (
                <Link
                  key={example}
                  href={`/ask?q=${encodeURIComponent(example)}`}
                  className="rounded-full border border-black/10 px-4 py-2 text-slate-600 transition hover:border-accent hover:text-accent"
                >
                  {example}
                </Link>
              )
            )}
          </div>
        </form>
      </section>

      <section className="mb-10 grid gap-6 lg:grid-cols-[1.3fr_0.7fr]">
        <div className="glass-card rounded-[2rem] p-8">
          <p className="text-sm uppercase tracking-[0.22em] text-accent">The record</p>
          <h2 className="mt-3 max-w-2xl text-3xl font-semibold tracking-tight">
            Every vote translated into plain language. Every dead bill with a cause of death. Every claim cited to the official record.
          </h2>
          <div className="mt-8 flex flex-wrap gap-3">
            <Link href="/bills" className="rounded-full bg-slate-900 px-5 py-3 text-sm font-medium text-white">
              Explore bills
            </Link>
            <Link href="/votes" className="rounded-full border border-black/10 px-5 py-3 text-sm font-medium">
              Explore votes
            </Link>
            <Link href="/petitions" className="rounded-full border border-black/10 px-5 py-3 text-sm font-medium">
              Sign a petition
            </Link>
            <Link href="/search" className="rounded-full border border-black/10 px-5 py-3 text-sm font-medium">
              Search everything
            </Link>
          </div>
        </div>
        <StatGrid
          stats={[
            { label: "Politicians loaded", value: String(politicians?.meta.total ?? 0) },
            { label: "Votes loaded", value: String(votes?.meta.total ?? 0) },
            { label: "Bills loaded", value: String(bills?.meta.total ?? 0) }
          ]}
        />
      </section>

      <section className="grid gap-6 lg:grid-cols-2">
        <div className="glass-card rounded-[2rem] p-8">
          <div className="flex items-center justify-between">
            <h2 className="text-2xl font-semibold">Recent votes</h2>
            <Link href="/votes" className="text-sm text-accent">
              See all
            </Link>
          </div>
          <div className="mt-6 space-y-4">
            {votes?.items.slice(0, 5).map((vote) => (
              <Link
                key={`${vote.session}-${vote.number}`}
                href={`/votes/${vote.chamber}/${vote.session}/${vote.number}`}
                className="block rounded-3xl border border-black/10 bg-white p-5 transition hover:-translate-y-0.5"
              >
                <p className="text-sm uppercase tracking-[0.18em] text-slate-500">
                  {vote.chamber} · {vote.session} · Vote {vote.number}
                </p>
                <p className="mt-2 text-lg font-medium">{vote.description_en}</p>
                <p className="mt-2 text-sm text-slate-500">
                  {vote.occurred_on} · {vote.result ?? "Result pending"} · {vote.vote_type}
                </p>
              </Link>
            ))}
            {!votes?.items.length ? (
              <DataGap
                title="No vote data yet"
                detail="Connect the ingestion pipeline and run the first sync to populate recent House and Senate votes."
              />
            ) : null}
          </div>
        </div>

        <div className="glass-card rounded-[2rem] p-8">
          <div className="flex items-center justify-between">
            <h2 className="text-2xl font-semibold">Recent bills</h2>
            <Link href="/bills" className="text-sm text-accent">
              See all
            </Link>
          </div>
          <div className="mt-6 space-y-4">
            {bills?.items.slice(0, 5).map((bill) => (
              <Link
                key={`${bill.session}-${bill.number}`}
                href={`/bills/${bill.session}/${bill.number}`}
                className="block rounded-3xl border border-black/10 bg-white p-5 transition hover:-translate-y-0.5"
              >
                <p className="text-sm uppercase tracking-[0.18em] text-slate-500">
                  {bill.number} · {bill.chamber} · {bill.bill_type}
                </p>
                <p className="mt-2 text-lg font-medium">{bill.title_en}</p>
                <p className="mt-2 text-sm text-slate-500">{bill.status_en ?? "Status pending"}</p>
              </Link>
            ))}
            {!bills?.items.length ? (
              <DataGap
                title="No bill data yet"
                detail="Bill records, statuses, and analysis surfaces will populate after the initial LEGISinfo and OpenParliament sync."
              />
            ) : null}
          </div>
        </div>
      </section>
    </PageShell>
  );
}
