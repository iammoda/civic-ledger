import Link from "next/link";
import { ReactNode } from "react";

import { DataGap } from "@/components/data-gap";
import { PageShell } from "@/components/page-shell";
import { Pagination } from "@/components/pagination";
import { SectionTabs, WHAT_HAPPENED_TABS } from "@/components/section-tabs";
import { VoteOutcome } from "@/components/viz/tally-bar";
import { listVotes, type VoteListItem } from "@/lib/api";
import { formatDateShort, humanizeMotion } from "@/lib/humanize";
import { voteActionLine } from "@/lib/vote-action";

export const metadata = { title: "What just happened in Parliament?" };

/** Substantive = tied to a bill. Pure motions are grouped and demoted. */
function isSubstantive(vote: VoteListItem): boolean {
  return Boolean(vote.bill_number);
}

function voteHeadline(vote: VoteListItem): { headline: string; subline: string | null } {
  const motion = humanizeMotion(vote.description_en);
  const isBill = Boolean(vote.bill_number);
  const headline = isBill
    ? vote.bill_title && !vote.bill_title.toLowerCase().startsWith("an act")
      ? vote.bill_title
      : vote.bill_one_sentence ?? vote.bill_title ?? motion.headline
    : vote.plain_meaning_en ?? motion.headline;
  const subline = isBill && headline !== vote.bill_one_sentence ? (vote.bill_one_sentence ?? null) : null;
  return { headline, subline };
}

function voteHref(vote: VoteListItem): string {
  return `/votes/${vote.chamber}/${vote.session}/${vote.number}`;
}

/** Full scoreboard row for a vote that matters. */
function VoteRow({ vote }: { vote: VoteListItem }) {
  const { headline, subline } = voteHeadline(vote);
  const action = voteActionLine(vote);
  const margin = Math.abs(vote.yea_total - vote.nay_total);
  const close = margin > 0 && margin <= 10;
  return (
    <Link href={voteHref(vote)} className="rule group grid gap-x-8 gap-y-2 py-6 md:grid-cols-[8.5rem_1fr_auto]">
      <div className="text-[13px] leading-5 text-slate-400">
        <p className="font-semibold text-slate-500">{vote.bill_number ?? "Motion"}</p>
        <p>{formatDateShort(vote.occurred_on)}</p>
        <p>Vote {vote.number}</p>
        {close ? <p className="mt-1 font-semibold text-amber-700">Close vote</p> : null}
      </div>
      <div className="min-w-0">
        <h2 className="font-serif text-xl font-bold leading-snug tracking-tight text-ink transition group-hover:text-accent sm:text-2xl">
          {headline}
        </h2>
        {subline ? <p className="mt-1.5 max-w-2xl text-sm leading-6 text-slate-500">{subline}</p> : null}
        {action ? <p className="mt-1.5 text-[13px] font-medium text-slate-500">{action}</p> : null}
      </div>
      <VoteOutcome result={vote.result} yea={vote.yea_total} nay={vote.nay_total} />
    </Link>
  );
}

/** Compact row for procedural motions inside the collapsed group. */
function MotionRow({ vote }: { vote: VoteListItem }) {
  const { headline } = voteHeadline(vote);
  const passed = vote.result === "Passed";
  return (
    <Link href={voteHref(vote)} className="rule group flex items-baseline justify-between gap-4 py-3">
      <p className="min-w-0 text-sm leading-6 text-slate-600 transition group-hover:text-accent">
        <span className="mr-3 text-xs text-slate-400">{formatDateShort(vote.occurred_on)}</span>
        {headline}
      </p>
      <p className={`stat-figure shrink-0 text-sm ${passed ? "text-teal-700" : "text-signal"}`}>
        {passed ? "Passed" : "Failed"} {vote.yea_total}–{vote.nay_total}
      </p>
    </Link>
  );
}

export default async function VotesPage({
  searchParams
}: {
  searchParams: Promise<{ offset?: string }>;
}) {
  const { offset } = await searchParams;
  const votes = await listVotes({ offset });

  // Split the list into segments: substantive votes render at full scale,
  // consecutive runs of procedural motions collapse into one quiet group.
  const segments: ReactNode[] = [];
  if (votes?.items.length) {
    let motionRun: VoteListItem[] = [];
    const flushMotions = () => {
      if (!motionRun.length) return;
      const run = motionRun;
      motionRun = [];
      if (run.length === 1) {
        segments.push(<MotionRow key={`m-${run[0].number}`} vote={run[0]} />);
        return;
      }
      segments.push(
        <details key={`group-${run[0].number}`} className="rule group/details py-4">
          <summary className="cursor-pointer list-none text-sm font-medium text-slate-500 transition hover:text-ink [&::-webkit-details-marker]:hidden">
            <span className="mr-2 inline-block transition group-open/details:rotate-90">▸</span>
            {run.length} procedural votes — scheduling and motions, not laws
          </summary>
          <div className="mt-2 border-t border-border/60 pl-5">
            {run.map((vote) => (
              <MotionRow key={`${vote.chamber}-${vote.session}-${vote.number}`} vote={vote} />
            ))}
          </div>
        </details>
      );
    };
    for (const vote of votes.items) {
      if (isSubstantive(vote)) {
        flushMotions();
        segments.push(<VoteRow key={`${vote.chamber}-${vote.session}-${vote.number}`} vote={vote} />);
      } else {
        motionRun.push(vote);
      }
    }
    flushMotions();
  }

  return (
    <PageShell
      eyebrow="What happened · Federal Parliament"
      title="What just happened?"
      description="Every recorded vote, translated into plain language — what was voted on, who won, and what happens next. Procedural motions are tucked away so the votes that matter stand out."
    >
      <SectionTabs tabs={WHAT_HAPPENED_TABS} ariaLabel="What happened sections" />

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
        <div>{segments}</div>
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
