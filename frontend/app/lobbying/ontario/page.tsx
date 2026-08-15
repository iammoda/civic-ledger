import type { Metadata } from "next";
import Link from "next/link";

import { DataGap } from "@/components/data-gap";
import { PageShell } from "@/components/page-shell";
import { Pagination } from "@/components/pagination";
import { SectionTabs, MONEY_TABS } from "@/components/section-tabs";
import { getOntarioRegistrations } from "@/lib/api";
import { formatDateShort } from "@/lib/humanize";

export const metadata: Metadata = {
  title: "Who lobbies Ontario — the provincial registry, searchable",
  description:
    "Every active registration in Ontario's lobbyist registry: which organizations are registered to lobby which ministries and MPPs, about what — searchable by organization, subject and ministry."
};

const PAGE_SIZE = 25;

export default async function OntarioLobbyingPage({
  searchParams
}: {
  searchParams: Promise<{ q?: string; subject?: string; ministry?: string; offset?: string }>;
}) {
  const { q, subject, ministry, offset: offsetParam } = await searchParams;
  const offset = Number.parseInt(offsetParam ?? "0", 10) || 0;
  const data = await getOntarioRegistrations({ q, subject, ministry, limit: PAGE_SIZE, offset });

  return (
    <PageShell
      eyebrow="Money · Ontario lobbying"
      title="Who lobbies Ontario"
      titleAccent="— on the record"
      description="Every active registration in Ontario's lobbyist registry: which organizations are licensed to lobby which ministries and MPPs, and what they say they want. From the Office of the Integrity Commissioner, synced weekly."
    >
      <SectionTabs tabs={MONEY_TABS} ariaLabel="Money sections" />

      {/* The honest-difference explainer: registrations, not meetings. */}
      <p className="mb-6 max-w-3xl border-l-4 border-amber-400 pl-4 text-sm leading-6 text-stone-600">
        <span className="font-semibold text-ink">Ontario publishes registrations, not meetings.</span>{" "}
        Unlike Ottawa&apos;s registry (which logs each communication), Ontario discloses who is{" "}
        <em>registered</em> to lobby which offices about what. A listing here means &ldquo;licensed to
        lobby&rdquo; — never &ldquo;met with.&rdquo;
      </p>

      <form action="/lobbying/ontario" method="get" className="mb-6">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
          <input
            name="q"
            aria-label="Search organizations, firms and lobbyists"
            defaultValue={q ?? ""}
            placeholder="Search organizations, firms, lobbyists… (e.g. 'Hydro One')"
            className="w-full rounded-none border-0 border-b-2 border-ink bg-transparent px-1 py-2 text-lg outline-none placeholder:text-stone-300 focus:border-accent sm:max-w-md"
          />
          <input
            name="ministry"
            aria-label="Filter by ministry or office"
            defaultValue={ministry ?? ""}
            placeholder="Ministry (e.g. 'Health')"
            className="w-full rounded-none border-0 border-b-2 border-ink bg-transparent px-1 py-2 text-lg outline-none placeholder:text-stone-300 focus:border-accent sm:max-w-56"
          />
          <input
            name="subject"
            aria-label="Filter by subject matter"
            defaultValue={subject ?? ""}
            placeholder="Subject (e.g. 'Housing')"
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
          detail="The Ontario lobbying data isn't reachable right now — try again in a moment."
        />
      ) : !data.items.length ? (
        <DataGap
          title="No registrations match"
          detail="Nothing in Ontario's active registrations matches these filters. The registry updates weekly — try broader terms."
        />
      ) : (
        <div>
          <p className="mb-2 text-sm text-stone-500">
            {data.total.toLocaleString("en-CA")} active registration{data.total === 1 ? "" : "s"}
          </p>
          {data.items.map((item) => (
            <article key={item.registration_number} className="rule py-5">
              <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
                <h2 className="font-serif text-lg font-bold tracking-tight text-ink">
                  {item.client_name ?? item.firm_name ?? item.lobbyist_name ?? "Unnamed registrant"}
                </h2>
                <span className="text-xs uppercase tracking-wide text-stone-400">
                  {item.lobbyist_type === "consultant" ? "via consultant" : "in-house"}
                  {item.firm_name && item.client_name ? ` · ${item.firm_name}` : ""}
                </span>
                {item.last_amendment_date ? (
                  <span className="ml-auto text-xs text-stone-500">
                    updated {formatDateShort(item.last_amendment_date)}
                  </span>
                ) : null}
              </div>
              {item.goals ? <p className="mt-1.5 max-w-3xl text-sm leading-6 text-stone-600">{item.goals}</p> : null}
              {item.subject_matters ? (
                <p className="mt-1 text-xs text-stone-500">Subjects: {item.subject_matters}</p>
              ) : null}
              {item.target_ministries.length ? (
                <p className="mt-1 text-xs text-stone-500">
                  Targets: {item.target_ministries.slice(0, 4).join(" · ")}
                  {item.target_ministries.length > 4 ? ` · +${item.target_ministries.length - 4} more` : ""}
                </p>
              ) : null}
              {item.target_mpp_offices.length ? (
                <p className="mt-1 text-xs font-medium text-amber-700">
                  Names {item.target_mpp_offices.length} MPP office
                  {item.target_mpp_offices.length === 1 ? "" : "s"}:{" "}
                  {item.target_mpp_offices.slice(0, 3).map((office) => office.replace("Office of the Member for ", "")).join(", ")}
                  {item.target_mpp_offices.length > 3 ? "…" : ""}
                </p>
              ) : null}
            </article>
          ))}
          <Pagination
            total={data.total}
            limit={PAGE_SIZE}
            offset={offset}
            basePath="/lobbying/ontario"
            params={{ q, subject, ministry }}
          />
        </div>
      )}

      <p className="mt-8 max-w-3xl text-xs leading-6 text-stone-500">
        Source: Ontario&apos;s{" "}
        <a
          href="https://lobbyist.oico.on.ca/Pages/Public/PublicSearch/"
          target="_blank"
          rel="noreferrer"
          className="text-accent"
        >
          Lobbyist Registry
        </a>{" "}
        (Office of the Integrity Commissioner), synced weekly. Registrations are legal disclosures by
        lobbyists themselves. Being lobbied is part of the job — what matters is that it&apos;s on the record.{" "}
        <Link href="/methodology" className="text-accent">
          Methodology →
        </Link>
      </p>
    </PageShell>
  );
}
