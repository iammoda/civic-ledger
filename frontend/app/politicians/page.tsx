import type { Metadata } from "next";
import Link from "next/link";

import { DataGap } from "@/components/data-gap";
import { PageShell } from "@/components/page-shell";
import { listPoliticians } from "@/lib/api";

const PROVINCES = ["AB", "BC", "MB", "NB", "NL", "NS", "NT", "NU", "ON", "PE", "QC", "SK", "YT"];

const LEVELS: Array<{ key: string; label: string }> = [
  { key: "federal", label: "Federal" },
  { key: "provincial", label: "Provincial" },
  { key: "municipal", label: "Municipal" }
];

export const metadata: Metadata = {
  title: "Find your representatives",
  description:
    "Every MP with party, riding and photo — filter by party, province or name, or look up who represents your postal code."
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
    const partyInfo = p.current_membership?.party;
    if (partyInfo?.slug && partyInfo.short_name) partySlugs.set(partyInfo.slug, partyInfo.short_name);
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
      eyebrow={level === "federal" ? "MPs" : level === "provincial" ? "MPPs · MLAs · MNAs" : "Councillors · Mayors"}
      title="Your representatives, on the record"
      description={
        level === "federal"
          ? "Every MP with their attendance, party discipline, money, and full voting record — identical measures for everyone."
          : "Every representative synced from official rosters — profiles and contact today, legislative records as their governments publish them."
      }
    >
      <div className="mb-6 flex flex-wrap gap-2">
        {LEVELS.map((entry) => (
          <Link
            key={entry.key}
            href={buildHref({ level: entry.key, party: "", province: "" })}
            className={`rounded-full px-4 py-2 text-sm font-medium transition ${
              level === entry.key
                ? "bg-slate-900 text-white"
                : "border border-black/10 bg-white text-slate-600 hover:border-accent hover:text-accent"
            }`}
          >
            {entry.label}
          </Link>
        ))}
      </div>
      <form action="/politicians" method="get" className="glass-card mb-6 rounded-[2rem] p-6">
        <div className="flex flex-col gap-3 sm:flex-row">
          <input
            name="q"
            aria-label="Search MPs by name"
            defaultValue={q ?? ""}
            placeholder="Search by name…"
            className="w-full rounded-full border border-black/10 bg-white px-5 py-3 outline-none focus:border-accent"
          />
          {party ? <input type="hidden" name="party" value={party} /> : null}
          {province ? <input type="hidden" name="province" value={province} /> : null}
          {level !== "federal" ? <input type="hidden" name="level" value={level} /> : null}
          <button type="submit" className="rounded-full bg-slate-900 px-6 py-3 text-sm font-medium text-white">
            Search
          </button>
        </div>
        {partySlugs.size || party ? (
          <div className="mt-4 flex flex-wrap gap-2">
            {party ? (
              <Link href={buildHref({ party: "" })} className="rounded-full border border-signal/40 px-3 py-1.5 text-xs text-signal">
                Party: {party} ✕
              </Link>
            ) : (
              [...partySlugs.entries()].map(([slug, name]) => (
                <Link
                  key={slug}
                  href={buildHref({ party: slug })}
                  className="rounded-full border border-black/10 bg-white px-3 py-1.5 text-xs text-slate-600 transition hover:border-accent hover:text-accent"
                >
                  {name}
                </Link>
              ))
            )}
            {province ? (
              <Link href={buildHref({ province: "" })} className="rounded-full border border-signal/40 px-3 py-1.5 text-xs text-signal">
                {province} ✕
              </Link>
            ) : (
              PROVINCES.map((code) => (
                <Link
                  key={code}
                  href={buildHref({ province: code })}
                  className="rounded-full border border-black/10 bg-white px-3 py-1.5 text-xs text-slate-500 transition hover:border-accent hover:text-accent"
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
          <p className="mb-4 text-sm text-slate-500">{politicians.meta.total} representatives</p>
          <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-3">
            {politicians.items.map((politician) => (
              <Link
                key={politician.slug}
                href={`/politicians/${politician.slug}`}
                className="glass-card rounded-[2rem] p-6 transition hover:-translate-y-0.5"
              >
                <div className="flex items-start gap-4">
                  {politician.image_url ? (
                    // eslint-disable-next-line @next/next/no-img-element -- external media host, avatar-sized
                    <img
                      src={politician.image_url}
                      alt=""
                      width={56}
                      height={56}
                      loading="lazy"
                      className="h-14 w-14 shrink-0 rounded-2xl object-cover"
                    />
                  ) : (
                    <div aria-hidden className="flex h-14 w-14 shrink-0 items-center justify-center rounded-2xl bg-slate-100 text-lg font-semibold text-slate-400">
                      {politician.full_name.charAt(0)}
                    </div>
                  )}
                  <div className="min-w-0">
                    <h2 className="truncate text-lg font-semibold">{politician.full_name}</h2>
                    <p className="mt-1 text-sm text-slate-600">
                      {politician.current_membership?.party?.short_name ?? "Independent or unknown"}
                    </p>
                    <p className="truncate text-sm text-slate-500">
                      {politician.current_membership?.riding_name ??
                        politician.current_membership?.region_name ??
                        "Constituency pending"}
                      {politician.level === "municipal" && politician.jurisdiction_name
                        ? ` · ${politician.jurisdiction_name}`
                        : politician.current_membership?.province_code
                          ? `, ${politician.current_membership.province_code}`
                          : ""}
                    </p>
                  </div>
                </div>
              </Link>
            ))}
          </div>
        </>
      )}
    </PageShell>
  );
}
