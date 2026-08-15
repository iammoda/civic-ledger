import type { Metadata } from "next";
import Link from "next/link";

import { PageShell } from "@/components/page-shell";

const sections = [
  {
    title: "Sources",
    body: "Everything traces to official records: OpenParliament, OurCommons, and LEGISinfo for bills and votes; the Registry of Lobbyists for lobbying; Elections Canada for donations; the House of Commons petitions system for e-petitions; ola.org for Ontario bills and division votes; official eScribe council minutes for municipal attendance, motions, and votes; Toronto and Vancouver open data for full council voting records. No media reports, no advocacy organizations."
  },
  {
    title: "Municipal minutes parsing",
    body: "For cities without open-data voting records, attendance, motions (with movers and seconders), per-member votes where printed, and conflict-of-interest declarations are parsed from the official published minutes. Every parsed row links back to the exact minutes page it came from. Names are matched automatically (honorifics, initials, wards normalized); unmatched names are logged and re-checked, never guessed. The live pipeline status and per-city coverage are public on the transparency page."
  },
  {
    title: "Procedural context",
    body: "Votes are classified as whipped, free, confidence, or voice votes because raw Canadian parliamentary vote totals are misleading without that frame. On top of that, every vote's direction is normalized — 'voted to advance' or 'voted to block' — because procedural motions routinely invert what Yes and No mean."
  },
  {
    title: "AI analysis",
    body: "Plain-language summaries are AI-generated from official records, enforced to a grade-8 reading level, and always cite sources. Outputs that fail quality checks are blocked, not published. Direction calls use deterministic rules first; AI handles only the ambiguous remainder."
  },
  {
    title: "Data gaps",
    body: "Missing ballots, incomplete committee records, and absent analysis are surfaced as first-class states throughout the app — never silently papered over."
  },
  {
    title: "Integrity flags",
    body: "Pattern detectors (lobbying bursts, donor/lobbyist overlaps, lobbying before a bill died) create drafts that a human reviews against the underlying records before anything publishes. Full thresholds are public on the methodology page."
  },
  {
    title: "Promise tracking",
    body: "We don't judge campaign promises ourselves. For kept/broken promise tracking, we point to Polimètre (Université Laval), an academic project that does this rigorously."
  }
];

export const metadata: Metadata = {
  title: "About the data",
  description:
    "Where every number comes from: primary sources only — Parliament, Elections Canada and official registries — with update schedules and known gaps."
};

export default function AboutDataPage() {
  return (
    <PageShell
      eyebrow="Methodology"
      title="About the data"
      description="This page makes source strategy, procedural assumptions, and known gaps explicit."
    >
      <div className="grid gap-6 md:grid-cols-2">
        {sections.map((section) => (
          <section key={section.title} className="rule-heavy pt-5">
            <h2 className="text-2xl font-semibold">{section.title}</h2>
            <p className="mt-4 text-sm leading-7 text-stone-600">{section.body}</p>
          </section>
        ))}
      </div>

      <div className="rule-heavy mt-8 pt-5">
        <h2 className="text-xl font-semibold">Deeper reading</h2>
        <ul className="mt-4 space-y-2 text-sm text-stone-700">
          <li>
            <Link href="/methodology" className="text-accent">
              Our detector thresholds and review rules →
            </Link>
          </li>
          <li>
            <a href="https://www.polimetre.org" target="_blank" rel="noreferrer" className="text-accent">
              Polimètre — academic promise tracking (Université Laval) ↗
            </a>
          </li>
          <li>
            <a href="https://openparliament.ca" target="_blank" rel="noreferrer" className="text-accent">
              OpenParliament — the volunteer project our House data builds on ↗
            </a>
          </li>
          <li>
            <Link href="/corrections" className="text-accent">
              Report an error →
            </Link>
          </li>
        </ul>
      </div>
    </PageShell>
  );
}
