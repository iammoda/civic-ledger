import { SectionHeading } from "@/components/viz/editorial";
import type { MppExpensesApiResponse } from "@/lib/api";
import { formatDateShort } from "@/lib/humanize";

const CATEGORY_LABELS: Record<string, string> = {
  travel: "Travel",
  accommodation: "Toronto accommodation",
  meals: "Meals",
  hospitality: "Hospitality & events"
};

function money(amount: number): string {
  return `$${Math.round(amount).toLocaleString("en-CA")}`;
}

/**
 * Ontario MPP expense disclosures: category totals + the biggest line items.
 * Same editorial rules as the federal card — raw numbers with their caveats,
 * no scores, no flags (large amounts are often routine).
 */
export function MppExpensesCard({ expenses }: { expenses: MppExpensesApiResponse }) {
  return (
    <div>
      <SectionHeading title="What they billed" />
      <p className="pt-2 text-sm leading-6 text-stone-500">
        {money(expenses.total)} in disclosed expenses — travel, accommodation, meals and hospitality billed
        to the Assembly. Northern and distant ridings legitimately cost more; judge the purpose, not just
        the size.
      </p>

      <dl className="grid gap-x-10 gap-y-3 pt-4 sm:grid-cols-4">
        {expenses.by_category.map((row) => (
          <div key={row.category}>
            <dt className="kicker">{CATEGORY_LABELS[row.category] ?? row.category}</dt>
            <dd className="stat-figure mt-0.5 text-lg text-ink">{money(row.total)}</dd>
          </div>
        ))}
      </dl>

      {expenses.items.length ? (
        <div className="pt-4">
          <p className="kicker">Biggest line items</p>
          <div className="pt-1">
            {expenses.items.map((item) => (
              <div key={item.id} className="rule flex flex-wrap items-baseline gap-x-3 gap-y-0.5 py-2.5">
                <span className="stat-figure w-24 shrink-0 text-sm font-bold text-ink">{money(item.amount)}</span>
                <span className="min-w-0 flex-1 truncate text-sm text-stone-600">
                  {item.description ?? item.purpose ?? CATEGORY_LABELS[item.category] ?? item.category}
                  {item.city ? ` — ${item.city}` : ""}
                </span>
                <span className="text-xs text-stone-500">
                  {item.occurred_on ? formatDateShort(item.occurred_on) : `Q${item.quarter} ${item.fiscal_year}`}
                </span>
              </div>
            ))}
          </div>
        </div>
      ) : null}

      <p className="mt-3 text-xs leading-5 text-stone-500">{expenses.source_note}</p>
    </div>
  );
}
