import { partyInfo } from "@/lib/parties";

/**
 * Every MP's ballot as one dot, grouped by party — 300+ people made
 * scannable in a glance. Filled dot = Yes, hollow = No, faint = didn't
 * vote. Server-rendered SVG; an accessible summary table should accompany
 * it wherever it appears (the vote detail page provides one).
 */
type Ballot = {
  person_slug: string;
  full_name: string;
  party_slug?: string | null;
  ballot: string;
};

const DOT = 7; // radius-ish cell
const CELL = 18;
const PER_ROW = 24;

export function DotGrid({ ballots, className = "" }: { ballots: Ballot[]; className?: string }) {
  if (!ballots.length) return null;

  // Group by party, largest first; inside a party: yes, no, then the rest.
  const groups = new Map<string, Ballot[]>();
  for (const ballot of ballots) {
    const key = partyInfo(ballot.party_slug).label;
    const list = groups.get(key) ?? [];
    list.push(ballot);
    groups.set(key, list);
  }
  const ordered = [...groups.entries()].sort((a, b) => b[1].length - a[1].length);
  const ballotRank = (b: string) => (b === "yea" ? 0 : b === "nay" ? 1 : 2);

  // Layout: for each party, a label row then dot rows.
  let y = 0;
  const parts: Array<{ label: string; color: string; y: number; dots: Array<{ x: number; y: number; ballot: string; name: string }> }> = [];
  for (const [label, list] of ordered) {
    const color = partyInfo(list[0].party_slug).color;
    const sorted = [...list].sort((a, b) => ballotRank(a.ballot) - ballotRank(b.ballot));
    y += 22; // label height
    const dots = sorted.map((ballot, i) => ({
      x: (i % PER_ROW) * CELL,
      y: y + Math.floor(i / PER_ROW) * CELL,
      ballot: ballot.ballot,
      name: ballot.full_name
    }));
    parts.push({ label, color, y: y - 8, dots });
    y += Math.ceil(sorted.length / PER_ROW) * CELL + 10;
  }

  const width = PER_ROW * CELL;
  const height = y;
  let dotIndex = 0;

  return (
    <svg
      viewBox={`0 0 ${width} ${height}`}
      className={`w-full max-w-md ${className}`}
      role="img"
      aria-label="Every MP's ballot, one dot each, grouped by party. Filled dots voted Yes, outlined dots voted No, faint dots did not vote."
    >
      {parts.map((part) => (
        <g key={part.label}>
          <text x={0} y={part.y} className="fill-stone-500" fontSize={11} fontWeight={600}>
            {part.label}
          </text>
          {part.dots.map((dot, i) => {
            const delay = { ["--dot-delay" as string]: `${Math.min((dotIndex++) * 2, 900)}ms` };
            if (dot.ballot === "yea") {
              return (
                <circle key={i} className="reveal-dot" style={delay} cx={dot.x + DOT} cy={dot.y + DOT} r={DOT - 1.5} fill={part.color}>
                  <title>{`${dot.name} — Yes`}</title>
                </circle>
              );
            }
            if (dot.ballot === "nay") {
              return (
                <circle key={i} className="reveal-dot" style={delay} cx={dot.x + DOT} cy={dot.y + DOT} r={DOT - 2.5} fill="none" stroke={part.color} strokeWidth={2}>
                  <title>{`${dot.name} — No`}</title>
                </circle>
              );
            }
            return (
              <circle key={i} className="reveal-dot" style={delay} cx={dot.x + DOT} cy={dot.y + DOT} r={DOT - 3} fill="#cbd5e1" opacity={0.55}>
                <title>{`${dot.name} — did not vote`}</title>
              </circle>
            );
          })}
        </g>
      ))}
    </svg>
  );
}
