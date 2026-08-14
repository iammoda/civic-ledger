import Link from "next/link";

import { DataGap } from "@/components/data-gap";
import { ExplainerStrip } from "@/components/explainer-strip";
import { LevelBadge } from "@/components/level-badge";
import { PageShell } from "@/components/page-shell";
import { Pagination } from "@/components/pagination";
import { listVotes } from "@/lib/api";
import { formatDate, humanizeMotion } from "@/lib/humanize";

export const metadata = { title: "What just happened in Parliament?" };

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
      title="What just happened?"
      description="Every recorded vote, translated into plain language — what was voted on, who won, and what happens next."
    >
      <ExplainerStrip id="votes">
        <span className="font-semibold">How voting works:</span> a bill must survive three readings in the
        House, then the Senate, to become law. MPs also vote on <span className="font-medium">motions</span> —
        statements or scheduling moves that aren&apos;t laws but show where each MP stands. Procedural motions
        can invert what Yes and No mean, so we spell out what each vote actually did.
      </ExplainerStrip>

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
            const motion = humanizeMotion(vote.description_en);
            return (
              <Link
                key={`${vote.chamber}-${vote.session}-${vote.number}`}
                href={`/votes/${vote.chamber}/${vote.session}/${vote.number}`}
                className="glass-card block p-4 transition hover:border-accent"
              >
                <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <LevelBadge level="federal" />
                      <span className="text-xs text-slate-500">
                        Vote {vote.number} · {formatDate(vote.occurred_on)}
                      </span>
                      {vote.bill_number ? (
                        <span className="rounded-md bg-slate-100 px-2 py-0.5 text-xs font-semibold text-slate-700">
                          {vote.bill_number}
                        </span>
                      ) : (
                        <span className="rounded-md bg-slate-100 px-2 py-0.5 text-xs text-slate-500">
                          Motion — not a bill
                        </span>
                      )}
                    </div>
                    {vote.bill_title ? (
                      <h2 className="mt-2 text-lg font-bold leading-7">{vote.bill_title}</h2>
                    ) : null}
                    {vote.bill_one_sentence ? (
                      <>
                        {/* What the bill is → what this vote did. */}
                        <p className="mt-1 truncate text-sm leading-6 text-slate-600">
                          {vote.bill_one_sentence}
                        </p>
                        <p className="mt-0.5 text-xs leading-5 text-slate-500">
                          {vote.plain_meaning_en ?? motion.headline}
                        </p>
                      </>
                    ) : (
                      <p className={vote.bill_title ? "mt-1 text-sm leading-6 text-slate-600" : "mt-2 text-lg font-bold leading-7"}>
                        {vote.plain_meaning_en ?? motion.headline}
                      </p>
                    )}
                    <p className="mt-0.5 truncate text-xs text-slate-400">{vote.description_en}</p>
                  </div>
                  <div className="shrink-0 text-left tabular-nums sm:text-right">
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
