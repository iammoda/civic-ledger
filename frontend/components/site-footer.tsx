import Link from "next/link";

const COLUMNS = [
  {
    title: "Explore",
    links: [
      { href: "/bills", label: "Bills" },
      { href: "/votes", label: "Votes" },
      { href: "/graveyard", label: "The Graveyard" },
      { href: "/politicians", label: "MPs" },
      { href: "/expenses", label: "Follow the money" },
      { href: "/receipts", label: "The Receipts" },
      { href: "/petitions", label: "Petitions" }
    ]
  },
  {
    title: "Understand",
    links: [
      { href: "/glossary", label: "Glossary — Parliament in plain words" },
      { href: "/methodology", label: "How we flag patterns" },
      { href: "/about-data", label: "About the data" },
      { href: "/transparency", label: "Transparency — live pipeline & coverage" }
    ]
  },
  {
    title: "Participate",
    links: [
      { href: "/ask", label: "Ask a question" },
      { href: "/act", label: "Write to your MP" },
      { href: "/charter", label: "What we are (and aren't)" },
      { href: "/corrections", label: "Report an error" }
    ]
  }
];

export function SiteFooter() {
  return (
    <footer className="mt-16 border-t border-border bg-white">
      <div className="mx-auto max-w-6xl px-4 py-10 sm:px-6">
        <div className="grid gap-8 sm:grid-cols-3">
          {COLUMNS.map((column) => (
            <div key={column.title}>
              <h2 className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                {column.title}
              </h2>
              <ul className="mt-3 space-y-2">
                {column.links.map((link) => (
                  <li key={link.href}>
                    <Link href={link.href} className="text-sm text-slate-700 hover:text-accent hover:underline">
                      {link.label}
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
        <p className="mt-8 border-t border-border pt-6 text-xs leading-5 text-slate-500">
          <span className="font-semibold text-slate-700">This is not a government website.</span> Civic Ledger is
          non-partisan and open source. Every number traces to an official government record: Parliament,
          Elections Canada, the Registry of Lobbyists, the House of Commons, provincial legislatures, and
          the Represent civic dataset. Federal coverage is deepest; provincial and municipal records grow
          as their governments publish more.{" "}
          <Link href="/charter" className="text-accent hover:underline">
            Read our charter →
          </Link>
        </p>
      </div>
    </footer>
  );
}
