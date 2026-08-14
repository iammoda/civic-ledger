import type { Metadata } from "next";
import Link from "next/link";

import { PageShell } from "@/components/page-shell";

const DETECTORS = [
  {
    name: "Lobbying contact cluster",
    what: "An MP was named in an unusual burst of lobbying communication reports — at least 6 contacts in 30 days, and at least 3× their own monthly baseline.",
    source: "Registry of Lobbyists communication reports."
  },
  {
    name: "Donor / lobbyist-client overlap",
    what: "The same name (normalized) appears both as a campaign contributor to an MP and as a lobbying client or registrant on communications naming that MP. Name matching can produce false positives for common names, which is one reason every flag is human-reviewed.",
    source: "Elections Canada financial returns + Registry of Lobbyists."
  },
  {
    name: "Lobbying before a bill died",
    what: "A bill died quietly (in committee, on the Order Paper, or withdrawn) and at least 3 lobbying communications on overlapping subject matter were filed in the 60 days before it died. Timing correlation is not causation — the flag marks the pattern, nothing more.",
    source: "Registry of Lobbyists + LEGISinfo bill statuses."
  }
];

export const metadata: Metadata = {
  title: "Methodology",
  description:
    "How the platform stays neutral: identical detectors and prompts for every party, human review before publishing, citations to primary sources."
};

export default function MethodologyPage() {
  return (
    <PageShell
      eyebrow="Methodology"
      title="How we flag patterns — and what a flag does not mean"
      description="Every number on this site traces to an official government record. Here is exactly how the automated checks work."
    >
      <div className="space-y-6">
        <div className="glass-card rounded-[2rem] p-8">
          <h2 className="text-xl font-semibold">The rules we hold ourselves to</h2>
          <ul className="mt-4 space-y-3 text-sm leading-7 text-slate-700">
            <li>
              <span className="font-medium">Human review before publishing.</span> Detectors only create
              drafts. A human reviews every flag against the underlying records before it can appear publicly.
              Dismissed flags never appear.
            </li>
            <li>
              <span className="font-medium">Symmetric by architecture.</span> The identical detectors, thresholds,
              and wording templates run on every member of every party. There is no party-specific logic anywhere
              in the codebase — which is open source and can be checked.
            </li>
            <li>
              <span className="font-medium">Facts, not conclusions.</span> A flag describes verifiable records
              (&quot;14 lobbying contacts in 30 days&quot;), never characterizations (&quot;corrupt&quot;,
              &quot;bought&quot;). Whether a
              pattern matters is your judgment to make, with the evidence in front of you.
            </li>
            <li>
              <span className="font-medium">Primary sources only.</span> Parliament, LEGISinfo, the Registry of
              Lobbyists, Elections Canada, and the House of Commons petitions system. No media reports, no
              advocacy organizations.
            </li>
            <li>
              <span className="font-medium">Missing data is shown as missing.</span> When a record isn&apos;t
              available, you see a &quot;Data Gap&quot; — never a silently filled blank.
            </li>
          </ul>
        </div>

        <div className="glass-card rounded-[2rem] p-8">
          <h2 className="text-xl font-semibold">The detectors</h2>
          <div className="mt-4 space-y-4">
            {DETECTORS.map((detector) => (
              <div key={detector.name} className="rounded-3xl border border-black/10 bg-white p-5">
                <h3 className="font-medium">{detector.name}</h3>
                <p className="mt-2 text-sm leading-6 text-slate-700">{detector.what}</p>
                <p className="mt-2 text-xs text-slate-500">Source: {detector.source}</p>
              </div>
            ))}
          </div>
        </div>

        <div className="glass-card rounded-[2rem] p-8">
          <h2 className="text-xl font-semibold">AI-generated text</h2>
          <p className="mt-3 text-sm leading-7 text-slate-700">
            Plain-language summaries are AI-generated from official records, held to a grade-8 readability
            standard, and always cite their sources. Summaries that fail quality checks are blocked, not
            published. Vote directions (&quot;voted to advance / block&quot;) are resolved by deterministic
            rules where possible; only ambiguous procedural motions use AI, and the raw motion text is always
            one click away.
          </p>
        </div>

        <div className="glass-card rounded-[2rem] p-8">
          <h2 className="text-xl font-semibold">Spotted an error?</h2>
          <p className="mt-3 text-sm leading-7 text-slate-700">
            Corrections make this platform better and are handled through a public queue.{" "}
            <Link href="/corrections" className="text-accent">
              Submit a correction or dispute →
            </Link>
          </p>
        </div>
      </div>
    </PageShell>
  );
}
