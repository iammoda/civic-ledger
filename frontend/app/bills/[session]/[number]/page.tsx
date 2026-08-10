import Link from "next/link";
import { notFound } from "next/navigation";

import { DataGap } from "@/components/data-gap";
import { EvidenceBadge } from "@/components/evidence-badge";
import { PageShell } from "@/components/page-shell";
import { SectorImpactList } from "@/components/sector-impact-list";
import { getBill } from "@/lib/api";

function formatAnalysisTitle(key: string) {
  return key
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

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

  return (
    <PageShell
      eyebrow={`${bill.chamber.toUpperCase()} · ${bill.session}`}
      title={`${bill.number} · ${bill.title_en}`}
      description={bill.status_en ?? "Status pending"}
    >
      <section className="grid gap-6 lg:grid-cols-[1.1fr_0.9fr]">
        <div className="glass-card rounded-[2rem] p-6">
          <h2 className="text-xl font-semibold">Plain-language analysis</h2>
          <div className="mt-4 space-y-4">
            {bill.analyses.length ? (
              bill.analyses.map((analysis) => (
                <div key={analysis.analysis_type} className="rounded-3xl border border-black/10 bg-white p-5">
                  <div className="flex flex-wrap items-center gap-3">
                    <h3 className="text-lg font-medium">{formatAnalysisTitle(analysis.analysis_type)}</h3>
                    <span className="rounded-full bg-slate-100 px-3 py-1 text-xs uppercase tracking-[0.16em] text-slate-600">
                      {analysis.status}
                    </span>
                    {typeof analysis.payload?.evidence_quality === "string" ? (
                      <EvidenceBadge value={analysis.payload.evidence_quality} />
                    ) : null}
                  </div>
                  <pre className="mt-4 overflow-x-auto whitespace-pre-wrap text-sm leading-7 text-slate-600">
                    {JSON.stringify(analysis.payload, null, 2)}
                  </pre>
                </div>
              ))
            ) : (
              <DataGap
                title="Analysis pending"
                detail="This bill is wired for summary, framing, omnibus, and sector-impact results, but none have been published yet."
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
