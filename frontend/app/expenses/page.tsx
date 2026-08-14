import Link from "next/link";

import { DataGap } from "@/components/data-gap";
import { ExplainerStrip } from "@/components/explainer-strip";
import { PageShell } from "@/components/page-shell";
import { PartyBadge } from "@/components/party-badge";
import { searchExpenses } from "@/lib/api";

const CATEGORY_CHIPS = [
  { label: "All", value: "" },
  { label: "Contracts", value: "contract" },
  { label: "Travel", value: "travel" },
  { label: "Hospitality", value: "hospitality" }
];

const CATEGORY_STYLES: Record<string, string> = {
  contract: "bg-sky-50 text-sky-700",
  travel: "bg-violet-50 text-violet-700",
  hospitality: "bg-emerald-50 text-emerald-700"
};

export default async function ExpensesPage({
  searchParams
}: {
  searchParams: Promise<{ q?: string; category?: string; fiscal_year?: string; min_amount?: string; sort?: string }>;
}) {
  const params = await searchParams;
  const results = await searchExpenses(params);

  const buildHref = (next: Record<string, string | undefined>) => {
    const merged = { ...params, ...next };
    const searchParamsOut = new URLSearchParams();
    for (const [key, value] of Object.entries(merged)) {
      if (value) searchParamsOut.set(key, value);
    }
    const qs = searchParamsOut.toString();
    return `/expenses${qs ? `?${qs}` : ""}`;
  };

  return (
    <PageShell
      eyebrow="Follow the money"
      title="Every dollar MPs spend — searchable"
      description="Contracts, travel claims, hospitality bills, and staff budgets, straight from the official quarterly disclosures. It's taxpayer money: search any supplier, sort by size, judge for yourself."
    >
      <ExplainerStrip id="mp-office-budget">
        Where this money comes from: every MP gets a taxpayer-funded office budget set by the House&apos;s
        Board of Internal Economy — it pays for staff, riding offices, travel, and contracts. Every line
        below is from their official disclosures.
      </ExplainerStrip>

      <form action="/expenses" method="get" className="glass-card mb-6 rounded-[2rem] p-6">
        <div className="flex flex-col gap-3 sm:flex-row">
          <input
            name="q"
            aria-label="Search expenses"
            defaultValue={params.q ?? ""}
            placeholder="Search suppliers, descriptions, cities, MPs… (e.g. 'advertising', 'Bell', an MP's name)"
            className="w-full rounded-full border border-black/10 bg-white px-5 py-3 outline-none focus:border-accent"
          />
          <input
            name="min_amount"
            defaultValue={params.min_amount ?? ""}
            placeholder="Min $"
            inputMode="numeric"
            pattern="[0-9]*"
            title="Numbers only, e.g. 5000"
            className="w-full rounded-full border border-black/10 bg-white px-5 py-3 outline-none focus:border-accent sm:w-32"
          />
          {params.category ? <input type="hidden" name="category" value={params.category} /> : null}
          {params.fiscal_year ? <input type="hidden" name="fiscal_year" value={params.fiscal_year} /> : null}
          {params.sort ? <input type="hidden" name="sort" value={params.sort} /> : null}
          <button type="submit" className="rounded-full bg-slate-900 px-6 py-3 text-sm font-medium text-white">
            Search
          </button>
        </div>
        <div className="mt-4 flex flex-wrap items-center gap-2">
          {CATEGORY_CHIPS.map((chip) => {
            const active = (params.category ?? "") === chip.value;
            return (
              <Link
                key={chip.label}
                href={buildHref({ category: chip.value || undefined })}
                className={`rounded-full border px-4 py-2 text-sm transition ${
                  active
                    ? "border-accent bg-accent text-white"
                    : "border-black/10 bg-white text-slate-700 hover:border-accent hover:text-accent"
                }`}
              >
                {chip.label}
              </Link>
            );
          })}
          <span className="ml-auto flex gap-2 text-sm">
            <Link
              href={buildHref({ sort: undefined })}
              className={params.sort !== "date" ? "font-medium text-accent" : "text-slate-500"}
            >
              Biggest first
            </Link>
            <span className="text-slate-300">·</span>
            <Link
              href={buildHref({ sort: "date" })}
              className={params.sort === "date" ? "font-medium text-accent" : "text-slate-500"}
            >
              Newest first
            </Link>
          </span>
        </div>
      </form>

      {!results?.items.length ? (
        <DataGap
          title="No expense records match"
          detail="Either the expense sync hasn't run yet, or nothing matches these filters. Expenses sync weekly from ourcommons.ca."
        />
      ) : (
        <>
          <p className="mb-4 text-sm text-slate-500">
            {results.meta.total.toLocaleString()} items · showing {results.items.length}
          </p>
          <div className="space-y-3">
            {results.items.map((item) => (
              <div key={item.id} className="glass-card rounded-[2rem] p-5">
                <div className="flex flex-wrap items-center gap-2">
                  <span className={`rounded-full px-3 py-1 text-xs font-medium ${CATEGORY_STYLES[item.category] ?? "bg-slate-100 text-slate-600"}`}>
                    {item.category}
                  </span>
                  {item.traveller_type && item.traveller_type.toLowerCase() !== "member" ? (
                    <span className="rounded-full bg-slate-100 px-3 py-1 text-xs text-slate-600">
                      {item.traveller_type}
                    </span>
                  ) : null}
                  <span className="min-w-0">
                    <span className="mr-2 text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-400">
                      supplier
                    </span>
                    <span className="font-semibold">
                      {item.supplier ?? item.description ?? item.purpose ?? "—"}
                    </span>
                  </span>
                  <span className="ml-auto text-lg font-semibold">
                    ${item.amount.toLocaleString(undefined, { maximumFractionDigits: 2 })}
                  </span>
                </div>
                {item.supplier && item.description ? (
                  <p className="mt-1 text-sm text-slate-500">{item.description}</p>
                ) : null}
                <div className="mt-3 flex flex-wrap items-center gap-2 text-sm text-slate-500">
                  {item.mp_image_url ? (
                    // eslint-disable-next-line @next/next/no-img-element -- external media host, avatar-sized
                    <img
                      src={item.mp_image_url}
                      alt=""
                      width={28}
                      height={28}
                      className="h-7 w-7 shrink-0 rounded-full object-cover"
                    />
                  ) : (
                    <span
                      aria-hidden
                      className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-slate-100 text-xs font-semibold text-slate-400"
                    >
                      {(item.mp_name ?? "?").charAt(0)}
                    </span>
                  )}
                  <span className="text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-400">
                    MP:
                  </span>
                  {item.mp_slug ? (
                    <Link href={`/politicians/${item.mp_slug}`} className="font-medium text-accent">
                      {item.mp_name}
                    </Link>
                  ) : (
                    <span className="font-medium">{item.mp_name}</span>
                  )}
                  {item.mp_party ? <PartyBadge party={item.mp_party} size="xs" /> : null}
                  <span className="text-slate-400">
                    Q{item.quarter} {item.fiscal_year}
                    {item.occurred_on ? ` · ${item.occurred_on}` : ""}
                    {item.city ? ` · ${item.city}` : ""}
                    {" · "}
                    <a href={item.source_url} target="_blank" rel="noreferrer" className="text-accent">
                      official record ↗
                    </a>
                  </span>
                </div>
              </div>
            ))}
          </div>
        </>
      )}

      <p className="mt-8 text-xs leading-6 text-slate-400">
        Source: House of Commons Members&apos; Expenditures (Proactive Disclosure). Large amounts are often
        routine — office leases, printing, northern-riding travel. Patterns worth a second look go through a
        human review queue before being flagged.{" "}
        <Link href="/methodology" className="text-accent">
          Methodology →
        </Link>
      </p>
    </PageShell>
  );
}
