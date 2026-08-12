import Link from "next/link";

import { DataGap } from "@/components/data-gap";
import { outcomeBadge } from "@/components/death-banner";
import { LevelBadge } from "@/components/level-badge";
import { PageShell } from "@/components/page-shell";
import { Pagination } from "@/components/pagination";
import { listBills } from "@/lib/api";
import { billTypeLabel, humanizeBillTitle, humanizeStatus } from "@/lib/humanize";

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
      eyebrow="Federal Parliament"
      title="Bills — the living and the dead"
      description="Every proposed federal law with a plain-language status. When a bill dies, we say exactly how."
    >
      <div className="mb-6 flex flex-wrap gap-2">
        {FILTERS.map((filter) => {
          const active = outcomeGroup === filter.value;
          const href = filter.value ? `/bills?outcome=${filter.value}` : "/bills";
          return (
            <Link
              key={filter.label}
              href={href}
              className={`rounded-lg border px-3 py-1.5 text-sm font-medium transition ${
                active
                  ? "border-accent bg-accent text-white"
                  : "border-border bg-white text-slate-700 hover:border-accent hover:text-accent"
              }`}
            >
              {filter.label}
            </Link>
          );
        })}
        <Link
          href="/graveyard"
          className="rounded-lg border border-signal/40 bg-white px-3 py-1.5 text-sm font-medium text-signal transition hover:bg-signal hover:text-white"
        >
          Visit the Graveyard →
        </Link>
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
        <div className="space-y-3">
          {bills.items.map((bill) => {
            const badge = outcomeBadge(bill.outcome, bill.is_law);
            const title = humanizeBillTitle(bill.title_en, bill.short_title_en);
            const status = humanizeStatus(bill.status_en);
            return (
              <Link
                key={`${bill.session}-${bill.number}`}
                href={`/bills/${bill.session}/${bill.number}`}
                className="glass-card block p-5 transition hover:border-accent"
              >
                <div className="flex flex-wrap items-center gap-2">
                  <LevelBadge level="federal" />
                  <span className="rounded-md bg-slate-100 px-2 py-0.5 text-xs font-semibold text-slate-600">
                    {bill.number}
                  </span>
                  <span className={`rounded-md px-2 py-0.5 text-xs font-semibold ${badge.className}`}>
                    {badge.label}
                  </span>
                  <span className="text-xs text-slate-500">{billTypeLabel(bill.bill_type)}</span>
                  {bill.is_omnibus ? (
                    <span className="rounded-md bg-amber-50 px-2 py-0.5 text-xs font-semibold text-amber-800">
                      Omnibus — many laws at once
                    </span>
                  ) : null}
                </div>
                <h2 className="mt-2 text-lg font-bold leading-7">{title.headline}</h2>
                {title.legal ? (
                  <p className="mt-0.5 truncate text-xs text-slate-400">{title.legal}</p>
                ) : null}
                <p className="mt-1.5 text-sm text-slate-600" title={status.raw}>
                  {status.label}
                  {status.hint ? <span className="text-slate-400"> — {status.hint}</span> : null}
                  {bill.sponsor_name ? (
                    <span className="text-slate-400"> · Sponsored by {bill.sponsor_name}</span>
                  ) : null}
                </p>
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
