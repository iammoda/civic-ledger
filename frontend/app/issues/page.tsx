import Link from "next/link";

import { DataGap } from "@/components/data-gap";
import { PageShell } from "@/components/page-shell";
import { listIssues } from "@/lib/api";

export const metadata = { title: "Issues — who supports what, with receipts" };

export default async function IssuesPage() {
  const issues = await listIssues();

  return (
    <PageShell
      eyebrow="What do you care about?"
      title="Issues"
      description="Pick what matters to you — see every bill on it, what happened, and how each party actually voted."
    >
      {!issues?.items.length ? (
        <DataGap
          title="Data temporarily unavailable"
          detail="The data service isn't responding right now — try again in a minute."
        />
      ) : (
        /* A typographic index, not a wall of boxes: the issue names ARE the page. */
        <div className="grid gap-x-14 sm:grid-cols-2 lg:grid-cols-3">
          {issues.items.map((issue) => (
            <Link key={issue.slug} href={`/issues/${issue.slug}`} className="rule group py-4">
              <h2 className="font-serif text-xl font-bold leading-snug tracking-tight text-ink transition group-hover:text-accent sm:text-2xl">
                {issue.name_en}
                <sup className="stat-figure ml-1.5 font-sans text-sm font-semibold text-stone-400">
                  {issue.bill_count}
                </sup>
              </h2>
              <p className="mt-1 text-[13px] tabular-nums text-stone-500">
                {issue.bill_count} bill{issue.bill_count === 1 ? "" : "s"}
                {issue.law_count > 0 ? (
                  <span className="text-teal-700"> · {issue.law_count} became law</span>
                ) : null}
                {issue.dead_count > 0 ? (
                  <span className="text-signal"> · {issue.dead_count} died</span>
                ) : null}
              </p>
            </Link>
          ))}
        </div>
      )}
    </PageShell>
  );
}
