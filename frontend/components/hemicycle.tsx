"use client";

import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";

import { PartyLogo } from "@/components/party-logo";
import { partyInfo } from "@/lib/parties";

type PartyBreakdown = {
  party_slug: string;
  party_name?: string | null;
  yea: number;
  nay: number;
  paired: number;
  absent: number;
};

type Segment = {
  name: string;
  value: number;
  color: string;
  side: "yea" | "nay";
};

/**
 * News-style hemicycle: Yes votes fan from the LEFT, No votes from the
 * RIGHT, every segment in its party's real color. The top-centre tick is
 * the majority line — if the Yes side crosses it, the motion passes.
 */
export function Hemicycle({
  rows,
  result,
  yeaTotal,
  nayTotal
}: {
  rows: PartyBreakdown[];
  result?: string | null;
  yeaTotal: number;
  nayTotal: number;
}) {
  if (!rows.length) {
    return <p className="text-sm text-slate-500">No recorded party breakdown is available.</p>;
  }

  // Left → right: biggest Yes party first, then smaller Yes parties toward
  // the centre; smaller No parties after the centre, biggest No party last.
  const yes: Segment[] = rows
    .filter((r) => r.yea > 0)
    .sort((a, b) => b.yea - a.yea)
    .map((r) => ({ name: partyInfo(r.party_slug).label, value: r.yea, color: partyInfo(r.party_slug).color, side: "yea" as const }));
  const no: Segment[] = rows
    .filter((r) => r.nay > 0)
    .sort((a, b) => a.nay - b.nay)
    .map((r) => ({ name: partyInfo(r.party_slug).label, value: r.nay, color: partyInfo(r.party_slug).color, side: "nay" as const }));
  const segments = [...yes, ...no];
  const passed = (result ?? "").toLowerCase() === "passed";

  return (
    <div>
      <div className="relative mx-auto w-full max-w-md">
        {/* Majority line at top centre. */}
        <div className="pointer-events-none absolute left-1/2 top-0 z-10 flex -translate-x-1/2 flex-col items-center">
          <span className="text-[10px] font-semibold uppercase tracking-wide text-slate-400">majority</span>
          <span className="h-3 w-px bg-slate-400" />
        </div>
        <div className="h-44">
          <ResponsiveContainer width="100%" height="100%">
            <PieChart margin={{ top: 18, bottom: 0, left: 0, right: 0 }}>
              <Pie
                data={segments}
                dataKey="value"
                nameKey="name"
                cx="50%"
                cy="100%"
                startAngle={180}
                endAngle={0}
                innerRadius="58%"
                outerRadius="100%"
                paddingAngle={0.75}
                stroke="none"
                isAnimationActive={false}
              >
                {segments.map((segment, index) => (
                  <Cell key={index} fill={segment.color} />
                ))}
              </Pie>
              <Tooltip
                formatter={(value, _name, entry) => {
                  const seg = entry?.payload as Segment | undefined;
                  return [`${value} voted ${seg?.side === "yea" ? "Yes" : "No"}`, seg?.name];
                }}
              />
            </PieChart>
          </ResponsiveContainer>
        </div>
        {/* Yes / No shoulders + result in the arc's mouth. */}
        <div className="pointer-events-none absolute inset-x-0 bottom-0 flex items-end justify-between px-1">
          <div className="text-left">
            <p className="text-2xl font-bold leading-6 text-ink">{yeaTotal}</p>
            <p className="text-xs font-semibold uppercase tracking-wide text-teal-700">Yes</p>
          </div>
          <div className="pb-0.5 text-center">
            <p className={`text-lg font-bold leading-5 ${passed ? "text-teal-700" : "text-signal"}`}>
              {passed ? "Passed" : result === "Negatived" ? "Failed" : result ?? ""}
            </p>
          </div>
          <div className="text-right">
            <p className="text-2xl font-bold leading-6 text-ink">{nayTotal}</p>
            <p className="text-xs font-semibold uppercase tracking-wide text-signal">No</p>
          </div>
        </div>
      </div>

      {/* Exact counts per party, with logos. */}
      <ul className="mt-5 divide-y divide-border border-t border-border">
        {[...rows]
          .sort((a, b) => b.yea + b.nay - (a.yea + a.nay))
          .map((row) => {
            const info = partyInfo(row.party_slug);
            return (
              <li key={row.party_slug} className="flex items-center gap-2.5 py-2 text-sm">
                <PartyLogo party={row.party_slug} size={18} />
                <span className="font-semibold">{info.label}</span>
                <span className="ml-auto tabular-nums text-slate-600">
                  {row.yea > 0 ? <span className="font-bold text-ink">{row.yea} Yes</span> : null}
                  {row.yea > 0 && row.nay > 0 ? <span className="text-slate-300"> · </span> : null}
                  {row.nay > 0 ? <span>{row.nay} No</span> : null}
                  {row.yea === 0 && row.nay === 0 ? "no votes cast" : null}
                  {row.absent > 0 ? <span className="text-slate-400"> · {row.absent} absent</span> : null}
                </span>
              </li>
            );
          })}
      </ul>
    </div>
  );
}
