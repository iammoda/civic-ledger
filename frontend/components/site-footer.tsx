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
 * Dark ink bookend: the one full-color surface every page shares. Opens with
 * the designed ending — the accountability loop closes with an action —
 * then the big serif wordmark and quiet link columns.
 */
export function SiteFooter() {
  return (
    <footer className="mt-20 bg-ink text-stone-300">
      {/* The ending every page earns: from reading the record to acting on it. */}
      <div className="border-b border-white/10">
        <div className="mx-auto flex max-w-[1600px] flex-wrap items-center justify-between gap-x-10 gap-y-6 px-5 py-12 sm:px-10">
          <div>
            <p className="kicker text-brass-bright">The record is public. So is your voice.</p>
            <p className="mt-2 max-w-xl font-serif text-2xl font-bold leading-snug tracking-tight text-white sm:text-3xl">
              See something worth acting on?
            </p>
          </div>
          <div className="flex flex-wrap gap-3">
            <Link
              href="/act"
              className="rounded-full bg-brass-bright px-6 py-3 text-sm font-bold text-ink transition hover:bg-amber-300"
            >
              Write to your MP →
            </Link>
            <Link
              href="/ask"
              className="rounded-full border border-white/25 px-6 py-3 text-sm font-semibold text-white transition hover:border-brass-bright hover:text-brass-bright"
            >
              Ask a question
            </Link>
          </div>
        </div>
      </div>

      <div className="mx-auto max-w-[1600px] px-5 sm:px-10 py-14">
        <p className="font-serif text-3xl font-bold tracking-tight text-white sm:text-4xl">
          Civic Ledger<span className="text-brass-bright">.</span>
        </p>
        <p className="mt-2 max-w-xl text-sm leading-6 text-stone-400">
          Who represents you — and what have they actually done? Every claim cites the official record.
        </p>
        <div className="mt-10 grid gap-8 border-t border-white/10 pt-8 sm:grid-cols-3">
          {COLUMNS.map((column) => (
            <div key={column.title}>
              <h2 className="text-xs font-semibold uppercase tracking-[0.1em] text-stone-500">
                {column.title}
              </h2>
              <ul className="mt-3 space-y-2">
                {column.links.map((link) => (
                  <li key={link.href}>
                    <Link href={link.href} className="text-sm text-stone-300 transition hover:text-white hover:underline">
                      {link.label}
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
        <p className="mt-10 border-t border-white/10 pt-6 text-xs leading-5 text-stone-500">
          <span className="font-semibold text-stone-300">This is not a government website.</span> Civic Ledger is
          non-partisan and open source. Every number traces to an official government record: Parliament,
          Elections Canada, the Registry of Lobbyists, the House of Commons, provincial legislatures, and
          the Represent civic dataset. Federal coverage is deepest; provincial and municipal records grow
          as their governments publish more.{" "}
          <Link href="/charter" className="text-brass-bright hover:underline">
            Read our charter →
          </Link>
        </p>
      </div>
    </footer>
  );
}
