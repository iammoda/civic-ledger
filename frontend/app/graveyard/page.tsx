import Link from "next/link";

import { DataGap } from "@/components/data-gap";
import { CountUp } from "@/components/motion/count-up";
import { Reveal } from "@/components/motion/reveal";
import { Pagination } from "@/components/pagination";
import { SectionTabs, WHAT_HAPPENED_TABS } from "@/components/section-tabs";
import { getGraveyardSummary, listBills } from "@/lib/api";
import { formatDateShort, humanizeBillTitle } from "@/lib/humanize";

export const metadata = { title: "The Graveyard — bills that died, and how" };

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

/* Memorial shades: red on ink, dimming with rank. */
const BAR_SHADES = ["bg-red-400", "bg-red-400/70", "bg-red-400/50", "bg-red-400/35", "bg-red-400/25", "bg-red-400/15"];

const CONTAINER = "mx-auto max-w-[1600px] px-5 sm:px-10";

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
    <main id="main">
      {/* ---------------------------------------------------------------- */}
      {/* The memorial: a dark field for the quiet institutional dead.      */}
      {/* Form expresses content — and every number is on the record.       */}
      {/* ---------------------------------------------------------------- */}
      <section className="bg-ink pb-12 pt-8 text-stone-300 sm:pb-14 sm:pt-12">
        <div className={CONTAINER}>
          <div className="border-t-2 border-white/80 pt-5">
            <p className="kicker text-red-400">What happened · The Graveyard</p>
            <h1 className="mt-3 max-w-4xl font-serif text-[2.5rem] font-bold leading-[1.05] tracking-tight text-white sm:text-[3.5rem]">
              Bills that died <em className="italic text-red-400">— and how</em>
            </h1>
            <p className="mt-4 max-w-2xl text-[17px] leading-7 text-stone-400">
              Most bills don&apos;t die in a dramatic vote. They die quietly: stuck in committee, stranded
              when Parliament ends, or pulled without explanation. Every death here has a cause attached.
            </p>

            {summary?.total ? (
              <Reveal className="mt-10 max-w-3xl">
                <p>
                  <CountUp
                    value={summary.total}
                    className="stat-figure font-sans text-6xl text-white sm:text-7xl"
                  />
                  <span className="ml-3 font-mono text-xs uppercase tracking-wider text-stone-500">
                    dead bills on the record
                  </span>
                </p>
                {/* How they die: one proportional bar, then the receipts. */}
                <div className="mt-6 flex h-3 w-full overflow-hidden rounded-full bg-white/5" aria-hidden>
                  {summary.mechanisms.map((row, i) => (
                    <div
                      key={row.mechanism}
                      className={`reveal-bar ${BAR_SHADES[i % BAR_SHADES.length]}`}
                      style={{ width: `${(row.count / summary.total) * 100}%`, transitionDelay: `${i * 90}ms` }}
                    />
                  ))}
                </div>
                <dl className="mt-5 grid gap-x-10 gap-y-2.5 text-sm sm:grid-cols-2">
                  {summary.mechanisms.map((row, i) => (
                    <div key={row.mechanism} className="flex items-baseline gap-2">
                      <span
                        aria-hidden
                        className={`inline-block h-2.5 w-2.5 shrink-0 translate-y-px rounded-sm ${BAR_SHADES[i % BAR_SHADES.length]}`}
                      />
                      <dt className="font-semibold text-white">
                        {MECHANISM_SHORT[row.mechanism] ?? row.mechanism.replaceAll("_", " ")}
                      </dt>
                      <dd className="text-stone-400">
                        <span className="stat-figure font-semibold text-stone-200">{row.count}</span>
                        {MECHANISM_NOTE[row.mechanism] ? ` — ${MECHANISM_NOTE[row.mechanism]}` : null}
                      </dd>
                    </div>
                  ))}
                </dl>
              </Reveal>
            ) : null}
          </div>
        </div>
      </section>

      {/* ---------------------------------------------------------------- */}
      {/* The ledger of the dead.                                            */}
      {/* ---------------------------------------------------------------- */}
      <section className={`${CONTAINER} py-8 sm:py-10`}>
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
            detail="Bills die when they're defeated or when a session ends and kills everything unfinished. If Parliament is mid-session, most deaths haven't happened yet."
          />
        ) : (
          <div>
            {bills.items.map((bill) => (
              <Link
                key={`${bill.session}-${bill.number}`}
                href={`/bills/${bill.session}/${bill.number}`}
                className="rule group grid gap-x-8 gap-y-1.5 py-5 md:grid-cols-[13rem_1fr]"
              >
                <div className="font-mono text-xs leading-5">
                  <p className="font-semibold text-signal">
                    {MECHANISM_SHORT[bill.death?.mechanism ?? bill.outcome] ?? bill.outcome.replaceAll("_", " ")}
                  </p>
                  <p className="text-stone-400">
                    {bill.number} · {bill.session}
                    {bill.death?.occurred_on ? ` · ${formatDateShort(bill.death.occurred_on)}` : ""}
                  </p>
                </div>
                <div className="min-w-0">
                  <h2 className="font-serif text-lg font-bold leading-snug tracking-tight text-ink transition group-hover:text-signal sm:text-xl">
                    {humanizeBillTitle(bill.title_en, bill.short_title_en).headline}
                  </h2>
                  {bill.death?.attribution_en ? (
                    <p className="mt-1 max-w-2xl text-sm leading-6 text-stone-500">{bill.death.attribution_en}</p>
                  ) : null}
                  {bill.sponsor_name ? (
                    <p className="mt-1 text-xs text-stone-400">Sponsored by {bill.sponsor_name}</p>
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

        <p className="mt-8 max-w-3xl text-xs leading-6 text-stone-500">
          Deaths are derived from LEGISinfo status codes and session-end sweeps (prorogation and dissolution
          kill every unfinished bill). A death is a fact about process, not a judgment — some bills deserve to
          die, some don&apos;t. The record lets you decide which was which.
        </p>
      </section>
    </main>
  );
}
