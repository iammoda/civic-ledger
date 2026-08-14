import type { Metadata } from "next";
import Link from "next/link";

import { DataGap } from "@/components/data-gap";
import { LevelBadge } from "@/components/level-badge";
import { PageShell } from "@/components/page-shell";
import { SectionTabs, YOUR_REPS_TABS } from "@/components/section-tabs";
import { listPoliticians } from "@/lib/api";
import { partyColor, partyInfo } from "@/lib/parties";

const PROVINCES = ["AB", "BC", "MB", "NB", "NL", "NS", "NT", "NU", "ON", "PE", "QC", "SK", "YT"];

const LEVELS: Array<{ key: string; label: string }> = [
  { key: "all", label: "All" },
  { key: "federal", label: "MPs — federal" },
  { key: "provincial", label: "MPPs & MLAs — provincial" },
  { key: "municipal", label: "Councillors & Mayors — municipal" }
];

export const metadata: Metadata = {
  title: "Who represents you?",
  description:
    "Every representative — federal, provincial and municipal — with party, riding and photo. Filter by party, province or name."
};

export default async function PoliticiansPage({
  searchParams
}: {
  searchParams: Promise<{ q?: string; party?: string; province?: string; level?: string }>;
}) {
  const { q, party, province, level: levelParam } = await searchParams;
  const level = LEVELS.some((entry) => entry.key === levelParam) ? levelParam! : "federal";
  const politicians = await listPoliticians({ q, party, province, level });

  // Party filter chips from the data itself — no hardcoded party list.
  const partySlugs = new Map<string, string>();
  for (const p of politicians?.items ?? []) {
    const partyEntry = p.current_membership?.party;
    if (partyEntry?.slug && partyEntry.short_name) partySlugs.set(partyEntry.slug, partyEntry.short_name);
  }

  const buildHref = (next: { q?: string; party?: string; province?: string; level?: string }) => {
    const params = new URLSearchParams();
    const merged = { q, party, province, level, ...next };
    if (merged.q) params.set("q", merged.q);
    if (merged.party) params.set("party", merged.party);
    if (merged.province) params.set("province", merged.province);
    if (merged.level && merged.level !== "federal") params.set("level", merged.level);
    const qs = params.toString();
    return `/politicians${qs ? `?${qs}` : ""}`;
  };

  return (
    <PageShell
      eyebrow="Your reps"
      title="Who represents you?"
      description={
        level === "all"
          ? "Every current representative — federal, provincial and municipal — synced from official rosters, with identical measures wherever their governments publish records."
          : level === "federal"
            ? "Every MP with their attendance, party discipline, money, and full voting record — identical measures for everyone."
            : "Every representative synced from official rosters — profiles and contact today, legislative records as their governments publish them."
      }
    >
      <SectionTabs tabs={YOUR_REPS_TABS} ariaLabel="Your reps sections" />

      {/* Level first: the primary way into the directory. */}
      <div className="mb-6 flex flex-wrap items-center gap-x-6 gap-y-2 text-sm font-medium">
        <span className="kicker">Level</span>
        {LEVELS.map((entry) => (
          <Link
            key={entry.key}
            href={buildHref({ level: entry.key, party: "", province: "" })}
            aria-current={level === entry.key ? "page" : undefined}
            className={`border-b-2 pb-0.5 transition ${
              level === entry.key
                ? "border-ink font-semibold text-ink"
                : "border-transparent text-slate-500 hover:text-ink"
            }`}
          >
            {entry.label}
          </Link>
        ))}
      </div>

      <form action="/politicians" method="get" className="mb-4">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
          <input
            name="q"
            aria-label="Search representatives by name"
            defaultValue={q ?? ""}
            placeholder="Search by name…"
            className="w-full rounded-none border-0 border-b-2 border-ink bg-transparent px-1 py-2 text-lg outline-none placeholder:text-slate-300 focus:border-accent sm:max-w-sm"
          />
          {party ? <input type="hidden" name="party" value={party} /> : null}
          {province ? <input type="hidden" name="province" value={province} /> : null}
          {level !== "federal" ? <input type="hidden" name="level" value={level} /> : null}
          <button type="submit" className="shrink-0 rounded-full bg-ink px-6 py-2.5 text-sm font-semibold text-white transition hover:bg-slate-700">
            Search
          </button>
        </div>
        {partySlugs.size || party || province ? (
          <div className="mt-4 flex flex-wrap items-center gap-x-4 gap-y-2 text-xs font-medium">
            {party ? (
              <Link href={buildHref({ party: "" })} className="rounded-full border border-signal/40 px-3 py-1 text-signal">
                Party: {partyInfo(party).label} ✕
              </Link>
            ) : (
              [...partySlugs.entries()].map(([slug, name]) => (
                <Link
                  key={slug}
                  href={buildHref({ party: slug })}
                  className="text-slate-500 transition hover:text-ink"
                >
                  <span
                    aria-hidden
                    className="mr-1.5 inline-block h-2 w-2 rounded-full"
                    style={{ backgroundColor: partyColor(slug) }}
                  />
                  {name}
                </Link>
              ))
            )}
            <span aria-hidden className="text-slate-300">·</span>
            {province ? (
              <Link href={buildHref({ province: "" })} className="rounded-full border border-signal/40 px-3 py-1 text-signal">
                {province} ✕
              </Link>
            ) : (
              PROVINCES.map((code) => (
                <Link
                  key={code}
                  href={buildHref({ province: code })}
                  className="text-slate-400 transition hover:text-ink"
                >
                  {code}
                </Link>
              ))
            )}
          </div>
        ) : null}
      </form>

      {!politicians?.items.length ? (
        <DataGap
          title={q || party || province ? "No matches" : "No politician records yet"}
          detail={
            q || party || province
              ? "Try different filters or clear the search."
              : "Run the first OpenParliament ingestion job to populate politician profiles."
          }
        />
      ) : (
        <>
          <p className="rule-heavy mb-2 pt-3 text-sm text-slate-500">
            <span className="stat-figure text-lg text-ink">{politicians.meta.total}</span> representatives
          </p>
          <div className="grid gap-x-10 sm:grid-cols-2 xl:grid-cols-3">
            {politicians.items.map((politician) => {
              const partyEntry = politician.current_membership?.party;
              return (
                <Link
                  key={politician.slug}
                  href={`/politicians/${politician.slug}`}
                  className="rule group flex items-center gap-5 py-5"
                >
                  {politician.image_url ? (
                    // eslint-disable-next-line @next/next/no-img-element -- external media host, avatar-sized
                    <img
                      src={politician.image_url.replace(/^http:\/\//, "https://")}
                      alt=""
                      width={72}
                      height={72}
                      loading="lazy"
                      className="h-18 w-18 shrink-0 rounded-md object-cover"
                      style={{ width: 72, height: 72, borderBottom: `3px solid ${partyColor(partyEntry?.slug)}` }}
                    />
                  ) : (
                    <div
                      aria-hidden
                      className="flex h-18 w-18 shrink-0 items-center justify-center rounded-md bg-slate-100 font-serif text-2xl font-semibold text-slate-400"
                      style={{ width: 72, height: 72, borderBottom: `3px solid ${partyColor(partyEntry?.slug)}` }}
                    >
                      {politician.full_name.charAt(0)}
                    </div>
                  )}
                  <div className="min-w-0">
                    <h2 className="truncate font-serif text-lg font-bold tracking-tight text-ink transition group-hover:text-accent">
                      {politician.full_name}
                    </h2>
                    <p className="mt-0.5 truncate text-sm text-slate-500">
                      <span className="font-medium" style={{ color: partyColor(partyEntry?.slug) }}>
                        {partyEntry ? partyInfo(partyEntry.slug).label : "No party on record"}
                      </span>
                      {" · "}
                      {politician.current_membership?.riding_name ??
                        politician.current_membership?.region_name ??
                        "Constituency pending"}
                      {politician.level === "municipal" && politician.jurisdiction_name
                        ? ` · ${politician.jurisdiction_name}`
                        : politician.current_membership?.province_code
                          ? `, ${politician.current_membership.province_code}`
                          : ""}
                    </p>
                    {level === "all" && politician.level ? (
                      <div className="mt-1.5">
                        <LevelBadge level={politician.level} />
                      </div>
                    ) : null}
                  </div>
                </Link>
              );
            })}
          </div>
        </>
      )}
    </PageShell>
  );
}
