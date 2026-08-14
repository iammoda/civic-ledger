import type { Metadata } from "next";
import Link from "next/link";

import { DataGap } from "@/components/data-gap";
import { PageShell } from "@/components/page-shell";
import { comparePoliticians, listPoliticians, type ComparisonSide } from "@/lib/api";

function MetricRow({
  label,
  a,
  b,
  format = (v: number) => String(v)
}: {
  label: string;
  a?: number | null;
  b?: number | null;
  format?: (v: number) => string;
}) {
  return (
    <div className="grid grid-cols-3 items-center gap-2 border-t border-black/5 py-3 text-sm">
      <span className="text-right font-medium">{a != null ? format(a) : "—"}</span>
      <span className="text-center text-xs uppercase tracking-[0.14em] text-slate-500">{label}</span>
      <span className="font-medium">{b != null ? format(b) : "—"}</span>
    </div>
  );
}

function SideHeader({ side }: { side: ComparisonSide }) {
  return (
    <div className="text-center">
      <Link href={`/politicians/${side.slug}`} className="text-lg font-semibold text-accent">
        {side.full_name}
      </Link>
      <p className="mt-1 text-sm text-slate-500">
        {side.party ?? "Unknown party"}
        {side.riding ? ` · ${side.riding}` : ""}
      </p>
    </div>
  );
}

export const metadata: Metadata = {
  title: "Compare two MPs",
  description:
    "Side-by-side voting records, attendance and party discipline for any two MPs."
};

export default async function ComparePage({
  searchParams
}: {
  searchParams: Promise<{ a?: string; b?: string }>;
}) {
  const { a, b } = await searchParams;
  const [politicians, comparison] = await Promise.all([
    listPoliticians(),
    a && b ? comparePoliticians(a, b) : Promise.resolve(null)
  ]);

  const options = politicians?.items ?? [];

  return (
    <PageShell
      eyebrow="Compare"
      title="MPs, side by side"
      description="Same measures for everyone: attendance, party discipline, dissents, lobbying attention, and donations."
    >
      <form action="/compare" method="get" className="glass-card rounded-[2rem] p-6">
        <div className="grid gap-3 sm:grid-cols-[1fr_auto_1fr_auto]">
          <select
            name="a"
            aria-label="First MP to compare"
            defaultValue={a ?? ""}
            required
            className="w-full rounded-full border border-black/10 bg-white px-5 py-3 outline-none focus:border-accent"
          >
            <option value="" disabled>
              Pick the first MP…
            </option>
            {options.map((p) => (
              <option key={p.slug} value={p.slug}>
                {p.full_name}
              </option>
            ))}
          </select>
          <span className="self-center text-center text-sm text-slate-500">vs</span>
          <select
            name="b"
            aria-label="Second MP to compare"
            defaultValue={b ?? ""}
            required
            className="w-full rounded-full border border-black/10 bg-white px-5 py-3 outline-none focus:border-accent"
          >
            <option value="" disabled>
              Pick the second MP…
            </option>
            {options.map((p) => (
              <option key={p.slug} value={p.slug}>
                {p.full_name}
              </option>
            ))}
          </select>
          <button type="submit" className="rounded-full bg-slate-900 px-6 py-3 text-sm font-medium text-white">
            Compare
          </button>
        </div>
      </form>

      {a && b && !comparison ? (
        <div className="mt-8">
          <DataGap title="Comparison unavailable" detail="One of those MPs wasn't found, or the API is unreachable." />
        </div>
      ) : null}

      {comparison ? (
        <div className="glass-card mt-8 rounded-[2rem] p-8">
          <div className="grid grid-cols-[1fr_auto_1fr] items-start gap-2">
            <SideHeader side={comparison.a} />
            <span aria-hidden className="self-center px-3 text-slate-300">
              |
            </span>
            <SideHeader side={comparison.b} />
          </div>

          <div className="mt-6">
            <MetricRow
              label="Attendance"
              a={comparison.a.attendance_pct}
              b={comparison.b.attendance_pct}
              format={(v) => `${v}%`}
            />
            <MetricRow
              label="Votes with party"
              a={comparison.a.party_line_pct}
              b={comparison.b.party_line_pct}
              format={(v) => `${v}%`}
            />
            <MetricRow label="Dissents" a={comparison.a.dissent_count} b={comparison.b.dissent_count} />
            <MetricRow label="Votes cast" a={comparison.a.votes_cast} b={comparison.b.votes_cast} />
            <MetricRow
              label="Lobbying contacts (12 mo)"
              a={comparison.a.lobbying_last_12mo}
              b={comparison.b.lobbying_last_12mo}
            />
            <MetricRow
              label="Donations on record"
              a={comparison.a.donations_total}
              b={comparison.b.donations_total}
              format={(v) => `$${v.toLocaleString(undefined, { maximumFractionDigits: 0 })}`}
            />
          </div>

          <p className="mt-6 border-t border-black/5 pt-4 text-xs text-slate-500">
            Identical metrics computed identically for every MP.{" "}
            <Link href="/methodology" className="text-accent">
              Methodology →
            </Link>
          </p>
        </div>
      ) : null}
    </PageShell>
  );
}
