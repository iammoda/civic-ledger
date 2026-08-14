import Link from "next/link";

import { DataGap } from "@/components/data-gap";
import { PageShell } from "@/components/page-shell";
import { Pagination } from "@/components/pagination";
import { SectionTabs, WHAT_HAPPENED_TABS } from "@/components/section-tabs";
import { getGraveyardSummary, listBills } from "@/lib/api";
import { formatDateShort, humanizeBillTitle } from "@/lib/humanize";

export const metadata = { title: "The Graveyard — bills that died, and how" };

const MECHANISM_LABELS: Record<string, string> = {
  defeated_vote: "Defeated on a recorded vote",
  died_committee: "Died in committee — never given a vote",
  died_order_paper: "Died on the Order Paper",
  died_senate: "Died in the Senate",
  withdrawn: "Withdrawn",
  not_proceeded_with: "Not proceeded with"
};

const MECHANISM_SHORT: Record<string, string> = {
  defeated_vote: "Voted down",
  died_committee: "Died in committee",
  died_order_paper: "Died waiting in line",
  died_senate: "Died in the Senate",
  withdrawn: "Withdrawn",
  not_proceeded_with: "Not proceeded with"
};

/** One story per mechanism — the pattern behind the number. */
const MECHANISM_NOTE: Record<string, string> = {
  died_order_paper: "never reached a vote before the session ended",
  died_senate: "passed the House, then ran out of road in the Senate",
  defeated_vote: "the only dramatic death — MPs actually voted them down",
  died_committee: "sent to committee for study and never came back",
  not_proceeded_with: "quietly dropped by their own sponsor",
  withdrawn: "formally withdrawn"
};

const BAR_SHADES = ["bg-signal", "bg-signal/75", "bg-signal/55", "bg-signal/40", "bg-signal/25", "bg-signal/15"];

export default async function GraveyardPage({
  searchParams
}: {
  searchParams: Promise<{ topic?: string; offset?: string }>;
}) {
  const { topic, offset } = await searchParams;
  const [bills, summary] = await Promise.all([
    listBills({ outcomeGroup: "dead", topic, offset }),
    getGraveyardSummary()
  ]);

  return (
    <PageShell
      eyebrow="What happened · The Graveyard"
      title="Bills that died"
      titleAccent="— and how"
      description="Most bills don't die in a dramatic vote. They die quietly: stuck in committee, stranded when Parliament ends, or pulled without explanation. Every death here has a cause attached."
      masthead={
        summary?.total ? (
          <div className="max-w-3xl">
            <p>
              <span className="stat-figure font-sans text-5xl text-signal sm:text-6xl">
                {summary.total.toLocaleString("en-CA")}
              </span>
              <span className="ml-3 text-sm font-medium text-slate-500">dead bills on the record</span>
            </p>
            {/* How they die: one proportional bar, then the receipts. */}
            <div className="mt-5 flex h-3 w-full overflow-hidden rounded-full" aria-hidden>
              {summary.mechanisms.map((row, i) => (
                <div
                  key={row.mechanism}
                  className={BAR_SHADES[i % BAR_SHADES.length]}
                  style={{ width: `${(row.count / summary.total) * 100}%` }}
                />
              ))}
            </div>
            <dl className="mt-4 grid gap-x-8 gap-y-2 text-sm sm:grid-cols-2">
              {summary.mechanisms.map((row, i) => (
                <div key={row.mechanism} className="flex items-baseline gap-2">
                  <span
                    aria-hidden
                    className={`inline-block h-2.5 w-2.5 shrink-0 translate-y-px rounded-sm ${BAR_SHADES[i % BAR_SHADES.length]}`}
                  />
                  <dt className="font-semibold text-ink">
                    {MECHANISM_SHORT[row.mechanism] ?? row.mechanism.replaceAll("_", " ")}
                  </dt>
                  <dd className="text-slate-500">
                    <span className="stat-figure font-semibold text-ink">{row.count}</span>
                    {MECHANISM_NOTE[row.mechanism] ? ` — ${MECHANISM_NOTE[row.mechanism]}` : null}
                  </dd>
                </div>
              ))}
            </dl>
          </div>
        ) : null
      }
    >
      <SectionTabs tabs={WHAT_HAPPENED_TABS} ariaLabel="What happened sections" />

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
        <div>
          {bills.items.map((bill) => (
            <Link
              key={`${bill.session}-${bill.number}`}
              href={`/bills/${bill.session}/${bill.number}`}
              className="rule group grid gap-x-8 gap-y-1.5 py-5 md:grid-cols-[11rem_1fr]"
            >
              <div className="text-[13px] leading-5">
                <p className="font-semibold text-signal">
                  {MECHANISM_SHORT[bill.death?.mechanism ?? bill.outcome] ?? bill.outcome.replaceAll("_", " ")}
                </p>
                <p className="text-slate-400">
                  {bill.number} · {bill.session}
                  {bill.death?.occurred_on ? ` · ${formatDateShort(bill.death.occurred_on)}` : ""}
                </p>
              </div>
              <div className="min-w-0">
                <h2 className="font-serif text-lg font-bold leading-snug tracking-tight text-ink transition group-hover:text-signal sm:text-xl">
                  {humanizeBillTitle(bill.title_en, bill.short_title_en).headline}
                </h2>
                {bill.death?.attribution_en ? (
                  <p className="mt-1 max-w-2xl text-sm leading-6 text-slate-500">{bill.death.attribution_en}</p>
                ) : null}
                {bill.sponsor_name ? (
                  <p className="mt-1 text-xs text-slate-400">Sponsored by {bill.sponsor_name}</p>
                ) : null}
              </div>
            </Link>
          ))}
        </div>
      )}

      {bills ? (
        <Pagination
          total={bills.meta.total}
          limit={bills.meta.limit}
          offset={bills.meta.offset}
          basePath="/graveyard"
          params={{ topic }}
        />
      ) : null}

      <p className="mt-8 max-w-3xl text-xs leading-6 text-slate-500">
        Deaths are derived from LEGISinfo status codes and session-end sweeps (prorogation and dissolution
        kill every unfinished bill). A death is a fact about process, not a judgment — some bills deserve to
        die, some don&apos;t. The record lets you decide which was which.
      </p>
    </PageShell>
  );
}
