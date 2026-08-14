import Link from "next/link";

import { HeaderSearch } from "@/components/header-search";
import { NavLink } from "@/components/nav-link";

const navItems = [
  { href: "/politicians", label: "Representatives" },
  { href: "/cabinet", label: "Cabinet" },
  { href: "/bills", label: "Bills" },
  { href: "/votes", label: "Votes" },
  { href: "/issues", label: "Issues" },
  { href: "/expenses", label: "Follow the money" },
  { href: "/receipts", label: "The Receipts" }
];

export function SiteHeader() {
  return (
    <header className="sticky top-0 z-20 border-b border-border bg-white/95 backdrop-blur">
      <div className="mx-auto flex max-w-6xl items-center justify-between gap-3 px-4 py-3 sm:px-6">
        <Link href="/" className="shrink-0 font-serif text-lg font-bold tracking-tight">
          Civic Ledger
        </Link>
        <nav aria-label="Main" className="hidden items-center gap-1 text-sm font-medium text-slate-700 sm:flex">
          {navItems.map((item) => (
            <NavLink
              key={item.href}
              href={item.href}
              label={item.label}
              className="rounded-lg px-3 py-2 transition hover:bg-slate-100 hover:text-ink"
              activeClassName="bg-slate-100 font-semibold text-ink"
            />
          ))}
        </nav>
        <HeaderSearch />
      </div>
      {/* Mobile nav: horizontal scroll strip under the wordmark. */}
      <nav
        aria-label="Main mobile"
        className="flex gap-1 overflow-x-auto border-t border-border px-4 py-2 text-sm font-medium text-slate-700 sm:hidden"
      >
        {[{ href: "/", label: "Home" }, ...navItems].map((item) => (
          <NavLink
            key={item.href}
            href={item.href}
            label={item.label}
            className="shrink-0 rounded-lg px-3 py-1.5 transition hover:bg-slate-100"
            activeClassName="bg-slate-100 font-semibold text-ink"
          />
        ))}
      </nav>
    </header>
  );
}
