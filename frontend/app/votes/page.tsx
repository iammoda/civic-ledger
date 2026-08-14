import Link from "next/link";

import { DataGap } from "@/components/data-gap";
import { ExplainerStrip } from "@/components/explainer-strip";
import { LevelBadge } from "@/components/level-badge";
import { PageShell } from "@/components/page-shell";
import { Pagination } from "@/components/pagination";
import { listVotes } from "@/lib/api";
import { formatDate, humanizeMotion } from "@/lib/humanize";
import { voteActionLine } from "@/lib/vote-action";

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
            const isBill = Boolean(vote.bill_number);
            // Never headline a raw "An Act to…" — the one-liner explains better.
            const headline = isBill
              ? vote.bill_title && !vote.bill_title.toLowerCase().startsWith("an act")
                ? vote.bill_title
                : vote.bill_one_sentence ?? vote.bill_title ?? motion.headline
              : vote.plain_meaning_en ?? motion.headline;
            const subline = isBill && headline !== vote.bill_one_sentence ? vote.bill_one_sentence : null;
            const action = voteActionLine(vote);
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
                    <h2 className="mt-2 text-lg font-bold leading-7">{headline}</h2>
                    {subline ? (
                      <p className="mt-1 text-sm leading-6 text-slate-600">{subline}</p>
                    ) : null}
                    {action ? <p className="mt-1 text-xs font-medium text-slate-500">{action}</p> : null}
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
