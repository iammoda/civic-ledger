import Link from "next/link";

import { PageShell } from "@/components/page-shell";

export const metadata = { title: "Our charter — what Civic Ledger is (and isn't)" };

const COMMITMENTS: Array<{ title: string; body: string }> = [
  {
    title: "This is not a government website",
    body: "Civic Ledger is independent. We have no affiliation with any government, party, or campaign — and no funding from any of them. Not even sort of."
  },
  {
    title: "We don't take sides",
    body: "Every ranking, chart, and story card is a straight computation over official records — the same math for every party and every MP. Nobody hand-picks who appears where. When we say someone billed $83,000, that's a fact with a receipt, not a verdict."
  },
  {
    title: "Every claim has a source",
    body: "Votes come from the parliamentary record, lobbying from the Registry of Lobbyists, donations from Elections Canada, spending from the House's own disclosures. Every number links back to the official record so you can check us."
  },
  {
    title: "Numbers ship with their caveats",
    body: "Raw numbers mislead: the Speaker can't vote, northern ridings legitimately cost more, ministers get lobbied because of their jobs. Wherever a number could smear someone unfairly, the caveat is printed right next to it — not buried in a methodology page."
  },
  {
    title: "AI content is labeled, gated, and checkable",
    body: "AI writes plain-language summaries and one-line descriptions — always labeled, always readability-checked, never used for accusations. When the AI doesn't know, we show a gap instead of a guess. Patterns worth flagging go through human review before they're published."
  },
  {
    title: "We store nothing about you",
    body: "No accounts, no tracking of who you are. Your postal code is used for the lookup and discarded; 'my MP' lives in your browser, not on our servers."
  },
  {
    title: "We correct mistakes fast",
    body: "Every page has a path to report an error. Corrections go to a triage queue and fixes note what changed."
  }
];

export default function CharterPage() {
  return (
    <PageShell
      eyebrow="Trust, in writing"
      title="What we are — and what we aren't"
      description="The rules this site holds itself to. If you ever catch us breaking one, call it out."
    >
      <div className="space-y-4">
        {COMMITMENTS.map((item, index) => (
          <section key={item.title} className="rule-heavy pt-5">
            <h2 className="text-lg font-bold">
              <span className="mr-2 text-stone-300">{index + 1}.</span>
              {item.title}
            </h2>
            <p className="mt-2 text-sm leading-7 text-stone-600">{item.body}</p>
          </section>
        ))}
      </div>

      <div className="mt-8 flex flex-wrap gap-3 text-sm">
        <Link href="/methodology" className="rounded-full border border-black/10 bg-white px-5 py-2.5 font-medium text-stone-700 transition hover:border-accent hover:text-accent">
          How we flag patterns →
        </Link>
        <Link href="/about-data" className="rounded-full border border-black/10 bg-white px-5 py-2.5 font-medium text-stone-700 transition hover:border-accent hover:text-accent">
          Where the data comes from →
        </Link>
        <Link href="/corrections" className="rounded-full border border-black/10 bg-white px-5 py-2.5 font-medium text-stone-700 transition hover:border-accent hover:text-accent">
          Report an error →
        </Link>
      </div>
    </PageShell>
  );
}
