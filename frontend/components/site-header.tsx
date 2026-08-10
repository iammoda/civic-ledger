import Link from "next/link";

const navItems = [
  { href: "/", label: "Home" },
  { href: "/politicians", label: "Politicians" },
  { href: "/votes", label: "Votes" },
  { href: "/bills", label: "Bills" },
  { href: "/committees", label: "Committees" },
  { href: "/about-data", label: "About Data" }
];

export function SiteHeader() {
  return (
    <header className="sticky top-0 z-20 border-b border-black/5 bg-white/75 backdrop-blur-xl">
      <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-4">
        <Link href="/" className="text-lg font-semibold tracking-tight">
          Civic Ledger
        </Link>
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
      </div>
    </header>
  );
}
