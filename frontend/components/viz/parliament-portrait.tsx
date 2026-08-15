import type { PoliticianListItem } from "@/lib/api";
import { partyColor } from "@/lib/parties";

/**
 * Parliament as a portrait: every sitting member, one dot, party colors —
 * in the Isotype / Du Bois tradition, the dataset itself is the artwork.
 * Each dot carries a tooltip; the strip is also a legend you can read.
 * Wrap in <Reveal> to let the chamber assemble party by party.
 */
export function ParliamentPortrait({
  politicians,
  rows = 6,
  className = ""
}: {
  politicians: PoliticianListItem[];
  rows?: number;
  className?: string;
}) {
  if (!politicians.length) return null;

  // Group by party, largest caucus first — the balance of power, visible.
  const groups = new Map<string, PoliticianListItem[]>();
  for (const person of politicians) {
    const key = person.current_membership?.party?.slug ?? "independent";
    const list = groups.get(key) ?? [];
    list.push(person);
    groups.set(key, list);
  }
  const ordered = [...groups.values()].sort((a, b) => b.length - a.length).flat();

  const cols = Math.ceil(ordered.length / rows);
  const CELL = 15;
  const R = 5;
  const width = cols * CELL;
  const height = rows * CELL;

  return (
    <svg
      viewBox={`0 0 ${width} ${height}`}
      className={`h-auto w-full ${className}`}
      role="img"
      aria-label={`The current Parliament: ${ordered.length} members, one dot each, coloured and grouped by party.`}
    >
      {ordered.map((person, i) => {
        // Fill column by column so parties read as contiguous blocks.
        const col = Math.floor(i / rows);
        const row = i % rows;
        // Single-string child: React 19 hydration requires <title> to hold
        // exactly one text node.
        const party = person.current_membership?.party?.short_name;
        const riding = person.current_membership?.riding_name;
        const tooltip = `${person.full_name}${party ? ` — ${party}` : ""}${riding ? `, ${riding}` : ""}`;
        return (
          <circle
            key={person.slug}
            className="reveal-dot"
            style={{ ["--dot-delay" as string]: `${Math.min(i * 2.5, 1000)}ms` }}
            cx={col * CELL + CELL / 2}
            cy={row * CELL + CELL / 2}
            r={R}
            fill={partyColor(person.current_membership?.party?.slug)}
          >
            <title>{tooltip}</title>
          </circle>
        );
      })}
    </svg>
  );
}
