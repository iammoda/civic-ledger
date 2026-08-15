import Link from "next/link";

import { DataGap } from "@/components/data-gap";
import { ExplainerStrip } from "@/components/explainer-strip";
import { LeaderBoard } from "@/components/leader-board";
import { PageShell } from "@/components/page-shell";
import { MONEY_TABS, SectionTabs } from "@/components/section-tabs";
import { getReceipts } from "@/lib/api";

export const metadata = { title: "The Receipts — who spends, who's lobbied, who shows up" };

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
      eyebrow="Money · Leaderboards"
      title="The Receipts"
      description="Who spends the most, who gets lobbied the most, who breaks ranks, who misses votes, and the biggest contracts on the books — computed straight from official records, same math for everyone."
    >
      <SectionTabs tabs={MONEY_TABS} ariaLabel="Money sections" />

      <div className="mb-6 flex flex-wrap items-center gap-x-6 gap-y-3 text-sm font-medium">
        <span className="kicker">Scope</span>
        {(
          [
            ["federal", "MPs — federal"],
            ["provincial", "MPPs — provincial"]
          ] as const
        ).map(([key, label]) => (
          <Link
            key={key}
            href={scopeHref(key)}
            scroll={false}
            aria-current={scope === key ? "page" : undefined}
            className={`border-b-2 pb-0.5 transition ${
              scope === key ? "border-ink font-semibold text-ink" : "border-transparent text-stone-500 hover:text-ink"
            }`}
          >
            {label}
          </Link>
        ))}
        <form action="/receipts" method="get" className="flex items-center gap-2">
          {scope === "provincial" ? <input type="hidden" name="scope" value="provincial" /> : null}
          <label htmlFor="receipts-province" className="text-stone-500">
            Province
          </label>
          <select
            id="receipts-province"
            name="province"
            defaultValue={province ?? ""}
            className="rounded-md border border-border bg-white px-2.5 py-1.5 text-sm outline-none focus:border-accent"
          >
            <option value="">All</option>
            {PROVINCE_CODES.map((code) => (
              <option key={code} value={code}>
                {code}
              </option>
            ))}
          </select>
          <button
            type="submit"
            className="rounded-full bg-ink px-4 py-1.5 text-sm font-semibold text-white transition hover:bg-stone-700"
          >
            Filter
          </button>
          {province ? (
            <Link
              href={scope === "provincial" ? "/receipts?scope=provincial" : "/receipts"}
              className="text-signal hover:underline"
            >
              {province} ✕<span className="sr-only"> — remove province filter</span>
            </Link>
          ) : null}
        </form>
      </div>

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
        <div className="grid gap-x-16 gap-y-12 lg:grid-cols-2">
          {receipts.boards.map((board) => (
            <LeaderBoard key={board.key} board={board} />
          ))}
        </div>
      )}

      {receipts ? (
        <p className="mt-10 text-xs leading-6 text-stone-500">
          {receipts.generated_note}{" "}
          <Link href="/charter" className="text-accent">
            How we keep this fair →
          </Link>
        </p>
      ) : null}
    </PageShell>
  );
}
