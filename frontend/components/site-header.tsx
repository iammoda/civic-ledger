import Link from "next/link";

import { HeaderSearch } from "@/components/header-search";
import { MyRepsChip } from "@/components/my-reps-chip";
import { NavLink } from "@/components/nav-link";

/**
 * Four doors, not eight: each nav item is a question, and the routes that
 * answer it light the item up. Sub-navigation lives inside each section
 * (SectionTabs) so first-time visitors see one simple choice.
 */
const NAV_SECTIONS = [
  {
    href: "/politicians",
    label: "Your reps",
    matchPrefixes: ["/politicians", "/cabinet", "/committees"]
  },
  {
    href: "/votes",
    label: "What happened",
    matchPrefixes: ["/votes", "/bills", "/graveyard", "/petitions"]
  },
  { href: "/issues", label: "Issues", matchPrefixes: ["/issues"] },
  {
    href: "/money",
    label: "Money",
    matchPrefixes: ["/money", "/expenses", "/receipts"]
  }
];

export function SiteHeader() {
  return (
    <header className="sticky top-0 z-20 border-b border-border bg-surface/95 backdrop-blur">
      <div className="mx-auto flex max-w-[1600px] items-center gap-4 px-5 py-3.5 sm:px-10">
        <Link href="/" className="shrink-0 font-serif text-[1.35rem] font-bold leading-none tracking-tight">
          Civic Ledger<span className="text-brass">.</span>
        </Link>
        <nav aria-label="Main" className="hidden items-center gap-1 text-[15px] font-medium text-stone-600 sm:flex">
          {NAV_SECTIONS.map((item) => (
            <NavLink
              key={item.href}
              href={item.href}
              label={item.label}
              matchPrefixes={item.matchPrefixes}
              className="border-b-2 border-transparent px-3 py-2 transition hover:text-ink"
              activeClassName="border-ink font-semibold text-ink"
            />
          ))}
        </nav>
        <div className="ml-auto flex items-center gap-2">
          <MyRepsChip />
          <HeaderSearch />
        </div>
      </div>
      {/* Mobile nav: horizontal scroll strip under the wordmark. */}
      <nav
        aria-label="Main mobile"
        className="flex gap-1 overflow-x-auto border-t border-border px-4 py-2 text-sm font-medium text-stone-600 sm:hidden"
      >
        {[{ href: "/", label: "Home", matchPrefixes: ["/"] }, ...NAV_SECTIONS].map((item) => (
          <NavLink
            key={item.href}
            href={item.href}
            label={item.label}
            matchPrefixes={item.matchPrefixes}
            className="shrink-0 rounded-full px-3 py-1.5 transition hover:bg-stone-100"
            activeClassName="bg-ink font-semibold text-white"
          />
        ))}
      </nav>
    </header>
  );
}
