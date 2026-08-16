import type { Metadata } from "next";
import Link from "next/link";

import { DataGap } from "@/components/data-gap";
import { PageShell } from "@/components/page-shell";
import { Pagination } from "@/components/pagination";
import { RegistrationRow } from "@/components/registration-row";
import { SectionTabs, MONEY_TABS } from "@/components/section-tabs";
import { getLobbyingCommunications, getLobbyingRegistrations } from "@/lib/api";
import { formatDateShort } from "@/lib/humanize";
import { LOBBYING_JURISDICTIONS, lobbyingJurisdiction } from "@/lib/lobbying-coverage";

export const metadata: Metadata = {
  title: "Who lobbies your governments — one place, every province",
  description:
    "Lobbying records across Canada: every federal and BC meeting logged, Ontario's registrations, and an honest scorecard of what each province does — and doesn't — disclose."
};

const PAGE_SIZE = 25;

export default async function LobbyingHubPage({
  searchParams
}: {
  searchParams: Promise<{
    province?: string;
    view?: string;
    q?: string;
    subject?: string;
    ministry?: string;
    offset?: string;
  }>;
}) {
  const params = await searchParams;
  const jurisdiction = lobbyingJurisdiction(params.province ?? "ca");
  const offset = Number.parseInt(params.offset ?? "0", 10) || 0;
  // BC publishes both kinds; everyone else has exactly one.
  const bcView = jurisdiction.code === "bc" && params.view === "registrations" ? "registrations" : "meetings";
  const activeKind =
    jurisdiction.status !== "live" ? null : jurisdiction.code === "bc" ? bcView : jurisdiction.kind;

  const [comms, registrations] = await Promise.all([
    activeKind === "meetings" && (jurisdiction.code === "ca" || jurisdiction.code === "bc")
      ? getLobbyingCommunications(jurisdiction.code, {
          q: params.q,
          subject: params.subject,
          limit: PAGE_SIZE,
          offset
        })
      : Promise.resolve(null),
    activeKind === "registrations" && (jurisdiction.code === "on" || jurisdiction.code === "bc")
      ? getLobbyingRegistrations(jurisdiction.code, {
          q: params.q,
          subject: params.subject,
          ministry: params.ministry,
          limit: PAGE_SIZE,
          offset
        })
      : Promise.resolve(null)
  ]);

  const laneHref = (code: string, view?: string) => {
    const out = new URLSearchParams();
    if (code !== "ca") out.set("province", code);
    if (view === "registrations") out.set("view", view);
    const qs = out.toString();
    return `/lobbying${qs ? `?${qs}` : ""}`;
  };

  return (
    <PageShell
      eyebrow="Money · Lobbying"
      title="Who lobbies your governments"
      titleAccent="— on the record"
      description="Paid lobbying is legal and disclosed — but every government decides how much you get to see. Pick a jurisdiction; we show exactly what its registry publishes, and say so plainly when it publishes little or nothing."
    >
      <SectionTabs tabs={MONEY_TABS} ariaLabel="Money sections" />

      {/* Jurisdiction chips: the filter switches datasets, never blends them. */}
      <nav aria-label="Jurisdiction" className="mb-5 flex flex-wrap gap-x-5 gap-y-2 text-sm font-medium">
        {LOBBYING_JURISDICTIONS.map((entry) => {
          const active = entry.code === jurisdiction.code;
          return (
            <Link
              key={entry.code}
              href={laneHref(entry.code)}
              aria-current={active ? "page" : undefined}
              className={`border-b-2 pb-0.5 transition ${
                active
                  ? "border-ink font-semibold text-ink"
                  : entry.status === "live"
                    ? "border-transparent text-stone-600 hover:text-ink"
                    : "border-transparent text-stone-400 hover:text-stone-600"
              }`}
            >
              {entry.short}
              {entry.status !== "live" ? <span aria-hidden className="ml-1 text-xs">·</span> : null}
            </Link>
          );
        })}
      </nav>

      {/* The disparity, printed where people will ask about it. */}
      <details className="mb-8 max-w-3xl border-l-4 border-amber-400 pl-4">
        <summary className="cursor-pointer text-sm font-semibold text-ink">
          Why the numbers differ wildly by province — who tells you what
        </summary>
        <ul className="mt-3 space-y-1.5 text-sm leading-6 text-stone-600">
          {LOBBYING_JURISDICTIONS.map((entry) => (
            <li key={entry.code}>
              <span className="font-semibold text-ink">{entry.label}:</span> {entry.scorecard}
              {entry.registryUrl ? (
                <>
                  {" "}
                  <a href={entry.registryUrl} target="_blank" rel="noreferrer" className="text-accent">
                    (official registry ↗)
                  </a>
                </>
              ) : null}
            </li>
          ))}
        </ul>
        <p className="mt-3 text-xs leading-5 text-stone-500">
          A meeting log tells you who actually talked to whom, when, about what. A registration only tells
          you who is <em>licensed</em> to lobby. That difference is each government&apos;s choice — not ours.
        </p>
      </details>

      {jurisdiction.status === "no-law" ? (
        <DataGap
          title={`${jurisdiction.label}: nothing to show — by law`}
          detail="The territories have no lobbying transparency law. Nobody is required to disclose lobbying here, so no registry exists. That absence is itself worth knowing."
        />
      ) : null}

      {jurisdiction.status === "planned" ? (
        <div className="max-w-3xl">
          <DataGap
            title={`${jurisdiction.label} is in the works`}
            detail={
              jurisdiction.gapNote ??
              `Every province runs its own lobbying registry, and some make the data far easier to reuse than others — BC publishes clean downloadable files, Ontario made us collect records one at a time, and ${jurisdiction.label} keeps its registry inside an app that doesn't share data easily. We add provinces based on how many people they serve and how hard their government makes it.`
            }
          />
          {jurisdiction.registryUrl ? (
            <p className="mt-4 text-sm">
              Meanwhile, the official registry is one click away:{" "}
              <a href={jurisdiction.registryUrl} target="_blank" rel="noreferrer" className="font-medium text-accent">
                {jurisdiction.registryName} ↗
              </a>
            </p>
          ) : null}
        </div>
      ) : null}

      {jurisdiction.code === "bc" && jurisdiction.status === "live" ? (
        <div className="mb-4 flex gap-5 text-sm font-medium">
          <Link
            href={laneHref("bc")}
            className={bcView === "meetings" ? "border-b-2 border-ink pb-0.5 font-semibold text-ink" : "text-stone-500 hover:text-ink"}
          >
            Meetings
          </Link>
          <Link
            href={laneHref("bc", "registrations")}
            className={bcView === "registrations" ? "border-b-2 border-ink pb-0.5 font-semibold text-ink" : "text-stone-500 hover:text-ink"}
          >
            Registrations
          </Link>
        </div>
      ) : null}

      {activeKind === "meetings" ? (
        <MeetingsLane
          jurisdictionCode={jurisdiction.code}
          jurisdictionLabel={jurisdiction.label}
          comms={comms}
          q={params.q}
          subject={params.subject}
          offset={offset}
          laneParams={{ province: params.province, view: params.view }}
        />
      ) : null}

      {activeKind === "registrations" ? (
        <RegistrationsLane
          jurisdictionCode={jurisdiction.code}
          jurisdictionLabel={jurisdiction.label}
          registrations={registrations}
          q={params.q}
          subject={params.subject}
          ministry={params.ministry}
          offset={offset}
          laneParams={{ province: params.province, view: params.view }}
        />
      ) : null}

      <p className="mt-8 max-w-3xl text-xs leading-6 text-stone-500">
        Being lobbied is part of the job — access is legal and disclosed. What matters is that it&apos;s on
        the record, and that the record is usable.{" "}
        <Link href="/methodology" className="text-accent">
          Methodology →
        </Link>
      </p>
    </PageShell>
  );
}

