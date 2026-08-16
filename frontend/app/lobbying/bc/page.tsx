import type { Metadata } from "next";
import Link from "next/link";

import { DataGap } from "@/components/data-gap";
import { PageShell } from "@/components/page-shell";
import { Pagination } from "@/components/pagination";
import { SectionTabs, MONEY_TABS } from "@/components/section-tabs";
import { getBcLobbying } from "@/lib/api";
import { formatDateShort } from "@/lib/humanize";

export const metadata: Metadata = {
  title: "Who lobbies British Columbia — every reported meeting, searchable",
  description:
    "BC's Lobbying Activity Reports: dated, per-meeting logs of who lobbied which public office holders about what, from the Office of the Registrar of Lobbyists' open data."
};

const PAGE_SIZE = 25;

export default async function BcLobbyingPage({
  searchParams
}: {
  searchParams: Promise<{ q?: string; subject?: string; offset?: string }>;
}) {
  const { q, subject, offset: offsetParam } = await searchParams;
  const offset = Number.parseInt(offsetParam ?? "0", 10) || 0;
  const data = await getBcLobbying({ q, subject, limit: PAGE_SIZE, offset });

  return (
    <PageShell
      eyebrow="Money · BC lobbying"
      title="Who lobbies British Columbia"
      titleAccent="— meeting by meeting"
      description="Unlike Ontario, BC discloses actual lobbying communications: every dated contact with a public office holder, who made it, for which client, about what. From the Registrar of Lobbyists' open data, synced monthly."
    >
      <SectionTabs tabs={MONEY_TABS} ariaLabel="Money sections" />

      <form action="/lobbying/bc" method="get" className="mb-6">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
          <input
            name="q"
            aria-label="Search organizations, lobbyists and office holders"
            defaultValue={q ?? ""}
            placeholder="Search organizations, lobbyists, office holders… (e.g. 'Teck')"
            className="w-full rounded-none border-0 border-b-2 border-ink bg-transparent px-1 py-2 text-lg outline-none placeholder:text-stone-300 focus:border-accent sm:max-w-md"
          />
          <input
            name="subject"
            aria-label="Filter by subject matter"
            defaultValue={subject ?? ""}
            placeholder="Subject (e.g. 'Energy')"
            className="w-full rounded-none border-0 border-b-2 border-ink bg-transparent px-1 py-2 text-lg outline-none placeholder:text-stone-300 focus:border-accent sm:max-w-56"
          />
          <button type="submit" className="rounded-full bg-slate-900 px-6 py-3 text-sm font-medium text-white">
            Search
          </button>
        </div>
      </form>

      {!data ? (
        <DataGap
          title="Registry data unavailable"
          detail="The BC lobbying data isn't reachable right now — try again in a moment."
        />
      ) : !data.items.length ? (
        <DataGap
          title="No reports match"
          detail="Nothing in BC's activity reports matches these filters. The dataset updates monthly — try broader terms."
        />
      ) : (
        <div>
          <p className="mb-2 text-sm text-stone-500">
            {data.total.toLocaleString("en-CA")} reported communication{data.total === 1 ? "" : "s"}
          </p>
          {data.items.map((item, index) => (
            <article key={`${item.comm_date}-${index}`} className="rule py-4">
              <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
                <h2 className="font-serif text-lg font-bold tracking-tight text-ink">
                  {item.client_name ?? item.registrant_name ?? "Unnamed client"}
                </h2>
                {item.registrant_name && item.client_name ? (
                  <span className="text-xs text-stone-400">lobbyist: {item.registrant_name}</span>
                ) : null}
                <span className="ml-auto text-xs text-stone-500">
                  {item.comm_date ? formatDateShort(item.comm_date) : "date unknown"}
                </span>
              </div>
              {item.dpoh_title ? (
                <p className="mt-1 text-sm font-medium text-stone-700">Lobbied: {item.dpoh_title}</p>
              ) : null}
              {item.institution ? <p className="mt-0.5 text-xs text-stone-500">{item.institution}</p> : null}
              {item.subjects ? (
                <p className="mt-1 line-clamp-2 text-sm leading-6 text-stone-600">{item.subjects}</p>
              ) : null}
            </article>
          ))}
          <Pagination
            total={data.total}
            limit={PAGE_SIZE}
            offset={offset}
            basePath="/lobbying/bc"
            params={{ q, subject }}
          />
        </div>
      )}

      <p className="mt-8 max-w-3xl text-xs leading-6 text-stone-500">
        Source:{" "}
        <a
          href="https://www.lobbyistsregistrar.bc.ca/the-registry/open-data/"
          target="_blank"
          rel="noreferrer"
          className="text-accent"
        >
          Office of the Registrar of Lobbyists for BC — open data
        </a>
        , updated monthly (reports since May 2020). Every row is a communication a lobbyist was legally
        required to report. Being lobbied is part of the job — what matters is that it&apos;s on the record.{" "}
        <Link href="/methodology" className="text-accent">
          Methodology →
        </Link>
      </p>
    </PageShell>
  );
}
