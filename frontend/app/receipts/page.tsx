import Link from "next/link";

import { DataGap } from "@/components/data-gap";
import { ExplainerStrip } from "@/components/explainer-strip";
import { PageShell } from "@/components/page-shell";
import { PartyLogo } from "@/components/party-logo";
import { getReceipts, type ReceiptRow } from "@/lib/api";
import { partyInfo } from "@/lib/parties";

export const metadata = { title: "The Receipts — who spends, who's lobbied, who shows up" };

function Avatar({ row }: { row: ReceiptRow }) {
  if (row.image_url) {
    // eslint-disable-next-line @next/next/no-img-element
    return (
      <img
        src={row.image_url}
        alt=""
        className="h-9 w-9 shrink-0 rounded-full border border-black/10 object-cover"
      />
    );
  }
  return (
    <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-slate-200 text-sm font-semibold text-slate-600">
      {row.person_name.charAt(0)}
    </span>
  );
}

function ScopePill({ href, active, children }: { href: string; active: boolean; children: React.ReactNode }) {
  return (
    <Link
      href={href}
      aria-current={active ? "page" : undefined}
      className={`rounded-full border px-4 py-2 text-sm transition ${
        active
          ? "border-accent bg-accent text-white"
          : "border-black/10 bg-white text-slate-700 hover:border-accent hover:text-accent"
      }`}
    >
      {children}
    </Link>
  );
}

const PROVINCE_CODES = [
  "AB", "BC", "MB", "NB", "NL", "NS", "NT", "NU", "ON", "PE", "QC", "SK", "YT",
] as const;

export default async function ReceiptsPage({
  searchParams
}: {
  searchParams: Promise<{ scope?: string; province?: string }>;
}) {
  const { scope: scopeParam, province: provinceParam } = await searchParams;
  // "ontario" survives as a backward-compat alias for the provincial scope.
  const scope =
    scopeParam === "provincial" || scopeParam === "ontario" ? "provincial" : "federal";
  const provinceCandidate = provinceParam?.toUpperCase();
  const province = PROVINCE_CODES.find((code) => code === provinceCandidate);
  const receipts = await getReceipts(scope, province);

  const scopeHref = (target: "federal" | "provincial") => {
    const params = new URLSearchParams();
    if (target === "provincial") params.set("scope", "provincial");
    if (province) params.set("province", province);
    const qs = params.toString();
    return `/receipts${qs ? `?${qs}` : ""}`;
  };

  return (
    <PageShell
      eyebrow="Follow the money · Show up · Break ranks"
      title="The Receipts"
      description="Who spends the most, who gets lobbied the most, who breaks ranks, who misses votes, and the biggest contracts on the books — computed straight from official records, same math for everyone."
    >
      <div className="mb-4 flex flex-wrap gap-2">
        <ScopePill href={scopeHref("federal")} active={scope === "federal"}>
          MPs — federal
        </ScopePill>
        <ScopePill href={scopeHref("provincial")} active={scope === "provincial"}>
          MPPs — provincial
        </ScopePill>
      </div>

      <form action="/receipts" method="get" className="mb-6 flex flex-wrap items-center gap-2">
        {scope === "provincial" ? (
          <input type="hidden" name="scope" value="provincial" />
        ) : null}
        <label htmlFor="receipts-province" className="text-sm text-slate-600">
          Province
        </label>
        <select
          id="receipts-province"
          name="province"
          defaultValue={province ?? ""}
          className="rounded-md border border-border bg-white px-3 py-2 text-sm outline-none focus:border-accent"
        >
          <option value="">All provinces</option>
          {PROVINCE_CODES.map((code) => (
            <option key={code} value={code}>
              {code}
            </option>
          ))}
        </select>
        <button
          type="submit"
          className="rounded-md bg-ink px-4 py-2 text-sm font-semibold text-white transition hover:bg-slate-700"
        >
          Filter
        </button>
        {province ? (
          <Link
            href={scope === "provincial" ? "/receipts?scope=provincial" : "/receipts"}
            className="inline-flex items-center gap-1.5 rounded-full border border-accent bg-white px-3 py-1.5 text-sm font-medium text-accent transition hover:bg-accent hover:text-white"
          >
            {province} only <span aria-hidden="true">✕</span>
            <span className="sr-only">— remove province filter</span>
          </Link>
        ) : null}
      </form>

      {scope === "provincial" && (!province || province === "ON") ? (
        <ExplainerStrip id="receipts-ontario-data">
          Ontario publishes no machine-readable per-MPP expense or lobbying data, so only the voting
          boards — dissent and attendance at Queen&apos;s Park — are available here. The money boards
          remain federal-only.
        </ExplainerStrip>
      ) : null}

      {!receipts?.boards.length ? (
        receipts?.note ? (
          <DataGap title="No provincial vote data yet" detail={receipts.note} />
        ) : (
          <DataGap
            title="Not enough data yet"
            detail="Leaderboards appear after the expense, lobbying, and vote syncs have run."
          />
        )
      ) : (
        <div className="grid gap-6 lg:grid-cols-2">
          {receipts.boards.map((board) => (
            <section key={board.key} className="glass-card rounded-[2rem] p-6">
              <h2 className="text-xl font-bold">{board.title}</h2>
              <p className="mt-1 text-sm text-slate-500">{board.subtitle}</p>
              <ol className="mt-4 space-y-2">
                {board.rows.map((row, index) => {
                  const inner = (
                    <>
                      <span className="w-6 shrink-0 text-right text-sm font-semibold text-slate-500">
                        {index + 1}
                      </span>
                      <Avatar row={row} />
                      <span className="min-w-0 flex-1">
                        <span className="flex flex-wrap items-center gap-1.5">
                          <span className="font-semibold">{row.person_name}</span>
                          {row.party ? (
                            <>
                              <PartyLogo party={row.party} size={18} />
                              <span className="text-xs text-slate-500">{partyInfo(row.party).label}</span>
                            </>
                          ) : null}
                        </span>
                        {row.context ? (
                          <span className="block truncate text-xs text-slate-500">{row.context}</span>
                        ) : row.riding ? (
                          <span className="block truncate text-xs text-slate-500">{row.riding}</span>
                        ) : null}
                      </span>
                      <span className="shrink-0 text-sm font-bold text-slate-800">{row.display}</span>
                    </>
                  );
                  return (
                    <li key={`${board.key}-${index}`}>
                      {row.person_slug ? (
                        <Link
                          href={`/politicians/${row.person_slug}`}
                          className="flex items-center gap-3 rounded-2xl border border-black/5 bg-white p-3 transition hover:border-accent"
                        >
                          {inner}
                        </Link>
                      ) : (
                        <span className="flex items-center gap-3 rounded-2xl border border-black/5 bg-white p-3">
                          {inner}
                        </span>
                      )}
                    </li>
                  );
                })}
              </ol>
              {/* The caveat ships with the numbers — the anti-fake-news layer. */}
              <p className="mt-4 rounded-2xl bg-slate-50 p-3 text-xs leading-5 text-slate-500">
                {board.caveat}
              </p>
            </section>
          ))}
        </div>
      )}

      {receipts ? (
        <p className="mt-8 text-xs leading-6 text-slate-500">
          {receipts.generated_note}{" "}
          <Link href="/charter" className="text-accent">
            How we keep this fair →
          </Link>
        </p>
      ) : null}
    </PageShell>
  );
}
