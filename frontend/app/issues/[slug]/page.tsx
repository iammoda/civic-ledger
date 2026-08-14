import Link from "next/link";
import { notFound } from "next/navigation";

import { DataGap } from "@/components/data-gap";
import { outcomeBadge } from "@/components/death-banner";
import { PageShell } from "@/components/page-shell";
import { PartyLogo } from "@/components/party-logo";
import { getIssue } from "@/lib/api";
import { humanizeBillTitle, humanizeStatus } from "@/lib/humanize";
import { partyInfo } from "@/lib/parties";

export async function generateMetadata({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const issue = await getIssue(slug);
  return { title: issue ? `${issue.name_en} — how they voted` : "Issue" };
}

export default async function IssueDetailPage({
  params
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  const issue = await getIssue(slug);

  if (!issue) {
    notFound();
  }

  return (
    <PageShell
      eyebrow="Issue"
      title={issue.name_en}
      description={
        issue.description_en ??
        "Every bill Parliament tagged to this issue — what happened to each one, and how the parties voted."
      }
    >
      <div className="space-y-8">
        {/* Panel 1: party positions from recorded ballots. */}
        <section>
          <h2 className="kicker">Where the parties stood</h2>
          {!issue.party_positions.length ? (
            <div className="mt-3">
              <DataGap
                title="No recorded votes yet"
                detail="None of the bills on this issue have reached a recorded vote — there's nothing to count yet. Watch this space."
              />
            </div>
          ) : (
            <>
              <div className="mt-3 divide-y divide-border rounded-md border border-border bg-white">
                {issue.party_positions.map((position) => {
                  const info = partyInfo(position.party_slug);
                  const total = position.yea + position.nay;
                  const yeaPct = total > 0 ? (position.yea / total) * 100 : 0;
                  return (
                    <div key={position.party_slug} className="flex items-center gap-3 px-4 py-3">
                      <PartyLogo party={position.party_slug} size={20} />
                      <span className="w-32 shrink-0 truncate text-sm font-medium">
                        {position.party_name ?? info.label}
                      </span>
                      <div className="flex h-2.5 min-w-0 flex-1 overflow-hidden rounded-sm bg-slate-100">
                        <div className="bg-teal-600" style={{ width: `${yeaPct}%` }} />
                        <div className="bg-rose-600" style={{ width: `${100 - yeaPct}%` }} />
                      </div>
                      <span className="w-32 shrink-0 text-right text-sm tabular-nums text-slate-700">
                        {position.yea} Yes · {position.nay} No
                      </span>
                    </div>
                  );
                })}
              </div>
              <p className="mt-2 text-xs leading-5 text-slate-500">
                {issue.positions_note} {issue.vote_count} recorded votes counted.
              </p>
            </>
          )}
        </section>

        {/* Panel 2: the bills themselves — the receipts. */}
        <section>
          <h2 className="kicker">Every bill on this issue</h2>
          {!issue.bills.length ? (
            <div className="mt-3">
              <DataGap
                title="No bills tagged yet"
                detail="No bill in our record has been linked to this issue so far. Tagging runs as new bills land — check back."
              />
            </div>
          ) : (
            <div className="mt-3 divide-y divide-border rounded-md border border-border bg-white">
              {issue.bills.map((bill) => {
                const badge = outcomeBadge(bill.outcome, bill.is_law);
                const title = humanizeBillTitle(bill.title_en, bill.short_title_en);
                const status = humanizeStatus(bill.status_en);
                return (
                  <Link
                    key={`${bill.session}-${bill.number}`}
                    href={`/bills/${bill.session}/${bill.number}`}
                    className="block px-4 py-3 transition hover:bg-slate-50"
                  >
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="rounded-md bg-slate-100 px-2 py-0.5 text-xs font-semibold text-slate-600">
                        {bill.number}
                      </span>
                      <span className={`rounded-md px-2 py-0.5 text-xs font-semibold ${badge.className}`}>
                        {badge.label}
                      </span>
                      <span className="text-xs text-slate-500" title={status.raw}>
                        {status.label}
                      </span>
                    </div>
                    <p className="mt-1.5 text-sm font-semibold leading-6">{title.headline}</p>
                    {bill.one_sentence ? (
                      <p className="mt-0.5 text-sm leading-6 text-slate-600">{bill.one_sentence}</p>
                    ) : null}
                  </Link>
                );
              })}
            </div>
          )}
        </section>
      </div>
    </PageShell>
  );
}
