/**
 * Party identity system: official party colors + display names.
 *
 * Colors are the parties' own brand colors, used purely to IDENTIFY parties
 * in charts and badges (like every newsroom does). Matching is by keyword so
 * provincial slugs ("conservative-party-of-british-columbia") resolve too.
 */

export type PartyInfo = {
  /** Canonical key, e.g. "liberal" */
  key: string;
  /** Short display name, e.g. "Liberal" */
  label: string;
  /** Brand color (hex) for charts and accents. */
  color: string;
  /** Tailwind classes for a soft badge (bg + text). */
  badgeClass: string;
  /** Path to the party logo in /public, when we have one. */
  logo?: string;
};

const PARTIES: Array<PartyInfo & { match: RegExp }> = [
  {
    key: "liberal",
    label: "Liberal",
    color: "#D71920",
    badgeClass: "bg-red-50 text-red-700",
    logo: "/parties/liberal.svg",
    match: /liberal/i
  },
  {
    key: "conservative",
    label: "Conservative",
    color: "#1A4782",
    badgeClass: "bg-blue-50 text-blue-800",
    logo: "/parties/conservative.svg",
    match: /conservative|tory/i
  },
  {
    key: "ndp",
    label: "NDP",
    color: "#F37021",
    badgeClass: "bg-orange-50 text-orange-700",
    logo: "/parties/ndp.svg",
    match: /ndp|new.?democratic/i
  },
  {
    key: "bloc",
    label: "Bloc",
    color: "#33B2CC",
    badgeClass: "bg-cyan-50 text-cyan-700",
    logo: "/parties/bloc.svg",
    match: /bloc/i
  },
  {
    key: "green",
    label: "Green",
    color: "#3D9B35",
    badgeClass: "bg-green-50 text-green-700",
    logo: "/parties/green.svg",
    match: /green/i
  },
  {
    key: "ppc",
    label: "PPC",
    color: "#442D7B",
    badgeClass: "bg-purple-50 text-purple-700",
    logo: "/parties/ppc.svg",
    match: /people'?s.?party|ppc/i
  }
];

const UNKNOWN: PartyInfo = {
  key: "other",
  label: "Independent",
  color: "#64748b",
  badgeClass: "bg-slate-100 text-slate-600"
};

/** Resolve a party slug or name ("liberal", "Bloc Québécois", provincial slugs…) to identity info. */
export function partyInfo(slugOrName?: string | null): PartyInfo {
  if (!slugOrName) return UNKNOWN;
  const found = PARTIES.find((p) => p.match.test(slugOrName));
  if (found) return found;
  if (/independent/i.test(slugOrName)) return { ...UNKNOWN, label: "Independent" };
  // Unknown party: keep its name, neutral styling.
  return { ...UNKNOWN, label: slugOrName };
}

/** Chart color for a party slug/name. */
export function partyColor(slugOrName?: string | null): string {
  return partyInfo(slugOrName).color;
}
