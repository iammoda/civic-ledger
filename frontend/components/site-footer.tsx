import Link from "next/link";

const COLUMNS = [
  {
    title: "Explore",
    links: [
      { href: "/bills", label: "Bills" },
      { href: "/votes", label: "Votes" },
      { href: "/graveyard", label: "The Graveyard" },
      { href: "/politicians", label: "MPs" },
      { href: "/expenses", label: "MP expenses" },
      { href: "/petitions", label: "Petitions" }
    ]
  },
  {
    title: "Understand",
    links: [
      { href: "/glossary", label: "Glossary — Parliament in plain words" },
      { href: "/methodology", label: "How we flag patterns" },
      { href: "/about-data", label: "About the data" }
    ]
  },
  {
    title: "Participate",
    links: [
      { href: "/ask", label: "Ask a question" },
      { href: "/act", label: "Write to your MP" },
      { href: "/my", label: "My representatives" },
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
          Non-partisan and open source. Every number traces to an official government record: Parliament,
          Elections Canada, the Registry of Lobbyists, and the House of Commons. Federal coverage is deep;
          provincial and municipal representatives are shown with contact information.
        </p>
      </div>
    </footer>
  );
}
