import type { Metadata } from "next";
import Link from "next/link";

import { DataGap } from "@/components/data-gap";
import { Pagination } from "@/components/pagination";
import { PageShell } from "@/components/page-shell";
import { PartyBadge } from "@/components/party-badge";
import { MONEY_TABS, SectionTabs } from "@/components/section-tabs";
import { searchExpenses } from "@/lib/api";
import { MP_BASE_SALARY, ROLE_TOP_UPS, SALARY_AS_OF, SALARY_SOURCE_URL, formatSalary } from "@/lib/salaries";
import { formatDateShort } from "@/lib/humanize";

const CATEGORY_CHIPS = [
  { label: "All", value: "" },
  { label: "Contracts", value: "contract" },
  { label: "Travel", value: "travel" },
  { label: "Hospitality", value: "hospitality" }
];

const ONTARIO_CATEGORY_CHIPS = [
  { label: "All", value: "" },
  { label: "Travel", value: "travel" },
  { label: "Accommodation", value: "accommodation" },
  { label: "Meals", value: "meals" },
  { label: "Hospitality", value: "hospitality" }
];

const SCOPE_CHIPS = [
  { label: "Federal MPs", value: "" },
  { label: "Ontario MPPs", value: "on-mpp" }
];

const CATEGORY_STYLES: Record<string, string> = {
  contract: "text-sky-700",
  travel: "text-violet-700",
  hospitality: "text-emerald-700"
};

export const metadata: Metadata = {
  title: "MP expenses explorer",
  description:
    "Search every MP expense line item — travel, hospitality and contracts — with caucus comparisons and outlier flags."
};

