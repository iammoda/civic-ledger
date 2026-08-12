import Link from "next/link";

import { DataGap } from "@/components/data-gap";
import { LevelBadge } from "@/components/level-badge";
import { PageShell } from "@/components/page-shell";
import { Pagination } from "@/components/pagination";
import { listVotes } from "@/lib/api";
import { formatDate, humanizeMotion } from "@/lib/humanize";

export const metadata = { title: "Every federal vote, translated" };

const EFFECT_CHIPS: Record<string, { label: string; className: string }> = {
  advance: { label: "Yes = move it forward", className: "bg-teal-50 text-teal-800" },
  block: { label: "Yes = block it", className: "bg-rose-50 text-rose-800" },
  other: { label: "Procedural", className: "bg-slate-100 text-slate-600" }
};

export default async function VotesPage({
  searchParams
}: {
  searchParams: Promise<{ offset?: string }>;
}) {
  const { offset } = await searchParams;
  const votes = await listVotes({ offset });

  return (
    <PageShell
      eyebrow="Federal Parliament"
      title="Every vote, translated"
      description="Procedural motions routinely invert what Yes and No mean. We say what each vote actually decided — the official motion text is always shown too."
    >
      {!votes?.items.length ? (
        <DataGap
          title={votes ? "No votes yet" : "Data temporarily unavailable"}
          detail={
            votes
              ? "Votes appear after the first data sync."
              : "The data service isn't responding right now — try again in a minute."
          }
        />
      ) : (
        <div className="space-y-3">
          {votes.items.map((vote) => {
            const chip = vote.yea_effect ? EFFECT_CHIPS[vote.yea_effect] : null;
            const motion = humanizeMotion(vote.description_en);
            return (
              <Link
                key={`${vote.chamber}-${vote.session}-${vote.number}`}
                href={`/votes/${vote.chamber}/${vote.session}/${vote.number}`}
                className="glass-card block p-5 transition hover:border-accent"
              >
                <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <LevelBadge level="federal" />
                      <span className="text-xs text-slate-500">
                        Vote {vote.number} · {formatDate(vote.occurred_on)}
                      </span>
                      {chip ? (
                        <span className={`rounded-md px-2 py-0.5 text-xs font-semibold ${chip.className}`}>
                          {chip.label}
                        </span>
                      ) : null}
                    </div>
                    <h2 className="mt-2 text-lg font-bold leading-7">
                      {vote.plain_meaning_en ?? motion.headline}
                    </h2>
                    <p className="mt-0.5 truncate text-xs text-slate-400">{vote.description_en}</p>
                  </div>
                  <div className="shrink-0 text-left sm:text-right">
                    <p
                      className={`text-base font-bold ${
                        vote.result === "Passed" ? "text-teal-700" : vote.result === "Negatived" ? "text-signal" : "text-slate-700"
                      }`}
                    >
                      {vote.result === "Negatived" ? "Failed" : vote.result ?? "Pending"}
                    </p>
                    <p className="text-sm text-slate-600">
                      {vote.yea_total} yes · {vote.nay_total} no
                    </p>
                  </div>
                </div>
              </Link>
            );
          })}
        </div>
      )}

      {votes ? (
        <Pagination
          total={votes.meta.total}
          limit={votes.meta.limit}
          offset={votes.meta.offset}
          basePath="/votes"
        />
      ) : null}
    </PageShell>
  );
}
