import Link from "next/link";

import { DataGap } from "@/components/data-gap";
import { PageShell } from "@/components/page-shell";
import { listVotes } from "@/lib/api";

export default async function VotesPage() {
  const votes = await listVotes();

  return (
    <PageShell
      eyebrow="Votes"
      title="Recorded votes with procedural context"
      description="Every vote is framed around parliamentary procedure so raw party-line tallies are not mistaken for full accountability."
    >
      {!votes?.items.length ? (
        <DataGap
          title="No votes loaded"
          detail="The vote feed will populate after the first structured ingestion run finishes."
        />
      ) : (
        <div className="space-y-4">
          {votes.items.map((vote) => (
            <Link
              key={`${vote.session}-${vote.number}`}
              href={`/votes/${vote.chamber}/${vote.session}/${vote.number}`}
              className="glass-card block rounded-[2rem] p-6"
            >
              <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
                <div>
                  <p className="text-sm uppercase tracking-[0.18em] text-slate-500">
                    {vote.chamber} · {vote.session} · Vote {vote.number}
                  </p>
                  <h2 className="mt-2 text-xl font-semibold">{vote.description_en}</h2>
                </div>
                <div className="rounded-2xl bg-white px-4 py-3 text-sm text-slate-600">
                  <p>{vote.result ?? "Result pending"}</p>
                  <p className="mt-1">{vote.yea_total} yea / {vote.nay_total} nay</p>
                  <p className="mt-1 uppercase tracking-[0.18em]">{vote.vote_type}</p>
                </div>
              </div>
            </Link>
          ))}
        </div>
      )}
    </PageShell>
  );
}
