import Link from "next/link";

import { AuthWidget } from "@/components/auth-widget";

const navItems = [
  { href: "/", label: "Home" },
  { href: "/ask", label: "Ask" },
  { href: "/politicians", label: "MPs" },
  { href: "/bills", label: "Bills & Votes" },
  { href: "/about-data", label: "About the Data" }
];

export function SiteHeader() {
  return (
    <header className="sticky top-0 z-20 border-b border-black/5 bg-white/75 backdrop-blur-xl">
      <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-4">
        <Link href="/" className="text-lg font-semibold tracking-tight">
          Civic Ledger
        </Link>
        <div className="flex items-center gap-4">
          <nav className="flex flex-wrap items-center gap-2 text-sm text-slate-700">
            {navItems.map((item) => (
              <Link
                key={item.href}
                href={item.href}
                className="rounded-full px-4 py-2 transition hover:bg-slate-900 hover:text-white"
              >
                {item.label}
              </Link>
            ))}
          </nav>
          <AuthWidget />
        </div>
      </div>
    </header>
  );
}
