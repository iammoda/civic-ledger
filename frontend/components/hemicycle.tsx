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

const VIEW_W = 400;
const VIEW_H = 210;
const CX = VIEW_W / 2;
const CY = VIEW_H - 4;
const OUTER_R = 186;
const INNER_R = 108;
// Visual gap between party segments, in degrees.
const PAD_DEG = 0.75;

function polar(cx: number, cy: number, r: number, angleDeg: number): [number, number] {
  const rad = (angleDeg * Math.PI) / 180;
  return [cx + r * Math.cos(rad), cy - r * Math.sin(rad)];
}

/** Annular sector from startDeg to endDeg (degrees, 180 = left, 0 = right). */
function arcPath(startDeg: number, endDeg: number): string {
  const [x1, y1] = polar(CX, CY, OUTER_R, startDeg);
  const [x2, y2] = polar(CX, CY, OUTER_R, endDeg);
  const [x3, y3] = polar(CX, CY, INNER_R, endDeg);
  const [x4, y4] = polar(CX, CY, INNER_R, startDeg);
  const large = Math.abs(startDeg - endDeg) > 180 ? 1 : 0;
  return [
    `M ${x1.toFixed(2)} ${y1.toFixed(2)}`,
    `A ${OUTER_R} ${OUTER_R} 0 ${large} 1 ${x2.toFixed(2)} ${y2.toFixed(2)}`,
    `L ${x3.toFixed(2)} ${y3.toFixed(2)}`,
    `A ${INNER_R} ${INNER_R} 0 ${large} 0 ${x4.toFixed(2)} ${y4.toFixed(2)}`,
    "Z"
  ].join(" ");
}

/**
 * News-style hemicycle: Yes votes fan from the LEFT, No votes from the
 * RIGHT, every segment in its party's real color. The top-centre tick is
 * the majority line — if the Yes side crosses it, the motion passes.
 *
 * Server-rendered SVG (the data is fully known at render time); the exact
 * per-party table below is the accessible reading of the same numbers, so
 * the chart itself is decorative to assistive tech.
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

  const total = segments.reduce((sum, s) => sum + s.value, 0);
  // Sweep from 180° (left) to 0° (right), minus padding between segments.
  const padTotal = PAD_DEG * Math.max(0, segments.length - 1);
  const sweepAvailable = 180 - padTotal;
  let cursor = 180;
  const paths = segments.map((segment, index) => {
    const sweep = total > 0 ? (segment.value / total) * sweepAvailable : 0;
    const start = cursor;
    const end = cursor - sweep;
    cursor = end - PAD_DEG;
    return (
      <path key={index} d={arcPath(start, end)} fill={segment.color}>
        <title>{`${segment.name}: ${segment.value} voted ${segment.side === "yea" ? "Yes" : "No"}`}</title>
      </path>
    );
  });

  return (
    <div>
      <div className="relative mx-auto w-full max-w-md">
        {/* Majority line at top centre. */}
        <div className="pointer-events-none absolute left-1/2 top-0 z-10 flex -translate-x-1/2 flex-col items-center">
          <span className="text-[10px] font-semibold uppercase tracking-wide text-slate-500">majority</span>
          <span className="h-3 w-px bg-slate-400" />
        </div>
        <div aria-hidden className="mt-4">
          <svg viewBox={`0 0 ${VIEW_W} ${VIEW_H}`} className="h-auto w-full" role="presentation">
            {paths}
          </svg>
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

      {/* Exact counts per party, with logos — the accessible reading of the chart. */}
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
                  {row.yea > 0 && row.nay > 0 ? <span aria-hidden className="text-slate-300"> · </span> : null}
                  {row.nay > 0 ? <span>{row.nay} No</span> : null}
                  {row.yea === 0 && row.nay === 0 ? "no votes cast" : null}
                  {row.absent > 0 ? <span className="text-slate-500"> · {row.absent} absent</span> : null}
                </span>
              </li>
            );
          })}
      </ul>
    </div>
  );
}
