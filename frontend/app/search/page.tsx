import type { Metadata } from "next";
import Link from "next/link";

import { DataGap } from "@/components/data-gap";
import { LevelBadge } from "@/components/level-badge";
import { PageShell } from "@/components/page-shell";
import { PartyBadge } from "@/components/party-badge";
import { searchContent } from "@/lib/api";

export const metadata: Metadata = {
  title: "Search",
  description:
    "Search MPs and representatives, bills, votes, petitions, council motions and expense records in plain language."
};

const CATEGORY_STYLES: Record<string, string> = {
  contract: "bg-sky-50 text-sky-700",
  travel: "bg-violet-50 text-violet-700",
  hospitality: "bg-emerald-50 text-emerald-700"
};

function SectionHeading({ kicker, note }: { kicker: string; note?: string }) {
  return (
    <div className="flex items-baseline justify-between border-b border-ink/80 pb-2">
      <h2 className="text-xl">{kicker}</h2>
      {note ? <p className="kicker">{note}</p> : null}
    </div>
  );
}

export default async function SearchPage({
  searchParams
}: {
  searchParams: Promise<{ q?: string }>;
}) {
  const { q } = await searchParams;
  const query = (q ?? "").trim();
  const response = query.length >= 2 ? await searchContent(query) : null;

  const people = response?.people ?? [];
  const results = response?.results ?? [];
  const expenses = response?.expenses ?? [];
  const nothingFound = response !== null && !people.length && !results.length && !expenses.length;

  return (
    <PageShell
      eyebrow="Search"
      title="Search the public record"
      description="One box for everything: your representatives, bills, votes, petitions, council motions — and every dollar MPs expense. Plain words work; we translate 'carbon tax' into what Parliament actually calls it."
    >
      <form action="/search" method="get" className="glass-card rounded-md border-border p-5">
        <div className="flex flex-col gap-3 sm:flex-row">
          <input
            name="q"
            aria-label="Search MPs, bills, votes, spending"
            defaultValue={query}
            minLength={2}
            maxLength={200}
            required
            placeholder="Search MPs, bills, votes, spending…"
            className="w-full rounded-md border border-border bg-white px-4 py-3 text-base outline-none focus:border-accent"
          />
          <button
            type="submit"
            className="rounded-md bg-ink px-6 py-3 text-sm font-semibold text-white transition hover:bg-slate-700"
          >
            Search
          </button>
        </div>
      </form>

      {query ? (
        <div className="mt-8 space-y-10">
          {/* 1 — Representatives: people first, because "who" is the most common question. */}
          {people.length ? (
            <section>
              <SectionHeading kicker="Representatives" note="Matched by name or riding" />
              <ul className="divide-y divide-border rounded-md border border-border bg-white">
                {people.map((person) => (
                  <li key={person.slug} className="flex items-center gap-3 px-4 py-3">
                    {person.image_url ? (
                      // eslint-disable-next-line @next/next/no-img-element -- external media host, avatar-sized
                      <img
                        src={person.image_url}
                        alt=""
                        width={40}
                        height={40}
                        className="h-10 w-10 shrink-0 rounded-full object-cover"
                      />
                    ) : (
                      <span
                        aria-hidden
                        className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-slate-100 text-sm font-semibold text-slate-500"
                      >
                        {person.full_name.charAt(0)}
                      </span>
                    )}
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <Link
                          href={`/politicians/${person.slug}`}
                          className="font-semibold hover:text-accent"
                        >
                          {person.full_name}
                        </Link>
                        <PartyBadge party={person.party_slug} size="xs" />
                        {person.roles.map((role) => (
                          <span
                            key={role}
                            className="inline-flex rounded-md bg-ink px-2 py-0.5 text-xs font-medium text-white"
                          >
                            {role}
                          </span>
                        ))}
                      </div>
                      {person.riding ? (
                        <p className="mt-0.5 truncate text-sm text-slate-500">
                          {person.riding}
                          {person.province_code ? `, ${person.province_code}` : ""}
                        </p>
                      ) : null}
                    </div>
                    {person.level ? <LevelBadge level={person.level} className="shrink-0" /> : null}
                  </li>
                ))}
              </ul>
            </section>
          ) : null}

          {/* 2 — The parliamentary record: bills, votes, petitions, motions. */}
          {results.length ? (
            <section>
              <SectionHeading kicker="Bills, votes & more" note="From the parliamentary record" />
              <div className="mt-3 space-y-3">
                {results.map((item) => (
                  <Link
                    key={`${item.entity_type}-${item.url_path}`}
                    href={item.url_path}
                    className="block rounded-md border border-border bg-white p-5 shadow-card transition hover:border-accent"
                  >
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="kicker rounded-md bg-mist px-2 py-0.5">
                        {item.entity_type}
                      </span>
                      {item.outcome && item.outcome !== "pending" && item.outcome !== "enacted" ? (
                        <span className="rounded-md bg-rose-50 px-2 py-0.5 text-xs font-medium text-rose-700">
                          {item.outcome.replaceAll("_", " ")}
                        </span>
                      ) : null}
                    </div>
                    <p className="mt-2 text-lg font-medium">{item.title}</p>
                    <p className="mt-1 text-sm text-slate-500">{item.snippet}</p>
                  </Link>
                ))}
              </div>
            </section>
          ) : null}

          {/* 3 — Spending: expense line items from the official disclosures. */}
          {expenses.length ? (
            <section>
              <SectionHeading kicker="Spending" note="From official MP expense disclosures" />
              <ul className="divide-y divide-border rounded-md border border-border bg-white">
                {expenses.map((item) => (
                  <li key={item.id} className="px-4 py-3">
                    <div className="flex items-baseline gap-3">
                      <div className="min-w-0 flex-1">
                        <div className="flex flex-wrap items-center gap-2">
                          <span
                            className={`rounded-md px-2 py-0.5 text-xs font-medium ${CATEGORY_STYLES[item.category] ?? "bg-slate-100 text-slate-600"}`}
                          >
                            {item.category}
                          </span>
                          <span className="font-semibold">
                            {item.supplier ?? item.description ?? "—"}
                          </span>
                        </div>
                        {item.supplier && item.description ? (
                          <p className="mt-0.5 text-sm text-slate-500">{item.description}</p>
                        ) : null}
                      </div>
                      <span className="shrink-0 text-right font-bold tabular-nums">
                        ${item.amount.toLocaleString(undefined, { maximumFractionDigits: 2 })}
                      </span>
                    </div>
                    <p className="mt-1 text-sm text-slate-500">
                      {item.mp_slug ? (
                        <Link href={`/politicians/${item.mp_slug}`} className="font-medium text-accent">
                          {item.mp_name}
                        </Link>
                      ) : (
                        <span className="font-medium">{item.mp_name}</span>
                      )}
                      {" · "}Q{item.quarter} {item.fiscal_year}
                      {" · "}
                      <a href={item.source_url} target="_blank" rel="noreferrer" className="text-accent">
                        official record ↗
                      </a>
                    </p>
                  </li>
                ))}
              </ul>
              <p className="mt-3 text-sm">
                <Link href={`/expenses?q=${encodeURIComponent(query)}`} className="font-medium text-accent">
                  Search all spending →
                </Link>
              </p>
            </section>
          ) : null}

          {nothingFound ? (
            <DataGap
              title="No results"
              detail={`Nothing in the record matched "${query}" — no representative, bill, vote or expense line. Try different words, or ask the question directly on the Ask page.`}
            />
          ) : null}

          {response === null && query.length >= 2 ? (
            <DataGap
              title="Search is temporarily unavailable"
              detail="The data service isn't responding — nothing is wrong with your search. Try again in a minute."
            />
          ) : null}
        </div>
      ) : null}
    </PageShell>
  );
}
