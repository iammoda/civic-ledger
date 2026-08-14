import { NavLink } from "@/components/nav-link";

/**
 * Sub-navigation inside a merged nav section — the second level of the
 * "four doors" structure. Rendered as quiet text tabs under the masthead,
 * not pills: the typographic system stays calm.
 */
export type SectionTab = { href: string; label: string };

export const WHAT_HAPPENED_TABS: SectionTab[] = [
  { href: "/votes", label: "Votes" },
  { href: "/bills", label: "Bills" },
  { href: "/graveyard", label: "The Graveyard" },
  { href: "/petitions", label: "Petitions" }
];

export const YOUR_REPS_TABS: SectionTab[] = [
  { href: "/politicians", label: "All representatives" },
  { href: "/cabinet", label: "The Cabinet" },
  { href: "/committees", label: "Committees" },
  { href: "/compare", label: "Compare two MPs" }
];

export const MONEY_TABS: SectionTab[] = [
  { href: "/money", label: "Overview" },
  { href: "/expenses", label: "Every expense" },
  { href: "/receipts", label: "Leaderboards" }
];

export function SectionTabs({ tabs, ariaLabel }: { tabs: SectionTab[]; ariaLabel: string }) {
  return (
    <nav aria-label={ariaLabel} className="mb-8 flex gap-6 overflow-x-auto border-b border-border text-[15px] font-medium text-slate-500">
      {tabs.map((tab) => (
        <NavLink
          key={tab.href}
          href={tab.href}
          label={tab.label}
          className="-mb-px shrink-0 whitespace-nowrap border-b-2 border-transparent pb-2.5 transition hover:text-ink"
          activeClassName="border-ink font-semibold text-ink"
        />
      ))}
    </nav>
  );
}
