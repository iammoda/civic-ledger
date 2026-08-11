import Link from "next/link";

import { DataGap } from "@/components/data-gap";
import { PageShell } from "@/components/page-shell";
import { listVotes } from "@/lib/api";

const EFFECT_CHIPS: Record<string, { label: string; className: string }> = {
  advance: { label: "Yes = advance", className: "bg-emerald-50 text-emerald-700" },
  block: { label: "Yes = block", className: "bg-rose-50 text-rose-700" },
  other: { label: "Procedural", className: "bg-slate-100 text-slate-600" }
};

export default async function VotesPage() {
  const votes = await listVotes();

  return (
    <PageShell
      eyebrow="Votes"
      title="Every vote, translated"
      description="Procedural motions routinely invert what Yes and No mean. We say what each vote actually decided — the raw motion text is always one click away."
    >
      {!votes?.items.length ? (
        <DataGap
          title="No votes loaded"
          detail="The vote feed will populate after the first structured ingestion run finishes."
        />
      ) : (
        <div className="space-y-4">
          {votes.items.map((vote) => {
            const chip = vote.yea_effect ? EFFECT_CHIPS[vote.yea_effect] : null;
            return (
              <Link
                key={`${vote.session}-${vote.number}`}
                href={`/votes/${vote.chamber}/${vote.session}/${vote.number}`}
                className="glass-card block rounded-[2rem] p-6 transition hover:-translate-y-0.5"
              >
                <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <p className="text-sm uppercase tracking-[0.18em] text-slate-500">
                        {vote.chamber} · {vote.session} · Vote {vote.number}
                      </p>
                      {chip ? (
                        <span className={`rounded-full px-3 py-1 text-xs font-medium ${chip.className}`}>
                          {chip.label}
                        </span>
                      ) : null}
                    </div>
                    <h2 className="mt-2 text-xl font-semibold leading-8">
                      {vote.plain_meaning_en ?? vote.description_en}
                    </h2>
                    {vote.plain_meaning_en ? (
                      <p className="mt-1 truncate text-sm text-slate-400">{vote.description_en}</p>
                    ) : null}
                  </div>
                  <div className="shrink-0 rounded-2xl bg-white px-4 py-3 text-sm text-slate-600">
                    <p className="font-medium">{vote.result ?? "Result pending"}</p>
                    <p className="mt-1">
                      {vote.yea_total} yes / {vote.nay_total} no
                    </p>
                    <p className="mt-1 text-xs uppercase tracking-[0.18em] text-slate-400">{vote.vote_type}</p>
                  </div>
                </div>
              </Link>
            );
          })}
        </div>
      )}
    </PageShell>
  );
}
