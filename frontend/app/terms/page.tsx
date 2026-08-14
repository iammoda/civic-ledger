import type { Metadata } from "next";
import Link from "next/link";

import { PageShell } from "@/components/page-shell";

export const metadata: Metadata = {
  title: "Terms of use",
  description:
    "The plain-language terms for using Civic Ledger: free for everyone, cite your sources, don't hammer the API, and here's how disputes and corrections work."
};

const SECTIONS: Array<{ title: string; body: React.ReactNode }> = [
  {
    title: "What this site is",
    body: (
      <>
        Civic Ledger is a free, non-partisan, open-source reference for Canadian civic records: bills, votes,
        expenses, lobbying, and donations, compiled from official government sources. It is run independently —
        it is not a government website and has no affiliation with any party or campaign.
      </>
    )
  },
  {
    title: "Accuracy, and its limits",
    body: (
      <>
        We work hard to reproduce official records faithfully and cite every claim to its primary source. But
        records upstream change, ingestion can lag, and software has bugs. The information here is provided
        &ldquo;as is,&rdquo; without warranty of any kind. It is not legal, financial, or professional advice.
        For authoritative versions, follow the source links on each page to the official record. When we learn
        of an error we fix it and note the change — see{" "}
        <Link href="/corrections" className="text-accent hover:underline">corrections</Link>.
      </>
    )
  },
  {
    title: "Facts, not verdicts",
    body: (
      <>
        Pages on this site describe documented actions of public officials: how they voted, what they billed,
        who registered to lobby them. Pattern flags (for example, lobbying activity shortly before a bill died)
        are published only after human review, describe correlations in the public record, and are not
        allegations of wrongdoing. Context and caveats are printed beside the numbers. If you are the subject
        of a page and believe something is wrong or missing context, the{" "}
        <Link href="/corrections" className="text-accent hover:underline">dispute process</Link> reaches a human
        and resolutions are published.
      </>
    )
  },
  {
    title: "AI-generated content",
    body: (
      <>
        Plain-language summaries and answers labeled as AI-generated are produced from cited primary sources,
        pass a readability check, and are never used to make accusations. They can still be imperfect — the
        cited record, linked beside every summary, is the authority.
      </>
    )
  },
  {
    title: "Using the data",
    body: (
      <>
        The underlying government records are public information. Our compilation and code are open source under{" "}
        <a
          href="https://www.gnu.org/licenses/agpl-3.0.en.html"
          className="text-accent hover:underline"
        >
          AGPL-3.0
        </a>
        . Cite the primary sources (linked on every page) for anything that matters; attribution of Civic Ledger
        is appreciated but the official record is the authority.
      </>
    )
  },
  {
    title: "Fair use of the service",
    body: (
      <>
        The site is free and anonymous. In return: don&rsquo;t hammer the API (rate limits apply, especially on
        AI-backed features, so they stay available for everyone), don&rsquo;t submit spam through the forms, and
        don&rsquo;t misrepresent this site&rsquo;s content as a government publication or as endorsements.
      </>
    )
  },
  {
    title: "Changes",
    body: (
      <>
        These terms may be updated as the platform evolves; material changes are noted in the public changelog
        of the open-source repository. Continued use after a change means acceptance of the updated terms.
      </>
    )
  }
];

export default function TermsPage() {
  return (
    <PageShell
      eyebrow="Terms"
      title="Terms of use, in plain language"
      description="Free for everyone, sourced from official records, corrected in public. Here's the deal in seven short sections."
    >
      <div className="space-y-4">
        {SECTIONS.map((section) => (
          <section key={section.title} className="glass-card rounded-[2rem] p-6">
            <h2 className="text-lg font-bold">{section.title}</h2>
            <p className="mt-2 text-sm leading-7 text-slate-600">{section.body}</p>
          </section>
        ))}
      </div>
      <p className="mt-8 text-sm text-slate-500">
        See also:{" "}
        <Link href="/privacy" className="text-accent hover:underline">
          privacy
        </Link>
        ,{" "}
        <Link href="/charter" className="text-accent hover:underline">
          our charter
        </Link>
        , and{" "}
        <Link href="/methodology" className="text-accent hover:underline">
          methodology
        </Link>
        . Last updated: August 2026.
      </p>
    </PageShell>
  );
}