export default async function ExpensesPage({
  searchParams
}: {
  searchParams: Promise<{
    q?: string;
    category?: string;
    fiscal_year?: string;
    min_amount?: string;
    sort?: string;
    scope?: string;
    person?: string;
    offset?: string;
  }>;
}) {
  const params = await searchParams;
  const isOntario = params.scope === "on-mpp";
  const results = await searchExpenses(params);
  const personName = params.person ? (results?.items[0]?.mp_name ?? params.person) : null;
  const categoryChips = isOntario ? ONTARIO_CATEGORY_CHIPS : CATEGORY_CHIPS;

  // CSV export of the current filters (served by the API; capped at 10k rows).
  const csvParams = new URLSearchParams();
  for (const key of ["q", "category", "fiscal_year", "min_amount", "scope", "person"] as const) {
    if (params[key]) csvParams.set(key, params[key]!);
  }
  const csvHref = `${process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/v1"}/expenses/search.csv${
    csvParams.size ? `?${csvParams.toString()}` : ""
  }`;

  const buildHref = (next: Record<string, string | undefined>) => {
    const merged = { ...params, offset: undefined, ...next };
    const searchParamsOut = new URLSearchParams();
    for (const [key, value] of Object.entries(merged)) {
      if (value) searchParamsOut.set(key, value);
    }
    const qs = searchParamsOut.toString();
    return `/expenses${qs ? `?${qs}` : ""}`;
  };

  return (
    <PageShell
      eyebrow="Money · Every expense"
      title="Every dollar MPs spend"
      titleAccent="— searchable"
      description="Contracts, travel claims, hospitality bills, and staff budgets, straight from the official quarterly disclosures. Every MP gets a taxpayer-funded office budget set by the House's Board of Internal Economy — search any supplier, sort by size, judge for yourself."
    >
      <SectionTabs tabs={MONEY_TABS} ariaLabel="Money sections" />

      {/* What MPs are paid: the salary context that frames all this spending. */}
      <details className="mb-8">
        <summary className="cursor-pointer">
          <span className="font-serif text-lg font-bold">What MPs are paid</span>
          <span className="ml-3 text-sm text-stone-500">
            base {formatSalary(MP_BASE_SALARY)}/yr · role top-ups · as of {SALARY_AS_OF}
          </span>
        </summary>
        <div className="mt-4 grid gap-x-10 gap-y-4 border-t border-border pt-4 sm:grid-cols-3">
          <div>
            <p className="kicker">Every MP</p>
            <p className="stat-figure mt-1 text-xl font-bold">{formatSalary(MP_BASE_SALARY)}</p>
            <p className="text-xs text-stone-500">base sessional allowance</p>
          </div>
          {ROLE_TOP_UPS.slice(0, 5).map((topUp) => (
            <div key={topUp.label}>
              <p className="kicker">{topUp.label.replace(" top-up", "")}</p>
              <p className="stat-figure mt-1 text-xl font-bold">+{formatSalary(topUp.amount)}</p>
              <p className="text-xs text-stone-500">on top of the base</p>
            </div>
          ))}
        </div>
        <p className="mt-3 text-xs leading-5 text-stone-500">
          Salaries are set by law and adjust automatically each April — they are separate from the office
          budgets below. Figures as of {SALARY_AS_OF}, from the official indemnities table{" "}
          <a href={SALARY_SOURCE_URL} target="_blank" rel="noreferrer" className="text-accent">
            (source ↗)
          </a>
          .
        </p>
      </details>

      <form action="/expenses" method="get" className="mb-2">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
          <input
            name="q"
            aria-label="Search expenses"
            defaultValue={params.q ?? ""}
            placeholder="Search suppliers, cities, MPs… (e.g. 'advertising', 'Bell')"
            className="w-full rounded-none border-0 border-b-2 border-ink bg-transparent px-1 py-2 text-lg outline-none placeholder:text-stone-300 focus:border-accent sm:max-w-md"
          />
          <input
            name="min_amount"
            aria-label="Minimum amount in dollars"
            defaultValue={params.min_amount ?? ""}
            placeholder="Min $"
            inputMode="numeric"
            pattern="[0-9]*"
            title="Numbers only, e.g. 5000"
            className="w-full rounded-none border-0 border-b-2 border-ink bg-transparent px-1 py-2 text-lg outline-none placeholder:text-stone-300 focus:border-accent sm:w-28"
          />
          {params.category ? <input type="hidden" name="category" value={params.category} /> : null}
          {params.person ? <input type="hidden" name="person" value={params.person} /> : null}
          {params.scope ? <input type="hidden" name="scope" value={params.scope} /> : null}
          {params.fiscal_year ? <input type="hidden" name="fiscal_year" value={params.fiscal_year} /> : null}
          {params.sort ? <input type="hidden" name="sort" value={params.sort} /> : null}
          <button type="submit" className="shrink-0 rounded-full bg-ink px-6 py-2.5 text-sm font-semibold text-white transition hover:bg-stone-700">
            Search
          </button>
          <a
            href={csvHref}
            download
            className="pb-2 text-sm text-stone-500 underline-offset-2 hover:text-accent hover:underline"
          >
            Download CSV
          </a>
        </div>
        <div className="mt-4 flex flex-wrap items-center gap-x-6 gap-y-2 text-sm font-medium">
          <span className="kicker">Who</span>
          {SCOPE_CHIPS.map((chip) => {
            const active = (params.scope ?? "") === chip.value;
            return (
              <Link
                key={chip.label}
                href={buildHref({ scope: chip.value || undefined, category: undefined })}
                scroll={false}
                className={`border-b-2 pb-0.5 transition ${
                  active ? "border-ink font-semibold text-ink" : "border-transparent text-stone-500 hover:text-ink"
                }`}
              >
                {chip.label}
              </Link>
            );
          })}
          {personName ? (
            <Link
              href={buildHref({ person: undefined, offset: undefined })}
              scroll={false}
              className="rounded-full border border-ink/20 px-3 py-1 text-xs font-semibold text-ink transition hover:border-signal hover:text-signal"
            >
              Only {personName} ✕
            </Link>
          ) : null}
          {isOntario ? (
            <span className="text-xs font-normal text-stone-500">
              travel, accommodation, meals &amp; hospitality only — Ontario doesn&apos;t disclose office budgets per MPP
            </span>
          ) : null}
        </div>
        <div className="mt-4 flex flex-wrap items-center gap-x-6 gap-y-2 text-sm font-medium">
          <span className="kicker">Show</span>
          {categoryChips.map((chip) => {
            const active = (params.category ?? "") === chip.value;
            return (
              <Link
                key={chip.label}
                href={buildHref({ category: chip.value || undefined })}
                scroll={false}
                className={`border-b-2 pb-0.5 transition ${
                  active ? "border-ink font-semibold text-ink" : "border-transparent text-stone-500 hover:text-ink"
                }`}
              >
                {chip.label}
              </Link>
            );
          })}
          <span className="ml-auto flex gap-2">
            <Link
              href={buildHref({ sort: undefined })}
              scroll={false}
              className={params.sort !== "date" ? "font-semibold text-ink" : "text-stone-500 hover:text-ink"}
            >
              Biggest first
            </Link>
            <span className="text-stone-300">·</span>
            <Link
              href={buildHref({ sort: "date" })}
              scroll={false}
              className={params.sort === "date" ? "font-semibold text-ink" : "text-stone-500 hover:text-ink"}
            >
              Newest first
            </Link>
          </span>
        </div>
      </form>

      {!results?.items.length ? (
        <DataGap
          title="No expense records match"
          detail="Nothing matches these filters. Expense records update weekly from ourcommons.ca — try clearing a filter."
        />
      ) : (
        <>
          <p className="rule-heavy mb-1 mt-6 pt-3 text-sm text-stone-500">
            <span className="stat-figure text-lg text-ink">{results.meta.total.toLocaleString()}</span> items ·
            showing {results.items.length}
          </p>
          <div>
            {results.items.map((item) => (
              <div key={item.id} className="rule grid gap-x-8 gap-y-2 py-5 md:grid-cols-[1fr_auto]">
                <div className="min-w-0">
                  <p className="text-[15px] leading-6">
                    <span className={`mr-2 text-xs font-bold uppercase tracking-wide ${CATEGORY_STYLES[item.category] ?? "text-stone-500"}`}>
                      {item.category}
                    </span>
                    <span className="font-semibold text-ink">
                      {item.supplier ?? item.description ?? item.purpose ?? "—"}
                    </span>
                    {item.traveller_type && item.traveller_type.toLowerCase() !== "member" ? (
                      <span className="ml-2 text-xs text-stone-500">{item.traveller_type}</span>
                    ) : null}
                  </p>
                  {item.supplier && item.description ? (
                    <p className="mt-0.5 text-sm text-stone-500">{item.description}</p>
                  ) : null}
                  <div className="mt-2 flex flex-wrap items-center gap-2 text-sm text-stone-500">
                    {item.mp_image_url ? (
                      // eslint-disable-next-line @next/next/no-img-element -- external media host, avatar-sized
                      <img
                        src={item.mp_image_url}
                        alt=""
                        width={24}
                        height={24}
                        loading="lazy"
                        className="h-6 w-6 shrink-0 rounded-md object-cover"
                      />
                    ) : (
                      <span
                        aria-hidden
                        className="flex h-6 w-6 shrink-0 items-center justify-center rounded-md bg-stone-100 text-[10px] font-semibold text-stone-500"
                      >
                        {(item.mp_name ?? "?").charAt(0)}
                      </span>
                    )}
                    {item.mp_slug ? (
                      <Link href={`/politicians/${item.mp_slug}`} className="font-medium text-ink hover:text-accent">
                        {item.mp_name}
                      </Link>
                    ) : (
                      <span className="font-medium">{item.mp_name}</span>
                    )}
                    {item.mp_party ? <PartyBadge party={item.mp_party} size="xs" /> : null}
                    <span>
                      Q{item.quarter} {item.fiscal_year}
                      {item.occurred_on ? ` · ${formatDateShort(item.occurred_on)}` : ""}
                      {item.city ? ` · ${item.city}` : ""}
                      {" · "}
                      <a href={item.source_url} target="_blank" rel="noreferrer" className="text-accent">
                        official record ↗
                      </a>
                    </span>
                  </div>
                </div>
                <p className="stat-figure shrink-0 text-xl font-semibold text-ink md:text-right">
                  ${item.amount.toLocaleString(undefined, { maximumFractionDigits: 2 })}
                </p>
              </div>
            ))}
          </div>
          <Pagination
            total={results.meta.total}
            limit={results.meta.limit}
            offset={results.meta.offset}
            basePath="/expenses"
            params={{
              q: params.q,
              category: params.category,
              fiscal_year: params.fiscal_year,
              min_amount: params.min_amount,
              sort: params.sort,
              scope: params.scope,
              person: params.person
            }}
          />
        </>
      )}

      {results?.data_current_to ? (
        <p className="mt-8 text-xs text-stone-500">
          Disclosures current to {formatDateShort(results.data_current_to)} — legislatures publish quarterly,
          with a lag. A few line items carry future dates (prepaid rent, booked events); that&apos;s how they
          appear in the source.
        </p>
      ) : null}
      <p className="mt-2 max-w-3xl text-xs leading-6 text-stone-500">
        Source: {isOntario
          ? "Legislative Assembly of Ontario members' expense disclosures."
          : "House of Commons Members' Expenditures (Proactive Disclosure)."}{" "}
        Large amounts are often
        routine — office leases, printing, northern-riding travel. Patterns worth a second look go through a
        human review queue before being flagged.{" "}
        <Link href="/methodology" className="text-accent">
          Methodology →
        </Link>
      </p>
    </PageShell>
  );
}
