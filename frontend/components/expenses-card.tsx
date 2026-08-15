import Link from "next/link";

import type { MpExpensesResponse } from "@/lib/api";

function money(value: number): string {
  return `$${value.toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
}

export function ExpensesCard({ expenses }: { expenses: MpExpensesResponse }) {
  const latest = expenses.quarters[0];
  if (!latest && !expenses.top_items.length) return null;

  const vsMedian =
    latest?.caucus_median_total && latest.caucus_median_total > 0
      ? latest.total / latest.caucus_median_total
      : null;
  const medianDeltaPct = vsMedian != null ? Math.round((vsMedian - 1) * 100) : null;

  const budget = expenses.budget;
  const evenPacePct = budget ? (100 * budget.quarters_reported) / 4 : 0;
  const runningHot = budget ? budget.utilization_pct > evenPacePct + 15 : false;

  return (
    <section>
      <div className="rule-heavy pt-3">
        <h2 className="font-serif text-2xl font-bold tracking-tight text-ink sm:text-3xl">Spending</h2>
        <p className="mt-1 text-sm text-stone-500">
          Their office budget is taxpayer money — staff, travel, hospitality, contracts. From the official
          quarterly disclosures.
        </p>
      </div>

      {expenses.flags.length ? (
        <div className="mt-5 space-y-3">
          {expenses.flags.map((flag) => (
            <div key={flag.headline_en} className="border-l-4 border-amber-400 pl-4">
              <p className="kicker text-amber-700">
                Flagged pattern · human-reviewed
              </p>
              <p className="mt-2 font-medium leading-6">{flag.headline_en}</p>
              {flag.detail_en ? <p className="mt-1 text-sm leading-6 text-stone-600">{flag.detail_en}</p> : null}
            </div>
          ))}
        </div>
      ) : null}

      {latest ? (
        <div className="mt-6">
          <div className="flex flex-wrap items-baseline gap-3">
            <span className="stat-figure font-sans text-4xl text-ink">{money(latest.total)}</span>
            <span className="text-sm text-stone-500">
              in Q{latest.quarter} {latest.fiscal_year}
            </span>
            {medianDeltaPct != null ? (
              <span
                className={`text-sm font-medium ${
                  medianDeltaPct > 50 ? "text-amber-700" : "text-stone-500"
                }`}
              >
                {Math.abs(medianDeltaPct) <= 5
                  ? "in line with their party's median"
                  : medianDeltaPct > 0
                    ? `${medianDeltaPct}% more than the median MP in their caucus`
                    : `${Math.abs(medianDeltaPct)}% less than the median MP in their caucus`}
              </span>
            ) : null}
            {expenses.spend_percentile != null ? (
              <span
                className={`text-sm font-medium ${
                  expenses.spend_percentile >= 90 ? "text-amber-700" : "text-stone-500"
                }`}
              >
                spends more than {Math.round(expenses.spend_percentile)}% of MPs
              </span>
            ) : null}
          </div>
          <div className="mt-4 grid grid-cols-2 gap-x-8 gap-y-3 border-t border-border pt-4 text-sm sm:grid-cols-4">
            {(
              [
                ["Staff", latest.salaries],
                ["Travel", latest.travel],
                ["Hospitality", latest.hospitality],
                ["Contracts", latest.contracts]
              ] as const
            ).map(([label, value]) => (
              <div key={label}>
                <p className="kicker">{label}</p>
                <p className="stat-figure mt-1 text-lg font-semibold">{money(value)}</p>
                {latest.total > 0 ? (
                  <p className="text-xs text-stone-500">
                    {Math.round((value / latest.total) * 100)}% of quarter
                  </p>
                ) : null}
              </div>
            ))}
          </div>
        </div>
      ) : null}

      {budget ? (
        <div className="mt-5">
          <p className="text-sm font-medium">
            Office budget used: {money(budget.ytd_total)} of {money(budget.annual_budget)} (
            {Math.round(budget.utilization_pct)}%)
          </p>
          <div className="mt-2 h-2.5 w-full overflow-hidden rounded-full bg-stone-200">
            <div
              className={`h-full rounded-full ${runningHot ? "bg-amber-500" : "bg-accent"}`}
              style={{ width: `${Math.min(100, Math.max(0, budget.utilization_pct))}%` }}
            />
          </div>
          <p className="mt-2 text-xs text-stone-500">
            {budget.note} Covers Q1–Q{budget.quarters_reported} of FY{budget.fiscal_year}–
            {budget.fiscal_year + 1}.
          </p>
        </div>
      ) : null}

      {expenses.mp_annual_salary != null ? (
        <p className="mt-3 text-xs text-stone-500">
          MP salary: {money(expenses.mp_annual_salary)}/yr (set by law, all MPs) — separate from this office
          budget.
        </p>
      ) : null}

      {expenses.top_items.length ? (
        <details className="mt-6 border-t border-border pt-4">
          <summary className="cursor-pointer text-sm font-medium text-accent">
            Biggest items ({expenses.top_items.length})
          </summary>
          <div className="mt-2">
            {expenses.top_items.map((item) => (
              <div key={item.id} className="rule flex items-start justify-between gap-3 py-3 text-sm">
                <div className="min-w-0">
                  <p className="truncate font-medium">{item.supplier ?? item.description ?? item.purpose ?? "—"}</p>
                  <p className="text-xs text-stone-500">
                    {item.category} · Q{item.quarter} {item.fiscal_year}
                    {item.occurred_on ? ` · ${item.occurred_on}` : ""}
                  </p>
                </div>
                <span className="stat-figure shrink-0 font-semibold">{money(item.amount)}</span>
              </div>
            ))}
          </div>
        </details>
      ) : null}

      <p className="mt-6 border-t border-border pt-4 text-xs leading-5 text-stone-500">
        {expenses.sources_note}{" "}
        <Link href={`/expenses?q=${encodeURIComponent(expenses.full_name)}`} className="text-accent">
          Search all their expenses →
        </Link>
      </p>
    </section>
  );
}