function MeetingsLane({
  jurisdictionCode,
  jurisdictionLabel,
  comms,
  q,
  subject,
  offset,
  laneParams
}: {
  jurisdictionCode: string;
  jurisdictionLabel: string;
  comms: Awaited<ReturnType<typeof getLobbyingCommunications>>;
  q?: string;
  subject?: string;
  offset: number;
  laneParams: Record<string, string | undefined>;
}) {
  return (
    <div>
      <form action="/lobbying" method="get" className="mb-6">
        {laneParams.province ? <input type="hidden" name="province" value={laneParams.province} /> : null}
        {laneParams.view ? <input type="hidden" name="view" value={laneParams.view} /> : null}
        <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
          <input
            name="q"
            aria-label="Search organizations, lobbyists and office holders"
            defaultValue={q ?? ""}
            placeholder="Search organizations, lobbyists, office holders…"
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

      {!comms ? (
        <DataGap title="Registry data unavailable" detail="The lobbying data isn't reachable right now — try again in a moment." />
      ) : !comms.items.length ? (
        <DataGap title="No reports match" detail="Nothing matches these filters — try broader terms." />
      ) : (
        <div>
          <p className="mb-2 text-sm text-stone-500">
            {comms.total.toLocaleString("en-CA")} reported communication{comms.total === 1 ? "" : "s"} —{" "}
            {jurisdictionLabel} logs every one
          </p>
          {comms.items.map((item, index) => (
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
              {item.registry_url ? (
                <p className="mt-1 text-xs">
                  <a href={item.registry_url} target="_blank" rel="noreferrer" className="text-accent">
                    View in the official registry ↗
                  </a>
                </p>
              ) : null}
            </article>
          ))}
          <Pagination
            total={comms.total}
            limit={PAGE_SIZE}
            offset={offset}
            basePath="/lobbying"
            params={{ ...laneParams, q, subject }}
          />
        </div>
      )}
      <p className="mt-6 max-w-3xl text-xs leading-5 text-stone-500">
        Source:{" "}
        {jurisdictionCode === "bc"
          ? "Office of the Registrar of Lobbyists for BC (open data, monthly). Reports since May 2020."
          : "Registry of Lobbyists (Office of the Commissioner of Lobbying of Canada), synced weekly."}{" "}
        Lobbyists file these reports themselves; dates and subjects are as reported.
      </p>
    </div>
  );
}

