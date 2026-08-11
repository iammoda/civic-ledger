import Link from "next/link";
import { notFound } from "next/navigation";

import { DataGap } from "@/components/data-gap";
import { DeathBanner, outcomeBadge } from "@/components/death-banner";
import { PageShell } from "@/components/page-shell";
import { PlainSummaryCard } from "@/components/plain-summary-card";
import { SectorImpactList } from "@/components/sector-impact-list";
import { getBill } from "@/lib/api";

export default async function BillDetailPage({
  params
}: {
  params: Promise<{ session: string; number: string }>;
}) {
  const { session, number } = await params;
  const bill = await getBill(session, number);

  if (!bill) {
    notFound();
  }

  const plainSummary = bill.analyses.find(
    (analysis) => analysis.analysis_type === "plain_summary" && analysis.status === "published"
  );
  const pendingGap = bill.data_gaps.find((gap) => gap.code === "analysis_pending");
  const badge = outcomeBadge(bill.outcome, bill.is_law);

  return (
    <PageShell
      eyebrow={`${bill.chamber.toUpperCase()} · ${bill.session}`}
      title={`${bill.number} · ${bill.short_title_en ?? bill.title_en}`}
      description={bill.status_en ?? "Status pending"}
    >
      <div className="mb-6 flex flex-wrap items-center gap-3">
        <span className={`rounded-full px-4 py-2 text-sm font-medium ${badge.className}`}>{badge.label}</span>
        {bill.topics.map((topic) => (
          <span key={topic} className="rounded-full border border-black/10 bg-white px-3 py-1.5 text-xs text-slate-600">
            {topic}
          </span>
        ))}
      </div>

      {bill.death ? (
        <div className="mb-6">
          <DeathBanner death={bill.death} />
        </div>
      ) : null}

      <div className="mb-6 flex flex-wrap gap-3">
        <Link
          href={`/act?bill=${encodeURIComponent(`${bill.session}/${bill.number}`)}`}
          className="rounded-full bg-slate-900 px-6 py-3 text-sm font-medium text-white"
        >
          Contact your MP about this
        </Link>
        <Link href="/petitions" className="rounded-full border border-black/10 px-6 py-3 text-sm font-medium">
          Find a related petition
        </Link>
      </div>

      <section className="grid gap-6 lg:grid-cols-[1.1fr_0.9fr]">
        <div className="glass-card rounded-[2rem] p-6">
          <h2 className="text-xl font-semibold">In plain language</h2>
          <div className="mt-4 space-y-4">
            {plainSummary ? (
              <PlainSummaryCard analysis={plainSummary} />
            ) : (
              <DataGap
                title={pendingGap?.label ?? "Analysis pending"}
                detail={
                  pendingGap?.detail ??
                  "The plain-language summary for this bill has not been generated yet."
                }
              />
            )}
          </div>
        </div>

        <div className="space-y-6">
          <div className="glass-card rounded-[2rem] p-6">
            <h2 className="text-xl font-semibold">Sector impacts</h2>
            <div className="mt-4">
              <SectorImpactList impacts={bill.sector_impacts as Array<{ sector?: string; direction?: string; description?: string }>} />
            </div>
          </div>
          <div className="glass-card rounded-[2rem] p-6">
            <h2 className="text-xl font-semibold">Recorded votes</h2>
            <div className="mt-4 space-y-3">
              {bill.related_votes.length ? (
                bill.related_votes.map((vote) => (
                  <Link
                    key={`${vote.session}-${vote.number}`}
                    href={`/votes/${vote.chamber}/${vote.session}/${vote.number}`}
                    className="block rounded-3xl border border-black/10 bg-white p-4"
                  >
                    <p className="font-medium">{vote.description_en}</p>
                    <p className="mt-1 text-sm text-slate-500">
                      {vote.occurred_on} · {vote.result ?? "Pending"} · {vote.vote_type}
                    </p>
                  </Link>
                ))
              ) : (
                <DataGap
                  title="No recorded votes"
                  detail="Bills often appear before any chamber vote is recorded, and some procedural data may still be ingesting."
                />
              )}
            </div>
          </div>
          <div className="glass-card rounded-[2rem] p-6">
            <h2 className="text-xl font-semibold">Source records</h2>
            {bill.legisinfo_url ? (
              <a href={bill.legisinfo_url} target="_blank" rel="noreferrer" className="mt-4 inline-block text-sm text-accent">
                Open LEGISinfo
              </a>
            ) : (
              <p className="mt-4 text-sm text-slate-600">LEGISinfo link not attached yet.</p>
            )}
          </div>
        </div>
      </section>
    </PageShell>
  );
}
