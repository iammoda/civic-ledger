import Link from "next/link";

import { DataGap } from "@/components/data-gap";
import { PageShell } from "@/components/page-shell";
import { Pagination } from "@/components/pagination";
import { SectionTabs, WHAT_HAPPENED_TABS } from "@/components/section-tabs";
import { StageGlyph } from "@/components/viz/stage-glyph";
import { listBills } from "@/lib/api";
import { billTypeLabel, formatDateShort, humanizeBillTitle, humanizeStatus } from "@/lib/humanize";

export const metadata = { title: "Federal bills — the living and the dead" };

const FILTERS = [
  { label: "All bills", value: undefined },
  { label: "In progress", value: "pending" },
  { label: "Became law", value: "law" },
  { label: "Died", value: "dead" }
];

export default async function BillsPage({
  searchParams
}: {
  searchParams: Promise<{ outcome?: string; offset?: string }>;
}) {
  const { outcome, offset } = await searchParams;
  const outcomeGroup = ["pending", "law", "dead"].includes(outcome ?? "") ? outcome : undefined;
  const bills = await listBills({ outcomeGroup, offset });

  return (
    <PageShell
      eyebrow="What happened · Federal Parliament"
      title="What are they trying to change?"
      description="Every proposed federal law — what it does, where it is on the road to becoming law, and when a bill dies, exactly how. A bill must survive three readings in the House, committee study, and the Senate before it becomes real."
    >
      <SectionTabs tabs={WHAT_HAPPENED_TABS} ariaLabel="What happened sections" />

      <div className="mb-2 flex flex-wrap items-center gap-x-6 gap-y-2 text-sm font-medium">
        <span className="kicker">Show</span>
        {FILTERS.map((filter) => {
          const active = outcomeGroup === filter.value;
          const href = filter.value ? `/bills?outcome=${filter.value}` : "/bills";
          return (
            <Link
              key={filter.label}
              href={href}
              className={`border-b-2 pb-0.5 transition ${
                active
                  ? "border-ink font-semibold text-ink"
                  : "border-transparent text-slate-500 hover:text-ink"
              }`}
            >
              {filter.label}
            </Link>
          );
        })}
      </div>

      {!bills?.items.length ? (
        <DataGap
          title={bills ? "No bills match this filter" : "Data temporarily unavailable"}
          detail={
            bills
              ? "Try a different filter."
              : "The data service isn't responding right now — try again in a minute."
          }
        />
      ) : (
        <div>
          {bills.items.map((bill) => {
            const title = humanizeBillTitle(bill.title_en, bill.short_title_en);
            const status = humanizeStatus(bill.status_en);
            const dead = bill.outcome === "dead";
            return (
              <Link
                key={`${bill.session}-${bill.number}`}
                href={`/bills/${bill.session}/${bill.number}`}
                className="rule group grid gap-x-8 gap-y-2 py-6 md:grid-cols-[8.5rem_1fr_auto]"
              >
                <div className="text-[13px] leading-5 text-slate-400">
                  <p className="font-semibold text-slate-500">{bill.number}</p>
                  <p>{billTypeLabel(bill.bill_type)}</p>
                  {bill.introduced_on ? <p>{formatDateShort(bill.introduced_on)}</p> : null}
                  {bill.is_omnibus ? <p className="mt-1 font-semibold text-amber-700">Omnibus</p> : null}
                </div>
                <div className="min-w-0">
                  <h2 className="font-serif text-xl font-bold leading-snug tracking-tight text-ink transition group-hover:text-accent sm:text-2xl">
                    {title.headline}
                  </h2>
                  {bill.one_sentence ? (
                    <p className="mt-1.5 max-w-2xl text-sm leading-6 text-slate-500">{bill.one_sentence}</p>
                  ) : title.legal ? (
                    <p className="mt-1 max-w-2xl truncate text-xs text-slate-400">{title.legal}</p>
                  ) : null}
                  {bill.sponsor_name ? (
                    <p className="mt-1.5 text-[13px] text-slate-500">Sponsored by {bill.sponsor_name}</p>
                  ) : null}
                </div>
                <div className="w-40 shrink-0 md:text-right">
                  <StageGlyph statusEn={bill.status_en} isLaw={bill.is_law} dead={dead} />
                  <p
                    className={`mt-1.5 text-[13px] font-semibold leading-5 ${
                      bill.is_law ? "text-teal-700" : dead ? "text-signal" : "text-slate-600"
                    }`}
                    title={status.raw}
                  >
                    {bill.is_law ? "Became law" : dead ? "Dead" : status.label}
                  </p>
                </div>
              </Link>
            );
          })}
        </div>
      )}

      {bills ? (
        <Pagination
          total={bills.meta.total}
          limit={bills.meta.limit}
          offset={bills.meta.offset}
          basePath="/bills"
          params={{ outcome }}
        />
      ) : null}
    </PageShell>
  );
}