function RegistrationsLane({
  jurisdictionCode,
  jurisdictionLabel,
  registrations,
  q,
  subject,
  ministry,
  offset,
  laneParams
}: {
  jurisdictionCode: string;
  jurisdictionLabel: string;
  registrations: Awaited<ReturnType<typeof getLobbyingRegistrations>>;
  q?: string;
  subject?: string;
  ministry?: string;
  offset: number;
  laneParams: Record<string, string | undefined>;
}) {
  return (
    <div>
      {jurisdictionCode === "on" ? (
        <p className="mb-6 max-w-3xl border-l-4 border-amber-400 pl-4 text-sm leading-6 text-stone-600">
          <span className="font-semibold text-ink">Ontario publishes registrations, not meetings.</span>{" "}
          Unlike Ottawa and BC (which log each communication), Ontario discloses who is <em>registered</em> to
          lobby which offices about what. A listing here means &ldquo;licensed to lobby&rdquo; — never
          &ldquo;met with.&rdquo;
        </p>
      ) : null}

      {registrations && registrations.details_pending > 0 ? (
        <p className="mb-4 text-sm text-stone-500">
          Syncing: full filings for {registrations.details_pending.toLocaleString("en-CA")} of{" "}
          {registrations.total.toLocaleString("en-CA")} registrations are still being collected from the
          registry (it has no data download, so each record is fetched individually). Every registration is
          already listed below; goals and targets fill in as they arrive.
        </p>
      ) : null}

      <form action="/lobbying" method="get" className="mb-6">
        {laneParams.province ? <input type="hidden" name="province" value={laneParams.province} /> : null}
        {laneParams.view ? <input type="hidden" name="view" value={laneParams.view} /> : null}
        <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
          <input
            name="q"
            aria-label="Search organizations, firms and lobbyists"
            defaultValue={q ?? ""}
            placeholder="Search organizations, firms, lobbyists…"
            className="w-full rounded-none border-0 border-b-2 border-ink bg-transparent px-1 py-2 text-lg outline-none placeholder:text-stone-300 focus:border-accent sm:max-w-md"
          />
          {jurisdictionCode === "on" ? (
            <input
              name="ministry"
              aria-label="Filter by ministry or office"
              defaultValue={ministry ?? ""}
              placeholder="Ministry (e.g. 'Health')"
              className="w-full rounded-none border-0 border-b-2 border-ink bg-transparent px-1 py-2 text-lg outline-none placeholder:text-stone-300 focus:border-accent sm:max-w-56"
            />
          ) : null}
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

      {!registrations ? (
        <DataGap title="Registry data unavailable" detail="The lobbying data isn't reachable right now — try again in a moment." />
      ) : !registrations.items.length ? (
        <DataGap title="No registrations match" detail="Nothing matches these filters — try broader terms." />
      ) : (
        <div>
          <p className="mb-2 text-sm text-stone-500">
            {registrations.total.toLocaleString("en-CA")} active registration
            {registrations.total === 1 ? "" : "s"} in {jurisdictionLabel}
          </p>
          {registrations.items.map((item) => (
            <RegistrationRow
              key={item.registration_number}
              item={item}
              registryUrl={
                jurisdictionCode === "bc"
                  ? "https://www.lobbyistsregistrar.bc.ca/app/secure/orl/lrs/do/guest"
                  : undefined
              }
            />
          ))}
          <Pagination
            total={registrations.total}
            limit={PAGE_SIZE}
            offset={offset}
            basePath="/lobbying"
            params={{ ...laneParams, q, subject, ministry }}
          />
        </div>
      )}
      <p className="mt-6 max-w-3xl text-xs leading-5 text-stone-500">
        Source:{" "}
        {jurisdictionCode === "on"
          ? "Ontario Lobbyist Registry (Office of the Integrity Commissioner), collected record-by-record because Ontario offers no data download; synced weekly."
          : "Office of the Registrar of Lobbyists for BC (open data, monthly)."}
      </p>
    </div>
  );
}
