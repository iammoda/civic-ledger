import Link from "next/link";

import { DataGap } from "@/components/data-gap";
import { outcomeBadge } from "@/components/death-banner";
import { PageShell } from "@/components/page-shell";
import { listBills } from "@/lib/api";

const FILTERS = [
  { label: "All bills", value: undefined },
  { label: "In progress", value: "pending" },
  { label: "Became law", value: "law" },
  { label: "Died", value: "dead" }
];

export default async function BillsPage({
  searchParams
}: {
  searchParams: Promise<{ outcome?: string }>;
}) {
  const { outcome } = await searchParams;
  const outcomeGroup = ["pending", "law", "dead"].includes(outcome ?? "") ? outcome : undefined;
  const bills = await listBills({ outcomeGroup });

  return (
    <PageShell
      eyebrow="Bills"
      title="Federal legislation — the living and the dead"
      description="Every bill with its plain-language summary, current status, and — when it died — exactly how."
    >
      <div className="mb-6 flex flex-wrap gap-2">
        {FILTERS.map((filter) => {
          const active = outcomeGroup === filter.value;
          const href = filter.value ? `/bills?outcome=${filter.value}` : "/bills";
          return (
            <Link
              key={filter.label}
              href={href}
              className={`rounded-full border px-4 py-2 text-sm transition ${
                active
                  ? "border-accent bg-accent text-white"
                  : "border-black/10 bg-white text-slate-700 hover:border-accent hover:text-accent"
              }`}
            >
              {filter.label}
            </Link>
          );
        })}
        <Link
          href="/graveyard"
          className="rounded-full border border-signal/40 px-4 py-2 text-sm text-signal transition hover:bg-signal hover:text-white"
        >
          Visit the Graveyard →
        </Link>
      </div>

      {!bills?.items.length ? (
        <DataGap
          title="No bills loaded"
          detail="Run bill ingestion to populate this page with current and historical legislation."
        />
      ) : (
        <div className="space-y-4">
          {bills.items.map((bill) => {
            const badge = outcomeBadge(bill.outcome, bill.is_law);
            return (
              <Link
                key={`${bill.session}-${bill.number}`}
                href={`/bills/${bill.session}/${bill.number}`}
                className="glass-card block rounded-[2rem] p-6 transition hover:-translate-y-0.5"
              >
                <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
                  <div>
                    <div className="flex flex-wrap items-center gap-2">
                      <p className="text-sm uppercase tracking-[0.18em] text-slate-500">
                        {bill.number} · {bill.session} · {bill.bill_type.replaceAll("_", " ")}
                      </p>
                      <span className={`rounded-full px-3 py-1 text-xs font-medium ${badge.className}`}>
                        {badge.label}
                      </span>
                    </div>
                    <h2 className="mt-2 text-xl font-semibold">{bill.short_title_en ?? bill.title_en}</h2>
                    <p className="mt-2 text-sm text-slate-600">{bill.sponsor_name ?? "Sponsor pending"}</p>
                  </div>
                  <div className="rounded-2xl bg-white px-4 py-3 text-sm text-slate-600 sm:max-w-xs">
                    <p>{bill.status_en ?? "Status pending"}</p>
                    {bill.is_omnibus ? <p className="mt-1 text-signal">Potential omnibus</p> : null}
                  </div>
                </div>
              </Link>
            );
          })}
        </div>
      )}
    </PageShell>
  );
}
