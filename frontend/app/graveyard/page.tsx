import Link from "next/link";

import { DataGap } from "@/components/data-gap";
import { PageShell } from "@/components/page-shell";
import { listBills } from "@/lib/api";

const MECHANISM_LABELS: Record<string, string> = {
  defeated_vote: "Defeated on a recorded vote",
  died_committee: "Died in committee — never given a vote",
  died_order_paper: "Died on the Order Paper",
  died_senate: "Died in the Senate",
  withdrawn: "Withdrawn",
  not_proceeded_with: "Not proceeded with"
};

export default async function GraveyardPage({
  searchParams
}: {
  searchParams: Promise<{ topic?: string }>;
}) {
  const { topic } = await searchParams;
  const bills = await listBills({ outcomeGroup: "dead", topic });

  return (
    <PageShell
      eyebrow="The Graveyard"
      title="Bills that died — and how"
      description="Most bills don't die in a dramatic vote. They die quietly: stuck in committee, stranded when Parliament ends, or pulled without explanation. Every death here has a cause attached."
    >
      {topic ? (
        <div className="mb-6">
          <Link href="/graveyard" className="rounded-full border border-signal/40 px-4 py-2 text-sm text-signal">
            Topic: {topic} ✕
          </Link>
        </div>
      ) : null}

      {!bills?.items.length ? (
        <DataGap
          title="No dead bills recorded yet"
          detail="Bill deaths appear after ingestion runs and a session ends or a bill is defeated. If Parliament is mid-session, most deaths haven't happened yet."
        />
      ) : (
        <div className="space-y-4">
          {bills.items.map((bill) => (
            <Link
              key={`${bill.session}-${bill.number}`}
              href={`/bills/${bill.session}/${bill.number}`}
              className="glass-card block rounded-[2rem] border-l-4 border-signal/60 p-6 transition hover:-translate-y-0.5"
            >
              <div className="flex flex-wrap items-center gap-2">
                <span className="rounded-full bg-rose-50 px-3 py-1 text-xs font-medium text-rose-700">
                  {MECHANISM_LABELS[bill.death?.mechanism ?? bill.outcome] ??
                    bill.outcome.replaceAll("_", " ")}
                </span>
                {bill.death?.occurred_on ? (
                  <span className="text-xs text-slate-400">{bill.death.occurred_on}</span>
                ) : null}
                <span className="ml-auto text-sm uppercase tracking-[0.14em] text-slate-500">
                  {bill.number} · {bill.session}
                </span>
              </div>
              <h2 className="mt-2 text-xl font-semibold">{bill.short_title_en ?? bill.title_en}</h2>
              {bill.death?.attribution_en ? (
                <p className="mt-2 text-sm leading-6 text-slate-600">{bill.death.attribution_en}</p>
              ) : null}
              {bill.sponsor_name ? (
                <p className="mt-2 text-xs text-slate-400">Sponsored by {bill.sponsor_name}</p>
              ) : null}
            </Link>
          ))}
        </div>
      )}

      <p className="mt-8 text-xs leading-6 text-slate-400">
        Deaths are derived from LEGISinfo status codes and session-end sweeps (prorogation and dissolution
        kill every unfinished bill). A death is a fact about process, not a judgment — some bills deserve to
        die, some don&apos;t. The record lets you decide which was which.
      </p>
    </PageShell>
  );
}
