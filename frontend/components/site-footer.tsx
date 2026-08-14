import Link from "next/link";

const COLUMNS = [
  {
    title: "Explore",
    links: [
      { href: "/politicians", label: "Your representatives" },
      { href: "/votes", label: "Votes" },
      { href: "/bills", label: "Bills" },
      { href: "/graveyard", label: "The Graveyard" },
      { href: "/issues", label: "Issues" },
      { href: "/money", label: "Money" },
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
      { href: "/corrections", label: "Report an error" },
      { href: "/privacy", label: "Privacy" },
      { href: "/terms", label: "Terms of use" }
    ]
  }
];

/**
 * Dark ink bookend: the one full-color surface on the site. Big serif
 * wordmark, quiet link columns, and the non-government disclaimer.
 */
export function SiteFooter() {
  return (
    <footer className="mt-20 bg-ink text-slate-300">
      <div className="mx-auto max-w-6xl px-4 py-14 sm:px-6">
        <p className="font-serif text-3xl font-bold tracking-tight text-white sm:text-4xl">
          Civic Ledger<span className="text-teal-400">.</span>
        </p>
        <p className="mt-2 max-w-xl text-sm leading-6 text-slate-400">
          Who represents you — and what have they actually done? Every claim cites the official record.
        </p>
        <div className="mt-10 grid gap-8 border-t border-white/10 pt-8 sm:grid-cols-3">
          {COLUMNS.map((column) => (
            <div key={column.title}>
              <h2 className="text-xs font-semibold uppercase tracking-[0.1em] text-slate-500">
                {column.title}
              </h2>
              <ul className="mt-3 space-y-2">
                {column.links.map((link) => (
                  <li key={link.href}>
                    <Link href={link.href} className="text-sm text-slate-300 transition hover:text-white hover:underline">
                      {link.label}
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
        <p className="mt-10 border-t border-white/10 pt-6 text-xs leading-5 text-slate-500">
          <span className="font-semibold text-slate-300">This is not a government website.</span> Civic Ledger is
          non-partisan and open source. Every number traces to an official government record: Parliament,
          Elections Canada, the Registry of Lobbyists, the House of Commons, provincial legislatures, and
          the Represent civic dataset. Federal coverage is deepest; provincial and municipal records grow
          as their governments publish more.{" "}
          <Link href="/charter" className="text-teal-400 hover:underline">
            Read our charter →
          </Link>
        </p>
      </div>
    </footer>
  );
}
