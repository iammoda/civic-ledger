import Link from "next/link";

import { DataGap } from "@/components/data-gap";
import { PageShell } from "@/components/page-shell";
import { listIssues } from "@/lib/api";

export const metadata = { title: "Issues — who supports what, with receipts" };

function countsLine(bills: number, laws: number, dead: number): string {
  const parts = [`${bills} bill${bills === 1 ? "" : "s"}`];
  if (laws > 0) parts.push(`${laws} became law`);
  if (dead > 0) parts.push(`${dead} died`);
  return parts.join(" · ");
}

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
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {issues.items.map((issue) => (
            <Link
              key={issue.slug}
              href={`/issues/${issue.slug}`}
              className="rounded-md border border-border bg-white p-4 transition hover:border-accent"
            >
              <h2 className="font-serif text-lg font-bold leading-6">{issue.name_en}</h2>
              {issue.description_en ? (
                <p className="mt-1 text-sm leading-6 text-slate-600">{issue.description_en}</p>
              ) : null}
              <p className="mt-2 text-xs tabular-nums text-slate-500">
                {countsLine(issue.bill_count, issue.law_count, issue.dead_count)}
              </p>
            </Link>
          ))}
        </div>
      )}
    </PageShell>
  );
}
