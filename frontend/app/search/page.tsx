import type { Metadata } from "next";
import Link from "next/link";

import { DataGap } from "@/components/data-gap";
import { PageShell } from "@/components/page-shell";
import { searchContent } from "@/lib/api";

export const metadata: Metadata = {
  title: "Search",
  description:
    "Search bills, votes, petitions and council motions in plain language."
};

export default async function SearchPage({
  searchParams
}: {
  searchParams: Promise<{ q?: string }>;
}) {
  const { q } = await searchParams;
  const query = (q ?? "").trim();
  const response = query.length >= 2 ? await searchContent(query) : null;

  return (
    <PageShell
      eyebrow="Search"
      title="Search bills and votes"
      description="Plain words work — we translate 'carbon tax' into what Parliament actually calls it."
    >
      <form action="/search" method="get" className="glass-card rounded-[2rem] p-6">
        <div className="flex flex-col gap-3 sm:flex-row">
          <input
            name="q"
            aria-label="Search bills and votes"
            defaultValue={query}
            minLength={2}
            maxLength={200}
            required
            placeholder="Search bills and votes…"
            className="w-full rounded-full border border-black/10 bg-white px-5 py-3 text-base outline-none focus:border-accent"
          />
          <button type="submit" className="rounded-full bg-slate-900 px-6 py-3 text-sm font-medium text-white">
            Search
          </button>
        </div>
      </form>

      {query ? (
        <div className="mt-8 space-y-3">
          {response?.results.length ? (
            response.results.map((item) => (
              <Link
                key={`${item.entity_type}-${item.url_path}`}
                href={item.url_path}
                className="block rounded-3xl border border-black/10 bg-white p-5 transition hover:-translate-y-0.5"
              >
                <div className="flex flex-wrap items-center gap-2">
                  <span className="rounded-full bg-slate-100 px-2.5 py-0.5 text-xs uppercase tracking-[0.14em] text-slate-500">
                    {item.entity_type}
                  </span>
                  {item.outcome && item.outcome !== "pending" && item.outcome !== "enacted" ? (
                    <span className="rounded-full bg-rose-50 px-2.5 py-0.5 text-xs font-medium text-rose-700">
                      {item.outcome.replaceAll("_", " ")}
                    </span>
                  ) : null}
                </div>
                <p className="mt-2 text-lg font-medium">{item.title}</p>
                <p className="mt-1 text-sm text-slate-500">{item.snippet}</p>
              </Link>
            ))
          ) : response ? (
            <DataGap
              title="No results"
              detail={`Nothing in the parliamentary record matched "${query}". Try different words, or ask the question directly on the Ask page.`}
            />
          ) : (
            <DataGap
              title="Search is temporarily unavailable"
              detail="The data service isn't responding — nothing is wrong with your search. Try again in a minute."
            />
          )}
        </div>
      ) : null}
    </PageShell>
  );
}
